# Favorite / unfavorite an article.
# A reader registers, an author publishes (same token is fine — you can
# favorite your own article in RealWorld), then we toggle the favorite.

# --- Register the user ---------------------------------------------------
POST {{host}}/users
Content-Type: application/json
{
  "user": {
    "username": "fav{{newUuid}}",
    "email": "{{newUuid}}@example.com",
    "password": "sup3r-s3cret-pw"
  }
}
HTTP 200
[Captures]
token: jsonpath "$.user.token"

# --- Publish an article --------------------------------------------------
POST {{host}}/articles
Authorization: Token {{token}}
Content-Type: application/json
{
  "article": {
    "title": "Favorite me {{newUuid}}",
    "description": "Star it.",
    "body": "Body text.",
    "tagList": []
  }
}
HTTP 200
[Captures]
slug: jsonpath "$.article.slug"

# --- Favorite it ---------------------------------------------------------
POST {{host}}/articles/{{slug}}/favorite
Authorization: Token {{token}}
HTTP 200
[Asserts]
jsonpath "$.article.favorited" == true
jsonpath "$.article.favoritesCount" == 1

# --- Unfavorite ----------------------------------------------------------
DELETE {{host}}/articles/{{slug}}/favorite
Authorization: Token {{token}}
HTTP 200
[Asserts]
jsonpath "$.article.favorited" == false
jsonpath "$.article.favoritesCount" == 0
