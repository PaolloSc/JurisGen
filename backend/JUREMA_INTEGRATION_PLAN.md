# Plano de Integração Jurema 7B no JurisGen AI

## Análise do Estado Atual

### Arquitetura Atual
```
LLMClient (client.py)
├── chat() → Claude CLI (único modelo usado na maioria dos endpoints)
├── chat_multi() → Claude + Jurema + LongCat (paralelo) ← usado apenas em generate-document
├── chat_with_jurema() → Claude + Jurema (paralelo) ← DEFINIDO MAS NUNCA CHAMADO
└── HuggingFaceClient
    ├── chat_jurema() → Jurema 7B via HF Inference API
    ├── chat_longcat() → LongCat Flash Thinking
    ├── _direct_inference() → fallback direto HF API
    └── Circuit breaker + retry (3 tentativas, delays [5, 15, 30]s)
```

### Problemas Identificados

1. **Jurema usado em apenas 1 endpoint** (generate-document via `chat_multi()`)
2. **`chat_with_jurema()` existe mas nunca é chamado** — método pronto para uso mas ignorado
3. **API HF retorna 503 frequentemente** (modelo carregando) — retry atual é básico
4. **Sem timeout por tentativa** — retry pode travar indefinidamente
5. **Circuit breaker sem recuperação parcial** — ou totalmente ativo ou totalmente cooldown

### Endpoints e Uso Atual de LLM

| Endpoint | Método LLM Atual | Jurema? | Linha |
|----------|------------------|---------|-------|
| generate-document | `chat_multi()` | ✅ Sim (único) | ~959 |
| chat | `chat()` | ❌ Não | ~1491 |
| adversarial-analysis | `chat()` | ❌ Não | ~1273 |
| apply-correction | `chat()` | ❌ Não | ~1453 |
| set-type | `chat()` | ❌ Não | ~782 |
| answer | `chat()` | ❌ Não | ~843 |

---

## Plano de Implementação

### FASE 1: Melhorar Confiabilidade da API HF (client.py)

#### 1.1 Exponential Backoff + Timeout por Tentativa

Substituir delays fixos `[5, 15, 30]` por exponential backoff com jitter:

```python
# Config atual (manter)
JUREMA_MAX_RETRIES = 3
JUREMA_COOLDOWN_SECONDS = 120

# Novo: timeout por tentativa individual
JUREMA_REQUEST_TIMEOUT = 45  # segundos por tentativa

# Novo: exponential backoff com jitter
async def _retry_delay(attempt: int) -> float:
    """Calculate delay with exponential backoff + random jitter."""
    import random
    base = min(5 * (2 ** attempt), 60)  # 5, 10, 20, max 60
    jitter = random.uniform(0, base * 0.3)  # até 30% de jitter
    return base + jitter
```

#### 1.2 Timeout por Tentativa no chat_jurema()

Adicionar timeout de 45s por tentativa individual usando `asyncio.wait_for()`:

```python
async def chat_jurema(self, system, user, temperature=0.3, max_tokens=2000):
    if not self._jurema_is_available():
        return None

    for attempt in range(JUREMA_MAX_RETRIES):
        try:
            response = await asyncio.wait_for(
                self.jurema.chat.completions.create(...),
                timeout=JUREMA_REQUEST_TIMEOUT,
            )
            text = response.choices[0].message.content or ""
            if text:
                return text
        except asyncio.TimeoutError:
            print(f"[Jurema] Timeout na tentativa {attempt + 1}")
        except Exception as e:
            # ... lógica existente de retry para 503 ...
        
        if attempt < JUREMA_MAX_RETRIES - 1:
            delay = await _retry_delay(attempt)
            await asyncio.sleep(delay)
    
    # fallback + circuit breaker (já existe)
```

#### 1.3 Circuit Breaker com Recuperação Parcial

Adicionar modo "half-open" para testar se Jurema voltou:

```python
class HuggingFaceClient:
    def __init__(self, api_key):
        # ... existing code ...
        self._jurema_cooldown_until: float = 0.0
        self._jurema_consecutive_failures: int = 0
        self._jurema_half_open: bool = False  # Novo

    def _jurema_is_available(self) -> bool:
        now = time.monotonic()
        if now >= self._jurema_cooldown_until:
            return True
        # Half-open: permitir 1 tentativa de teste
        if self._jurema_half_open:
            return False  # Já tem uma tentativa em andamento
        return False

    def _jurema_mark_failure(self):
        self._jurema_consecutive_failures += 1
        if self._jurema_consecutive_failures >= 3:
            self._jurema_cooldown_until = time.monotonic() + JUREMA_COOLDOWN_SECONDS
            self._jurema_half_open = True  # Permitir teste após cooldown
            print(f"[Jurema] Circuit breaker — cooldown {JUREMA_COOLDOWN_SECONDS}s")

    def _jurema_mark_success(self):
        self._jurema_consecutive_failures = 0
        self._jurema_half_open = False
```

