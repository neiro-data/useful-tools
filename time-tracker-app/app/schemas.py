"""API request/response contract (Pydantic v2 models).

This module is the **single source of truth** for the shapes exchanged over HTTP. It is imported
by ``app/api.py`` (route signatures) and will be imported by the backend-developer's route
implementations. It intentionally contains **no I/O or business logic** — only validation and
serialization concerns.

Conventions
-----------
- Timestamps are ISO-8601 UTC strings (matching ``app/schema.py``'s storage format), typed as
  ``AwareDatetime`` so pydantic parses/validates them but callers may still treat them as text at
  the storage boundary. Backend code is responsible for normalizing to UTC before persisting.
- ``*Read`` models represent full API responses (include ``id`` and server-owned fields).
- ``*Create`` models represent request bodies for creation (no ``id``, no server-owned fields).
- ``*Update`` models represent ``PATCH`` request bodies: every field is optional, and only fields
  explicitly provided (``exclude_unset=True`` on the server side) should be applied.
- See ``app/API_CONTRACT.md`` for the endpoint-level contract (paths, status codes, error shapes)
  this module supports.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

# --- Shared / cross-cutting -----------------------------------------------------------------


class EntryMode(StrEnum):
    """How an entry's timestamps were produced."""

    TIMER = "timer"
    MANUAL = "manual"


NonEmptyStr = Annotated[str, Field(min_length=1, max_length=200)]
"""A required, non-blank, reasonably-bounded single-line string (e.g. titles, names)."""


class ErrorDetail(BaseModel):
    """The body of an API error, always wrapped in :class:`ErrorResponse`."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "timer_already_running",
                "message": "A timer is already running (entry_id=42). Stop it before starting"
                " another.",
                "details": {"running_entry_id": 42},
            }
        }
    )

    code: str = Field(description="Stable, machine-readable error code (snake_case).")
    message: str = Field(description="Human-readable explanation, safe to show to the user.")
    details: dict[str, Any] | None = Field(
        default=None, description="Optional structured context (e.g. offending field, IDs)."
    )


class ErrorResponse(BaseModel):
    """Envelope returned for every non-2xx JSON response."""

    error: ErrorDetail


# --- Categories ---------------------------------------------------------------------------------


class CategoryCreate(BaseModel):
    """Request body for ``POST /categories``."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"name": "Deep Work", "color": "#4C6EF5", "sort_order": 0}}
    )

    name: NonEmptyStr
    color: Annotated[str, Field(max_length=32)] | None = Field(
        default=None, description="Free-form color token, e.g. a hex code (#RRGGBB) or CSS name."
    )
    sort_order: int = Field(default=0, ge=0, description="Lower values sort first in UI lists.")


class CategoryUpdate(BaseModel):
    """Request body for ``PATCH /categories/{category_id}``. All fields optional; only fields
    explicitly present in the request payload are applied (partial update semantics)."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"name": "Deep Work", "color": "#4C6EF5"}}
    )

    name: NonEmptyStr | None = None
    color: Annotated[str, Field(max_length=32)] | None = None
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class CategoryRead(BaseModel):
    """Response representation of a category."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "Deep Work",
                "color": "#4C6EF5",
                "is_active": True,
                "sort_order": 0,
            }
        }
    )

    id: int
    name: str
    color: str | None
    is_active: bool
    sort_order: int


class CategoryListResponse(BaseModel):
    """Response for ``GET /categories``."""

    items: list[CategoryRead]
    total: int


# --- Tags -----------------------------------------------------------------------------------


class TagCreate(BaseModel):
    """Request body for ``POST /tags``."""

    model_config = ConfigDict(json_schema_extra={"example": {"name": "focus"}})

    name: NonEmptyStr


class TagUpdate(BaseModel):
    """Request body for ``PATCH /tags/{tag_id}``. Partial update semantics (see
    :class:`CategoryUpdate`)."""

    model_config = ConfigDict(json_schema_extra={"example": {"name": "deep-focus"}})

    name: NonEmptyStr | None = None
    is_active: bool | None = None


class TagRead(BaseModel):
    """Response representation of a tag."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"id": 1, "name": "focus", "is_active": True}}
    )

    id: int
    name: str
    is_active: bool


class TagListResponse(BaseModel):
    """Response for ``GET /tags``."""

    items: list[TagRead]
    total: int


# --- Entries ------------------------------------------------------------------------------------


class EntryCreateManual(BaseModel):
    """Request body for ``POST /entries`` (manual-mode entry creation).

    ``entry_mode`` is not accepted from the client: this endpoint always creates
    ``entry_mode="manual"`` entries. Timer-mode entries are only created via ``POST
    /timer/start`` / ``POST /timer/stop`` (see ``app/API_CONTRACT.md``).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Write quarterly report",
                "notes": "Draft + review with team",
                "category_id": 1,
                "tag_ids": [1, 3],
                "start_ts": "2026-07-13T09:00:00+00:00",
                "end_ts": "2026-07-13T10:30:00+00:00",
            }
        }
    )

    title: NonEmptyStr
    notes: Annotated[str, Field(max_length=4000)] | None = None
    category_id: int | None = None
    tag_ids: list[int] = Field(default_factory=list)
    start_ts: AwareDatetime
    end_ts: AwareDatetime

    @model_validator(mode="after")
    def _check_end_after_start(self) -> "EntryCreateManual":
        if self.end_ts < self.start_ts:
            raise ValueError("end_ts must be greater than or equal to start_ts")
        return self


