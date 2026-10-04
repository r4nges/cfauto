# CFAUTO — Sub-projeto 4A: Caixa/PDV — Design

- **Data:** 2026-09-29
- **Status:** aprovado em brainstorming, aguardando revisão da spec escrita
- **Base:** `docs/superpowers/specs/2026-09-23-cfauto-arquitetura-design.md` (spec de arquitetura, manda sobre esta onde não houver decisão nova aqui; atualizada junto com esta spec), `docs/superpowers/specs/2026-09-28-clientes-design.md`, `referencia/analise/caixa-clientes-historico.md` (§2–§4, §7, §8), `referencia/appsscript/04-CAIXA.gs`
- **Branch:** `feat/caixa-4a`

## 1. Objetivo e escopo

Entregar o caixa utilizável de ponta a ponta para a validação conjunta com o cliente: abrir sessão com fundo de troco, vender produtos e serviços (juntos ou separados) com desconto e taxa por forma de pagamento, vender no crediário lançando a dívida no razão do cliente, receber crediário, cancelar venda com estorno, fechar a sessão com resumo e sangria, consultar o Histórico e ajustar as taxas em Configurações › Parâmetros.

Sucesso: o cliente faz o fluxo cadastro → venda → crediário → recebimento → fechamento → Histórico sem planilha, e os saldos de estoque e de cliente batem com as vendas.

**Fora do 4A (vai para o 4B):** venda externa (4 deduções), contrato/assinatura com parcelas, job de ativação de parcelas, relatório de vendas "já disponível × a cair". **Fora do sub-projeto 4:** cupom/comprovante impresso, parcelamento de cartão, split de pagamento, juros/multa do crediário.

### 1.1 Decisões do brainstorming (29/09)

| # | Decisão | Alternativas descartadas |
|---|---|---|
| D1 | Sub-projeto 4 dividido em **4A** (este) e **4B** (externa, contrato, parcelas, job, relatório a cair). Validação manual conjunta (Clientes + Caixa) logo após o 4A. | Tudo num ciclo só; validar só após o 4B |
| D2 | **Crediário automático**: venda no crediário lança `DEBITO`/`VENDA_CREDIARIO` no razão na mesma transação; recebimento lança `CREDITO`/`RECEBIMENTO`; cancelar estorna com `CANCELAMENTO`. Todos com `venda_id`. | Manual pelo Clientes (spec original §1.3/§4.4) |
| D3 | **Crédito a favor** só abate no crediário: saldo negativo é consumido pela próxima venda a prazo (−50 + 30 = −20). Recebimento maior que a dívida vira crédito a favor. Sem forma de pagamento nova. | Forma "Crédito da loja" |
| D4 | **Limite de crédito**: venda que passa do disponível gera aviso com confirmação; não bloqueia; o excesso fica na auditoria. Cliente sem limite não avisa. | Só admin autoriza; bloqueio sempre |
| D5 | **Carrinho misto**: uma venda (tipo `VENDA`) pode ter produtos e serviços; o item diz qual é. Produto baixa estoque, serviço não. | Tipos PRODUTO/SERVICO separados (spec original §3.2) |
| D6 | **Autorização do administrador por senha na hora**: estoque insuficiente e cancelamento, quando o logado não é admin, abrem diálogo de login+senha do admin sem trocar a sessão. A venda grava quem operou e quem autorizou. | Só com admin logado |
| D7 | Desconto por venda (R$ ou %), gravado; **não permitido no crediário** (como o original); operador livre para dar desconto. Operador não edita preço unitário. | Desconto por item; desconto só-admin |
| D8 | Cancelar venda: só admin (logado ou por senha), **só com a sessão da venda ABERTA**; motivo obrigatório. Sessão fechada é imutável. | Cancelar em sessão fechada |
| D9 | Uma forma de pagamento por venda; troco só na tela (não gravado). | Split; troco gravado |
| D10 | Taxas na tabela `taxa_pagamento` com **repasse** por forma; padrões gravados pela migração; edição só-admin em Configurações › Parâmetros. Sem passo de taxas no assistente de primeira execução. | Taxas no assistente (spec original §6.1) |

