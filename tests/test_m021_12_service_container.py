from pathlib import Path

P = Path(
    "app/core/service_container.py"
)


def test_m021_12_singletons_and_reuse():
    text = P.read_text(
        encoding="utf-8"
    )

    assert (
        text.count(
            "self.common_crawl_warc_content_client ="
        )
        == 1
    )
    assert (
        text.count(
            "self.common_crawl_content_hydrator ="
        )
        == 1
    )
    assert (
        text.count(
            "self.open_web_enrichment_service ="
        )
        == 1
    )
    assert (
        text.count(
            "self.osint_pipeline ="
        )
        == 1
    )
    assert (
        "self.common_crawl_content_hydrator"
        in text
    )
