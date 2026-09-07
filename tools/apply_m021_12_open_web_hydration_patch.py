from pathlib import Path

APP_PATH = Path(
    "app/application/open_web_enrichment_service.py"
)
CONTAINER_PATH = Path(
    "app/core/service_container.py"
)


def patch_application() -> tuple[bool, str]:
    original = APP_PATH.read_text(
        encoding="utf-8"
    )
    text = original

    if (
        "from app.osint.open_web.content_hydration import"
        not in text
    ):
        anchor = (
            "from app.osint.open_web.contracts import OpenWebQuery\n"
        )
        import_block = (
            "from app.osint.open_web.content_hydration import (\n"
            "    CommonCrawlContentHydrator,\n"
            "    OpenWebHydrationBatchResult,\n"
            ")\n"
        )
        if anchor not in text:
            return False, "OpenWebQuery import anchor not found."
        text = text.replace(
            anchor,
            anchor + import_block,
            1,
        )

    if (
        "hydration: OpenWebHydrationBatchResult | None"
        not in text
    ):
        anchor = (
            "    extraction: OpenWebExtractionBatchResult\n"
        )
        if anchor not in text:
            return False, "result extraction field anchor not found."
        text = text.replace(
            anchor,
            (
                "    hydration: OpenWebHydrationBatchResult | None\n"
                "    extraction: OpenWebExtractionBatchResult\n"
            ),
            1,
        )

    if (
        "content_hydrator: CommonCrawlContentHydrator | None = None"
        not in text
    ):
        anchor = (
            "        persistence_service: OsintFindingPersistenceService,\n"
            "    ) -> None:\n"
        )
        if anchor not in text:
            return False, "constructor anchor not found."
        text = text.replace(
            anchor,
            (
                "        persistence_service: OsintFindingPersistenceService,\n"
                "        content_hydrator: CommonCrawlContentHydrator | None = None,\n"
                "    ) -> None:\n"
            ),
            1,
        )

        assignment = (
            "        self.persistence_service = persistence_service\n"
        )
        if assignment not in text:
            return False, "persistence assignment anchor not found."
        text = text.replace(
            assignment,
            assignment
            + "        self.content_hydrator = content_hydrator\n",
            1,
        )

    if (
        "hydration = self.content_hydrator.hydrate("
        not in text
    ):
        old = (
            "        discovery = self.discovery_service.discover(query)\n"
            "        extraction = self.extraction_bridge.extract_documents(\n"
            "            discovery.documents,\n"
            "            query=query,\n"
            "        )\n"
        )
        new = (
            "        discovery = self.discovery_service.discover(query)\n"
            "\n"
            "        hydration = None\n"
            "        extraction_documents = discovery.documents\n"
            "\n"
            "        if self.content_hydrator is not None:\n"
            "            hydration = self.content_hydrator.hydrate(\n"
            "                list(discovery.documents)\n"
            "            )\n"
            "            extraction_documents = hydration.documents\n"
            "\n"
            "        extraction = self.extraction_bridge.extract_documents(\n"
            "            extraction_documents,\n"
            "            query=query,\n"
            "        )\n"
        )
        if old not in text:
            return False, "discovery/extraction block anchor not found."
        text = text.replace(
            old,
            new,
            1,
        )

    if (
        "            hydration=hydration,"
        not in text
    ):
        anchor = (
            "            discovery=discovery,\n"
            "            extraction=extraction,\n"
        )
        if anchor not in text:
            return False, "result constructor anchor not found."
        text = text.replace(
            anchor,
            (
                "            discovery=discovery,\n"
                "            hydration=hydration,\n"
                "            extraction=extraction,\n"
            ),
            1,
        )

    compile(
        text,
        str(APP_PATH),
        "exec",
    )

    backup = APP_PATH.with_suffix(
        ".py.m021_12_backup"
    )
    if (
        text != original
        and not backup.exists()
    ):
        backup.write_text(
            original,
            encoding="utf-8",
        )

    APP_PATH.write_text(
        text,
        encoding="utf-8",
    )
    return True, str(backup)


