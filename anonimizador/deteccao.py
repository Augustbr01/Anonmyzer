"""
Tipos e utilitarios compartilhados por todos os detectores.

`Deteccao` mora aqui (e nao em detectores/cpf.py) porque todo detector precisa
dela: manter no cpf.py obrigaria cnpj.py, nomes.py etc. a importar do detector
de CPF, o que nao faz sentido. `detectores/cpf.py` reexporta o nome, entao
`from anonimizador.detectores.cpf import Deteccao` continua funcionando.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import IntEnum


class Confianca(IntEnum):
    """
    Quanta certeza o detector tem de que aquilo e mesmo um dado pessoal.

    Usada para desempatar sobreposicoes (ver `resolver_sobreposicoes`) e para
    o relatorio no fim da execucao. NAO e usada para descartar deteccoes: pelo
    principio de calibracao do projeto, deteccao de baixa confianca ainda e
    redigida -- falso positivo custa menos que falso negativo.
    """

    BAIXA = 1   # so formato/regex, sem checksum (RG, passaporte)
    MEDIA = 2   # checksum fraco, ou heuristica com contexto forte
    ALTA = 3    # digito verificador matematico, ou NER com contexto


# Desempate final entre deteccoes de mesma confianca e mesmo tamanho.
# O caso real: um numero "cru" de 11 digitos pode passar no checksum de CPF,
# de PIS e de CNH ao mesmo tempo -- sao algoritmos diferentes sobre o mesmo
# tamanho de entrada. Qualquer um que ganhe, o numero e redigido do mesmo
# jeito; a ordem abaixo so decide qual ROTULO aparece no lugar.
PRIORIDADE_TIPO = {
    "CPF": 100,
    "CNPJ": 95,
    "TITULO_ELEITOR": 90,
    "CNH": 85,
    "PIS": 80,
    "NOME": 70,
    "RG": 60,
    "PASSAPORTE": 55,
}


@dataclass(frozen=True)
class Deteccao:
    """
    Um trecho do texto identificado como dado pessoal.

    `inicio`/`fim` sao offsets em caracteres no texto original, no padrao de
    slice do Python: texto[inicio:fim] == texto. O redator depende disso.

    Imutavel (frozen) de proposito: deteccao e um valor, nao um objeto com
    ciclo de vida. Isso tambem a torna hashable, o que permite deduplicar com
    set() quando dois detectores acham exatamente a mesma coisa.
    """

    texto: str
    inicio: int
    fim: int
    tipo: str
    confianca: Confianca = Confianca.ALTA
    detector: str = ""

    def __post_init__(self) -> None:
        if self.inicio < 0 or self.fim < self.inicio:
            raise ValueError(f"offsets invalidos: inicio={self.inicio} fim={self.fim}")

    @property
    def comprimento(self) -> int:
        return self.fim - self.inicio

    def sobrepoe(self, outra: "Deteccao") -> bool:
        return self.inicio < outra.fim and outra.inicio < self.fim


# --------------------------------------------------------------------------
# Utilitarios de texto
# --------------------------------------------------------------------------

def normalizar(texto: str) -> str:
    """Minusculas e sem acentos -- para comparar palavra-chave com o texto."""
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return sem_acento.lower()


def somente_digitos(s: str) -> str:
    return re.sub(r"\D", "", s)


def contexto_anterior(texto: str, inicio: int, janela: int = 40) -> str:
    """Os `janela` caracteres imediatamente antes de uma deteccao."""
    return texto[max(0, inicio - janela) : inicio]


def tem_palavra_chave(
    texto: str,
    inicio: int,
    palavras: tuple[str, ...],
    janela: int = 40,
) -> bool:
    """
    Diz se alguma das `palavras` aparece logo antes da posicao `inicio`.

    E o que separa "RG: 12.345.678-9" (quase certamente um RG) de um numero
    solto de 9 digitos que por acaso tem o mesmo formato. Comparacao ignora
    acento e caixa, entao "n° do orgao" casa com "orgao"/"ORGAO"/"órgão".
    """
    trecho = normalizar(contexto_anterior(texto, inicio, janela))
    return any(normalizar(p) in trecho for p in palavras)


# --------------------------------------------------------------------------
# Uniao de deteccoes
# --------------------------------------------------------------------------

def resolver_sobreposicoes(deteccoes: list[Deteccao]) -> list[Deteccao]:
    """
    Resolve deteccoes que disputam o mesmo trecho do texto, mantendo uma so.

    Necessario porque o projeto usa UNIAO de detectores (nunca intersecao):
    varios detectores rodam sobre o mesmo texto e e normal dois apontarem para
    o mesmo trecho, ou para trechos que se cruzam parcialmente. Redigir os dois
    corromperia os offsets do redator.

    Criterio, nesta ordem:
      1. maior confianca;
      2. maior trecho (prefere "Joao da Silva" a "Joao");
      3. prioridade do tipo (tabela PRIORIDADE_TIPO);
      4. posicao no texto, so para o resultado ser deterministico.

    Nada e descartado por ser "fraco demais" -- so por perder uma disputa
    direta por posicao, e nesse caso o trecho segue redigido pela vencedora.
    """
    ordenadas = sorted(
        deteccoes,
        key=lambda d: (
            d.confianca,
            d.comprimento,
            PRIORIDADE_TIPO.get(d.tipo, 0),
            -d.inicio,
        ),
        reverse=True,
    )

    aceitas: list[Deteccao] = []
    for candidata in ordenadas:
        if not any(candidata.sobrepoe(ja) for ja in aceitas):
            aceitas.append(candidata)

    return sorted(aceitas, key=lambda d: d.inicio)
