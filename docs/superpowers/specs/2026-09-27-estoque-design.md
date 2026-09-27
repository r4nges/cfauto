# CFAUTO — Sub-projeto 2: Estoque — Design

- **Data:** 2026-09-27
- **Status:** aprovado em brainstorming (usuário autorizou seguir para plano e implementação)
- **Base:** `docs/superpowers/specs/2026-09-23-cfauto-arquitetura-design.md` (spec de arquitetura, manda sobre esta onde não houver decisão nova aqui), `referencia/analise/estoque-compras-usuarios.md`, `referencia/appsscript/01-ESTOQUE.gs`
- **Branch:** `feat/estoque`

## 1. Objetivo e escopo

Entregar o módulo Estoque utilizável de ponta a ponta: cadastro de produto e serviço, ajuste de estoque com motivo, histórico de movimentações por produto, entrada de mercadoria por XML de NF-e com tela de conferência, estorno de nota e cadastro de Bens Físicos. É a base do PDV (sub-projeto 4) e do Markup/DRE (sub-projeto 6).

Fora deste sub-projeto: markup e rateio (6), estoque mínimo automático e alertas (7), fornecedor/cotação (8), baixa por venda (4), importador de planilhas (9).

### 1.1 Decisões do brainstorming (27/09)

| # | Decisão | Alternativas descartadas |
|---|---|---|
| D1 | Entrada de NF-e **só por arquivo XML**. O serviço recebe os bytes do XML; outra fonte (SEFAZ com certificado A1) pode ser plugada depois sem mudar o resto. Resolve a pendência §9 da spec de arquitetura. | SEFAZ NFeDistribuicaoDFe (certificado A1, SOAP/mTLS, ~1 semana); API de terceiro (meudanfe: contrato incerto, risco na demo) |
| D2 | Custo da entrada = **custo efetivo** do item: `vProd − vDesc + vFrete + vSeg + vOutro + vIPI + vICMSST + vFCPST`. | Só `vUnCom` (original) |
| D3 | **Bens Físicos** ficam em Configurações › CFAUTO (só admin). | Aba no Estoque (módulo ESTOQUE) |
| D4 | **Ajuste de estoque** é ação própria com motivo; o formulário de edição não altera a quantidade (só o estoque inicial, no cadastro). | Campo editável no formulário (original) |
| D5 | **Livro de movimentos** (`movimento_estoque`) + saldo em `produto.estoque`, alterado exclusivamente por `movimentar()`. | Só campo + auditoria; estoque 100% derivado |
| D6 | O pacote do painel CFAUTO se chama `cfauto/gestao/` (a spec de arquitetura dizia `cfauto/cfauto/`). | — |

## 2. Modelo de dados (migration `0002_estoque`)

Convenções da spec de arquitetura §3 valem (PK inteira, `criado_em`/`atualizado_em`, `ativo` em cadastros, `Dinheiro()` 2 casas, `Quantidade()` 3 casas).

### 2.1 Novidades no `core`

- **`Custo()`** = `DecimalEscalado(4)`: custo unitário com 4 casas. Com 2 casas, um item de R$ 0,035 viraria R$ 0,04 (14% de erro no fracionado). Usado em `produto.preco_entrada`, `servico_material.custo_unit` e nos campos `preco_entrada_*` do item de nota.
- **`sequencia`** (`nome` PK, `ultimo` inteiro) e `core/sequencias.py::proximo_codigo(s, nome, *, prefixo="", digitos)`: incrementa e devolve o código formatado (`0001`, `SERV-001`, `BEM-001`). Número nunca reaproveitado, mesmo após desativação. Passa de 9999 sem quebrar (`10000`). Reusada depois por Clientes (`CLI-`) e Saídas (`SAI-`).
- **`core/dates.para_datahora`** passa a aceitar ISO 8601 com fuso (`2026-09-20T10:15:00-03:00`), descartando o fuso (hora de parede local).
- **Erros novos** em `core/errors.py`: `EanDuplicado`, `NotaJaImportada`, `XmlInvalido(ValorInvalido)`, `EstoqueInsuficiente` (este já previsto na spec de arquitetura §6.6).

