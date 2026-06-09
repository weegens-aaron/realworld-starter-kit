# CORS policy

The Conduit API and its browser frontends do **not** always share an origin:

- the Playwright/e2e suite drives a page served from a throwaway origin;
- the demo SPA can be hosted anywhere (a static host, a different port, a
  preview URL);
- local dev often runs the UI and the API on different ports.

So every cross-origin request the browser makes (and the `OPTIONS` *preflight*
that precedes the non-simple ones) has to be explicitly allowed by the server,
or the browser will block the response. This doc is the source of truth the
`conduit-fnd-cors` bead implements against.

## What we allow (and why it's safe to be permissive)

| Setting             | Default | Rationale                                                         |
| ------------------- | ------- | ----------------------------------------------------------------- |
| `allow_origins`     | `["*"]` | Demo/e2e frontends live on unpredictable origins.                 |
| `allow_methods`     | `["*"]` | RealWorld uses GET/POST/PUT/DELETE; `*` covers them + preflight.  |
| `allow_headers`     | `["*"]` | Clients send `Authorization` + `Content-Type` freely.             |
| `expose_headers`    | `["*"]` | Nothing secret leaks via headers; keeps clients unsurprising.     |
| `allow_credentials` | `false` | Auth is header-based, not cookie-based — no credentialed CORS.    |

### The key insight: header auth, not cookie auth

Conduit's auth token rides in an **`Authorization: Token <jwt>`** header that
the frontend reads from `localStorage` (see `frontend/static/js/auth.js` and
the ADR on the HTMX/JWT strategy). Because we never put the session in a
cookie, the browser has no ambient credential to protect, so:

- we do **not** set `allow_credentials=True`, and
- we are therefore free to use the wildcard `allow_origins=["*"]`.

This matters: the wildcard origin and `allow_credentials=True` are mutually
exclusive in the CORS spec — Starlette will silently refuse to echo a wildcard
when credentials are on. Keeping credentials off is what *lets* us stay
maximally permissive for the demo without tripping that footgun.

## Locking it down

The defaults are permissive on purpose, but every knob is overridable from the
environment (read in `backend/core/config.py`):

```bash
# Comma-separated allowlist; replaces the wildcard.
CONDUIT_CORS_ORIGINS="https://demo.example.com,https://app.example.com"

# Only flip this on if/when auth ever moves to cookies — and then origins
# MUST be an explicit allowlist (no wildcard).
CONDUIT_CORS_ALLOW_CREDENTIALS=true
```

## Where it's wired

`CORSMiddleware` is added in `backend/main.py`'s `create_app()` factory. It is
registered as application middleware, so Starlette short-circuits the `OPTIONS`
preflight before it ever reaches a route handler — preflight "just works" for
every endpoint, current and future.
