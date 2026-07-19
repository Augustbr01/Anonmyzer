"""
Testes dos detectores de contato: e-mail, telefone e endereco/CEP.

Boa parte destes testes e sobre o que NAO deve ser detectado. Telefone e
endereco nao tem digito verificador, entao o que segura a precisao e a
estrutura (DDD real, prefixo coerente, ancora de logradouro) -- se essas
regras afrouxarem, o documento tratado vira uma sopa de marcadores.
"""

from __future__ import annotations

import pytest

from anonimizador.deteccao import Confianca
from anonimizador.detectores.email import detectar_emails
from anonimizador.detectores.endereco import detectar_enderecos
from anonimizador.detectores.telefone import detectar_telefones, telefone_valido


def _textos(deteccoes) -> list[str]:
    return [d.texto for d in deteccoes]


# --------------------------------------------------------------------------
# E-mail
# --------------------------------------------------------------------------

@pytest.mark.parametrize("texto, esperado", [
    ("Contato: joao.silva@empresa.com.br", "joao.silva@empresa.com.br"),
    ("Escreva para joao+tag@gmail.com", "joao+tag@gmail.com"),
    ("MARIA@EMPRESA.COM consta no cadastro", "MARIA@EMPRESA.COM"),
    ("mailto:pedro@x.io agora", "pedro@x.io"),
    ("usuario_1-teste@sub.dominio.org", "usuario_1-teste@sub.dominio.org"),
])
def test_email_detectado(texto, esperado, conferir_offsets):
    deteccoes = detectar_emails(texto)
    assert _textos(deteccoes) == [esperado]
    conferir_offsets(texto, deteccoes)


def test_email_nao_engole_ponto_final_da_frase():
    """
    "contato@x.com." termina a frase -- o ponto e pontuacao, nao parte do
    dominio. Incluir o ponto quebraria o e-mail no mapa de-para.
    """
    assert _textos(detectar_emails("Escreva para contato@x.com.")) == ["contato@x.com"]


@pytest.mark.parametrize("texto", [
    "Sem email aqui, so texto normal.",
    "arroba solta @ nao vale",
    "a@b sem TLD nao vale",
    "duas@@arrobas.com",
])
def test_email_nao_detectado(texto):
    assert detectar_emails(texto) == []


# --------------------------------------------------------------------------
# Telefone
# --------------------------------------------------------------------------

@pytest.mark.parametrize("texto, esperado", [
    ("Telefone: (11) 98765-4321", "(11) 98765-4321"),
    ("Fone 11 3456-7890 comercial", "11 3456-7890"),
    ("Celular +55 11 98765-4321", "+55 11 98765-4321"),
    ("Sem mascara: 11987654321", "11987654321"),
    ("Fixo sem mascara: 1134567890", "1134567890"),
    ("Contato (21) 3456-7890", "(21) 3456-7890"),
])
def test_telefone_detectado(texto, esperado, conferir_offsets):
    deteccoes = detectar_telefones(texto)
    assert _textos(deteccoes) == [esperado]
    conferir_offsets(texto, deteccoes)


def test_telefone_local_exige_contexto():
    """Sem DDD nao sobra estrutura; so a palavra-chave sustenta a deteccao."""
    assert _textos(detectar_telefones("Tel: 98765-4321")) == ["98765-4321"]
    assert detectar_telefones("Numero solto 98765-4321 aqui") == []


def test_telefone_local_nao_duplica_numero_completo():
    """
    "(11) 98765-4321" contem "98765-4321". Sem a guarda de sobreposicao
    sairiam duas deteccoes encavaladas para o mesmo telefone -- e deteccao
    encavalada e recusada pelo redator.
    """
    deteccoes = detectar_telefones("Telefone: (11) 98765-4321")
    assert len(deteccoes) == 1


@pytest.mark.parametrize("texto, motivo", [
    ("DDD inexistente: (20) 98765-4321", "20 nao esta na lista oficial"),
    ("Celular sem o 9: (11) 8765-43210", "celular tem que comecar com 9"),
    ("CPF 111.444.777-35 no texto", "formato de CPF"),
    ("CPF cru 11144477735 no texto", "DDD 11 valido, mas 3o digito nao e 9 nem 2-5"),
    ("Data 12/03/2024 registrada", "data"),
    ("Valor 1.234.567,89 apurado", "dinheiro"),
    ("CEP 01310-100 do imovel", "CEP tem 3 digitos apos o hifen"),
])
def test_telefone_nao_detectado(texto, motivo):
    assert detectar_telefones(texto) == [], f"deveria rejeitar: {motivo}"


