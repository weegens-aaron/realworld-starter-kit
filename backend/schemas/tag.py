"""Tag schema — just the list envelope.

RealWorld's tags endpoint returns a flat ``{"tags": ["dragons", "training"]}``:
no per-tag object, no count. So there's exactly one schema here — the wrapper
around a list of tag *names* (strings), which is what the model's ``Tag.name``
gives us.
"""

from __future__ import annotations

from backend.schemas.base import Schema


class TagsResponse(Schema):
    """``{"tags": [...]}`` — the only shape the tags endpoint emits."""

    tags: list[str]
