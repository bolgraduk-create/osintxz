from pathlib import Path

PATH = Path("tests/test_common_crawl_open_web_provider.py")

def main() -> int:
    if not PATH.is_file():
        print(f"[FAIL] Missing {PATH}")
        return 1

    original = PATH.read_text(encoding="utf-8")

    old = (
        'def test_domain_uses_apex_and_subdomain_patterns():\n'
        '    s = Stub([])\n'
        '    CommonCrawlOpenWebProvider(s).search(OpenWebQuery(OsintTargetType.DOMAIN, "example.org", limit=10))\n'
        '    assert [c["url_pattern"] for c in s.calls] == ["example.org/*", "*.example.org/*"]\n'
    )

    new = (
        'def test_domain_uses_bounded_exact_homepage_probes():\n'
        '    s = Stub([])\n'
        '    result = CommonCrawlOpenWebProvider(s).search(\n'
        '        OpenWebQuery(OsintTargetType.DOMAIN, "example.org", limit=10)\n'
        '    )\n'
        '    assert result.status is OpenWebStatus.SUCCESS\n'
        '    assert [c["url_pattern"] for c in s.calls] == [\n'
        '        "https://example.org/",\n'
        '        "http://example.org/",\n'
        '        "https://www.example.org/",\n'
        '        "http://www.example.org/",\n'
        '    ]\n'
        '    assert all("*" not in c["url_pattern"] for c in s.calls)\n'
    )

    if old not in original:
        if "def test_domain_uses_bounded_exact_homepage_probes():" in original:
            print("[PASS] M021.11.1 regression test already updated.")
            return 0
        print("[FAIL] Old M021.11 domain test was not found.")
        return 1

    updated = original.replace(old, new, 1)
    compile(updated, str(PATH), "exec")

    backup = PATH.with_suffix(".py.m021_11_1_backup")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")

    PATH.write_text(updated, encoding="utf-8")

    print("[PASS] M021.11 regression test updated to bounded exact DOMAIN probes.")
    print("[INFO] Production code unchanged.")
    print(f"[INFO] Backup: {backup}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
