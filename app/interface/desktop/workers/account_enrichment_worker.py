from __future__ import annotations

from time import perf_counter
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from app.osint.connectors.maigret_connector import MaigretConnector


class AccountEnrichmentWorker(QObject):
    """Analyst-triggered deep enrichment for one already discovered account."""

    succeeded = Signal(object)
    failed = Signal(object)

    _SKIP_KEYS = {
        "html", "body", "headers", "cookies", "cookie", "response",
        "request", "raw", "raw_data", "page_content", "content",
    }
    _PRIORITY_TOKENS = (
        "name", "username", "user", "id", "bio", "about", "description",
        "avatar", "image", "photo", "location", "city", "country",
        "website", "url", "link", "email", "phone", "followers",
        "following", "created", "joined", "verified",
    )

    def __init__(
        self,
        *,
        username: str,
        site: str,
        profile_url: str = "",
        timeout: int = 25,
    ) -> None:
        super().__init__()
        self.username = str(username or "").strip().lstrip("@")
        self.site = str(site or "").strip()
        self.profile_url = str(profile_url or "").strip()
        self.timeout = max(5, int(timeout or 25))

    @Slot()
    def run(self) -> None:
        started = perf_counter()
        try:
            if not self.username:
                raise ValueError("Username is required for account enrichment.")
            if not self.site:
                raise ValueError("A Maigret site name is required for account enrichment.")

            result = MaigretConnector().deep_enrich(
                username=self.username,
                site=self.site,
                timeout=self.timeout,
            )
            snapshot = self._snapshot_result(result)
            duration = perf_counter() - started

            if result.success:
                self.succeeded.emit(
                    {
                        "snapshot": snapshot,
                        "duration": duration,
                    }
                )
                return

            self.failed.emit(
                {
                    "snapshot": snapshot,
                    "duration": duration,
                    "error": str(result.error or "Account enrichment failed."),
                }
            )
        except Exception as exc:
            self.failed.emit(
                {
                    "snapshot": {
                        "username": self.username,
                        "site": self.site,
                        "profileUrl": self.profile_url,
                        "connector": "Maigret",
                        "status": "failed",
                        "fields": [],
                        "observations": [],
                        "error": str(exc),
                    },
                    "duration": perf_counter() - started,
                    "error": str(exc),
                }
            )

    def _snapshot_result(self, result: Any) -> dict[str, Any]:
        observations: list[dict[str, Any]] = []
        all_metadata: list[dict[str, Any]] = []

        for finding in list(getattr(result, "findings", ()) or ()):
            metadata = getattr(finding, "metadata", None)
            metadata = self._public_value(metadata) if isinstance(metadata, dict) else {}
            if isinstance(metadata, dict):
                all_metadata.append(metadata)
            observations.append(
                {
                    "source": str(getattr(finding, "source", "") or self.site),
                    "url": str(getattr(finding, "url", "") or self.profile_url),
                    "value": str(getattr(finding, "value", "") or self.username),
                    "confidence": self._safe_optional_float(
                        getattr(finding, "confidence", None)
                    ),
                    "reliability": self._safe_optional_float(
                        getattr(finding, "reliability", None)
                    ),
                    "metadata": metadata if isinstance(metadata, dict) else {},
                }
            )

        fields = self._extract_fields(all_metadata)
        raw_data = self._public_value(getattr(result, "raw_data", None))
        result_metadata = self._public_value(getattr(result, "metadata", None))

        return {
            "username": self.username,
            "site": self.site,
            "profileUrl": self.profile_url,
            "connector": str(getattr(result, "connector", "") or "Maigret"),
            "status": str(
                getattr(getattr(result, "status", None), "value", None)
                or getattr(result, "status", "")
                or "unknown"
            ),
            "error": str(getattr(result, "error", "") or ""),
            "executionTime": self._safe_float(
                getattr(result, "execution_time", 0.0)
            ),
            "fields": fields,
            "observations": observations,
            "rawData": raw_data,
            "resultMetadata": (
                result_metadata if isinstance(result_metadata, dict) else {}
            ),
        }

    @classmethod
    def _extract_fields(
        cls,
        metadata_items: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        flattened: list[tuple[str, str]] = []
        for metadata in metadata_items:
            cls._flatten(metadata, flattened, path="", depth=0)

        seen: set[tuple[str, str]] = set()
        fields: list[dict[str, str]] = []
        for path, value in flattened:
            normalized = (path.casefold(), value.casefold())
            if normalized in seen:
                continue
            seen.add(normalized)
            fields.append(
                {
                    "key": path,
                    "label": cls._field_label(path),
                    "value": value,
                }
            )

        fields.sort(
            key=lambda item: (
                cls._field_priority(item["key"]),
                item["label"].casefold(),
                item["value"].casefold(),
            )
        )
        return fields[:80]

    @classmethod
    def _flatten(
        cls,
        value: Any,
        output: list[tuple[str, str]],
        *,
        path: str,
        depth: int,
    ) -> None:
        if value is None or depth > 4 or len(output) >= 160:
            return

        if isinstance(value, dict):
            for key, child in list(value.items())[:100]:
                key_text = str(key or "").strip()
                if not key_text or key_text.casefold() in cls._SKIP_KEYS:
                    continue
                child_path = f"{path}.{key_text}" if path else key_text
                cls._flatten(
                    child,
                    output,
                    path=child_path,
                    depth=depth + 1,
                )
            return

        if isinstance(value, (list, tuple, set, frozenset)):
            values = list(value)[:30]
            if values and all(
                not isinstance(item, (dict, list, tuple, set, frozenset))
                for item in values
            ):
                text = ", ".join(
                    str(item).strip()
                    for item in values
                    if str(item).strip()
                )
                if text and path:
                    output.append((path, text[:700]))
                return
            for index, child in enumerate(values):
                cls._flatten(
                    child,
                    output,
                    path=f"{path}[{index}]" if path else f"[{index}]",
                    depth=depth + 1,
                )
            return

        text = " ".join(str(value).split()).strip()
        if not text or not path:
            return
        if len(text) > 700:
            text = text[:697] + "..."
        output.append((path, text))

    @classmethod
    def _field_priority(cls, key: str) -> int:
        lowered = str(key or "").casefold()
        for index, token in enumerate(cls._PRIORITY_TOKENS):
            if token in lowered:
                return index
        return len(cls._PRIORITY_TOKENS) + 5

    @staticmethod
    def _field_label(path: str) -> str:
        tail = str(path or "").split(".")[-1]
        tail = tail.replace("_", " ").replace("-", " ")
        return " ".join(part.capitalize() for part in tail.split()) or path

    @classmethod
    def _public_value(
        cls,
        value: Any,
        *,
        depth: int = 0,
    ) -> Any:
        if depth > 5:
            return None
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            out: dict[str, Any] = {}
            for key, child in list(value.items())[:120]:
                key_text = str(key or "")
                if key_text.casefold() in cls._SKIP_KEYS:
                    continue
                out[key_text] = cls._public_value(
                    child,
                    depth=depth + 1,
                )
            return out
        if isinstance(value, (list, tuple, set, frozenset)):
            return [
                cls._public_value(item, depth=depth + 1)
                for item in list(value)[:80]
            ]
        return str(value)

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _safe_optional_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
