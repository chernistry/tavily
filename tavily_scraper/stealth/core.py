"""
Core stealth techniques to evade basic bot detection.
"""

from playwright.async_api import Page

from tavily_scraper.stealth.config import StealthConfig


async def apply_core_stealth(page: Page, config: StealthConfig) -> None:
    """
    Apply core stealth techniques to the page.

    This focuses on:
    * Hiding obvious automation flags (navigator.webdriver, window.chrome)
    * Normalizing navigator properties (languages, plugins, hardware hints)
    * Making the permissions API behave like a real browser

    All scripts are defensive: they swallow their own errors so we never break
    the page if a browser/vendor changes something.

    Args:
        page: Playwright page instance.
        config: Stealth configuration.
    """
    if not config.enabled:
        return

    # --- navigator.webdriver and basic automation flags ---
    if config.spoof_webdriver:
        await page.add_init_script(
            """
            (() => {
              try {
                // Remove existing webdriver flags on the prototype and instance
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

                // Some detectors check for window.chrome + runtime
                if (!window.chrome) {
                  window.chrome = { runtime: {} };
                } else if (!window.chrome.runtime) {
                  window.chrome.runtime = {};
                }
              } catch (e) {
                // Never let stealth patches break the page
              }
            })();
            """
        )

    # --- navigator languages, plugins, and basic hardware hints ---
    if config.spoof_user_agent:
        await page.add_init_script(
            """
            (() => {
              try {
                // Languages
                Object.defineProperty(navigator, 'languages', {
                  get: () => ['en-US', 'en'],
                  configurable: true,
                });

                // Basic plugin array stub
                const makePlugins = () => {
                  const plugins = [
                    { name: 'Chrome PDF Plugin' },
                    { name: 'Chrome PDF Viewer' },
                    { name: 'Native Client' },
                  ];
                  const pluginArray = {
                    length: plugins.length,
                    item: (index) => plugins[index] || null,
                    namedItem: (name) => plugins.find(p => p.name === name) || null,
                  };
                  plugins.forEach((p, i) => {
                    Object.defineProperty(pluginArray, i, {
                      value: p,
                      enumerable: true,
                    });
                  });
                  return pluginArray;
                };

                Object.defineProperty(navigator, 'plugins', {
                  get: () => makePlugins(),
                  configurable: true,
                });

                // Normalize a couple of hardware hints
                if (!('hardwareConcurrency' in navigator)) {
                  Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 8,
                    configurable: true,
                  });
                }
                if (!('deviceMemory' in navigator)) {
                  Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8,
                    configurable: true,
                  });
                }
              } catch (e) {
                // Defensive: ignore if environment differs
              }
            })();
            """
        )

    # --- Permissions API normalization ---
    await page.add_init_script(
        """
        (() => {
          try {
            const permissions = window.navigator.permissions;
            if (!permissions || !permissions.query) {
              return;
            }

            const originalQuery = permissions.query.bind(permissions);

            permissions.query = (parameters) => {
              try {
                if (parameters && parameters.name === 'notifications') {
                  const defaultState = (typeof Notification !== 'undefined' &&
                    Notification.permission) || 'default';
                  return Promise.resolve({ state: defaultState });
                }
                return originalQuery(parameters);
              } catch (e) {
                const fallbackState = (typeof Notification !== 'undefined' &&
                  Notification.permission) || 'default';
                return Promise.resolve({ state: fallbackState });
              }
            };
          } catch (e) {
            // Do nothing if permissions API behaves differently
          }
        })();
        """
    )
