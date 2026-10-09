# SPDX-FileCopyrightText: Magenta ApS <https://magenta.dk>
# SPDX-License-Identifier: MPL-2.0
import pytest
from httpx import AsyncClient


@pytest.mark.integration_test
async def test_ready(test_client: AsyncClient) -> None:
    r = await test_client.get("/health/ready")
    assert r.status_code == 200, r.json()