## 2. Modelo de dados (migration `0004_caixa`)

Convenções da spec de arquitetura §3 valem (PK inteira, `ComTimestamps`, `Dinheiro()` 2 casas, `Quantidade()` 3 casas, `DecimalEscalado`, `EnumTexto`). Enum é gravado como VARCHAR sem constraint: o 4B acrescenta valores (`EXTERNA`, `CONTRATO`, `BOLETO`, `CARTAO_CONTRATO`) sem migração de enum.

### 2.1 Tabelas novas (`cfauto/caixa/models.py`)

**sessao_caixa**

| Campo | Tipo | Regra |
|---|---|---|
| `protocolo` | str(24), único | `CX-yyyyMMdd-HHmm` de `clock.agora()`; se já existir, sufixo `-2`, `-3`… |
| `status` | enum `StatusSessao` (ABERTA / FECHADA) | índice único parcial `WHERE status = 'ABERTA'`: no máximo uma aberta |
| `aberta_em`, `aberta_por` | datetime, FK usuario | |
| `fundo_troco` | Dinheiro | ≥ 0 |
| `fechada_em`, `fechada_por` | nullable | preenchidos no fechamento |
| `valor_mantido`, `sangria` | Dinheiro, nullable | preenchidos no fechamento |
| `resumo_json` | JSON (texto), nullable | snapshot do resumo (§3.3) |

**venda**

| Campo | Tipo | Regra |
|---|---|---|
| `sessao_id` | FK sessao_caixa, indexado | sessão ABERTA no momento |
| `data_hora` | datetime, indexado | `clock.agora()` |
| `usuario_id` | FK usuario | quem operou |
| `autorizado_por` | FK usuario, nullable | admin que autorizou estoque insuficiente (§4.2) |
| `cliente_id` | FK cliente, nullable, indexado | obrigatório em CREDIARIO e RECEBIMENTO |
| `tipo` | enum `TipoVenda` | 4A: `VENDA`, `RECEBIMENTO` |
| `forma_pagamento` | enum `FormaPagamento` | 4A: `DINHEIRO`, `PIX`, `DEBITO`, `CREDITO`, `CREDIARIO` |
| `desconto` | Dinheiro | em R$, ≥ 0; 0 no crediário e no recebimento |
| `bruto` | Dinheiro | Σ subtotais − desconto (venda) ou valor abatido (recebimento) |
| `taxa` | Dinheiro | §3.2 |
| `liquido` | Dinheiro | §3.2 |
| `repasse_taxa` | bool | cópia de `taxa_pagamento.repasse` no momento |
| `data_liquidacao` | date, nullable | nula no crediário ("aguardando pagamento") |
| `cancelada` | bool | default false |
| `cancelada_em`, `cancelada_por`, `cancelamento_autorizado_por`, `motivo_cancelamento` | nullable | §4.4 |

O valor cobrado do cliente (`bruto + taxa` com repasse, senão `bruto`) é derivado, não gravado. Recebimento é uma `venda` sem itens.

**venda_item**

| Campo | Tipo | Regra |
|---|---|---|
| `venda_id` | FK venda, indexado | |
| `produto_id`, `servico_id` | FK, nullable | `CHECK` exatamente um preenchido |
| `descricao_snapshot` | str(200) | descrição/nome no momento |
| `categoria_snapshot` | str(60) | categoria do produto; `"Serviço"` para serviço |
| `qtd` | Quantidade | > 0; fracionada permitida |
| `preco_unit` | Dinheiro | produto: `preco_promocional` se houver, senão `preco_venda`; serviço: `Servico.preco` |
| `subtotal` | Dinheiro | `arredondar(qtd × preco_unit)` |

**taxa_pagamento**

