"""
Cliente MNI (Modelo Nacional de Interoperabilidade) para o PJe.

Fala SOAP diretamente com o endpoint `intercomunicacao` do tribunal — sem
intermediários. As credenciais do PJe (CPF/senha do advogado) saem daqui
direto para o tribunal e não trafegam por serviço de terceiro.

Operação usada: `consultarProcesso` do MNI 2.2.2 (a mesma que o Escritório
Digital do CNJ consome). O parsing é agnóstico de namespace, então funciona
também com tribunais em 2.2 ou 3.0.

Configuração (.env):
    PJE_CPF, PJE_SENHA        credenciais padrão (opcionais; podem vir por header)
    PJE_MNI_ENDPOINTS         JSON com endpoints por tribunal (ver resolver_endpoint)
    PJE_MNI_TIMEOUT           timeout em segundos (padrão: 120)
"""

from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

import httpx

# ─── Namespaces MNI ───────────────────────────────────────────
# Confirmados no WSDL de produção do TJCE (pje1grau/intercomunicacao?wsdl).
# O envelope da operação é `{servico}consultarProcesso`, mas os parâmetros são
# declarados com form="qualified" no namespace `{tipos}` — mandar os filhos sem
# prefixo faz o JAX-WS do tribunal desserializar tudo como nulo.
NS_SERVICO_PADRAO = "http://www.cnj.jus.br/servico-intercomunicacao-2.2.2/"
NS_TIPOS_PADRAO = "http://www.cnj.jus.br/tipos-servico-intercomunicacao-2.2.2"
NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
NS_WSDL = "http://schemas.xmlsoap.org/wsdl/"
NS_WSDL_SOAP = "http://schemas.xmlsoap.org/wsdl/soap/"
NS_XSD = "http://www.w3.org/2001/XMLSchema"

DEFAULT_TIMEOUT = float(os.getenv("PJE_MNI_TIMEOUT", "120"))

# Alguns tribunais filtram na borda quem não parece navegador — o TJMG devolve
# 426 Upgrade Required sem User-Agent e 302 com ele.
USER_AGENT = os.getenv(
    "PJE_MNI_USER_AGENT",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36",
)


class MNIError(Exception):
    """Falha ao falar com o MNI do tribunal (rede, SOAP Fault ou sucesso=false)."""

    def __init__(self, mensagem: str, *, status: int = 502, detalhe: str = ""):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status = status
        self.detalhe = detalhe


# ─── Número CNJ (Resolução CNJ 65/2008) ───────────────────────
# NNNNNNN-DD.AAAA.J.TR.OOOO
SEGMENTOS = {
    "1": "STF",
    "2": "CNJ",
    "3": "STJ",
    "4": "Justiça Federal",
    "5": "Justiça do Trabalho",
    "6": "Justiça Eleitoral",
    "7": "Justiça Militar da União",
    "8": "Justiça Estadual",
    "9": "Justiça Militar Estadual",
}

# Código TR → UF na Justiça Estadual (J=8) e Eleitoral (J=6)
UF_POR_CODIGO = {
    "01": "AC", "02": "AL", "03": "AP", "04": "AM", "05": "BA", "06": "CE",
    "07": "DFT", "08": "ES", "09": "GO", "10": "MA", "11": "MT", "12": "MS",
    "13": "MG", "14": "PA", "15": "PB", "16": "PR", "17": "PE", "18": "PI",
    "19": "RJ", "20": "RN", "21": "RS", "22": "RO", "23": "RR", "24": "SC",
    "25": "SE", "26": "SP", "27": "TO",
}


@dataclass
class NumeroCNJ:
    """Número único de processo decomposto nos campos da Resolução 65/2008."""

    digitos: str
    sequencial: str
    digito_verificador: str
    ano: str
    segmento: str
    codigo_tribunal: str
    origem: str
    sigla: str
    segmento_nome: str

    @property
    def formatado(self) -> str:
        return (
            f"{self.sequencial}-{self.digito_verificador}.{self.ano}."
            f"{self.segmento}.{self.codigo_tribunal}.{self.origem}"
        )

    @property
    def digito_valido(self) -> bool:
        """Confere o DV módulo 97 base 10 (ISO 7064 / MOD 97-10)."""
        base = (
            self.sequencial + self.ano + self.segmento
            + self.codigo_tribunal + self.origem
        )
        return 98 - (int(base) * 100) % 97 == int(self.digito_verificador)

    def to_dict(self) -> dict[str, Any]:
        return {
            "numero": self.formatado,
            "digitos": self.digitos,
            "ano": self.ano,
            "segmento": self.segmento,
            "segmentoNome": self.segmento_nome,
            "tribunal": self.sigla,
            "codigoTribunal": self.codigo_tribunal,
            "origem": self.origem,
            "digitoValido": self.digito_valido,
        }


