"""Domain-level error types.

Route handlers raise these instead of building HTTP responses directly; a single exception
handler registered in ``app/main.py`` translates them (and FastAPI's own validation errors) into
the standard error envelope described in ``app/API_CONTRACT.md``.
"""

from typing import Any


class DomainError(Exception):
    """Base class for application errors that should be surfaced as a structured HTTP response."""

    status_code: int = 400

    def __init__(
        self,
        message: str,
        *,
        code: str = "bad_request",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


class NotFoundError(DomainError):
    """A path-referenced resource (category/tag/entry id) does not exist. Maps to ``404``."""

    status_code = 404

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="resource_not_found", details=details)


class ConflictError(DomainError):
    """A state conflict (duplicate name, timer already running/not running). Maps to ``409``."""

    status_code = 409

    def __init__(
        self,
        message: str,
        *,
        code: str = "conflict",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, details=details)


class ValidationError(DomainError):
    """A business-rule validation failure not caught by pydantic parsing. Maps to ``422``."""

    status_code = 422

    def __init__(
        self, message: str, *, fields: list[dict[str, Any]] | None = None
    ) -> None:
        super().__init__(
            message, code="validation_error", details={"fields": fields or []}
        )
