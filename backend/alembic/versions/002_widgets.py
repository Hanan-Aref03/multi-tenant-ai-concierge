"""002 — widgets table

Revision ID: 002_widgets
Revises: 001_tenants
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002_widgets"
down_revision = "001_tenants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "widgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("widget_id", sa.String(64), nullable=False, unique=True),
        sa.Column("greeting", sa.Text(), nullable=False, server_default="Hi! How can I help you?"),
        sa.Column("accent_colour", sa.String(7), nullable=False, server_default="#3B82F6"),
        sa.Column("allowed_origins", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_widgets_widget_id", "widgets", ["widget_id"])
    op.create_index("ix_widgets_tenant_id", "widgets", ["tenant_id"])

    # RLS: scope all access to the current tenant
    op.execute("ALTER TABLE widgets ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON widgets
        USING (tenant_id = current_setting('app.tenant_id', TRUE)::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON widgets")
    op.drop_table("widgets")
