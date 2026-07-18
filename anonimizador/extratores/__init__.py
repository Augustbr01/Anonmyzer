"""
Extratores: transformam um arquivo em texto puro para os detectores.

O ponto da separacao entre extrator e detector: a logica de deteccao/redacao
nao sabe (nem precisa saber) de onde o texto veio. Acrescentar PDF e Excel
depois e escrever pdf.py/excel.py com a mesma assinatura e registrar aqui em
EXTRATORES -- detectores, redator e CLI nao mudam.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from anonimizador.extratores.txt import extrair_txt

__all__ = ["EXTRATORES", "FormatoNaoSuportadoError", "extrair"]


class FormatoNaoSuportadoError(ValueError):
    """Levantada para extensao de arquivo ainda sem extrator."""


# Registro extensao -> funcao extratora.
# Proximos da fila: ".pdf" (pdf.py) e ".xlsx"/".xls"/".csv" (excel.py).
EXTRATORES: dict[str, Callable[[Path], str]] = {
    ".txt": extrair_txt,
    ".md": extrair_txt,
    ".csv": extrair_txt,  # tratado como texto puro por enquanto
}


def extrair(caminho: Path) -> str:
    """Extrai o texto de um arquivo, escolhendo o extrator pela extensao."""
    extensao = caminho.suffix.lower()
    extrator = EXTRATORES.get(extensao)

    if extrator is None:
        suportadas = ", ".join(sorted(EXTRATORES))
        raise FormatoNaoSuportadoError(
            f"Extensao '{extensao}' ainda nao suportada. Hoje: {suportadas}."
        )

    return extrator(caminho)
