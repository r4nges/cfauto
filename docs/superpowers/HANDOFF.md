# CFAUTO — Handoff

Atualizado em 28/09/2026. Leia primeiro este arquivo; depois a spec e o plano do sub-projeto em andamento.

## Onde estamos

- **Sub-projeto 1 — Fundação: concluído, validado manualmente e em `main`.**
  core, db + Alembic, auth + usuários, licença, provisionamento/assistente, janela principal com login e navegação, auditoria, esqueleto de jobs.
- **Sub-projeto 2 — Estoque: concluído (12/12 tasks via SDD) e mergeado em `main` (fast-forward, sem conflito).**
  Produto e livro de movimentos, Serviço com materiais e preço calculado, Bens Físicos, leitura de XML de NF-e, entrada por NF-e com conferência item a item e vínculo por fornecedor, estorno só-admin com religação de cadeia de custo, e 4 telas de UI (Estoque/Produtos, Serviços, Entradas de NF-e, Bens Físicos em Configurações › CFAUTO). Review final whole-branch (opus): 1 Important corrigido (estorno fora de ordem restaurava custo de nota já estornada — corrigido e re-revisado limpo), 7 Minor deferred (não bloqueiam, ver commits/PRs de cada task pro detalhe — ledger do plano já foi removido, histórico vive no git).
- Suíte: 400 testes, ruff e mypy limpos (pre-commit roda os três).
- **Sub-projeto 3 — Clientes: implementação concluída via SDD (8/8 tasks, cada uma revisada individualmente) mais uma review final whole-branch limpa** (branch `feat/clientes`, ainda não mergeada em `main`). Cadastro com dependentes, razão `cliente_lancamento` (saldo só muda por `clientes.razao.lancar`), lançamento manual débito/crédito, saldo negativo = crédito a favor, extrato com impressão (`QPrintPreviewDialog`), inativar/reativar/excluir só-admin. **Falta**: rodar o checklist de QA manual do Passo 7 da Task 8 do plano (criar cliente com dependentes, aviso de celular duplicado, creditar mais que a dívida mostra "crédito a favor", imprimir extrato — preview abre, imprime via "Microsoft Print to PDF", operador não vê Inativar/Excluir nem edita o limite) — ainda não foi executado por um humano.
- **Próximo: sub-projeto 4 — Caixa/PDV.** Decisões pendentes que ele herda: se venda no crediário e recebimento lançam no razão automaticamente (motivos `VENDA_CREDIARIO`/`RECEBIMENTO` + coluna `venda_id`), como usar o crédito a favor, alerta de limite, observações do cliente no PDV, e se `buscar_clientes` precisa aceitar o módulo PDV.

## Débito técnico conhecido do Estoque (Minor, não bloqueante — considerar nos próximos sub-projetos)

- UI cria entidades ORM temporárias pra prévia ao vivo em Produtos/Serviços (`ui/estoque/produtos.py`, `ui/estoque/servicos.py`), contrariando a regra "ui nunca usa ORM" da spec §2.2 — plan-mandated, mas vai se repetir no PDV (sub-projeto 4). Recomendado extrair cálculos de preço/fracionado pra funções puras antes de reusar o padrão lá.
- Custo exibido em telas de estoque usa 2 casas, escondendo a precisão de 4 casas do `Custo()` — considerar `formatar_custo` com até 4 casas se precisão visual importar em telas futuras.
- Auditoria de estorno de nota não registra a mudança de custo do produto (dá pra reconstruir pelos itens da nota, mas não fica explícito no log).
- Falta política única de tamanho de texto entre `criar_produto` (sem validação/truncamento) e `_criar_produto` da entrada por NF-e (trunca em silêncio em 200 chars).

## Débito técnico conhecido do Clientes (Minor, não bloqueante — considerar nos próximos sub-projetos)

- `razao.lancar` não tem lock de linha sobre `saldo_devedor` (lê e escreve na mesma transação, sem trava). Adiado de propósito: CFAUTO é um processo desktop SQLite único; multiusuário significa múltiplos logins na mesma máquina, não processos concorrentes do SO. `with_for_update()` é um no-op no SQLite; se algum dia for preciso, usar `BEGIN IMMEDIATE` na transação. Espelha o mesmo padrão de `estoque.movimentos.movimentar`.
- O sub-projeto 4 vai adicionar membros de `MotivoLancamento` (`VENDA_CREDIARIO`, `RECEBIMENTO`) para lançamentos automáticos de venda/recebimento. Quando isso acontecer: o diálogo de lançamento manual em `cfauto/ui/clientes/lancamento.py` hoje lista todos os membros de `MotivoLancamento` e `razao.lancar_manual` aceita qualquer um deles — um operador poderia criar à mão um lançamento "Venda no crediário" sem `venda_id`. Recomendado um subconjunto `MOTIVOS_MANUAIS` (excluindo os motivos futuros só-de-venda/pagamento) compartilhado pelo diálogo e por `lancar_manual`. Além disso, `descrever_lancamento` em `extrato_html.py` indexa `TITULOS_MOTIVO_LANCAMENTO` diretamente pelo motivo — um motivo novo sem entrada correspondente gera `KeyError` ao imprimir um extrato; todo novo membro de `MotivoLancamento` precisa da entrada em `TITULOS_MOTIVO_LANCAMENTO` na mesma mudança.
- Excluir um cliente que tenha vendas num módulo futuro (vendas não estão nesta branch) mas nenhuma linha em `cliente_lancamento` hoje bateria na constraint de chave estrangeira do banco (`PRAGMA foreign_keys=ON`) e levantaria `IntegrityError`, capturado pelo hook global de exceção do app em vez de um erro de domínio limpo. O sub-projeto 4/5 deve decidir se "tem vendas" precisa de sua própria guarda em `excluir_cliente`, similar a `ClienteComHistorico`.

