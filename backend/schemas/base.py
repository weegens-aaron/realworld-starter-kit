"""Shared Pydantic v2 base for every request/response schema.

The RealWorld JSON API speaks **camelCase** on the wire (``tagList``,
``favoritesCount``, ``createdAt``, ...) while our Python code stays
``snake_case``. Rather than hand-aliasing every field, :class:`Schema` wires a
single :func:`pydantic.alias_generators.to_camel` alias generator: each model
declares ``snake_case`` attributes and serialization automatically emits the
camelCase the spec mandates. ``populate_by_name=True`` keeps both spellings
valid on the way *in* (so a service can build a model with ``tag_list=[...]``
and a client can POST ``{"tagList": [...]}``), and ``from_attributes=True``
lets a model be hydrated straight off an ORM row.

Keeping this config in one place is the whole point — DRY beats repeating the
same ``ConfigDict`` on a dozen models, and "there should be one obvious way to
do it" applies to alias policy too.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


def blank_to_none(value: object) -> object:
    """Normalise an empty/whitespace-only string to ``None``.

    RealWorld treats a missing ``bio``/``image`` as JSON ``null``, never as an
    empty string. The DB columns are nullable, but a client (or an over-eager
    form) can still hand us ``""``; this collapses that to ``None`` so the
    serialized payload matches the contract. Non-string values pass through
    untouched.
    """
    if isinstance(value, str) and not value.strip():
        return None
    return value


class Schema(BaseModel):
    """Base model: camelCase aliases on the wire, snake_case in Python."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )
