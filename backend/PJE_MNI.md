# Acesso ao PJe via MNI

O PJe não tem "uma API REST". O que existe de oficial é o **MNI — Modelo Nacional
de Interoperabilidade** (CNJ): um webservice SOAP que cada tribunal publica no
caminho `intercomunicacao`. É por ele que o Escritório Digital do CNJ lê os autos,
e é o que este módulo consome.

`backend/pje_mni.py` fala MNI direto com o tribunal e `main.py` expõe isso como
REST. **As credenciais vão daqui para o tribunal, sem intermediário.**

## O que dá para fazer (e o que não dá)

| Fonte | Acesso | Traz documentos? | Credencial |
|---|---|---|---|
| **MNI/PJe** (este módulo) | processos em que você atua | sim, PDFs dos autos | CPF + senha do PJe |
| **DataJud/CNJ** (`/api/cnj/search`) | metadados públicos de todos os tribunais | não | chave pública do CNJ |

MNI é acesso **aos seus processos**: o tribunal só devolve o que aquele CPF pode
ver. Não serve para varrer processos de terceiros nem substitui o DataJud em
pesquisa de jurisprudência.

## Configuração

```bash
# credenciais padrão do servidor (opcional — podem vir por header a cada request)
PJE_CPF=12345678900
PJE_SENHA=sua-senha-do-pje

# endpoints MNI verificados, por tribunal e grau (tem precedência sobre os candidatos)
PJE_MNI_ENDPOINTS='{"TJCE": {"1": "https://pje.tjce.jus.br/pje1grau/intercomunicacao",
                             "2": "https://pje.tjce.jus.br/pje2grau/intercomunicacao"}}'

PJE_MNI_TIMEOUT=120
```

Cada tribunal publica o MNI em um caminho próprio e **não existe lista oficial
consolidada**. Sem `PJE_MNI_ENDPOINTS` o cliente tenta, em ordem: as URLs já
verificadas (tabela abaixo), depois `pje{grau}grau/intercomunicacao`,
`pje{grau}g/intercomunicacao` e `pje/intercomunicacao` sob
`https://pje.{sigla}.jus.br/`. Descubra com `/api/v1/pje/diagnostico/{numero}`,
confirme com o tribunal e fixe o endereço no `.env`.

### Endpoints verificados

Varredura de 57 tribunais (27 TJs, 6 TRFs, 24 TRTs) em 05/09/2026: **6
responderam** com WSDL válido nesses caminhos. Os demais usam outro caminho, não
expõem o MNI publicamente ou estavam fora do ar — o segundo artigo do TecJustiça
sobre o assunto faz a mesma ressalva.

| Tribunal | WSDL | Endereço real de chamada (`soap:address`) |
|---|---|---|
| TJCE 1º | `pje.tjce.jus.br/pje1grau/intercomunicacao` | `pjews.tjce.jus.br/pje1grau/intercomunicacao` |
| TJCE 2º | `pje.tjce.jus.br/pje2grau/intercomunicacao` | `pjews.tjce.jus.br/pje2grau/intercomunicacao` |
| TJPE 1º | `pje.tjpe.jus.br/pje/intercomunicacao` | `pje.cloud.tjpe.jus.br/1g/intercomunicacao` |
| TJPE 2º | `pje.tjpe.jus.br/pje2g/intercomunicacao` | `pje.cloud.tjpe.jus.br/2g/intercomunicacao` |
| TRF5 | `pje.trf5.jus.br/pje/intercomunicacao` | `pje.trf5.jus.br/pjemni/intercomunicacao` |
| TJMT | `pje.tjmt.jus.br/pje/intercomunicacao` | mesmo endereço |
| TJPA | `pje.tjpa.jus.br/pje/intercomunicacao` | mesmo endereço |
| TJRR | `pje.tjrr.jus.br/pje/intercomunicacao` | mesmo endereço |

Dois casos verificados que **não** funcionam:

- **TJMG** filtra por `User-Agent`: sem um de navegador, devolve `426 Upgrade
  Required` em qualquer caminho. Com UA de navegador o filtro sai da frente e
  aparece a resposta real — `302` para
  `www8.tjmg.jus.br/error/server_error.html` em todos os caminhos MNI testados,
  ou seja, a rota não existe publicamente. (O cliente passou a mandar
  `User-Agent` de navegador por causa disso; ajustável por `PJE_MNI_USER_AGENT`.)
- **TRT3** não expõe `intercomunicacao` em nenhum caminho testado; o que
  responde é `pje-comum-api`, a API REST interna do PJe, com erro estruturado
  (`ARQ-013`) para rota desconhecida.

Em ambos, o caminho é pedir o endereço (e o credenciamento) à TI do tribunal.

