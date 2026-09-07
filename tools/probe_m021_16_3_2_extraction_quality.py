from __future__ import annotations

from pathlib import Path


ROOTS = (
    Path("app/processing"),
    Path("app/services"),
    Path("app/application"),
    Path("app/osint"),
)

TOKENS = (
    "phone",
    "PHONE",
    "url",
    "URL",
    "UnifiedExtraction",
    "extract_identifiers",
    "extraction",
)


print("=" * 88)
print("M021.16.3.2 EXTRACTION QUALITY CONTRACT PROBE")
print("=" * 88)


files = []

for root in ROOTS:
    if not root.exists():
        continue

    for path in root.rglob("*.py"):
        try:
            text = path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            continue

        lower = text.casefold()

        if (
            "phone" in lower
            or "unifiedextraction" in lower
            or "extractionbridge" in lower
        ):
            files.append(path)


print("\n=== RELEVANT FILES ===")

for path in sorted(set(files)):
    print(path)


print("\n=== PHONE / URL EXTRACTION REFERENCES ===")

for path in sorted(set(files)):
    text = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    lines = text.splitlines()

    hits = []

    for number, line in enumerate(
        lines,
        start=1,
    ):
        low = line.casefold()

        if any(
            token in low
            for token in (
                "phone",
                "url_pattern",
                "url_regex",
                "extract_url",
                "extract_phone",
                "phonenumbers",
                "unifiedextraction",
            )
        ):
            hits.append(number)

    if not hits:
        continue

    print()
    print("=" * 88)
    print(path)
    print("=" * 88)

    emitted = set()

    for hit in hits:
        start = max(1, hit - 8)
        end = min(
            len(lines),
            hit + 15,
        )

        for number in range(
            start,
            end + 1,
        ):
            if number in emitted:
                continue

            emitted.add(number)

            print(
                f"{number:04d}: "
                f"{lines[number - 1]}"
            )


print("\n=== OPEN WEB EXTRACTION BRIDGE FULL ===")

bridge = Path(
    "app/osint/open_web/extraction_bridge.py"
)

if bridge.exists():
    for number, line in enumerate(
        bridge.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines(),
        start=1,
    ):
        print(
            f"{number:04d}: {line}"
        )


print("\n=== DEPENDENCY CHECK ===")

try:
    import phonenumbers
except ImportError:
    print("phonenumbers: NOT INSTALLED")
else:
    print(
        "phonenumbers: INSTALLED",
        getattr(
            phonenumbers,
            "__version__",
            "unknown",
        ),
    )


print("\nPROBE COMPLETE")
