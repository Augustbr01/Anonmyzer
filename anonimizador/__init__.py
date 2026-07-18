"""
Anonimizador -- remove/pseudonimiza dados pessoais de documentos.

Roda 100% local. Nenhum modulo deste pacote faz chamada de rede em tempo de
execucao (ver README, secao "Garantia de operacao offline").
"""

from anonimizador.deteccao import Confianca, Deteccao

__all__ = ["Deteccao", "Confianca"]
__version__ = "0.1.0"
