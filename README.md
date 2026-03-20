# JurisGen AI — Gerador Adaptativo de Documentos Jurídicos

Sistema de geração de documentos jurídicos brasileiros com IA, interface conversacional híbrida (chat + formulários estruturados) e integração com SharePoint para referência de estilo.

## Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND (React + Vite)                  │
│                                                              │
│  ┌──────────┐  ┌──────────────────────┐  ┌───────────────┐  │
│  │ Sidebar   │  │     Chat Area        │  │  Input Bar    │  │
│  │           │  │                      │  │               │  │
│  │ SharePoint│  │  Messages[]          │  │  [textarea]   │  │
│  │ Browser   │  │  ├─ text             │  │  [send btn]   │  │
│  │           │  │  ├─ questions (form)  │  │               │  │
│  │ Session   │  │  ├─ outline (card)   │  └───────────────┘  │
│  │ Info      │  │  └─ document (view)  │                     │
│  └──────────┘  └──────────────────────┘                     │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP/JSON + NDJSON streaming
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI)                          │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────────────────────┐  │
│  │ Session Manager   │  │        AI Pipeline               │  │
│  │                   │  │                                  │  │
│  │ - doc_type        │  │  1. Classify intent              │  │
│  │ - answers{}       │  │  2. Generate questions (JSON)    │  │
│  │ - outline{}       │  │  3. Adaptive follow-up           │  │
│  │ - messages[]      │  │  4. Generate outline (JSON)      │  │
│  │ - style_refs[]    │  │  5. Generate doc (streaming)     │  │
│  └──────────────────┘  └──────────┬───────────────────────┘  │
│                                   │                          │
│  ┌────────────────────────────────┼────────────────────────┐ │
│  │         External Services      │                        │ │
│  │                                ▼                        │ │
│  │  ┌──────────────┐   ┌──────────────────┐               │ │
│  │  │ Claude API   │   │ Microsoft Graph  │               │ │
│  │  │              │   │   (SharePoint)   │               │ │
│  │  │ - Extended   │   │                  │               │ │
│  │  │   Thinking   │   │ - Search docs    │               │ │
│  │  │ - Structured │   │ - Fetch content  │               │ │
│  │  │   Output     │   │ - .docx extract  │               │ │
│  │  └──────────────┘   └──────────────────┘               │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Como o SharePoint entra no fluxo

O sistema usa documentos do SharePoint como **referências de estilo**, não como templates:

1. **Usuário busca** documentos no SharePoint pela sidebar (ex: "petição inicial consumidor")
2. **Backend busca** via Microsoft Graph API (`/search/query`) filtrando por `.docx`
3. **Usuário seleciona** um ou mais documentos como referência
4. **Backend extrai** o texto do `.docx` via `python-docx` (máx. 3000 chars/doc)
5. **Texto é injetado** no `system prompt` do Claude como seção de referência
6. **Claude adapta** seu estilo de escrita para ser consistente com os modelos

Isso garante que o documento gerado soa como algo que saiu do escritório do usuário, não como texto genérico de IA.

## Fluxo Híbrido: Chat + Formulários

A interface combina dois modos:

### Modo Estruturado (wizard)
- Seleção de tipo → Perguntas com opções → Outline → Documento
- O AI retorna JSON estruturado que o frontend renderiza como formulários interativos
- Cada rodada de perguntas é adaptativa (baseada nas respostas anteriores)

### Modo Chat (livre)
- O usuário pode digitar qualquer coisa a qualquer momento
- O AI interpreta a intenção e responde adequadamente
- Pode pular etapas, fazer perguntas diretas, pedir revisões

Ambos os modos coexistem — o chat funciona em qualquer estágio.

## Setup

### Pré-requisitos

- Python 3.12+
- Node.js 20+
- Conta Anthropic (API key)
- Azure AD App Registration (para SharePoint)

### 1. Configurar Azure AD (SharePoint)

```bash
# No Azure Portal (portal.azure.com):
# 1. Entra ID → App registrations → New registration
# 2. API permissions → Microsoft Graph → Application permissions:
#    - Sites.Read.All
#    - Files.Read.All
# 3. Grant admin consent
# 4. Certificates & secrets → New client secret

# Encontrar IDs do SharePoint:
# GET https://graph.microsoft.com/v1.0/sites/{hostname}:/sites/{site-name}
# GET https://graph.microsoft.com/v1.0/sites/{site-id}/drives
```

### 2. Backend

```bash
cd backend
cp .env.example .env
# Editar .env com suas credenciais

pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

### 4. Docker (produção)

```bash
cp backend/.env.example backend/.env
# Editar .env

docker compose up -d
```

## Endpoints da API

### Sessões
- `POST /api/sessions` — Criar nova sessão
- `GET /api/sessions/{id}` — Estado da sessão

### SharePoint
- `POST /api/sharepoint/search` — Buscar documentos
- `POST /api/sharepoint/attach` — Anexar como referência de estilo
- `DELETE /api/sharepoint/detach/{session_id}/{item_id}` — Remover referência

### Pipeline AI
- `POST /api/pipeline/set-type` — Definir tipo e gerar perguntas iniciais
- `POST /api/pipeline/answer` — Submeter respostas (retorna mais perguntas ou outline)
- `POST /api/pipeline/regenerate-outline/{id}` — Regenerar outline
- `POST /api/pipeline/generate-document/{id}` — Gerar documento (streaming NDJSON)

### Chat
- `POST /api/chat` — Mensagem livre (qualquer estágio)

## Próximos passos para produção

### Obrigatórios
- [ ] Substituir session store in-memory por Redis
- [ ] Adicionar autenticação (OAuth2 / Azure AD SSO)
- [ ] Rate limiting na API
- [ ] Logging estruturado (structlog)
- [ ] HTTPS com certificado válido

### Recomendados
- [ ] Exportar documento para .docx (python-docx)
- [ ] Exportar para PDF (ReportLab/WeasyPrint)
- [ ] Histórico de documentos gerados (PostgreSQL)
- [ ] Cache de tokens Graph API no Redis
- [ ] Streaming SSE no frontend (substituir polling NDJSON)
- [ ] Testes automatizados (pytest + Playwright)
- [ ] CI/CD via GitLab (já familiar da stack TRT-3)

### Opcionais
- [ ] Multi-tenancy (múltiplos escritórios)
- [ ] Fine-tuning de prompts por área jurídica
- [ ] Integração com PJe para peticionamento direto
- [ ] Versionamento de documentos gerados
- [ ] Revisão colaborativa (WebSocket)

## Stack

| Camada | Tecnologia | Motivo |
|--------|-----------|--------|
| Frontend | React + Vite | SPA leve, hot reload, familiar |
| Backend | FastAPI | Async nativo, tipagem, docs auto |
| AI | Claude API (Sonnet) | Extended thinking, JSON mode, qualidade |
| SharePoint | Microsoft Graph API | Acesso docs via client credentials |
| Deploy | Docker Compose | Portável, replicável |
| Sessions | In-memory → Redis | Escala horizontal |

## Licença

Projeto interno. Não distribuir sem autorização.
