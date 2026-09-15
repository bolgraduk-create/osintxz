from pathlib import Path
import zipfile

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.application.registry_ua_edr_sync_service import UaEdrSyncPlan, UaEdrSyncService
from app.infrastructure.registries.ukraine_edr_downloader import (
    UaEdrDatasetResources,
    UaEdrResource,
)
from app.models.registry_ua_edr import UaEdrSubject, UaEdrSyncState
from app.repositories.registry_ua_edr_repository import UaEdrRepository


def resource(name, rid):
    return UaEdrResource(
        name=name,
        resource_id=rid,
        url=f"https://data.gov.ua/dataset/x/resource/{rid}/download/{name}",
        modified_at="2026-09-08T12:00:00+03:00",
        hash_value=f"hash-{rid}",
    )


def test_generation_is_loaded_before_atomic_activation(tmp_path: Path):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    UaEdrSubject.__table__.create(engine)
    UaEdrSyncState.__table__.create(engine)
    session = Session(engine)
    repo = UaEdrRepository(session)

    old = repo.ensure_sync_state()
    old.active_generation = "old-generation"
    old.status = "ready"
    session.commit()

    uo = resource("UO.zip", "uo1")
    fop = resource("FOP.zip", "fop1")
    resources = UaEdrDatasetResources("dataset", "2026-09-08", uo, fop)
    plan = UaEdrSyncPlan(resources, resources.fingerprint, False)
    service = UaEdrSyncService(repository=repo)
    service.begin(plan)
    session.commit()

    assert repo.active_generation() == "old-generation"

    archive = tmp_path / "UO.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "UO.xml",
            '''<?xml version="1.0" encoding="utf-8"?><DATA><SUBJECT>
            <RECORD>101</RECORD><NAME>TEST COMPANY</NAME><EDRPOU>12345678</EDRPOU>
            <OPF>ТОВ</OPF><STAN>registered</STAN></SUBJECT></DATA>''',
        )

    progress = list(
        service.iter_import_zip_batches(
            archive_path=archive,
            subject_kind="company",
            generation=plan.generation,
            resource=uo,
            batch_size=1,
        )
    )
    session.commit()
    assert progress[-1].imported == 1
    assert repo.active_generation() == "old-generation"

    service.mark_ready(plan, uo_count=1, fop_count=0)
    session.commit()
    assert repo.active_generation() == plan.generation
    assert repo.search_registration_id("12345678")[0].name == "TEST COMPANY"


def test_build_plan_compares_official_fingerprint_not_local_generation():
    class Repo:
        def active_official_fingerprint(self):
            return "official-fingerprint"

    class Resources:
        fingerprint = "official-fingerprint"

    class Client:
        def resolve_latest(self, *, timeout=30):
            return Resources()

    service = UaEdrSyncService(repository=Repo(), dataset_client=Client())
    plan = service.build_plan()
    assert plan.generation == "official-fingerprint"
    assert plan.unchanged is True
