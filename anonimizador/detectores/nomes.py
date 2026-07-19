"""
Detector de nomes de pessoas, via NER (spaCy) + regras de apoio.

Diferente dos documentos, nome nao tem checksum: nao existe conta que prove
que "Joao da Silva" e uma pessoa e "Silva Materiais" e uma empresa. Por isso
aqui vale o principio de calibracao do projeto -- UNIAO de detectores, nunca
intersecao. Rodam tres estrategias sobre o mesmo texto e o que qualquer uma
achar vira deteccao:

  1. NER (pt_core_news_sm), entidades PER -- o detector principal;
  2. nome precedido de ROTULO ou PRONOME DE TRATAMENTO ("Nome: ...",
     "Contratante: ...", "Sr. ...") -- pega o que o NER perde;
  3. sequencias em CAIXA ALTA (so com agressivo=True) -- ver abaixo.

Por que (2) e (3) existem, se o NER ja funciona: modelos de NER sao treinados
em texto corrido com capitalizacao normal e degradam MUITO em documento
juridico/administrativo, que e cheio de "JOAO DA SILVA" em caixa alta e de
campos de formulario. Nesses trechos o NER sozinho tem recall baixo, e recall
baixo aqui significa dado pessoal vazando -- o pior caso do projeto.

A estrategia (3) fica atras de uma flag porque em caixa alta ela nao consegue
separar nome de titulo de secao: "CONTRATO DE PRESTACAO DE SERVICOS" tem a
mesma forma de "MARIA OLIVEIRA SANTOS". Ligada, redige demais; e a troca certa
quando o documento e critico.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from anonimizador.deteccao import Confianca, Deteccao, normalizar

__all__ = [
    "MODELO_PADRAO",
    "ModeloIndisponivelError",
    "carregar_modelo",
    "detectar_nomes",
]

MODELO_PADRAO = "pt_core_news_sm"

# Trechos maiores que isso sao processados em pedacos: o spaCy tem limite de
# tamanho por documento e o consumo de memoria cresce rapido.
LIMITE_CHUNK = 100_000


class ModeloIndisponivelError(RuntimeError):
    """Levantada quando o modelo de NER nao esta instalado."""


# --------------------------------------------------------------------------
# Regexes de apoio
# --------------------------------------------------------------------------

# Uma "palavra de nome": comeca com maiuscula (com ou sem acento).
_PALAVRA = r"[A-ZÀ-Ý][A-Za-zÀ-ÿ']+"
# Conectivos que aparecem no meio de nome composto, em qualquer caixa
# ("da Silva", "DA SILVA", "de Oliveira", "dos Santos").
#
# "e" fica DE FORA de proposito. Em documento, "X e Y" quase sempre e duas
# pessoas, nao um nome so: aceitar "e" transformaria "Pedro Lima e Beatriz
# Costa" numa entidade unica -- o que, no modo pseudonimo, daria um unico
# token a duas pessoas diferentes.
_CONECTIVO = r"[Dd][AaEeOo]s?"
# Separador dentro de um nome: espaco/tab, NUNCA quebra de linha. Com \s+ o
# padrao atravessa a quebra e engole o rotulo da linha seguinte -- em
# "Nome: Ana Paula Ferreira\nRG: ..." o nome casaria ate o "RG".
_ESPACO = r"[ \t]+"
# Nome completo: uma palavra, seguida de outras, com conectivos opcionais.
NOME_COMPLETO = rf"{_PALAVRA}(?:{_ESPACO}(?:{_CONECTIVO}{_ESPACO})?{_PALAVRA})*"

PRONOMES_TRATAMENTO = re.compile(
    rf"\b(?:Sr|Sra|Srta|Dr|Dra|Prof|Profa|Exmo|Exma|Ilmo|Ilma)\.?{_ESPACO}"
    rf"(?P<nome>{NOME_COMPLETO})"
)

# Rotulos de campo de formulario/documento. Comparados sem acento e sem caixa.
ROTULOS = (
    "nome",
    "nome completo",
    "nome civil",
    "nome social",
    "contratante",
    "contratado",
    "contratada",
    "requerente",
    "requerido",
    "autor",
    "autora",
    "reu",
    "re",
    "beneficiario",
    "beneficiaria",
    "titular",
    "cliente",
    "paciente",
    "funcionario",
    "empregado",
    "empregador",
    "responsavel",
    "declarante",
    "testemunha",
    "procurador",
    "socio",
    "representante",
    "segurado",
    "portador",
)

PADRAO_ROTULADO = re.compile(
    rf"(?P<rotulo>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ ]{{1,28}}?)\s*:\s*(?P<nome>{NOME_COMPLETO})"
)

# Caixa alta: 2+ palavras de 2+ letras. So usado no modo agressivo.
PADRAO_CAIXA_ALTA = re.compile(
    rf"\b([A-ZÀ-Ý]{{2,}}(?:{_ESPACO}(?:[A-ZÀ-Ý]{{2,}}|{_CONECTIVO})){{1,6}})\b"
)

# Vocabulario de documento/formulario -- palavras que nunca sao nome de pessoa.
# Usado em dois pontos:
#   1. descarta trecho em CAIXA ALTA que contenha qualquer uma delas (titulo
#      de secao nao e nome);
#   2. descarta entidade PER de UMA palavra so que seja uma delas.
#
# (2) e a unica vez no projeto em que uma deteccao e descartada, e vai na
# contramao do principio "prefere falso positivo". A justificativa e estreita:
# o pt_core_news_sm marca substantivo comum capitalizado no inicio de linha
# como PER ("Contato do paciente:" -> PER "Contato"), e nenhuma palavra desta
# lista e nome de pessoa em portugues. So vale para deteccao de UMA palavra --
# nome composto nunca e afetado.
#
# AO EDITAR: entra so substantivo comum que nao seja tambem sobrenome. Nomes
# como Rosa, Neves, Cruz, Franca e Pereira sao palavras comuns E sobrenomes
# reais -- incluir qualquer um deles criaria falso negativo de verdade.
_VOCABULARIO_DOCUMENTO = {
    # tipos de documento e estrutura de texto juridico
    "contrato", "prestacao", "servicos", "servico", "declaracao", "termo",
    "anexo", "clausula", "paragrafo", "artigo", "capitulo", "secao", "titulo",
    "documento", "certidao", "requerimento", "procuracao", "recibo", "nota",
    "fiscal", "oficio", "memorando", "ata", "edital", "aviso", "comunicado",
    "laudo", "parecer", "comprovante", "extrato", "boletim", "formulario",
    # cabecalho administrativo
    "relatorio", "ficha", "cadastro", "atendimento", "protocolo", "pedido",
    "registro", "controle", "resumo", "historico", "situacao", "observacoes",
    "sistema", "setor", "departamento", "unidade", "filial", "matriz",
    # entidades e lugares
    "empresa", "ltda", "sociedade", "banco", "agencia", "conta",
    "endereco", "rua", "avenida", "bairro", "cidade", "estado", "cep",
    "brasil", "republica", "federativa", "ministerio", "secretaria",
    "tribunal", "justica", "vara", "comarca", "processo", "autos",
    # rotulos de documento
    "cpf", "cnpj", "rg", "cnh", "pis", "pasep", "nit", "identidade",
    "objeto", "valor", "total", "data", "assinatura", "testemunhas",
    "partes", "presente", "instrumento", "particular", "geral",
    "estoque", "produto", "quantidade", "preco", "pagamento", "fatura",
    "periodo", "prazo", "vencimento", "interno",
    # campos de contato e de cabecalho de formulario
    "contato", "assunto", "referencia", "remetente", "destinatario",
    "interessado", "solicitante", "emitente", "favorecido",
    "telefone", "celular", "email", "fone", "whatsapp",
    "numero", "codigo", "tipo", "status", "categoria", "descricao",
    "natureza", "finalidade", "motivo", "origem", "destino", "complemento",
}


# --------------------------------------------------------------------------
# Modelo
# --------------------------------------------------------------------------

@lru_cache(maxsize=4)
def carregar_modelo(nome: str = MODELO_PADRAO) -> Any:
    """
    Carrega o modelo de NER, uma vez por processo (lru_cache).

    Nao faz chamada de rede: `spacy.load` le o modelo ja instalado no disco.
    Se o modelo nao estiver instalado, levanta ModeloIndisponivelError com a
    instrucao de instalacao em vez de tentar baixar.
    """
    try:
        import spacy
    except ImportError as erro:  # pragma: no cover
        raise ModeloIndisponivelError(
            "spaCy nao esta instalado. Rode: pip install -r requirements.txt"
        ) from erro

    # So o NER interessa aqui; desligar parser/lemmatizer/tagger acelera
    # bastante e reduz memoria. Se o modelo nao permitir, carrega inteiro.
    desligar = ["parser", "lemmatizer", "attribute_ruler", "tagger", "morphologizer"]
    try:
        return spacy.load(nome, disable=desligar)
    except OSError as erro:
        raise ModeloIndisponivelError(
            f"Modelo de NER '{nome}' nao encontrado.\n"
            f"Instale com: python -m spacy download {nome}\n"
            "(o download acontece UMA VEZ; depois o anonimizador roda offline)"
        ) from erro
    except Exception:  # pragma: no cover - fallback defensivo
        return spacy.load(nome)


# --------------------------------------------------------------------------
# Estrategias
# --------------------------------------------------------------------------

def _eh_vocabulario_de_documento(trecho: str) -> bool:
    """
    True para trecho de UMA palavra que e vocabulario de formulario.

    Restrito a uma palavra de proposito: "Contato" e rotulo de campo, mas
    "Contato Silva" (se existisse) seria nome. Nome composto nunca cai aqui.
    """
    palavras = normalizar(trecho).split()
    return len(palavras) == 1 and palavras[0] in _VOCABULARIO_DOCUMENTO


def _fatiar(texto: str, limite: int = LIMITE_CHUNK) -> list[tuple[int, str]]:
    """
    Divide texto longo em pedacos, devolvendo (offset_no_original, trecho).

    Corta preferencialmente em quebra de linha para nao partir um nome ao
    meio -- um nome cortado no limite do pedaco viraria falso negativo.
    """
    if len(texto) <= limite:
        return [(0, texto)]

    pedacos: list[tuple[int, str]] = []
    inicio = 0
    while inicio < len(texto):
        fim = min(inicio + limite, len(texto))
        if fim < len(texto):
            quebra = texto.rfind("\n", inicio + limite // 2, fim)
            if quebra != -1:
                fim = quebra + 1
        pedacos.append((inicio, texto[inicio:fim]))
        inicio = fim
    return pedacos


def _expandir_entidade(doc: Any, ent: Any) -> tuple[int, int]:
    """
    Estende a entidade sobre conectivo + palavra seguinte.

    O pt_core_news_sm as vezes corta nome composto em "Joao" + "Silva" ou
    devolve so "Joao" em "Joao da Silva". Como o redator troca exatamente o
    trecho detectado, um corte desses deixaria "da Silva" visivel no texto
    final. A expansao so anda sobre conectivo seguido de palavra capitalizada
    -- padrao especifico o bastante para nao engolir a frase seguinte.

    "e" NAO entra na lista: em "Pedro Lima e Beatriz Costa" ele emendaria duas
    pessoas numa entidade so (ver comentario em _CONECTIVO).
    """
    fim = ent.end
    while fim + 1 < len(doc):
        conectivo = doc[fim]
        seguinte = doc[fim + 1]
        eh_conectivo = conectivo.text.lower() in {"da", "de", "do", "das", "dos"}
        seguinte_capitalizada = bool(seguinte.text) and seguinte.text[0].isupper()
        if eh_conectivo and seguinte_capitalizada and seguinte.text.isalpha():
            fim += 2
        else:
            break

    span = doc[ent.start : fim]
    return span.start_char, span.end_char


def _detectar_por_ner(texto: str, modelo: Any) -> list[Deteccao]:
    deteccoes: list[Deteccao] = []

    for deslocamento, pedaco in _fatiar(texto):
        doc = modelo(pedaco)
        for ent in doc.ents:
            if ent.label_ != "PER":
                continue

            inicio_char, fim_char = _expandir_entidade(doc, ent)
            bruto = pedaco[inicio_char:fim_char]

            # O proprio spaCy as vezes estende a entidade por cima da quebra de
            # linha e captura o rotulo do campo seguinte -- em "Nome: Ana Paula
            # Ferreira\nRG: ..." ele devolve "Ana Paula Ferreira\nRG". Corta na
            # primeira quebra: nome de pessoa nao atravessa linha.
            if "\n" in bruto:
                bruto = bruto.split("\n", 1)[0]

            trecho = bruto.strip()
            if len(trecho) < 2:
                continue
            if _eh_vocabulario_de_documento(trecho):
                continue

            # .strip() pode ter tirado espacos da ponta; realinha os offsets.
            inicio_real = deslocamento + inicio_char + bruto.index(trecho)
            deteccoes.append(
                Deteccao(
                    texto=trecho,
                    inicio=inicio_real,
                    fim=inicio_real + len(trecho),
                    tipo="NOME",
                    confianca=Confianca.ALTA,
                    detector="nomes:ner",
                )
            )

    return deteccoes


def _detectar_por_regra(texto: str) -> list[Deteccao]:
    """Nomes precedidos de pronome de tratamento ou de rotulo de campo."""
    deteccoes: list[Deteccao] = []

    for match in PRONOMES_TRATAMENTO.finditer(texto):
        deteccoes.append(
            Deteccao(
                texto=match.group("nome"),
                inicio=match.start("nome"),
                fim=match.end("nome"),
                tipo="NOME",
                confianca=Confianca.ALTA,
                detector="nomes:tratamento",
            )
        )

    for match in PADRAO_ROTULADO.finditer(texto):
        rotulo = normalizar(match.group("rotulo")).strip()
        # O rotulo casado pode vir grudado no texto anterior ("... e o
        # Contratante"); basta que TERMINE com um rotulo conhecido.
        if not any(rotulo == r or rotulo.endswith(" " + r) for r in ROTULOS):
            continue
        deteccoes.append(
            Deteccao(
                texto=match.group("nome"),
                inicio=match.start("nome"),
                fim=match.end("nome"),
                tipo="NOME",
                confianca=Confianca.ALTA,
                detector="nomes:rotulo",
            )
        )

    return deteccoes


def _detectar_caixa_alta(texto: str) -> list[Deteccao]:
    """
    Sequencias em CAIXA ALTA que podem ser nome (modo agressivo).

    Filtra por lista de ruido para nao redigir cabecalho e titulo de secao,
    mas ainda assim e a estrategia mais barulhenta das tres -- por isso e
    opcional.
    """
    deteccoes: list[Deteccao] = []

    for match in PADRAO_CAIXA_ALTA.finditer(texto):
        trecho = match.group(1)
        palavras = normalizar(trecho).split()
        if any(p in _VOCABULARIO_DOCUMENTO for p in palavras):
            continue
        if len([p for p in palavras if len(p) > 2]) < 2:
            continue
        deteccoes.append(
            Deteccao(
                texto=trecho,
                inicio=match.start(1),
                fim=match.end(1),
                tipo="NOME",
                confianca=Confianca.BAIXA,
                detector="nomes:caixa_alta",
            )
        )

    return deteccoes


def detectar_nomes(
    texto: str,
    modelo: Any | None = None,
    nome_modelo: str = MODELO_PADRAO,
    agressivo: bool = False,
) -> list[Deteccao]:
    """
    Encontra nomes de pessoas em um texto.

    `modelo` permite injetar um pipeline spaCy ja carregado (util em teste e
    para nao recarregar a cada arquivo). `agressivo=True` liga a varredura de
    caixa alta -- mais recall, bem mais falso positivo.

    O resultado pode conter sobreposicoes, ja que as estrategias rodam em
    paralelo sobre o mesmo texto; quem resolve isso e
    `deteccao.resolver_sobreposicoes`, chamado pelo agregador.
    """
    if modelo is None:
        modelo = carregar_modelo(nome_modelo)

    deteccoes = _detectar_por_ner(texto, modelo)
    deteccoes.extend(_detectar_por_regra(texto))
    if agressivo:
        deteccoes.extend(_detectar_caixa_alta(texto))

    return deteccoes
