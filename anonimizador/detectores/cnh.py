"""
Detector de CNH (numero de registro da Carteira Nacional de Habilitacao).

11 digitos com dois verificadores. O algoritmo tem uma particularidade que
nenhum dos outros documentos tem: quando o primeiro DV "estoura" (resto 10),
alem de virar 0 ele aplica um DESCONTO de 2 no segundo DV. Se esse desconto
levar o segundo DV para negativo, soma-se 11.

Ver nota sobre colisao de numeros de 11 digitos em detectores/pis.py.
"""

from __future__ import annotations

import re

from anonimizador.deteccao import Confianca, Deteccao, somente_digitos

__all__ = ["PADRAO_CNH", "cnh_valida", "detectar_cnhs"]

# CNH normalmente aparece sem mascara.
PADRAO_CNH = re.compile(r"\b(\d{11})\b")


def cnh_valida(cnh: str) -> bool:
    """Valida numero de registro de CNH pelos digitos verificadores."""
    d = somente_digitos(cnh)

    if len(d) != 11:
        return False

    if d == d[0] * 11:
        return False

    base = d[:9]

    # DV1: pesos decrescentes 9..1.
    soma1 = sum(int(base[i]) * (9 - i) for i in range(9))
    resto1 = soma1 % 11
    if resto1 >= 10:
        dv1 = 0
        desconto = 2
    else:
        dv1 = resto1
        desconto = 0

    # DV2: pesos crescentes 1..9, menos o desconto herdado do DV1.
    soma2 = sum(int(base[i]) * (i + 1) for i in range(9))
    resto2 = soma2 % 11
    dv2 = 0 if resto2 >= 10 else resto2
    dv2 -= desconto
    if dv2 < 0:
        dv2 += 11

    return int(d[9]) == dv1 and int(d[10]) == dv2


def detectar_cnhs(texto: str) -> list[Deteccao]:
    """Encontra todos os numeros de CNH validos em um texto."""
    deteccoes = []
    for match in PADRAO_CNH.finditer(texto):
        candidato = match.group(1)
        if cnh_valida(candidato):
            deteccoes.append(
                Deteccao(
                    texto=candidato,
                    inicio=match.start(1),
                    fim=match.end(1),
                    tipo="CNH",
                    confianca=Confianca.ALTA,
                    detector="cnh",
                )
            )
    return deteccoes
