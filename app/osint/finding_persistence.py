"""
M021.3 — OSINT Findings Persistence + Provenance.

Persists successful/partial OSINT findings into the existing investigation
domain model:

    OsintFinding
        -> Source(SourceType.OSINT)
        -> Evidence
        -> Entity (when the finding exposes a supported identifier)
        -> EvidenceEntity

No new database tables are introduced.
No recursive pivots or inferred ownership relationships are created here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from ipaddress import ip_address
import json
import re
from typing import Any
from uuid import UUID

from app.models.entity import Entity, EntityType
from app.models.evidence import Evidence, EvidenceType
from app.models.source import Source, SourceType
from app.osint.capabilities import DiscoveryGoal
from app.osint.enrichment_execution import (
    EnrichmentExecutionResult,
    NewEntityBudget,
)
from app.osint.models import OsintTargetType
from app.osint.result import OsintFinding, ResultStatus
from app.osint.username_quality import (
    UsernameFindingKind,
    UsernameFindingQuality,
)
from app.osint.username_fusion import (
    UsernameProfileFusion,
    UsernameProfileFusionPolicy,
    UsernameProfileObservation,
)
from app.services.entity_service import EntityService
from app.services.evidence_link_service import EvidenceLinkService
from app.services.evidence_service import EvidenceService
from app.services.source_service import SourceService


_CERTIFICATE_EMAIL_LOCAL_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+$"
)



@dataclass(frozen=True, slots=True)
class PersistedFinding:
    connector: str
    finding_index: int
    source: Source
    evidence: Evidence
    entities: tuple[Entity, ...]
    source_created: bool
    evidence_created: bool
    entities_created: int
    links_created: int


@dataclass(slots=True)
class OsintPersistenceResult:
    case_id: UUID
    target_type: OsintTargetType
    target_value: str
    goal: DiscoveryGoal
    persisted: list[PersistedFinding] = field(default_factory=list)
    skipped_results: int = 0
    skipped_findings: int = 0

    @property
    def persisted_findings(self) -> int:
        return len(self.persisted)

    @property
    def sources_created(self) -> int:
        return sum(item.source_created for item in self.persisted)

    @property
    def evidences_created(self) -> int:
        return sum(item.evidence_created for item in self.persisted)

    @property
    def entities_created(self) -> int:
        return sum(item.entities_created for item in self.persisted)

    @property
    def links_created(self) -> int:
        return sum(item.links_created for item in self.persisted)


class OsintFindingPersistenceService:
    """
    Persistence boundary between OSINT connector results and investigation data.

    Dependencies are the existing domain services; this service does not write
    database models directly except for attaching metadata_json to a newly
    created Evidence object before flushing through the existing repository
    session.
    """

    def __init__(
        self,
        *,
        source_service: SourceService,
        evidence_service: EvidenceService,
        entity_service: EntityService,
        evidence_link_service: EvidenceLinkService,
    ) -> None:
        self.source_service = source_service
        self.evidence_service = evidence_service
        self.entity_service = entity_service
        self.evidence_link_service = evidence_link_service

    def persist_execution(
        self,
        *,
        case_id: UUID,
        target_type: OsintTargetType,
        target_value: str,
        goal: DiscoveryGoal,
        execution: EnrichmentExecutionResult,
        parent_entity_id: UUID | None = None,
    ) -> OsintPersistenceResult:
        result = OsintPersistenceResult(
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
            connector_result = record.result

            if connector_result.status not in {
                ResultStatus.SUCCESS,
                ResultStatus.PARTIAL,
            }:
                result.skipped_results += 1
                continue

            for index, finding in enumerate(connector_result.findings):
                if not self._is_persistable_finding(finding):
                    result.skipped_findings += 1
                    continue

                persisted = self._persist_finding(
                    case_id=case_id,
                    target_type=target_type,
                    target_value=target_value,
                    goal=goal,
                    connector=connector_result.connector,
                    capability_module=record.capability.module,
                    finding=finding,
                    finding_index=index,
                    parent_entity_id=parent_entity_id,
                    username_profile_fusion=username_profile_fusion,
                    new_entity_budget=getattr(
                        execution,
                        "entity_budget",
                        None,
                    ),
                )
                result.persisted.append(persisted)

        return result


    def persist_findings(
        self,
        *,
        case_id: UUID,
        target_type: OsintTargetType,
        target_value: str,
        goal: DiscoveryGoal,
        connector: str,
        capability_module: str,
        findings: list[OsintFinding] | tuple[OsintFinding, ...],
        parent_entity_id: UUID | None = None,
    ) -> OsintPersistenceResult:
        """Persist standard OsintFinding objects through the M021.3 path.

        This generic entry point is used by non-connector producers such as
        Open-Web extraction. It reuses _persist_finding(), so provenance and
        idempotency remain identical to connector execution persistence.
        """
        result = OsintPersistenceResult(
            case_id=case_id,
            target_type=target_type,
            target_value=target_value,
            goal=goal,
        )

        for index, finding in enumerate(findings):
            if not self._is_persistable_finding(finding):
                result.skipped_findings += 1
                continue

            result.persisted.append(
                self._persist_finding(
                    case_id=case_id,
                    target_type=target_type,
                    target_value=target_value,
                    goal=goal,
                    connector=connector,
                    capability_module=capability_module,
                    finding=finding,
                    finding_index=index,
                    parent_entity_id=parent_entity_id,
                )
            )

        return result

    @classmethod
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

    def _persist_finding(
        self,
        *,
        case_id: UUID,
        target_type: OsintTargetType,
        target_value: str,
        goal: DiscoveryGoal,
        connector: str,
        capability_module: str,
        finding: OsintFinding,
        finding_index: int,
        parent_entity_id: UUID | None,
        username_profile_fusion: dict[str, UsernameProfileFusion] | None = None,
        new_entity_budget: NewEntityBudget | None = None,
    ) -> PersistedFinding:
        source_key = self._source_key(
            connector=connector,
            target_type=target_type,
            target_value=target_value,
            goal=goal,
        )
        source, source_created = self._ensure_source(
            case_id=case_id,
            connector=connector,
            source_key=source_key,
            target_type=target_type,
            target_value=target_value,
            goal=goal,
        )

        evidence_key = self._evidence_key(
            source_key=source_key,
            finding=finding,
        )
        evidence, evidence_created = self._ensure_evidence(
            case_id=case_id,
            source=source,
            connector=connector,
            capability_module=capability_module,
            finding=finding,
            finding_index=finding_index,
            evidence_key=evidence_key,
            target_type=target_type,
            target_value=target_value,
            goal=goal,
            parent_entity_id=parent_entity_id,
        )

        entities: list[Entity] = []
        created_count = 0
        links_created = 0

        entity_candidates = self._entity_candidates(finding)

        # M021.16.6.4.2 username quality gate
        if (
            target_type is OsintTargetType.USERNAME
            and goal is DiscoveryGoal.ACCOUNT_DISCOVERY
        ):
            entity_candidates = self._username_quality_candidates(
                finding=finding,
                target_value=target_value,
                candidates=entity_candidates,
            )

        # M021.16.3.4 Open-Web provenance suppression:
        # finding.url is the page/evidence provenance in Open-Web extraction.
        # It must stay in Evidence metadata, but must not become a discovered
        # URL Entity merely because persistence exposes provenance URLs.
        if connector.strip().casefold().startswith("open_web:"):
            entity_candidates = tuple(
                candidate
                for candidate in entity_candidates
                if not self._is_open_web_provenance_url_candidate(
                    entity_type=candidate[0],
                    value=candidate[1],
                    finding=finding,
                    target_type=target_type,
                    target_value=target_value,
                )
            )

        for entity_type, value, confidence in entity_candidates:
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

            existing_entity = None

            if (
                new_entity_budget is not None
                and new_entity_budget.exhausted
            ):
                existing_entity = (
                    self._find_existing_entity(
                        case_id=case_id,
                        entity_type=entity_type,
                        value=value,
                    )
                )

                if existing_entity is None:
                    continue

            if existing_entity is not None:
                entity = existing_entity
                created = False
            else:
                entity, created = self._resolve_or_create_entity(
                    case_id=case_id,
                    entity_type=entity_type,
                    value=value,
                    confidence=confidence,
                    metadata=entity_metadata,
                )

                if (
                    created
                    and new_entity_budget is not None
                ):
                    new_entity_budget.consume(1)

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
            created_count += int(created)

            _, link_created = self.evidence_link_service.ensure_link(
                evidence_id=evidence.id,
                entity_id=entity.id,
            )
            links_created += int(link_created)

        # Preserve the explicit parent pivot provenance as a link to the same
        # Evidence. This means "this evidence was discovered while enriching
        # this entity", not "the discovered entity belongs to the parent".
        if parent_entity_id is not None:
            _, link_created = self.evidence_link_service.ensure_link(
                evidence_id=evidence.id,
                entity_id=parent_entity_id,
            )
            links_created += int(link_created)

        return PersistedFinding(
            connector=connector,
            finding_index=finding_index,
            source=source,
            evidence=evidence,
            entities=tuple(entities),
            source_created=source_created,
            evidence_created=evidence_created,
            entities_created=created_count,
            links_created=links_created,
        )

    def _ensure_source(
        self,
        *,
        case_id: UUID,
        connector: str,
        source_key: str,
        target_type: OsintTargetType,
        target_value: str,
        goal: DiscoveryGoal,
    ) -> tuple[Source, bool]:
        path = f"osint://{source_key}"

        for source in self.source_service.repository.get_by_case(case_id):
            if (
                source.source_type is SourceType.OSINT
                and (source.original_path or "") == path
            ):
                return source, False

        source = self.source_service.create_source(
            case_id=case_id,
            name=f"OSINT · {connector}",
            source_type=SourceType.OSINT,
            path=path,
            description=(
                f"OSINT enrichment source. connector={connector}; "
                f"target_type={target_type.value}; "
                f"target_value={target_value}; goal={goal.value}; "
                f"provenance_key={source_key}"
            ),
        )
        return source, True

    def _ensure_evidence(
        self,
        *,
        case_id: UUID,
        source: Source,
        connector: str,
        capability_module: str,
        finding: OsintFinding,
        finding_index: int,
        evidence_key: str,
        target_type: OsintTargetType,
        target_value: str,
        goal: DiscoveryGoal,
        parent_entity_id: UUID | None,
    ) -> tuple[Evidence, bool]:
        marker = f"osint_evidence_key={evidence_key}"

        for evidence in self.evidence_service.repository.get_by_source(source.id):
            if marker in (evidence.description or ""):
                return evidence, False

        evidence_type = self._evidence_type(finding)
        value = self._evidence_value(finding)

        evidence = self.evidence_service.create_evidence(
            case_id=case_id,
            source_id=source.id,
            evidence_type=evidence_type,
            title=self._evidence_title(connector, finding),
            value=value[:1024] if value else None,
            description=(
                f"{marker}; connector={connector}; "
                f"finding_category={finding.category}; "
                f"origin_target_type={target_type.value}; "
                f"origin_target_value={target_value}; "
                f"goal={goal.value}"
            ),
        )

        metadata = {
            "workflow": "osint_enrichment",
            "provenance_version": 1,
            "evidence_key": evidence_key,
            "connector": connector,
            "capability_module": capability_module,
            "finding_index": finding_index,
            "finding": {
                "category": finding.category,
                "value": finding.value,
                "source": finding.source,
                "url": finding.url,
                "confidence": finding.confidence,
                "reliability": finding.reliability,
                "metadata": finding.metadata,
            },
            "origin": {
                "target_type": target_type.value,
                "target_value": target_value,
                "goal": goal.value,
                "parent_entity_id": (
                    str(parent_entity_id)
                    if parent_entity_id is not None
                    else None
                ),
            },
        }
        evidence.metadata_json = json.dumps(
            metadata,
            ensure_ascii=False,
            default=str,
            sort_keys=True,
        )

        repository = self.evidence_service.repository
        session = getattr(repository, "session", None)
        if session is not None:
            session.flush()

        return evidence, True

    def _find_existing_entity(
        self,
        *,
        case_id: UUID,
        entity_type: EntityType,
        value: str,
    ) -> Entity | None:
        """
        Resolve an already-persisted Entity without creating anything.

        This is used after the recursive new-entity budget is exhausted so
        evidence can still be linked to known entities without allowing a new
        Entity to slip past the hard budget.
        """

        normalizer = getattr(
            self.entity_service,
            "normalizer",
            None,
        )

        repository = getattr(
            self.entity_service,
            "repository",
            None,
        )

        if (
            normalizer is None
            or repository is None
        ):
            return None

        try:
            normalized = normalizer.normalize(
                entity_type,
                value,
            )

            return repository.find_in_case(
                case_id=case_id,
                entity_type=entity_type,
                normalized_value=normalized,
            )

        except Exception:
            return None

    def _resolve_or_create_entity(
        self,
        *,
        case_id: UUID,
        entity_type: EntityType,
        value: str,
        confidence: float,
        metadata: dict[str, Any],
    ) -> tuple[Entity, bool]:
        method = getattr(
            self.entity_service,
            "resolve_or_create_entity",
            None,
        )
        metadata_json = json.dumps(
            metadata,
            ensure_ascii=False,
            default=str,
            sort_keys=True,
        )

        if callable(method):
            return method(
                case_id=case_id,
                entity_type=entity_type,
                value=value,
                confidence=confidence,
                metadata_json=metadata_json,
                description="Entity discovered through OSINT enrichment.",
            )

        # Backward-compatible fallback for older EntityService snapshots.
        normalizer = self.entity_service.normalizer
        normalized = normalizer.normalize(entity_type, value)
        existing = self.entity_service.repository.find_in_case(
            case_id=case_id,
            entity_type=entity_type,
            normalized_value=normalized,
        )
        if existing is not None:
            return existing, False

        entity = self.entity_service.create_entity(
            case_id=case_id,
            entity_type=entity_type,
            value=value,
            normalized_value=normalized,
            confidence=confidence,
            metadata_json=metadata_json,
            description="Entity discovered through OSINT enrichment.",
        )
        return entity, True

    @classmethod
    def _is_open_web_provenance_url_candidate(
        cls,
        *,
        entity_type: EntityType,
        value: str,
        finding: OsintFinding,
        target_type: OsintTargetType,
        target_value: str,
    ) -> bool:
        if entity_type is not EntityType.URL:
            return False

        candidate = cls._canonical_url_for_comparison(value)
        if not candidate:
            return False

        provenance = cls._canonical_url_for_comparison(
            finding.url or ""
        )

        if provenance and candidate == provenance:
            # Preserve a URL finding's own value when it is genuinely the
            # extracted identifier. Only suppress the extra candidate that
            # exists solely because finding.url is provenance.
            finding_category = (
                finding.category or ""
            ).strip().casefold()
            finding_value = cls._canonical_url_for_comparison(
                finding.value or ""
            )

            if (
                finding_category in {
                    "url",
                    "archived_url",
                    "public_url",
                    "link",
                }
                and finding_value
                and candidate == finding_value
                and candidate != cls._canonical_url_for_comparison(
                    target_value
                    if target_type is OsintTargetType.URL
                    else ""
                )
            ):
                return False

            return True

        if target_type is OsintTargetType.URL:
            target = cls._canonical_url_for_comparison(
                target_value
            )
            if target and candidate == target:
                return True

        return False

    @staticmethod
    def _canonical_url_for_comparison(
        value: str,
    ) -> str:
        from urllib.parse import urlsplit, urlunsplit

        raw = value.strip()
        if not raw:
            return ""

        try:
            parsed = urlsplit(raw)
        except ValueError:
            return raw.casefold().rstrip("/")

        scheme = parsed.scheme.casefold()
        host = (parsed.hostname or "").casefold().rstrip(".")

        if not scheme or not host:
            return raw.casefold().rstrip("/")

        port = parsed.port
        netloc = host

        if port and not (
            (scheme == "http" and port == 80)
            or (scheme == "https" and port == 443)
        ):
            netloc = f"{host}:{port}"

        path = parsed.path or "/"
        if path != "/":
            path = path.rstrip("/")

        return urlunsplit(
            (
                scheme,
                netloc,
                path,
                parsed.query,
                "",
            )
        )

    @classmethod
    def _username_quality_candidates(
        cls,
        *,
        finding: OsintFinding,
        target_value: str,
        candidates: tuple[tuple[EntityType, str, float], ...],
    ) -> tuple[tuple[EntityType, str, float], ...]:
        classification = UsernameFindingQuality.classify(
            category=finding.category,
            value=finding.value,
            url=finding.url,
            target_username=target_value,
            metadata=finding.metadata,
        )

        filtered: list[tuple[EntityType, str, float]] = []

        for entity_type, value, confidence in candidates:
            if entity_type is EntityType.ACCOUNT:
                continue

            if entity_type is EntityType.URL:
                if classification.kind is not UsernameFindingKind.PUBLIC_PROFILE:
                    continue

                canonical = (
                    classification.canonical_profile_url
                    or UsernameFindingQuality.canonicalize_url(value)
                )

                if not canonical:
                    continue

                filtered.append((EntityType.URL, canonical, confidence))
                continue

            filtered.append((entity_type, value, confidence))

        unique: list[tuple[EntityType, str, float]] = []
        seen: set[tuple[EntityType, str]] = set()

        for item in filtered:
            key = (item[0], item[1].strip().casefold())
            if not key[1] or key in seen:
                continue

            seen.add(key)
            unique.append(item)

        return tuple(unique)

    @staticmethod
    def _certificate_domain_candidate(
        value: str,
    ) -> str | None:
        """
        Return a conservative canonical domain extracted from a certificate
        subject/SAN value.

        Certificate text is untrusted OSINT evidence. Only a syntactically
        valid DNS name is allowed to become a DOMAIN Entity. Wildcard SANs are
        reduced to their base DNS name (``*.example.com`` -> ``example.com``).
        Arbitrary certificate/common-name text never becomes a pivot.
        """

        text = str(value or "").strip().rstrip(".")

        if text.startswith("*."):
            text = text[2:]

        if (
            not text
            or len(text) > 253
            or "." not in text
            or "@" in text
            or "://" in text
            or any(character.isspace() for character in text)
        ):
            return None

        try:
            canonical = (
                text
                .encode("idna")
                .decode("ascii")
                .casefold()
            )
        except UnicodeError:
            return None

        labels = canonical.split(".")

        if len(labels) < 2:
            return None

        for label in labels:
            if (
                not label
                or len(label) > 63
                or label.startswith("-")
                or label.endswith("-")
                or not all(
                    character.isalnum()
                    or character == "-"
                    for character in label
                )
            ):
                return None

        # A purely numeric TLD is not a public DNS hostname and is especially
        # useful to reject accidental certificate text/serial fragments.
        if labels[-1].isdigit():
            return None

        return canonical

    @classmethod
    def _certificate_email_candidate(
        cls,
        value: str,
    ) -> str | None:
        """
        Return an email address only when the whole certificate value is a
        conservative syntactic email identifier.
        """

        text = str(value or "").strip()

        if (
            not text
            or len(text) > 320
            or text.count("@") != 1
            or any(character.isspace() for character in text)
        ):
            return None

        local, domain = text.rsplit("@", 1)

        if (
            not local
            or len(local) > 64
            or local.startswith(".")
            or local.endswith(".")
            or ".." in local
            or _CERTIFICATE_EMAIL_LOCAL_RE.fullmatch(local)
            is None
        ):
            return None

        canonical_domain = cls._certificate_domain_candidate(
            domain
        )

        if canonical_domain is None:
            return None

        return f"{local}@{canonical_domain}"

    @classmethod
    def _certificate_identifier_candidates(
        cls,
        value: str,
        confidence: float,
    ) -> tuple[tuple[EntityType, str, float], ...]:
        """
        Convert certificate SAN/common-name findings into first-class
        identifiers only when the COMPLETE value is syntactically safe.

        Supported:
        - DNS names / wildcard DNS names -> DOMAIN
        - email identifiers -> EMAIL

        Unsupported certificate text remains Evidence only.
        """

        candidates: list[
            tuple[
                EntityType,
                str,
                float,
            ]
        ] = []

        # crt.sh normally emits one SAN per finding, but accepting line-separated
        # values makes this boundary robust to other certificate connectors.
        parts = [
            part.strip()
            for part in str(value or "").replace(
                "\r",
                "\n",
            ).split("\n")
            if part.strip()
        ]

        for part in parts:
            email = cls._certificate_email_candidate(
                part
            )

            if email is not None:
                candidates.append(
                    (
                        EntityType.EMAIL,
                        email,
                        confidence,
                    )
                )
                continue

            domain = cls._certificate_domain_candidate(
                part
            )

            if domain is not None:
                candidates.append(
                    (
                        EntityType.DOMAIN,
                        domain,
                        confidence,
                    )
                )

        unique: list[
            tuple[
                EntityType,
                str,
                float,
            ]
        ] = []
        seen: set[
            tuple[
                EntityType,
                str,
            ]
        ] = set()

        for item in candidates:
            key = (
                item[0],
                item[1].casefold(),
            )

            if key in seen:
                continue

            seen.add(key)
            unique.append(item)

        return tuple(unique)

    @staticmethod
    def _metadata_ip_candidates(
        metadata: dict[str, Any] | None,
    ) -> tuple[str, ...]:
        """
        Extract canonical IP addresses from discovery-tool metadata.

        Current bounded discovery connectors expose IPs through fields such as
        ``host_ip``, ``ip``, ``a`` and ``aaaa``. Only syntactically valid IP
        addresses are accepted, so arbitrary metadata text can never become an
        IP Entity.
        """

        if not isinstance(metadata, dict):
            return ()

        values: list[str] = []

        for key in (
            "host_ip",
            "ip",
            "a",
            "aaaa",
        ):
            raw = metadata.get(key)

            if raw is None:
                continue

            if isinstance(raw, (list, tuple, set, frozenset)):
                items = raw
            else:
                items = (raw,)

            for item in items:
                text = str(item).strip()

                if not text:
                    continue

                try:
                    canonical = str(
                        ip_address(text)
                    )
                except ValueError:
                    continue

                if canonical not in values:
                    values.append(canonical)

        return tuple(values)

    @staticmethod
    def _entity_candidates(
        finding: OsintFinding,
    ) -> tuple[tuple[EntityType, str, float], ...]:
        candidates: list[tuple[EntityType, str, float]] = []
        category = (finding.category or "").strip().casefold()
        value = (finding.value or "").strip()
        url = (finding.url or "").strip()
        metadata = (
            getattr(finding, "metadata", {})
            or {}
        )

        if category == "search_query":
            return ()

        category_map = {
            "phone": EntityType.PHONE,
            "email": EntityType.EMAIL,
            "username": EntityType.USERNAME,
            "domain": EntityType.DOMAIN,
            "hostname": EntityType.DOMAIN,
            "subdomain": EntityType.DOMAIN,
            # Discovery-chain categories.
            "dns": EntityType.DOMAIN,
            "ip": EntityType.IP,
            "url": EntityType.URL,
            "http": EntityType.URL,
            "endpoint": EntityType.URL,
            "archived_url": EntityType.URL,
            "historical_url": EntityType.URL,
            "public_url": EntityType.URL,
            "link": EntityType.URL,
            "account": EntityType.ACCOUNT,
            "location": EntityType.LOCATION,
        }

        confidence = (
            OsintFindingPersistenceService._clamp_confidence(
                finding.confidence
            )
        )

        if category == "certificate" and value:
            candidates.extend(
                OsintFindingPersistenceService
                ._certificate_identifier_candidates(
                    value,
                    confidence,
                )
            )

        mapped = category_map.get(category)
        if mapped is not None and value:
            candidates.append(
                (
                    mapped,
                    value,
                    confidence,
                )
            )

        # DNSX and HTTPX expose resolved addresses in structured metadata.
        # Persist them as first-class IP entities so they can enter the normal
        # NETWORK_ENRICHMENT pivot path after provenance has been recorded.
        if category in {
            "dns",
            "http",
        }:
            for ip_value in (
                OsintFindingPersistenceService
                ._metadata_ip_candidates(
                    metadata
                )
            ):
                candidates.append(
                    (
                        EntityType.IP,
                        ip_value,
                        confidence,
                    )
                )

        # URL provenance is independently useful even when the finding category
        # is "account" and value is the original searched username.
        # Search navigation leads remain evidence metadata, not URL entities.
        if (
            url
            and not metadata.get(
                "lead_only",
                False,
            )
        ):
            candidates.append(
                (
                    EntityType.URL,
                    url,
                    confidence,
                )
            )

        unique: list[tuple[EntityType, str, float]] = []
        seen: set[tuple[EntityType, str]] = set()
        for item in candidates:
            key = (
                item[0],
                item[1].strip(),
            )
            if not key[1] or key in seen:
                continue
            seen.add(key)
            unique.append(item)

        return tuple(unique)

    @staticmethod
    def _evidence_type(finding: OsintFinding) -> EvidenceType:
        category = (finding.category or "").strip().casefold()

        mapping = {
            "phone": EvidenceType.PHONE,
            "email": EvidenceType.EMAIL,
            "username": EvidenceType.USERNAME,
            "account": EvidenceType.LINK if finding.url else EvidenceType.OTHER,
            "url": EvidenceType.LINK,
            "http": EvidenceType.LINK,
            "endpoint": EvidenceType.LINK,
            "archived_url": EvidenceType.LINK,
            "historical_url": EvidenceType.LINK,
            "public_url": EvidenceType.LINK,
            "link": EvidenceType.LINK,
            "dns": EvidenceType.METADATA,
            "certificate": EvidenceType.METADATA,
            "location": EvidenceType.LOCATION,
            "hash": EvidenceType.HASH,
            "metadata": EvidenceType.METADATA,
        }
        return mapping.get(category, EvidenceType.OTHER)

    @staticmethod
    def _evidence_value(finding: OsintFinding) -> str:
        if finding.url:
            return finding.url
        return finding.value or ""

    @staticmethod
    def _evidence_title(
        connector: str,
        finding: OsintFinding,
    ) -> str:
        category = (finding.category or "finding").strip()
        return f"OSINT · {connector} · {category}"[:255]

    @staticmethod
    def _source_key(
        *,
        connector: str,
        target_type: OsintTargetType,
        target_value: str,
        goal: DiscoveryGoal,
    ) -> str:
        payload = "|".join(
            (
                connector.strip().casefold(),
                target_type.value,
                target_value.strip().casefold(),
                goal.value,
            )
        )
        digest = sha256(payload.encode("utf-8")).hexdigest()
        return f"{connector.strip().casefold()}:{digest}"

    @staticmethod
    def _evidence_key(
        *,
        source_key: str,
        finding: OsintFinding,
    ) -> str:
        metadata_json = json.dumps(
            finding.metadata or {},
            ensure_ascii=False,
            default=str,
            sort_keys=True,
            separators=(",", ":"),
        )
        payload = "|".join(
            (
                source_key,
                (finding.category or "").strip().casefold(),
                (finding.value or "").strip(),
                (finding.source or "").strip(),
                (finding.url or "").strip(),
                metadata_json,
            )
        )
        return sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _is_persistable_finding(finding: OsintFinding) -> bool:
        return bool(
            (finding.value or "").strip()
            or (finding.url or "").strip()
            or finding.metadata
        )

    @staticmethod
    def _clamp_confidence(value: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, number))
