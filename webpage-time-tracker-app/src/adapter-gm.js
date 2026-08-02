// ---------------------------------------------------------------------------
// Chrome / Tampermonkey adapter.
//
// GM_getValue/GM_setValue are synchronous here, but the core only ever awaits
// them, so wrapping each call in an already-resolved promise keeps the core
// platform-agnostic without slowing Chrome down (the await unwraps on the
// same microtask tick).
// ---------------------------------------------------------------------------
(function () {
  'use strict';

  const CONFIG_FETCHED_KEY = 'wtt.config.fetchedAt';

  function gmGet(key, fallback) {
    try {
      const raw = GM_getValue(key, null);
      if (raw === null || raw === undefined) return fallback;
      // Tampermonkey may hand back either a string or an already-parsed
      // object depending on version/value — tolerate both.
      return typeof raw === 'string' && key !== CONFIG_FETCHED_KEY ? JSON.parse(raw) : raw;
    } catch (err) {
      return fallback;
    }
  }

  function gmSet(key, value) {
    try {
      GM_setValue(key, value);
    } catch (err) {
      /* storage unavailable — this run just uses what it has */
    }
  }

  const adapter = {
    getValue(key, fallback) {
      return Promise.resolve(gmGet(key, fallback));
    },

    setValue(key, value) {
      gmSet(key, value);
      return Promise.resolve();
    },

    fetchConfig(url, timeoutMs) {
      if (typeof GM_xmlhttpRequest !== 'function') return Promise.resolve(null);
      return new Promise((resolve) => {
        try {
          GM_xmlhttpRequest({
            method: 'GET',
            url,
            timeout: timeoutMs,
            onload: (response) => {
              resolve(response.status === 200 ? response.responseText : null);
            },
            onerror: () => resolve(null),
            ontimeout: () => resolve(null),
          });
        } catch (err) {
          /* GM_xmlhttpRequest unavailable — the cache stands */
          resolve(null);
        }
      });
    },

    // Bonus on top of the shadow-root panel the core renders on every
    // platform: Chrome/Tampermonkey users also get native menu commands.
    registerMenu(items) {
      if (typeof GM_registerMenuCommand !== 'function') return;
      for (const item of items) {
        GM_registerMenuCommand(item.label, item.run);
      }
    },
  };

  window.__wttMain(adapter);
})();
