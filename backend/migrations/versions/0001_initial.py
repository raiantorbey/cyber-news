"""Initial SignalWatch schema.

Revision ID: 0001
Revises:
"""
from collections.abc import Sequence
from datetime import datetime, timezone

from alembic import context, op
import sqlalchemy as sa

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _seed_default_sources() -> None:
    sources = sa.table(
        "sources",
        sa.column("name", sa.String), sa.column("kind", sa.String), sa.column("url", sa.String),
        sa.column("enabled", sa.Boolean), sa.column("config", sa.JSON),
        sa.column("created_at", sa.DateTime(timezone=True)), sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    rows = [
        {"name": "BleepingComputer", "kind": "RSS", "url": "https://www.bleepingcomputer.com/feed/", "enabled": True, "config": {}, "created_at": now, "updated_at": now},
        {"name": "Krebs on Security", "kind": "RSS", "url": "https://krebsonsecurity.com/feed/", "enabled": True, "config": {}, "created_at": now, "updated_at": now},
        {"name": "The Hacker News", "kind": "RSS", "url": "https://feeds.feedburner.com/TheHackersNews", "enabled": True, "config": {}, "created_at": now, "updated_at": now},
        {"name": "SANS Internet Storm Center", "kind": "RSS", "url": "https://isc.sans.edu/rssfeed.xml", "enabled": True, "config": {}, "created_at": now, "updated_at": now},
        {"name": "NVD CVE API 2.0", "kind": "NVD", "url": "https://services.nvd.nist.gov/rest/json/cves/2.0", "enabled": True, "config": {}, "created_at": now, "updated_at": now},
        {"name": "CISA Known Exploited Vulnerabilities", "kind": "CISA", "url": "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json", "enabled": True, "config": {}, "created_at": now, "updated_at": now},
        {"name": "GitHub Security Tools", "kind": "GITHUB", "url": "https://api.github.com/search/repositories", "enabled": True, "config": {}, "created_at": now, "updated_at": now},
    ]
    if context.is_offline_mode():
        rows = [{**row, "config": op.inline_literal("{}", type_=sa.String())} for row in rows]
        op.bulk_insert(sources, rows, multiinsert=False)
    else:
        op.bulk_insert(sources, rows)


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("kind", sa.Enum("RSS", "NVD", "CISA", "GITHUB", name="sourcekind", native_enum=False), nullable=False),
        sa.Column("url", sa.String(2000), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sources_kind", "sources", ["kind"])
    op.create_index("ix_sources_enabled", "sources", ["enabled"])
    _seed_default_sources()
    op.create_table(
        "vulnerabilities",
        sa.Column("cve_id", sa.String(20), primary_key=True),
        sa.Column("description", sa.Text()),
        sa.Column("severity", sa.String(20)),
        sa.Column("cvss_score", sa.Float()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("modified_at", sa.DateTime(timezone=True)),
        sa.Column("kev", sa.Boolean(), nullable=False),
        sa.Column("vendor", sa.String(300)),
        sa.Column("product", sa.String(300)),
        sa.Column("date_added", sa.DateTime(timezone=True)),
        sa.Column("due_date", sa.DateTime(timezone=True)),
        sa.Column("required_action", sa.Text()),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("severity", "cvss_score", "published_at", "kev", "vendor"):
        op.create_index(f"ix_vulnerabilities_{column}", "vulnerabilities", [column])
    op.create_table(
        "articles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_id", sa.String(1000), nullable=False),
        sa.Column("canonical_url", sa.String(2000), nullable=False, unique=True),
        sa.Column("title", sa.String(1000), nullable=False),
        sa.Column("excerpt", sa.Text()),
        sa.Column("author", sa.String(300)),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("duplicate_key", sa.String(500), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_id", "external_id", name="uq_article_source_external"),
    )
    op.create_index("ix_articles_source_id", "articles", ["source_id"])
    op.create_index("ix_articles_category", "articles", ["category"])
    op.create_index("ix_articles_duplicate_key", "articles", ["duplicate_key"])
    op.create_index("ix_articles_published_at", "articles", ["published_at"])
    op.create_index("ix_articles_published_category", "articles", ["published_at", "category"])
    op.create_table(
        "article_cve_links",
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("cve_id", sa.String(20), sa.ForeignKey("vulnerabilities.cve_id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "tools",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("github_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("full_name", sa.String(500), nullable=False, unique=True),
        sa.Column("url", sa.String(2000), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("language", sa.String(100)),
        sa.Column("stars", sa.Integer(), nullable=False),
        sa.Column("forks", sa.Integer(), nullable=False),
        sa.Column("topics", sa.JSON(), nullable=False),
        sa.Column("pushed_at", sa.DateTime(timezone=True)),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("language", "stars", "pushed_at", "discovered_at"):
        op.create_index(f"ix_tools_{column}", "tools", [column])
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Enum("RUNNING", "SUCCEEDED", "FAILED", name="runstatus", native_enum=False), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("items_seen", sa.Integer(), nullable=False),
        sa.Column("items_written", sa.Integer(), nullable=False),
        sa.Column("error", sa.String(1000)),
    )
    op.create_index("ix_ingestion_runs_source_id", "ingestion_runs", ["source_id"])
    op.create_index("ix_ingestion_runs_status", "ingestion_runs", ["status"])
    op.create_index("ix_ingestion_runs_started_at", "ingestion_runs", ["started_at"])


def downgrade() -> None:
    op.drop_table("ingestion_runs")
    op.drop_table("tools")
    op.drop_table("article_cve_links")
    op.drop_table("articles")
    op.drop_table("vulnerabilities")
    op.drop_table("sources")
