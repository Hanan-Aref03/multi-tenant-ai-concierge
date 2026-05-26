"""004 — tenant_config table (agent persona + guardrail settings)

Revision ID: 004_tenant_config
Revises: 003_widget_sessions
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004_tenant_config"
down_revision = "003_widget_sessions"
branch_labels = None
depends_on = None

VALID_TOOLS = ["rag_search", "capture_lead", "escalate"]
VALID_TONES = ["polite", "firm", "brief"]


def upgrade() -> None:
    op.create_table(
        "tenant_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("agent_persona", sa.Text(), nullable=False, server_default="You are a helpful assistant."),
        sa.Column("enabled_tools", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("ARRAY['rag_search','capture_lead','escalate']")),
        sa.Column("allowed_topics", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("blocked_topics", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("refusal_tone", sa.String(16), nullable=False, server_default="polite"),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_tenant_config_tenant_id", "tenant_config", ["tenant_id"])

    op.execute("ALTER TABLE tenant_config ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON tenant_config
        USING (tenant_id = current_setting('app.tenant_id', TRUE)::uuid)
    """)

    op.execute(f"""
        ALTER TABLE tenant_config ADD CONSTRAINT chk_refusal_tone
        CHECK (refusal_tone IN ({', '.join(f"'{t}'" for t in VALID_TONES)}))
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenant_config")
    op.drop_table("tenant_config")
