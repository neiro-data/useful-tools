"""Shared test helper for freezing ``datetime.now()`` in a specific application module.

Kept intentionally dependency-free (no ``freezegun``) — a small subclass swap via
``monkeypatch.setattr`` is enough for the one call site (``datetime.now(tz)``) each test needs to
control.
"""

from datetime import datetime

import pytest


def freeze_module_now(
    monkeypatch: pytest.MonkeyPatch, module_path: str, fixed_instant: datetime
) -> None:
    """Patch ``datetime`` inside ``module_path`` so ``datetime.now(tz)`` always resolves
    ``fixed_instant`` converted into the requested ``tz`` (or as-is if ``tz`` is ``None``).

    ``module_path`` is the dotted path to patch, e.g. ``"app.routers.today.datetime"`` — the
    module must do ``from datetime import datetime`` (not ``import datetime``) for this to take
    effect, since we're replacing the name bound in that module's namespace.
    """

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:  # type: ignore[override]
            if tz is None:
                return fixed_instant
            return fixed_instant.astimezone(tz)  # type: ignore[arg-type]

    monkeypatch.setattr(module_path, _FrozenDateTime)
