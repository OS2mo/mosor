# SPDX-FileCopyrightText: Magenta ApS <https://magenta.dk>
# SPDX-License-Identifier: MPL-2.0
from fastramqpi.config import Settings as FastRAMQPISettings
from pydantic import BaseSettings


class _Settings(BaseSettings):
    class Config:
        frozen = True
        env_nested_delimiter = "__"

    fastramqpi: FastRAMQPISettings

    # File names of SOR dumps in MO's EXPORTS file store, with the dump date
    # as `datetime.strptime` directives, e.g. SOR_Region_%d%m%y.csv.
    sor_file_pattern: str

    # SOR code of the dump's root row, the region. A dump with any other root
    # is rejected.
    sor_root_code: str

    # Name of the root unit in MO.
    sor_root_name: str = "SOR"

    # Refuse to ingest a dump that removes more units than this, unless forced.
    # Protects against a truncated dump terminating half the tree.
    sor_max_terminations: int = 10
