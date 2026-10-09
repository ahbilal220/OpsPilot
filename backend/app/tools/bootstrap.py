from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.tools.adapters.database import DatabaseDiagnosticsTool
from app.tools.adapters.deployments import DeploymentHistoryTool
from app.tools.adapters.logs import DemoLogsTool
from app.tools.adapters.prometheus import PrometheusMetricsTool
from app.tools.adapters.repository import GitHistoryTool, RepositorySearchTool
from app.tools.gateway import ToolGateway
from app.tools.policy import ToolPolicy
from app.tools.registry import ToolRegistry


def build_tool_gateway(
    settings: Settings,
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
) -> ToolGateway:
    registry = ToolRegistry()
    fixture_root = Path(settings.tool_fixture_root)
    repository_root = Path(settings.tool_repository_root)
    registry.register(DemoLogsTool(fixture_root))
    registry.register(PrometheusMetricsTool(settings.prometheus_url))
    registry.register(RepositorySearchTool(repository_root))
    registry.register(GitHistoryTool(repository_root))
    registry.register(DeploymentHistoryTool(fixture_root))
    registry.register(DatabaseDiagnosticsTool(session_factory, engine.dialect.name))
    return ToolGateway(
        registry,
        ToolPolicy(),
        max_output_chars=settings.tool_max_output_chars,
    )
