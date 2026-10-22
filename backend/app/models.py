import enum
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SourceKind(str, enum.Enum):
    RSS = "rss"
    NVD = "nvd"
    CISA = "cisa"
    GITHUB = "github"


class RunStatus(str, enum.Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    kind: Mapped[SourceKind] = mapped_column(Enum(SourceKind, native_enum=False), index=True)
    url: Mapped[str] = mapped_column(String(2000), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    articles: Mapped[list["Article"]] = relationship(back_populates="source")
    runs: Mapped[list["IngestionRun"]] = relationship(back_populates="source")


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_article_source_external"),
        UniqueConstraint("source_id", "canonical_url", name="uq_article_source_canonical"),
        Index("ix_articles_published_category", "published_at", "category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(1000))
    canonical_url: Mapped[str] = mapped_column(String(2000), index=True)
    title: Mapped[str] = mapped_column(String(1000))
    excerpt: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(50), index=True)
    duplicate_key: Mapped[str] = mapped_column(String(500), index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    image_url: Mapped[str | None] = mapped_column(String(2000))
    image_bytes: Mapped[bytes | None] = mapped_column(LargeBinary)
    image_content_type: Mapped[str | None] = mapped_column(String(100))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    source: Mapped[Source] = relationship(back_populates="articles")
    vulnerabilities: Mapped[list["Vulnerability"]] = relationship(
        secondary="article_cve_links", back_populates="articles"
    )

    @property
    def has_image(self) -> bool:
        return self.image_bytes is not None

    @property
    def cve_ids(self) -> list[str]:
        return sorted(vulnerability.cve_id for vulnerability in self.vulnerabilities)


class Vulnerability(Base):
    __tablename__ = "vulnerabilities"

    cve_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    description: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str | None] = mapped_column(String(20), index=True)
    cvss_score: Mapped[float | None] = mapped_column(Float, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    kev: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    vendor: Mapped[str | None] = mapped_column(String(300), index=True)
    product: Mapped[str | None] = mapped_column(String(300))
    date_added: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    required_action: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    articles: Mapped[list[Article]] = relationship(
        secondary="article_cve_links", back_populates="vulnerabilities"
    )

    @property
    def source_references(self) -> list[dict[str, str]]:
        references = []
        payload = self.raw_payload or {}
        if payload.get("nvd") is not None:
            references.append({"source": "NVD", "url": f"https://nvd.nist.gov/vuln/detail/{self.cve_id}"})
        if payload.get("cisa") is not None:
            references.append({
                "source": "CISA KEV",
                "url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
            })
        return references


class ArticleCVELink(Base):
    __tablename__ = "article_cve_links"

    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True)
    cve_id: Mapped[str] = mapped_column(ForeignKey("vulnerabilities.cve_id", ondelete="CASCADE"), primary_key=True)


class Tool(Base):
    __tablename__ = "tools"

    id: Mapped[int] = mapped_column(primary_key=True)
    github_id: Mapped[int] = mapped_column(unique=True)
    full_name: Mapped[str] = mapped_column(String(500), unique=True)
    url: Mapped[str] = mapped_column(String(2000))
    description: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(100), index=True)
    stars: Mapped[int] = mapped_column(Integer, default=0, index=True)
    forks: Mapped[int] = mapped_column(Integer, default=0)
    topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus, native_enum=False), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    items_seen: Mapped[int] = mapped_column(Integer, default=0)
    items_written: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String(1000))

    source: Mapped[Source] = relationship(back_populates="runs")
