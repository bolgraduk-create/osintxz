from __future__ import annotations

from pathlib import Path


FILES = (
    Path("app/interface/desktop/workers/investigation_search_worker.py"),
    Path("app/osint/manager.py"),
    Path("app/osint/pipeline.py"),
    Path("app/osint/runner.py"),
    Path("app/osint/registry.py"),
    Path("app/osint/enrichment_execution.py"),
    Path("app/core/service_container.py"),
)

EMAIL_TOKENS = (
    "email",
    "holehe",
    "haveibeenpwned",
    "hibp",
    "ghunt",
)


print("=" * 88)
print("M021.16.4.1 EMAIL DISCOVERY ARCHITECTURE AUDIT")
print("=" * 88)


print("\n=== EMAIL-RELATED FILES ===")

for root in (
    Path("app/osint"),
    Path("app/application"),
):
    if not root.exists():
        continue

    for path in sorted(root.rglob("*.py")):
        text = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        if any(
            token in text.casefold()
            for token in EMAIL_TOKENS
        ):
            print(path)


print("\n=== EXACT CORE CONTRACTS ===")

for path in FILES:
    print()
    print("=" * 88)
    print(path)
    print("=" * 88)

    if not path.exists():
        print("[MISSING]")
        continue

    lines = path.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()

    for number, line in enumerate(
        lines,
        start=1,
    ):
        lowered = line.casefold()

        if (
            path.name == "investigation_search_worker.py"
            or any(
                token in lowered
                for token in (
                    "enrich",
                    "pipeline",
                    "execute",
                    "run",
                    "registry",
                    "capability",
                    "recursive",
                    "open_web",
                    "osint_",
                )
            )
        ):
            print(
                f"{number:04d}: {line}"
            )


print("\n=== EMAIL CONNECTOR CONTRACTS ===")

for root in (
    Path("app/osint/connectors"),
    Path("app/osint"),
):
    if not root.exists():
        continue

    for path in sorted(root.rglob("*.py")):
        name = path.name.casefold()

        if not any(
            token in name
            for token in EMAIL_TOKENS
        ):
            continue

        print()
        print("=" * 88)
        print(path)
        print("=" * 88)

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


print("\n=== SERVICE CONTAINER EMAIL / OSINT WIRING ===")

container = Path(
    "app/core/service_container.py"
)

if container.exists():
    for number, line in enumerate(
        container.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines(),
        start=1,
    ):
        lowered = line.casefold()

        if any(
            token in lowered
            for token in (
                "holehe",
                "hibp",
                "email",
                "osint_pipeline",
                "recursive_enrichment",
                "enrichment_execution",
                "pivot",
            )
        ):
            print(
                f"{number:04d}: {line}"
            )


print("\nAUDIT COMPLETE")
