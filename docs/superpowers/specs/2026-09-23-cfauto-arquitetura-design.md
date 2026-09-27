# CFAUTO — Design de Arquitetura (reconstrução em Python)

- **Data:** 2026-09-23
- **Status:** aprovado em brainstorming, aguardando revisão da spec
- **Entrada:** `prompt-claude-code-cfauto.md` (requisitos), `referencia/appsscript/*.gs` (código original), `referencia/analise/*.md` (análise do código original)
- **Prazo:** apresentação no hackathon Aceleração de Viçosa, dezembro/2026 (~10 semanas)

## 0. Objetivo e princípios

Reconstruir como aplicação desktop Windows (executável único) o sistema de gestão CFAUTO, hoje distribuído em 10 planilhas Google Sheets + Apps Script, com banco SQLite local.

Princípios de fidelidade (aprovados):

1. O `prompt-claude-code-cfauto.md` manda onde é explícito.
2. Bugs do sistema original **não** são replicados. Cada correção está listada na seção 8 (Divergências intencionais).
3. Regras que só existem no código original entram quando aprovadas pelo usuário (lista na seção 1.2).
4. Definições contábeis/financeiras usam a definição padrão, com o nome correto na tela.

## 1. Escopo

### 1.1 Módulos

| Módulo | Origem | Conteúdo |
|---|---|---|
| Estoque | ESTOQUE | Produto, Serviço, entrada por NF-e, estorno |
| Clientes | CLIENTES | Cadastro, dependentes, extrato, saldo devedor (manual) |
| Caixa/PDV | CAIXA | Sessão, vendas, venda externa, contrato/assinatura, receber crediário, fechamento |
| Histórico | HISTORICO | Consulta de vendas de sessões fechadas |
| Saídas | SAÍDAS | Contas a pagar, parcelamento, empréstimo, boleto, pagamento, dashboard |
| Compras | COMPRAS | Fornecedores, cotação, sugestão de compra, pedido |
| CFAUTO | ADMINISTRATIVO | Markup, DRE, Balancete, Indicadores, Curva ABC, Bens Físicos, Comparador |
| Usuários | USUARIO + MENU | Login, permissões por módulo |
| Sistema | novo | Licença, provisionamento, auditoria, alertas, jobs, importador |

### 1.2 Funcionalidades do original fora do `.md`, aprovadas

- Entrada de mercadoria por NF-e (XML ou chave de acesso; **sem** PDF) e estorno de nota.
- Abertura de caixa com fundo de troco, sangria no fechamento, protocolo de sessão `CX-yyyyMMdd-HHmm`.
- Estoque mínimo por Curva ABC (job semanal).
- Saídas avançado: empréstimo (juros simples ou tabela Price), boleto multi-parcela (até 72), semáforo de vencimento, dashboard.
- Repasse de taxa ao cliente, relatório de vendas ("já disponível" × "a cair"), cadastro completo de cliente.

### 1.3 Fora de escopo

- Leitura de nota fiscal em PDF.
- Aplicação automática de juros/multa de crediário e aumento automático de limite (campos existem, sem efeito, como no original).
- Incremento automático do saldo devedor na venda a prazo (continua manual; validar com o usuário depois).
- Multi-terminal / acesso remoto.

## 2. Arquitetura

Monolito em camadas, um único processo. Jobs agendados rodam com APScheduler dentro do app, com recuperação na inicialização (processa o que venceu enquanto o app estava fechado). As funções dos jobs são funções de serviço puras, sem acoplamento ao scheduler, permitindo migrar para um serviço Windows no futuro.

Alternativas descartadas: serviço Windows separado (dois executáveis, privilégio de admin, concorrência no SQLite); backend FastAPI local + cliente Qt (dobra a superfície sem ganho para o caso de loja única).

### 2.1 Estrutura de pastas