class EntryUpdate(BaseModel):
    """Request body for ``PATCH /entries/{entry_id}``. Partial update semantics: only fields
    explicitly present in the request payload are applied.

    Applies to entries in either mode. If both ``start_ts`` and ``end_ts`` end up set (either
    newly provided or already present on the stored entry) the resulting pair must satisfy
    ``end_ts >= start_ts``; enforcing that against the *stored* value is the backend's
    responsibility since this model only sees the fields present in a given PATCH request.
    """

    model_config = ConfigDict(json_schema_extra={"example": {"title": "Write Q3 report (final)"}})

    title: NonEmptyStr | None = None
    notes: Annotated[str, Field(max_length=4000)] | None = None
    category_id: int | None = None
    tag_ids: list[int] | None = None
    start_ts: AwareDatetime | None = None
    end_ts: AwareDatetime | None = None

    @model_validator(mode="after")
    def _check_end_after_start_if_both_present(self) -> "EntryUpdate":
        if self.start_ts is not None and self.end_ts is not None and self.end_ts < self.start_ts:
            raise ValueError("end_ts must be greater than or equal to start_ts")
        return self


class EntryRead(BaseModel):
    """Response representation of an entry, with resolved category and tags."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 42,
                "title": "Write quarterly report",
                "notes": "Draft + review with team",
                "category": {
                    "id": 1,
                    "name": "Deep Work",
                    "color": "#4C6EF5",
                    "is_active": True,
                    "sort_order": 0,
                },
                "tags": [{"id": 1, "name": "focus", "is_active": True}],
                "start_ts": "2026-07-13T09:00:00+00:00",
                "end_ts": "2026-07-13T10:30:00+00:00",
                "duration_minutes": 90.0,
                "entry_mode": "manual",
                "created_at": "2026-07-13T09:00:05+00:00",
                "updated_at": "2026-07-13T10:30:02+00:00",
            }
        }
    )

    id: int
    title: str
    notes: str | None
    category: CategoryRead | None
    tags: list[TagRead]
    start_ts: datetime
    end_ts: datetime | None
    duration_minutes: float | None
    entry_mode: EntryMode
    created_at: datetime
    updated_at: datetime


class EntryListResponse(BaseModel):
    """Response for ``GET /entries``."""

    items: list[EntryRead]
    total: int
    limit: int
    offset: int


# --- Timer ----------------------------------------------------------------------------------


class TimerStartRequest(BaseModel):
    """Request body for ``POST /timer/start``.

    All fields are optional and may be filled in/edited later via ``POST /timer/stop`` or
    ``PATCH /entries/{entry_id}``. If ``title`` is omitted the backend assigns a placeholder
    (e.g. ``"Untitled"``).
    """

    model_config = ConfigDict(
        json_schema_extra={"example": {"title": "Write quarterly report", "category_id": 1}}
    )

    title: NonEmptyStr | None = None
    notes: Annotated[str, Field(max_length=4000)] | None = None
    category_id: int | None = None
    tag_ids: list[int] = Field(default_factory=list)


class TimerStopRequest(BaseModel):
    """Request body for ``POST /timer/stop``.

    All fields optional; any provided value overwrites what was set at start time. Omitted
    fields are left as-is.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"title": "Write quarterly report (final)", "tag_ids": [1, 3]}
        }
    )

    title: NonEmptyStr | None = None
    notes: Annotated[str, Field(max_length=4000)] | None = None
    category_id: int | None = None
    tag_ids: list[int] | None = None


class TimerCurrentResponse(BaseModel):
    """Response for ``GET /timer/current``. ``running`` is ``false`` (with ``entry: null``) when
    no timer is active — this endpoint always returns ``200``, never ``404``, since "no running
    timer" is a normal, expected state."""

    model_config = ConfigDict(json_schema_extra={"example": {"running": True, "entry": None}})

    running: bool
    entry: EntryRead | None


# --- Today convenience view ------------------------------------------------------------------


class TodayResponse(BaseModel):
    """Response for ``GET /today``: everything the Today screen needs in one round trip.

    ``entries`` covers the caller's local "today" (see ``app/API_CONTRACT.md`` for how the date
    boundary/timezone is resolved) and excludes the running timer, which is surfaced separately
    via ``running_timer`` even if its ``start_ts`` falls within today.
    """

    entries: list[EntryRead]
    running_timer: EntryRead | None
    recent_categories: list[CategoryRead] = Field(
        description="Active categories most recently used on an entry, most-recent first."
    )
    recent_tags: list[TagRead] = Field(
        description="Active tags most recently used on an entry, most-recent first."
    )
