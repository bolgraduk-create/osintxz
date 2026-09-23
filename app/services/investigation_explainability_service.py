"""Normalize existing analytical explanations into one Investigation contract.

The service is an adapter only. It does not calculate scores, choose identity
resolution decisions, alter graph analysis, change search order, or create
merge records.
"""

from __future__ import annotations

from typing import Any, Iterable
from uuid import UUID

from app.analysis.graph_explainability import (
    GraphEntityExplanation,
    GraphPairExplanation,
)
from app.entity_resolution.contracts import (
    EntityResolutionResult,
    EntityResolutionSignalDirection,
)
from app.investigation.explainability import (
    InvestigationExplainabilityBundle,
    InvestigationExplanation,
    InvestigationExplanationDomain,
    InvestigationExplanationEffect,
    InvestigationExplanationQuestion,
    InvestigationExplanationReason,
    InvestigationExplanationSubject,
)
from app.investigation.search_result import InvestigationSearchHit
from app.models.entity_merge import EntityMerge


class InvestigationExplainabilityService:
    """Build normalized WHY answers from canonical source-layer explanations."""

    METADATA_KEY = "investigation_explainability"

    def annotate_search_hits(
        self,
        hits: list[InvestigationSearchHit],
    ) -> list[InvestigationSearchHit]:
        for hit in hits:
            bundle = self.explain_search_hit(hit)
            hit.metadata[self.METADATA_KEY] = bundle.to_payload()
        return hits

    def explain_search_hit(
        self,
        hit: InvestigationSearchHit,
    ) -> InvestigationExplainabilityBundle:
        if not isinstance(hit, InvestigationSearchHit):
            raise TypeError("hit must be InvestigationSearchHit.")

        explanations: list[InvestigationExplanation] = []
        subject = InvestigationExplanationSubject(
            object_type=hit.object_type,
            object_id=hit.object_id,
        )

        search_payload = hit.metadata.get("search_explanation")
        if not isinstance(search_payload, dict):
            search_payload = {}

        search_reasons = self._search_reasons(search_payload)
        methods = [
            str(value)
            for value in (
                search_payload.get("matched_methods")
                or [
                    getattr(method, "value", str(method))
                    for method in hit.matched_methods
                ]
            )
            if str(value).strip()
        ]

        raw_search_summary = str(
            search_payload.get("summary")
            or ""
        ).strip()
        found_summary = (
            "The object was returned by Investigation Search"
            + (
                " using " + ", ".join(methods)
                if methods
                else ""
            )
            + ". This explains retrieval, not whether the underlying "
            "content is true."
        )

        explanations.append(
            InvestigationExplanation(
                domain=InvestigationExplanationDomain.SEARCH,
                question=InvestigationExplanationQuestion.FOUND,
                subject=subject,
                summary=found_summary,
                reasons=tuple(search_reasons),
                metadata={
                    "matchedMethods": methods,
                    "sourceSearchSummary": raw_search_summary,
                    "retrievalRelevanceIsEvidenceConfidence": False,
                    "canonicalEvidenceConfidenceSupplied": bool(
                        isinstance(
                            hit.metadata.get(
                                "canonical_evidence_confidence"
                            ),
                            dict,
                        )
                    ),
                },
            )
        )

        ranking = search_payload.get("ranking")
        if not isinstance(ranking, dict):
            ranking = hit.metadata.get("mathematical_ranking")
        if not isinstance(ranking, dict):
            ranking = {}

        ranking_reasons = self._ranking_reasons(hit, ranking)
        if ranking_reasons:
            explanations.append(
                InvestigationExplanation(
                    domain=InvestigationExplanationDomain.SEARCH,
                    question=InvestigationExplanationQuestion.RANKED,
                    subject=subject,
                    summary=(
                        "The search position is explained by deterministic "
                        "retrieval/fusion/ranking signals; these are relevance "
                        "signals, not Evidence confidence."
                    ),
                    reasons=tuple(ranking_reasons),
                    metadata={
                        "finalScore": float(hit.final_score),
                        "rankingChangedByExplainability": False,
                    },
                )
            )

        canonical = hit.metadata.get(
            "canonical_evidence_confidence"
        )
        if isinstance(canonical, dict):
            strongest = self._strongest_proposition(canonical)
            if strongest is not None:
                evidence = self._evidence_explanation_from_payload(
                    strongest,
                    subject=subject,
                )
                if evidence is not None:
                    explanations.append(evidence)

                    contradiction = self._contradiction_explanation_from_payload(
                        strongest,
                        subject=subject,
                    )
                    if contradiction is not None:
                        explanations.append(contradiction)

        return InvestigationExplainabilityBundle(
            explanations=tuple(self._deduplicate(explanations))
        )

    def explain_evidence_proposition(
        self,
        proposition: object,
    ) -> InvestigationExplainabilityBundle:
        entity_id = self._uuid(
            getattr(proposition, "entity_id", None)
        )
        if entity_id is None:
            raise ValueError(
                "Evidence proposition must expose a valid entity_id."
            )

        payload = self._evidence_payload_from_object(proposition)
        subject = InvestigationExplanationSubject(
            object_type="entity",
            object_id=entity_id,
        )

        explanations: list[InvestigationExplanation] = []
        confidence = self._evidence_explanation_from_payload(
            payload,
            subject=subject,
        )
        if confidence is not None:
            explanations.append(confidence)

        contradiction = self._contradiction_explanation_from_payload(
            payload,
            subject=subject,
        )
        if contradiction is not None:
            explanations.append(contradiction)

        return InvestigationExplainabilityBundle(
            explanations=tuple(explanations)
        )

    def explain_entity_resolution(
        self,
        result: EntityResolutionResult,
    ) -> InvestigationExplainabilityBundle:
        if not isinstance(result, EntityResolutionResult):
            raise TypeError("result must be EntityResolutionResult.")

        subject = InvestigationExplanationSubject(
            object_type="entity",
            object_id=result.first_entity_id,
            related_object_type="entity",
            related_object_id=result.second_entity_id,
        )

        reasons = tuple(
            InvestigationExplanationReason(
                code=reason.code,
                message=reason.message,
                effect=self._resolution_effect(reason.direction),
                score=reason.score,
                details=dict(reason.details),
            )
            for reason in result.reasons
        )

        explanations = [
            InvestigationExplanation(
                domain=InvestigationExplanationDomain.ENTITY_RESOLUTION,
                question=InvestigationExplanationQuestion.RESOLVED,
                subject=subject,
                summary=(
                    "Entity Resolution decision is "
                    f"{result.decision.value}; identity support is "
                    f"{result.identity_score:.3f} and decision confidence is "
                    f"{result.confidence:.3f}. These values are not treated as "
                    "calibrated probabilities."
                ),
                reasons=reasons,
                metadata={
                    "decision": result.decision.value,
                    "identityScore": float(result.identity_score),
                    "decisionConfidence": float(result.confidence),
                    "supportScore": float(result.support_score),
                    "contradictionScore": float(
                        result.contradiction_score
                    ),
                    "mergePerformed": False,
                },
            )
        ]

        contradictory = tuple(
            reason
            for reason in reasons
            if reason.effect
            == InvestigationExplanationEffect.CONTRADICT
        )
        if contradictory or result.contradiction_score > 0.0:
            explanations.append(
                InvestigationExplanation(
                    domain=InvestigationExplanationDomain.ENTITY_RESOLUTION,
                    question=InvestigationExplanationQuestion.CONTRADICTED,
                    subject=subject,
                    summary=(
                        "Entity Resolution observed contradictory identity "
                        "signals for this entity pair."
                    ),
                    reasons=contradictory,
                    metadata={
                        "contradictionScore": float(
                            result.contradiction_score
                        ),
                    },
                )
            )

        return InvestigationExplainabilityBundle(
            explanations=tuple(explanations)
        )

    def explain_graph_entity(
        self,
        explanation: GraphEntityExplanation,
    ) -> InvestigationExplainabilityBundle:
        if not isinstance(explanation, GraphEntityExplanation):
            raise TypeError(
                "explanation must be GraphEntityExplanation."
            )

        subject = InvestigationExplanationSubject(
            object_type="entity",
            object_id=explanation.entity_id,
        )

        reasons: list[InvestigationExplanationReason] = [
            InvestigationExplanationReason(
                code=f"graph_reason_{index}",
                message=message,
                effect=InvestigationExplanationEffect.CONTEXT,
            )
            for index, message in enumerate(
                explanation.reasons,
                start=1,
            )
        ]

        for metric in explanation.metric_ranks:
            reasons.append(
                InvestigationExplanationReason(
                    code=f"graph_rank:{metric.metric}",
                    message=(
                        f"{metric.metric} is ranked {metric.rank} of "
                        f"{metric.total_entities} with value "
                        f"{metric.value:.6f}."
                    ),
                    effect=InvestigationExplanationEffect.CONTEXT,
                    score=float(metric.value),
                    details={
                        "metric": metric.metric,
                        "rank": metric.rank,
                        "totalEntities": metric.total_entities,
                    },
                )
            )

        return InvestigationExplainabilityBundle(
            explanations=(
                InvestigationExplanation(
                    domain=InvestigationExplanationDomain.GRAPH,
                    question=InvestigationExplanationQuestion.RANKED,
                    subject=subject,
                    summary=(
                        "The Entity's graph position is explained by separate "
                        "centrality ranks, component membership and community "
                        "membership; no combined graph-importance score is "
                        "invented."
                    ),
                    reasons=tuple(reasons),
                    metadata={
                        "componentIndex": explanation.component_index,
                        "componentSize": explanation.component_size,
                        "communityId": explanation.community_id,
                        "communitySize": explanation.community_size,
                    },
                ),
            )
        )

    def explain_graph_pair(
        self,
        explanation: GraphPairExplanation,
    ) -> InvestigationExplainabilityBundle:
        if not isinstance(explanation, GraphPairExplanation):
            raise TypeError(
                "explanation must be GraphPairExplanation."
            )

        subject = InvestigationExplanationSubject(
            object_type="entity",
            object_id=explanation.source_entity_id,
            related_object_type="entity",
            related_object_id=explanation.target_entity_id,
        )

        reasons = tuple(
            InvestigationExplanationReason(
                code=f"graph_pair_reason_{index}",
                message=message,
                effect=InvestigationExplanationEffect.CONTEXT,
            )
            for index, message in enumerate(
                explanation.reasons,
                start=1,
            )
        )

        if explanation.has_direct_relationship:
            summary = (
                "A direct structural graph relationship exists between the "
                "two Entities. This explains association structure, not "
                "identity."
            )
        elif explanation.has_link_prediction:
            summary = (
                "No direct relationship exists, but graph analysis produced "
                "a structural missing-link prediction. This is not a persisted "
                "Relationship and not identity evidence."
            )
        else:
            summary = (
                "The pair explanation describes shared graph structure "
                "without claiming a direct Relationship."
            )

        return InvestigationExplainabilityBundle(
            explanations=(
                InvestigationExplanation(
                    domain=InvestigationExplanationDomain.GRAPH,
                    question=InvestigationExplanationQuestion.LINKED,
                    subject=subject,
                    summary=summary,
                    reasons=reasons,
                    metadata={
                        "directRelationship": bool(
                            explanation.has_direct_relationship
                        ),
                        "linkPrediction": bool(
                            explanation.has_link_prediction
                        ),
                        "sameComponent": bool(
                            explanation.same_component
                        ),
                        "sameCommunity": bool(
                            explanation.same_community
                        ),
                        "componentMode": explanation.component_mode,
                    },
                ),
            )
        )

    def explain_entity_merge(
        self,
        merge: EntityMerge,
    ) -> InvestigationExplainabilityBundle:
        if not isinstance(merge, EntityMerge):
            raise TypeError("merge must be EntityMerge.")

        reason = str(merge.reason or "").strip()
        message = (
            reason
            if reason
            else (
                "A persisted EntityMerge record exists, but no explicit merge "
                "reason was stored."
            )
        )

        return InvestigationExplainabilityBundle(
            explanations=(
                InvestigationExplanation(
                    domain=InvestigationExplanationDomain.ENTITY_MERGE,
                    question=InvestigationExplanationQuestion.MERGED,
                    subject=InvestigationExplanationSubject(
                        object_type="entity",
                        object_id=merge.source_entity_id,
                        related_object_type="entity",
                        related_object_id=merge.target_entity_id,
                    ),
                    summary=message,
                    reasons=(
                        InvestigationExplanationReason(
                            code=(
                                "stored_merge_reason"
                                if reason
                                else "merge_reason_missing"
                            ),
                            message=message,
                            effect=(
                                InvestigationExplanationEffect.CONTEXT
                                if reason
                                else InvestigationExplanationEffect.LIMITATION
                            ),
                        ),
                    ),
                    metadata={
                        "persistedMergeRecord": True,
                        "resolutionDecisionInferred": False,
                    },
                ),
            )
        )

    def from_payloads(
        self,
        payloads: Iterable[dict[str, Any]],
    ) -> InvestigationExplainabilityBundle:
        """Rehydrate payloads previously produced by the unified contract."""

        explanations: list[InvestigationExplanation] = []

        for row in payloads:
            if not isinstance(row, dict):
                continue

            subject_payload = row.get("subject")
            if not isinstance(subject_payload, dict):
                continue

            object_id = self._uuid(
                subject_payload.get("objectId")
            )
            related_id = self._uuid(
                subject_payload.get("relatedObjectId")
            )
            object_type = str(
                subject_payload.get("objectType")
                or ""
            ).strip()
            related_type = str(
                subject_payload.get("relatedObjectType")
                or ""
            ).strip()

            if not object_type or object_id is None:
                continue
            if bool(related_type) != (related_id is not None):
                continue

            try:
                domain = InvestigationExplanationDomain(
                    str(row.get("domain") or "")
                )
                question = InvestigationExplanationQuestion(
                    str(row.get("question") or "")
                )
            except ValueError:
                continue

            summary = str(
                row.get("summary")
                or ""
            ).strip()
            if not summary:
                continue

            reasons = tuple(
                self._contract_reason_from_payload(
                    reason,
                    default_effect=InvestigationExplanationEffect.CONTEXT,
                )
                for reason in (
                    row.get("reasons")
                    or []
                )
                if isinstance(reason, dict)
            )
            limitations = tuple(
                self._contract_reason_from_payload(
                    reason,
                    default_effect=InvestigationExplanationEffect.LIMITATION,
                )
                for reason in (
                    row.get("limitations")
                    or []
                )
                if isinstance(reason, dict)
            )

            explanations.append(
                InvestigationExplanation(
                    domain=domain,
                    question=question,
                    subject=InvestigationExplanationSubject(
                        object_type=object_type,
                        object_id=object_id,
                        related_object_type=(
                            related_type
                            or None
                        ),
                        related_object_id=related_id,
                    ),
                    summary=summary,
                    reasons=reasons,
                    limitations=limitations,
                    metadata=dict(
                        row.get("metadata")
                        or {}
                    ),
                )
            )

        return InvestigationExplainabilityBundle(
            explanations=tuple(
                self._deduplicate(
                    explanations
                )
            )
        )

    def collect(
        self,
        bundles: Iterable[InvestigationExplainabilityBundle],
    ) -> InvestigationExplainabilityBundle:
        explanations: list[InvestigationExplanation] = []
        for bundle in bundles:
            if not isinstance(bundle, InvestigationExplainabilityBundle):
                raise TypeError(
                    "collect() accepts InvestigationExplainabilityBundle values."
                )
            explanations.extend(bundle.explanations)
        return InvestigationExplainabilityBundle(
            explanations=tuple(self._deduplicate(explanations))
        )

    def _search_reasons(
        self,
        payload: dict[str, Any],
    ) -> list[InvestigationExplanationReason]:
        reasons: list[InvestigationExplanationReason] = []
        for index, row in enumerate(payload.get("reasons") or [], start=1):
            if not isinstance(row, dict):
                continue
            message = str(row.get("reason") or "").strip()
            if not message:
                continue
            reasons.append(
                InvestigationExplanationReason(
                    code=f"search_match_{index}",
                    message=message,
                    effect=InvestigationExplanationEffect.SUPPORT,
                    score=self._number(row.get("score")),
                    method=str(row.get("method") or "").strip() or None,
                    details=dict(row.get("details") or {}),
                )
            )
        return reasons

    def _ranking_reasons(
        self,
        hit: InvestigationSearchHit,
        ranking: dict[str, Any],
    ) -> list[InvestigationExplanationReason]:
        reasons: list[InvestigationExplanationReason] = []

        if hit.scores.fusion is not None:
            reasons.append(
                InvestigationExplanationReason(
                    code="search_fusion_score",
                    message=(
                        "Rank fusion contributed retrieval agreement score "
                        f"{float(hit.scores.fusion):.3f}."
                    ),
                    effect=InvestigationExplanationEffect.CONTEXT,
                    score=float(hit.scores.fusion),
                )
            )

        if hit.scores.rerank is not None:
            reasons.append(
                InvestigationExplanationReason(
                    code="search_rerank_score",
                    message=(
                        "Deterministic mathematical reranking produced score "
                        f"{float(hit.scores.rerank):.3f}."
                    ),
                    effect=InvestigationExplanationEffect.CONTEXT,
                    score=float(hit.scores.rerank),
                    details={
                        "ranking": dict(ranking),
                    },
                )
            )

        if hit.final_score is not None:
            reasons.append(
                InvestigationExplanationReason(
                    code="search_final_score",
                    message=(
                        "The final search ordering score is "
                        f"{float(hit.final_score):.3f}; it represents search "
                        "relevance/ranking, not Evidence confidence."
                    ),
                    effect=InvestigationExplanationEffect.CONTEXT,
                    score=float(hit.final_score),
                )
            )
        return reasons

    def _evidence_explanation_from_payload(
        self,
        payload: dict[str, Any],
        *,
        subject: InvestigationExplanationSubject,
    ) -> InvestigationExplanation | None:
        explanation = payload.get("explanation")
        if not isinstance(explanation, dict):
            return None

        summary = str(explanation.get("summary") or "").strip()
        if not summary:
            return None

        return InvestigationExplanation(
            domain=InvestigationExplanationDomain.EVIDENCE,
            question=InvestigationExplanationQuestion.CONFIDENT,
            subject=subject,
            summary=summary,
            reasons=tuple(
                self._normalized_evidence_reasons(
                    explanation.get("reasons"),
                    default_effect=InvestigationExplanationEffect.SUPPORT,
                )
            ),
            limitations=tuple(
                self._normalized_evidence_reasons(
                    explanation.get("limitations"),
                    default_effect=InvestigationExplanationEffect.LIMITATION,
                )
            ),
            metadata={
                "propositionKey": str(
                    payload.get("proposition_key") or ""
                ),
                "confidence": self._number(
                    payload.get("confidence_score")
                ),
                "coverage": self._number(
                    payload.get("assessment_coverage")
                ),
                "generalSourceTruthScore": False,
            },
        )

    def _contradiction_explanation_from_payload(
        self,
        payload: dict[str, Any],
        *,
        subject: InvestigationExplanationSubject,
    ) -> InvestigationExplanation | None:
        explanation = payload.get("explanation")
        if not isinstance(explanation, dict):
            return None

        contradictory = []
        for row in explanation.get("limitations") or []:
            if not isinstance(row, dict):
                continue
            code = str(row.get("code") or "")
            effect = str(row.get("effect") or "")
            if (
                code in {"hard_conflict", "contradiction_present"}
                or effect == "contradiction"
            ):
                contradictory.extend(
                    self._normalized_evidence_reasons(
                        [row],
                        default_effect=InvestigationExplanationEffect.CONTRADICT,
                    )
                )

        if not contradictory:
            return None

        return InvestigationExplanation(
            domain=InvestigationExplanationDomain.EVIDENCE,
            question=InvestigationExplanationQuestion.CONTRADICTED,
            subject=subject,
            summary=(
                "The proposition has explicit contradictory Evidence in the "
                "canonical Evidence Confidence analysis."
            ),
            reasons=tuple(contradictory),
            metadata={
                "propositionKey": str(
                    payload.get("proposition_key") or ""
                ),
                "hardConflict": bool(
                    payload.get("hard_conflict")
                ),
            },
        )

    def _evidence_payload_from_object(
        self,
        proposition: object,
    ) -> dict[str, Any]:
        confidence = getattr(proposition, "confidence", None)
        explanation = getattr(proposition, "explanation", None)
        explanation_payload = {}
        to_payload = getattr(explanation, "to_payload", None)
        if callable(to_payload):
            candidate = to_payload()
            if isinstance(candidate, dict):
                explanation_payload = candidate

        return {
            "proposition_key": str(
                getattr(proposition, "proposition_key", "") or ""
            ),
            "confidence_score": self._number(
                getattr(
                    proposition,
                    "confidence_score",
                    getattr(confidence, "confidence_score", None),
                )
            ),
            "assessment_coverage": self._number(
                getattr(
                    proposition,
                    "assessment_coverage",
                    getattr(confidence, "assessment_coverage", None),
                )
            ),
            "hard_conflict": bool(
                getattr(confidence, "hard_conflict", False)
            ),
            "explanation": explanation_payload,
        }

    def _normalized_evidence_reasons(
        self,
        rows: Any,
        *,
        default_effect: InvestigationExplanationEffect,
    ) -> list[InvestigationExplanationReason]:
        reasons: list[InvestigationExplanationReason] = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            code = str(row.get("code") or "").strip()
            message = str(row.get("message") or "").strip()
            if not code or not message:
                continue
            effect = self._effect(
                row.get("effect"),
                default=default_effect,
            )
            reasons.append(
                InvestigationExplanationReason(
                    code=code,
                    message=message,
                    effect=effect,
                    score=self._number(row.get("value")),
                    details={
                        "coverage": self._number(
                            row.get("coverage")
                        ),
                        **dict(row.get("details") or {}),
                    },
                )
            )
        return reasons

    def _contract_reason_from_payload(
        self,
        row: dict[str, Any],
        *,
        default_effect: InvestigationExplanationEffect,
    ) -> InvestigationExplanationReason:
        return InvestigationExplanationReason(
            code=str(
                row.get("code")
                or "unknown_reason"
            ),
            message=str(
                row.get("message")
                or "Explanation reason unavailable."
            ),
            effect=self._effect(
                row.get("effect"),
                default=default_effect,
            ),
            score=self._number(
                row.get("score")
            ),
            method=str(
                row.get("method")
                or ""
            ).strip() or None,
            details=dict(
                row.get("details")
                or {}
            ),
        )

    @staticmethod
    def _strongest_proposition(
        canonical: dict[str, Any],
    ) -> dict[str, Any] | None:
        rows = [
            row
            for row in (canonical.get("propositions") or [])
            if isinstance(row, dict)
        ]
        if not rows:
            return None
        return max(
            rows,
            key=lambda row: (
                float(row.get("confidence_score") or 0.0),
                float(row.get("assessment_coverage") or 0.0),
                str(row.get("proposition_key") or ""),
            ),
        )

    @staticmethod
    def _resolution_effect(
        direction: EntityResolutionSignalDirection,
    ) -> InvestigationExplanationEffect:
        if direction == EntityResolutionSignalDirection.SUPPORT:
            return InvestigationExplanationEffect.SUPPORT
        if direction == EntityResolutionSignalDirection.CONTRADICT:
            return InvestigationExplanationEffect.CONTRADICT
        return InvestigationExplanationEffect.NEUTRAL

    @staticmethod
    def _effect(
        value: Any,
        *,
        default: InvestigationExplanationEffect,
    ) -> InvestigationExplanationEffect:
        normalized = str(
            getattr(value, "value", value) or ""
        ).strip().casefold()
        mapping = {
            "support": InvestigationExplanationEffect.SUPPORT,
            "contradict": InvestigationExplanationEffect.CONTRADICT,
            "contradiction": InvestigationExplanationEffect.CONTRADICT,
            "limitation": InvestigationExplanationEffect.LIMITATION,
            "uncertainty": InvestigationExplanationEffect.LIMITATION,
            "context": InvestigationExplanationEffect.CONTEXT,
            "neutral": InvestigationExplanationEffect.NEUTRAL,
        }
        return mapping.get(normalized, default)

    @staticmethod
    def _number(value: Any) -> float | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _uuid(value: Any) -> UUID | None:
        if isinstance(value, UUID):
            return value
        try:
            return UUID(str(value))
        except (TypeError, ValueError, AttributeError):
            return None

    @staticmethod
    def _deduplicate(
        explanations: Iterable[InvestigationExplanation],
    ) -> list[InvestigationExplanation]:
        seen: set[tuple[str, str, str, str]] = set()
        result: list[InvestigationExplanation] = []
        for explanation in explanations:
            key = (
                explanation.domain.value,
                explanation.question.value,
                str(explanation.subject.object_id),
                str(explanation.subject.related_object_id or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            result.append(explanation)
        return result


__all__ = [
    "InvestigationExplainabilityService",
]
