# SPDX-FileCopyrightText: Magenta ApS <https://magenta.dk>
# SPDX-License-Identifier: MPL-2.0
from uuid import UUID

import structlog
from fastapi import APIRouter
from fastramqpi.events import Event

from mo_sor import depends

router = APIRouter()
logger = structlog.stdlib.get_logger()


@router.post("/org_unit")
async def handle_mo_org_unit(
    settings: depends.Settings,
    mo: depends.GraphQLClient,
    event: Event[UUID],
) -> None:
    logger.info("MO org_unit event received", uuid=str(event.subject))