#### 1.4 Métricas de Logging

Adicionar contadores para monitoramento:

```python
class HuggingFaceClient:
    def __init__(self, api_key):
        # ... existing ...
        self._stats = {
            "jurema_calls": 0,
            "jurema_successes": 0,
            "jurema_failures": 0,
            "jurema_timeouts": 0,
            "jurema_503s": 0,
            "longcat_calls": 0,
            "longcat_successes": 0,
        }

    async def get_stats(self) -> dict:
        return {**self._stats, "jurema_available": self._jurema_is_available()}
```

---

### FASE 2: Integrar Jurema nos Endpoints

#### 2.1 Endpoint: `/api/chat` (Chat Livre)

**Objetivo**: Jurema valida/responde com perspectiva de jurisprudência brasileira.

**Mudança**: Usar `chat_with_jurema()` em vez de `chat()`.

**Prompt Jurema para Chat**:
```python
jurema_system = """Você é o modelo Jurema, especialista em direito brasileiro com foco em jurisprudência.
Analise a pergunta/resposta e forneça:
1. Jurisprudência relevante (ementas, súmulas, OJs) que complementa a resposta
2. Artigos de lei específicos aplicáveis
3. Se houver erro jurídico na resposta principal, aponte com gentileza

Seja conciso (máximo 300 palavras). Responda em português brasileiro.
Se não houver jurisprudência relevante, diga "Sem jurisprudência específica para este tema."
NÃO invente citações — use apenas conhecimento real."""

jurema_user = f"Pergunta do usuário: {request.message}\n\nResposta principal (Claude): [será preenchida após Claude responder]"
```

**Implementação**:
```python
# No endpoint /api/chat, substituir:
# response_text = await llm.chat(system=system_prompt, user=...)

# Por:
result = await llm.chat_with_jurema(
    system=system_prompt,
    user=f"Histórico recente:\n{history}\n\nMensagem atual: {request.message}",
    jurema_system=JUREMA_CHAT_SYSTEM,
    jurema_user=f"Pergunta: {request.message}",
    max_tokens=2000,
    jurema_max_tokens=800,
)

response_text = result["claude"]
jurema_text = result.get("jurema")

# Adicionar jurisprudência como nota complementar
if jurema_text:
    response_text += f"\n\n---\n**📚 Jurisprudência (Jurema 7B):**\n{jurema_text}"
```

#### 2.2 Endpoint: `/api/pipeline/adversarial-analysis/{session_id}`

**Objetivo**: Jurema fornece jurisprudência que suporta a posição adversária.

**Mudança**: Usar `chat_with_jurema()` na etapa de análise de vulnerabilidades.

**Prompt Jurema para Análise Adversarial**:
```python
jurema_system = """Você é o modelo Jurema, especialista em jurisprudência brasileira.
Sua função: encontrar jurisprudência que FORTALECE a posição da parte adversária (réu).

Analise a peça jurídica e para cada ponto vulnerável:
1. Encontre ementas/súmulas que o réu usaria contra o autor
2. Identifique teses defensivas com respaldo jurisprudencial
3. Liste precedentes que desfavorecem a tese do autor

Seja específico: cite tribunais, números de processo quando possível.
Máximo 500 palavras. Responda em português brasileiro.
NÃO invente citações — use apenas jurisprudência real."""

jurema_user = f"Peça jurídica para análise adversária:\n{document_text[:3000]}\n\nVulnerabilidades identificadas:\n{_json.dumps([v['title'] for v in vulnerabilities[:5]])}"
```

**Implementação**:
```python
# Na etapa 2 (vulnerability analysis), após obter vulnerabilities:

# Enriquecer com jurisprudência adversarial da Jurema
if llm.jurema_available:
    jurema_result = await llm.hf_client.chat_jurema(
        system=JUREMA_ADVERSARIAL_SYSTEM,
        user=jurema_user,
        max_tokens=1000,
    )
    if jurema_result and is_valid_legal_pt(jurema_result):
        # Adicionar como vulnerabilidade jurisprudencial
        vulnerabilities.append({
            "id": f"v_jurema_{len(vulnerabilities)+1}",
            "title": "Jurisprudência adversarial (Jurema 7B)",
            "severity": "MEDIA",
            "category": "FUNDAMENTACAO",
            "description": jurema_result,
            "correction": "Reforçar fundamentação com jurisprudência que neutralize estes precedentes adversários.",
        })
```

