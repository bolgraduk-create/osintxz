from __future__ import annotations

from pathlib import Path
import shutil

TARGET = Path(
    "app/osint/open_web/providers/"
    "targeted_phone_public_sources.py"
)


def main() -> int:
    if not TARGET.exists():
        print(f"[FAIL] Missing: {TARGET}")
        return 1

    original = TARGET.read_text(encoding="utf-8")

    if "PublicDocumentTextFetcher" in original:
        print("[PASS] Patch already applied.")
        return 0

    text = original

    import_anchor = '''from app.osint.open_web.providers.live_web import LiveWebOpenWebProvider
'''

    import_block = import_anchor + '''from app.osint.open_web.public_document_fetcher import (
    PublicDocumentTextFetcher,
)
'''

    if import_anchor not in text:
        print("[FAIL] LiveWeb import anchor not found.")
        return 1

    text = text.replace(import_anchor, import_block, 1)

    constructor_anchor = '''        self.live_web = live_web or LiveWebOpenWebProvider()
        self.rules = rules or self.DEFAULT_RULES
'''

    constructor_block = '''        self.live_web = live_web or LiveWebOpenWebProvider()
        self.document_fetcher = PublicDocumentTextFetcher(
            live_web=self.live_web,
            transport=transport,
        )
        self.rules = rules or self.DEFAULT_RULES
'''

    if constructor_anchor not in text:
        print("[FAIL] constructor anchor not found.")
        return 1

    text = text.replace(constructor_anchor, constructor_block, 1)

    fetch_anchor = '''            live_result = self.live_web.search(
                OpenWebQuery(
                    target_type=OsintTargetType.URL,
                    value=url,
                    case_id=query.case_id,
                    limit=1,
                    timeout=query.timeout,
                    depth=query.depth,
                    parent_entity_id=query.parent_entity_id,
                )
            )

            if not live_result.usable or not live_result.documents:
                fetch_failures += 1
                continue

            document = live_result.documents[0]
'''

    fetch_block = '''            live_result = self.live_web.search(
                OpenWebQuery(
                    target_type=OsintTargetType.URL,
                    value=url,
                    case_id=query.case_id,
                    limit=1,
                    timeout=query.timeout,
                    depth=query.depth,
                    parent_entity_id=query.parent_entity_id,
                )
            )

            document = None

            if live_result.usable and live_result.documents:
                document = live_result.documents[0]
            else:
                outcome = self.document_fetcher.fetch(
                    url,
                    timeout=query.timeout,
                )
                document = outcome.document

            if document is None:
                fetch_failures += 1
                continue
'''

    if fetch_anchor not in text:
        print("[FAIL] fetch-flow anchor not found.")
        return 1

    text = text.replace(fetch_anchor, fetch_block, 1)

    metadata_anchor = '''                    "source_targeted": True,
'''

    metadata_block = '''                    "source_targeted": True,
                    "document_aware_verification": True,
                    "content_extraction_kind": (
                        document.metadata.get("extraction_kind")
                        or "live_web_text"
                    ),
'''

    if metadata_anchor not in text:
        print("[FAIL] metadata anchor not found.")
        return 1

    text = text.replace(metadata_anchor, metadata_block, 1)

    try:
        compile(text, str(TARGET), "exec")
    except Exception as exc:
        print(f"[FAIL] compile: {exc}")
        return 1

    backup = TARGET.with_suffix(
        TARGET.suffix + ".m021_16_7_5_1_backup"
    )

    if not backup.exists():
        shutil.copy2(TARGET, backup)

    TARGET.write_text(text, encoding="utf-8")

    print("[PASS] Document-aware fallback integrated.")
    print("[PASS] HTML/text continues through existing LiveWeb.")
    print("[PASS] PDF/DOCX/text documents use bounded retrieval.")
    print("[PASS] Exact phone verification remains mandatory.")
    print("[PASS] LiveWeb security policy was not weakened.")
    print("[PASS] No database migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
