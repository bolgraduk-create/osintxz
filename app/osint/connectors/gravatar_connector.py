"""
M021.16.5.1 — Gravatar public profile connector.
"""

from __future__ import annotations

import hashlib
from typing import Any

import requests

from app.osint.base_connector import BaseConnector
from app.osint.models import ConnectorRequest, OsintTargetType
from app.osint.result import OsintFinding, OsintResult, ResultStatus


class GravatarConnector(BaseConnector):
    name = "gravatar"

    description = (
        "Retrieve public Gravatar profile metadata and explicitly "
        "verified public account URLs for an email address."
    )

    supported_targets = {OsintTargetType.EMAIL}

    BASE_URL = "https://api.gravatar.com/v3"

    def is_available(self) -> bool:
        return True

    @staticmethod
    def email_hash(value: str) -> str:
        normalized = value.strip().casefold()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def execute(self, request: ConnectorRequest) -> OsintResult:
        if request.target.target_type not in self.supported_targets:
            return OsintResult(
                connector=self.name,
                status=ResultStatus.NOT_SUPPORTED,
                error="Unsupported target.",
            )

        email = request.target.value.strip()
        identifier = self.email_hash(email)
        url = f"{self.BASE_URL}/profiles/{identifier}"

        try:
            response = requests.get(
                url,
                timeout=request.timeout,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "OSINTXZ/1.0 GravatarConnector",
                },
            )
        except requests.RequestException as exc:
            return OsintResult(
                connector=self.name,
                status=ResultStatus.FAILED,
                error=str(exc),
                metadata={
                    "profile_identifier": identifier,
                    "public_data_only": True,
                },
            )

        if response.status_code == 404:
            return OsintResult(
                connector=self.name,
                status=ResultStatus.SUCCESS,
                metadata={
                    "profile_found": False,
                    "records_found": 0,
                    "profile_identifier": identifier,
                    "public_data_only": True,
                },
            )

        if response.status_code == 429:
            return OsintResult(
                connector=self.name,
                status=ResultStatus.PARTIAL,
                error="Gravatar API rate limit reached.",
                metadata={
                    "profile_identifier": identifier,
                    "rate_limited": True,
                    "public_data_only": True,
                },
            )

        if response.status_code != 200:
            return OsintResult(
                connector=self.name,
                status=ResultStatus.FAILED,
                error=f"Gravatar API error: {response.status_code}",
                metadata={
                    "profile_identifier": identifier,
                    "public_data_only": True,
                },
            )

        try:
            data: dict[str, Any] = response.json()
        except Exception:
            return OsintResult(
                connector=self.name,
                status=ResultStatus.PARTIAL,
                error="Unable to parse Gravatar profile response.",
                raw_data=response.text if request.save_raw_output else None,
                metadata={
                    "profile_identifier": identifier,
                    "public_data_only": True,
                },
            )

        result = OsintResult(
            connector=self.name,
            status=ResultStatus.SUCCESS,
            raw_data=data if request.save_raw_output else None,
        )

        profile_url = self._clean_public_url(data.get("profile_url"))

        result.add_finding(
            OsintFinding(
                category="account",
                value=email,
                source=self.name,
                url=profile_url,
                confidence=0.95,
                reliability=0.95,
                metadata={
                    "profile_found": True,
                    "profile_identifier": identifier,
                    "display_name": data.get("display_name"),
                    "profile_url": profile_url,
                    "avatar_url": data.get("avatar_url"),
                    "location": data.get("location"),
                    "job_title": data.get("job_title"),
                    "company": data.get("company"),
                    "description": data.get("description"),
                    "public_data_only": True,
                    "identity_claim_strength": "profile_observation",
                },
            )
        )

        verified_count = 0
        verified_accounts = data.get("verified_accounts")

        if isinstance(verified_accounts, list):
            seen_urls: set[str] = set()

            for account in verified_accounts:
                if not isinstance(account, dict):
                    continue

                account_url = self._clean_public_url(account.get("url"))
                if not account_url:
                    continue

                key = account_url.casefold().rstrip("/")
                if key in seen_urls:
                    continue

                seen_urls.add(key)
                verified_count += 1

                result.add_finding(
                    OsintFinding(
                        category="url",
                        value=account_url,
                        source=self.name,
                        url=profile_url,
                        confidence=1.0,
                        reliability=0.98,
                        metadata={
                            "verified_by_source": True,
                            "verification_source": "gravatar",
                            "service_type": account.get("service_type"),
                            "service_label": account.get("service_label"),
                            "is_hidden": bool(account.get("is_hidden", False)),
                            "profile_identifier": identifier,
                            "public_data_only": True,
                        },
                    )
                )

        result.metadata = {
            "profile_found": True,
            "profile_identifier": identifier,
            "verified_accounts_found": verified_count,
            "records_found": result.total_findings,
            "public_data_only": True,
            "official_api": True,
        }

        return result

    @staticmethod
    def _clean_public_url(value: object) -> str | None:
        if not isinstance(value, str):
            return None

        candidate = value.strip()
        if not candidate.startswith(("https://", "http://")):
            return None

        return candidate
