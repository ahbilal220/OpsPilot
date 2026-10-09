from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ToolExecution(Base):
    __tablename__ = "tool_executions"
    __table_args__ = (
        Index("ix_tool_executions_investigation_created", "investigation_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    investigation_id: Mapped[UUID] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"), index=True
    )
    tool_name: Mapped[str] = mapped_column(String(120), index=True)
    risk_level: Mapped[str] = mapped_column(String(40))
    input_data: Mapped[dict[str, Any]] = mapped_column("input", JSON, default=dict)
    output_data: Mapped[dict[str, Any] | None] = mapped_column("output", JSON)
    status: Mapped[str] = mapped_column(String(40), index=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