**Repare na terceira coluna.** Em metade dos casos o serviço atende em host ou
caminho diferente daquele onde o WSDL está publicado. Por isso o cliente lê o
`<soap:address>` do WSDL e chama o endereço que está lá — mandar a requisição
para a URL do WSDL simplesmente não funciona no TJCE, no TJPE nem no TRF5.

Credenciais: são o **login do próprio advogado no PJe**. Alguns tribunais exigem
cadastro prévio do sistema consumidor ou certificado digital — pergunte à
corregedoria/TI do tribunal antes de assumir que basta CPF e senha.

## Endpoints REST

Autenticação por header: `X-MNI-CPF`, `X-MNI-SENHA`. Opcional:
`X-MNI-ENDPOINT` força um endpoint específico. Query `grau=1|2`.

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/v1/processo/{numero}` | capa + partes + movimentos + lista de documentos |
| GET | `/api/v1/processo/{numero}/capa` | só os metadados da capa |
| GET | `/api/v1/processo/{numero}/documentos/ids` | IDs e descrições dos documentos |
| GET | `/api/v1/processo/{numero}/peticao-inicial` | inicial e seus anexos |
| GET | `/api/v1/processo/{numero}/documento/{id}` | download binário do documento |
| GET | `/api/v1/pje/diagnostico/{numero}` | decompõe o número CNJ e testa os WSDL candidatos |

O número aceita as duas formas: `0020682-74.2019.8.06.0128` ou
`00206827420198060128`.

### Exemplos

```bash
# capa do processo
curl -H "X-MNI-CPF: 12345678900" -H "X-MNI-SENHA: minha-senha" \
     http://localhost:8000/api/v1/processo/0020682-74.2019.8.06.0128/capa

# baixar um documento
curl -H "X-MNI-CPF: 12345678900" -H "X-MNI-SENHA: minha-senha" \
     -o inicial.pdf \
     http://localhost:8000/api/v1/processo/00206827420198060128/documento/123456

# descobrir o endpoint MNI do tribunal
curl -H "X-MNI-CPF: 12345678900" -H "X-MNI-SENHA: minha-senha" \
     http://localhost:8000/api/v1/pje/diagnostico/0020682-74.2019.8.06.0128
```

```python
import httpx

headers = {"X-MNI-CPF": "12345678900", "X-MNI-SENHA": "minha-senha"}
base = "http://localhost:8000/api/v1"

processo = httpx.get(f"{base}/processo/0020682-74.2019.8.06.0128", headers=headers).json()
print(processo["processo"]["classe"], processo["processo"]["partes"])

for doc in processo["processo"]["documentos"]:
    pdf = httpx.get(f"{base}/processo/00206827420198060128/documento/{doc['idDocumento']}",
                    headers=headers)
    open(f"{doc['idDocumento']}.pdf", "wb").write(pdf.content)
```

Sem passar pelo HTTP, direto no Python:

```python
from pje_mni import MNIClient

cliente = MNIClient(cpf="12345678900", senha="minha-senha")
dados = await cliente.consultar_processo("0020682-74.2019.8.06.0128")
conteudo, mimetype, nome = await cliente.baixar_documento("00206827420198060128", "123456")
```

## Erros

O corpo de erro segue sempre a mesma forma:

```json
{"sucesso": false, "erro": "...", "detalhe": "...", "sugestao": "..."}
```

| Status | Causa provável |
|---|---|
| 400 | número CNJ fora do formato de 20 dígitos |
| 401 | credencial ausente ou recusada pelo tribunal (SOAP Fault de senha) |
| 403 | documento sob sigilo ou CPF sem acesso àquele processo |
| 404 | processo inexistente no tribunal, ou endpoint MNI errado |
| 502 | o MNI respondeu erro/XML inválido |
| 504 | o MNI do tribunal não respondeu no tempo |

`WSDL acessível ≠ serviço funcionando`: há tribunais que publicam o endpoint e
devolvem timeout ou resposta vazia. O `/diagnostico` separa "não achei o
endereço" de "o tribunal não respondeu".

## Validado contra tribunal real

Verificado em 05/09/2026 contra o MNI de produção do **TJCE**
(`pje1grau/intercomunicacao`), sem credencial válida:

1. **Descoberta** — o WSDL devolve namespace 2.2.2, `soap:address` em
   `pjews.tjce.jus.br`, SOAPAction
   `http://www.cnj.jus.br/servico-intercomunicacao-2.2.2/consultarProcesso` e as
   6 operações do MNI (`consultarProcesso`, `consultarAvisosPendentes`,
   `consultarTeorComunicacao`, `entregarManifestacaoProcessual`,
   `consultarAlteracao`, `confirmarRecebimento`).
