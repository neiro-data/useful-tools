// Popup-only architecture: no background service worker.
// The popup stays open for the duration of the click -> capture -> fetch flow,
// so a synchronous (async/await) chain here is sufficient; a background worker
// would add MV3 onClicked-vs-default_popup ambiguity for no benefit (see plan).

(function () {
  "use strict";

  const runtime = globalThis.browser ?? globalThis.chrome;
  const SERVER_ORIGIN = "http://127.0.0.1:8765";
  const TOKEN_KEY = "authToken";

  const statusEl = document.getElementById("status");
  const tokenInput = document.getElementById("token");
  const saveTokenBtn = document.getElementById("save-token");
  const convertBtn = document.getElementById("convert");
  const resultEl = document.getElementById("result");

  function setStatus(kind, text) {
    statusEl.className = `status status--${kind}`;
    statusEl.textContent = text;
  }

  function setResult(kind, text) {
    resultEl.hidden = false;
    resultEl.className = `result result--${kind}`;
    resultEl.textContent = text;
  }

  function unreachableHint() {
    return "Server unreachable. Start it with: uv run html2epub-server";
  }

  async function loadToken() {
    const stored = await runtime.storage.local.get(TOKEN_KEY);
    if (stored[TOKEN_KEY]) {
      tokenInput.value = stored[TOKEN_KEY];
    }
  }

  async function saveToken() {
    const value = tokenInput.value.trim();
    await runtime.storage.local.set({ [TOKEN_KEY]: value });
    setStatus("ok", "Token saved.");
    void checkHealth();
  }

  async function checkHealth() {
    try {
      const res = await fetch(`${SERVER_ORIGIN}/health`, { method: "GET" });
      if (!res.ok) {
        setStatus("error", unreachableHint());
        convertBtn.disabled = true;
        return;
      }
      const body = await res.json();
      setStatus("ok", `Server running (v${body.version ?? "?"}).`);
      convertBtn.disabled = false;
    } catch (_err) {
      setStatus("error", unreachableHint());
      convertBtn.disabled = true;
    }
  }

  async function getActiveTab() {
    const [tab] = await runtime.tabs.query({ active: true, currentWindow: true });
    if (!tab || typeof tab.id !== "number") {
      throw new Error("No active tab found.");
    }
    return tab;
  }

  async function captureActiveTab(tabId) {
    const [injection] = await runtime.scripting.executeScript({
      target: { tabId },
      func: capturePage,
    });
    if (!injection || !injection.result) {
      throw new Error("Could not capture page content.");
    }
    return injection.result;
  }

  async function convert() {
    convertBtn.disabled = true;
    resultEl.hidden = true;

    try {
      const { [TOKEN_KEY]: token } = await runtime.storage.local.get(TOKEN_KEY);
      if (!token) {
        setResult("error", "Set the auth token first.");
        return;
      }

      const tab = await getActiveTab();
      const captured = await captureActiveTab(tab.id);

      const res = await fetch(`${SERVER_ORIGIN}/convert`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Auth-Token": token,
        },
        body: JSON.stringify({
          html: captured.html,
          url: captured.url,
          title: captured.title || null,
          split_level: null,
        }),
      });

      const body = await res.json();
      if (res.ok && body.ok) {
        setResult("ok", `Saved: ${body.path}`);
      } else {
        setResult("error", body.error || `Request failed (${res.status}).`);
      }
    } catch (err) {
      setResult("error", err instanceof Error ? err.message : unreachableHint());
    } finally {
      convertBtn.disabled = false;
    }
  }

  saveTokenBtn.addEventListener("click", () => void saveToken());
  convertBtn.addEventListener("click", () => void convert());

  void loadToken();
  void checkHealth();
})();
