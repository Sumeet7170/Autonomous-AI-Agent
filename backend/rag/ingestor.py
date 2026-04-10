"""
RAG Ingestor — PDF/Document → Text Chunks

Handles:
  1. Reading PDFs with PyMuPDF (fast, handles scanned docs better than pypdf)
  2. Cleaning and normalizing extracted text
  3. Splitting text into overlapping chunks using a character-based splitter
  4. Attaching metadata to each chunk (filename, page, chunk_id)

Returns a list of Document objects ready to be embedded.
"""
import re
import uuid
from pathlib import Path

import fitz  # PyMuPDF
from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)


class Document:
    """
    Represents a single text chunk from a larger document.
    This is the atomic unit that gets embedded and stored in the vector DB.
    """
    def __init__(self, content: str, metadata: dict):
        self.content = content
        self.metadata = metadata
        self.chunk_id = metadata.get("chunk_id", str(uuid.uuid4())[:8])


def _clean_text(text: str) -> str:
    """
    Clean raw PDF text:
    - Remove excessive whitespace
    - Normalize line breaks
    - Strip null bytes and control characters
    """
    text = text.replace("\x00", "")                  # Remove null bytes
    text = re.sub(r"[ \t]+", " ", text)              # Collapse spaces/tabs
    text = re.sub(r"\n{3,}", "\n\n", text)           # Max 2 consecutive newlines
    text = re.sub(r"-\n", "", text)                  # Fix hyphenated line breaks
    return text.strip()


def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """
    Split text into overlapping fixed-size chunks.

    Why overlapping?
    - Ensures context is not lost at chunk boundaries
    - A sentence that spans two chunks will appear in both — so no information is cut off

    This is a character-based splitter (fast and predictable).
    For production at scale, switch to a token-based splitter.
    """
    if not text.strip():
        return []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)

        # Try to end at a sentence boundary (period, newline)
        # This makes chunks more semantically coherent
        if end < text_len:
            boundary = max(
                text.rfind(".", start, end),
                text.rfind("\n", start, end),
            )
            if boundary > start + chunk_size // 2:
                end = boundary + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - chunk_overlap  # Move back by overlap amount

    return chunks


async def ingest_pdf(file_path: str, namespace: str = "default") -> list[Document]:
    """
    Main ingestion function. Takes a PDF file path, returns a list of Document chunks.

    Args:
        file_path: Absolute path to the PDF file
        namespace: Logical group name (e.g., "project_docs", "legal_contracts")

    Returns:
        List of Document objects (chunks), ready for embedding
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    filename = path.name
    logger.info("Starting PDF ingestion", filename=filename, namespace=namespace)

    try:
        doc = fitz.open(file_path)
    except Exception as e:
        raise ValueError(f"Failed to open PDF '{filename}': {e}")

    all_chunks: list[Document] = []
    total_pages = len(doc)

    for page_num, page in enumerate(doc, start=1):
        raw_text = page.get_text("text")
        cleaned = _clean_text(raw_text)

        if not cleaned:
            logger.debug("Empty page skipped", page=page_num, filename=filename)
            continue

        # Split page text into chunks
        chunks = _split_text(
            text=cleaned,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )

        for i, chunk_text in enumerate(chunks):
            chunk_id = f"{filename}__p{page_num}__c{i}"
            all_chunks.append(Document(
                content=chunk_text,
                metadata={
                    "chunk_id": chunk_id,
                    "filename": filename,
                    "page": page_num,
                    "chunk_index": i,
                    "namespace": namespace,
                    "file_path": str(path),
                },
            ))

    doc.close()

    logger.info(
        "PDF ingestion complete",
        filename=filename,
        pages=total_pages,
        chunks=len(all_chunks),
        namespace=namespace,
    )
    return all_chunks
