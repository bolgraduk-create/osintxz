from sqlalchemy import text

from app.database.session import engine


with engine.connect() as conn:

    conn.execute(
        text(
            "CREATE SCHEMA IF NOT EXISTS public;"
        )
    )

    conn.commit()


print("Schema restored")