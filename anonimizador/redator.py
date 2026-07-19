"""
Redator: aplica as substituicoes no texto conforme o modo escolhido.

MODO PSEUDONIMO
    Cada valor distinto vira um token estavel (PESSOA_001, CPF_001). A MESMA
    pessoa citada varias vezes recebe sempre o mesmo token, entao o texto
    continua fazendo sentido -- da para saber que duas mencoes sao da mesma
    pessoa. Gera o mapa de-para.

    >>> O MAPA REVERTE A PSEUDONIMIZACAO. Ele precisa do mesmo cuidado que o
    >>> documento original: se vazar junto com o texto redigido, a protecao
    >>> acabou. Guarde separado, ou apague depois de usar.

MODO ANONIMO
    Cada ocorrencia vira um marcador generico por tipo ([NOME], [CPF]), SEM
    vinculo entre ocorrencias -- duas mencoes da mesma pessoa viram dois
    [NOME] independentes. Nao gera mapa. Irreversivel, inclusive por
    correlacao entre mencoes. E o modo para compartilhar documento.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum

from anonimizador.deteccao import Deteccao, somente_digitos

__all__ = ["Modo", "MARCADORES", "PREFIXOS_TOKEN", "EntradaMapa", "Resultado", "redigir"]


class Modo(str, Enum):
    PSEUDONIMO = "pseudonimo"
    ANONIMO = "anonimo"


# Marcador generico usado no modo anonimo.
MARCADORES = {
    "NOME": "[NOME]",
    "CPF": "[CPF]",
    "CNPJ": "[CNPJ]",
    "RG": "[RG]",
    "CNH": "[CNH]",
    "PIS": "[PIS]",
    "TITULO_ELEITOR": "[TITULO_ELEITOR]",
    "PASSAPORTE": "[PASSAPORTE]",
    "EMAIL": "[EMAIL]",
    "TELEFONE": "[TELEFONE]",
    "ENDERECO": "[ENDERECO]",
    "CEP": "[CEP]",
}

# Prefixo do token no modo pseudonimo.
PREFIXOS_TOKEN = {
    "NOME": "PESSOA",
    "CPF": "CPF",
    "CNPJ": "CNPJ",
    "RG": "RG",
    "CNH": "CNH",
    "PIS": "PIS",
    "TITULO_ELEITOR": "TITULO",
    "PASSAPORTE": "PASSAPORTE",
    "EMAIL": "EMAIL",
    "TELEFONE": "TELEFONE",
    "ENDERECO": "ENDERECO",
    "CEP": "CEP",
}


@dataclass
class EntradaMapa:
    """Uma linha do mapa de-para (so existe no modo pseudonimo)."""

    token: str
    valor: str
    tipo: str
    ocorrencias: int = 0


@dataclass
class Resultado:
    texto: str
    mapa: list[EntradaMapa] = field(default_factory=list)
    deteccoes: list[Deteccao] = field(default_factory=list)

    @property
    def total_substituicoes(self) -> int:
        return len(self.deteccoes)

    def contagem_por_tipo(self) -> dict[str, int]:
        contagem: dict[str, int] = {}
        for deteccao in self.deteccoes:
            contagem[deteccao.tipo] = contagem.get(deteccao.tipo, 0) + 1
        return dict(sorted(contagem.items()))


def _chave(tipo: str, texto: str) -> str:
    """
    Normaliza um valor para decidir se duas ocorrencias sao "a mesma coisa".

    Sem isso, "123.456.789-09" e "12345678909" ganhariam tokens diferentes
    apesar de serem o mesmo CPF, e o texto pseudonimizado sugeriria duas
    pessoas onde ha uma.

    LIMITACAO CONHECIDA em nomes: a comparacao e por texto normalizado, entao
    "Joao da Silva" e "Joao" recebem tokens diferentes mesmo sendo a mesma
    pessoa. Resolver isso exigiria ligacao de correferencia, que esta fora do
    escopo atual. O erro e na direcao segura -- separa demais, nunca junta
    pessoas distintas sob o mesmo token.

    CUIDADO AO ACRESCENTAR TIPO NOVO: o ramo final ("so digitos") e destrutivo
    para qualquer tipo textual -- um e-mail viraria chave vazia e TODOS os
    e-mails do documento colapsariam num unico token. Tipo com letra precisa
    de ramo proprio aqui.
    """
    if tipo in {"NOME", "ENDERECO"}:  # texto livre
        sem_acento = unicodedata.normalize("NFKD", texto)
        sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
        return re.sub(r"\s+", " ", sem_acento).strip().lower()

    if tipo == "EMAIL":
        return texto.strip().lower()

    if tipo == "TELEFONE":
        # "+55 11 98765-4321" e "11987654321" sao o mesmo telefone.
        digitos = somente_digitos(texto)
        if len(digitos) in (12, 13) and digitos.startswith("55"):
            digitos = digitos[2:]
        return digitos

    if tipo in {"CNPJ", "PASSAPORTE"}:  # podem ter letras
        return re.sub(r"[^A-Za-z0-9]", "", texto).upper()

    return somente_digitos(texto)


def redigir(
    texto: str,
    deteccoes: list[Deteccao],
    modo: Modo = Modo.ANONIMO,
) -> Resultado:
    """
    Aplica as substituicoes e devolve o texto tratado.

    Espera deteccoes SEM sobreposicao (use
    `deteccao.resolver_sobreposicoes`, ja aplicado por
    `detectores.detectar_tudo`). Sobreposicao aqui produziria texto corrompido.
    """
    modo = Modo(modo)
    ordenadas = sorted(deteccoes, key=lambda d: d.inicio)

    for anterior, atual in zip(ordenadas, ordenadas[1:]):
        if anterior.fim > atual.inicio:
            raise ValueError(
                "deteccoes sobrepostas chegaram ao redator "
                f"({anterior.texto!r} e {atual.texto!r}) -- "
                "chame resolver_sobreposicoes antes"
            )

    entradas: dict[tuple[str, str], EntradaMapa] = {}
    contadores: dict[str, int] = {}
    substituicoes: list[tuple[int, int, str]] = []

    for deteccao in ordenadas:
        if modo is Modo.ANONIMO:
            # Marcador generico, sem estado: duas mencoes da mesma pessoa
            # produzem dois marcadores sem vinculo entre si.
            troca = MARCADORES.get(deteccao.tipo, f"[{deteccao.tipo}]")
        else:
            chave = (deteccao.tipo, _chave(deteccao.tipo, deteccao.texto))
            entrada = entradas.get(chave)
            if entrada is None:
                prefixo = PREFIXOS_TOKEN.get(deteccao.tipo, deteccao.tipo)
                contadores[prefixo] = contadores.get(prefixo, 0) + 1
                entrada = EntradaMapa(
                    token=f"{prefixo}_{contadores[prefixo]:03d}",
                    valor=deteccao.texto,
                    tipo=deteccao.tipo,
                )
                entradas[chave] = entrada
            entrada.ocorrencias += 1
            troca = entrada.token

        substituicoes.append((deteccao.inicio, deteccao.fim, troca))

    # De tras para frente: substituir da direita para a esquerda mantem
    # validos os offsets das deteccoes ainda nao aplicadas.
    partes = list(texto)
    for inicio, fim, troca in reversed(substituicoes):
        partes[inicio:fim] = troca

    return Resultado(
        texto="".join(partes),
        mapa=list(entradas.values()) if modo is Modo.PSEUDONIMO else [],
        deteccoes=ordenadas,
    )
