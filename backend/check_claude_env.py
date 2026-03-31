"""
check_claude_env.py — Diagnóstico do ambiente Claude CLI no backend.

Valida:
  1. Claude CLI está instalado e acessível no PATH
  2. Credenciais OAuth existem (via CLAUDE_CREDENTIALS_B64 ou arquivo local)
  3. Claude CLI consegue executar um prompt simples (teste de fumaça)
  4. Variáveis de ambiente relevantes estão configuradas

Uso:
    python check_claude_env.py          # diagnóstico completo
    python check_claude_env.py --quick  # apenas variáveis e binário (sem chamar a API)
"""

import os
import shutil
import subprocess
import sys
import json
import base64
import argparse


def section(title: str):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print('='*50)


def ok(msg: str):
    print(f"  [OK]  {msg}")


def warn(msg: str):
    print(f"  [WARN] {msg}")


def fail(msg: str):
    print(f"  [FAIL] {msg}")


def check_env_vars():
    section("Variáveis de Ambiente")

    # Provider config
    auth_mode = os.getenv("CLAUDE_AUTH_MODE", "<não definida>")
    provider = os.getenv("LLM_PROVIDER", "<não definida>")
    print(f"  CLAUDE_AUTH_MODE  = {auth_mode}")
    print(f"  LLM_PROVIDER      = {provider}")

    if auth_mode == "cli" and provider == "claude_cli":
        ok("Configuração principal: Claude CLI sem API key")
    elif provider == "claude_cli":
        warn("LLM_PROVIDER=claude_cli mas CLAUDE_AUTH_MODE não é 'cli'")
    else:
        warn(f"Provider ativo: {provider} (não é claude_cli)")

    # Credentials
    creds_b64 = os.getenv("CLAUDE_CREDENTIALS_B64")
    if creds_b64:
        try:
            decoded = base64.b64decode(creds_b64).decode("utf-8")
            data = json.loads(decoded)
            ok(f"CLAUDE_CREDENTIALS_B64 presente e decodificável (chaves: {list(data.keys())})")
        except Exception as e:
            fail(f"CLAUDE_CREDENTIALS_B64 inválido: {e}")
    else:
        warn("CLAUDE_CREDENTIALS_B64 não definida (esperado em ambiente Render/CI)")
        cred_file = os.path.join(os.path.expanduser("~"), ".claude", ".credentials.json")
        if os.path.exists(cred_file):
            ok(f"Arquivo de credenciais local encontrado: {cred_file}")
        else:
            fail(f"Credenciais não encontradas em {cred_file} — execute 'claude login'")

    # Fallbacks (opcionais)
    maritaca = os.getenv("MARITACA_API_KEY")
    if maritaca:
        ok("MARITACA_API_KEY configurada (fallback disponível)")
    else:
        print("  MARITACA_API_KEY  = <não definida> (fallback desativado)")

    hf_key = os.getenv("HF_API_KEY")
    if hf_key:
        ok("HF_API_KEY configurada (Jurema 7B disponível)")
    else:
        print("  HF_API_KEY        = <não definida> (Jurema 7B desativado)")

    # Nunca deve ser necessária, mas registra se presente
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        warn("ANTHROPIC_API_KEY está definida — será usada pelo CLI como conveniência, não é obrigatória")
    else:
        ok("ANTHROPIC_API_KEY ausente (correto — autenticação via OAuth/CLI)")


def check_binary():
    section("Binário Claude CLI")

    claude_exe = shutil.which("claude") or shutil.which("claude.cmd")
    if claude_exe:
        ok(f"claude encontrado: {claude_exe}")
    else:
        fail("claude não encontrado no PATH")
        print("  Instale com: npm install -g @anthropic-ai/claude-code")
        return False

    # Version check
    try:
        result = subprocess.run(
            [claude_exe, "--version"],
            capture_output=True, text=True, timeout=10,
            env={**os.environ, "NO_COLOR": "1", "CI": "1"},
        )
        version_line = (result.stdout or result.stderr or "").strip().splitlines()[0]
        ok(f"Versão: {version_line}")
    except Exception as e:
        warn(f"Não foi possível verificar versão: {e}")

    return True


def check_credentials_file():
    section("Arquivo de Credenciais")

    # Reproduz a lógica do start.sh — verifica se credentials foram escritas
    claude_dir = os.path.join(os.path.expanduser("~"), ".claude")
    cred_file = os.path.join(claude_dir, ".credentials.json")

    if os.path.exists(cred_file):
        try:
            with open(cred_file) as f:
                data = json.load(f)
            ok(f"Credenciais carregadas de {cred_file} (chaves: {list(data.keys())})")
            return True
        except Exception as e:
            fail(f"Arquivo existe mas é inválido: {e}")
            return False
    else:
        fail(f"Arquivo ausente: {cred_file}")
        print("  Em produção (Render): defina CLAUDE_CREDENTIALS_B64 no dashboard.")
        print("  Localmente: execute 'claude login'.")
        return False


def check_smoke_test():
    section("Teste de Fumaça (chamada real ao Claude CLI)")

    claude_exe = shutil.which("claude") or shutil.which("claude.cmd")
    if not claude_exe:
        fail("Claude CLI não encontrado — pulando teste")
        return

    env = os.environ.copy()
    env.update({"TERM": "dumb", "NO_COLOR": "1", "CI": "1", "PYTHONIOENCODING": "utf-8"})

    prompt = "Responda apenas: OK"
    try:
        result = subprocess.run(
            [claude_exe, "-p", "-", "--output-format", "text"],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            env=env,
        )
        if result.returncode == 0 and result.stdout.strip():
            ok(f"Resposta recebida: {result.stdout.strip()[:80]}")
        else:
            err = (result.stderr or result.stdout or "").strip()
            fail(f"Retornou RC={result.returncode}: {err[:200]}")
    except subprocess.TimeoutExpired:
        fail("Timeout ao chamar Claude CLI (60s)")
    except Exception as e:
        fail(f"Erro ao chamar Claude CLI: {e}")


def main():
    parser = argparse.ArgumentParser(description="Diagnóstico Claude CLI")
    parser.add_argument("--quick", action="store_true", help="Apenas variáveis e binário (sem chamada de API)")
    args = parser.parse_args()

    print("\nJurisGen — Diagnóstico do Ambiente Claude CLI")
    print(f"Python: {sys.version}")
    print(f"HOME:   {os.path.expanduser('~')}")

    check_env_vars()
    bin_ok = check_binary()
    cred_ok = check_credentials_file()

    if not args.quick and bin_ok and cred_ok:
        check_smoke_test()
    elif not bin_ok or not cred_ok:
        section("Resumo")
        fail("Ambiente incompleto — corrija os erros acima antes de iniciar o servidor.")
        sys.exit(1)

    section("Resumo")
    ok("Diagnóstico concluído.")


if __name__ == "__main__":
    main()