### 2.2 Tabelas do Estoque (`cfauto/estoque/models.py`)

**produto**

| Campo | Tipo | Regra |
|---|---|---|
| `codigo` | str(20), único | sequência `produto`, 4 dígitos |
| `ean` | str(14), único, nulo | só dígitos, 1–14; vazio → nulo; sem validar dígito verificador (códigos internos são comuns) |
| `descricao` | str(200) | obrigatória, `strip()`; **sem** a `limparDescricao` do original (apagava dados legítimos) |
| `categoria` | str(60) | texto livre, padrão `""` |
| `embalagem` | str(30) | padrão `"Unidade"` |
| `fator` | Quantidade | > 0, padrão 1: unidades de estoque por embalagem |
| `data_ult_entrada` | date, nulo | carimbada **só** no cadastro e na entrada por NF-e |
| `preco_entrada` | Custo | custo da embalagem do produto, ≥ 0 |
| `preco_venda` | Dinheiro | ≥ 0, padrão 0 |
| `preco_promocional` | Dinheiro, nulo | > 0 quando informado |
| `estoque` | Quantidade | saldo; só muda via `movimentar()` |
| `estoque_minimo` | Quantidade | ≥ 0, padrão 0 |
| `estoque_minimo_manual` | bool | o job do sub-projeto 7 não sobrescreve quando `True` |
| `destino` | enum str | `REVENDA` (padrão), `USO_CONSUMO`, `MATERIA_PRIMA`; sem efeito em cálculo por enquanto |
| `markup_pct` | DecimalEscalado(2), nulo | lógica no sub-projeto 6 |
| `markup_manual` | bool | lógica no sub-projeto 6 |
| `ativo` | bool | exclusão lógica |

Propriedades Python (nunca gravadas):
- `preco_fracionado = preco_entrada / fator`
- `margem = (preco_venda − preco_fracionado) / preco_venda`; `None` se `preco_venda ≤ 0` ou `preco_entrada ≤ 0`.

**servico**: `codigo` (sequência `servico`, `SERV-` + 3 dígitos), `nome` str(120), `mao_obra_pct` DecimalEscalado(2) ≥ 0, `ativo`.
**servico_material**: `servico_id` FK, `descricao` str(120), `custo_unit` Custo > 0, `qtd` Quantidade > 0.
Propriedades de `Servico`: `custo_materiais = Σ(custo_unit × qtd)`; `preco = arredondar(custo_materiais × (1 + mao_obra_pct/100))`.

**movimento_estoque**: `produto_id` FK, `data_hora` (índice), `tipo` enum (`CADASTRO`, `ENTRADA_NF`, `ESTORNO_NF`, `AJUSTE`, `VENDA`, `CANCELAMENTO_VENDA`), `quantidade` Quantidade com sinal (≠ 0), `saldo_apos` Quantidade, `usuario_id` FK, `motivo` enum nulo (`INVENTARIO`, `PERDA_AVARIA`, `CONSUMO_INTERNO`, `OUTRO`; só em `AJUSTE`), `observacao` str(200) nula, `nota_entrada_item_id` FK nulo. `VENDA`/`CANCELAMENTO_VENDA` existem no enum; a coluna `venda_item_id` chega na migration do sub-projeto 4.

**nota_entrada**: `chave` str(44), `numero` int, `serie` int, `modelo` int (55/65), `emitente_cnpj` str(14), `emitente_nome` str(120), `data_emissao` date, `data_entrada` datetime, `valor_total` Dinheiro (`vNF`), `usuario_id` FK, `xml_original` Text, `estornada` bool, `estornada_em` datetime nulo, `estornada_por` FK nulo.
Índice **único parcial** `ix_nota_entrada_chave_ativa` em `chave` `WHERE estornada = 0`: impede importar duas vezes, mas permite reimportar uma nota estornada (corrigir vínculo errado = estornar e reimportar).

