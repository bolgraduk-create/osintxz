from app.database.init_db import drop_database, init_database


print("Dropping tables...")

drop_database()

print("Creating tables...")

init_database()

print("Database recreated")