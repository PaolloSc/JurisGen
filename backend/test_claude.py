import subprocess, os, tempfile

claude_exe = os.path.join(os.path.expanduser("~"), ".local", "bin", "claude.exe")
env = os.environ.copy()
env["CLAUDE_CODE_GIT_BASH_PATH"] = r"C:\Users\paollo\AppData\Local\Programs\Git\bin\bash.exe"

prompt = """System: Você é um assistente jurídico. Gere 3 perguntas para uma petição inicial.
Responda APENAS com JSON válido:
{"thinking_summary": "resumo", "questions": [{"id": "q1", "text": "pergunta", "type": "text"}]}

User: O usuário quer elaborar: Petição Inicial"""

# Write to temp file and pass via stdin to avoid command line length issues
with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
    f.write(prompt)
    tmp = f.name

# Use --input-file or pipe stdin
with open(tmp, 'r', encoding='utf-8') as pf:
    result = subprocess.run(
        [claude_exe, "-p", prompt, "--output-format", "text"],
        capture_output=True,
        text=True,
        encoding='utf-8',
        timeout=120,
        env=env,
    )

os.unlink(tmp)
print("RC:", result.returncode)
print("STDOUT:", repr(result.stdout[:500]))
print("STDERR:", repr(result.stderr[:500]))
