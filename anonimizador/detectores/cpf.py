"""
Detector de CPF.

CPF segue um algoritmo deterministico (modulo 11 nos dois ultimos digitos),
entao diferente de nomes, aqui nao precisamos de IA/NER -- regex + validacao
matematica ja resolve com confiabilidade praticamente total.

Isso evita falsos positivos comuns: numeros de pedido, protocolo, telefone
com 11 digitos que nao sao CPF valido sao descartados pela validacao.
"""

from __future__ import annotations

import re

from anonimizador.deteccao import Confianca, Deteccao, somente_digitos

# `Deteccao` foi movida para anonimizador/deteccao.py (todo detector precisa
# dela). Reexportada aqui para nao quebrar imports que apontem para este modulo.
__all__ = ["Deteccao", "PADRAO_CPF", "cpf_valido", "detectar_cpfs"]

PADRAO_CPF = re.compile(r"\b(\d{3}\.?\d{3}\.?\d{3}-?\d{2})\b")


def cpf_valido(cpf: str) -> bool:
    """Valida CPF pelo algoritmo oficial dos digitos verificadores."""
    digitos = somente_digitos(cpf)

    if len(digitos) != 11:
        return False

    if digitos == digitos[0] * 11:
        return False

    def calcula_digito(cpf_parcial: str) -> int:
        peso = len(cpf_parcial) + 1
        soma = sum(int(d) * (peso - i) for i, d in enumerate(cpf_parcial))
        resto = (soma * 10) % 11
        return 0 if resto == 10 else resto

    primeiro_digito = calcula_digito(digitos[:9])
    segundo_digito = calcula_digito(digitos[:9] + str(primeiro_digito))

    return digitos[-2:] == f"{primeiro_digito}{segundo_digito}"


def detectar_cpfs(texto: str) -> list[Deteccao]:
    """Encontra todos os CPFs validos em um texto."""
    deteccoes = []
    for match in PADRAO_CPF.finditer(texto):
        candidato = match.group(1)
        if cpf_valido(candidato):
            deteccoes.append(
                Deteccao(
                    texto=candidato,
                    inicio=match.start(1),
                    fim=match.end(1),
                    tipo="CPF",
                    confianca=Confianca.ALTA,
                    detector="cpf",
                )
            )
    return deteccoes