**nota_entrada_item**: `nota_id` FK, `n_item` int, `codigo_fornecedor` str(60) (`cProd`), `ean` str(14) nulo, `descricao_nota` str(200), `unidade` str(10) (`uCom`), `qtd_nota` DecimalEscalado(4) (`qCom`), `valor_produto`, `desconto`, `frete`, `seguro`, `outros`, `ipi`, `icms_st` (Dinheiro, padrão 0), `custo_total` Dinheiro, `produto_id` FK nulo (nulo = item ignorado), `fator` Quantidade nulo, `qtd_estoque` Quantidade nulo, `preco_entrada_aplicado` Custo nulo, `preco_entrada_anterior` Custo nulo, `data_ult_entrada_anterior` date nulo.

**vinculo_fornecedor_produto**: `emitente_cnpj` str(14), `codigo_fornecedor` str(60), `produto_id` FK, `fator` Quantidade; único em (`emitente_cnpj`, `codigo_fornecedor`); tem timestamps.

### 2.3 Bens Físicos (`cfauto/gestao/models.py`)

**bem_fisico**: `codigo` (sequência `bem`, `BEM-` + 3 dígitos), `descricao` str(200), `tipo` enum (`MOVEL`, `INTANGIVEL`, `OUTROS`), `valor` Dinheiro > 0, `data_cadastro` date (padrão hoje, editável), `ativo` (baixa = `False`, sai do Balancete).

Todos os modelos são importados em `cfauto/modelos.py`; o teste existente `test_modelos_batem_com_migracoes` garante que a migration bate com os modelos.

## 3. Regras de serviço

Padrões da spec de arquitetura §2.2: funções recebem `Session` + `Ator`, verificam permissão na entrada, escrevem em transação do chamador e auditam na mesma transação.

**Permissões:** tudo do Estoque exige `Modulo.ESTOQUE`; **estorno de nota exige admin**; Bens Físicos exige `Modulo.CFAUTO` (só admin).

### 3.1 Movimentação (`estoque/movimentos.py`)

`movimentar(s, ator, produto, quantidade, tipo, *, motivo=None, observacao=None, nota_item=None) -> MovimentoEstoque`: soma `quantidade` (≠ 0) ao `produto.estoque`, grava o movimento com `saldo_apos` e `data_hora = clock.agora()`. Não verifica permissão nem bloqueia saldo negativo: quem chama decide. Única função que altera `produto.estoque`.

Invariante testada: para todo produto, `Σ movimento.quantidade == produto.estoque`.

### 3.2 Produto (`estoque/produtos.py`)

- **criar_produto(dados)**: valida os campos da tabela §2.2. EAN já usado por outro produto (ativo ou não) → `EanDuplicado` citando código e descrição do dono. Gera `codigo`. **Carimba `data_ult_entrada = hoje`**, mesmo com estoque inicial 0 (como o original). Estoque inicial > 0 gera movimento `CADASTRO`. `estoque_minimo > 0` no cadastro → `estoque_minimo_manual = True`. Auditoria `criar`.
- **atualizar_produto(id, dados)**: altera descrição, EAN, categoria, embalagem, fator, preço de entrada, preço de venda, preço promocional, estoque mínimo e destino. **Não** altera estoque nem `data_ult_entrada`. Se `estoque_minimo` mudou → `estoque_minimo_manual = True`; senão vale o flag enviado (permite voltar ao automático). Não mexe em `markup_pct`/`markup_manual` (decisão do sub-projeto 6). Auditoria `alterar` com antes/depois.
- **desativar_produto / reativar_produto**: permitido com estoque ≠ 0. Auditoria.
- **ajustar_estoque(id, nova_quantidade, motivo, observacao)**: `nova_quantidade ≥ 0`; diferença zero → `ValorInvalido("Estoque já está com essa quantidade.")`; motivo `OUTRO` exige observação. Movimento `AJUSTE` com a diferença. Auditoria `ajustar_estoque` (antes/depois do saldo, motivo). Não carimba data.
- **buscar_produtos(termo, incluir_inativos=False)**: termo vazio → todos por descrição. Senão, em ordem: código exato (aceita sem zeros: `1` → `0001`) e EAN exato; depois descrição normalizada (NFKD sem acentos + `casefold`) começando pelo termo; depois contendo **todas** as palavras do termo. Ranking em Python (volume de loja pequena). Nunca "qualquer coluna contém".
- **obter_produto(id)**, **listar_movimentos(produto_id)** (mais recente primeiro), **categorias_usadas()** (distintas, não vazias, ordenadas).

