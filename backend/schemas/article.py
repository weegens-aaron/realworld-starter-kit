"""Article schemas: the entity, its envelopes, and write payloads.

The serialized :class:`ArticleSchema` is the spec's full article shape —
including the three computed/viewer-relative bits a bare ORM row doesn't carry
verbatim:

* ``tagList`` — the article's tag *names* (``[t.name for t in article.tags]``).
* ``favorited`` — does *this viewer* favorite it? (per-request, not stored).
* ``favoritesCount`` — how many users favorite it (the ``favorites_count``
  column property on the model, computed in SQL).

Because those depend on the viewer and on eagerly-loaded relationships,
:meth:`ArticleSchema.from_article` takes them as explicit keyword args rather
than guessing — the service layer (which owns the query) passes what it loaded.
That keeps the serializer honest and dodges async lazy-load surprises.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import Field

from backend.schemas.base import Schema
from backend.schemas.user import ProfileSchema

if TYPE_CHECKING:
    from backend.models import Article


class ArticleSchema(Schema):
    """A single article in full RealWorld shape (author embedded as profile)."""

    slug: str
    title: str
    description: str
    body: str
    tag_list: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    favorited: bool = False
    favorites_count: int = 0
    author: ProfileSchema

    @classmethod
    def from_article(
        cls,
        article: Article,
        *,
        author: ProfileSchema,
        favorited: bool = False,
        favorites_count: int = 0,
    ) -> ArticleSchema:
        """Build from an ORM article + viewer-relative facts.

        ``article.tags`` must be loaded (the caller's query is responsible for
        eager-loading it); ``favorited`` and ``favorites_count`` are supplied by
        the service since they depend on the requesting user / a SQL count.
        """
        return cls(
            slug=article.slug,
            title=article.title,
            description=article.description,
            body=article.body,
            tag_list=[tag.name for tag in article.tags],
            created_at=article.created_at,
            updated_at=article.updated_at,
            favorited=favorited,
            favorites_count=favorites_count,
            author=author,
        )


# --------------------------------------------------------------------------- #
# Response envelopes
# --------------------------------------------------------------------------- #
class ArticleResponse(Schema):
    """``{"article": {...}}`` — single-article wrapper."""

    article: ArticleSchema


class MultipleArticlesResponse(Schema):
    """``{"articles": [...], "articlesCount": N}`` — list + total wrapper.

    ``articlesCount`` is the *total* matching the query (for pagination), not
    ``len(articles)`` on the returned page — the service supplies it.
    """

    articles: list[ArticleSchema]
    articles_count: int


# --------------------------------------------------------------------------- #
# Request bodies (mirrors of openapi.yml)
# --------------------------------------------------------------------------- #
class NewArticle(Schema):
    """Create payload inner: ``{title, description, body, tagList?}``."""

    title: str
    description: str
    body: str
    tag_list: list[str] = Field(default_factory=list)


class NewArticleRequest(Schema):
    article: NewArticle


class UpdateArticle(Schema):
    """Update payload inner — all optional; absent keys mean "leave as-is"."""

    title: str | None = None
    description: str | None = None
    body: str | None = None


class UpdateArticleRequest(Schema):
    article: UpdateArticle
