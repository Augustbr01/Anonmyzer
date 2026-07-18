"""
Testes dos detectores com digito verificador.

Os valores validos aqui foram calculados a mao pelo algoritmo de cada
documento (ou, no caso do CNPJ alfanumerico, tirados do exemplo oficial da
RFB), justamente para os testes nao ficarem circulares -- validar o codigo
com numeros gerados pelo proprio codigo nao prova nada.
"""

from __future__ import annotations

import pytest

from anonimizador.detectores.cnh import cnh_valida, detectar_cnhs
from anonimizador.detectores.cnpj import cnpj_valido, detectar_cnpjs
from anonimizador.detectores.cpf import cpf_valido, detectar_cpfs
from anonimizador.detectores.pis import detectar_pis, pis_valido
from anonimizador.detectores.titulo_eleitor import detectar_titulos, titulo_valido


# --------------------------------------------------------------------------
# CPF
# --------------------------------------------------------------------------

@pytest.mark.parametrize("valor", [
    "111.444.777-35",   # com mascara
    "11144477735",      # sem mascara
    "111444777-35",     # mascara parcial
])
def test_cpf_valido_aceita_formatos(valor):
    assert cpf_valido(valor)


@pytest.mark.parametrize("valor", [
    "111.444.777-36",   # DV errado
    "111.111.111-11",   # todos iguais
    "000.000.000-00",   # todos iguais (passaria no modulo 11 sem a guarda)
    "1114447773",       # curto demais
    "111444777355",     # longo demais
    "",
])
def test_cpf_valido_rejeita(valor):
    assert not cpf_valido(valor)


def test_detectar_cpfs_ignora_numero_de_11_digitos_que_nao_e_cpf():
    # E o ganho real da validacao sobre regex pura: numero de protocolo com
    # 11 digitos tem o formato de CPF mas nao passa no digito verificador.
    texto = "Protocolo 12345678901 registrado."
    assert detectar_cpfs(texto) == []


def test_detectar_cpfs_encontra_varios(conferir_offsets):
    texto = "Titulares: 111.444.777-35 e 529.982.247-25."
    deteccoes = detectar_cpfs(texto)
    assert [d.texto for d in deteccoes] == ["111.444.777-35", "529.982.247-25"]
    conferir_offsets(texto, deteccoes)


# --------------------------------------------------------------------------
# CNPJ -- numerico legado e alfanumerico (IN RFB 2.229/2024, vigente 07/2026)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("valor", [
    "11.222.333/0001-81",    # legado com mascara
    "11222333000181",        # legado sem mascara
])
def test_cnpj_legado_valido(valor):
    assert cnpj_valido(valor)


@pytest.mark.parametrize("valor", [
    "12.ABC.345/01DE-35",    # exemplo oficial da RFB
    "12ABC34501DE35",        # sem mascara
    "12.abc.345/01de-35",    # minusculo (normalizado antes de validar)
])
def test_cnpj_alfanumerico_valido(valor):
    """
    O formato que passa a valer em julho/2026.

    Um validador que so aceite \\d deixaria TODOS estes passarem sem detectar
    -- falso negativo, o pior caso do projeto.
    """
    assert cnpj_valido(valor)


@pytest.mark.parametrize("valor", [
    "11.222.333/0001-82",    # DV errado (legado)
    "12.ABC.345/01DE-36",    # DV errado (alfanumerico)
    "00.000.000/0000-00",    # todos iguais
    "12.ABC.345/01DE-3X",    # DV nao pode ter letra
    "1A.BC3.45D/01DE-3",     # tamanho errado
])
def test_cnpj_invalido(valor):
    assert not cnpj_valido(valor)


def test_cnpj_dv_continua_numerico_no_formato_novo():
    """As 12 primeiras posicoes aceitam letra; os 2 DVs finais, nunca."""
    assert not cnpj_valido("12ABC34501DEA5")


def test_detectar_cnpjs_acha_os_dois_formatos(conferir_offsets):
    texto = "Fornecedores: 11.222.333/0001-81 (antigo) e 12.ABC.345/01DE-35 (novo)."
    deteccoes = detectar_cnpjs(texto)
    assert [d.texto for d in deteccoes] == [
        "11.222.333/0001-81",
        "12.ABC.345/01DE-35",
    ]
    conferir_offsets(texto, deteccoes)


# --------------------------------------------------------------------------
# Titulo de eleitor
# --------------------------------------------------------------------------

def test_titulo_valido():
    assert titulo_valido("123456780698")


@pytest.mark.parametrize("valor", [
    "123456780699",   # DV2 errado
    "123456780598",   # DV1 errado
    "123456789998",   # UF 99 nao existe
    "123456780000",   # UF 00 nao existe
    "12345678069",    # curto
])
def test_titulo_invalido(valor):
    assert not titulo_valido(valor)


def test_detectar_titulos(conferir_offsets):
    texto = "Titulo de eleitor: 123456780698."
    deteccoes = detectar_titulos(texto)
    assert [d.texto for d in deteccoes] == ["123456780698"]
    conferir_offsets(texto, deteccoes)


# --------------------------------------------------------------------------
# PIS/PASEP/NIT
# --------------------------------------------------------------------------

@pytest.mark.parametrize("valor", ["12345678900", "12034567899", "123.45678.90-0"])
def test_pis_valido(valor):
    assert pis_valido(valor)


@pytest.mark.parametrize("valor", ["12345678901", "11111111111", "1234567890"])
def test_pis_invalido(valor):
    assert not pis_valido(valor)


def test_detectar_pis(conferir_offsets):
    texto = "PIS 123.45678.90-0 do empregado."
    deteccoes = detectar_pis(texto)
    assert [d.texto for d in deteccoes] == ["123.45678.90-0"]
    conferir_offsets(texto, deteccoes)


# --------------------------------------------------------------------------
# CNH
# --------------------------------------------------------------------------

def test_cnh_valida_com_desconto():
    """98765432109 exercita o caminho do desconto de 2 no segundo DV."""
    assert cnh_valida("98765432109")


@pytest.mark.parametrize("valor", ["98765432100", "00000000000", "9876543210"])
def test_cnh_invalida(valor):
    assert not cnh_valida(valor)


def test_detectar_cnhs(conferir_offsets):
    texto = "Registro CNH 98765432109 valido."
    deteccoes = detectar_cnhs(texto)
    assert [d.texto for d in deteccoes] == ["98765432109"]
    conferir_offsets(texto, deteccoes)


# --------------------------------------------------------------------------
# Casos-limite compartilhados
# --------------------------------------------------------------------------

@pytest.mark.parametrize("detectar", [
    detectar_cpfs, detectar_cnpjs, detectar_titulos, detectar_pis, detectar_cnhs,
])
def test_texto_vazio_nao_quebra(detectar):
    assert detectar("") == []


@pytest.mark.parametrize("detectar", [
    detectar_cpfs, detectar_cnpjs, detectar_titulos, detectar_pis, detectar_cnhs,
])
def test_nao_casa_dentro_de_numero_maior(detectar):
    """
    Um numero longo NAO deve virar deteccao por conter um documento valido
    nos primeiros digitos -- e o que a ancora \\b garante.
    """
    assert detectar("9999911144477735999999") == []