```
cfauto/
  core/        db.py (engine, sessão, transação), config.py, clock.py (hoje injetável),
               money.py (Decimal, arredondamento), dates.py (normalização na borda), audit.py,
               errors.py (exceções de domínio)
  auth/        usuários, hash argon2, permissões, sessão logada
  licenca/     verificação Ed25519 offline, anti-relógio
  estoque/     produto, serviço, nota de entrada (NF-e), estorno, estoque mínimo
  clientes/    cliente, dependentes, extrato
  caixa/       sessão, venda, taxas/liquidação, externa, contrato + parcelas, recebimento, fechamento
  historico/   consultas sobre sessões fechadas
  saidas/      conta a pagar, parcelamento, empréstimo, boleto, pagamento
  compras/     fornecedor, cotação, sugestão, pedido
  cfauto/      markup, dre, balancete, indicadores, abc, bens, comparador
  jobs/        scheduler + catch-up
  importador/  .xlsx do Google → banco
  ui/          PySide6: main window, login, um subpacote por módulo, widgets de gráfico (matplotlib)
migrations/    Alembic
tests/         espelha os domínios
tools/         gerar_licenca.py (chave privada fora do repositório)
build.ps1
```

### 2.2 Regras de camada

- Cada domínio tem `models.py` (SQLAlchemy 2.x), `service.py` (regras) e `schemas.py` (dataclasses de entrada/saída com tipos reais: `Decimal`, `date`, `datetime`, enums).
- Funções de serviço recebem `Session` e o `Usuario` corrente e **verificam permissão** na entrada. A UI esconde o que o usuário não pode usar, mas a autoridade é o serviço.
- `ui/` chama apenas `service`. Nunca usa ORM nem SQL diretamente.
- `cfauto/` só lê dados dos outros domínios; a única escrita é o preço de venda / markup do produto (via serviço de estoque).
- Toda escrita roda em transação; o registro de auditoria é gravado na mesma transação.
- Acesso a campos sempre por nome (atributos ORM/dataclasses). Proibido acoplamento por posição (tuplas/índices) — ver bug nº 1 do `.md`.
- `clock.hoje()` / `clock.agora()` são a única fonte de data atual, substituível em testes.
- Datas vindas de fora (UI, importador, XML, APIs) são normalizadas em `core/dates.py`; string de data nunca circula internamente.

## 3. Modelo de dados

Convenções: PK inteira autoincremento; código de negócio legível (`0001`, `SERV-001`, `CLI-0001`, `SAI-0001`, `BEM-001`, `CX-…`) com `unique`, gerado por sequência e nunca reaproveitado. Dinheiro `Numeric(12,2)`, quantidade `Numeric(12,3)`. Toda tabela tem `criado_em`, `atualizado_em`; entidades de cadastro têm `ativo` (soft delete).

### 3.1 Cadastros

- **produto**: `codigo`, `ean` (unique, nullable), `descricao`, `categoria`, `embalagem`, `fator`, `data_ult_entrada`, `preco_entrada` (pacote), `preco_venda`, `preco_promocional` (nullable), `estoque`, `estoque_minimo`, `destino` (enum REVENDA / USO_CONSUMO / MATERIA_PRIMA), `markup_pct`, `markup_manual` (bool).
  - `preco_fracionado = preco_entrada / fator` e `margem = (preco_venda − fracionado) / preco_venda` são **calculados** (hybrid property), nunca gravados.
- **servico**: `codigo`, `nome`, `mao_obra_pct`, `ativo`; **servico_material**: `servico_id`, `descricao`, `custo_unit`, `qtd`. Preço = Σ(custo_unit × qtd) × (1 + mao_obra_pct/100), calculado. Um único cadastro de serviço.
- **bem_fisico**: `codigo`, `descricao`, `tipo` (MOVEL / INTANGIVEL / OUTROS), `valor`, `data_cadastro`.
- **cliente**: `codigo`, nome, CPF, contatos, endereço, `limite` (nullable = ilimitado), `saldo_devedor` (editado manualmente), campos de juros/multa (guardados, sem efeito), `somente_titular`; **cliente_dependente** (até 4 por cliente). Aviso de duplicidade por CPF/celular; exclusão bloqueada com saldo devedor > 0.
- **fornecedor**: nome, representante, contatos, condições, pedido mínimo.

### 3.2 Caixa