| Campo | Tipo | Regra |
|---|---|---|
| `forma` | enum FormaPagamento, único | CREDIARIO não entra (taxa sempre 0, sem liquidação) |
| `pct` | DecimalEscalado(2) | ≥ 0; **0 é válido** |
| `dias` | int | ≥ 0; **0 é válido** |
| `repasse` | bool | cliente paga a taxa |

Linhas criadas pela migração: DINHEIRO 0%/0, PIX 0%/0, DEBITO 1,5%/7, CREDITO 3,5%/7, todas sem repasse.

### 2.2 Alterações em tabelas existentes

- `cliente_lancamento.venda_id`: FK venda, nullable, indexado.
- `movimento_estoque.venda_item_id`: FK venda_item, nullable (mesmo padrão de `nota_entrada_item_id`).
- `MotivoLancamento` ganha `VENDA_CREDIARIO` ("Venda no crediário"), `RECEBIMENTO` ("Recebimento") e `CANCELAMENTO` ("Cancelamento de venda/recebimento"), com as entradas em `TITULOS_MOTIVO_LANCAMENTO` (sem elas `extrato_html.descrever_lancamento` dá `KeyError`).
- `MOTIVOS_MANUAIS = (COMPRA_ANOTADA, PAGAMENTO, CORRECAO, OUTRO)` em `clientes/models.py`: o diálogo `ui/clientes/lancamento.py` lista só esses e `razao.lancar_manual` recusa os outros com `ValorInvalido`.

## 3. Cálculo (`cfauto/caixa/calculo.py`)

Funções puras, sem banco e sem ORM. A prévia da UI e os serviços usam as mesmas funções — resolve o débito técnico "UI cria entidade ORM temporária para prévia".

### 3.1 Venda

- `subtotal_item = arredondar(qtd × preco_unit)`; `subtotal = Σ subtotal_item`.
- Desconto: `TipoDesconto.REAIS` (0 ≤ valor ≤ subtotal) ou `TipoDesconto.PERCENTUAL` (0 ≤ pct ≤ 100, `desconto = arredondar(subtotal × pct / 100)`). Fora da faixa → `ValorInvalido`.
- `bruto = subtotal − desconto`.

### 3.2 Pagamento (venda e recebimento)

- Crediário: `taxa = 0`, `liquido = bruto`, `repasse = False`, `data_liquidacao = None`.
- Demais formas, com `(pct, dias, repasse)` da `taxa_pagamento`:
  - `taxa = arredondar(bruto × pct / 100)` — arredondamento **no total**, não por item;
  - `liquido = bruto` se `repasse`, senão `bruto − taxa`;
  - `cobrado = bruto + taxa` se `repasse`, senão `bruto`;
  - `data_liquidacao = data_hora.date() + dias`.
- Troco (só DINHEIRO, só tela): `troco = recebido − cobrado`; `recebido < cobrado` é inválido.

### 3.3 Resumo da sessão

Sobre as vendas não canceladas da sessão:

- `vendas[forma] = {qtd, bruto, taxa, liquido}` para tipo VENDA (inclui CREDIARIO);
- `recebimentos[forma] = {qtd, bruto, taxa, liquido}` para tipo RECEBIMENTO, **em linhas separadas** (divergência nº 32);
- `canceladas = {qtd, bruto}` (informativo, fora dos totais);
- `total_vendido = Σ bruto das VENDAS` (não inclui recebimentos);
- `dinheiro = Σ cobrado em DINHEIRO` (vendas + recebimentos); `gaveta = fundo_troco + dinheiro`;
- no fechamento: `sangria = gaveta − valor_mantido`, com `0 ≤ valor_mantido ≤ gaveta`.

Decimais vão para o JSON como texto (`core.jsonutil.para_json`).

## 4. Serviços (`cfauto/caixa/`)

Todos recebem `Session` e `Ator`, verificam permissão na entrada, rodam numa transação e gravam auditoria na mesma transação. Entrada/saída por dataclasses em `cfauto/caixa/schemas.py`.

### 4.1 Sessão (`sessao.py`) — módulo PDV

