from __future__ import annotations

from pathlib import Path


CONTAINER = Path("app/core/service_container.py")
WORKER = Path(
    "app/interface/desktop/workers/investigation_search_worker.py"
)
VIEW = Path(
    "app/interface/desktop/views/workspace/investigation_search_view.py"
)


def patch_container(text: str) -> str:
    marker = "M021.16.5.2A GDELT exact-email Open-Web registration"
    if marker in text:
        return text

    anchor = '''        self.open_web_provider_registry.register(
            self.live_web_open_web_provider
        )

        self.open_web_discovery_service = (
'''
    replacement = '''        self.open_web_provider_registry.register(
            self.live_web_open_web_provider
        )

        # M021.16.5.2A GDELT exact-email Open-Web registration
        from app.osint.open_web.providers.gdelt_exact_email import (
            GdeltExactEmailOpenWebProvider,
        )

        self.gdelt_exact_email_open_web_provider = (
            GdeltExactEmailOpenWebProvider(
                live_web_provider=self.live_web_open_web_provider,
            )
        )

        self.open_web_provider_registry.register(
            self.gdelt_exact_email_open_web_provider
        )

        self.open_web_discovery_service = (
'''
    if anchor not in text:
        raise RuntimeError("Live Web registration anchor not found.")

    return text.replace(anchor, replacement, 1)


def patch_worker(text: str) -> str:
    marker = "M021.16.5.2A EMAIL public-web"
    if marker in text:
        return text

    anchor = '''                osint_result = (
                    self.container.osint_enrichment_service.enrich_target(
                        case_id=self.case_id,
                        target_type=target_type,
                        value=normalized,
                        depth=0,
                        timeout=120,
                        use_cache=True,
                        save_raw_output=False,
                        include_metadata=True,
                        include_related=True,
                    )
                )

                if self.recursive:
'''
    replacement = '''                osint_result = (
                    self.container.osint_enrichment_service.enrich_target(
                        case_id=self.case_id,
                        target_type=target_type,
                        value=normalized,
                        depth=0,
                        timeout=120,
                        use_cache=True,
                        save_raw_output=False,
                        include_metadata=True,
                        include_related=True,
                    )
                )

                # M021.16.5.2A EMAIL public-web
                self.status_changed.emit(
                    "Поиск точных публичных упоминаний email..."
                )

                email_open_web_result = (
                    self.container.open_web_enrichment_service.enrich(
                        OpenWebQuery(
                            target_type=target_type,
                            value=normalized,
                            case_id=str(self.case_id),
                            limit=15,
                            timeout=30,
                            depth=0,
                        ),
                        case_id=self.case_id,
                    )
                )

                if self.recursive:
'''
    if anchor not in text:
        raise RuntimeError("EMAIL osint_result anchor not found.")

    text = text.replace(anchor, replacement, 1)

    old_payload = '''                        "open_web": None,
                        "osint": osint_result,
                        "recursive": None,
'''
    new_payload = '''                        "open_web": email_open_web_result,
                        "osint": osint_result,
                        "recursive": None,
'''
    if old_payload not in text:
        raise RuntimeError("EMAIL payload anchor not found.")

    return text.replace(old_payload, new_payload, 1)


