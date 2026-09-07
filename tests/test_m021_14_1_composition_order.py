
from pathlib import Path

P = Path("app/core/service_container.py")

def test_recursive_service_before_open_web_bridge():
    text = P.read_text(encoding="utf-8")
    assert text.index("self.osint_recursive_enrichment_service =") < text.index(
        "self.open_web_recursive_pivot_service ="
    )

def test_singletons():
    text = P.read_text(encoding="utf-8")
    assert text.count("self.osint_recursive_enrichment_service =") == 1
    assert text.count("self.open_web_recursive_pivot_service =") == 1
    assert text.count("self.osint_pipeline =") == 1