### 3.3 Serviço (`estoque/servicos.py`)

`criar_servico`, `atualizar_servico` (substitui a lista inteira de materiais), `desativar_servico`/`reativar_servico`, `listar_servicos(incluir_inativos)`. Validações: nome obrigatório; ao menos 1 material; material com descrição, `custo_unit > 0`, `qtd > 0`; `mao_obra_pct ≥ 0`. Auditoria com snapshot (nome, %, materiais, preço). Serviço nunca movimenta estoque. Diferente do original, serviço tem edição.

### 3.4 Leitura do XML (`estoque/nfe.py`, puro, sem banco)

`ler_nfe(conteudo: bytes) -> NotaFiscalLida`:
- Parser `defusedxml.ElementTree` (nova dependência declarada). Namespace `http://www.portalfiscal.inf.br/nfe`. Aceita raiz `nfeProc` ou `NFe`.
- Chave: atributo `infNFe@Id` sem o prefixo `NFe`; 44 dígitos com dígito verificador módulo 11 válido.
- Cabeçalho: `ide/nNF`, `ide/serie`, `ide/mod`, `ide/dhEmi` (ou `dEmi`, NF-e 2.0) via `core.dates`; `emit/CNPJ` (ou `CPF`), `emit/xNome`; `dest/CNPJ` (ou `CPF`, pode faltar); `total/ICMSTot/vNF`.
- Itens (`det`, atributo `nItem`): `cProd`, `cEAN`, `cEANTrib`, `xProd`, `uCom`, `qCom`, `vUnCom`, `uTrib`, `qTrib`, `vProd`, `vDesc`, `vFrete`, `vSeg`, `vOutro`, `imposto/IPI/IPITrib/vIPI`, `imposto/ICMS/*/vICMSST` e `vFCPST`. EAN vazio ou `SEM GTIN` → `None`; EAN é mantido só se for todo dígitos.
- Números com `Decimal(texto)` direto. **Nunca `para_decimal`**: o XML usa ponto decimal e `"1.000"` viraria mil.
- `custo_total = vProd − vDesc + vFrete + vSeg + vOutro + vIPI + vICMSST + vFCPST` (arredondado a centavos).
- Qualquer falha (XML malformado, não é NF-e, chave inválida, campo obrigatório ausente, número inválido) → `XmlInvalido` com mensagem clara.

`sugerir_fator(descricao, unidade, qtd, unidade_trib, qtd_trib) -> Decimal`: se `unidade_trib ≠ unidade` e `qtd_trib / qtd` é inteiro > 1 → essa razão; senão a heurística `extrairFator` do original (`01-ESTOQUE.gs:518-530`, portada com os mesmos padrões sobre a descrição); senão 1.

### 3.5 Entrada por NF-e (`estoque/entrada.py`)

**preparar_entrada(s, ator, conteudo) -> ConferenciaNota**:
- Lê o XML. Já existe `nota_entrada` não estornada com a chave → `NotaJaImportada` (número, emitente e data de entrada na mensagem).
- Aviso (não bloqueia) se `empresa.cnpj` está configurado e o destinatário é outro.
- Para cada item, sugere o produto nesta ordem:
  1. vínculo (`emitente_cnpj`, `codigo_fornecedor`) apontando para produto **ativo** → fator do vínculo;
  2. `cEAN` = `produto.ean` (ativo) → fator = `produto.fator` (o EAN do produto identifica a embalagem dele);
  3. `cEANTrib` = `produto.ean` (ativo) → fator = `(qTrib / qCom) × produto.fator`;
  4. nenhum → sugestão de ação "criar" com fator de `sugerir_fator`.
