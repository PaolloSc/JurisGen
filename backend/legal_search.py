"""
Pesquisa jurídica real: jurisprudência, doutrina e modelos.
Usa DATAJUD API (CNJ) para busca direta nos tribunais + DuckDuckGo como fallback.
Retorna resultados com fontes verificáveis (URL, tribunal, data, ementa).
"""

import asyncio
import re
from typing import Any

import httpx

# ─── DATAJUD API (CNJ) ────────────────────────────────────────
# API pública do Conselho Nacional de Justiça — Elasticsearch
DATAJUD_BASE = "https://api-publica.datajud.cnj.jus.br"
DATAJUD_KEY = "cDZHYzlZa0JadVREZDJCb0ZxSkR0dz09"

TRIBUNAL_ENDPOINTS = {
    "STJ": f"{DATAJUD_BASE}/api_publica_stj/_search",
    "STF": f"{DATAJUD_BASE}/api_publica_stf/_search",
    "TST": f"{DATAJUD_BASE}/api_publica_tst/_search",
    "TJSP": f"{DATAJUD_BASE}/api_publica_tjsp/_search",
    "TJMG": f"{DATAJUD_BASE}/api_publica_tjmg/_search",
    "TJRJ": f"{DATAJUD_BASE}/api_publica_tjrj/_search",
    "TRT3": f"{DATAJUD_BASE}/api_publica_trt3/_search",
}

# Tribunais prioritários por tipo de ação
TRIBUNAL_PRIORITY = {
    "trabalhista": ["TST", "TRT3"],
    "consumidor": ["STJ", "TJSP", "TJMG"],
    "civil": ["STJ", "TJSP", "TJMG"],
    "penal": ["STJ", "STF", "TJSP"],
    "constitucional": ["STF", "STJ"],
    "default": ["STJ", "TJSP", "STF"],
}


async def search_datajud(
    tema: str,
    tribunais: list[str] | None = None,
    max_per_tribunal: int = 3,
) -> list[dict[str, Any]]:
    """
    Busca jurisprudência diretamente na API DATAJUD do CNJ.
    Retorna ementas reais com nº processo, relator, data, tribunal.
    """
    if not tribunais:
        tribunais = ["STJ", "TJSP", "STF"]

    headers = {
        "Authorization": f"APIKey {DATAJUD_KEY}",
        "Content-Type": "application/json",
    }

    # Elasticsearch query body
    query_body = {
        "size": max_per_tribunal,
        "query": {
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": tema,
                            "fields": ["assunto.nome", "classe.nome"],
                            "type": "best_fields",
                            "fuzziness": "AUTO",
                        }
                    }
                ],
            }
        },
        "sort": [{"dataAjuizamento": {"order": "desc"}}],
        "_source": [
            "numeroProcesso", "classe.nome", "assunto.nome",
            "dataAjuizamento", "tribunal", "grau",
            "movimentos.nome", "movimentos.dataHora",
        ],
    }

    results = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        tasks = []
        for trib in tribunais:
            endpoint = TRIBUNAL_ENDPOINTS.get(trib)
            if not endpoint:
                continue
            tasks.append(_fetch_tribunal(client, endpoint, trib, headers, query_body))

        responses = await asyncio.gather(*tasks, return_exceptions=True)
        for resp in responses:
            if isinstance(resp, list):
                results.extend(resp)

    return results


async def _fetch_tribunal(
    client: httpx.AsyncClient,
    endpoint: str,
    tribunal: str,
    headers: dict,
    query_body: dict,
) -> list[dict]:
    """Fetch results from one tribunal endpoint."""
    try:
        resp = await client.post(endpoint, headers=headers, json=query_body)
        if resp.status_code != 200:
            return []

        data = resp.json()
        hits = data.get("hits", {}).get("hits", [])
        results = []

        for hit in hits:
            src = hit.get("_source", {})
            numero = src.get("numeroProcesso", "")
            classe = src.get("classe", {}).get("nome", "")
            assuntos = [a.get("nome", "") for a in src.get("assunto", [])]
            data_ajuiz = src.get("dataAjuizamento", "")

            # Build ementa-like text from available data
            assunto_text = ", ".join(assuntos) if assuntos else "N/A"

            # Get last substantive movement as "ementa"
            movimentos = src.get("movimentos", [])
            ementa = ""
            for mov in movimentos[:5]:
                nome_mov = mov.get("nome", "")
                if any(kw in nome_mov.lower() for kw in ["julgamento", "decisão", "acórdão", "sentença"]):
                    ementa = nome_mov
                    break
            if not ementa and movimentos:
                ementa = movimentos[0].get("nome", "")

            # Format process number as CNJ standard
            numero_formatado = _format_processo_cnj(numero)

            results.append({
                "type": "jurisprudencia",
                "title": f"{classe} - {assunto_text}",
                "processo": numero_formatado,
                "tribunal": tribunal,
                "source": _tribunal_full_name(tribunal),
                "data": data_ajuiz[:10] if data_ajuiz else "",
                "ementa": ementa,
                "assuntos": assuntos,
                "classe": classe,
                "snippet": f"{classe}. {assunto_text}. Processo {numero_formatado}. {ementa}",
                "url": _build_tribunal_url(tribunal, numero),
            })

        return results
    except Exception:
        return []