- `sessao_aberta(s, ator) -> PainelSessao | None`: protocolo, abertura, fundo, gaveta ao vivo, nº de vendas.
- `sugestao_fundo(s, ator) -> Decimal`: `valor_mantido` da última sessão FECHADA, ou 0.
- `abrir_sessao(s, ator, fundo) -> PainelSessao`: `fundo ≥ 0`; já há ABERTA → `SessaoJaAberta`. Auditoria `abrir`/`sessao_caixa`.
- `previa_fechamento(s, ator) -> ResumoSessao` (§3.3, sem gravar).
- `fechar_sessao(s, ator, valor_mantido) -> FechamentoSessao` (protocolo, `resumo: ResumoSessao`, `valor_mantido`, `sangria`): valida faixa, grava `fechada_*`, `valor_mantido`, `sangria`, `resumo_json`, `status = FECHADA`. Auditoria `fechar`. Qualquer usuário com PDV fecha, inclusive sessão aberta por outro.

### 4.2 Venda (`venda.py`) — módulo PDV

`registrar_venda(s, ator, dados: NovaVenda, *, autorizador: Ator | None = None, confirmar_limite: bool = False, confirmar_estoque: bool = False) -> int`

`NovaVenda`: itens (`produto_id` ou `servico_id`, `qtd`), `forma`, desconto (tipo + valor), `cliente_id` opcional.

1. Sessão ABERTA, senão `SessaoFechada`.
2. Carrinho não vazio; `qtd > 0`; produto/serviço existe e está ativo; cliente informado existe e está ativo. Falhas → `ValorInvalido`.
3. CREDIARIO: exige cliente; desconto tem de ser zero.
4. Preço unitário e descrição vêm **do banco**, nunca da UI (§2.1 `venda_item`).
5. Estoque: soma a `qtd` do **mesmo produto repetido** no carrinho e compara com `produto.estoque`. Faltando: `EstoqueInsuficiente` com a lista de produtos e saldos para **todos**, inclusive admin logado, até o reenvio com `confirmar_estoque=True`. Com a flag, exige um admin responsável — o admin logado ou o `autorizador` —, segue (estoque pode ficar negativo) e grava `autorizado_por`; sem admin responsável levanta `EstoqueInsuficiente` de novo. `autorizador` que não é admin → `PermissaoNegada`.
6. Limite (CREDIARIO, cliente com `limite`): se `bruto > cliente.disponivel` e não `confirmar_limite` → `LimiteExcedido(disponivel, excesso)`.
7. Calcula (§3), grava `venda` e `venda_item`.
8. Produtos: `movimentar(s, ator, produto, −qtd, TipoMovimento.VENDA, observacao="Venda nº {id}", venda_item_id=...)`.
9. CREDIARIO: `razao.lancar(s, ator, cliente, DEBITO, bruto, VENDA_CREDIARIO, "Venda nº {id}", venda_id=id)`.
10. Auditoria `criar`/`venda` com forma, totais, itens, `autorizado_por` e, se houve, `limite_excedido: {disponivel, excesso}`.

Padrão de confirmação: o serviço levanta o erro, a UI pergunta (ou pede a senha do admin) e reenvia a mesma venda com `confirmar_estoque`/`autorizador`/`confirmar_limite` (as flags se acumulam entre reenvios). Nada é gravado na tentativa que falha.

`vendas_da_sessao(s, ator) -> list[LinhaVenda]`: vendas da sessão aberta, mais recentes primeiro, com itens resumidos e flag de cancelada.

### 4.3 Recebimento (`recebimento.py`) — módulo PDV

`registrar_recebimento(s, ator, cliente_id, valor, forma) -> int`

