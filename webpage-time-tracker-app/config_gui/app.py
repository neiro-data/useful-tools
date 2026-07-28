"""Tkinter settings window — `uv run wtt-config`.

Add sites, change per-site limits, and see what is registered, without editing
the userscript. Tkinter rather than an in-page panel because the host pages
being tracked (YouTube, X) send a CSP that blocks third-party images, which
would break the icon column exactly where it is used.
"""

from __future__ import annotations

import threading
import tkinter as tk
from collections.abc import Callable
from http.server import ThreadingHTTPServer
from tkinter import messagebox, ttk

from config_gui import icons, regex_suggest, server, store
from config_gui.models import Config, ConfigError, Site, host_regex
from config_gui.regex_suggest import Suggestion

_PAD = 10


class Tooltip:
    """A small delay-free popup shown on hover, bound to one or more widgets."""

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self._text = text
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def _show(self, event: tk.Event) -> None:
        if self._tip is not None:
            return
        self._tip = tk.Toplevel(event.widget)
        self._tip.wm_overrideredirect(True)
        x = event.widget.winfo_rootx()
        y = event.widget.winfo_rooty() + event.widget.winfo_height() + 4
        self._tip.wm_geometry(f"+{x}+{y}")
        ttk.Label(
            self._tip,
            text=self._text,
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            padding=4,
            wraplength=280,
        ).pack()

    def _hide(self, _event: tk.Event) -> None:
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None


