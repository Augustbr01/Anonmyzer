"""
Testes do detector de nomes.

Nome nao tem checksum, entao nao da para afirmar "detecta certo" em absoluto.
O que estes testes travam sao os comportamentos que ja custaram bug:
nao emendar duas pessoas numa so, nao atravessar quebra de linha, e nao
depender do NER sozinho em texto de formulario.
"""

from __future__ import annotations

import pytest

from anonimizador.detectores.nomes import detectar_nomes

pytestmark = pytest.mark.usefixtures("modelo_ner")


def _textos(deteccoes) -> list[str]:
    return [d.texto for d in deteccoes]


def test_nome_simples(modelo_ner, conferir_offsets):
    texto = "Joao da Silva foi atendido na unidade central."
    deteccoes = detectar_nomes(texto, modelo=modelo_ner)
    assert any("Joao da Silva" in t for t in _textos(deteccoes))
    conferir_offsets(texto, deteccoes)


def test_nome_composto_completo(modelo_ner, conferir_offsets):
    texto = "Maria Oliveira Santos assinou o documento."
    deteccoes = detectar_nomes(texto, modelo=modelo_ner)
    assert any("Maria Oliveira Santos" in t for t in _textos(deteccoes))
    conferir_offsets(texto, deteccoes)


def test_duas_pessoas_ligadas_por_e_nao_viram_uma_so(modelo_ner):
    """
    Regressao: a expansao de entidade andava sobre o conectivo "e" e emendava
    "Pedro Lima e Beatriz Costa" numa entidade unica. No modo pseudonimo isso
    daria UM token para DUAS pessoas.
    """
    texto = "Pedro Henrique dos Santos Lima e Beatriz Costa compareceram."
    deteccoes = detectar_nomes(texto, modelo=modelo_ner)
    assert not any("e Beatriz" in t for t in _textos(deteccoes))
    assert any("Beatriz" in t for t in _textos(deteccoes))


def test_nome_nao_atravessa_quebra_de_linha(modelo_ner, conferir_offsets):
    """
    Regressao: em formulario, o nome casava ate o rotulo da linha seguinte
    ("Ana Paula Ferreira\\nRG"), fazendo o redator apagar o rotulo junto.
    """
    texto = "Nome: Ana Paula Ferreira\nRG: 12.345.678-9"
    deteccoes = detectar_nomes(texto, modelo=modelo_ner)
    assert all("\n" not in d.texto for d in deteccoes)
    assert any("Ana Paula Ferreira" in t for t in _textos(deteccoes))
    conferir_offsets(texto, deteccoes)


def test_pronome_de_tratamento(modelo_ner, conferir_offsets):
    texto = "O Sr. Carlos Eduardo de Almeida assinou o termo."
    deteccoes = detectar_nomes(texto, modelo=modelo_ner)
    assert any("Carlos Eduardo de Almeida" in t for t in _textos(deteccoes))
    conferir_offsets(texto, deteccoes)


def test_rotulo_de_campo(modelo_ner, conferir_offsets):
    texto = "Contratante: Fernanda Lima Rocha\nContratado: outra parte"
    deteccoes = detectar_nomes(texto, modelo=modelo_ner)
    assert any("Fernanda Lima Rocha" in t for t in _textos(deteccoes))
    conferir_offsets(texto, deteccoes)


def test_regra_de_rotulo_funciona_sem_ner():
    """
    A estrategia de rotulo e regex pura -- vale mesmo sem modelo carregado.

    Serve de rede: se o NER falhar num documento, o campo rotulado ainda e
    pego. Por isso o teste passa um modelo falso, que nao acha nada.
    """
    class ModeloVazio:
        def __call__(self, texto):
            class Doc:
                ents = ()
            return Doc()

    texto = "Requerente: Joana Martins Pereira"
    deteccoes = detectar_nomes(texto, modelo=ModeloVazio())
    assert _textos(deteccoes) == ["Joana Martins Pereira"]


def test_modo_agressivo_pega_nome_em_caixa_alta_que_o_ner_corta(modelo_ner):
    """
    Caso real medido com pt_core_news_sm: em caixa alta o NER devolve so
    "MARIA" de "MARIA OLIVEIRA SANTOS" -- ou seja, "OLIVEIRA SANTOS" vazaria.
    O modo agressivo existe exatamente para essa situacao.
    """
    texto = "CONTRATO DE PRESTAÇÃO DE SERVIÇOS entre MARIA OLIVEIRA SANTOS e a empresa."

    padrao = _textos(detectar_nomes(texto, modelo=modelo_ner, agressivo=False))
    agressivo = _textos(detectar_nomes(texto, modelo=modelo_ner, agressivo=True))

    assert not any("OLIVEIRA SANTOS" in t for t in padrao)
    assert any("MARIA OLIVEIRA SANTOS" in t for t in agressivo)


def test_modo_agressivo_ignora_cabecalho(modelo_ner):
    """A lista de ruido evita redigir titulo de secao em caixa alta."""
    texto = "CONTRATO DE PRESTAÇÃO DE SERVIÇOS"
    deteccoes = detectar_nomes(texto, modelo=modelo_ner, agressivo=True)
    assert not any(d.detector == "nomes:caixa_alta" for d in deteccoes)


def test_texto_vazio(modelo_ner):
    assert detectar_nomes("", modelo=modelo_ner) == []


def test_texto_sem_nomes(modelo_ner):
    texto = "O pedido foi entregue no prazo previsto pelo regulamento."
    assert detectar_nomes(texto, modelo=modelo_ner) == []
