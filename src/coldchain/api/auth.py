"""Explicit local-development identity boundary."""

from fastapi import Request

from coldchain.application.interfaces import Identity
from coldchain.application.workflow import AuthorizationError
from coldchain.config import Settings


def local_identity(request: Request) -> Identity:
    settings: Settings = request.app.state.settings
    if settings.environment not in {"local", "test"}:
        raise AuthorizationError("local identity headers are disabled outside development")
    actor_id = request.headers.get("X-Actor-ID", "").strip()
    roles = frozenset(
        role.strip().lower()
        for role in request.headers.get("X-Actor-Roles", "").split(",")
        if role.strip()
    )
    if not actor_id:
        raise AuthorizationError("authenticated actor identity is required")
    return Identity(actor_id=actor_id, roles=roles)