2. **Envelope aceito** — com CPF `00000000000` e senha inválida, o tribunal
   responde `Erro ao realizar login via MNI. exception invoking: loginFailed`.
   Ou seja: o XML foi desserializado e a chamada chegou à autenticação. Com
   credencial real, a consulta segue adiante.
3. **Envelope sem os prefixos de namespace é rejeitado** — a mesma chamada com
   os parâmetros sem prefixo devolve HTTP 500:
   `Unmarshalling Error: elemento inesperado (uri:"", local:"idConsultante")`.

O passo 3 é a razão de os parâmetros irem qualificados: o schema declara
`form="qualified"` em `tipos-servico-intercomunicacao-2.2.2`, e o JAX-WS do
tribunal recusa o que vier sem prefixo.

Falta o único passo que exige credencial real: consultar um processo em que você
atue. Use o CLI:

```bash
cd backend
python pje_cli.py diagnostico 0020682-74.2019.8.06.0128          # sem credencial
python pje_cli.py consultar   0020682-74.2019.8.06.0128 --cpf 12345678900
python pje_cli.py documentos  0020682-74.2019.8.06.0128 --cpf 12345678900
python pje_cli.py baixar      0020682-74.2019.8.06.0128 123456 --cpf 12345678900
```

O CPF pode ficar em `backend/.env` (`PJE_CPF=...`) — o arquivo está no
`.gitignore`. A senha é pedida por `getpass`: não passe em argumento, que fica no
histórico do shell e visível na lista de processos, e não a escreva no `.env`
versionado de ninguém.

> **Cuidado ao testar com CPF real.** O PJe bloqueia a conta após algumas
> tentativas de login malsucedidas. Por isso o cliente confere os dígitos
> verificadores do CPF antes de chamar o tribunal, e por isso os testes de
> protocolo aqui usaram `00000000000` — um CPF inexistente, que não pertence a
> ninguém e não tem conta para bloquear.

## Detalhes de implementação

- **Contrato lido do WSDL**: namespace do serviço, namespace dos parâmetros,
  SOAPAction e endereço de chamada saem do `?wsdl` do próprio tribunal (uma
  leitura por URL, em cache). Sem WSDL acessível, cai no padrão MNI 2.2.2. O
  parsing ignora namespace (compara só o nome local), então serve 2.2, 2.2.2 e 3.0.
- **Parâmetros qualificados**: `idConsultante`, `senhaConsultante` etc. vão no
  namespace `tipos-servico-intercomunicacao-2.2.2`, como o schema exige.
- **Recusa sem SOAP Fault**: o MNI costuma responder HTTP 200 com
  `sucesso=false` e uma mensagem; ela vira `MNIError` com o status certo
  (`loginFailed` → 401, "não encontrado" → 404, "sigilo" → 403).
- **Conexão derrubada**: o PJe reseta a primeira conexão de vez em quando; GET e
  POST têm uma retentativa.
- **User-Agent**: enviado como navegador, porque tribunal com filtro de borda
  (TJMG) responde 426 a cliente sem UA. Configurável em `PJE_MNI_USER_AGENT`.
- **CPF conferido localmente**: dígitos verificadores validados antes de chamar
  o tribunal, para um typo não gastar tentativa de login (o PJe bloqueia a conta
  após algumas falhas).
- **MTOM/XOP**: quando o tribunal devolve `multipart/related`, as partes binárias
  são casadas com os `<xop:Include href="cid:...">` antes do parsing.
- **Segurança**: a senha só aparece no envelope enviado ao tribunal — nunca é
  registrada em log nem devolvida nas respostas.

## Testes

```bash
cd backend && python test_pje_mni.py
```

São 8 testes offline: número CNJ, análise do WSDL, resolução de endpoint,
parsing da resposta, SOAP Fault, MTOM/XOP, recusa por `sucesso=false` e um teste
ponta a ponta contra um MNI falso em `127.0.0.1` — que serve WSDL com
`soap:address` em outro caminho, para provar que o cliente segue o endereço
anunciado e envia os parâmetros qualificados.

Para testar contra tribunal real, use o `pje_cli.py` (seção acima).

## Sobre APIs REST de terceiros para o PJe

Existem serviços que oferecem esse mesmo REST hospedado por terceiros, pedindo
`X-MNI-CPF` e `X-MNI-SENHA`. Os headers aqui são propositalmente iguais, para o
código ser intercambiável — mas note a diferença: mandar CPF e senha do PJe para
um host de terceiro entrega a um estranho acesso aos seus autos, inclusive
processos em segredo de justiça, com o registro de acesso saindo no seu nome.
Este módulo existe para não precisar fazer isso.
