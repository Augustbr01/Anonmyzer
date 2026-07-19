"""
Detector de endereco (logradouro) e CEP.

>>> DOS TRES DETECTORES NOVOS, ESTE E O MAIS FRACO. Endereco nao tem checksum
>>> nem formato fixo: e texto livre, de tamanho variavel, sem comeco e fim
>>> obviamente delimitados. Aqui nao da para prometer o recall que CPF ou
>>> e-mail entregam.

O que ancora a deteccao e o TIPO DE LOGRADOURO ("Rua", "Avenida", "Praca") na
frente, e o NUMERO no fim. Exigir os dois derruba muito falso positivo, mas
tem um custo assumido: endereco sem numero ("mora na Rua das Flores") ou sem
o tipo na frente ("Flores, 123") NAO e detectado. Sao falsos negativos
conhecidos -- ver "Limitacoes" no README.

Sobre CEP: e a parte confiavel deste modulo. O formato 12345-678 e distinto o
bastante para valer sozinho (nao colide com telefone, que tem 4 digitos depois
do hifen, nem com RG). Ja o CEP sem hifen e so 8 digitos crus, indistinguivel
de qualquer outro numero -- esse so vale com a palavra "CEP" por perto.

CONFIANCA ALTA no logradouro completo, e isso e proposital: nome de rua
costuma ser nome de pessoa ("Rua Joaquim Nabuco, 123"), e o NER marca esse
miolo como PER. Com as duas em ALTA, o desempate cai no tamanho e o endereco
inteiro vence -- que e o que queremos. Se o endereco fosse MEDIA, o NOME
venceria e o texto sairia como "Rua [NOME], 123", vazando rua e numero.
"""

from __future__ import annotations

import re

from anonimizador.deteccao import Confianca, Deteccao, tem_palavra_chave

__all__ = [
    "PADRAO_CEP",
    "PADRAO_CEP_SEM_HIFEN",
    "PADRAO_LOGRADOURO",
    "PALAVRAS_CHAVE_CEP",
    "detectar_enderecos",
]

# Abreviacoes de uma letra so ("R", "Q") ficam de fora: com IGNORECASE elas
# casariam com inicio de palavra demais. As que entram abreviadas exigem o
# ponto.
_TIPOS_LOGRADOURO = (
    r"(?:Rua|R\.|Avenida|Av\.?|Travessa|Trav\.?|Alameda|Al\.|Pra[çc]a|"
    r"Rodovia|Rod\.|Estrada|Largo|Beco|Viela|Quadra|Conjunto|Conj\.|"
    r"Loteamento|Vila|Ch[áa]cara|S[íi]tio|Fazenda|Passagem|Ladeira)"
)

# Complemento opcional, colado no numero: ", apto 45", "- bloco B".
_COMPLEMENTO = (
    r"(?:\s*[-,]\s*(?:apto?|apartamento|ap|casa|bloco|bl|sala|andar|conj|"
    r"cobertura|fundos|lote|quadra)\.?\s*\d{0,5}[A-Za-z]?)?"
)

# Tipo de logradouro + nome + numero (virgula opcional entre nome e numero).
PADRAO_LOGRADOURO = re.compile(
    rf"\b({_TIPOS_LOGRADOURO}\s+[^\n,;:]{{2,60}}?,?\s*"
    rf"(?:n[º°o]?\.?\s*)?\d{{1,6}}[-/]?[A-Za-z]?{_COMPLEMENTO})",
    re.IGNORECASE,
)

# CEP com hifen: formato proprio, detectado sozinho.
PADRAO_CEP = re.compile(r"\b(\d{5}-\d{3})\b")

# CEP sem hifen: 8 digitos crus, so com contexto.
PADRAO_CEP_SEM_HIFEN = re.compile(r"\b(\d{8})\b")

PALAVRAS_CHAVE_CEP = ("cep", "codigo postal", "c.e.p")

JANELA_CONTEXTO = 30


def detectar_enderecos(texto: str, janela: int = JANELA_CONTEXTO) -> list[Deteccao]:
    """Encontra logradouros e CEPs em um texto."""
    deteccoes: list[Deteccao] = []

    for match in PADRAO_LOGRADOURO.finditer(texto):
        trecho = match.group(1).rstrip()
        deteccoes.append(
            Deteccao(
                texto=trecho,
                inicio=match.start(1),
                fim=match.start(1) + len(trecho),
                tipo="ENDERECO",
                confianca=Confianca.ALTA,
                detector="endereco:logradouro",
            )
        )

    for match in PADRAO_CEP.finditer(texto):
        deteccoes.append(
            Deteccao(
                texto=match.group(1),
                inicio=match.start(1),
                fim=match.end(1),
                tipo="CEP",
                confianca=Confianca.ALTA,
                detector="endereco:cep",
            )
        )

    for match in PADRAO_CEP_SEM_HIFEN.finditer(texto):
        if tem_palavra_chave(texto, match.start(1), PALAVRAS_CHAVE_CEP, janela):
            deteccoes.append(
                Deteccao(
                    texto=match.group(1),
                    inicio=match.start(1),
                    fim=match.end(1),
                    tipo="CEP",
                    confianca=Confianca.MEDIA,
                    detector="endereco:cep_sem_hifen",
                )
            )

    return sorted(deteccoes, key=lambda d: d.inicio)
