
"""
OSINT Expansion 05R3c — Recursive Candidate Diagnostic

Read-only diagnostic for the latest OSINT-enriched Case.

It answers:
- which Entity types/values were just persisted;
- which of them are supported by OsintPivotCandidatePolicy;
- which would become DOMAIN/URL/IP/EMAIL/PHONE/USERNAME pivots;
- which finding category / connector created them;
- how many EvidenceEntity links they have.

NO writes.
NO network.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database.session import engine
from app.models.case import Case
from app.models.entity import Entity
from app.models.evidence import Evidence
from app.models.evidence_entity import EvidenceEntity
from app.osint.pivot_candidates import OsintPivotCandidatePolicy


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "storage" / "cache" / "osint_expansion_05r3c"


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


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    print(
        "OSINT Expansion 05R3c — Recursive Candidate Diagnostic",
        flush=True,
    )
    print("=" * 78, flush=True)

    policy = OsintPivotCandidatePolicy()

    with Session(bind=engine, expire_on_commit=False) as session:
        case = session.execute(
            select(Case)
            .order_by(
                Case.updated_at.desc(),
                Case.created_at.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()

        if case is None:
            raise RuntimeError("No Case exists in the database.")

        print(f"Latest Case: {case.id} · {case.title}", flush=True)

        entities = list(
            session.execute(
                select(Entity)
                .where(
                    Entity.case_id == case.id,
                    Entity.deleted_at.is_(None),
                )
                .order_by(Entity.created_at.desc())
                .limit(30)
            ).scalars()
        )

        osint_entities = []

        for entity in entities:
            metadata = parse_json(entity.metadata_json)

            if metadata.get("workflow") != "osint_enrichment":
                continue

            target_type = policy.target_type_for_entity(
                entity.entity_type
            )

            candidate = policy.from_entity(
                entity,
                depth=1,
            )

            link_count = session.scalar(
                select(func.count())
                .select_from(EvidenceEntity)
                .where(
                    EvidenceEntity.entity_id == entity.id
                )
            ) or 0

            evidence_id = metadata.get("evidence_id")
            evidence_info = None

            if evidence_id:
                try:
                    evidence = session.get(
                        Evidence,
                        evidence_id,
                    )
                except Exception:
                    evidence = None

                if evidence is not None:
                    evidence_metadata = parse_json(
                        evidence.metadata_json
                    )
                    finding = evidence_metadata.get("finding") or {}
                    evidence_info = {
                        "id": str(evidence.id),
                        "title": evidence.title,
                        "value": evidence.value,
                        "finding_category": finding.get("category"),
                        "finding_value": finding.get("value"),
                        "finding_url": finding.get("url"),
                        "connector": evidence_metadata.get("connector"),
                        "capability_module": (
                            evidence_metadata.get("capability_module")
                        ),
                    }

            record = {
                "id": str(entity.id),
                "entity_type": enum_text(entity.entity_type),
                "value": entity.value,
                "normalized_value": entity.normalized_value,
                "confidence": float(entity.confidence),
                "supported_by_pivot_policy": (
                    target_type is not None
                ),
                "pivot_target_type": (
                    enum_text(target_type)
                    if target_type is not None
                    else None
                ),
                "candidate_created": (
                    candidate is not None
                ),
                "evidence_links": int(link_count),
                "origin": {
                    "connector": metadata.get("connector"),
                    "finding_category": metadata.get("finding_category"),
                    "finding_source": metadata.get("finding_source"),
                    "finding_url": metadata.get("finding_url"),
                    "origin_target_type": metadata.get(
                        "origin_target_type"
                    ),
                    "origin_target_value": metadata.get(
                        "origin_target_value"
                    ),
                    "discovery_goal": metadata.get("discovery_goal"),
                },
                "evidence": evidence_info,
            }

            osint_entities.append(record)

        print(
            f"Recent OSINT entities inspected: {len(osint_entities)}",
            flush=True,
        )
        print("", flush=True)

        supported = 0
        rejected = 0

        for index, record in enumerate(osint_entities, 1):
            if record["candidate_created"]:
                supported += 1
                verdict = (
                    "PIVOT "
                    f"→ {record['pivot_target_type']}"
                )
            else:
                rejected += 1
                verdict = "REJECTED"

            print(
                f"[{index}] {record['entity_type']}: "
                f"{record['value']}",
                flush=True,
            )
            print(
                f"    verdict={verdict} "
                f"links={record['evidence_links']} "
                f"connector={record['origin']['connector']} "
                f"category={record['origin']['finding_category']}",
                flush=True,
            )

        print("", flush=True)
        print(
            f"supported={supported} rejected={rejected}",
            flush=True,
        )

        report = {
            "case_id": str(case.id),
            "case_title": case.title,
            "entities_inspected": len(osint_entities),
            "supported": supported,
            "rejected": rejected,
            "entities": osint_entities,
        }

    report_path = OUT / "candidate_diagnostic.json"
    report_path.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    print("", flush=True)
    print(f"JSON: {report_path}", flush=True)
    print(
        "OSINT EXPANSION 05R3c CANDIDATE DIAGNOSTIC: PASS",
        flush=True,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
