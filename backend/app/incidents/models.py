import enum
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Severity(enum.StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class IncidentStatus(enum.StrEnum):
    created = "created"
    queued = "queued"
    investigating = "investigating"
    diagnosis_ready = "diagnosis_ready"
    remediation_ready = "remediation_ready"
    awaiting_approval = "awaiting_approval"
    executing = "executing"
    verifying = "verifying"
    resolved = "resolved"
    blocked = "blocked"
    failed = "failed"
    cancelled = "cancelled"


class IncidentSource(enum.StrEnum):
    manual = "manual"
    alert = "alert"
    benchmark = "benchmark"


class Service(Base):
    __tablename__ = "services"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    repository_url: Mapped[str | None] = mapped_column(Text)
    default_branch: Mapped[str] = mapped_column(String(120), default="main")
    environment: Mapped[str] = mapped_column(String(80), default="local")
    service_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (Index("ix_incidents_status_created_at", "status", "created_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[Severity] = mapped_column(Enum(Severity, name="incident_severity"))
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus, name="incident_status"), default=IncidentStatus.created
    )
    source: Mapped[IncidentSource] = mapped_column(
        Enum(IncidentSource, name="incident_source"), default=IncidentSource.manual
    )
    service_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("services.id", ondelete="SET NULL"), index=True
    )
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
