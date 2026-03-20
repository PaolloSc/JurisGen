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

from llm.client import LLMClient
llm = LLMClient()


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
    """Download and extract text from a SharePoint document."""
    token = _get_graph_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(
            f"{GRAPH_BASE}/drives/{drive_id}/items/{item_id}/content",
            headers=headers,
        )
        if not resp.is_success:
            raise HTTPException(status_code=resp.status_code, detail="Failed to download document")
        content_bytes = resp.content

    try:
        import docx, io
        doc = docx.Document(io.BytesIO(content_bytes))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())[:3000]
    except Exception:
        return content_bytes[:3000].decode("utf-8", errors="ignore")


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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("JurisGen AI Backend started")
    yield
    # Shutdown
    print("JurisGen AI Backend shutting down")


app = FastAPI(
    title="JurisGen AI",
    description="Gerador Adaptativo de Documentos Jurídicos",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
cors_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "https://*.trycloudflare.com",
]
# Allow all origins when behind Cloudflare tunnel
cors_origins_regex = r"https://.*\.trycloudflare\.com"
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=cors_origins_regex,
    allow_credentials=True,
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
        if q["type"] in ("choice", "multiple") and "options" in q:
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
indexing_status: dict[str, Any] = {"running": False, "progress": "", "indexed": [], "total_chunks": 0, "error": None}


async def _run_indexing():
    """Background task: download and index all SharePoint docs."""
    global indexing_status
    indexing_status = {"running": True, "progress": "Iniciando...", "indexed": [], "total_chunks": 0, "error": None}

    try:
        token = _get_graph_token()
        drive_id = os.getenv("SHAREPOINT_DRIVE_ID", "")
        headers_graph = {"Authorization": f"Bearer {token}"}

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

                    indexing_status["progress"] = f"Baixando: {name}"

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
                        text = ""

                        if ext == "docx":
                            import docx, io
                            doc = docx.Document(io.BytesIO(content_bytes))
                            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
                        elif ext == "pdf":
                            import fitz
                            pdf = fitz.open(stream=content_bytes, filetype="pdf")
                            text = "\n".join(page.get_text() for page in pdf)
                            pdf.close()
                        elif ext == "txt":
                            text = content_bytes.decode("utf-8", errors="ignore")

                        if not text.strip():
                            indexing_status["indexed"].append({"name": name, "chunks": 0, "status": "sem texto"})
                            continue

                        chunk_size = 1000
                        chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

                        document_store.append({
                            "name": name,
                            "folder": folder_name,
                            "content": text,
                            "chunks": len(chunks),
                            "chunk_texts": chunks,
                            "source": "sharepoint",
                            "web_url": item.get("webUrl", ""),
                            "preview": text[:200],
                        })
                        indexing_status["total_chunks"] += len(chunks)
                        indexing_status["indexed"].append({
                            "name": name,
                            "chunks": len(chunks),
                            "preview": text[:180],
                            "status": "indexado",
                        })

                    except Exception as e:
                        indexing_status["indexed"].append({"name": name, "chunks": 0, "status": f"erro: {str(e)[:80]}"})

        async with httpx.AsyncClient() as client:
            await index_folder(client)

        n = len(indexing_status["indexed"])
        c = indexing_status["total_chunks"]
        indexing_status["progress"] = f"Concluído: {n} documentos, {c} trechos."
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
    """List all documents currently indexed in memory."""
    docs = []
    for d in document_store:
        docs.append({
            "name": d["name"],
            "folder": d.get("folder", ""),
            "chunks": d.get("chunks", 0),
            "preview": d.get("preview", "")[:200],
            "web_url": d.get("web_url", ""),
            "source": d.get("source", ""),
        })
    return {
        "total": len(docs),
        "total_chunks": sum(d["chunks"] for d in docs),
        "documentos": docs,
    }


@app.post("/api/sharepoint/upload")
async def upload_sharepoint_file():
    """Handle file upload to session (placeholder for multipart)."""
    raise HTTPException(status_code=501, detail="Use a rota /api/indexar-sharepoint para carregar documentos.")


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

    system_prompt = """Você é um assistente jurídico especializado em elaborar documentos jurídicos brasileiros.
O usuário quer elaborar um documento do tipo informado. Sua tarefa é gerar perguntas ADAPTATIVAS e INTELIGENTES
para coletar as informações necessárias para redigir esse documento.

REGRAS:
- Gere entre 3 e 8 perguntas relevantes para o tipo de documento
- As perguntas devem ser específicas ao contexto (não genéricas)
- Use tipos variados: "choice" (com opções), "multiple" (múltipla escolha), "text" (resposta livre)
- Para "choice" e "multiple", inclua opções relevantes e sempre uma opção "Outro"
- Opções devem ter campos: id (string curta), label (texto visível), desc (descrição opcional)
- Cada pergunta deve ter: id (q1, q2...), text, type, options (se choice/multiple)
- Pense no que um advogado experiente perguntaria ao cliente

Responda APENAS com JSON válido neste formato:
{
  "thinking_summary": "breve resumo do raciocínio",
  "questions": [
    {"id": "q1", "text": "pergunta", "type": "choice", "options": [{"id": "opt1", "label": "Opção 1", "desc": "descrição"}, {"id": "other", "label": "Outro"}]},
    {"id": "q2", "text": "pergunta livre", "type": "text"}
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
    update_session(session)

    doc_type = session.doc_type or "Documento Jurídico"
    answers_text = "\n".join(f"- {k}: {v}" for k, v in session.answers.items())

    # Provide document store context if available
    docs_context = ""
    if document_store:
        docs_context = f"\n\nVocê tem acesso a {len(document_store)} documentos de referência do escritório para usar como base de estilo e argumentação."

    system_prompt = f"""Você é um assistente jurídico especializado. O usuário está elaborando: {doc_type}.
