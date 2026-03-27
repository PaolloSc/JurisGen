"""
JurisGen AI - Backend FastAPI
Gerador Adaptativo de Documentos Jurídicos
"""

import os
import uuid
from datetime import datetime
from typing import Any, Optional
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

from llm.client import LLMClient, is_valid_legal_pt
llm = LLMClient()


# ─── Jurema 7B Prompts por Contexto ──────────────────────────
JUREMA_CHAT_SYSTEM = """Você é o modelo Jurema, especialista em direito brasileiro com foco em jurisprudência.
Analise a pergunta e forneça:
1. Jurisprudência relevante (ementas, súmulas, OJs) que complementa
2. Artigos de lei específicos aplicáveis
3. Se houver erro jurídico, aponte com gentileza

Seja conciso (máx 300 palavras). Responda em pt-BR.
NÃO invente citações — use apenas conhecimento real."""

JUREMA_ADVERSARIAL_SYSTEM = """Você é o modelo Jurema, especialista em jurisprudência brasileira.
Encontre jurisprudência que FORTALECE a posição da parte adversária (réu).
Para cada ponto vulnerável, cite ementas/súmulas que o réu usaria.
Seja específico: tribunais, nº processo quando possível. Máx 500 palavras. pt-BR.
NÃO invente citações — use apenas jurisprudência real."""

JUREMA_VALIDATION_SYSTEM = """Você é o modelo Jurema, validador jurídico.
Verifique se a correção é consistente com jurisprudência brasileira.
Responda em JSON válido:
{"valida": true/false, "jurisprudencia_reforco": "...", "jurisprudencia_contradiz": "...", "recomendacao": "..."}
NÃO invente citações."""

# Importar busca no JusBrasil
try:
    from jusbrasil_search import JusBrasilSearch
    jusbrasil_search = JusBrasilSearch()
except ImportError:
    jusbrasil_search = None


# ============== SharePoint / Graph API ==============

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

def _get_graph_token() -> str:
    """Obtain OAuth2 token via client credentials. Raises HTTPException if creds missing."""
    tenant_id = os.getenv("MS_TENANT_ID")
    client_id = os.getenv("MS_CLIENT_ID")
    client_secret = os.getenv("MS_CLIENT_SECRET")

    if not all([tenant_id, client_id, client_secret]):
        raise HTTPException(
            status_code=503,
            detail="SharePoint credentials not configured in environment variables. "
                   "Set MS_TENANT_ID, MS_CLIENT_ID and MS_CLIENT_SECRET in .env"
        )

    import msal
    msal_app = msal.ConfidentialClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=client_secret,
    )
    result = msal_app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        error = result.get("error_description", result.get("error", "Unknown error"))
        raise HTTPException(status_code=502, detail=f"Failed to authenticate with Azure AD: {error}")
    return result["access_token"]


async def _sharepoint_search(query: str, limit: int = 10) -> list[dict]:
    """Search SharePoint documents using Microsoft Graph Search API."""
    token = _get_graph_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    payload = {
        "requests": [{
            "entityTypes": ["driveItem"],
            "query": {"queryString": f"{query} filetype:docx OR filetype:doc"},
            "size": limit,
            "fields": ["id", "name", "webUrl", "parentReference", "lastModifiedDateTime", "size"],
        }]
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(f"{GRAPH_BASE}/search/query", headers=headers, json=payload)
        if not resp.is_success:
            raise HTTPException(status_code=resp.status_code, detail=f"Graph API error: {resp.text}")
        data = resp.json()

    hits = (
        data.get("value", [{}])[0]
            .get("hitsContainers", [{}])[0]
            .get("hits", [])
    )

    results = []
    for hit in hits:
        resource = hit.get("resource", {})
        parent = resource.get("parentReference", {})
        results.append({
            "id": resource.get("id", ""),
            "name": resource.get("name", ""),
            "web_url": resource.get("webUrl", ""),
            "drive_id": parent.get("driveId", ""),
            "site_id": parent.get("siteId", ""),
            "last_modified": resource.get("lastModifiedDateTime", ""),
            "summary": hit.get("summary", ""),
        })
    return results


async def _get_document_content(drive_id: str, item_id: str) -> str:
    """Download and extract structured text from a SharePoint document using Docling."""
    token = _get_graph_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Get file metadata to know the extension
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        meta_resp = await client.get(
            f"{GRAPH_BASE}/drives/{drive_id}/items/{item_id}",
            headers=headers,
        )
        file_name = meta_resp.json().get("name", "document") if meta_resp.is_success else "document"

        resp = await client.get(
            f"{GRAPH_BASE}/drives/{drive_id}/items/{item_id}/content",
            headers=headers,
        )
        if not resp.is_success:
            raise HTTPException(status_code=resp.status_code, detail="Failed to download document")
        content_bytes = resp.content

    # Docling: structured extraction with layout, tables, headings
    try:
        import tempfile
        from docling.document_converter import DocumentConverter

        suffix = "." + file_name.rsplit(".", 1)[-1] if "." in file_name else ".pdf"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content_bytes)
            tmp_path = tmp.name

        converter = DocumentConverter()
        result = converter.convert(tmp_path)
        md_text = result.document.export_to_markdown()

        import os
        os.unlink(tmp_path)

        if md_text and md_text.strip():
            return md_text[:6000]
    except Exception as e:
        print(f"[Docling] Falha na extração: {e}. Tentando fallback...")

    # Fallback: python-docx para DOCX
    try:
        import docx, io
        doc = docx.Document(io.BytesIO(content_bytes))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())[:3000]
    except Exception:
        pass

    # Fallback: PyPDF2 para PDF
    try:
        import PyPDF2, io
        reader = PyPDF2.PdfReader(io.BytesIO(content_bytes))
        text = "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
        if text.strip():
            return text[:4000]
    except Exception:
        pass

    if b'\x00' in content_bytes[:1000] or content_bytes[:4] == b'%PDF':
        return "[Documento em formato binário não suportado ou falha na extração de texto.]"

    try:
        return content_bytes[:4000].decode("utf-8", errors="ignore")
    except Exception:
        return "[Falha ao tentar ler o arquivo como texto UTF-8]"


# ============== CNJ DataJud API ==============

async def _cnj_search(tribunal: str, query: str, limit: int = 10) -> list[dict]:
    """Search for a process or keywords in CNJ DataJud API."""
    # Using the public API Key provided in CNJ's documentation as fallback
    api_key = os.getenv("CNJ_API_KEY", "cDZpZl9JTUJ0TXlPQU0xcUpFeVE6Ym9Ld2VTb0dUNHkyMW1id211MExOQQ==")
    
    # CNJ endpoint uses lowercase 'api_publica_{sigla}'
    url = f"https://api-publica.datajud.cnj.jus.br/api_publica_{tribunal.lower()}/_search"
    headers = {
        "Authorization": f"APIKey {api_key}",
        "Content-Type": "application/json"
    }
    
    import re
    # If the query is mostly digits, assume it's a process number search
    is_processo = bool(re.match(r'^[\d\.\-]+$', query.strip()))
    
    if is_processo:
        numero = re.sub(r'[^\d]', '', query)
        payload = {
            "query": {
                "match": {
                    "numeroProcesso": numero
                }
            },
            "size": limit
        }
    else:
        # Generic text search in class, subjects, and judging organ
        payload = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["classe.nome", "assuntos.nome", "orgaoJulgador.nome"]
                }
            },
            "size": limit
        }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if not resp.is_success:
            print("CNJ API Error:", resp.text)
            raise HTTPException(status_code=resp.status_code, detail=f"CNJ API Error: {resp.text}")
        data = resp.json()

    hits = data.get("hits", {}).get("hits", [])
    results = []
    
    for hit in hits:
        source = hit.get("_source", {})
        
        # safely extract subjects & movements
        assuntos = source.get("assuntos", [])
        assunto_principal = assuntos[0].get("nome", "") if assuntos else ""
        
        movimentos = source.get("movimentos", [])
        ultimos_movimentos = [m.get("nome", "") for m in reversed(movimentos[-3:])] if movimentos else []
        
        results.append({
            "numeroProcesso": source.get("numeroProcesso", ""),
            "classe": source.get("classe", {}).get("nome", ""),
            "tribunal": source.get("tribunal", tribunal.upper()),
            "dataAjuizamento": source.get("dataAjuizamento", ""),
            "orgaoJulgador": source.get("orgaoJulgador", {}).get("nome", ""),
            "assuntoPrincipal": assunto_principal,
            "movimentos": ultimos_movimentos,
            "grau": source.get("grau", "")
        })
        
    return results


