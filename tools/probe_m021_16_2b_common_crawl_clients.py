from pathlib import Path


FILES = (
    Path("app/infrastructure/open_web/common_crawl_client.py"),
    Path("app/infrastructure/open_web/common_crawl_raw_index.py"),
)


print("=" * 88)
print("M021.16.2B COMMON CRAWL CLIENT CONTRACT PROBE")
print("=" * 88)

for path in FILES:
    print()
    print("=" * 88)
    print(path)
    print("=" * 88)

    if not path.exists():
        print("[MISSING]")
        continue

    for number, line in enumerate(
        path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines(),
        start=1,
    ):
        print(f"{number:04d}: {line}")

print()
print("PROBE COMPLETE")
