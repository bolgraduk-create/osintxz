"""
Stabilization 08C — remove only the whitespace issues reported by
`git diff --check` during the final post-Astra baseline verification.

No business logic is changed.
"""

from __future__ import annotations

from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]


TRAILING_WHITESPACE_LINES: dict[str, tuple[int, ...]] = {
    "app/analysis/analyzers/entity_analyzer.py": (
        1004,
    ),
    "app/interface/desktop/main_window.py": (
        231,
    ),
    "app/interface/desktop/pages/case_workspace_page.py": (
        3003,
        5301,
        5490,
    ),
    "app/interface/desktop/pages/cases_page.py": (
        1412,
    ),
    "app/interface/desktop/views/workspace/case_workspace_view.py": (
        168,
        373,
        792,
        1544,
    ),
    "app/repositories/message_repository.py": (
        177,
    ),
}


NORMALIZE_EOF: tuple[str, ...] = (
    "app/analysis/analyzers/entity_analyzer.py",
    "app/repositories/entity_repository.py",
    "app/repositories/evidence_repository.py",
    "app/services/telegram_import_service.py",
)


def backup(path: Path) -> None:
    backup_path = path.with_name(
        path.name + ".stabilization08c.bak"
    )

    if not backup_path.exists():
        shutil.copy2(
            path,
            backup_path,
        )
        print(
            f"Backup created: {backup_path}"
        )


def strip_reported_lines(
    relative_path: str,
    line_numbers: tuple[int, ...],
) -> None:
    path = ROOT / relative_path

    if not path.exists():
        raise FileNotFoundError(
            f"Missing file: {path}"
        )

    original = path.read_text(
        encoding="utf-8",
    )

    lines = original.splitlines(
        keepends=True
    )

    for line_number in line_numbers:
        index = line_number - 1

        if index < 0 or index >= len(lines):
            raise RuntimeError(
                f"{relative_path}: line {line_number} "
                "does not exist in the current file."
            )

        line = lines[index]

        if line.endswith("\r\n"):
            body = line[:-2]
            ending = "\n"
        elif line.endswith("\n"):
            body = line[:-1]
            ending = "\n"
        elif line.endswith("\r"):
            body = line[:-1]
            ending = "\n"
        else:
            body = line
            ending = ""

        lines[index] = (
            body.rstrip(" \t")
            + ending
        )

    updated = "".join(
        lines
    )

    if updated != original:
        backup(path)

        path.write_text(
            updated,
            encoding="utf-8",
            newline="\n",
        )

        print(
            f"Trailing whitespace fixed: {relative_path}"
        )
    else:
        print(
            f"No trailing whitespace change needed: {relative_path}"
        )


def normalize_eof(
    relative_path: str,
) -> None:
    path = ROOT / relative_path

    if not path.exists():
        raise FileNotFoundError(
            f"Missing file: {path}"
        )

    original = path.read_text(
        encoding="utf-8",
    )

    # Git's "new blank line at EOF" means the diff adds one or more
    # empty logical lines after the final content line. Keep exactly
    # one terminating newline, but no extra blank lines.
    updated = original.rstrip(
        " \t\r\n"
    ) + "\n"

    if updated != original:
        backup(path)

        path.write_text(
            updated,
            encoding="utf-8",
            newline="\n",
        )

        print(
            f"EOF normalized: {relative_path}"
        )
    else:
        print(
            f"EOF already normalized: {relative_path}"
        )


def main() -> None:
    for relative_path, line_numbers in (
        TRAILING_WHITESPACE_LINES.items()
    ):
        strip_reported_lines(
            relative_path,
            line_numbers,
        )

    for relative_path in NORMALIZE_EOF:
        normalize_eof(
            relative_path
        )

    print("")
    print(
        "Stabilization 08C whitespace cleanup: PASS"
    )
    print(
        "Run: git diff --check"
    )


if __name__ == "__main__":
    main()
