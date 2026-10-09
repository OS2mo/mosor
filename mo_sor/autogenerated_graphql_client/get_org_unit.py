from typing import Optional
from uuid import UUID

from .base_model import BaseModel


class GetOrgUnit(BaseModel):
    org_units: "GetOrgUnitOrgUnits"


class GetOrgUnitOrgUnits(BaseModel):
    objects: list["GetOrgUnitOrgUnitsObjects"]


class GetOrgUnitOrgUnitsObjects(BaseModel):
    current: Optional["GetOrgUnitOrgUnitsObjectsCurrent"]


class GetOrgUnitOrgUnitsObjectsCurrent(BaseModel):
    uuid: UUID
    user_key: str
    name: str


GetOrgUnit.update_forward_refs()
GetOrgUnitOrgUnits.update_forward_refs()
GetOrgUnitOrgUnitsObjects.update_forward_refs()
GetOrgUnitOrgUnitsObjectsCurrent.update_forward_refs()
