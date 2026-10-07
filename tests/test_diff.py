# SPDX-FileCopyrightText: Magenta ApS <https://magenta.dk>
# SPDX-License-Identifier: MPL-2.0
from datetime import date

from mo_sor.diff import Diff
from mo_sor.diff import diff
from mo_sor.sor_file import SorUnit

# Made-up codes in the shape of real ones, with valid check digits
ROOT = SorUnit(
    code="1001000016005",
    parent_code=None,
    name="SOR",
    type="region",
    level=1,
    start=date(2015, 7, 30),
)
A = SorUnit(
    code="100001000016006",
    parent_code=ROOT.code,
    name="A",
    type="klinisk enhed",
    level=2,
    start=date(2015, 7, 30),
)
B = A.copy(update={"code": "1000001000016004", "name": "B"})


def units(*units: SorUnit) -> dict[str, SorUnit]:
    return {unit.code: unit for unit in units}


def test_no_previous_dump_means_everything_is_added() -> None:
    assert diff(None, units(ROOT, A)) == Diff(
        added={ROOT.code, A.code}, changed=set(), removed=set()
    )


def test_identical_dumps() -> None:
    assert diff(units(ROOT, A), units(ROOT, A)) == Diff(
        added=set(), changed=set(), removed=set()
    )


def test_added_and_removed() -> None:
    assert diff(units(ROOT, A), units(ROOT, B)) == Diff(
        added={B.code}, changed=set(), removed={A.code}
    )


def test_changed() -> None:
    old = units(ROOT, A, B)
    new = units(
        ROOT,
        A.copy(update={"name": "Renamed"}),
        B.copy(update={"start": date(2025, 1, 9)}),
    )
    assert diff(old, new) == Diff(added=set(), changed={A.code, B.code}, removed=set())


def test_codes() -> None:
    d = Diff(added={"1"}, changed={"2"}, removed={"3"})
    assert d.codes == {"1", "2", "3"}
