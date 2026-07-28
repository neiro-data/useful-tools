// ==UserScript==
// @name         Webpage Time Tracker
// @namespace    https://github.com/neiro-data/useful-tools
// @version      0.2.0
// @description  Tracks focused time per time-sink site against that site's own daily limit, then escalates nudges once you go over.
// @author       neiro
// @match        *://*/*
// @run-at       document-start
// @noframes
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_registerMenuCommand
// ==/UserScript==

(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // CONFIG — the only part meant to be edited.
  // ---------------------------------------------------------------------------
  const CONFIG = {
    // The day rolls over at this local hour. 4am rather than midnight, so
    // "it resets in two minutes" isn't available at 23:58.
    dayStartHour: 4,
    // No input for this long and the clock stops, even on a focused tab.
    idleSeconds: 60,
    // How long a dismissed overlay stays gone.
    snoozeMinutes: 5,
    // Days of per-site history kept. Nothing enforces against it — it exists so
    // "am I actually improving?" is answerable.
    historyDays: 14,
    tickMs: 1000,
    saveEverySeconds: 5,

    // Each rule carries its own daily limit — there is no pooled budget.
    // host is matched against location.hostname, path against location.pathname.
    // Omit path to track the whole site.
    rules: [
      {
        name: 'YouTube Shorts',
        host: /(^|\.)youtube\.com$/,
        path: /^\/shorts(\/|$)/,
        limitMinutes: 15,
      },
      {
        name: 'Instagram Reels',
        host: /(^|\.)instagram\.com$/,
        path: /^\/reels?(\/|$)/,
        limitMinutes: 15,
      },
      { name: 'X', host: /(^|\.)(x|twitter)\.com$/, limitMinutes: 30 },
    ],
  };

  // Escalation ladder for a single site, highest first — the first entry whose
  // `at` that site's ratio has reached wins. Below 1.0 there is no level: the
  // badge alone carries the information, and it is always on.
  const LEVELS = [
    { at: 1.5, overlay: true, dismissDelaySeconds: 5, grayscale: true, pauseVideo: true },
    { at: 1.25, overlay: true, dismissDelaySeconds: 5 },
    { at: 1.0, overlay: true, dismissDelaySeconds: 0 },
  ];

  // Ratio below which the badge is dimmed rather than fully opaque.
  const DIM_BELOW = 0.5;

  // ---------------------------------------------------------------------------
  // Cheap early-out.
  //
  // @match is *://*/* so that the site list lives in CONFIG.rules alone rather
  // than being split between metadata and code. The hostname can't change
  // without a page load, so a host that matches no rule can bail immediately
  // and cost the page nothing further. The *path* can change under us (SPA
  // routing), so path matching has to stay dynamic.
  // ---------------------------------------------------------------------------
  if (!CONFIG.rules.some((rule) => rule.host.test(location.hostname))) return;

  const STORE_KEY = 'wtt.state.v2';
  const budgetSeconds = (rule) => Math.max(1, Math.round(rule.limitMinutes * 60));

  // ---------------------------------------------------------------------------
  // State, shared across origins.
  //
  // localStorage is per-origin and so structurally cannot hold counters visible
  // from YouTube *and* Instagram *and* X. GM_setValue is stored by Tampermonkey
  // itself and is visible from every matched origin.
  //
  // Shape: { days: { "2026-07-28": { "YouTube Shorts": 412.5, … }, … } }
  // ---------------------------------------------------------------------------
  function dayKey(now = Date.now()) {
    const d = new Date(now - CONFIG.dayStartHour * 3600e3);
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }

  function readState() {
    let raw = null;
    try {
      raw = GM_getValue(STORE_KEY, null);
    } catch (err) {
      raw = null;
    }
    if (typeof raw === 'string') {
      try {
        raw = JSON.parse(raw);
      } catch (err) {
        raw = null;
      }
    }
    if (!raw || typeof raw.days !== 'object' || raw.days === null) return { days: {} };

    // Day keys are zero-padded ISO dates, so a lexicographic compare is a date
    // compare, and pruning on read means no separate maintenance pass.
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

  function writeState(next) {
    try {
      GM_setValue(STORE_KEY, next);
    } catch (err) {
      /* storage unavailable — keep counting in memory */
    }
  }

  let state = readState();
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

  function flush() {
    if (unsaved > 0) {
      writeState(state);
      unsaved = 0;
    }
  }

  // Another tab may have advanced a counter while this one was hidden. Merge
  // per site rather than wholesale, so two tabs on *different* tracked sites
  // don't clobber each other's progress.
  function resync() {
    flush();
    const stored = readState();
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

  // ---------------------------------------------------------------------------
  // Attentive time
  // ---------------------------------------------------------------------------
  function activeRule() {
    for (const rule of CONFIG.rules) {
      if (!rule.host.test(location.hostname)) continue;
      if (rule.path && !rule.path.test(location.pathname)) continue;
      return rule;
    }
    return null;
  }

  // Only the visible, focused tab counts — which also means two tabs on the
  // same site can never double-count the same second.
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
      resync();
      lastTick = Date.now();
      lastActivity = Date.now();
    } else {
      flush();
    }
  });
  window.addEventListener('focus', () => {
    resync();
    lastTick = Date.now();
    lastActivity = Date.now();
  });
  window.addEventListener('blur', flush);
  window.addEventListener('pagehide', flush);

  // ---------------------------------------------------------------------------
  // SPA navigation
  //
  // Entering youtube.com/shorts/… fires no page load, so a one-shot check at
  // startup would miss it. The tick below would catch it within a second on its
  // own; patching history exists so the overlay clears the instant you navigate
  // off a tracked route rather than lingering.
  // ---------------------------------------------------------------------------
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

  // ---------------------------------------------------------------------------
  // UI — inside a shadow root, or the host site's CSS and ours would fight.
  // ---------------------------------------------------------------------------
  const STYLES = `
    :host { all: initial; }
    .badge, .overlay { font: 500 13px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    .badge {
      position: fixed; right: 16px; bottom: 16px;
      background: rgba(20, 20, 22, 0.88); color: #f4f4f5;
      padding: 7px 12px; border-radius: 999px;
      box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
      pointer-events: none; white-space: nowrap;
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
  `;

  let shadowRoot = null;
  let badgeEl = null;
  let overlayEl = null;
  let overlayButton = null;
  let overlayKey = null;
  let overlayShownAt = 0;
  let grayscaleEl = null;

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

  function render() {
    const rule = activeRule();
    if (!rule) {
      hideOverlay();
      hideBadge();
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
      showOverlay(rule, level);
    } else {
      hideOverlay();
      showBadge(rule, ratio);
    }
  }

  // ---------------------------------------------------------------------------
  // Clock
  // ---------------------------------------------------------------------------
  function tick() {
    const now = Date.now();
    // Real elapsed time, not the nominal interval — but clamped, so waking the
    // laptop after two hours doesn't inject two hours of "usage".
    const delta = Math.min(Math.max(now - lastTick, 0), CONFIG.tickMs * 2);
    lastTick = now;

    const key = dayKey(now);
    if (!state.days[key]) {
      state.days[key] = {};
      snoozeUntil = {};
      unsaved = 0;
      writeState(state);
    }

    const rule = delta > 0 && isCounting() ? activeRule() : null;
    if (rule) {
      state.days[key][rule.name] = (state.days[key][rule.name] || 0) + delta / 1000;
      unsaved += delta / 1000;
      if (unsaved >= CONFIG.saveEverySeconds) flush();
    }

    render();
  }

  setInterval(tick, CONFIG.tickMs);
  render();

  // ---------------------------------------------------------------------------
  // Tampermonkey menu
  // ---------------------------------------------------------------------------
  if (typeof GM_registerMenuCommand === 'function') {
    GM_registerMenuCommand('Time tracker: status', () => {
      resync();
      const lines = CONFIG.rules.map((rule) => {
        const used = usedSeconds(rule);
        const pct = Math.round((used / budgetSeconds(rule)) * 100);
        return `  ${rule.name}: ${formatClock(used)} / ${rule.limitMinutes}:00 (${pct}%)`;
      });

      // Last 7 days across every site, oldest first — the trend the per-day
      // history exists for.
      const recent = Object.keys(state.days).sort().slice(-7);
      const trend = recent.map((day) => {
        const total = Object.values(state.days[day]).reduce((sum, s) => sum + s, 0);
        return `  ${day}: ${formatClock(total)}`;
      });

      alert(
        `Today (${dayKey()}, resets at ${CONFIG.dayStartHour}:00)\n${lines.join('\n')}\n\n` +
        `Last 7 days, all sites\n${trend.join('\n')}`
      );
    });

    GM_registerMenuCommand("Time tracker: reset this site's counter", () => {
      const rule = activeRule();
      if (!rule) return;
      resync();
      delete today()[rule.name];
      delete snoozeUntil[rule.name];
      writeState(state);
      render();
    });

    GM_registerMenuCommand('Time tracker: grant 10 more minutes here', () => {
      const rule = activeRule();
      if (!rule) return;
      resync();
      today()[rule.name] = Math.max(0, usedSeconds(rule) - 600);
      delete snoozeUntil[rule.name];
      writeState(state);
      render();
    });
  }
})();
