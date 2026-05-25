# MinIO bucket plan

Hanan owns the object storage boundary.
Mohammad owns any retrieval or memory flow that reads tenant content.

Recommended buckets:
- `tenant-uploads` for raw tenant documents and attachments
- `tenant-exports` for generated CSV/PDF exports
- `platform-artifacts` for platform-level build artifacts and diagnostics
- `eval-artifacts` for evaluation captures and red-team evidence

Rules:
- every object key starts with `tenant_id/`
- object lifecycle policies must support tenant erasure
- signed URLs must be short-lived and tenant-scoped
