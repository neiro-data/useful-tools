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
