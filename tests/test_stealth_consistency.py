import shutil
import tempfile

import pytest

from tavily_scraper.stealth.device_profiles import DeviceProfile
from tavily_scraper.stealth.session import SessionManager


class TestStickyProfiles:
    @pytest.fixture
    def temp_dir(self):
        d = tempfile.mkdtemp()
        yield d
        shutil.rmtree(d)

    @pytest.fixture
    def manager(self, temp_dir):
        return SessionManager(data_dir=temp_dir)

    def test_device_profile_serialization(self):
        profile = DeviceProfile(
            name="test_profile",
            user_agent="Mozilla/5.0 Test",
            viewport_width=1024,
            viewport_height=768,
            locale="en-US",
            timezone_id="UTC"
        )
        data = profile.to_dict()
        assert data["name"] == "test_profile"
        
        reconstructed = DeviceProfile.from_dict(data)
        assert reconstructed == profile

    @pytest.mark.asyncio
    async def test_save_load_profile(self, manager):
        profile_data = {
            "name": "sticky_profile",
            "user_agent": "StickyAgent/1.0",
            "viewport_width": 1920,
            "viewport_height": 1080,
            "locale": "fr-FR",
            "timezone_id": "Europe/Paris"
        }
        
        await manager.save_profile("user_sticky", profile_data)
        
        loaded = manager.load_profile("user_sticky")
        assert loaded is not None
        assert loaded["user_agent"] == "StickyAgent/1.0"
        
        # Verify file exists
        path = manager._get_profile_path("user_sticky")
        assert path.exists()
        assert path.name == "user_sticky.profile.json"

    def test_load_missing_profile(self, manager):
        loaded = manager.load_profile("ghost_user")
        assert loaded is None


class TestFingerprintHardening:
    @pytest.mark.asyncio
    async def test_canvas_noise_injection(self):
        from tavily_scraper.stealth.config import StealthConfig
        from tavily_scraper.stealth.advanced import apply_advanced_stealth
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # 1. Baseline: No stealth
            await page.set_content('<canvas id="c" width="100" height="100"></canvas>')
            baseline_data_url = await page.evaluate("""() => {
                const c = document.getElementById('c');
                const ctx = c.getContext('2d');
                ctx.fillStyle = 'red';
                ctx.fillRect(10, 10, 50, 50);
                return c.toDataURL();
            }""")

            # 2. Enable stealth
            config = StealthConfig(enabled=True, fingerprint_evasions=True)
            await apply_advanced_stealth(page, config)
            
            # 3. Render same content
            # We need to reload or re-evaluate to ensure scripts apply? 
            # apply_advanced_stealth adds init scripts, so we need to reload the page or open a new one.
            # But add_init_script applies to *future* loads.
            # Let's reload the page.
            await page.reload()
            await page.set_content('<canvas id="c" width="100" height="100"></canvas>')
            
            stealth_data_url = await page.evaluate("""() => {
                const c = document.getElementById('c');
                const ctx = c.getContext('2d');
                ctx.fillStyle = 'red';
                ctx.fillRect(10, 10, 50, 50);
                return c.toDataURL();
            }""")

            # Assert noise was injected (hashes differ)
            assert baseline_data_url != stealth_data_url, "Canvas fingerprint should differ with stealth enabled"

            # 4. Consistency check (same session/page)
            stealth_data_url_2 = await page.evaluate("""() => {
                const c = document.getElementById('c');
                const ctx = c.getContext('2d');
                ctx.fillStyle = 'red';
                ctx.fillRect(10, 10, 50, 50);
                return c.toDataURL();
            }""")
            
            assert stealth_data_url == stealth_data_url_2, "Canvas fingerprint should be stable within session"

            await browser.close()

    @pytest.mark.asyncio
    async def test_webgl_vendor_spoofing(self):
        from tavily_scraper.stealth.config import StealthConfig
        from tavily_scraper.stealth.advanced import apply_advanced_stealth
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            config = StealthConfig(enabled=True, fingerprint_evasions=True)
            await apply_advanced_stealth(page, config)
            await page.reload() # Apply init scripts

            # Check WebGL 1
            vendor = await page.evaluate("""() => {
                const canvas = document.createElement('canvas');
                const gl = canvas.getContext('webgl');
                const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
                return gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL);
            }""")
            
            assert vendor != "Google Inc. (Google)", "WebGL vendor should be spoofed (not default Headless)"
            assert vendor in ["Intel Inc.", "Apple Inc.", "Apple", "NVIDIA Corporation", "AMD", "Mesa"], f"Unexpected vendor: {vendor}"

            # Check WebGL 2 if available
            vendor2 = await page.evaluate("""() => {
                const canvas = document.createElement('canvas');
                const gl = canvas.getContext('webgl2');
                if (!gl) return 'N/A';
                const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
                return gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL);
            }""")
            
            if vendor2 != 'N/A':
                assert vendor2 == vendor, "WebGL2 vendor should match WebGL1"

            await browser.close()
