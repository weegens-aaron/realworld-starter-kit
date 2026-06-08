/*
 * apiclient.js — Browser API client + JWT/HTMX header injection for Conduit.
 *
 * Per ADR 0001 (HTMX + JWT-in-localStorage), this bead owns ALL request-header
 * wiring so the `Authorization: Token <jwt>` scheme lives in exactly one place:
 *
 *   1. HTMX requests   -> a single `htmx:configRequest` listener injects the
 *                         header onto every request that has a token.
 *   2. fetch() requests -> one shared `request()` wrapper injects the SAME
 *                         header via the SAME code path (authHeaders()).
 *   3. Errors          -> API/validation errors are centralized into the
 *                         RealWorld `.error-messages` list (both HTMX response
 *                         errors and fetch-client errors share one renderer).
 *
 * The token itself is owned by `auth.js` (`window.__conduit_auth.getToken()`),
 * which reads `localStorage['jwtToken']`. We never touch localStorage directly
 * here — single source of truth, no two modules fighting over the scheme.
 *
 * Dependency-free vanilla JS. Works as a classic browser <script> (attaches to
 * window + wires HTMX) and as a CommonJS module (for tests).
 */
(function (factory) {
  'use strict';

  var root =
    typeof window !== 'undefined'
      ? window
      : typeof globalThis !== 'undefined'
        ? globalThis
        : this;

  var api = factory(root);

  // Public global used by page beads that want to call the JSON API from JS.
  root.__conduit_api = api;

  // In a real browser, wire the HTMX header injector + error surfacing once the
  // document is available. (Tests drive `installHtmxHandlers` manually.)
  if (root.document) {
    if (root.document.readyState === 'loading' && root.document.addEventListener) {
      root.document.addEventListener('DOMContentLoaded', function () {
        api.installHtmxHandlers(root.document);
      });
    } else {
      api.installHtmxHandlers(root.document);
    }
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
})(function (root) {
  'use strict';

  // Conduit/RealWorld JSON API is mounted under /api on the same FastAPI app.
  var API_BASE = '/api';
  var AUTH_SCHEME = 'Token'; // RealWorld uses `Token`, NOT `Bearer`.
  var ERROR_SELECTOR = '.error-messages';

  // ---- Token access -----------------------------------------------------------
  // Always read through auth.js so localStorage stays the single source of truth.

  function getToken() {
    var auth = root.__conduit_auth;
    if (auth && typeof auth.getToken === 'function') {
      return auth.getToken();
    }
    return null;
  }

  // Build a headers object with the `Authorization: Token <jwt>` header attached
  // IFF a token exists. Unauthenticated requests omit it entirely. This is the
  // ONE place the scheme is assembled — both HTMX and fetch flow through it.
  function authHeaders(extra) {
    var headers = {};
    if (extra) {
      Object.keys(extra).forEach(function (key) {
        headers[key] = extra[key];
      });
    }
    var token = getToken();
    if (token) {
      headers['Authorization'] = AUTH_SCHEME + ' ' + token;
    }
    return headers;
  }

  // ---- HTMX integration -------------------------------------------------------

  // Inject the auth header onto outgoing HTMX requests. Same scheme, same source
  // of truth as the fetch client — no per-element `hx-headers` duplication.
  function handleConfigRequest(evt) {
    if (!evt || !evt.detail || !evt.detail.headers) {
      return;
    }
    var token = getToken();
    if (token) {
      evt.detail.headers['Authorization'] = AUTH_SCHEME + ' ' + token;
    }
  }

  // Surface non-2xx HTMX responses into `.error-messages`. HTMX won't swap a
  // failed response by default, so without this an API error would be silent.
  function handleResponseError(evt) {
    var xhr = evt && evt.detail && evt.detail.xhr;
    if (!xhr) {
      return;
    }
    var data = safeParseJson(xhr.responseText);
    renderErrors(extractErrorMessages(data, xhr.status));
  }

  var handlersInstalled = false;

  // Wire the two HTMX listeners exactly once. Events bubble to `document`, so a
  // single document-level listener covers the whole page (and survives swaps).
  function installHtmxHandlers(doc) {
    if (handlersInstalled || !doc || typeof doc.addEventListener !== 'function') {
      return;
    }
    doc.addEventListener('htmx:configRequest', handleConfigRequest);
    doc.addEventListener('htmx:responseError', handleResponseError);
    handlersInstalled = true;
  }

  // ---- fetch-based API client -------------------------------------------------

  function resolveUrl(path) {
    if (/^https?:\/\//.test(path) || path.indexOf(API_BASE + '/') === 0 || path === API_BASE) {
      return path;
    }
    return API_BASE + (path.charAt(0) === '/' ? path : '/' + path);
  }

  // The single shared request path. Injects the auth header, JSON-encodes object
  // bodies, parses the response, and routes API/validation errors to
  // `.error-messages` (unless the caller opts out via `surfaceErrors: false`).
  function request(path, options) {
    options = options || {};
    var headers = authHeaders(options.headers);
    var body = options.body;

    // Object bodies are JSON; strings/FormData/etc. are passed through untouched.
    if (body != null && typeof body === 'object' && !isStringifyExempt(body)) {
      if (!hasHeader(headers, 'Content-Type')) {
        headers['Content-Type'] = 'application/json';
      }
      body = JSON.stringify(body);
    }

    var fetchOptions = {
      method: (options.method || 'GET').toUpperCase(),
      headers: headers,
    };
    if (body != null) {
      fetchOptions.body = body;
    }
    if (options.signal) {
      fetchOptions.signal = options.signal;
    }

    return root.fetch(resolveUrl(path), fetchOptions).then(function (response) {
      return handleResponse(response, options);
    });
  }

  function handleResponse(response, options) {
    var surface = options.surfaceErrors !== false;
    var container = options.errorContainer;

    return readBody(response).then(function (data) {
      if (!response.ok) {
        var messages = extractErrorMessages(data, response.status);
        if (surface) {
          renderErrors(messages, container);
        }
        var err = new Error('API request failed (' + response.status + ')');
        err.status = response.status;
        err.messages = messages;
        err.data = data;
        throw err;
      }
      // A successful request clears any previously-surfaced errors.
      if (surface) {
        clearErrors(container);
      }
      return data;
    });
  }

  function readBody(response) {
    var contentType = '';
    if (response.headers && typeof response.headers.get === 'function') {
      contentType = response.headers.get('Content-Type') || '';
    }
    if (contentType.indexOf('application/json') !== -1) {
      return response.json().catch(function () {
        return null;
      });
    }
    if (typeof response.text === 'function') {
      return response.text().catch(function () {
        return null;
      });
    }
    return Promise.resolve(null);
  }

  // Convenience verbs — thin sugar over request() so callers stay DRY.
  function get(path, options) {
    return request(path, assign({ method: 'GET' }, options));
  }
  function post(path, body, options) {
    return request(path, assign({ method: 'POST', body: body }, options));
  }
  function put(path, body, options) {
    return request(path, assign({ method: 'PUT', body: body }, options));
  }
  function del(path, options) {
    return request(path, assign({ method: 'DELETE' }, options));
  }

  // ---- Error extraction + rendering ------------------------------------------

  // Normalize the various error shapes the API can return into a flat list of
  // human-readable strings:
  //   - RealWorld:        { "errors": { "email": ["has already been taken"] } }
  //   - FastAPI default:  { "detail": "Not authenticated" }
  //   - FastAPI validation: { "detail": [ { "loc": [...], "msg": "..." } ] }
  function extractErrorMessages(data, status) {
    var messages = [];

    if (data && data.errors && typeof data.errors === 'object') {
      Object.keys(data.errors).forEach(function (field) {
        var fieldErrors = data.errors[field];
        var list = Array.isArray(fieldErrors) ? fieldErrors : [fieldErrors];
        list.forEach(function (msg) {
          if (msg == null) {
            return;
          }
          // "body"/"" are generic buckets — render the message bare.
          var prefix = field && field !== 'body' ? field + ' ' : '';
          messages.push(prefix + String(msg));
        });
      });
    } else if (data && typeof data.detail === 'string') {
      messages.push(data.detail);
    } else if (data && Array.isArray(data.detail)) {
      data.detail.forEach(function (item) {
        if (item && item.msg) {
          var loc = Array.isArray(item.loc) && item.loc.length
            ? String(item.loc[item.loc.length - 1]) + ' '
            : '';
          messages.push(loc + item.msg);
        }
      });
    } else if (typeof data === 'string' && data.trim()) {
      messages.push(data.trim());
    }

    if (messages.length === 0) {
      messages.push(statusFallback(status));
    }
    return messages;
  }

  function statusFallback(status) {
    if (status === 401 || status === 403) {
      return 'You are not authorized to perform this action.';
    }
    if (status === 404) {
      return 'The requested resource was not found.';
    }
    if (status >= 500) {
      return 'Something went wrong on our end. Please try again.';
    }
    return 'Request failed' + (status ? ' (' + status + ')' : '') + '.';
  }

  // Render messages as `<li>` children of the RealWorld `.error-messages` list.
  // `container` may be an element, a selector string, or omitted (defaults to
  // the first `.error-messages` on the page).
  function renderErrors(messages, container) {
    var el = resolveContainer(container);
    if (!el) {
      return;
    }
    clearChildren(el);
    (messages || []).forEach(function (msg) {
      var li = root.document.createElement('li');
      li.textContent = msg; // textContent => XSS-safe, no HTML injection.
      el.appendChild(li);
    });
  }

  function clearErrors(container) {
    var el = resolveContainer(container);
    if (el) {
      clearChildren(el);
    }
  }

  function resolveContainer(container) {
    if (container && typeof container === 'object' && container.appendChild) {
      return container; // already an element
    }
    if (!root.document || typeof root.document.querySelector !== 'function') {
      return null;
    }
    return root.document.querySelector(
      typeof container === 'string' && container ? container : ERROR_SELECTOR
    );
  }

  // ---- small helpers ----------------------------------------------------------

  function clearChildren(el) {
    if ('innerHTML' in el) {
      el.innerHTML = '';
    }
    while (el.firstChild) {
      el.removeChild(el.firstChild);
    }
  }

  function hasHeader(headers, name) {
    var lower = name.toLowerCase();
    return Object.keys(headers).some(function (key) {
      return key.toLowerCase() === lower;
    });
  }

  // Bodies we must NOT JSON.stringify (the browser serializes these natively).
  function isStringifyExempt(body) {
    return (
      (typeof FormData !== 'undefined' && body instanceof FormData) ||
      (typeof Blob !== 'undefined' && body instanceof Blob) ||
      (typeof ArrayBuffer !== 'undefined' && body instanceof ArrayBuffer) ||
      (typeof URLSearchParams !== 'undefined' && body instanceof URLSearchParams)
    );
  }

  function safeParseJson(text) {
    if (!text) {
      return null;
    }
    try {
      return JSON.parse(text);
    } catch (err) {
      return text;
    }
  }

  function assign(target, source) {
    if (source) {
      Object.keys(source).forEach(function (key) {
        if (key !== 'method' || target.method == null) {
          target[key] = source[key];
        }
      });
    }
    return target;
  }

  return {
    // header wiring
    getToken: getToken,
    authHeaders: authHeaders,
    installHtmxHandlers: installHtmxHandlers,
    handleConfigRequest: handleConfigRequest,
    handleResponseError: handleResponseError,
    // fetch client
    request: request,
    get: get,
    post: post,
    put: put,
    del: del,
    // error surfacing
    extractErrorMessages: extractErrorMessages,
    renderErrors: renderErrors,
    clearErrors: clearErrors,
  };
});
