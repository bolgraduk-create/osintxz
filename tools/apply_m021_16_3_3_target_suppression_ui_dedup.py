from __future__ import annotations

from pathlib import Path

BRIDGE = Path("app/osint/open_web/extraction_bridge.py")
VIEW = Path("app/interface/desktop/views/workspace/investigation_search_view.py")


def patch_bridge(text: str) -> str:
    if "M021.16.3.3 target suppression" in text:
        return text

    old_call = '''        candidates, skipped_quality = self._filter_quality_candidates(
            candidates,
            document=document,
        )
'''
    new_call = '''        candidates, skipped_quality = self._filter_quality_candidates(
            candidates,
            document=document,
            query=query,
        )
'''
    if old_call not in text:
        raise RuntimeError("quality-filter call anchor not found")
    text = text.replace(old_call, new_call, 1)

    old_sig = '''    def _filter_quality_candidates(
        cls,
        candidates: Iterable[ExtractionCandidate],
        *,
        document: OpenWebDocument,
    ) -> tuple[list[ExtractionCandidate], int]:
'''
    new_sig = '''    def _filter_quality_candidates(
        cls,
        candidates: Iterable[ExtractionCandidate],
        *,
        document: OpenWebDocument,
        query: OpenWebQuery | None = None,
    ) -> tuple[list[ExtractionCandidate], int]:
'''
    if old_sig not in text:
        raise RuntimeError("quality-filter signature anchor not found")
    text = text.replace(old_sig, new_sig, 1)

    old_local = '''        document_url = cls._canonical_url(document.url)

        for candidate in candidates:
            if candidate.entity_type is EntityType.URL:
                candidate_url = cls._canonical_url(
                    candidate.normalized_value or candidate.value
                )
                if document_url and candidate_url == document_url:
                    skipped += 1
                    continue
'''
    new_local = '''        document_url = cls._canonical_url(document.url)

        # M021.16.3.3 target suppression
        query_url = ""
        if (
            query is not None
            and query.target_type.value == "url"
        ):
            query_url = cls._canonical_url(query.value)

        for candidate in candidates:
            if candidate.entity_type is EntityType.URL:
                candidate_url = cls._canonical_url(
                    candidate.normalized_value or candidate.value
                )
                if (
                    candidate_url
                    and candidate_url in {
                        document_url,
                        query_url,
                    }
                ):
                    skipped += 1
                    continue
'''
    if old_local not in text:
        raise RuntimeError("URL suppression anchor not found")
    return text.replace(old_local, new_local, 1)


def patch_view(text: str) -> str:
    if "M021.16.3.3 unique entity presentation" in text:
        return text

    start = text.find("    def _fill_entities(self, result) -> None:")
    end = text.find("    def _fill_sources(self, result) -> None:")
    if start < 0 or end < 0 or end <= start:
        raise RuntimeError("_fill_entities block not found")

    new_block = '''    def _fill_entities(self, result) -> None:
        # M021.16.3.3 unique entity presentation
        grouped = {}

        for persistence in result.persistence:
            for persisted in persistence.persisted:
                evidence = getattr(persisted, "evidence", None)
                evidence_id = getattr(evidence, "id", None)

                for entity in persisted.entities:
                    entity_type = getattr(entity, "entity_type", "")
                    type_value = getattr(
                        entity_type,
                        "value",
                        str(entity_type),
                    )
                    value = (
                        getattr(entity, "normalized_value", None)
                        or getattr(entity, "value", "")
                    )

                    key = (
                        str(type_value).casefold(),
                        str(value).casefold(),
                    )

                    confidence = getattr(entity, "confidence", None)
                    confidence_value = (
                        float(confidence)
                        if isinstance(confidence, (int, float))
                        else None
                    )

                    item = grouped.setdefault(
                        key,
                        {
                            "type": str(type_value),
                            "value": str(value),
                            "confidence": confidence_value,
                            "sources": set(),
                            "evidence_ids": set(),
                        },
                    )

                    if (
                        confidence_value is not None
                        and (
                            item["confidence"] is None
                            or confidence_value > item["confidence"]
                        )
                    ):
                        item["confidence"] = confidence_value

                    target_value = getattr(
                        persistence,
                        "target_value",
                        None,
                    )
                    if target_value:
                        item["sources"].add(str(target_value))

                    if evidence_id is not None:
                        item["evidence_ids"].add(str(evidence_id))

        for item in sorted(
            grouped.values(),
            key=lambda value: (
                value["type"].casefold(),
                value["value"].casefold(),
            ),
        ):
            confidence_text = (
                f"{item['confidence']:.2f}"
                if item["confidence"] is not None
                else "—"
            )

            evidence_ids = sorted(item["evidence_ids"])
            evidence_text = (
                evidence_ids[0]
                if len(evidence_ids) == 1
                else (
                    f"{len(evidence_ids)} evidence"
                    if evidence_ids
                    else "—"
                )
            )

            source_text = ", ".join(
                sorted(item["sources"])
            ) or "—"

            row = self.entities_table.rowCount()
            self.entities_table.insertRow(row)

            cells = [
                item["type"],
                item["value"],
                confidence_text,
                source_text,
                evidence_text,
            ]

            for col, cell in enumerate(cells):
                self.entities_table.setItem(
                    row,
                    col,
                    QTableWidgetItem(str(cell)),
                )

'''

    return text[:start] + new_block + text[end:]


def main() -> int:
    for path in (BRIDGE, VIEW):
        if not path.is_file():
            print(f"[FAIL] Missing {path}")
            return 1

    originals = {
        BRIDGE: BRIDGE.read_text(encoding="utf-8"),
        VIEW: VIEW.read_text(encoding="utf-8"),
    }

    try:
        updated = {
            BRIDGE: patch_bridge(originals[BRIDGE]),
            VIEW: patch_view(originals[VIEW]),
        }
        for path, value in updated.items():
            compile(value, str(path), "exec")
    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 1

    for path, value in updated.items():
        backup = path.with_suffix(".py.m021_16_3_3_backup")
        if not backup.exists():
            backup.write_text(originals[path], encoding="utf-8")
        path.write_text(value, encoding="utf-8")

    print("[PASS] Query URL suppression added.")
    print("[PASS] Search UI renders unique normalized entities.")
    print("[PASS] Evidence aggregation added.")
    print("[PASS] No DB migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
