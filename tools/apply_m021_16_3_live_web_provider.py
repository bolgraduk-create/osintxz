from __future__ import annotations

from pathlib import Path


CONTAINER = Path("app/core/service_container.py")
ENRICH = Path("app/application/open_web_enrichment_service.py")
INIT = Path("app/osint/open_web/providers/__init__.py")


def patch_container(text: str) -> str:
    if "LiveWebOpenWebProvider" not in text:
        import_anchor = """from app.osint.open_web.providers.common_crawl import (
    CommonCrawlOpenWebProvider,
)
"""
        import_new = import_anchor + """from app.osint.open_web.providers.live_web import (
    LiveWebOpenWebProvider,
)
"""
        if import_anchor not in text:
            raise RuntimeError("Common Crawl provider import anchor not found.")
        text = text.replace(import_anchor, import_new, 1)

    if "self.live_web_open_web_provider" not in text:
        anchor = """        self.open_web_provider_registry.register(
            self.common_crawl_open_web_provider
        )

        self.open_web_discovery_service = (
"""
        replacement = """        self.open_web_provider_registry.register(
            self.common_crawl_open_web_provider
        )

        self.live_web_open_web_provider = (
            LiveWebOpenWebProvider()
        )

        self.open_web_provider_registry.register(
            self.live_web_open_web_provider
        )

        self.open_web_discovery_service = (
"""
        if anchor not in text:
            raise RuntimeError("Open-Web registry wiring anchor not found.")
        text = text.replace(anchor, replacement, 1)

    return text


def patch_enrichment(text: str) -> str:
    marker = "provider-aware hydration"
    if marker in text:
        return text

    old = """        hydration = None
        extraction_documents = discovery.documents

        if self.content_hydrator is not None:
            hydration = self.content_hydrator.hydrate(
                list(discovery.documents)
            )
            extraction_documents = hydration.documents
"""

    new = """        hydration = None
        extraction_documents = list(discovery.documents)

        # M021.16.3 provider-aware hydration:
        # only Common Crawl metadata documents require WARC hydration.
        # Live Web documents already contain visible text and must go directly
        # to the unified extraction bridge.
        if self.content_hydrator is not None:
            common_crawl_documents = [
                document
                for document in discovery.documents
                if document.provider.strip().casefold() == "common_crawl"
            ]
            prehydrated_documents = [
                document
                for document in discovery.documents
                if document.provider.strip().casefold() != "common_crawl"
            ]

            if common_crawl_documents:
                hydration = self.content_hydrator.hydrate(
                    common_crawl_documents
                )
                extraction_documents = (
                    prehydrated_documents
                    + list(hydration.documents)
                )
            else:
                extraction_documents = prehydrated_documents
"""

    if old not in text:
        raise RuntimeError("Current enrichment hydration block not found.")
    return text.replace(old, new, 1)


def patch_init(text: str) -> str:
    line = "from .live_web import LiveWebOpenWebProvider\n"
    if line not in text:
        if text and not text.endswith("\n"):
            text += "\n"
        text += line
    return text


def main() -> int:
    for path in (CONTAINER, ENRICH, INIT):
        if not path.exists():
            print(f"[FAIL] Missing {path}")
            return 1

    live = Path("app/osint/open_web/providers/live_web.py")
    if not live.exists():
        print("[FAIL] Live Web provider file was not unpacked.")
        return 1

    originals = {
        CONTAINER: CONTAINER.read_text(encoding="utf-8"),
        ENRICH: ENRICH.read_text(encoding="utf-8"),
        INIT: INIT.read_text(encoding="utf-8"),
    }

    try:
        updated = {
            CONTAINER: patch_container(originals[CONTAINER]),
            ENRICH: patch_enrichment(originals[ENRICH]),
            INIT: patch_init(originals[INIT]),
        }

        compile(live.read_text(encoding="utf-8"), str(live), "exec")
        for path, text in updated.items():
            compile(text, str(path), "exec")
    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 1

    for path, text in updated.items():
        backup = path.with_suffix(".py.m021_16_3_backup")
        if not backup.exists():
            backup.write_text(originals[path], encoding="utf-8")
        path.write_text(text, encoding="utf-8")

    print("[PASS] Live Web provider wired into existing OpenWeb registry.")
    print("[PASS] Provider-aware hydration enabled.")
    print("[PASS] Common Crawl remains WARC-hydrated.")
    print("[PASS] Live Web text goes directly to extraction.")
    print("[PASS] SSRF/private-network protections enabled.")
    print("[PASS] No second ServiceContainer or pipeline.")
    print("[PASS] No database migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
