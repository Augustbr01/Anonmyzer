"""
Detector de endereco de e-mail.

E o dado pessoal mais facil de detectar do projeto: o formato tem uma ancora
obrigatoria (@) e um TLD no fim, entao regex sozinho ja da precisao alta --
diferente de RG ou telefone, quase nada em documento tem essa forma por acaso.
Por isso confianca ALTA sem exigir contexto.

Nao se valida dominio nem se checa MX: isso exigiria rede, e o projeto e
offline. Um e-mail sintaticamente valido de dominio inexistente ainda e dado
pessoal e deve ser redigido do mesmo jeito.
"""

from __future__ import annotations

import re

from anonimizador.deteccao import Confianca, Deteccao

__all__ = ["PADRAO_EMAIL", "detectar_emails"]

# Parte local + @ + dominio + TLD.
#
# O lookbehind evita casar so o final de um endereco maior. O TLD exige 2+
# letras, o que faz o ponto final de frase ficar de fora: em "contato@x.com."
# o grupo termina em "com" e o "." sobra para o texto.
PADRAO_EMAIL = re.compile(
    r"(?<![A-Za-z0-9._%+-])"
    r"([A-Za-z0-9._%+-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*"
    r"\.[A-Za-z]{2,})"
)


def detectar_emails(texto: str) -> list[Deteccao]:
    """Encontra todos os enderecos de e-mail em um texto."""
    return [
        Deteccao(
            texto=match.group(1),
            inicio=match.start(1),
            fim=match.end(1),
            tipo="EMAIL",
            confianca=Confianca.ALTA,
            detector="email",
        )
        for match in PADRAO_EMAIL.finditer(texto)
    ]
