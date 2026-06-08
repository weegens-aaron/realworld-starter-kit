/*
 * auth.js — Foundation auth + debug module for the Conduit frontend.
 *
 * Per ADR 0001 (HTMX + JWT-in-localStorage):
 *   - `localStorage['jwtToken']` is the SINGLE source of truth for auth.
 *   - There is no server session and no auth cookie.
 *   - This module owns token I/O and exposes two globals:
 *       window.__conduit_auth   — internal API used by page beads
 *                                 (login/register set the token, logout clears it)
 *       window.__conduit_debug__ — the SELECTORS-contract debug hook used by e2e
 *
 * The debug contract (see ADR 0001, Decision (d)):
 *   getToken()       -> raw jwtToken string, or null if absent
 *   getAuthState()   -> 'authenticated' | 'unauthenticated' | 'loading' | 'unavailable'
 *   getCurrentUser() -> cached current-user object (GET /api/user), or null
 *
 * Auth-state semantics:
 *   'unavailable'     -> localStorage cannot be read (private mode / JS error / pre-boot)
 *   'unauthenticated' -> no token in localStorage
 *   'loading'         -> token present but the current user is not resolved yet
 *   'authenticated'   -> token present AND current user resolved
 *
 * Deliberately NOT here: the htmx:configRequest / fetch header injector and the
 * API client live in `conduit-fe-apiclient` so a single bead owns header wiring
 * (no two modules fighting over the `Token <jwt>` scheme).
 *
 * Dependency-free vanilla JS. Works as a classic browser <script> (attaches to
 * window) and as a CommonJS module (for tests), exporting the same API.
 */
(function (factory) {
  'use strict';

  // The host object we attach the public globals to: `window` in the browser,
  // `globalThis` everywhere else (tests, workers, etc.).
  var root =
    typeof window !== 'undefined'
      ? window
      : typeof globalThis !== 'undefined'
        ? globalThis
        : this;

  var api = factory(root);

  // Browser globals: the debug hook the SELECTORS contract reads, plus the
  // internal auth API the page beads call.
  root.__conduit_auth = api;
  root.__conduit_debug__ = {
    getToken: api.getToken,
    getAuthState: api.getAuthState,
    getCurrentUser: api.getCurrentUser,
  };

  // CommonJS export for tests (no bundler, no browser globals required).
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
})(function (root) {
  'use strict';

  var TOKEN_KEY = 'jwtToken';

  // In-memory cache of identity-dependent state. localStorage is the source of
  // truth for the *token*; the current user is fetched once after boot and
  // cached here (the server can't see the client-only token on a cold load).
  var currentUser = null;

  // Reads the raw token. Returns:
  //   string  -> a token is present
  //   null    -> no token (key absent / empty)
  //   throws  -> localStorage genuinely unavailable (surfaced as 'unavailable')
  function readRawToken() {
    var value = root.localStorage.getItem(TOKEN_KEY);
    return value ? value : null;
  }

  // ---- Debug contract (window.__conduit_debug__) ------------------------------

  function getToken() {
    try {
      return readRawToken();
    } catch (err) {
      // Storage unreadable (e.g. blocked cookies/storage) — treat as "no token"
      // for callers that just want the string; state queries get 'unavailable'.
      return null;
    }
  }

  function getAuthState() {
    var token;
    try {
      token = readRawToken();
    } catch (err) {
      return 'unavailable';
    }
    if (!token) {
      return 'unauthenticated';
    }
    // Token present: authenticated only once the current user is resolved;
    // otherwise we're still resolving it (boot fetch in flight).
    return currentUser ? 'authenticated' : 'loading';
  }

  function getCurrentUser() {
    return currentUser || null;
  }

  // ---- Token lifecycle (window.__conduit_auth) --------------------------------
  // Used by the login/register/settings/logout page beads.

  // Store the token (login / register success). Clears any stale cached user so
  // the next getAuthState() reports 'loading' until the boot fetch resolves.
  function setToken(token) {
    if (!token) {
      // Defensive: setToken('') / setToken(null) is really a logout.
      clearToken();
      return;
    }
    try {
      root.localStorage.setItem(TOKEN_KEY, token);
    } catch (err) {
      // If we cannot persist, don't pretend we're authenticated.
      currentUser = null;
      return;
    }
    currentUser = null;
  }

  // Remove the token and forget the cached user (logout).
  function clearToken() {
    currentUser = null;
    try {
      root.localStorage.removeItem(TOKEN_KEY);
    } catch (err) {
      // Nothing more we can do; in-memory state is already cleared.
    }
  }

  // Cache the resolved current user (from GET /api/user, or directly from a
  // login/register response). Flips state from 'loading' -> 'authenticated'.
  function setCurrentUser(user) {
    currentUser = user || null;
  }

  // Convenience: a RealWorld login/register response is `{ user: { token, ... } }`.
  // setSession stores the token AND caches the user in one DRY call.
  function setSession(user) {
    if (!user || !user.token) {
      clearToken();
      return;
    }
    setToken(user.token);
    setCurrentUser(user);
  }

  return {
    // debug contract
    getToken: getToken,
    getAuthState: getAuthState,
    getCurrentUser: getCurrentUser,
    // token lifecycle
    setToken: setToken,
    clearToken: clearToken,
    setCurrentUser: setCurrentUser,
    setSession: setSession,
  };
});
