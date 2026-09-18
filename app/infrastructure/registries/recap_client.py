from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.infrastructure.registries.courtlistener_client import (
    CourtListenerCredentialsError,
    CourtListenerHttpClient,
)


class PacerPaidAccessBlockedError(RuntimeError):
    """Raised when code attempts to initiate a paid PACER fetch automatically."""


@dataclass(frozen=True, slots=True)
class PacerPaidFetchGuard:
    """Hard safety boundary: R11 never initiates paid PACER retrieval."""

    automatic_paid_fetch_enabled: bool = False

    def authorize(
        self,
        *,
        explicit_user_confirmation: bool,
        authorized_budget_usd: Decimal | float | str | None,
    ) -> None:
        if authorized_budget_usd is not None:
            try:
                budget = Decimal(str(authorized_budget_usd))
            except (InvalidOperation, ValueError) as exc:
                raise ValueError("authorized_budget_usd must be numeric.") from exc
            if budget < 0:
                raise ValueError("authorized_budget_usd must not be negative.")

        note = (
            " Explicit confirmation was supplied, but paid PACER access remains hard-blocked in R11."
            if explicit_user_confirmation
            else " No explicit user confirmation was supplied."
        )
        raise PacerPaidAccessBlockedError(
            "Paid PACER retrieval is disabled. OSINTXZ R11 only searches data already available in the RECAP archive."
            + note
        )


class CourtListenerRecapHttpClient(CourtListenerHttpClient):
    """CourtListener v4 search client for existing RECAP/PACER dockets only."""

    def search_recap_dockets(
        self,
        value: str,
        *,
        field: str,
        limit: int = 20,
        timeout: int = 30,
    ) -> dict:
        if not self.configured:
            raise CourtListenerCredentialsError(
                "CourtListener API token is not configured."
            )
        if field not in {"caseName", "docketNumber"}:
            raise ValueError("Unsupported RECAP docket search field.")

        query_value = self._quoted_search_value(value)
        payload = self._get(
            self.SEARCH_URL,
            params={"type": "d", "q": f'{field}:"{query_value}"'},
            timeout=timeout,
        )
        results = payload.get("results")
        if isinstance(results, list):
            bounded = max(1, min(int(limit), 100))
            if len(results) > bounded:
                payload = dict(payload)
                payload["results"] = results[:bounded]
        return payload
