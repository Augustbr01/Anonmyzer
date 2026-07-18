"""
Testes do redator -- a diferenca entre os dois modos e o que se testa aqui.

Regra que separa os modos, e que estes testes travam:
  - pseudonimo: mesma pessoa -> MESMO token (coerencia preservada);
  - anonimo:    mesma pessoa -> marcadores INDEPENDENTES (sem correlacao).
"""

from __future__ import annotations

import pytest

from anonimizador.deteccao import Deteccao
from anonimizador.redator import Modo, redigir


def _det(texto: str, valor: str, tipo: str, ocorrencia: int = 0) -> Deteccao:
    """Monta uma Deteccao localizando `valor` dentro de `texto`."""
    inicio = -1
    for _ in range(ocorrencia + 1):
        inicio = texto.index(valor, inicio + 1)
    return Deteccao(texto=valor, inicio=inicio, fim=inicio + len(valor), tipo=tipo)


# --------------------------------------------------------------------------
# Modo pseudonimo
# --------------------------------------------------------------------------

def test_pseudonimo_mesma_pessoa_recebe_o_mesmo_token():
    texto = "Joao da Silva assinou. Depois Joao da Silva confirmou."
    deteccoes = [
        _det(texto, "Joao da Silva", "NOME", 0),
        _det(texto, "Joao da Silva", "NOME", 1),
    ]
    resultado = redigir(texto, deteccoes, Modo.PSEUDONIMO)

    assert resultado.texto == "PESSOA_001 assinou. Depois PESSOA_001 confirmou."
    assert len(resultado.mapa) == 1
    assert resultado.mapa[0].ocorrencias == 2


def test_pseudonimo_pessoas_diferentes_recebem_tokens_diferentes():
    texto = "Joao da Silva e Maria Santos."
    deteccoes = [
        _det(texto, "Joao da Silva", "NOME"),
        _det(texto, "Maria Santos", "NOME"),
    ]
    resultado = redigir(texto, deteccoes, Modo.PSEUDONIMO)

    assert resultado.texto == "PESSOA_001 e PESSOA_002."
    assert len(resultado.mapa) == 2


def test_pseudonimo_numera_por_tipo():
    texto = "Joao, CPF 111.444.777-35."
    deteccoes = [_det(texto, "Joao", "NOME"), _det(texto, "111.444.777-35", "CPF")]
    resultado = redigir(texto, deteccoes, Modo.PSEUDONIMO)
    assert resultado.texto == "PESSOA_001, CPF CPF_001."


def test_pseudonimo_mesmo_cpf_com_e_sem_mascara_vira_um_token():
    """
    Sem normalizar, "111.444.777-35" e "11144477735" ganhariam tokens
    diferentes e o texto sugeriria duas pessoas onde ha uma.
    """
    texto = "CPF 111.444.777-35, tambem escrito 11144477735."
    deteccoes = [
        _det(texto, "111.444.777-35", "CPF"),
        _det(texto, "11144477735", "CPF"),
    ]
    resultado = redigir(texto, deteccoes, Modo.PSEUDONIMO)
    assert resultado.texto == "CPF CPF_001, tambem escrito CPF_001."
    assert len(resultado.mapa) == 1


def test_pseudonimo_nome_normaliza_caixa_e_acento():
    texto = "JOÃO DA SILVA e Joao da Silva sao a mesma pessoa."
    deteccoes = [
        _det(texto, "JOÃO DA SILVA", "NOME"),
        _det(texto, "Joao da Silva", "NOME"),
    ]
    resultado = redigir(texto, deteccoes, Modo.PSEUDONIMO)
    assert len(resultado.mapa) == 1


def test_pseudonimo_gera_mapa_com_valor_real():
    texto = "Joao da Silva."
    resultado = redigir(texto, [_det(texto, "Joao da Silva", "NOME")], Modo.PSEUDONIMO)
    entrada = resultado.mapa[0]
    assert entrada.valor == "Joao da Silva"
    assert entrada.token == "PESSOA_001"
    assert entrada.tipo == "NOME"


# --------------------------------------------------------------------------
# Modo anonimo
# --------------------------------------------------------------------------

