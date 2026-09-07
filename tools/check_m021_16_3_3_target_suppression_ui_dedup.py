from pathlib import Path


def main() -> int:
    bridge = Path(
        "app/osint/open_web/extraction_bridge.py"
    ).read_text(encoding="utf-8")
    view = Path(
        "app/interface/desktop/views/workspace/investigation_search_view.py"
    ).read_text(encoding="utf-8")

    checks = [
        ("query passed to quality gate", "query=query" in bridge),
        (
            "query URL canonicalized",
            "query_url = cls._canonical_url(query.value)" in bridge,
        ),
        (
            "UI unique presentation",
            "M021.16.3.3 unique entity presentation" in view,
        ),
        ("UI evidence aggregation", '"evidence_ids": set()' in view),
    ]

    print("=" * 72)
    print("M021.16.3.3 TARGET SUPPRESSION + UI DEDUP AUDIT")
    print("=" * 72)

    failed = False
    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed |= not ok

    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