# ============== Models ==============

class SessionCreate(BaseModel):
    doc_type: Optional[str] = None


class Session(BaseModel):
    id: str
    doc_type: Optional[str] = None
    answers: dict[str, Any] = {}
    outline: Optional[dict[str, Any]] = None
    messages: list[dict[str, Any]] = []
    style_refs: list[dict[str, Any]] = []
    answer_rounds: int = 0
    created_at: datetime
    updated_at: datetime


class SharePointSearchRequest(BaseModel):
    query: str
    limit: int = 10


class SharePointAttachRequest(BaseModel):
    session_id: str
    item_id: str
    name: str
    drive_id: Optional[str] = None
    content: Optional[str] = None


class CnjSearchRequest(BaseModel):
    tribunal: str = "tst"
    query: str
    limit: int = 10


class SetTypeRequest(BaseModel):
    session_id: str
    doc_type: str
    context: Optional[str] = None


class AnswerRequest(BaseModel):
    session_id: str
    answers: dict[str, Any]


class ChatRequest(BaseModel):
    session_id: str
    message: str


# ============== App Setup ==============

from sharepoint_sync import (
    start_scheduler as sp_start_scheduler,
    stop_scheduler as sp_stop_scheduler,
    run_sync as sp_run_sync,
    sync_state as sp_sync_state,
    list_local_files as sp_list_local_files,
    FILES_DIR as SP_FILES_DIR,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("JurisGen AI Backend started")
    sp_start_scheduler()
    yield
    # Shutdown
    sp_stop_scheduler()
    print("JurisGen AI Backend shutting down")


app = FastAPI(
    title="JurisGen AI",
    description="Gerador Adaptativo de Documentos Jurídicos",
    version="1.0.0",
    lifespan=lifespan
)

# CORS — allow all origins (frontend is a public static site, no cookies used)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== In-Memory Store ==============

sessions: dict[str, Session] = {}
# Document knowledge base: list of {"name", "content", "source", "web_url", "chunks"}
document_store: list[dict[str, Any]] = []


# ============== Helper Functions ==============

def get_session(session_id: str) -> Session:
    """Get session by ID or raise 404"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[session_id]


def update_session(session: Session):
    """Update session timestamp"""
    session.updated_at = datetime.now()
    sessions[session.id] = session


def _normalize_questions(questions: list) -> list:
    """Normalize question objects to ensure 'text' field is always present."""
    normalized = []
    for q in questions:
        if not isinstance(q, dict):
            continue
        # Ensure 'text' field exists - Claude may use different field names
        text = q.get("text") or q.get("question") or q.get("label") or q.get("title") or ""
        if not text:
            continue  # Skip questions with no text at all
        q["text"] = text
        # Ensure 'id' exists
        if "id" not in q:
            q["id"] = f"q{len(normalized) + 1}"
        # Normalize type
        q_type = str(q.get("type", "text")).lower()
        if q_type in ("choice", "select", "single"):
            q["type"] = "choice"
        elif q_type in ("multiple", "multi", "multiple_choice"):
            q["type"] = "multiple"
        else:
            q["type"] = "text"
        # Normalize options
        if q["type"] in ("choice", "multiple"):
            if "options" in q and isinstance(q["options"], list) and len(q["options"]) > 0:
                opts = []
                for opt in q["options"]:
                    if isinstance(opt, str):
                        opts.append({"id": opt.lower().replace(" ", "_")[:20], "label": opt})
                    elif isinstance(opt, dict):
                        opt_id = opt.get("id") or opt.get("value") or opt.get("label", "opt")
                        opt_label = opt.get("label") or opt.get("text") or opt.get("value") or str(opt_id)
                        opts.append({"id": str(opt_id), "label": opt_label, "desc": opt.get("desc", opt.get("description", ""))})
                    else:
                        opts.append({"id": str(opt), "label": str(opt)})
                q["options"] = opts
            else:
                # choice/multiple without options -> convert to text
                q["type"] = "text"
                q.pop("options", None)
        normalized.append(q)
    return normalized


# ============== API Routes ==============

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "service": "JurisGen AI Backend"}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/llm/status")
async def llm_status():
    """Return LLM availability status"""
    return {"available": True, "provider": "claude_cli", "message": "Claude disponível via backend."}


@app.post("/api/cnj/search")
async def search_processo_cnj(request: CnjSearchRequest):
    """Search for process info or keywords using CNJ DataJud API."""
    try:
        resultados = await _cnj_search(request.tribunal, request.query, request.limit)
        return {"resultados": resultados}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bibliotecas-sharepoint")
async def listar_bibliotecas_sharepoint():
    """List SharePoint libraries (requires credentials)."""
    try:
        token = _get_graph_token()
        site_id = os.getenv("SHAREPOINT_SITE_ID", os.getenv("MS_SITE_ID", ""))
        if not site_id:
            return {"bibliotecas": [], "message": "MS_SITE_ID não configurado."}
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GRAPH_BASE}/sites/{site_id}/lists",
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            if resp.status_code != 200:
                return {"bibliotecas": [], "message": f"Erro ao buscar listas: {resp.status_code}"}
            lists_data = resp.json().get("value", [])
            bibliotecas = [
                {"title": l["displayName"], "id": l["id"]}
                for l in lists_data
                if l.get("list", {}).get("template") == "documentLibrary"
            ]
        return {"bibliotecas": bibliotecas}
    except Exception:
        return {"bibliotecas": [], "message": "Credenciais do SharePoint não configuradas."}


@app.post("/api/listar-sharepoint")
async def listar_documentos_sharepoint(request: dict):
    """List documents in a SharePoint library, recursively listing folders."""
    try:
        token = _get_graph_token()
        drive_id = os.getenv("SHAREPOINT_DRIVE_ID", "")
        if not drive_id:
            return {"documentos": [], "total_documentos": 0, "message": "SHAREPOINT_DRIVE_ID não configurado."}

        biblioteca = request.get("biblioteca", "Documentos")
        headers = {"Authorization": f"Bearer {token}"}
        documentos = []

        folder_id = request.get("folder_id", None)
        if folder_id:
            url = f"{GRAPH_BASE}/drives/{drive_id}/items/{folder_id}/children?$top=50"
        else:
            url = f"{GRAPH_BASE}/drives/{drive_id}/root/children?$top=50"

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=30)
            if resp.status_code != 200:
                return {"documentos": [], "total_documentos": 0, "message": f"Erro {resp.status_code}"}
            for item in resp.json().get("value", []):
                if "folder" in item:
                    documentos.append({
                        "name": item["name"],
                        "type": "folder",
                        "id": item["id"],
                        "web_url": item.get("webUrl", ""),
                        "child_count": item.get("folder", {}).get("childCount", 0),
                        "status": f"{item['folder']['childCount']} itens",
                    })
                else:
                    documentos.append({
                        "name": item.get("name", ""),
                        "type": "file",
                        "id": item["id"],
                        "web_url": item.get("webUrl", ""),
                        "size": item.get("size", 0),
                        "mime": item.get("file", {}).get("mimeType", ""),
                        "modified": item.get("lastModifiedDateTime", ""),
                        "status": "disponível",
                    })

        return {"documentos": documentos, "total_documentos": len(documentos)}
    except Exception as e:
        return {"documentos": [], "total_documentos": 0, "message": str(e)}


# ─── Background indexing state ───
import asyncio
from vector_store import index_document, semantic_search, get_stats as vs_get_stats

indexing_status: dict[str, Any] = {"running": False, "progress": "", "indexed": [], "total_chunks": 0, "error": None}


async def _run_indexing():
    """Background task: download SharePoint docs, extract with Docling, index in ChromaDB."""
    global indexing_status
    indexing_status = {"running": True, "progress": "Iniciando...", "indexed": [], "total_chunks": 0, "error": None}

    try:
        token = _get_graph_token()
        drive_id = os.getenv("SHAREPOINT_DRIVE_ID", "")
        headers_graph = {"Authorization": f"Bearer {token}"}

        # Run blocking Docling/embedding calls in a thread pool
        loop = asyncio.get_event_loop()

        async def index_folder(client, folder_path="root", folder_name=""):
            url = f"{GRAPH_BASE}/drives/{drive_id}/{folder_path}/children?$top=100"
            resp = await client.get(url, headers=headers_graph, timeout=30)
            if resp.status_code != 200:
                return

            for item in resp.json().get("value", []):
                if "folder" in item:
                    subfolder = f"{folder_name}/{item['name']}" if folder_name else item["name"]
                    await index_folder(client, f"items/{item['id']}", subfolder)
                else:
                    name = item.get("name", "")
                    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
                    if ext not in ("docx", "doc", "pdf", "txt"):
                        continue

                    indexing_status["progress"] = f"Baixando e convertendo: {name}"

                    try:
                        dl_resp = await client.get(
                            f"{GRAPH_BASE}/drives/{drive_id}/items/{item['id']}/content",
                            headers=headers_graph,
                            follow_redirects=True,
                            timeout=60,
                        )
                        if not dl_resp.is_success:
                            indexing_status["indexed"].append({"name": name, "chunks": 0, "status": f"erro: {dl_resp.status_code}"})
                            continue

                        content_bytes = dl_resp.content
                        web_url = item.get("webUrl", "")

                        indexing_status["progress"] = f"Indexando (Docling + vetores): {name}"

                        # Run blocking I/O (Docling + embeddings + ChromaDB) in thread pool
                        result = await loop.run_in_executor(
                            None,
                            lambda b=content_bytes, n=name, f=folder_name, u=web_url: index_document(
                                file_bytes=b,
                                filename=n,
                                folder=f,
                                web_url=u,
                                source="sharepoint",
                            )
                        )

                        # Keep in-memory store as a lightweight cache for quick preview
                        if result.get("status") in ("indexed", "skipped"):
                            already = any(d["name"] == name for d in document_store)
                            if not already:
                                document_store.append({
                                    "name": name,
                                    "folder": folder_name,
                                    "chunks": result.get("chunks", 0),
                                    "source": "sharepoint",
                                    "web_url": web_url,
                                    "preview": result.get("preview", ""),
                                })

                        indexing_status["total_chunks"] += result.get("chunks", 0)
                        indexing_status["indexed"].append({
                            "name": name,
                            "chunks": result.get("chunks", 0),
                            "preview": result.get("preview", "")[:180],
                            "status": result.get("status", "indexado"),
                        })

                    except Exception as e:
                        indexing_status["indexed"].append({"name": name, "chunks": 0, "status": f"erro: {str(e)[:80]}"})

        async with httpx.AsyncClient() as client:
            await index_folder(client)

        n = len(indexing_status["indexed"])
        c = indexing_status["total_chunks"]
        indexing_status["progress"] = f"Concluído: {n} documentos, {c} trechos no banco vetorial."
    except Exception as e:
        indexing_status["error"] = str(e)
        indexing_status["progress"] = f"Erro: {e}"
    finally:
        indexing_status["running"] = False


@app.post("/api/indexar-sharepoint")
async def indexar_sharepoint(request: dict):
    """Start background indexing of SharePoint documents."""
    if indexing_status["running"]:
        return {
            "message": "Indexação já em andamento.",
            "progress": indexing_status["progress"],
            "documentos": indexing_status["indexed"],
            "total_chunks": indexing_status["total_chunks"],
        }

    asyncio.create_task(_run_indexing())

    return {
        "message": "Indexação iniciada em segundo plano. Consulte /api/indexar-status para acompanhar.",
        "documentos": [],
        "total_chunks": 0,
    }


@app.get("/api/indexar-status")
async def indexar_status():
    """Check current indexing progress."""
    return {
        "running": indexing_status["running"],
        "progress": indexing_status["progress"],
        "total_documentos": len(indexing_status["indexed"]),
        "total_chunks": indexing_status["total_chunks"],
        "documentos": indexing_status["indexed"],
        "error": indexing_status["error"],
    }


@app.get("/api/documentos-indexados")
async def listar_documentos_indexados():
    """List all documents indexed in ChromaDB (persisted) plus in-memory cache."""
    try:
        stats = vs_get_stats()
        return {
            "total": stats["total_documents"],
            "total_chunks": stats["total_chunks"],
            "documentos": [{"name": n} for n in stats.get("documents", [])],
            "chroma_path": stats.get("chroma_path", ""),
        }
    except Exception:
        # Fallback to in-memory store
        docs = [
            {
                "name": d["name"],
                "folder": d.get("folder", ""),
                "chunks": d.get("chunks", 0),
                "preview": d.get("preview", "")[:200],
                "web_url": d.get("web_url", ""),
                "source": d.get("source", ""),
            }
            for d in document_store
        ]
        return {
            "total": len(docs),
            "total_chunks": sum(d["chunks"] for d in docs),
            "documentos": docs,
        }


# ─── RAG endpoints ────────────────────────────────────────────────────────────

class RagSearchRequest(BaseModel):
    query: str
    n_results: int = 5
    source: Optional[str] = None


@app.post("/api/rag/search")
async def rag_search(request: RagSearchRequest):
    """
    Semantic search over indexed documents using vector embeddings.
    Returns the most relevant text chunks for the given query.
    """
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        None,
        lambda: semantic_search(
            query=request.query,
            n_results=request.n_results,
            filter_source=request.source,
        )
    )
    return {"query": request.query, "results": results, "total": len(results)}


@app.get("/api/rag/stats")
async def rag_stats():
    """Return ChromaDB vector store statistics."""
    loop = asyncio.get_event_loop()
    stats = await loop.run_in_executor(None, vs_get_stats)
    return stats


@app.post("/api/sharepoint/upload")
async def upload_sharepoint_file():
    """Handle file upload to session (placeholder for multipart)."""
    raise HTTPException(status_code=501, detail="Use a rota /api/sharepoint/sync para sincronizar documentos.")


# ─── SharePoint Auto-Sync endpoints ──────────────────────────────────────────

class SyncRequest(BaseModel):
    force: bool = False


@app.post("/api/sharepoint/sync")
async def trigger_sharepoint_sync(request: SyncRequest = SyncRequest()):
    """
    Trigger an immediate SharePoint library sync.
    Downloads all files, converts with Docling, and indexes in ChromaDB.
    Set force=true to re-index already-cached files.
    """
    if sp_sync_state["running"]:
        return {
            "message": "Sincronização já em andamento.",
            "status": sp_sync_state,
        }
    asyncio.create_task(sp_run_sync(force=request.force))
    return {"message": "Sincronização iniciada.", "status": sp_sync_state}


@app.get("/api/sharepoint/sync-status")
async def sharepoint_sync_status():
    """Return the current sync status and file list."""
    return sp_sync_state


@app.get("/api/sharepoint/biblioteca")
async def listar_biblioteca_local():
    """
    List all locally cached SharePoint files (from disk manifest).
    These files are immediately available for use in JurisGen sessions.
    """
    loop = asyncio.get_event_loop()
    files = await loop.run_in_executor(None, sp_list_local_files)
    total_size = sum(f.get("size", 0) for f in files)
    total_chunks = sum(f.get("chunks", 0) for f in files)
    return {
        "total": len(files),
        "total_size_bytes": total_size,
        "total_chunks": total_chunks,
        "last_sync": sp_sync_state.get("last_sync"),
        "next_sync": sp_sync_state.get("next_sync"),
        "files": files,
    }


@app.get("/api/sharepoint/files/{item_id}")
async def download_cached_file(item_id: str):
    """
    Download a locally cached SharePoint file by its item ID.
    Returns the raw file bytes with appropriate Content-Type.
    """
    from fastapi.responses import FileResponse
    loop = asyncio.get_event_loop()
    files = await loop.run_in_executor(None, sp_list_local_files)

    file_info = next((f for f in files if f["item_id"] == item_id), None)
    if not file_info:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado no cache local.")

    local_path = file_info.get("local_path", "")
    if not local_path or not os.path.exists(local_path):
        raise HTTPException(status_code=404, detail="Arquivo não disponível localmente. Sincronize novamente.")

    name = file_info["name"]
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    media_types = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "doc": "application/msword",
        "txt": "text/plain; charset=utf-8",
    }
    media_type = media_types.get(ext, "application/octet-stream")

    return FileResponse(
        path=local_path,
        filename=name,
        media_type=media_type,
    )


# ─── Sessions ───

@app.post("/api/sessions", response_model=Session)
async def create_session(data: SessionCreate):
    """Create a new session"""
    session_id = str(uuid.uuid4())
    now = datetime.now()
    
    session = Session(
        id=session_id,
        doc_type=data.doc_type,
        answers={},
        outline=None,
        messages=[],
        style_refs=[],
        created_at=now,
        updated_at=now
    )
    
    sessions[session_id] = session
    return session


@app.get("/api/sessions/{session_id}", response_model=Session)
async def get_session_state(session_id: str):
    """Get session state"""
    return get_session(session_id)


# ─── SharePoint ───

@app.post("/api/sharepoint/search")
async def search_sharepoint(request: SharePointSearchRequest):
    """Search documents in SharePoint via Microsoft Graph API."""
    results = await _sharepoint_search(request.query, request.limit)
    return {"results": results, "query": request.query}


@app.post("/api/sharepoint/attach")
async def attach_sharepoint_document(request: SharePointAttachRequest):
    """Attach a SharePoint document as style reference, downloading its content."""
    session = get_session(request.session_id)

    content = request.content
    if not content and request.drive_id:
        content = await _get_document_content(request.drive_id, request.item_id)

    ref = {
        "id": request.item_id,
        "name": request.name,
        "content": (content or "")[:3000],
        "attached_at": datetime.now().isoformat(),
    }

    session.style_refs.append(ref)
    update_session(session)

    return {"status": "attached", "ref": ref}


@app.delete("/api/sharepoint/detach/{session_id}/{item_id}")
async def detach_sharepoint_document(session_id: str, item_id: str):
    """Remove a style reference from session"""
    session = get_session(session_id)
    
    session.style_refs = [ref for ref in session.style_refs if ref.get("id") != item_id]
    update_session(session)
    
    return {"status": "detached", "item_id": item_id}


# ─── Pipeline AI ───

@app.post("/api/pipeline/set-type")
async def set_document_type(request: SetTypeRequest):
    """Generate adaptive questions based on the document type using AI."""
    session = get_session(request.session_id)
    session.doc_type = request.doc_type
    context = getattr(request, "context", "") or request.doc_type
    update_session(session)

    system_prompt = """Você é um advogado sênior especializado em contencioso brasileiro.
O usuário quer elaborar um documento jurídico. Gere POUCAS perguntas essenciais — máximo 5.

REGRA PRINCIPAL: SE TIVER DÚVIDA SOBRE QUALQUER DADO, NÃO PERGUNTE — use [CAMPO] no documento.
Exemplos de placeholders: [Nome do Autor], [CPF], [RG], [Endereço], [Valor do Pedido], [Data do Fato], [Nome do Réu], [CNPJ], [Número do Contrato].

PERGUNTAS PERMITIDAS (máximo 5, SOMENTE as essenciais):
1. **Fatos principais** — o que aconteceu, quando, valores envolvidos (1-2 perguntas com opções)
2. **Tese jurídica** — qual o enquadramento legal pretendido (1 pergunta com opções)
3. **Pedidos** — o que o cliente quer obter (1 pergunta com opções)

PROIBIDO:
- NÃO pergunte sobre CPF, RG, endereço, CNPJ — use [CAMPO] direto no documento
- NÃO faça perguntas de "texto livre" — prefira sempre "choice" com opções prontas mais "Outro"
- NÃO gere mais que 5 perguntas

FORMATO DE PERGUNTAS: use SEMPRE "choice" ou "multiple", NUNCA "text" puro.
Toda pergunta "choice" deve ter a última opção: {"id": "other", "label": "Outro", "desc": "Informar manualmente"}

Responda APENAS com JSON válido:
{
  "thinking_summary": "estratégia jurídica resumida em 1 frase",
  "questions": [
    {"id": "q1", "text": "pergunta", "type": "choice", "options": [{"id": "opt1", "label": "Opção A", "desc": "explicação"}, {"id": "opt2", "label": "Opção B", "desc": "explicação"}, {"id": "other", "label": "Outro", "desc": "Informar manualmente"}]}
  ]
}"""

    user_prompt = f"O usuário quer elaborar: {request.doc_type}\nContexto adicional: {context}"

    try:
        raw = await llm.chat(system=system_prompt, user=user_prompt, json_mode=True)
        import json as _json
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = _json.loads(text)
        questions = _normalize_questions(data.get("questions", []))
        return {
            "session_id": session.id,
            "doc_type": request.doc_type,
            "thinking_summary": data.get("thinking_summary", ""),
            "questions": questions,
        }
    except Exception as e:
        # Fallback to basic questions if AI fails
        return {
            "session_id": session.id,
            "doc_type": request.doc_type,
            "thinking_summary": f"Erro na IA: {str(e)[:100]}. Usando perguntas padrão.",
            "questions": [
                {"id": "q1", "text": "Descreva os fatos do caso em detalhes", "type": "text"},
                {"id": "q2", "text": "Quais são as partes envolvidas? (nomes, CPF/CNPJ)", "type": "text"},
                {"id": "q3", "text": "Qual o resultado desejado?", "type": "text"},
            ],
        }


@app.post("/api/pipeline/answer")
async def submit_answer(request: AnswerRequest):
    """Submit answers. AI decides: ask more questions or generate outline."""
    session = get_session(request.session_id)

    for key, value in request.answers.items():
        session.answers[key] = value if isinstance(value, str) else ", ".join(value) if isinstance(value, list) else str(value)
    session.answer_rounds += 1
    update_session(session)

    doc_type = session.doc_type or "Documento Jurídico"
    answers_text = "\n".join(f"- {k}: {v}" for k, v in session.answers.items())
    is_final_round = session.answer_rounds >= 2

    # Provide document store context if available
    docs_context = ""
    if document_store:
        docs_context = f"\n\nVocê tem acesso a {len(document_store)} documentos de referência do escritório para usar como base de estilo e argumentação."

    force_outline = "IMPORTANTE: Esta é a SEGUNDA rodada de perguntas. Você DEVE gerar o roteiro (OPÇÃO 2) agora com as informações disponíveis. Use [placeholders] para dados faltantes. NÃO faça mais perguntas.\n\n" if is_final_round else ""

    system_prompt = f"""Você é um assistente jurídico especializado. O usuário está elaborando: {doc_type}.
Informações já coletadas:
{answers_text}
{docs_context}

{force_outline}Analise as informações. Você tem DUAS opções:

OPÇÃO 1 - Se FALTAM informações ESSENCIAIS (fatos, tese, pedidos) E esta é a PRIMEIRA rodada, gere perguntas de refinamento.
Responda com JSON:
{{"action": "more_questions", "thinking_summary": "por que precisa de mais info", "questions": [...]}}

FORMATO OBRIGATÓRIO DAS PERGUNTAS DE REFINAMENTO:
- Use MAJORITARIAMENTE tipo "choice" (opções clicáveis) — o usuário prefere CLICAR, não digitar
- Cada pergunta "choice" DEVE ter campo "options" com array de opções: [{{"id": "x", "label": "texto", "desc": "explicação"}}]
- SEMPRE inclua uma opção {{"id": "other", "label": "Outro (especifique)"}} em cada choice
- Use "multiple" para perguntas com várias respostas possíveis (também com options obrigatório)
- Use "text" (campo aberto) APENAS na ÚLTIMA pergunta, para observações adicionais
- Máximo 5-6 perguntas de refinamento
- Dados pessoais faltantes (CPF, RG, endereço) NÃO precisam ser perguntados — serão [placeholders]
- Foque nas informações que mudam a ESTRATÉGIA JURÍDICA

OPÇÃO 2 - Se já tem informações SUFICIENTES, gere um roteiro COMPLETO e PROFISSIONAL do documento.

O roteiro deve ter entre 8 e 14 seções, cobrindo TODOS os aspectos de uma peça jurídica real.

Responda com JSON:
{{"action": "outline", "outline": {{
  "title": "TÍTULO DA PEÇA EM MAIÚSCULAS (ex: AÇÃO DE INDENIZAÇÃO POR DANOS MORAIS E MATERIAIS C/C TUTELA DE URGÊNCIA)",
  "subtitle": "Descrição breve do caso (ex: Decorrente de fraude bancária com descontos indevidos em conta corrente)",
  "estimated_pages": N,
  "key_arguments": [
    "Tese jurídica principal (ex: Responsabilidade objetiva do fornecedor de serviço — CDC)",
    "Segunda tese (ex: Nexo causal entre falha de segurança e dano sofrido)",
    "Terceira tese (ex: Configuração do dano moral in re ipsa)",
    "Quarta tese se aplicável",
    "Quinta tese se aplicável"
  ],
  "sections": [
    {{
      "title": "I. ENDEREÇAMENTO E QUALIFICAÇÃO DAS PARTES",
      "description": "Identificação completa do autor/consumidor e réu/fornecedor, incluindo dados pessoais, endereços e qualificação jurídica",
      "legal_basis": ["Art. 319, II do CPC"],
      "priority": "obrigatoria"
    }},
    {{
      "title": "II. DOS FATOS",
      "description": "Narrativa cronológica detalhada dos fatos, com datas, valores, circunstâncias e tentativas de resolução extrajudicial",
      "legal_basis": ["Art. 319, III do CPC"],
      "priority": "obrigatoria"
    }},
    {{
      "title": "III. DO DIREITO APLICÁVEL",
      "description": "Fundamentação sobre a legislação aplicável, natureza da relação jurídica e enquadramento legal",
      "legal_basis": ["Artigos específicos das leis aplicáveis ao caso"],
      "priority": "obrigatoria"
    }}
  ]
}}}}

REGRAS DO ROTEIRO:
- Mínimo 8 seções, máximo 14 seções
- Títulos em MAIÚSCULAS com numeração romana (I, II, III...)
- Cada seção deve ter description detalhada (2-3 frases explicando o conteúdo)
- legal_basis deve conter artigos ESPECÍFICOS de leis reais (CDC, CC, CPC, CLT, CF, etc.)
- key_arguments devem ser as TESES JURÍDICAS centrais (não repetir títulos de seções)
- Seções obrigatórias: Qualificação, Fatos, Direito, Pedidos
- Adicione seções específicas ao caso: danos morais, danos materiais, tutela de urgência, responsabilidade objetiva, inversão do ônus da prova, etc.
- A última seção deve ser "PROVAS, VALOR DA CAUSA E FECHAMENTO"
- estimated_pages: calcule com base no número de seções (cada seção ≈ 1-1.5 páginas)

Responda APENAS com JSON válido."""

    try:
        raw = await llm.chat(system=system_prompt, user=f"Informações coletadas até agora para {doc_type}:\n{answers_text}", json_mode=True)
        import json as _json
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = _json.loads(text)

        action = data.get("action", "outline")

        if action == "more_questions":
            return {
                "action": "more_questions",
                "thinking_summary": data.get("thinking_summary", ""),
                "questions": _normalize_questions(data.get("questions", [])),
            }
        else:
            outline = data.get("outline", {})
            session.outline = outline
            update_session(session)
            return {
                "action": "outline",
                "outline": outline,
            }

    except Exception as e:
        # Fallback: generate comprehensive outline directly
        session.outline = {
            "title": doc_type.upper() if doc_type else "DOCUMENTO JURÍDICO",
            "subtitle": f"Baseado em {len(session.answers)} informações coletadas",
            "estimated_pages": 12,
            "key_arguments": [v for v in session.answers.values() if len(str(v)) > 10][:5],
            "sections": [
                {"title": "I. ENDEREÇAMENTO E QUALIFICAÇÃO DAS PARTES", "description": "Identificação completa do autor e réu, incluindo dados pessoais, endereços e qualificação jurídica.", "legal_basis": ["Art. 319, II do CPC"], "priority": "obrigatoria"},
                {"title": "II. DOS FATOS", "description": "Narrativa cronológica detalhada dos fatos que ensejam a demanda, com datas, valores e circunstâncias.", "legal_basis": ["Art. 319, III do CPC"], "priority": "obrigatoria"},
                {"title": "III. DO DIREITO APLICÁVEL", "description": "Fundamentação sobre a legislação aplicável ao caso e natureza da relação jurídica.", "legal_basis": ["CF/88", "CC/2002"], "priority": "obrigatoria"},
                {"title": "IV. DA RESPONSABILIDADE", "description": "Demonstração da responsabilidade da parte ré pelos danos causados, com análise do nexo causal.", "legal_basis": ["Art. 186 do CC", "Art. 927 do CC"], "priority": "obrigatoria"},
                {"title": "V. DOS DANOS MATERIAIS", "description": "Quantificação e comprovação dos prejuízos materiais sofridos pelo autor.", "legal_basis": ["Art. 402 do CC"], "priority": "obrigatoria"},
                {"title": "VI. DOS DANOS MORAIS", "description": "Configuração do dano moral, abalo psicológico e violação aos direitos da personalidade.", "legal_basis": ["Art. 5º, V e X da CF", "Art. 186 do CC"], "priority": "obrigatoria"},
                {"title": "VII. DA TUTELA DE URGÊNCIA", "description": "Pedido de tutela provisória de urgência com demonstração do periculum in mora e fumus boni iuris.", "legal_basis": ["Arts. 300 a 302 do CPC"], "priority": "condicional"},
                {"title": "VIII. DOS PEDIDOS", "description": "Lista completa dos pedidos ao juízo, incluindo condenações, obrigações de fazer e custas processuais.", "legal_basis": ["Art. 319, IV do CPC"], "priority": "obrigatoria"},
                {"title": "IX. PROVAS, VALOR DA CAUSA E FECHAMENTO", "description": "Requerimento de provas, fixação do valor da causa e fecho da petição.", "legal_basis": ["Art. 319, V e VI do CPC"], "priority": "obrigatoria"},
            ],
        }
        update_session(session)
        return {"action": "outline", "outline": session.outline}


@app.post("/api/pipeline/regenerate-outline/{session_id}")
async def regenerate_outline(session_id: str):
    """
    Regenerate the document outline
    TODO: Implement AI outline generation
    """
    session = get_session(session_id)
    
    # Placeholder - regenerates outline
    session.outline = {
        "title": f"{session.doc_type or 'Documento'} (Regenerado)",
        "sections": [
            {"id": "s1", "title": "Cabeçalho", "content": "..."},
            {"id": "s2", "title": "Fundamentação", "content": "..."},
            {"id": "s3", "title": "Pedido", "content": "..."},
            {"id": "s4", "title": "Encerramento", "content": "..."}
        ]
    }
    update_session(session)
    
    return {"outline": session.outline}


@app.post("/api/pipeline/generate-document/{session_id}")
async def generate_document(session_id: str):
    """
    Generate the final document section by section using AI, streamed as NDJSON.
    Each section gets its OWN targeted legal research (jurisprudence, doctrine)
    based on the section's specific topic — not a generic pre-search.
    """
    from fastapi.responses import StreamingResponse
    import json as _json
    from legal_search import (
        search_section_sources,
        format_section_sources,
        build_verification_block,
    )

    # Função de busca dinâmica de jurisprudência
    def _search_sumulas_dinamicas(query: str) -> list[dict[str, Any]]:
        """Busca dinâmica de súmulas e jurisprudência para complementar o raciocínio do LLM"""
        resultados = []
        
        # Buscar no JusBrasil se disponível
        if jusbrasil_search:
            try:
                # Tentar login automático se houver credenciais
                email = os.getenv("JUSBRASIL_EMAIL", "")
                password = os.getenv("JUSBRASIL_PASSWORD", "")
                
                if email and password:
                    if not hasattr(jusbrasil_search, '_logged_in'):
                        jusbrasil_search.login(email, password)
                        jusbrasil_search._logged_in = True
                    
                    # Buscar jurisprudência relevante
                    jurisprudencia = jusbrasil_search.buscar_jurisprudencia(query, "TST", 5)
                    sumulas = jusbrasil_search.buscar_sumulas(f"{query} TST", 3)
                    
                    resultados.extend(jurisprudencia)
                    resultados.extend(sumulas)
            except Exception as e:
                print(f"Aviso: Falha ao buscar no JusBrasil: {e}")
        
        # Buscar em fontes públicas alternativas
        try:
            # Buscar no TST
            import requests
            from bs4 import BeautifulSoup
            
            # Buscar no site do TST
            search_url = f"https://www.tst.jus.br/busca/-/search/contents?searchTerm={query.replace(' ', '+')}"
            response = requests.get(search_url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extrair resultados relevantes
                for item in soup.find_all(['div', 'article'], limit=5):
                    texto = item.get_text(strip=True)
                    if len(texto) > 100 and any(keyword in texto.lower() for keyword in ['súmula', 'sumula', 'tst', 'tribunal']):
                        resultados.append({
                            "tipo": "Jurisprudência Pública",
                            "texto": texto[:500],
                            "fonte": "TST - Busca Pública",
                            "url": search_url,
                            "data_busca": datetime.now().isoformat()
                        })
        except Exception as e:
            print(f"Aviso: Falha ao buscar no TST: {e}")
        
        return resultados

    session = get_session(session_id)
    doc_type = session.doc_type or "Documento Jurídico"
    answers_text = "\n".join(f"- {k}: {v}" for k, v in session.answers.items())
    outline = session.outline or {}
    sections = outline.get("sections", [])

    # Case context summary for targeted searches
    case_context = f"{doc_type} {' '.join(list(session.answers.values())[:3])}"[:200]

    # Build reference context using semantic RAG search
    docs_context = ""
    try:
        loop = asyncio.get_event_loop()
        rag_hits = await loop.run_in_executor(
            None,
            lambda: semantic_search(query=case_context, n_results=5)
        )
        if rag_hits:
            rag_snippets = [
                f"[{h['filename']}] (score={h['score']}): {h['text'][:300]}"
                for h in rag_hits
            ]
            docs_context = "\n\nDocumentos relevantes do escritório (busca semântica):\n" + "\n\n".join(rag_snippets)
    except Exception:
        if document_store:
            previews = [f"[{d['name']}]: {d.get('preview', '')[:300]}" for d in document_store[:5]]
            docs_context = "\n\nDocumentos de referência do escritório:\n" + "\n".join(previews)

    async def stream_sections():
        # Collect ALL sources across sections for the final verification block
        all_sources_global = []
        global_source_idx = 1

        for i, sec in enumerate(sections):
            section_title = sec.get("title", f"Seção {i+1}")
            section_desc = sec.get("description", "")
            legal_basis = sec.get("legal_basis", [])
            basis_text = ", ".join(legal_basis) if legal_basis else "conforme legislação aplicável"

            # ── Per-section targeted search ──
            yield _json.dumps({
                "type": "research",
                "data": {
                    "section": section_title,
                    "status": "searching",
                    "message": f"Pesquisando jurisprudência e doutrina para: {section_title}...",
                },
            }, ensure_ascii=False) + "\n"

            try:
                section_sources = await search_section_sources(
                    section_title=section_title,
                    section_description=section_desc,
                    case_context=case_context,
                    doc_type=doc_type,
                )
                sources_text = format_section_sources(section_sources)
                # Tag each source with its section for the global block
                for src in section_sources.get("all_sources", []):
                    src["section"] = section_title
                    src["global_idx"] = global_source_idx
                    all_sources_global.append(src)
                    global_source_idx += 1
            except Exception:
                section_sources = {"jurisprudencia": [], "doutrina": [], "all_sources": []}
                sources_text = ""

            # Notify frontend how many sources found for this section
            n_found = len(section_sources.get("all_sources", []))
            tribunais = section_sources.get("tribunais_consultados", [])
            search_query = section_sources.get("search_query", "")
            yield _json.dumps({
                "type": "research",
                "data": {
                    "section": section_title,
                    "status": "done",
                    "total": n_found,
                    "sources": section_sources.get("all_sources", []),
                    "tribunais": tribunais,
                    "search_query": search_query,
                    "message": f"{n_found} fontes encontradas para {section_title}",
                },
            }, ensure_ascii=False) + "\n"

            # ── Build per-section prompt with its own sources ──
            n_juris = len(section_sources.get("jurisprudencia", []))
            sources_instruction = ""
            if sources_text:
                sources_instruction = f"""
══════════════════════════════════════════════
FONTES PESQUISADAS ESPECIFICAMENTE PARA ESTA SEÇÃO:
{sources_text}
══════════════════════════════════════════════

INSTRUÇÕES DE CITAÇÃO — PRIORIDADE ABSOLUTA:
1. JURISPRUDÊNCIA TEM PRIORIDADE MÁXIMA. Foram encontradas {n_juris} jurisprudências acima.
2. Você DEVE citar TODAS as {n_juris} jurisprudências, incorporando cada uma no corpo do texto.
3. Para cada jurisprudência:
   a) TRANSCREVA A EMENTA COMPLETA (ou o máximo do snippet fornecido) entre aspas duplas — NÃO resuma nem abrevia
   b) Após a ementa, insira a referência: (Tribunal, Processo nº X, j. DD/MM/AAAA) [Fonte N]
   c) Adicione análise de 1-2 frases explicando como a ementa sustenta o argumento do caso concreto
