"""SERVER-SIDE ONLY: synchronize Ukraine EDR for OSINTXZ Registry Backend."""
from __future__ import annotations

import argparse
from pathlib import Path
from time import perf_counter
import sys
from uuid import uuid4

from app.application.registry_ua_edr_sync_service import UaEdrSyncPlan, UaEdrSyncService
from app.database.session import create_session
from app.infrastructure.registries.ukraine_edr_downloader import UaEdrDatasetClient
from app.repositories.registry_ua_edr_repository import UaEdrRepository


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-dir",
        default="storage/cache/registry/ua_edr",
        help="Server-side directory for downloaded official ZIP resources.",
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
        help="auto uses PostgreSQL COPY when available; SQLAlchemy is a portable fallback.",
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
        "OSINTXZ Registry Backend ingestion — server-side infrastructure only; "
        "end-user desktops must not run this command."
    )
    if args.batch_size < 1:
        print("--batch-size must be at least 1", file=sys.stderr)
        return 2

    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    session = create_session()
    repository = UaEdrRepository(session)
    dataset_client = UaEdrDatasetClient()
    service = UaEdrSyncService(repository=repository, dataset_client=dataset_client)
    plan = None
    activated = False

    try:
        resolved_mode = service.resolve_write_mode(args.write_mode)
        print(f"Database loader: {resolved_mode}")

        plan = service.build_plan()
        print(f"EDR generation: {plan.generation}")
        print(f"Dataset: {plan.resources.dataset_id}")
        if plan.unchanged and not args.force:
            print("Ukraine EDR mirror is already up to date.")
            return 0
        if plan.unchanged and args.force:
            # Rebuild into a distinct generation so the active mirror remains
            # queryable until the forced rebuild is fully complete.
            plan = UaEdrSyncPlan(
                resources=plan.resources,
                generation=f"{plan.resources.fingerprint[:24]}-{uuid4().hex[:8]}",
                unchanged=False,
            )
            print(f"Forced rebuild generation: {plan.generation}")

        service.begin(plan)
        session.commit()

        downloads = {}
        for kind, resource in (("company", plan.resources.uo), ("sole_trader", plan.resources.fop)):
            target = cache_dir / f"{plan.generation}-{resource.name}"
            print(f"Downloading {resource.name} ...")
            downloaded = dataset_client.download(resource, target)
            downloads[kind] = downloaded
            print(f"  {downloaded.size_bytes:,} bytes; sha256={downloaded.sha256}")

        counts = {"company": 0, "sole_trader": 0}
        for kind, resource in (("company", plan.resources.uo), ("sole_trader", plan.resources.fop)):
            print(f"Importing {resource.name} ...")
            started = perf_counter()
            for progress in service.iter_import_zip_batches(
                archive_path=downloads[kind].path,
                subject_kind=kind,
                generation=plan.generation,
                resource=resource,
                batch_size=args.batch_size,
                write_mode=resolved_mode,
            ):
                counts[kind] = progress.imported
                session.commit()  # server ingestion command owns bounded commits
                elapsed = max(perf_counter() - started, 0.001)
                rate = progress.imported / elapsed
                print(
                    f"  {kind}: {progress.imported:,} "
                    f"({rate:,.0f} rows/s, {progress.write_mode})",
                    flush=True,
                )

        # Activation is a separate durable transaction. The previous active
        # generation stayed queryable throughout parsing/COPY.
        service.mark_ready(
            plan,
            uo_count=counts["company"],
            fop_count=counts["sole_trader"],
        )
        session.commit()
        activated = True

        removed = 0
        try:
            removed = service.cleanup_old_generations(plan.generation)
            session.commit()
        except Exception as cleanup_error:
            # Cleanup is not part of activation correctness. Keep the newly
            # activated generation and remove stale rows on a later server job.
            session.rollback()
            print(f"Warning: old EDR generation cleanup failed: {cleanup_error}", file=sys.stderr)

        print(
            "Ukraine EDR mirror ready: "
            f"companies={counts['company']:,}; sole_traders={counts['sole_trader']:,}; "
            f"old_rows_removed={removed:,}"
        )
        return 0
    except KeyboardInterrupt:
        session.rollback()
        if plan is not None and not activated:
            repository.delete_generation(plan.generation)
            service.mark_failed(plan, "Interrupted by server operator")
            session.commit()
        print("EDR sync interrupted; previous active generation remains unchanged.", file=sys.stderr)
        return 130
    except Exception as exc:
        session.rollback()
        if plan is not None and not activated:
            try:
                repository.delete_generation(plan.generation)
                service.mark_failed(plan, exc)
                session.commit()
            except Exception:
                session.rollback()
        print(f"EDR sync failed: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
