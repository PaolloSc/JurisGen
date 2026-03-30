import asyncio, httpx, json


async def test_generate():
    api_base = "https://jurisgen.onrender.com"
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        # 1. Create session
        r = await client.post(f"{api_base}/api/sessions", json={})
        print("Create session:", r.status_code)
        if r.status_code != 200:
            print("Error:", r.text[:300])
            return
        sid = r.json()["id"]
        print("Session:", sid)

        # 2. Set type
        r = await client.post(
            f"{api_base}/api/pipeline/set-type",
            json={
                "session_id": sid,
                "doc_type": "Peticao Inicial",
                "context": "Peticao Inicial",
            },
        )
        print("Set type:", r.status_code)
        if r.status_code != 200:
            print("Error:", r.text[:300])
            return
        d = r.json()
        print("Questions:", len(d.get("questions", [])))

        # 3. Submit answers and get outline
        answers = {"Tipo de acao": "Indenizacao", "Valor estimado": "R$ 50.000"}
        r = await client.post(
            f"{api_base}/api/pipeline/answer",
            json={"session_id": sid, "answers": answers},
        )
        print("Answer:", r.status_code)
        if r.status_code != 200:
            print("Error:", r.text[:300])
            return
        d = r.json()
        print("Action:", d.get("action"))
        outline = d.get("outline")
        sections = outline.get("sections", []) if outline else []
        print("Outline sections:", len(sections))

        # 4. Generate document
        print("Starting document generation...")
        r = await client.post(f"{api_base}/api/pipeline/generate-document/{sid}")
        print("Generate status:", r.status_code)
        if r.status_code != 200:
            print("Error:", r.text[:300])
            return

        # Read stream
        content = b""
        line_buffer = b""
        section_count = 0
        error_count = 0

        async for chunk in r.aiter_bytes():
            content += chunk

        print("Total bytes received:", len(content))
        text = content.decode("utf-8", errors="replace")

        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
                t = ev.get("type", "")
                if t == "section":
                    section_count += 1
                    title = ev.get("data", {}).get("section_title", "?")
                    content_len = len(ev.get("data", {}).get("content", ""))
                    print(
                        f"  Section {section_count}: {title[:60]} (content: {content_len} chars)"
                    )
                elif t == "error":
                    error_count += 1
                    print(f"  ERROR: {ev.get('message', '?')[:200]}")
                elif t == "done":
                    print(
                        f"  DONE: sections={ev.get('total_sections')}, sources={ev.get('total_sources')}"
                    )
                elif t == "research":
                    msg = ev.get("data", {}).get("message", "")
                    print(f"  Research: {msg[:80]}")
            except json.JSONDecodeError as e:
                print(f"  JSON parse error: {e} on line: {line[:100]}")

        print(f"Total sections: {section_count}, errors: {error_count}")


asyncio.run(test_generate())