- **Nunca** casa por descrição ou substring.
- `ConferenciaNota` traz o cabeçalho, os avisos e, por item, os dados lidos, `custo_total`, o produto sugerido (id, código, descrição), a origem (`VINCULO`/`EAN`/`EAN_TRIB`/`NENHUMA`) e o fator sugerido.

**confirmar_entrada(s, ator, conteudo, decisoes) -> NotaEntrada**:
- Relê o XML (não confia em cópia da UI) e repete a checagem de duplicidade.
- `decisoes` cobre exatamente os `n_item` da nota. Cada uma é `VINCULAR(produto_id, fator)`, `CRIAR(descricao, fator)` ou `IGNORAR`. `fator > 0`; produto de `VINCULAR` precisa existir e estar ativo.
- Para cada item não ignorado:
  - `CRIAR`: novo produto com a descrição informada, `embalagem = uCom`, `fator` = fator do item, `ean` = `cEAN` se livre (senão nulo), destino `REVENDA`, preço de venda 0, estoque 0. Auditoria `criar`.
  - `qtd_estoque = qtd_nota × fator`; `custo_unitario = custo_total / qtd_estoque`.
  - `preco_entrada_anterior` e `data_ult_entrada_anterior` guardados no item.
  - `produto.preco_entrada = custo_unitario × produto.fator` (Custo, 4 casas). A embalagem e o fator do produto **nunca** são sobrescritos pela nota; o fracionado resultante é o custo por unidade de estoque da nota (último custo; divergência nº 25 da spec de arquitetura). `preco_entrada_aplicado` guarda o valor gravado.
  - `produto.data_ult_entrada = hoje`.
  - Movimento `ENTRADA_NF` de `+qtd_estoque` ligado ao item.
  - Grava ou atualiza o vínculo (`emitente_cnpj`, `codigo_fornecedor`) → produto, fator.
- Grava `nota_entrada` com `data_entrada = clock.agora()` e o XML original. Uma auditoria `entrada` por nota (chave, número, emitente, total, nº de itens lançados e ignorados).

### 3.6 Estorno (`estoque/entrada.py`)

**estornar_entrada(s, ator, nota_id, *, confirmar_negativo=False)** (só admin):
- Nota já estornada → `ValorInvalido`.
- Se algum produto ficaria com estoque negativo e `confirmar_negativo` é falso → `EstoqueInsuficiente` listando código, descrição, saldo atual e quantidade a estornar. A UI pede confirmação e chama de novo com `True`.
- Processa os itens com produto em **ordem inversa** de `n_item` (vários itens do mesmo produto restauram na ordem certa):
  - movimento `ESTORNO_NF` de `−qtd_estoque`;
  - restaura `preco_entrada` e `data_ult_entrada` anteriores **somente se** `produto.preco_entrada == preco_entrada_aplicado` e não existe nota posterior (id maior) não estornada com o mesmo produto; caso contrário mantém os valores atuais (uma entrada mais nova ou uma edição manual prevalece).
- Nunca apaga produto; produtos criados pela nota ficam com o saldo resultante. Vínculos permanecem.
- Marca `estornada`, `estornada_em`, `estornada_por`. Auditoria `estornar`.

`listar_notas(s, ator)` (mais recente primeiro, inclui estornadas) e `obter_nota(s, ator, nota_id)` com itens e produtos.

### 3.7 Bens Físicos (`gestao/bens.py`)

`criar_bem`, `atualizar_bem`, `baixar_bem` / `reativar_bem`, `listar_bens(incluir_baixados)`, `total_bens_ativos()` (Σ valor dos ativos; será o Ativo Não Circulante do Balancete). Descrição obrigatória, `valor > 0`. Auditoria em todas as escritas.

## 4. Interface

