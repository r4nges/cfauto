# Análise de regras de negócio — 03-ADMINISTRATIVO.gs (CFAUTO) e 05-SAIDAS.gs (Contas a Pagar)

Fonte: `referencia/appsscript/03-ADMINISTRATIVO.gs` (2746 linhas) e `referencia/appsscript/05-SAIDAS.gs` (1526 linhas), lidos por inteiro.
Comparado com `prompt-claude-code-cfauto.md`. Citações no formato `arquivo:linha` (`03:` = 03-ADMINISTRATIVO.gs, `05:` = 05-SAIDAS.gs; outros arquivos aparecem com o nome).
Convenção: índice de array JS `row[n]` = coluna n+1 (row[0]=A, row[4]=E ...).

---

## 1. Layout de dados

### 1.1 Planilhas referenciadas (IDs)

| Constante / local | ID | Planilha | O que 03/05 leem ou escrevem |
|---|---|---|---|
| `ID_PLANILHA_ESTOQUE_MKP` `03:26` | `1aPr4-chXwNE19RWIXgOPceB-OmF31Ft5SgtugEPwoMA` | ESTOQUE (aba "ESTOQUE" ou a 1ª) | Lê A..M a partir da linha 6; **escreve** J (Preço de Venda) |
| `ID_PLANILHA_CAIXA_MKP` `03:27` | `1nBVAh4brJ6KiIgrokph58btEkdkydSlRwDbVBbPzCzA` | CAIXA (aba "CAIXA" ou a 1ª) | Lê linhas ≥7 e as células do painel F2 (dinheiro na gaveta) e J2 (entrada virtual) |
| `ID_PLANILHA_HISTORICO_MKP` `03:28` | `1119HW8n6Ma-H83wbLw9I13bTJ9EgJhhpciPFyyaUXI8` | HISTÓRICO (1ª aba) | Lê A..M a partir da linha 2 |
| `ID_PLANILHA_SAIDAS_MKP` `03:29` | `16PD_PSyOKStz2QCVuB66PbFlHdIl6EsbZtP34oB0BJY` | SAÍDAS (1ª aba) | Lê A..J a partir da linha 7 |
| literal `05:1089` | `1UtU74AmVxtfjupGB9BZkr6AdSjUCE9cQWKO7mU-m8gs` | USUÁRIOS (mesmo ID de `07-MENU.gs:6`) | 05 lê a coluna A (nomes) a partir da linha 7 da 1ª aba |
| URL literal `05:1320` e `05:1357` | HISTÓRICO `1119HW8n...`, aba **gid 568036251** | HISTÓRICO, aba de "contas pagas" | 05 **acrescenta** (appendRow) a linha inteira da conta quando ela é paga ou editada para PAGO |
| Planilha ativa do 03 | (CFAUTO/ADMINISTRATIVO, `07-MENU.gs:18` = `19qZGkj8...`) | abas "Markup", "Comparador" (oculta) | Markup (produtos, bens, serviços), Comparador (fórmulas GOOGLEFINANCE) |
| PropertiesService (DocumentProperties) do CFAUTO | — | — | `CAPITAL_SOCIAL`, `LUCROS_RETIDOS`, `CDI_MANUAL`, `POUPANCA_ANUAL`, `INVEST_SIMPLES_ANUAL`, `CDB_PERC_CDI`, `RENDA_FIXA_DESATIVADOS` (`03:831-832`, `03:2004-2019`, `03:2033-2047`) |

Observação: o 03 abre SAÍDAS e HISTÓRICO com `getSheets()[0]` (a **primeira** aba). O 05 usa a aba pelo nome `"SAÍDAS"` (`05:1130`, `obterOuCriarAba`). Se alguém reordenar as abas, o 03 passa a ler a aba errada.

### 1.2 ESTOQUE (como o 03 lê) — cabeçalho linha 5, dados a partir da linha 6
`03:168-171`, `03:188-189`, `03:296-310`, `03:571-575`, `03:1526-1530`

| Col | Significado |
|---|---|
| A | Código (EAN) |
| B | ID interno (chave do mapa de custo do CMV, `03:573`) |
| C | Descrição |
| D | Categoria |
| E | (não lido pelo 03; em `01-ESTOQUE.gs` é Modo/Embalagem) |
| F | (não lido pelo 03; Fator, `01-ESTOQUE.gs:630`) |
| G | Data de Entrada |
| H | Preço de Entrada (pacote) — só referência |
| I | **Preço Fracionado** (custo por unidade) — usado em Markup, CMV, valor do estoque |
| J | **Preço de Venda** — escrito pelo Markup |
| K | Estoque (quantidade) |
| L | Margem |
| M | Destino |

Serviços também moram no Estoque a partir da coluna N (`01-ESTOQUE.gs:1186`), e o 03 **tem um segundo cadastro de serviços** na aba Markup (ver 8.2).

### 1.3 CAIXA (caixa aberto) — dados a partir da linha 7, painel nas linhas 1-3
O `04-CAIXA.gs` localiza as colunas pelo **nome do cabeçalho da linha 6** (`04-CAIXA.gs:796-819`), mas o 03 usa **posições fixas**:

| Col (03) | Significado | Onde |
|---|---|---|
| B | ID do produto | `03:662`, `03:2182` |
| C | Descrição (`"RECEBIMENTO DE CONTA / FIADO"` = recebimento de crediário) | `03:132-133` |
| D | Categoria (`"Assinatura"`, `"CREDIARIO"` ...) | `03:2176` |
| E | Preço (valor bruto da linha) | `03:134`, `03:663` |
| F | Quantidade | `03:664` |
| G | Forma de pagamento | `03:1489` |
| I | Taxa (R$) | `03:665` |
| J | "Recebido" = **data** em que o dinheiro cai (texto dd/MM/yyyy ou Date) | `03:1495-1497` |
| K | Data/Hora da venda | `03:659`, `03:2179` |
| F2 | Painel: dinheiro na gaveta | `03:1470`, `03:2406` |
| J2 | Painel: entrada virtual do caixa aberto | `03:2407` |

A coluna H ("Liquidado em" = dias, ou `FUTURO`) não é lida pelo 03 no caixa aberto. **Não dá para confirmar** que a planilha real tem exatamente essa ordem, porque o Caixa se baseia em cabeçalhos; o 03 só funciona se a ordem física for essa.

### 1.4 HISTÓRICO — cabeçalho na linha 1, dados a partir da linha 2 (13 colunas)
Cabeçalho criado em `09-HISTORICO.gs` (fecharCaixaEArquivar): Horário, ID Sessão, Código de Barras, ID Produto, Descrição, Categoria, Preço Bruto, Quantidade, Pagamento, Liquidado Em, Taxa, Recebido Líquido, Cliente.

