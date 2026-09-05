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
consolidada**. Sem `PJE_MNI_ENDPOINTS` o cliente tenta, em ordem,
`pje{grau}grau/intercomunicacao`, `pje{grau}g/intercomunicacao` e
`pje/intercomunicacao` sob `https://pje.{sigla}.jus.br/` — bom para descobrir,
ruim para produção. Descubra uma vez com `/api/v1/pje/diagnostico/{numero}`,
confirme com o tribunal e fixe o endereço no `.env`.

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

## Detalhes de implementação

- **Namespace**: o cliente lê o `targetNamespace` do `?wsdl` do tribunal e usa
  esse valor no envelope; se o WSDL não estiver acessível, cai no padrão MNI
  2.2.2. O parsing ignora namespace (compara só o nome local), então serve para
  2.2, 2.2.2 e 3.0.
- **MTOM/XOP**: quando o tribunal devolve `multipart/related`, as partes binárias
  são casadas com os `<xop:Include href="cid:...">` antes do parsing.
- **Segurança**: a senha só aparece no envelope enviado ao tribunal — nunca é
  registrada em log nem devolvida nas respostas.

## Testes

```bash
cd backend && python test_pje_mni.py
```

Rodam offline: número CNJ, resolução de endpoint, parsing da resposta, SOAP
Fault, MTOM/XOP e um teste ponta a ponta contra um MNI falso em `127.0.0.1`.

## Sobre APIs REST de terceiros para o PJe

Existem serviços que oferecem esse mesmo REST hospedado por terceiros, pedindo
`X-MNI-CPF` e `X-MNI-SENHA`. Os headers aqui são propositalmente iguais, para o
código ser intercambiável — mas note a diferença: mandar CPF e senha do PJe para
um host de terceiro entrega a um estranho acesso aos seus autos, inclusive
processos em segredo de justiça, com o registro de acesso saindo no seu nome.
Este módulo existe para não precisar fazer isso.
