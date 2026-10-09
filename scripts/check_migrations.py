"""Round-trip migrations on a separate, pre-created disposable PostgreSQL database.

Run from backend (/app in its container). DATABASE_URL is inherited from the app;
only its database name is replaced. Never runs against the application's database.
"""
import os

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

url = make_url(os.environ["DATABASE_URL"])
test_database = "opspilot_migration_check"
if url.database == test_database:
    raise RuntimeError("Provide the application URL; the script chooses a separate test database")
os.environ["DATABASE_URL"] = url.set(database=test_database).render_as_string(hide_password=False)
config = Config("alembic.ini")
command.upgrade(config, "head")
command.check(config)
command.downgrade(config, "base")
command.upgrade(config, "head")
command.check(config)
print("PASS: PostgreSQL migration upgrade, schema comparison, downgrade, re-upgrade")
