"""
Testes dos extratores.

A codificacao e o ponto sensivel: nome de pessoa em portugues tem acento, e
um acento lido errado vira um nome que o NER nao reconhece -- ou seja, falha
de encoding se converte em dado pessoal nao detectado.
"""

from __future__ import annotations

import pytest

from anonimizador.extratores import FormatoNaoSuportadoError, extrair
from anonimizador.extratores.txt import ler_texto


def test_le_utf8(tmp_path):
    arquivo = tmp_path / "doc.txt"
    arquivo.write_text("João da Silva, CPF 111.444.777-35", encoding="utf-8")
    assert "João da Silva" in extrair(arquivo)


def test_le_utf8_com_bom(tmp_path):
    """Bloco de Notas do Windows grava UTF-8 com BOM por padrao."""
    arquivo = tmp_path / "doc.txt"
    arquivo.write_bytes("﻿João da Silva".encode("utf-8"))
    texto = extrair(arquivo)
    assert texto.startswith("João")  # BOM consumido, nao vira caractere


def test_le_cp1252(tmp_path):
    """Exportacao de sistema legado no Windows pt-BR costuma vir assim."""
    arquivo = tmp_path / "doc.txt"
    arquivo.write_bytes("João da Silva — acento e travessão".encode("cp1252"))
    texto = extrair(arquivo)
    assert "João da Silva" in texto


def test_le_latin1(tmp_path):
    arquivo = tmp_path / "doc.txt"
    arquivo.write_bytes("Conceição Assunção".encode("latin-1"))
    assert "Conceição Assunção" in extrair(arquivo)


def test_arquivo_inexistente(tmp_path):
    with pytest.raises(FileNotFoundError):
        ler_texto(tmp_path / "nao_existe.txt")


def test_extensao_nao_suportada(tmp_path):
    """PDF e Excel ainda nao tem extrator -- o erro tem que ser explicito."""
    arquivo = tmp_path / "doc.pdf"
    arquivo.write_bytes(b"%PDF-1.4")
    with pytest.raises(FormatoNaoSuportadoError, match="pdf"):
        extrair(arquivo)


def test_arquivo_vazio(tmp_path):
    arquivo = tmp_path / "vazio.txt"
    arquivo.write_text("", encoding="utf-8")
    assert extrair(arquivo) == ""
