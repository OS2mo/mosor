# SPDX-FileCopyrightText: Magenta ApS <https://magenta.dk>
# SPDX-License-Identifier: MPL-2.0
"""Build SOR dumps for tests."""

import csv
import io

NIV_COLUMNS = [f"Niv{i}" for i in range(1, 9)]
COLUMNS = [
    "CodeSOR",
    "ParentCodeSOR",
    "FromDate",
    "ToDate",
    "Name",
    "Type",
    "Level",
    *NIV_COLUMNS,
]

Row = dict[str, str]


def row(
    code: str,
    parent: str = "",
    from_date: str = "20150730",
    name: str = "Unit",
    type_: str = "klinisk enhed",
    level: int | str = 1,
) -> Row:
    """Build a row like those in a real dump. `dump` fills in the Niv columns."""
    return {
        "CodeSOR": code,
        "ParentCodeSOR": parent,
        "FromDate": f"{from_date} 00:00:00 ",
        "ToDate": "99991231 23:59:00 ",
        "Name": name,
        "Type": type_,
        "Level": str(level),
    }


def dump(*rows: Row, columns: list[str] = COLUMNS) -> str:
    """Build a dump the way SOR delivers it: UTF-8 BOM and CRLF."""
    by_code = {r["CodeSOR"]: r for r in rows}
    out = io.StringIO()
    writer = csv.DictWriter(
        out,
        columns,
        delimiter=";",
        lineterminator="\r\n",
        restval="",
        extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows({**r, **_niv(r, by_code)} for r in rows)
    return "\ufeff" + out.getvalue()


def _niv(unit: Row, by_code: dict[str, Row]) -> Row:
    """The Niv columns of a row, as in a real dump.

    Niv1 is always "SOR", and Niv2 onwards are the names from just below the
    root down to the unit itself. The parser ignores these columns; they are
    only filled in so test dumps look like real ones. Some test dumps are
    broken on purpose (unknown parents, cycles), so the path stops where it
    can no longer be followed.
    """
    names: list[str] = []
    node: Row | None = unit
    # Bounded, so a cycle cannot loop forever
    while node and node["ParentCodeSOR"] and len(names) < len(NIV_COLUMNS) - 1:
        names.append(node["Name"])
        node = by_code.get(node["ParentCodeSOR"])
    return dict(zip(NIV_COLUMNS, ["SOR", *reversed(names)]))
