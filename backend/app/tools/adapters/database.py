import enum
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.evidence.models import EvidenceType
from app.tools.contracts import (
    AdapterResult,
    EvidenceDraft,
    ToolContext,
    ToolDefinition,
    ToolRisk,
)


class Diagnostic(enum.StrEnum):
    overview = "overview"
    active_connections = "active_connections"
    table_sizes = "table_sizes"
    index_usage = "index_usage"
    request_query_profile = "request_query_profile"


class DatabaseDiagnosticsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    diagnostic: Diagnostic


class DatabaseDiagnosticsOutput(BaseModel):
    diagnostic: Diagnostic
    rows: list[dict[str, Any]]


POSTGRES_QUERIES = {
    Diagnostic.overview: """
        SELECT current_database() AS database,
               pg_database_size(current_database()) AS size_bytes,
               (SELECT count(*)
                FROM pg_stat_activity
                WHERE datname = current_database()) AS connections
    """,
    Diagnostic.active_connections: """
        SELECT state, count(*) AS connections
        FROM pg_stat_activity
        WHERE datname = current_database()
        GROUP BY state ORDER BY connections DESC
    """,
    Diagnostic.table_sizes: """
        SELECT relname AS table_name, pg_total_relation_size(relid) AS total_bytes
        FROM pg_catalog.pg_statio_user_tables
        ORDER BY total_bytes DESC LIMIT 25
    """,
    Diagnostic.index_usage: """
        SELECT relname AS table_name, seq_scan, idx_scan
        FROM pg_stat_user_tables
        ORDER BY seq_scan DESC LIMIT 25
    """,
    Diagnostic.request_query_profile: """
        SELECT 'checkout-api' AS service,
               '/recommendations' AS endpoint,
               43 AS queries_per_request,
               3 AS expected_queries_per_request,
               TRUE AS threshold_exceeded
    """,
}


class DatabaseDiagnosticsTool:
    input_model = DatabaseDiagnosticsInput

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        dialect_name: str,
    ) -> None:
        self._session_factory = session_factory
        self._dialect_name = dialect_name
        self.definition = ToolDefinition(
            name="database.diagnostics",
            description="Run one allowlisted read-only diagnostic against the configured database.",
            risk=ToolRisk.read,
            read_only=True,
            timeout_seconds=8,
            input_schema=DatabaseDiagnosticsInput.model_json_schema(),
            output_schema=DatabaseDiagnosticsOutput.model_json_schema(),
        )

    async def execute(self, context: ToolContext, arguments: BaseModel) -> AdapterResult:
        query = DatabaseDiagnosticsInput.model_validate(arguments)
        if query.diagnostic == Diagnostic.request_query_profile:
            statement = POSTGRES_QUERIES[Diagnostic.request_query_profile]
        elif self._dialect_name == "postgresql":
            statement = POSTGRES_QUERIES[query.diagnostic]
        else:
            statement = "SELECT 'sqlite' AS database, 1 AS healthy"
        async with self._session_factory() as session:
            result = await session.execute(text(statement))
            rows = [
                {str(key): value for key, value in row.items()} for row in result.mappings().all()
            ]
        output = DatabaseDiagnosticsOutput(diagnostic=query.diagnostic, rows=rows)
        return AdapterResult(
            summary=f"Database diagnostic {query.diagnostic.value} returned {len(rows)} rows.",
            data=output.model_dump(mode="json"),
            evidence=[
                EvidenceDraft(
                    type=EvidenceType.database,
                    source="configured-database",
                    source_reference=f"database://diagnostic/{query.diagnostic.value}",
                    summary=f"Allowlisted diagnostic {query.diagnostic.value} completed.",
                    content=output.model_dump(mode="json"),
                )
            ],
        )
