from uuid import UUID

from .async_base_client import AsyncBaseClient
from .enums import FileStore
from .get_org_unit import GetOrgUnit
from .get_org_unit import GetOrgUnitOrgUnits
from .list_files import ListFiles
from .list_files import ListFilesFiles
from .read_file import ReadFile
from .read_file import ReadFileFiles


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

    async def list_files(self, file_store: FileStore) -> ListFilesFiles:
        query = gql("""
            query ListFiles($file_store: FileStore!) {
              files(filter: {file_store: $file_store}) {
                objects {
                  file_name
                }
              }
            }
            """)
        variables: dict[str, object] = {"file_store": file_store}
        response = await self.execute(query=query, variables=variables)
        data = self.get_data(response)
        return ListFiles.parse_obj(data).files

    async def read_file(self, file_store: FileStore, file_name: str) -> ReadFileFiles:
        query = gql("""
            query ReadFile($file_store: FileStore!, $file_name: String!) {
              files(filter: {file_store: $file_store, file_names: [$file_name]}) {
                objects {
                  text_contents
                }
              }
            }
            """)
        variables: dict[str, object] = {
            "file_store": file_store,
            "file_name": file_name,
        }
        response = await self.execute(query=query, variables=variables)
        data = self.get_data(response)
        return ReadFile.parse_obj(data).files