4. Formato de ementa completa obrigatório:
   "EMENTA: [texto integral da ementa conforme fornecido acima...]"
   (Tribunal, Processo nº X, Rel. Min./Des. Y, j. DD/MM/AAAA) [Fonte N]
5. Artigos de lei são COMPLEMENTARES às ementas — cite-os após cada bloco de jurisprudência.
6. Para doutrina: transcreva o trecho relevante entre aspas e inclua [Fonte N].
7. NÃO invente citações — use APENAS as fontes fornecidas acima.
8. Se o snippet não tiver número de processo completo, cite pelo título e tribunal disponíveis.
9. O texto desta seção DEVE ter no mínimo {max(n_juris, 3)} blocos de ementa transcrita.
"""
            else:
                sources_instruction = """
Não foram encontradas fontes específicas para esta seção na pesquisa.
Use fundamentação legal (artigos de lei) sem citar jurisprudência específica.
NÃO invente números de processo ou citações jurisprudenciais.
"""

            system_prompt = f"""Você é um advogado sênior redigindo uma peça jurídica real: {doc_type}.
Escreva a seção "{section_title}" de forma COMPLETA, PROFISSIONAL e PRONTA PARA PROTOCOLAR.

Informações do caso:
{answers_text}

Descrição da seção: {section_desc}
Fundamentação legal sugerida: {basis_text}
{docs_context}
{sources_instruction}

