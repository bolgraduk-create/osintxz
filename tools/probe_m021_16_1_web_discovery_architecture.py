from __future__ import annotations

from pathlib import Path


ROOT = Path("app")


PATTERNS = (
    "common_crawl",
    "CommonCrawl",
    "open_web",
    "OpenWeb",
    "warc",
    "WARC",
)


print("=" * 80)
print("M021.16.1 MULTI-SOURCE WEB DISCOVERY AUDIT")
print("=" * 80)


print("\n=== RELEVANT FILES ===")

relevant = []

for path in ROOT.rglob("*.py"):
    try:
        text = path.read_text(
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        continue

    if any(
        pattern in text
        for pattern in PATTERNS
    ):
        relevant.append(path)


for path in sorted(relevant):
    print(path)


print("\n=== CLASSES / FUNCTIONS ===")

for path in sorted(relevant):
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
        stripped = line.strip()

        if (
            stripped.startswith("class ")
            or stripped.startswith("def ")
            or stripped.startswith("async def ")
        ):
            if any(
                token.casefold()
                in stripped.casefold()
                for token in (
                    "common",
                    "crawl",
                    "open_web",
                    "openweb",
                    "warc",
                    "discover",
                    "provider",
                    "hydrate",
                )
            ):
                hits.append(
                    (
                        number,
                        stripped,
                    )
                )

    if hits:
        print(f"\n--- {path} ---")

        for number, line in hits:
            print(
                f"{number}: {line}"
            )


print("\n=== SERVICE CONTAINER REFERENCES ===")

container = Path(
    "app/core/service_container.py"
)

if container.exists():
    lines = container.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()

    for number, line in enumerate(
        lines,
        start=1,
    ):
        if any(
            token in line.casefold()
            for token in (
                "open_web",
                "common_crawl",
                "warc",
            )
        ):
            start = max(
                0,
                number - 4,
            )
            end = min(
                len(lines),
                number + 4,
            )

            print(
                f"\n--- around line {number} ---"
            )

            for index in range(
                start,
                end,
            ):
                print(
                    f"{index + 1}: "
                    f"{lines[index]}"
                )


print("\n=== TEST FILES ===")

tests = Path("tests")

if tests.exists():
    for path in sorted(
        tests.rglob("*.py")
    ):
        name = path.name.casefold()

        if any(
            token in name
            for token in (
                "common",
                "open_web",
                "warc",
                "m021_11",
                "m021_12",
                "m021_13",
                "m021_14",
                "m021_15",
            )
        ):
            print(path)


print("\nAUDIT COMPLETE")