@pytest.mark.parametrize("numero, esperado", [
    ("11987654321", True),      # celular
    ("1134567890", True),       # fixo
    ("5511987654321", True),    # com DDI
    ("2098765432", False),      # DDD 20 nao existe
    ("11187654321", False),     # celular sem o 9
    ("1114567890", False),      # fixo comecando com 1
    ("119876543", False),       # tamanho errado
])
def test_telefone_valido(numero, esperado):
    assert telefone_valido(numero) is esperado


def test_todos_os_ddds_sao_de_dois_digitos():
    from anonimizador.detectores.telefone import DDDS_VALIDOS
    assert all(11 <= ddd <= 99 for ddd in DDDS_VALIDOS)


# --------------------------------------------------------------------------
# Endereco e CEP
# --------------------------------------------------------------------------

@pytest.mark.parametrize("texto, esperado", [
    ("Rua das Flores, 123", "Rua das Flores, 123"),
    ("Avenida Paulista, nº 1578, apto 45", "Avenida Paulista, nº 1578, apto 45"),
    ("Av. Brasil 500 - bloco B", "Av. Brasil 500 - bloco B"),
    ("Mora na Praça da Sé, 12", "Praça da Sé, 12"),
    ("R. Ipiranga, 45", "R. Ipiranga, 45"),
])
def test_endereco_detectado(texto, esperado, conferir_offsets):
    deteccoes = detectar_enderecos(texto)
    assert esperado in _textos(deteccoes)
    conferir_offsets(texto, deteccoes)


def test_endereco_exige_numero():
    """
    Sem numero a ancora fica fraca demais ("subiu a rua correndo").
    Falso negativo conhecido e assumido -- ver Limitacoes no README.
    """
    assert detectar_enderecos("Subiu a rua correndo depressa.") == []


def test_endereco_nao_detecta_texto_comum():
    assert detectar_enderecos("Texto normal sem endereco nenhum aqui.") == []


def test_cep_com_hifen_detectado(conferir_offsets):
    texto = "CEP 01310-100"
    deteccoes = detectar_enderecos(texto)
    assert "01310-100" in _textos(deteccoes)
    assert [d for d in deteccoes if d.tipo == "CEP"][0].confianca is Confianca.ALTA
    conferir_offsets(texto, deteccoes)


def test_cep_sem_hifen_exige_contexto():
    assert "01310100" in _textos(detectar_enderecos("CEP: 01310100"))
    assert detectar_enderecos("Numero solto 01310100 no texto") == []


def test_cep_nao_confunde_com_telefone():
    """CEP tem 3 digitos depois do hifen; telefone tem 4."""
    assert detectar_telefones("CEP 01310-100") == []
    assert [d.tipo for d in detectar_enderecos("CEP 01310-100")] == ["CEP"]


def test_endereco_com_cep_junto(conferir_offsets):
    texto = "Rua das Flores, 123 - CEP 01310-100"
    deteccoes = detectar_enderecos(texto)
    tipos = sorted(d.tipo for d in deteccoes)
    assert tipos == ["CEP", "ENDERECO"]
    conferir_offsets(texto, deteccoes)


# --------------------------------------------------------------------------
# Bateria de variacoes reais
#
# Formatos coletados numa rodada exploratoria, incluindo varios que nao foram
# projetados de proposito. Ficam aqui como regressao: sao a evidencia de ate
# onde cada detector chega hoje.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("texto, esperado", [
    ("nome.sobrenome@sub.dominio.com.br", "nome.sobrenome@sub.dominio.com.br"),
    ("joao_silva@empresa.com", "joao_silva@empresa.com"),
    ("joao-silva@empresa.com", "joao-silva@empresa.com"),
    ("123@numeros.com", "123@numeros.com"),
    ("joao@minha-empresa.com.br", "joao@minha-empresa.com.br"),
    ("Contato (contato@x.com) disponivel", "contato@x.com"),
    ("<contato@x.com>", "contato@x.com"),
    ("ponto-virgula contato@x.com; segue", "contato@x.com"),
    ("joao@empresa.com)", "joao@empresa.com"),
])
def test_email_variacoes(texto, esperado, conferir_offsets):
    deteccoes = detectar_emails(texto)
    assert esperado in _textos(deteccoes)
    conferir_offsets(texto, deteccoes)


def test_email_dois_no_mesmo_trecho():
    texto = "contato@x.com, outro@y.com"
    assert _textos(detectar_emails(texto)) == ["contato@x.com", "outro@y.com"]


def test_email_nao_confunde_com_url():
    """URL tem ponto e dominio, mas nao tem @ -- nao pode virar e-mail."""
    assert detectar_emails("Acesse https://empresa.com/contato hoje") == []


