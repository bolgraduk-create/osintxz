"""Run the Registry Backend ASGI process."""
from __future__ import annotations

import uvicorn

from app.registry_backend.settings import backend_settings


def main() -> None:
    uvicorn.run(
        "app.registry_backend.api:app",
        host=backend_settings.host,
        port=backend_settings.port,
        reload=False,
        proxy_headers=True,
    )


if __name__ == "__main__":
    main()