| Col | Significado | Uso no 03 |
|---|---|---|
| A | Data/hora | filtro de período (`03:109`, `03:628`) |
| B | ID sessão (protocolo) | — |
| C | EAN | — |
| D | ID produto | CMV e chave da Curva ABC (`03:631`, `03:2149`) |
| E | Descrição | `03:1545`, `03:2150` |
| F | Categoria (`"CREDIARIO"` para recebimentos, `"Assinatura"`) | exclusões (`03:117`, `03:637`, `03:2147`) |
| G | Preço bruto | receita (`03:118`, `03:633`) |
| H | Quantidade | CMV / ABC (`03:634`) |
| I | Forma de pagamento | `03:1546`, `03:2378` |
| J | Liquidado em (**dias**, ou `FUTURO`) | `03:1549`, `03:2381-2386` |
| K | Taxa | `03:635` |
| L | Recebido líquido | `03:897` ("lucroAprox"), `03:1548`, `03:2384` |
| M | Cliente | — |

### 1.5 SAÍDAS — cabeçalho implícito (linha 6, **nunca criado pelo código**), dados a partir da linha 7, 10 colunas
`05:1153`, `05:1171`, `05:1180`, `05:1185`, `05:1209-1220`

| Col | Significado | Formato gravado |
|---|---|---|
| A | ID `SAI-n`, n = linha − 6 (`05:1189`) | texto |
| B | Data de registro (hoje) | texto `dd/MM/yyyy` (`05:1133`) |
| C | Categoria (com acento: "Conta Variável", "Empréstimo", "Salário", "Pró-Labore") | texto |
| D | Descrição | texto |
| E | Valor (parcela) | número |
| F | Parcela `k/n` (ou `kª`) | texto |
| G | Vencimento | texto `dd/MM/yyyy` (o Sheets pode converter em Date sozinho, por isso o código trata os dois casos) |
| H | Status `PENDENTE` / `PAGO` | texto |
| I | Repetição `SIM` / `NAO` | texto |
| J | Observações (texto livre com "Amortização/Juros/Saldo", "Código", "Taxa Boleto", "Pago em") | texto |

### 1.6 Aba "Markup" (planilha CFAUTO) — cabeçalho linha 5, dados a partir da linha 6
`03:39-49`

| Bloco | Colunas | Conteúdo |
|---|---|---|
| Painel | K1:L3 | L1 Gastos do Mês, L2 Receita Bruta do Mês, L3 Rateio % (`03:159-161`) |
| Produtos | A..K | A Código, B ID, C Descrição, D Categoria, E Custo Compra (fracionado), F Rateio (R$), G Custo Real, H Markup %, I Preço Final, J Preço Promocional, K Data Entrada |
| Bens Físicos | N..Q (col 14-17) `03:1200` | Código `BEM-nnn`, "Descrição — Tipo", Valor, Data de Cadastro |
| Serviços | S..X (col 19-24) `03:2444` | Código `SERV-nnn`, Nome, Material, Custo Unit., Qtd, % Mão de Obra |

**A linha N da aba Markup corresponde à linha N do Estoque**: o alinhamento é por posição, não por ID (ver 11).

### 1.7 Aba "Comparador" (oculta, planilha CFAUTO)
`03:1802-1817`, `03:1911-1922`
- B1 `=GOOGLEFINANCE("BVMF:BOVA11")`
- B2 `=INDEX(GOOGLEFINANCE("BVMF:BOVA11","close",TODAY()-370,TODAY()-355),2,2)`
- B3 `=GOOGLEFINANCE("CURRENCY:USDBRL")`
- B4 `=INDEX(GOOGLEFINANCE("CURRENCY:USDBRL","close",TODAY()-370,TODAY()-355),2,2)`
- D2 e G2: séries mensais (`"MONTHLY"`) de BOVA11 e USDBRL, de `DATE(anoI,mesI,1)` até `DATE(anoF,mesF,28)`.

---

## 2. Markup

### 2.1 Gastos do mês (numerador do rateio) — `obterGastosDoMesSaidas` `03:57-92`
- Lê SAÍDAS linhas ≥7, colunas A..I.
- Categoria normalizada (sem acento, maiúscula) precisa **conter** uma destas: `"FIXA"`, `"VARIAVEL"`, `"SALARIO"`, `"SALARIOS"` (`03:61`, `03:74`). Na prática: Conta Fixa, Conta Variável, Salário. **Pró-Labore, Despesa Prevista/Imprevista, Boleto, Empréstimo e Outros Proventos ficam de fora.**
- Filtro: **Data de Registro (coluna B)** no mês/ano correntes (`03:70`, `03:82`). **Não** usa o vencimento, ao contrário do DRE.
- Não filtra status (soma PAGO e PENDENTE).
- Valor: `parseFloat(String(E).replace(/[^\d,.-]/g,'').replace(',', '.'))` (`03:72`).

### 2.2 Receita bruta do mês (denominador) — `obterReceitaDoMes` `03:97-142`
- HISTÓRICO: linhas com data (A) no mês/ano atual; exclui `F === "CREDIARIO"` (recebimentos de fiado); soma **G** (bruto) (`03:116-118`).
- CAIXA aberto: todas as linhas com descrição não vazia e que não contenham "RECEBIMENTO DE CONTA"; soma **E** (`03:132-134`). **Não há filtro de data nem de `FUTURO`**: todas as parcelas futuras de contrato de assinatura que estão no caixa aberto entram na receita "do mês".

### 2.3 Fórmulas — `atualizarMarkupCompleto` `03:148-226`
```
rateioPercentual = receitaMes > 0 ? gastosMes / receitaMes : 0          (03:158)
custoCompra      = Estoque!I (preço fracionado)                         (03:188)
rateio (R$)      = custoCompra × rateioPercentual                       (03:199)
custoReal        = custoCompra + rateio                                 (03:200)
markup           = markup antigo da linha (H) se não vazio, senão 30    (03:198)
precoFinal       = precoFinal antigo (I) se não vazio,
                   senão custoReal × (1 + markup/100)                   (03:204-206)
promocional      = promocional antigo (J) || ""                         (03:207)
Estoque!J        = promocional se ≠ "", senão precoFinal                (03:211, 03:218)
```
- O rateio é **percentual sobre o custo**, e o valor fica igual para todos os produtos: gastos/receita. O prompt fala em "aplicado proporcionalmente ao custo", o que é a mesma coisa.
- Markup padrão = **30%** (`03:198`).
- Linha sem código e sem descrição vira linha vazia na Markup e grava `""` no Estoque!J (`03:191-194`). **Isso apaga o preço de venda de linhas vazias do Estoque.**
- Ao final, um alert mostra os gastos, a receita e o rateio (`03:220-225`).

### 2.4 Preservação de markups manuais
- O mapa `dadosAntigosMap` é indexado pelo **número da linha** (`03:174-181`), e não pelo ID do produto.
- Na prática, qualquer Preço Final já existente é **sempre** preservado (`03:204-206`). Como a 1ª execução grava o Preço Final em todas as linhas, a partir da 2ª execução o lote **nunca mais recalcula preço** quando o custo ou o rateio mudam. Só as colunas E/F/G são atualizadas, e o Markup % em H fica inconsistente com o preço em I. Ver 11.

