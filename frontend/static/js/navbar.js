/*
 * navbar.js — flips the server-rendered navbar into its signed-in state.
 *
 * Per ADR 0001 the shell is server-rendered but auth is client-owned: the JWT
 * lives only in localStorage, so the server renders BOTH nav states and this
 * module decides which to show once a token is known.
 *
 *   [data-auth="anon"]  shown when there is NO token (the server default)
 *   [data-auth="user"]  shown when a token IS present (New Article / Settings /
 *                       the profile link with .user-pic)
 *
 * It also fills the authenticated profile link: href -> /profile/<username>,
 * the username text, and the .user-pic src once the current user is resolved
 * (cached by auth.js after GET /api/user). Re-runs on the `conduit:auth-changed`
 * event so login/logout flip the navbar without a full reload.
 *
 * Browser-only (DOM required); no CommonJS export — there is nothing to unit
 * test here that isn't just DOM plumbing.
 */
(function () {
  'use strict';

  if (typeof document === 'undefined') {
    return;
  }

  // auth.js owns token I/O; fall back to the debug hook if it ever loads first.
  function authApi() {
    return (
      window.__conduit_auth ||
      (window.__conduit_debug__ && {
        getToken: window.__conduit_debug__.getToken,
        getCurrentUser: window.__conduit_debug__.getCurrentUser,
      }) ||
      null
    );
  }

  function setHidden(selector, hidden) {
    var nodes = document.querySelectorAll(selector);
    for (var i = 0; i < nodes.length; i++) {
      nodes[i].hidden = hidden;
    }
  }

  function fillProfile(user) {
    if (!user || !user.username) {
      return;
    }
    var profileHref = '/profile/' + encodeURIComponent(user.username);
    var links = document.querySelectorAll('a[data-nav="profile"]');
    for (var i = 0; i < links.length; i++) {
      links[i].setAttribute('href', profileHref);
    }
    var names = document.querySelectorAll('[data-nav="username"]');
    for (var j = 0; j < names.length; j++) {
      names[j].textContent = user.username;
    }
    if (user.image) {
      // Only override when the user actually has an image; otherwise the
      // server-rendered default-avatar.svg src stays (ADR 0001 fallback).
      var pics = document.querySelectorAll('a[data-nav="profile"] .user-pic');
      for (var k = 0; k < pics.length; k++) {
        pics[k].setAttribute('src', user.image);
      }
    }
  }

  function hydrate() {
    var auth = authApi();
    var hasToken = !!(auth && auth.getToken && auth.getToken());
    setHidden('[data-auth="anon"]', hasToken);
    setHidden('[data-auth="user"]', !hasToken);
    if (hasToken && auth.getCurrentUser) {
      fillProfile(auth.getCurrentUser());
    }
  }

  // Public hook so login/register/settings beads can re-flip after they change
  // auth state (in addition to dispatching `conduit:auth-changed`).
  window.__conduit_nav = { hydrate: hydrate };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', hydrate);
  } else {
    hydrate();
  }
  document.addEventListener('conduit:auth-changed', hydrate);
})();
