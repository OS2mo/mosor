# SPDX-FileCopyrightText: Magenta ApS <https://magenta.dk>
# SPDX-License-Identifier: MPL-2.0
from uuid import uuid4

import pytest
from fastapi.encoders import jsonable_encoder
from fastramqpi.events import Event
from httpx import AsyncClient
from structlog.testing import capture_logs


@pytest.mark.integration_test
async def test_org_unit_event(test_client: AsyncClient) -> None:
    uuid = uuid4()

    with capture_logs() as cap_logs:
        r = await test_client.post(
            "/org_unit",
            json=jsonable_encoder(Event(subject=uuid, priority=1)),
        )
    r.raise_for_status()

    assert {
        "event": "MO org_unit event received",
        "uuid": str(uuid),
        "log_level": "info",
    } in cap_logs
