"""
Detector de Titulo de Eleitor.

Formato: 12 digitos, decompostos em
    - posicoes 1-8  : numero sequencial;
    - posicoes 9-10 : codigo da UF (01 a 28 -- 27 unidades da federacao + 28
                      para titulos emitidos no exterior);
    - posicoes 11-12: digitos verificadores (modulo 11).

Sobre o caso especial SP/MG: as fontes divergem sobre o que fazer quando o
resto da divisao da 0 nas UFs 01 (SP) e 02 (MG) -- parte das implementacoes
usa DV 0, parte usa DV 1. Em vez de escolher uma e arriscar rejeitar titulos
reais, aceitamos AS DUAS possibilidades nesse caso especifico. Isso segue o
principio de calibracao do projeto: um falso positivo a mais custa menos que
deixar vazar um titulo valido.
"""

from __future__ import annotations

import re

from anonimizador.deteccao import Confianca, Deteccao, somente_digitos

__all__ = ["PADRAO_TITULO", "titulo_valido", "detectar_titulos"]

# Titulo e quase sempre escrito corrido; alguns sistemas usam espaco ou ponto
# separando os blocos 4-4-4.
PADRAO_TITULO = re.compile(r"\b(\d{4}[\s.]?\d{4}[\s.]?\d{4})\b")

UFS_CASO_ESPECIAL = {1, 2}  # SP e MG
UF_MINIMA, UF_MAXIMA = 1, 28


def _dvs_aceitos(resto: int, uf_especial: bool) -> set[int]:
    """Valores de DV aceitaveis para um dado resto do modulo 11."""
    aceitos = {0} if resto == 10 else {resto}
    if resto == 0 and uf_especial:
        aceitos.add(1)
    return aceitos


def titulo_valido(titulo: str) -> bool:
    """Valida titulo de eleitor pelos dois digitos verificadores."""
    d = somente_digitos(titulo)

    if len(d) != 12:
        return False

    if d == d[0] * 12:
        return False

    uf = int(d[8:10])
    if not UF_MINIMA <= uf <= UF_MAXIMA:
        return False

    especial = uf in UFS_CASO_ESPECIAL

    # DV1: sequencial (8 primeiros digitos) com pesos 2..9.
    soma1 = sum(int(digito) * peso for digito, peso in zip(d[:8], range(2, 10)))
    if int(d[10]) not in _dvs_aceitos(soma1 % 11, especial):
        return False

    # DV2: codigo da UF com pesos 7 e 8, mais o DV1 com peso 9.
    soma2 = int(d[8]) * 7 + int(d[9]) * 8 + int(d[10]) * 9
    return int(d[11]) in _dvs_aceitos(soma2 % 11, especial)


def detectar_titulos(texto: str) -> list[Deteccao]:
    """Encontra todos os titulos de eleitor validos em um texto."""
    deteccoes = []
    for match in PADRAO_TITULO.finditer(texto):
        candidato = match.group(1)
        if titulo_valido(candidato):
            deteccoes.append(
                Deteccao(
                    texto=candidato,
                    inicio=match.start(1),
                    fim=match.end(1),
                    tipo="TITULO_ELEITOR",
                    confianca=Confianca.ALTA,
                    detector="titulo_eleitor",
                )
            )
    return deteccoes
