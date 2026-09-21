from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, Signal, Slot

from app.core.config import settings


class AnalysisProviderDiscoveryWorker(QObject):
    """Discover local Analysis provider availability without blocking QML."""

    succeeded = Signal(object)
    failed = Signal(object)

    @Slot()
    def run(self) -> None:
        configured_model = str(
            settings.ollama_model
            or settings.ai_model
            or settings.default_model
            or ""
        ).strip()

        models: list[str] = []
        if configured_model:
            models.append(configured_model)

        payload = {
            "ollamaOnline": False,
            "ollamaModels": models,
            "ollamaError": "",
        }

        base_url = str(settings.ollama_url or "").strip().rstrip("/")
        if not base_url:
            self.succeeded.emit(payload)
            return

        try:
            request = Request(
                base_url + "/api/tags",
                headers={"Accept": "application/json"},
                method="GET",
            )
            with urlopen(request, timeout=2.0) as response:
                data = json.loads(response.read().decode("utf-8"))

            discovered: list[str] = []
            for item in list(data.get("models") or []):
                if not isinstance(item, dict):
                    continue
                name = str(
                    item.get("name")
                    or item.get("model")
                    or ""
                ).strip()
                if name and name not in discovered:
                    discovered.append(name)

            if configured_model and configured_model not in discovered:
                discovered.insert(0, configured_model)

            payload["ollamaOnline"] = True
            payload["ollamaModels"] = discovered or models
        except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            payload["ollamaError"] = str(exc)

        self.succeeded.emit(payload)
