"""
Detector de CNPJ -- formato numerico legado E formato alfanumerico (2026).

A Instrucao Normativa RFB n. 2.229/2024 introduz, a partir de julho/2026, o
CNPJ ALFANUMERICO:

    - as 12 primeiras posicoes passam a aceitar letras maiusculas (A-Z) alem
      de digitos;
    - os 2 digitos verificadores finais continuam SEMPRE numericos;
    - o calculo do DV continua em modulo 11, mas cada caractere e convertido
      pelo seu valor ASCII menos 48 antes de entrar na conta
      ('0' -> 0, '9' -> 9, 'A' -> 17, 'Z' -> 42);
    - CNPJs antigos (so numericos) continuam validos e nao mudam -- note que
      para digitos "ASCII menos 48" da exatamente o valor do digito, ou seja,
      e o mesmo algoritmo de sempre, generalizado.

Consequencia pratica para este detector: usar regex de digitos (\\d{14}) aqui
deixaria passar todo CNPJ novo sem detectar -- exatamente o falso negativo que
o projeto trata como pior caso. Por isso o padrao aceita [A-Z0-9] nas 12
primeiras posicoes.
"""

from __future__ import annotations

import re

from anonimizador.deteccao import Confianca, Deteccao

__all__ = ["PADRAO_CNPJ", "cnpj_valido", "detectar_cnpjs"]

# 12 posicoes alfanumericas + 2 DVs numericos, com separadores opcionais.
# IGNORECASE porque um CNPJ digitado em minusculas continua sendo um CNPJ real
# no documento -- normalizamos para maiuscula antes de validar (ver abaixo).
PADRAO_CNPJ = re.compile(
    r"\b([A-Z0-9]{2}\.?[A-Z0-9]{3}\.?[A-Z0-9]{3}/?[A-Z0-9]{4}-?\d{2})\b",
    re.IGNORECASE,
)

# Pesos do modulo 11, identicos aos do CNPJ numerico classico.
PESOS_DV1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
PESOS_DV2 = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)


def _limpar(cnpj: str) -> str:
    """Remove separadores e normaliza para maiuscula."""
    return re.sub(r"[^A-Za-z0-9]", "", cnpj).upper()


def _valor(caractere: str) -> int:
    """
    Converte um caractere para o valor usado no modulo 11.

    Regra da IN 2.229/2024: ASCII do caractere menos 48. Para digitos isso
    devolve o proprio digito ('7' = 55 - 48 = 7), o que mantem os CNPJs
    numericos antigos validando exatamente como antes.
    """
    return ord(caractere) - 48


def _calcula_digito(base: str, pesos: tuple[int, ...]) -> int:
    soma = sum(_valor(c) * p for c, p in zip(base, pesos))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def cnpj_valido(cnpj: str) -> bool:
    """
    Valida CNPJ nos dois formatos (numerico legado e alfanumerico novo).

    Aceita com ou sem mascara: "12.ABC.345/01DE-35" e "12ABC34501DE35" sao
    tratados igual.
    """
    limpo = _limpar(cnpj)

    if len(limpo) != 14:
        return False

    # Os dois DVs finais sao numericos em qualquer um dos formatos.
    if not limpo[12:].isdigit():
        return False

    # As 12 primeiras posicoes so aceitam A-Z e 0-9.
    if not re.fullmatch(r"[A-Z0-9]{12}", limpo[:12]):
        return False

    # Repeticao total ("00000000000000") passa no modulo 11 mas nao e CNPJ real.
    if limpo == limpo[0] * 14:
        return False

    dv1 = _calcula_digito(limpo[:12], PESOS_DV1)
    dv2 = _calcula_digito(limpo[:12] + str(dv1), PESOS_DV2)

    return limpo[12:] == f"{dv1}{dv2}"


def detectar_cnpjs(texto: str) -> list[Deteccao]:
    """Encontra todos os CNPJs validos em um texto."""
    deteccoes = []
    for match in PADRAO_CNPJ.finditer(texto):
        candidato = match.group(1)
        if cnpj_valido(candidato):
            deteccoes.append(
                Deteccao(
                    texto=candidato,
                    inicio=match.start(1),
                    fim=match.end(1),
                    tipo="CNPJ",
                    confianca=Confianca.ALTA,
                    detector="cnpj",
                )
            )
    return deteccoes
