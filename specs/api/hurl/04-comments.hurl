# Comments on an article.
# Author registers, publishes an article, then comments on it, lists the
# comments and deletes one. All inline so the file is independent.

# --- Register the author -------------------------------------------------
POST {{host}}/users
Content-Type: application/json
{
  "user": {
    "username": "commenter{{newUuid}}",
    "email": "{{newUuid}}@example.com",
    "password": "sup3r-s3cret-pw"
  }
}
HTTP 200
[Captures]
token: jsonpath "$.user.token"

# --- Publish an article to comment on ------------------------------------
POST {{host}}/articles
Authorization: Token {{token}}
Content-Type: application/json
{
  "article": {
    "title": "Comment me {{newUuid}}",
    "description": "Please.",
    "body": "Leave a comment below.",
    "tagList": ["meta"]
  }
}
HTTP 200
[Captures]
slug: jsonpath "$.article.slug"

# --- Add a comment -------------------------------------------------------
POST {{host}}/articles/{{slug}}/comments
Authorization: Token {{token}}
Content-Type: application/json
{
  "comment": {
    "body": "First!"
  }
}
HTTP 200
[Captures]
comment_id: jsonpath "$.comment.id"
[Asserts]
jsonpath "$.comment.body" == "First!"
jsonpath "$.comment.author.username" exists

# --- List comments (anonymous) -------------------------------------------
GET {{host}}/articles/{{slug}}/comments
HTTP 200
[Asserts]
jsonpath "$.comments" count >= 1

# --- Delete the comment --------------------------------------------------
DELETE {{host}}/articles/{{slug}}/comments/{{comment_id}}
Authorization: Token {{token}}
HTTP 200
