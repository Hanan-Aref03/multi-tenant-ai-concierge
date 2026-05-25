"""Database session helpers.

Hanan owns the Postgres session lifecycle and RLS session variable setup.
"""

# TODO: open scoped sessions, set app.tenant_id, and clear request-local state.
