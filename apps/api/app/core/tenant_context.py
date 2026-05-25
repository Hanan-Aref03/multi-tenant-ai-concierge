"""Request-scoped tenant_id handling.

Hanan owns the tenant boundary enforcement.
Mohammad uses this context in retrieval and agent flows.
"""

# TODO: propagate tenant_id into DB sessions, service calls, and audit logs.
