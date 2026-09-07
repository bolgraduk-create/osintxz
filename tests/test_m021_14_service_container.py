from pathlib import Path

P = Path("app/core/service_container.py")


def test_m021_14_singletons_and_reuse():
    text = P.read_text(encoding="utf-8")

    assert text.count("self.open_web_recursive_pivot_service =") == 1
    assert text.count("self.osint_recursive_enrichment_service =") == 1
    assert text.count("self.open_web_enrichment_service =") == 1
    assert text.count("self.osint_pipeline =") == 1

    pos = text.index("self.open_web_recursive_pivot_service =")
    block = text[pos:pos + 1000]
    assert "self.osint_recursive_enrichment_service" in block
