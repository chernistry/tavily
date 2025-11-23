"""
Advanced stealth techniques including fingerprinting resistance and
network simulation.
"""

import random
from typing import Literal

from playwright.async_api import Page

from tavily_scraper.stealth.config import StealthConfig


async def apply_advanced_stealth(page: Page, config: StealthConfig) -> None:
    """
    Apply advanced stealth techniques to the page.

    This focuses on:
    * Canvas and WebGL tweaks to make fingerprinting less stable
    * AudioContext noise to reduce audio fingerprint reliability
    * WebRTC surface masking to avoid IP/device leakage

    These techniques are more invasive than the core ones and should only be
    enabled when needed (typically in "moderate" or "aggressive" modes).
    """
    if not (config.enabled and config.fingerprint_evasions):
        return

    # Canvas noise injection – inspired by common stealth plugins. We add a tiny
    # amount of noise to a subset of pixels so that exact fingerprints differ
    # across runs, but visual output is unaffected for normal users.
    await page.add_init_script(
        """
        (() => {
          try {
            if (HTMLCanvasElement.prototype.__tavily_canvas_patched__) {
              return;
            }
            HTMLCanvasElement.prototype.__tavily_canvas_patched__ = true;

            const originalGetImageData =
              CanvasRenderingContext2D.prototype.getImageData;

            CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {
              const imageData = originalGetImageData.call(this, x, y, w, h);
              try {
                const { data } = imageData;
                // Nudge every Nth pixel very slightly
                for (let i = 0; i < data.length; i += 4 * 10) {
                  data[i] = data[i] ^ 0x01;       // R
                  data[i + 1] = data[i + 1] ^ 0x01; // G
                  data[i + 2] = data[i + 2] ^ 0x01; // B
                }
              } catch (e) {
                // Swallow – worst case we return original data
              }
              return imageData;
            };
          } catch (e) {
            // Do nothing if canvas is non-standard
          }
        })();
        """
    )

    # WebGL vendor spoofing – normalize to a common vendor/renderer combo.
    await page.add_init_script(
        """
        (() => {
          try {
            const patchContext = (WebGLClass) => {
              if (!WebGLClass || WebGLClass.prototype.__tavily_webgl_patched__) {
                return;
              }
              WebGLClass.prototype.__tavily_webgl_patched__ = true;

              const getParameter = WebGLClass.prototype.getParameter;
              WebGLClass.prototype.getParameter = function(parameter) {
                try {
                  const debugInfo = this.getExtension &&
                    this.getExtension('WEBGL_debug_renderer_info');
                  if (debugInfo) {
                    if (parameter === debugInfo.UNMASKED_VENDOR_WEBGL) {
                      return 'Intel Inc.';
                    }
                    if (parameter === debugInfo.UNMASKED_RENDERER_WEBGL) {
                      return 'Intel Iris OpenGL Engine';
                    }
                  }
                  // Fallback magic numbers for UNMASKED_VENDOR/RENDERER
                  if (parameter === 37445) {
                    return 'Intel Inc.';
                  }
                  if (parameter === 37446) {
                    return 'Intel Iris OpenGL Engine';
                  }
                } catch (e) {
                  // If anything goes wrong, fall through to original
                }
                return getParameter.call(this, parameter);
              };
            };

            if (typeof WebGLRenderingContext !== 'undefined') {
              patchContext(WebGLRenderingContext);
            }
            if (typeof WebGL2RenderingContext !== 'undefined') {
              patchContext(WebGL2RenderingContext);
            }
          } catch (e) {
            // Leave WebGL untouched if environment differs
          }
        })();
        """
    )

    # WebRTC masking – remove local IP leakage and normalize devices.
    if config.mask_webrtc:
        await page.add_init_script(
            """
            (() => {
              try {
                const RTC = window.RTCPeerConnection || window.webkitRTCPeerConnection;
                if (RTC && !RTC.prototype.__tavily_webrtc_patched__) {
                  RTC.prototype.__tavily_webrtc_patched__ = true;

                  const origCreateDataChannel = RTC.prototype.createDataChannel;
                  RTC.prototype.createDataChannel = function() {
                    try {
                      this.__tavily_webrtc_dc__ = true;
                    } catch (e) {}
                    return origCreateDataChannel.apply(this, arguments);
                  };

                  const origOnIceCandidateDesc = Object.getOwnPropertyDescriptor(RTC.prototype, 'onicecandidate');
                  Object.defineProperty(RTC.prototype, 'onicecandidate', {
                    set: function(handler) {
                      const wrapped = (event) => {
                        try {
                          if (event && event.candidate && event.candidate.candidate) {
                            const c = event.candidate.candidate;
                            // Replace host IPs with 0.0.0.0
                            const sanitized = c.replace(/(candidate:\\d+ \\d+ udp \\d+ )([0-9.]+)( .*)/, '$10.0.0.0$3');
                            event = new RTCIceCandidate({ sdpMid: event.candidate.sdpMid, sdpMLineIndex: event.candidate.sdpMLineIndex, candidate: sanitized });
                          }
                        } catch (e) {}
                        return handler ? handler(event) : undefined;
                      };
                      if (origOnIceCandidateDesc && origOnIceCandidateDesc.set) {
                        return origOnIceCandidateDesc.set.call(this, wrapped);
                      }
                      this._onicecandidate = wrapped;
                    },
                    get: function() {
                      return this._onicecandidate;
                    },
                    configurable: true,
                  });
                }

                // Normalize enumerateDevices to avoid empty arrays in headless
                if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
                  const origEnum = navigator.mediaDevices.enumerateDevices.bind(navigator.mediaDevices);
                  navigator.mediaDevices.enumerateDevices = () => origEnum().then(list => {
                    if (list && list.length > 0) return list;
                    return [
                      { kind: 'audioinput', label: 'Default - Microphone', deviceId: 'default', groupId: 'default' },
                      { kind: 'audiooutput', label: 'Default - Speakers', deviceId: 'default', groupId: 'default' },
                    ];
                  }).catch(() => ([
                    { kind: 'audioinput', label: 'Default - Microphone', deviceId: 'default', groupId: 'default' },
                    { kind: 'audiooutput', label: 'Default - Speakers', deviceId: 'default', groupId: 'default' },
                  ]));
                }
              } catch (e) {
                // Ignore if WebRTC is unavailable
              }
            })();
            """
        )

    # AudioContext fingerprinting is increasingly used. We add subtle noise to
    # the returned channel data to make fingerprints less stable.
    await page.add_init_script(
        """
        (() => {
          try {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (!AudioCtx || AudioCtx.prototype.__tavily_audio_patched__) {
              return;
            }
            AudioCtx.prototype.__tavily_audio_patched__ = true;

            const originalGetChannelData = AudioCtx.prototype.getChannelData;

            AudioCtx.prototype.getChannelData = function() {
              const results = originalGetChannelData.apply(this, arguments);
              try {
                const len = results.length;
                const stride = Math.max(1, Math.floor(len / 500));
                for (let i = 0; i < len; i += stride) {
                  results[i] = results[i] + (Math.random() - 0.5) * 1e-7;
                }
              } catch (e) {
                // Ignore if typed arrays behave unexpectedly
              }
              return results;
            };
          } catch (e) {
            // No-op if AudioContext is unavailable
          }
        })();
        """
    )


