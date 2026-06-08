'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

// ---- DOM-ish stubs (Node has no DOM) ---------------------------------------

class FakeEl {
  constructor(tag) {
    this.tagName = tag;
    this.childNodes = [];
    this.textContent = '';
    this._listeners = {};
  }
  set innerHTML(_v) {
    this.childNodes = [];
  }
  get innerHTML() {
    return this.childNodes.map((c) => `<li>${c.textContent}</li>`).join('');
  }
  get firstChild() {
    return this.childNodes[0] || null;
  }
  appendChild(child) {
    this.childNodes.push(child);
    return child;
  }
  removeChild(child) {
    this.childNodes = this.childNodes.filter((c) => c !== child);
    return child;
  }
  addEventListener(type, fn) {
    (this._listeners[type] = this._listeners[type] || []).push(fn);
  }
  dispatch(type, evt) {
    (this._listeners[type] || []).forEach((fn) => fn(evt));
  }
}

class FakeDoc {
  constructor() {
    this.readyState = 'complete';
    this._listeners = {};
    this._selectors = {};
  }
  createElement(tag) {
    return new FakeEl(tag);
  }
  querySelector(sel) {
    return this._selectors[sel] || null;
  }
  register(sel, el) {
    this._selectors[sel] = el;
  }
  addEventListener(type, fn) {
    (this._listeners[type] = this._listeners[type] || []).push(fn);
  }
  dispatch(type, evt) {
    (this._listeners[type] || []).forEach((fn) => fn(evt));
  }
}

function makeResponse(status, body, contentType = 'application/json') {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: {
      get: (h) => (h.toLowerCase() === 'content-type' ? contentType : null),
    },
    json: async () => body,
    text: async () => (body == null ? '' : typeof body === 'string' ? body : JSON.stringify(body)),
  };
}

// ---- Boot: install a document BEFORE requiring so HTMX handlers wire up. ----

const doc = new FakeDoc();
const errorBox = new FakeEl('ul');
doc.register('.error-messages', errorBox);
globalThis.document = doc;

let currentToken = null;
globalThis.__conduit_auth = { getToken: () => currentToken };

const api = require('./apiclient.js');

let lastFetch = null;
test.beforeEach(() => {
  currentToken = null;
  errorBox.childNodes = [];
  lastFetch = null;
});

function stubFetch(response) {
  globalThis.fetch = (url, options) => {
    lastFetch = { url, options };
    return Promise.resolve(response);
  };
}

// ---- header injection (fetch) ----------------------------------------------

test('authenticated fetch includes Token header from auth module', async () => {
  currentToken = 'jwt-abc';
  stubFetch(makeResponse(200, { user: { username: 'aaron' } }));
  await api.get('/user');
  assert.equal(lastFetch.options.headers['Authorization'], 'Token jwt-abc');
});

test('unauthenticated fetch omits the Authorization header', async () => {
  currentToken = null;
  stubFetch(makeResponse(200, { articles: [] }));
  await api.get('/articles');
  assert.equal('Authorization' in lastFetch.options.headers, false);
});

test('object bodies are JSON-encoded with a Content-Type header', async () => {
  stubFetch(makeResponse(200, { article: {} }));
  await api.post('/articles', { article: { title: 'Hi' } });
  assert.equal(lastFetch.options.method, 'POST');
  assert.equal(lastFetch.options.headers['Content-Type'], 'application/json');
  assert.equal(lastFetch.options.body, JSON.stringify({ article: { title: 'Hi' } }));
});

test('relative paths resolve under /api', async () => {
  stubFetch(makeResponse(200, {}));
  await api.get('/tags');
  assert.equal(lastFetch.url, '/api/tags');
  await api.get('tags');
  assert.equal(lastFetch.url, '/api/tags');
  await api.get('/api/already');
  assert.equal(lastFetch.url, '/api/already');
});

// ---- header injection (HTMX) -----------------------------------------------

