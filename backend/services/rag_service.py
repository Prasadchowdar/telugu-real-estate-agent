import os
import logging
import json
from typing import Optional, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ChromaDB vector store for PDF knowledge base
# ---------------------------------------------------------------------------

CHROMA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_db")
COLLECTION_NAME = "property_knowledge"

_collection = None  # lazy-init


def _get_collection():
    """Lazy-initialize ChromaDB collection."""
    global _collection
    if _collection is not None:
        return _collection

    try:
        import chromadb
        from chromadb.config import Settings

        client = chromadb.PersistentClient(
            path=CHROMA_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            f"ChromaDB collection '{COLLECTION_NAME}' ready – "
            f"{_collection.count()} documents"
        )
        return _collection
    except Exception as e:
        logger.error(f"Failed to initialize ChromaDB: {e}")
        raise


# ---------------------------------------------------------------------------
# Embedding helper  (uses sentence-transformers for Telugu support)
# ---------------------------------------------------------------------------

_embed_model = None


def _get_embedder():
    """Lazy-load a multilingual sentence-transformer model."""
    global _embed_model
    if _embed_model is not None:
        return _embed_model

    try:
        from sentence_transformers import SentenceTransformer

        # paraphrase-multilingual-MiniLM supports Telugu
        _embed_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        logger.info("Sentence-transformer model loaded for embeddings")
        return _embed_model
    except Exception as e:
        logger.error(f"Failed to load embedding model: {e}")
        raise


def _embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a list of texts and return list of float vectors."""
    model = _get_embedder()
    embeddings = model.encode(texts, show_progress_bar=False)
    return [emb.tolist() for emb in embeddings]


# ---------------------------------------------------------------------------
# PDF ingestion
# ---------------------------------------------------------------------------


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


async def ingest_pdf(file) -> dict:
    """
    Ingest a PDF file into the ChromaDB vector store.

    Steps:
        1. Save uploaded file to temp location
        2. Extract text with pdfplumber
        3. Chunk into ~500 char pieces with overlap
        4. Embed with sentence-transformers
        5. Store in ChromaDB
    """
    import tempfile
    import pdfplumber

    collection = _get_collection()

    # Save to temp file
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Extract text page by page
        all_text = ""
        page_count = 0
        with pdfplumber.open(tmp_path) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text += text + "\n\n"

        if not all_text.strip():
            return {
                "status": "error",
                "message": "No text could be extracted from the PDF",
            }

        # Chunk text
        chunks = _chunk_text(all_text)
        logger.info(
            f"PDF '{file.filename}': {page_count} pages, "
            f"{len(all_text)} chars, {len(chunks)} chunks"
        )

        # Embed chunks
        embeddings = _embed_texts(chunks)

        # Store in ChromaDB with metadata
        ids = [f"{file.filename}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {"source": file.filename, "chunk_index": i, "page_count": page_count}
            for i in range(len(chunks))
        ]

        # Upsert (handles re-uploads of same file)
        collection.upsert(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        logger.info(
            f"Ingested {len(chunks)} chunks from '{file.filename}' into ChromaDB"
        )
        return {
            "status": "success",
            "message": f"PDF ingested: {page_count} pages, {len(chunks)} chunks stored",
            "filename": file.filename,
            "chunks": len(chunks),
            "total_documents": collection.count(),
        }

    except Exception as e:
        logger.error(f"PDF ingestion failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Ingestion failed: {str(e)}"}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# RAG search — called during real-time voice conversation
# ---------------------------------------------------------------------------


async def search_context(query: str, top_k: int = 3) -> Optional[str]:
    """
    Search the vector store for chunks relevant to the user's query.
    Returns formatted context string or None if no results.

    This runs in ~50-100ms and is called once per conversation turn,
    between STT completion and LLM generation.
    """
    try:
        collection = _get_collection()

        if collection.count() == 0:
            logger.info("RAG: No documents in knowledge base")
            return None

        # Embed the query
        query_embedding = _embed_texts([query])[0]

        # Search
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        if not results["documents"] or not results["documents"][0]:
            return None

        # Format context for LLM injection
        context_parts = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            similarity = 1 - dist  # cosine distance → similarity
            if similarity < 0.15:  # lower threshold for multilingual embeddings
                continue
            source = meta.get("source", "Unknown")
            context_parts.append(f"[Source: {source}]\n{doc}")
            logger.debug(f"RAG: chunk sim={similarity:.3f} from {source}")

        if not context_parts:
            logger.info("RAG: No sufficiently relevant chunks found")
            return None

        context = "\n\n---\n\n".join(context_parts)
        logger.info(
            f"RAG: Found {len(context_parts)} relevant chunks for query: "
            f"'{query[:50]}...'"
        )
        return context

    except Exception as e:
        logger.error(f"RAG search error: {e}", exc_info=True)
        return None


async def get_business_summary() -> Optional[str]:
    """
    Retrieve a summary of the business/company from uploaded PDFs.
    Used to generate a dynamic greeting when a call starts.

    Searches with broad business-related queries to find company name,
    services, and key offerings.
    """
    try:
        collection = _get_collection()
        if collection.count() == 0:
            logger.info("RAG: No documents — cannot extract business info")
            return None

        # Use a broad query to find company/business info
        queries = [
            "company name business details contact information",
            "property real estate services offerings",
        ]

        all_docs = []
        for query in queries:
            query_embedding = _embed_texts([query])[0]
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=min(3, collection.count()),
                include=["documents", "distances"],
            )
            if results["documents"] and results["documents"][0]:
                for doc, dist in zip(results["documents"][0], results["distances"][0]):
                    similarity = 1 - dist
                    if similarity > 0.2 and doc not in all_docs:
                        all_docs.append(doc)

        if not all_docs:
            return None

        # Return the first few chunks as business context
        summary = "\n\n".join(all_docs[:3])
        logger.info(f"RAG: Business summary extracted ({len(summary)} chars)")
        return summary

    except Exception as e:
        logger.error(f"Business summary extraction error: {e}", exc_info=True)
        return None
