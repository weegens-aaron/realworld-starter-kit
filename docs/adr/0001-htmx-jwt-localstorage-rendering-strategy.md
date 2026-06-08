# ADR 0001: HTMX + JWT-in-localStorage Rendering Strategy

- **Status:** Accepted
- **Date:** 2026-06-08
- **Deciders:** Frontend Foundations (`conduit-fe-fnd`)
- **Bead:** `conduit-fe-adr`
- **Tags:** adr, frontend, auth, htmx

## Context

We ship a **single FastAPI application** that serves *both* the Conduit JSON
API (`/api/...`) and the server-rendered HTML UI (Jinja2 + HTMX). The repo
layout (`conduit-fnd-scaffold`) is:

```
/backend    api/ · models/ · services/ · core/
/frontend   templates/ · static/ · routes/
```

So there is **one process, one address space** — the HTML routes can import the
service layer directly; there is no separate frontend server.

The wrinkle: the e2e **SELECTORS contract** (`SELECTORS.md`, the Playwright
specs, and `helpers/debug.ts`) was written for a *client-rendered SPA* and
mandates browser-side conventions that are unusual for a server-rendered app:

1. The auth JWT **must** live in `localStorage` under the key **`jwtToken`**.
2. A global **`window.__conduit_debug__`** object must exist exposing
   `getToken()`, `getAuthState()`, and `getCurrentUser()`.
3. Authenticated API calls use the RealWorld scheme
   **`Authorization: Token <jwt>`** (note: `Token`, *not* `Bearer`).
4. Null/empty avatars must render an `src` containing **`default-avatar.svg`**
   across `.user-img`, `.user-pic`, `.comment-author-img`, and
   `.article-meta img`.

The core tension: **the JWT lives only in the browser (`localStorage`), which
the server cannot read during a normal full-page navigation.** A standard
server session would solve auth trivially, but it would *violate the SELECTORS
contract* (no `jwtToken` in `localStorage`, no debug hook reflecting it). We
must reconcile "server-rendered HTML" with "client-owned auth state."

## Decision

We adopt a **server-renders-the-shell, client-owns-auth-and-hydrates** model.
The four sub-decisions called out by the bead:

### (a) Where auth state lives & how HTMX attaches `Authorization`

- **`localStorage['jwtToken']` is the single source of truth for auth.** There
  is no server session and no auth cookie. This is non-negotiable: the
  SELECTORS contract reads `jwtToken` directly.
- A thin vanilla-JS module (`frontend/static/js/auth.js`) owns all token I/O:
  `getToken() / setToken() / clearToken()`.
- HTMX attaches the header **globally, once**, via a single
  `htmx:configRequest` listener that injects
  `Authorization: Token <jwt>` from `localStorage` onto **every same-origin
  request that has a token**. We deliberately do **not** sprinkle
  `hx-headers='{"Authorization": ...}'` across templates — that would duplicate
  the token wiring on every element (DRY violation) and can't see a token that
  changes after page load.

  ```js
  // frontend/static/js/auth.js  (sketch — full impl lands in conduit-fe-apiclient/-debug)
  document.body.addEventListener('htmx:configRequest', (evt) => {
    const token = window.__conduit_auth.getToken();
    if (token) evt.detail.headers['Authorization'] = `Token ${token}`;
  });
  ```

- The `fetch`-based API client (`conduit-fe-apiclient`) injects the same header
  through one shared request wrapper, so HTMX requests and JS-initiated
  requests share **one** header-injection code path.

### (b) HTML routes: service layer, *not* a self-HTTP-hop

- **Server-side HTML routes call the internal service layer directly**
  (`from backend.services import ...`). They do **not** make an HTTP round-trip
  back to our own `/api/...` endpoints.
  - Rationale: same process, same address space — a self-`httpx` call would add
    a pointless network hop, a second serialization pass, and a second auth
    decode for zero benefit.