def _sigla_tribunal(segmento: str, codigo: str) -> str:
    if segmento == "4":
        return f"TRF{int(codigo)}"
    if segmento == "5":
        return f"TRT{int(codigo)}"
    if segmento == "6":
        return f"TRE{UF_POR_CODIGO.get(codigo, codigo)}"
    if segmento == "8":
        return f"TJ{UF_POR_CODIGO.get(codigo, codigo)}"
    if segmento == "9":
        return f"TJM{UF_POR_CODIGO.get(codigo, codigo)}"
    if segmento == "7":
        return "CJM"
    return SEGMENTOS.get(segmento, f"J{segmento}-{codigo}")


def parse_numero_cnj(numero: str) -> NumeroCNJ:
    """Aceita o número com ou sem máscara e devolve os campos decompostos."""
    digitos = re.sub(r"\D", "", numero or "")
    if len(digitos) != 20:
        raise MNIError(
            f"Número de processo inválido: esperados 20 dígitos, recebidos {len(digitos)}.",
            status=400,
            detalhe="Formato CNJ: NNNNNNN-DD.AAAA.J.TR.OOOO",
        )
    segmento = digitos[13]
    codigo_tribunal = digitos[14:16]
    return NumeroCNJ(
        digitos=digitos,
        sequencial=digitos[0:7],
        digito_verificador=digitos[7:9],
        ano=digitos[9:13],
        segmento=segmento,
        codigo_tribunal=codigo_tribunal,
        origem=digitos[16:20],
        sigla=_sigla_tribunal(segmento, codigo_tribunal),
        segmento_nome=SEGMENTOS.get(segmento, "desconhecido"),
    )


def cpf_valido(cpf: str) -> bool:
    """Confere os dois dígitos verificadores do CPF."""
    d = [int(c) for c in re.sub(r"\D", "", cpf or "")]
    if len(d) != 11 or len(set(d)) == 1:
        return False
    for pos in (9, 10):
        soma = sum(d[i] * (pos + 1 - i) for i in range(pos))
        digito = 0 if soma % 11 < 2 else 11 - soma % 11
        if digito != d[pos]:
            return False
    return True


# ─── Resolução de endpoint ────────────────────────────────────
# Cada tribunal publica o MNI em um caminho próprio e não existe lista oficial
# consolidada — por isso o mapa abaixo traz apenas *candidatos* pelo padrão mais
# comum. O caminho confiável é declarar o endpoint verificado em
# PJE_MNI_ENDPOINTS, que tem precedência sobre qualquer candidato.
#
#   PJE_MNI_ENDPOINTS='{"TJCE": {"1": "https://pje.tjce.jus.br/pje1grau/intercomunicacao",
#                                "2": "https://pje.tjce.jus.br/pje2grau/intercomunicacao"},
#                       "TRT3": "https://pje.trt3.jus.br/pje/intercomunicacao"}'
CAMINHOS_CANDIDATOS = (
    "pje{grau}grau/intercomunicacao",
    "pje{grau}g/intercomunicacao",
    "pje/intercomunicacao",
)

# URLs cujo WSDL respondeu em varredura de 2026-09-05 (57 tribunais testados,
# 6 responderam). São só o ponto de partida: o endereço efetivo de chamada vem
# do <soap:address> do próprio WSDL, que em vários tribunais aponta para outro
# host — TJCE atende em pjews.tjce.jus.br, TJPE em pje.cloud.tjpe.jus.br,
# TRF5 em /pjemni/. Responder ao WSDL não garante que a consulta funcione.
ENDPOINTS_VERIFICADOS: dict[str, dict[str, str]] = {
    "TJCE": {
        "1": "https://pje.tjce.jus.br/pje1grau/intercomunicacao",
        "2": "https://pje.tjce.jus.br/pje2grau/intercomunicacao",
    },
    "TJMT": {"*": "https://pje.tjmt.jus.br/pje/intercomunicacao"},
    "TJPA": {"*": "https://pje.tjpa.jus.br/pje/intercomunicacao"},
    "TJPE": {
        "1": "https://pje.tjpe.jus.br/pje/intercomunicacao",
        "2": "https://pje.tjpe.jus.br/pje2g/intercomunicacao",
    },
    "TJRR": {"*": "https://pje.tjrr.jus.br/pje/intercomunicacao"},
    "TRF5": {"*": "https://pje.trf5.jus.br/pje/intercomunicacao"},
}


