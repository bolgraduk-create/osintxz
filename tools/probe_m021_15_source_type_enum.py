from sqlalchemy import text

from app.core.service_container import ServiceContainer
from app.database.session import SessionLocal

print("=" * 72)
print("M021.15 SOURCE TYPE ENUM PROBE")
print("=" * 72)

session = SessionLocal()

try:
    print("\nDATABASE ENUM source_type:")

    rows = session.execute(
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

    for row in rows:
        print(" -", row[0])

    print("\nSOURCE MODEL ENUM:")

    from app.models.source import SourceType

    for item in SourceType:
        print(
            " -",
            item.name,
            "=",
            item.value,
        )

finally:
    session.close()