### 2.5 Bidirecional markup% ↔ preço — `onEdit` `03:232-261`
- Editar H (Markup %): `precoFinal = G × (1 + H/100)` e grava I (`03:242-245`).
- Editar I (Preço Final): `markup = G > 0 ? ((I/G) − 1) × 100 : 0`, arredondado a 2 casas, e grava H (`03:246-249`).
- Editar J (Promoção): envia a promoção para o Estoque, ou o preço final se a promoção ficar vazia ou não for numérica (`03:250-253`).
- Depois de editar H ou I: se J tem promoção numérica, envia J; senão envia o preço final (`03:259-260`).
- `empurrarPrecoParaEstoque(linha, valor)` grava `Estoque!J{linha}`, **na mesma linha física** (`03:263-271`).

### 2.6 Janela "Atualizar Preço" (produto a produto, promoção opcional) — `03:280-528`
- Lê **direto do Estoque** (A..J): código, descrição, H (pacote, só referência), I (fracionado), J (preço atual) (`03:289-318`). Produtos sem descrição são ignorados. A lista mostra no máximo 100 resultados (`03:457`), com busca sem acento em código + descrição (`03:441-446`).
- Campo **"Rateio %" digitado na janela, padrão 10** (`03:394`, `03:473`). **Não usa o rateio calculado em L3.**
- `custoComRateio = fracionado × (1 + rateio/100)` (`03:486`).
- Ao editar o preço: `markup = ((preco/custoComRateio) − 1) × 100`. Ao editar o markup ou o rateio: `preco = custoComRateio × (1 + markup/100)` (`03:489-499`). Ao abrir o produto, o markup é recalculado a partir do preço atual (`03:478`).
- Salvar (`salvarPrecoSimples` `03:324-359`): `Estoque!J = promo se numérica, senão preço` (`03:330-334`). Também sincroniza a linha correspondente da aba Markup: E = fracionado, F = fracionado × rateio%, G, H, I = preço, J = promo ou "" (`03:337-350`).

### 2.7 Write-back no Estoque
Só a coluna **J (Preço de Venda)** do Estoque é escrita, e sempre por número de linha (`03:218`, `03:267`, `03:334`). O Estoque recebe o **preço promocional** no lugar do preço cheio quando há promoção. O preço "cheio" existe só na aba Markup, coluna I.

---

## 3. DRE — `gerarDRE(mes, ano)` `03:598-716`

Filtro de período (`03:603-609`): mês e ano podem ser `"TODOS"`. **Uma linha com data não parseável (null) entra em qualquer período** (`03:604`).

| Linha | Fórmula / filtro exato |
|---|---|
| Receita Bruta | HISTÓRICO: soma G, filtrando por A no período e excluindo `F === "CREDIARIO"` (comparação exata e sensível a maiúsculas) (`03:628-639`). **+** CAIXA aberto: soma E, filtrando por K no período, excluindo descrição vazia e "RECEBIMENTO DE CONTA" (`03:656-667`) |
| (−) Taxas | HISTÓRICO K + CAIXA I, com os mesmos filtros (`03:640`, `03:668`) |
| (=) Receita Líquida | `receitaBruta − taxasVenda` (`03:707`) |
| (−) CMV | `Σ qtd × custoFracionadoAtual[id]`, com mapa `Estoque!B → Estoque!I` (`03:564-582`). Só soma quando o ID existe no Estoque (`03:641`, `03:669`). Serviços, venda externa sem produto e assinatura dão CMV 0 |
| (=) Lucro Bruto | `receitaLiquida − cmv` (`03:708`) |
| (−) Despesas Operacionais | SAÍDAS filtradas por **G = vencimento** no período (`03:689`). Categoria normalizada **igual a** uma de `CONTA FIXA, CONTA VARIAVEL, DESPESA PREVISTA, DESPESA IMPREVISTA, SALARIO, PRO-LABORE, OUTROS PROVENTOS` (`03:678`, `03:698`). Soma E. **Não filtra status** (PENDENTE também entra) |
| (−) Despesas Financeiras | Só categorias `BOLETO` e `EMPRESTIMO`: extrai do texto J os valores de `Juros: R$ x` e `Taxa Boleto: R$ x` com regex (`03:588-593`, `03:696-697`). **O principal (E) de Boleto e Empréstimo nunca entra no DRE** (a justificativa está em `03:548-551`) |
| (=) Lucro Líquido | `lucroBruto − despOper − despFin` (`03:709`) |
| Margem líquida | `receitaBruta > 0 ? lucroLiquido / receitaBruta : 0`, **sobre a receita bruta** (`03:710`) |

Notas:
- "Exceto Crediário" quer dizer excluir a linha de **recebimento de fiado** (categoria `CREDIARIO` / descrição "RECEBIMENTO DE CONTA"). A **venda feita no crediário** (pagamento = Crediário, categoria do produto) **entra** normalmente na receita, pelo regime de competência. O prompt dá a entender outra coisa (ver 10).
- No caixa aberto **não se filtram as linhas `FUTURO` nem `Assinatura`**. Com mês específico, a data K da parcela futura (a data da própria parcela, `04-CAIXA.gs:2083`, `04-CAIXA.gs:2181`) as coloca no mês certo. Com ano ou "TODOS", **todas as parcelas futuras do contrato entram**.
- CMV usa o custo **atual**, confirmado (`03:542-544`).
- UI: os filtros de ano são fixos, 2024-2027, com 2026 selecionado (`03:748-751`). O destaque "Pra cada R$1,00 vendido sobra R$ X" mostra `margemLiquida` formatada como R$ (`03:781-785`).

---

## 4. Balancete — `gerarBalancete` `03:1617-1635`

### 4.1 Ativo Circulante — `calcularAtivoCirculanteAutomatico` `03:1462-1574`
| Grupo | Fórmula |
|---|---|
| Caixa Físico | `parseFloat(Caixa!F2)` (`03:1470`). Com o caixa FECHADO, F2 contém o texto "FECHADO" e o valor vira 0 (`04-CAIXA.gs:64`) |
| Caixa Virtual | Caixa aberto, linhas com pagamento normalizado em {CREDITO, DEBITO, PIX, EXTERNA} e descrição sem "RECEBIMENTO DE CONTA", em que o **texto da coluna J (Recebido) == hoje (dd/MM/yyyy)**: soma E (**bruto**) (`03:1480-1500`) |
| Contas a Receber — Cartão a cair | (a) Caixa aberto: mesmas linhas com `J ≠ hoje`, soma E (bruto) (`03:1500`). **+** (b) HISTÓRICO: toda linha com pagamento ≠ CREDIARIO e A do tipo Date, em que `A + J dias (00:00) > hoje`: soma L (líquido), ou G se L for 0 (`03:1558-1563`). A parte (b) **não filtra forma de pagamento** e **só aceita A como Date** (texto é ignorado) |
| Contas a Receber — Crediário | Caixa aberto: pagamento == CREDIARIO → `+E`, ou `−E` se a descrição contém "RECEBIMENTO DE CONTA" (`03:1505-1515`). HISTÓRICO: pagamento (I) == CREDIARIO → `+G`, ou `−G` se a descrição (E) contém "RECEBIMENTO DE CONTA" (`03:1552-1556`). Depois `max(0, …)` (`03:1570`). **Ver bug 11.6: o desconto nunca acontece** |
| Mercadoria | `Σ Estoque!I × Estoque!K` em todas as linhas ≥6 (`03:1526-1531`) |
| **Ativo Circulante** | soma dos 5 (`03:1571`) |

