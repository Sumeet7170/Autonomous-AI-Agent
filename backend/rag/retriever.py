"""
RAG Retriever — Semantic Search + LLM Answer Generation

This is the final step in the RAG pipeline:
  1. Takes the user's query
  2. Retrieves the top-K most relevant document chunks from the vector store
  3. Builds a context-stuffed prompt
  4. Asks the LLM to answer ONLY from the retrieved context

The strict "answer only from context" rule is enforced via the system prompt.
If the answer cannot be found in the documents, the LLM says so explicitly.
"""
from core.llm import llm_client
from core.config import settings
from core.logger import get_logger
from rag.vector_store import vector_store
from models.schemas import DocumentSource, QueryResponse

logger = get_logger(__name__)

RAG_SYSTEM_PROMPT = """You are a precise document Q&A assistant.

STRICT RULES — follow these exactly:
1. Answer ONLY using the information in the provided CONTEXT DOCUMENTS below
2. If the answer is not found in the context, say: "I could not find this information in the provided documents."
3. Do NOT make up facts, use prior training knowledge, or add information not in the context
4. Cite which document (filename + page) you found the answer in
5. Be concise and factual — avoid filler phrases like "Based on the context..."
6. If multiple sources say different things, present all of them

Format:
- Answer in clear paragraphs
- End with: **Sources:** [list source file + page]"""


async def retrieve_and_answer(
    query: str,
    namespace: str = "default",
    top_k: int = None,
    session_id: str = "default",
) -> QueryResponse:
    """
    Full RAG pipeline: query → retrieve → answer.

    Args:
        query:      The user's natural language question
        namespace:  Document collection to search in
        top_k:      Number of chunks to retrieve (defaults to settings.TOP_K)
        session_id: For logging and memory association

    Returns:
        QueryResponse with the answer and the source chunks used
    """
    k = top_k or settings.TOP_K
    logger.info("RAG query", query=query[:100], namespace=namespace, top_k=k)

    # ── Step 1: Retrieve relevant chunks ──────────────────────────────────────
    raw_results = await vector_store.search(query, namespace=namespace, top_k=k)

    if not raw_results:
        logger.warning("No documents found in namespace", namespace=namespace)
        return QueryResponse(
            answer=(
                "No documents have been uploaded to this namespace yet. "
                f"Please upload PDF files to the '{namespace}' collection first."
            ),
            sources=[],
            session_id=session_id,
            namespace=namespace,
            query=query,
            model_used=llm_client.model,
        )

    # ── Step 2: Build context for the LLM ────────────────────────────────────
    context_blocks = []
    sources: list[DocumentSource] = []

    for i, result in enumerate(raw_results, start=1):
        context_blocks.append(
            f"[Document {i}] File: {result['filename']} | Page: {result.get('page', 'N/A')}\n"
            f"{result['content']}"
        )
        sources.append(DocumentSource(
            filename=result["filename"],
            page=result.get("page"),
            chunk_id=result["chunk_id"],
            content=result["content"][:300] + "..." if len(result["content"]) > 300 else result["content"],
            score=result["score"],
        ))

    context_str = "\n\n---\n\n".join(context_blocks)

    # ── Step 3: Generate answer with strict context ───────────────────────────
    messages = [
        {"role": "system", "content": RAG_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"CONTEXT DOCUMENTS:\n\n{context_str}\n\n"
                f"---\n\nUSER QUESTION: {query}\n\n"
                "Answer using ONLY the context documents above."
            ),
        },
    ]

    answer = await llm_client.complete(messages, temperature=0.2, max_tokens=2048)

    logger.info(
        "RAG answer generated",
        query_len=len(query),
        context_chunks=len(raw_results),
        answer_len=len(answer),
    )

    return QueryResponse(
        answer=answer,
        sources=sources,
        session_id=session_id,
        namespace=namespace,
        query=query,
        model_used=llm_client.model,
    )


async def stream_rag_answer(
    query: str,
    namespace: str = "default",
    top_k: int = None,
):
    """
    Streaming version of retrieve_and_answer.
    Yields text chunks for SSE streaming to the frontend.
    Also yields source metadata as the first SSE event.
    """
    import json
    k = top_k or settings.TOP_K

    raw_results = await vector_store.search(query, namespace=namespace, top_k=k)

    if not raw_results:
        yield f"data: No documents found in namespace '{namespace}'.\n\n"
        return

    # Send sources first as a metadata event
    sources = [
        {
            "filename": r["filename"],
            "page": r.get("page"),
            "score": r["score"],
        }
        for r in raw_results
    ]
    yield f"data: {json.dumps({'type': 'sources', 'data': sources})}\n\n"

    # Build context
    context_blocks = [
        f"[Document {i+1}] File: {r['filename']} | Page: {r.get('page', 'N/A')}\n{r['content']}"
        for i, r in enumerate(raw_results)
    ]
    context_str = "\n\n---\n\n".join(context_blocks)

    messages = [
        {"role": "system", "content": RAG_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"CONTEXT DOCUMENTS:\n\n{context_str}\n\n---\n\nUSER QUESTION: {query}",
        },
    ]

    async for chunk in llm_client.stream(messages, temperature=0.2):
        yield f"data: {json.dumps({'type': 'token', 'data': chunk})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"
