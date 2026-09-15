from __future__ import annotations

from pathlib import Path
import zipfile

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.application.registry_ua_edrsr_sync_service import (
    UaEdrsrSyncPlan,
    UaEdrsrSyncService,
)
from app.infrastructure.registries.ukraine_edrsr_downloader import (
    UaEdrsrDatasetResources,
    UaEdrsrResource,
)
from app.models.registry_ua_edrsr import UaEdrsrDecision, UaEdrsrSyncState
from app.repositories.registry_ua_edrsr_repository import UaEdrsrRepository


def _plan() -> UaEdrsrSyncPlan:
    resource = UaEdrsrResource(
        name="edrsr_data_2026.zip",
        resource_id="r1",
        url="https://data.gov.ua/example/edrsr_data_2026.zip",
        modified_at="2026-09-13T06:15:00+03:00",
        hash_value="12dc69e4fac79392021714bc1d7857c5",
    )
    resources = UaEdrsrDatasetResources(
        dataset_year=2026,
        dataset_id="d1",
        dataset_name="edrsr-2026",
        modified_at="2026-09-13T06:17:00+03:00",
        resource=resource,
    )
    return UaEdrsrSyncPlan(2026, resources, resources.fingerprint, False)


def test_auto_mode_uses_portable_sqlalchemy_loader_on_sqlite(tmp_path: Path):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    UaEdrsrDecision.__table__.create(engine)
    UaEdrsrSyncState.__table__.create(engine)
    session = Session(engine)
    repository = UaEdrsrRepository(session)
    service = UaEdrsrSyncService(repository=repository)
    assert service.resolve_write_mode("auto") == "sqlalchemy"

    archive_path = tmp_path / "edrsr.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "documents.csv",
            (
                "doc_id\tcourt_code\tjudgment_code\tjustice_kind\tcategory_code\t"
                "cause_num\tadjudication_date\treceipt_date\tjudge\tdoc_url\tstatus\tdate_publ\n"
                "195\t5014\t5\t3\t4047\t19/273\t2006-06-01 00:00:00\t"
                "2006-06-05 00:00:00\tJudge\thttps://example.test/195\t1\t2007-08-22 00:00:00\n"
            ).encode("utf-8"),
        )
        archive.writestr(
            "courts.csv",
            "court_code\tname\tinstance_code\tregion_code\n5014\tCourt\t1\t44\n".encode("utf-8"),
        )

    progress = list(
        service.iter_import_zip_batches(
            archive_path=archive_path,
            plan=_plan(),
            source_hash="sha256-test",
            batch_size=1,
            write_mode="auto",
        )
    )
    assert progress[-1].imported == 1
    assert progress[-1].write_mode == "sqlalchemy"
    row = session.query(UaEdrsrDecision).one()
    assert row.doc_id == 195
    assert row.cause_num_normalized == "19/273"
    assert row.source_hash == "sha256-test"


def test_explicit_copy_rejects_non_postgres_database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    session = Session(engine)
    service = UaEdrsrSyncService(repository=UaEdrsrRepository(session))
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


def test_postgres_copy_has_static_columns_and_uuid_primary_key():
    session = _FakePostgresSession()
    repository = UaEdrsrRepository(session)
    assert repository.copy_insert([
        {
            "dataset_year": 2026,
            "generation": "g1",
            "doc_id": 195,
            "cause_num": "19/273",
            "cause_num_normalized": "19/273",
        }
    ]) == 1
    copy_context = session.driver.cursor_instance.copy_context
    assert copy_context.sql.startswith("COPY registry_ua_edrsr_decisions (")
    assert "id, dataset_year, generation, doc_id" in copy_context.sql
    written = copy_context.rows[0]
    assert str(written[0])
    assert written[1:4] == (2026, "g1", 195)