#### 2.3 Endpoint: `/api/pipeline/apply-correction/{session_id}`

**Objetivo**: Jurema valida se a correção é consistente com jurisprudência.

**Mudança**: Usar `chat_with_jurema()` para validar a correção.

**Prompt Jurema para Validação de Correção**:
```python
jurema_system = """Você é o modelo Jurema, validador jurídico.
Analise a correção proposta e verifique:
1. Se a correção é juridicamente consistente com a jurisprudência brasileira
2. Se há jurisprudência que CONTRADIZ a correção
3. Se há jurisprudência que REFORÇA a correção

Responda em JSON:
{
  "valida": true/false,
  "jurisprudencia_reforco": "ementa que reforça a correção",
  "jurisprudencia_contradiz": "ementa que contradiz (se houver)",
  "recomendacao": "sugestão final"
}

NÃO invente citações. Se não houver jurisprudência relevante, indique."""

jurema_user = f"Vulnerabilidade: {vuln_title}\nCorreção sugerida: {vuln_correction}\nTexto original:\n{section_text[:1500]}"
```

**Implementação**:
```python
# No endpoint apply-correction, após obter corrected do Claude:

# Validar com Jurema
jurema_validation = None
if llm.jurema_available:
    jurema_raw = await llm.hf_client.chat_jurema(
        system=JUREMA_VALIDATION_SYSTEM,
        user=jurema_user,
        max_tokens=800,
    )
    if jurema_raw and is_valid_legal_pt(jurema_raw):
        try:
            jurema_validation = json.loads(jurema_raw)
        except:
            jurema_validation = {"recomendacao": jurema_raw}

return {
    "corrected_text": corrected,
    "jurema_validation": jurema_validation,
}
```

#### 2.4 Endpoint: `/api/pipeline/generate-document/{session_id}`

**Estado atual**: Já usa `chat_multi()` com Jurema. **Melhoria**: Garantir que Jurema seja chamada mesmo se LongCat falhar.

**Mudança mínima**: Separar as chamadas para que falha de LongCat não afete Jurema.

```python
# Atual (paralelo com gather):
claude_result, jurema_result, longcat_result = await asyncio.gather(
    claude_task, jurema_task, longcat_task, return_exceptions=True,
)

# Melhorado: Jurema em paralelo com Claude (independente de LongCat)
claude_task = self.chat(system=system, user=user, max_tokens=max_tokens)
jurema_task = self.hf_client.chat_jurema(...) if self.hf_client else None

# LongCat separado (opcional, não afeta Jurema)
longcat_task = self.hf_client.chat_longcat(...) if self.hf_client else None
```

---

### FASE 3: Estrutura de Código Mínima

#### Arquivos a Modificar

| Arquivo | Mudanças |
|---------|----------|
| `llm/client.py` | FASE 1 (retry, timeout, circuit breaker) + helper `chat_with_jurema_enriched()` |
| `main.py` | FASE 2 (integrar Jurema em chat, adversarial, apply-correction) |

#### Novo Método Helper em LLMClient

Criar `chat_with_jurema_enriched()` que simplifica o uso em endpoints:

```python
async def chat_with_jurema_enriched(
    self,
    system: str,
    user: str,
    jurema_system: str,
    jurema_user: str | None = None,
    max_tokens: int = 2000,
    jurema_max_tokens: int = 800,
    json_mode: bool = False,
    enrich_separator: str = "\n\n---\n**📚 Jurisprudência (Jurema 7B):**\n",
) -> dict[str, str | None]:
    """
    Claude + Jurema em paralelo. Retorna dict com 'response' (texto final enriquecido)
    e 'jurema' (resposta bruta da Jurema ou None).
    """
    result = await self.chat_with_jurema(
        system=system,
        user=user,
        jurema_system=jurema_system,
        jurema_user=jurema_user or user,
        max_tokens=max_tokens,
        jurema_max_tokens=jurema_max_tokens,
        json_mode=json_mode,
    )
    
    response = result["claude"]
    jurema = result.get("jurema")
    
    if jurema:
        response += f"{enrich_separator}{jurema}"
    
    return {"response": response, "jurema": jurema}
```