- **sessao_caixa**: `protocolo`, `aberta_em`, `aberta_por`, `fundo_troco`, `fechada_em`, `fechada_por`, `sangria`, `valor_mantido`, `resumo_json`, `status` (ABERTA / FECHADA). No máximo uma sessão ABERTA.
- **venda**: `sessao_id`, `data_hora`, `usuario_id`, `cliente_id` (nullable), `tipo` (PRODUTO / SERVICO / EXTERNA / CONTRATO / RECEBIMENTO), `forma_pagamento` (DINHEIRO / PIX / DEBITO / CREDITO / CREDIARIO / EXTERNA / BOLETO / CARTAO_CONTRATO), `bruto`, `desconto`, `taxa`, `liquido`, `repasse_taxa`, `data_liquidacao` (data calculada), `cancelada`, `cancelada_por`, `cancelada_em`, `motivo_cancelamento`.
- **venda_item**: `venda_id`, `produto_id` / `servico_id` (nullable), `descricao_snapshot`, `categoria_snapshot`, `qtd`, `preco_unit`, `subtotal`.
- **venda_externa_deducao**: `venda_id`, `origem`, `taxa_plataforma_pct`, `taxa_plataforma_valor`, `frete`, `desconto`, `motoboy`.
- **contrato**: cliente, descrição, valor da parcela, nº de parcelas, forma, dia base, tolerância; **parcela_receber**: `contrato_id`, `numero`, `vencimento`, `valor`, `status` (PENDENTE / ATIVADA / CANCELADA), `venda_id` (nullable).
- **taxa_pagamento**: `forma`, `pct`, `dias`. Valor 0 é válido. Padrões iniciais: Débito 1,5% / 7 dias; Crédito 3,5% / 7 dias; PIX 0% / 0; Dinheiro 0 / 0; Crediário 0 / — .

### 3.3 Histórico

Não há tabela copiada. O Histórico é uma **visão/consulta** sobre `venda` de sessões `FECHADA`, expondo `protocolo`, bruto, líquido e `dias_liquidacao = data_liquidacao − data(data_hora)` (inteiro), preservando a semântica que o `.md` distingue ("dias" no Histórico × data calculada na venda). Dados importados das planilhas entram em sessões com protocolo `IMPORT-…`.

### 3.4 Saídas

- **conta_pagar**: `codigo`, `grupo_parcela_id` (liga parcelas da mesma conta), `parcela_n`, `parcela_total`, `data_registro`, `categoria` (enum: CONTA_FIXA, CONTA_VARIAVEL, DESPESA_PREVISTA, DESPESA_IMPREVISTA, BOLETO, EMPRESTIMO, SALARIO, PRO_LABORE, OUTROS_PROVENTOS), `descricao`, `valor`, `vencimento`, `status` (PENDENTE / PAGO), `repeticao`, `juros`, `taxa_boleto`, `pago_em`, `valor_pago`, `multa_paga`, `observacao` (texto livre, sem semântica).
- **emprestimo**: `grupo_parcela_id`, `valor_recebido`, `data_recebimento`, `modo` (SIMPLES / PRICE), `taxa_mensal`, `n_parcelas`; **emprestimo_parcela**: `numero`, `amortizacao`, `juros`, `saldo`.

### 3.5 Estoque — notas

- **nota_entrada**: chave de acesso (unique), fornecedor, data de emissão, data de entrada, total, `estornada`; **nota_entrada_item**: `produto_id`, `qtd` (em unidades de estoque), `custo_unit`, dados originais do item do XML.

### 3.6 Compras

- **cotacao** (data, status), **cotacao_item** (`fornecedor_id`, `produto_id`, preço, observação), **pedido** (`fornecedor_id`, data, total), **pedido_item** (`produto_id`, qtd, preço). `ultimo_preco_pago` é derivado do último `pedido_item` do produto.

### 3.7 Sistema

- **usuario**: `nome`, `funcao`, `login` (unique), `senha_hash` (argon2id), `hash_legado` (SHA-256 do importador, nullable), `admin`, `modulos` (lista), `tentativas_falhas`, `bloqueado_ate`, `ativo`.
- **audit_log**: `usuario_id`, `acao`, `entidade`, `entidade_id`, `antes` (JSON), `depois` (JSON), `timestamp`.
- **config** (chave/valor tipado): capital social, lucros retidos, CDI manual, poupança, CDB % CDI, investimento simples, cartões ativos, cotações em cache (valor + data), última execução de cada job, tempo de bloqueio ocioso, dados da empresa.
- **licenca_estado**: chave instalada, `ultima_data_vista`.
- **alerta**: tipo, referência, mensagem, criado_em, lido.

