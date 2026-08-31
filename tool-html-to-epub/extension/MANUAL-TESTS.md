# Manual test checklist

These items are not covered by `pytest` and must be verified by hand. Run the server
(`uv run html2epub-server`) before starting.

## Chrome

- [ ] Load the unpacked extension (`chrome://extensions` → Developer mode → Load unpacked →
      `extension/chrome/`) and confirm it appears with no manifest errors.
- [ ] Click the toolbar icon on a normal article page. Confirm the popup shows "Server running"
      status, then click **Convert this page** and confirm success text (`Saved: <path>`) appears
      in the popup. This build has **no toolbar badge and no OS notification** — all status is
      popup-only, so watch the popup, not the icon.
- [ ] Stop the server, click convert again, and confirm the popup shows the "Server unreachable"
      hint with the `uv run html2epub-server` command, rather than failing silently.
- [ ] Copy the actual generated extension ID (from `chrome://extensions`, once loaded) and confirm
      a converted request succeeds — the CORS allowlist in `handler.py` matches by the
      `chrome-extension://` scheme **prefix**, not a hardcoded ID, so no config change should be
      needed when the ID differs across installs/machines. Still worth confirming a request from
      that exact origin is not rejected.
- [ ] Convert a page you're logged into (e.g. a paywalled article you have access to) and confirm
      the resulting EPUB contains the real article content, not a login wall — this is the core
      reason the extension captures the rendered DOM instead of re-fetching the URL server-side.

## Safari (blocked until Phase 4 is built)

Phase 4 (`xcrun safari-web-extension-converter`) has not been run in this repo — no full Xcode
install in this environment, only Command Line Tools. Once it has been run on a machine with full
Xcode and `extension/safari/` exists, verify:

- [ ] `xcrun safari-web-extension-converter extension/chrome/ --macos-only --project-location extension/safari/`
      completes without errors.
- [ ] The generated Xcode project builds and code-signs successfully.
- [ ] Safari → Settings → Extensions: the extension is enabled, and "Allow on Every Website" (or a
      per-site grant) is set so `activeTab` works.
- [ ] First request to `127.0.0.1` triggers the macOS **Local Network** permission prompt; confirm
      allowing it lets conversion succeed, and denying it surfaces as "server unreachable" in the
      popup rather than a silent failure.
- [ ] If the containing app is unsigned/ad-hoc, confirm Develop → Allow Unsigned Extensions is set
      (note: this resets on every Safari restart).

## Not applicable to this build

- ~~macOS notification permission~~ — not applicable. `popup.js` uses no `chrome.notifications` /
  `browser.notifications` calls; all status is rendered inline in the popup DOM.
