"""Application-facing persistence ports."""

from typing import Protocol, TypeVar

EntityT = TypeVar("EntityT")
IdentifierT = TypeVar("IdentifierT", contravariant=True)


class Repository(Protocol[EntityT, IdentifierT]):
    """Minimal repository contract; domain-specific ports will extend it."""

    async def get(self, identifier: IdentifierT) -> EntityT | None: ...

    async def add(self, entity: EntityT) -> None: ...
