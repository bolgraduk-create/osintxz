"""R13.28c analysis workspace run profiles and OpenAI cost telemetry.

Pure application policy. No Qt, database, network or provider initialization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.investigation_rag_conclusions_service import (
    InvestigationRAGConclusionKind,
)


@dataclass(frozen=True, slots=True)
class AnalysisModeProfile:
    key: str
    label: str
    description: str
    conclusion_kinds: tuple[InvestigationRAGConclusionKind, ...]
    max_output_tokens: int
    recommended_model: str
    recommended_reasoning: str

    @property
    def ai_request_count(self) -> int:
        # Summary is always one call; every selected conclusion is one call.
        return 1 + len(self.conclusion_kinds)


ANALYSIS_MODE_PROFILES: dict[str, AnalysisModeProfile] = {
    "quick": AnalysisModeProfile(
        key="quick",
        label="Quick",
        description="Fast orientation: one grounded investigation summary.",
        conclusion_kinds=(),
        max_output_tokens=1800,
        recommended_model="gpt-5.6-luna",
        recommended_reasoning="low",
    ),
    "standard": AnalysisModeProfile(
        key="standard",
        label="Standard",
        description="Summary plus hypotheses and contradiction analysis.",
        conclusion_kinds=(
            InvestigationRAGConclusionKind.HYPOTHESES,
            InvestigationRAGConclusionKind.CONTRADICTIONS,
        ),
        max_output_tokens=2800,
        recommended_model="gpt-5.6-terra",
        recommended_reasoning="medium",
    ),
    "deep": AnalysisModeProfile(
        key="deep",
        label="Deep",
        description=(
            "Full analytical pass: summary, hypotheses, contradictions "
            "and next investigation steps."
        ),
        conclusion_kinds=(
            InvestigationRAGConclusionKind.HYPOTHESES,
            InvestigationRAGConclusionKind.CONTRADICTIONS,
            InvestigationRAGConclusionKind.NEXT_STEPS,
        ),
        max_output_tokens=4200,
        recommended_model="gpt-5.6",
        recommended_reasoning="high",
    ),
}


OPENAI_ANALYSIS_MODELS: tuple[dict[str, Any], ...] = (
    {
        "id": "gpt-5.6-luna",
        "label": "GPT-5.6 Luna",
        "tier": "Fast / economical",
        "inputUsdPerMillion": 0.20,
        "cachedInputUsdPerMillion": 0.02,
        "outputUsdPerMillion": 1.20,
    },
    {
        "id": "gpt-5.6-terra",
        "label": "GPT-5.6 Terra",
        "tier": "Balanced",
        "inputUsdPerMillion": 2.00,
        "cachedInputUsdPerMillion": 0.20,
        "outputUsdPerMillion": 12.00,
    },
    {
        "id": "gpt-5.6",
        "label": "GPT-5.6 Sol",
        "tier": "Deep reasoning",
        "inputUsdPerMillion": 4.00,
        "cachedInputUsdPerMillion": 0.40,
        "outputUsdPerMillion": 20.00,
    },
)

OPENAI_MODEL_PRICING = {
    str(item["id"]): {
        "input": float(item["inputUsdPerMillion"]),
        "cached_input": float(item["cachedInputUsdPerMillion"]),
        "output": float(item["outputUsdPerMillion"]),
    }
    for item in OPENAI_ANALYSIS_MODELS
}

OPENAI_PRICING_EFFECTIVE_DATE = "2026-09-21"

OPENAI_REASONING_EFFORTS = (
    "none",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
)


def normalize_analysis_mode(value: Any) -> AnalysisModeProfile:
    key = str(value or "standard").strip().casefold()
    return ANALYSIS_MODE_PROFILES.get(
        key,
        ANALYSIS_MODE_PROFILES["standard"],
    )


def normalize_openai_model(value: Any, *, fallback: str = "gpt-5.6") -> str:
    candidate = str(value or fallback).strip()
    if candidate in OPENAI_MODEL_PRICING:
        return candidate
    return str(fallback or "gpt-5.6").strip() or "gpt-5.6"


def normalize_reasoning_effort(value: Any, *, fallback: str = "medium") -> str:
    candidate = str(value or fallback).strip().casefold()
    if candidate in OPENAI_REASONING_EFFORTS:
        return candidate
    normalized_fallback = str(fallback or "medium").strip().casefold()
    return (
        normalized_fallback
        if normalized_fallback in OPENAI_REASONING_EFFORTS
        else "medium"
    )


def generation_kwargs_for_profile(
    *,
    provider: str,
    mode: str,
    model: str | None,
    reasoning_effort: str | None,
) -> dict[str, Any]:
    profile = normalize_analysis_mode(mode)
    if str(provider or "").strip().casefold() != "openai":
        return {}

    resolved_model = normalize_openai_model(
        model,
        fallback=profile.recommended_model,
    )
    resolved_reasoning = normalize_reasoning_effort(
        reasoning_effort,
        fallback=profile.recommended_reasoning,
    )

    kwargs: dict[str, Any] = {
        "model": resolved_model,
        "max_output_tokens": profile.max_output_tokens,
    }
    if resolved_reasoning != "none":
        kwargs["reasoning"] = {
            "effort": resolved_reasoning,
        }
    return kwargs


def estimate_openai_cost(
    usage: dict[str, Any] | None,
) -> dict[str, Any]:
    """Estimate text-token cost from actual per-request usage events.

    The value is explicitly an estimate. Provider pricing can change and
    special service tiers/tool charges are outside this calculation.
    """

    payload = dict(usage or {})
    events = [
        dict(item)
        for item in list(payload.get("events") or [])
        if isinstance(item, dict)
    ]

    total_usd = 0.0
    priced_requests = 0
    unpriced_requests = 0

    for event in events:
        raw_model = str(event.get("model") or "").strip()
        rates = OPENAI_MODEL_PRICING.get(raw_model)
        if not rates:
            unpriced_requests += 1
            continue

        input_tokens = max(0, int(event.get("inputTokens") or 0))
        cached_tokens = min(
            input_tokens,
            max(0, int(event.get("cachedInputTokens") or 0)),
        )
        uncached_tokens = max(0, input_tokens - cached_tokens)
        output_tokens = max(0, int(event.get("outputTokens") or 0))

        # Current GPT-5.6 pricing applies a long-context multiplier when an
        # individual request exceeds 272K input tokens.
        long_context = input_tokens > 272_000
        input_multiplier = 2.0 if long_context else 1.0
        output_multiplier = 1.5 if long_context else 1.0

        total_usd += (
            (uncached_tokens / 1_000_000.0)
            * rates["input"]
            * input_multiplier
        )
        total_usd += (
            (cached_tokens / 1_000_000.0)
            * rates["cached_input"]
            * input_multiplier
        )
        total_usd += (
            (output_tokens / 1_000_000.0)
            * rates["output"]
            * output_multiplier
        )
        priced_requests += 1

    return {
        "currency": "USD",
        "estimatedUsd": round(total_usd, 6),
        "display": "$" + format(total_usd, ".4f"),
        "pricedRequests": priced_requests,
        "unpricedRequests": unpriced_requests,
        "pricingEffectiveDate": OPENAI_PRICING_EFFECTIVE_DATE,
        "approximate": True,
        "notice": (
            "Estimated from reported text-token usage and configured model "
            "rates; provider pricing and non-text charges may change."
        ),
    }


def analysis_workspace_catalog() -> dict[str, Any]:
    return {
        "modes": [
            {
                "key": profile.key,
                "label": profile.label,
                "description": profile.description,
                "requests": profile.ai_request_count,
                "maxOutputTokens": profile.max_output_tokens,
                "recommendedModel": profile.recommended_model,
                "recommendedReasoning": profile.recommended_reasoning,
            }
            for profile in ANALYSIS_MODE_PROFILES.values()
        ],
        "models": [dict(item) for item in OPENAI_ANALYSIS_MODELS],
        "reasoningEfforts": list(OPENAI_REASONING_EFFORTS),
        "pricingEffectiveDate": OPENAI_PRICING_EFFECTIVE_DATE,
    }
