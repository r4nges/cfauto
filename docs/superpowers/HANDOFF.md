# CFAUTO — Handoff

Atualizado em 04/10/2026. Leia primeiro este arquivo; depois a spec e o plano do sub-projeto em andamento.

## Onde estamos

- **Sub-projeto 1 — Fundação: concluído, validado manualmente e em `main`.**
  core, db + Alembic, auth + usuários, licença, provisionamento/assistente, janela principal com login e navegação, auditoria, esqueleto de jobs.
- **Sub-projeto 2 — Estoque: concluído (12/12 tasks via SDD) e mergeado em `main` (fast-forward, sem conflito).**
  Produto e livro de movimentos, Serviço com materiais e preço calculado, Bens Físicos, leitura de XML de NF-e, entrada por NF-e com conferência item a item e vínculo por fornecedor, estorno só-admin com religação de cadeia de custo, e 4 telas de UI (Estoque/Produtos, Serviços, Entradas de NF-e, Bens Físicos em Configurações › CFAUTO). Review final whole-branch (opus): 1 Important corrigido (estorno fora de ordem restaurava custo de nota já estornada — corrigido e re-revisado limpo), 7 Minor deferred (não bloqueiam, ver commits/PRs de cada task pro detalhe — ledger do plano já foi removido, histórico vive no git).
- Suíte: 403 testes, ruff e mypy limpos (pre-commit roda os três).
- **Sub-projeto 3 — Clientes: concluído (8/8 tasks via SDD, cada uma revisada individualmente, mais review final whole-branch limpa) e mergeado em `main`** (fast-forward, sem conflito; branch `feat/clientes` já deletada). Cadastro com dependentes, razão `cliente_lancamento` (saldo só muda por `clientes.razao.lancar`), lançamento manual débito/crédito, saldo negativo = crédito a favor, extrato com impressão (`QPrintPreviewDialog`), inativar/reativar/excluir só-admin. **Falta**: rodar o checklist de QA manual do Passo 7 da Task 8 do plano (criar cliente com dependentes, aviso de celular duplicado, creditar mais que a dívida mostra "crédito a favor", imprimir extrato — preview abre, imprime via "Microsoft Print to PDF", operador não vê Inativar/Excluir nem edita o limite) — nenhum subagent tem display para rodar isso; ainda não foi executado por um humano, apesar de já estar em `main`. **Adiado por decisão de 29/09: a validação manual roda depois do Caixa/PDV**, junto com o Caixa, para o cliente também poder testar (ver "Ordem de trabalho atual").
- **Sub-projeto 4A — Caixa/PDV: concluído na branch `feat/caixa-4a`** (13 tasks; spec `docs/superpowers/specs/2026-09-29-caixa-4a-design.md`, plano `docs/superpowers/plans/2026-09-29-caixa-4a.md`). Sessão de caixa com fundo e protocolo, venda mista produto + serviço, desconto R$/%, taxas por forma com repasse (Configurações › Parâmetros), crediário e recebimento lançados no razão do cliente (`VENDA_CREDIARIO`/`RECEBIMENTO`/`CANCELAMENTO`, com `venda_id`), limite com aviso + confirmação, autorização do admin por senha na hora (estoque insuficiente e cancelamento), cancelamento com estorno de estoque e razão só com a sessão aberta, fechamento com resumo e sangria, Histórico (vendas e sessões fechadas). Suíte: 602 testes; ruff e mypy limpos. **Falta**: review final whole-branch, merge em `main` e a validação manual conjunta (abaixo).
- **Próximo: sub-projeto 4B** — venda externa (4 deduções), contrato/assinatura com parcelas, job de ativação de parcelas e relatório "já disponível × a cair".

- **Ainda não commitado no working tree** (carregado em `feat/caixa-4a`): o fix do diálogo "Novo cliente" que não cabia na tela (`cfauto/ui/clientes/dialogo_cliente.py` com `QScrollArea` e Salvar/Cancelar fixos, mais o teste `test_dialogo_cabe_na_tela_e_rola_com_botoes_fixos` em `tests/ui/test_clientes.py`) e os prints em `docs/superpowers/erros/`. Deve ganhar commit próprio (`fix(clientes): ...`) antes do merge de `feat/caixa-4a`.