"Já disponível" versus "a cair": no caixa aberto a regra compara a **data texto da coluna J com hoje**. No histórico compara `data + dias > hoje`. **O dinheiro virtual de caixas já fechados que já caiu não entra no Ativo Circulante** (não existe saldo bancário no ativo). Ele só aparece no bloco "Saldo Real" (4.4).

### 4.2 Ativo Não Circulante
`somarBensFisicos()` = Σ do valor dos bens (`03:1285-1287`). O Balancete agrupa por tipo em `bensPorTipo` (`03:1628-1629`).

### 4.3 Passivo — `calcularPassivoAutomatico` `03:1302-1344`
- Todas as linhas de SAÍDAS com `status.upper().trim() === "PENDENTE"`, de qualquer categoria (`03:1316-1317`).
- `umAnoDepois = hoje(00:00) + 365 dias` (`03:1305-1307`).
- Circulante quando **não há data de vencimento** ou quando `vencimento <= umAnoDepois`. Contas vencidas também contam como Circulante. Nos demais casos, Não Circulante (`03:1326-1329`).
- O detalhamento item a item é ordenado com `localeCompare` sobre a string `dd/MM/yyyy` (`03:1342`), o que dá **ordem errada** (ordena pelo dia).
- A UI agrupa por `categoria|descricao` e mostra o número de parcelas e "de X até Y" (`03:1693-1711`). Como o Boleto grava "desc (k/n)" (`05:1170`), **cada parcela de boleto vira um grupo próprio**. As datas do grupo são ordenadas como string dd/MM (`03:1704`).
- "Dívida paga no ano" (informativo): SAÍDAS com status PAGO, categoria BOLETO ou EMPRESTIMO e **ano do vencimento** igual ao ano atual (`03:1580-1610`). Não usa a data do pagamento.

### 4.4 Saldo Real de Caixa/Banco — `calcularSaldoRealCaixaEBanco` `03:2367-2433`
```
totalVirtualRecebidoHistorico = Σ HISTÓRICO onde I ∈ {CREDITO,DEBITO,PIX,EXTERNA}, J ≠ "FUTURO",
                                e (A + J dias) <= hoje  (ou A não parseável → entra)
                                valor = L || G                                         (03:2376-2396)
caixaVirtualAberto            = Caixa!J2 (inteiro, sem separar o que já caiu)          (03:2407)
totalSaidasPagas              = Σ SAÍDAS.E com status == "PAGO", qualquer categoria e data (03:2418-2423)
totalVirtualRecebido          = histórico + caixaVirtualAberto                         (03:2429)
saldoBancoDisponivel          = totalVirtualRecebido − totalSaidasPagas                 (03:2430)
dinheiroFisico                = Caixa!F2 (só exibido; não entra no saldo)              (03:2406)
```
- Sem filtro de período, como diz o prompt. Parte do princípio de que as contas são pagas pelo banco.
- Mistura critérios: o J2 do caixa aberto inclui o que "ainda vai cair" (o próprio `03:1472` admite isso), enquanto o histórico só considera o que já caiu. O J2 exclui `FUTURO` (`04-CAIXA.gs:83`).
- O dinheiro recebido de um empréstimo nunca é registrado como entrada, mas as parcelas pagas saem do saldo. Resultado: o saldo tende a ficar negativo.

### 4.5 Capital Social / Lucros Retidos
- São os únicos valores manuais. Ficam em DocumentProperties (`CAPITAL_SOCIAL`, `LUCROS_RETIDOS`), com `parseFloat || 0` (`03:829-851`).
- PL = soma dos dois (`03:1625`). A tela do Balancete tem inputs e o botão "Salvar PL" (`03:1657-1671`).
- Informativo: "Ativo Total − Passivo Total (referência pro Patrimônio)" (`03:1751`). Não existe fechamento A = P + PL, e isso é intencional (`03:1346-1351`).
- **Ativo Total** = AC + Bens. **Passivo Total** = PC + PNC (`03:1631-1632`).

---

## 5. Indicadores — `gerarIndicadores` `03:909-972`

Fontes: `obterDadosPatrimoniais()` (AC, bens, passivo, PL, `03:857-872`) e `gerarDRE("TODOS", anoAtual)`, ou seja, **o ano civil inteiro**, inclusive despesas com vencimento em meses futuros do ano (`03:913`).

| Indicador | Fórmula | Caso sem valor |
|---|---|---|
| ROE | `LL / PL` | `null` se `PL === 0` (a UI mostra **"—"**, não "N/A") (`03:918`, `03:1014`). PL negativo calcula normalmente |
| ROA | `LL / ativoTotal` | `0` se ativoTotal ≤ 0 (`03:919`) |
| Margem Bruta | `lucroBruto / receitaBruta` | 0 (`03:921`) |
| Margem Líquida | `dre.margemLiquida` = LL / **receita bruta** | 0 (`03:922`) |
| Dívida Líquida | `passivoTotal − ativoCirculante` (`03:924`). **Não é passivo − caixa**: desconta estoque e recebíveis | — |
| Dívida Bruta / PL | `passivoTotal / PL` | 0 se PL ≤ 0 (`03:925`) |
| Dívida Líquida / PL | `dividaLiquida / PL` | 0 se PL ≤ 0. **Calculado mas não exibido** (`03:926`) |
| Passivo / Ativos | `passivoTotal / ativoTotal` | 0 (`03:927`) |
| Valor de Firma (proxy) | `PL + dividaLiquida` (`03:929`) | — |
| CAGR Receita | anos distintos em HISTÓRICO!A (**sem** o filtro de datas implausíveis). Se houver ≥2 anos: `anoInicial = min`, `anoFinal = max`, `n = anoFinal − anoInicial`, e `(recFinal/recInicial)^(1/n) − 1`, com receita anual = Σ G excluindo `F === "CREDIARIO"` (`03:878-904`, `03:931-963`) | `null` se <2 anos ou receita inicial ≤ 0. A UI mostra "Precisa de 2+ anos" (`03:1082`) |
| CAGR "Lucro" (aprox.) | Mesma fórmula sobre `lucroAprox = Σ coluna L (Recebido Líquido)` (`03:897`, `03:958`). **Não é lucro**: é a receita líquida de taxas | `null` se lucroAprox inicial ≤ 0 |

Observações:
- `anoFinal` costuma ser o ano corrente, ainda incompleto, e é comparado com um ano inicial completo. Isso distorce o CAGR.
- Na tela de Indicadores, os rótulos do Passivo estão desatualizados: "Passivo Circulante (Boletos pendentes)" / "Não Circulante (Empréstimos pendentes)" (`03:1047-1048`). A regra real é o vencimento em até 1 ano, qualquer categoria.
- A tela de Indicadores **também repete** o DRE completo do ano e o Balancete completo (`03:1027-1050`).

---

## 6. Comparador de Investimento — `gerarComparadorInvestimento` `03:2058-2104` + evolução `03:1945-2001`

