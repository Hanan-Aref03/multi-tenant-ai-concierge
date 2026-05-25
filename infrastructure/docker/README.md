# Docker assets

Hanan owns the local platform composition.
Ali Faddel owns the developer bootstrap and image wiring.

Current local stack:
- `postgres` for tenant data and RLS policies
- `redis` for session and short-term memory isolation
- `minio` for object storage and export artifacts
- `vault` for secrets and service tokens

Useful commands:
- `docker compose up -d postgres redis minio vault`
- `docker compose run --rm api-smoke`
- `powershell -ExecutionPolicy Bypass -File scripts/verify_isolation.ps1`

Notes:
- app containers are intentionally deferred until each team lane lands its first slice
- the API spine can still be smoke-tested with the standard-library entry point
