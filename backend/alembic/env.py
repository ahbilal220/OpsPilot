import asyncio

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.agents.models import Diagnosis, Hypothesis  # noqa: F401
from app.audit.models import AuditEvent  # noqa: F401
from app.auth.models import User  # noqa: F401
from app.core.config import Settings
from app.db.base import Base
from app.evidence.models import Evidence  # noqa: F401
from app.incidents.models import Incident, Service  # noqa: F401
from app.investigations.models import Investigation  # noqa: F401
from app.providers.models import ModelExecution  # noqa: F401
from app.tools.models import ToolExecution  # noqa: F401


def migrate(connection):  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def online() -> None:
    engine = create_async_engine(
        Settings().database_url.get_secret_value(), poolclass=pool.NullPool
    )
    async with engine.connect() as connection:
        await connection.run_sync(migrate)
    await engine.dispose()


if context.is_offline_mode():
    context.configure(
        url=Settings().database_url.get_secret_value(),
        target_metadata=Base.metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(online())
