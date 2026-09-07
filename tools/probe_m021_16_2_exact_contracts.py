from pathlib import Path


FILES = (
    Path("app/osint/open_web/contracts.py"),
    Path("app/osint/open_web/providers/common_crawl.py"),
    Path("app/infrastructure/open_web/common_crawl_metadata_client.py"),
    Path("app/osint/open_web/service.py"),
)


print("=" * 88)
print("M021.16.2 EXACT CONTRACT PROBE")
print("=" * 88)


for path in FILES:
    print()
    print("=" * 88)
    print(path)
    print("=" * 88)

    if not path.exists():
        print("[MISSING]")
        continue

    text = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    for number, line in enumerate(
        text.splitlines(),
        start=1,
    ):
        print(
            f"{number:04d}: {line}"
        )


print()
print("=" * 88)
print("SERVICE CONTAINER OPEN-WEB BLOCK")
print("=" * 88)


container = Path(
    "app/core/service_container.py"
)

lines = container.read_text(
    encoding="utf-8",
    errors="replace",
).splitlines()


start = 1330
end = 1420

for index in range(
    start - 1,
    min(end, len(lines)),
):
    print(
        f"{index + 1:04d}: "
        f"{lines[index]}"
    )


print()
print("PROBE COMPLETE")
