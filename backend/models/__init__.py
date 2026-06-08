"""SQLAlchemy 2.0 ORM models.

The declarative :class:`Base` and the engine/session wiring live in
``backend.core.db`` (the ``conduit-fnd-db`` bead). It's re-exported here so the
domain-model beads can ``from backend.models import Base`` and declare their
tables (User, Article, Comment, Tag, ...) right next to where they live, while
still sharing the one metadata registry the rest of the app uses.
"""

from backend.core.db import Base

__all__ = ["Base"]
