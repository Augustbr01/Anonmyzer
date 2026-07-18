"""Fixtures compartilhadas."""

from __future__ import annotations

import pytest

from anonimizador.detectores.nomes import ModeloIndisponivelError, carregar_modelo


@pytest.fixture(scope="session")
def modelo_ner():
    """
    Modelo spaCy carregado uma vez para toda a sessao de testes.

    Se o modelo nao estiver instalado, os testes que dependem dele sao pulados
    em vez de falhar -- assim os detectores de documento (que nao precisam de
    NER) continuam testaveis num ambiente sem o modelo baixado.
    """
    try:
        return carregar_modelo()
    except ModeloIndisponivelError as erro:
        pytest.skip(f"modelo de NER indisponivel: {erro}")


@pytest.fixture
def conferir_offsets():
    """
    Verifica que toda deteccao aponta exatamente para o trecho que diz apontar.

    Vale para todos os detectores: se `texto[inicio:fim] != texto_detectado`,
    o redator substitui o pedaco errado do documento -- que e a forma mais
    silenciosa de vazar dado (o texto sai "tratado" com o dado real intacto
    alguns caracteres ao lado).
    """
    def _conferir(texto: str, deteccoes) -> None:
        for deteccao in deteccoes:
            assert texto[deteccao.inicio : deteccao.fim] == deteccao.texto, (
                f"offset errado em {deteccao!r}: "
                f"texto[{deteccao.inicio}:{deteccao.fim}] == "
                f"{texto[deteccao.inicio:deteccao.fim]!r}"
            )
    return _conferir
