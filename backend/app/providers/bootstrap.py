from app.core.config import Settings
from app.providers.fixture import FixtureModelProvider
from app.providers.router import ModelRouter


def build_model_router(settings: Settings) -> ModelRouter:
    if settings.model_provider != "fixture":
        raise ValueError("Only the offline fixture model provider is configured in Phase 3")
    return ModelRouter(FixtureModelProvider())
