# CFAUTO — Handoff

Atualizado em 28/09/2026. Leia primeiro este arquivo; depois a spec e o plano do sub-projeto em andamento.

## Onde estamos

- **Sub-projeto 1 — Fundação: concluído, validado manualmente e em `main`.**
  core, db + Alembic, auth + usuários, licença, provisionamento/assistente, janela principal com login e navegação, auditoria, esqueleto de jobs.
- **Sub-projeto 2 — Estoque: concluído (12/12 tasks via SDD) e mergeado em `main` (fast-forward, sem conflito).**
  Produto e livro de movimentos, Serviço com materiais e preço calculado, Bens Físicos, leitura de XML de NF-e, entrada por NF-e com conferência item a item e vínculo por fornecedor, estorno só-admin com religação de cadeia de custo, e 4 telas de UI (Estoque/Produtos, Serviços, Entradas de NF-e, Bens Físicos em Configurações › CFAUTO). Review final whole-branch (opus): 1 Important corrigido (estorno fora de ordem restaurava custo de nota já estornada — corrigido e re-revisado limpo), 7 Minor deferred (não bloqueiam, ver commits/PRs de cada task pro detalhe — ledger do plano já foi removido, histórico vive no git).
- Suíte: 400 testes, ruff e mypy limpos (pre-commit roda os três).
- **Sub-projeto 3 — Clientes: concluído** (branch `feat/clientes`). Cadastro com dependentes, razão `cliente_lancamento` (saldo só muda por `clientes.razao.lancar`), lançamento manual débito/crédito, saldo negativo = crédito a favor, extrato com impressão (`QPrintPreviewDialog`), inativar/reativar/excluir só-admin.
- **Próximo: sub-projeto 4 — Caixa/PDV.** Decisões pendentes que ele herda: se venda no crediário e recebimento lançam no razão automaticamente (motivos `VENDA_CREDIARIO`/`RECEBIMENTO` + coluna `venda_id`), como usar o crédito a favor, alerta de limite, observações do cliente no PDV, e se `buscar_clientes` precisa aceitar o módulo PDV.

### Resumo do plano do sub-projeto 3 (Clientes)

1. **Modelo + migração `0003_clientes` + erros.** `cfauto/clientes/models.py`: enums `Sexo` (M/F/OUTRO), `FrequenciaJuros` (DIARIO/MENSAL/BIMESTRAL), `TipoLancamento` (DEBITO/CREDITO), `MotivoLancamento` (COMPRA_ANOTADA/PAGAMENTO/CORRECAO/OUTRO) + dicts `TITULOS_*`; `LIMITE_PADRAO = Decimal("500.00")`, `MAX_DEPENDENTES = 4`; `Cliente` (spec §2.1; `index=True` em `nome_busca`, `celular`, `cpf`; `dependentes` com cascade delete-orphan, lazy selectin, ordenado por id; property `disponivel`), `ClienteDependente`, `ClienteLancamento` com `Index("ix_cliente_lancamento_cliente_data", "cliente_id", "data_hora")`. Migração no estilo da 0002 (Decimal → `sa.Integer`, enum → `sa.String(20)`, nomes pela `CONVENCAO_NOMES`). Registrar em `cfauto/modelos.py`. Erros `ClienteComSaldo` e `ClienteComHistorico` (`ErroDominio`). O teste `test_modelos_batem_com_migracoes` já cobre a migração.
2. **`clientes/validacao.py`** (funções puras): `so_digitos`; `normalizar_nome` ("Informe nome e sobrenome."); `normalizar_celular` (vazio → "Celular obrigatório."; tira o prefixo 55 quando há 12–13 dígitos; fora de 10–11 dígitos → "Celular deve ter DDD + número (10 ou 11 dígitos)."; DDD < 11 → "DDD inválido."); `cpf_valido` e `normalizar_cpf` (vazio ou só " .-" → None; senão "CPF inválido."); `normalizar_email` ("E-mail inválido."); `formatar_celular`, `formatar_cpf`, `formatar_saldo` (negativo → "Crédito a favor R$ X"). CPFs de teste: válidos 529.982.247-25 e 111.444.777-35; inválido 529.982.247-26.
3. **`schemas.py` + `cadastro.py`.** Schemas: `DadosDependente(nome, parentesco="")`; `DadosCliente` (todos os campos, `limite=LIMITE_PADRAO`, `dependentes: tuple`); `ResumoCliente(id, codigo, nome, celular, cpf, saldo_devedor, limite, disponivel, ativo)`; `FichaCliente(id, codigo, dados, saldo_devedor, disponivel, ativo)`; `LinhaLancamento(id, data_hora, tipo, valor, saldo_apos, motivo, observacao, usuario)`; `Extrato(cliente, inicio, fim, saldo_anterior, linhas, saldo_final)`. Funções:
   - `criar_cliente` → int; `editar_cliente`.
   - `verificar_duplicados(s, ator, dados, ignorar_id=None)`: valida `dados` antes de procurar.
   - `buscar_clientes(s, ator, texto, *, incluir_inativos=False)`: `contains(..., autoescape=True)`; com ≥ 3 dígitos, casa também CPF/celular.
   - `obter_cliente` → `FichaCliente`; `carregar_cliente` (entidade ORM, usada pelo razão); `resumo_cliente`.
   - Não-admin criando com limite ≠ padrão, ou alterando o limite numa edição → `PermissaoNegada("Só administradores alteram o limite de crédito.")`.
   - Auditoria: `registrar(s, ator.id, "criar"|"alterar", "cliente", id, antes, depois)` (o código usa ação e entidade separadas, não "cliente.criar").
   - Tamanhos de texto validados com `ValorInvalido`.
