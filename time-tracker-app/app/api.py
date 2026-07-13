"""Root API router: aggregates all Phase 1 resource routers.

Feature-specific routers live under ``app/routers/`` (one module per resource) and are included
here. Route bodies in those modules are stubs (``raise NotImplementedError``) — see
``app/API_CONTRACT.md`` for the endpoint contract and ``app/schemas.py`` for the request/response
models the backend-developer implements against. Reports/exports (Phase 2) are not included yet.
"""

from fastapi import APIRouter

from app.routers import categories, entries, tags, timer, today

router = APIRouter()
router.include_router(categories.router)
router.include_router(tags.router)
router.include_router(entries.router)
router.include_router(timer.router)
router.include_router(today.router)
