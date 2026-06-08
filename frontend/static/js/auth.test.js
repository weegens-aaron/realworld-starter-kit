'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

// A minimal in-memory localStorage stand-in (Node has no DOM storage).
function makeStorage() {
  const map = new Map();
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: (k) => map.delete(k),
    _map: map,
  };
}

// A storage whose every access throws — simulates blocked/unavailable storage.
function makeThrowingStorage() {
  const boom = () => {
    throw new Error('storage unavailable');
  };
  return { getItem: boom, setItem: boom, removeItem: boom };
}

// Install a fresh storage on the global the module reads from, BEFORE requiring.
globalThis.localStorage = makeStorage();
const auth = require('./auth.js');

test.beforeEach(() => {
  // Fresh storage + clean in-memory state for every test.
  globalThis.localStorage = makeStorage();
  auth.clearToken();
});

test('globals are attached for the SELECTORS contract', () => {
  assert.equal(globalThis.__conduit_auth, auth);
  const dbg = globalThis.__conduit_debug__;
  assert.equal(typeof dbg.getToken, 'function');
  assert.equal(typeof dbg.getAuthState, 'function');
  assert.equal(typeof dbg.getCurrentUser, 'function');
});

test('unauthenticated: no token in localStorage', () => {
  assert.equal(auth.getToken(), null);
  assert.equal(auth.getAuthState(), 'unauthenticated');
  assert.equal(auth.getCurrentUser(), null);
});

test('loading: token present but current user not resolved', () => {
  auth.setToken('jwt-123');
  assert.equal(auth.getToken(), 'jwt-123');
  assert.equal(auth.getAuthState(), 'loading');
  assert.equal(auth.getCurrentUser(), null);
});

test('authenticated: token present and current user resolved', () => {
  auth.setToken('jwt-123');
  const user = { username: 'aaron', email: 'a@example.com' };
  auth.setCurrentUser(user);
  assert.equal(auth.getAuthState(), 'authenticated');
  assert.deepEqual(auth.getCurrentUser(), user);
  // And the token is persisted to localStorage under the contract key.
  assert.equal(globalThis.localStorage.getItem('jwtToken'), 'jwt-123');
});

test('unavailable: storage cannot be read', () => {
  globalThis.localStorage = makeThrowingStorage();
  assert.equal(auth.getAuthState(), 'unavailable');
  assert.equal(auth.getToken(), null);
});

test('login then logout lifecycle: set on login, cleared on logout', () => {
  // login
  auth.setSession({ token: 'jwt-xyz', username: 'aaron' });
  assert.equal(auth.getToken(), 'jwt-xyz');
  assert.equal(auth.getAuthState(), 'authenticated');
  // logout
  auth.clearToken();
  assert.equal(auth.getToken(), null);
  assert.equal(auth.getAuthState(), 'unauthenticated');
  assert.equal(auth.getCurrentUser(), null);
  assert.equal(globalThis.localStorage.getItem('jwtToken'), null);
});

test('setToken clears any stale cached user (re-login as someone else)', () => {
  auth.setSession({ token: 'old', username: 'old-user' });
  assert.equal(auth.getAuthState(), 'authenticated');
  // A fresh login provides a new token before the new user resolves.
  auth.setToken('new');
  assert.equal(auth.getToken(), 'new');
  assert.equal(auth.getCurrentUser(), null);
  assert.equal(auth.getAuthState(), 'loading');
});

test('setToken with empty/null behaves like logout', () => {
  auth.setToken('jwt');
  auth.setToken('');
  assert.equal(auth.getToken(), null);
  assert.equal(auth.getAuthState(), 'unauthenticated');
});

test('setSession without a token clears the session', () => {
  auth.setToken('jwt');
  auth.setSession({ username: 'no-token-here' });
  assert.equal(auth.getToken(), null);
  assert.equal(auth.getAuthState(), 'unauthenticated');
});
