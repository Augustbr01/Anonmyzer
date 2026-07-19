"""
Detector de telefone brasileiro (fixo e celular).

Telefone nao tem digito verificador, mas tem ESTRUTURA suficiente para servir
de filtro -- e e isso que este modulo usa no lugar do checksum:

  - o DDD tem que existir de verdade (a lista oficial nao cobre 20, 23, 25,
    26, 29, 30, 36, 39, 40, 50, 52, 56-60, 70, 72, 76, 78, 80, 90);
  - celular tem 9 digitos e comeca obrigatoriamente com 9;
  - fixo tem 8 digitos e comeca com 2, 3, 4 ou 5.

Na pratica isso descarta bem: um CPF cru como "11144477735" tem DDD 11
(valido), mas o proximo digito e 1 -- nao e 9 nem 2-5, entao nao passa.

>>> COLISAO COM DOCUMENTOS: celular com DDD tem 11 digitos, mesmo tamanho de
>>> CPF/PIS/CNH. Numero cru que passe nos dois pode sair rotulado como
>>> documento em vez de telefone. Nao afeta a seguranca -- o trecho e redigido
>>> de qualquer forma; muda so o rotulo (ver PRIORIDADE_TIPO em deteccao.py).

0800 e afins ficam de fora de proposito: sao linhas publicas de empresa, nao
dado pessoal, e redigi-las so tiraria informacao util do documento.
"""

from __future__ import annotations

import re

from anonimizador.deteccao import Confianca, Deteccao, somente_digitos, tem_palavra_chave

__all__ = [
    "DDDS_VALIDOS",
    "PALAVRAS_CHAVE",
    "PADRAO_TELEFONE",
    "PADRAO_TELEFONE_LOCAL",
    "telefone_valido",
    "detectar_telefones",
]

# Lista oficial de DDDs em uso no Brasil.
DDDS_VALIDOS = frozenset(
    [11, 12, 13, 14, 15, 16, 17, 18, 19]          # SP
    + [21, 22, 24, 27, 28]                        # RJ / ES
    + [31, 32, 33, 34, 35, 37, 38]                # MG
    + [41, 42, 43, 44, 45, 46, 47, 48, 49]        # PR / SC
    + [51, 53, 54, 55]                            # RS
    + [61, 62, 63, 64, 65, 66, 67, 68, 69]        # Centro-Oeste / AC / RO
    + [71, 73, 74, 75, 77, 79]                    # BA / SE
    + [81, 82, 83, 84, 85, 86, 87, 88, 89]        # Nordeste
    + [91, 92, 93, 94, 95, 96, 97, 98, 99]        # Norte / MA
)

PALAVRAS_CHAVE = (
    "telefone", "tel", "fone", "celular", "cel", "whatsapp", "whats",
    "contato", "recado", "ramal", "movel",
)

# Regex permissivo de proposito -- quem filtra e `telefone_valido`, na mesma
# logica do CPF (formato solto + validacao depois).
# As ancoras impedem casar no meio de um numero maior.
PADRAO_TELEFONE = re.compile(
    r"(?<![\w-])"
    r"((?:\+?55[\s.-]?)?(?:\(\d{2}\)|\d{2})[\s.-]?\d{4,5}[\s.-]?\d{4})"
    r"(?![\w-])"
)

# Numero local, sem DDD. So vale com palavra-chave por perto: sem o DDD nao
# sobra estrutura suficiente para separar de qualquer outro numero de 8-9
# digitos do documento.
PADRAO_TELEFONE_LOCAL = re.compile(r"(?<![\w-])(9?\d{4}[\s.-]?\d{4})(?![\w-])")

JANELA_CONTEXTO = 40


def telefone_valido(numero: str) -> bool:
    """Valida um telefone pela estrutura: DDD real + prefixo coerente."""
    d = somente_digitos(numero)

    # Codigo do pais opcional.
    if len(d) in (12, 13) and d.startswith("55"):
        d = d[2:]

    if len(d) == 11:                      # DDD + celular
        return int(d[:2]) in DDDS_VALIDOS and d[2] == "9"

    if len(d) == 10:                      # DDD + fixo
        return int(d[:2]) in DDDS_VALIDOS and d[2] in "2345"

    return False


def _local_valido(numero: str) -> bool:
    """Valida numero sem DDD (8 ou 9 digitos)."""
    d = somente_digitos(numero)
    if len(d) == 9:
        return d[0] == "9"
    if len(d) == 8:
        return d[0] in "2345"
    return False


def detectar_telefones(texto: str, janela: int = JANELA_CONTEXTO) -> list[Deteccao]:
    """Encontra telefones em um texto."""
    deteccoes: list[Deteccao] = []

    for match in PADRAO_TELEFONE.finditer(texto):
        if telefone_valido(match.group(1)):
            deteccoes.append(
                Deteccao(
                    texto=match.group(1),
                    inicio=match.start(1),
                    fim=match.end(1),
                    tipo="TELEFONE",
                    confianca=Confianca.ALTA,
                    detector="telefone",
                )
            )

    for match in PADRAO_TELEFONE_LOCAL.finditer(texto):
        inicio, fim = match.start(1), match.end(1)

        # O padrao local tambem casa o miolo de um numero completo ja
        # detectado ("(11) 98765-4321" contem "98765-4321"). Sem esta guarda
        # sairiam duas deteccoes encavaladas para o mesmo telefone.
        if any(inicio < d.fim and d.inicio < fim for d in deteccoes):
            continue

        if not _local_valido(match.group(1)):
            continue

        if tem_palavra_chave(texto, inicio, PALAVRAS_CHAVE, janela):
            deteccoes.append(
                Deteccao(
                    texto=match.group(1),
                    inicio=inicio,
                    fim=fim,
                    tipo="TELEFONE",
                    confianca=Confianca.MEDIA,
                    detector="telefone:local",
                )
            )

    return sorted(deteccoes, key=lambda d: d.inicio)
