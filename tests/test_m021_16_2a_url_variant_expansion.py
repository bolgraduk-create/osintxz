from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery
from app.osint.open_web.providers.common_crawl import CommonCrawlOpenWebProvider


def _q(value: str) -> OpenWebQuery:
    return OpenWebQuery(
        target_type=OsintTargetType.URL,
        value=value,
    )


def test_url_variants_include_scheme_host_and_slash_equivalents():
    probes = CommonCrawlOpenWebProvider._probes(
        _q("https://www.uic.edu/about/contact-us/")
    )

    assert "https://www.uic.edu/about/contact-us/" in probes
    assert "https://www.uic.edu/about/contact-us" in probes
    assert "http://www.uic.edu/about/contact-us/" in probes
    assert "https://uic.edu/about/contact-us/" in probes
    assert len(probes) <= 8
    assert len(probes) == len(set(p.casefold() for p in probes))


def test_url_variants_preserve_query_string():
    probes = CommonCrawlOpenWebProvider._probes(
        _q("https://example.com/page?id=123")
    )

    assert probes
    assert all("id=123" in p for p in probes)


def test_url_variants_do_not_add_wildcards():
    probes = CommonCrawlOpenWebProvider._probes(
        _q("https://example.com/a/b")
    )

    assert all("*" not in p for p in probes)


def test_domain_behavior_remains_bounded_homepage_probes():
    query = OpenWebQuery(
        target_type=OsintTargetType.DOMAIN,
        value="example.com",
    )
    probes = CommonCrawlOpenWebProvider._probes(query)

    assert probes == [
        "https://example.com/",
        "http://example.com/",
        "https://www.example.com/",
        "http://www.example.com/",
    ]