REGRAS DE REDAÇÃO:
- Use linguagem jurídica formal brasileira
- PRIORIDADE DE CITAÇÃO: jurisprudência > súmulas > doutrina > artigos de lei
- Cada seção substantiva DEVE ter no mínimo 3 ementas transcritas na íntegra das fontes pesquisadas
- Transcreva SEMPRE a ementa COMPLETA — nunca resuma ou use reticências (...) dentro da ementa
- Cada ementa deve ser seguida de análise de como ela se aplica ao caso concreto
- Artigos de lei são suporte — ementas transcritas na íntegra são o argumento central
- Seja detalhista e extenso — esta seção será usada diretamente na peça
- Para fatos: narrativa cronológica detalhada com os dados fornecidos
- Para direito: blocos de ementa integral + artigo de lei como complemento + análise aplicada ao caso
- Para pedidos: lista enumerada e específica
- Use os dados reais fornecidos pelo usuário
- Para dados NÃO informados, use placeholders: [Nome Completo], [CPF], [RG], [Endereço], etc.
- NUNCA invente jurisprudência — use somente as fontes fornecidas
- Se as fontes fornecidas forem irrelevantes ou em outro idioma, IGNORE-AS e use apenas artigos de lei brasileiros

PROIBIDO:
- NÃO faça perguntas ao usuário (ex: "Você gostaria que eu...")
- NÃO exponha seu raciocínio ou pensamentos
- NÃO diga que faltam informações ou fontes
- NÃO peça permissão para pesquisar
- NÃO inclua meta-comentários sobre a redação
- APENAS escreva o texto jurídico final, pronto para protocolar

