# Liveness probe — the one endpoint that already exists in the scaffold.
# Everything downstream assumes the app booted and the /api tree is mounted.
# HOST points at .../api, so the health route lives at {{host}}/health.
GET {{host}}/health
HTTP 200
[Asserts]
jsonpath "$.status" == "ok"
