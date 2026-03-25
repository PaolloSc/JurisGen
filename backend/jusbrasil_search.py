#!/usr/bin/env python3
"""
Integração com JusBrasil para busca de jurisprudência
Complemento para o modelo LLM no JurisGen
"""

import json
import time
from curl_cffi import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
import os
from dotenv import load_dotenv

load_dotenv()

class JusBrasilSearch:
    """Busca de jurisprudência no JusBrasil"""
    
    def __init__(self):
        self.session = requests.Session(impersonate="chrome110")
        self.base_url = "https://www.jusbrasil.com.br"
        # Sem headers malucos para evitar flags do CloudFlare com curl_cffi
    
    def login(self, email: str, password: str) -> bool:
        """Realiza login no JusBrasil"""
        try:
            # Primeiro, obter a página de login para capturar tokens CSRF
            login_page_url = f"{self.base_url}/login"
            response = self.session.get(login_page_url)
            
            if response.status_code != 200:
                print(f"❌ Falha ao acessar página de login: {response.status_code}")
                return False
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Procurar por tokens CSRF
            csrf_token = None
            csrf_input = soup.find('input', {'name': '_csrf'})
            if csrf_input:
                csrf_token = csrf_input.get('value')
            
            # Dados do formulário de login
            login_data = {
                'email': email,
                'password': password,
            }
            
            if csrf_token:
                login_data['_csrf'] = csrf_token
            
            # Realizar login
            login_url = f"{self.base_url}/login"
            response = self.session.post(login_url, data=login_data)
            
            # Verificar se o login foi bem-sucedido
            if response.status_code == 200:
                # Verificar se há redirecionamento ou se ainda está na página de login
                if 'login' in response.url and 'error' not in response.url:
                    print("✅ Login realizado com sucesso!")
                    return True
                else:
                    print("❌ Login falhou - verifique suas credenciais")
                    return False
            else:
                print(f"❌ Erro no login: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Erro ao realizar login: {e}")
            return False
    
    def buscar_jurisprudencia(self, termo_busca: str, tribunal: str = "TST", limite: int = 10) -> List[Dict[str, Any]]:
        """Busca jurisprudência no JusBrasil"""
        resultados = []
        
        try:
            # URL focada em jurisprudência do JusBrasil
            search_url = f"{self.base_url}/jurisprudencia/busca"
            params = {
                'q': termo_busca
            }
            if tribunal:
                search_url = f"{self.base_url}/jurisprudencia/busca" # tribunal could be used via params generally or url part, let's keep simple query
                params['q'] = f"{termo_busca} {tribunal}"
            
            response = self.session.get(search_url, params=params)
            
            if response.status_code != 200:
                print(f"❌ Falha ao buscar jurisprudência: {response.status_code}")
                return resultados
            
            soup = BeautifulSoup(response.content, 'html.parser')
            artigos = soup.find_all('article')
            
            for artigo in artigos[:limite]:
                # Recuperar Ementa e informações processuais, limpando botões extras e formatos de leitura com o 'separator'
                texto_limpo = artigo.get_text(separator=' ', strip=True)
                texto_limpo = texto_limpo.replace('Mostrar mais', '').replace('Mostrar data de publicação', '')
                
                # Se for muito pequeno, talvez não seja ementa
                if len(texto_limpo) < 50:
                    continue
                
                resultados.append({
                    "tipo": "Jurisprudência/Súmula",
                    "texto": texto_limpo,
                    "fonte": f"JusBrasil - Search",
                    "url": response.url,
                    "data_busca": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "tribunal": tribunal,
                    "termo_busca": termo_busca
                })
            
            return resultados
            
        except Exception as e:
            print(f"❌ Erro ao buscar jurisprudência: {e}")
            return resultados
    
    def buscar_sumulas(self, termo_busca: str = "Súmulas TST", limite: int = 20) -> List[Dict[str, Any]]:
        """Busca súmulas no JusBrasil"""
        sumulas = []
        
        try:
            # URL de busca no JusBrasil
            search_url = f"{self.base_url}/busca"
            params = {
                'q': termo_busca,
                'type': 'jurisprudence',
                'court': 'tst',
                'page': 1
            }
            
            response = self.session.get(search_url, params=params)
            
            if response.status_code != 200:
                print(f"❌ Falha ao buscar súmulas: {response.status_code}")
                return sumulas
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Estratégias de busca para súmulas no JusBrasil
            estrategias = [
                # Buscar por containers de resultados
                soup.find_all(['div', 'article'], class_=True),
                # Buscar por links de súmulas
                soup.find_all('a', href=True),
                # Buscar por textos específicos
                soup.find_all(['p', 'span', 'h1', 'h2', 'h3']),
            ]
            
            textos_processados = set()
            contador = 0
            
            for estrategia in estrategias:
                if contador >= limite:
                    break
                    
                for elemento in estrategia:
                    if contador >= limite:
                        break
                        
                    texto = self.extrair_texto_elemento(elemento)
                    
                    # Filtrar textos já processados
                    if texto in textos_processados:
                        continue
                    textos_processados.add(texto)
                    
                    # Filtrar textos muito curtos
                    if len(texto) < 50:
                        continue
                    
                    # Verificar se contém indícios de ser uma súmula
                    palavras_chave = ['súmula', 'sumula', 'o.j.', 'orientação', 'orientacao', 'jurisprudencial', 'tst']
                    if any(palavra in texto.lower() for palavra in palavras_chave):
                        # Verificar se tem número (padrão de súmula)
                        import re
                        if re.search(r'\d{1,3}', texto):
                            sumulas.append({
                                "tipo": "Súmula/OJ",
                                "texto": texto,
                                "fonte": "JusBrasil",
                                "url": response.url,
                                "data_busca": time.strftime("%Y-%m-%d %H:%M:%S"),
                                "termo_busca": termo_busca
                            })
                            contador += 1
            
            return sumulas
            
        except Exception as e:
            print(f"❌ Erro ao buscar súmulas: {e}")
            return sumulas
    
    def extrair_texto_elemento(self, elemento) -> str:
        """Extrai texto limpo de um elemento BeautifulSoup"""
        if not elemento:
            return ""
        texto = elemento.get_text(separator=" ", strip=True)
        return " ".join(texto.split())
    
    def salvar_resultados_json(self, resultados: List[Dict[str, Any]], filepath: str = "jusbrasil_resultados.json"):
        """Salva os resultados da busca em arquivo JSON"""
        data = {
            "fonte": "JusBrasil",
            "data_coleta": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_resultados": len(resultados),
            "resultados": resultados
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ {len(resultados)} resultados salvos em {filepath}")
    
    def buscar_completa(self, termo_busca: str, tribunal: str = "TST", limite: int = 15) -> List[Dict[str, Any]]:
        """Busca completa: jurisprudência + súmulas"""
        # Buscar jurisprudência
        jurisprudencia = self.buscar_jurisprudencia(termo_busca, tribunal, limite)
        
        # Buscar súmulas
        sumulas = self.buscar_sumulas(f"{termo_busca} {tribunal}", limite // 2)
        
        # Combinar resultados
        todos_resultados = jurisprudencia + sumulas
        
        # Remover duplicatas
        textos_vistos = set()
        resultados_unicos = []
        
        for resultado in todos_resultados:
            texto_limpo = resultado["texto"].lower().strip()
            if texto_limpo not in textos_vistos:
                textos_vistos.add(texto_limpo)
                resultados_unicos.append(resultado)
        
        return resultados_unicos


def main():
    """Função principal para teste"""
    print("🔍 Iniciando busca no JusBrasil...")
    
    # Credenciais do JusBrasil (substitua com suas credenciais reais)
    email = os.getenv("JUSBRASIL_EMAIL", "")
    password = os.getenv("JUSBRASIL_PASSWORD", "")
    
    if not email or not password:
        print("❌ Credenciais do JusBrasil não configuradas no .env")
        return
    
    # Inicializar busca
    busca = JusBrasilSearch()
    
    # Realizar login
    if not busca.login(email, password):
        print("❌ Falha no login. Verifique suas credenciais.")
        return
    
    # Buscar jurisprudência
    termo_busca = "horas extras intervalo intrajornada"
    print(f"📡 Buscando jurisprudência sobre: {termo_busca}")
    
    resultados = busca.buscar_completa(termo_busca, "TST", 10)
    
    # Salvar resultados
    if resultados:
        busca.salvar_resultados_json(resultados, "jusbrasil_busca_tst.json")
        print(f"🎉 Busca concluída! {len(resultados)} resultados encontrados.")
    else:
        print("❌ Nenhum resultado encontrado.")
        # Salvar arquivo vazio para não quebrar o sistema
        busca.salvar_resultados_json([])


if __name__ == "__main__":
    main()