## Documentos

| O quê | Onde |
|---|---|
| Requisitos originais | `prompt-claude-code-cfauto.md` |
| Spec de arquitetura (manda sobre tudo) | `docs/superpowers/specs/2026-09-23-cfauto-arquitetura-design.md` |
| Plano da Fundação | `docs/superpowers/plans/2026-09-23-fundacao.md` |
| Código original (Apps Script) e análises | `referencia/appsscript/`, `referencia/analise/*.md` |
| Ledger da execução da Fundação (local, fora do git) | `.superpowers/sdd/2026-09-23-fundacao/progress.md` |
| Prints da validação manual | `docs/superpowers/erros/` |

Ordem dos sub-projetos (spec §7.4): 1 Fundação ✔ → 2 Estoque → 3 Clientes → 4 Caixa/PDV → 5 Saídas → 6 CFAUTO I → 7 CFAUTO II → 8 Compras → 9 Importador/seed/empacotamento. ~1 semana cada; apresentação no hackathon em dezembro/2026. Demo mínima (cadastro → venda → relatório) ao fim do 6.

## Decisões recentes (validação manual da Fundação, 27/09)

- **CFAUTO e USUARIOS são só-admin** (`MODULOS_SO_ADMIN` em `cfauto/core/permissoes.py`): nunca liberados pela lista de módulos, nem na tela de usuários nem no serviço.
- **Navegação**: menu lateral retrátil (botão ☰) só com os módulos operacionais. CFAUTO, Usuários e Auditoria ficam na página **Configurações** (botão na barra, só admin), que também tem a aba **Parâmetros** reservada para a futura parametrização (candidatos na spec §6.2).
- **Inatividade**: bloqueio de tela padrão de 5 min (`seguranca.minutos_inatividade`).
- **Estilo base adiado para depois dos módulos principais** (Estoque → CFAUTO I). Até lá o app força esquema claro (`configurar_aparencia` em `cfauto/ui/app.py`), porque o modo escuro do Windows deixava rótulos invisíveis no assistente. Escopo previsto do estilo base: Fusion + paleta própria, cores/fontes centralizadas (hoje há hex soltos em `login.py`, `licenca.py`, `janela_principal.py`), `QTranslator` pt_BR (botões do Qt ainda em inglês: "Next"/"Cancel"), padrões de formulário/tabela/botão e visual do menu lateral.

## Itens adiados da Fundação (ruling R11 do ledger)

Recuperação anti-rollback da licença via data de emissão, filtro por usuário na auditoria, `--icon` no build, teste de `Aplicacao`, `pytest-cov` no pre-commit, config tipado. Alerta, `schemas.py` e taxas no assistente entram nos sub-projetos 4 e 7.

## Pendências a validar com o usuário (spec §9)

- Fonte do XML a partir da chave de acesso da NF-e — **primeira pergunta do sub-projeto 2**.
- Saldo devedor de crediário manual — resolvido no sub-projeto 3 (razão `cliente_lancamento`, ver spec §9 atualizada).
- Ordem das colunas da aba CAIXA e se `VALOR` do Histórico é unitário ou total — antes do importador (sub-projeto 9).

## Como rodar

```powershell
uv sync
uv run pytest
$env:CFAUTO_HOME = "$env:TEMP\cfauto-teste"; uv run python -m cfauto   # pasta de dados descartável
powershell -ExecutionPolicy Bypass -File build.ps1                      # gera dist/CFAUTO.exe
```

Licença de teste: `uv run python tools/gerar_licenca.py emitir --cliente "Teste" --dias 30` (chave privada em `%USERPROFILE%\.cfauto-licenca\privada.pem`, fora do repo).

## Armadilhas do ambiente

- O hook do RTK engole a linha de resumo do pytest. Use `rtk proxy uv run pytest` e, para contar testes, `--junitxml`.
- O Smart App Control do Windows bloqueia `mypy.exe` (por isso o pre-commit usa `uv run -m mypy`) e pode bloquear o `CFAUTO.exe` não assinado.
- Os testes de UI rodam com `QT_QPA_PLATFORM=offscreen` (`tests/conftest.py`), que ignora esquema de cor; o teste de aparência usa subprocesso com o plugin `windows`.
- Não colar `\u00a0` e afins em mensagens de commit via heredoc: o escape vira o caractere invisível.