class SuggestPreviewDialog(tk.Toplevel):
    """Shows a proposed host/path with a match-samples table; `result` is Apply's Suggestion."""

    def __init__(self, parent: tk.Toplevel, suggestion: Suggestion, domain: str) -> None:
        super().__init__(parent)
        self.result: Suggestion | None = None
        self.title("Suggested regex")
        self.resizable(False, False)
        self.transient(parent)
        self._suggestion = suggestion

        body = ttk.Frame(self, padding=_PAD)
        body.grid(sticky="nsew")

        row = 0
        if suggestion.host:
            ttk.Label(body, text=f"Host: {suggestion.host}").grid(
                row=row, column=0, columnspan=3, sticky="w", pady=2
            )
            row += 1
        if suggestion.path:
            ttk.Label(body, text=f"Path: {suggestion.path}").grid(
                row=row, column=0, columnspan=3, sticky="w", pady=2
            )
            row += 1
        ttk.Label(body, text=suggestion.note, foreground="#666", wraplength=340).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )
        row += 1

        for sample_url, matched, expected in regex_suggest.match_samples(suggestion, domain):
            ok = matched == expected
            mark = "✓" if ok else "✗"
            color = "#2a7" if ok else "#c33"
            ttk.Label(body, text=mark, foreground=color).grid(row=row, column=0, sticky="w")
            ttk.Label(body, text=sample_url).grid(row=row, column=1, sticky="w", padx=(4, 0))
            row += 1

        buttons = ttk.Frame(body)
        buttons.grid(row=row, column=0, columnspan=3, sticky="e", pady=(_PAD, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="Apply", command=self._apply).pack(side="right")
        self.grab_set()

    def _apply(self) -> None:
        self.result = self._suggestion
        self.destroy()


class SiteDialog(tk.Toplevel):
    """Add/Edit modal. `result` is the new Site, or None if cancelled."""

    def __init__(self, parent: tk.Tk, site: Site | None = None) -> None:
        super().__init__(parent)
        self.result: Site | None = None
        self.title("Edit site" if site else "Add site")
        self.resizable(False, False)
        self.transient(parent)

        advanced = bool(site and not site.domain)
        self._var_name = tk.StringVar(value=site.name if site else "")
        self._var_domain = tk.StringVar(value=(site.domain if site else ""))
        self._var_host = tk.StringVar(value=(site.host if site else ""))
        self._var_path = tk.StringVar(value=(site.path or "" if site else ""))
        self._var_hint = tk.StringVar(value="")
        self._var_limit = tk.StringVar(value=str(site.limit_minutes if site else 15))
        self._var_advanced = tk.BooleanVar(value=advanced)

        body = ttk.Frame(self, padding=_PAD)
        body.grid(sticky="nsew")
        # ttk.Spinbox subclasses ttk.Entry, so one type covers every row.
        rows: list[tuple[str, ttk.Entry]] = [
            ("Name", ttk.Entry(body, textvariable=self._var_name, width=34)),
            ("Domain", ttk.Entry(body, textvariable=self._var_domain, width=34)),
            ("Host regex", ttk.Entry(body, textvariable=self._var_host, width=34)),
            ("Path regex (optional)", ttk.Entry(body, textvariable=self._var_path, width=34)),
            (
                "Suggest hint (optional)",
                ttk.Entry(body, textvariable=self._var_hint, width=34),
            ),
            ("Limit (minutes)", ttk.Spinbox(body, from_=1, to=1440, textvariable=self._var_limit)),
        ]
        _tooltip_text = (
            "Needs the Claude Code CLI (`claude`) installed and logged in. "
            "Falls back to ANTHROPIC_API_KEY if set."
        )
        self._widgets: dict[str, ttk.Entry] = {}
        for row, (label, widget) in enumerate(rows):
            ttk.Label(body, text=label).grid(row=row, column=0, sticky="w", pady=3, padx=(0, 8))
            widget.grid(row=row, column=1, sticky="ew", pady=3)
            self._widgets[label] = widget
            if label == "Domain":
                self._btn_suggest = ttk.Button(body, text="Suggest…", command=self._suggest)
                self._btn_suggest.grid(row=row, column=2, sticky="w", padx=(6, 0))
                Tooltip(self._btn_suggest, _tooltip_text)
            if label == "Suggest hint (optional)":
                ttk.Label(
                    body,
                    text='e.g. "only Shorts" — used by Suggest, not saved',
                    foreground="#888",
                ).grid(row=row, column=2, sticky="w", padx=(6, 0))

        ttk.Checkbutton(
            body,
            text="Advanced: write the host regex myself",
            variable=self._var_advanced,
            command=self._sync_advanced,
        ).grid(row=len(rows), column=0, columnspan=2, sticky="w", pady=(6, 0))

        buttons = ttk.Frame(body)
        buttons.grid(row=len(rows) + 1, column=0, columnspan=2, sticky="e", pady=(_PAD, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="Save", command=self._save).pack(side="right")

        self._sync_advanced()
        self.bind("<Return>", lambda _event: self._save())
        self.bind("<Escape>", lambda _event: self.destroy())
        self.grab_set()
        self._widgets["Name"].focus_set()

    def _sync_advanced(self) -> None:
        advanced = self._var_advanced.get()
        self._widgets["Domain"].configure(state="disabled" if advanced else "normal")
        self._widgets["Host regex"].configure(state="normal" if advanced else "disabled")
        if not advanced and self._var_domain.get():
            self._var_host.set("")

    def _suggest(self) -> None:
        domain = self._var_domain.get().strip() or self._var_host.get().strip()
        if not domain:
            messagebox.showinfo("Suggest", "Enter a domain first.", parent=self)
            return
        hint = self._var_hint.get().strip() or None
        advanced = self._var_advanced.get()
        self._btn_suggest.configure(state="disabled", text="Suggesting…")
        threading.Thread(
            target=self._suggest_worker, args=(domain, hint, advanced), daemon=True
        ).start()

    def _suggest_worker(self, domain: str, hint: str | None, advanced: bool) -> None:
        try:
            suggestion = None if hint else regex_suggest.suggest_local(domain)
            if suggestion is None:
                suggestion = regex_suggest.suggest_via_claude(domain, hint, advanced=advanced)
            suggestion = regex_suggest.validate(suggestion, advanced=advanced)
        except ConfigError as err:
            self._marshal(self._suggest_failed, str(err))
            return
        self._marshal(self._suggest_done, suggestion, domain)

    def _marshal(self, func: Callable[..., None], *args: object) -> None:
        """`self.after(...)`, but tolerant of the window having been torn down mid-flight."""
        try:
            self.after(0, func, *args)
        except tk.TclError:
            pass

    def _suggest_failed(self, message: str) -> None:
        if not self.winfo_exists():
            return
        self._btn_suggest.configure(state="normal", text="Suggest…")
        messagebox.showinfo("Suggest", message, parent=self)

    def _suggest_done(self, suggestion: Suggestion, domain: str) -> None:
        if not self.winfo_exists():
            return
        self._btn_suggest.configure(state="normal", text="Suggest…")
        dialog = SuggestPreviewDialog(self, suggestion, domain)
        self.wait_window(dialog)
        if dialog.result is None:
            return
        if dialog.result.path is not None:
            self._var_path.set(dialog.result.path)
        if self._var_advanced.get() and dialog.result.host is not None:
            self._var_host.set(dialog.result.host)

    def _save(self) -> None:
        try:
            limit = int(self._var_limit.get())
        except ValueError:
            messagebox.showerror("Invalid limit", "Limit must be a whole number.", parent=self)
            return
        try:
            host = (
                self._var_host.get().strip()
                if self._var_advanced.get()
                else host_regex(self._var_domain.get())
            )
            self.result = Site(
                name=self._var_name.get().strip(),
                host=host,
                limit_minutes=limit,
                path=self._var_path.get().strip() or None,
            ).validated()
        except ConfigError as err:
            messagebox.showerror("Invalid site", str(err), parent=self)
            return
        self.destroy()


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Webpage Time Tracker — settings")
        self.minsize(620, 340)
        self.config_data: Config = store.load()
        self._images: dict[str, tk.PhotoImage] = {}
        self._httpd: ThreadingHTTPServer | None = None

        frame = ttk.Frame(self, padding=_PAD)
        frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(
            frame, columns=("domain", "path", "limit"), selectmode="browse", height=10
        )
        self.tree.heading("#0", text="Site")
        self.tree.heading("domain", text="Domain")
        self.tree.heading("path", text="Path")
        self.tree.heading("limit", text="Limit")
        self.tree.column("#0", width=200, stretch=False)
        self.tree.column("domain", width=180)
        self.tree.column("path", width=140)
        self.tree.column("limit", width=70, anchor="e")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _event: self._edit())

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(_PAD, 0))
        ttk.Button(buttons, text="Add", command=self._add).pack(side="left")
        ttk.Button(buttons, text="Edit", command=self._edit).pack(side="left", padx=6)
        ttk.Button(buttons, text="Remove", command=self._remove).pack(side="left")

        self.status = ttk.Label(frame, text="", foreground="#666")
        self.status.pack(fill="x", pady=(_PAD, 0))

        self._start_server()
        self._refresh()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # -- server ------------------------------------------------------------
    def _start_server(self) -> None:
        try:
            self._httpd, _thread = server.serve_forever_in_background()
        except OSError as err:
            self._set_status(f"Config server not running ({err}). Settings still save to disk.")
            return
        self._set_status(f"Serving {server.CONFIG_URL} — reload a tracked tab to apply changes.")

    def _set_status(self, text: str) -> None:
        self.status.configure(text=text)

    def _on_close(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
        self.destroy()

    # -- list --------------------------------------------------------------
    def _refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for index, site in enumerate(self.config_data.sites):
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                text=f" {site.name}",
                image=self._image_for(site),
                values=(site.domain or "(regex)", site.path or "—", f"{site.limit_minutes} min"),
            )

    def _image_for(self, site: Site) -> tk.PhotoImage:
        """Cached icon if present; the globe now and the real one once fetched."""
        domain = site.domain
        cached = icons.icon_path(domain) if domain else icons.globe_path()
        if not cached.exists():
            threading.Thread(
                target=self._fetch_icon, args=(domain,), name="wtt-icon", daemon=True
            ).start()
            cached = icons.globe_path()
        key = str(cached)
        if key not in self._images:
            self._images[key] = tk.PhotoImage(file=key)
        return self._images[key]

    def _fetch_icon(self, domain: str) -> None:
        icons.fetch(domain)
        self.after(0, self._refresh)

    def _selected(self) -> int | None:
        selection = self.tree.selection()
        return int(selection[0]) if selection else None

    def _save(self) -> None:
        try:
            store.save(self.config_data)
        except (ConfigError, OSError) as err:
            messagebox.showerror("Could not save", str(err), parent=self)
            return
        self._refresh()

    def _add(self) -> None:
        dialog = SiteDialog(self)
        self.wait_window(dialog)
        if dialog.result is None:
            return
        self.config_data.sites.append(dialog.result)
        self._save()

    def _edit(self) -> None:
        index = self._selected()
        if index is None:
            return
        dialog = SiteDialog(self, self.config_data.sites[index])
        self.wait_window(dialog)
        if dialog.result is None:
            return
        self.config_data.sites[index] = dialog.result
        self._save()

    def _remove(self) -> None:
        index = self._selected()
        if index is None:
            return
        site = self.config_data.sites[index]
        if not messagebox.askyesno("Remove site", f"Stop tracking {site.name}?", parent=self):
            return
        del self.config_data.sites[index]
        self._save()


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