Escreva APENAS o conteúdo da seção, sem repetir o título. Comece diretamente com o texto jurídico."""

            try:
                user_msg = f"Redija a seção '{section_title}' da peça {doc_type}."
                multi = await llm.chat_multi(
                    system=system_prompt,
                    user=user_msg,
                    section_title=section_title,
                    max_tokens=4500,
                )

                content = multi["claude"]

                # Validate and enrich with HF models ONLY if output is valid Portuguese legal text
                def _is_valid_legal_pt(text: str) -> bool:
                    """Check if text is valid Portuguese legal content (not garbage/chinese/etc)."""
                    if not text or len(text) < 50:
                        return False
                    if text.startswith("[Modelo"):
                        return False
                    # Check for non-Latin characters (Chinese, Japanese, Korean, etc.)
                    import re as _re
                    non_latin = len(_re.findall(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]', text))
                    if non_latin > 5:
                        return False
                    # Must contain some Portuguese legal keywords
                    pt_keywords = ["art.", "lei", "código", "tribunal", "processo", "direito", "jurisprudência", "dano", "réu", "autor"]
                    text_lower = text.lower()
                    matches = sum(1 for kw in pt_keywords if kw in text_lower)
                    return matches >= 2

                jurema_extra = multi.get("jurema", "")
                longcat_extra = multi.get("longcat", "")

                enrichments = []
                if _is_valid_legal_pt(jurema_extra):
                    enrichments.append(jurema_extra)
                if _is_valid_legal_pt(longcat_extra):
                    enrichments.append(longcat_extra)

                if enrichments:
                    content += "\n\n" + "\n\n".join(enrichments)

                # Clean Claude output: remove "thinking" leaks
                import re as _re
                # Remove lines where Claude asks questions or exposes thinking
                thinking_patterns = [
                    r'(?:Você|Voce) gostaria que eu.*?\?',
                    r'(?:Observo|Noto|Percebo) que (?:há|existe).*?(?:problema|fontes|dados)',
                    r'Para (?:redigir|completar|escrever) adequadamente.*?(?:preciso|necessito)',
                    r'(?:Aguarde|Forneça|Indique).*?(?:jurisprudência|dados|informações)',
                    r'^\d+\.\s+\*\*(?:Procure|Redija|Aguarde).*?\*\*.*$',
                    r'^(?:Opção|Alternativa)\s+\d+.*$',
                ]
                for pattern in thinking_patterns:
                    content = _re.sub(pattern, '', content, flags=_re.MULTILINE | _re.IGNORECASE)
                # Remove multiple blank lines
                content = _re.sub(r'\n{3,}', '\n\n', content).strip()

            except Exception as e:
                content = f"[Erro ao gerar esta seção: {str(e)[:100]}]"

            # Track which models contributed
            models_used = ["Claude CLI"]
            if llm.jurema_available:
                if _is_valid_legal_pt(multi.get("jurema", "")):
                    models_used.append("Jurema 7B")
                if _is_valid_legal_pt(multi.get("longcat", "")):
                    models_used.append("LongCat")

            event = {
                "type": "section",
                "data": {
                    "section_title": section_title,
                    "content": content,
                    "legal_basis": legal_basis,
                    "sources_count": n_found,
                    "models_used": models_used,
                },
            }
            yield _json.dumps(event, ensure_ascii=False) + "\n"

        # ── Final: Verification seal with ALL sources from all sections ──
        if all_sources_global:
            verification = build_verification_block(all_sources_global)
            yield _json.dumps({
                "type": "section",
                "data": {
                    "section_title": "SELO DE VERIFICAÇÃO — FONTES CONSULTADAS",
                    "content": verification,
                    "legal_basis": [],
                    "is_sources": True,
                    "sources_count": len(all_sources_global),
                },
            }, ensure_ascii=False) + "\n"

        # Final progress event
        yield _json.dumps({
            "type": "done",
            "total_sections": len(sections),
            "total_sources": len(all_sources_global),
        }, ensure_ascii=False) + "\n"

    return StreamingResponse(stream_sections(), media_type="application/x-ndjson")


# ─── Análise Adversarial ───

class AdversarialRequest(BaseModel):
    session_id: str
    document_text: str


@app.post("/api/pipeline/adversarial-analysis/{session_id}")
async def adversarial_analysis(session_id: str, request: AdversarialRequest):
    """
    Análise adversarial estruturada: gera peça adversária, identifica vulnerabilidades
    e sugere correções. Streamed como NDJSON.
    """
    from fastapi.responses import StreamingResponse
    import json as _json

    session = get_session(session_id)
    doc_type = session.doc_type or "Documento Jurídico"
    answers_text = "\n".join(f"- {k}: {v}" for k, v in session.answers.items())
    document_text = request.document_text

    async def stream_analysis():
        # ── Step 1: Classification & Adversarial Strategy ──
        yield _json.dumps({
            "type": "status",
            "data": {"step": "classification", "message": "Classificando peça e definindo estratégia adversarial..."},
        }, ensure_ascii=False) + "\n"

        classification_prompt = f"""Você é um advogado sênior especializado em contencioso brasileiro.
