# CFAUTO — Sub-projeto 3: Clientes — Design

- **Data:** 2026-09-28
- **Status:** aprovado em brainstorming, aguardando revisão da spec escrita
- **Base:** `docs/superpowers/specs/2026-09-23-cfauto-arquitetura-design.md` (spec de arquitetura, manda sobre esta onde não houver decisão nova aqui), `referencia/analise/caixa-clientes-historico.md` (§1.6, §3.1, §3.2, §5), `referencia/appsscript/08-CLIENTES.gs`
- **Branch:** `feat/clientes`

## 1. Objetivo e escopo

Entregar o módulo Clientes utilizável de ponta a ponta: cadastro completo de cliente com dependentes, razão (livro) de lançamentos que mantém o saldo devedor, lançamento manual de débito/crédito, extrato imprimível, inativação/exclusão. É a base do crediário e do recebimento de conta no PDV (sub-projeto 4).

Sucesso: o sub-projeto 4 liga venda no crediário e recebimento ao cliente **sem refazer o modelo** — só acrescenta motivos de lançamento e a FK para a venda.

Fora deste sub-projeto: venda no crediário, receber conta, alerta de limite e exibição das observações no PDV, uso do crédito a favor (4); juros, multa e aumento automático de limite (sem efeito, como no original); importador e saldo inicial vindo das planilhas (9).

### 1.1 Decisões do brainstorming (28/09)

| # | Decisão | Alternativas descartadas |
|---|---|---|
| D1 | **Razão do cliente** (`cliente_lancamento`) + saldo em `cliente.saldo_devedor`, alterado exclusivamente por `lancar()`. Mesmo padrão do livro de movimentos do Estoque. | Campo `saldo_devedor` editável com auditoria (spec de arquitetura original) |
| D2 | Lançamento manual por **débito/crédito com valor + motivo** (aumentar ou abater dívida). | "Definir saldo para X" gravando delta; ambos |
| D3 | Permissões: módulo CLIENTES cadastra, edita dados, lança e vê extrato. **Só admin**: limite/"sem limite", inativar, reativar, excluir. Lançamento nunca é editado nem apagado; erro se corrige com lançamento contrário motivo `CORRECAO`. | Lançamento só-admin |
| D4 | Extrato na tela + impressão por `QPrintPreviewDialog` com `QTextDocument` (HTML). PDF pela impressora "Microsoft Print to PDF" do Windows; nenhuma dependência nova. | PDF direto com `reportlab` |
| D5 | Cliente **sem lançamentos** pode ser excluído de fato; **com histórico** só inativado (`ativo`). Saldo ≠ 0 bloqueia as duas coisas. | Só inativação; exclusão sempre |
| D6 | Validações: nome ≥ 2 palavras; celular obrigatório **com DDD** (10–11 dígitos); CPF opcional, com **dígito verificador** quando informado; duplicidade de CPF/celular é aviso confirmável. | Celular ≥ 8 dígitos sem DDD (original); CPF sem DV (original); CPF único |
| D7 | Crédito maior que o saldo é aceito e deixa o saldo **negativo = crédito a favor do cliente**. | Bloquear o excedente; perder o excedente em silêncio (original) |

## 2. Modelo de dados (migration `0003_clientes`)

Convenções da spec de arquitetura §3 valem (PK inteira, `ComTimestamps`, `Dinheiro()` 2 casas, `DecimalEscalado`, `EnumTexto`).

### 2.1 Tabelas (`cfauto/clientes/models.py`)

**cliente**