test('htmx:configRequest injects the Token header when authenticated', () => {
  currentToken = 'jwt-xyz';
  const evt = { detail: { headers: {} } };
  doc.dispatch('htmx:configRequest', evt);
  assert.equal(evt.detail.headers['Authorization'], 'Token jwt-xyz');
});

test('htmx:configRequest omits the header when unauthenticated', () => {
  currentToken = null;
  const evt = { detail: { headers: {} } };
  doc.dispatch('htmx:configRequest', evt);
  assert.equal('Authorization' in evt.detail.headers, false);
});

// ---- error surfacing --------------------------------------------------------

test('RealWorld validation errors render into .error-messages', async () => {
  stubFetch(
    makeResponse(422, { errors: { email: ['has already been taken'], password: ["is too short"] } })
  );
  await assert.rejects(() => api.post('/users', { user: {} }));
  const texts = errorBox.childNodes.map((li) => li.textContent);
  assert.deepEqual(texts, ['email has already been taken', 'password is too short']);
});

test('the generic "body" field renders its message bare', async () => {
  stubFetch(makeResponse(422, { errors: { body: ["can't be empty"] } }));
  await assert.rejects(() => api.post('/articles', {}));
  assert.deepEqual(errorBox.childNodes.map((li) => li.textContent), ["can't be empty"]);
});

test('FastAPI string detail surfaces as a single message', async () => {
  stubFetch(makeResponse(401, { detail: 'Not authenticated' }));
  await assert.rejects(() => api.get('/user'));
  assert.deepEqual(errorBox.childNodes.map((li) => li.textContent), ['Not authenticated']);
});

test('FastAPI validation detail array surfaces loc + msg', async () => {
  stubFetch(
    makeResponse(422, { detail: [{ loc: ['body', 'title'], msg: 'field required' }] })
  );
  await assert.rejects(() => api.post('/articles', {}));
  assert.deepEqual(errorBox.childNodes.map((li) => li.textContent), ['title field required']);
});

test('a status with no parseable body falls back to a friendly message', async () => {
  stubFetch(makeResponse(500, null, 'text/plain'));
  await assert.rejects(() => api.get('/articles'));
  assert.equal(errorBox.childNodes.length, 1);
  assert.match(errorBox.childNodes[0].textContent, /went wrong/);
});

test('a successful request clears previously surfaced errors', async () => {
  api.renderErrors(['stale error']);
  assert.equal(errorBox.childNodes.length, 1);
  stubFetch(makeResponse(200, { user: {} }));
  await api.get('/user');
  assert.equal(errorBox.childNodes.length, 0);
});

test('surfaceErrors:false leaves .error-messages untouched', async () => {
  stubFetch(makeResponse(422, { errors: { email: ['bad'] } }));
  await assert.rejects(() => api.get('/user', { surfaceErrors: false }));
  assert.equal(errorBox.childNodes.length, 0);
});

test('the thrown error carries status, messages, and data', async () => {
  stubFetch(makeResponse(422, { errors: { email: ['bad'] } }));
  const err = await api.post('/users', {}).then(
    () => null,
    (e) => e
  );
  assert.equal(err.status, 422);
  assert.deepEqual(err.messages, ['email bad']);
  assert.deepEqual(err.data, { errors: { email: ['bad'] } });
});

test('htmx:responseError surfaces the xhr body into .error-messages', () => {
  const evt = {
    detail: { xhr: { status: 403, responseText: JSON.stringify({ detail: 'Forbidden' }) } },
  };
  doc.dispatch('htmx:responseError', evt);
  assert.deepEqual(errorBox.childNodes.map((li) => li.textContent), ['Forbidden']);
});

test('renderErrors accepts an explicit element container', () => {
  const custom = new FakeEl('ul');
  api.renderErrors(['scoped message'], custom);
  assert.deepEqual(custom.childNodes.map((li) => li.textContent), ['scoped message']);
  // default container untouched
  assert.equal(errorBox.childNodes.length, 0);
});