Analise a peça jurídica abaixo e responda com JSON válido:

{{
  "tipo_peca": "tipo da peça (ex: Petição Inicial)",
  "peca_adversaria": "tipo da peça adversária (ex: Contestação)",
  "trilha": "contencioso|trabalhista|administrativo|constitucional",
  "confianca": 95,
  "racional": "Explicação de 2-3 frases sobre a classificação e natureza da demanda.",
  "estrategia_adversarial": "Parágrafo detalhado (3-5 frases) descrevendo a estratégia completa que a defesa usaria: quais teses atacar, como romper nexo causal, quais excludentes invocar, como combater cada pedido."
}}

PEÇA PARA ANÁLISE:
{document_text[:6000]}"""

        try:
            raw = await llm.chat(
                system=classification_prompt,
                user="Classifique esta peça e defina a estratégia adversarial.",
                json_mode=True,
            )
            import json as _j
            text = raw.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            classification = _j.loads(text)
        except Exception:
            classification = {
                "tipo_peca": doc_type,
                "peca_adversaria": "Contestação",
                "trilha": "contencioso",
                "confianca": 85,
                "racional": "Classificação baseada no tipo de documento informado.",
                "estrategia_adversarial": "Análise da estratégia adversarial não disponível.",
            }

        yield _json.dumps({
            "type": "classification",
            "data": classification,
        }, ensure_ascii=False) + "\n"

        # ── Step 2: Vulnerability Analysis ──
        yield _json.dumps({
            "type": "status",
            "data": {"step": "vulnerabilities", "message": "Identificando vulnerabilidades na peça..."},
        }, ensure_ascii=False) + "\n"

        vuln_prompt = f"""Você é um advogado sênior da parte adversária. Analise a peça jurídica abaixo
