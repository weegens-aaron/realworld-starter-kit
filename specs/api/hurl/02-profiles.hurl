# Profiles + follow/unfollow.
# Mints two users: a "follower" (whose token we use) and a "celebrity"
# (whom we follow). Both are registered inline so the file stands alone.

# --- Register the celebrity (the followee) -------------------------------
POST {{host}}/users
Content-Type: application/json
{
  "user": {
    "username": "celeb{{newUuid}}",
    "email": "{{newUuid}}@example.com",
    "password": "sup3r-s3cret-pw"
  }
}
HTTP 200
[Captures]
celeb_username: jsonpath "$.user.username"

# --- Register the follower (we drive the API as this user) ---------------
POST {{host}}/users
Content-Type: application/json
{
  "user": {
    "username": "fan{{newUuid}}",
    "email": "{{newUuid}}@example.com",
    "password": "sup3r-s3cret-pw"
  }
}
HTTP 200
[Captures]
token: jsonpath "$.user.token"

# --- Read the celebrity's public profile (anonymous) ---------------------
GET {{host}}/profiles/{{celeb_username}}
HTTP 200
[Asserts]
jsonpath "$.profile.username" == "{{celeb_username}}"
jsonpath "$.profile.following" == false

# --- Follow them ---------------------------------------------------------
POST {{host}}/profiles/{{celeb_username}}/follow
Authorization: Token {{token}}
HTTP 200
[Asserts]
jsonpath "$.profile.username" == "{{celeb_username}}"
jsonpath "$.profile.following" == true

# --- Unfollow ------------------------------------------------------------
DELETE {{host}}/profiles/{{celeb_username}}/follow
Authorization: Token {{token}}
HTTP 200
[Asserts]
jsonpath "$.profile.following" == false
