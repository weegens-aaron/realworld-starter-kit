# Article CRUD + listing.
# Registers an author inline, then exercises create -> read -> list ->
# update -> delete against a freshly minted article slug.

# --- Register the author -------------------------------------------------
POST {{host}}/users
Content-Type: application/json
{
  "user": {
    "username": "author{{newUuid}}",
    "email": "{{newUuid}}@example.com",
    "password": "sup3r-s3cret-pw"
  }
}
HTTP 200
[Captures]
token: jsonpath "$.user.token"

# --- Create an article ---------------------------------------------------
POST {{host}}/articles
Authorization: Token {{token}}
Content-Type: application/json
{
  "article": {
    "title": "How to test {{newUuid}}",
    "description": "A short story about Hurl.",
    "body": "Once upon a time there was a green CI badge.",
    "tagList": ["testing", "hurl"]
  }
}
# Canonical RealWorld spec returns 200 for create/update/delete.
HTTP 200
[Captures]
slug: jsonpath "$.article.slug"
[Asserts]
jsonpath "$.article.slug" exists
jsonpath "$.article.title" startsWith "How to test"
jsonpath "$.article.tagList" includes "hurl"
jsonpath "$.article.favorited" == false
jsonpath "$.article.author.username" exists

# --- Read it back by slug (anonymous) ------------------------------------
GET {{host}}/articles/{{slug}}
HTTP 200
[Asserts]
jsonpath "$.article.slug" == "{{slug}}"

# --- List articles -------------------------------------------------------
GET {{host}}/articles
HTTP 200
[Asserts]
jsonpath "$.articles" exists
jsonpath "$.articlesCount" exists

# --- Filter the list by tag ----------------------------------------------
GET {{host}}/articles?tag=hurl
HTTP 200
[Asserts]
jsonpath "$.articles" exists

# --- Update the body -----------------------------------------------------
PUT {{host}}/articles/{{slug}}
Authorization: Token {{token}}
Content-Type: application/json
{
  "article": {
    "body": "Updated: the badge stayed green."
  }
}
HTTP 200
[Asserts]
jsonpath "$.article.body" == "Updated: the badge stayed green."

# --- Delete it -----------------------------------------------------------
DELETE {{host}}/articles/{{slug}}
Authorization: Token {{token}}
HTTP 200