e identifique TODAS as vulnerabilidades, pontos fracos e lacunas argumentativas.

Para cada vulnerabilidade, responda com JSON:
{{
  "vulnerabilities": [
    {{
      "id": "v1",
      "title": "Título curto da vulnerabilidade",
      "severity": "ALTA|MEDIA|BAIXA",
      "category": "FUNDAMENTACAO|ESTRATEGIA|PROVAS|PEDIDOS|FATOS",
      "description": "Descrição detalhada de 2-4 frases explicando a vulnerabilidade, como a parte adversária exploraria isso, e por que enfraquece a peça.",
      "correction": "Sugestão de correção em 1-2 frases para fortalecer a peça original."
    }}
  ]
}}

Identifique entre 3 e 7 vulnerabilidades, ordenadas por severidade (ALTA primeiro).
Seja específico e mencione jurisprudência/súmulas que a parte adversária usaria.

PEÇA PARA ANÁLISE:
{document_text[:6000]}

Informações do caso:
{answers_text}"""

        try:
            raw = await llm.chat(
                system=vuln_prompt,
                user="Identifique todas as vulnerabilidades desta peça jurídica.",
                json_mode=True,
                max_tokens=3000,
            )
            import json as _j
            text = raw.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            vuln_data = _j.loads(text)
            vulnerabilities = vuln_data.get("vulnerabilities", [])
        except Exception:
            vulnerabilities = []

        yield _json.dumps({
            "type": "vulnerabilities",
            "data": {"vulnerabilities": vulnerabilities, "total": len(vulnerabilities)},
        }, ensure_ascii=False) + "\n"

        # ── Step 2b: Enrich with Jurema adversarial jurisprudence ──
        if llm.jurema_available:
            yield _json.dumps({
                "type": "status",
                "data": {"step": "jurema_adversarial", "message": "Buscando jurisprudência adversarial com Jurema 7B..."},
            }, ensure_ascii=False) + "\n"

            jurema_adversarial_user = f"Peça jurídica:\n{document_text[:3000]}\n\nVulnerabilidades:\n{_json.dumps([v.get('title', '') for v in vulnerabilities[:5]], ensure_ascii=False)}"
            try:
                jurema_raw = await llm.chat_jurema(
                    system=JUREMA_ADVERSARIAL_SYSTEM,
                    user=jurema_adversarial_user,
                    max_tokens=1000,
                )
                if jurema_raw and is_valid_legal_pt(jurema_raw):
                    vulnerabilities.append({
                        "id": f"v_jurema_{len(vulnerabilities)+1}",
                        "title": "Jurisprudência adversarial (Jurema 7B)",
                        "severity": "MEDIA",
                        "category": "FUNDAMENTACAO",
                        "description": jurema_raw,
                        "correction": "Reforçar fundamentação com jurisprudência que neutralize estes precedentes adversários.",
                    })
                    yield _json.dumps({
                        "type": "vulnerabilities",
                        "data": {"vulnerabilities": vulnerabilities, "total": len(vulnerabilities), "jurema_enriched": True},
                    }, ensure_ascii=False) + "\n"
            except Exception as e:
                print(f"[Jurema] Erro na análise adversarial: {e}")

        # ── Step 3: Generate Adversarial Document (Contestação) ──
        yield _json.dumps({
            "type": "status",
            "data": {"step": "adversarial_doc", "message": f"Gerando {classification.get('peca_adversaria', 'Contestação')}..."},
        }, ensure_ascii=False) + "\n"

        peca_adversaria = classification.get("peca_adversaria", "Contestação")
        adversarial_prompt = f"""Você é um advogado sênior representando a PARTE RÉ.
