// ==UserScript==
// @name         Webpage Time Tracker
// @namespace    https://github.com/neiro-data/useful-tools
// @version      0.3.0
// @description  Tracks focused time per time-sink site against that site's own daily limit, then escalates nudges once you go over.
// @author       neiro
// @match        *://*/*
// @run-at       document-start
// @noframes
// @inject-into  content
// @grant        GM.getValue
// @grant        GM.setValue
// @grant        GM.xmlHttpRequest
// ==/UserScript==

// ---------------------------------------------------------------------------
// Platform-agnostic core. Exports main(adapter); a platform adapter file
// (adapter-gm.js or adapter-safari.js) builds the adapter object and calls
// this with it. See the adapter contract in the repo README for the shape
// adapters must implement: getValue, setValue, fetchConfig, registerMenu.
// ---------------------------------------------------------------------------
(function () {
  'use strict';

  async function main(adapter) {
    // -------------------------------------------------------------------------
    // CONFIG
    //
    // Settings live in ~/.webpage-time-tracker/config.json, edited with the
    // Tkinter app (`uv run wtt-config`) and served on loopback while its window
    // is open. This script never blocks on that: it renders from the copy
    // cached in storage, then refreshes it in the background. The defaults
    // below are the fallback for a fresh install with no cache and no server.
    // -------------------------------------------------------------------------
    const DEFAULTS = {
      // The day rolls over at this local hour. 4am rather than midnight, so
      // "it resets in two minutes" isn't available at 23:58.
      dayStartHour: 4,
      // No input for this long and the clock stops, even on a focused tab.
      idleSeconds: 60,
      // How long a dismissed overlay stays gone.
      snoozeMinutes: 5,
      // Days of per-site history kept. Nothing enforces against it — it
      // exists so "am I actually improving?" is answerable.
      historyDays: 14,

      // Each site carries its own daily limit — there is no pooled budget.
      // host is matched against location.hostname, path against
      // location.pathname. Omit path to track the whole site.
      sites: [
        { name: 'YouTube Shorts', host: '(^|\\.)youtube\\.com$', path: '^/shorts(/|$)', limitMinutes: 15 },
        { name: 'Instagram Reels', host: '(^|\\.)instagram\\.com$', path: '^/reels?(/|$)', limitMinutes: 15 },
        { name: 'X', host: '(^|\\.)(x|twitter)\\.com$', limitMinutes: 30 },
      ],
    };

    // Not user-settable — implementation detail of the clock, not a
    // preference.
    const TICK_MS = 1000;
    const SAVE_EVERY_SECONDS = 5;

    const CONFIG_KEY = 'wtt.config.v1';
    const CONFIG_FETCHED_KEY = 'wtt.config.fetchedAt';
    const CONFIG_URL = 'http://127.0.0.1:8787/config.json';
    // The refresh runs on every page, so it is rate-limited across all tabs.
    const CONFIG_REFRESH_MS = 30000;
    // A loopback that's unreachable (server closed, or blocked by Safari's
    // local-network policy) is the normal state — the config GUI is only open
    // occasionally — so failures back off the poll interval instead of
    // stopping it permanently. Delay doubles per consecutive failure, capped
    // here, and resets to CONFIG_REFRESH_MS on the next success.
    const MAX_CONFIG_POLL_MS = 10 * 60 * 1000;

    // -------------------------------------------------------------------------
    // Serialized storage I/O.
    //
    // A boolean mutex would drop a resync() call that arrives while a write is
    // in flight — and dropped resyncs are exactly the ones that matter (tab
    // reactivation after another tab advanced the counter). Chaining onto a
    // single promise queues every storage mutation instead of dropping any.
    // -------------------------------------------------------------------------
    let ioChain = Promise.resolve();
    const serialize = (fn) => (ioChain = ioChain.then(fn, fn));

    // A bad pattern from the config file must not take the whole script down
    // at document-start, so each site is compiled independently and a broken
    // one is dropped rather than thrown.
    function compile(raw) {
      const source = raw && Array.isArray(raw.sites) ? raw : DEFAULTS;
      const pick = (key, min, max) => {
        const value = source[key];
        return typeof value === 'number' && isFinite(value) && value >= min && value <= max
          ? value
          : DEFAULTS[key];
      };
      const rules = [];
      for (const site of source.sites) {
        if (!site || typeof site.name !== 'string' || !site.name) continue;
        if (typeof site.limitMinutes !== 'number' || !(site.limitMinutes > 0)) continue;
        try {
          rules.push({
            name: site.name,
            host: new RegExp(site.host),
            path: site.path ? new RegExp(site.path) : null,
            limitMinutes: site.limitMinutes,
          });
        } catch (err) {
          /* unusable pattern — skip this site */
        }
      }
      return {
        dayStartHour: pick('dayStartHour', 0, 23),
        idleSeconds: pick('idleSeconds', 5, 86400),
        snoozeMinutes: pick('snoozeMinutes', 1, 1440),
        historyDays: pick('historyDays', 1, 365),
        rules: rules.length ? rules : compile(DEFAULTS).rules,
      };
    }

    let CONFIG = compile(await adapter.getValue(CONFIG_KEY, DEFAULTS));

    // Called with the fresh config once the main path is ready to apply it.
    // Left null on pages that early-out below — the cache is still updated,
    // so a reload picks up a site that was only just added.
    let onFreshConfig = null;
    let configFailures = 0;
    let configPollHandle = null;
    // Set only after the host early-out below. Pages that bail there must
    // warm the cache once but never schedule a recurring poll.
    let pollingStarted = false;

    // Self-scheduling instead of setInterval so the delay can grow on
    // failure and shrink back to the base on the next success.
    function reschedulePoll() {
      if (!pollingStarted) return;
      if (configPollHandle !== null) clearTimeout(configPollHandle);
      const delay =
        configFailures > 0
          ? Math.min(CONFIG_REFRESH_MS * 2 ** configFailures, MAX_CONFIG_POLL_MS)
          : CONFIG_REFRESH_MS;
      configPollHandle = setTimeout(refreshConfig, delay);
    }

    async function refreshConfig() {
      // The rate-limit stamp is read and written on EVERY page, before the
      // early-out below, so awaiting both is mandatory: unserialized, the
      // 30s cross-tab throttle would degenerate into unbounded refetching.
      const last = await adapter.getValue(CONFIG_FETCHED_KEY, 0);
      if (typeof last === 'number' && Date.now() - last < CONFIG_REFRESH_MS) {
        reschedulePoll();
        return;
      }
      await adapter.setValue(CONFIG_FETCHED_KEY, Date.now());

      const body = await adapter.fetchConfig(CONFIG_URL, 2000);
      if (body === null) {
        configFailures += 1;
        reschedulePoll();
        return;
      }
      configFailures = 0;
      reschedulePoll();

      let fresh = null;
      try {
        fresh = JSON.parse(body);
      } catch (err) {
        return;
      }
      if (!fresh || !Array.isArray(fresh.sites) || !fresh.sites.length) return;
      await adapter.setValue(CONFIG_KEY, fresh);
      if (onFreshConfig) onFreshConfig(fresh);
    }

    await refreshConfig();

    // Escalation ladder for a single site, highest first — the first entry
    // whose `at` that site's ratio has reached wins. Below 1.0 there is no
    // level: the badge alone carries the information, and it is always on.
    const LEVELS = [
      { at: 1.5, overlay: true, dismissDelaySeconds: 5, grayscale: true, pauseVideo: true },
      { at: 1.25, overlay: true, dismissDelaySeconds: 5 },
      { at: 1.0, overlay: true, dismissDelaySeconds: 0 },
    ];

    // Ratio below which the badge is dimmed rather than fully opaque.
    const DIM_BELOW = 0.5;

    // -------------------------------------------------------------------------
    // Cheap early-out.
    //
    // @match is *://*/* so that the site list lives in CONFIG.rules alone
    // rather than being split between metadata and code. The hostname can't
    // change without a page load, so a host that matches no rule can bail
    // immediately and cost the page nothing further. The *path* can change
    // under us (SPA routing), so path matching has to stay dynamic.
    // -------------------------------------------------------------------------
    if (!CONFIG.rules.some((rule) => rule.host.test(location.hostname))) return;

    // A config that lands after startup applies to this page immediately, so
    // an already-open tab converges on an updated limit within one refresh
    // cycle (poll below, rate-limited to once per CONFIG_REFRESH_MS across
    // tabs). A site added for some *other* host can't — the early-out above
    // already ran — which is why adding a new host still asks for a tab
    // reload.
    onFreshConfig = (fresh) => {
      CONFIG = compile(fresh);
      render();
    };
    // Only a tracked page installs the recurring poll; the initial
    // `await refreshConfig()` above ran before this flag was set, so it
    // warmed the cache without scheduling anything.
    pollingStarted = true;
    reschedulePoll();

    const STORE_KEY = 'wtt.state.v2';
    const budgetSeconds = (rule) => Math.max(1, Math.round(rule.limitMinutes * 60));

    // -------------------------------------------------------------------------
    // State, shared across origins.
    //
    // localStorage is per-origin and so structurally cannot hold counters
    // visible from YouTube *and* Instagram *and* X. Adapter storage is kept by
    // the userscript engine itself and is visible from every matched origin.
    //
    // Shape: { days: { "2026-07-28": { "YouTube Shorts": 412.5, … }, … } }
    // -------------------------------------------------------------------------
    function dayKey(now = Date.now()) {
      const d = new Date(now - CONFIG.dayStartHour * 3600e3);
      const pad = (n) => String(n).padStart(2, '0');
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    }

    async function readState() {
      let raw = null;
      try {
        raw = await adapter.getValue(STORE_KEY, null);
      } catch (err) {
        raw = null;
      }
      // The engine may hand back either a string or an already-parsed object
      // depending on platform/version — tolerate both.
      if (typeof raw === 'string') {
        try {
          raw = JSON.parse(raw);
        } catch (err) {
          raw = null;
        }
      }
      if (!raw || typeof raw.days !== 'object' || raw.days === null) return { days: {} };

      // Day keys are zero-padded ISO dates, so a lexicographic compare is a
      // date compare, and pruning on read means no separate maintenance pass.
      const cutoff = dayKey(Date.now() - CONFIG.historyDays * 86400e3);
      const days = {};
      for (const [day, sites] of Object.entries(raw.days)) {
        if (day < cutoff || !sites || typeof sites !== 'object') continue;
        const clean = {};
        for (const [name, seconds] of Object.entries(sites)) {
          if (typeof seconds === 'number' && isFinite(seconds) && seconds > 0) clean[name] = seconds;
        }
        days[day] = clean;
      }
      return { days };
    }

    async function writeState(next) {
      try {
        await adapter.setValue(STORE_KEY, next);
      } catch (err) {
        /* storage unavailable — keep counting in memory */
      }
    }

    let state = await readState();
    let unsaved = 0;
    let lastTick = Date.now();
    let lastActivity = Date.now();
    // Per site, so dismissing on X doesn't also silence Shorts.
    let snoozeUntil = {};

    function today() {
      const key = dayKey();
      if (!state.days[key]) state.days[key] = {};
      return state.days[key];
    }

    const usedSeconds = (rule) => today()[rule.name] || 0;

    async function flush() {
      if (unsaved > 0) {
        const pending = unsaved;
        await writeState(state);
        // Only cleared after the write resolves — clearing it first would
        // silently discard the delta on a failed write. Clamped at zero: a
        // day rollover in tick() can reset `unsaved` to 0 while this write is
        // in flight, and the subtraction below must not drive it negative.
        unsaved = Math.max(0, unsaved - pending);
      }
    }

    // Another tab may have advanced a counter while this one was hidden.
    // Merge per site rather than wholesale, so two tabs on *different*
    // tracked sites don't clobber each other's progress.
    async function resync() {
      await flush();
      const stored = await readState();
      const key = dayKey();
      const mine = state.days[key] || {};
      const theirs = stored.days[key] || {};
      const merged = {};
      for (const name of new Set([...Object.keys(mine), ...Object.keys(theirs)])) {
        merged[name] = Math.max(mine[name] || 0, theirs[name] || 0);
      }
      stored.days[key] = merged;
      state = stored;
    }

    // -------------------------------------------------------------------------
    // Attentive time
    // -------------------------------------------------------------------------
    function activeRule() {
      for (const rule of CONFIG.rules) {
        if (!rule.host.test(location.hostname)) continue;
        if (rule.path && !rule.path.test(location.pathname)) continue;
        return rule;
      }
      return null;
    }

    // Only the visible, focused tab counts — which also means two tabs on
    // the same site can never double-count the same second.
    function isCounting() {
      if (document.visibilityState !== 'visible') return false;
      if (!document.hasFocus()) return false;
      if (Date.now() - lastActivity > CONFIG.idleSeconds * 1000) return false;
      return activeRule() !== null;
    }

    const bumpActivity = () => {
      lastActivity = Date.now();
    };
    for (const evt of ['mousemove', 'mousedown', 'keydown', 'scroll', 'wheel', 'touchstart']) {
      window.addEventListener(evt, bumpActivity, { passive: true, capture: true });
    }

    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        serialize(resync);
        lastTick = Date.now();
        lastActivity = Date.now();
      } else {
        // No unsaved > 0 gate here: this path is the reliable flush point on
        // Safari, which fires before pagehide.
        serialize(flush);
      }
    });
    window.addEventListener('focus', () => {
      serialize(resync);
      lastTick = Date.now();
      lastActivity = Date.now();
    });
    window.addEventListener('blur', () => serialize(flush));
    // Kept at the same SAVE_EVERY_SECONDS cadence rather than lowered for
    // pagehide: worst case ~SAVE_EVERY_SECONDS+1s lost per unload, well below
    // the noise floor of a 15-minute limit. The visibilitychange handler
    // above is the real safety net and fires reliably before pagehide.
    window.addEventListener('pagehide', () => serialize(flush));

    // -------------------------------------------------------------------------
    // SPA navigation
    //
    // Entering youtube.com/shorts/… fires no page load, so a one-shot check at
    // startup would miss it. The tick below would catch it within a second on
    // its own; patching history exists so the overlay clears the instant you
    // navigate off a tracked route rather than lingering.
    //
    // Best-effort, and a no-op on Safari: Userscripts.app only exposes the GM
    // APIs to scripts injected into `content`, i.e. an isolated world whose
    // `history` is not the page's. The tick is the real mechanism; this is a
    // latency optimisation for Chrome, never a correctness requirement.
    // -------------------------------------------------------------------------
    function onNavigate() {
      lastActivity = Date.now();
      render();
    }

    const wrapHistory = (fn) =>
      function wrapped() {
        const result = fn.apply(this, arguments);
        Promise.resolve().then(onNavigate);
        return result;
      };
    try {
      history.pushState = wrapHistory(history.pushState);
      history.replaceState = wrapHistory(history.replaceState);
    } catch (err) {
      /* sandboxed history — the per-tick check still covers us */
    }
    window.addEventListener('popstate', onNavigate);

    // -------------------------------------------------------------------------
    // UI — inside a shadow root, or the host site's CSS and ours would fight.
    // -------------------------------------------------------------------------
    const STYLES = `
      :host { all: initial; }
      .badge, .overlay, .panel { font: 500 13px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
      .badge {
        position: fixed; right: 16px; bottom: 16px;
        background: rgba(20, 20, 22, 0.88); color: #f4f4f5;
        padding: 7px 12px; border-radius: 999px;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
        pointer-events: auto; white-space: nowrap; cursor: pointer;
        transition: opacity 200ms ease;
      }
      .badge.dim { opacity: 0.4; }
      .badge.over { background: rgba(150, 30, 30, 0.92); }
      .overlay {
        position: fixed; inset: 0;
        background: rgba(10, 10, 12, 0.94); color: #f4f4f5;
        display: flex; flex-direction: column;
        align-items: center; justify-content: center; gap: 18px;
        text-align: center; padding: 24px; pointer-events: auto;
      }
      .overlay h1 { font-size: 26px; font-weight: 600; margin: 0; }
      .overlay p { font-size: 15px; margin: 0; color: #b8b8bd; max-width: 34em; }
      .overlay .clock { font-size: 44px; font-weight: 700; font-variant-numeric: tabular-nums; }
      .overlay button {
        font: inherit; font-size: 14px; margin-top: 8px;
        padding: 10px 18px; border-radius: 8px; border: 1px solid #3a3a40;
        background: #1c1c20; color: #f4f4f5; cursor: pointer;
      }
      .overlay button[disabled] { opacity: 0.45; cursor: not-allowed; }
      .panel {
        position: fixed; right: 16px; bottom: 56px;
        background: rgba(20, 20, 22, 0.96); color: #f4f4f5;
        border-radius: 10px; padding: 10px; min-width: 220px;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
        pointer-events: auto; white-space: pre-wrap;
      }
      .panel button {
        display: block; width: 100%; text-align: left; font: inherit; font-size: 12px;
        padding: 6px 8px; margin: 2px 0; border-radius: 6px; border: none;
        background: transparent; color: #f4f4f5; cursor: pointer;
      }
      .panel button:hover { background: rgba(255, 255, 255, 0.08); }
      .panel .status { padding: 6px 8px; color: #b8b8bd; font-size: 12px; }
    `;

    let shadowRoot = null;
    let badgeEl = null;
    let overlayEl = null;
    let overlayButton = null;
    let overlayKey = null;
    let overlayShownAt = 0;
    let grayscaleEl = null;
    let panelEl = null;

    function ui() {
      if (shadowRoot && shadowRoot.host.isConnected) return shadowRoot;
      const host = document.createElement('div');
      host.style.cssText = 'position: fixed; inset: 0; z-index: 2147483647; pointer-events: none;';
      shadowRoot = host.attachShadow({ mode: 'closed' });
      const style = document.createElement('style');
      style.textContent = STYLES;
      shadowRoot.appendChild(style);
      // documentElement, not body — at document-start there is no body yet.
      (document.body || document.documentElement).appendChild(host);
      badgeEl = null;
      overlayEl = null;
      panelEl = null;
      return shadowRoot;
    }

    function formatClock(totalSeconds) {
      const s = Math.max(0, Math.round(totalSeconds));
      const m = Math.floor(s / 60);
      return `${m}:${String(s % 60).padStart(2, '0')}`;
    }

    function showBadge(rule, ratio) {
      const root = ui();
      if (!badgeEl) {
        badgeEl = document.createElement('div');
        badgeEl.className = 'badge';
        badgeEl.addEventListener('click', togglePanel);
        root.appendChild(badgeEl);
      }
      badgeEl.classList.toggle('dim', ratio < DIM_BELOW);
      badgeEl.classList.toggle('over', ratio >= 1);
      badgeEl.textContent =
        `${rule.name} · ${formatClock(usedSeconds(rule))} / ${rule.limitMinutes}:00`;
    }

    function hideBadge() {
      if (badgeEl) {
        badgeEl.remove();
        badgeEl = null;
      }
    }

    function showOverlay(rule, level) {
      const root = ui();
      // Rebuild only when the site or level changes, so the dismiss countdown
      // isn't reset every tick.
      const key = `${rule.name}@${level.at}`;
      if (!overlayEl || overlayKey !== key) {
        hideOverlay();
        overlayKey = key;
        overlayShownAt = Date.now();
        overlayEl = document.createElement('div');
        overlayEl.className = 'overlay';
        overlayEl.innerHTML = `
          <h1>Over your daily limit</h1>
          <div class="clock"></div>
          <p></p>
          <button type="button"></button>
        `;
        root.appendChild(overlayEl);
        overlayButton = overlayEl.querySelector('button');
        overlayButton.addEventListener('click', () => {
          snoozeUntil[rule.name] = Date.now() + CONFIG.snoozeMinutes * 60000;
          hideOverlay();
          render();
        });
      }

      const used = usedSeconds(rule);
      const over = used - budgetSeconds(rule);
      overlayEl.querySelector('.clock').textContent = formatClock(used);
      overlayEl.querySelector('p').textContent =
        `${rule.name} is limited to ${rule.limitMinutes} min/day. ` +
        `You're ${formatClock(over)} over. Resets at ${CONFIG.dayStartHour}:00.`;

      const waited = (Date.now() - overlayShownAt) / 1000;
      const remaining = Math.max(0, Math.ceil((level.dismissDelaySeconds || 0) - waited));
      overlayButton.disabled = remaining > 0;
      overlayButton.textContent = remaining > 0
        ? `Wait ${remaining}s…`
        : `Dismiss for ${CONFIG.snoozeMinutes} min`;
    }

    function hideOverlay() {
      if (overlayEl) {
        overlayEl.remove();
        overlayEl = null;
        overlayButton = null;
        overlayKey = null;
      }
    }

    function setGrayscale(on) {
      if (on && !grayscaleEl) {
        grayscaleEl = document.createElement('style');
        grayscaleEl.textContent = 'html { filter: grayscale(1) !important; }';
        (document.head || document.documentElement).appendChild(grayscaleEl);
      } else if (!on && grayscaleEl) {
        grayscaleEl.remove();
        grayscaleEl = null;
      }
    }

    function pauseVideos() {
      for (const video of document.querySelectorAll('video')) {
        if (!video.paused) video.pause();
      }
    }

    // -------------------------------------------------------------------------
    // Badge menu — a small panel in the shadow root, opened by clicking the
    // badge. Replaces the old alert() dump so it works the same on every
    // platform (alert() is unavailable from Safari's page-injected world).
    // The items themselves are core logic (they touch state/resync/render);
    // adapter.registerMenu() is only for platform-native menu surfaces on top
    // of this (e.g. GM_registerMenuCommand on Chrome).
    // -------------------------------------------------------------------------
    function hidePanel() {
      if (panelEl) {
        panelEl.remove();
        panelEl = null;
      }
    }

    function togglePanel() {
      if (panelEl) {
        hidePanel();
        return;
      }
      const root = ui();
      panelEl = document.createElement('div');
      panelEl.className = 'panel';
      for (const item of menuItems) {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = item.label;
        button.addEventListener('click', async () => {
          hidePanel();
          await item.run();
        });
        panelEl.appendChild(button);
      }
      root.appendChild(panelEl);
    }

    // Shows plain text (the status report) in place of the menu list —
    // dismissed the same way, by clicking the badge again.
    function showStatusPanel(text) {
      hidePanel();
      const root = ui();
      panelEl = document.createElement('div');
      panelEl.className = 'panel';
      const pre = document.createElement('div');
      pre.className = 'status';
      pre.textContent = text;
      panelEl.appendChild(pre);
      const close = document.createElement('button');
      close.type = 'button';
      close.textContent = 'Close';
      close.addEventListener('click', hidePanel);
      panelEl.appendChild(close);
      root.appendChild(panelEl);
    }

    function render() {
      const rule = activeRule();
      if (!rule) {
        hideOverlay();
        hideBadge();
        hidePanel();
        setGrayscale(false);
        return;
      }

      const ratio = usedSeconds(rule) / budgetSeconds(rule);
      const level = LEVELS.find((entry) => ratio >= entry.at) || null;

      setGrayscale(Boolean(level && level.grayscale));
      if (level && level.pauseVideo) pauseVideos();

      const snoozed = Date.now() < (snoozeUntil[rule.name] || 0);
      if (level && level.overlay && !snoozed) {
        hideBadge();
        hidePanel();
        showOverlay(rule, level);
      } else {
        hideOverlay();
        showBadge(rule, ratio);
      }
    }

    // -------------------------------------------------------------------------
    // Clock
    //
    // tick() itself stays synchronous — the 1s UI update must not be
    // serialized behind storage I/O — and only fires the serialized flush()
    // without waiting on it.
    // -------------------------------------------------------------------------
    function tick() {
      const now = Date.now();
      // Real elapsed time, not the nominal interval — but clamped, so waking
      // the laptop after two hours doesn't inject two hours of "usage".
      const delta = Math.min(Math.max(now - lastTick, 0), TICK_MS * 2);
      lastTick = now;

      const key = dayKey(now);
      if (!state.days[key]) {
        state.days[key] = {};
        snoozeUntil = {};
        unsaved = 0;
        serialize(() => writeState(state));
      }

      const rule = delta > 0 && isCounting() ? activeRule() : null;
      if (rule) {
        state.days[key][rule.name] = (state.days[key][rule.name] || 0) + delta / 1000;
        unsaved += delta / 1000;
        if (unsaved >= SAVE_EVERY_SECONDS) serialize(flush);
      }

      render();
    }

    setInterval(tick, TICK_MS);
    render();

    // -------------------------------------------------------------------------
    // Menu commands. These bodies are core logic — they touch state, resync,
    // and render — only their registration is platform-specific.
    // -------------------------------------------------------------------------
    const menuItems = [
      {
        label: 'Time tracker: status',
        run: () =>
          serialize(async () => {
            await resync();
            const lines = CONFIG.rules.map((rule) => {
              const used = usedSeconds(rule);
              const pct = Math.round((used / budgetSeconds(rule)) * 100);
              return `  ${rule.name}: ${formatClock(used)} / ${rule.limitMinutes}:00 (${pct}%)`;
            });

            // Last 7 days across every site, oldest first — the trend the
            // per-day history exists for.
            const recent = Object.keys(state.days).sort().slice(-7);
            const trend = recent.map((day) => {
              const total = Object.values(state.days[day]).reduce((sum, s) => sum + s, 0);
              return `  ${day}: ${formatClock(total)}`;
            });

            showStatusPanel(
              `Today (${dayKey()}, resets at ${CONFIG.dayStartHour}:00)\n${lines.join('\n')}\n\n` +
              `Last 7 days, all sites\n${trend.join('\n')}`
            );
          }),
      },
      {
        label: "Time tracker: reset this site's counter",
        run: () =>
          serialize(async () => {
            const rule = activeRule();
            if (!rule) return;
            await resync();
            delete today()[rule.name];
            delete snoozeUntil[rule.name];
            await writeState(state);
            render();
          }),
      },
      {
        label: 'Time tracker: grant 10 more minutes here',
        run: () =>
          serialize(async () => {
            const rule = activeRule();
            if (!rule) return;
            await resync();
            today()[rule.name] = Math.max(0, usedSeconds(rule) - 600);
            delete snoozeUntil[rule.name];
            await writeState(state);
            render();
          }),
      },
    ];

    adapter.registerMenu(menuItems);
  }

  window.__wttMain = main;
})();

