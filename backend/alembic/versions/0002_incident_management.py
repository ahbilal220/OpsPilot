"""Phase 1 incident management."""

import sqlalchemy as sa

from alembic import op

revision = "0002_incident_management"
down_revision = "0001_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    severity = sa.Enum("low", "medium", "high", "critical", name="incident_severity")
    status = sa.Enum(
        "created",
        "queued",
        "investigating",
        "diagnosis_ready",
        "remediation_ready",
        "awaiting_approval",
        "executing",
        "verifying",
        "resolved",
        "blocked",
        "failed",
        "cancelled",
        name="incident_status",
    )
    source = sa.Enum("manual", "alert", "benchmark", name="incident_source")
    actor_type = sa.Enum("user", "system", "agent", name="actor_type")

    op.create_table(
        "services",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("repository_url", sa.Text(), nullable=True),
        sa.Column("default_branch", sa.String(120), nullable=False),
        sa.Column("environment", sa.String(80), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "incidents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", severity, nullable=False),
        sa.Column("status", status, nullable=False),
        sa.Column("source", source, nullable=False),
        sa.Column(
            "service_id",
            sa.Uuid(),
            sa.ForeignKey("services.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_incidents_service_id", "incidents", ["service_id"])
    op.create_index("ix_incidents_status_created_at", "incidents", ["status", "created_at"])
    op.create_table(
        "investigations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "incident_id",
            sa.Uuid(),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("current_node", sa.String(100), nullable=False),
        sa.Column("queue_task_id", sa.String(80), nullable=True, unique=True),
        sa.Column("iteration_count", sa.Integer(), nullable=False),
        sa.Column("tool_calls_count", sa.Integer(), nullable=False),
        sa.Column("llm_cost_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_investigations_incident_id", "investigations", ["incident_id"])
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "incident_id",
            sa.Uuid(),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("actor_type", actor_type, nullable=False),
        sa.Column("actor_id", sa.String(100), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_events_incident_id", "audit_events", ["incident_id"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("investigations")
    op.drop_table("incidents")
    op.drop_table("services")
    sa.Enum(name="actor_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="incident_source").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="incident_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="incident_severity").drop(op.get_bind(), checkfirst=True)
