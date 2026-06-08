"""Pydantic v2 request/response schemas for the RealWorld JSON API.

Split per entity (mirroring ``backend.models``): ``user`` (User + Profile),
``article``, ``comment``, ``tag``, all riding the shared camelCase
:class:`~backend.schemas.base.Schema` base. Callers import from the package
root — ``from backend.schemas import ArticleResponse, ProfileSchema`` — so the
module split stays an implementation detail.

Every model is re-exported here; ``__all__`` keeps the "unused import" linter
honest about the deliberate flattening.
"""

from backend.schemas.article import (
    ArticleResponse,
    ArticleSchema,
    MultipleArticlesResponse,
    NewArticle,
    NewArticleRequest,
    UpdateArticle,
    UpdateArticleRequest,
)
from backend.schemas.base import Schema, blank_to_none
from backend.schemas.comment import (
    CommentResponse,
    CommentSchema,
    MultipleCommentsResponse,
    NewComment,
    NewCommentRequest,
)
from backend.schemas.tag import TagsResponse
from backend.schemas.user import (
    LoginUser,
    LoginUserRequest,
    NewUser,
    NewUserRequest,
    ProfileResponse,
    ProfileSchema,
    UpdateUser,
    UpdateUserRequest,
    UserResponse,
    UserSchema,
)

__all__ = [
    # base
    "Schema",
    "blank_to_none",
    # user / profile
    "UserSchema",
    "ProfileSchema",
    "UserResponse",
    "ProfileResponse",
    "NewUser",
    "NewUserRequest",
    "LoginUser",
    "LoginUserRequest",
    "UpdateUser",
    "UpdateUserRequest",
    # article
    "ArticleSchema",
    "ArticleResponse",
    "MultipleArticlesResponse",
    "NewArticle",
    "NewArticleRequest",
    "UpdateArticle",
    "UpdateArticleRequest",
    # comment
    "CommentSchema",
    "CommentResponse",
    "MultipleCommentsResponse",
    "NewComment",
    "NewCommentRequest",
    # tag
    "TagsResponse",
]
