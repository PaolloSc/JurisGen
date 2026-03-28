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
    
    def _extrair_ementa_formatada(self, url_processo: str) -> Optional[Dict[str, str]]:
        """
        Entra na página do processo no JusBrasil e extrai a ementa já formatada
        (equivalente ao botão 'Copiar ementa').
        Retorna dict com 'ementa' (texto formatado) e metadados, ou None se falhar.
        """
        try:
            response = self.session.get(url_processo)
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.content, 'html.parser')

            ementa_text = None
            referencia = None

            # Estratégia 1: Buscar pelo bloco de ementa (data-testid ou classe específica)
            ementa_el = (
                soup.find(attrs={"data-testid": "ementa"})
                or soup.find("div", class_=lambda c: c and "ementa" in c.lower() if c else False)
                or soup.find("section", class_=lambda c: c and "ementa" in c.lower() if c else False)
            )

            if ementa_el:
                ementa_text = ementa_el.get_text(separator='\n', strip=True)

            # Estratégia 2: Buscar pelo texto que começa com "EMENTA:" ou "Ementa:"
            if not ementa_text:
                import re
                all_text = soup.get_text(separator='\n')
                match = re.search(
                    r'(EMENTA\s*:.*?)(?=\n\s*(?:ACÓRDÃO|RELATÓRIO|VOTO|Vistos,|Isto posto|Ante o exposto|DECISÃO))',
                    all_text,
                    re.DOTALL | re.IGNORECASE
                )
                if match:
                    ementa_text = match.group(1).strip()

            # Estratégia 3: Buscar dentro de elementos com texto "EMENTA"
            if not ementa_text:
                for tag in soup.find_all(['p', 'div', 'span']):
                    tag_text = tag.get_text(strip=True)
                    if tag_text.upper().startswith("EMENTA:") or tag_text.upper().startswith("EMENTA "):
                        ementa_text = tag.get_text(separator='\n', strip=True)
                        # Pegar também os irmãos seguintes até encontrar outro heading
                        for sibling in tag.find_next_siblings():
                            sib_text = sibling.get_text(strip=True).upper()
                            if any(sib_text.startswith(kw) for kw in ["ACÓRDÃO", "RELATÓRIO", "VOTO", "DECISÃO"]):
                                break
                            ementa_text += '\n' + sibling.get_text(separator='\n', strip=True)
                        break

            # Extrair referência/citação (tribunal, relator, data, publicação)
            ref_el = (
                soup.find(attrs={"data-testid": "document-header"})
                or soup.find("header")
            )
            if ref_el:
                referencia = ref_el.get_text(separator=' ', strip=True)

            # Extrair metadados da página
            titulo_el = soup.find('h1') or soup.find('title')
            titulo = titulo_el.get_text(strip=True) if titulo_el else ""

            # Buscar dados estruturados (relator, órgão julgador, data)
            metadados = {}
            for label_text in ["Relator", "Órgão julgador", "Órgão Julgador", "Data de julgamento",
                               "Data de publicação", "Tipo", "Número"]:
                label_el = soup.find(string=lambda s: s and label_text.lower() in s.lower() if s else False)
                if label_el:
                    parent = label_el.find_parent()
                    if parent:
                        value = parent.find_next_sibling()
                        if value:
                            metadados[label_text.lower()] = value.get_text(strip=True)

            if ementa_text and len(ementa_text) > 50:
                return {
                    "ementa": ementa_text,
                    "referencia": referencia,
                    "titulo": titulo,
                    "metadados": metadados,
                }

            return None

        except Exception as e:
            print(f"⚠️ Erro ao extrair ementa de {url_processo}: {e}")
            return None

    def buscar_jurisprudencia(self, termo_busca: str, tribunal: str = "TST", limite: int = 10) -> List[Dict[str, Any]]:
        """Busca jurisprudência no JusBrasil, entrando em cada resultado para extrair a ementa formatada"""
        resultados = []

        try:
            # URL focada em jurisprudência do JusBrasil
            search_url = f"{self.base_url}/jurisprudencia/busca"
            params = {
                'q': termo_busca
            }
            if tribunal:
                params['q'] = f"{termo_busca} {tribunal}"

            response = self.session.get(search_url, params=params)

            if response.status_code != 200:
                print(f"❌ Falha ao buscar jurisprudência: {response.status_code}")
                return resultados

            soup = BeautifulSoup(response.content, 'html.parser')

            # Extrair links dos resultados para navegar até cada processo
            links_processos = []
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                # Links de jurisprudência no JusBrasil seguem padrão /jurisprudencia/...
                if '/jurisprudencia/' in href and href not in [link for link, _ in links_processos]:
                    # Ignorar links de busca/navegação
                    if '/busca' in href or '/filtros' in href:
                        continue
                    full_url = href if href.startswith('http') else f"{self.base_url}{href}"
                    titulo = a_tag.get_text(strip=True)
                    if len(titulo) > 10:
                        links_processos.append((full_url, titulo))

            # Deduplica por URL
            seen_urls = set()
            links_unicos = []
            for url, titulo in links_processos:
                # Normalizar URL removendo query params
                url_base = url.split('?')[0]
                if url_base not in seen_urls:
                    seen_urls.add(url_base)
                    links_unicos.append((url, titulo))

            print(f"📋 Encontrados {len(links_unicos)} resultados. Extraindo ementas em paralelo...")

            # Extrair ementas em paralelo com ThreadPool para velocidade
            from concurrent.futures import ThreadPoolExecutor, as_completed

            links_para_extrair = links_unicos[:limite]

            def _extrair_com_titulo(args):
                url, titulo = args
                return titulo, url, self._extrair_ementa_formatada(url)

            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(_extrair_com_titulo, item): item for item in links_para_extrair}
                for future in as_completed(futures):
                    try:
                        titulo, url_processo, ementa_data = future.result()
                    except Exception:
                        continue

                    if ementa_data:
                        meta = ementa_data.get("metadados", {})
                        ref_parts = []
                        if meta.get("número"):
                            ref_parts.append(meta["número"])
                        if meta.get("relator"):
                            ref_parts.append(f"Relator(a): {meta['relator']}")
                        if meta.get("órgão julgador"):
                            ref_parts.append(meta["órgão julgador"])
                        if meta.get("data de julgamento"):
                            ref_parts.append(f"julgado em {meta['data de julgamento']}")
                        if meta.get("data de publicação"):
                            ref_parts.append(f"PUBLIC {meta['data de publicação']}")

                        referencia_formatada = ", ".join(ref_parts) if ref_parts else ementa_data.get("referencia", "")

                        resultados.append({
                            "tipo": "Jurisprudência/Súmula",
                            "texto": ementa_data["ementa"],
                            "ementa": ementa_data["ementa"],
                            "referencia_formatada": f"({referencia_formatada})",
                            "titulo": ementa_data.get("titulo", titulo),
                            "fonte": "JusBrasil",
                            "url": url_processo,
                            "data_busca": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "tribunal": tribunal,
                            "termo_busca": termo_busca
                        })
                        print(f"  ✅ Ementa extraída: {titulo[:60]}...")
                    else:
                        # Fallback: usar texto do resultado da busca
                        resultados.append({
                            "tipo": "Jurisprudência/Súmula",
                            "texto": titulo,
                            "fonte": "JusBrasil - Search",
                            "url": url_processo,
                            "data_busca": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "tribunal": tribunal,
                            "termo_busca": termo_busca
                        })
                        print(f"  ⚠️ Fallback (sem ementa): {titulo[:60]}...")

            print(f"✅ {len(resultados)} jurisprudências processadas")
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