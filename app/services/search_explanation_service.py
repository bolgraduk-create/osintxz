"""Build deterministic human/machine-readable explanations for unified search hits."""

from __future__ import annotations

from app.investigation.search_result import InvestigationSearchHit


class SearchExplanationService:
    """Annotate final hits with a stable explanation payload."""

    METADATA_KEY = "search_explanation"

    def annotate(self, hits: list[InvestigationSearchHit]) -> list[InvestigationSearchHit]:
        for hit in hits:
            hit.metadata[self.METADATA_KEY] = self.build(hit)
        return hits

    def build(self, hit: InvestigationSearchHit) -> dict:
        methods = [method.value for method in hit.matched_methods]
        reasons = [
            {
                "reason": reason.reason,
                "method": reason.method.value if reason.method is not None else None,
                "score": reason.score,
                "details": dict(reason.details),
            }
            for reason in hit.reasons
        ]

        ranking = hit.metadata.get("mathematical_ranking")
        confidence = hit.metadata.get("evidence_confidence")

        summary_parts: list[str] = []
        if methods:
            summary_parts.append("matched by " + ", ".join(methods))
        if hit.scores.fusion is not None:
            summary_parts.append(f"fusion={hit.scores.fusion:.3f}")
        if hit.scores.rerank is not None:
            summary_parts.append(f"rerank={hit.scores.rerank:.3f}")
        if hit.scores.confidence is not None:
            summary_parts.append(f"confidence={hit.scores.confidence:.3f}")

        return {
            "identity": {
                "case_id": str(hit.case_id) if hit.case_id is not None else None,
                "object_type": hit.object_type,
                "object_id": str(hit.object_id),
            },
            "summary": "; ".join(summary_parts) if summary_parts else "No explanation signals available.",
            "matched_methods": methods,
            "reasons": reasons,
            "scores": hit.scores.available_scores(),
            "ranking": ranking,
            "confidence": confidence,
            "provenance": {
                "source_present": hit.source is not None,
                "source_id": hit.metadata.get("source_id"),
                "evidence_support_count": hit.metadata.get("evidence_support_count"),
            },
        }