- Sessão ABERTA; cliente existe e está **ativo**; `valor > 0`; forma ∈ {DINHEIRO, PIX, DEBITO, CREDITO}.
- Grava `venda` tipo RECEBIMENTO, sem itens, `bruto = valor`, taxa/líquido/liquidação pela §3.2 (com repasse o cliente paga `valor + taxa` e a dívida abate `valor`).
- `razao.lancar(s, ator, cliente, CREDITO, valor, RECEBIMENTO, "Recebimento nº {id}", venda_id=id)`.
- Valor maior que o saldo devedor é aceito e vira crédito a favor (a UI avisa antes).
- Auditoria `criar`/`venda`.

### 4.4 Cancelamento (`venda.py`)

`cancelar_venda(s, ator, venda_id, motivo, *, autorizador: Ator | None = None) -> None`

- Exige `ator.admin` ou `autorizador` admin, senão `PermissaoNegada`.
- A sessão da venda tem de estar ABERTA, senão `SessaoFechada("Sessão fechada: a venda não pode mais ser cancelada.")`.
- Venda já cancelada → `ValorInvalido`. Motivo obrigatório (até 200 caracteres).
- Devolve o estoque de cada item de produto: `movimentar(+qtd, CANCELAMENTO_VENDA, venda_item_id=...)`.
- Estorna o razão: venda CREDIARIO → `CREDITO`/`CANCELAMENTO`; RECEBIMENTO → `DEBITO`/`CANCELAMENTO`; ambos com `venda_id` e observação "Cancelamento da venda nº {id}: {motivo}". O estorno vale mesmo com cliente inativo.
- Marca `cancelada`, `cancelada_em`, `cancelada_por = ator.id`, `cancelamento_autorizado_por` (autorizador, se houve), `motivo_cancelamento`. Nenhuma linha é apagada.
- Auditoria `cancelar`/`venda`.

### 4.5 Taxas (`taxas.py`)

- `listar_taxas(s, ator)` — módulo PDV (a prévia do PDV precisa das taxas).
- `atualizar_taxa(s, ator, forma, pct, dias, repasse)` — só admin; `pct ≥ 0`, `dias ≥ 0`; auditoria `alterar`/`taxa_pagamento`.

### 4.6 Histórico (`cfauto/historico/consultas.py`) — módulo HISTORICO, só leitura

Só vendas de sessões **FECHADAS**.

- `listar_vendas(s, ator, filtro) -> list[LinhaHistorico]`. Filtro: período (por `data_hora`), forma, tipo, cliente, incluir canceladas (padrão não). Linha: protocolo, data/hora, descrição (VENDA: 1º item + " (+N itens)"; RECEBIMENTO: "RECEBIMENTO DE CONTA / FIADO"), cliente, forma, bruto, taxa, líquido, `dias_liquidacao = (data_liquidacao − data_hora.date()).days` (nulo no crediário), cancelada.
- `detalhe_venda(s, ator, venda_id)`: itens, desconto, autorizações, cancelamento.
- `listar_sessoes(s, ator, periodo) -> list[LinhaSessao]`: protocolo, abertura/fechamento, quem, fundo, total vendido, gaveta, mantido, sangria; resumo completo a partir de `resumo_json`.

### 4.7 Mudanças em código existente

- `core/permissoes.py`: `exigir_algum_modulo(ator, *modulos)`. `estoque.produtos.buscar_produtos` e `estoque.servicos.listar_servicos` passam a aceitar ESTOQUE **ou** PDV; `clientes.cadastro.buscar_clientes` e `obter_cliente` aceitam CLIENTES **ou** PDV.
- `auth/service.py`: `autorizar_admin(s, login, senha) -> Ator` — usa `autenticar` (mesmas regras de tentativas e bloqueio) e exige admin (`PermissaoNegada("Usuário não é administrador.")`). Não troca a sessão logada.
- `clientes/razao.py`: `lancar(..., venda_id: int | None = None)`.
- `clientes/cadastro.py`: `excluir_cliente` recusa cliente com vendas (`ClienteComHistorico("O cliente tem vendas registradas e não pode ser excluído; use Inativar.")`).
- `estoque/movimentos.py`: `movimentar(..., venda_item_id: int | None = None)`.
- `core/errors.py`: `SessaoFechada`, `SessaoJaAberta`, `LimiteExcedido(disponivel, excesso)` (subclasses de `ErroDominio`). `EstoqueInsuficiente` ganha atributo opcional com a lista de faltas (produto, saldo, pedido), sem quebrar os usos atuais.

