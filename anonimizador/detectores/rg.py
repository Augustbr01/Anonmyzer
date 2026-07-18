"""
Detector de RG -- DETECCAO DE MENOR CONFIANCA.

>>> ATENCAO: diferente de CPF/CNPJ/PIS/CNH/titulo, o RG NAO TEM digito
>>> verificador nacional padronizado. O formato e definido por cada orgao
>>> emissor estadual e nao existe checksum publico universal que sirva para
>>> validar. Tudo que este modulo faz e reconhecer FORMATO -- nao ha como
>>> confirmar matematicamente que o numero encontrado e mesmo um RG.

Consequencia direta: aqui o risco de FALSO NEGATIVO e real (um RG em formato
estadual incomum simplesmente nao casa com os padroes abaixo), coisa que nao
acontece nos detectores com checksum. Se o documento tratado for critico, vale
conferir o resultado manualmente ou rodar com --agressivo.

Para nao poluir o texto redigindo todo numero de 8 digitos que aparece, o
detector trabalha em duas faixas:

  1. numero MASCARADO (12.345.678-9): formato distinto o bastante para ser
     detectado sozinho, sem depender de contexto -- confianca BAIXA;
  2. numero SOLTO (7 a 9 digitos): so vira deteccao se houver palavra-chave
     por perto ("RG:", "Identidade", "SSP") -- confianca MEDIA, porque o
     contexto compensa a ausencia de checksum.

Numero solto SEM contexto e ignorado de proposito: qualquer numero de pedido,
protocolo ou matricula cairia nessa faixa, e redigir tudo tornaria o documento
inutil sem ganho real de privacidade.
"""

from __future__ import annotations

import re

from anonimizador.deteccao import Confianca, Deteccao, tem_palavra_chave

__all__ = ["PALAVRAS_CHAVE", "PADRAO_RG_MASCARADO", "PADRAO_RG_SOLTO", "detectar_rgs"]

# Termos que costumam anteceder um numero de RG no documento. Comparacao
# ignora acento e caixa (ver deteccao.tem_palavra_chave).
PALAVRAS_CHAVE = (
    "rg",
    "r.g.",
    "registro geral",
    "identidade",
    "cedula de identidade",
    "carteira de identidade",
    "orgao emissor",
    "orgao expedidor",
    "expedidor",
    "ssp",
    "detran",
    "ifp",
    "sds",
)

# Faixa 1 -- com mascara: 12.345.678-9 (DV pode ser digito ou X).
PADRAO_RG_MASCARADO = re.compile(r"\b(\d{1,2}\.\d{3}\.\d{3}-?[\dXx])\b")

# Faixa 2 -- solto: 7 a 9 digitos, com DV opcional. So usado com contexto.
PADRAO_RG_SOLTO = re.compile(r"\b(\d{7,9}-?[\dXx]?)\b")

JANELA_CONTEXTO = 40


def detectar_rgs(texto: str, janela: int = JANELA_CONTEXTO) -> list[Deteccao]:
    """
    Encontra numeros de RG em um texto.

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
                tipo="RG",
                confianca=confianca,
                detector="rg",
            )
        )

    for match in PADRAO_RG_MASCARADO.finditer(texto):
        com_contexto = tem_palavra_chave(texto, match.start(1), PALAVRAS_CHAVE, janela)
        registrar(match, Confianca.MEDIA if com_contexto else Confianca.BAIXA)

    for match in PADRAO_RG_SOLTO.finditer(texto):
        if tem_palavra_chave(texto, match.start(1), PALAVRAS_CHAVE, janela):
            registrar(match, Confianca.MEDIA)

    return deteccoes
