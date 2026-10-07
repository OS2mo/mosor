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
