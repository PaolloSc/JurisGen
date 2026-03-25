#!/usr/bin/env python3
"""
Script para raspar Súmulas e Orientações Jurisprudenciais do TST
Salva em sumulas_tst.json para uso no JurisGen
"""

import json
import time
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any


def extrair_texto_elemento(elemento) -> str:
    """Extrai texto limpo de um elemento BeautifulSoup"""
    if not elemento:
        return ""
    texto = elemento.get_text(separator=" ", strip=True)
    # Remove múltiplos espaços
    return " ".join(texto.split())


def obter_somatorio_suministros() -> List[Dict[str, Any]]:
    """Obtém o Somatório de Súmulas e Orientações Jurisprudenciais do TST"""
    url = "https://www.tst.jus.br/web/somatorio-de-sumulas-e-orientacoes-jurisprudenciais"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Estrutura típica do portal TST
        # Busca por containers de súmulas
        sumulas = []
        
        # Procurar por divs que contenham súmulas
        # O TST costuma usar classes como 'sumula', 'sumulas', 'sumario', etc.
        containers = soup.find_all(['div', 'section'], class_=True)
        
        for container in containers:
            class_names = container.get('class', [])
            if any(keyword in ' '.join(class_names).lower() for keyword in ['sumula', 'sumulas', 'sumario', 'jurisprudencia']):
                # Procurar itens dentro do container
                itens = container.find_all(['div', 'p', 'li'], recursive=True)
                
                for item in itens:
                    texto = extrair_texto_elemento(item)
                    if len(texto) > 50:  # Filtrar textos muito curtos
                        # Tentar identificar se é uma súmula
                        if any(keyword in texto.lower() for keyword in ['súmula', 'sumula', 'orientação', 'orientacao', 'o.j.']):
                            sumulas.append({
                                "tipo": "Súmula/OJ",
                                "texto": texto,
                                "fonte": "TST - Somatório",
                                "url": url
                            })
        
        return sumulas
        
    except Exception as e:
        print(f"Erro ao obter somatório: {e}")
        return []


def obter_somatorio_suministros_alternativo() -> List[Dict[str, Any]]:
    """Método alternativo para obter súmulas usando scraping mais robusto"""
    url = "https://www.tst.jus.br/web/somatorio-de-sumulas-e-orientacoes-jurisprudenciais"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Buscar por padrões comuns de numeração de súmulas
        sumulas = []
        
        # Padrões de busca
        padroes = [
            r'SÚMULA.*?\d+',
            r'Sumula.*?\d+',
            r'O\.J\..*?\d+',
            r'Orientação Jurisprudencial.*?\d+'
        ]
        
        # Texto completo da página
        texto_pagina = soup.get_text(separator="\n", strip=True)
        
        # Dividir em parágrafos
        paragrafos = [p.strip() for p in texto_pagina.split('\n') if p.strip()]
        
        for paragrafo in paragrafos:
            if len(paragrafo) > 100:  # Texto significativo
                # Verificar se contém padrões de súmula
                if any(padrao.lower() in paragrafo.lower() for padrao in ['súmula', 'sumula', 'o.j.', 'orientação', 'orientacao']):
                    sumulas.append({
                        "tipo": "Súmula/OJ",
                        "texto": paragrafo,
                        "fonte": "TST - Somatório (Alternativo)",
                        "url": url
                    })
        
        return sumulas
        
    except Exception as e:
        print(f"Erro no método alternativo: {e}")
        return []


def obter_somatorio_suministros_completo() -> List[Dict[str, Any]]:
    """Método mais completo para obter súmulas"""
    url = "https://www.tst.jus.br/web/somatorio-de-sumulas-e-orientacoes-jurisprudenciais"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Estratégias de busca
        estrategias = [
            # Buscar por headings que possam conter números de súmulas
            soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']),
            # Buscar por parágrafos com texto significativo
            soup.find_all('p'),
            # Buscar por listas
            soup.find_all(['li', 'dd']),
            # Buscar por divs com classes específicas
            soup.find_all('div', class_=True),
        ]
        
        sumulas = []
        textos_processados = set()
        
        for estrategia in estrategias:
            for elemento in estrategia:
                texto = extrair_texto_elemento(elemento)
                
                # Filtrar textos já processados
                if texto in textos_processados:
                    continue
                textos_processados.add(texto)
                
                # Filtrar textos muito curtos ou irrelevantes
                if len(texto) < 50:
                    continue
                
                # Verificar se contém indícios de ser uma súmula
                palavras_chave = ['súmula', 'sumula', 'o.j.', 'orientação', 'orientacao', 'jurisprudencial']
                if any(palavra in texto.lower() for palavra in palavras_chave):
                    # Verificar se tem número (padrão de súmula)
                    import re
                    if re.search(r'\d{1,3}', texto):
                        sumulas.append({
                            "tipo": "Súmula/OJ",
                            "texto": texto,
                            "fonte": "TST - Somatório Completo",
                            "url": url
                        })
        
        return sumulas
        
    except Exception as e:
        print(f"Erro no método completo: {e}")
        return []


def salvar_sumulas_json(sumulas: List[Dict[str, Any]], filepath: str = "sumulas_tst.json"):
    """Salva a lista de súmulas em arquivo JSON"""
    data = {
        "fonte": "Tribunal Superior do Trabalho (TST)",
        "data_coleta": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_somatorios": len(sumulas),
        "somatorios": sumulas
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ {len(sumulas)} somatórios salvos em {filepath}")


def main():
    """Função principal para executar o scraping"""
    print("🔍 Iniciando scraping de Súmulas e Orientações Jurisprudenciais do TST...")
    
    # Tentar métodos diferentes
    print("📡 Método 1: Scraping estruturado...")
    sumulas_1 = obter_somatorio_suministros()
    
    print("📡 Método 2: Scraping por padrões...")
    sumulas_2 = obter_somatorio_suministros_alternativo()
    
    print("📡 Método 3: Scraping completo...")
    sumulas_3 = obter_somatorio_suministros_completo()
    
    # Combinar resultados
    todas_sumulas = sumulas_1 + sumulas_2 + sumulas_3
    
    # Remover duplicatas
    textos_vistos = set()
    sumulas_unicas = []
    
    for sumula in todas_sumulas:
        texto_limpo = sumula["texto"].lower().strip()
        if texto_limpo not in textos_vistos:
            textos_vistos.add(texto_limpo)
            sumulas_unicas.append(sumula)
    
    # Salvar resultados
    if sumulas_unicas:
        salvar_sumulas_json(sumulas_unicas)
        print(f"🎉 Scraping concluído! {len(sumulas_unicas)} somatórios únicos encontrados.")
    else:
        print("❌ Nenhum somatório encontrado. Verifique a conexão ou a estrutura da página.")
        
        # Salvar arquivo vazio para não quebrar o sistema
        salvar_sumulas_json([])
    
    return sumulas_unicas


if __name__ == "__main__":
    main()