"""Tests for the Pydantic request/response schemas.

These assert the *contract*, not the plumbing: the exact serialized field sets
(camelCase keys), the empty-string -> null normalization for bio/image, and
that the ``from_*`` ORM factories project the right shapes — including the
viewer-relative ``following`` / ``favorited`` / ``favoritesCount`` bits.

The ORM factory tests build *transient* model instances (no DB session) and
hand the relationship/computed values in explicitly, mirroring how a service
would call them after eager-loading.
"""

from __future__ import annotations

from datetime import UTC, datetime

from backend.models import Article, Comment, Tag, User
from backend.schemas import (
    ArticleResponse,
    ArticleSchema,
    CommentSchema,
    MultipleArticlesResponse,
    MultipleCommentsResponse,
    NewArticleRequest,
    ProfileResponse,
    ProfileSchema,
    TagsResponse,
    UserResponse,
    UserSchema,
)

_NOW = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)


# --------------------------------------------------------------------------- #
# Null normalization
# --------------------------------------------------------------------------- #
def test_blank_bio_image_normalize_to_none():
    """Empty / whitespace-only bio & image collapse to ``None``."""
    user = UserSchema(email="e@x.io", token="tok", username="bob", bio="", image="   ")
    assert user.bio is None
    assert user.image is None

    profile = ProfileSchema(username="bob", bio="", image="\t\n")
    assert profile.bio is None
    assert profile.image is None


def test_nonblank_bio_image_preserved():
    profile = ProfileSchema(username="bob", bio="hi", image="http://img")
    assert profile.bio == "hi"
    assert profile.image == "http://img"


# --------------------------------------------------------------------------- #
# Exact serialized field sets + camelCase aliases
# --------------------------------------------------------------------------- #
def test_user_response_field_set():
    body = UserResponse(
        user=UserSchema(email="e@x.io", token="tok", username="bob", bio=None, image=None)
    )
    dumped = body.model_dump(by_alias=True)
    assert set(dumped) == {"user"}
    assert set(dumped["user"]) == {"email", "token", "username", "bio", "image"}


def test_profile_response_field_set():
    body = ProfileResponse(profile=ProfileSchema(username="bob", following=True))
    dumped = body.model_dump(by_alias=True)
    assert set(dumped) == {"profile"}
    assert set(dumped["profile"]) == {"username", "bio", "image", "following"}
    assert dumped["profile"]["following"] is True


def test_article_response_camelcase_field_set():
    author = ProfileSchema(username="bob", following=False)
    article = ArticleSchema(
        slug="how-to-train",
        title="How to train",
        description="ever wonder?",
        body="...",
        tag_list=["dragons", "training"],
        created_at=_NOW,
        updated_at=_NOW,
        favorited=True,
        favorites_count=3,
        author=author,
    )
    dumped = ArticleResponse(article=article).model_dump(by_alias=True)
    assert set(dumped) == {"article"}
    assert set(dumped["article"]) == {
        "slug",
        "title",
        "description",
        "body",
        "tagList",
        "createdAt",
        "updatedAt",
        "favorited",
        "favoritesCount",
        "author",
    }
    assert dumped["article"]["tagList"] == ["dragons", "training"]
    assert dumped["article"]["favoritesCount"] == 3


def test_multiple_articles_envelope_keys():
    dumped = MultipleArticlesResponse(articles=[], articles_count=0).model_dump(by_alias=True)
    assert set(dumped) == {"articles", "articlesCount"}
    assert dumped["articlesCount"] == 0


def test_comment_envelopes():
    author = ProfileSchema(username="bob")
    comment = CommentSchema(id=1, created_at=_NOW, updated_at=_NOW, body="nice", author=author)
    single = comment.model_dump(by_alias=True)
    assert set(single) == {"id", "createdAt", "updatedAt", "body", "author"}

    many = MultipleCommentsResponse(comments=[comment]).model_dump(by_alias=True)
    assert set(many) == {"comments"}


def test_tags_envelope():
    dumped = TagsResponse(tags=["dragons", "training"]).model_dump(by_alias=True)
    assert dumped == {"tags": ["dragons", "training"]}


# --------------------------------------------------------------------------- #
# Inbound camelCase accepted (populate_by_name + alias)
# --------------------------------------------------------------------------- #
def test_new_article_request_accepts_camelcase():
    req = NewArticleRequest.model_validate(
        {"article": {"title": "t", "description": "d", "body": "b", "tagList": ["x"]}}
    )
    assert req.article.tag_list == ["x"]


def test_new_article_request_accepts_snake_case():
    req = NewArticleRequest.model_validate(
        {"article": {"title": "t", "description": "d", "body": "b", "tag_list": ["x"]}}
    )
    assert req.article.tag_list == ["x"]


# --------------------------------------------------------------------------- #
# ORM factories
# --------------------------------------------------------------------------- #
def test_user_schema_from_user_normalizes_and_embeds_token():
    user = User(username="bob", email="e@x.io", bio="", image=None, password_hash="x")
    schema = UserSchema.from_user(user, token="jwt-123")
    assert schema.token == "jwt-123"
    assert schema.email == "e@x.io"
    assert schema.bio is None  # "" normalized


def test_profile_schema_from_user_following_flag():
    user = User(username="bob", email="e@x.io", bio="hi", image=None, password_hash="x")
    schema = ProfileSchema.from_user(user, following=True)
    assert schema.username == "bob"
    assert schema.following is True
    assert schema.bio == "hi"


def test_article_schema_from_article_projects_tags_and_counts():
    author_user = User(username="bob", email="e@x.io", password_hash="x")
    author = ProfileSchema.from_user(author_user, following=False)
    article = Article(
        slug="how-to-train",
        title="How to train",
        description="d",
        body="b",
        author=author_user,
    )
    article.tags = [Tag(name="dragons"), Tag(name="training")]
    article.created_at = _NOW
    article.updated_at = _NOW

    schema = ArticleSchema.from_article(article, author=author, favorited=True, favorites_count=7)
    assert schema.tag_list == ["dragons", "training"]
    assert schema.favorited is True
    assert schema.favorites_count == 7
    assert schema.author.username == "bob"


def test_comment_schema_from_comment():
    author_user = User(username="bob", email="e@x.io", password_hash="x")
    author = ProfileSchema.from_user(author_user)
    comment = Comment(id=5, body="great read", author=author_user, article_id=1)
    comment.created_at = _NOW
    comment.updated_at = _NOW

    schema = CommentSchema.from_comment(comment, author=author)
    assert schema.id == 5
    assert schema.body == "great read"
    assert schema.author.username == "bob"