| Campo | Tipo | Regra |
|---|---|---|
| `codigo` | str(20), único | `proximo_codigo(s, "cliente", prefixo="CLI-", digitos=4)` → `CLI-0001`; nunca reaproveitado |
| `nome` | str(120) | obrigatório, `strip()`, espaços internos colapsados, ≥ 2 palavras |
| `nome_busca` | str(120), indexado | `normalizar_texto(nome)`; recalculado a cada gravação |
| `celular` | str(11) | só dígitos, 10–11, DDD entre 11 e 99 |
| `cpf` | str(11), nulo, indexado | só dígitos, DV válido, não aceita 11 dígitos iguais; **não** é único |
| `email` | str(120), nulo | formato simples `algo@algo.algo` |
| `endereco` | str(200), padrão `""` | texto livre |
| `nascimento` | date, nulo | não pode ser futura |
| `sexo` | enum str, nulo | `M`, `F`, `OUTRO` |
| `observacoes` | str(500), padrão `""` | aviso para o caixa (exibido no PDV no sub-projeto 4) |
| `limite` | Dinheiro, nulo | nulo = **sem limite**; ≥ 0; padrão de cliente novo R$ 500,00 |
| `saldo_devedor` | Dinheiro, padrão 0 | só muda via `lancar()`; negativo = crédito a favor |
| `somente_titular` | bool, padrão `False` | com `True`, a lista de dependentes tem que estar vazia |
| `aumento_auto` | bool, padrão `False` | guardado, sem efeito |
| `aumento_auto_pct` | DecimalEscalado(2), padrão 5,00 | guardado, sem efeito |
| `juros_dias` | int, padrão 30 | guardado, sem efeito |
| `juros_frequencia` | enum str, padrão `MENSAL` | `DIARIO`, `MENSAL`, `BIMESTRAL`; guardado, sem efeito |
| `juros_pct` | DecimalEscalado(2), padrão 2,00 | percentual (não fração); guardado, sem efeito |
| `juros_mora` | bool, padrão `False` | guardado, sem efeito |
| `ativo` | bool, padrão `True` | exclusão lógica |

Propriedade Python (nunca gravada): `disponivel` = `None` se `limite` nulo (ilimitado), senão `limite − saldo_devedor` (pode passar de `limite` quando há crédito a favor; pode ser negativo quando o saldo excede o limite).

**cliente_dependente**

| Campo | Tipo | Regra |
|---|---|---|
| `cliente_id` | FK `cliente.id`, indexado | `cascade="all, delete-orphan"` a partir do cliente |
| `nome` | str(120) | obrigatório, `strip()` |
| `parentesco` | str(40), padrão `""` | texto livre |

No máximo 4 por cliente (validado no serviço).

**cliente_lancamento** (append-only: nunca atualizado nem apagado)

| Campo | Tipo | Regra |
|---|---|---|
| `cliente_id` | FK `cliente.id`, indexado | |
| `data_hora` | datetime | `clock.agora()` |
| `tipo` | enum str | `DEBITO` (aumenta a dívida), `CREDITO` (abate) |
| `valor` | Dinheiro | > 0, sem sinal; o sinal vem do `tipo` |
| `saldo_apos` | Dinheiro | `cliente.saldo_devedor` depois do lançamento |
| `motivo` | enum str | `COMPRA_ANOTADA`, `PAGAMENTO`, `CORRECAO`, `OUTRO` |
| `observacao` | str(200), padrão `""` | obrigatória quando `motivo = CORRECAO` |
| `usuario_id` | FK `usuario.id` | autor |

Extensões previstas (não implementadas aqui): o sub-projeto 4 acrescenta motivos `VENDA_CREDIARIO` e `RECEBIMENTO` e a coluna `venda_id` (nula) por migração; o sub-projeto 9 acrescenta `SALDO_INICIAL`. Índice composto `(cliente_id, data_hora)` para o extrato.

### 2.2 Novidades no `core`

- Erros novos em `core/errors.py`: `ClienteComSaldo(ErroDominio)` (inativar/excluir com saldo ≠ 0) e `ClienteComHistorico(ErroDominio)` (excluir cliente que tem lançamentos).

## 3. Serviços (`cfauto/clientes/`)

Padrão do Estoque: funções recebem `Session` e `Ator`, entrada/saída por dataclasses em `schemas.py`, erros de `core/errors.py`, a UI nunca recebe entidade ORM. Quem chama controla a transação (`with fabrica.begin()`), como nos demais serviços.

### 3.1 `validacao.py` (funções puras, sem banco)

- `normalizar_nome(texto) -> str` — `strip`, colapsa espaços; `ValorInvalido` se < 2 palavras.
- `normalizar_celular(texto) -> str` — extrai dígitos; `ValorInvalido` se não tiver 10–11 dígitos ou DDD fora de 11–99.
- `normalizar_cpf(texto) -> str | None` — vazio → `None`; extrai dígitos; `ValorInvalido` se ≠ 11 dígitos, todos iguais ou DV errado.
- `normalizar_email(texto) -> str | None` — vazio → `None`; `ValorInvalido` sem `@` ou sem ponto no domínio.
- `formatar_celular(digitos) -> str` — `(11) 98765-4321` / `(11) 3456-7890`.
- `formatar_cpf(digitos) -> str` — `123.456.789-09`.

### 3.2 `razao.py`

