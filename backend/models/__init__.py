"""SQLAlchemy 2.0 ORM models.

The declarative :class:`Base` and the engine/session wiring live in
``backend.core.db`` (the ``conduit-fnd-db`` bead). It's re-exported here so the
domain models share the one metadata registry the rest of the app uses, and so
callers can write ``from backend.models import Base, User, Article``.

Importing this package is what *registers* every model on ``Base.metadata`` —
which is exactly what Alembic autogenerate and ``Base.metadata.create_all``
need. So the side effect of pulling each model class into this namespace isn't
incidental; it's the point. Keep the imports here even though a linter might
call them "unused" (``__all__`` keeps it honest).
"""

from backend.core.db import Base
from backend.models.article import Article, Favorite, Tag, article_tags
from backend.models.comment import Comment
from backend.models.user import Follow, User

__all__ = [
    "Base",
    "User",
    "Follow",
    "Article",
    "Tag",
    "article_tags",
    "Comment",
    "Favorite",
]
