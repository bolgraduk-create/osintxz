from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


@dataclass(frozen=True, slots=True)
class PhoneIntelligence:
    input_value: str
    e164: str | None
    international: str | None
    national: str | None
    country_code: int | None
    region_code: str | None
    region_description: str | None
    carrier: str | None
    number_type: str | None
    timezones: tuple[str, ...]
    possible: bool
    valid: bool
    search_variants: tuple[str, ...]
    normalization_status: str = "normalized"
    possible_e164_candidates: tuple[str, ...] = ()

    def metadata(self) -> dict[str, Any]:
        return {
            "input_value": self.input_value,
            "e164": self.e164,
            "international": self.international,
            "national": self.national,
            "country_code": self.country_code,
            "region_code": self.region_code,
            "region_description": self.region_description,
            "carrier": self.carrier,
            "number_type": self.number_type,
            "timezones": list(self.timezones),
            "possible": self.possible,
            "valid": self.valid,
            "search_variants": list(self.search_variants),
            "provider": "python-phonenumbers",
            "local_only": True,
            "network_used": False,
            "normalization_status": self.normalization_status,
            "possible_e164_candidates": list(self.possible_e164_candidates),
        }


class PhoneIntelligenceService:
    """Local-only phone enrichment. Never guesses country silently."""

    _TYPE_NAMES = {
        0: "fixed_line",
        1: "mobile",
        2: "fixed_line_or_mobile",
        3: "toll_free",
        4: "premium_rate",
        5: "shared_cost",
        6: "voip",
        7: "personal_number",
        8: "pager",
        9: "uan",
        10: "voicemail",
        99: "unknown",
    }

    @staticmethod
    def available() -> bool:
        try:
            import phonenumbers  # noqa: F401
        except ImportError:
            return False
        return True

    def analyze(self, value: str, *, default_region: str | None = None) -> PhoneIntelligence:
        try:
            import phonenumbers
            from phonenumbers import carrier, geocoder, timezone
        except ImportError as exc:
            raise RuntimeError("python package 'phonenumbers' is not installed") from exc

        raw = str(value or "").strip()
        if not raw:
            raise ValueError("Phone value must not be empty.")

        region = str(default_region).strip().upper() if default_region and str(default_region).strip() else None
        try:
            parsed = phonenumbers.parse(raw, region)
        except phonenumbers.NumberParseException:
            if region or raw.startswith("+") or not re.fullmatch(r"[0-9()\s.-]+", raw):
                raise
            digits = re.sub(r"\D", "", raw)
            candidates = ()
            if 11 <= len(digits) <= 15:
                try:
                    international_candidate = phonenumbers.parse("+" + digits, None)
                except phonenumbers.NumberParseException:
                    pass
                else:
                    if phonenumbers.is_valid_number(international_candidate):
                        candidates = (phonenumbers.format_number(
                            international_candidate, phonenumbers.PhoneNumberFormat.E164
                        ),)
            return PhoneIntelligence(
                input_value=raw, e164=None, international=None, national=None,
                country_code=None, region_code=None, region_description=None,
                carrier=None, number_type=None, timezones=(), possible=False,
                valid=False, search_variants=(), normalization_status="ambiguous",
                possible_e164_candidates=candidates,
            )

        possible = phonenumbers.is_possible_number(parsed)
        valid = phonenumbers.is_valid_number(parsed)
        e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        international = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        national = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
        region_code = phonenumbers.region_code_for_number(parsed) or None
        region_description = geocoder.description_for_number(parsed, "en") or None
        carrier_name = carrier.name_for_number(parsed, "en") or None
        number_type = self._TYPE_NAMES.get(int(phonenumbers.number_type(parsed)), "unknown")
        timezones = tuple(item for item in timezone.time_zones_for_number(parsed) if item)

        return PhoneIntelligence(
            input_value=raw,
            e164=e164,
            international=international,
            national=national,
            country_code=getattr(parsed, "country_code", None),
            region_code=region_code,
            region_description=region_description,
            carrier=carrier_name,
            number_type=number_type,
            timezones=timezones,
            possible=possible,
            valid=valid,
            search_variants=self.build_search_variants(
                raw=raw,
                e164=e164,
                international=international,
                national=national,
            ),
        )

    @classmethod
    def build_search_variants(
        cls,
        *,
        raw: str,
        e164: str | None,
        international: str | None,
        national: str | None,
    ) -> tuple[str, ...]:
        candidates: list[str] = []

        def add(value: str | None) -> None:
            if value is None:
                return
            text = " ".join(str(value).strip().split())
            if text and text not in candidates:
                candidates.append(text)

        add(e164)
        if e164:
            add(re.sub(r"\D+", "", e164))
        add(international)
        add(national)
        raw_clean = " ".join(str(raw).strip().split())
        if raw_clean.startswith("+"):
            add(raw_clean)

        return tuple(f'"{item}"' for item in candidates[:6])
