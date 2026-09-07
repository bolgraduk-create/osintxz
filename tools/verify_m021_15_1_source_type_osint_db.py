from __future__ import annotations

from sqlalchemy import text
import app.database.session as session_module


def main() -> int:
    engine = session_module.engine

    print("=" * 72)
    print("M021.15.1 DATABASE ENUM VERIFY")
    print("=" * 72)

    with engine.connect() as connection:
        labels = [
            row[0]
            for row in connection.execute(
                text(
                    """
                    SELECT e.enumlabel
                    FROM pg_type t
                    JOIN pg_enum e
                        ON t.oid = e.enumtypid
                    WHERE t.typname = 'source_type'
                    ORDER BY e.enumsortorder
                    """
                )
            ).all()
        ]

    for label in labels:
        print(" -", label)

    ok = "OSINT" in labels
    print(f"\nOSINT PRESENT: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