### 6.1 Cartões de mercado (valor pontual)
- BOVA11: `crescimento = atual / (close de ~1 ano atrás) − 1`, e `null` se o valor de 1 ano atrás for ≤ 0 (`03:2063-2069`). "~1 ano atrás" = **primeiro fechamento na janela de TODAY()−370 a TODAY()−355** (`03:1811`).
- Dólar: igual, com `CURRENCY:USDBRL` (`03:1813-1815`).
- Um `SpreadsheetApp.flush()` força o recálculo antes da leitura (`03:2060`).

### 6.2 CDI
- API do BCB SGS, **série 4391** (CDI mensal, % a.m.): `https://api.bcb.gov.br/dados/serie/bcdata.sgs.4391/dados/ultimos/12?formato=json` (`03:1827`).
- `cdiAnual = Π(1 + valor/100) − 1` sobre os 12 últimos meses (`03:1834-1839`).
- Qualquer falha (HTTP ≠ 200, lista vazia, exceção) devolve `null`, e o sistema usa `cdiManual/100` (`03:2073`). A fonte aparece no cartão: "Banco Central (automático)" / "Configurado manualmente" (`03:2074`).

### 6.3 Renda fixa configurável (DocumentProperties, `03:2003-2024`)
| Chave | Padrão | Uso |
|---|---|---|
| `CDI_MANUAL` | 10.5 (% a.a.) | fallback do CDI |
| `POUPANCA_ANUAL` | 6.17 | `poupanca = x/100` |
| `INVEST_SIMPLES_ANUAL` | 10 | `investSimples = x/100` ("Investimento Simples", um 4º cartão que **não aparece no prompt**) |
| `CDB_PERC_CDI` | 100 (% do CDI) | `cdb = cdiUsado × x/100` |

Leitura com `parseFloat(prop) || padrão`: **se o usuário salvar 0, o valor volta ao padrão**.

### 6.4 Cartões ativáveis
- 4 cartões: `cdi`, `poupanca`, `simples`, `cdb`. A lista dos desativados é guardada como JSON em `RENDA_FIXA_DESATIVADOS`, e o clique alterna (`03:2031-2052`, `03:1100-1103`).
- `melhorRendaFixa = max(ativos)`. **Se todos estiverem desligados, usa o max de todos** (`03:2083-2088`).
- BOVA11 e Dólar **não** entram na "melhor opção".
- Sugestão (`03:2090-2097`): se `crescimentoEmpresa` (= CAGR Receita) é null, mostra a mensagem de falta de 2 anos. Se é **maior** que o melhor, sugere "reinvestir no negócio"; senão, "proteger parte em renda fixa". Empate (`=`) cai em "menor".

### 6.5 Gráfico de evolução em cotas — `gerarEvolucaoComparativa` `03:1945-2001`
1. Meses com vendas: ano-mês de cada data do HISTÓRICO!A, descartando anos `< anoAtual − 10` ou `> anoAtual + 1` (`03:1857-1880`). Precisa de **≥2 meses** (`03:1947`). Usa só os **últimos 24** (`03:1952`).
2. Empresa: receita do mês (Σ G, exclui `CREDIARIO`, `03:1885-1905`), `índice = receita_mês / receita_1º_mês × 100` (base `|| 1`) (`03:1956-1958`). **Meses sem venda não aparecem**: a série tem buracos.
3. BOVA11 e Dólar: GOOGLEFINANCE mensal do 1º ao último mês. Lê `n+3` linhas, fica só com as linhas cuja 1ª coluna é Date e indexa pela 1ª (`03:1961-1974`). **Só entram no gráfico se o número de pontos for igual ao número de meses da empresa** (`03:1997-1998`). Com buracos na série da empresa, ficam de fora.
4. CDI: `obterCDIMensal(n)` pega os **últimos n meses até hoje**, que não são os mesmos meses da empresa. O índice começa em 100 e multiplica por `(1+cdi[i])` para i ≥ 1 (`03:1977-1986`).
5. Rótulos "Jan/25" (`03:1988-1992`). O eixo Y do gráfico mostra `v + '%'`, embora os valores sejam pontos de índice (`03:1151`).

---

## 7. Curva ABC — `gerarCurvaABC(mes, ano)` `03:2124-2224`

- Período: mesmo `dentroDoPeriodo` do DRE; data nula entra (`03:2127-2133`).
- HISTÓRICO: exclui `F === "CREDIARIO"` ou `F === "Assinatura"` (exato, sensível a maiúsculas) e linhas sem descrição (`03:2146-2153`).
- CAIXA aberto: exclui descrição vazia ou "RECEBIMENTO DE CONTA" e `D === "Assinatura"`, e filtra por K (`03:2173-2180`).
- **Agrupamento**: chave `id || desc`, ou seja, o ID do produto e, sem ID, a descrição (`03:2155`, `03:2186`). Soma receita (G/E, bruto) e qtd (H/F). A descrição e a categoria vêm da 1ª ocorrência.
- Venda Externa, serviços e vendas pagas no crediário **entram**: só "Assinatura" e recebimento de fiado saem. Não é estritamente "produto físico".
- Ordena por receita decrescente. Para cada item, `pctAcumulado = acumulado_incluindo_o_item / total` (`03:2203-2206`):
  - `<= 0.80` → **A**; `<= 0.95` → **B**; senão **C** (`03:2208-2210`).
  - Consequência: o item que "atravessa" os 80% vai para B. Se um único produto tem mais de 80% da receita, ele **não é A** (com 100% vira C).
- Resumo por classe: quantidade de produtos e receita (`03:2220-2221`). Sem vendas no período, devolve o erro "Nenhuma venda de produto encontrada nesse período." (`03:2199-2201`).
- UI: filtro Mês/Ano (anos fixos 2024-2027), rosca por classe (A verde, B âmbar, C cinza) e tabela com Produto, Qtd, Receita, % Receita, % Acumulado e Classe (`03:2255-2347`).

---

## 8. Bens Físicos (e Serviços no CFAUTO)

### 8.1 Bens — `03:1192-1287`, UI `03:1353-1435`
- Moram na aba Markup, colunas N..Q, a partir da linha 6. O cabeçalho é criado automaticamente na 1ª inclusão (`03:1251-1253`).
- Campos: descrição (obrigatória), tipo ∈ {**Móvel**, **Intangível**, **Outros**}, valor (obrigatório) (`03:1372-1381`, `03:1414`).
- Gravação: `[codigo, desc + " — " + tipo, valor, hoje "dd/MM/yyyy"]`. Descrição e tipo vão **concatenados** numa célula e são separados de novo por `" — "` na leitura (`03:1264`, `03:1230-1231`). Tipo ausente vira "Outros".
- Código: `BEM-` + (maior número existente + 1), com 3 dígitos (`03:1235-1243`). Ao excluir o último, o código é reutilizado.
- A linha livre é a primeira em que a coluna N está vazia a partir da linha 6 (`03:1260-1261`).
- Exclusão: `clearContent` das 4 células, sem deleteRow (`03:1273-1283`). Deixa buracos.
- Não há edição, depreciação nem data de aquisição (a data gravada é a do cadastro).
- Alimentam o Ativo Não Circulante (Σ valor) e o `bensPorTipo`.