## 4. Fluxos

### 4.1 Venda (PDV)

1. Exige sessão ABERTA e módulo PDV.
2. Itens de produto: baixa por `produto_id` na mesma transação (`estoque = estoque − qtd`). Estoque insuficiente → aviso; somente admin pode confirmar. Serviço não baixa estoque.
3. `bruto = Σ subtotal − desconto`; `taxa = round(bruto × pct/100, 2)` (arredondamento no total da venda); `liquido = bruto − taxa`, ou `liquido = bruto` se `repasse_taxa` (valor cobrado ao cliente = bruto + taxa); `data_liquidacao = data + dias`.
4. Crediário: taxa 0, sem troco; não altera `saldo_devedor`. Limite de crédito gera aviso (não bloqueia), como no original.
5. **Venda externa**: `liquido = max(0, bruto − (bruto × plataforma% + frete + desconto + motoboy))`; deduções gravadas em colunas próprias; `taxa` = soma das deduções; baixa de estoque opcional se ligada a produto.
6. **Cancelar venda**: só admin; na mesma transação estorna estoque dos itens, marca `cancelada`, registra auditoria. Nenhuma linha é apagada. Cancelar venda de parcela de contrato volta a parcela para PENDENTE.

### 4.2 Contrato/assinatura

Cria `contrato` e N `parcela_receber` com `vencimento = data_base + relativedelta(months=k)` (k = 0..N−1, sempre a partir da data base, nunca encadeado). A parcela 1 vira venda (tipo CONTRATO) imediatamente. Prazo de liquidação = dias da forma + tolerância.

### 4.3 Ativação de parcelas (job)

Na inicialização e diariamente às 00:05: para cada `parcela_receber` PENDENTE com `vencimento ≤ hoje`:
- se há sessão ABERTA → cria venda CONTRATO com `data_hora = vencimento`, na sessão aberta; marca ATIVADA e grava `venda_id`;
- se não há → nada; a abertura da próxima sessão dispara a ativação.

Idempotente (parcela ATIVADA nunca gera segunda venda).

### 4.4 Receber crediário

Cria venda tipo RECEBIMENTO (descrição "RECEBIMENTO DE CONTA / FIADO") com a forma real, taxa da configuração e troco calculado. `saldo_devedor` não muda automaticamente; a tela exibe lembrete com atalho para ajuste manual (auditado).

### 4.5 Sessão de caixa

- **Abrir**: fundo de troco (sugestão = `valor_mantido` da última sessão), gera protocolo, dispara ativação de parcelas pendentes.
- **Fechar** (transação única): resumo por forma (bruto, taxa, líquido), com EXTERNA e RECEBIMENTO em linhas separadas; gaveta = fundo + dinheiro; `sangria = gaveta − valor_mantido`; grava resumo JSON; status FECHADA. Nada é copiado nem apagado.

### 4.6 Entrada por NF-e

Parse do XML (ou do XML obtido pela chave de acesso — fonte a definir no plano do sub-projeto 2; fallback: só XML). Casamento item→produto por EAN, depois por código do fornecedor salvo em vínculo anterior; **nunca** por substring de descrição. Tela de conferência: itens sem par podem ser vinculados a produto existente ou criar produto novo. Ao confirmar: `estoque += qtd × fator` quando a nota vem em embalagem, `preco_entrada` = custo da nota, `data_ult_entrada` = data de entrada. Estorno: reverte pela `nota_entrada` (subtrai quantidades, restaura preço anterior guardado no item); nunca apaga produto.

`data_ult_entrada` é carimbada apenas no cadastro de produto e na entrada por nota; nunca em edição manual de quantidade.

### 4.7 Markup

- `rateio_pct` do mês = Σ contas (CONTA_FIXA + CONTA_VARIAVEL + SALARIO) com vencimento no mês ÷ receita bruta do mês (mesma regra de receita do DRE). Receita zero → rateio 0 com aviso.
- `rateio_rs = fracionado × rateio_pct`; `custo_real = fracionado + rateio_rs`.
- `preco = custo_real × (1 + markup_pct/100)`; editar preço → `markup_pct = (preco / custo_real − 1) × 100`. Editar qualquer um marca `markup_manual = True`.
- Reprocessamento em lote: produtos com `markup_manual = False` recebem o markup padrão (config, inicial 30%); manuais mantêm `markup_pct` e têm o preço recalculado com o custo atual. Grava `preco_venda` no produto.
- "Atualizar Preço" produto a produto, com preço promocional opcional; se houver promocional, é ele o preço usado no PDV.
- Um único rateio no sistema.

