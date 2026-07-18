"""
Detector de PIS/PASEP/NIT/NIS.

Sao quatro nomes para numeros de 11 digitos que compartilham o mesmo algoritmo
de digito verificador (modulo 11, pesos 3,2,9,8,7,6,5,4,3,2). O detector
devolve todos com o tipo "PIS".

ATENCAO A COLISAO DE 11 DIGITOS: CPF, PIS e CNH tem todos 11 digitos, e um
mesmo numero cru pode passar em mais de um checksum -- sao contas diferentes
sobre entradas do mesmo tamanho. Isso NAO e um problema de seguranca: qualquer
detector que ganhe a disputa, o numero acaba redigido. O desempate (ver
anonimizador/deteccao.py, PRIORIDADE_TIPO) so decide qual rotulo aparece no
lugar do numero.
"""

from __future__ import annotations

import re

from anonimizador.deteccao import Confianca, Deteccao, somente_digitos

__all__ = ["PADRAO_PIS", "pis_valido", "detectar_pis"]

# Formato usual com mascara: 123.45678.90-0
PADRAO_PIS = re.compile(r"\b(\d{3}\.?\d{5}\.?\d{2}-?\d{1})\b")

PESOS = (3, 2, 9, 8, 7, 6, 5, 4, 3, 2)


def pis_valido(pis: str) -> bool:
    """Valida PIS/PASEP/NIT pelo digito verificador."""
    d = somente_digitos(pis)

    if len(d) != 11:
        return False

    if d == d[0] * 11:
        return False

    soma = sum(int(digito) * peso for digito, peso in zip(d[:10], PESOS))
    resto = soma % 11
    dv = 11 - resto
    if dv >= 10:  # cobre resto 0 (dv 11) e resto 1 (dv 10)
        dv = 0

    return int(d[10]) == dv


def detectar_pis(texto: str) -> list[Deteccao]:
    """Encontra todos os PIS/PASEP/NIT validos em um texto."""
    deteccoes = []
    for match in PADRAO_PIS.finditer(texto):
        candidato = match.group(1)
        if pis_valido(candidato):
            deteccoes.append(
                Deteccao(
                    texto=candidato,
                    inicio=match.start(1),
                    fim=match.end(1),
                    tipo="PIS",
                    confianca=Confianca.ALTA,
                    detector="pis",
                )
            )
    return deteccoes
