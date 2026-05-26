"""Tenant content endpoints.

Mohammad owns ingestion and retrieval-facing APIs.
"""

import uuid
import os
import logging
from typing import List, Optional, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from minio import Minio

from apps.api.app.services.rag_service import index_document, delete_document_index

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "content-store")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class ContentBase(BaseModel):
    title: str = Field(..., max_length=255, description="Document title")
    body: str = Field(..., description="The main text body/content to be chunked and indexed")
    content_type: Literal["faq", "doc", "policy", "service"] = Field(
        ..., description="Must be one of: faq, doc, policy, service"
    )

class ContentCreate(ContentBase):
    pass

class ContentUpdate(ContentBase):
    pass

class ContentResponse(ContentBase):
    id: str
    tenant_id: str

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Dependencies (imported from Hanan's domain; fallbacks provided for local testing)
# ---------------------------------------------------------------------------

try:
    from apps.api.app.core.tenant_context import get_current_tenant_id
except ImportError:
    logger.warning("get_current_tenant_id not found. Using dev fallback.")
    async def get_current_tenant_id() -> str:
        return "dev-tenant-123"

try:
    from apps.api.app.db.session import get_db
except ImportError:
    logger.warning("get_db not found. Using fallback.")
    async def get_db():
        # Placeholder that yields None – replace with real async session
        yield None


# ---------------------------------------------------------------------------
# MinIO Client
# ---------------------------------------------------------------------------

_minio_client = None

def get_minio_client() -> Minio:
    """Return a singleton MinIO client instance."""
    global _minio_client
    if _minio_client is None:
        _minio_client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE,
        )
        # Ensure the bucket exists (idempotent)
        if not _minio_client.bucket_exists(MINIO_BUCKET):
            _minio_client.make_bucket(MINIO_BUCKET)
            logger.info("Created MinIO bucket '%s'", MINIO_BUCKET)
    return _minio_client


async def upload_to_minio(tenant_id: str, content_id: str, body: str) -> None:
    """Store raw content in MinIO under {tenant_id}/content/{content_id}."""
    client = get_minio_client()
    object_name = f"{tenant_id}/content/{content_id}"
    try:
        client.put_object(
            MINIO_BUCKET,
            object_name,
            data=body.encode("utf-8"),
            length=len(body.encode("utf-8")),
            content_type="text/plain",
        )
        logger.info("Uploaded to MinIO: %s", object_name)
    except Exception as e:
        logger.error("MinIO upload failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store file in object storage: {str(e)}",
        )


