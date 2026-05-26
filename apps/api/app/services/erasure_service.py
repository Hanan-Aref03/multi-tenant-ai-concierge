"""Right-to-erasure (GDPR Article 17) — purge all tenant data.

Mohammad owns this module: vectors, conversation memory, and raw files.
Hanan owns the base tables (content_documents, content_chunks) and their RLS.

Call ``purge_tenant()`` from an admin endpoint or a scheduled job.
The function is idempotent — running it twice is safe.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def purge_tenant(
    tenant_id: str,
    db_session,
    redis_client=None,
    minio_client=None,
    minio_bucket: str = "content-store",
) -> dict:
    """
    Delete all data for *tenant_id* across the three storage layers.

    Layers
    ------
    1. pgvector  — ``app.content_chunks`` rows (embeddings + text)
    2. Redis     — all conversation-memory keys matching ``conv:{tenant_id}:*``
    3. MinIO     — all objects under the ``{tenant_id}/`` prefix

    Returns
    -------
    dict with keys:
        chunks_deleted  int   rows removed from app.content_chunks
        redis_deleted   int   Redis keys deleted
        minio_deleted   int   MinIO objects deleted
        errors          list  non-fatal error messages (empty means clean run)
    """
    result = {
        "chunks_deleted": 0,
        "redis_deleted": 0,
        "minio_deleted": 0,
        "errors": [],
    }

    # ------------------------------------------------------------------
    # 1. pgvector: delete all chunks for this tenant
    # ------------------------------------------------------------------
    if db_session is not None:
        try:
            from sqlalchemy import text as sa_text

            delete_sql = """
                DELETE FROM app.content_chunks
                WHERE tenant_id = :tenant_id;
            """
            res = await db_session.execute(
                sa_text(delete_sql), {"tenant_id": tenant_id}
            )
            await db_session.commit()
            result["chunks_deleted"] = res.rowcount or 0
            logger.info(
                "Erasure: deleted %d chunk rows for tenant=%s",
                result["chunks_deleted"], tenant_id,
            )
        except Exception as exc:
            msg = f"pgvector deletion failed for tenant={tenant_id}: {exc}"
            logger.error(msg)
            result["errors"].append(msg)
    else:
        logger.warning("Erasure: no db_session provided; skipping pgvector deletion")

    # ------------------------------------------------------------------
    # 2. Redis: delete all conversation-memory keys for this tenant
    # ------------------------------------------------------------------
    if redis_client is not None:
        try:
            pattern = f"conv:{tenant_id}:*"
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)
                if keys:
                    await redis_client.delete(*keys)
                    deleted += len(keys)
                if cursor == 0:
                    break
            result["redis_deleted"] = deleted
            logger.info(
                "Erasure: deleted %d Redis keys for tenant=%s",
                deleted, tenant_id,
            )
        except Exception as exc:
            msg = f"Redis deletion failed for tenant={tenant_id}: {exc}"
            logger.error(msg)
            result["errors"].append(msg)
    else:
        logger.warning("Erasure: no redis_client provided; skipping Redis deletion")

    # ------------------------------------------------------------------
    # 3. MinIO: delete all objects under {tenant_id}/ prefix
    # ------------------------------------------------------------------
    if minio_client is not None:
        try:
            prefix = f"{tenant_id}/"
            deleted = 0
            # minio-py list_objects is synchronous; wrap in executor if needed
            objects = minio_client.list_objects(minio_bucket, prefix=prefix, recursive=True)
            names = [obj.object_name for obj in objects]
            for name in names:
                minio_client.remove_object(minio_bucket, name)
                deleted += 1
            result["minio_deleted"] = deleted
            logger.info(
                "Erasure: deleted %d MinIO objects for tenant=%s",
                deleted, tenant_id,
            )
        except Exception as exc:
            msg = f"MinIO deletion failed for tenant={tenant_id}: {exc}"
            logger.error(msg)
            result["errors"].append(msg)
    else:
        logger.warning("Erasure: no minio_client provided; skipping MinIO deletion")

    logger.info(
        "Erasure complete for tenant=%s — chunks=%d redis=%d minio=%d errors=%d",
        tenant_id,
        result["chunks_deleted"],
        result["redis_deleted"],
        result["minio_deleted"],
        len(result["errors"]),
    )
    return result
