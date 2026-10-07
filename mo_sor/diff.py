# SPDX-FileCopyrightText: Magenta ApS <https://magenta.dk>
# SPDX-License-Identifier: MPL-2.0
from pydantic import BaseModel

from mo_sor.sor_file import SorUnit


class Diff(BaseModel, frozen=True):
    added: set[str]
    changed: set[str]
    removed: set[str]

    @property
    def codes(self) -> set[str]:
        return self.added | self.changed | self.removed


def diff(old: dict[str, SorUnit] | None, new: dict[str, SorUnit]) -> Diff:
    """Find the SOR codes that differ between two dumps.

    Without a previous dump, every unit in the new dump is added.
    """
    old = old or {}
    common = old.keys() & new.keys()
    return Diff(
        added=new.keys() - old.keys(),
        changed={code for code in common if old[code] != new[code]},
        removed=old.keys() - new.keys(),
    )
