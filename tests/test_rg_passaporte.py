"""
Testes dos detectores SEM checksum (confianca menor).

O ponto central aqui nao e "acha ou nao acha", e a graduacao: como nao ha
validacao matematica possivel, o que separa deteccao de ruido e o CONTEXTO.
Estes testes fixam esse comportamento.
"""

from __future__ import annotations

from anonimizador.deteccao import Confianca
from anonimizador.detectores.passaporte import detectar_passaportes
from anonimizador.detectores.rg import detectar_rgs


# --------------------------------------------------------------------------
# RG
# --------------------------------------------------------------------------

def test_rg_mascarado_detectado_sem_contexto(conferir_offsets):
    """Formato 12.345.678-9 e distinto o bastante para valer sozinho."""
    texto = "O numero 12.345.678-9 consta dos autos."
    deteccoes = detectar_rgs(texto)
    assert [d.texto for d in deteccoes] == ["12.345.678-9"]
    assert deteccoes[0].confianca is Confianca.BAIXA
    conferir_offsets(texto, deteccoes)


def test_rg_mascarado_com_contexto_tem_confianca_maior():
    texto = "RG: 12.345.678-9"
    deteccoes = detectar_rgs(texto)
    assert deteccoes[0].confianca is Confianca.MEDIA


def test_rg_solto_exige_contexto():
    """
    Numero solto de 9 digitos SEM palavra-chave e ignorado de proposito.

    Sem essa regra, todo numero de pedido/protocolo/matricula do documento
    viraria "RG" e o texto tratado ficaria inutilizavel.
    """
    assert detectar_rgs("O pedido 123456789 foi entregue.") == []


def test_rg_solto_com_contexto_e_detectado(conferir_offsets):
    texto = "Identidade 123456789 expedida pelo SSP."
    deteccoes = detectar_rgs(texto)
    assert [d.texto for d in deteccoes] == ["123456789"]
    assert deteccoes[0].confianca is Confianca.MEDIA
    conferir_offsets(texto, deteccoes)


def test_rg_contexto_ignora_acento_e_caixa():
    """"ORGÃO EXPEDIDOR" e "orgao expedidor" tem que valer igual."""
    assert detectar_rgs("ÓRGÃO EXPEDIDOR 123456789") != []


def test_rg_dv_com_x():
    texto = "RG 12.345.678-X"
    assert [d.texto for d in detectar_rgs(texto)] == ["12.345.678-X"]


def test_rg_nao_dispara_dentro_de_cpf_formatado():
    """O formato do CPF (3.3.3-2) nao pode casar com o do RG (2.3.3-1)."""
    assert detectar_rgs("CPF 111.444.777-35") == []


# --------------------------------------------------------------------------
# Passaporte
# --------------------------------------------------------------------------

def test_passaporte_br_detectado_sem_contexto(conferir_offsets):
    texto = "Documento FZ123456 apresentado na fronteira."
    deteccoes = detectar_passaportes(texto)
    assert [d.texto for d in deteccoes] == ["FZ123456"]
    assert deteccoes[0].confianca is Confianca.BAIXA
    conferir_offsets(texto, deteccoes)


def test_passaporte_com_contexto_tem_confianca_maior():
    texto = "Passaporte n. FZ123456"
    deteccoes = detectar_passaportes(texto)
    assert deteccoes[0].confianca is Confianca.MEDIA


def test_passaporte_exige_maiuscula_sem_contexto():
    """
    Sem contexto, so o padrao em CAIXA ALTA vale.

    "Fz123456" em caixa mista tem cara de codigo de produto/referencia, e
    aceitar isso encheria o documento de falso positivo.
    """
    assert detectar_passaportes("Referencia Fz123456 do catalogo.") == []


def test_passaporte_estrangeiro_com_contexto():
    """Formato fora do padrao brasileiro so e aceito com palavra-chave."""
    texto = "Passaporte: X1234567"
    assert [d.texto for d in detectar_passaportes(texto)] == ["X1234567"]


def test_passaporte_sem_deteccoes_duplicadas():
    """As duas faixas casam o mesmo trecho; deve sair uma deteccao so."""
    texto = "Passaporte FZ123456"
    assert len(detectar_passaportes(texto)) == 1