### 4.8 DRE

Período selecionável (mês padrão).

1. Receita Bruta = Σ `bruto` das vendas não canceladas no período (sessões abertas e fechadas), **excluindo tipo RECEBIMENTO**. Venda a prazo (crediário) entra. Parcelas não ativadas não são venda e não entram.
2. (−) Taxas = Σ `taxa`.
3. = Receita Líquida.
4. (−) CMV = Σ qtd × `preco_fracionado` **atual** do produto (itens com produto).
5. = Lucro Bruto.
6. (−) Despesas Operacionais = contas com **vencimento** no período, exceto EMPRESTIMO; BOLETO entra pelo valor integral.
7. (−) Despesas Financeiras = juros + taxa_boleto de contas com vencimento no período, mais juros das parcelas de empréstimo (o principal de empréstimo não é despesa).
8. = Lucro Líquido.

## 5. Painéis CFAUTO

### 5.1 Balancete (informativo; não força Ativo = Passivo + PL)

- **Ativo Circulante**: caixa físico (fundo + dinheiro da sessão aberta; sem sessão aberta, `valor_mantido` da última) + caixa virtual disponível (= Saldo Real de Caixa/Banco, abaixo) + mercadoria (Σ estoque × fracionado) + contas a receber (Σ saldo_devedor + vendas com `data_liquidacao > hoje` + parcelas PENDENTES).
- **Ativo Não Circulante**: Σ bens físicos.
- **Passivo**: contas PENDENTES agrupadas por `grupo_parcela_id` (descrição); Circulante = vencimento ≤ hoje + 1 ano (inclui vencidas e sem data); Não Circulante = demais.
- **Patrimônio Líquido**: capital social + lucros retidos (config, únicos valores digitados).
- **Saldo Real de Caixa/Banco** = Σ líquido virtual já liquidado (todo o histórico) + Σ empréstimos recebidos − Σ `valor_pago` de contas pagas (todo o histórico). Premissa: contas são pagas pelo banco.

### 5.2 Indicadores (período padrão: últimos 12 meses)

| Indicador | Fórmula | Sem dado |
|---|---|---|
| ROE | LL / PL | "N/A" se PL vazio ou 0 |
| ROA | LL / Ativo total | "N/A" se ativo 0 |
| Margem Bruta | LB / Receita Líquida | "N/A" se receita 0 |
| Margem Líquida | LL / Receita Líquida | "N/A" se receita 0 |
| Dívida Líquida | (EMPRESTIMO + BOLETO pendentes) − (caixa físico + virtual disponível) | — |
| Dívida/PL | Dívida Líquida / PL | "N/A" se PL vazio ou 0 |
| Passivo/Ativos | Passivo total / Ativo total | "N/A" se ativo 0 |
| CAGR Receita | (R_final / R_inicial)^(1/anos) − 1, anos civis fechados | "N/A" com < 2 anos |
| CAGR Lucro | idem com Lucro Líquido | "N/A" com < 2 anos ou lucro inicial ≤ 0 |

### 5.3 Curva ABC

Receita por produto (itens de vendas PRODUTO e EXTERNA ligadas a produto, não canceladas; exclui RECEBIMENTO e CONTRATO), ordenada decrescente, % acumulado. Classe A = itens até o que cruza 80% (inclusive); B = seguintes até o que cruza 95%; C = resto. Filtro mês/ano; gráfico de rosca por classe.

### 5.4 Comparador de Investimento

- CDI: API SGS do Banco Central, série 4391 (mensal), composta em 12 meses; fallback manual.
- BOVA11: brapi.dev; Dólar: AwesomeAPI (USD-BRL); preço atual × fechamento mais próximo de 1 ano atrás; cache em `config` com data; fallback manual.
- Poupança (taxa a.a.), CDB (% do CDI), Investimento Simples (taxa a.a.) configuráveis.
- Cartões (CDI, Poupança, CDB, Investimento Simples, BOVA11, Dólar) ativáveis individualmente; "melhor opção" considera todos os ativos.
- Gráfico de cotas: índice 100 no 1º mês com vendas; série mensal alinhada (meses sem venda repetem o valor anterior; mercado reamostrado para fim de mês); eixo rotulado "índice"; datas fora de hoje ± 10 anos descartadas; últimos 24 meses por padrão.

