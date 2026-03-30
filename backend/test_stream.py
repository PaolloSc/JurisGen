import asyncio, httpx, json


async def test_generate():
    api_base = "https://jurisgen.onrender.com"
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
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

        # 4. Generate document — read in REAL TIME
        print("Starting document generation...")
        r = await client.post(f"{api_base}/api/pipeline/generate-document/{sid}")
        print("Generate status:", r.status_code)
        if r.status_code != 200:
            print("Error:", r.text[:300])
            return

        total_bytes = 0
        section_count = 0
        error_count = 0
        line_buffer = ""

        async for chunk in r.aiter_bytes():
            total_bytes += len(chunk)
            try:
                text_chunk = chunk.decode("utf-8")
            except:
                text_chunk = chunk.decode("latin-1", errors="replace")

            line_buffer += text_chunk

            while "\n" in line_buffer:
                line, line_buffer = line_buffer.split("\n", 1)
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
                            f"  Section {section_count}: {title[:60]} ({content_len} chars)"
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
                        status = ev.get("data", {}).get("status", "")
                        print(f"  Research [{status}]: {msg[:80]}")
                except json.JSONDecodeError:
                    pass

            if total_bytes % 2000 < len(chunk):
                print(
                    f"  ... {total_bytes} bytes, {section_count} sections, {error_count} errors"
                )

        # Process any remaining buffered data after stream closes
        print(f"\nStream closed. Buffer: {len(line_buffer)} chars remaining")
        for line in line_buffer.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
                t = ev.get("type", "")
                if t == "section":
                    section_count += 1
                    title = ev.get("data", {}).get("section_title", "?")
                    print(f"  [BUFFERED] Section: {title[:60]}")
                elif t == "error":
                    error_count += 1
                    print(f"  [BUFFERED] ERROR: {ev.get('message', '?')[:100]}")
            except:
                pass

        print(
            f"\nTotal bytes: {total_bytes}, sections: {section_count}, errors: {error_count}"
        )


asyncio.run(test_generate())
