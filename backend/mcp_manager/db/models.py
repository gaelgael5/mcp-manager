import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Table, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from pgvector.sqlalchemy import Vector
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

    _id: Mapped[int] = mapped_column(
        BigInteger,
        server_default=text("nextval('mcp_services__id_seq')"),
        nullable=False,
        unique=True,
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
    repo_status: Mapped[str | None] = mapped_column(String(20))
    needs_reindex: Mapped[bool] = mapped_column(Boolean, default=False)
    index_attempts: Mapped[int] = mapped_column(default=0)
    is_deprecated: Mapped[bool] = mapped_column(Boolean, default=False)
    stars: Mapped[int | None] = mapped_column(nullable=True)
    canonical_id: Mapped[str | None] = mapped_column(String(500), index=True)
    search_vector = Column(TSVECTOR)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    summaries: Mapped[list["McpSummary"]] = relationship(back_populates="service", cascade="all, delete-orphan")
    installations: Mapped[list["McpInstallation"]] = relationship(back_populates="service", cascade="all, delete-orphan")
    parameters: Mapped[list["McpParameter"]] = relationship(back_populates="service", cascade="all, delete-orphan")


class McpSummary(Base):
    __tablename__ = "mcp_summaries"
    __table_args__ = (
        UniqueConstraint("parent_id", "culture", name="uq_service_culture"),
        Index("idx_summaries_culture", "culture"),
    )

    _id: Mapped[int] = mapped_column(
        BigInteger,
        server_default=text("nextval('mcp_summaries__id_seq')"),
        nullable=False,
        unique=True,
    )
    parent_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mcp_services._id", ondelete="CASCADE"), nullable=False
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
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
    rag_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heuristic_quality: Mapped[int | None] = mapped_column(nullable=True)
    llm_quality: Mapped[int | None] = mapped_column(nullable=True)

    service: Mapped["McpService"] = relationship(back_populates="summaries")


class InstallTarget(Base):
    __tablename__ = "install_targets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    modes: Mapped[list] = mapped_column(JSONB, default=list)
    skill_modes: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    installations: Mapped[list["McpInstallation"]] = relationship(back_populates="target", cascade="all, delete-orphan")


class McpInstallation(Base):
    __tablename__ = "mcp_installations"
    __table_args__ = (
        UniqueConstraint("parent_id", "install_target_id", name="uq_service_target"),
        Index("idx_installations_target", "install_target_id"),
    )

    _id: Mapped[int] = mapped_column(
        BigInteger,
        server_default=text("nextval('mcp_installations__id_seq')"),
        nullable=False,
        unique=True,
    )
    parent_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mcp_services._id", ondelete="CASCADE"), nullable=False
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
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


class McpParameter(Base):
    __tablename__ = "mcp_parameters"
    __table_args__ = (
        UniqueConstraint("parent_id", "name", name="uq_service_param_name"),
    )

    _id: Mapped[int] = mapped_column(
        BigInteger,
        server_default=text("nextval('mcp_parameters__id_seq')"),
        nullable=False,
        unique=True,
    )
    parent_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mcp_services._id", ondelete="CASCADE"), nullable=False
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # "registry", "ai", "manual"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    service: Mapped["McpService"] = relationship(back_populates="parameters")


skill_source_skills = Table(
    "skill_source_skills",
    Base.metadata,
    Column("source_pid", BigInteger, ForeignKey("skill_sources._id", ondelete="CASCADE"), primary_key=True),
    Column("skill_pid", BigInteger, ForeignKey("skills._id", ondelete="CASCADE"), primary_key=True),
)


class SkillSource(Base):
    __tablename__ = "skill_sources"
    __table_args__ = (
        Index("ix_skill_sources_repo_url", "repo_url",
              postgresql_where=text("repo_url IS NOT NULL")),
    )

    _id: Mapped[int] = mapped_column(
        BigInteger,
        server_default=text("nextval('skill_sources__id_seq')"),
        nullable=False,
        unique=True,
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    repo_url: Mapped[str | None] = mapped_column(Text)  # GitHub repo URL
    skills_path: Mapped[str] = mapped_column(String(255), default="")  # directory in the repo (empty = root)
    type: Mapped[str] = mapped_column(String(200), nullable=False)  # pipe-separated: opencode|codex|gemini-cli|github-copilot|amp|claude|cursor
    description: Mapped[str | None] = mapped_column(Text)
    repo_format: Mapped[str] = mapped_column(
        String(20), nullable=False, default="skills", server_default="skills"
    )  # "skills" (flat skills.sh layout) or "plugin" (wshobson/agents-style plugins/*/skills/*)
    repo_status: Mapped[str | None] = mapped_column(String(20))  # "ok", "no_skills_dir", "repo_404", etc.
    branch_hash: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_count: Mapped[int] = mapped_column(default=0)
    stars: Mapped[int | None] = mapped_column(nullable=True)
    enrichment_status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending"
    )  # pending, enriching, done, failed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    skills: Mapped[list["Skill"]] = relationship(secondary=skill_source_skills, back_populates="sources")
    translations: Mapped[list["SkillSourceTranslation"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        foreign_keys="[SkillSourceTranslation.parent_id]",
        primaryjoin="SkillSource._id == SkillSourceTranslation.parent_id",
    )


class Skill(Base):
    __tablename__ = "skills"

    _id: Mapped[int] = mapped_column(
        BigInteger,
        server_default=text("nextval('skills__id_seq')"),
        nullable=False,
        unique=True,
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    target_type: Mapped[str] = mapped_column(String(200), nullable=False)  # pipe-separated: opencode|codex|gemini-cli|github-copilot|amp|claude|cursor
    licence: Mapped[str | None] = mapped_column(String(255))
    licence_url: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(100))
    install_command: Mapped[str | None] = mapped_column(Text)
    weekly_installs: Mapped[int] = mapped_column(default=0)
    canonical_id: Mapped[str | None] = mapped_column(String(500), index=True)
    needs_summary: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sources: Mapped[list["SkillSource"]] = relationship(secondary=skill_source_skills, back_populates="skills")
    translations: Mapped[list["SkillTranslation"]] = relationship(
        back_populates="skill",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        foreign_keys="[SkillTranslation.parent_id]",
        primaryjoin="Skill._id == SkillTranslation.parent_id",
    )


class SkillSourceTranslation(Base):
    __tablename__ = "skill_sources_translations"
    __table_args__ = (
        UniqueConstraint("parent_id", "culture", name="uq_skill_source_culture"),
        Index("idx_skill_sources_translations_culture", "culture"),
    )

    _id: Mapped[int] = mapped_column(
        BigInteger,
        server_default=text("nextval('skill_sources_translations__id_seq')"),
        nullable=False,
        unique=True,
    )
    parent_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("skill_sources._id", ondelete="CASCADE"), nullable=False
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    culture: Mapped[str] = mapped_column(String(5), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_hash: Mapped[str | None] = mapped_column(String(64))
    heuristic_quality: Mapped[int | None] = mapped_column(nullable=True)
    llm_quality: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    rag_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    source: Mapped["SkillSource"] = relationship(
        back_populates="translations",
        foreign_keys=[parent_id],
        primaryjoin="SkillSource._id == SkillSourceTranslation.parent_id",
    )


class SkillTranslation(Base):
    __tablename__ = "skills_translations"
    __table_args__ = (
        UniqueConstraint("parent_id", "culture", name="uq_skill_culture"),
        Index("idx_skills_translations_culture", "culture"),
    )

    _id: Mapped[int] = mapped_column(
        BigInteger,
        server_default=text("nextval('skills_translations__id_seq')"),
        nullable=False,
        unique=True,
    )
    parent_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("skills._id", ondelete="CASCADE"), nullable=False
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    culture: Mapped[str] = mapped_column(String(5), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_hash: Mapped[str | None] = mapped_column(String(64))
    heuristic_quality: Mapped[int | None] = mapped_column(nullable=True)
    llm_quality: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    rag_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    skill: Mapped["Skill"] = relationship(
        back_populates="translations",
        foreign_keys=[parent_id],
        primaryjoin="Skill._id == SkillTranslation.parent_id",
    )


class ApiToken(Base):
    __tablename__ = "api_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    rate_limit_per_min: Mapped[int] = mapped_column(default=60)
    request_count: Mapped[int] = mapped_column(default=0)
    last_reset_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class McpInstance(Base):
    __tablename__ = "mcp_instances"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)  # https://mcp.other.org
    api_key: Mapped[str | None] = mapped_column(Text)  # X-API-Key for the remote instance
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False)  # "mcp_xxxx..." for display
    owner_email: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    picture: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


preference_group_services = Table(
    "preference_group_services",
    Base.metadata,
    Column("group_id", UUID(as_uuid=True), ForeignKey("preference_groups.id", ondelete="CASCADE"), primary_key=True),
    Column("mcp_service_id", UUID(as_uuid=True), ForeignKey("mcp_services.id", ondelete="CASCADE"), primary_key=True),
)


preference_group_skills = Table(
    "preference_group_skills",
    Base.metadata,
    Column("group_id", UUID(as_uuid=True), ForeignKey("preference_groups.id", ondelete="CASCADE"), primary_key=True),
    Column("skill_id", UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True),
)


class PreferenceGroup(Base):
    __tablename__ = "preference_groups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    services: Mapped[list["McpService"]] = relationship(secondary=preference_group_services)
    skills: Mapped[list["Skill"]] = relationship(secondary=preference_group_skills)
    user: Mapped["User"] = relationship()


class Language(Base):
    __tablename__ = "languages"

    code: Mapped[str] = mapped_column(String(5), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    display_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100, server_default="100"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


EMBEDDING_DIM = 1024  # mxbai-embed-large


class McpEmbedding(Base):
    __tablename__ = "mcp_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    mcp_service_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mcp_services.id", ondelete="CASCADE")
    )
    skill_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE")
    )
    chunk_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "summary", "doc_chunk", "skill_summary"
    chunk_index: Mapped[int] = mapped_column(default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
