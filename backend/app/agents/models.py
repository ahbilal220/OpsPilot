import enum
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HypothesisStatus(enum.StrEnum):
    proposed = "proposed"
    testing = "testing"
    supported = "supported"
    rejected = "rejected"
    inconclusive = "inconclusive"


class Hypothesis(Base):
    __tablename__ = "hypotheses"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    investigation_id: Mapped[UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(40), default=HypothesisStatus.proposed.value)
    supporting_evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    contradicting_evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    validation_plan: Mapped[list[str]] = mapped_column(JSON, default=list)
    validation_result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Diagnosis(Base):
    __tablename__ = "diagnoses"
    __table_args__ = (
        UniqueConstraint("incident_id"),
        UniqueConstraint("investigation_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    incident_id: Mapped[UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    investigation_id: Mapped[UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), index=True
    )
    root_cause: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    evidence_ids: Mapped[list[str]] = mapped_column(JSON)
    limitations: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
