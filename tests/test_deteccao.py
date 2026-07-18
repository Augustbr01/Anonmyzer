"""Testes do nucleo compartilhado: offsets, contexto e uniao de deteccoes."""

from __future__ import annotations

import pytest

from anonimizador.deteccao import (
    Confianca,
    Deteccao,
    normalizar,
    resolver_sobreposicoes,
    tem_palavra_chave,
)


def _deteccao(texto="X", inicio=0, fim=1, tipo="CPF", confianca=Confianca.ALTA):
    return Deteccao(texto=texto, inicio=inicio, fim=fim, tipo=tipo, confianca=confianca)


def test_offsets_invalidos_sao_rejeitados():
    with pytest.raises(ValueError):
        Deteccao(texto="X", inicio=5, fim=2, tipo="CPF")


def test_sobrepoe():
    a = _deteccao(inicio=0, fim=10)
    assert a.sobrepoe(_deteccao(inicio=5, fim=15))     # cruzamento parcial
    assert a.sobrepoe(_deteccao(inicio=2, fim=4))      # contida
    assert not a.sobrepoe(_deteccao(inicio=10, fim=20))  # encostada, sem cruzar


def test_normalizar_remove_acento_e_caixa():
    assert normalizar("ÓRGÃO Expedidor") == "orgao expedidor"


def test_tem_palavra_chave_so_olha_para_tras():
    texto = "numero 123 RG"
    # "RG" vem DEPOIS da posicao 7; nao pode contar como contexto.
    assert not tem_palavra_chave(texto, 7, ("rg",))
    assert tem_palavra_chave(texto, 7, ("numero",))


def test_tem_palavra_chave_respeita_janela():
    texto = "RG" + " " * 100 + "123456789"
    posicao = texto.index("123456789")
    assert not tem_palavra_chave(texto, posicao, ("rg",), janela=40)
    assert tem_palavra_chave(texto, posicao, ("rg",), janela=200)


# --------------------------------------------------------------------------
# resolver_sobreposicoes
# --------------------------------------------------------------------------

def test_resolver_mantem_maior_confianca():
    fraca = _deteccao(inicio=0, fim=10, confianca=Confianca.BAIXA, tipo="RG")
    forte = _deteccao(inicio=0, fim=10, confianca=Confianca.ALTA, tipo="CPF")
    assert resolver_sobreposicoes([fraca, forte]) == [forte]


def test_resolver_prefere_trecho_maior():
    """
    Empatada a confianca, ganha o trecho maior.

    E o que garante que "Joao da Silva" (NER completo) vence "Joao" (NER
    cortado): ficar com o menor deixaria "da Silva" visivel no texto final.
    """
    curta = _deteccao(texto="Joao", inicio=0, fim=4, tipo="NOME")
    longa = _deteccao(texto="Joao da Silva", inicio=0, fim=13, tipo="NOME")
    assert resolver_sobreposicoes([curta, longa]) == [longa]


def test_resolver_nao_descarta_deteccoes_independentes():
    a = _deteccao(inicio=0, fim=5)
    b = _deteccao(inicio=10, fim=15)
    assert len(resolver_sobreposicoes([a, b])) == 2


def test_resolver_devolve_ordenado_por_posicao():
    """O redator depende dessa ordem."""
    a = _deteccao(inicio=20, fim=25)
    b = _deteccao(inicio=0, fim=5)
    c = _deteccao(inicio=10, fim=15)
    assert [d.inicio for d in resolver_sobreposicoes([a, b, c])] == [0, 10, 20]


def test_resolver_saida_nunca_tem_sobreposicao():
    deteccoes = [
        _deteccao(inicio=0, fim=10, confianca=Confianca.ALTA),
        _deteccao(inicio=5, fim=15, confianca=Confianca.MEDIA),
        _deteccao(inicio=12, fim=20, confianca=Confianca.BAIXA),
        _deteccao(inicio=18, fim=30, confianca=Confianca.ALTA),
    ]
    resolvidas = resolver_sobreposicoes(deteccoes)
    for anterior, atual in zip(resolvidas, resolvidas[1:]):
        assert anterior.fim <= atual.inicio


def test_resolver_colisao_de_11_digitos_mantem_uma_so():
    """
    CPF, PIS e CNH tem 11 digitos e podem passar nos tres checksums ao mesmo
    tempo. O trecho tem que sair redigido uma unica vez -- redigir tres vezes
    corromperia o texto.
    """
    mesmo_trecho = dict(texto="12345678900", inicio=0, fim=11)
    deteccoes = [
        Deteccao(**mesmo_trecho, tipo="PIS"),
        Deteccao(**mesmo_trecho, tipo="CNH"),
        Deteccao(**mesmo_trecho, tipo="CPF"),
    ]
    resolvidas = resolver_sobreposicoes(deteccoes)
    assert len(resolvidas) == 1
    assert resolvidas[0].tipo == "CPF"  # maior prioridade em PRIORIDADE_TIPO
