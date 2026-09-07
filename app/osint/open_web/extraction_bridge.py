"""M021.8 Open-Web document -> identifier extraction bridge.

The bridge reuses UnifiedExtractionService.extract_text() and converts its
normalized ExtractionCandidate objects into ordinary OsintFinding objects.

It deliberately performs no persistence, relationship inference, recursive
execution, networking or transaction management.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable
from urllib.parse import urlsplit, urlunsplit

from app.models.entity import EntityType
from app.osint.open_web.contracts import OpenWebDocument, OpenWebQuery
from app.osint.result import OsintFinding
from app.processing.extraction.contracts import ExtractionCandidate
from app.services.unified_extraction_service import UnifiedExtractionService


@dataclass(slots=True)
class OpenWebExtractionResult:
    """Extraction output for one Open-Web document."""

    document: OpenWebDocument
    candidates: list[ExtractionCandidate] = field(default_factory=list)
    findings: list[OsintFinding] = field(default_factory=list)
    skipped_duplicates: int = 0
    extraction_error: str | None = None

    @property
    def success(self) -> bool:
        return self.extraction_error is None

    @property
    def total_candidates(self) -> int:
        return len(self.candidates)

    @property
    def total_findings(self) -> int:
        return len(self.findings)


@dataclass(slots=True)
class OpenWebExtractionBatchResult:
    """Aggregate extraction result for multiple documents."""

    results: list[OpenWebExtractionResult] = field(default_factory=list)

    @property
    def findings(self) -> list[OsintFinding]:
        return [
            finding
            for result in self.results
            for finding in result.findings
        ]

    @property
    def successful_documents(self) -> int:
        return sum(1 for result in self.results if result.success)

    @property
    def failed_documents(self) -> int:
        return sum(1 for result in self.results if not result.success)

    @property
    def total_findings(self) -> int:
        return sum(result.total_findings for result in self.results)


class OpenWebIdentifierExtractionBridge:
    """Convert public web documents into standard OSINT findings."""

    def __init__(
        self,
        extraction_service: UnifiedExtractionService,
    ) -> None:
        self.extraction_service = extraction_service

    def extract_document(
        self,
        document: OpenWebDocument,
        *,
        query: OpenWebQuery | None = None,
    ) -> OpenWebExtractionResult:
        text = self._build_extraction_text(document)

        if not text:
            return OpenWebExtractionResult(document=document)

        try:
            raw_candidates = self.extraction_service.extract_text(text)
        except Exception as exc:
            return OpenWebExtractionResult(
                document=document,
                extraction_error=str(exc) or exc.__class__.__name__,
            )

        candidates, skipped_duplicates = self._deduplicate_candidates(
            raw_candidates
        )

        # M021.16.3.2 quality gate
        candidates, skipped_quality = self._filter_quality_candidates(
            candidates,
            document=document,
            query=query,
        )
        skipped_duplicates += skipped_quality

        findings = [
            self._candidate_to_finding(
                candidate=candidate,
                document=document,
                query=query,
            )
            for candidate in candidates
        ]

        return OpenWebExtractionResult(
            document=document,
            candidates=candidates,
            findings=findings,
            skipped_duplicates=skipped_duplicates,
        )

    def extract_documents(
        self,
        documents: Iterable[OpenWebDocument],
        *,
        query: OpenWebQuery | None = None,
    ) -> OpenWebExtractionBatchResult:
        """Extract each document independently; one bad document is isolated."""

        return OpenWebExtractionBatchResult(
            results=[
                self.extract_document(document, query=query)
                for document in documents
            ]
        )

    @staticmethod
    def _build_extraction_text(
        document: OpenWebDocument,
    ) -> str:
        """Extract page content only; document URL stays provenance metadata."""

        return document.extraction_text.strip()

    @classmethod
    def _filter_quality_candidates(
        cls,
        candidates: Iterable[ExtractionCandidate],
        *,
        document: OpenWebDocument,
        query: OpenWebQuery | None = None,
    ) -> tuple[list[ExtractionCandidate], int]:
        accepted: list[ExtractionCandidate] = []
        skipped = 0
        document_url = cls._canonical_url(document.url)

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

            if candidate.entity_type is EntityType.PHONE:
                if not cls._plausible_open_web_phone(candidate.value):
                    skipped += 1
                    continue

            accepted.append(candidate)

        return accepted, skipped

    @staticmethod
    def _plausible_open_web_phone(value: str) -> bool:
        raw = value.strip()
        digits = "".join(ch for ch in raw if ch.isdigit())

        if len(digits) < 7 or len(digits) > 15:
            return False

        if raw.isdigit():
            return False

        has_plus = raw.startswith("+")
        has_phone_formatting = any(
            ch in raw
            for ch in (" ", "-", "(", ")")
        )

        if not has_plus and not has_phone_formatting:
            return False

        if len(digits) in {8, 14}:
            year_text = digits[:4]
            if year_text.isdigit():
                year = int(year_text)
                if 1900 <= year <= 2100:
                    return False

        return True

    @staticmethod
    def _canonical_url(value: str) -> str:
        raw = value.strip()
        if not raw:
            return ""

        try:
            parsed = urlsplit(raw)
        except ValueError:
            return raw.casefold().rstrip("/")

        scheme = parsed.scheme.casefold()
        host = (parsed.hostname or "").casefold().rstrip(".")
        if not host:
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

    @staticmethod
    def _deduplicate_candidates(
        candidates: Iterable[ExtractionCandidate],
    ) -> tuple[list[ExtractionCandidate], int]:
        """Collapse duplicate normalized identifiers inside one document."""

        unique: list[ExtractionCandidate] = []
        seen: set[tuple[str, str]] = set()
        duplicates = 0

        for candidate in candidates:
            normalized_value = candidate.normalized_value.strip()
            if not normalized_value:
                continue

            key = (
                candidate.entity_type.value,
                normalized_value,
            )

            if key in seen:
                duplicates += 1
                continue

            seen.add(key)
            unique.append(candidate)

        return unique, duplicates

    @staticmethod
    def _candidate_to_finding(
        *,
        candidate: ExtractionCandidate,
        document: OpenWebDocument,
        query: OpenWebQuery | None,
    ) -> OsintFinding:
        """Map an extraction candidate to the existing universal OSINT finding."""

        candidate_confidence = max(
            0.0,
            min(1.0, float(candidate.confidence)),
        )
        document_confidence = max(
            0.0,
            min(1.0, float(document.confidence)),
        )
        document_reliability = max(
            0.0,
            min(1.0, float(document.reliability)),
        )

        metadata = {
            "workflow": "open_web_discovery",
            "lead_only": True,
            "verified_ownership": False,
            "normalized_value": candidate.normalized_value,
            "extraction": {
                "entity_type": candidate.entity_type.value,
                "candidate_metadata": dict(candidate.metadata),
            },
            "document": {
                "provider": document.provider,
                "url": document.url,
                "title": document.title,
                "captured_at": document.captured_at,
                "content_type": document.content_type,
                "metadata": dict(document.metadata),
            },
        }

        if query is not None:
            metadata["origin"] = {
                "target_type": query.target_type.value,
                "target_value": query.value,
                "case_id": query.case_id,
                "depth": query.depth,
                "parent_entity_id": query.parent_entity_id,
            }

        return OsintFinding(
            category=candidate.entity_type.value,
            value=candidate.value,
            confidence=min(
                candidate_confidence,
                document_confidence,
            ),
            source=document.provider,
            url=document.url,
            reliability=document_reliability,
            metadata=metadata,
        )