Regras comuns:
- Dinheiro e quantidade digitados em `QLineEdit` e convertidos na borda com `core.money.para_decimal` (formato brasileiro). Nunca `QDoubleSpinBox` (float).
- `ui/comum.py` ganha helpers de tabela (criação somente leitura com seleção por linha e preenchimento por lista de textos) usados pelas telas novas, e `formatar_qtd` (`1,5`; sem zeros à direita) e `formatar_pct` (`12,5%`).
- Erros de domínio aparecem via `mostrar_erro`.

### 4.1 Página Estoque (`ui/estoque/`)

`PaginaEstoque` (`QTabWidget`) com três abas:

- **Produtos** (`TelaProdutos`):
  - Campo de busca que filtra ao digitar; caixa "Mostrar inativos".
  - Colunas: Código, EAN, Descrição, Categoria, Embalagem, Estoque, Custo unit., Preço venda, Margem, Última entrada, Destino. Linha com `estoque_minimo > 0` e `estoque ≤ estoque_minimo` destacada; inativos em cinza.
  - Botões: Novo, Editar (também duplo clique), Ajustar estoque, Movimentações, Desativar/Reativar.
  - `DialogoProduto`: preço fracionado e margem calculados ao vivo; estoque inicial só na criação; categoria em combo editável com as já usadas; estoque mínimo com a caixa "Definido manualmente", marcada sozinha quando o valor muda.
  - `DialogoAjusteEstoque`: saldo atual, nova quantidade, motivo, observação.
  - `DialogoMovimentos`: data/hora, tipo, quantidade, saldo, usuário, motivo/observação, nota.
- **Serviços** (`TelaServicos`):
  - Colunas: Código, Nome, Materiais, Custo materiais, Mão de obra %, Preço.
  - `DialogoServico` com tabela de materiais (adicionar/remover linha) e preço ao vivo; mão de obra padrão 50%.
- **Entradas de NF-e** (`TelaEntradas`):
  - Lista de notas: Data de entrada, Número/Série, Emitente, Valor, Itens, Situação.
  - Botões: "Importar XML…" (`QFileDialog`), "Ver itens", "Estornar" (visível só para admin; confirma e trata `EstoqueInsuficiente` com segunda confirmação).
  - `DialogoConferencia`:
    - cabeçalho da nota e avisos;
    - tabela por item com Nº, Código forn., EAN, Descrição da nota, Un., Qtd nota, Custo total, Ação (Vincular / Criar novo / Ignorar), Produto (botão "Escolher…" abre busca de produtos ativos), Fator (editável), Qtd no estoque e Custo unit. (calculados);
    - descrição editável quando a ação é Criar;
    - "Confirmar entrada" habilitado só com todos os itens decididos.

### 4.2 Gestão (`ui/gestao/`)

`PaginaGestao` (`QTabWidget`) substitui o "em construção" da aba CFAUTO em Configurações. Primeira aba: **Bens Físicos** (`TelaBens`):
- colunas Código, Descrição, Tipo, Valor, Data, Situação;
- total dos ativos no rodapé;
- botões Novo, Editar, Baixar/Reativar, caixa "Mostrar baixados";
- `DialogoBem`.

### 4.3 Janela principal

`JanelaPrincipal` passa a montar as páginas por um mapa `Modulo → fábrica(fabrica, ator)`: `ESTOQUE → PaginaEstoque`; os demais continuam `PaginaEmConstrucao`. `PaginaConfiguracoes` usa `PaginaGestao` na aba CFAUTO.

## 5. Testes

Camada de serviço (SQLite migrado, `relogio` fixo, fixtures `admin`/`operador`; novo fixture `estoquista` com módulo ESTOQUE):
- **Sequência**: códigos consecutivos, prefixos independentes, sem reaproveitar após desativação, passa de 9999.
- **Produto**:
  - códigos 0001/0002;
  - EAN duplicado bloqueado; vários produtos sem EAN;
  - fracionado e margem, com `None` sem preço;
  - data carimbada no cadastro (estoque 0 incluído) e não na edição;
  - edição não altera estoque;
  - regra do mínimo manual;
  - ajuste (diferença, motivo, OUTRO sem observação, sem alteração);
  - Σ movimentos = estoque;
  - `PermissaoNegada` para operador sem ESTOQUE;
  - busca (código sem zeros, EAN, acento/maiúsculas, todas as palavras, inativos).
