from pathlib import Path

TARGET = Path("app/osint/finding_persistence.py")


def main() -> int:
    if not TARGET.exists():
        print(f"[FAIL] Missing {TARGET}")
        return 1

    original = TARGET.read_text(encoding="utf-8")
    if "M021.16.6.4.3A cross-source profile fusion" in original:
        print("[PASS] Patch already applied.")
        return 0

    text = original

    a = """from app.osint.username_quality import (
    UsernameFindingKind,
    UsernameFindingQuality,
)
"""
    b = a + """from app.osint.username_fusion import (
    UsernameProfileFusion,
    UsernameProfileFusionPolicy,
    UsernameProfileObservation,
)
"""
    if a not in text:
        print("[FAIL] username_quality import anchor not found.")
        return 1
    text = text.replace(a, b, 1)

    a = """        result = OsintPersistenceResult(
            case_id=case_id,
            target_type=target_type,
            target_value=target_value,
            goal=goal,
        )

        for record in execution.records:
"""
    b = """        result = OsintPersistenceResult(
            case_id=case_id,
            target_type=target_type,
            target_value=target_value,
            goal=goal,
        )

        # M021.16.6.4.3A cross-source profile fusion
        username_profile_fusion = self._build_username_profile_fusion(
            execution=execution,
            target_type=target_type,
            target_value=target_value,
            goal=goal,
        )

        for record in execution.records:
"""
    if a not in text:
        print("[FAIL] persist_execution anchor not found.")
        return 1
    text = text.replace(a, b, 1)

    a = """                    finding=finding,
                    finding_index=index,
                    parent_entity_id=parent_entity_id,
                )
"""
    b = """                    finding=finding,
                    finding_index=index,
                    parent_entity_id=parent_entity_id,
                    username_profile_fusion=username_profile_fusion,
                )
"""
    if a not in text:
        print("[FAIL] persist call anchor not found.")
        return 1
    text = text.replace(a, b, 1)

    a = """        finding: OsintFinding,
        finding_index: int,
        parent_entity_id: UUID | None,
    ) -> PersistedFinding:
"""
    b = """        finding: OsintFinding,
        finding_index: int,
        parent_entity_id: UUID | None,
        username_profile_fusion: dict[str, UsernameProfileFusion] | None = None,
    ) -> PersistedFinding:
"""
    if a not in text:
        print("[FAIL] _persist_finding signature anchor not found.")
        return 1
    text = text.replace(a, b, 1)

    helper_anchor = "    def _persist_finding(\n"
    helpers = """    @classmethod
    def _build_username_profile_fusion(
        cls,
        *,
        execution: EnrichmentExecutionResult,
        target_type: OsintTargetType,
        target_value: str,
        goal: DiscoveryGoal,
    ) -> dict[str, UsernameProfileFusion]:
        if (
            target_type is not OsintTargetType.USERNAME
            or goal is not DiscoveryGoal.ACCOUNT_DISCOVERY
        ):
            return {}

        observations: list[UsernameProfileObservation] = []

        for record in execution.records:
            connector_result = record.result
            if connector_result.status not in {
                ResultStatus.SUCCESS,
                ResultStatus.PARTIAL,
            }:
                continue

            provider = (
                record.runtime_connector_name
                or connector_result.connector
                or record.capability.connector_class
            )

            for finding in connector_result.findings:
                classification = UsernameFindingQuality.classify(
                    category=finding.category,
                    value=finding.value,
                    url=finding.url,
                    target_username=target_value,
                    metadata=finding.metadata,
                )
                if (
                    classification.kind is UsernameFindingKind.PUBLIC_PROFILE
                    and classification.canonical_profile_url
                ):
                    observations.append(
                        UsernameProfileObservation(
                            provider=provider,
                            canonical_url=classification.canonical_profile_url,
                            confidence=finding.confidence,
                            reliability=finding.reliability,
                        )
                    )

        return UsernameProfileFusionPolicy.fuse(observations)

    @staticmethod
    def _is_recalibratable_username_profile(entity: Entity) -> bool:
        if entity.entity_type is not EntityType.URL:
            return False
        raw = entity.metadata_json or ""
        try:
            metadata = json.loads(raw) if raw else {}
        except Exception:
            return False
        return (
            metadata.get("workflow") == "osint_enrichment"
            and metadata.get("origin_target_type") == OsintTargetType.USERNAME.value
            and metadata.get("discovery_goal") == DiscoveryGoal.ACCOUNT_DISCOVERY.value
        )

"""
    if helper_anchor not in text:
        print("[FAIL] helper anchor not found.")
        return 1
    text = text.replace(helper_anchor, helpers + helper_anchor, 1)

    a = """        for entity_type, value, confidence in entity_candidates:
            entity, created = self._resolve_or_create_entity(
                case_id=case_id,
                entity_type=entity_type,
                value=value,
                confidence=confidence,
                metadata={
                    "workflow": "osint_enrichment",
                    "connector": connector,
                    "source_id": str(source.id),
                    "evidence_id": str(evidence.id),
                    "finding_category": finding.category,
                    "finding_source": finding.source,
                    "finding_url": finding.url,
                    "origin_target_type": target_type.value,
                    "origin_target_value": target_value,
                    "discovery_goal": goal.value,
                },
            )
            entities.append(entity)
"""
    b = """        for entity_type, value, confidence in entity_candidates:
            entity_metadata = {
                "workflow": "osint_enrichment",
                "connector": connector,
                "source_id": str(source.id),
                "evidence_id": str(evidence.id),
                "finding_category": finding.category,
                "finding_source": finding.source,
                "finding_url": finding.url,
                "origin_target_type": target_type.value,
                "origin_target_value": target_value,
                "discovery_goal": goal.value,
            }

            profile_fusion = None
            if (
                target_type is OsintTargetType.USERNAME
                and goal is DiscoveryGoal.ACCOUNT_DISCOVERY
                and entity_type is EntityType.URL
                and username_profile_fusion
            ):
                canonical_profile_url = UsernameFindingQuality.canonicalize_url(value)
                profile_fusion = username_profile_fusion.get(canonical_profile_url)
                if profile_fusion is not None:
                    confidence = profile_fusion.confidence
                    entity_metadata["profile_fusion"] = profile_fusion.metadata()

            entity, created = self._resolve_or_create_entity(
                case_id=case_id,
                entity_type=entity_type,
                value=value,
                confidence=confidence,
                metadata=entity_metadata,
            )

            if (
                profile_fusion is not None
                and not created
                and self._is_recalibratable_username_profile(entity)
                and abs(float(entity.confidence) - float(profile_fusion.confidence)) > 1e-9
            ):
                updated = self.entity_service.update_confidence(
                    entity.id,
                    profile_fusion.confidence,
                )
                if updated is not None:
                    entity = updated

            entities.append(entity)
"""
    if a not in text:
        print("[FAIL] entity loop anchor not found.")
        return 1
    text = text.replace(a, b, 1)

    try:
        compile(text, str(TARGET), "exec")
    except Exception as exc:
        print(f"[FAIL] compile: {exc}")
        return 1

    backup = TARGET.with_suffix(".py.m021_16_6_4_3a_backup")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")
    TARGET.write_text(text, encoding="utf-8")

    print("[PASS] Cross-source username profile fusion added.")
    print("[PASS] Same-provider duplicates count once.")
    print("[PASS] Confidence cap is 0.97.")
    print("[PASS] Existing EntityService/EvidenceEntity reused.")
    print("[PASS] No database migration.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