### 8.2 Serviços na aba Markup (colunas S..X) — `03:2436-2747`
- Uma linha por material: `[SERV-nnn, nome, material, custoUnit, qtd, %MO]` (`03:2542-2544`). `qtd` usa `parseFloat || 1`, então **qtd 0 vira 1**. `%MO` é repetido em cada linha e, no agrupamento, vale o da 1ª linha (`03:2497-2499`).
- `totalMateriais = Σ custoUnit × qtd`, `valorMaoObra = totalMateriais × %MO/100` e `precoFinal = totalMateriais + valorMaoObra` (`03:2508-2513`). A UI sugere %MO = 50 (`03:2603`) e exige custo > 0 por material (`03:2641`).
- Exclusão: limpa todas as linhas com o código (`03:2554-2571`). Não há edição.
- **Existe um cadastro de serviços duplicado** em `01-ESTOQUE.gs:1182-1290` (Estoque, colunas N..S). O prompt cita só o do Estoque.

---

## 9. SAÍDAS (Contas a Pagar) — 05-SAIDAS.gs

### 9.1 Menu — `05:8-18`
Novo Lançamento, Buscar, Editar, Excluir, Dashboard e Pagar Boleto (que na verdade paga qualquer dívida pendente).

### 9.2 Categorias — `05:62-72`
Conta Fixa, Conta Variável, Despesa Prevista, Despesa Imprevista, Boleto, Empréstimo, Salário, Pró-Labore, Outros Proventos ("Outros (Bonificação / Extras)"). São gravadas com o rótulo acentuado, exatamente como no `<option value>`.

### 9.3 Formulário e validação — `05:209-246`
- Descrição é obrigatória.
- Boleto: todas as parcelas precisam de valor > 0.
- Empréstimo: `empTotal > 0`.
- Demais categorias: data inicial preenchida e valor > 0.
- Campos que aparecem ou somem conforme a categoria (`05:229-246`):
  - Boleto: esconde valor, repetição e datas; mostra código de barras e N parcelas (1-72) com data, valor e taxa por parcela.
  - Empréstimo: esconde valor, repetição e data final; mostra total, tipo de juros (TOTAL/MES), taxa e nº de parcelas.
  - Salário/Pró-Labore/Outros Proventos: esconde repetição e data final; mostra o seletor de colaborador.
- Parse de moeda (cliente): remove tudo que não é `[0-9,-]` e troca a vírgula por ponto (`05:144`). "1.234,56" vira 1234.56.

### 9.4 Geração de registros — `salvarSaidaModalScript` `05:1129-1191`
Em todos os casos: B = data de hoje, status da **1ª** parcela = status escolhido, **demais = "PENDENTE"**.

**Empréstimo** (`05:1141-1155`), com P = total, n = parcelas, taxa em %:
- `TOTAL`: `pmt = P(1 + taxa/100)/n`; `juros_k = pmt − P/n`; `amort_k = P/n`.
- `MES` (Price): `i = taxa/100`, `pmt = P·i(1+i)^n / ((1+i)^n − 1)` (ou `P/n` se i = 0); `juros_k = saldo·i`; `amort_k = pmt − juros_k`.
- `saldo = k == n ? 0 : max(0, saldo − amort_k)`.
- Linha: `["", hoje, "Empréstimo", desc, pmt, "k/n", venc, status, "SIM", "Amortização: R$ X | Juros: R$ Y | Saldo: R$ Z"]`.
- Vencimento = data inicial, com `+1 mês` por parcela via `setMonth` (`05:1154`). `pmt` não é arredondado.

**Boleto** (`05:1156-1172`), para cada parcela k de total:
- valor gravado = **valor + taxa do boleto** (`05:1164`);
- descrição = `desc (k/total)` quando total > 1;
- obs = `"Código: <barras>"` + `" | Taxa Boleto: R$ x"` quando taxa > 0;
- repetição = "SIM" sempre, mesmo com 1 parcela;
- vencimento = data informada na parcela.
- **Não há juros de boleto**. O pagamento não pede juros nem multa.

**Repetição mensal** (`repeticao === "SIM"` e dataFinal preenchida, `05:1173-1182`):
- `totalMeses = (anoF − anoI)*12 + (mesF − mesI) + 1`;
- gera enquanto `dt <= dataFinal`, somando 1 mês com `setMonth`;
- parcela = `k/totalMeses` (ou `kª` se totalMeses ≤ 0);
- valor igual em todas, obs = código de boleto (normalmente vazio).

**Simples**: 1 linha, parcela `"1/1"`, repetição conforme o select (pode ficar "SIM" com 1 linha só se não houver data final) (`05:1183-1186`).

**ID**: `SAI-(linha − 6)` (`05:1188-1189`). Grava `setValues` a partir de `max(7, lastRow+1)`.

**Salário / Pró-Labore / Outros Proventos** (`05:1088-1123`, `05:171-182`):
- lista os nomes da coluna A (linha ≥7) da planilha USUÁRIOS;
- ID `USR-n` por posição;
- `salarioBase` **sempre 0**, então o valor nunca é preenchido automaticamente;
- a descrição é preenchida como `"<Categoria> - <Nome>"`;
- **`idUsuario` é enviado mas não é gravado** (`05:294` vs. `05:1185`);
- vira um lançamento simples, sem repetição.

### 9.5 Pagar dívida — `05:927-1072`, `05:1227-1339`
- Lista as linhas com ID preenchido e status que não contém "PAGO", ordenadas por vencimento. Linhas sem data ficam no topo (timestamp 0) (`05:1239-1298`).
- Semáforo: `dias = ceil((venc − hoje)/1 dia)`.
  - `< 0` → vermelho, "VENCIDO há N dia(s)";
  - `0..1` → laranja, "Vence HOJE" / "Vence AMANHÃ";
  - `2..9` → amarelo, "Vence em N dias";
  - `≥ 10` → verde, "Prazo de N dias" (`05:1257-1276`).
- Confirmar (`05:1302-1339`):
  - H = "PAGO";
  - J recebe `" | Pago em: dd/MM/yyyy"` (data escolhida, padrão hoje);
  - **copia a linha inteira** para a aba de gid 568036251 da planilha HISTÓRICO (appendRow), num try/catch silencioso.
- **Não há campo para juros/multa de atraso, valor efetivamente pago nem conta de origem.** A "data de pagamento" existe só como texto na obs.

### 9.6 Status
Só `PENDENTE` e `PAGO`. "Vencida" é derivado: não pago e vencimento < hoje, e só aparece no dashboard e no semáforo. A tela de busca mostra "EM ABERTO" para tudo que não contém "PAGO" (`05:426-430`).

### 9.7 Buscar / Editar / Excluir
- Buscar: filtra por ID, descrição ou categoria. A lista vem invertida, mais recentes primeiro (`05:1193-1225`, `05:400-408`).
- Editar (`05:1341-1377`):
  - altera C, D, E, G (vencimento como **texto livre** "DD/MM/AAAA"), H e J (obs livre);
  - não altera parcela, repetição nem data de registro;
  - **não propaga para as outras parcelas** do mesmo lançamento;
  - se o status salvo é PAGO, **copia de novo** a linha para o HISTÓRICO gid 568036251, a cada salvamento (duplicação).
- Excluir: `deleteRow` de uma única linha (`05:1379-1385`). Não há exclusão em grupo das parcelas.
- Todas as operações identificam o registro pelo **número da linha** capturado quando o modal abriu.