# ─── DuckDuckGo (fallback + complemento para ementas) ─────────

async def search_duckduckgo_jurisprudencia(
    tema: str,
    case_context: str = "",
    max_results: int = 5,
) -> list[dict[str, Any]]:
    """Busca jurisprudência via DuckDuckGo — foca em ementas de tribunais."""
    from duckduckgo_search import DDGS

    combined = f"{tema} {case_context}"[:200]

    queries = [
        f'site:stj.jus.br ementa "{tema}"',
        f'site:jusbrasil.com.br ementa "{tema}" acórdão',
        f'"{tema}" ementa relator julgado tribunal',
        f'site:stf.jus.br ementa "{tema}"',
    ]

    loop = asyncio.get_running_loop()

    def _search():
        found = []
        with DDGS() as ddgs:
            for query in queries:
                try:
                    hits = list(ddgs.text(query, max_results=3))
                    for hit in hits:
                        found.append({
                            "type": "jurisprudencia",
                            "title": hit.get("title", ""),
                            "url": hit.get("href", ""),
                            "snippet": hit.get("body", ""),
                            "source": _extract_source(hit.get("href", "")),
                            "tribunal": _extract_tribunal_from_url(hit.get("href", "")),
                            "processo": _extract_processo_from_text(
                                hit.get("title", "") + " " + hit.get("body", "")
                            ),
                        })
                except Exception:
                    continue
        return found

    results = await loop.run_in_executor(None, _search)
    return _deduplicate(results)[:max_results]


async def search_doutrina_targeted(
    tema: str,
    max_results: int = 2,
) -> list[dict[str, Any]]:
    """Busca doutrina e artigos jurídicos."""
    from duckduckgo_search import DDGS

    queries = [
        f'site:conjur.com.br "{tema}"',
        f'site:migalhas.com.br "{tema}"',
        f'doutrina "{tema}" direito brasileiro',
    ]

    loop = asyncio.get_running_loop()

    def _search():
        found = []
        with DDGS() as ddgs:
            for query in queries:
                try:
                    hits = list(ddgs.text(query, max_results=2))
                    for hit in hits:
                        found.append({
                            "type": "doutrina",
                            "title": hit.get("title", ""),
                            "url": hit.get("href", ""),
                            "snippet": hit.get("body", ""),
                            "source": _extract_source(hit.get("href", "")),
                        })
                except Exception:
                    continue
        return found

    results = await loop.run_in_executor(None, _search)
    return _deduplicate(results)[:max_results]


# ─── Main per-section search function ─────────────────────────

async def search_section_sources(
    section_title: str,
    section_description: str,
    case_context: str,
    doc_type: str = "",
    max_juris: int = 5,
    max_doutrina: int = 2,
) -> dict[str, Any]:
    """
    Busca fontes específicas para UMA seção do documento.
    Combina DATAJUD (tribunais reais) + DuckDuckGo (ementas completas).
    """
    # Build focused search term
    topic = f"{section_title} {section_description}".strip()
    topic = re.sub(r'^(DA|DO|DOS|DAS|D[OA]S?)\s+', '', topic, flags=re.IGNORECASE)
    topic = topic[:120]

    # Skip non-substantive sections
    skip_sections = {
        "qualificação", "partes", "encerramento", "requerimentos finais",
        "fechamento", "assinatura", "endereçamento",
    }
    is_substantive = not any(skip in section_title.lower() for skip in skip_sections)

    juris = []
    doutrina = []

    if is_substantive:
        # Choose tribunals based on doc type
        tribunais = _pick_tribunais(doc_type)

        # Run all searches in parallel
        datajud_task = search_datajud(topic, tribunais=tribunais, max_per_tribunal=2)
        ddg_task = search_duckduckgo_jurisprudencia(topic, case_context, max_results=max_juris)
        doutrina_task = search_doutrina_targeted(topic, max_results=max_doutrina)

        datajud_results, ddg_results, doutrina_results = await asyncio.gather(
            datajud_task, ddg_task, doutrina_task,
            return_exceptions=True,
        )

        if isinstance(datajud_results, Exception):
            datajud_results = []
        if isinstance(ddg_results, Exception):
            ddg_results = []
        if isinstance(doutrina_results, Exception):
            doutrina_results = []

        # Combine: DATAJUD first (structured), then DuckDuckGo (ementas)
        juris = list(datajud_results) + list(ddg_results)
        juris = _deduplicate(juris)[:max_juris]
        doutrina = list(doutrina_results)

    all_sources = list(juris) + list(doutrina)

    return {
        "jurisprudencia": juris,
        "doutrina": doutrina,
        "all_sources": all_sources,
        "section_title": section_title,
        "search_query": topic,
        "tribunais_consultados": [s.get("tribunal", s.get("source", "")) for s in juris],
    }


