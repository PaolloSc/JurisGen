"""
Pesquisa jurídica real: jurisprudência, doutrina e modelos.
Retorna resultados com fontes verificáveis (URL, tribunal, data).
"""

import asyncio
from typing import Any


async def search_jurisprudencia(tema: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Busca jurisprudência real em tribunais brasileiros via web."""
    from duckduckgo_search import DDGS

    queries = [
        f'site:stj.jus.br jurisprudencia "{tema}"',
        f'site:stf.jus.br jurisprudencia "{tema}"',
        f'site:tst.jus.br jurisprudencia "{tema}"',
        f'site:jusbrasil.com.br jurisprudencia "{tema}"',
    ]

    results = []
    loop = asyncio.get_running_loop()

    def _search():
        found = []
        with DDGS() as ddgs:
            for query in queries:
                try:
                    hits = list(ddgs.text(query, max_results=2))
                    for hit in hits:
                        found.append({
                            "type": "jurisprudencia",
                            "title": hit.get("title", ""),
                            "url": hit.get("href", ""),
                            "snippet": hit.get("body", ""),
                            "source": _extract_source(hit.get("href", "")),
                        })
                except Exception:
                    continue
        return found

    results = await loop.run_in_executor(None, _search)
    # Deduplicate by URL
    seen = set()
    unique = []
    for r in results:
        if r["url"] not in seen:
            seen.add(r["url"])
            unique.append(r)
    return unique[:max_results]


async def search_doutrina(tema: str, max_results: int = 3) -> list[dict[str, Any]]:
    """Busca doutrina e artigos jurídicos."""
    from duckduckgo_search import DDGS

    queries = [
        f'doutrina "{tema}" direito brasileiro artigo',
        f'site:conjur.com.br "{tema}"',
        f'site:migalhas.com.br "{tema}"',
    ]

    results = []
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
    seen = set()
    unique = []
    for r in results:
        if r["url"] not in seen:
            seen.add(r["url"])
            unique.append(r)
    return unique[:max_results]


async def search_modelos(tipo_documento: str, max_results: int = 3) -> list[dict[str, Any]]:
    """Busca modelos de peças jurídicas."""
    from duckduckgo_search import DDGS

    queries = [
        f'modelo "{tipo_documento}" petição minuta',
        f'site:jusbrasil.com.br modelo "{tipo_documento}"',
    ]

    results = []
    loop = asyncio.get_running_loop()

    def _search():
        found = []
        with DDGS() as ddgs:
            for query in queries:
                try:
                    hits = list(ddgs.text(query, max_results=2))
                    for hit in hits:
                        found.append({
                            "type": "modelo",
                            "title": hit.get("title", ""),
                            "url": hit.get("href", ""),
                            "snippet": hit.get("body", ""),
                            "source": _extract_source(hit.get("href", "")),
                        })
                except Exception:
                    continue
        return found

    results = await loop.run_in_executor(None, _search)
    seen = set()
    unique = []
    for r in results:
        if r["url"] not in seen:
            seen.add(r["url"])
            unique.append(r)
    return unique[:max_results]


async def pesquisar_tudo(tema: str, tipo_documento: str) -> dict[str, Any]:
    """Executa todas as pesquisas em paralelo e retorna resultados consolidados."""
    juris_task = search_jurisprudencia(tema)
    doutrina_task = search_doutrina(tema)
    modelos_task = search_modelos(tipo_documento)

    jurisprudencia, doutrina, modelos = await asyncio.gather(
        juris_task, doutrina_task, modelos_task,
        return_exceptions=True,
    )

    # Handle exceptions gracefully
    if isinstance(jurisprudencia, Exception):
        jurisprudencia = []
    if isinstance(doutrina, Exception):
        doutrina = []
    if isinstance(modelos, Exception):
        modelos = []

    all_sources = []
    all_sources.extend(jurisprudencia)
    all_sources.extend(doutrina)
    all_sources.extend(modelos)

    return {
        "jurisprudencia": jurisprudencia,
        "doutrina": doutrina,
        "modelos": modelos,
        "all_sources": all_sources,
        "total": len(all_sources),
    }


def format_sources_for_prompt(research: dict) -> str:
    """Formata os resultados de pesquisa para incluir no prompt do Claude."""
    lines = []

    if research.get("jurisprudencia"):
        lines.append("=== JURISPRUDÊNCIA ENCONTRADA ===")
        for r in research["jurisprudencia"]:
            lines.append(f"- [{r['source']}] {r['title']}")
            lines.append(f"  URL: {r['url']}")
            lines.append(f"  Trecho: {r['snippet'][:200]}")
            lines.append("")

    if research.get("doutrina"):
        lines.append("=== DOUTRINA E ARTIGOS ===")
        for r in research["doutrina"]:
            lines.append(f"- [{r['source']}] {r['title']}")
            lines.append(f"  URL: {r['url']}")
            lines.append(f"  Trecho: {r['snippet'][:200]}")
            lines.append("")

    if research.get("modelos"):
        lines.append("=== MODELOS DE REFERÊNCIA ===")
        for r in research["modelos"]:
            lines.append(f"- [{r['source']}] {r['title']}")
            lines.append(f"  URL: {r['url']}")
            lines.append("")

    return "\n".join(lines)


def format_sources_for_document(research: dict) -> str:
    """Gera bloco de fontes verificáveis para incluir no final do documento."""
    lines = ["", "═" * 60, "FONTES CONSULTADAS (verificáveis)", "═" * 60, ""]

    for i, src in enumerate(research.get("all_sources", []), 1):
        icon = {"jurisprudencia": "⚖️", "doutrina": "📚", "modelo": "📄"}.get(src["type"], "🔗")
        lines.append(f"[{i}] {icon} {src['title']}")
        lines.append(f"    Fonte: {src['source']}")
        lines.append(f"    Link: {src['url']}")
        lines.append("")

    return "\n".join(lines)


def _extract_source(url: str) -> str:
    """Extrai nome do tribunal/site da URL."""
    if "stj.jus.br" in url:
        return "STJ - Superior Tribunal de Justiça"
    if "stf.jus.br" in url:
        return "STF - Supremo Tribunal Federal"
    if "tst.jus.br" in url:
        return "TST - Tribunal Superior do Trabalho"
    if "trf" in url and "jus.br" in url:
        return "TRF - Tribunal Regional Federal"
    if "tjmg" in url or "mg.jus.br" in url:
        return "TJMG - Tribunal de Justiça de Minas Gerais"
    if "tjsp" in url or "sp.jus.br" in url:
        return "TJSP - Tribunal de Justiça de São Paulo"
    if "jusbrasil" in url:
        return "JusBrasil"
    if "conjur" in url:
        return "ConJur - Consultor Jurídico"
    if "migalhas" in url:
        return "Migalhas"
    if "planalto.gov" in url:
        return "Planalto - Legislação Federal"
    # Generic
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.replace("www.", "")
        return domain
    except Exception:
        return "Fonte web"