async def simulate_network_conditions(
    page: Page,
    profile: Literal["fast_3g", "slow_3g", "4g"] = "fast_3g",
) -> None:
    """
    Simulate realistic network conditions (throttling).

    We use a small set of coarse profiles rather than fully random values so
    that behavior is realistic but still varied across runs.
    """

    if not page.context:
        return

    if profile == "slow_3g":
        download = 750 * 1024  # ~0.75 Mbps
        upload = 250 * 1024  # ~0.25 Mbps
        latency = random.randint(150, 400)
    elif profile == "4g":
        download = int(10 * 1024 * 1024)  # ~10 Mbps
        upload = int(3 * 1024 * 1024)  # ~3 Mbps
        latency = random.randint(20, 80)
    else:  # fast_3g default
        download = int(1.6 * 1024 * 1024)  # ~1.6 Mbps
        upload = int(750 * 1024)  # ~0.75 Mbps
        latency = random.randint(80, 200)

    # CDP session is Chromium-specific; guard in case of future engine changes.
    try:
        client = await page.context.new_cdp_session(page)
        await client.send(
            "Network.emulateNetworkConditions",
            {
                "offline": False,
                "latency": latency,
                "downloadThroughput": int(download),
                "uploadThroughput": int(upload),
            },
        )
    except Exception:
        # If emulation fails, we simply continue without throttling.
        return
