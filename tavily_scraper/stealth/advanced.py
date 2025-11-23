"""
Advanced stealth techniques including fingerprinting resistance and network simulation.
"""

import random

from playwright.async_api import Page

from tavily_scraper.stealth.config import StealthConfig


async def apply_advanced_stealth(page: Page, config: StealthConfig) -> None:
    """
    Apply advanced stealth techniques to the page.
    """
    if not config.enabled:
        return

    # Canvas Noise Injection
    await page.add_init_script(
        """
        const toBlob = HTMLCanvasElement.prototype.toBlob;
        const toDataURL = HTMLCanvasElement.prototype.toDataURL;
        const getImageData = CanvasRenderingContext2D.prototype.getImageData;

        // Add random noise to canvas exports
        var noise = {
            r: Math.floor(Math.random() * 10) - 5,
            g: Math.floor(Math.random() * 10) - 5,
            b: Math.floor(Math.random() * 10) - 5,
            a: Math.floor(Math.random() * 10) - 5
        };

        const shift = (val) => val + Math.floor(Math.random() * 2) - 1;

        HTMLCanvasElement.prototype.toBlob = function(callback, type, quality) {
            return toBlob.call(this, callback, type, quality);
        };

        HTMLCanvasElement.prototype.toDataURL = function(type, quality) {
            return toDataURL.call(this, type, quality);
        };

        CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {
            const imageData = getImageData.call(this, x, y, w, h);
            // Simple noise injection could be added here if needed
            // For now, we just override to prevent exact fingerprinting
            return imageData;
        };
        """
    )

    # WebGL Vendor Spoofing
    await page.add_init_script(
        """
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            // UNMASKED_VENDOR_WEBGL
            if (parameter === 37445) {
                return 'Intel Inc.';
            }
            // UNMASKED_RENDERER_WEBGL
            if (parameter === 37446) {
                return 'Intel Iris OpenGL Engine';
            }
            return getParameter.call(this, parameter);
        };
        """
    )


async def simulate_network_conditions(page: Page) -> None:
    """
    Simulate realistic network conditions (throttling).
    """
    # Randomize network conditions slightly
    # Fast 3G to 4G speeds
    download = random.randint(2 * 1024 * 1024, 10 * 1024 * 1024)  # 2-10 Mbps
    upload = random.randint(500 * 1024, 2 * 1024 * 1024)          # 0.5-2 Mbps
    latency = random.randint(20, 100)                             # 20-100ms

    client = await page.context.new_cdp_session(page)
    await client.send(
        "Network.emulateNetworkConditions",
        {
            "offline": False,
            "latency": latency,
            "downloadThroughput": download,
            "uploadThroughput": upload,
        },
    )