- `lancar(s, ator, cliente, tipo, valor, motivo, observacao="") -> ClienteLancamento` — **única porta** de alteração de `saldo_devedor`. Arredonda `valor`; `ValorInvalido` se ≤ 0; `CORRECAO` sem observação → `ValorInvalido`. `DEBITO` soma, `CREDITO` subtrai (pode ficar negativo, D7). Grava `saldo_apos` e registra auditoria (`cliente.lancamento`, antes/depois do saldo, tipo, valor, motivo). Não checa permissão nem limite: quem chama decide (o PDV do sub-projeto 4 chamará com seus próprios motivos).
- `lancar_manual(s, ator, cliente_id, tipo, valor, motivo, observacao) -> LinhaLancamento` — `exigir_modulo(CLIENTES)`; cliente inativo → `ValorInvalido`; delega a `lancar`.
- `extrato(s, ator, cliente_id, inicio, fim) -> Extrato` — `exigir_modulo(CLIENTES)`; `saldo_anterior` = `saldo_apos` do último lançamento antes de `inicio` (0 se nenhum); linhas com `inicio ≤ data ≤ fim` em ordem cronológica; `saldo_final` = `saldo_apos` da última linha, ou `saldo_anterior` se o período estiver vazio.

### 3.3 `cadastro.py`

- `criar_cliente(s, ator, dados: DadosCliente) -> int` — `exigir_modulo(CLIENTES)`; não-admin só cria com `limite` = padrão (R$ 500,00); outro valor ou "sem limite" → `PermissaoNegada`. Valida via `validacao`, gera código, grava dependentes, audita (`cliente.criar`).
- `editar_cliente(s, ator, cliente_id, dados: DadosCliente) -> None` — `exigir_modulo(CLIENTES)`; se `limite` mudou (inclui passar para/de sem limite) → `exigir_admin`. Nunca altera `saldo_devedor` nem `codigo`. Lista de dependentes é substituída inteira. Audita snapshot antes/depois (`cliente.editar`).
- `verificar_duplicados(s, ator, cpf, celular, ignorar_id=None) -> list[ResumoCliente]` — clientes (ativos ou não) com o mesmo CPF ou celular, já normalizados; a UI chama antes de salvar.
- `buscar_clientes(s, ator, texto, incluir_inativos=False) -> list[ResumoCliente]` — texto vazio lista todos; senão casa por `nome_busca` contendo o texto normalizado, `codigo` contendo o texto em maiúsculas, ou dígitos do texto contidos em `cpf`/`celular` (só quando o texto tem ≥ 3 dígitos). Ordem por nome.
- `obter_cliente(s, ator, cliente_id) -> FichaCliente` — dados, dependentes, saldo, disponível.
- `inativar_cliente` / `reativar_cliente(s, ator, cliente_id)` — `exigir_admin`; inativar com saldo ≠ 0 → `ClienteComSaldo`. Audita.
- `excluir_cliente(s, ator, cliente_id)` — `exigir_admin`; saldo ≠ 0 → `ClienteComSaldo`; com qualquer lançamento → `ClienteComHistorico`. Apaga cliente e dependentes. Audita (snapshot antes).

`DadosCliente` carrega todos os campos editáveis (incluindo os de juros e a lista de `DadosDependente`); `FichaCliente`/`ResumoCliente`/`LinhaLancamento`/`Extrato` são dataclasses de leitura.

### 3.4 `extrato_html.py`

- `gerar_html_extrato(extrato: Extrato, loja: str, emitido_em: datetime) -> str` — função pura: cabeçalho com nome da loja, dados do cliente (nome, código, CPF e celular formatados), período, saldo anterior, tabela (data/hora, descrição do motivo, débito, crédito, saldo), saldo final ("Crédito a favor" quando negativo), data de emissão. Escapa texto do usuário (`html.escape`). O nome da loja vem de `config.obter(s, "empresa.nome")` (gravado pelo assistente de primeira execução), lido pela UI e passado como argumento.

### 3.5 Auditoria

Via `core/audit.registrar`, com antes/depois em JSON, entidade `"cliente"` e ação `criar`, `alterar`, `inativar`, `reativar`, `excluir` ou `lancamento` (ação e entidade separadas, como no resto do código). Cobre o "cliente (saldo devedor, limite)" da spec de arquitetura §5.

## 4. UI (`cfauto/ui/clientes/`)

Padrão do Estoque: tela de lista + diálogos, usando `criar_tabela`, `preencher_tabela`, `ler_decimal`, `mostrar_erro` de `ui/comum.py`. Sem entidade ORM na UI; prévias usam funções puras (evita o débito técnico registrado no handoff).

