"""Align Phase 1 timestamp constraints with the domain models."""

from alembic import op

revision = "0003_phase_one_constraints"
down_revision = "0002_incident_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("services", "incidents", "investigations"):
        with op.batch_alter_table(table) as batch:
            batch.alter_column("created_at", nullable=False)
            batch.alter_column("updated_at", nullable=False)
    with op.batch_alter_table("audit_events") as batch:
        batch.alter_column("created_at", nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("audit_events") as batch:
        batch.alter_column("created_at", nullable=True)
    for table in ("investigations", "incidents", "services"):
        with op.batch_alter_table(table) as batch:
            batch.alter_column("updated_at", nullable=True)
            batch.alter_column("created_at", nullable=True)
