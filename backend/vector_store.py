"""
Vector Store para RAG jurídico
Usa Docling (SimplePipeline — sem modelos ML pesados) para extração de texto
+ ChromaDB para busca semântica.

Estratégia de indexação:
  - Apenas documentos marcados como "relevantes" pelo sharepoint_sync são indexados.
  - Relevância é determinada por pasta, palavra-chave no nome, ou tamanho máximo.
  - Fallback automático: python-docx → PyMuPDF → UTF-8 raw se Docling falhar.
"""

from __future__ import annotations

import os
import hashlib
import tempfile
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────────────────

CHROMA_PATH = os.getenv("CHROMA_PATH", str(Path(__file__).parent / "chroma_db"))
COLLECTION_NAME = "jurisgen_docs"
CHUNK_SIZE = 800   # chars
CHUNK_OVERLAP = 100

# Docling artifacts path — avoids random cache dirs; set before any import
_DOCLING_ARTIFACTS = os.getenv(
    "DOCLING_ARTIFACTS_PATH",
    str(Path(__file__).parent / ".docling_artifacts"),
)
os.environ.setdefault("DOCLING_ARTIFACTS_PATH", _DOCLING_ARTIFACTS)


# ─── Lazy singletons ─────────────────────────────────────────────────────────

_chroma_client = None
_collection = None
_embedder = None
_docling_converter = None


def _get_embedder():
    """Lazy-load the sentence-transformer embedder (multilingual)."""
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer  # type: ignore
        model_name = os.getenv(
            "EMBEDDING_MODEL",
            "paraphrase-multilingual-mpnet-base-v2"
        )
        logger.info(f"[VectorStore] Carregando modelo de embeddings: {model_name}")
        _embedder = SentenceTransformer(model_name)
        logger.info("[VectorStore] Modelo carregado.")
    return _embedder


def _get_collection():
    """Return (or create) the ChromaDB collection."""
    global _chroma_client, _collection
    if _collection is None:
        import chromadb  # type: ignore
        _chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = _chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            f"[VectorStore] ChromaDB pronto em '{CHROMA_PATH}'. "
            f"Documentos: {_collection.count()}"
        )
    return _collection


def _get_docling_converter():
    """
    Return a lazy singleton Docling converter using SimplePipeline.

    SimplePipeline does NOT download heavy layout/table ML models.
    It uses docling-parse (native PDF parser) and direct DOCX/TXT parsing.
    Suitable for text-heavy legal documents.
    """
    global _docling_converter
    if _docling_converter is None:
        try:
            from docling.document_converter import DocumentConverter, PdfFormatOption  # type: ignore
            from docling.datamodel.base_models import InputFormat  # type: ignore
            from docling.datamodel.pipeline_options import PdfPipelineOptions  # type: ignore
            from docling.pipeline.simple_pipeline import SimplePipeline  # type: ignore

            opts = PdfPipelineOptions()
            opts.do_ocr = False               # skip Tesseract — not needed for digital PDFs
            opts.do_table_structure = False   # skip ML table detection
            opts.generate_picture_images = False

            _docling_converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(
                        pipeline_cls=SimplePipeline,
                        pipeline_options=opts,
                    )
                }
            )
            logger.info("[Docling] Converter inicializado com SimplePipeline (sem ML pesado).")
        except Exception as e:
            logger.warning(f"[Docling] Não foi possível inicializar: {e}")
            _docling_converter = None
    return _docling_converter


# ─── Text chunking ────────────────────────────────────────────────────────────

def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    if not text.strip():
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        start += chunk_size - overlap
    return [c for c in chunks if c]


# ─── Docling extraction ───────────────────────────────────────────────────────

