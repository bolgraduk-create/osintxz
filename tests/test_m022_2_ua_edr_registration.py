from pathlib import Path


def test_service_container_registers_remote_ua_edr_provider():
    text = Path("app/core/service_container.py").read_text(encoding="utf-8")
    assert "RegistryApiHttpClient" in text
    assert "RemoteRegistryProvider" in text
    assert "UA_EDR_PROVIDER_INFO" in text
    assert "self.ua_edr_registry_provider" in text
    assert "UaEdrRepository(session)" not in text
    assert "UkraineEdrRegistryProvider(" not in text


def test_migration_extends_current_confirmed_head():
    text = Path(
        "migrations/versions/20260913_1505_add_ua_edr_registry_cache.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision = "20260902_2015"' in text
    assert "registry_ua_edr_subjects" in text
    assert "registry_ua_edr_sync_state" in text
