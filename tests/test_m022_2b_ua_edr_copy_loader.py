from pathlib import Path
import zipfile

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.application.registry_ua_edr_sync_service import UaEdrSyncService
from app.models.registry_ua_edr import UaEdrSubject, UaEdrSyncState
from app.repositories.registry_ua_edr_repository import UaEdrRepository
from app.infrastructure.registries.ukraine_edr_downloader import UaEdrResource


def _resource():
    return UaEdrResource(
        name="UO.zip",
        resource_id="uo-test",
        url="https://data.gov.ua/example/UO.zip",
        modified_at="2026-09-13T12:00:00+03:00",
        hash_value="test-hash",
    )


def test_auto_mode_keeps_portable_sqlalchemy_fallback_on_sqlite(tmp_path: Path):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    UaEdrSubject.__table__.create(engine)
    UaEdrSyncState.__table__.create(engine)
    session = Session(engine)
    repo = UaEdrRepository(session)
    service = UaEdrSyncService(repository=repo)

    assert repo.supports_postgres_copy() is False
    assert service.resolve_write_mode("auto") == "sqlalchemy"

    archive = tmp_path / "UO.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "UO.xml",
            """<?xml version='1.0' encoding='utf-8'?><DATA><SUBJECT>
            <RECORD>1</RECORD><NAME>TEST</NAME><EDRPOU>12345678</EDRPOU>
            </SUBJECT></DATA>""",
        )

    progress = list(
        service.iter_import_zip_batches(
            archive_path=archive,
            subject_kind="company",
            generation="g1",
            resource=_resource(),
            batch_size=1,
            write_mode="auto",
        )
    )
    assert progress[-1].write_mode == "sqlalchemy"


def test_explicit_copy_rejects_non_postgres_database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    session = Session(engine)
    service = UaEdrSyncService(repository=UaEdrRepository(session))

    try:
        service.resolve_write_mode("copy")
    except RuntimeError as exc:
        assert "not PostgreSQL" in str(exc)
    else:
        raise AssertionError("copy mode must reject a non-PostgreSQL bind")


class _FakeCopy:
    def __init__(self, sql):
        self.sql = sql
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def write_row(self, row):
        self.rows.append(row)


class _FakeCursor:
    def __init__(self):
        self.copy_context = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def copy(self, sql):
        self.copy_context = _FakeCopy(sql)
        return self.copy_context


class _FakeDriverConnection:
    def __init__(self):
        self.cursor_instance = _FakeCursor()

    def cursor(self):
        return self.cursor_instance


class _FakeProxiedConnection:
    def __init__(self, driver):
        self.driver_connection = driver


class _FakeSaConnection:
    def __init__(self, driver):
        self.connection = _FakeProxiedConnection(driver)


class _FakeDialect:
    name = "postgresql"


class _FakeBind:
    dialect = _FakeDialect()


class _FakePostgresSession:
    def __init__(self):
        self.driver = _FakeDriverConnection()
        self.sa_connection = _FakeSaConnection(self.driver)

    def get_bind(self):
        return _FakeBind()

    def connection(self):
        return self.sa_connection


def test_postgres_copy_writes_static_columns_and_supplies_uuid_primary_key():
    session = _FakePostgresSession()
    repo = UaEdrRepository(session)
    row = {
        "generation": "g1",
        "subject_kind": "company",
        "record_id": "101",
        "name": "TEST COMPANY",
        "name_normalized": "TEST COMPANY",
        "registration_id": "12345678",
        "family_farm": None,
    }

    assert repo.supports_postgres_copy() is True
    assert repo.copy_insert([row]) == 1

    copy_context = session.driver.cursor_instance.copy_context
    assert copy_context is not None
    assert copy_context.sql.startswith("COPY registry_ua_edr_subjects (")
    assert "id, generation, subject_kind" in copy_context.sql
    assert len(copy_context.rows) == 1
    written = copy_context.rows[0]
    assert str(written[0])  # UUID generated for BaseModel primary key
    assert written[1:6] == (
        "g1",
        "company",
        "101",
        "TEST COMPANY",
        "TEST COMPANY",
    )
    assert written[7] == "12345678"
