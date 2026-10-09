"""Phase 2 tool gateway persistence."""

import sqlalchemy as sa

from alembic import op

revision = "0004_tool_gateway"
down_revision = "0003_phase_one_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    evidence_type = sa.Enum(
        "log",
        "metric",
        "code",
        "git",
        "deployment",
        "document",
        "database",
        "test",
        "trace",
        name="evidence_type",
    )
    op.create_table(
        "evidence",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "incident_id",
            sa.Uuid(),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "investigation_id",
            sa.Uuid(),
            sa.ForeignKey("investigations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", evidence_type, nullable=False),
        sa.Column("source", sa.String(120), nullable=False),
        sa.Column("source_reference", sa.Text(), nullable=True),
        sa.Column("tool_name", sa.String(120), nullable=False),
        sa.Column("query", sa.JSON(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_evidence_incident_id", "evidence", ["incident_id"])
    op.create_index("ix_evidence_investigation_id", "evidence", ["investigation_id"])
    op.create_index("ix_evidence_tool_name", "evidence", ["tool_name"])
    op.create_index("ix_evidence_incident_type", "evidence", ["incident_id", "type"])

    op.create_table(
        "tool_executions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "investigation_id",
            sa.Uuid(),
            sa.ForeignKey("investigations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_name", sa.String(120), nullable=False),
        sa.Column("risk_level", sa.String(40), nullable=False),
        sa.Column("input", sa.JSON(), nullable=False),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_tool_executions_investigation_id", "tool_executions", ["investigation_id"])
    op.create_index("ix_tool_executions_tool_name", "tool_executions", ["tool_name"])
    op.create_index("ix_tool_executions_status", "tool_executions", ["status"])
    op.create_index(
        "ix_tool_executions_investigation_created",
        "tool_executions",
        ["investigation_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("tool_executions")
    op.drop_table("evidence")
    sa.Enum(name="evidence_type").drop(op.get_bind(), checkfirst=True)
