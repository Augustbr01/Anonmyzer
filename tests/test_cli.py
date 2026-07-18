"""
Testes de ponta a ponta do CLI.

Quase todos rodam com --sem-nomes para nao pagar o carregamento do modelo de
NER a cada teste; a integracao com o NER e coberta em test_nomes.py e
test_corpus.py.
"""

from __future__ import annotations

import json

from anonimizador.cli import main

DOCUMENTO = """Ficha de atendimento

Contratante: Joao da Silva
CPF: 111.444.777-35
RG: 12.345.678-9

O CPF 111.444.777-35 consta tambem no rodape.
"""


def _preparar(tmp_path, conteudo=DOCUMENTO):
    arquivo = tmp_path / "ficha.txt"
    arquivo.write_text(conteudo, encoding="utf-8")
    return arquivo


def test_modo_anonimo_grava_saida_sem_mapa(tmp_path, capsys):
    arquivo = _preparar(tmp_path)
    assert main([str(arquivo), "--modo", "anonimo", "--sem-nomes"]) == 0

    saida = tmp_path / "ficha.anonimizado.txt"
    texto = saida.read_text(encoding="utf-8")

    assert "111.444.777-35" not in texto
    assert "[CPF]" in texto
    assert not (tmp_path / "ficha.mapa.json").exists()


def test_modo_anonimo_nao_correlaciona(tmp_path):
    """As duas mencoes do mesmo CPF viram marcadores identicos e sem vinculo."""
    arquivo = _preparar(tmp_path)
    main([str(arquivo), "--modo", "anonimo", "--sem-nomes"])
    texto = (tmp_path / "ficha.anonimizado.txt").read_text(encoding="utf-8")
    assert texto.count("[CPF]") == 2
    assert "CPF_001" not in texto


def test_modo_pseudonimo_grava_saida_e_mapa(tmp_path):
    arquivo = _preparar(tmp_path)
    assert main([str(arquivo), "--modo", "pseudonimo", "--sem-nomes"]) == 0

    texto = (tmp_path / "ficha.anonimizado.txt").read_text(encoding="utf-8")
    mapa = json.loads((tmp_path / "ficha.mapa.json").read_text(encoding="utf-8"))

    # Mesmo CPF nas duas mencoes -> mesmo token, uma entrada so no mapa.
    assert texto.count("CPF_001") == 2
    assert "111.444.777-35" not in texto

    entradas_cpf = [e for e in mapa["mapa"] if e["tipo"] == "CPF"]
    assert len(entradas_cpf) == 1
    assert entradas_cpf[0]["valor_real"] == "111.444.777-35"
    assert entradas_cpf[0]["ocorrencias"] == 2


def test_mapa_traz_o_aviso_de_risco(tmp_path):
    """O mapa reverte a protecao; o arquivo tem que dizer isso."""
    arquivo = _preparar(tmp_path)
    main([str(arquivo), "--modo", "pseudonimo", "--sem-nomes"])
    mapa = json.loads((tmp_path / "ficha.mapa.json").read_text(encoding="utf-8"))
    assert "ATENCAO" in mapa["aviso"]


def test_modo_padrao_e_anonimo(tmp_path):
    """Sem --modo, vale o modo mais seguro (nao gera mapa)."""
    arquivo = _preparar(tmp_path)
    main([str(arquivo), "--sem-nomes"])
    assert not (tmp_path / "ficha.mapa.json").exists()


def test_simular_nao_grava_nada(tmp_path, capsys):
    arquivo = _preparar(tmp_path)
    assert main([str(arquivo), "--simular", "--sem-nomes"]) == 0

    assert not (tmp_path / "ficha.anonimizado.txt").exists()
    assert "nada foi gravado" in capsys.readouterr().out


def test_saida_personalizada(tmp_path):
    arquivo = _preparar(tmp_path)
    destino = tmp_path / "limpo.txt"
    assert main([str(arquivo), "-o", str(destino), "--sem-nomes"]) == 0
    assert destino.exists()


def test_recusa_sobrescrever_sem_forcar(tmp_path, capsys):
    arquivo = _preparar(tmp_path)
    (tmp_path / "ficha.anonimizado.txt").write_text("ja existe", encoding="utf-8")

    assert main([str(arquivo), "--sem-nomes"]) == 1
    assert "ja existe" in capsys.readouterr().err
    assert (tmp_path / "ficha.anonimizado.txt").read_text(encoding="utf-8") == "ja existe"


def test_forcar_sobrescreve(tmp_path):
    arquivo = _preparar(tmp_path)
    (tmp_path / "ficha.anonimizado.txt").write_text("ja existe", encoding="utf-8")
    assert main([str(arquivo), "--sem-nomes", "--forcar"]) == 0
    assert (tmp_path / "ficha.anonimizado.txt").read_text(encoding="utf-8") != "ja existe"


def test_recusa_sobrescrever_o_proprio_original(tmp_path, capsys):
    """
    Gravar por cima da entrada destruiria o documento original -- e o mapa,
    sozinho, nao o reconstroi.
    """
    arquivo = _preparar(tmp_path)
    assert main([str(arquivo), "-o", str(arquivo), "--sem-nomes"]) == 1
    assert arquivo.read_text(encoding="utf-8") == DOCUMENTO


def test_arquivo_inexistente(tmp_path, capsys):
    assert main([str(tmp_path / "nao_existe.txt")]) == 1
    assert "nao encontrado" in capsys.readouterr().err


def test_extensao_nao_suportada(tmp_path, capsys):
    arquivo = tmp_path / "doc.pdf"
    arquivo.write_bytes(b"%PDF-1.4")
    assert main([str(arquivo)]) == 1
    assert "nao suportada" in capsys.readouterr().err


def test_relatorio_mostra_contagem_por_tipo(tmp_path, capsys):
    arquivo = _preparar(tmp_path)
    main([str(arquivo), "--sem-nomes"])
    saida = capsys.readouterr().out
    assert "CPF" in saida
    assert "RG" in saida


def test_ponta_a_ponta_com_ner(tmp_path, modelo_ner):
    """Um caminho completo, com deteccao de nomes ligada."""
    arquivo = _preparar(tmp_path)
    assert main([str(arquivo), "--modo", "pseudonimo"]) == 0

    texto = (tmp_path / "ficha.anonimizado.txt").read_text(encoding="utf-8")
    assert "Joao da Silva" not in texto
    assert "111.444.777-35" not in texto
    assert "PESSOA_001" in texto
