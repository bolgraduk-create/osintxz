from __future__ import annotations

import hashlib

import httpx

from app.breach_intelligence.contracts import (
    BreachFinding,
    BreachQueryKind,
    BreachResultStatus,
    BreachSearchResult,
)
from app.breach_intelligence.hibp_client import (
    HibpCredentialsError,
    HibpHttpClient,
)
from app.intelligence_sources.policy import IntelligenceDataSanitizer


class BreachIntelligenceService:
    """
    Safe breach-intelligence facade.

    Raw passwords/tokens are never returned. For password checks, the caller's
    plaintext exists only transiently long enough to compute the k-anonymity
    SHA-1 prefix/suffix locally.
    """

    def __init__(
        self,
        *,
        hibp_client: HibpHttpClient,
        data_sanitizer: IntelligenceDataSanitizer | None = None,
    ) -> None:
        self.hibp_client = hibp_client
        self.data_sanitizer = (
            data_sanitizer or IntelligenceDataSanitizer()
        )

    def search_email(
        self,
        email: str,
        *,
        timeout: int = 30,
    ) -> BreachSearchResult:
        value = (email or "").strip()
        if not value or "@" not in value:
            return BreachSearchResult(
                source="hibp",
                kind=BreachQueryKind.EMAIL,
                status=BreachResultStatus.NOT_SUPPORTED,
                error="Malformed email address.",
            )

        if not self.hibp_client.account_lookup_configured:
            return BreachSearchResult(
                source="hibp",
                kind=BreachQueryKind.EMAIL,
                status=BreachResultStatus.NOT_CONFIGURED,
                error="HIBP API key is not configured.",
                metadata={
                    "credentials_required": True,
                    "automatic_execution": False,
                },
            )

        try:
            rows = self.hibp_client.breached_account(
                value,
                timeout=timeout,
            )
        except HibpCredentialsError as exc:
            return BreachSearchResult(
                source="hibp",
                kind=BreachQueryKind.EMAIL,
                status=BreachResultStatus.NOT_CONFIGURED,
                error=str(exc),
            )
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            if code == 404:
                return BreachSearchResult(
                    source="hibp",
                    kind=BreachQueryKind.EMAIL,
                    status=BreachResultStatus.SUCCESS,
                    findings=[],
                    metadata={"breaches_found": 0},
                )
            if code in {401, 403}:
                return BreachSearchResult(
                    source="hibp",
                    kind=BreachQueryKind.EMAIL,
                    status=BreachResultStatus.FAILED,
                    error=f"HIBP access rejected (HTTP {code}).",
                    metadata={
                        "credentials_invalid_or_forbidden": True,
                        "retryable": False,
                    },
                )
            retryable = code == 429 or code >= 500
            return BreachSearchResult(
                source="hibp",
                kind=BreachQueryKind.EMAIL,
                status=(
                    BreachResultStatus.PARTIAL
                    if retryable
                    else BreachResultStatus.FAILED
                ),
                error=f"HIBP HTTP {code}.",
                metadata={
                    "retryable": retryable,
                    "rate_limited": code == 429,
                },
            )
        except httpx.RequestError as exc:
            return BreachSearchResult(
                source="hibp",
                kind=BreachQueryKind.EMAIL,
                status=BreachResultStatus.PARTIAL,
                error=str(exc),
                metadata={"retryable": True},
            )
        except Exception as exc:
            return BreachSearchResult(
                source="hibp",
                kind=BreachQueryKind.EMAIL,
                status=BreachResultStatus.FAILED,
                error=str(exc),
                metadata={"failure_isolated": True},
            )

        findings = [
            finding
            for row in rows
            if (finding := self._map_hibp_breach(value, row))
            is not None
        ]

        sanitized = self.data_sanitizer.sanitize(findings)
        return BreachSearchResult(
            source="hibp",
            kind=BreachQueryKind.EMAIL,
            status=BreachResultStatus.SUCCESS,
            findings=list(sanitized.value),
            metadata={
                "breaches_found": len(findings),
                "secret_fields_redacted": sanitized.redacted_count,
                "raw_credentials_returned": False,
            },
        )

    def check_password(
        self,
        password: str,
        *,
        timeout: int = 30,
    ) -> BreachSearchResult:
        if not isinstance(password, str) or not password:
            return BreachSearchResult(
                source="hibp_pwned_passwords",
                kind=BreachQueryKind.PASSWORD,
                status=BreachResultStatus.NOT_SUPPORTED,
                error="Password must not be empty.",
            )

        try:
            count = self.hibp_client.pwned_password_count(
                password,
                timeout=timeout,
            )
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            retryable = code == 429 or code >= 500
            return BreachSearchResult(
                source="hibp_pwned_passwords",
                kind=BreachQueryKind.PASSWORD,
                status=(
                    BreachResultStatus.PARTIAL
                    if retryable
                    else BreachResultStatus.FAILED
                ),
                error=f"Pwned Passwords HTTP {code}.",
                metadata={
                    "retryable": retryable,
                    "rate_limited": code == 429,
                },
            )
        except httpx.RequestError as exc:
            return BreachSearchResult(
                source="hibp_pwned_passwords",
                kind=BreachQueryKind.PASSWORD,
                status=BreachResultStatus.PARTIAL,
                error=str(exc),
                metadata={"retryable": True},
            )
        except Exception as exc:
            return BreachSearchResult(
                source="hibp_pwned_passwords",
                kind=BreachQueryKind.PASSWORD,
                status=BreachResultStatus.FAILED,
                error=str(exc),
                metadata={"failure_isolated": True},
            )

        finding = BreachFinding(
            source="hibp_pwned_passwords",
            record_id="password-exposure-check",
            subject_type="password",
            subject_value=None,
            password_exposed=count > 0,
            occurrence_count=count,
            metadata={
                "k_anonymity": True,
                "plaintext_stored": False,
                "full_hash_stored": False,
                "secret_material_present": False,
            },
        )

        return BreachSearchResult(
            source="hibp_pwned_passwords",
            kind=BreachQueryKind.PASSWORD,
            status=BreachResultStatus.SUCCESS,
            findings=[finding],
            metadata={
                "password_exposed": count > 0,
                "occurrence_count": count,
                "plaintext_stored": False,
                "full_hash_stored": False,
            },
        )

    @staticmethod
    def _map_hibp_breach(
        email: str,
        row: dict,
    ) -> BreachFinding | None:
        name = str(row.get("Name") or "").strip()
        if not name:
            return None

        classes = row.get("DataClasses")
        if not isinstance(classes, list):
            classes = []

        normalized_classes = tuple(
            str(item).strip()
            for item in classes
            if str(item).strip()
        )

        password_exposed = any(
            "password" in item.casefold()
            for item in normalized_classes
        )

        return BreachFinding(
            source="hibp",
            record_id=name,
            subject_type="email",
            subject_value=email,
            breach_name=name,
            breach_title=(
                str(row.get("Title") or "").strip()
                or None
            ),
            breach_domain=(
                str(row.get("Domain") or "").strip()
                or None
            ),
            breach_date=(
                str(row.get("BreachDate") or "").strip()
                or None
            ),
            added_date=(
                str(row.get("AddedDate") or "").strip()
                or None
            ),
            modified_date=(
                str(row.get("ModifiedDate") or "").strip()
                or None
            ),
            exposed_data_classes=normalized_classes,
            password_exposed=password_exposed,
            metadata={
                "pwn_count": row.get("PwnCount"),
                "is_verified": row.get("IsVerified"),
                "is_fabricated": row.get("IsFabricated"),
                "is_sensitive": row.get("IsSensitive"),
                "is_retired": row.get("IsRetired"),
                "is_spam_list": row.get("IsSpamList"),
                "is_malware_free": row.get("IsMalwareFree"),
                "is_subscription_free": row.get(
                    "IsSubscriptionFree"
                ),
                "description": (
                    str(row.get("Description") or "").strip()
                    or None
                ),
                # Defensive sanitizer coverage if an upstream schema or future
                # wrapper ever introduces raw secret fields.
                "raw_credentials_returned": False,
            },
        )