### 9.8 Dashboard — `obterDadosDashboard` `05:1387-1527`
- Filtro por mês/ano do **vencimento**. Linhas sem vencimento parseável entram sempre (`05:1415-1420`). Os anos disponíveis vêm dos vencimentos, em ordem decrescente (`05:1513-1514`).
- KPIs:
  - `totalGeral` = Σ E;
  - `totalQuitadas` = Σ E com status contendo PAGO;
  - `totalVencidas` = não pago e venc < hoje;
  - `totalAtivas` = não pago e venc ≥ hoje ou sem data;
  - `totalJurosTaxas` = regex `Taxa Boleto: R$ x` + `Juros: R$ x` na obs de **qualquer** categoria e status (`05:1427-1442`).
- Gráficos:
  - rosca por categoria (Σ E, com %);
  - barras "Contas Fixas" por mês de vencimento (`cat === "Conta Fixa"` exato);
  - "Curva de Amortização": `saldo = totalGeral − Σacumulado(totalMes)` por mês de vencimento (`05:1492-1504`). Ignora se foi pago: é só o cronograma, não o saldo devedor real;
  - "Crescimento da Dívida": barras de `totalMes` por mês de **vencimento** (e não de registro, apesar do nome "Novas Dívidas no Mês") mais a linha acumulada.
- "Total Pago no Período" filtra pelo **vencimento**, não pela data do pagamento.

---

## 10. Divergências e omissões em relação ao `prompt-claude-code-cfauto.md`

1. **Data do rateio no Markup**: o prompt só diz "gastos do mês". O original filtra pela **data de registro** (`03:82`), enquanto o DRE usa o vencimento. Uma conta fixa de 12x cadastrada hoje joga as 12 parcelas no rateio deste mês. Recomendação: usar o vencimento, como no DRE.
2. **Receita do mês do rateio**: inclui o caixa aberto **sem filtro de data nem de FUTURO** (`03:129-136`). O prompt não menciona.
3. **Rateio da janela "Atualizar Preço"**: é um campo manual com padrão 10%, que **ignora** o rateio calculado (L3) (`03:394`, `03:486`). O prompt descreve um único rateio calculado.
4. **Markup padrão 30%** (`03:198`): não está no prompt.
5. **Promoção substitui o preço no Estoque** (`03:211`): o prompt diz "preço promocional opcional" mas não explica que é ele que vai para o preço de venda do produto. O preço cheio fica só no Markup.
6. **"Receita Bruta exceto Crediário"**: o original exclui só o **recebimento de fiado** (categoria `CREDIARIO` / "RECEBIMENTO DE CONTA"). A venda feita no crediário **conta** como receita. A frase do prompt pode ser lida como "excluir vendas no crediário", o que estaria errado.
7. **Despesas Operacionais do DRE**: a lista exata é Conta Fixa, Conta Variável, Despesa Prevista, Despesa Imprevista, Salário, Pró-Labore e Outros Proventos, **independente do status**. Boleto e Empréstimo entram **só com juros/taxa**; o principal nunca entra (`03:696-700`). O prompt não detalha isso.
8. **Margem líquida sobre a receita bruta** (`03:710`), não sobre a receita líquida.
9. **CMV = 0** para serviços, venda externa sem vínculo e assinatura (ID fora do Estoque). O prompt não diz.
10. **Ativo Circulante / "Caixa Virtual já disponível"**: só conta a venda virtual **do caixa aberto que liquida hoje** (bruto). O dinheiro virtual de caixas anteriores que já caiu **não está no ativo**, só no "Saldo Real". O prompt dá a entender que "Caixa Virtual" é o saldo disponível.
11. **Passivo**: vencidas e sem data contam como Circulante. O prompt não diz. Agrupamento na UI por `categoria|descrição`.
12. **Dívida Líquida = Passivo Total − Ativo Circulante** (`03:924`), definição não usual. O prompt só dá o nome.
13. **Indicadores extras** que não estão no prompt: **Valor de Firma (proxy) = PL + Dívida Líquida**, Dívida Líquida/PL (calculado e não exibido) e "Dívida paga no ano" no Balancete.
14. **"CAGR de Lucro"** é na verdade o CAGR da soma de "Recebido Líquido" (coluna L), **não do lucro** (`03:897`).
15. **ROE** mostra "—", não o texto "N/A" (`03:1014`). ROA, margens e índices de dívida mostram 0 quando o denominador é 0, sem N/A.
16. **Os Indicadores usam o DRE do ano civil inteiro** (`03:913`), inclusive despesas com vencimento em meses futuros.
17. **Comparador**:
    - são **4 cartões de renda fixa**: CDI, Poupança, **Investimento Simples (10% a.a.)** e CDB. O prompt fala em "Poupança e CDB" e não cita o Investimento Simples;
    - CDB é configurado como **% do CDI** (padrão 100), não como taxa própria;
    - padrões: CDI manual 10,5, poupança 6,17, simples 10;
    - série BCB = **4391** (CDI mensal composto em 12 meses);
    - "1 ano atrás" = janela de 370 a 355 dias;
    - a sugestão compara **só com a renda fixa ativa**; BOVA11 e Dólar não entram;
    - com tudo desligado, usa o máximo de todos;
    - gráfico: **últimos 24 meses**, filtro de plausibilidade `[anoAtual−10, anoAtual+1]`, e ao menos 2 meses.
18. **Curva ABC** exclui também **"Assinatura"** (o prompt cita "Crediário e Assinatura", ok). Mas **inclui** serviços e venda externa, e o item que cruza 80% vai para B.
19. **Bens**: o tipo é guardado junto com a descrição; a data é a de cadastro; não há edição. O prompt está alinhado com isso, exceto por não citar a exclusão.
20. **Serviços**: há **dois cadastros** (Estoque N+ em `01-ESTOQUE.gs:1186` e Markup S+ em `03:2444`). O prompt cita só o do Estoque. A regra de preço é idêntica.
21. **SAÍDAS — funcionalidades que o prompt não menciona**:
    - Empréstimo com cálculo de parcela (juros TOTAL simples ou tabela Price mensal), gravando amortização/juros/saldo por parcela (`05:1141-1155`);
    - Boleto com N parcelas (até 72) de datas, valores e taxas independentes, código de barras, valor gravado = valor + taxa (`05:1156-1172`);
    - só a 1ª parcela recebe o status escolhido, as demais nascem PENDENTE;
    - integração com a planilha de **Usuários** para Salário/Pró-Labore/Outros (descrição automática "Categoria - Nome");
    - **cópia da conta paga para uma aba do HISTÓRICO** (gid 568036251) ao pagar ou editar para PAGO;
    - "Pago em: data" registrado na observação;
    - semáforo de vencimento (vermelho/laranja/amarelo/verde, com cortes 0, 1 e 9 dias);
    - Dashboard com 5 KPIs e 4 gráficos (9.8).
