-- Hanan owns the base Postgres schema for platform tenancy and isolation.

CREATE SCHEMA IF NOT EXISTS app;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE OR REPLACE FUNCTION app.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TABLE IF NOT EXISTS app.tenants (
    tenant_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug text NOT NULL UNIQUE,
    display_name text NOT NULL,
    owner_email text NOT NULL,
    status text NOT NULL DEFAULT 'provisioning',
    provisioning_stage text NOT NULL DEFAULT 'requested',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    archived_at timestamptz,
    deleted_at timestamptz,
    CONSTRAINT tenants_status_check CHECK (status IN ('provisioning', 'active', 'suspended', 'archived', 'deleted')),
    CONSTRAINT tenants_stage_check CHECK (provisioning_stage IN ('requested', 'active', 'suspended', 'archived', 'deleted'))
);

CREATE TABLE IF NOT EXISTS app.tenant_members (
    member_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES app.tenants(tenant_id) ON DELETE CASCADE,
    email text NOT NULL,
    role text NOT NULL DEFAULT 'member',
    active boolean NOT NULL DEFAULT true,
    invited_by text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT tenant_members_unique_email UNIQUE (tenant_id, email),
    CONSTRAINT tenant_members_role_check CHECK (role IN ('tenant_admin', 'member'))
);

CREATE TABLE IF NOT EXISTS app.content_documents (
    document_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES app.tenants(tenant_id) ON DELETE CASCADE,
    title text NOT NULL,
    body text NOT NULL,
    source_uri text,
    kind text NOT NULL DEFAULT 'document',
    tags text[] NOT NULL DEFAULT '{}'::text[],
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT content_documents_unique_tenant_document UNIQUE (tenant_id, document_id),
    CONSTRAINT content_documents_kind_check CHECK (kind IN ('document', 'faq', 'policy', 'product'))
);

CREATE TABLE IF NOT EXISTS app.content_chunks (
    chunk_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    document_id uuid NOT NULL,
    chunk_index integer NOT NULL,
    content text NOT NULL,
    embedding vector(1536),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT content_chunks_unique_order UNIQUE (document_id, chunk_index),
    CONSTRAINT content_chunks_document_fk FOREIGN KEY (tenant_id, document_id)
        REFERENCES app.content_documents (tenant_id, document_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS app.conversations (
    conversation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES app.tenants(tenant_id) ON DELETE CASCADE,
    visitor_id text NOT NULL,
    source_origin text,
    status text NOT NULL DEFAULT 'open',
    summary text NOT NULL DEFAULT '',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT conversations_unique_tenant_conversation UNIQUE (tenant_id, conversation_id),
    CONSTRAINT conversations_status_check CHECK (status IN ('open', 'escalated', 'closed'))
);

CREATE TABLE IF NOT EXISTS app.conversation_messages (
    message_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    conversation_id uuid NOT NULL,
    role text NOT NULL,
    content text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT conversation_messages_conversation_fk FOREIGN KEY (tenant_id, conversation_id)
        REFERENCES app.conversations (tenant_id, conversation_id)
        ON DELETE CASCADE,
    CONSTRAINT conversation_messages_role_check CHECK (role IN ('system', 'user', 'assistant', 'tool'))
);

CREATE TABLE IF NOT EXISTS app.leads (
    lead_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES app.tenants(tenant_id) ON DELETE CASCADE,
    full_name text NOT NULL,
    email text NOT NULL,
    company text,
    intent text,
    source text NOT NULL DEFAULT 'widget',
    status text NOT NULL DEFAULT 'new',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT leads_unique_tenant_lead UNIQUE (tenant_id, lead_id),
    CONSTRAINT leads_status_check CHECK (status IN ('new', 'qualified', 'escalated', 'closed'))
);

CREATE TABLE IF NOT EXISTS app.audit_events (
    event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid,
    actor text NOT NULL,
    action text NOT NULL,
    resource_type text NOT NULL,
    resource_id text NOT NULL,
    outcome text NOT NULL DEFAULT 'success',
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT audit_events_outcome_check CHECK (outcome IN ('success', 'denied', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_tenant_members_tenant_id ON app.tenant_members (tenant_id);
CREATE INDEX IF NOT EXISTS idx_content_documents_tenant_id ON app.content_documents (tenant_id);
CREATE INDEX IF NOT EXISTS idx_content_chunks_tenant_id ON app.content_chunks (tenant_id);
CREATE INDEX IF NOT EXISTS idx_conversations_tenant_id ON app.conversations (tenant_id);
CREATE INDEX IF NOT EXISTS idx_conversation_messages_tenant_id ON app.conversation_messages (tenant_id);
CREATE INDEX IF NOT EXISTS idx_leads_tenant_id ON app.leads (tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_tenant_id ON app.audit_events (tenant_id);

CREATE TRIGGER tenants_touch_updated_at
BEFORE UPDATE ON app.tenants
FOR EACH ROW
EXECUTE FUNCTION app.set_updated_at();

CREATE TRIGGER tenant_members_touch_updated_at
BEFORE UPDATE ON app.tenant_members
FOR EACH ROW
EXECUTE FUNCTION app.set_updated_at();

CREATE TRIGGER content_documents_touch_updated_at
BEFORE UPDATE ON app.content_documents
FOR EACH ROW
EXECUTE FUNCTION app.set_updated_at();

CREATE TRIGGER conversations_touch_updated_at
BEFORE UPDATE ON app.conversations
FOR EACH ROW
EXECUTE FUNCTION app.set_updated_at();

CREATE TRIGGER leads_touch_updated_at
BEFORE UPDATE ON app.leads
FOR EACH ROW
EXECUTE FUNCTION app.set_updated_at();