Redija uma {peca_adversaria} COMPLETA contra a peça jurídica abaixo.

A {peca_adversaria} deve:
1. Começar com o endereçamento correto ao juízo competente
2. Qualificar a parte ré
3. Fazer preliminares se cabíveis
4. Impugnar CADA fato e fundamento da peça adversária
5. Apresentar tese de defesa robusta com jurisprudência e artigos de lei
6. Combater CADA pedido individualmente
7. Formular pedidos de improcedência

Estratégia a seguir:
{classification.get('estrategia_adversarial', '')}

Vulnerabilidades identificadas na peça adversária (explore-as):
{_json.dumps([{{"title": v["title"], "description": v["description"]}} for v in vulnerabilities[:5]], ensure_ascii=False)}

PEÇA ADVERSÁRIA (para contestar):
{document_text[:5000]}

Redija a {peca_adversaria} completa, profissional e pronta para protocolar.
Use linguagem jurídica formal brasileira."""

        try:
            adversarial_doc = await llm.chat(
                system=adversarial_prompt,
                user=f"Redija a {peca_adversaria} completa.",
                max_tokens=4000,
            )
        except Exception as e:
            adversarial_doc = f"[Erro ao gerar {peca_adversaria}: {str(e)[:100]}]"

        yield _json.dumps({
            "type": "adversarial_document",
            "data": {
                "title": peca_adversaria,
                "content": adversarial_doc,
            },
        }, ensure_ascii=False) + "\n"

        # ── Done ──
        yield _json.dumps({
            "type": "done",
            "data": {
                "total_vulnerabilities": len(vulnerabilities),
                "peca_adversaria": peca_adversaria,
                "confianca": classification.get("confianca", 0),
            },
        }, ensure_ascii=False) + "\n"

    return StreamingResponse(stream_analysis(), media_type="application/x-ndjson")


@app.post("/api/pipeline/apply-correction/{session_id}")
async def apply_correction(session_id: str, request: dict):
    """
    Aplica uma correção de vulnerabilidade ao texto de uma seção.
    Valida com Jurema se a correção é consistente com jurisprudência.
    Recebe: section_text, vulnerability (title + correction)
    Retorna: texto corrigido + validação Jurema.
    """
    session = get_session(session_id)
    section_text = request.get("section_text", "")
    vuln_title = request.get("vulnerability_title", "")
    vuln_correction = request.get("correction", "")

    prompt = f"""Você é um advogado sênior revisando uma peça jurídica.

VULNERABILIDADE IDENTIFICADA: {vuln_title}
CORREÇÃO SUGERIDA: {vuln_correction}

TEXTO ORIGINAL DA SEÇÃO:
{section_text}

Reescreva o texto da seção incorporando a correção sugerida para fortalecer a argumentação.
Mantenha o estilo jurídico formal. Faça APENAS as alterações necessárias para corrigir a vulnerabilidade.
Retorne APENAS o texto corrigido, sem explicações."""

    try:
        corrected = await llm.chat(
            system=prompt,
            user="Aplique a correção ao texto.",
            max_tokens=3000,
        )
    except Exception as e:
        corrected = section_text  # Return original on error

    # Validate with Jurema
    jurema_validation = None
    if llm.jurema_available:
        try:
            jurema_user = f"Vulnerabilidade: {vuln_title}\nCorreção sugerida: {vuln_correction}\nTexto original:\n{section_text[:1500]}"
            jurema_raw = await llm.chat_jurema(
                system=JUREMA_VALIDATION_SYSTEM,
                user=jurema_user,
                max_tokens=800,
            )
            if jurema_raw and is_valid_legal_pt(jurema_raw):
                import json as _json
                try:
                    jurema_validation = _json.loads(jurema_raw)
                except:
                    jurema_validation = {"recomendacao": jurema_raw, "valida": True}
        except Exception as e:
            print(f"[Jurema] Erro na validação de correção: {e}")

    return {"corrected_text": corrected, "jurema_validation": jurema_validation}


# ─── Chat ───

@app.post("/api/chat")
async def chat_message(request: ChatRequest):
    """Free-form chat with AI + Jurema enrichment."""
    session = get_session(request.session_id)

    session.messages.append({
        "role": "user",
        "type": "text",
        "content": request.message,
        "timestamp": datetime.now().isoformat(),
    })

    # Build context from session
    doc_type = session.doc_type or "documento jurídico"
    answers_text = "\n".join(f"- {k}: {v}" for k, v in session.answers.items()) if session.answers else "Nenhuma informação coletada ainda."

    # RAG: semantic search for relevant office documents
    docs_context = ""
    try:
        _loop = asyncio.get_event_loop()
        _hits = await _loop.run_in_executor(
            None,
            lambda: semantic_search(query=request.message, n_results=3)
        )
        if _hits:
            _snippets = [f"[{h['filename']}]: {h['text'][:250]}" for h in _hits]
            docs_context = "\nDocumentos relevantes do escritório:\n" + "\n\n".join(_snippets)
    except Exception:
        if document_store:
            docs_context = f"\nVocê tem {len(document_store)} documentos de referência do escritório indexados."

    # Recent message history for context
    recent = session.messages[-10:]
    history = "\n".join(f"{m['role']}: {m.get('content','')}" for m in recent)

    system_prompt = f"""Você é um assistente jurídico especializado do escritório Carvalho & Furtado Advogados.
Tipo de documento: {doc_type}
Informações coletadas: {answers_text}
{docs_context}

Responda de forma profissional, direta e útil. Se o usuário pedir ajustes no documento, faça.
Se pedir informações jurídicas, responda com base na legislação brasileira."""

    try:
        # Use chat_with_jurema for parallel Claude + Jurema
        result = await llm.chat_with_jurema(
            system=system_prompt,
            user=f"Histórico recente:\n{history}\n\nMensagem atual: {request.message}",
            jurema_system=JUREMA_CHAT_SYSTEM,
            jurema_user=f"Pergunta do usuário: {request.message}",
            max_tokens=2000,
            jurema_max_tokens=800,
        )
        response_text = result["claude"]
        jurema_text = result.get("jurema")

        # Append Jurema jurisprudence as complementary note
        if jurema_text:
            response_text += f"\n\n---\n**📚 Jurisprudência (Jurema 7B):**\n{jurema_text}"
    except Exception as e:
        response_text = f"Erro ao processar: {str(e)[:200]}"
        jurema_text = None

    response = {
        "role": "assistant",
        "type": "text",
        "content": response_text,
        "timestamp": datetime.now().isoformat(),
        "jurema_used": jurema_text is not None,
    }
    session.messages.append(response)
    update_session(session)

    return {"response": response_text, "jurema_used": jurema_text is not None}


@app.get("/api/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    """Return full message history for a session."""
    session = get_session(session_id)
    return {"messages": session.messages, "session_id": session_id}


# ─── Serve frontend static files (production) ───
import pathlib
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

_frontend_dist = pathlib.Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    # Serve static assets (js, css, images)
    app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="static-assets")

    # Catch-all: serve index.html for SPA routes
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = _frontend_dist / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_frontend_dist / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
