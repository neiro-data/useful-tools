# API Contract — Phase 1 (Core Capture)

Status: **design spec**, not yet implemented. Backend-developer implements against this contract
and the Pydantic models in `app/schemas.py`. Reports/exports are **Phase 2** and out of scope here.

Base URL: `http://127.0.0.1:8000` (localhost only; no auth in Phase 1 — single-user, offline-first
desktop use case). All request/response bodies are `application/json`. All timestamps are
ISO-8601, UTC, with explicit offset (e.g. `2026-07-13T09:00:00+00:00`) — matching the storage
format in `app/schema.py`.

## Conventions

- **Resource routers**, mounted under `app/api.py`'s root router:
  - `/categories` — `app/routers/categories.py`
  - `/tags` — `app/routers/tags.py`
  - `/entries` — `app/routers/entries.py`
  - `/timer` — `app/routers/timer.py`
  - `/today` — composed read; lives in `app/routers/today.py` (or inline in `api.py` — backend's
    call, it's a thin aggregation with no independent state).
- **Pagination:** `limit` (default 50, max 200) / `offset` (default 0) query params on all list
  endpoints. Response envelope includes `total` (count matching filters, ignoring
  limit/offset) alongside `items`.
- **Partial updates:** all `PATCH` endpoints use partial-update semantics — only fields present
  in the JSON body are applied (server reads the request with `exclude_unset=True`); omitted
  fields are left untouched. `null` is a valid, explicit "clear this field" value for nullable
  fields (e.g. `category_id`, `notes`).
- **Idempotency:** `PATCH` and the deactivate endpoints are idempotent (calling twice with the
  same input yields the same end state, second call still `200`). `POST` create endpoints are
  not idempotent (no client-supplied idempotency key in Phase 1).
- **Soft delete for categories/tags:** categories and tags are never hard-deleted (entries may
  reference them, and reports need historical names) — only deactivated (`is_active=false`).
  Entries support hard `DELETE`.

## Error envelope

Every non-2xx JSON response uses this shape (see `ErrorResponse` / `ErrorDetail` in
`app/schemas.py`):

```json
{
  "error": {
    "code": "resource_not_found",
    "message": "Category 999 does not exist.",
    "details": { "category_id": 999 }
  }
}
```

`code` is a stable, machine-readable `snake_case` string the frontend can branch on; `message` is
safe to show directly to the user; `details` is optional structured context.

Standard error codes used across endpoints:

| HTTP status | `code`                     | When |
|---|---|---|
| 400 | `bad_request`               | Malformed request not covered by a more specific code. |
| 404 | `resource_not_found`         | Path-referenced resource (category/tag/entry id) doesn't exist. |
| 409 | `conflict`                  | Generic state conflict (e.g. referenced tag/category id doesn't exist on create). |
| 409 | `timer_already_running`     | `POST /timer/start` called while a timer is active. `details.running_entry_id` set. |
| 409 | `no_running_timer`          | `POST /timer/stop` called while no timer is active. |
| 422 | `validation_error`          | Pydantic/FastAPI request validation failure. `details.fields` is a list of `{loc, msg}`. Backend must register an exception handler translating FastAPI's default 422 body into this envelope, for consistency across all endpoints. |
| 500 | `internal_error`            | Unhandled server error. |

FastAPI's default validation error body is **not** used as-is; it must be normalized into the
envelope above (see the `422` row) so every error response — validation or otherwise — has the
same shape for the frontend to handle generically.

---

## Categories

| Method | Path | Purpose |
|---|---|---|
| GET | `/categories` | List categories. |
| POST | `/categories` | Create a category. |
| GET | `/categories/{category_id}` | Get one category. |
| PATCH | `/categories/{category_id}` | Partially update a category. |
| POST | `/categories/{category_id}/deactivate` | Soft-deactivate a category (`is_active=false`). |

### `GET /categories`

Query params: `include_inactive: bool = false`, `limit: int = 50` (max 200), `offset: int = 0`.
Default sort: `sort_order ASC, name ASC`.

- `200` → `CategoryListResponse` (`{items: CategoryRead[], total: int}`).

### `POST /categories`

Body: `CategoryCreate` (`name` required, non-empty, unique; `color` optional; `sort_order`
optional, default `0`).

- `201` → `CategoryRead`.
- `409 conflict` → `name` already exists (case-sensitive match on the DB's `UNIQUE` constraint).
- `422 validation_error` → e.g. blank `name`.

### `GET /categories/{category_id}`

- `200` → `CategoryRead`.
- `404 resource_not_found`.

### `PATCH /categories/{category_id}`

Body: `CategoryUpdate` (all fields optional: `name`, `color`, `sort_order`, `is_active`).

- `200` → updated `CategoryRead`.
- `404 resource_not_found`.
- `409 conflict` → rename collides with another category's `name`.
- `422 validation_error`.

Note: `is_active` is settable here too (e.g. to reactivate); `POST .../deactivate` is a
convenience shortcut for the common "turn off" action, not the only way to change it.

### `POST /categories/{category_id}/deactivate`

No body. Sets `is_active=false`. Idempotent (deactivating an already-inactive category is a
no-op, still `200`).

- `200` → updated `CategoryRead`.
- `404 resource_not_found`.

---

## Tags

| Method | Path | Purpose |
|---|---|---|
| GET | `/tags` | List tags. |
| POST | `/tags` | Create a tag. |
| GET | `/tags/{tag_id}` | Get one tag. |
| PATCH | `/tags/{tag_id}` | Partially update a tag. |
| POST | `/tags/{tag_id}/deactivate` | Soft-deactivate a tag. |

Same shape/semantics as categories, minus `color`/`sort_order`.

### `GET /tags`

Query params: `include_inactive: bool = false`, `limit: int = 50` (max 200), `offset: int = 0`.
Default sort: `name ASC`.

- `200` → `TagListResponse` (`{items: TagRead[], total: int}`).

### `POST /tags`

Body: `TagCreate` (`name` required, non-empty, unique).

- `201` → `TagRead`.
- `409 conflict` → duplicate `name`.
- `422 validation_error`.

### `GET /tags/{tag_id}`

- `200` → `TagRead`.
- `404 resource_not_found`.

### `PATCH /tags/{tag_id}`

Body: `TagUpdate` (`name`, `is_active`, both optional).

- `200` → updated `TagRead`.
- `404 resource_not_found`.
- `409 conflict` → rename collides with another tag.
- `422 validation_error`.

### `POST /tags/{tag_id}/deactivate`

No body. Idempotent.

- `200` → updated `TagRead`.
- `404 resource_not_found`.

---

## Entries (manual mode + shared entry operations)

| Method | Path | Purpose |
|---|---|---|
| GET | `/entries` | List entries with filters. |
| POST | `/entries` | Create a manual-mode entry. |
| GET | `/entries/{entry_id}` | Get one entry. |
| PATCH | `/entries/{entry_id}` | Update an entry (either mode). |
| DELETE | `/entries/{entry_id}` | Hard-delete an entry. |

These endpoints operate on entries of **either** `entry_mode`. Timer-mode entries are *created*
only via `/timer/start` + `/timer/stop`, but once they exist they can be read/edited/deleted the
same way as manual entries through this router.

### `GET /entries`

Query params (all optional, combinable with AND semantics):

| Param | Type | Meaning |
|---|---|---|
| `start_date` | `date` (`YYYY-MM-DD`) | Include entries with `start_ts >= start_date 00:00:00Z`. |
| `end_date` | `date` (`YYYY-MM-DD`) | Include entries with `start_ts <= end_date 23:59:59Z` (inclusive day). |
| `category_id` | `int` | Only entries with this category. |
| `tag_id` | `int` | Only entries linked to this tag (via `entry_tags`). |
| `entry_mode` | `"timer" \| "manual"` | Only entries of this mode. |
| `limit` | `int`, default 50, max 200 | Page size. |
| `offset` | `int`, default 0 | Page offset. |

Default sort: `start_ts DESC` (most recent first).

- `200` → `EntryListResponse` (`{items: EntryRead[], total, limit, offset}`).
- `422 validation_error` → e.g. `end_date < start_date`, unrecognized `entry_mode` value.

### `POST /entries`

Body: `EntryCreateManual` (`title` required; `notes`, `category_id`, `tag_ids` optional;
`start_ts` and `end_ts` both **required**; `end_ts >= start_ts` enforced by the schema). Always
creates `entry_mode="manual"` — the client cannot set `entry_mode` on this endpoint.

Duration rule: `duration_minutes = (end_ts - start_ts) in minutes`, computed and stored by the
backend at write time (not trusted from the client, not left for the frontend to derive).

- `201` → `EntryRead`.
- `404 resource_not_found` → `category_id` or a `tag_ids` entry doesn't exist. `details` names
  which id(s) were invalid.
- `422 validation_error` → blank `title`, missing `start_ts`/`end_ts`, `end_ts < start_ts`.

### `GET /entries/{entry_id}`

- `200` → `EntryRead`.
- `404 resource_not_found`.

### `PATCH /entries/{entry_id}`

Body: `EntryUpdate` (all fields optional: `title`, `notes`, `category_id`, `tag_ids`, `start_ts`,
`end_ts`). `entry_mode` is **not** editable via this endpoint (immutable after creation).

Duration rule: whenever the *effective* `start_ts`/`end_ts` pair (after applying the patch on top
of the stored row) both resolve to non-null, the backend recomputes and overwrites
`duration_minutes`; if `end_ts` resolves to `null` (e.g. clearing it), `duration_minutes` is set
back to `null` too. The backend must validate `end_ts >= start_ts` against the *effective* pair,
not just the fields present in this one request (the schema-level validator in `EntryUpdate` only
catches the case where both are supplied in the same request).

- `200` → updated `EntryRead`.
- `404 resource_not_found` → entry, `category_id`, or a `tag_ids` entry doesn't exist.
- `422 validation_error` → effective `end_ts < start_ts`, blank `title`.

### `DELETE /entries/{entry_id}`

Hard delete (cascades to `entry_tags` rows via `ON DELETE CASCADE`). If this entry is the
currently-running timer, deleting it clears the "running timer" state (there is simply no longer
any entry with `end_ts IS NULL`).

- `204` → no body.
- `404 resource_not_found`.

---

## Timer

| Method | Path | Purpose |
|---|---|---|
| POST | `/timer/start` | Start a new running timer. |
| GET | `/timer/current` | Get the currently-running timer, if any. |
| POST | `/timer/stop` | Stop the running timer. |

### Single-active-timer rule

At most **one** entry may have `end_ts IS NULL` (`entry_mode='timer'`) at any time. This is
enforced at the application layer (backend-developer should also add a guard query — e.g. `SELECT
... WHERE end_ts IS NULL` — inside the same transaction as the insert, to close the race between
check and insert):

- `POST /timer/start` while a timer is already running → **`409 Conflict`**, `code:
  "timer_already_running"`, with `details.running_entry_id` set to the id of the entry already in
  progress. The existing timer is left untouched — the client must explicitly stop it (or the
  user resolves it in the UI) before starting a new one. No new entry is created.
- `POST /timer/stop` while no timer is running → **`409 Conflict`**, `code: "no_running_timer"`.

### `POST /timer/start`

Body: `TimerStartRequest` (`title` optional — defaults to `"Untitled"` if omitted; `notes`,
`category_id`, `tag_ids` optional). Creates an entry with `entry_mode="timer"`, `start_ts = now()`
(server-generated, UTC), `end_ts = NULL`, `duration_minutes = NULL`.

- `201` → `EntryRead` (the newly-started running entry; `end_ts` and `duration_minutes` are
  `null`).
- `409 timer_already_running` (see above).
- `404 resource_not_found` → invalid `category_id`/`tag_ids`.
- `422 validation_error`.

### `GET /timer/current`

No params. Always `200` — "no timer running" is a normal state, not an error/404.

- `200` → `TimerCurrentResponse`: `{"running": false, "entry": null}` when idle, or
  `{"running": true, "entry": EntryRead}` (with `end_ts`/`duration_minutes` still `null`) when a
  timer is active.

### `POST /timer/stop`

Body: `TimerStopRequest` (all fields optional — `title`, `notes`, `category_id`, `tag_ids`; any
field provided overwrites what was set at start time, omitted fields are left as-is). Sets
`end_ts = now()` (server-generated, UTC) on the running entry and computes `duration_minutes =
(end_ts - start_ts) in minutes`.

- `200` → the stopped `EntryRead` (now with `end_ts` and `duration_minutes` populated).
- `409 no_running_timer` (see above).
- `404 resource_not_found` → invalid `category_id`/`tag_ids` supplied in the stop body.
- `422 validation_error`.

---

## Today (convenience aggregation)

| Method | Path | Purpose |
|---|---|---|
| GET | `/today` | Everything the Today screen needs in one round trip. |

### `GET /today`

Composes, in a single response, what would otherwise take 3 separate calls (`GET /entries?
start_date=<today>&end_date=<today>`, `GET /timer/current`, plus a "recently used" query with no
standalone endpoint of its own in Phase 1). Implemented as its own thin read — **not** a client
composing three requests — to keep the Today screen to one network round trip on a
resource-constrained localhost desktop client and to avoid the frontend re-implementing "what
counts as today."

"Today" boundary: resolved server-side using `settings.timezone` (see `app/schema.py`'s
`settings` table) applied to the server's current time, converted back to the UTC
`start_ts` range used to filter `entries`. Entries are matched on `start_ts` falling within
`[today 00:00:00, today 23:59:59]` in that timezone.

- `200` → `TodayResponse`:
  - `entries: EntryRead[]` — today's entries, `start_ts DESC`, **excluding** the running timer
    entry even if its `start_ts` is today (surfaced separately, since it's incomplete/in-progress
    and the UI treats it differently).
  - `running_timer: EntryRead | null` — same payload as `GET /timer/current`'s `entry` field.
  - `recent_categories: CategoryRead[]` — active categories most recently used on any entry
    (`ORDER BY MAX(entries.start_ts) DESC` across entries referencing each category), capped at a
    small fixed count (suggest 5) to keep the payload light.
  - `recent_tags: TagRead[]` — same idea via `entry_tags`, capped at a small fixed count (suggest
    8).

No query params in Phase 1 (always "today" in the configured timezone). No additional error
cases beyond the standard `500 internal_error`.
