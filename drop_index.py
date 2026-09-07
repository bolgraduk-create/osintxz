from sqlalchemy import text

from app.database.session import engine


with engine.connect() as conn:
    conn.execute(
        text("DROP INDEX IF EXISTS ix_sources_status;")
    )
    conn.commit()

print("Index removed")