22. **"Juros" e "Taxa de boleto"**: o prompt quer campos estruturados, o que está certo. Mas no original os **juros só existem no Empréstimo** (calculados no cadastro) e a **taxa só no Boleto** (no cadastro). **Pagar uma conta não registra juros nem multa.** No modelo novo, prever também `juros_pagos` / `multa` / `data_pagamento` / `valor_pago` no pagamento, e `amortizacao` / `saldo_devedor` no empréstimo.
23. **Saldo Real**: usa o **J2 inteiro do caixa aberto** (inclui o que ainda vai cair) e o valor **líquido** (L) do histórico. O prompt não especifica.
24. **Leitura de categorias no 03**: o DRE compara por **igualdade** normalizada; o Markup compara por **substring** ("FIXA", "VARIAVEL", "SALARIO"). No modelo novo, usar um enum.

---

## 11. Bugs, gambiarras e pontos frágeis (não repetir)

1. **Acoplamento por número de linha entre Markup e Estoque** (`03:174-181`, `03:263-267`, `03:334-349`). Markups preservados, push de preço e sincronização usam o índice da linha. Inserir, excluir ou ordenar linhas no Estoque transfere markups e preços para o produto errado. É o mesmo tipo de bug citado no prompt. Chavear por ID do produto.
2. **O lote de Markup nunca mais recalcula preço** (`03:204-206`): qualquer Preço Final existente é tratado como "manual". Guardar uma flag `preco_manual` (ou guardar o markup e derivar o preço), para que o reprocessamento respeite só os manuais de verdade.
3. **Linhas vazias apagam o preço no Estoque** (`03:191-194`, `03:218`), porque o lote grava `""` em J.
4. **`onEdit` simples chamando `openById`** (`03:232`, `03:265`): gatilhos simples não têm autorização para abrir outra planilha. O push para o Estoque falha em silêncio, só com Logger, a menos que haja um gatilho instalável. Não é possível confirmar pelo código qual dos dois está configurado.
5. **Dois rateios diferentes** (L3 calculado vs. 10% digitado na janela), e a janela sobrescreve F/G/H da aba Markup com o rateio digitado.
6. **Crediário a receber nunca diminui (provável)**: o recebimento de fiado é gravado com categoria `CREDIARIO` e **pagamento = forma usada pelo cliente** (Dinheiro/PIX/...) (`04-CAIXA.gs:360-370`). O Balancete só desconta quando `pagamento == CREDIARIO` **e** a descrição contém "RECEBIMENTO" (`03:1510-1512`, `03:1552-1553`), combinação que não ocorre. No histórico, o recebimento ainda cai no ramo "cartão a cair" se `dias > 0`. No modelo novo, relacionar o recebimento com a venda a prazo e o cliente.
7. **Linhas FUTURO/Assinatura não filtradas** no DRE (caixa aberto), no rateio do Markup e no Ativo Circulante. No DRE anual/TODOS, contratos futuros inflam a receita.
8. **Mistura de bruto e líquido**: Caixa Virtual e Cartão a cair do caixa aberto usam E (bruto); o histórico usa L (líquido); o Saldo Real usa J2 + L.
9. **Data nula = entra em todos os períodos** (`03:604`, `03:2128`, `05:1415`). Uma data corrompida polui qualquer filtro. Rejeitar na borda.
10. **Datas texto vs. Date** tratadas de formas diferentes em cada função:
    - `03:1550` aceita só Date;
    - `03:1599-1601` faz `split('/')` sem remover a hora;
    - a ordenação é feita sobre strings dd/MM/yyyy (`03:1342`, `03:1704`).
11. **`setMonth(+1)` com dias 29 a 31**: 31/01 + 1 mês vira 03/03 e o erro se acumula nas parcelas seguintes (`05:1154`, `05:1181`). `totalMeses` também pode não bater com o número de linhas geradas (rótulo "1/2" com 1 linha só). Usar `relativedelta` com clamp no último dia do mês.
12. **ID `SAI-(linha−6)`** (`05:1189`): depois de `deleteRow`, novos registros **repetem IDs existentes**. Usar PK autoincremento ou UUID.
13. **Operações por número de linha** capturado ao abrir o modal (editar, excluir, pagar): condição de corrida, ou seja, se a planilha mudar entre abrir e confirmar, a ação atinge a linha errada.
14. **Parcelas sem vínculo**: não existe "grupo/lançamento pai". Editar ou excluir não afeta as irmãs, e o passivo agrupa por texto de descrição, que falha em boletos com o sufixo "(k/n)". Modelar `lancamento` 1-N `parcela`.
15. **Juros e taxas em texto livre com regex** (`03:588-593`, `05:1429-1442`), e a obs é **editável livremente** no modal de edição (`05:500`). Um "Pago em" ou uma edição manual pode quebrar ou duplicar valores. O prompt já pede campos estruturados.
16. **Cópia duplicada para o HISTÓRICO** a cada edição com status PAGO (`05:1356-1374`). Também não há remoção se a conta voltar para PENDENTE.
17. **`parseFloat(x) || padrão`** nas configurações do comparador (`03:2006-2009`): 0 vira o padrão. Também em `qtd || 1` (`03:2543`).
18. **Série do gráfico de cotas desalinhada**: meses da empresa com buracos vs. mercado contínuo vs. CDI dos "últimos n meses até hoje". O eixo Y mostra "%" para pontos de índice. Se o 1º mês tiver receita 0, base = 1 (`03:1957`). Construir um calendário mensal contínuo e alinhar todas as séries por ano-mês.
19. **CAGR sem filtro de plausibilidade e com ano corrente incompleto** (`03:936-958`), e "CAGR Lucro" que não é lucro.
20. **Curva ABC com corte "inclusivo"**: o item que ultrapassa 80% vai para B, e um único produto dominante não é A. Recomendação: classificar pelo acumulado **anterior** ao item (`acum_antes < 0.80` → A), ou documentar a regra escolhida e testá-la.
21. **Ordem física das colunas do Caixa assumida no 03** (E, G, I, J, K), enquanto o 04 usa mapeamento por cabeçalho. É acoplamento posicional entre módulos.
22. **`getSheets()[0]`** para SAÍDAS e HISTÓRICO no 03, contra aba por nome no 05.
23. **Erros engolidos**: todo bloco de leitura faz `try/catch` com `Logger.log` e devolve 0. Uma planilha inacessível gera um DRE ou Balancete "zerado" sem aviso ao usuário.
24. **Rótulos de UI desatualizados** (Passivo "Boletos/Empréstimos" em `03:1047-1048`), comentário de layout da Markup desatualizado (`03:18-21` vs. `03:47-49`) e anos fixos 2024-2027 nos filtros.
25. **Empréstimo não registra a entrada do dinheiro**: só as parcelas como saída. O Saldo Real fica subestimado.
26. **Colaborador não é persistido** (`idUsuario` descartado) e `salarioBase` é sempre 0: o vínculo com Usuário é só cosmético.
27. **Exclusão de bens/serviços com `clearContent`** deixa buracos e reutiliza o código do último item excluído (`03:1235-1243`, `03:2464-2477`).
28. **Parse de moeda do 03 em `obterGastosDoMesSaidas`** (`03:72`): se E vier como texto "1.234,56", vira `"1.234.56"` e o resultado é 1.234. Nos outros pontos é `parseFloat(row[4])` direto, que falha com texto em formato BR.
