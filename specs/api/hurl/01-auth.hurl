# Registration -> login -> current user -> update.
# Self-contained: mints a fresh user with a random email so the suite is
# re-runnable and parallel-safe (no fixture teardown needed).
#
# RealWorld gotcha: the auth scheme is "Authorization: Token <jwt>" (NOT
# Bearer) — see backend/core/deps.py _AUTH_SCHEME.

# --- Register a brand-new user ------------------------------------------
POST {{host}}/users
Content-Type: application/json
{
  "user": {
    "username": "u{{newUuid}}",
    "email": "{{newUuid}}@example.com",
    "password": "sup3r-s3cret-pw"
  }
}
# Canonical RealWorld spec returns 200 (not 201) for registration.
HTTP 200
[Captures]
reg_token: jsonpath "$.user.token"
reg_email: jsonpath "$.user.email"
reg_username: jsonpath "$.user.username"
[Asserts]
jsonpath "$.user.email" exists
jsonpath "$.user.username" exists
jsonpath "$.user.token" exists

# --- Log in with the same credentials -----------------------------------
POST {{host}}/users/login
Content-Type: application/json
{
  "user": {
    "email": "{{reg_email}}",
    "password": "sup3r-s3cret-pw"
  }
}
HTTP 200
[Captures]
token: jsonpath "$.user.token"
[Asserts]
jsonpath "$.user.email" == "{{reg_email}}"
jsonpath "$.user.token" exists

# --- Who am I? (requires the captured token) -----------------------------
GET {{host}}/user
Authorization: Token {{token}}
HTTP 200
[Asserts]
jsonpath "$.user.email" == "{{reg_email}}"
jsonpath "$.user.username" == "{{reg_username}}"

# --- A missing token is a 401 -------------------------------------------
GET {{host}}/user
HTTP 401

# --- Update the profile bio/image ---------------------------------------
PUT {{host}}/user
Authorization: Token {{token}}
Content-Type: application/json
{
  "user": {
    "bio": "I write Hurl tests for breakfast.",
    "image": "https://example.com/avatar.png"
  }
}
HTTP 200
[Asserts]
jsonpath "$.user.bio" == "I write Hurl tests for breakfast."
jsonpath "$.user.image" == "https://example.com/avatar.png"
