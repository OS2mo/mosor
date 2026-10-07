# SPDX-FileCopyrightText: Magenta ApS <https://magenta.dk>
# SPDX-License-Identifier: MPL-2.0
from datetime import date

import pytest

from mo_sor.dumps import dump_date

PATTERN = "SOR_Region_%d%m%y.csv"


@pytest.mark.parametrize(
    "file_name,expected",
    [
        pytest.param("SOR_Region_300426.csv", date(2026, 4, 30), id="dump"),
        pytest.param("SOR_Region_010526.csv", date(2026, 5, 1), id="leading-zeros"),
        pytest.param("SOR_Region_udtraek.csv", None, id="no-date"),
        pytest.param("sor_report.csv", None, id="other-file"),
        pytest.param("SOR_Region_310226.csv", None, id="invalid-date"),
    ],
)
def test_dump_date(file_name: str, expected: date | None) -> None:
    assert dump_date(file_name, PATTERN) == expected
