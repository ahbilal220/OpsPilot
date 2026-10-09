import pytest
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from alembic import command
from app.core.config import Settings
from app.main import create_app


class MemoryRedis:
    def __init__(self):
        self.values = {}
        self.ttls = {}
        self.attempts = 0

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, ex):
        self.values[key] = value
        self.ttls[key] = ex

    async def delete(self, key):
        self.values.pop(key, None)

    async def ping(self):
        return True

    async def eval(self, script, count, key):
        self.attempts += 1
        return self.attempts


@pytest.fixture
def settings(tmp_path, monkeypatch):
    url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    return Settings(database_url=SecretStr(url), cookie_secure=False, registration_enabled=True)


@pytest.fixture
async def client(settings):
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        app.state.redis = MemoryRedis()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Origin": settings.frontend_origin},
        ) as client:
            yield client, app
