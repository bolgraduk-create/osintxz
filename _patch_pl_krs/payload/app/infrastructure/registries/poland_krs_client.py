from __future__ import annotations

import json
from typing import Any

import httpx


class PolandKrsHttpClient:
    """Bounded client for the official Polish KRS Open API."""

    BASE_URL = "https://api-krs.ms.gov.pl/api/krs"
    MAX_RESPONSE_BYTES = 6_000_000

    def __init__(
        self,
        *,
        transport=None,
        user_agent: str = "OSINTXZ/1.0 RegistryIntelligence",
    ) -> None:
        self.transport = transport
        self.user_agent = user_agent

    def get_current_extract(
        self,
        krs_number: str,
        *,
        register: str,
        timeout: int = 30,
    ) -> dict[str, Any]:
        register = register.strip().upper()
        if register not in {"P", "S"}:
            raise ValueError("KRS register must be P or S.")

        url = f"{self.BASE_URL}/OdpisAktualny/{krs_number}"
        return self._get(
            url,
            params={"rejestr": register, "format": "json"},
            timeout=timeout,
        )

    def _get(
        self,
        url: str,
        *,
        params: dict[str, str],
        timeout: int,
    ) -> dict[str, Any]:
        with httpx.Client(
            timeout=httpx.Timeout(float(timeout)),
            transport=self.transport,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            },
        ) as client:
            with client.stream(
                "GET",
                url,
                params=params,
                headers={"Accept-Encoding": "identity"},
            ) as response:
                if response.headers.get(
                    "Content-Encoding", "identity"
                ).lower() != "identity":
                    raise ValueError(
                        "Unexpected registry HTTP content encoding."
                    )

                body = bytearray()
                for chunk in response.iter_bytes(chunk_size=65536):
                    if len(body) + len(chunk) > self.MAX_RESPONSE_BYTES:
                        raise ValueError(
                            "Registry response exceeds download limit."
                        )
                    body.extend(chunk)

                response.raise_for_status()

        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(
                "KRS response must be valid JSON."
            ) from exc

        if not isinstance(payload, dict):
            raise ValueError(
                "KRS response must be a JSON object."
            )
        return payload
