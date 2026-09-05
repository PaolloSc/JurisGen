"""
Testes do cliente MNI/PJe — rodam offline, sem tocar em tribunal.

    python test_pje_mni.py
"""

import base64
import sys
from xml.etree import ElementTree as ET

from pje_mni import (
    MNIError,
    analisar_wsdl,
    _levantar_se_fault,
    _parsear_resposta,
    _separar_mtom,
    _resolver_xop,
    candidatos_endpoint,
    parse_numero_cnj,
    sem_conteudo,
)

PDF_FALSO = b"%PDF-1.4 conteudo de teste"

RESPOSTA = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
 <soap:Body>
  <ns2:consultarProcessoResposta xmlns:ns2="http://www.cnj.jus.br/servico-intercomunicacao-2.2.2/"
                                 xmlns:ns4="http://www.cnj.jus.br/intercomunicacao-2.2.2.xsd"
                                 sucesso="true" mensagem="Sucesso">
   <processo>
    <ns4:dadosBasicos numero="00206827420198060128" classeProcessual="7"
                      codigoLocalidade="0128" nivelSigilo="0" dataAjuizamento="20190412103000"
                      valorCausa="15000.00">
     <ns4:polo polo="AT">
      <ns4:parte>
       <ns4:pessoa nome="Maria da Silva" tipoPessoa="fisica" numeroDocumentoPrincipal="12345678900"/>
       <ns4:advogado nome="Joao Advogado" inscricao="CE12345"/>
      </ns4:parte>
     </ns4:polo>
     <ns4:polo polo="PA">
      <ns4:parte>
       <ns4:pessoa nome="Empresa XYZ LTDA" tipoPessoa="juridica" numeroDocumentoPrincipal="11222333000144"/>
      </ns4:parte>
     </ns4:polo>
     <ns4:assunto principal="true">
      <ns4:codigoNacional>1234</ns4:codigoNacional>
     </ns4:assunto>
     <ns4:orgaoJulgador codigoOrgao="128" nomeOrgao="1a Vara Civel de Maracanau" instancia="ORIG"/>
    </ns4:dadosBasicos>
    <ns4:documento idDocumento="123456" tipoDocumento="57" mimetype="application/pdf"
                   dataHora="20190412103500" descricao="Peticao Inicial" nivelSigilo="0">
     <ns4:conteudo>{base64.b64encode(PDF_FALSO).decode()}</ns4:conteudo>
     <ns4:documentoVinculado idDocumento="123457" mimetype="application/pdf" descricao="Procuracao"/>
    </ns4:documento>
    <ns4:movimento dataHora="20190413090000">
     <ns4:movimentoNacional codigoNacional="26">
      <ns4:complemento>Distribuicao por sorteio</ns4:complemento>
     </ns4:movimentoNacional>
    </ns4:movimento>
   </processo>
  </ns2:consultarProcessoResposta>
 </soap:Body>
</soap:Envelope>"""

FAULT = """<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body>
 <soap:Fault><faultcode>soap:Server</faultcode>
  <faultstring>Senha invalida para o consultante informado</faultstring>
 </soap:Fault></soap:Body></soap:Envelope>"""


# Recorte com a mesma forma do WSDL de produção do TJCE: parâmetros
# form="qualified" em namespace próprio e <soap:address> em outro host.
WSDL = """<?xml version='1.0' encoding='UTF-8'?>
<wsdl:definitions xmlns:wsdl="http://schemas.xmlsoap.org/wsdl/"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
    xmlns:tns="http://www.cnj.jus.br/servico-intercomunicacao-2.2.2/"
    targetNamespace="http://www.cnj.jus.br/servico-intercomunicacao-2.2.2/">
 <wsdl:types>
  <xs:schema targetNamespace="http://www.cnj.jus.br/tipos-servico-intercomunicacao-2.2.2">
   <xs:complexType name="tipoConsultarProcesso">
    <xs:sequence>
     <xs:element form="qualified" name="idConsultante" type="xs:string"/>
     <xs:element form="qualified" name="senhaConsultante" type="xs:string"/>
     <xs:element form="qualified" name="numeroProcesso" type="xs:string"/>
    </xs:sequence>
   </xs:complexType>
  </xs:schema>
  <xs:schema targetNamespace="http://www.cnj.jus.br/servico-intercomunicacao-2.2.2/">
   <xs:element name="consultarProcesso" type="ns2:tipoConsultarProcesso"
               xmlns:ns2="http://www.cnj.jus.br/tipos-servico-intercomunicacao-2.2.2"/>
  </xs:schema>
 </wsdl:types>
 <wsdl:binding name="ServicoIntercomunicacaoSoapBinding" type="tns:ServicoIntercomunicacao">
  <soap:binding style="document" transport="http://schemas.xmlsoap.org/soap/http"/>
  <wsdl:operation name="consultarProcesso">
   <soap:operation soapAction="http://www.cnj.jus.br/servico-intercomunicacao-2.2.2/consultarProcesso"/>
  </wsdl:operation>
  <wsdl:operation name="entregarManifestacaoProcessual">
   <soap:operation soapAction="http://www.cnj.jus.br/servico-intercomunicacao-2.2.2/entregarManifestacaoProcessual"/>
  </wsdl:operation>
 </wsdl:binding>
 <wsdl:service name="ServicoIntercomunicacaoService">
  <wsdl:port binding="tns:ServicoIntercomunicacaoSoapBinding" name="ServicoIntercomunicacaoPort">
   <soap:address location="{address}"/>
  </wsdl:port>
 </wsdl:service>
