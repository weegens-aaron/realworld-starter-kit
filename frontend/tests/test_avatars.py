"""Tests for default-avatar handling (conduit-fe-avatar).

Verifies that null/empty author/user images render an ``src`` containing
``default-avatar.svg`` in every avatar location, and that real image URLs
pass through untouched.

Run with jinja2 available, e.g.:
    uv run --with jinja2 python -m unittest frontend.tests.test_avatars -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

# Make the repo root importable so `frontend` resolves as a package.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from frontend.avatars import (  # noqa: E402
    DEFAULT_AVATAR_URL,
    avatar_src,
    register_avatar_helpers,
)

TEMPLATES_DIR = REPO_ROOT / "frontend" / "templates"

# The four avatar locations the SELECTORS contract / ADR 0001 cares about.
AVATAR_CLASSES = ["user-img", "user-pic", "comment-author-img", "article-meta"]


def make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
    )
    register_avatar_helpers(env)
    return env


def render_avatar(env: Environment, image, css_class: str) -> str:
    tmpl = env.from_string(
        '{% from "macros/avatars.html" import avatar %}'
        "{{ avatar(image, class=cls, alt='avatar') }}"
    )
    return tmpl.render(image=image, cls=css_class)


class AvatarSrcFilterTests(unittest.TestCase):
    def test_none_falls_back(self):
        self.assertEqual(avatar_src(None), DEFAULT_AVATAR_URL)

    def test_empty_string_falls_back(self):
        self.assertEqual(avatar_src(""), DEFAULT_AVATAR_URL)

    def test_whitespace_falls_back(self):
        self.assertEqual(avatar_src("   "), DEFAULT_AVATAR_URL)

    def test_real_url_passes_through(self):
        url = "https://cdn.example.com/me.png"
        self.assertEqual(avatar_src(url), url)

    def test_default_url_contains_marker(self):
        self.assertIn("default-avatar.svg", DEFAULT_AVATAR_URL)


class AvatarMacroTests(unittest.TestCase):
    def setUp(self):
        self.env = make_env()

    def test_null_image_renders_default_in_all_locations(self):
        for cls in AVATAR_CLASSES:
            for image in (None, "", "   "):
                with self.subTest(cls=cls, image=image):
                    html = render_avatar(self.env, image, cls)
                    self.assertIn("default-avatar.svg", html)
                    self.assertIn(f'class="{cls}"', html)
                    self.assertIn("<img", html)

    def test_real_image_renders_through_in_all_locations(self):
        url = "https://cdn.example.com/me.png"
        for cls in AVATAR_CLASSES:
            with self.subTest(cls=cls):
                html = render_avatar(self.env, url, cls)
                self.assertIn(url, html)
                self.assertNotIn("default-avatar.svg", html)


if __name__ == "__main__":
    unittest.main()
