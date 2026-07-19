# anonimizador

Remove ou pseudonimiza dados pessoais (nomes e números de documento) de arquivos,
para que documentos com dados sensíveis possam ser tratados e compartilhados sem
risco de vazamento.

**Roda 100% local/offline.** Nenhuma chamada de rede em tempo de execução, nenhuma
telemetria — ver [Garantia de operação offline](#garantia-de-operação-offline).

## Instalação

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # Linux/macOS

pip install -r requirements-dev.txt
python -m spacy download pt_core_news_sm
```

O `spacy download` é a **única** etapa que usa rede, e acontece uma vez só: ele
baixa o modelo de reconhecimento de nomes para o disco. Depois disso o
anonimizador nunca mais precisa de conexão.

> Se o `spacy download` falhar com `ModuleNotFoundError: No module named 'click'`,
> rode `pip install click` — versões recentes do `typer` deixaram de trazer o
> `click`, do qual a CLI do spaCy ainda depende.

## Uso

```bash
python -m anonimizador documento.txt                        # modo anônimo (padrão)
python -m anonimizador documento.txt --modo pseudonimo
python -m anonimizador documento.txt --simular              # só lista, não grava
```

### Os dois modos

| | **anônimo** (padrão) | **pseudônimo** |
|---|---|---|
| Substituição | `[NOME]`, `[CPF]` | `PESSOA_001`, `CPF_001` |
| Mesma pessoa citada 2x | dois marcadores **sem vínculo** | **mesmo token** nas duas |
| Gera mapa de-para | não | sim |
| Reversível | não | sim, com o mapa |
| Para quê | compartilhar o documento | analisar preservando a coerência do texto |

O modo anônimo é o padrão por ser o mais seguro: sem mapa não há o que vazar, e
sem consistência entre menções não dá para reidentificar ninguém nem por
correlação (não se sabe se dois `[NOME]` são a mesma pessoa).

O modo pseudônimo preserva a coerência — dá para acompanhar que `PESSOA_001`
aparece em vários pontos do texto — mas gera o arquivo `<documento>.mapa.json`:

> ⚠️ **O mapa reverte a pseudonimização.** Ele merece o mesmo cuidado que o
> documento original. Se vazar junto com o texto tratado, os dois juntos
> equivalem ao documento sem tratamento nenhum. Guarde separado, ou apague
> depois de usar. O `.gitignore` já bloqueia mapas para eles não irem parar no
> histórico do git.

### Opções

| flag | efeito |
|---|---|
| `-m, --modo` | `anonimo` (padrão) ou `pseudonimo` |
| `-o, --saida` | arquivo de saída (padrão: `<arquivo>.anonimizado.<ext>`) |
| `--mapa` | onde gravar o mapa (padrão: `<arquivo>.mapa.json`) |
| `--simular` | lista o que seria detectado e **não grava nada** |
| `--sem-nomes` | pula o NER (não carrega o modelo — bem mais rápido) |
| `--agressivo` | liga a varredura de nomes em CAIXA ALTA (mais recall, mais falso positivo) |
| `-f, --forcar` | sobrescreve saída existente |

`--simular` **imprime os valores reais na tela**. Use só para calibrar, em
ambiente confiável.

## O que é detectado

### Com dígito verificador (validação matemática, confiança alta)

O checksum é o que separa dado real de número qualquer: um número de pedido com
11 dígitos tem o formato de CPF, mas não passa no dígito verificador e é
descartado.

| documento | módulo |
|---|---|
| CPF | [`detectores/cpf.py`](anonimizador/detectores/cpf.py) |
| CNPJ — numérico **e alfanumérico** | [`detectores/cnpj.py`](anonimizador/detectores/cnpj.py) |
| Título de eleitor | [`detectores/titulo_eleitor.py`](anonimizador/detectores/titulo_eleitor.py) |
| PIS/PASEP/NIT | [`detectores/pis.py`](anonimizador/detectores/pis.py) |
| CNH | [`detectores/cnh.py`](anonimizador/detectores/cnh.py) |

**CNPJ alfanumérico (IN RFB nº 2.229/2024, vigente a partir de 07/2026):** as 12
primeiras posições passam a aceitar letras maiúsculas; os 2 dígitos
verificadores continuam numéricos. O cálculo segue em módulo 11, com cada
caractere convertido por *ASCII − 48*. O detector aceita os dois formatos —
validado contra o exemplo oficial `12.ABC.345/01DE-35`. Um validador que só
aceitasse `\d` deixaria passar **todo** CNPJ no formato novo.

### Contato (formato inequívoco ou validação estrutural)

| dado | módulo | o que sustenta a detecção |
|---|---|---|
| E-mail | [`detectores/email.py`](anonimizador/detectores/email.py) | âncora obrigatória (`@`) + TLD |
| Telefone | [`detectores/telefone.py`](anonimizador/detectores/telefone.py) | DDD da lista oficial + prefixo coerente |
| Endereço e CEP | [`detectores/endereco.py`](anonimizador/detectores/endereco.py) | tipo de logradouro + número; CEP `12345-678` |

**Telefone** não tem dígito verificador, mas tem estrutura suficiente para
filtrar: o DDD precisa existir de verdade (20, 23, 30, 36, 39... não existem),
celular tem 9 dígitos começando com 9, fixo tem 8 começando com 2-5. Na prática
isso descarta bem — um CPF cru como `11144477735` tem DDD 11 válido, mas o
terceiro dígito é 1, então não passa. Número sem DDD só é aceito com `Tel:`
ou `Celular:` por perto.

**Endereço é o detector mais fraco do projeto** — texto livre, sem checksum e
sem começo/fim delimitados. A âncora é o tipo de logradouro na frente
(`Rua`, `Avenida`, `Praça`) e o número no fim; exigir os dois derruba muito
falso positivo, ao custo de não detectar endereço sem número. O CEP com hífen,
esse sim, é confiável e vale sozinho.

### Sem dígito verificador (só formato, confiança menor)

| documento | módulo |
|---|---|
| RG | [`detectores/rg.py`](anonimizador/detectores/rg.py) |
| Passaporte | [`detectores/passaporte.py`](anonimizador/detectores/passaporte.py) |

Não existe checksum nacional padronizado para esses dois — o formato varia por
órgão emissor. Aqui só há reconhecimento de formato, e **o risco de falso
negativo é real** (um RG em formato estadual incomum pode não casar). Para
compensar, os dois usam contexto: um número solto de 9 dígitos só vira RG se
houver `RG:`, `Identidade` ou `SSP` por perto. Sem essa regra, todo número de
protocolo do documento viraria "RG".

### Nomes de pessoas

NER com spaCy `pt_core_news_sm`, em união com duas regras de apoio
([`detectores/nomes.py`](anonimizador/detectores/nomes.py)):

1. entidades `PER` do modelo;
2. nome após rótulo ou pronome de tratamento (`Nome:`, `Contratante:`, `Sr.`);
3. sequências em CAIXA ALTA — só com `--agressivo`.

(2) e (3) existem porque modelos de NER são treinados em texto corrido e
degradam muito em documento jurídico/administrativo, cheio de caixa alta e campo
de formulário. Medido com `pt_core_news_sm`: em
`"...entre MARIA OLIVEIRA SANTOS e a empresa"` o NER devolve apenas `MARIA` —
`OLIVEIRA SANTOS` vazaria. Com `--agressivo`, o nome completo é pego.

## Princípio de calibração

Não existe detector de nome 100% preciso. Entre os dois erros possíveis:

- **falso positivo** — redige algo que não precisava: custa legibilidade;
- **falso negativo** — deixa passar um dado real: **é o pior caso do projeto.**

Então o sistema é deliberadamente agressivo: detectores rodam em **união, nunca
interseção**, e detecção de baixa confiança ainda é redigida. A confiança serve
para desempatar sobreposições e alimentar o relatório — nunca para descartar.

**Há exatamente uma exceção**, em `nomes.py`: entidade `PER` de **uma palavra
só** que seja vocabulário de formulário (`Contato`, `Telefone`, `Assunto`) é
descartada. O `pt_core_news_sm` marca substantivo comum capitalizado no início
de linha como pessoa, e sem esse filtro `"Contato do paciente:"` virava
`"[NOME] do paciente:"`. A lista contém só substantivos comuns que não são
sobrenome brasileiro — há um teste (`test_vocabulario_nao_contem_sobrenome_comum`)
travando isso, porque incluir `Rosa`, `Neves` ou `Cruz` ali criaria falso
negativo de verdade. Nome composto nunca é afetado.

## Como está organizado

```
anonimizador/
  deteccao.py          Deteccao, Confianca, união e resolução de sobreposições
  detectores/          um módulo por tipo de dado; __init__.py agrega todos
  extratores/          arquivo -> texto puro (hoje: txt)
  redator.py           aplica as substituições conforme o modo
  cli.py               ponto de entrada
```

A separação existe para que cada eixo cresça sozinho:

- **novo tipo de documento** → escreva o módulo no padrão do `cpf.py` e registre
  em `DETECTORES_DOCUMENTO` (em `detectores/__init__.py`). Redator e CLI não mudam.
- **novo tipo de arquivo** (PDF, Excel) → escreva o extrator com a assinatura
  `(Path) -> str` e registre em `EXTRATORES` (em `extratores/__init__.py`).
  Detecção e redação não mudam.

`Deteccao` mora em `deteccao.py`, não em `cpf.py`: todo detector precisa dela, e
mantê-la no detector de CPF obrigaria os outros a importar de lá. O nome segue
reexportado por `detectores/cpf.py`.

## Testes

```bash
pytest                                              # tudo
pytest -s tests/test_corpus.py                      # placar de precisão/recall
```

`tests/test_corpus.py` mantém um corpus anotado e mede **precisão e recall** a
cada rodada — é o que permite comparar antes/depois ao trocar de modelo
(`pt_core_news_lg`, Presidio) em vez de julgar no olho. O teste **exige recall
1.0**: cada ponto faltante é um dado pessoal que vazaria. A precisão é só
reportada, com piso frouxo.

Placar atual (6 documentos, `pt_core_news_sm`):

```
modo padrão     recall 1.00   precisão 1.00 (26/26 detecções úteis)
modo agressivo  recall 1.00   precisão 1.00 (26/26 detecções úteis)
```

Precisão 1.00 aqui significa "nenhum falso positivo **neste corpus**" — não que
o detector seja perfeito. O corpus é pequeno (6 documentos); ele serve para
pegar regressão, não para atestar qualidade absoluta.

Para acrescentar um caso, adicione um `Documento` em `CORPUS` com todos os dados
pessoais listados em `esperado`.

## Garantia de operação offline

Nenhum módulo do pacote importa `requests`, `urllib`, `socket` ou `httpx`.
`spacy.load()` lê o modelo já instalado no disco; se ele não estiver lá, o
programa **falha com instrução de instalação** em vez de tentar baixar. Para
conferir:

```bash
grep -rE "requests|urllib|socket|httpx|http\." anonimizador/
```

## Limitações conhecidas

- **RG e passaporte não têm validação matemática** — só formato. RG em formato
  estadual incomum pode escapar.
- **NER degrada em CAIXA ALTA.** Documento predominantemente em caixa alta deve
  ser rodado com `--agressivo`.
- **Correferência não é resolvida:** no modo pseudônimo, `João da Silva` e
  `João` recebem tokens diferentes mesmo sendo a mesma pessoa. O erro é na
  direção segura — separa demais, nunca junta duas pessoas sob um token.
- **Números de 11 dígitos são ambíguos:** CPF, PIS, CNH e celular com DDD têm o
  mesmo tamanho e um número pode passar em mais de uma validação. Isso não
  afeta a segurança (o número é redigido de todo jeito), só o rótulo escolhido.
- **Endereço sem número não é detectado** (`"mora na Rua das Flores"`), nem
  endereço sem o tipo de logradouro na frente (`"Flores, 123"`). São falsos
  negativos conhecidos e assumidos — é o preço de manter a precisão do
  detector mais frágil do projeto.
- **Só TXT por enquanto.** PDF e Excel são os próximos extratores.
- **Data de nascimento ainda não é detectada.** É o dado pessoal que falta;
  data é difícil porque o formato colide com toda outra data do documento
  (emissão, vencimento, assinatura) e só o contexto separa.