Informações já coletadas:
{answers_text}
{docs_context}

Analise as informações. Você tem DUAS opções:

OPÇÃO 1 - Se FALTAM informações críticas para elaborar o documento, gere mais perguntas adaptativas.
Responda com JSON:
{{"action": "more_questions", "thinking_summary": "por que precisa de mais info", "questions": [...]}}

OPÇÃO 2 - Se já tem informações SUFICIENTES, gere um roteiro detalhado do documento.
Responda com JSON:
{{"action": "outline", "outline": {{
  "title": "título da peça",
  "subtitle": "subtítulo descritivo",
  "estimated_pages": N,
  "key_arguments": ["argumento 1", "argumento 2"],
  "sections": [
    {{"title": "Seção", "description": "o que conterá", "legal_basis": ["Art. X da Lei Y"]}}
  ]
}}}}

As perguntas (se opção 1) devem ser específicas ao caso, NÃO genéricas. Use choice/multiple/text conforme adequado.
O roteiro (se opção 2) deve ter seções detalhadas com fundamentação legal específica ao caso.
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
        # Fallback: generate outline directly
        session.outline = {
            "title": doc_type,
            "subtitle": f"Baseado em {len(session.answers)} informações",
            "estimated_pages": 5,
            "key_arguments": [v for v in session.answers.values() if len(str(v)) > 10][:5],
            "sections": [
                {"title": "Qualificação das Partes", "description": "Identificação completa.", "legal_basis": ["CPC Art. 319"]},
                {"title": "Dos Fatos", "description": "Narrativa dos fatos.", "legal_basis": []},
                {"title": "Do Direito", "description": "Fundamentação jurídica.", "legal_basis": []},
                {"title": "Dos Pedidos", "description": "Requerimentos.", "legal_basis": []},
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
async def generate_document(session_id: str, background_tasks: BackgroundTasks):
    """
    Generate the final document (streaming)
    TODO: Implement AI document generation with streaming
    """
    session = get_session(session_id)
    
    # Extract variables to avoid complex expressions in f-string
    cliente = session.answers.get("cliente", "__NOME DO CLIENTE__")
    tipo_pessoa = session.answers.get("tipo_pessoa", "pessoa física")
    doc_cliente = session.answers.get("documento", "__DOCUMENTO__")
    reu = session.answers.get("reu", "__NOME DO RÉU__")
    reu_tipo = session.answers.get("reu_tipo_pessoa", "pessoa física")
    reu_doc = session.answers.get("reu_documento", "__DOCUMENTO__")
    vara = session.answers.get("vara", "__VARA__")
    artigo = session.answers.get("artigo", "300")
    fatos = session.answers.get("fatos", "__Descreva os fatos...__")
    fundamentacao = session.answers.get("fundamentacao", "__Descreva a fundamentação jurídica...__")
    pedidos = session.answers.get("pedidos", "__Liste os pedidos...__")
    cidade = session.answers.get("cidade", "__CIDADE__")
    doc_type_label = session.doc_type or "AÇÃO"
    tipo_doc_cliente = "CNPJ" if tipo_pessoa.lower() == "pessoa jurídica" else "CPF"
    tipo_doc_reu = "CNPJ" if reu_tipo.lower() == "pessoa jurídica" else "CPF"

    sample_doc = f"""{doc_type_label}

EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA {vara} VARA CÍVEL DA COMARCA DE __COMARCA__

{cliente}, {tipo_doc_cliente}: {doc_cliente}, através de seu advogado e progenitor ao final firmado, vem respeitosamente à presença de Vossa Excelência com fundamento no artigo {artigo} do Código de Processo Civil propor

{doc_type_label}

em face de {reu}, {tipo_doc_reu}: {reu_doc}, pelos fatos e fundamentos a seguir expostos:

I - DOS FATOS
{fatos}

II - DO DIREITO
{fundamentacao}

III - DOS PEDIDOS
{pedidos}

Protesta provar o alegado por todos os meios de prova em direito admitidos.

Termos em que,
P. Deferimento.

{cidade}, {datetime.now().strftime("%d de %B de %Y")}

_______________________
OAB/UF
Advogado"""

    return {
        "session_id": session.id,
        "document": sample_doc,
        "message": "Document generated successfully"
    }


# ─── Chat ───

@app.post("/api/chat")
async def chat_message(request: ChatRequest):
    """Free-form chat with AI."""
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

    docs_context = ""
    if document_store:
        docs_context = f"\nVocê tem {len(document_store)} documentos de referência do escritório indexados na memória."

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
        response_text = await llm.chat(
            system=system_prompt,
            user=f"Histórico recente:\n{history}\n\nMensagem atual: {request.message}",
        )
    except Exception as e:
        response_text = f"Erro ao processar: {str(e)[:200]}"

    response = {
        "role": "assistant",
        "type": "text",
        "content": response_text,
        "timestamp": datetime.now().isoformat(),
    }
    session.messages.append(response)
    update_session(session)

    return {"response": response_text}


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
