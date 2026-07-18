"""
Detector de Passaporte -- DETECCAO DE MENOR CONFIANCA.

>>> ATENCAO: passaporte NAO tem digito verificador validavel de forma simples.
>>> O passaporte brasileiro segue o padrao de 2 letras + 6 digits (ex.: FZ123456),
>>> mas passaportes estrangeiros que aparecam no documento podem ter qualquer
>>> outro formato. Como no RG, aqui so ha reconhecimento de FORMATO.

Duas faixas, mesma logica do detector de RG:

  1. padrao brasileiro (2 letras MAIUSCULAS + 6 digitos), detectado sozinho --
     confianca BAIXA. Exige maiuscula justamente para nao casar com codigo de
     produto ou referencia escritos em caixa mista;
  2. qualquer sequencia letras+digitos de 6 a 9 caracteres COM palavra-chave
     por perto ("Passaporte n."), o que cobre passaporte estrangeiro --
     confianca MEDIA.
"""

from __future__ import annotations

import re

from anonimizador.deteccao import Confianca, Deteccao, tem_palavra_chave

__all__ = [
    "PALAVRAS_CHAVE",
    "PADRAO_PASSAPORTE_BR",
    "PADRAO_PASSAPORTE_CONTEXTO",
    "detectar_passaportes",
]

PALAVRAS_CHAVE = (
    "passaporte",
    "passport",
    "documento de viagem",
    "travel document",
)

# Faixa 1 -- padrao brasileiro, so maiusculas.
PADRAO_PASSAPORTE_BR = re.compile(r"\b([A-Z]{2}\d{6})\b")

# Faixa 2 -- formato generico, so aceito quando ha palavra-chave por perto.
PADRAO_PASSAPORTE_CONTEXTO = re.compile(r"\b([A-Za-z]{1,3}\d{5,8})\b")

JANELA_CONTEXTO = 40


def detectar_passaportes(texto: str, janela: int = JANELA_CONTEXTO) -> list[Deteccao]:
    """
    Encontra numeros de passaporte em um texto.

    Nao ha validacao matematica possivel -- ver aviso no topo do modulo.
    """
    deteccoes: list[Deteccao] = []
    ja_vistos: set[tuple[int, int]] = set()

    def registrar(match: re.Match, confianca: Confianca) -> None:
        posicao = (match.start(1), match.end(1))
        if posicao in ja_vistos:
            return
        ja_vistos.add(posicao)
        deteccoes.append(
            Deteccao(
                texto=match.group(1),
                inicio=posicao[0],
                fim=posicao[1],
                tipo="PASSAPORTE",
                confianca=confianca,
                detector="passaporte",
            )
        )

    for match in PADRAO_PASSAPORTE_BR.finditer(texto):
        com_contexto = tem_palavra_chave(texto, match.start(1), PALAVRAS_CHAVE, janela)
        registrar(match, Confianca.MEDIA if com_contexto else Confianca.BAIXA)

    for match in PADRAO_PASSAPORTE_CONTEXTO.finditer(texto):
        if tem_palavra_chave(texto, match.start(1), PALAVRAS_CHAVE, janela):
            registrar(match, Confianca.MEDIA)

    return deteccoes