- **`TelaClientes`** — página do módulo CLIENTES na navegação lateral (substitui o `PaginaEmConstrucao`). Campo de busca + "mostrar inativos". Tabela: código, nome, celular formatado, saldo (vermelho quando devedor; "Crédito R$ X" quando negativo), disponível ("Ilimitado" quando sem limite), situação. Botões: Novo, Editar, Lançamento, Extrato; Inativar/Reativar e Excluir só aparecem para admin (o serviço também barra). Duplo clique abre edição.
- **`DialogoCliente`** (novo/editar)
  - *Dados*: nome, celular e CPF (sem `inputMask`: o texto é reformatado para `(11) 98765-4321` / `000.000.000-00` ao sair do campo; o texto inválido fica como digitado e o erro aparece ao salvar), e-mail, nascimento (opcional, `dd/mm/aaaa`), sexo (opcional), endereço, observações para o caixa.
  - *Crédito*: limite + "sem limite" — desabilitados para não-admin; saldo atual só leitura.
  - *Dependentes*: "somente titular" + até 4 linhas nome/parentesco; marcar "somente titular" limpa e desabilita as linhas.
  - *Juros (guardados para uso futuro)*: dias, frequência, %, mora legal, aumento automático e %.
  - Salvar: erros de validação aparecem no diálogo sem fechar; depois `verificar_duplicados` — havendo, `QMessageBox` lista os clientes encontrados e pergunta "Salvar mesmo assim?"; então grava.
- **`DialogoLancamento`** — cliente e saldo atual no topo; "Aumentar dívida" / "Abater dívida"; valor; motivo; observação (obrigatória para Correção); prévia "Saldo após: R$ X" calculada por função pura.
- **`DialogoExtrato`** — período (padrão: últimos 90 dias até hoje), tabela do razão, saldo anterior e final, botão "Imprimir extrato" que abre `QPrintPreviewDialog` com `QTextDocument.setHtml(gerar_html_extrato(...))`.

## 5. Erros e casos-limite

- Mensagens de domínio via `mostrar_erro`; `PermissaoNegada` quando a UI for contornada.
- Lançamento em cliente inativo: bloqueado (reativar antes).
- Edição concorrente não é tratada além do que o SQLite já garante (loja única, mesmo padrão do Estoque).
- Busca com texto só de símbolos → lista vazia, sem erro.

## 6. Testes

TDD como no Estoque; UI com `QT_QPA_PLATFORM=offscreen`.

- **validacao**: CPFs válidos e inválidos (inclui `111.111.111-11` e DV trocado), CPF vazio → `None`, celular com 10 e 11 dígitos, sem DDD, DDD `01`, nome de uma palavra, espaços colapsados, e-mail sem `@`, formatadores.
- **razao**: débito e crédito atualizam saldo e `saldo_apos`; crédito acima do saldo deixa negativo; valor ≤ 0 rejeitado; `CORRECAO` sem observação rejeitada; cliente inativo bloqueia `lancar_manual`; auditoria gravada; extrato com saldo anterior correto na borda do período e período vazio.
- **cadastro**: códigos sequenciais não reaproveitados após exclusão; não-admin barrado ao criar com limite ≠ padrão, sem limite, e ao editar limite; não-admin edita os demais campos; > 4 dependentes e dependente com `somente_titular` rejeitados; `verificar_duplicados` ignora o próprio id; inativar/excluir com saldo ≠ 0 e excluir com histórico bloqueados; reativar; busca por nome sem acento, código, CPF e celular parciais, inativos ocultos por padrão.
- **extrato_html**: contém saldos e linhas, escapa `<script>` vindo da observação, "Crédito a favor" com saldo negativo.
- **UI**: crédito desabilitado para não-admin; botões de admin ocultos para não-admin; aviso de duplicado aparece; "somente titular" limpa dependentes; prévia de saldo no lançamento.

## 7. Mudanças na spec de arquitetura (mesmo commit desta spec)

- §3 `cliente`: `saldo_devedor` passa a ser mantido pelo razão `cliente_lancamento` (lançamentos manuais até o sub-projeto 4); saldo negativo = crédito a favor; tabelas `cliente_lancamento` e campos da §2.1 desta spec.
- §4.4: o "ajuste manual" após receber crediário vira lançamento `CREDITO`/`PAGAMENTO` no razão.
- Divergências intencionais: CPF com DV, celular com DDD, código de cliente nunca reaproveitado, pagamento excedente vira crédito a favor (original perdia).
- §9: pendência "saldo devedor manual" reformulada — o sub-projeto 4 decide se venda no crediário e recebimento lançam no razão automaticamente.