- **But the server only renders what it can authenticate.** Because the JWT is
  client-only, the server **cannot** know the viewer's identity on a cold full-
  page load. Therefore:
  - **Server renders from the service layer:** the page *shell* (navbar,
    `.container`, footer) and all **public / unauthenticated** content
    (global feed, tags sidebar, public profiles, public articles).
  - **Client hydrates authenticated content** *after* boot: the boot script
    reads `jwtToken`, flips the navbar to its logged-in state, and HTMX fetches
    personalized data (`Your Feed`, follow/favorite state, current user) from
    the **JSON API** with the injected `Token` header.
- Net rule for page beads: **"public + structure = server-rendered from the
  service layer; identity-dependent = client-hydrated via the JSON API."**

### (c) Protected-route redirects without a server session

- The server **cannot** redirect unauthenticated users for protected routes
  (`/editor`, `/editor/:slug`, `/settings`) because it doesn't see the token.
  So **route guarding is client-side and runs before paint.**
- Protected-route templates include a **synchronous guard script at the top of
  `<head>`** (before any visible content) that does:

  ```html
  <script>
    if (!localStorage.getItem('jwtToken')) {
      window.location.replace('/login');  // replace() => no broken back-button entry
    }
  </script>
  ```

  Running it in `<head>` (parser-blocking, pre-paint) avoids a flash of
  protected content (FOPC). `location.replace` keeps history clean.
- The server still happily serves the protected route's HTML; the guard just
  bounces the browser before the user sees anything. This is the standard,
  contract-compatible way to gate routes when auth state is client-owned.

### (d) Client JS footprint (`__conduit_debug__` + default-avatar)

- **Thin, dependency-free, vanilla JS.** No SPA framework, no client-state
  library (no Redux/Zustand/etc.). The whole foundation client is a couple of
  small modules:
  - `auth.js` — token I/O, the `htmx:configRequest` header injector, and the
    public `window.__conduit_debug__` contract.
  - the API client wrapper (`conduit-fe-apiclient`) layered on top.
- **`window.__conduit_debug__` contract** (implemented in `conduit-fe-debug`):

  | Method | Returns |
  | --- | --- |
  | `getToken()` | the raw `jwtToken` string, or `null` if absent |
  | `getAuthState()` | one of `'authenticated' \| 'unauthenticated' \| 'loading' \| 'unavailable'` |
  | `getCurrentUser()` | the cached current-user object (from `GET /api/user`), or `null` |

  State semantics:
  - `'loading'` — boot script is still resolving the current user (token present
    but `GET /api/user` in flight).
  - `'authenticated'` — token present **and** current user resolved.
  - `'unauthenticated'` — no token in `localStorage`.
  - `'unavailable'` — the debug hook itself can't determine state (e.g. JS error
    / pre-boot). This is the safe default before `auth.js` initializes.
  - `jwtToken` is **set** on successful login/register and **cleared** on logout
    (owned by the login/register/settings page beads, using `auth.js` setters).

- **Default avatars are handled server-side in Jinja2, not JS.** A single shared
  macro / filter renders the avatar `src`, falling back to `default-avatar.svg`
  when the image is null/empty. One macro reused across `.user-img`,
  `.user-pic`, `.comment-author-img`, and `.article-meta img` keeps it DRY and
  keeps it out of the JS bundle. (Implemented in `conduit-fe-avatar`.)

## Rationale

- **SELECTORS compliance is a hard constraint, not a preference.** Anything that
  drops `jwtToken` from `localStorage` or the `__conduit_debug__` hook fails the
  e2e suite. So auth state *must* live client-side; we design around that rather
  than fight it.
- **No-network-hop honored.** Direct service-layer calls for server-rendered
  content respect the single-app reality — no self-HTTP, no double-decode.
- **Simplicity / thin client.** One global header injector + one tiny auth
  module beats per-element header config and a heavyweight client store. Less JS
  to ship, fewer places for the `Token` scheme to drift.
- **Clear seam for page beads.** "Public/structure → server; identity-dependent
  → client-hydrated" is a single, unambiguous rule every page bead can follow.
