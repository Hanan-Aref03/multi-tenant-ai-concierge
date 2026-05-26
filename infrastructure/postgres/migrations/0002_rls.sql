-- Hanan owns the Row Level Security policies.

CREATE OR REPLACE FUNCTION app.current_tenant_id()
RETURNS uuid
LANGUAGE sql
STABLE
AS $$
    SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid;
$$;

CREATE OR REPLACE FUNCTION app.current_actor_role()
RETURNS text
LANGUAGE sql
STABLE
AS $$
    SELECT NULLIF(current_setting('app.actor_role', true), '');
$$;

CREATE OR REPLACE FUNCTION app.is_platform_manager()
RETURNS boolean
LANGUAGE sql
STABLE
AS $$
    SELECT app.current_actor_role() = 'platform_manager';
$$;

CREATE OR REPLACE FUNCTION app.has_tenant_access(row_tenant_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
AS $$
    SELECT row_tenant_id = app.current_tenant_id() OR app.is_platform_manager();
$$;

ALTER TABLE app.tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.tenant_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.content_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.content_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.conversation_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.audit_events ENABLE ROW LEVEL SECURITY;

ALTER TABLE app.tenants FORCE ROW LEVEL SECURITY;
ALTER TABLE app.tenant_members FORCE ROW LEVEL SECURITY;
ALTER TABLE app.content_documents FORCE ROW LEVEL SECURITY;
ALTER TABLE app.content_chunks FORCE ROW LEVEL SECURITY;
ALTER TABLE app.conversations FORCE ROW LEVEL SECURITY;
ALTER TABLE app.conversation_messages FORCE ROW LEVEL SECURITY;
ALTER TABLE app.leads FORCE ROW LEVEL SECURITY;
ALTER TABLE app.audit_events FORCE ROW LEVEL SECURITY;

CREATE POLICY tenants_select_policy
ON app.tenants
FOR SELECT
USING (app.has_tenant_access(tenant_id));

CREATE POLICY tenants_write_policy
ON app.tenants
FOR ALL
USING (app.has_tenant_access(tenant_id))
WITH CHECK (app.has_tenant_access(tenant_id));

CREATE POLICY tenant_members_policy
ON app.tenant_members
FOR ALL
USING (app.has_tenant_access(tenant_id))
WITH CHECK (app.has_tenant_access(tenant_id));

CREATE POLICY content_documents_policy
ON app.content_documents
FOR ALL
USING (app.has_tenant_access(tenant_id))
WITH CHECK (app.has_tenant_access(tenant_id));

CREATE POLICY content_chunks_policy
ON app.content_chunks
FOR ALL
USING (app.has_tenant_access(tenant_id))
WITH CHECK (app.has_tenant_access(tenant_id));

CREATE POLICY conversations_policy
ON app.conversations
FOR ALL
USING (app.has_tenant_access(tenant_id))
WITH CHECK (app.has_tenant_access(tenant_id));

CREATE POLICY conversation_messages_policy
ON app.conversation_messages
FOR ALL
USING (app.has_tenant_access(tenant_id))
WITH CHECK (app.has_tenant_access(tenant_id));

CREATE POLICY leads_policy
ON app.leads
FOR ALL
USING (app.has_tenant_access(tenant_id))
WITH CHECK (app.has_tenant_access(tenant_id));

CREATE POLICY audit_events_policy
ON app.audit_events
FOR ALL
USING (tenant_id IS NULL OR app.has_tenant_access(tenant_id))
WITH CHECK (tenant_id IS NULL OR app.has_tenant_access(tenant_id));
