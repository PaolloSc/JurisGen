import json
import os
import subprocess
import asyncio
from typing import AsyncIterator

import httpx
from openai import AsyncOpenAI


# ─── HuggingFace Models Configuration ────────────────────────
HF_JUREMA_MODEL = "Jurema-br/Jurema-7B"
HF_LONGCAT_MODEL = "meituan-longcat/LongCat-Flash-Thinking"
HF_INFERENCE_URL = "https://router.huggingface.co/v1"


class HuggingFaceClient:
    """Client for HuggingFace Inference API (OpenAI-compatible)."""

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

    async def chat_jurema(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str:
        """Chat with Jurema 7B — specialized Brazilian legal model."""
        try:
            response = await self.jurema.chat.completions.create(
                model=HF_JUREMA_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            # Fallback: try direct inference API
            return await self._direct_inference(HF_JUREMA_MODEL, system, user, max_tokens)

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
            return await self._direct_inference(HF_LONGCAT_MODEL, system, user, max_tokens)

    async def _direct_inference(
        self, model: str, system: str, user: str, max_tokens: int
    ) -> str:
        """Fallback: call HuggingFace Inference API directly (non-OpenAI format)."""
        url = f"https://api-inference.huggingface.co/models/{model}"
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
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 503:
                # Model loading — return empty
                return f"[Modelo {model} carregando no HuggingFace. Tente novamente em alguns minutos.]"
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and data:
                return data[0].get("generated_text", "")
            return str(data)


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
        else:
            self.client = AsyncOpenAI(
                base_url=os.getenv("MARITACA_BASE_URL", "https://chat.maritaca.ai/api"),
                api_key=os.getenv("MARITACA_API_KEY", ""),
            )
            self.model = os.getenv("MARITACA_MODEL", "sabia-4")

        # HuggingFace models (Jurema 7B + LongCat)
        hf_key = os.getenv("HF_API_KEY", "")
        self.hf_client = HuggingFaceClient(hf_key) if hf_key else None

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

        results = {"claude": "", "jurema": "", "longcat": ""}

        if self.hf_client:
            # Jurema: focused on extracting/citing jurisprudence
            jurema_prompt = f"""Você é o modelo Jurema, especialista em direito brasileiro.
Com base nas fontes de jurisprudência fornecidas, gere APENAS citações jurisprudenciais formatadas
para a seção "{section_title}". Para cada jurisprudência:
1. Transcreva a ementa ou trecho relevante entre aspas
2. Formate: (Tribunal, Tipo Nº Processo, Rel. Min./Des. Nome, j. DD/MM/AAAA)
3. Explique brevemente a relevância para o caso

Responda APENAS com as citações formatadas, sem texto adicional."""

            jurema_task = self.hf_client.chat_jurema(
                system=jurema_prompt,
                user=user,
                temperature=0.2,
                max_tokens=2000,
            )

            # LongCat: validate reasoning and suggest improvements
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

            # Run all three in parallel
            claude_result, jurema_result, longcat_result = await asyncio.gather(
                claude_task, jurema_task, longcat_task,
                return_exceptions=True,
            )

            results["claude"] = claude_result if isinstance(claude_result, str) else f"[Erro Claude: {claude_result}]"
            results["jurema"] = jurema_result if isinstance(jurema_result, str) else ""
            results["longcat"] = longcat_result if isinstance(longcat_result, str) else ""
        else:
            # No HF key — just use Claude
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
                # Claude CLI is a native .exe on Windows
                claude_exe = os.path.join(os.path.expanduser("~"), ".local", "bin", "claude.exe")
                if not os.path.exists(claude_exe):
                    claude_exe = os.path.join(os.path.expanduser("~"), ".local", "bin", "claude")

                env = os.environ.copy()
                env["TERM"] = "dumb"
                env["PYTHONIOENCODING"] = "utf-8"
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
                    raise Exception(f"Claude CLI Error: {error_output or 'erro desconhecido'}")

                output = result.stdout.strip()
                if not output:
                    raise Exception("Claude CLI retornou resposta vazia. Verifique se o login foi concluído com sucesso.")
                return output
            except FileNotFoundError:
                raise Exception("Claude CLI not found. Is it installed via npm and in your PATH?")

        return await loop.run_in_executor(None, _run)

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