## 5. Permissões

| Ação | Quem |
|---|---|
| Abrir/fechar sessão, vender, receber crediário, ver vendas da sessão | módulo PDV |
| Vender com estoque insuficiente | admin logado ou autorização do admin por senha |
| Cancelar venda | admin logado ou autorização do admin por senha; só sessão aberta |
| Editar taxas | admin (Configurações › Parâmetros) |
| Histórico | módulo HISTORICO |
| Buscar produto/serviço/cliente no PDV | módulo PDV (além de ESTOQUE/CLIENTES) |

## 6. UI

### 6.1 `cfauto/ui/caixa/` — `PaginaCaixa` (módulo PDV)

Registrada em `PAGINAS_DOS_MODULOS` (`ui/janela_principal.py`).

- **Sem sessão aberta:** "Caixa fechado" + botão **Abrir caixa** (`DialogoAbrirCaixa`: fundo com a sugestão preenchida).
- **Com sessão aberta** (`pdv.py`):

```
CX-20260929-0812 · fundo R$ 100,00 · gaveta R$ 350,00   [Receber crediário] [Vendas da sessão] [Fechar caixa]
Buscar: [EAN / código / nome_____]
 resultados: produtos + serviços ativos (estoque visível)
 carrinho: Descrição | Qtd (editável) | Unit | Subtotal | ✕
Cliente: [buscar]  nome · código · saldo · disponível / crédito a favor · ⚠ observações / dependentes / somente titular
Desconto [__] R$|%   Forma [Dinheiro ▼]   Recebido [__]  Troco R$ …
Subtotal · Desconto · Taxa (se repasse) · TOTAL A COBRAR          [Limpar] [Finalizar]
```

- Busca: Enter com EAN exato adiciona 1 unidade direto (leitor de código de barras); senão lista resultados.
- Prévia ao vivo por `calculo.py`. Painel do cliente mostra observações, dependentes e "somente titular" como aviso (sem regra aplicada).
- Crediário: exige cliente, desabilita desconto e mostra aviso quando o total passa do disponível.
- Dinheiro: "Recebido" opcional; preenchido e menor que o total bloqueia Finalizar.
- Finalizar: `EstoqueInsuficiente` → confirmação (admin logado) ou `DialogoAutorizacao` (login + senha) e reenvio; `LimiteExcedido` → confirmação e reenvio. Sucesso → mensagem na própria tela ("Venda nº X registrada"), carrinho limpo, gaveta atualizada.
- `DialogoRecebimento`: cliente, saldo, valor, forma, recebido/troco, aviso de excedente → crédito a favor.
- `DialogoFechamento`: resumo por forma, recebimentos à parte, canceladas, gaveta; valor mantido → sangria; confirmar.
- `DialogoVendasSessao`: lista com detalhe; **Cancelar** pede motivo e, se o logado não é admin, `DialogoAutorizacao`.
- Cadastro de cliente continua só em Clientes.

### 6.2 `cfauto/ui/historico/` — `TelaHistorico` (módulo HISTORICO)

- Aba **Vendas**: filtros (período, padrão mês atual; forma; tipo; cliente; incluir canceladas); duplo clique abre o detalhe.
- Aba **Sessões**: lista; duplo clique mostra o resumo gravado.

### 6.3 Configurações › Parâmetros

`PaginaParametros` substitui o placeholder em `ui/configuracoes.py`: grupo "Taxas por forma de pagamento" (forma | % | dias | repasse | Salvar). Demais parâmetros continuam para depois.

## 7. Testes

TDD com os fixtures atuais (`fabrica`, `relogio` fixo, admin e operador), banco criado pelas migrations.