def test_anonimo_nao_correlaciona_mencoes():
    """
    A garantia central do modo anonimo: duas mencoes da mesma pessoa saem
    como marcadores indistinguiveis, sem nada que as ligue entre si.
    """
    texto = "Joao da Silva assinou. Depois Joao da Silva confirmou."
    deteccoes = [
        _det(texto, "Joao da Silva", "NOME", 0),
        _det(texto, "Joao da Silva", "NOME", 1),
    ]
    resultado = redigir(texto, deteccoes, Modo.ANONIMO)

    assert resultado.texto == "[NOME] assinou. Depois [NOME] confirmou."


def test_anonimo_pessoas_diferentes_ficam_indistinguiveis():
    texto = "Joao da Silva e Maria Santos."
    deteccoes = [
        _det(texto, "Joao da Silva", "NOME"),
        _det(texto, "Maria Santos", "NOME"),
    ]
    resultado = redigir(texto, deteccoes, Modo.ANONIMO)
    assert resultado.texto == "[NOME] e [NOME]."


def test_anonimo_nunca_gera_mapa():
    texto = "Joao da Silva, CPF 111.444.777-35."
    deteccoes = [
        _det(texto, "Joao da Silva", "NOME"),
        _det(texto, "111.444.777-35", "CPF"),
    ]
    assert redigir(texto, deteccoes, Modo.ANONIMO).mapa == []


def test_anonimo_usa_marcador_por_tipo():
    texto = "Joao, CPF 111.444.777-35, CNPJ 11.222.333/0001-81."
    deteccoes = [
        _det(texto, "Joao", "NOME"),
        _det(texto, "111.444.777-35", "CPF"),
        _det(texto, "11.222.333/0001-81", "CNPJ"),
    ]
    resultado = redigir(texto, deteccoes, Modo.ANONIMO)
    assert resultado.texto == "[NOME], CPF [CPF], CNPJ [CNPJ]."


# --------------------------------------------------------------------------
# Correcao das substituicoes
# --------------------------------------------------------------------------

def test_substituicao_preserva_o_resto_do_texto():
    texto = "Antes 111.444.777-35 depois."
    resultado = redigir(texto, [_det(texto, "111.444.777-35", "CPF")], Modo.ANONIMO)
    assert resultado.texto == "Antes [CPF] depois."


def test_substituicoes_multiplas_nao_desalinham():
    """
    Com varias substituicoes de tamanhos diferentes, aplicar da esquerda para
    a direita deslocaria os offsets seguintes. O redator aplica ao contrario;
    este teste falha se essa ordem for invertida.
    """
    texto = "A 111.444.777-35 B 529.982.247-25 C 11.222.333/0001-81 D"
    deteccoes = [
        _det(texto, "111.444.777-35", "CPF"),
        _det(texto, "529.982.247-25", "CPF"),
        _det(texto, "11.222.333/0001-81", "CNPJ"),
    ]
    resultado = redigir(texto, deteccoes, Modo.ANONIMO)
    assert resultado.texto == "A [CPF] B [CPF] C [CNPJ] D"


def test_sem_deteccoes_devolve_texto_intacto():
    texto = "Nada sensivel aqui."
    assert redigir(texto, [], Modo.ANONIMO).texto == texto


def test_deteccoes_sobrepostas_sao_recusadas():
    """
    Sobreposicao chegando ao redator corromperia o texto. Falhar alto e melhor
    que gravar um arquivo silenciosamente errado.
    """
    texto = "Joao da Silva"
    deteccoes = [
        Deteccao(texto="Joao da", inicio=0, fim=7, tipo="NOME"),
        Deteccao(texto="da Silva", inicio=5, fim=13, tipo="NOME"),
    ]
    with pytest.raises(ValueError, match="sobrepostas"):
        redigir(texto, deteccoes, Modo.ANONIMO)


def test_contagem_por_tipo():
    texto = "Joao, Maria, CPF 111.444.777-35."
    deteccoes = [
        _det(texto, "Joao", "NOME"),
        _det(texto, "Maria", "NOME"),
        _det(texto, "111.444.777-35", "CPF"),
    ]
    resultado = redigir(texto, deteccoes, Modo.ANONIMO)
    assert resultado.contagem_por_tipo() == {"CPF": 1, "NOME": 2}