#### Constantes de Prompt Jurema

Adicionar em `main.py` (ou novo arquivo `prompts.py`):

```python
# Prompts Jurema por contexto
JUREMA_CHAT_PROMPT = """Você é o modelo Jurema, especialista em direito brasileiro com foco em jurisprudência.
Analise a pergunta e forneça:
1. Jurisprudência relevante (ementas, súmulas, OJs) que complementa
2. Artigos de lei específicos aplicáveis
3. Se houver erro jurídico, aponte com gentileza

Seja conciso (máx 300 palavras). Responda em pt-BR.
NÃO invente citações."""

JUREMA_ADVERSARIAL_PROMPT = """Você é o modelo Jurema, especialista em jurisprudência brasileira.
Encontre jurisprudência que FORTALECE a posição da parte adversária (réu).
Para cada ponto vulnerável, cite ementas/súmulas que o réu usaria.
Seja específico: tribunais, nº processo. Máx 500 palavras. pt-BR.
NÃO invente citações."""

JUREMA_VALIDATION_PROMPT = """Você é o modelo Jurema, validador jurídico.
Verifique se a correção é consistente com jurisprudência brasileira.
Responda em JSON: {"valida": bool, "reforco": "...", "contradiz": "...", "recomendacao": "..."}
NÃO invente citações."""
```

---

### FASE 4: Configuração (.env)

Variáveis opcionais para controle fino:

```bash
# ─── Jurema 7B Config ────────────────────────────────
JUREMA_MAX_RETRIES=3          # Tentativas por chamada
JUREMA_COOLDOWN_SECONDS=120   # Tempo de circuit breaker
JUREMA_REQUEST_TIMEOUT=45     # Timeout por tentativa (segundos)
JUREMA_ENABLED=true           # Desabilitar globalmente se false
```

---

## Resumo das Mudanças

### client.py (HuggingFaceClient)
1. ✅ Exponential backoff com jitter (substituir delays fixos)
2. ✅ Timeout por tentativa (45s via asyncio.wait_for)
3. ✅ Circuit breaker com half-open (recuperação parcial)
4. ✅ Métricas de logging (_stats dict)
5. ✅ Novo helper `chat_with_jurema_enriched()` em LLMClient

### main.py (Endpoints)
1. ✅ `/api/chat` → usar `chat_with_jurema()` com JUREMA_CHAT_PROMPT
2. ✅ `/api/pipeline/adversarial-analysis` → enriquecer vulnerabilities com Jurema
3. ✅ `/api/pipeline/apply-correction` → validar correção com Jurema
4. ✅ `/api/pipeline/generate-document` → já funciona, melhoria menor na separação de tarefas

### Novo arquivo (opcional)
- `prompts.py` → constantes de prompt Jurema por contexto

---

## Ordem de Implementação

1. **client.py** — melhorar retry/timeout/circuit breaker (FASE 1)
2. **client.py** — adicionar `chat_with_jurema_enriched()` helper
3. **main.py** — integrar Jurema no endpoint `/api/chat`
4. **main.py** — integrar Jurema no endpoint `adversarial-analysis`
5. **main.py** — integrar Jurema no endpoint `apply-correction`
6. **main.py** — melhoria menor em `generate-document` (separar LongCat)
7. **Testes** — verificar cada endpoint com Jurema ativa e em cooldown

---

## Riscos e Mitigações

| Risco | Mitigação |
|-------|-----------|
| Jurema 503 permanente | Circuit breaker + fallback gracioso (retorna None, nunca bloqueia) |
| Jurema retorna lixo (chinês, etc) | `is_valid_legal_pt()` já existe e filtra |
| Latência alta (Jurema lenta) | Timeout de 45s por tentativa + Claude roda em paralelo |
| API key HF expirada | Log claro + circuit breaker evita spam de erros |
| Jurema inventa jurisprudência | Prompts explícitos "NÃO invente citações" + validação |

---

## Critérios de Sucesso

1. ✅ Jurema participa de 4 endpoints (chat, adversarial, apply-correction, generate-document)
2. ✅ HF API 503 não causa falha — retry automático + fallback gracioso
3. ✅ Timeout de 45s por tentativa evita travamento
4. ✅ Circuit breaker previne spam de erros quando Jurema está instável
5. ✅ Resposta de Jurema é sempre complementar — nunca substitui Claude
6. ✅ Zero breaking changes — endpoints existentes continuam funcionando