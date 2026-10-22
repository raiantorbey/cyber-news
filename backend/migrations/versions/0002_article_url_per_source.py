"""Allow the same canonical article URL from multiple sources.

Revision ID: 0002
Revises: 0001
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        convention = {"uq": "uq_%(table_name)s_%(column_0_name)s"}
        with op.batch_alter_table("articles", naming_convention=convention) as batch:
            batch.drop_constraint("uq_articles_canonical_url", type_="unique")
            batch.create_index("ix_articles_canonical_url", ["canonical_url"], unique=False)
            batch.create_unique_constraint("uq_article_source_canonical", ["source_id", "canonical_url"])
    else:
        op.drop_constraint("articles_canonical_url_key", "articles", type_="unique")
        op.create_index("ix_articles_canonical_url", "articles", ["canonical_url"], unique=False)
        op.create_unique_constraint("uq_article_source_canonical", "articles", ["source_id", "canonical_url"])


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        with op.batch_alter_table("articles") as batch:
            batch.drop_constraint("uq_article_source_canonical", type_="unique")
            batch.drop_index("ix_articles_canonical_url")
            batch.create_unique_constraint("uq_articles_canonical_url", ["canonical_url"])
    else:
        op.drop_constraint("uq_article_source_canonical", "articles", type_="unique")
        op.drop_index("ix_articles_canonical_url", table_name="articles")
        op.create_unique_constraint("articles_canonical_url_key", "articles", ["canonical_url"])
