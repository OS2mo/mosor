# SPDX-FileCopyrightText: Magenta ApS <https://magenta.dk>
# SPDX-License-Identifier: MPL-2.0
from datetime import date
from uuid import UUID

import pytest

from mo_sor import sor_file
from mo_sor.sor_file import InvalidSorFile
from mo_sor.sor_file import SorUnit
from mo_sor.sor_file import code_to_uuid
from tests.sor_dumps import COLUMNS
from tests.sor_dumps import dump
from tests.sor_dumps import row

# Made-up codes in the shape of real ones, with valid check digits
ROOT = "1001000016005"
CHILD = "100001000016006"
GRANDCHILD = "1000001000016004"

NOT_A_CODE = r'string does not match regex "^[1-9]\d*100001600\d$"'


def parse_dump(text: str) -> dict[str, SorUnit]:
    return sor_file.parse(text, root_code=ROOT, root_name="SOR")


def tree(
    root_from: str = "20150730",
    child_from: str = "20150730",
    grandchild_from: str = "20150730",
) -> str:
    return dump(
        row(ROOT, name="Region", type_="region", from_date=root_from),
        row(CHILD, ROOT, name="Område", from_date=child_from, level=2),
        row(GRANDCHILD, CHILD, name="Afdeling", from_date=grandchild_from, level=3),
    )


def test_root_is_configurable() -> None:
    """Every region has its own root."""
    units = sor_file.parse(dump(row(CHILD)), root_code=CHILD, root_name="Region Nord")
    assert units[CHILD].name == "Region Nord"

    with pytest.raises(InvalidSorFile):
        sor_file.parse(dump(row(ROOT)), root_code=CHILD, root_name="SOR")


def test_parse() -> None:
    units = parse_dump(tree(child_from="20200101"))

    assert units == {
        ROOT: SorUnit(
            code=ROOT,
            parent_code=None,
            name="SOR",
            type="region",
            level=1,
            start=date(2015, 7, 30),
        ),
        CHILD: SorUnit(
            code=CHILD,
            parent_code=ROOT,
            name="Område",
            type="klinisk enhed",
            level=2,
            start=date(2020, 1, 1),
        ),
        GRANDCHILD: SorUnit(
            code=GRANDCHILD,
            parent_code=CHILD,
            name="Afdeling",
            type="klinisk enhed",
            level=3,
            start=date(2020, 1, 1),
        ),
    }


def test_parse_without_bom_and_crlf() -> None:
    text = dump(row(ROOT), row(CHILD, ROOT, level=2))
    text = text.removeprefix("\ufeff").replace("\r\n", "\n")
    assert parse_dump(text).keys() == {ROOT, CHILD}


def test_uuids_match_the_importer() -> None:
    """UUIDs are derived like in the one-off importer, which created the units.

    Changing how they are derived would make MO's existing units unreachable.
    """
    assert code_to_uuid(ROOT) == UUID("6a1ff8b2-63c5-57f6-a4e2-82a442030303")
    units = parse_dump(tree())
    assert units[CHILD].uuid == code_to_uuid(CHILD)
    assert units[CHILD].parent_uuid == code_to_uuid(ROOT)
    assert units[ROOT].parent_uuid is None


def test_start_is_clamped_to_parent_start() -> None:
    """MO rejects a unit that starts before its parent.

    The clamp carries down the tree: the grandchild starts no earlier than the
    child's clamped start.
    """
    units = parse_dump(
        tree(root_from="20150730", child_from="20250109", grandchild_from="20150730")
    )
    assert units[ROOT].start == date(2015, 7, 30)
    assert units[CHILD].start == date(2025, 1, 9)
    assert units[GRANDCHILD].start == date(2025, 1, 9)


def test_start_after_parent_is_kept() -> None:
    units = parse_dump(tree(grandchild_from="20260501"))
    assert units[GRANDCHILD].start == date(2026, 5, 1)


def test_rows_in_any_order() -> None:
    text = dump(
        row(GRANDCHILD, CHILD, level=3),
        row(CHILD, ROOT, level=2),
        row(ROOT),
    )
    assert parse_dump(text).keys() == {ROOT, CHILD, GRANDCHILD}


def test_names_and_codes_are_stripped() -> None:
    text = dump(row(ROOT), row(f" {CHILD} ", f"{ROOT} ", name=" Afdeling ", level=2))
    assert parse_dump(text)[CHILD].name == "Afdeling"
    assert parse_dump(text)[CHILD].parent_code == ROOT