def patch_container() -> tuple[bool, str]:
    original = CONTAINER_PATH.read_text(
        encoding="utf-8"
    )
    text = original

    if (
        "from app.infrastructure.open_web.common_crawl_warc_client import"
        not in text
    ):
        anchor = "class ServiceContainer:"
        imports = (
            "from app.infrastructure.open_web.common_crawl_warc_client import (\n"
            "    CommonCrawlWarcContentClient,\n"
            ")\n"
            "from app.osint.open_web.content_hydration import (\n"
            "    CommonCrawlContentHydrator,\n"
            ")\n\n"
        )
        if anchor not in text:
            return False, "ServiceContainer class anchor not found."
        text = text.replace(
            anchor,
            imports + anchor,
            1,
        )

    if (
        "self.common_crawl_warc_content_client ="
        not in text
    ):
        anchor = (
            "        self.open_web_enrichment_service = (\n"
        )
        wiring = (
            "        self.common_crawl_warc_content_client = (\n"
            "            CommonCrawlWarcContentClient()\n"
            "        )\n"
            "\n"
            "        self.common_crawl_content_hydrator = (\n"
            "            CommonCrawlContentHydrator(\n"
            "                client=self.common_crawl_warc_content_client,\n"
            "                max_documents=3,\n"
            "                timeout=20,\n"
            "            )\n"
            "        )\n"
            "\n"
        )
        if anchor not in text:
            return False, "OpenWebEnrichmentService wiring anchor not found."
        text = text.replace(
            anchor,
            wiring + anchor,
            1,
        )

    if (
        "content_hydrator=("
        not in text
    ):
        anchor = (
            "                persistence_service=(\n"
            "                    self.osint_finding_persistence_service\n"
            "                ),\n"
        )
        if anchor not in text:
            return False, "persistence wiring anchor not found."
        text = text.replace(
            anchor,
            anchor
            + (
                "                content_hydrator=(\n"
                "                    self.common_crawl_content_hydrator\n"
                "                ),\n"
            ),
            1,
        )

    compile(
        text,
        str(CONTAINER_PATH),
        "exec",
    )

    checks = {
        "warc client": (
            text.count(
                "self.common_crawl_warc_content_client ="
            )
            == 1
        ),
        "hydrator": (
            text.count(
                "self.common_crawl_content_hydrator ="
            )
            == 1
        ),
        "open-web enrichment": (
            text.count(
                "self.open_web_enrichment_service ="
            )
            == 1
        ),
        "osint pipeline": (
            text.count(
                "self.osint_pipeline ="
            )
            == 1
        ),
    }

    if not all(
        checks.values()
    ):
        return False, (
            "ServiceContainer singleton guard failed: "
            + ", ".join(
                key
                for key, value
                in checks.items()
                if not value
            )
        )

    backup = CONTAINER_PATH.with_suffix(
        ".py.m021_12_backup"
    )
    if (
        text != original
        and not backup.exists()
    ):
        backup.write_text(
            original,
            encoding="utf-8",
        )

    CONTAINER_PATH.write_text(
        text,
        encoding="utf-8",
    )
    return True, str(backup)


def main() -> int:
    if (
        not APP_PATH.is_file()
        or not CONTAINER_PATH.is_file()
    ):
        print(
            "[FAIL] Required M021.9/M021.10 files are missing."
        )
        return 1

    ok, info = patch_application()
    if not ok:
        print(
            f"[FAIL] Application patch: {info}"
        )
        return 1

    print(
        "[PASS] OpenWebEnrichmentService hydration boundary applied."
    )
    print(
        f"[INFO] Application backup: {info}"
    )

    ok, info = patch_container()
    if not ok:
        print(
            f"[FAIL] ServiceContainer patch: {info}"
        )
        return 1

    print(
        "[PASS] M021.12 ServiceContainer hydration wiring applied."
    )
    print(
        f"[INFO] Container backup: {info}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
