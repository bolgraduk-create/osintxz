from pathlib import Path
P = Path("app/core/service_container.py")

def test_common_crawl_wiring_is_singleton_and_reuses_registry():
    text = P.read_text(encoding="utf-8")
    assert text.count("self.common_crawl_http_client =") == 1
    assert text.count("self.common_crawl_open_web_provider =") == 1
    assert "self.open_web_provider_registry.register(" in text
    assert text.count("self.open_web_provider_registry =") == 1
    assert text.count("self.open_web_discovery_service =") == 1
    assert text.count("self.osint_pipeline =") == 1
