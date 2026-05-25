"""003 — widget_sessions table (audit + revocation; JWT is self-contained)

Revision ID: 003_widget_sessions
Revises: 002_widgets
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003_widget_sessions"
down_revision = "002_widgets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "widget_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("widget_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("widgets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("issued_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_widget_sessions_conversation_id", "widget_sessions", ["conversation_id"])
    op.create_index("ix_widget_sessions_tenant_id", "widget_sessions", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("widget_sessions")