def _endpoints_configurados() -> dict[str, Any]:
    bruto = os.getenv("PJE_MNI_ENDPOINTS", "").strip()
    if not bruto:
        return {}
    try:
        return {str(k).upper(): v for k, v in json.loads(bruto).items()}
    except (json.JSONDecodeError, AttributeError) as exc:
        raise MNIError(
            "PJE_MNI_ENDPOINTS não é um JSON válido de tribunal → endpoint.",
            status=500,
            detalhe=str(exc),
        ) from exc


def _do_mapa(mapa: dict[str, Any], sigla: str, grau: str) -> Optional[str]:
    entrada = mapa.get(sigla)
    if isinstance(entrada, str):
        return entrada
    if isinstance(entrada, dict):
        return entrada.get(str(grau)) or entrada.get("*")
    return None


def candidatos_endpoint(num: NumeroCNJ, grau: str = "1") -> list[str]:
    """Endpoints prováveis do MNI para o tribunal do processo, em ordem de tentativa.

    Precedência: PJE_MNI_ENDPOINTS (o que o usuário confirmou com o tribunal),
    depois as URLs já verificadas, depois os caminhos genéricos.
    """
    configurado = _do_mapa(_endpoints_configurados(), num.sigla, grau)
    if configurado:
        return [configurado]

    candidatos = []
    verificado = _do_mapa(ENDPOINTS_VERIFICADOS, num.sigla, grau)
    if verificado:
        candidatos.append(verificado)

    base = f"https://pje.{num.sigla.lower()}.jus.br/"
    candidatos += [
        url
        for c in CAMINHOS_CANDIDATOS
        if (url := base + c.format(grau=grau)) not in candidatos
    ]
    return candidatos


def resolver_endpoint(numero: str, grau: str = "1") -> str:
    """Endpoint a usar para o processo (o primeiro candidato, se não houver config)."""
    return candidatos_endpoint(parse_numero_cnj(numero), grau)[0]


# ─── Helpers de XML (agnósticos de namespace) ─────────────────
def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _filhos(el: Optional[ET.Element], nome: str) -> list[ET.Element]:
    if el is None:
        return []
    return [c for c in el if _local(c.tag) == nome]


def _filho(el: Optional[ET.Element], nome: str) -> Optional[ET.Element]:
    filhos = _filhos(el, nome)
    return filhos[0] if filhos else None


def _busca(el: Optional[ET.Element], nome: str) -> Optional[ET.Element]:
    if el is None:
        return None
    for node in el.iter():
        if _local(node.tag) == nome:
            return node
    return None


def _attr(el: Optional[ET.Element], *nomes: str, padrao: str = "") -> str:
    """Lê um atributo; se não existir, tenta o elemento filho de mesmo nome."""
    if el is None:
        return padrao
    for nome in nomes:
        if nome in el.attrib:
            return el.attrib[nome]
        filho = _filho(el, nome)
        if filho is not None and (filho.text or "").strip():
            return filho.text.strip()
    return padrao


async def _get_com_retry(
    client: httpx.AsyncClient, url: str, tentativas: int = 2
) -> httpx.Response:
    """GET tolerante a reset de conexão — o PJe derruba a primeira conexão às vezes."""
    erro: Optional[httpx.HTTPError] = None
    for _ in range(tentativas):
        try:
            return await client.get(url)
        except httpx.TransportError as exc:
            erro = exc
    raise erro if erro else httpx.HTTPError("falha desconhecida no GET")


# ─── Contrato do serviço, lido do WSDL do tribunal ────────────
@dataclass
class ServicoMNI:
    """O que o WSDL do tribunal diz sobre como falar com ele."""

    wsdl: str
    endpoint: str
    ns_servico: str = NS_SERVICO_PADRAO
    ns_tipos: str = NS_TIPOS_PADRAO
    soap_action: str = ""
    operacoes: list[str] = field(default_factory=list)

    @classmethod
    def presumido(cls, url: str) -> "ServicoMNI":
        """Contrato assumido quando o WSDL não está acessível."""
        return cls(
            wsdl=f"{url}?wsdl",
            endpoint=url,
            soap_action=f"{NS_SERVICO_PADRAO}consultarProcesso",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "wsdl": self.wsdl,
            "endpoint": self.endpoint,
            "namespace": self.ns_servico,
            "namespaceTipos": self.ns_tipos,
            "soapAction": self.soap_action,
            "operacoes": self.operacoes,
        }