4. **`razao.py`**:
   - `saldo_apos(saldo, tipo, valor)`: função pura.
   - `lancar`: porta única. Valor arredondado ≤ 0 → "O valor do lançamento deve ser maior que zero."; CORRECAO sem observação → erro. Audita com a ação "lancamento".
   - `lancar_manual` → `LinhaLancamento`: exige o módulo CLIENTES; cliente inativo → "Cliente inativo: reative antes de lançar."
   - `extrato(s, ator, cliente_id, inicio, fim)`: fim < início → erro; join com `Usuario.nome.label("usuario")`; período [início 00:00, fim + 1 dia 00:00).
5. **Inativar/reativar/excluir** em `cadastro.py`:
   - Todas exigem admin (`exigir_admin`).
   - Saldo ≠ 0 → `ClienteComSaldo` ("O cliente deve R$ X; zere o saldo antes de inativar." ou "tem crédito a favor de R$ X").
   - Excluir cliente com lançamentos → `ClienteComHistorico` ("... use Inativar.").
   - Código de cliente nunca reaproveitado.
6. **`extrato_html.py`**: `descrever_lancamento(linha)`; `gerar_html_extrato(extrato, loja, emitido_em)` com `html.escape`; período vazio → "Nenhum lançamento no período."; nome da loja vem de `config.obter(s, "empresa.nome", "")`.
7. **UI de cadastro** (`cfauto/ui/clientes/`: `dialogo_cliente.py`, `tela.py`):
   - `TelaClientes`: busca, "mostrar inativos", Novo/Editar. Os botões `botao_situacao` e `botao_excluir` ficam ocultos para não-admin. Exclusão por `excluir_selecionado(confirmar)`.
   - `DialogoCliente(fabrica, ator, ficha=None)`:
     - Celular e CPF sem `inputMask`: reformatar no `editingFinished`.
     - Nascimento em `QLineEdit` (dd/mm/aaaa), lido com `dates.para_data`.
     - Limite e "sem limite" desabilitados para não-admin; 4 linhas de dependente.
     - `salvar(confirmar=None)`: por padrão pergunta com `_perguntar`, como em `ui/estoque/entradas.py:486`.
   - Registrar `Modulo.CLIENTES: TelaClientes` em `PAGINAS_DOS_MODULOS` (`ui/janela_principal.py:29`).
8. **UI do razão**:
   - `ui/clientes/lancamento.py`: `DialogoLancamento(fabrica, ator, resumo)` com prévia "Saldo após: …" (ou "—" quando o valor é inválido).
   - `ui/clientes/extrato.py`: `DialogoExtrato`, período padrão = últimos 90 dias. `imprimir()` chama `_abrir_previa(doc)`, que abre `QPrintPreviewDialog` e imprime com `doc.print_`; nos testes, monkeypatch de `_abrir_previa`.
   - Botões Lançamento/Extrato na tela; por fim, atualizar este HANDOFF.

Review Focus do plano: (1) celular "+55 (11) 98765-4321" → 11 dígitos; (2) busca por "%" ou "_" não lista todo mundo; (3) valor 0,004 arredonda a zero → rejeitado; (4) lançamentos às 00:00 do dia inicial e às 23:59:59 do dia final entram no extrato; (5) operador edita cliente sem limite (`limite` None) sem ser barrado.

Fixtures úteis (`tests/conftest.py`): `sessao`, `admin`, `operador` (PDV + CLIENTES, nome "Maria"), `estoquista` (sem CLIENTES), `relogio` (2026-09-23 10:00). Na UI, `QMessageBox` trava o teste offscreen: fazer monkeypatch de `mostrar_erro` e passar `confirmar=` nos métodos.

## Débito técnico conhecido do Estoque (Minor, não bloqueante — considerar nos próximos sub-projetos)

- UI cria entidades ORM temporárias pra prévia ao vivo em Produtos/Serviços (`ui/estoque/produtos.py`, `ui/estoque/servicos.py`), contrariando a regra "ui nunca usa ORM" da spec §2.2 — plan-mandated, mas vai se repetir no PDV (sub-projeto 4). Recomendado extrair cálculos de preço/fracionado pra funções puras antes de reusar o padrão lá.
- Custo exibido em telas de estoque usa 2 casas, escondendo a precisão de 4 casas do `Custo()` — considerar `formatar_custo` com até 4 casas se precisão visual importar em telas futuras.
- Auditoria de estorno de nota não registra a mudança de custo do produto (dá pra reconstruir pelos itens da nota, mas não fica explícito no log).
- Falta política única de tamanho de texto entre `criar_produto` (sem validação/truncamento) e `_criar_produto` da entrada por NF-e (trunca em silêncio em 200 chars).

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
- Saldo devedor de crediário manual — revisitar após o sub-projeto 4.
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