### 5.5 Alertas

Sino na barra superior: produto classe A/B com `estoque ≤ estoque_minimo`; margem líquida do mês corrente negativa; contas vencidas ou vencendo em ≤ 1 dia; licença expirando em ≤ 15 dias.

### 5.6 Estoque mínimo (job)

Semanal (segunda 06:00; catch-up se a última execução tem mais de 7 dias): média semanal de vendas por produto (últimas 8 semanas, por `produto_id`) × semanas de cobertura (A = 3, B = 2, C = 1). Produtos com `estoque_minimo` editado manualmente ficam marcados e não são sobrescritos.

### 5.7 Compras

Fornecedores cadastrados; exportar cotação em branco (.xlsx por fornecedor); importar preenchida (substitui o bloco do fornecedor na cotação, sem duplicar); comparação de menor preço e 2ª opção; sugestão de quantidade = `max(0, venda_semanal_media × semanas − estoque_atual)` ajustada pelo fator de preço limitado a [0,5; 2], com `venda_semanal_media` calculada do histórico; respeito ao pedido mínimo (opção de forçar); finalizar gera `pedido` por fornecedor e exporta texto do pedido. A entrada no estoque acontece depois, pela NF-e.

## 6. Segurança, licença, provisionamento, jobs

### 6.1 Provisionamento

- Banco em `%APPDATA%\CFAUTO\cfauto.db`.
- Na inicialização: se o banco não existe, cria via `alembic upgrade head` (migrations embutidas no executável); se existe e há migrations pendentes, faz backup e aplica.
- Primeira execução: wizard cria o admin, recebe a licença, dados da empresa e taxas (opcionais).
- Backup: diário e ao fechar o app, mantendo os 7 últimos, em `%APPDATA%\CFAUTO\backups`.

### 6.2 Autenticação e permissões

- argon2id (`argon2-cffi`). 5 tentativas falhas → bloqueio de 5 minutos. Logout manual; bloqueio de tela após inatividade (padrão 5 min; `seguranca.minutos_inatividade`).
- Permissão: flag `admin` ou lista de módulos (PDV, ESTOQUE, CLIENTES, SAIDAS, COMPRAS, HISTORICO). CFAUTO e USUARIOS são só-admin (`MODULOS_SO_ADMIN`): nunca liberados pela lista de módulos, nem na tela de usuários nem no serviço.
- Navegação: menu lateral retrátil (botão ☰) com os módulos do usuário. Os só-admin ficam fora dele, na seção **Configurações** (botão na barra superior, visível só para admin), com abas CFAUTO, Usuários, Auditoria e Parâmetros.
- **Parâmetros** (a detalhar): página de parametrização do sistema, hoje reservada. Candidatos: minutos de inatividade, markup padrão, taxas por forma de pagamento, capital social e lucros retidos, dias de aviso de licença.
- Ações só-admin: cancelar venda, estornar NF-e, editar markup/preço em lote, gerenciar usuários, editar config financeira, confirmar venda com estoque insuficiente, ver auditoria.
- Usuários importados com hash SHA-256 legado: aceito uma vez no login e regravado em argon2id.

### 6.3 Licença

- Formato: `base64url(payload_json) + "." + base64url(assinatura_ed25519)`; payload `{cliente, emitida, expira, maquina?}`.
- O app embute só a chave pública; `tools/gerar_licenca.py` assina com a privada, que fica fora do repositório e do build.
- Anti-relógio: `ultima_data_vista` só avança; se `hoje < ultima_data_vista − 1 dia`, bloqueia com "relógio do sistema inconsistente".
- Vínculo com máquina opcional (hash de nome da máquina + ID do volume).
- Licença vencida ou inválida: o app abre apenas na tela de licença; dados intactos.

### 6.4 Auditoria

Registrada (antes/depois em JSON) para: venda (criação, cancelamento), sessão (abrir, fechar), produto (preço, custo, estoque, markup), nota de entrada (entrada, estorno), conta a pagar (todas as operações), cliente (saldo devedor, limite), usuário (todas), config financeira. Tela de consulta com filtros, só admin.