def analisar_wsdl(conteudo: bytes, url: str) -> ServicoMNI:
    """Extrai do WSDL o endereço real do serviço, os namespaces e o SOAPAction.

    O endereço importa: o TJCE, por exemplo, publica o WSDL em `pje.tjce.jus.br`
    mas atende as chamadas em `pjews.tjce.jus.br`.
    """
    raiz = ET.fromstring(conteudo)
    servico = ServicoMNI.presumido(url)
    servico.wsdl = f"{url}?wsdl"
    servico.ns_servico = raiz.get("targetNamespace") or NS_SERVICO_PADRAO

    for schema in raiz.iter(f"{{{NS_XSD}}}schema"):
        alvo = schema.get("targetNamespace")
        if alvo and any(c.get("name") == "tipoConsultarProcesso" for c in schema):
            servico.ns_tipos = alvo
            break

    for endereco in raiz.iter(f"{{{NS_WSDL_SOAP}}}address"):
        if endereco.get("location"):
            servico.endpoint = endereco.get("location", url)
            break

    servico.soap_action = f"{servico.ns_servico}consultarProcesso"
    for binding in raiz.iter(f"{{{NS_WSDL}}}binding"):
        for operacao in binding:
            nome = operacao.get("name") or ""
            if _local(operacao.tag) != "operation" or not nome:
                continue
            if nome not in servico.operacoes:
                servico.operacoes.append(nome)
            if nome != "consultarProcesso":
                continue
            for filho in operacao:
                if _local(filho.tag) == "operation" and filho.get("soapAction"):
                    servico.soap_action = filho.get("soapAction", "")
    return servico


