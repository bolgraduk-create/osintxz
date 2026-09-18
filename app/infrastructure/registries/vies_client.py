from __future__ import annotations

import json
from typing import Any

import httpx


class ViesServiceError(RuntimeError):
    """A structured VIES service-level error returned by the EU endpoint."""

    def __init__(self, codes: tuple[str, ...], *, messages: tuple[str, ...] = ()) -> None:
        self.codes = codes
        self.messages = messages
        details = ", ".join(codes) if codes else "UNKNOWN_VIES_ERROR"
        if messages:
            details = f"{details}: {'; '.join(messages)}"
        super().__init__(details)


class ViesRegistryHttpClient:
    """Bounded client for the European Commission VIES REST API."""

    BASE_URL = "https://ec.europa.eu/taxation_customs/vies/rest-api"
    CHECK_VAT_URL = f"{BASE_URL}/check-vat-number"
    MAX_RESPONSE_BYTES = 2_000_000

    def __init__(self, *, transport=None, user_agent: str = "OSINTXZ/1.0 RegistryIntelligence") -> None:
        self.transport = transport
        self.user_agent = user_agent

    def _client(self, timeout: int) -> httpx.Client:
        return httpx.Client(
            timeout=httpx.Timeout(float(timeout)),
            transport=self.transport,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    def check_vat(self, country_code: str, vat_number: str, *, timeout: int = 30) -> dict[str, Any]:
        country_code = country_code.strip().upper()
        vat_number = vat_number.strip().upper()
        if len(country_code) != 2 or not country_code.isalpha():
            raise ValueError("VIES country_code must be a two-letter code.")
        if not vat_number or not vat_number.isalnum():
            raise ValueError("VIES vat_number must be alphanumeric and must not include the country prefix.")

        body = {"countryCode": country_code, "vatNumber": vat_number}

        with self._client(timeout) as client:
            with client.stream(
                "POST",
                self.CHECK_VAT_URL,
                json=body,
                headers={"Accept-Encoding": "identity"},
            ) as response:
                if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                    raise ValueError("Unexpected registry HTTP content encoding.")

                raw = bytearray()
                for chunk in response.iter_bytes(chunk_size=65536):
                    if len(raw) + len(chunk) > self.MAX_RESPONSE_BYTES:
                        raise ValueError("Registry response exceeds download limit.")
                    raw.extend(chunk)

                try:
                    result = json.loads(raw)
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    response.raise_for_status()
                    raise ValueError("VIES response must be valid JSON.") from exc

                if not isinstance(result, dict):
                    response.raise_for_status()
                    raise ValueError("VIES response must be a JSON object.")

                if result.get("actionSucceed") is False:
                    codes: list[str] = []
                    messages: list[str] = []
                    wrappers = result.get("errorWrappers")
                    if isinstance(wrappers, list):
                        for wrapper in wrappers:
                            if not isinstance(wrapper, dict):
                                continue
                            code = str(wrapper.get("error") or "").strip()
                            message = str(wrapper.get("message") or "").strip()
                            if code:
                                codes.append(code)
                            if message:
                                messages.append(message)
                    raise ViesServiceError(
                        tuple(codes) or ("UNKNOWN_VIES_ERROR",),
                        messages=tuple(messages),
                    )

                response.raise_for_status()

        return result