@pytest.mark.parametrize("texto, esperado", [
    ("(11)98765-4321", "(11)98765-4321"),        # sem espaco apos o DDD
    ("+55 (11) 98765-4321", "+55 (11) 98765-4321"),
    ("55 11 98765-4321", "55 11 98765-4321"),    # DDI sem o +
    ("11.98765.4321", "11.98765.4321"),          # separado por ponto
    ("11-98765-4321", "11-98765-4321"),          # separado por hifen
    ("Ligue 11987654321 hoje", "11987654321"),   # cru, no meio da frase
    ("Tel (11) 3456-7890 ramal 123", "(11) 3456-7890"),
    ("(85) 99999-8888", "(85) 99999-8888"),      # DDD do Nordeste
])
def test_telefone_variacoes(texto, esperado, conferir_offsets):
    deteccoes = detectar_telefones(texto)
    assert esperado in _textos(deteccoes)
    conferir_offsets(texto, deteccoes)


@pytest.mark.parametrize("texto, motivo", [
    ("Processo 0001234-56.2024.8.26.0100", "numero de processo judicial"),
    ("Periodo 2020-2024", "intervalo de anos"),
    ("(11) 9876-5432", "8 digitos comecando com 9 nao existe mais"),
    ("0800 123 4567", "linha publica de empresa, nao dado pessoal"),
])
def test_telefone_falsos_positivos_conhecidos(texto, motivo):
    assert detectar_telefones(texto) == [], f"deveria rejeitar: {motivo}"


@pytest.mark.parametrize("texto, esperado", [
    ("Rua das Flores nº 123", "Rua das Flores nº 123"),
    ("Rua das Flores n° 123", "Rua das Flores n° 123"),
    ("Avenida Brigadeiro Faria Lima, 3477", "Avenida Brigadeiro Faria Lima, 3477"),
    ("Praça da República, 50", "Praça da República, 50"),
    ("Alameda Santos, 100", "Alameda Santos, 100"),
    ("Travessa São José, 12", "Travessa São José, 12"),
    ("Estrada do Campo Limpo, 500", "Estrada do Campo Limpo, 500"),
    ("Largo do Machado, 21", "Largo do Machado, 21"),
    ("Av Brasil, 1500", "Av Brasil, 1500"),           # sem ponto na abreviacao
    ("Rua Dr. Joao Pessoa, 88", "Rua Dr. Joao Pessoa, 88"),
    ("Rua Sete de Setembro, 1000", "Rua Sete de Setembro, 1000"),
])
def test_endereco_variacoes(texto, esperado, conferir_offsets):
    deteccoes = detectar_enderecos(texto)
    assert esperado in _textos(deteccoes)
    conferir_offsets(texto, deteccoes)


@pytest.mark.parametrize("texto, esperado", [
    ("Rua A, 1, apto 45", "Rua A, 1, apto 45"),
    ("Rua 5, 200", "Rua 5, 200"),
    ("Rua B, 45 - Jardim Sao Paulo", "Rua B, 45"),
])
def test_endereco_com_nome_de_uma_letra(texto, esperado):
    """
    Regressao: o nome do logradouro exigia 2+ caracteres, entao "Rua A, 1"
    passava batido -- endereco inteiro sem deteccao. Formato comum em
    loteamento e condominio.
    """
    assert esperado in _textos(detectar_enderecos(texto))


def test_endereco_para_no_fim_do_numero():
    """Bairro depois do numero fica de fora; a parte identificadora ja saiu."""
    assert "Rua das Flores, 123" in _textos(detectar_enderecos("Rua das Flores, 123 - Centro"))


def test_endereco_sem_numero_nao_e_detectado():
    """
    "s/n" nao tem digito, entao nao ancora. Falso negativo conhecido: a
    alternativa seria aceitar logradouro sem numero, o que dispararia em
    qualquer mencao a "rua" no texto corrido.
    """
    assert detectar_enderecos("Rua das Flores, s/n") == []


@pytest.mark.xfail(
    reason="formato composto (Brasilia/loteamento) nao coberto -- lacuna conhecida",
    strict=True,
)
@pytest.mark.parametrize("texto", [
    "Quadra 3, Casa 12",
    "SQN 210 Bloco A Apto 305",
])
def test_endereco_formato_composto_nao_coberto(texto):
    """
    LACUNA CONHECIDA, marcada como xfail para ficar visivel na saida do pytest.

    Enderecos de Brasilia (SQN/SQS/SHIS) e de loteamento com quadra/lote nao
    seguem "tipo + nome + numero" e escapam do padrao. Cobri-los exige uma
    familia de padroes propria; deixar o padrao geral atravessar virgula
    resolveria, mas dispararia em texto corrido ("na rua sozinho, havia 3
    anos"). Se este teste passar, a lacuna foi fechada -- atualize o README.
    """
    assert detectar_enderecos(texto) != []
