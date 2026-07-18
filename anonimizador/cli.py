"""
Interface de linha de comando.

    python -m anonimizador documento.txt --modo pseudonimo
    python -m anonimizador documento.txt --modo anonimo -o limpo.txt
    python -m anonimizador documento.txt --simular

Interface grafica e fase futura; este e o ponto de entrada unico por enquanto.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from anonimizador import __version__
from anonimizador.detectores import detectar_tudo
from anonimizador.extratores import FormatoNaoSuportadoError, extrair
from anonimizador.redator import Modo, Resultado, redigir

AVISO_MAPA = (
    "ATENCAO: este arquivo reverte a pseudonimizacao. Trate-o com o mesmo "
    "cuidado do documento original -- guarde separado do texto redigido, ou "
    "apague quando nao precisar mais. Os dois juntos equivalem ao documento "
    "sem tratamento nenhum."
)


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="anonimizador",
        description="Remove ou pseudonimiza dados pessoais de documentos. Roda 100%% offline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "modos:\n"
            "  anonimo     (padrao) troca por marcador generico: [NOME], [CPF].\n"
            "              Sem vinculo entre mencoes, sem mapa, irreversivel.\n"
            "              Use para compartilhar o documento.\n"
            "  pseudonimo  troca por token estavel: PESSOA_001, CPF_001.\n"
            "              Mesma pessoa = mesmo token, texto continua coerente.\n"
            "              GERA MAPA DE-PARA, que reverte a protecao se vazar.\n"
        ),
    )
    parser.add_argument("arquivo", type=Path, help="documento a tratar")
    parser.add_argument(
        "-m", "--modo",
        type=Modo, choices=list(Modo), default=Modo.ANONIMO,
        help="modo de tratamento (padrao: anonimo, o mais seguro)",
    )
    parser.add_argument(
        "-o", "--saida", type=Path, default=None,
        help="arquivo de saida (padrao: <arquivo>.anonimizado.<ext>)",
    )
    parser.add_argument(
        "--mapa", type=Path, default=None,
        help="onde gravar o mapa de-para (padrao: <arquivo>.mapa.json). So no modo pseudonimo",
    )
    parser.add_argument(
        "--simular", action="store_true",
        help="lista o que seria detectado e NAO grava nada. Mostra os valores "
             "reais na tela -- use so para calibrar, em ambiente confiavel",
    )
    parser.add_argument(
        "--sem-nomes", action="store_true",
        help="pula a deteccao de nomes (nao carrega o modelo de NER)",
    )
    parser.add_argument(
        "--agressivo", action="store_true",
        help="liga a varredura de nomes em CAIXA ALTA: mais recall, bem mais "
             "falso positivo. Vale a pena em documento critico",
    )
    parser.add_argument(
        "--modelo", default="pt_core_news_sm",
        help="modelo spaCy de NER (padrao: pt_core_news_sm)",
    )
    parser.add_argument(
        "-f", "--forcar", action="store_true",
        help="sobrescreve arquivos de saida ja existentes",
    )
    parser.add_argument("--version", action="version", version=f"anonimizador {__version__}")
    return parser


def _caminho_saida(arquivo: Path, saida: Path | None) -> Path:
    if saida is not None:
        return saida
    return arquivo.with_suffix(f".anonimizado{arquivo.suffix}")


def _caminho_mapa(arquivo: Path, mapa: Path | None) -> Path:
    if mapa is not None:
        return mapa
    return arquivo.with_suffix(".mapa.json")


def _gravar_mapa(caminho: Path, resultado: Resultado, origem: Path) -> None:
    conteudo = {
        "aviso": AVISO_MAPA,
        "arquivo_origem": origem.name,
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "total_entradas": len(resultado.mapa),
        "mapa": [
            {
                "valor_real": entrada.valor,
                "token": entrada.token,
                "tipo": entrada.tipo,
                "ocorrencias": entrada.ocorrencias,
            }
            for entrada in resultado.mapa
        ],
    }
    caminho.write_text(
        json.dumps(conteudo, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _relatorio(resultado: Resultado) -> str:
    if not resultado.deteccoes:
        return "  nenhuma deteccao"
    linhas = [
        f"  {tipo:<16} {quantidade}"
        for tipo, quantidade in resultado.contagem_por_tipo().items()
    ]
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)

    if not args.arquivo.is_file():
        print(f"erro: arquivo nao encontrado: {args.arquivo}", file=sys.stderr)
        return 1

    try:
        texto = extrair(args.arquivo)
    except FormatoNaoSuportadoError as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 1

    try:
        deteccoes = detectar_tudo(
            texto,
            incluir_nomes=not args.sem_nomes,
            agressivo=args.agressivo,
        )
    except Exception as erro:  # ModeloIndisponivelError e afins
        print(f"erro: {erro}", file=sys.stderr)
        return 1

    if args.simular:
        print(f"{len(deteccoes)} deteccao(oes) em {args.arquivo.name}:\n")
        for deteccao in deteccoes:
            print(
                f"  [{deteccao.tipo:<15}] {deteccao.texto!r}"
                f"  (pos {deteccao.inicio}-{deteccao.fim}, "
                f"confianca {deteccao.confianca.name.lower()}, "
                f"via {deteccao.detector})"
            )
        print("\nnada foi gravado (--simular)")
        return 0

    resultado = redigir(texto, deteccoes, args.modo)

    saida = _caminho_saida(args.arquivo, args.saida)
    if saida.resolve() == args.arquivo.resolve():
        print("erro: a saida nao pode ser o proprio arquivo de entrada", file=sys.stderr)
        return 1
    if saida.exists() and not args.forcar:
        print(f"erro: {saida} ja existe (use --forcar para sobrescrever)", file=sys.stderr)
        return 1

    saida.write_text(resultado.texto, encoding="utf-8")

    print(f"modo:   {args.modo.value}")
    print(f"saida:  {saida}")
    print(f"deteccoes ({resultado.total_substituicoes} no total):")
    print(_relatorio(resultado))

    if args.modo is Modo.PSEUDONIMO:
        caminho_mapa = _caminho_mapa(args.arquivo, args.mapa)
        if caminho_mapa.exists() and not args.forcar:
            print(
                f"\nerro: {caminho_mapa} ja existe (use --forcar para sobrescrever).\n"
                f"O texto tratado FOI gravado em {saida}, mas sem o mapa.",
                file=sys.stderr,
            )
            return 1
        _gravar_mapa(caminho_mapa, resultado, args.arquivo)
        print(f"\nmapa:   {caminho_mapa}")
        print(f"        {AVISO_MAPA}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
