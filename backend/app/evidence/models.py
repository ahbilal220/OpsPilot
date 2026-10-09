import enum
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EvidenceType(enum.StrEnum):
    log = "log"
    metric = "metric"
    code = "code"
    git = "git"
    deployment = "deployment"
    document = "document"
    database = "database"
    test = "test"
    trace = "trace"


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (Index("ix_evidence_incident_type", "incident_id", "type"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    incident_id: Mapped[UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    investigation_id: Mapped[UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[EvidenceType] = mapped_column(Enum(EvidenceType, name="evidence_type"))
    source: Mapped[str] = mapped_column(String(120))
    source_reference: Mapped[str | None] = mapped_column(Text)
    tool_name: Mapped[str] = mapped_column(String(120), index=True)
    query: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    content: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
