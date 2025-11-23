(() => {
  try {
    const proto = Object.getPrototypeOf(navigator);
    if (proto && Object.prototype.hasOwnProperty.call(proto, 'webdriver')) {
      delete proto.webdriver;
    }
    if (Object.prototype.hasOwnProperty.call(navigator, 'webdriver')) {
      delete navigator.webdriver;
    }
    Object.defineProperty(navigator, 'webdriver', {
      get: () => undefined,
      configurable: true,
    });

    if (!window.chrome) {
      window.chrome = { runtime: {} };
    } else if (!window.chrome.runtime) {
      window.chrome.runtime = {};
    }
  } catch (e) {
    // Defensive: never let stealth patches break the page.
  }
})();
