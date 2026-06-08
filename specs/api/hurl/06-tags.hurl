# Tags endpoint — public, no auth.
# Just assert the envelope shape; contents depend on what articles exist.
GET {{host}}/tags
HTTP 200
[Asserts]
jsonpath "$.tags" exists
jsonpath "$.tags" isCollection