- **Serviço**: preço calculado, edição substitui materiais, validações, `SERV-001`.
- **NF-e (parser)**, com fixtures XML sintéticos em `tests/estoque/fixtures/`:
  - `nfeProc` com item com EAN, item `SEM GTIN` e item com IPI + ST + frete + seguro + outros + desconto;
  - `NFe` sem protocolo;
  - XML malformado; não-NF-e; dígito verificador errado;
  - `qCom` `"1.0000"` lido como 1;
  - `sugerir_fator` (razão tributável, `c/12`, `12x1`, padrão 1).
- **Entrada**:
  - custo efetivo;
  - casamento na ordem vínculo > EAN > EAN tributável > nenhuma; descrição parecida não casa;
  - confirmar: estoque += qtd × fator, preço convertido para a embalagem do produto, data, vínculo gravado e reaproveitado na nota seguinte, movimento, auditoria;
  - criar produto novo pela nota; ignorar item;
  - nota duplicada bloqueada; reimportação após estorno permitida;
  - decisões incompletas, extras ou com produto inativo rejeitadas.
- **Estorno**:
  - reverte estoque;
  - restaura preço só se for a última entrada e não houve edição;
  - mantém o preço com entrada posterior;
  - mesmo produto em dois itens;
  - nunca apaga produto;
  - negativo exige confirmação;
  - só admin; estorno duplo rejeitado.
- **Bens**: CRUD, `BEM-001`, total só de ativos, só admin.
- **Migração**: tabelas novas presentes; modelos batem com a migration (teste existente).

UI (pytest-qt, offscreen):
- `PaginaEstoque` com as três abas;
- criar produto pelo diálogo e ver na tabela;
- ajuste pelo diálogo;
- conferência com XML de fixture → confirmar → nota na lista e estoque atualizado;
- janela principal mostra a página Estoque (não "em construção") para quem tem o módulo;
- Configurações › CFAUTO mostra Bens Físicos; criar bem pelo diálogo.

Qualidade: `ruff`, `mypy`, suíte inteira verde (pre-commit).

## 6. Divergências novas em relação ao original

Continua a numeração da spec de arquitetura §8.

| # | Original | Novo | Motivo |
|---|---|---|---|
| 36 | Custo da nota = `vUnCom` | Custo efetivo (desconto, frete, seguro, outros, IPI, ICMS-ST, FCP-ST) | Decisão do usuário (D2) |
| 37 | Estoque sobrescrito no formulário de edição, sem motivo | Ajuste próprio com motivo + livro de movimentos | Rastreabilidade (D4, D5) |
| 38 | Fator extraído do nome na importação, inconsistente com o F cadastrado | Fator por vínculo fornecedor/código ou EAN, sempre conferido na tela | Bug nº 1 da análise do ESTOQUE |
| 39 | Estorno não reverte preço nem data | Restaura preço/data anteriores quando a nota é a entrada mais recente | Integridade |
| 40 | Chave de acesso via API de terceiro (checagem `'<xml'` provavelmente nunca passou) | Só XML; chave lida e validada do próprio arquivo | D1 |
| 41 | Serviço sem edição | Serviço editável | Usabilidade |
| 42 | Custo com 2 casas | `Custo()` com 4 casas | Precisão do fracionado |

## 7. Pendências e decisões adiadas

- `destino` USO_CONSUMO / MATERIA_PRIMA sem efeito; decidir no sub-projeto 4 (PDV) e 7 (ABC) se saem das vendas/curva.
- Preço de venda editado no formulário × `markup_manual`: decidir no sub-projeto 6.
- `fornecedor` (sub-projeto 8) poderá ligar `nota_entrada.emitente_cnpj` e `vinculo_fornecedor_produto` ao cadastro de fornecedor pelo CNPJ.
- Fonte SEFAZ (certificado A1) para buscar XML pela chave: pós-hackathon, se a loja tiver certificado.
