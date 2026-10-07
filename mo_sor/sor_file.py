# SPDX-FileCopyrightText: Magenta ApS <https://magenta.dk>
# SPDX-License-Identifier: MPL-2.0
"""Parsing and validation of SOR dumps.

A dump is a semicolon-separated CSV file (UTF-8 with BOM, CRLF) with one row
per SOR unit. Parsing is strict: a dump that fails validation is rejected as a
whole, so a broken file never reaches MO.
"""

import csv
import io
from datetime import date
from datetime import datetime
from typing import Any
from uuid import NAMESPACE_URL
from uuid import UUID
from uuid import uuid5

from pydantic import BaseModel
from pydantic import Field
from pydantic import ValidationError
from pydantic import validator

# Same namespace as the one-off importer, so the UUIDs match the units it
# created.
SOR_NAMESPACE = uuid5(NAMESPACE_URL, "sor.dk")

# A SOR ID is a running number, the SOR namespace 1000016, the partition ID 00
# and a check digit, see Sundhedsdatastyrelsen's "Info om opbygningen af
# SOR-ID'er". There is no maximum length, as the running number keeps growing.
CODE_PATTERN = r"^[1-9]\d*100001600\d$"
DATE_FORMAT = "%Y%m%d %H:%M:%S"


# The last digit of a SOR ID is a check digit, computed with the Verhoeff
# algorithm (https://en.wikipedia.org/wiki/Verhoeff_algorithm), see
# Sundhedsdatastyrelsen's "Info om opbygningen af SOR-ID'er". It detects any
# single changed digit and any swap of two adjacent digits.
#
# These are the algorithm's standard tables: D combines two digits, P mixes a
# digit depending on its position.
_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def has_valid_check_digit(code: str) -> bool:
    """Check the check digit of a code of digits.

    The check digit catches codes mangled by Excel, which keeps 15 significant
    digits and zeroes the rest.
    """
    # Fold the digits right to left, starting at 0. The check digit is chosen
    # so that a valid code ends at 0.
    checksum = 0
    for i, digit in enumerate(reversed(code)):
        checksum = _VERHOEFF_D[checksum][_VERHOEFF_P[i % 8][int(digit)]]
    return checksum == 0


def code_to_uuid(code: str) -> UUID:
    return uuid5(SOR_NAMESPACE, code)


class InvalidSorFile(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__(errors)
        self.errors = errors


class SorRow(BaseModel, frozen=True, anystr_strip_whitespace=True):
    """A row in a SOR dump.

    Fields with an alias are the dump's columns; columns not listed here are
    ignored.
    """

    # Line in the dump, for error messages
    line: int
    code: str = Field(alias="CodeSOR", regex=CODE_PATTERN)
    # Empty for the root
    parent_code: str | None = Field(alias="ParentCodeSOR", regex=CODE_PATTERN)
    from_date: date = Field(alias="FromDate")
    name: str = Field(alias="Name", min_length=1)
    type: str = Field(alias="Type", min_length=1)
    level: int = Field(alias="Level", ge=1)

    @validator("parent_code", pre=True)
    def empty_parent_is_none(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @validator("from_date", pre=True)
    def parse_sor_date(cls, v: Any) -> Any:
        if isinstance(v, str):
            # Only the date is used, so the missing timezone does not matter
            return datetime.strptime(v.strip(), DATE_FORMAT).date()  # noqa: DTZ007
        return v

    @validator("code", "parent_code")
    def check_digit(cls, v: str | None) -> str | None:
        if v is not None and not has_valid_check_digit(v):
            raise ValueError("invalid check digit")
        return v


class SorUnit(BaseModel, frozen=True):
    """A unit as it should be in MO."""

    code: str
    parent_code: str | None
    name: str
    type: str
    level: int
    # FromDate clamped to the parent's start, as MO rejects a unit that starts
    # before its parent.
    start: date

    @property
    def uuid(self) -> UUID:
        return code_to_uuid(self.code)

    @property
    def parent_uuid(self) -> UUID | None:
        if self.parent_code is None:
            return None
        return code_to_uuid(self.parent_code)


def _read_rows(text: str) -> dict[str, SorRow]:
    reader = csv.DictReader(
        io.StringIO(text.removeprefix("\ufeff"), newline=""), delimiter=";"
    )
    required = {f.alias for f in SorRow.__fields__.values() if f.has_alias}
    missing = required - set(reader.fieldnames or [])
    if missing:
        raise InvalidSorFile([f"missing columns: {sorted(missing)}"])

    errors: list[str] = []
    rows: dict[str, SorRow] = {}
    for raw in reader:
        # Counts lines in the file, including blank lines the reader skips
        line = reader.line_num
        try:
            row = SorRow.parse_obj({**raw, "line": line})
        except ValidationError as e:
            for error in e.errors():
                column = error["loc"][0]
                errors.append(f"line {line}: {column} {raw[column]!r}: {error['msg']}")
            continue
        if row.code in rows:
            errors.append(f"line {line}: duplicate CodeSOR {row.code}")
            continue
        rows[row.code] = row
    if errors:
        raise InvalidSorFile(errors)
    return rows


def _check_tree(rows: dict[str, SorRow], root_code: str) -> None:
    errors = []
    if root_code not in rows:
        errors.append(f"the root {root_code} is not in the dump")
    for row in rows.values():
        if row.code == root_code:
            if row.parent_code is not None:
                errors.append(f"line {row.line}: the root has a ParentCodeSOR")
            elif row.level != 1:
                errors.append(f"line {row.line}: the root has Level {row.level}")
            continue
        if row.parent_code is None:
            errors.append(f"line {row.line}: ParentCodeSOR is empty")
            continue
        parent = rows.get(row.parent_code)
        if parent is None:
            errors.append(f"line {row.line}: unknown parent {row.parent_code}")
        # Levels strictly increasing down the tree also rules out cycles
        elif row.level != parent.level + 1:
            errors.append(
                f"line {row.line}: Level {row.level} under parent with Level"
                f" {parent.level}"
            )
    if errors:
        raise InvalidSorFile(errors)


def parse(text: str, root_code: str, root_name: str) -> dict[str, SorUnit]:
    """Parse and validate a SOR dump.

    The dump has a single root row, the region. Like the one-off importer,
    we use it as the root unit in MO instead of creating an extra unit
    above it.

    Args:
        text: The dump.
        root_code: SOR code of the root row. A dump with any other root is
            rejected.
        root_name: Name of the root unit in MO.

    Returns:
        The units in the dump, keyed by SOR code.

    Raises:
        InvalidSorFile: If the dump fails validation.
    """
    rows = _read_rows(text)
    _check_tree(rows, root_code)

    # Top-down, so each parent's start is known before its children's
    units: dict[str, SorUnit] = {}
    for row in sorted(rows.values(), key=lambda r: r.level):
        start = row.from_date
        if row.parent_code is not None:
            start = max(start, units[row.parent_code].start)
        units[row.code] = SorUnit(
            code=row.code,
            parent_code=row.parent_code,
            name=root_name if row.code == root_code else row.name,
            type=row.type,
            level=row.level,
            start=start,
        )
    return units
