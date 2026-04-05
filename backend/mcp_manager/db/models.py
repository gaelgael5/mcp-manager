import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class McpService(Base):
    __tablename__ = "mcp_services"
    __table_args__ = (
        UniqueConstraint("source_type", "name", name="uq_source_type_name"),
        Index("idx_services_source_type", "source_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    doc_url: Mapped[str | None] = mapped_column(Text)
    doc_hash: Mapped[str | None] = mapped_column(String(64))
    branch_hash: Mapped[str | None] = mapped_column(String(64))
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    transport: Mapped[str | None] = mapped_column(String(20))
    category: Mapped[str | None] = mapped_column(String(100))
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    package_info: Mapped[dict] = mapped_column(JSONB, default=dict)
    source_origins: Mapped[list[str] | None] = mapped_column(ARRAY(Text), default=list)
    is_deprecated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    summaries: Mapped[list["McpSummary"]] = relationship(back_populates="service", cascade="all, delete-orphan")
    installations: Mapped[list["McpInstallation"]] = relationship(back_populates="service", cascade="all, delete-orphan")


class McpSummary(Base):
    __tablename__ = "mcp_summaries"
    __table_args__ = (
        UniqueConstraint("mcp_service_id", "culture", name="uq_service_culture"),
        Index("idx_summaries_culture", "culture"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    mcp_service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mcp_services.id", ondelete="CASCADE"), nullable=False
    )
    culture: Mapped[str] = mapped_column(String(5), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    service: Mapped["McpService"] = relationship(back_populates="summaries")


class InstallTarget(Base):
    __tablename__ = "install_targets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    installations: Mapped[list["McpInstallation"]] = relationship(back_populates="target", cascade="all, delete-orphan")


class McpInstallation(Base):
    __tablename__ = "mcp_installations"
    __table_args__ = (
        UniqueConstraint("mcp_service_id", "install_target_id", name="uq_service_target"),
        Index("idx_installations_target", "install_target_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    mcp_service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mcp_services.id", ondelete="CASCADE"), nullable=False
    )
    install_target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("install_targets.id", ondelete="CASCADE"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    data: Mapped[str] = mapped_column(Text, nullable=False)
    env_vars: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    service: Mapped["McpService"] = relationship(back_populates="installations")
    target: Mapped["InstallTarget"] = relationship(back_populates="installations")