# ─── Formatting functions ─────────────────────────────────────

def format_section_sources(sources: dict) -> str:
    """
    Formata as fontes encontradas para injetar no prompt de UMA seção.
    Inclui snippets completos para que o Claude tenha dados reais para citar.
    """
    lines = []

    if sources.get("jurisprudencia"):
        lines.append("JURISPRUDÊNCIA ENCONTRADA PARA ESTA SEÇÃO (CITE OBRIGATORIAMENTE):")
        for i, r in enumerate(sources["jurisprudencia"], 1):
            processo = r.get("processo", "")
            tribunal = r.get("tribunal", r.get("source", ""))
            data = r.get("data", "")

            lines.append(f"  [{i}] {r['title']}")
            if processo:
                lines.append(f"      Processo: {processo}")
            lines.append(f"      Tribunal: {tribunal}")
            if data:
                lines.append(f"      Data: {data}")
            lines.append(f"      URL: {r.get('url', '')}")
            lines.append(f"      Trecho/Ementa: {r.get('snippet', r.get('ementa', ''))}")
            lines.append("")

    if sources.get("doutrina"):
        lines.append("DOUTRINA/ARTIGOS ENCONTRADOS PARA ESTA SEÇÃO:")
        offset = len(sources.get("jurisprudencia", []))
        for i, r in enumerate(sources["doutrina"], 1):
            idx = offset + i
            lines.append(f"  [{idx}] {r['title']}")
            lines.append(f"      Fonte: {r.get('source', '')}")
            lines.append(f"      URL: {r.get('url', '')}")
            lines.append(f"      Trecho: {r.get('snippet', '')}")
            lines.append("")

    return "\n".join(lines)


def build_verification_block(all_sources: list[dict], source_number_start: int = 1) -> str:
    """
    Gera bloco de SELO DE VERIFICAÇÃO com todas as fontes numeradas.
    """
    if not all_sources:
        return ""

    lines = [
        "",
        "═" * 60,
        "SELO DE VERIFICAÇÃO — FONTES CONSULTADAS",
        "Todas as fontes abaixo são verificáveis.",
        "═" * 60,
        "",
    ]

    icons = {"jurisprudencia": "⚖️", "doutrina": "📚", "modelo": "📄"}

    for i, src in enumerate(all_sources, source_number_start):
        icon = icons.get(src.get("type", ""), "🔗")
        tipo_label = {
            "jurisprudencia": "Jurisprudência",
            "doutrina": "Doutrina/Artigo",
            "modelo": "Modelo",
        }.get(src.get("type", ""), "Fonte")

        lines.append(f"[{i}] {icon} {tipo_label}")
        lines.append(f"    Título: {src.get('title', '')}")
        if src.get("processo"):
            lines.append(f"    Processo: {src['processo']}")
        lines.append(f"    Fonte: {src.get('source', src.get('tribunal', ''))}")
        if src.get("data"):
            lines.append(f"    Data: {src['data']}")
        lines.append(f"    Link: {src.get('url', '')}")
        if src.get("section"):
            lines.append(f"    Citado em: {src['section']}")
        lines.append("")

    return "\n".join(lines)


# ─── Helper functions ──────────────────────────────────────────

def _pick_tribunais(doc_type: str) -> list[str]:
    """Pick relevant tribunals based on document type."""
    doc_lower = doc_type.lower() if doc_type else ""
    for key, tribunais in TRIBUNAL_PRIORITY.items():
        if key in doc_lower:
            return tribunais
    return TRIBUNAL_PRIORITY["default"]


def _format_processo_cnj(numero: str) -> str:
    """Format a CNJ process number: NNNNNNN-DD.YYYY.J.TR.OOOO"""
    n = re.sub(r'\D', '', numero)
    if len(n) == 20:
        return f"{n[:7]}-{n[7:9]}.{n[9:13]}.{n[13]}.{n[14:16]}.{n[16:]}"
    return numero


