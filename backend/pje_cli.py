"""
Teste do acesso MNI/PJe pela linha de comando, sem subir o servidor.

A senha é pedida interativamente (getpass) — não passe por argumento, que fica
no histórico do shell e na lista de processos.

    python pje_cli.py diagnostico 0020682-74.2019.8.06.0128
    python pje_cli.py consultar   0020682-74.2019.8.06.0128 --cpf 12345678900
    python pje_cli.py documentos  0020682-74.2019.8.06.0128 --cpf 12345678900
    python pje_cli.py baixar      0020682-74.2019.8.06.0128 123456 --cpf 12345678900
"""

import argparse
import asyncio
import getpass
import json
import os
import sys

from dotenv import load_dotenv

from pje_mni import MNIError, MNIClient, sem_conteudo, verificar_endpoints


load_dotenv()  # lê PJE_CPF / PJE_SENHA do backend/.env, se existir


def _mostrar(dados) -> None:
    print(json.dumps(dados, ensure_ascii=False, indent=2, default=str))


def _cliente(args) -> MNIClient:
    cpf = args.cpf or os.getenv("PJE_CPF") or input("CPF: ").strip()
    senha = os.getenv("PJE_SENHA") or getpass.getpass("Senha do PJe: ")
    return MNIClient(cpf=cpf, senha=senha, endpoint=args.endpoint, timeout=args.timeout)


async def executar(args) -> int:
    try:
        if args.comando == "diagnostico":
            _mostrar(await verificar_endpoints(args.numero, grau=args.grau))
            return 0

        cliente = _cliente(args)
        if args.comando == "consultar":
            _mostrar(
                sem_conteudo(
                    await cliente.consultar_processo(args.numero, grau=args.grau)
                )
            )
        elif args.comando == "documentos":
            _mostrar(await cliente.listar_documentos(args.numero, grau=args.grau))
        elif args.comando == "baixar":
            conteudo, mimetype, nome = await cliente.baixar_documento(
                args.numero, args.id_documento, grau=args.grau
            )
            destino = args.saida or nome
            with open(destino, "wb") as arquivo:
                arquivo.write(conteudo)
            print(f"{destino}  ({mimetype}, {len(conteudo)} bytes)")
    except MNIError as exc:
        print(f"erro {exc.status}: {exc.mensagem}", file=sys.stderr)
        if exc.detalhe:
            print(f"detalhe: {exc.detalhe}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Cliente MNI/PJe de linha de comando")
    parser.add_argument(
        "comando", choices=["diagnostico", "consultar", "documentos", "baixar"]
    )
    parser.add_argument("numero", help="número CNJ, com ou sem máscara")
    parser.add_argument("id_documento", nargs="?", help="id do documento (baixar)")
    parser.add_argument("--cpf", help="CPF do consultante (padrão: PJE_CPF)")
    parser.add_argument("--grau", default="1", choices=["1", "2"])
    parser.add_argument("--endpoint", help="força um endpoint MNI específico")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--saida", help="arquivo de destino (baixar)")
    args = parser.parse_args()

    if args.comando == "baixar" and not args.id_documento:
        parser.error("baixar exige o id do documento")
    return asyncio.run(executar(args))


if __name__ == "__main__":
    sys.exit(main())
