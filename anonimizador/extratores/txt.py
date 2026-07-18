"""
Extrator de arquivos de texto puro.

O unico ponto nao-trivial aqui e a CODIFICACAO. Documento brasileiro exportado
de sistema antigo costuma vir em cp1252/latin-1, e ler isso como UTF-8 falha
ou corrompe justamente os acentos -- que aparecem em nome de pessoa. Um nome
corrompido na leitura nao e detectado pelo NER, ou seja, erro de encoding
vira vazamento de dado. Por isso tentamos varias codificacoes em ordem.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["CODIFICACOES", "extrair_txt", "ler_texto"]

# Ordem importa: UTF-8 primeiro (falha alto se o arquivo nao for UTF-8, o que
# e o que queremos); cp1252 antes de latin-1 porque cp1252 e o padrao do
# Windows pt-BR e cobre aspas/travessao que latin-1 nao tem. latin-1 fica por
# ultimo como rede de seguranca: ele aceita qualquer byte e nunca falha.
CODIFICACOES = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


def ler_texto(caminho: Path, codificacoes: tuple[str, ...] = CODIFICACOES) -> str:
    """Le um arquivo tentando as codificacoes em ordem."""
    if not caminho.is_file():
        raise FileNotFoundError(f"Arquivo nao encontrado: {caminho}")

    bytes_lidos = caminho.read_bytes()

    for codificacao in codificacoes:
        try:
            return bytes_lidos.decode(codificacao)
        except UnicodeDecodeError:
            continue

    # Inalcancavel enquanto latin-1 estiver na lista, mas deixa o erro
    # explicito caso alguem mude CODIFICACOES.
    raise UnicodeDecodeError(
        "anonimizador", bytes_lidos, 0, len(bytes_lidos),
        f"nenhuma das codificacoes funcionou: {codificacoes}",
    )


def extrair_txt(caminho: Path) -> str:
    """Extrai o texto de um .txt."""
    return ler_texto(caminho)