@pytest.mark.parametrize(
    "text,error",
    [
        pytest.param(
            dump(row(ROOT), columns=[c for c in COLUMNS if c != "Level"]),
            "missing columns: ['Level']",
            id="missing-column",
        ),
        pytest.param(
            dump(row(ROOT), row("1.00100001601E+12", ROOT, level=2)),
            f"line 3: CodeSOR '1.00100001601E+12': {NOT_A_CODE}",
            id="code-in-scientific-notation",
        ),
        pytest.param(
            # GRANDCHILD as Excel saves it: Excel keeps 15 significant digits and
            # zeroes the 16th. The code still has the right shape, so only the
            # check digit catches it.
            dump(row(ROOT), row(f"{GRANDCHILD[:-1]}0", ROOT, level=2)),
            f"line 3: CodeSOR '{GRANDCHILD[:-1]}0': invalid check digit",
            id="excel-zeroed-check-digit",
        ),
        pytest.param(
            # ROOT with the last digit changed from 5 to 6, as the parent
            dump(row(ROOT), row(CHILD, "1001000016006", level=2)),
            "line 3: ParentCodeSOR '1001000016006': invalid check digit",
            id="wrong-check-digit-in-parent",
        ),
        pytest.param(
            dump(row(ROOT), row("123", ROOT, level=2)),
            f"line 3: CodeSOR '123': {NOT_A_CODE}",
            id="code-too-short",
        ),
        pytest.param(
            dump(row(ROOT), row("1234567890123", ROOT, level=2)),
            f"line 3: CodeSOR '1234567890123': {NOT_A_CODE}",
            id="code-without-sor-namespace",
        ),
        pytest.param(
            dump(row(ROOT), row(CHILD, "abc", level=2)),
            f"line 3: ParentCodeSOR 'abc': {NOT_A_CODE}",
            id="invalid-parent-code",
        ),
        pytest.param(
            dump(row(ROOT), row(CHILD, ROOT, from_date="2015-07-30", level=2)),
            "line 3: FromDate '2015-07-30 00:00:00 ': time data '2015-07-30 00:00:00'"
            " does not match format '%Y%m%d %H:%M:%S'",
            id="invalid-date",
        ),
        pytest.param(
            # The reader fills the missing columns of a short row with None
            dump(row(ROOT)) + f"{CHILD};{ROOT}\r\n",
            "line 3: FromDate None: none is not an allowed value",
            id="truncated-row",
        ),
        pytest.param(
            dump(row(ROOT), row(CHILD, ROOT, level="x")),
            "line 3: Level 'x': value is not a valid integer",
            id="non-numeric-level",
        ),
        pytest.param(
            dump(row(ROOT), row(CHILD, ROOT, level=0)),
            "line 3: Level '0': ensure this value is greater than or equal to 1",
            id="level-not-positive",
        ),
        pytest.param(
            dump(row(ROOT), row(CHILD, ROOT, name=" ", level=2)),
            "line 3: Name ' ': ensure this value has at least 1 characters",
            id="empty-name",
        ),
        pytest.param(
            dump(row(ROOT), row(CHILD, ROOT, type_="", level=2)),
            "line 3: Type '': ensure this value has at least 1 characters",
            id="empty-type",
        ),
        pytest.param(
            dump(row(ROOT), row(CHILD, ROOT, level=2), row(CHILD, ROOT, level=2)),
            f"line 4: duplicate CodeSOR {CHILD}",
            id="duplicate-code",
        ),
        pytest.param(
            dump(row(ROOT), row(CHILD, GRANDCHILD, level=2)),
            f"line 3: unknown parent {GRANDCHILD}",
            id="unknown-parent",
        ),
        pytest.param(
            dump(row(CHILD)),
            f"the root {ROOT} is not in the dump",
            id="wrong-root",
        ),
        pytest.param(
            dump(row(ROOT), row(CHILD)),
            "line 3: ParentCodeSOR is empty",
            id="two-roots",
        ),
        pytest.param(
            dump(row(CHILD), row(ROOT, CHILD, level=2)),
            "line 3: the root has a ParentCodeSOR",
            id="root-has-parent",
        ),
        pytest.param(
            dump(row(ROOT, level=2)),
            "line 2: the root has Level 2",
            id="root-not-level-1",
        ),
        pytest.param(
            dump(row(ROOT), row(CHILD, ROOT, level=3)),
            "line 3: Level 3 under parent with Level 1",
            id="level-skips",
        ),
        pytest.param(
            # A cycle cannot satisfy level = parent level + 1
            dump(
                row(ROOT),
                row(CHILD, GRANDCHILD, level=2),
                row(GRANDCHILD, CHILD, level=3),
            ),
            "line 3: Level 2 under parent with Level 3",
            id="cycle",
        ),
    ],
)
def test_invalid_dump_is_rejected(text: str, error: str) -> None:
    with pytest.raises(InvalidSorFile) as exc_info:
        parse_dump(text)
    assert error in exc_info.value.errors


def test_all_errors_are_collected() -> None:
    text = dump(row(ROOT), row("1", ROOT, level=2), row("2", ROOT, level=2))
    with pytest.raises(InvalidSorFile) as exc_info:
        parse_dump(text)
    assert exc_info.value.errors == [
        f"line 3: CodeSOR '1': {NOT_A_CODE}",
        f"line 4: CodeSOR '2': {NOT_A_CODE}",
    ]


def test_line_numbers_count_blank_lines() -> None:
    """Errors point at the right line in the file, even after a blank line."""
    lines = dump(row(ROOT), row("123", ROOT, level=2)).split("\r\n")
    text = "\r\n".join([*lines[:2], "", *lines[2:]])
    with pytest.raises(InvalidSorFile) as exc_info:
        parse_dump(text)
    assert exc_info.value.errors == [f"line 4: CodeSOR '123': {NOT_A_CODE}"]
