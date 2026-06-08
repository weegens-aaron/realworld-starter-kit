"""Conduit backend source tree (API routers, ORM models, services, core).

This is the server half of the single FastAPI application. Per ADR 0001 the
HTML routes in ``frontend`` import this service layer directly — there is no
self-HTTP hop, because it's one process and one address space.
"""
