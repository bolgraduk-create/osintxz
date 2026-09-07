from pathlib import Path

FILES = [
    Path(
        r"app/interface/desktop/pages/"
        r"case_workspace_page.py"
    ),
    Path(
        r"app/interface/desktop/views/workspace/"
        r"case_workspace_view.py"
    ),
    Path(
        r"app/interface/desktop/managers/"
        r"page_manager.py"
    ),
]

RANGES = {
    "case_workspace_page.py": [
        (1, 230),
        (1080, 1245),
    ],
    "case_workspace_view.py": [
        (1, 430),
    ],
    "page_manager.py": [
        (1, 235),
    ],
}

print("=" * 80)
print("M021.15 EXACT UI CONTRACT PROBE")
print("=" * 80)

for path in FILES:
    print("\n")
    print("=" * 80)
    print("FILE:", path)
    print("=" * 80)

    if not path.exists():
        print("[MISSING]")
        continue

    lines = path.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()

    wanted = RANGES.get(
        path.name,
        [],
    )

    for start, end in wanted:
        print(
            f"\n--- LINES {start}-{end} ---"
        )

        for number in range(
            start,
            min(end, len(lines)) + 1,
        ):
            print(
                f"{number:05}: "
                f"{lines[number - 1]}"
            )
