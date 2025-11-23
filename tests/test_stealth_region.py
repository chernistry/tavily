from tavily_scraper.stealth.config import StealthConfig
from tavily_scraper.stealth.device_profiles import (
    build_context_options,
    choose_geo_profile,
)


def test_region_alignment_eu() -> None:
    config = StealthConfig(enabled=True, target_region="EU")
    options, profile = build_context_options(config, target_region="EU")
    
    assert profile is not None
    assert profile.region == "EU"
    assert "Europe" in profile.timezone_id or "London" in profile.timezone_id or "Berlin" in profile.timezone_id or "Paris" in profile.timezone_id
    assert options["timezone_id"] == profile.timezone_id
    assert options["locale"] == profile.locale

def test_region_alignment_us() -> None:
    config = StealthConfig(enabled=True, target_region="US")
    options, profile = build_context_options(config, target_region="US")
    
    assert profile is not None
    assert profile.region == "US"
    assert "America" in profile.timezone_id
    assert options["timezone_id"] == profile.timezone_id

def test_region_alignment_apac() -> None:
    config = StealthConfig(enabled=True, target_region="APAC")
    options, profile = build_context_options(config, target_region="APAC")
    
    assert profile is not None
    assert profile.region == "APAC"
    # APAC timezones vary (Asia/Tokyo, Australia/Sydney, etc.)
    assert "Asia" in profile.timezone_id or "Australia" in profile.timezone_id
    assert options["timezone_id"] == profile.timezone_id

def test_geo_profile_alignment() -> None:
    # Test direct geo profile selection
    geo_us = choose_geo_profile(region="US")
    assert geo_us is not None
    assert geo_us.region == "US"
    
    geo_eu = choose_geo_profile(region="EU")
    assert geo_eu is not None
    assert geo_eu.region == "EU"
    
    geo_apac = choose_geo_profile(region="APAC")
    assert geo_apac is not None
    assert geo_apac.region == "APAC"

def test_random_geolocation_alignment() -> None:
    # Test that build_context_options picks aligned geo
    config = StealthConfig(enabled=True, random_geolocation=True, target_region="EU")
    options, profile = build_context_options(config, target_region="EU")
    
    assert profile is not None
    assert profile.region == "EU"
    assert "geolocation" in options
    
    # We can't easily assert the geolocation region from coordinates without a map,
    # but we can check if it matches one of our EU profiles?
    # Or we can just trust choose_geo_profile logic which we tested above.
    # Let's check if the lat/lon is roughly in Europe?
    lat = options["geolocation"]["latitude"]
    lon = options["geolocation"]["longitude"]
    
    # Rough EU box: Lat 35-70, Lon -10 to 40
    assert 30 < lat < 75
    assert -20 < lon < 50