### 6.5 Jobs

| Job | Agenda | Catch-up na inicialização |
|---|---|---|
| Ativar parcelas | diário 00:05 + abertura de sessão | sim |
| Estoque mínimo | segunda 06:00 | se última execução > 7 dias |
| Alertas | a cada 30 min | sim |
| Backup | diário + ao fechar | — |

Cada job grava a última execução em `config`.

### 6.6 Erros e logs

Nenhuma exceção é engolida retornando 0. Serviços lançam exceções de domínio tipadas (`PermissaoNegada`, `SessaoFechada`, `EstoqueInsuficiente`, `LicencaInvalida`, …); a UI mostra mensagem clara. Falha de API externa aparece como "usando valor manual de dd/mm/aaaa". Log rotativo em `%APPDATA%\CFAUTO\logs`.

## 7. Testes, empacotamento, entrega

### 7.1 Testes

- pytest; SQLite em memória com schema criado pelas migrations; `clock` fixo; fixtures de usuário admin e operador.
- Obrigatórios: markup bidirecional e lote preservando manual; DRE (ordem, exclusão de RECEBIMENTO, CMV pelo custo atual, despesa por vencimento, boleto integral, empréstimo só juros); ABC (cortes 80/95, produto dominante); parcelas (ativação, fila sem sessão, idempotência, vencimento de 31/01); taxa 0 respeitada; fechamento com resumo por forma; baixa e estorno de estoque; cancelamento de venda; licença (válida, vencida, adulterada, relógio atrasado); permissão negada no serviço; tabela Price conferida contra valores calculados à mão; importador com `.xlsx` de exemplo.
- UI: smoke test com `pytest-qt` (login, troca de módulo).
- Qualidade: `ruff`, `mypy` (modo leve), `pytest --cov`, via pre-commit.

### 7.2 Empacotamento

PyInstaller `--onefile --windowed` com ícone, migrations e assets, via `build.ps1`; validação em pasta limpa sem Python. Seed de demonstração (`cfauto.exe --demo` ou botão no wizard) com 2+ anos de histórico.

### 7.3 Stack

Python 3.12, PySide6, SQLAlchemy 2.x, Alembic, APScheduler 3.x, argon2-cffi, cryptography (Ed25519), openpyxl, matplotlib (`FigureCanvasQTAgg`), python-dateutil, httpx, pytest, pytest-qt, ruff, mypy, PyInstaller.

### 7.4 Sub-projetos (cada um: spec detalhada se necessário → plano → implementação)

1. **Fundação**: core, db + Alembic, auth + usuários, licença, provisionamento/wizard, janela principal com login e navegação, auditoria, esqueleto de jobs.
2. **Estoque**: produto, serviço, bens físicos, NF-e e estorno.
3. **Clientes**.
4. **Caixa/PDV**: sessão, vendas, externa, contrato + parcelas, recebimento, fechamento, histórico.
5. **Saídas**: contas, parcelamento, empréstimo, boleto, pagamento, dashboard.
6. **CFAUTO I**: markup, DRE, balancete, indicadores.
7. **CFAUTO II**: curva ABC, estoque mínimo, alertas, comparador.
8. **Compras**.
9. **Importador .xlsx**, seed de demonstração, empacotamento final.

~1 semana por sub-projeto + 1 de folga. Demo mínima (cadastro → venda → relatório) ao fim do 6.

## 8. Divergências intencionais em relação ao original

Referências de linha em `referencia/analise/*.md`.

