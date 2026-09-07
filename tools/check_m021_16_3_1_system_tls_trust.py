from pathlib import Path


def main() -> int:
    text = Path(
        "app/osint/open_web/providers/live_web.py"
    ).read_text(encoding="utf-8")

    checks = [
        (
            "truststore optional import",
            "import truststore" in text,
        ),
        (
            "TLS context helper",
            "def _tls_context(" in text,
        ),
        (
            "OS trust context",
            "truststore.SSLContext" in text,
        ),
        (
            "httpx receives TLS context",
            "verify=self._tls_context()" in text,
        ),
        (
            "verification is not disabled",
            "verify=False" not in text,
        ),
        (
            "CERT_REQUIRED fallback",
            "ssl.CERT_REQUIRED" in text,
        ),
        (
            "SSRF guard preserved",
            "not ip.is_global" in text,
        ),
    ]

    print("=" * 72)
    print("M021.16.3.1 SYSTEM TLS TRUST AUDIT")
    print("=" * 72)

    failed = False
    for label, ok in checks:
        print(
            f"[{'PASS' if ok else 'FAIL'}] {label}"
        )
        failed |= not ok

    print(
        f"\nRESULT: {'FAIL' if failed else 'PASS'}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
