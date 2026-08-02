from __future__ import annotations

import inspect
import tkinter as tk
from collections.abc import Iterator
from tkinter import messagebox

import pytest

from config_gui import app as app_module
from config_gui import regex_suggest
from config_gui.models import Site
from config_gui.regex_suggest import Suggestion, SuggestUnavailable


def _tk_root() -> tk.Tk | None:
    """A real display-backed Tk root, or None if this environment can't make one."""
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError:
        return None
    return root


@pytest.fixture
def root() -> Iterator[tk.Tk]:
    instance = _tk_root()
    if instance is None:
        pytest.skip("no display available to create a Tk root")
    yield instance
    instance.destroy()


def test_no_declared_attribute_shadows_tkinter_misc_internals(root: tk.Tk) -> None:
    """Regression guard for the `self._name = StringVar(...)` shadow bug.

    `tkinter.Toplevel.__init__`/`Tk.__init__` set their own bookkeeping (e.g.
    `_name`, the widget's Tk path name) as plain instance attributes before any
    subclass body runs. Reassigning one of those names in `SiteDialog`/`App`
    (as `self._name = StringVar(...)` used to) breaks widget teardown —
    `destroy()` hashes `_name`, which raises for a Tk Variable, not a string.
    This greps the class source for `self.<name> =` assignments and asserts
    none collide with attribute names a bare `Toplevel`/`Tk` already carries.
    """
    reserved = set(vars(tk.Toplevel(root)))
    reserved |= set(vars(root))
    # `_name` is the specific attribute Tk uses internally for the widget path.
    assert "_name" in reserved

    for cls in (app_module.SiteDialog, app_module.App):
        source = inspect.getsource(cls)
        assigned = {
            line.split("self.", 1)[1].split(" ", 1)[0].split("=", 1)[0].strip()
            for line in source.splitlines()
            if "self." in line and "=" in line and not line.strip().startswith("#")
        }
        colliding = assigned & reserved
        assert not colliding, f"{cls.__name__} shadows tkinter internals: {colliding}"


def test_site_dialog_construct_and_destroy_does_not_raise(root: tk.Tk) -> None:
    dialog = app_module.SiteDialog(root)
    # This used to raise TypeError: unhashable type: 'StringVar' when `_name`
    # was shadowed by a StringVar instead of Tk's own widget path string.
    dialog.destroy()


def test_site_dialog_save_populates_result(root: tk.Tk) -> None:
    dialog = app_module.SiteDialog(root)
    dialog._var_name.set("Hacker News")
    dialog._var_domain.set("news.ycombinator.com")
    dialog._var_limit.set("20")

    dialog._save()

    assert dialog.result is not None
    assert dialog.result.name == "Hacker News"
    assert dialog.result.limit_minutes == 20


def test_site_dialog_edit_prefills_from_existing_site(root: tk.Tk) -> None:
    site = Site.from_domain("Hacker News", "news.ycombinator.com", 20)
    dialog = app_module.SiteDialog(root, site)

    assert dialog._var_name.get() == "Hacker News"
    assert dialog._var_limit.get() == "20"

    dialog._var_limit.set("45")
    dialog._save()

    assert dialog.result is not None
    assert dialog.result.limit_minutes == 45
    dialog.destroy()


# -- Suggest flow --------------------------------------------------------------


def test_suggest_worker_failure_marshals_suggest_failed(
    root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    dialog = app_module.SiteDialog(root)
    monkeypatch.setattr(regex_suggest, "suggest_local", lambda _domain: None)

    def _raise(*_args: object, **_kwargs: object) -> Suggestion:
        raise SuggestUnavailable("no CLI, no key")

    monkeypatch.setattr(regex_suggest, "suggest_via_claude", _raise)

    calls: list[str] = []
    monkeypatch.setattr(dialog, "_suggest_failed", lambda message: calls.append(message))

    dialog._suggest_worker("example.com", None, False)
    root.update()

    assert calls == ["no CLI, no key"]
    dialog.destroy()


def test_suggest_worker_success_marshals_suggest_done(
    root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    dialog = app_module.SiteDialog(root)
    suggestion = Suggestion(host=None, path="^/watch(/|$)", note="videos")
    monkeypatch.setattr(regex_suggest, "suggest_local", lambda _domain: suggestion)

    seen: list[tuple[Suggestion, str]] = []
    monkeypatch.setattr(
        dialog, "_suggest_done", lambda suggestion, domain: seen.append((suggestion, domain))
    )

    dialog._suggest_worker("youtube.com", None, False)
    root.update()

    assert seen == [(suggestion, "youtube.com")]
    dialog.destroy()


def test_suggest_failed_reenables_button_and_shows_message(
    root: tk.Tk, monkeypatch: pytest.MonkeyPatch
) -> None:
    dialog = app_module.SiteDialog(root)
    dialog._btn_suggest.configure(state="disabled", text="Suggesting…")
    shown: list[str] = []
    monkeypatch.setattr(
        messagebox, "showinfo", lambda _title, message, **_kwargs: shown.append(message)
    )

    dialog._suggest_failed("boom")

    assert str(dialog._btn_suggest["state"]) == "normal"
    assert shown == ["boom"]
    dialog.destroy()
