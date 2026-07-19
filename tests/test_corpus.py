"""
Corpus anotado -- mede precisao e recall a cada rodada.

Serve para acompanhar a qualidade da deteccao conforme o projeto evolui:
trocar pt_core_news_sm por pt_core_news_lg, ou entrar com Presidio, muda os
numeros aqui e da para comparar antes/depois em vez de julgar "no olho".

Como ler as duas metricas neste projeto:

  RECALL    (achou tudo que era pra achar?) -- e o que importa. Cada ponto
            que falta e um dado pessoal vazando no arquivo tratado. O teste
            EXIGE recall 1.0.

  PRECISAO  (o que achou era mesmo dado pessoal?) -- custa legibilidade, nao
            seguranca. Precisao baixa deixa o documento mais redigido do que
            precisava; e o lado errado aceitavel pelo principio de calibracao
            do projeto. O teste so REPORTA, com um piso frouxo para pegar
            regressao grosseira.

Para acrescentar caso: adicione um Documento em CORPUS com todos os dados
pessoais listados em `esperado`. Rode `pytest -s tests/test_corpus.py` para
ver o relatorio.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from anonimizador.detectores import detectar_tudo

# Todos os numeros abaixo sao ficticios, mas com digito verificador VALIDO --
# numero invalido nao exercita o detector, ele e descartado no checksum.


@dataclass
class Documento:
    nome: str
    texto: str
    esperado: list[tuple[str, str]] = field(default_factory=list)


CORPUS = [
    Documento(
        nome="ficha cadastral (formulario com rotulos)",
        texto=(
            "FICHA DE CADASTRO\n"
            "\n"
            "Nome: Joao da Silva\n"
            "CPF: 111.444.777-35\n"
            "RG: 12.345.678-9\n"
            "PIS: 123.45678.90-0\n"
            "Titulo de eleitor: 123456780698\n"
            "\n"
            "Atendente responsavel: Maria Oliveira Santos\n"
        ),
        esperado=[
            ("NOME", "Joao da Silva"),
            ("CPF", "111.444.777-35"),
            ("RG", "12.345.678-9"),
            ("PIS", "123.45678.90-0"),
            ("TITULO_ELEITOR", "123456780698"),
            ("NOME", "Maria Oliveira Santos"),
        ],
    ),
    Documento(
        nome="contrato (texto corrido)",
        texto=(
            "Pelo presente instrumento particular, de um lado a empresa "
            "inscrita no CNPJ 11.222.333/0001-81, e de outro Carlos Eduardo "
            "de Almeida, portador do CPF 529.982.247-25, doravante "
            "denominado contratado, fica acordado o seguinte.\n"
            "\n"
            "A testemunha Beatriz Costa Lima assina em conjunto.\n"
        ),
        esperado=[
            ("CNPJ", "11.222.333/0001-81"),
            ("NOME", "Carlos Eduardo de Almeida"),
            ("CPF", "529.982.247-25"),
            ("NOME", "Beatriz Costa Lima"),
        ],
    ),
    Documento(
        nome="oficio com CNPJ alfanumerico (regra de 07/2026)",
        texto=(
            "Ao setor de compras,\n"
            "\n"
            "Informamos que o fornecedor passou a operar sob o CNPJ "
            "12.ABC.345/01DE-35, no novo formato alfanumerico. O contato "
            "segue sendo o Sr. Rafael Menezes Cardoso, CNH 98765432109, "
            "passaporte FZ123456.\n"
        ),
        esperado=[
            ("CNPJ", "12.ABC.345/01DE-35"),
            ("NOME", "Rafael Menezes Cardoso"),
            ("CNH", "98765432109"),
            ("PASSAPORTE", "FZ123456"),
        ],
    ),
    Documento(
        nome="cadastro com dados de contato",
        texto=(
            "CADASTRO DE CLIENTE\n"
            "\n"
            "Nome: Ana Paula Ferreira\n"
            "E-mail: ana.ferreira@provedor.com.br\n"
            "Telefone: (11) 98765-4321\n"
            "Fixo: 11 3456-7890\n"
            "Endereco: Rua das Flores, 123, apto 45\n"
            "CEP: 01310-100\n"
            "\n"
            "Segundo contato: joao@outro.com, celular 21987654321.\n"
        ),
        esperado=[
            ("NOME", "Ana Paula Ferreira"),
            ("EMAIL", "ana.ferreira@provedor.com.br"),
            ("TELEFONE", "(11) 98765-4321"),
            ("TELEFONE", "11 3456-7890"),
            ("ENDERECO", "Rua das Flores, 123, apto 45"),
            ("CEP", "01310-100"),
            ("EMAIL", "joao@outro.com"),
            ("TELEFONE", "21987654321"),
        ],
    ),
    Documento(
        nome="endereco com nome de pessoa no logradouro",
        texto=(
            "O imovel fica na Rua Joaquim Nabuco, 450, no bairro central. "
            "O proprietario Ricardo Alves Pinto pode ser contatado pelo "
            "e-mail ricardo.pinto@imobiliaria.com ou pelo telefone "
            "(21) 3456-7890.\n"
        ),
        esperado=[
            # O endereco inteiro tem que vencer o NER, que marca
            # "Joaquim Nabuco" como pessoa dentro dele.
            ("ENDERECO", "Rua Joaquim Nabuco, 450"),
            ("NOME", "Ricardo Alves Pinto"),
            ("EMAIL", "ricardo.pinto@imobiliaria.com"),
            ("TELEFONE", "(21) 3456-7890"),
        ],
    ),
    Documento(
        nome="controle negativo (nenhum dado pessoal)",
        texto=(
            "RELATORIO DE ESTOQUE\n"
            "\n"
            "O pedido 12345678901 foi entregue no prazo previsto. O protocolo "
            "de recebimento 98765 consta no sistema. O valor total apurado "
            "no periodo foi de 45.789,00 conforme o regulamento interno.\n"
        ),
        esperado=[],
    ),
]


def _spans_esperados(documento: Documento) -> list[tuple[int, int, str, str]]:
    """Localiza cada valor esperado no texto (todas as ocorrencias)."""
    spans = []
    for tipo, valor in documento.esperado:
        inicio = documento.texto.find(valor)
        assert inicio != -1, (
            f"corpus mal anotado: {valor!r} nao aparece em {documento.nome!r}"
        )
        while inicio != -1:
            spans.append((inicio, inicio + len(valor), tipo, valor))
            inicio = documento.texto.find(valor, inicio + 1)
    return spans


def _avaliar(documento: Documento, agressivo: bool) -> dict:
    deteccoes = detectar_tudo(documento.texto, agressivo=agressivo)
    esperados = _spans_esperados(documento)

    # Um esperado esta coberto se ALGUMA deteccao contem o trecho inteiro.
    # Deteccao maior que o esperado ("Sr. Fulano" em vez de "Fulano") conta
    # como acerto: redigiu demais, mas nao vazou.
    faltantes = [
        (valor, tipo)
        for inicio, fim, tipo, valor in esperados
        if not any(d.inicio <= inicio and d.fim >= fim for d in deteccoes)
    ]

    # Deteccao que nao encosta em nenhum esperado e falso positivo.
    falsos_positivos = [
        d for d in deteccoes
        if not any(d.inicio < fim and inicio < d.fim for inicio, fim, _, _ in esperados)
    ]

    total_esperado = len(esperados)
    acertos = total_esperado - len(faltantes)

    return {
        "recall": acertos / total_esperado if total_esperado else 1.0,
        "precisao": (
            (len(deteccoes) - len(falsos_positivos)) / len(deteccoes)
            if deteccoes else 1.0
        ),
        "faltantes": faltantes,
        "falsos_positivos": falsos_positivos,
        "total_deteccoes": len(deteccoes),
        "total_esperado": total_esperado,
    }


@pytest.mark.parametrize("documento", CORPUS, ids=lambda d: d.nome)
def test_recall_total_por_documento(documento, modelo_ner):
    """
    Recall tem que ser 1.0: todo dado pessoal anotado precisa ser redigido.

    Se este teste falhar, a lista de faltantes na mensagem e literalmente a
    lista do que vazaria no arquivo de saida.
    """
    metricas = _avaliar(documento, agressivo=False)
    assert metricas["recall"] == 1.0, (
        f"{documento.nome}: nao detectado -> {metricas['faltantes']}"
    )


def test_controle_negativo_nao_inventa_dado_pessoal(modelo_ner):
    """
    Documento sem dado pessoal nao deveria produzir muita deteccao.

    Nao exige zero: numero de pedido com 11 digitos pode passar por acaso em
    algum checksum, e o principio do projeto aceita esse tipo de erro. O que
    o teste pega e o caso em que o detector vira ruido puro.
    """
    negativo = next(d for d in CORPUS if "negativo" in d.nome)
    deteccoes = detectar_tudo(negativo.texto, agressivo=False)
    assert len(deteccoes) <= 2, (
        f"falsos positivos demais no controle negativo: "
        f"{[(d.tipo, d.texto) for d in deteccoes]}"
    )


def test_relatorio_de_metricas(modelo_ner, capsys):
    """
    Nao valida nada estrito -- imprime o placar do corpus inteiro.

    Rode com `pytest -s tests/test_corpus.py::test_relatorio_de_metricas`
    para ver os numeros ao comparar modelos ou mexer nos detectores.
    """
    linhas = ["", "=" * 72, "PLACAR DO CORPUS", "=" * 72]
    precisao_global = {}

    for agressivo in (False, True):
        modo = "agressivo" if agressivo else "padrao"
        linhas.append(f"\nmodo {modo}:")

        # Precisao e somada no corpus inteiro (micro-media), nao tirada por
        # documento: o controle negativo tem zero esperados, e ali a precisao
        # por documento so pode dar 0.0 ou 1.0 -- numero degenerado, que
        # afundaria qualquer media feita documento a documento.
        deteccoes_totais = 0
        falsos_totais = 0

        for documento in CORPUS:
            m = _avaliar(documento, agressivo)
            deteccoes_totais += m["total_deteccoes"]
            falsos_totais += len(m["falsos_positivos"])
            linhas.append(
                f"  {documento.nome[:42]:<44} "
                f"recall {m['recall']:.2f}  "
                f"({m['total_deteccoes']} deteccoes / {m['total_esperado']} esperados)"
            )
            for valor, tipo in m["faltantes"]:
                linhas.append(f"      NAO DETECTADO  [{tipo}] {valor!r}")
            for d in m["falsos_positivos"]:
                linhas.append(f"      falso positivo [{d.tipo}] {d.texto!r} via {d.detector}")

        precisao = (
            (deteccoes_totais - falsos_totais) / deteccoes_totais
            if deteccoes_totais else 1.0
        )
        precisao_global[modo] = precisao
        linhas.append(
            f"  --> precisao do corpus: {precisao:.2f} "
            f"({deteccoes_totais - falsos_totais}/{deteccoes_totais} deteccoes uteis)"
        )

    linhas.append("=" * 72)
    with capsys.disabled():
        print("\n".join(linhas))

    # Piso frouxo, so para pegar regressao grosseira. Precisao baixa custa
    # legibilidade, nao seguranca -- quem guarda a seguranca e o teste de
    # recall acima.
    assert precisao_global["padrao"] >= 0.70
    assert precisao_global["agressivo"] >= 0.60
