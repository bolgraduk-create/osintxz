from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class UsernameProfileObservation:
    provider: str
    canonical_url: str
    confidence: float
    reliability: float

@dataclass(frozen=True, slots=True)
class UsernameProfileFusion:
    canonical_url: str
    providers: tuple[str, ...]
    provider_count: int
    confidence: float

    def metadata(self) -> dict[str, object]:
        return {
            "model": "username_profile_cross_source_v1",
            "canonical_profile_url": self.canonical_url,
            "providers": list(self.providers),
            "provider_count": self.provider_count,
            "confidence": self.confidence,
        }

class UsernameProfileFusionPolicy:
    CAP = 0.97

    @classmethod
    def fuse(cls, observations: list[UsernameProfileObservation]) -> dict[str, UsernameProfileFusion]:
        grouped: dict[str, dict[str, UsernameProfileObservation]] = {}
        for obs in observations:
            url = obs.canonical_url.strip()
            provider = obs.provider.strip()
            if not url or not provider:
                continue
            bucket = grouped.setdefault(url, {})
            key = provider.casefold()
            current = bucket.get(key)
            if current is None or cls._single_signal(obs) > cls._single_signal(current):
                bucket[key] = obs
        result: dict[str, UsernameProfileFusion] = {}
        for url, bucket in grouped.items():
            vals = list(bucket.values())
            if not vals:
                continue
            base = max(cls._single_signal(v) for v in vals)
            count = len(vals)
            bonus = 0.0 if count <= 1 else 0.06 if count == 2 else 0.10 if count == 3 else 0.13
            providers = tuple(sorted((v.provider for v in vals), key=str.casefold))
            result[url] = UsernameProfileFusion(
                canonical_url=url,
                providers=providers,
                provider_count=count,
                confidence=round(min(cls.CAP, base + bonus), 4),
            )
        return result

    @staticmethod
    def _clamp(value: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, number))

    @classmethod
    def _single_signal(cls, obs: UsernameProfileObservation) -> float:
        c = cls._clamp(obs.confidence)
        r = cls._clamp(obs.reliability)
        return max(0.60, min(0.86, 0.55 + 0.20 * c + 0.12 * r))