## Ordem de trabalho atual (decidida em 29/09/2026)

1. **Sub-projeto 4A — Caixa/PDV**: concluído (ver acima).
2. **Agora: validação manual conjunta** — checklist do Clientes (plano de 28/09, Task 8, Passo 7) + roteiro da spec do 4A (§8), feita pelo usuário e pelo cliente com o `dist\CFAUTO.exe` rebuildado. A investigação da travadinha (seção "A verificar") entra junto. Depois: 4B e sub-projeto 5 (Saídas).
3. **Sub-projeto 4B** (venda externa, contrato + parcelas, job de ativação, relatório "já disponível × a cair") — precisa de spec própria.
4. Só então sub-projeto 5 (Saídas) em diante.

Motivo: entregar um fluxo testável ponta a ponta (cadastro → venda → crediário) para o cliente validar, em vez de validar módulos isolados.

## Débito técnico conhecido do Estoque (Minor, não bloqueante — considerar nos próximos sub-projetos)

- UI cria entidades ORM temporárias pra prévia ao vivo em Produtos/Serviços (`ui/estoque/produtos.py`, `ui/estoque/servicos.py`), contrariando a regra "ui nunca usa ORM" da spec §2.2 — plan-mandated. O PDV não repete o padrão: a prévia usa `cfauto/caixa/calculo.py` (funções puras). As telas do Estoque continuam como estão.
- Custo exibido em telas de estoque usa 2 casas, escondendo a precisão de 4 casas do `Custo()` — considerar `formatar_custo` com até 4 casas se precisão visual importar em telas futuras.
- Auditoria de estorno de nota não registra a mudança de custo do produto (dá pra reconstruir pelos itens da nota, mas não fica explícito no log).
- Falta política única de tamanho de texto entre `criar_produto` (sem validação/truncamento) e `_criar_produto` da entrada por NF-e (trunca em silêncio em 200 chars).

## Débito técnico conhecido do Clientes (Minor, não bloqueante — considerar nos próximos sub-projetos)

- `razao.lancar` não tem lock de linha sobre `saldo_devedor` (lê e escreve na mesma transação, sem trava). Adiado de propósito: CFAUTO é um processo desktop SQLite único; multiusuário significa múltiplos logins na mesma máquina, não processos concorrentes do SO. `with_for_update()` é um no-op no SQLite; se algum dia for preciso, usar `BEGIN IMMEDIATE` na transação. Espelha o mesmo padrão de `estoque.movimentos.movimentar`.
- Resolvido no 4A: `MOTIVOS_MANUAIS` separa os motivos manuais dos automáticos do caixa; os títulos dos motivos novos existem em `TITULOS_MOTIVO_LANCAMENTO`; `excluir_cliente` recusa cliente com vendas.

## Documentos

| O quê | Onde |
|---|---|
| Requisitos originais | `prompt-claude-code-cfauto.md` |
| Spec de arquitetura (manda sobre tudo) | `docs/superpowers/specs/2026-09-23-cfauto-arquitetura-design.md` |
| Plano da Fundação | `docs/superpowers/plans/2026-09-23-fundacao.md` |
| Spec do Caixa 4A | `docs/superpowers/specs/2026-09-29-caixa-4a-design.md` |
| Plano do Caixa 4A | `docs/superpowers/plans/2026-09-29-caixa-4a.md` |
| Código original (Apps Script) e análises | `referencia/appsscript/`, `referencia/analise/*.md` |
| Ledger da execução da Fundação (local, fora do git) | `.superpowers/sdd/2026-09-23-fundacao/progress.md` |
| Prints da validação manual | `docs/superpowers/erros/` |
| Grafo de conhecimento do repo (código + docs + specs), gerado via `/graphify` em 29/09/2026 — 1461 nós, 5207 arestas, 99 comunidades. Abrir `graph.html` num navegador ou perguntar direto (`/graphify query "..."`). Desatualiza a cada commit; rodar `/graphify --update` (ou refazer) antes de confiar nele pra explorar o sub-projeto 4 em diante | `graphify-out/GRAPH_REPORT.md`, `graphify-out/graph.html` (fora do git) |

