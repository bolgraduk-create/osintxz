
"""
OSINT Expansion 05R3c2 — Evidence -> Entity Candidate Diagnostic

Robust read-only diagnostic.

Unlike 05R3c, this script does NOT choose the case by Case.updated_at and does
NOT require Entity.metadata_json.workflow to exist.

It:
1. finds the most recently created OSINT Evidence in the whole DB;
2. uses that Evidence.case_id as the target Case;
3. loads recent OSINT Evidence rows for that Case;
4. reconstructs the exact OsintFinding stored in Evidence.metadata_json;
5. calls production OsintFindingPersistenceService._entity_candidates();
6. compares predicted candidates with actual EvidenceEntity links.

NO writes.
NO network.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import engine
from app.models.case import Case
from app.models.entity import Entity
from app.models.evidence import Evidence
from app.models.evidence_entity import EvidenceEntity
from app.models.source import Source
from app.osint.finding_persistence import (
    OsintFindingPersistenceService,
)
from app.osint.result import OsintFinding


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "storage" / "cache" / "osint_expansion_05r3c2"


def parse_json(value: Any) -> dict[str, Any]:
    if not value:
        return {}

    if isinstance(value, dict):
        return value

    try:
        parsed = json.loads(str(value))
    except Exception:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def enum_text(value: Any) -> str:
    return getattr(value, "value", str(value))


def reconstruct_finding(
    evidence: Evidence,
) -> tuple[OsintFinding | None, dict[str, Any]]:
    metadata = parse_json(
        evidence.metadata_json
    )

    finding_data = metadata.get(
        "finding"
    )

    if not isinstance(
        finding_data,
        dict,
    ):
        return None, metadata

    try:
        finding = OsintFinding(
            category=str(
                finding_data.get("category")
                or ""
            ),
            value=str(
                finding_data.get("value")
                or ""
            ),
            confidence=float(
                finding_data.get(
                    "confidence",
                    1.0,
                )
                or 1.0
            ),
            source=(
                str(finding_data["source"])
                if finding_data.get("source")
                is not None
                else None
            ),
            url=(
                str(finding_data["url"])
                if finding_data.get("url")
                is not None
                else None
            ),
            reliability=float(
                finding_data.get(
                    "reliability",
                    1.0,
                )
                or 1.0
            ),
            metadata=(
                finding_data.get(
                    "metadata"
                )
                if isinstance(
                    finding_data.get(
                        "metadata"
                    ),
                    dict,
                )
                else {}
            ),
        )
    except Exception:
        return None, metadata

    return finding, metadata


def main() -> int:
    OUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "OSINT Expansion 05R3c2 — Evidence -> Entity Candidate Diagnostic",
        flush=True,
    )
    print(
        "=" * 82,
        flush=True,
    )

    with Session(
        bind=engine,
        expire_on_commit=False,
    ) as session:
        latest_row = session.execute(
            select(
                Evidence,
                Source,
            )
            .join(
                Source,
                Source.id == Evidence.source_id,
            )
            .where(
                Source.original_path.like(
                    "osint://%"
                )
            )
            .order_by(
                Evidence.created_at.desc()
            )
            .limit(1)
        ).first()

        if latest_row is None:
            raise RuntimeError(
                "No OSINT Evidence exists in the database."
            )

        latest_evidence, latest_source = (
            latest_row
        )

        case_id = (
            latest_evidence.case_id
        )

        case = session.get(
            Case,
            case_id,
        )

        print(
            f"Case from newest OSINT Evidence: "
            f"{case_id} · "
            f"{getattr(case, 'title', None)}",
            flush=True,
        )
        print(
            f"Newest Evidence: {latest_evidence.id} · "
            f"{latest_evidence.title}",
            flush=True,
        )
        print(
            "",
            flush=True,
        )

        rows = session.execute(
            select(
                Evidence,
                Source,
            )
            .join(
                Source,
                Source.id == Evidence.source_id,
            )
            .where(
                Evidence.case_id == case_id,
                Source.original_path.like(
                    "osint://%"
                ),
            )
            .order_by(
                Evidence.created_at.desc()
            )
            .limit(25)
        ).all()

        records = []

        for evidence, source in rows:
            finding, metadata = (
                reconstruct_finding(
                    evidence
                )
            )

            links = list(
                session.execute(
                    select(
                        EvidenceEntity,
                        Entity,
                    )
                    .join(
                        Entity,
                        Entity.id
                        == EvidenceEntity.entity_id,
                    )
                    .where(
                        EvidenceEntity.evidence_id
                        == evidence.id
                    )
                ).all()
            )

            linked_entities = [
                {
                    "id": str(
                        entity.id
                    ),
                    "entity_type": enum_text(
                        entity.entity_type
                    ),
                    "value": entity.value,
                    "normalized_value": (
                        entity.normalized_value
                    ),
                    "confidence": float(
                        entity.confidence
                    ),
                }
                for _link, entity in links
            ]

            predicted = []

            if finding is not None:
                candidates = (
                    OsintFindingPersistenceService
                    ._entity_candidates(
                        finding
                    )
                )

                predicted = [
                    {
                        "entity_type": enum_text(
                            entity_type
                        ),
                        "value": value,
                        "confidence": float(
                            confidence
                        ),
                    }
                    for (
                        entity_type,
                        value,
                        confidence,
                    )
                    in candidates
                ]

            finding_data = (
                metadata.get(
                    "finding"
                )
                if isinstance(
                    metadata.get(
                        "finding"
                    ),
                    dict,
                )
                else {}
            )

            origin = (
                metadata.get(
                    "origin"
                )
                if isinstance(
                    metadata.get(
                        "origin"
                    ),
                    dict,
                )
                else {}
            )

            record = {
                "evidence_id": str(
                    evidence.id
                ),
                "created_at": str(
                    evidence.created_at
                ),
                "source_id": str(
                    source.id
                ),
                "source_name": source.name,
                "source_path": (
                    source.original_path
                ),
                "evidence_type": enum_text(
                    evidence.evidence_type
                ),
                "evidence_title": (
                    evidence.title
                ),
                "evidence_value": (
                    evidence.value
                ),
                "workflow": (
                    metadata.get(
                        "workflow"
                    )
                ),
                "connector": (
                    metadata.get(
                        "connector"
                    )
                ),
                "capability_module": (
                    metadata.get(
                        "capability_module"
                    )
                ),
                "origin": origin,
                "finding": {
                    "category": (
                        finding_data.get(
                            "category"
                        )
                    ),
                    "value": (
                        finding_data.get(
                            "value"
                        )
                    ),
                    "url": (
                        finding_data.get(
                            "url"
                        )
                    ),
                    "source": (
                        finding_data.get(
                            "source"
                        )
                    ),
                    "metadata": (
                        finding_data.get(
                            "metadata"
                        )
                    ),
                },
                "reconstructed": (
                    finding is not None
                ),
                "predicted_entity_candidates": (
                    predicted
                ),
                "actual_linked_entities": (
                    linked_entities
                ),
            }

            records.append(
                record
            )

        print(
            f"Recent OSINT Evidence inspected: "
            f"{len(records)}",
            flush=True,
        )
        print(
            "",
            flush=True,
        )

        for index, record in enumerate(
            records,
            1,
        ):
            finding = record[
                "finding"
            ]
            predicted = record[
                "predicted_entity_candidates"
            ]
            linked = record[
                "actual_linked_entities"
            ]

            print(
                f"[{index}] "
                f"{record['connector']} · "
                f"category={finding['category']!r}",
                flush=True,
            )
            print(
                f"    value={finding['value']!r}",
                flush=True,
            )
            print(
                f"    url={finding['url']!r}",
                flush=True,
            )
            print(
                f"    predicted_candidates="
                f"{len(predicted)} "
                f"actual_entity_links="
                f"{len(linked)}",
                flush=True,
            )

            for candidate in (
                predicted[:8]
            ):
                print(
                    "      predict -> "
                    f"{candidate['entity_type']}: "
                    f"{candidate['value']}",
                    flush=True,
                )

            for entity in (
                linked[:8]
            ):
                print(
                    "      linked  -> "
                    f"{entity['entity_type']}: "
                    f"{entity['value']}",
                    flush=True,
                )

        empty_predictions = sum(
            1
            for item in records
            if not item[
                "predicted_entity_candidates"
            ]
        )

        predicted_but_unlinked = sum(
            1
            for item in records
            if (
                item[
                    "predicted_entity_candidates"
                ]
                and not item[
                    "actual_linked_entities"
                ]
            )
        )

        linked_count = sum(
            len(
                item[
                    "actual_linked_entities"
                ]
            )
            for item in records
        )

        summary = {
            "evidence_inspected": len(
                records
            ),
            "empty_predictions": (
                empty_predictions
            ),
            "predicted_but_unlinked": (
                predicted_but_unlinked
            ),
            "actual_linked_entities": (
                linked_count
            ),
        }

        print(
            "",
            flush=True,
        )
        print(
            "SUMMARY",
            flush=True,
        )
        print(
            json.dumps(
                summary,
                ensure_ascii=False,
            ),
            flush=True,
        )

        report = {
            "case_id": str(
                case_id
            ),
            "case_title": getattr(
                case,
                "title",
                None,
            ),
            "latest_evidence_id": str(
                latest_evidence.id
            ),
            "summary": summary,
            "records": records,
        }

    report_path = (
        OUT
        / "evidence_candidate_diagnostic.json"
    )

    report_path.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    print(
        "",
        flush=True,
    )
    print(
        f"JSON: {report_path}",
        flush=True,
    )
    print(
        "OSINT EXPANSION 05R3c2 EVIDENCE/CANDIDATE DIAGNOSTIC: PASS",
        flush=True,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