async def delete_from_minio(tenant_id: str, content_id: str) -> None:
    """Remove raw content from MinIO."""
    client = get_minio_client()
    object_name = f"{tenant_id}/content/{content_id}"
    try:
        client.remove_object(MINIO_BUCKET, object_name)
        logger.info("Deleted from MinIO: %s", object_name)
    except Exception as e:
        logger.error("MinIO deletion failed: %s", e)
        # Not failing the whole request if cleanup fails – log and continue
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file from object storage: {str(e)}",
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/", response_model=ContentResponse, status_code=status.HTTP_201_CREATED)
async def upload_content(
    payload: ContentCreate,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload document content.
    - Saves document to the database
    - Chunks text & generates embeddings
    - Uploads the raw text to MinIO
    """
    content_id = str(uuid.uuid4())

    # 1. Insert into `app.content_documents`, but do NOT commit yet.
    sql_insert = """
        INSERT INTO app.content_documents (document_id, tenant_id, title, content, kind)
        VALUES (:document_id, :tenant_id, :title, :content, :kind);
    """
    try:
        await db.execute(
            text(sql_insert),
            {
                "document_id": content_id,
                "tenant_id": tenant_id,
                "title": payload.title,
                "content": payload.body,
                "kind": payload.content_type,
            },
        )
    except Exception as e:
        logger.error("DB insert failed: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error")

    # 2. Index (chunk + embed) – this is part of the same transaction.
    try:
        await index_document(
            tenant_id=tenant_id,
            content_id=content_id,
            title=payload.title,
            text=payload.body,
            content_type=payload.content_type,
            db_session=db,
        )
    except Exception as e:
        logger.error("Indexing failed: %s", e)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Content saved but vector indexing failed. Transaction rolled back.",
        )

    # 3. At this point both DB insert and indexing succeeded → commit.
    await db.commit()

    # 4. Upload raw file to MinIO (outside DB transaction)
    await upload_to_minio(tenant_id, content_id, payload.body)

    return ContentResponse(
        id=content_id,
        tenant_id=tenant_id,
        title=payload.title,
        body=payload.body,
        content_type=payload.content_type,
    )


@router.put("/{content_id}", response_model=ContentResponse)
async def update_content(
    content_id: str,
    payload: ContentUpdate,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Update existing document content.
    - Verifies document belongs to requesting tenant
    - Updates DB representation
    - Re-chunks, re-embeds, and re-indexes
    - Updates raw text in MinIO
    """
    # 1. Verify existence and tenant ownership
    check_sql = "SELECT document_id FROM app.content_documents WHERE document_id = :id AND tenant_id = :tenant_id;"
    row = (await db.execute(text(check_sql), {"id": content_id, "tenant_id": tenant_id})).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found or unauthorized")

    # 2. Update local DB (no commit yet)
    update_sql = """
        UPDATE app.content_documents
        SET title = :title, content = :content, kind = :kind
        WHERE document_id = :id AND tenant_id = :tenant_id;
    """
    try:
        await db.execute(
            text(update_sql),
            {
                "id": content_id,
                "tenant_id": tenant_id,
                "title": payload.title,
                "content": payload.body,
                "kind": payload.content_type,
            },
        )
    except Exception as e:
        logger.error("DB update failed: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error")

    # 3. Re-index (within same transaction)
    try:
        await index_document(
            tenant_id=tenant_id,
            content_id=content_id,
            title=payload.title,
            text=payload.body,
            content_type=payload.content_type,
            db_session=db,
        )
    except Exception as e:
        logger.error("Re-indexing failed: %s", e)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Content updated but vector re-indexing failed. Rolled back.",
        )

    # Commit after DB and embeddings succeed
    await db.commit()

    # 4. Update MinIO object
    await upload_to_minio(tenant_id, content_id, payload.body)

    return ContentResponse(
        id=content_id,
        tenant_id=tenant_id,
        title=payload.title,
        body=payload.body,
        content_type=payload.content_type,
    )


@router.delete("/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_content(
    content_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete document and all associated embeddings / files.
    - Verifies document belongs to requesting tenant
    - Deletes from content table
    - Deletes matching vector index embeddings
    - Deletes matching MinIO object
    """
    # 1. Verify ownership
    check_sql = "SELECT document_id FROM app.content_documents WHERE document_id = :id AND tenant_id = :tenant_id;"
    row = (await db.execute(text(check_sql), {"id": content_id, "tenant_id": tenant_id})).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found or unauthorized")

    # 2. Delete from content_documents table
    delete_sql = "DELETE FROM app.content_documents WHERE document_id = :id AND tenant_id = :tenant_id;"
    try:
        await db.execute(text(delete_sql), {"id": content_id, "tenant_id": tenant_id})
    except Exception as e:
        logger.error("DB delete failed: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error")

    # 3. Delete embeddings (still inside transaction)
    try:
        await delete_document_index(tenant_id, content_id, db_session=db)
    except Exception as e:
        logger.error("Embedding deletion failed: %s", e)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove vector index. Rolled back.",
        )

    await db.commit()

    # 4. Delete MinIO object (outside transaction)
    await delete_from_minio(tenant_id, content_id)


@router.get("/", response_model=List[ContentResponse])
async def list_content(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """
    List content for the current tenant (paginated).
    - Automatically filtered by tenant_id
    """
    sql_list = """
        SELECT document_id AS id, tenant_id, title, content AS body, kind AS content_type
        FROM app.content_documents
        WHERE tenant_id = :tenant_id
        LIMIT :limit OFFSET :offset;
    """
    try:
        result = await db.execute(
            text(sql_list),
            {"tenant_id": tenant_id, "limit": limit, "offset": offset},
        )
        rows = result.fetchall()
        return [
            ContentResponse(
                id=row.id,
                tenant_id=row.tenant_id,
                title=row.title,
                body=row.body,
                content_type=row.content_type,
            )
            for row in rows
        ]
    except Exception as e:
        logger.error("List query failed: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve content")