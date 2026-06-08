"""Shared default-avatar handling for Conduit's Jinja2 templates.

Per ADR 0001, null/empty avatars must render an ``src`` containing
``default-avatar.svg`` across ``.user-img``, ``.user-pic``,
``.comment-author-img`` and ``.article-meta img``.

This module is the *single source of truth* for that fallback. Templates
never hardcode the default URL; they go through the ``avatar_src`` filter
(or the ``avatar`` macro, which itself uses the filter). One rule, one
place — DRY, and easy to change if the asset path ever moves.
"""

from __future__ import annotations

# Single source of truth for the fallback asset path. The leading "/static"
# matches the FastAPI StaticFiles mount the scaffold wires up.
DEFAULT_AVATAR_URL = "/static/images/default-avatar.svg"


def avatar_src(image: str | None) -> str:
    """Resolve an avatar URL, falling back to the default for null/empty input.

    Treats ``None``, the empty string and whitespace-only strings as "no
    image" so a blank ``image`` field (RealWorld normalizes these to null)
    still yields the default avatar.

    >>> avatar_src(None)
    '/static/images/default-avatar.svg'
    >>> avatar_src("   ")
    '/static/images/default-avatar.svg'
    >>> avatar_src("https://cdn.example.com/me.png")
    'https://cdn.example.com/me.png'
    """
    if image and image.strip():
        return image
    return DEFAULT_AVATAR_URL


def register_avatar_helpers(env) -> None:
    """Install the avatar helpers on a Jinja2 ``Environment``.

    Adds the ``avatar_src`` filter and the ``DEFAULT_AVATAR_URL`` global so
    both the shared ``avatar`` macro and any ad-hoc template can render the
    fallback consistently. Downstream layout/page beads call this once when
    they build the environment.
    """
    env.filters["avatar_src"] = avatar_src
    env.globals["DEFAULT_AVATAR_URL"] = DEFAULT_AVATAR_URL
