from uuid import UUID

from .async_base_client import AsyncBaseClient
from .get_org_unit import GetOrgUnit
from .get_org_unit import GetOrgUnitOrgUnits


def gql(q: str) -> str:
    return q


class GraphQLClient(AsyncBaseClient):
    async def get_org_unit(self, uuid: UUID) -> GetOrgUnitOrgUnits:
        query = gql("""
            query GetOrgUnit($uuid: UUID!) {
              org_units(filter: {uuids: [$uuid]}) {
                objects {
                  current {
                    uuid
                    user_key
                    name
                  }
                }
              }
            }
            """)
        variables: dict[str, object] = {"uuid": uuid}
        response = await self.execute(query=query, variables=variables)
        data = self.get_data(response)
        return GetOrgUnit.parse_obj(data).org_units
