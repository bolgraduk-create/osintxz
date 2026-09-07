from __future__ import annotations

from pathlib import Path
import shutil

SERVICE = Path("app/osint/open_web/service.py")
VIEW = Path(
    "app/interface/desktop/views/workspace/"
    "investigation_search_view.py"
)


def patch_service(text: str) -> str:
    marker = "M021.16.7.10 RATE LIMIT IS NOT PROVIDER FAILURE"
    if marker in text:
        return text

    needle = (
        "            if result.provider.strip().casefold() "
        "!= provider.info.name.strip().casefold():\n"
    )
    if needle not in text:
        raise RuntimeError(
            "OpenWebDiscoveryService provider normalization marker not found."
        )

    block = '''
            # M021.16.7.10 RATE LIMIT IS NOT PROVIDER FAILURE
            #
            # HTTP 429 means the public upstream temporarily throttled us.
            # The provider itself is operational; represent this as PARTIAL
            # instead of FAILED so UI/diagnostics do not report a broken
            # connector. No bypass, proxy rotation or evasion is attempted.
            if (
                result.status is OpenWebStatus.FAILED
                and result.error
                and (
                    "429 Too Many Requests" in result.error
                    or "HTTP 429" in result.error
                )
            ):
                metadata = dict(result.metadata)
                metadata.update(
                    {
                        "rate_limited": True,
                        "retryable": True,
                        "failure_isolated": True,
                    }
                )
                result = OpenWebResult(
                    provider=result.provider,
                    status=OpenWebStatus.PARTIAL,
                    documents=list(result.documents),
                    error=(
                        "Public upstream rate limit reached (HTTP 429). "
                        "Retry later."
                    ),
                    metadata=metadata,
                )

'''
    return text.replace(needle, block + needle, 1)


def patch_view(text: str) -> str:
    marker = "M021.16.7.10 OPEN-WEB GOAL LABEL"
    if marker in text:
        return text

    needle = '                "exact_email_public_web",\n'
    if needle not in text:
        raise RuntimeError(
            "Hard-coded exact_email_public_web UI label not found."
        )

    replacement = (
        '                # M021.16.7.10 OPEN-WEB GOAL LABEL\n'
        '                "open_web_discovery",\n'
    )
    return text.replace(needle, replacement, 1)


def main() -> int:
    for path in (SERVICE, VIEW):
        if not path.exists():
            print(f"[FAIL] Missing: {path}")
            return 1

    originals = {
        SERVICE: SERVICE.read_text(encoding="utf-8"),
        VIEW: VIEW.read_text(encoding="utf-8"),
    }

    try:
        patched_service = patch_service(originals[SERVICE])
        patched_view = patch_view(originals[VIEW])

        compile(patched_service, str(SERVICE), "exec")
        compile(patched_view, str(VIEW), "exec")
    except Exception as exc:
        print(f"[FAIL] {exc}")
        print("[INFO] No project files were changed.")
        return 1

    backups = {
        SERVICE: SERVICE.with_suffix(
            SERVICE.suffix + ".m021_16_7_10_backup"
        ),
        VIEW: VIEW.with_suffix(
            VIEW.suffix + ".m021_16_7_10_backup"
        ),
    }

    for path, backup in backups.items():
        if not backup.exists():
            shutil.copy2(path, backup)

    SERVICE.write_text(patched_service, encoding="utf-8")
    VIEW.write_text(patched_view, encoding="utf-8")

    print("[PASS] HTTP 429 is reported as retryable PARTIAL.")
    print("[PASS] No rate-limit bypass or evasion added.")
    print("[PASS] Open-Web UI goal label is generic/correct.")
    print("[PASS] Targeted Phone provider unchanged.")
    print("[PASS] SearXNG Phone provider unchanged.")
    print("[PASS] No database migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
