// Function body injected one-shot into the active tab via chrome.scripting.executeScript.
// Must have no closures over popup.js state — it runs in the page's isolated world.
function capturePage() {
  return {
    html: document.documentElement.outerHTML,
    url: location.href,
    title: document.title,
  };
}
