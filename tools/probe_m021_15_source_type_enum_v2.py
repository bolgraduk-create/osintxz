from sqlalchemy import text
from sqlalchemy.engine import Engine

import app.database.session as session_module

print("=" * 72)
print("M021.15 SOURCE TYPE ENUM PROBE v2")
print("=" * 72)

print("\nDATABASE SESSION MODULE:")
print("module:", session_module.__file__)

interesting = []

for name in dir(session_module):
    if name.startswith("_"):
        continue

    value = getattr(
        session_module,
        name,
    )

    if (
        "session" in name.casefold()
        or "engine" in name.casefold()
    ):
        interesting.append(
            (
                name,
                type(value).__name__,
            )
        )

for name, type_name in interesting:
    print(
        f" - {name}: {type_name}"
    )

engine = None

for name in dir(session_module):
    value = getattr(
        session_module,
        name,
    )

    if isinstance(
        value,
        Engine,
    ):
        engine = value
        print(
            f"\nENGINE FOUND: {name}"
        )
        break

if engine is None:
    print(
        "\nENGINE NOT FOUND IN app.database.session"
    )
else:
    print(
        "\nDATABASE ENUM source_type:"
    )

    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT
                    e.enumsortorder,
                    e.enumlabel
                FROM pg_type t
                JOIN pg_enum e
                    ON t.oid = e.enumtypid
                WHERE t.typname = 'source_type'
                ORDER BY e.enumsortorder
                """
            )
        ).all()

    if not rows:
        print(
            " - ENUM source_type NOT FOUND"
        )
    else:
        for order, label in rows:
            print(
                f" - {order}: {label}"
            )

print(
    "\nPYTHON SourceType:"
)

try:
    from app.models.source import SourceType
except Exception as exc:
    print(
        "SOURCE TYPE IMPORT ERROR:",
        repr(exc),
    )
else:
    for item in SourceType:
        print(
            f" - {item.name} = {item.value}"
        )

print("\nPROBE COMPLETE")
