import json
import re
import os
import random
import subprocess
import asyncio
import time
from typing import AsyncIterator

import httpx
from openai import AsyncOpenAI


# ─── HuggingFace Models Configuration ────────────────────────
HF_JUREMA_MODEL = "Jurema-br/Jurema-7B"
HF_LONGCAT_MODEL = "meituan-longcat/LongCat-Flash-Thinking"
HF_INFERENCE_URL = "https://router.huggingface.co/hf-inference/v1"

# ─── Jurema Retry / Circuit Breaker Config ────────────────────
JUREMA_MAX_RETRIES = int(os.getenv("JUREMA_MAX_RETRIES", "3"))
JUREMA_COOLDOWN_SECONDS = int(os.getenv("JUREMA_COOLDOWN_SECONDS", "120"))
JUREMA_REQUEST_TIMEOUT = int(os.getenv("JUREMA_REQUEST_TIMEOUT", "45"))


async def _jurema_retry_delay(attempt: int) -> float:
    """Exponential backoff with jitter: 5s, 10s, 20s (max 60s) + 0-30% jitter."""
    base = min(5 * (2 ** attempt), 60)
    jitter = random.uniform(0, base * 0.3)
    return base + jitter


def is_valid_legal_pt(text: str) -> bool:
    """Check if text is valid Portuguese legal content (not garbage/chinese/etc)."""
    if not text or len(text) < 50:
        return False
    if text.startswith("[Modelo") or text.startswith("[Erro"):
        return False
    non_latin = len(re.findall(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]', text))
    if non_latin > 5:
        return False
    pt_keywords = [
        "art.", "lei", "código", "tribunal", "processo", "direito",
        "jurisprudência", "dano", "réu", "autor", "súmula", "ementa",
    ]
    text_lower = text.lower()
    matches = sum(1 for kw in pt_keywords if kw in text_lower)
    return matches >= 2


class HuggingFaceClient:
    """Client for HuggingFace Inference API (OpenAI-compatible) with retry and circuit breaker."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.jurema = AsyncOpenAI(
            base_url=HF_INFERENCE_URL,
            api_key=api_key,
        )
        self.longcat = AsyncOpenAI(
            base_url=HF_INFERENCE_URL,
            api_key=api_key,
        )
        # Circuit breaker state
        self._jurema_cooldown_until: float = 0.0
        self._jurema_consecutive_failures: int = 0
        self._jurema_half_open: bool = False
        # Metrics
        self._stats = {
            "jurema_calls": 0,
            "jurema_successes": 0,
            "jurema_failures": 0,
            "jurema_timeouts": 0,
            "jurema_503s": 0,
            "longcat_calls": 0,
            "longcat_successes": 0,
        }

    def _jurema_is_available(self) -> bool:
        """Check if Jurema is outside cooldown period (supports half-open)."""
        if time.monotonic() >= self._jurema_cooldown_until:
            return True
        return False

    def _jurema_mark_failure(self):
        """Track failures and activate circuit breaker after consecutive failures."""
        self._jurema_consecutive_failures += 1
        if self._jurema_consecutive_failures >= 3:
            self._jurema_cooldown_until = time.monotonic() + JUREMA_COOLDOWN_SECONDS
            self._jurema_half_open = True
            print(f"[Jurema] Circuit breaker ativado — cooldown de {JUREMA_COOLDOWN_SECONDS}s (falhas consecutivas: {self._jurema_consecutive_failures})")

    def _jurema_mark_success(self):
        """Reset failure counter on success."""
        self._jurema_consecutive_failures = 0
        self._jurema_half_open = False

    async def get_stats(self) -> dict:
        """Return current Jurema/LongCat stats."""
        return {**self._stats, "jurema_available": self._jurema_is_available()}

    async def warm_up(self):
        """Fire a tiny request to wake up the Jurema model on HF Inference."""
        try:
            print("[Jurema] Enviando warm-up request...")
            await self.jurema.chat.completions.create(
                model=HF_JUREMA_MODEL,
                messages=[{"role": "user", "content": "Olá"}],
                max_tokens=1,
            )
            print("[Jurema] Warm-up OK — modelo ativo no HuggingFace")
        except Exception as e:
            print(f"[Jurema] Warm-up falhou (normal se modelo frio): {e}")

    async def chat_jurema(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str | None:
        """Chat with Jurema 7B with exponential backoff, timeout, and circuit breaker. Returns None on failure."""
        if not self._jurema_is_available():
            print("[Jurema] Em cooldown — pulando chamada")
            return None

        self._stats["jurema_calls"] += 1
        last_error = None

        for attempt in range(JUREMA_MAX_RETRIES):
            try:
                response = await asyncio.wait_for(
                    self.jurema.chat.completions.create(
                        model=HF_JUREMA_MODEL,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        temperature=temperature,
                        max_tokens=max_tokens,
                    ),
                    timeout=JUREMA_REQUEST_TIMEOUT,
                )
                text = response.choices[0].message.content or ""
                if text:
                    self._stats["jurema_successes"] += 1
                    self._jurema_mark_success()
                    print(f"[Jurema] Resposta obtida (tentativa {attempt + 1})")
                    return text
            except asyncio.TimeoutError:
                last_error = f"Timeout ({JUREMA_REQUEST_TIMEOUT}s)"
                self._stats["jurema_timeouts"] += 1
                print(f"[Jurema] Timeout na tentativa {attempt + 1}")
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                is_loading = "503" in error_str or "loading" in error_str or "service unavailable" in error_str
                if is_loading:
                    self._stats["jurema_503s"] += 1
                if is_loading and attempt < JUREMA_MAX_RETRIES - 1:
                    delay = await _jurema_retry_delay(attempt)
                    print(f"[Jurema] Modelo carregando (tentativa {attempt + 1}) — retry em {delay:.1f}s...")
                    await asyncio.sleep(delay)
                    continue
                print(f"[Jurema] Erro na tentativa {attempt + 1}: {e}")
                break

            # Delay between retries (exponential backoff)
            if attempt < JUREMA_MAX_RETRIES - 1:
                delay = await _jurema_retry_delay(attempt)
                print(f"[Jurema] Retry em {delay:.1f}s (tentativa {attempt + 1}/{JUREMA_MAX_RETRIES})")
                await asyncio.sleep(delay)

        # All retries exhausted — try direct inference as last resort
        try:
            result = await self._direct_inference(HF_JUREMA_MODEL, system, user, max_tokens)
            if result and not result.startswith("["):
                self._stats["jurema_successes"] += 1
                self._jurema_mark_success()
                return result
        except Exception:
            pass

        self._stats["jurema_failures"] += 1
        self._jurema_mark_failure()
        print(f"[Jurema] Todas as tentativas falharam. Último erro: {last_error}")
        return None

    async def chat_longcat(
        self,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int = 2000,
    ) -> str:
        """Chat with LongCat Flash Thinking — formal reasoning model."""
        try:
            response = await self.longcat.chat.completions.create(
                model=HF_LONGCAT_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            print(f"[LongCat] Erro na API OpenAI compat: {e}. Tentando fallback...")
            return await self._direct_inference(HF_LONGCAT_MODEL, system, user, max_tokens)

    async def _direct_inference(
        self, model: str, system: str, user: str, max_tokens: int
    ) -> str:
        """Fallback: call HuggingFace Inference API directly (non-OpenAI format)."""
        url = f"https://router.huggingface.co/hf-inference/models/{model}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "inputs": f"<|system|>\n{system}\n<|user|>\n{user}\n<|assistant|>\n",
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": 0.3,
                "return_full_text": False,
            },
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 503:
                    # Model loading — return empty or loading warning
                    print(f"[{model}] Modelo carregando (503). Retornando aviso.")
                    return f"[Modelo {model} carregando no HuggingFace. Tente novamente em alguns minutos.]"
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, list) and data:
                    return data[0].get("generated_text", "")
                return str(data)
            except Exception as e:
                print(f"[Fallback {model}] Erro grave: {e}")
                return f"[Erro ao acessar {model}: {e}]"


class _EOFRetryError(Exception):
    """Sentinel for transient Claude CLI EOF errors — triggers retry logic."""


class LLMClient:
    def __init__(self):
        # Allow choosing between maritaca, ollama, or claude_cli
        # Defaulting to claude_cli if CLAUDE_AUTH_MODE=cli is found
        if os.getenv("CLAUDE_AUTH_MODE") == "cli":
            self.provider = "claude_cli"
        else:
            self.provider = os.getenv("LLM_PROVIDER", "maritaca")

        if self.provider == "ollama":
            self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434/v1").rstrip("/v1").rstrip("/")
            self.model = os.getenv("OLLAMA_MODEL", "llama3.2")
            self.client = None
        elif self.provider == "claude_cli":
            self.claude_path = os.getenv("CLAUDE_CLI_PATH", "claude")
            self.client = None
        elif self.provider == "anthropic":
            import anthropic as _anthropic
            self.anthropic_client = _anthropic.AsyncAnthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            )
            self.model = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")
            self.client = None
        else:
            self.client = AsyncOpenAI(
                base_url=os.getenv("MARITACA_BASE_URL", "https://chat.maritaca.ai/api"),
                api_key=os.getenv("MARITACA_API_KEY", ""),
            )
            self.model = os.getenv("MARITACA_MODEL", "sabia-4")

        # HuggingFace models (Jurema 7B + LongCat)
        hf_key = os.getenv("HF_API_KEY", "")
        self.hf_client = HuggingFaceClient(hf_key) if hf_key else None

        # Local Ollama Jurema (priority over HF when enabled)
        self.ollama_jurema_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/v1").rstrip("/")
        self.ollama_jurema_model = os.getenv("JUREMA_OLLAMA_MODEL", "jurema")
        self.ollama_jurema_enabled = os.getenv("JUREMA_PROVIDER", "").lower() == "ollama"

    @property
    def jurema_available(self) -> bool:
        """Check if Jurema client is configured (local Ollama or HuggingFace)."""
        if self.ollama_jurema_enabled:
            return True
        return bool(self.hf_client and self.hf_client._jurema_is_available())

    async def _chat_jurema_ollama(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str | None:
        """Chat with Jurema 7B via local Ollama (JUREMA_PROVIDER=ollama)."""
        payload = {
            "model": self.ollama_jurema_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                r = await client.post(f"{self.ollama_jurema_url}/api/chat", json=payload)
                r.raise_for_status()
                msg = r.json().get("message", {})
                return msg.get("content") or None
        except Exception as e:
            print(f"[Jurema-Ollama] Erro: {e}")
            return None

    async def chat_jurema(
        self,
        system: str,
        user: str,
        max_tokens: int = 1000,
    ) -> str | None:
        """Unified Jurema call — routes to Ollama or HuggingFace based on JUREMA_PROVIDER."""
        if self.ollama_jurema_enabled:
            return await self._chat_jurema_ollama(system=system, user=user, max_tokens=max_tokens)
        if self.hf_client and self.hf_client._jurema_is_available():
            return await self.hf_client.chat_jurema(system=system, user=user, max_tokens=max_tokens)
        return None

    async def chat_with_jurema(
        self,
        system: str,
        user: str,
        jurema_system: str,
        jurema_user: str,
        max_tokens: int = 2000,
        jurema_max_tokens: int = 1500,
        json_mode: bool = False,
    ) -> dict[str, str | None]:
        """
        Run Claude (primary) + Jurema (enrichment) in PARALLEL.
        Returns {"claude": str, "jurema": str | None}.
        Jurema failure never blocks or degrades Claude's result.
        """
        claude_task = self.chat(system=system, user=user, max_tokens=max_tokens, json_mode=json_mode)

        if self.ollama_jurema_enabled:
            # Local Ollama has priority over HuggingFace
            jurema_task = self._chat_jurema_ollama(
                system=jurema_system,
                user=jurema_user,
                max_tokens=jurema_max_tokens,
            )
            claude_result, jurema_result = await asyncio.gather(
                claude_task, jurema_task, return_exceptions=True,
            )
        elif self.hf_client and self.hf_client._jurema_is_available():
            jurema_task = self.hf_client.chat_jurema(
                system=jurema_system,
                user=jurema_user,
                max_tokens=jurema_max_tokens,
            )
            claude_result, jurema_result = await asyncio.gather(
                claude_task, jurema_task, return_exceptions=True,
            )
        else:
            claude_result = await claude_task
            jurema_result = None

        # Claude must always return
        if isinstance(claude_result, Exception):
            raise claude_result
        claude_text = claude_result if isinstance(claude_result, str) else str(claude_result)

        # Jurema is optional — validate output
        jurema_text = None
        if isinstance(jurema_result, str) and is_valid_legal_pt(jurema_result):
            jurema_text = jurema_result

        return {"claude": claude_text, "jurema": jurema_text}

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
        Claude + Jurema in parallel. Returns dict with 'response' (final enriched text)
        and 'jurema' (raw Jurema output or None).
        Convenience wrapper around chat_with_jurema that auto-appends enrichment.
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

    async def status(self) -> dict:
        if self.provider == "claude_cli":
            return {
                "provider": "claude_cli",
                "available": True,
                "authenticated": True,
                "message": "Claude CLI ativo. Se o chat falhar, verifique login ou limite de uso.",
                "details": "Status rápido baseado na configuração do backend.",
            }

        if self.provider == "ollama":
            return {
                "provider": "ollama",
                "available": True,
                "message": f"Ollama ativo ({self.model})",
            }

        if self.provider == "anthropic":
            return {
                "provider": "anthropic",
                "available": bool(os.getenv("ANTHROPIC_API_KEY")),
                "message": "Anthropic configurado" if os.getenv("ANTHROPIC_API_KEY") else "ANTHROPIC_API_KEY ausente",
            }

        return {
            "provider": "maritaca",
            "available": bool(os.getenv("MARITACA_API_KEY")),
            "message": "Maritaca configurado" if os.getenv("MARITACA_API_KEY") else "MARITACA_API_KEY ausente",
        }

    async def chat(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> str:
        if self.provider == "ollama":
            return await self._chat_ollama(system, user, temperature, max_tokens)
        elif self.provider == "claude_cli":
            return await self._chat_claude_cli(system, user, json_mode)
        elif self.provider == "anthropic":
            return await self._chat_anthropic(system, user, temperature, max_tokens)
        else:
            return await self._chat_openai(system, user, temperature, max_tokens)

    async def chat_multi(
        self,
        system: str,
        user: str,
        section_title: str = "",
        temperature: float = 0.3,
        max_tokens: int = 3000,
    ) -> dict[str, str]:
        """
        Run Claude CLI + Jurema 7B + LongCat in PARALLEL.
        Returns dict with keys: 'claude', 'jurema', 'longcat'.
        Claude writes the main text; Jurema enriches with jurisprudence;
        LongCat validates legal reasoning.
        """
        # Claude: main document writer
        claude_task = self.chat(system=system, user=user, max_tokens=max_tokens)

        results = {"claude": "", "jurema": None, "longcat": None}

        jurema_prompt = f"""Você é o modelo Jurema, especialista em jurisprudência brasileira.
Para a seção "{section_title}", forneça jurisprudência ADICIONAL relevante no formato abaixo.
Busque em sua base de conhecimento ementas REAIS de tribunais superiores (TST, STF, STJ, TRTs).

FORMATO OBRIGATÓRIO para cada jurisprudência:

[Parágrafo introdutório contextualizando o ponto jurídico]

EMENTA: [texto integral da ementa]
(SIGLA nº NÚMERO, Relator(a): NOME, ÓRGÃO JULGADOR, julgado em DD-MM-AAAA, DJe DD-MM-AAAA)

[Parágrafo de análise conectando ao caso]

---

Forneça entre 2 e 4 jurisprudências neste formato. NÃO invente — use apenas jurisprudência real.
Responda APENAS com as citações formatadas, sem meta-comentários."""

        if self.ollama_jurema_enabled:
            # Local Ollama Jurema — no LongCat (only available on HF)
            jurema_task = self._chat_jurema_ollama(
                system=jurema_prompt,
                user=user,
                temperature=0.2,
                max_tokens=2000,
            )
            claude_result, jurema_result = await asyncio.gather(
                claude_task, jurema_task, return_exceptions=True,
            )
            results["claude"] = claude_result if isinstance(claude_result, str) else f"[Erro Claude: {claude_result}]"
            results["jurema"] = jurema_result if isinstance(jurema_result, str) and is_valid_legal_pt(jurema_result) else None
        elif self.hf_client:
            jurema_task = self.hf_client.chat_jurema(
                system=jurema_prompt,
                user=user,
                temperature=0.2,
                max_tokens=2000,
            )

            longcat_prompt = f"""You are a legal reasoning validator. Analyze the legal arguments
for section "{section_title}" and provide:
1. Key legal principles that apply (in Portuguese)
2. Any logical gaps in the argumentation
3. Suggested additional legal bases (Brazilian law articles, súmulas)

Be concise. Respond in Portuguese."""

            longcat_task = self.hf_client.chat_longcat(
                system=longcat_prompt,
                user=user,
                temperature=0.2,
                max_tokens=1500,
            )

            claude_result, jurema_result, longcat_result = await asyncio.gather(
                claude_task, jurema_task, longcat_task,
                return_exceptions=True,
            )

            results["claude"] = claude_result if isinstance(claude_result, str) else f"[Erro Claude: {claude_result}]"
            results["jurema"] = jurema_result if isinstance(jurema_result, str) and is_valid_legal_pt(jurema_result) else None
            results["longcat"] = longcat_result if isinstance(longcat_result, str) and is_valid_legal_pt(longcat_result) else None
        else:
            claude_result = await claude_task
            results["claude"] = claude_result if isinstance(claude_result, str) else f"[Erro: {claude_result}]"

        return results

    async def stream(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
        max_tokens: int = 3000,
    ) -> AsyncIterator[str]:
        """Gera texto em streaming — yield de chunks de texto conforme chegam."""
        if self.provider == "ollama":
            async for chunk in self._stream_ollama(system, user, temperature, max_tokens):
                yield chunk
        elif self.provider == "claude_cli":
            # Claude CLI doesn't natively stream in a way we can intercept easily to yield here,
            # so we map the sync call to yield once.
            res = await self._chat_claude_cli(system, user)
            yield res
        else:
            async for chunk in self._stream_openai(system, user, temperature, max_tokens):
                yield chunk

    # ── Claude CLI ────────────────────────────────────────────────────────────

    async def _chat_claude_cli(self, system: str, user: str, json_mode: bool = False) -> str:
        prompt = f"System: {system}\n\nUser: {user}"

        loop = asyncio.get_running_loop()
        def _run():
            try:
                # Resolve claude executable: shutil.which checks PATH correctly on
                # both Windows (finds claude.cmd / claude.exe in %APPDATA%\npm)
                # and Linux (finds /usr/local/bin/claude after npm -g install).
                import shutil
                claude_exe = shutil.which("claude") or shutil.which("claude.cmd")
                if not claude_exe:
                    # Last-resort hardcoded candidates
                    for c in [
                        "/usr/local/bin/claude",
                        os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "npm", "claude.cmd"),
                        os.path.join(os.path.expanduser("~"), ".local", "bin", "claude"),
                    ]:
                        if os.path.exists(c):
                            claude_exe = c
                            break
                if not claude_exe:
                    raise FileNotFoundError("claude not found")

                env = os.environ.copy()
                env["TERM"] = "dumb"
                env["PYTHONIOENCODING"] = "utf-8"
                # Garante que HOME aponta para o diretório correto (importante no Docker/Linux)
                if "HOME" not in env or not env["HOME"]:
                    env["HOME"] = os.path.expanduser("~")
                # Garante que o Claude CLI encontre as credenciais no diretório correto
                claude_home = os.path.join(env["HOME"], ".claude")
                if os.path.isdir(claude_home):
                    env["CLAUDE_CONFIG_DIR"] = claude_home
                # Desativa qualquer telemetria/interatividade
                env["NO_COLOR"] = "1"
                env["CI"] = "1"
                # Claude Code on Windows needs git-bash path
                if "CLAUDE_CODE_GIT_BASH_PATH" not in env:
                    git_bash_path = r"C:\Users\paollo\AppData\Local\Programs\Git\bin\bash.exe"
                    if os.path.exists(git_bash_path):
                        env["CLAUDE_CODE_GIT_BASH_PATH"] = git_bash_path

                # Pass prompt via stdin pipe to avoid command line length limits
                cmd = [claude_exe, "-p", "-", "--output-format", "text"]
                result = subprocess.run(
                    cmd,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    timeout=180,
                    env=env,
                )
                if result.returncode != 0:
                    error_output = (result.stderr or result.stdout or "").strip()
                    lower_error = error_output.lower()
                    if "login" in lower_error or "authenticated" in lower_error or "authentication" in lower_error:
                        raise Exception("Claude CLI não está autenticado. Execute 'claude login' e tente novamente.")
                    if "limit" in lower_error or "quota" in lower_error or "resets" in lower_error:
                        raise Exception(f"Claude CLI atingiu o limite da conta. {error_output}")
                    # EOF errors are transient — signal for retry
                    if "eof" in lower_error or "error reading from server" in lower_error:
                        raise _EOFRetryError(f"Claude CLI EOF: {error_output}")
                    raise Exception(f"Claude CLI Error: {error_output or 'erro desconhecido'}")

                output = result.stdout.strip()
                if not output:
                    raise Exception("Claude CLI retornou resposta vazia. Verifique se o login foi concluído com sucesso.")
                return output
            except _EOFRetryError:
                raise
            except FileNotFoundError:
                raise Exception("Claude CLI not found. Is it installed via npm and in your PATH?")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                return await loop.run_in_executor(None, _run)
            except _EOFRetryError as e:
                if attempt < max_retries - 1:
                    delay = 2 ** attempt  # 1s, 2s, 4s
                    print(f"[Claude CLI] EOF transient error (tentativa {attempt + 1}/{max_retries}), retry em {delay}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    raise Exception(str(e))

    # ── Ollama ────────────────────────────────────────────────────────────────

    async def _chat_ollama(self, system, user, temperature, max_tokens):
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        async with httpx.AsyncClient(timeout=300) as client:
            r = await client.post(f"{self.ollama_url}/api/chat", json=payload)
            r.raise_for_status()
            msg = r.json()["message"]
            return msg.get("content") or msg.get("thinking", "")

    async def _stream_ollama(self, system, user, temperature, max_tokens) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": True,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        # glm-5:cloud é modelo de raciocínio: thinking tokens chegam primeiro,
        # conteúdo real só aparece depois. Ignoramos chunks de thinking.
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream("POST", f"{self.ollama_url}/api/chat", json=payload) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = data.get("message", {})
                    chunk = msg.get("content", "")
                    # Ignora chunks de thinking (campo thinking presente mas content vazio)
                    if chunk:
                        yield chunk
                    if data.get("done"):
                        break

    # ── Anthropic SDK ─────────────────────────────────────────────────────────

    async def _chat_anthropic(self, system, user, temperature, max_tokens):
        response = await self.anthropic_client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text

    # ── OpenAI-compatible (Maritaca) ──────────────────────────────────────────

    async def _chat_openai(self, system, user, temperature, max_tokens):
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    async def _stream_openai(self, system, user, temperature, max_tokens) -> AsyncIterator[str]:
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


llm_client = LLMClient()
