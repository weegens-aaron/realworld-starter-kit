"""Service layer: the business logic the API *and* HTML routes share.

Per ADR 0001, server-rendered HTML routes call into this package directly
(no self-HTTP hop). Keeping logic here — rather than in the routers — is what
makes that single shared code path possible. Empty at scaffold time.
"""
