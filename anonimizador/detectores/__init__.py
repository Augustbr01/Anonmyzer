"""
Agregador dos detectores.

Roda todos os detectores sobre o mesmo texto e devolve a UNIAO das deteccoes,
com sobreposicoes resolvidas. Nunca intersecao: se um detector acha e outro
nao, o trecho e redigido do mesmo jeito.

Para acrescentar um tipo de documento novo, escreva o modulo seguindo o padrao
de cpf.py e registre a funcao em DETECTORES_DOCUMENTO -- nada mais precisa
mudar (nem o redator, nem o CLI).
"""

from __future__ import annotations

from typing import Any, Callable

from anonimizador.deteccao import Deteccao, resolver_sobreposicoes
from anonimizador.detectores.cnh import detectar_cnhs
from anonimizador.detectores.cnpj import detectar_cnpjs
from anonimizador.detectores.cpf import detectar_cpfs
from anonimizador.detectores.email import detectar_emails
from anonimizador.detectores.endereco import detectar_enderecos
from anonimizador.detectores.passaporte import detectar_passaportes
from anonimizador.detectores.pis import detectar_pis
from anonimizador.detectores.rg import detectar_rgs
from anonimizador.detectores.telefone import detectar_telefones
from anonimizador.detectores.titulo_eleitor import detectar_titulos

__all__ = ["DETECTORES_DOCUMENTO", "detectar_documentos", "detectar_tudo"]

# Detectores que NAO dependem do modelo de NER: assinatura uniforme
# (texto) -> list[Deteccao]. Agrupados por quanto se pode confiar neles.
DETECTORES_DOCUMENTO: dict[str, Callable[[str], list[Deteccao]]] = {
    # digito verificador matematico
    "cpf": detectar_cpfs,
    "cnpj": detectar_cnpjs,
    "titulo_eleitor": detectar_titulos,
    "pis": detectar_pis,
    "cnh": detectar_cnhs,
    # formato inequivoco ou validacao estrutural
    "email": detectar_emails,
    "telefone": detectar_telefones,
    "endereco": detectar_enderecos,
    # so formato, sem checksum (ver aviso nos respectivos modulos)
    "rg": detectar_rgs,
    "passaporte": detectar_passaportes,
}


def detectar_documentos(texto: str) -> list[Deteccao]:
    """Roda so os detectores que nao precisam do modelo de NER."""
    deteccoes: list[Deteccao] = []
    for detectar in DETECTORES_DOCUMENTO.values():
        deteccoes.extend(detectar(texto))
    return deteccoes


def detectar_tudo(
    texto: str,
    *,
    incluir_nomes: bool = True,
    modelo: Any | None = None,
    agressivo: bool = False,
) -> list[Deteccao]:
    """
    Roda todos os detectores e devolve a lista final, ja sem sobreposicao.

    O resultado vem ordenado por posicao no texto, que e o que o redator
    espera. `incluir_nomes=False` pula o NER -- util para processar so
    documentos sem pagar o custo de carregar o modelo.
    """
    deteccoes = detectar_documentos(texto)

    if incluir_nomes:
        # Import adiado: carregar nomes.py puxa spaCy, e quem roda apenas os
        # detectores de documento nao deveria precisar dele instalado.
        from anonimizador.detectores.nomes import detectar_nomes

        deteccoes.extend(detectar_nomes(texto, modelo=modelo, agressivo=agressivo))

    return resolver_sobreposicoes(deteccoes)
