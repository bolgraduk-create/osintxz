from pathlib import Path


def main() -> int:
    text = Path(
        "app/osint/pivot_router.py"
    ).read_text(encoding="utf-8")

    checks = [
        (
            "safe SUPPORT marker",
            "M021.16.6.3.1 safe SUPPORT routing" in text,
        ),
        (
            "NetworkMode imported",
            "NetworkMode," in text,
        ),
        (
            "CORE allowed",
            "ConnectorDisposition.CORE" in text,
        ),
        (
            "SUPPORT allowed",
            "ConnectorDisposition.SUPPORT" in text,
        ),
        (
            "network-mode guard",
            "_network_mode_allowed_for_goal" in text,
        ),
        (
            "PASSIVE allowed",
            "NetworkMode.PASSIVE" in text,
        ),
        (
            "PASSIVE_REMOTE allowed",
            "NetworkMode.PASSIVE_REMOTE" in text,
        ),
    ]

    print("=" * 72)
    print("M021.16.6.3.1 SAFE SUPPORT ROUTING AUDIT")
    print("=" * 72)

    failed = False

    for label, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        failed |= not ok

    print(f"\nRESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