# ─── Cliente ──────────────────────────────────────────────────
@dataclass
class MNIClient:
    """Cliente do webservice `intercomunicacao` (MNI) de um tribunal PJe."""

    cpf: str
    senha: str
    endpoint: Optional[str] = None
    timeout: float = DEFAULT_TIMEOUT
    namespace: str = NS_SERVICO_PADRAO
    verify_ssl: bool = True
    _servicos: dict[str, ServicoMNI] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self.cpf = re.sub(r"\D", "", self.cpf or "")
        if not self.cpf or not self.senha:
            raise MNIError(
                "Credenciais do PJe ausentes: informe CPF e senha "
                "(headers X-MNI-CPF / X-MNI-SENHA ou PJE_CPF / PJE_SENHA no .env).",
                status=401,
            )
        # Pega o typo aqui em vez de gastar uma tentativa de login no tribunal —
        # o PJe bloqueia a conta depois de algumas falhas seguidas.
        if len(self.cpf) == 11 and not cpf_valido(self.cpf):
            raise MNIError(
                "CPF do consultante inválido: os dígitos verificadores não conferem.",
                status=400,
            )

    # ── SOAP ────────────────────────────────────────────────
    def _envelope(
        self,
        numero: str,
        *,
        movimentos: bool,
        incluir_cabecalho: bool,
        incluir_documentos: bool,
        documentos: Optional[list[str]],
        servico: ServicoMNI,
    ) -> str:
        """Monta o envelope com os parâmetros qualificados no namespace de tipos."""
        docs = "".join(
            f"<tip:documento>{escape(str(d))}</tip:documento>"
            for d in (documentos or [])
        )
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<soapenv:Envelope xmlns:soapenv="{NS_SOAP}"'
            f' xmlns:ser="{servico.ns_servico}" xmlns:tip="{servico.ns_tipos}">'
            "<soapenv:Header/><soapenv:Body>"
            "<ser:consultarProcesso>"
            f"<tip:idConsultante>{escape(self.cpf)}</tip:idConsultante>"
            f"<tip:senhaConsultante>{escape(self.senha)}</tip:senhaConsultante>"
            f"<tip:numeroProcesso>{escape(numero)}</tip:numeroProcesso>"
            f"<tip:movimentos>{str(movimentos).lower()}</tip:movimentos>"
            f"<tip:incluirCabecalho>{str(incluir_cabecalho).lower()}</tip:incluirCabecalho>"
            f"<tip:incluirDocumentos>{str(incluir_documentos).lower()}</tip:incluirDocumentos>"
            f"{docs}"
            "</ser:consultarProcesso>"
            "</soapenv:Body></soapenv:Envelope>"
        )

    async def _descobrir_servico(self, url: str) -> ServicoMNI:
        """Lê o WSDL do tribunal (uma vez por URL) para saber como chamá-lo."""
        if url in self._servicos:
            return self._servicos[url]
        servico = ServicoMNI.presumido(url)
        try:
            async with httpx.AsyncClient(
                timeout=min(self.timeout, 30.0),
                verify=self.verify_ssl,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                resp = await _get_com_retry(client, f"{url}?wsdl")
            if resp.is_success and b"definitions" in resp.content[:4000]:
                servico = analisar_wsdl(resp.content, url)
        except (httpx.HTTPError, ET.ParseError):
            pass  # tribunal sem WSDL público: segue com o contrato padrão
        self._servicos[url] = servico
        return servico

    async def _post(self, servico: ServicoMNI, url: str, corpo: str) -> tuple[bytes, str]:
        headers = {
            "Content-Type": "text/xml;charset=UTF-8",
            "SOAPAction": f'"{servico.soap_action}"',
            "Accept": "text/xml, multipart/related, application/xop+xml",
            "User-Agent": USER_AGENT,
        }
        # O endereço do WSDL vem primeiro; se ele não atender (endereço interno
        # publicado por engano), tenta a própria URL de onde o WSDL foi lido.
        destinos = [servico.endpoint] + ([url] if url != servico.endpoint else [])
        erro: Optional[Exception] = None
        resp = None
        async with httpx.AsyncClient(
            timeout=self.timeout, verify=self.verify_ssl, follow_redirects=True
        ) as client:
            for destino in destinos:
                for _ in range(2):
                    try:
                        resp = await client.post(
                            destino, content=corpo.encode("utf-8"), headers=headers
                        )
                        break
                    except httpx.TransportError as exc:
                        erro = exc
                    except httpx.HTTPError as exc:
                        erro = exc
                        break
                if resp is not None:
                    break
        if resp is None:
            raise MNIError(
                f"Não foi possível alcançar o MNI em {' nem '.join(destinos)}.",
                status=504,
                detalhe=str(erro),
            ) from erro
        if resp.status_code >= 500 and b"Fault" not in resp.content:
            raise MNIError(
                f"O MNI do tribunal respondeu HTTP {resp.status_code}.",
                status=502,
                detalhe=resp.text[:500],
            )
        if resp.status_code == 404:
            raise MNIError(
                f"Endpoint MNI não encontrado ({url}). Confirme o caminho com o tribunal "
                "e declare-o em PJE_MNI_ENDPOINTS.",
                status=404,
            )
        return resp.content, resp.headers.get("content-type", "")

    async def _chamar(self, url: str, **kwargs: Any) -> tuple[ET.Element, ServicoMNI]:
        servico = await self._descobrir_servico(url)
        corpo = self._envelope(servico=servico, **kwargs)
        bruto, content_type = await self._post(servico, url, corpo)
        xml, anexos = _separar_mtom(bruto, content_type)
        try:
            raiz = ET.fromstring(xml)
        except ET.ParseError as exc:
            raise MNIError(
                "Resposta do MNI não é um XML válido.",
                status=502,
                detalhe=bruto[:300].decode("utf-8", "ignore"),
            ) from exc
        _levantar_se_fault(raiz)
        _resolver_xop(raiz, anexos)
        return raiz, servico

    # ── Operações ───────────────────────────────────────────
    async def consultar_processo(
        self,
        numero: str,
        *,
        movimentos: bool = True,
        incluir_cabecalho: bool = True,
        incluir_documentos: bool = False,
        documentos: Optional[list[str]] = None,
        grau: str = "1",
    ) -> dict[str, Any]:
        """Consulta um processo. Devolve JSON já normalizado."""
        num = parse_numero_cnj(numero)
        urls = [self.endpoint] if self.endpoint else candidatos_endpoint(num, grau)

        erro: Optional[MNIError] = None
        for url in urls:
            try:
                raiz, servico = await self._chamar(
                    url,
                    numero=num.digitos,
                    movimentos=movimentos,
                    incluir_cabecalho=incluir_cabecalho,
                    incluir_documentos=incluir_documentos,
                    documentos=documentos,
                )
            except MNIError as exc:
                erro = exc
                if exc.status in (404, 504):
                    continue  # candidato errado: tenta o próximo caminho
                raise
            return _parsear_resposta(raiz, num, servico.endpoint)

        raise erro or MNIError("Nenhum endpoint MNI candidato respondeu.", status=502)

    async def listar_documentos(self, numero: str, grau: str = "1") -> dict[str, Any]:
        """IDs e descrições dos documentos, sem baixar conteúdo."""
        dados = await self.consultar_processo(
            numero, movimentos=False, incluir_documentos=False, grau=grau
        )
        processo = dados.get("processo", {})
        return {
            "sucesso": dados.get("sucesso", False),
            "numero": processo.get("numero", ""),
            "documentos": [
                {k: d.get(k, "") for k in ("idDocumento", "descricao", "tipoDocumento", "mimetype", "dataHora")}
                for d in processo.get("documentos", [])
            ],
        }

    async def capa(self, numero: str, grau: str = "1") -> dict[str, Any]:
        """Só os metadados da capa: classe, partes, assuntos, órgão julgador."""
        dados = await self.consultar_processo(
            numero, movimentos=False, incluir_documentos=False, grau=grau
        )
        processo = dict(dados.get("processo", {}))
        processo.pop("documentos", None)
        processo.pop("movimentos", None)
        return {**dados, "processo": processo}

    async def baixar_documento(
        self, numero: str, id_documento: str, grau: str = "1"
    ) -> tuple[bytes, str, str]:
        """Baixa um documento. Devolve (conteúdo, mimetype, nome do arquivo)."""
        dados = await self.consultar_processo(
            numero,
            movimentos=False,
            incluir_documentos=True,
            documentos=[id_documento],
            grau=grau,
        )
        for doc in dados.get("processo", {}).get("documentos", []):
            if str(doc.get("idDocumento")) != str(id_documento):
                continue
            conteudo = doc.get("_conteudo")
            if not conteudo:
                raise MNIError(
                    f"O tribunal não devolveu o conteúdo do documento {id_documento} "
                    "(pode estar sob sigilo ou fora do seu acesso).",
                    status=403,
                )
            mimetype = doc.get("mimetype") or "application/octet-stream"
            nome = _nome_arquivo(numero, doc, mimetype)
            return conteudo, mimetype, nome

        raise MNIError(
            f"Documento {id_documento} não encontrado no processo {numero}.", status=404
        )

    async def peticao_inicial(self, numero: str, grau: str = "1") -> dict[str, Any]:
        """Petição inicial e seus anexos (metadados, sem conteúdo binário)."""
        dados = await self.consultar_processo(
            numero, movimentos=False, incluir_documentos=False, grau=grau
        )
        docs = dados.get("processo", {}).get("documentos", [])
        inicial = next(
            (
                d
                for d in docs
                if "inicial" in f"{d.get('descricao','')} {d.get('tipoDocumento','')}".lower()
            ),
            docs[0] if docs else None,
        )
        if inicial is None:
            raise MNIError(
                f"Nenhum documento disponível no processo {numero}.", status=404
            )
        return {
            "sucesso": True,
            "numero": dados.get("processo", {}).get("numero", ""),
            "peticaoInicial": inicial,
            "anexos": inicial.get("documentosVinculados", []),
        }

    async def verificar(self, numero: str, grau: str = "1") -> dict[str, Any]:
        """Health-check dos endpoints candidatos (não consulta processo)."""
        return await verificar_endpoints(
            numero, grau=grau, timeout=self.timeout, verify_ssl=self.verify_ssl
        )


async def verificar_endpoints(
    numero: str,
    grau: str = "1",
    timeout: float = DEFAULT_TIMEOUT,
    verify_ssl: bool = True,
) -> dict[str, Any]:
    """Testa o WSDL de cada endpoint candidato do tribunal. Não exige credencial.

    Serve para separar "não achei o endereço" de "o tribunal não respondeu":
    WSDL acessível não garante que a consulta funcione, mas WSDL inacessível já
    elimina o candidato.
    """
    num = parse_numero_cnj(numero)
    resultados = []
    async with httpx.AsyncClient(
        timeout=min(timeout, 30.0),
        verify=verify_ssl,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for url in candidatos_endpoint(num, grau):
            item: dict[str, Any] = {"wsdl": f"{url}?wsdl"}
            try:
                resp = await _get_com_retry(client, f"{url}?wsdl")
                item["status"] = resp.status_code
                item["ok"] = resp.is_success and b"definitions" in resp.content[:4000]
                if item["ok"]:
                    item["servico"] = analisar_wsdl(resp.content, url).to_dict()
            except (httpx.HTTPError, ET.ParseError) as exc:
                item["status"] = None
                item["ok"] = False
                item["erro"] = str(exc)[:200]
            resultados.append(item)
    return {"processo": num.to_dict(), "candidatos": resultados}


# ─── MTOM/XOP e SOAP Fault ────────────────────────────────────
def _separar_mtom(bruto: bytes, content_type: str) -> tuple[bytes, dict[str, bytes]]:
    """Separa o XML das partes binárias quando a resposta vem em multipart/related."""
    if "multipart/" not in content_type.lower():
        return bruto, {}

    import email

    mensagem = email.message_from_bytes(
        b"Content-Type: " + content_type.encode() + b"\r\nMIME-Version: 1.0\r\n\r\n" + bruto
    )
    xml = b""
    anexos: dict[str, bytes] = {}
    for parte in mensagem.walk():
        if parte.is_multipart():
            continue
        carga = parte.get_payload(decode=True) or b""
        cid = (parte.get("Content-ID") or "").strip("<>")
        if not xml and "xml" in (parte.get_content_type() or ""):
            xml = carga
        elif cid:
            anexos[cid] = carga
    return xml or bruto, anexos


def _resolver_xop(raiz: ET.Element, anexos: dict[str, bytes]) -> None:
    """Substitui <xop:Include href="cid:..."> pelo base64 do anexo correspondente."""
    if not anexos:
        return
    for pai in raiz.iter():
        for filho in list(pai):
            if _local(filho.tag) != "Include":
                continue
            cid = (filho.get("href") or "").removeprefix("cid:")
            dados = anexos.get(cid) or anexos.get(cid.replace("%40", "@"))
            if dados is not None:
                pai.text = base64.b64encode(dados).decode("ascii")
                pai.remove(filho)


def _levantar_se_fault(raiz: ET.Element) -> None:
    fault = _busca(raiz, "Fault")
    if fault is None:
        return
    texto = _attr(fault, "faultstring")
    if not texto:
        node = _busca(fault, "Text")  # SOAP 1.2
        texto = (node.text or "").strip() if node is not None else ""
    codigo = _attr(fault, "faultcode")
    status = 401 if re.search(r"senha|credencia|autentic|autoriz", texto, re.I) else 502
    raise MNIError(
        f"SOAP Fault do tribunal: {texto or codigo or 'sem detalhe'}", status=status
    )


# ─── Parsing da resposta ──────────────────────────────────────
def _parsear_resposta(raiz: ET.Element, num: NumeroCNJ, endpoint: str) -> dict[str, Any]:
    resposta = _busca(raiz, "consultarProcessoResposta") or raiz
    mensagem = _attr(resposta, "mensagem")
    sucesso = _attr(resposta, "sucesso").strip().lower() == "true"

    processo_el = _busca(resposta, "processo")
    if processo_el is None:
        # O MNI recusa por `sucesso=false` + mensagem, sem SOAP Fault.
        raise MNIError(
            mensagem or "O MNI não devolveu dados do processo.",
            status=_status_da_mensagem(mensagem) if not sucesso else 502,
            detalhe=f"endpoint={endpoint}",
        )

    basicos = _busca(processo_el, "dadosBasicos")
    orgao = _busca(basicos, "orgaoJulgador")

    return {
        "sucesso": True,
        "mensagem": mensagem,
        "endpoint": endpoint,
        "processo": {
            "numero": _attr(basicos, "numero", padrao=num.formatado),
            "tribunal": num.sigla,
            "segmento": num.segmento_nome,
            "codigoClasse": _attr(basicos, "classeProcessual"),
            "classe": _attr(basicos, "descricaoClasse", "classe"),
            "dataAjuizamento": _attr(basicos, "dataAjuizamento"),
            "valorCausa": _attr(basicos, "valorCausa"),
            "nivelSigilo": _attr(basicos, "nivelSigilo"),
            "codigoLocalidade": _attr(basicos, "codigoLocalidade"),
            "orgaoJulgador": {
                "codigo": _attr(orgao, "codigoOrgao"),
                "nome": _attr(orgao, "nomeOrgao"),
                "instancia": _attr(orgao, "instancia"),
            },
            "assuntos": _parsear_assuntos(basicos),
            "partes": _parsear_polos(basicos),
            "movimentos": _parsear_movimentos(processo_el),
            "documentos": _parsear_documentos(processo_el),
        },
    }


def _status_da_mensagem(mensagem: str) -> int:
    """Traduz a mensagem de recusa do tribunal em status HTTP."""
    if re.search(
        r"senha|usu.rio|credencia|autentic|autoriz|permiss|login", mensagem, re.I
    ):
        return 401
    if re.search(r"sigilo|segredo", mensagem, re.I):
        return 403
    if re.search(r"n.o (foi )?encontrad|inexistent|n.o localizad", mensagem, re.I):
        return 404
    return 502


def _parsear_assuntos(basicos: Optional[ET.Element]) -> list[dict[str, Any]]:
    assuntos = []
    for a in _filhos(basicos, "assunto"):
        assuntos.append(
            {
                "codigo": _attr(a, "codigoNacional", "codigoPaiNativo"),
                "descricao": _attr(a, "descricao"),
                "principal": _attr(a, "principal").lower() == "true",
            }
        )
    return assuntos


def _parsear_polos(basicos: Optional[ET.Element]) -> dict[str, list[dict[str, Any]]]:
    rotulos = {"AT": "ativo", "PA": "passivo", "TC": "terceiro", "FI": "fiscal"}
    partes: dict[str, list[dict[str, Any]]] = {}
    for polo in _filhos(basicos, "polo"):
        chave = rotulos.get(_attr(polo, "polo").upper(), "outros")
        for parte in _filhos(polo, "parte"):
            pessoa = _busca(parte, "pessoa")
            partes.setdefault(chave, []).append(
                {
                    "nome": _attr(pessoa, "nome"),
                    "tipoPessoa": _attr(pessoa, "tipoPessoa"),
                    "documento": _attr(pessoa, "numeroDocumentoPrincipal"),
                    "advogados": [
                        {
                            "nome": _attr(adv, "nome"),
                            "inscricao": _attr(adv, "inscricao"),
                        }
                        for adv in _filhos(parte, "advogado")
                    ],
                }
            )
    return partes


def _parsear_movimentos(processo_el: ET.Element) -> list[dict[str, Any]]:
    movimentos = []
    for m in _filhos(processo_el, "movimento"):
        nacional = _busca(m, "movimentoNacional")
        local = _busca(m, "movimentoLocal")
        movimentos.append(
            {
                "dataHora": _attr(m, "dataHora"),
                "codigo": _attr(nacional, "codigoNacional") or _attr(local, "codigoMovimento"),
                "descricao": _attr(local, "descricao") or _attr(m, "descricao"),
                "complementos": [
                    (c.text or "").strip()
                    for c in (_filhos(nacional, "complemento") + _filhos(m, "complemento"))
                ],
            }
        )
    return movimentos


def _parsear_documento(d: ET.Element) -> dict[str, Any]:
    conteudo_el = _filho(d, "conteudo")
    bruto = (conteudo_el.text or "").strip() if conteudo_el is not None else ""
    conteudo: Optional[bytes] = None
    if bruto:
        try:
            conteudo = base64.b64decode(bruto, validate=False)
        except (ValueError, TypeError):
            conteudo = None
    return {
        "idDocumento": _attr(d, "idDocumento"),
        "descricao": _attr(d, "descricao"),
        "tipoDocumento": _attr(d, "tipoDocumento", "tipoDocumentoLocal"),
        "mimetype": _attr(d, "mimetype"),
        "dataHora": _attr(d, "dataHora"),
        "nivelSigilo": _attr(d, "nivelSigilo"),
        "hash": _attr(d, "hash"),
        "temConteudo": conteudo is not None,
        "tamanhoBytes": len(conteudo) if conteudo else 0,
        "documentosVinculados": [
            _parsear_documento(v) for v in _filhos(d, "documentoVinculado")
        ],
        "_conteudo": conteudo,
    }


def _parsear_documentos(processo_el: ET.Element) -> list[dict[str, Any]]:
    return [_parsear_documento(d) for d in _filhos(processo_el, "documento")]


def _nome_arquivo(numero: str, doc: dict[str, Any], mimetype: str) -> str:
    extensoes = {
        "application/pdf": "pdf",
        "text/html": "html",
        "text/plain": "txt",
        "image/jpeg": "jpg",
        "image/png": "png",
        "application/msword": "doc",
    }
    ext = extensoes.get(mimetype.split(";")[0].strip(), "bin")
    base = re.sub(r"\D", "", numero)
    return f"{base}-{doc.get('idDocumento','doc')}.{ext}"


def sem_conteudo(dados: dict[str, Any]) -> dict[str, Any]:
    """Remove os bytes dos documentos para a resposta JSON."""
    processo = dados.get("processo")
    if isinstance(processo, dict):
        for doc in processo.get("documentos", []):
            _limpar(doc)
    return dados


def _limpar(doc: dict[str, Any]) -> None:
    doc.pop("_conteudo", None)
    for vinculado in doc.get("documentosVinculados", []):
        _limpar(vinculado)


def cliente_de_credenciais(
    cpf: Optional[str] = None,
    senha: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> MNIClient:
    """Cria o cliente a partir dos headers da requisição ou do .env."""
    return MNIClient(
        cpf=cpf or os.getenv("PJE_CPF", ""),
        senha=senha or os.getenv("PJE_SENHA", ""),
        endpoint=endpoint or os.getenv("PJE_MNI_ENDPOINT") or None,
    )