- **`tests/caixa/test_calculo.py`:** taxa 0; arredondamento no total; repasse × sem repasse; desconto % e R$ nos limites e fora deles; `data_liquidacao`; crediário sem liquidação; troco e recebido insuficiente; resumo com recebimentos separados, canceladas fora, gaveta e sangria.
- **Sessão:** uma aberta (serviço e índice parcial); protocolo que colide ganha `-2`; sugestão de fundo; fechamento grava resumo/sangria e torna a sessão imutável; venda sem sessão → `SessaoFechada`; faixa do valor mantido.
- **Venda:** carrinho misto baixa só produto; preço do banco (promocional vale); produto repetido somado na checagem; `EstoqueInsuficiente` para operador e para admin logado sem `confirmar_estoque`, aprovado com a flag + admin responsável (grava `autorizado_por`), autorizador não-admin recusado; crediário exige cliente, recusa desconto e lança DEBITO com `venda_id`; `LimiteExcedido` com e sem confirmação; sem limite não avisa; crédito a favor consumido (−50 + 30 = −20).
- **Recebimento:** CREDITO no razão; excedente vira crédito a favor; taxa e repasse; cliente inativo recusado; forma CREDIARIO recusada.
- **Cancelamento:** permissão (admin, autorizador, operador sozinho); só sessão aberta; devolve estoque; estorna razão de crediário (CREDITO) e de recebimento (DEBITO); não cancela duas vezes; auditoria.
- **Taxas:** só admin altera; 0 aceito; auditoria.
- **Integração:** buscas liberadas para quem só tem PDV; `lancar_manual` recusa motivos automáticos; extrato imprime os motivos novos; `excluir_cliente` barra cliente com vendas; `autorizar_admin` recusa operador e conta tentativas falhas.
- **Histórico:** só sessões fechadas; filtros; `dias_liquidacao` inteiro e nulo no crediário.
- **UI (pytest-qt, offscreen):** PDV sem sessão mostra só Abrir caixa; venda completa atualiza a gaveta; crediário desabilita desconto; fluxo do operador abre `DialogoAutorizacao`; fechamento mostra a sangria; Histórico e Parâmetros carregam; operador não vê Parâmetros.
- **Migração:** `0004` sobe e desce; as 4 taxas-padrão existem.

## 8. QA manual (validação conjunta com o cliente, após o 4A)

Roda junto com o checklist do Clientes (plano de 28/09, Task 8, Passo 7), com o `.exe` rebuildado e pasta de dados descartável:

1. Abrir caixa com fundo sugerido; tentar vender com caixa fechado (bloqueado).
2. Venda mista (produto + serviço) em dinheiro com desconto e troco; estoque do produto baixa, serviço não.
3. Venda em débito com repasse ligado em Parâmetros: total cobrado inclui a taxa.
4. Operador vende produto sem estoque: pede senha do admin; com a senha, conclui.
5. Venda no crediário acima do limite: aviso, confirma; extrato do cliente mostra "Venda no crediário".
6. Receber crediário maior que a dívida: vira crédito a favor; próxima venda a prazo consome o crédito.
7. Operador cancela uma venda com a senha do admin: estoque volta, razão estornado.
8. Fechar caixa: resumo por forma, recebimentos à parte, gaveta e sangria conferidos à mão.
9. Histórico mostra a sessão fechada e suas vendas; venda cancelada só com o filtro.

## 9. Mudanças na spec de arquitetura (feitas junto com esta spec)

§1.1 (Clientes: saldo pelo razão, automático pelo PDV), §1.3 (sai "incremento manual do saldo"), §3.2 (tipos de venda, autorizações, `taxa_pagamento.repasse`, crediário fora da tabela), §4.1 (carrinho misto, autorização por senha, crediário no razão, desconto), §4.4 (recebimento automático), §6.1 (taxas fora do assistente), §6.2 (Parâmetros com taxas), §7.4 (4A/4B), §8 (divergências 39–40), §9 (pendência do crediário resolvida).
