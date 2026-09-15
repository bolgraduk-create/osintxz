"""Non-destructive Registry Backend health probe."""
from __future__ import annotations

from app.core.config import settings
from app.infrastructure.registries.registry_api_client import RegistryApiHttpClient


if __name__ == "__main__":
    token = (
        settings.registry_api_token.get_secret_value()
        if settings.registry_api_token is not None
        else None
    )
    client = RegistryApiHttpClient(
        base_url=settings.registry_api_url,
        token=token,
        default_timeout=settings.registry_api_timeout,
    )
    try:
        print(client.health())
    finally:
        client.close()