</wsdl:definitions>"""


def test_analisar_wsdl():
    servico = analisar_wsdl(
        WSDL.format(address="https://pjews.tjce.jus.br/pje1grau/intercomunicacao").encode(),
        "https://pje.tjce.jus.br/pje1grau/intercomunicacao",
    )
    assert servico.ns_servico == "http://www.cnj.jus.br/servico-intercomunicacao-2.2.2/"
    assert servico.ns_tipos == "http://www.cnj.jus.br/tipos-servico-intercomunicacao-2.2.2"
    assert servico.soap_action == (
        "http://www.cnj.jus.br/servico-intercomunicacao-2.2.2/consultarProcesso"
    )
    # o endereço de chamada sai do WSDL, não da URL onde ele foi lido
    assert servico.endpoint == "https://pjews.tjce.jus.br/pje1grau/intercomunicacao"
    assert servico.wsdl == "https://pje.tjce.jus.br/pje1grau/intercomunicacao?wsdl"
    assert "entregarManifestacaoProcessual" in servico.operacoes

    # sem WSDL utilizável, cai no contrato padrão
    from pje_mni import ServicoMNI

    padrao = ServicoMNI.presumido("https://pje.x.jus.br/pje/intercomunicacao")
    assert padrao.endpoint == "https://pje.x.jus.br/pje/intercomunicacao"
    assert padrao.soap_action.endswith("consultarProcesso")
    print("ok  analise do wsdl")


def test_numero_cnj():
    num = parse_numero_cnj("0020682-74.2019.8.06.0128")
    assert num.sigla == "TJCE", num.sigla
    assert num.ano == "2019"
    assert num.origem == "0128"
    assert num.digito_valido, "DV do numero real deveria validar"
    assert parse_numero_cnj("00206827420198060128").formatado == num.formatado

    # siglas por segmento
    assert parse_numero_cnj("00000000020235030001").sigla == "TRT3"
    assert parse_numero_cnj("00000000020244013400").sigla == "TRF1"
    assert parse_numero_cnj("00000000020248260100").sigla == "TJSP"
    assert parse_numero_cnj("00000000020248070001").sigla == "TJDFT"

    for invalido in ("123", "", "abc-def"):
        try:
            parse_numero_cnj(invalido)
        except MNIError as exc:
            assert exc.status == 400
        else:
            raise AssertionError(f"deveria rejeitar {invalido!r}")
    print("ok  numero CNJ")


def test_endpoints():
    num = parse_numero_cnj("0020682-74.2019.8.06.0128")
    candidatos = candidatos_endpoint(num, "1")
    assert candidatos[0] == "https://pje.tjce.jus.br/pje1grau/intercomunicacao"
    assert len(candidatos) == 3

    import os

    import pje_mni

    os.environ["PJE_MNI_ENDPOINTS"] = '{"TJCE": {"1": "https://custom/mni", "2": "https://custom/mni2"}}'
    try:
        assert candidatos_endpoint(num, "1") == ["https://custom/mni"]
        assert candidatos_endpoint(num, "2") == ["https://custom/mni2"]
        os.environ["PJE_MNI_ENDPOINTS"] = "{isso nao e json}"
        try:
            candidatos_endpoint(num, "1")
        except MNIError as exc:
            assert exc.status == 500
        else:
            raise AssertionError("JSON invalido deveria falhar")
    finally:
        os.environ.pop("PJE_MNI_ENDPOINTS", None)
        pje_mni._endpoints_configurados()
    print("ok  resolucao de endpoint")


def test_parsing():
    raiz = ET.fromstring(RESPOSTA)
    num = parse_numero_cnj("0020682-74.2019.8.06.0128")
    dados = _parsear_resposta(raiz, num, "https://pje.tjce.jus.br/pje1grau/intercomunicacao")

    proc = dados["processo"]
    assert dados["sucesso"] is True
    assert proc["numero"] == "00206827420198060128"
    assert proc["tribunal"] == "TJCE"
    assert proc["codigoClasse"] == "7"
    assert proc["valorCausa"] == "15000.00"
    assert proc["orgaoJulgador"]["nome"] == "1a Vara Civel de Maracanau"
    assert proc["assuntos"][0] == {"codigo": "1234", "descricao": "", "principal": True}

    assert proc["partes"]["ativo"][0]["nome"] == "Maria da Silva"
    assert proc["partes"]["ativo"][0]["advogados"][0]["inscricao"] == "CE12345"
    assert proc["partes"]["passivo"][0]["tipoPessoa"] == "juridica"

    assert proc["movimentos"][0]["codigo"] == "26"
    assert proc["movimentos"][0]["complementos"] == ["Distribuicao por sorteio"]

    doc = proc["documentos"][0]
    assert doc["idDocumento"] == "123456"
    assert doc["descricao"] == "Peticao Inicial"
    assert doc["_conteudo"] == PDF_FALSO
    assert doc["tamanhoBytes"] == len(PDF_FALSO)
    assert doc["documentosVinculados"][0]["idDocumento"] == "123457"

    sem_conteudo(dados)
    assert "_conteudo" not in proc["documentos"][0]
    assert "_conteudo" not in proc["documentos"][0]["documentosVinculados"][0]
    print("ok  parsing da resposta")


def test_fault():
    try:
        _levantar_se_fault(ET.fromstring(FAULT))
    except MNIError as exc:
        assert exc.status == 401, exc.status
        assert "Senha invalida" in exc.mensagem
    else:
        raise AssertionError("SOAP Fault deveria virar MNIError")
    print("ok  soap fault")


def test_mtom():
    corpo = (
        '<?xml version="1.0"?>'
        '<env xmlns:xop="http://www.w3.org/2004/08/xop/include">'
        '<conteudo><xop:Include href="cid:doc-1@pje"/></conteudo></env>'
    )
    bruto = (
        b"--limite\r\nContent-Type: application/xop+xml; type=\"text/xml\"\r\n"
        b"Content-ID: <root@pje>\r\n\r\n" + corpo.encode() + b"\r\n"
        b"--limite\r\nContent-Type: application/pdf\r\n"
        b"Content-Transfer-Encoding: binary\r\n"
        b"Content-ID: <doc-1@pje>\r\n\r\n" + PDF_FALSO + b"\r\n--limite--\r\n"
    )
    xml, anexos = _separar_mtom(bruto, 'multipart/related; boundary="limite"; type="application/xop+xml"')
    assert anexos["doc-1@pje"] == PDF_FALSO, anexos
    raiz = ET.fromstring(xml)
    _resolver_xop(raiz, anexos)
    conteudo = raiz.find("conteudo")
    assert base64.b64decode(conteudo.text) == PDF_FALSO
    assert len(conteudo) == 0, "o xop:Include deveria ter sido removido"
    print("ok  mtom/xop")



def test_ponta_a_ponta():
    """MNI falso em localhost: descoberta pelo WSDL, envelope, parsing e download."""
    import asyncio
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from pje_mni import MNIClient

    recebido = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # silencia o log do servidor de teste
            pass

        def do_GET(self):
            assert self.path.endswith("?wsdl"), self.path
            corpo = WSDL.format(
                address=f"http://127.0.0.1:{self.server.server_port}/ws/intercomunicacao"
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/xml;charset=UTF-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def do_POST(self):
            recebido["caminho"] = self.path
            recebido["soapaction"] = self.headers.get("SOAPAction")
            recebido["envelope"] = self.rfile.read(
                int(self.headers.get("Content-Length", 0))
            ).decode()
            resposta = RESPOSTA.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/xml;charset=UTF-8")
            self.send_header("Content-Length", str(len(resposta)))
            self.end_headers()
            self.wfile.write(resposta)

    servidor = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    endpoint = f"http://127.0.0.1:{servidor.server_port}/pje1grau/intercomunicacao"

    try:
        cliente = MNIClient(cpf="123.456.789-00", senha="segredo", endpoint=endpoint, timeout=10)
        dados = asyncio.run(cliente.consultar_processo("0020682-74.2019.8.06.0128"))
        assert dados["processo"]["partes"]["ativo"][0]["nome"] == "Maria da Silva"

        # seguiu o <soap:address> do WSDL em vez da URL de leitura
        assert recebido["caminho"] == "/ws/intercomunicacao", recebido["caminho"]
        assert dados["endpoint"].endswith("/ws/intercomunicacao")
        assert recebido["soapaction"] == (
            '"http://www.cnj.jus.br/servico-intercomunicacao-2.2.2/consultarProcesso"'
        )

        envelope = recebido["envelope"]
        assert 'xmlns:tip="http://www.cnj.jus.br/tipos-servico-intercomunicacao-2.2.2"' in envelope
        assert "<tip:idConsultante>12345678900</tip:idConsultante>" in envelope, envelope
        assert "<tip:senhaConsultante>segredo</tip:senhaConsultante>" in envelope
        assert "<tip:numeroProcesso>00206827420198060128</tip:numeroProcesso>" in envelope
        assert "<tip:movimentos>true</tip:movimentos>" in envelope
        assert "<ser:consultarProcesso>" in envelope

        conteudo, mimetype, nome = asyncio.run(
            cliente.baixar_documento("0020682-74.2019.8.06.0128", "123456")
        )
        assert conteudo == PDF_FALSO
        assert mimetype == "application/pdf"
        assert nome == "00206827420198060128-123456.pdf"
        assert "<tip:documento>123456</tip:documento>" in recebido["envelope"]

        ids = asyncio.run(cliente.listar_documentos("0020682-74.2019.8.06.0128"))
        assert ids["documentos"][0]["descricao"] == "Peticao Inicial"

        inicial = asyncio.run(cliente.peticao_inicial("0020682-74.2019.8.06.0128"))
        assert inicial["peticaoInicial"]["idDocumento"] == "123456"
        assert inicial["anexos"][0]["idDocumento"] == "123457"
    finally:
        servidor.shutdown()
    print("ok  ponta a ponta (MNI falso em localhost)")


def test_recusa_sem_fault():
    """O MNI recusa credencial com sucesso=false + mensagem, sem SOAP Fault."""
    from pje_mni import _parsear_resposta

    recusa = """<?xml version="1.0"?>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body>
     <ns2:consultarProcessoResposta xmlns:ns2="http://www.cnj.jus.br/servico-intercomunicacao-2.2.2/">
      <sucesso>false</sucesso>
      <mensagem>Usuario ou senha invalidos</mensagem>
     </ns2:consultarProcessoResposta></soap:Body></soap:Envelope>"""
    try:
        _parsear_resposta(ET.fromstring(recusa), parse_numero_cnj("00206827420198060128"), "x")
    except MNIError as exc:
        assert exc.status == 401, exc.status
        assert "senha" in exc.mensagem.lower()
    else:
        raise AssertionError("sucesso=false deveria virar MNIError")

    inexistente = recusa.replace(
        "Usuario ou senha invalidos", "Processo nao encontrado na base de dados"
    )
    try:
        _parsear_resposta(ET.fromstring(inexistente), parse_numero_cnj("00206827420198060128"), "x")
    except MNIError as exc:
        assert exc.status == 404, exc.status
    else:
        raise AssertionError("processo inexistente deveria virar MNIError")
    print("ok  recusa sem soap fault")


if __name__ == "__main__":
    falhas = 0
    for teste in (
        test_numero_cnj,
        test_analisar_wsdl,
        test_endpoints,
        test_parsing,
        test_fault,
        test_mtom,
        test_recusa_sem_fault,
        test_ponta_a_ponta,
    ):
        try:
            teste()
        except AssertionError as exc:
            falhas += 1
            print(f"FALHOU  {teste.__name__}: {exc}")
    print("\ntodos os testes passaram" if not falhas else f"\n{falhas} teste(s) falharam")
    sys.exit(1 if falhas else 0)