| # | Original | Novo | Motivo |
|---|---|---|---|
| 1 | Ligações por número de linha (Markup↔Estoque, baixa de estoque, edição/pagamento de conta) | Tudo por ID | Bug de acoplamento posicional |
| 2 | Histórico = cópia de linhas do caixa, sem transação | Visão sobre sessões fechadas | Atomicidade, sem duplicação |
| 3 | Parcelas FUTURO ficam no caixa para sempre e nunca viram receita | `parcela_receber` + job de ativação | Regra do `.md` nunca implementada |
| 4 | `parseFloat(x) \|\| padrão` transforma taxa 0 em padrão | 0 é valor válido | Bug |
| 5 | Desconto calculado na tela e descartado | Desconto gravado | Bug |
| 6 | Excluir venda = `deleteRow` sem estorno nem log | Cancelamento com estorno + auditoria, só admin | Integridade |
| 7 | Venda externa grava só a soma das deduções | 4 deduções em colunas | `.md` |
| 8 | Serviço duplicado (Estoque e Markup) e não vendável | Cadastro único, vendável no PDV | `.md` + bug |
| 9 | Datas de parcela com `setMonth` encadeado (31/01 → 03/03) | `relativedelta` a partir da data base | Bug |
| 10 | Juros/taxa extraídos por regex da observação | Campos estruturados | `.md` |
| 11 | DRE: Boleto/Empréstimo só juros+taxa | Boleto integral; empréstimo só juros+taxa | Decisão do usuário |
| 12 | Rateio do Markup por data de registro; segundo rateio fixo de 10% | Um rateio, por vencimento | Coerência com DRE |
| 13 | Lote de markup nunca recalcula após 1ª vez | Flag `markup_manual` | Bug |
| 14 | Caixa virtual só da sessão aberta; Saldo Real inclui valores a cair | Por `data_liquidacao ≤ hoje`, todas as sessões | Correção contábil |
| 15 | Empréstimo recebido nunca entra no saldo | Entrada registrada | Correção contábil |
| 16 | Crediário a receber nunca diminui (compara forma "CREDIARIO") | Baseado em `saldo_devedor` | Bug |
| 17 | Dívida Líquida = Passivo − AC | Dívida financeira − caixa | Definição padrão |
| 18 | "CAGR de Lucro" = crescimento da receita líquida | Crescimento do Lucro Líquido | Definição correta |
| 19 | Valor de Firma | Removido | Fora do `.md`, definição duvidosa |
| 20 | ROE "—", ROA 0 sem denominador | "N/A" | `.md` |
| 21 | ABC: produto dominante (>80%) não fica em A | Item que cruza o corte pertence à classe | Bug |
| 22 | Comparador desalinha séries, eixo "%" | Série mensal alinhada, eixo "índice"; BOVA11/Dólar entram na melhor opção | Bug |
| 23 | Estoque mínimo casa por descrição | Por `produto_id` | Bug |
| 24 | NF-e/estorno/Compras casam por substring de nome; estorno apaga produto com estoque ≤ 0; PDF renomeia produto | EAN/código; nunca apaga | Bugs |
| 25 | Custo médio calculado e sobrescrito pelo último custo | Último custo (comportamento efetivo), explícito | Clareza |
| 26 | Parse de moeda remove pontos ("10.5" → 105) | Parser de moeda BR testado | Bug |
| 27 | Senha SHA-256 sem sal; permissão só abre link | argon2id; permissão verificada no serviço | Segurança |
| 28 | IDs `CLI-`/`SAI-` baseados em nº de linhas (repetem) | Sequência nunca reaproveitada | Bug |
| 29 | Contas pagas copiadas ao Histórico a cada edição | Sem cópia; consulta direta | Bug |
| 30 | Repetição mensal: só 1ª parcela recebe status escolhido | Status explícito por parcela | Clareza |
| 31 | Erros de leitura retornam 0 silenciosamente | Exceções tipadas + mensagem | Bug |
| 32 | Recebimento de fiado somado como venda no fechamento | Linha própria no resumo | Clareza |
| 33 | Compras: anti-duplicação apaga pedidos do dia do fornecedor; último preço = menor cotado; reimportar duplica bloco; venda semanal digitada | Pedido por ID; último preço = pedido real; reimportar substitui; média calculada | Bugs |
| 34 | Proteção por `onEdit` revertendo edições | Transações + permissões + auditoria | `.md` |
| 35 | Estoque inteiro em alguns pontos, fração em outros | `Numeric(12,3)` em todo lugar | Consistência |

## 9. Pendências a validar com o usuário

- Saldo devedor de crediário manual (original não incrementa na venda). Revisitar após o sub-projeto 4.
- Ordem física das colunas da aba CAIXA e se `VALOR` do Histórico é unitário ou total — confirmar com `.xlsx` reais antes do importador (sub-projeto 9).
- Fonte do XML a partir da chave de acesso da NF-e (sub-projeto 2).
