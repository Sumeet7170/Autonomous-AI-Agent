"""
File Upload API Route — POST /api/upload

Handles PDF uploads, ingestion, and embedding in one atomic operation.
Returns ingestion metadata (chunk count, pages, etc.) to the frontend.

Flow:
  1. Receive PDF via multipart/form-data
  2. Validate file type and size
  3. Save to disk
  4. Run RAG ingestor (extract text + chunk)
  5. Embed all chunks and store in FAISS
  6. Save metadata to database
  7. Return UploadResponse
"""
import uuid
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.logger import get_logger
from db.database import get_db
from db.models import DocumentRecord
from rag.ingestor import ingest_pdf
from rag.vector_store import vector_store
from models.schemas import UploadResponse, DocumentInfo

router = APIRouter(prefix="/api/upload", tags=["upload"])
logger = get_logger(__name__)


@router.post("", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    namespace: str = Form(default="default"),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a PDF document and ingest it into the RAG system.

    - `file`: PDF file (multipart/form-data)
    - `namespace`: Logical group for this document (e.g., "legal", "research")

    The ingestion (chunking + embedding) runs synchronously so the frontend
    knows exactly how many chunks were created before the response returns.
    For very large files (>10 MB), consider moving this to a background task.
    """
    # ── Validate file type ────────────────────────────────────────────────────
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported. Please upload a .pdf file.",
        )

    # ── Validate file size ────────────────────────────────────────────────────
    content = await file.read()
    size_bytes = len(content)
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024

    if size_bytes > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size_bytes // (1024*1024)} MB). Maximum is {settings.MAX_FILE_SIZE_MB} MB.",
        )

    # ── Save file to disk ─────────────────────────────────────────────────────
    file_id = str(uuid.uuid4())
    upload_dir = Path(settings.UPLOAD_DIR) / namespace
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_filename = f"{file_id}_{file.filename.replace(' ', '_')}"
    file_path = upload_dir / safe_filename

    with open(file_path, "wb") as f:
        f.write(content)

    logger.info("File saved", filename=file.filename, size_bytes=size_bytes, namespace=namespace)

    # ── Create DB record (status: processing) ─────────────────────────────────
    doc_record = DocumentRecord(
        id=file_id,
        filename=file.filename,
        namespace=namespace,
        file_path=str(file_path),
        size_bytes=size_bytes,
        status="processing",
    )
    db.add(doc_record)
    await db.flush()

    try:
        # ── Ingest: extract + chunk ───────────────────────────────────────────
        documents = await ingest_pdf(str(file_path), namespace=namespace)

        if not documents:
            raise ValueError("No text could be extracted from this PDF. It may be scanned/image-based.")

        # ── Embed + store in vector DB ────────────────────────────────────────
        chunks_added = await vector_store.add_documents(documents)

        # ── Update DB record ──────────────────────────────────────────────────
        # Get page count from last chunk's metadata
        page_count = max(d.metadata.get("page", 1) for d in documents)

        doc_record.chunk_count = chunks_added
        doc_record.page_count = page_count
        doc_record.status = "ready"
        doc_record.processed_at = datetime.utcnow()

        logger.info(
            "Document ingested successfully",
            filename=file.filename,
            chunks=chunks_added,
            pages=page_count,
            namespace=namespace,
        )

        return UploadResponse(
            filename=file.filename,
            file_id=file_id,
            namespace=namespace,
            chunks_created=chunks_added,
            pages_processed=page_count,
            message=f"✅ Successfully ingested '{file.filename}': {chunks_added} chunks from {page_count} pages.",
        )

    except Exception as e:
        doc_record.status = "failed"
        doc_record.error = str(e)
        logger.error("Ingestion failed", filename=file.filename, error=str(e))
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")


@router.get("/documents", response_model=list[DocumentInfo])
async def list_documents(
    namespace: str = "default",
    db: AsyncSession = Depends(get_db),
):
    """List all uploaded documents in a namespace."""
    from sqlalchemy import select
    result = await db.execute(
        select(DocumentRecord)
        .where(DocumentRecord.namespace == namespace)
        .order_by(DocumentRecord.uploaded_at.desc())
    )
    records = result.scalars().all()

    return [
        DocumentInfo(
            file_id=r.id,
            filename=r.filename,
            namespace=r.namespace,
            chunk_count=r.chunk_count or 0,
            pages=r.page_count or 0,
            size_bytes=r.size_bytes or 0,
            uploaded_at=r.uploaded_at,
        )
        for r in records
    ]


@router.get("/namespaces")
async def list_namespaces():
    """List all available document namespaces."""
    return {"namespaces": vector_store.list_namespaces()}
