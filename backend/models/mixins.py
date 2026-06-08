"""Reusable mapped-column mixins shared across ORM models.

Right now there's exactly one: :class:`TimestampMixin`, which stamps a row's
``created_at`` / ``updated_at`` the way RealWorld's payloads expect (ISO-8601,
timezone-aware). Article and Comment both carry timestamps, so factoring the
two columns into a mixin keeps the definition in one place (DRY) instead of
copy-pasting the same ``server_default`` / ``onupdate`` dance per table.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """Adds timezone-aware ``created_at`` / ``updated_at`` columns.

    The defaults are computed *by the database* (``func.now()``), so a row gets
    sane timestamps even if it's inserted by something other than the ORM (a
    raw migration, say). ``updated_at`` additionally refreshes on every UPDATE
    via ``onupdate`` — again at the SQL layer — so it can't drift just because a
    caller forgot to touch it.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
