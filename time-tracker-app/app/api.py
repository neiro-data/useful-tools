"""Root API router: aggregates all resource routers.

Feature-specific routers live under ``app/routers/`` (one module per resource) and are included
here. See ``app/API_CONTRACT.md`` for the endpoint contract and ``app/schemas.py`` for the
request/response models each router implements against.
"""

from fastapi import APIRouter

from app.routers import categories, entries, reports, tags, timer, today

router = APIRouter()
router.include_router(categories.router)
router.include_router(tags.router)
router.include_router(entries.router)
router.include_router(timer.router)
router.include_router(today.router)
router.include_router(reports.router)
