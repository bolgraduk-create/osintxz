from pathlib import Path


def test_service_container_registers_live_web_provider():
    text = Path("app/core/service_container.py").read_text(encoding="utf-8")
    assert "LiveWebOpenWebProvider" in text
    assert "self.live_web_open_web_provider" in text
    assert "self.open_web_provider_registry.register" in text


def test_enrichment_uses_provider_aware_hydration():
    text = Path(
        "app/application/open_web_enrichment_service.py"
    ).read_text(encoding="utf-8")

    assert '== "common_crawl"' in text
    assert '!= "common_crawl"' in text
    assert "prehydrated_documents" in text