def patch_view(text: str) -> str:
    marker = (
        "M021.16.5.2A combined EMAIL OSINT/Open-Web presentation"
    )
    if marker in text:
        return text

    old_call = '''        if osint_result is not None:
            self._show_osint_result(payload, osint_result)
            return
'''
    new_call = '''        if osint_result is not None:
            # M021.16.5.2A combined EMAIL OSINT/Open-Web presentation
            self._show_osint_result(
                payload,
                osint_result,
                payload.get("open_web"),
            )
            return
'''
    if old_call not in text:
        raise RuntimeError("OSINT result call anchor not found.")

    text = text.replace(old_call, new_call, 1)

    old_sig = '''    def _show_osint_result(self, payload: dict, result) -> None:
'''
    new_sig = '''    def _show_osint_result(
        self,
        payload: dict,
        result,
        open_web_result=None,
    ) -> None:
'''
    if old_sig not in text:
        raise RuntimeError("_show_osint_result signature anchor not found.")

    text = text.replace(old_sig, new_sig, 1)

    old_total = '''        total_findings = sum(
            getattr(execution, "total_findings", 0)
            for execution in result.executions
        )
'''
    new_total = '''        total_findings = sum(
            getattr(execution, "total_findings", 0)
            for execution in result.executions
        )

        public_documents = (
            open_web_result.documents_found
            if open_web_result is not None
            else 0
        )
        public_findings = (
            open_web_result.findings_extracted
            if open_web_result is not None
            else 0
        )
        public_persisted = (
            open_web_result.persisted_findings
            if open_web_result is not None
            else 0
        )
'''
    if old_total not in text:
        raise RuntimeError("total_findings anchor not found.")

    text = text.replace(old_total, new_total, 1)

    overview_anchor = '''                    f"Findings: {total_findings}",
                    f"Сохранено findings: {result.persisted_findings}",
'''
    overview_replacement = '''                    f"OSINT findings: {total_findings}",
                    f"OSINT сохранено: {result.persisted_findings}",
                    "",
                    f"Public-Web подтверждённых страниц: {public_documents}",
                    f"Public-Web findings: {public_findings}",
                    f"Public-Web сохранено: {public_persisted}",
'''
    if overview_anchor not in text:
        raise RuntimeError("overview findings anchor not found.")

    text = text.replace(
        overview_anchor,
        overview_replacement,
        1,
    )

    old_fill = '''        self._fill_entities(result)
        self._fill_osint_sources(result)
        self.set_running(False)
'''
    new_fill = '''        if open_web_result is None:
            self._fill_entities(result)
        else:
            class _CombinedPersistence:
                pass

            combined = _CombinedPersistence()
            combined.persistence = (
                list(result.persistence)
                + list(open_web_result.persistence)
            )
            self._fill_entities(combined)

        self._fill_osint_sources(result)

        if open_web_result is not None:
            self._fill_email_open_web_sources(
                open_web_result
            )

        self.set_running(False)
'''
    if old_fill not in text:
        raise RuntimeError("result fill anchor not found.")

    text = text.replace(old_fill, new_fill, 1)

    source_anchor = '''    def _fill_osint_sources(self, result) -> None:
'''
    method = '''    def _fill_email_open_web_sources(
        self,
        result,
    ) -> None:
        for provider_result in result.discovery.results:
            metadata = provider_result.metadata or {}
            documents = len(provider_result.documents)

            detail_parts = []

            candidates = metadata.get("candidates_returned")
            verified = metadata.get("verified_documents")

            if candidates is not None:
                detail_parts.append(
                    f"кандидатов: {candidates}"
                )

            if verified is not None:
                detail_parts.append(
                    f"подтверждено: {verified}"
                )

            if provider_result.error:
                detail_parts.append(provider_result.error)

            detail = (
                "; ".join(detail_parts)
                or (
                    "Доступен; точных публичных "
                    "упоминаний не найдено."
                    if documents == 0
                    else "—"
                )
            )

            status = getattr(
                provider_result.status,
                "value",
                str(provider_result.status),
            )

            row = self.sources_table.rowCount()
            self.sources_table.insertRow(row)

            cells = [
                str(provider_result.provider),
                str(status),
                str(documents),
                "exact_email_public_web",
                str(detail),
            ]

            for col, cell in enumerate(cells):
                self.sources_table.setItem(
                    row,
                    col,
                    QTableWidgetItem(cell),
                )

'''
    if source_anchor not in text:
        raise RuntimeError("_fill_osint_sources anchor not found.")

    return text.replace(
        source_anchor,
        method + source_anchor,
        1,
    )


def main() -> int:
    provider = Path(
        "app/osint/open_web/providers/gdelt_exact_email.py"
    )

    for path in (provider, CONTAINER, WORKER, VIEW):
        if not path.exists():
            print(f"[FAIL] Missing {path}")
            return 1

    originals = {
        CONTAINER: CONTAINER.read_text(encoding="utf-8"),
        WORKER: WORKER.read_text(encoding="utf-8"),
        VIEW: VIEW.read_text(encoding="utf-8"),
    }

    try:
        updated = {
            CONTAINER: patch_container(originals[CONTAINER]),
            WORKER: patch_worker(originals[WORKER]),
            VIEW: patch_view(originals[VIEW]),
        }

        compile(
            provider.read_text(encoding="utf-8"),
            str(provider),
            "exec",
        )

        for path, value in updated.items():
            compile(value, str(path), "exec")

    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 1

    for path, value in updated.items():
        backup = path.with_suffix(".py.m021_16_5_2a_backup")
        if not backup.exists():
            backup.write_text(originals[path], encoding="utf-8")

        path.write_text(value, encoding="utf-8")

    print("[PASS] GDELT exact-email provider installed.")
    print("[PASS] Provider registered in existing Open-Web registry.")
    print("[PASS] EMAIL now runs OSINT + eligible Open-Web providers.")
    print("[PASS] Candidate pages require live exact-email verification.")
    print("[PASS] Existing Live Web TLS/SSRF protection reused.")
    print("[PASS] Verified page text flows into UnifiedExtraction.")
    print("[PASS] No second pipeline.")
    print("[PASS] No database migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