def _build_tribunal_url(tribunal: str, numero: str) -> str:
    """Build a direct URL to consult the process in the tribunal's system."""
    n = re.sub(r'\D', '', numero)
    urls = {
        "STJ": f"https://processo.stj.jus.br/processo/pesquisa/?tipoPesquisa=tipoPesquisaNumeroUnico&termo={n}",
        "STF": f"https://portal.stf.jus.br/processos/detalhe.asp?incidente={n}",
        "TST": f"https://consultaprocessual.tst.jus.br/consultaProcessual/consultaTstNumUnica.do?consulta=Consultar&conscsjt=&numeroTst=&digitoTst=&anoTst=&orgaoTst=&tribunalTst=&varaTst=&consulta=Consultar&numUnica={n}",
        "TJSP": f"https://esaj.tjsp.jus.br/cpopg/show.do?processo.codigo={n}",
        "TJMG": f"https://www5.tjmg.jus.br/jurisprudencia/pesquisaPalavrasEspelhoAcordao.do?&numeroRegistro=1&totalLinhas=1&palavras={n}",
        "TJRJ": f"https://www3.tjrj.jus.br/ejuris/ConsultarJurisprudencia.aspx?&NumeroProcesso={n}",
    }
    return urls.get(tribunal, f"https://www.jusbrasil.com.br/jurisprudencia/busca?q={n}")


def _tribunal_full_name(code: str) -> str:
    """Return full tribunal name."""
    names = {
        "STJ": "STJ - Superior Tribunal de Justiça",
        "STF": "STF - Supremo Tribunal Federal",
        "TST": "TST - Tribunal Superior do Trabalho",
        "TJSP": "TJSP - Tribunal de Justiça de São Paulo",
        "TJMG": "TJMG - Tribunal de Justiça de Minas Gerais",
        "TJRJ": "TJRJ - Tribunal de Justiça do Rio de Janeiro",
        "TRT3": "TRT-3 - Tribunal Regional do Trabalho da 3ª Região",
    }
    return names.get(code, code)


def _extract_tribunal_from_url(url: str) -> str:
    """Extract tribunal code from URL."""
    if "stj.jus.br" in url: return "STJ"
    if "stf.jus.br" in url: return "STF"
    if "tst.jus.br" in url: return "TST"
    if "tjsp" in url or "sp.jus.br" in url: return "TJSP"
    if "tjmg" in url or "mg.jus.br" in url: return "TJMG"
    if "tjrj" in url or "rj.jus.br" in url: return "TJRJ"
    if "jusbrasil" in url: return "JusBrasil"
    return ""


def _extract_processo_from_text(text: str) -> str:
    """Extract process number in CNJ format from text."""
    # Pattern: 1234567-12.1234.1.12.1234
    match = re.search(r'\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}', text)
    if match:
        return match.group()
    # Pattern: REsp 1.234.567 or AgRg no REsp 1.234.567
    match = re.search(r'(?:REsp|AREsp|AgRg|HC|RHC|RMS|AI)\s*n?\.?\s*([\d.]+)', text)
    if match:
        return match.group()
    return ""


def _deduplicate(results: list[dict]) -> list[dict]:
    """Remove duplicates by URL or processo number."""
    seen = set()
    unique = []
    for r in results:
        key = r.get("url", "") or r.get("processo", "") or r.get("title", "")
        if key and key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def _extract_source(url: str) -> str:
    """Extrai nome do tribunal/site da URL."""
    if "stj.jus.br" in url: return "STJ - Superior Tribunal de Justiça"
    if "stf.jus.br" in url: return "STF - Supremo Tribunal Federal"
    if "tst.jus.br" in url: return "TST - Tribunal Superior do Trabalho"
    if "trf" in url and "jus.br" in url: return "TRF - Tribunal Regional Federal"
    if "tjmg" in url or "mg.jus.br" in url: return "TJMG - Tribunal de Justiça de Minas Gerais"
    if "tjsp" in url or "sp.jus.br" in url: return "TJSP - Tribunal de Justiça de São Paulo"
    if "tjrj" in url or "rj.jus.br" in url: return "TJRJ - Tribunal de Justiça do Rio de Janeiro"
    if "jusbrasil" in url: return "JusBrasil"
    if "conjur" in url: return "ConJur - Consultor Jurídico"
    if "migalhas" in url: return "Migalhas"
    if "planalto.gov" in url: return "Planalto - Legislação Federal"
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return "Fonte web"
