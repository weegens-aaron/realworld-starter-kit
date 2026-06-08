"""Cross-cutting concerns: configuration, security, shared dependencies."""

from backend.core.config import Settings, get_settings
from backend.core.db import (
    Base,
    DbSession,
    async_session_factory,
    create_engine,
    engine,
    get_db,
)
from backend.core.deps import (
    CurrentUser,
    OptionalUser,
    RequiredUser,
    get_current_user,
    get_optional_user,
)
from backend.core.errors import (
    APIError,
    ConflictError,
    ForbiddenError,
    GenericErrorModel,
    NotFoundError,
    UnauthorizedError,
    UnprocessableEntityError,
    register_exception_handlers,
)
from backend.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

__all__ = [
    "Settings",
    "get_settings",
    # database
    "Base",
    "DbSession",
    "async_session_factory",
    "create_engine",
    "engine",
    "get_db",
    # errors
    "APIError",
    "ConflictError",
    "ForbiddenError",
    "GenericErrorModel",
    "NotFoundError",
    "UnauthorizedError",
    "UnprocessableEntityError",
    "register_exception_handlers",
    # security
    "TokenError",
    "create_access_token",
    "decode_access_token",
    "hash_password",
    "verify_password",
    # dependencies
    "CurrentUser",
    "OptionalUser",
    "RequiredUser",
    "get_current_user",
    "get_optional_user",
]
