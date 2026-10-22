"""Cache a locally-served thumbnail for each article.

Revision ID: 0003
Revises: 0002
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        with op.batch_alter_table("articles") as batch:
            batch.add_column(sa.Column("image_url", sa.String(2000)))
            batch.add_column(sa.Column("image_bytes", sa.LargeBinary()))
            batch.add_column(sa.Column("image_content_type", sa.String(100)))
    else:
        op.add_column("articles", sa.Column("image_url", sa.String(2000)))
        op.add_column("articles", sa.Column("image_bytes", sa.LargeBinary()))
        op.add_column("articles", sa.Column("image_content_type", sa.String(100)))


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        with op.batch_alter_table("articles") as batch:
            batch.drop_column("image_content_type")
            batch.drop_column("image_bytes")
            batch.drop_column("image_url")
    else:
        op.drop_column("articles", "image_content_type")
        op.drop_column("articles", "image_bytes")
        op.drop_column("articles", "image_url")