// ---------------------------------------------------------------------------
// Safari / Userscripts.app (quoid) adapter.
//
// GM.* here is natively promise-based, so these are thin passthroughs. The
// badge menu itself is rendered by the core into the shadow root on every
// platform, so registerMenu has nothing extra to add on Safari — it exists
// only to satisfy the adapter contract.
// ---------------------------------------------------------------------------
(function () {
  'use strict';

  const CONFIG_FETCHED_KEY = 'wtt.config.fetchedAt';

  // A missing GM API is not recoverable and used to fail silently: every read
  // fell through to its fallback, so the script ran on its baked-in DEFAULTS
  // and looked healthy while persisting nothing. Say so once — once, not once
  // per tick — so the next install misconfigured this way is obvious.
  let warnedNoGM = false;
  function warnOnce() {
    if (warnedNoGM) return;
    warnedNoGM = true;
    console.warn(
      '[wtt] GM storage unavailable — nothing will persist and the settings app ' +
        'will be ignored. Userscripts.app exposes GM only to @inject-into content.',
    );
  }

  const adapter = {
    async getValue(key, fallback) {
      // Checked explicitly rather than leaning on the catch below, which also
      // covers an ordinary JSON.parse failure — a different, recoverable thing.
      if (typeof GM === 'undefined' || typeof GM.getValue !== 'function') {
        warnOnce();
        return fallback;
      }
      try {
        const raw = await GM.getValue(key, null);
        if (raw === null || raw === undefined) return fallback;
        // Userscripts.app may serialize values as a string or hand back the
        // original object — tolerate both, same as the GM adapter.
        return typeof raw === 'string' && key !== CONFIG_FETCHED_KEY ? JSON.parse(raw) : raw;
      } catch (err) {
        return fallback;
      }
    },

    async setValue(key, value) {
      if (typeof GM === 'undefined' || typeof GM.setValue !== 'function') {
        warnOnce();
        return;
      }
      try {
        await GM.setValue(key, value);
      } catch (err) {
        /* storage unavailable — this run just uses what it has */
      }
    },

    async fetchConfig(url, timeoutMs) {
      if (typeof GM === 'undefined' || typeof GM.xmlHttpRequest !== 'function') {
        warnOnce();
        return null;
      }
      try {
        const response = await GM.xmlHttpRequest({ method: 'GET', url, timeout: timeoutMs });
        return response && response.status === 200 ? response.responseText : null;
      } catch (err) {
        // Covers both request failures and Safari's local-network policy
        // blocking the 127.0.0.1 loopback outright — either way, no config.
        return null;
      }
    },

    registerMenu() {
      /* no-op — the core's shadow-root panel is the menu on this platform */
    },
  };

  window.__wttMain(adapter);
})();