- **Security posture is explicitly acknowledged.** `localStorage` JWTs are
  XSS-exfiltratable (no `HttpOnly` protection). We accept this *because the
  contract dictates it*, and we compensate by mandating XSS-safe rendering
  (autoescaping everywhere — see `conduit-fe-xss`) as the primary mitigation.

## Alternatives Considered

1. **Server-session auth (cookie-based).** *Rejected.* The cleanest, most
   secure option (`HttpOnly` cookie, server knows the user, trivial redirects),
   but it produces **no `jwtToken` in `localStorage`** and nothing for
   `__conduit_debug__` to reflect → fails the SELECTORS contract outright. A
   hybrid (cookie *and* mirror the JWT into `localStorage`) was rejected as
   two-sources-of-truth complexity for no contract benefit.

2. **HTMX-fetches-JSON for *everything* (pure SPA-ish).** *Rejected.* Render an
   empty shell and hydrate *all* content (even public) via the JSON API. Throws
   away server-rendering's SEO/first-paint benefits, makes the no-JS experience
   blank, and adds latency for content we can render directly from the service
   layer. We use client hydration **only** where identity is required.

3. **Server-renders-from-service-layer for *everything*, including auth.**
   *Rejected.* Impossible as the sole strategy: the server can't see the
   client-only token on a cold load, so it can't render identity-dependent
   content server-side. (We *do* use it for public content — see Decision (b).)

4. **Self-HTTP hop (HTML routes call our own `/api` via `httpx`).** *Rejected.*
   Real network round-trip + double serialization + double auth decode inside
   one process. Pure overhead.

5. **Heavier client store (Redux/Zustand/Alpine store).** *Rejected (YAGNI).*
   The auth state is "one token + one cached user." A 30-line vanilla module
   covers it; a state library is ceremony we don't need.

6. **`Bearer` token scheme.** *Rejected.* RealWorld/Conduit mandates
   `Authorization: Token <jwt>`. Using `Bearer` would fail the API contract.

## Consequences

- **Positive**
  - Passes the SELECTORS contract (localStorage `jwtToken` + `__conduit_debug__`).
  - One header-injection path shared by HTMX and the JS API client.
  - Public content is real server-rendered HTML (good first paint / SEO / no-JS).
  - Page beads get a single, crisp rule for where each piece of data comes from.
- **Negative / accepted trade-offs**
  - JWT in `localStorage` is XSS-exfiltratable → we hard-require autoescaping
    (`conduit-fe-xss`) as mitigation.
  - A brief client-side "loading" window exists before personalized content and
    navbar state resolve; treat `'loading'`/`'unavailable'` as first-class UI
    states, not edge cases.
  - Protected routes rely on a pre-paint client guard; the server will still
    serve their HTML to anyone (the guard bounces unauthenticated viewers). Any
    *sensitive* data on those pages must come from token-authenticated API
    calls, never be inlined server-side.

## Reference (for downstream page beads)

| Concern | Contract |
| --- | --- |
| Token storage | `localStorage` key **`jwtToken`** |
| Auth header | `Authorization: Token <jwt>` (injected globally via `htmx:configRequest` + shared API client) |
| Debug hook | `window.__conduit_debug__.{getToken, getAuthState, getCurrentUser}` |
| Auth states | `authenticated` · `unauthenticated` · `loading` · `unavailable` |
| Token lifecycle | set on login/register success; cleared on logout |
| Server-rendered (service layer) | page shell + public content (global feed, tags, public profiles/articles) |
| Client-hydrated (JSON API) | `Your Feed`, follow/favorite state, current user, all identity-dependent UI |
| Protected routes | `/editor`, `/editor/:slug`, `/settings` — guarded pre-paint by a `<head>` script; redirect to `/login` |
| Default avatar | server-side Jinja2 macro → `src` contains `default-avatar.svg` for null/empty images |
| Error surfacing | API/validation errors render into `.error-messages` (see `conduit-fe-apiclient`) |