Ordem dos sub-projetos (spec §7.4): 1 Fundação ✔ → 2 Estoque → 3 Clientes → 4 Caixa/PDV → 5 Saídas → 6 CFAUTO I → 7 CFAUTO II → 8 Compras → 9 Importador/seed/empacotamento. ~1 semana cada; apresentação no hackathon em dezembro/2026. Demo mínima (cadastro → venda → relatório) ao fim do 6.

## Decisões recentes (validação manual da Fundação, 27/09)

- **CFAUTO e USUARIOS são só-admin** (`MODULOS_SO_ADMIN` em `cfauto/core/permissoes.py`): nunca liberados pela lista de módulos, nem na tela de usuários nem no serviço.
- **Navegação**: menu lateral retrátil (botão ☰) só com os módulos operacionais. CFAUTO, Usuários e Auditoria ficam na página **Configurações** (botão na barra, só admin), que também tem a aba **Parâmetros** reservada para a futura parametrização (candidatos na spec §6.2).
- **Inatividade**: bloqueio de tela padrão de 5 min (`seguranca.minutos_inatividade`).
- **Estilo base adiado para depois dos módulos principais** (Estoque → CFAUTO I). Até lá o app força esquema claro (`configurar_aparencia` em `cfauto/ui/app.py`), porque o modo escuro do Windows deixava rótulos invisíveis no assistente. Escopo previsto do estilo base: Fusion + paleta própria, cores/fontes centralizadas (hoje há hex soltos em `login.py`, `licenca.py`, `janela_principal.py`), `QTranslator` pt_BR (botões do Qt ainda em inglês: "Next"/"Cancel"), padrões de formulário/tabela/botão e visual do menu lateral.

## Itens adiados da Fundação (ruling R11 do ledger)

Recuperação anti-rollback da licença via data de emissão, filtro por usuário na auditoria, `--icon` no build, teste de `Aplicacao`, `pytest-cov` no pre-commit, config tipado. Alerta, `schemas.py` e taxas no assistente entram nos sub-projetos 4 e 7.

## A verificar: travadinha ao abrir o app e ao clicar em Sair (relatado em 29/09, QA manual do Clientes)

Sintoma: o `CFAUTO.exe` dá uma pequena trava ao abrir e ao clicar em Sair. Ainda **não medido** — só hipóteses lidas no código (`cfauto/ui/app.py`, `janela_principal.py`):

- **Abrir**: o `.exe` é `--onefile` do PyInstaller, que descompacta ~57 MB em `%TEMP%\_MEI*` a cada execução (e o Smart App Control escaneia). Comparar com `uv run python -m cfauto` (sem descompactação): se a trava sumir, é o empacotamento; alternativa `--onedir`. Também roda na thread da UI antes do login: migração Alembic, `catchup` dos jobs e, depois do login, `JanelaPrincipal` cria todas as telas de módulo, cada uma com consulta ao banco.
- **Sair**: o menu Sair (`_sair` → `fechar_sessao` → `_logout`) destrói a janela e monta o `DialogoLogin` na mesma thread. Já fechar o app de vez dispara `_ao_sair`, que roda `fazer_backup` **na thread da UI** antes de encerrar — cópia do banco cresce com os dados. Medir o tempo de `fazer_backup` e do construtor de `JanelaPrincipal` antes de decidir (mover backup para thread/`QThread`, ou construir telas sob demanda).

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
- Desde 29/09 também bloqueia `pytest.exe` (erro 4551), então `build.ps1` falha no passo de testes. Use sempre `uv run -m pytest` (com `rtk proxy` na frente) e `uv run -m PyInstaller --noconfirm --clean --onefile --windowed --name CFAUTO --add-data "cfauto/migrations;cfauto/migrations" --collect-submodules cfauto --collect-submodules apscheduler cfauto/__main__.py`; o `build.ps1` ainda não foi ajustado.
- O `.exe` aberto trava o rebuild de `dist\CFAUTO.exe`: feche o app antes.
- Os testes de UI rodam com `QT_QPA_PLATFORM=offscreen` (`tests/conftest.py`), que ignora esquema de cor; o teste de aparência usa subprocesso com o plugin `windows`.
- Não colar `\u00a0` e afins em mensagens de commit via heredoc: o escape vira o caractere invisível.
