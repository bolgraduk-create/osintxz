from pathlib import Path


FILES = (
    Path(
        "app/interface/desktop/workers/"
        "investigation_search_worker.py"
    ),
    Path(
        "app/osint/enrichment_execution.py"
    ),
    Path(
        "app/osint/pipeline.py"
    ),
    Path(
        "app/osint/registry.py"
    ),
)


print("=" * 88)
print("M021.16.4.2 EMAIL EXECUTION CONTRACT")
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
        print(
            f"{number:04d}: {line}"
        )


print()
print("=" * 88)
print("SERVICE CONTAINER OSINT BLOCK")
print("=" * 88)


container = Path(
    "app/core/service_container.py"
)

lines = container.read_text(
    encoding="utf-8",
    errors="replace",
).splitlines()

for start, end in (
    (1280, 1345),
    (1400, 1470),
):
    print()
    print(
        f"--- lines {start}-{end} ---"
    )

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
