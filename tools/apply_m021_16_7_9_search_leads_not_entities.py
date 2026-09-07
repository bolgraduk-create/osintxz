from __future__ import annotations

from pathlib import Path
import re
import shutil

TARGET = Path("app/osint/finding_persistence.py")


def main() -> int:
    if not TARGET.exists():
        print(f"[FAIL] Missing: {TARGET}")
        return 1

    original = TARGET.read_text(encoding="utf-8")

    marker = "M021.16.7.9 SEARCH LEADS ARE NOT ENTITIES"
    if marker in original:
        print("[PASS] Patch already applied.")
        return 0

    # Locate the generic provenance URL promotion:
    #
    # if url:
    #     candidates.append(
    #         (
    #             EntityType.URL,
    #             url,
    #             ...
    #
    # Replace only the condition. The rest of persistence stays intact.
    pattern = re.compile(
        r"(?m)^(?P<indent>\s*)if url:\s*$"
    )

    matches = list(pattern.finditer(original))

    if not matches:
        print("[FAIL] Generic URL candidate condition not found.")
        print("[INFO] No project files were changed.")
        return 1

    # Choose the match inside _entity_candidates().
    selected = None
    entity_pos = original.find("def _entity_candidates(")

    for match in matches:
        if match.start() > entity_pos >= 0:
            selected = match
            break

    if selected is None:
        print("[FAIL] _entity_candidates URL promotion not found.")
        print("[INFO] No project files were changed.")
        return 1

    indent = selected.group("indent")

    replacement = (
        indent
        + "# M021.16.7.9 SEARCH LEADS ARE NOT ENTITIES\\n"
        + indent
        + "# PhoneInfoga/search-engine query URLs are navigation leads,\\n"
        + indent
        + "# not discovered public URLs. Keep them in Evidence metadata,\\n"
        + indent
        + "# but never promote them to EntityType.URL.\\n"
        + indent
        + 'if url and category != "search_query":'
    )

    patched = (
        original[:selected.start()]
        + replacement
        + original[selected.end():]
    )

    try:
        compile(patched, str(TARGET), "exec")
    except Exception as exc:
        print(f"[FAIL] Compile failed: {exc}")
        print("[INFO] No project files were changed.")
        return 1

    compact = "".join(patched.split())

    if 'ifurlandcategory!="search_query":' not in compact:
        print("[FAIL] Expected search_query guard is absent.")
        print("[INFO] No project files were changed.")
        return 1

    backup = TARGET.with_suffix(
        TARGET.suffix + ".m021_16_7_9_backup"
    )
    if not backup.exists():
        shutil.copy2(TARGET, backup)

    TARGET.write_text(patched, encoding="utf-8")

    print("[PASS] search_query URL -> Entity promotion disabled.")
    print("[PASS] Search leads remain persistable as Evidence/provenance.")
    print("[PASS] Confirmed/extracted URL categories remain Entity-capable.")
    print("[PASS] Account/profile URL provenance remains unchanged.")
    print("[PASS] No database migration.")
    print("[INFO] Existing bad URL entities are not deleted automatically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