def extract_text_with_docling(file_bytes: bytes, filename: str) -> str:
    """
    Extract structured markdown from a file using Docling SimplePipeline.

    Falls back automatically to python-docx → PyMuPDF → UTF-8 if Docling fails.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    suffix = f".{ext}" if ext else ".pdf"

    converter = _get_docling_converter()
    if converter is not None:
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            try:
                result = converter.convert(tmp_path)
                md_text = result.document.export_to_markdown()
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

            if md_text and md_text.strip():
                logger.info(f"[Docling] Extraídos {len(md_text)} chars de '{filename}'")
                return md_text
        except Exception as e:
            logger.warning(f"[Docling] Falha em '{filename}': {e}. Tentando fallback...")

    # Fallback 1: python-docx
    if ext in ("docx", "doc"):
        try:
            import docx, io  # type: ignore
            doc = docx.Document(io.BytesIO(file_bytes))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            if text.strip():
                logger.info(f"[DOCX fallback] Extraídos {len(text)} chars de '{filename}'")
                return text
        except Exception as e2:
            logger.warning(f"[DOCX fallback] {e2}")

    # Fallback 2: PyMuPDF for PDF
    if ext == "pdf":
        try:
            import fitz, io  # type: ignore
            pdf = fitz.open(stream=file_bytes, filetype="pdf")
            text = "\n".join(page.get_text() for page in pdf)
            pdf.close()
            if text.strip():
                logger.info(f"[PyMuPDF fallback] Extraídos {len(text)} chars de '{filename}'")
                return text
        except Exception as e3:
            logger.warning(f"[PyMuPDF fallback] {e3}")

    # Fallback 3: raw UTF-8
    try:
        return file_bytes.decode("utf-8", errors="ignore")
    except Exception:
        return ""


# ─── Relevance scoring ────────────────────────────────────────────────────────

# Pastas que indicam documentos de referência/base (case-insensitive, substrings)
_REFERENCE_FOLDER_HINTS = [
    "template", "modelo", "referencia", "referência", "base", "padrão",
    "padrao", "minutas", "minuta", "jurisprudencia", "jurisprudência",
    "doutrina", "legislacao", "legislação", "contrato",
]

# Palavras no nome do arquivo que indicam documento de referência
_REFERENCE_NAME_HINTS = [
    "modelo", "template", "referencia", "base", "minuta", "padrão",
    "padrao", "contrato", "peticao", "petição", "inicial", "contestacao",
]


def score_relevance(filename: str, folder: str, file_bytes: bytes | None = None) -> float:
    """
    Score document relevance for indexing (0.0 = irrelevant, 1.0 = highly relevant).

    Used to decide if a document should be fully indexed in ChromaDB or just mirrored.
    """
    name_lower = filename.lower()
    folder_lower = folder.lower()
    score = 0.0

    # Folder hints (strong signal)
    for hint in _REFERENCE_FOLDER_HINTS:
        if hint in folder_lower:
            score += 0.5
            break

    # Filename hints (moderate signal)
    for hint in _REFERENCE_NAME_HINTS:
        if hint in name_lower:
            score += 0.3
            break

    # File extension (weak signal — prefer structured formats)
    ext = name_lower.rsplit(".", 1)[-1] if "." in name_lower else ""
    if ext in ("docx", "doc"):
        score += 0.2  # DOCX = usually editable template/model
    elif ext == "pdf":
        score += 0.1
    elif ext == "txt":
        score += 0.15

    # Penalize very small files (probably not useful content)
    if file_bytes is not None and len(file_bytes) < 2_000:
        score -= 0.3

    return min(max(score, 0.0), 1.0)


# ─── Main indexing function ───────────────────────────────────────────────────

def index_document(
    file_bytes: bytes,
    filename: str,
    folder: str = "",
    web_url: str = "",
    source: str = "sharepoint",
    force: bool = False,
) -> dict:
    """
    Convert a file with Docling (SimplePipeline) and store chunks in ChromaDB.

    Returns:
        {"name": filename, "chunks": N, "chars": M,
         "status": "indexed"|"skipped"|"error", "relevance": float}
    """
    collection = _get_collection()

    # Relevance check
    relevance = score_relevance(filename, folder, file_bytes)

    # Deduplication by content hash
    file_hash = hashlib.sha256(file_bytes).hexdigest()[:16]
    doc_id_base = f"{file_hash}_{filename}"

    if not force:
        existing = collection.get(
            where={"file_hash": file_hash},
            limit=1,
            include=[],
        )
        if existing and existing["ids"]:
            logger.info(f"[VectorStore] '{filename}' já indexado (hash={file_hash}). Pulando.")
            return {"name": filename, "chunks": 0, "chars": 0, "status": "skipped",
                    "relevance": relevance}

    # Extract text via Docling
    text = extract_text_with_docling(file_bytes, filename)
    if not text.strip():
        return {"name": filename, "chunks": 0, "chars": 0, "status": "sem texto",
                "relevance": relevance}

    # Chunk the text
    chunks = _chunk_text(text)
    if not chunks:
        return {"name": filename, "chunks": 0, "chars": len(text), "status": "sem chunks",
                "relevance": relevance}

    # Delete old chunks for this document (by filename, for re-indexing)
    try:
        old = collection.get(where={"filename": filename}, include=[], limit=10000)
        if old and old["ids"]:
            collection.delete(ids=old["ids"])
            logger.info(f"[VectorStore] Removidos {len(old['ids'])} chunks antigos de '{filename}'")
    except Exception as e:
        logger.warning(f"[VectorStore] Erro ao remover chunks antigos: {e}")

    # Generate embeddings
    embedder = _get_embedder()
    embeddings = embedder.encode(chunks, show_progress_bar=False, batch_size=32).tolist()

    # Prepare batch for ChromaDB
    ids = [f"{doc_id_base}_chunk{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "filename": filename,
            "folder": folder,
            "web_url": web_url,
            "source": source,
            "file_hash": file_hash,
            "chunk_index": i,
            "total_chunks": len(chunks),
            "relevance": round(relevance, 2),
        }
        for i in range(len(chunks))
    ]

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )

    logger.info(f"[VectorStore] '{filename}': {len(chunks)} chunks indexados (relevância={relevance:.2f}).")
    return {
        "name": filename,
        "chunks": len(chunks),
        "chars": len(text),
        "status": "indexed",
        "relevance": relevance,
        "preview": text[:200],
    }


# ─── Semantic search ──────────────────────────────────────────────────────────

def semantic_search(
    query: str,
    n_results: int = 5,
    filter_source: Optional[str] = None,
) -> list[dict]:
    """
    Search the vector store for chunks semantically similar to `query`.

    Returns list of:
        {"text": ..., "filename": ..., "folder": ..., "web_url": ...,
         "chunk_index": ..., "score": ..., "source": ..., "relevance": ...}
    """
    collection = _get_collection()
    if collection.count() == 0:
        return []

    embedder = _get_embedder()
    query_embedding = embedder.encode([query], show_progress_bar=False)[0].tolist()

    where = {"source": filter_source} if filter_source else None

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, collection.count()),
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    output = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]

    for text, meta, dist in zip(docs, metas, dists):
        output.append({
            "text": text,
            "filename": meta.get("filename", ""),
            "folder": meta.get("folder", ""),
            "web_url": meta.get("web_url", ""),
            "chunk_index": meta.get("chunk_index", 0),
            "source": meta.get("source", ""),
            "relevance": meta.get("relevance", 0.0),
            "score": round(1 - dist, 4),  # cosine similarity
        })

    return output


# ─── Stats ────────────────────────────────────────────────────────────────────

def get_stats() -> dict:
    """Return stats about the vector store."""
    try:
        collection = _get_collection()
        total = collection.count()
        sample = collection.get(limit=min(total, 10000), include=["metadatas"])
        filenames = list({m.get("filename", "") for m in (sample.get("metadatas") or [])})
        return {
            "total_chunks": total,
            "total_documents": len(filenames),
            "documents": filenames[:50],
            "chroma_path": CHROMA_PATH,
        }
    except Exception as e:
        return {"error": str(e), "total_chunks": 0, "total_documents": 0}


def delete_document(filename: str) -> int:
    """Remove all chunks for a given filename. Returns number of chunks deleted."""
    try:
        collection = _get_collection()
        old = collection.get(where={"filename": filename}, include=[], limit=10000)
        if old and old["ids"]:
            collection.delete(ids=old["ids"])
            return len(old["ids"])
    except Exception as e:
        logger.warning(f"[VectorStore] Erro ao deletar '{filename}': {e}")
    return 0
