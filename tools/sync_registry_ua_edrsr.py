"""SERVER-SIDE ONLY: synchronize one Ukraine EDRSR yearly archive."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
import sys
from uuid import uuid4

from app.application.registry_ua_edrsr_sync_service import (
    UaEdrsrSyncPlan,
    UaEdrsrSyncService,
)
from app.infrastructure.registries.ukraine_edrsr_downloader import UaEdrsrDatasetClient
from app.registry_backend.database import create_registry_ingestion_session
from app.repositories.registry_ua_edrsr_repository import UaEdrsrRepository


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--year",
        type=int,
        default=datetime.now(timezone.utc).year,
        help="EDRSR source year to synchronize. Defaults to the current UTC year.",
    )
    parser.add_argument(
        "--cache-dir",
        default="storage/cache/registry/ua_edrsr",
        help="Server-side directory for downloaded official yearly ZIP resources.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50_000,
        help="Rows per bounded transaction. COPY defaults to 50,000.",
    )
    parser.add_argument(
        "--write-mode",
        choices=("auto", "copy", "sqlalchemy"),
        default="auto",
        help="auto uses PostgreSQL COPY when available; SQLAlchemy is the portable fallback.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild even when the current official fingerprint is already active.",
    )
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    print(
        "OSINTXZ Registry Backend EDRSR ingestion — server-side infrastructure only; "
        "end-user desktops must not run this command."
    )
    if args.batch_size < 1:
        print("--batch-size must be at least 1", file=sys.stderr)
        return 2

    cache_dir = Path(args.cache_dir) / str(args.year)
    cache_dir.mkdir(parents=True, exist_ok=True)

    session = create_registry_ingestion_session()
    repository = UaEdrsrRepository(session)
    dataset_client = UaEdrsrDatasetClient()
    service = UaEdrsrSyncService(repository=repository, dataset_client=dataset_client)
    plan: UaEdrsrSyncPlan | None = None
    activated = False

    try:
        resolved_mode = service.resolve_write_mode(args.write_mode)
        print(f"Database loader: {resolved_mode}")

        plan = service.build_plan(dataset_year=args.year)
        print(f"EDRSR year: {plan.dataset_year}")
        print(f"Generation: {plan.generation}")
        print(f"Dataset: {plan.resources.dataset_id}")
        print(f"Resource: {plan.resources.resource.resource_id}")

        if plan.unchanged and not args.force:
            print(f"Ukraine EDRSR {plan.dataset_year} mirror is already up to date.")
            return 0
        if plan.unchanged and args.force:
            plan = UaEdrsrSyncPlan(
                dataset_year=plan.dataset_year,
                resources=plan.resources,
                generation=f"{plan.resources.fingerprint[:24]}-{uuid4().hex[:8]}",
                unchanged=False,
            )
            print(f"Forced rebuild generation: {plan.generation}")

        service.begin(plan)
        session.commit()

        resource = plan.resources.resource
        target = cache_dir / resource.name
        print(f"Downloading {resource.name} ...")
        downloaded = dataset_client.download(resource, target)
        print(f"  {downloaded.size_bytes:,} bytes; sha256={downloaded.sha256}")

        count = 0
        started = perf_counter()
        print(f"Importing EDRSR {plan.dataset_year} ...")
        for progress in service.iter_import_zip_batches(
            archive_path=downloaded.path,
            plan=plan,
            source_hash=downloaded.sha256,
            batch_size=args.batch_size,
            write_mode=resolved_mode,
        ):
            count = progress.imported
            session.commit()
            elapsed = max(perf_counter() - started, 0.001)
            rate = progress.imported / elapsed
            print(
                f"  decisions: {progress.imported:,} "
                f"({rate:,.0f} rows/s, {progress.write_mode})",
                flush=True,
            )

        service.mark_ready(plan, record_count=count, source_hash=downloaded.sha256)
        session.commit()
        activated = True

        removed = 0
        try:
            removed = service.cleanup_old_generations(plan)
            session.commit()
        except Exception as cleanup_error:
            session.rollback()
            print(
                f"Warning: old EDRSR generation cleanup failed: {cleanup_error}",
                file=sys.stderr,
            )

        print(
            f"Ukraine EDRSR {plan.dataset_year} mirror ready: "
            f"decisions={count:,}; old_rows_removed={removed:,}"
        )
        return 0
    except KeyboardInterrupt:
        session.rollback()
        if plan is not None and not activated:
            repository.delete_generation(plan.dataset_year, plan.generation)
            service.mark_failed(plan, "Interrupted by server operator")
            session.commit()
        print(
            "EDRSR sync interrupted; previous active yearly generation remains unchanged.",
            file=sys.stderr,
        )
        return 130
    except Exception as exc:
        session.rollback()
        if plan is not None and not activated:
            try:
                repository.delete_generation(plan.dataset_year, plan.generation)
                service.mark_failed(plan, exc)
                session.commit()
            except Exception:
                session.rollback()
        print(f"EDRSR sync failed: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
