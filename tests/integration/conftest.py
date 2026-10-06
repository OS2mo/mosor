# SPDX-FileCopyrightText: Magenta ApS <https://magenta.dk>
# SPDX-License-Identifier: MPL-2.0
import pytest
from fastapi import FastAPI

from mo_sor.app import create_app


@pytest.fixture
async def app() -> FastAPI:
    """Override the FastRAMQPI `app` fixture.

    The FastRAMQPI `test_client`/`server` fixtures run this app under a real
    uvicorn server, so the GraphQL event system delivers MO events to it.
    """
    return create_app()
