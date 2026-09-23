# Análise de regras de negócio — CAIXA (04), CLIENTES (08), HISTÓRICO (09)

Fonte: `referencia/appsscript/04-CAIXA.gs` (2674 linhas), `08-CLIENTES.gs` (857), `09-HISTORICO.gs` (130), lidos por inteiro.
Consultas pontuais a outros arquivos (`03-ADMINISTRATIVO.gs`, `07-MENU.gs`) só para esclarecer como os dados do Caixa/Histórico são consumidos.
Comparação feita com `prompt-claude-code-cfauto.md`.

Legenda: **[FATO]** = está no código; **[INFERÊNCIA]** = dedução, não confirmada no código; **[AMBÍGUO]** = o código não deixa claro.

---

## 0. Visão geral da topologia

Cada módulo é uma planilha Google separada, com seu próprio projeto Apps Script. As planilhas se falam por `openById`.

| Planilha | ID | Quem referencia |
|---|---|---|
| ESTOQUE | `1aPr4-chXwNE19RWIXgOPceB-OmF31Ft5SgtugEPwoMA` | `04-CAIXA.gs:5` (padrão, pode ser trocado pela property `ID_PLANILHA_ESTOQUE`, `04-CAIXA.gs:612`) |
| CLIENTES | `1WrD5GmVXteevylzXZphNMQlcZEkgpxmogbZicK8Gq78` | `04-CAIXA.gs:6` |
| HISTÓRICO | `1119HW8n6Ma-H83wbLw9I13bTJ9EgJhhpciPFyyaUXI8` | `04-CAIXA.gs:7` |
| CAIXA (a própria) | `1nBVAh4brJ6KiIgrokph58btEkdkydSlRwDbVBbPzCzA` | `07-MENU.gs:11` |
| USUÁRIOS | `1UtU74AmVxtfjupGB9BZkr6AdSjUCE9cQWKO7mU-m8gs` | `07-MENU.gs:6` |

Pra que o Caixa abre cada uma:
- **ESTOQUE**: lista de produtos pro PDV (`04-CAIXA.gs:576-607`) e baixa de estoque (`04-CAIXA.gs:307-321`, `2131-2147`).
- **CLIENTES**: lista de clientes/limites (`04-CAIXA.gs:533-574`), quitação de dívida (`04-CAIXA.gs:337-353`), saldo devedor pra montar a lista de itens em aberto (`04-CAIXA.gs:431-444`).
- **HISTÓRICO**: grava no fechamento (`04-CAIXA.gs:210-219`), lê pro relatório de vendas (`04-CAIXA.gs:727-739`) e pros itens de crediário do cliente (`04-CAIXA.gs:449-476`). Sempre usa a **primeira aba** (`getSheets()[0]`), não uma aba com nome.

`08-CLIENTES.gs` roda **dentro** da planilha CLIENTES (`getActiveSpreadsheet()`, `08-CLIENTES.gs:20-21`).
`09-HISTORICO.gs` é uma **versão antiga/alternativa**, pensada pra uma planilha única com abas INÍCIO/CAIXA/CLIENTES/HIST (`09-HISTORICO.gs:108-130`). Ela redefine `obterConfiguracoes` e `fecharCaixaEArquivar` com semântica diferente (ver §4.4). **Não é o fluxo canônico**: o fechamento que vale é o de `04-CAIXA.gs:130`.

---

## 1. Layout de dados

### 1.1 Planilha CAIXA, aba `CAIXA`

**Painel (linhas 1–3)** [FATO]
| Célula | Conteúdo | Ref |
|---|---|---|
| H1 | fórmula `=NOW()`, relógio decorativo | `04-CAIXA.gs:51-54` |
| H2 | data de hoje em texto `dd/MM/yyyy` | `04-CAIXA.gs:57` |
| F2:G3 (mesclada) | Dinheiro na gaveta = `SALDO_INICIAL + Σ Dinheiro`, ou o texto "FECHADO" | `04-CAIXA.gs:59, 64, 99` |
| J2 (J2:K2/K3 mesclada) | Entrada virtual = Σ Crédito+Débito+PIX+Externa (líquido) | `04-CAIXA.gs:61, 100` |

- **Linha 6**: cabeçalho da tabela de vendas (`04-CAIXA.gs:797`).
- **Linha 7 em diante**: uma linha por item vendido ou movimento (`04-CAIXA.gs:75-77, 283`).
- **Linha 5 em diante**: área protegida (`04-CAIXA.gs:30, 2567`). A linha 4 não é usada pelo código.

**Colunas: localizadas pelo TEXTO do cabeçalho, não pela letra** (`getMapeamentoColunas`, `04-CAIXA.gs:796-819`). O cabeçalho passa por `removerAcentos` + `toUpperCase` e cai na primeira regra que casar, nesta ordem:

| Campo lógico | Regra no cabeçalho | Significado |
|---|---|---|
| `ean` | contém "BARRA" ou "EAN" | código de barras |
| `id` | igual a "ID" ou contém "ID " | ID do produto |
| `desc` | contém "DESCRIC" ou "PRODUTO" | descrição |
| `categoria` | contém "CATEGOR" | categoria |
| `preco` | contém "PRECO" ou "VALOR" | valor **bruto da linha** (subtotal = preço × qtd, ver §3.1) |
| `qtd` | contém "QUANT" ou "QTD" | quantidade |
| `pagto` | contém "PAGAMEN" ou "PAGAMET" | forma de pagamento (texto livre, ex. "Débito") |
| `liquidado` | contém "LIQUID" | **nº de dias** até o dinheiro cair, `""` (crediário) ou `"FUTURO"` |
| `dataRecebimento` | contém "RECEB" | **data** em texto `dd/MM/yyyy` em que cai, ou "Aguardando Pagamento" |
| `taxa` | contém "TAXA" | taxa em R$ |
| `recebido` | contém "VENDA" | valor **líquido** que a loja recebe (a coluna se chama "Venda") |
| `hora` | contém "HORA" ou "DATA" | data/hora da venda em texto `dd/MM/yyyy HH:mm:ss` |
| `cliente` | contém "CLIEN" | nome do cliente, ou origem/plataforma na venda externa |

**Letras reais das colunas: [AMBÍGUO]**
- Quando o mapeamento falha, `atualizarPainelCaixa` supõe `pagto = I (9)` e `preco = G (7)` (`04-CAIXA.gs:70`).
- `03-ADMINISTRATIVO.gs:1487-1500` lê o CAIXA por posição fixa: C = descrição, E = valor, G = pagamento, J = "Recebido" (data).
- O comentário em `04-CAIXA.gs:808-810` diz que "Recebido" vem logo depois de "Liquidado em".
- Com o mínimo de 13 colunas (`04-CAIXA.gs:279`), o layout mais provável [INFERÊNCIA] é: `A EAN | B ID | C Descrição | D Categoria | E Valor | F Qtd | G Pagamento | H Taxa ou Dias | I Dias a Liquidar ou Taxa | J Recebido (data) | K Venda (líquido) | L Data/Hora | M Cliente`.
- Esses dois palpites se contradizem. É mais um sinal do acoplamento por posição.

### 1.2 Aba oculta `_BACKUP_CAIXA` (na planilha CAIXA)
Cópia só de valores de `A1:(lastRow, max(lastCol,15))` do CAIXA, usada pra desfazer edições manuais (`04-CAIXA.gs:2619-2642`).

### 1.3 DocumentProperties da planilha CAIXA (fazem o papel de "Configurações")
Não existe aba de Configurações no 04. Tudo fica em `PropertiesService.getDocumentProperties()`.

| Chave | Padrão | Uso | Ref |
|---|---|---|---|
| `ID_PLANILHA_ESTOQUE` | ID fixo acima | de onde vem o estoque | `04-CAIXA.gs:612` |
| `TAXA_DEBITO` | 1.5 (%) | | `:613` |
| `DIAS_DEBITO` | 7 | | `:614` |
| `TAXA_CREDITO` | 3.5 (%) | | `:615` |
| `DIAS_CREDITO` | 7 | | `:616` |
| `TAXA_PIX` | 0 (%) | | `:617` |
| `TAXA_CREDIARIO` | 0 (%) | **salva, mas nunca usada** no cálculo | `:618` |
| `REPASSE_DEBITO` / `REPASSE_CREDITO` | "SIM"/"NAO" (padrão = não) | cliente paga a taxa? | `:619-620` |
| `STATUS_CAIXA` | "ABERTO" se não existir | | `:45, 121, 228` |
| `ID_SESSAO_CAIXA` | — | protocolo `CX-yyyyMMdd-HHmm` | `:119, 122` |
| `DATA_ABERTURA` | — | ISO, **gravado e nunca lido** | `:123` |
| `SALDO_INICIAL` | — | fundo de troco | `:124` |
| `SUGESTAO_PROXIMO_FUNDO` | — | valor "mantido" no último fechamento | `:207` |

### 1.4 Planilha ESTOQUE, aba `ESTOQUE` (ou a primeira aba) — só as colunas que o Caixa usa
- Dados a partir da **linha 6**. Lê `A:K` (`04-CAIXA.gs:584-586`).
- A = EAN, B = ID, C = Descrição, D = Categoria (padrão "Geral"), **J = Preço de venda** (idx 9), **K = Estoque/qtd** (idx 10) (`04-CAIXA.gs:593-598`).
- A baixa de estoque escreve **na coluna 11 (K)**, com o número da linha capturado no cache do diálogo (`04-CAIXA.gs:314, 2138`).
- Segundo `03-ADMINISTRATIVO.gs:1527-1528`, I = custo fracionado.
- O Caixa **não lê** o bloco de Serviços (colunas N+).

### 1.5 Planilha HISTÓRICO, primeira aba
Cabeçalho na linha 1 (é criado se a aba estiver vazia; os nomes têm erros de digitação: "EANO", "PAGAMETO") e dados a partir da linha 2 (`04-CAIXA.gs:213-219`).

| Col | Cabeçalho | Conteúdo gravado | Ref |
|---|---|---|---|
| A | HORA E DATA | data/hora da venda em **texto** `dd/MM/yyyy HH:mm:ss` (ou a hora do fechamento, se estava vazia) | `04-CAIXA.gs:164-174` |
| B | PROTOCOLO | `ID_SESSAO_CAIXA` ou `"CX-AVULSO"` | `:137` |
| C | EANO | EAN | |
| D | ID | ID do produto | |
| E | DESCRIÇÃO | | |
| F | CATEGORIA | | |
| G | VALOR | valor bruto (`preco`) | |
| H | QUANTIDADE | `parseInt`, padrão 1 | `:160` |
| I | PAGAMETO | forma, como estava escrita | |
| J | RECEBIMENTO | **o conteúdo de `liquidado`**, ou seja, nº de DIAS (ou `""`) | `:188` |
| K | TAXA | R$ | |
| L | VENDA | valor líquido (`recebido`) | |
| M | CLIENTE | | |

A coluna "Recebido" do caixa (data calculada) **não é arquivada**. O Histórico guarda só os dias, e a data real precisa ser recalculada como A + J. Isso bate com o aviso do prompt sobre "recebimento = dias".

### 1.6 Planilha CLIENTES, aba `CLIENTES`
- Dados a partir da **linha 7** (índice 6 em todos os loops: `04-CAIXA.gs:343, 436, 541`; `08-CLIENTES.gs:29, 328, 410, 465, 519`).
- Colunas conforme `08-CLIENTES.gs:580-605`:

| Col | Campo | Observação |
|---|---|---|
| A | ID | `CLI-n` |
| B | Nome | busca do crediário é por **nome** |
| C | Celular/WhatsApp | |
| D | CPF | |
| E | Limite Total (R$) | |
| F | Limite Usado = **saldo devedor** | fonte da verdade da dívida (`04-CAIXA.gs:430`) |
| G | Disponível | número `E−F` ou o texto `"ILIMITADO"` |
| H | "Aumento Aut.?" (SIM/NÃO) | **conflito**: o 04 também lê H como "data de vencimento" pro atraso (§8) |
| I | % Aumento automático | guardado como fração (÷100, `08-CLIENTES.gs:830`) |
| J | Sem Limite? (SIM/NÃO) | |
| K | Somente Titular? (SIM/NÃO) | |
| L | Observações (avisos pro caixa) | |
| M–P | Dependentes 1–4 | |
| Q | Dias p/ juros | padrão 30 |
| R | Frequência dos juros | Diário/Mensal/Bimestral, padrão Mensal |
| S | % Juros | fração, padrão 2% → 0.02 |
| T | Juros de mora legal? | SIM/NÃO |
| U | Endereço | |
| V | Data de nascimento | |
| W | Sexo | |
| X | E-mail | |

---

## 2. Formas de pagamento, taxa e liquidação

### 2.1 Formas
- **PDV**: Dinheiro, PIX, Débito, Crédito, Crediário (`04-CAIXA.gs:955-961`).
- **Receber pagamento de conta**: Dinheiro, PIX, Débito, Crédito (`:1408`).
- **Venda externa e contrato**: gravadas como `"Externa"` (`:2092`).
- A comparação é feita com `removerAcentos(...).toUpperCase()`: "DEBITO", "CREDITO", "PIX", "CREDIARIO". Qualquer outra coisa é tratada como Dinheiro (`:247-256`).

### 2.2 `calcularTaxaELiquidacao(forma, valorBruto)` (`04-CAIXA.gs:245-270`)

| Forma | taxaPct | dias | repasse | pendente |
|---|---|---|---|---|
| DEBITO | `cfg.taxaDebito` (padrão 1.5) | `cfg.diasDebito` (padrão 7) | `cfg.repasseDebito` | não |
| CREDITO | `cfg.taxaCredito` (padrão 3.5) | `cfg.diasCredito` (padrão 7) | `cfg.repasseCredito` | não |
| PIX | `cfg.taxaPix` (padrão 0) | **0, fixo no código** | **false, fixo** | não |
| CREDIARIO | **0, fixo** (ignora `TAXA_CREDIARIO`) | 0 | false | **sim** |
| outra (Dinheiro) | 0 | 0 | false | não |

Fórmulas:
```
taxaValor          = valorBruto × taxaPct / 100
valorCobradoCliente = repasse ? valorBruto + taxaValor : valorBruto   // calculado mas NÃO gravado
valorLiquidoLoja    = pendente ? 0 : (repasse ? valorBruto : valorBruto − taxaValor)
diasParaLiquidar    = pendente ? "" : dias
dataRecebimentoTexto = pendente ? "Aguardando Pagamento" : hoje + dias (dd/MM/yyyy)
```
- Na gravação, taxa e líquido são arredondados com `toFixed(2)` (`:296-297`). O cálculo é **por item** (cada linha do carrinho passa pela função separadamente), então o arredondamento também é por item.
- **Parcelamento de cartão: não existe.** Crédito tem uma taxa só e um prazo só, sem número de parcelas nem taxa por faixa de parcelas.
- **Configurável × fixo no código**:
  - Configuráveis (tela ⚙️, `04-CAIXA.gs:1689-1754`): taxas e dias de débito/crédito, taxa PIX, repasse.
  - Fixos no código: dias do PIX = 0, repasse do PIX = não, crediário sem taxa, dinheiro sem taxa.
  - Os padrões 1.5 / 3.5 / 7 / 7 estão fixos em `obterConfiguracoes`.
- **Bug**: `parseFloat(prop) || padrão` (`04-CAIXA.gs:613-618`). Se o usuário salvar **0** em taxa ou dias, a leitura volta pro padrão (0 → 1.5%, 0 dias → 7). Não dá pra ter débito sem taxa nem liquidação D+0 no débito/crédito.

### 2.3 Taxas na venda externa e no contrato
Essas vendas **não** usam `calcularTaxaELiquidacao`. A taxa (%) e os dias são digitados na hora (§3.3 e §3.4).

---

## 3. Fluxos de venda

### 3.1 Venda de produto no PDV (`processarVendaPDV`, `04-CAIXA.gs:275-328`, UI em `:921-1350`)
1. O diálogo só abre se `STATUS_CAIXA !== 'FECHADO'` (`:825`).
2. Ao abrir, carrega **uma vez** a lista de produtos (`A:K` do ESTOQUE), os clientes e a configuração (`:1034-1039`).
3. Busca por EAN, ID ou nome, com no máximo 10 resultados (`:1135-1152`). O fluxo é: seleciona o produto → informa a quantidade → confirma (`:1159-1206`).
4. **Checagem de estoque só no cliente, e por item**: `if (p.est < qtd)` bloqueia (`:1183`). Ela não soma o mesmo produto adicionado duas vezes ao carrinho e não é refeita no servidor.
5. Item do carrinho: `{rowEstoque, ean, id, desc, categoria, preco: pVenda, qtd, subtotal: pVenda*qtd}` (`:1188-1197`).
6. No servidor: **uma linha no CAIXA por item** com `preco = item.subtotal` (o total da linha, não o unitário), `qtd`, `pagto`, dias, data de recebimento, taxa, líquido, hora (texto) e `cliente` (`:282-304`). Nas vendas que não são crediário, o cliente é `"À Vista / Consumidor Final"` (`:1315`).
7. **Baixa de estoque** (`:307-321`): para cada item com `rowEstoque`, lê `K(rowEstoque)`, faz `parseInt`, grava `max(0, atual − qtd)`.
   - A escrita acontece **na linha capturada no início do diálogo**. Se o ESTOQUE ganhou ou perdeu linhas nesse meio-tempo, a baixa cai no produto errado.
   - Um erro na baixa **só vai pro log**: a venda fica gravada e o estoque não. Não há atomicidade.
8. **Serviço**: **não existe venda de serviço no 04-CAIXA.** O PDV só lista produtos `A:K`, e não há referência a "SERV-" nem ao bloco N+ (grep). `01-ESTOQUE.gs:1601` filtra uma categoria "Serviço", mas nenhum código no Caixa grava essa categoria.

**Descontos** (`:1002-1013`, `:1247-1273`, `:1325-1345`):
- Tipo R$ ou %. O % é limitado a 0–100 e o R$ a 0–subtotal. A UI mostra a conversão inversa (R$ ↔ %).
- Desconto desativado quando a forma é Crediário (`:1050-1055, 1252-1255`).
- `total = max(0, subtotal − desconto)`. Com repasse de taxa, a UI soma a taxa ao total exibido (`:1273-1279`).
- **BUG GRAVE**: a UI manda `desconto: descontoEmReais` (`:1345`), mas `processarVendaPDV` **ignora `dadosVenda.desconto`**. As linhas são gravadas com o `subtotal` cheio, sem desconto. O desconto só existe na tela.

**Troco no PDV**:
- Só aparece com Dinheiro. `troco = valorRecebido − total`; se for negativo, mostra "Falta R$ X" (`:1285-1304`).
- É **apenas visual**: não bloqueia valor insuficiente e não é gravado.

**Crediário no PDV**:
- Exige cliente selecionado (`:1316-1322`) e grava o **nome** na coluna cliente.
- Mostra saldo devedor, disponível e dias de atraso. Se `total > limiteTotal − limiteUsado` e o cliente não for ilimitado, aparece o alerta "VENDA EXCEDE O LIMITE", **mas a venda não é bloqueada** (`:1114-1122`; `finalizarVenda` não verifica isso).
- Linha gravada com `liquidado = ""`, `dataRecebimento = "Aguardando Pagamento"`, `taxa = 0`, `recebido (líquido) = 0`.
- **Nenhum código incrementa `CLIENTES!F` (Limite Usado) numa venda no crediário.** Procurei nos três arquivos e em todo o projeto: a coluna F só é escrita no pagamento (`04-CAIXA.gs:350`) e no cadastro (`08-CLIENTES.gs:586`, sempre 0). [AMBÍGUO] Ou a dívida é lançada à mão na planilha, ou há alguma fórmula que não está nos .gs. Uma fórmula seria apagada no primeiro pagamento, porque `setValue` sobrescreve. Na prática, **o saldo devedor não sobe sozinho**.
- "Somente titular" e "dependentes" são **só avisos** na busca de clientes (`:1670-1672`). Não há regra aplicada.

### 3.2 Receber pagamento de cliente / quitação de fiado (`processarPagamentoContaCliente`, `04-CAIXA.gs:330-399`, UI `:1352-1636`)
1. Só abre com o caixa aberto (`:833`).
2. Seleciona o cliente e carrega os "produtos comprados" em aberto com `obterItensCrediarioCliente(nome)` (`:425-531`):
   - Junta as linhas do Histórico e do CAIXA aberto em que cliente == nome (normalizado), pagamento contém "CREDIARIO", descrição não vazia e sem "RECEBIMENTO DE CONTA".
   - Ordena por data, da mais antiga pra mais nova.
   - Calcula `jaQuitado = max(0, Σ(preco×qtd) − limiteUsadoAtual)` e vai descontando em **FIFO**. Sobram só os itens que ainda não estão cobertos.
   - Como `preco` já é o subtotal da linha (§3.1), a conta `preco × qtd` **multiplica a quantidade duas vezes** nas linhas com qtd > 1.
   - A tabela da UI soma só `data-preco` (`:1522, 1545`), sem a qtd. As duas contas são inconsistentes.
3. O valor a pagar vem preenchido com a soma dos itens marcados, mas pode ser editado (pagamento parcial) (`:1415-1417`). **Os itens marcados não são gravados como pagos.** Só o valor importa.
4. No servidor:
   - `valor ≤ 0` é rejeitado.
   - Procura o cliente pelo **ID** (`dados[i][0]`) e faz `novoLimiteUsado = max(0, F − valor)` → grava em F. G recebe `"ILIMITADO"` ou `E − novoF`. **Se o saldo zerar, apaga a coluna H** (`:349-353`).
   - Um pagamento maior que a dívida é perdido sem aviso (não vira crédito do cliente).
5. Grava uma linha no CAIXA (`:361-381`):
   - desc = `"RECEBIMENTO DE CONTA / FIADO"`, **categoria = `"CREDIARIO"`**, preco = valor, qtd = 1.
   - **pagto = a forma usada pra pagar** (Dinheiro/PIX/Débito/Crédito). A taxa e os dias seguem `calcularTaxaELiquidacao(forma, valor)`.
6. **Troco**:
   - A UI exige `recebido ≥ valor` quando é Dinheiro (`:1605-1611`).
   - O servidor calcula `troco = max(0, recebido − valor)` só pra mensagem (`:386-390`).
   - O troco não abate a dívida e não é gravado (`:334-335`).
7. **Taxa com repasse**: a UI mostra "Taxa repassada ao cliente", mas a dívida baixa pelo `valor`, a linha grava `preco = valor` e o líquido = valor. O valor extra que o cliente pagaria não aparece em lugar nenhum.
8. **Juros e multa: nenhum cálculo.** Os campos Q–T existem no cadastro, mas nunca são aplicados (§5).

### 3.3 Venda Externa (`salvarVendaExterna`, `04-CAIXA.gs:2105-2158`, UI `:2205-2539`)
- Entradas:
  - descrição e valor bruto (obrigatórios)
  - categoria ∈ {"Venda Externa", "Delivery", "Outras Entradas"}
  - origem/plataforma
  - data (input date, pode ser no passado)
  - taxa da plataforma (%), frete (R$), desconto (R$), motoboy/entrega (R$)
  - dias até cair
- Fórmulas (`:2117-2119`):
  ```
  taxaValor     = valorBruto × taxaPct/100
  totalDeducoes = taxaValor + frete + desconto + custoEntrega
  valorLiquido  = max(0, valorBruto − totalDeducoes)
  ```
- Linha gravada (`escreverLinhaEntradaExterna`, `:2077-2103`):
  - pagto = `"Externa"`, qtd = **1 sempre**, `liquidado = dias`
  - dataRecebimento = dataVenda + dias
  - **coluna TAXA = totalDeducoes** (as 4 deduções somadas numa coluna só; as parcelas **não** são guardadas separadas)
  - VENDA = líquido, hora = data escolhida + 00:00:00, **cliente = origem**
  - EAN e ID **não são gravados**, mesmo com produto vinculado. Por isso a Curva ABC por ID não enxerga essas vendas.
- **Vínculo com o estoque** (opcional):
  - O valor é sugerido como `pVenda × qtd` (`:2404-2422`).
  - A baixa é na coluna K da linha em cache: `max(0, atual − qtdVendida)` (`:2131-2147`).
  - Não há checagem de estoque suficiente.
- **Não verifica se o caixa está aberto** (`abrirJanelaVendaExterna`, `:2059-2062`).

### 3.4 Contrato / Assinatura (`salvarContratoAssinatura`, `04-CAIXA.gs:2165-2203`)
- Entradas: descrição, cliente/contratante, data de início, valor mensal, duração em meses (padrão 12), forma de cobrança, taxa (%), dias base e tolerância de atraso.
- Sugestões fixas na UI por forma de cobrança (`:2467-2473`): Cartão 4.5% / 30 dias; Boleto 2% / 2 dias; PIX 0/0; Dinheiro 0/0; Outros 0/0. São editáveis.
- Fórmulas:
  ```
  diasParaLiquidar     = dias + diasAtraso            // tolerância somada ao prazo
  taxaValor            = valorMensal × taxaPct/100
  valorLiquidoParcela  = max(0, valorMensal − taxaValor)
  para k = 0 .. n−1:
     dataParcela = dataInicio com setMonth(mes + k)
     descricao   = desc + " [forma]" + " (k+1/n)"
     categoria   = "Assinatura", pagto = "Externa", qtd = 1, cliente = contratante
     liquidado   = (k >= 1) ? "FUTURO" : diasParaLiquidar
     hora        = dataParcela (texto), dataRecebimento = dataParcela + diasParaLiquidar
  ```
- Todas as parcelas entram **de uma vez no CAIXA aberto**. A 1ª conta hoje (mesmo que a data de início seja no futuro). Da 2ª à n-ésima ficam como FUTURO.
- **Como a marca FUTURO é tratada**:
  - O painel ignora (`:79-83`).
  - O fechamento separa e reescreve essas linhas a partir da linha 7 (§4).
  - O relatório subtrai de volta (`:699-705`).
  - `03-ADMINISTRATIVO.gs:2382` também ignora.
- **Ativação: NÃO EXISTE.** Nenhum código troca "FUTURO" por um número de dias quando a data chega. O comentário em `04-CAIXA.gs:2162-2163` ("só sendo contadas quando a data delas chegar (via Histórico/DRE, que já filtram por data)") é falso: as linhas FUTURO nunca vão pro Histórico, porque o fechamento sempre as mantém no Caixa. **As parcelas 2..n nunca viram receita.**
- `setMonth` tem estouro de mês: início em 31/01 → a parcela 2 cai em 03/03 (ou 02/03), e daí em diante as datas ficam deslocadas.
- Não há cancelamento de contrato. Pra cancelar, só excluindo linha por linha.

### 3.5 Cancelamento / estorno (`excluirVendaPorLinha`, `04-CAIXA.gs:898-911`, UI `:1910-2002`)
- Lista as linhas do caixa aberto (da mais recente pra mais antiga), com filtro de texto e `confirm()`. Faz `deleteRow(linha)`.
- **Não devolve o estoque, não reverte a quitação de crediário (F) e não gera log/auditoria.** Também exclui linhas FUTURO.
- Depois do fechamento não há estorno (o Histórico não tem ferramenta).
- Não checa permissão nem status do caixa.
- A linha é identificada pelo número da linha na planilha. Se outra linha for apagada antes, o índice fica velho (a UI remove da lista local, mas as linhas abaixo mudam de número).

---

## 4. Abertura e fechamento de caixa

### 4.1 Abertura (`abrirCaixa`, `04-CAIXA.gs:105-128`)
- Recusa se o caixa já estiver ABERTO.
- **Atenção**: numa instalação nova, `STATUS_CAIXA` não existe e o painel considera "ABERTO" (`:45`). Então dá pra vender sem abrir, e o fechamento usa o protocolo `"CX-AVULSO"` (`:137`).
- Pede o fundo de troco e sugere `SUGESTAO_PROXIMO_FUNDO`. Se a resposta vier vazia, usa a sugestão (ou 0).
- Protocolo `CX-yyyyMMdd-HHmm` (fuso do script). Duas aberturas no mesmo minuto geram o mesmo ID.
- Grava STATUS/ID/DATA_ABERTURA/SALDO_INICIAL.

### 4.2 Painel ao vivo (`atualizarPainelCaixa`, `04-CAIXA.gs:39-103`)
- Pula FUTURO.
- `valorConsiderado = líquido > 0 ? líquido : bruto`.
- Gaveta = SALDO_INICIAL + Σ Dinheiro.
- Virtual = Σ Crédito+Débito+PIX+Externa (total já caído + a cair).
- Crediário não entra.
- Chama `atualizarBackupCaixa()` no fim.

### 4.3 Fechamento (`fecharCaixaEArquivar`, `04-CAIXA.gs:130-235`)
1. Recusa se já estiver FECHADO.
2. Percorre a linha 7 em diante. As linhas FUTURO vão pra `linhasFuturasParaManter`. Nas outras, se `desc ≠ ""` ou `preco > 0`:
   - `resumo[formaPagto] += precoBruto`, onde a chave precisa ser **exatamente** "Dinheiro", "PIX", "Débito", "Crédito", "Crediário" ou "Externa". Qualquer outra grafia cai em **Dinheiro** (`:177`).
   - `TotalBruto += preco` e `TotalLiquido += valRecebido`. TotalLiquido é calculado mas não aparece.
   - Monta a linha do Histórico (A–M, §1.5).
3. `totalGaveta = saldoInicial + resumo.Dinheiro` (bruto).
4. **Sangria**: pergunta quanto MANTER. Rejeita se for maior que a gaveta. `sangria = gaveta − manter`.
5. Mostra o relatório (fundo, vendas em dinheiro, gaveta, manter, sangria, PIX, Débito, Crédito, Crediário, Externa, TOTAL VENDIDO) e pede confirmação SIM/NÃO.
6. Grava `SUGESTAO_PROXIMO_FUNDO = manter`.
   - **A sangria e o resumo da sessão não são guardados em lugar nenhum** (só aparecem no alerta).
7. Faz append no Histórico (primeira aba, cria o cabeçalho se estiver vazia).
8. Limpa conteúdo e formato de `A7:(lastRow, lastCol)`. Reescreve as linhas FUTURO a partir da linha 7 (conteúdo bruto, sem formatação).
9. STATUS = FECHADO. Apaga ID_SESSAO e SALDO_INICIAL. Atualiza o painel.

Observações:
- O "TOTAL VENDIDO" **inclui os recebimentos de fiado** (linhas com categoria CREDIARIO e pagamento Dinheiro/PIX/...). A venda original no crediário e depois o recebimento são somados, então o total vendido fica inflado.
- A ordem é: grava o Histórico, depois limpa o Caixa, sem transação. Se falhar no meio, pode duplicar ou perder dados.

### 4.4 Versão alternativa em `09-HISTORICO.gs` (legado)
- `obterConfiguracoes` (`09-HISTORICO.gs:4-30`) lê uma aba **"Configurações"** (chave na coluna A, valor na B, a partir da linha 2):
  - `ID_PLANILHA_ESTOQUE`, `ID_PLANILHA_HISTORICO` ou `ID_EXTERNO` → `idPlanilhaExterna`
  - `NOME_ABA_HISTORICO` ou `NOME_ABA_CAIXA` → `nomeAbaHistoricoCaixa` (padrão "HIST")
- `fecharCaixaEArquivar` (`:36-103`):
  - Usa a aba `VENDAS_HOJE`, depois `CAIXA`, depois a ativa. Dados **a partir da linha 2**, 13 colunas **copiadas como estão** (sem mapeamento, sem protocolo, sem tratar FUTURO, sem sangria).
  - Filtra linhas com A, C ou E preenchidas. Grava na aba HIST/HISTORICO/HISTÓRICO/CAIXA da planilha externa, criando o cabeçalho `Horário | ID Sessão | Código de Barras | ID Produto | Descrição | Categoria | Preço Bruto | Quantidade | Pagamento | Liquidado Em | Taxa | Recebido Líquido | Cliente` (`:66-70`) se não existir.
  - Limpa só o conteúdo.
- Se estiver no mesmo projeto que o 04, as funções com o mesmo nome **colidem** (no Apps Script vale a última carregada). Tratar como **código morto/legado**. O único dado aproveitável são os nomes de coluna mais legíveis, que confirmam a semântica: J = "Liquidado Em" (dias), L = "Recebido Líquido".
- Navegação `irParaInicio/Caixa/Clientes/Historico` (`:108-130`): só troca de aba.

---

## 5. Clientes e crediário (`08-CLIENTES.gs`)

**Cadastro** (`salvarClienteScript`, `:540-607`; formulário `:609-857`)
- Validações na UI:
  - nome com **≥ 2 palavras** (`:783`)
  - celular com **≥ 8 dígitos** (`:789`)
  - CPF opcional, **sem validação de dígito verificador**
- **Duplicado** (`verificarDuplicado`, `:510-538`): compara CPF e celular só pelos dígitos, ignorando o próprio ID. **Só avisa**: o usuário pode confirmar e salvar mesmo assim (`:801-808`).
- Padrões de um novo cliente (`:611-616`): limite R$ 500, aumento automático NÃO (se ligado, a UI sugere 5%), sem limite NÃO, somente titular NÃO, juros após 30 dias, frequência Mensal, 2%, mora legal NÃO.
- **ID**: `"CLI-" + max(1, lastRow − 5)` (`:577-578`). Depende da contagem de linhas, então **repete IDs** depois de uma exclusão. Não é zero-padded.
- Novo cliente: F = 0, G = `"ILIMITADO"` ou E.
- Edição: sobrescreve B–E, G–X. Mantém F. Recalcula G = E − F (ou ILIMITADO).
- "Somente titular" limpa os dependentes na UI (`:763-774`).

**Limite / saldo**:
- Limite total em E. Saldo devedor em F. Disponível em G (calculado e gravado; não é fórmula).
- "Sem limite" (J = SIM) torna o disponível "ILIMITADO".
- **Aumento automático (H/I): guardado e nunca aplicado** em nenhum lugar.

**Atraso** (`04-CAIXA.gs:546-552`): se F > 0 e H for uma data válida no passado, `diasAtraso = floor((hoje − H)/1 dia)`. Mas H guarda "SIM"/"NÃO" (aumento automático), então `new Date("SIM")` é inválido e **o atraso sai sempre 0**, a não ser que alguém digite uma data em H à mão. O pagamento que zera a dívida **apaga H** (`04-CAIXA.gs:353`), e com isso some também o flag de aumento automático.

**Juros/multa**: Q (dias), R (frequência), S (%), T (mora) **são só cadastrados**. Nenhuma função calcula juros.

**Exclusão** (`apagarClienteSelecionado`, `:18-61`):
- Usa a linha selecionada (≥ 7). **Bloqueia se F > 0.** Pede confirmação e faz `deleteRow`.

**Busca e extrato**:
- `obterTodosClientesComItens` (`:457-508`) devolve um único item sintético "Compras em Aberto no Crediário" = F. Não detalha itens.
- O extrato (`gerarExtratoImpressao`, `:322-399`) mostra só "Saldo em aberto" = F e usa `window.print()`.
- A busca tolera texto quebrado por encoding (substituições tipo `Ã£`→a, `:107-119`).

**Pagamentos**: ver §3.2. A dívida baixa por **valor**, identificada pelo ID. A lista de itens é casada pelo **nome**.

---

## 6. Proteção, auditoria, backup e autenticação

- **`onOpen`** (`04-CAIXA.gs:16-21`): chama `protegerLinhasCaixaSilencioso()` e `atualizarBackupCaixa()`.
- **Proteção nativa** (`:2553-2607`):
  - Protege o range da linha 5 até `max(maxRows, 2000)` × `max(maxCols, 26)`. Tira todos os editores e a edição por domínio. É identificada pela descrição fixa.
  - Tem botões Proteger e Desproteger. A proteção volta sozinha no próximo `onOpen`.
  - O comentário admite que **o dono nunca fica bloqueado** (`:2612-2614`).
- **`onEdit`** (`:23-34`): qualquer edição manual na aba CAIXA com linha ≥ 5 chama `restaurarDoBackupCaixa(range)`:
  - Copia de volta do `_BACKUP_CAIXA` o mesmo retângulo.
  - Se a área estiver fora do backup, limpa.
- **Backup** (`:2621-2642`):
  - A aba oculta é sobrescrita (só valores) a cada `atualizarPainelCaixa` (ou seja, depois de toda operação feita por botão) e no `onOpen`.
  - É uma única versão, sem histórico e sem registro de quem mudou.
- **Auditoria**: nenhuma. Nada registra usuário, horário ou valor antigo/novo. Exclusões de venda e de cliente são definitivas e sem rastro.
- **Autenticação** (`07-MENU.gs:37-150`, só como referência):
  - Login e senha contra a planilha USUÁRIOS (dados a partir da linha 6: A ID, B Nome, C Login, D hash SHA-256 **sem salt**, E permissões separadas por vírgula).
  - "ADMIN" ou "TODOS" libera tudo. Os outros perfis precisam do nome do módulo (CAIXA, CLIENTES, HISTORICO...).
  - Depois do login, só **abre a URL da planilha**. Quem tem o link entra direto, então não há controle real.
  - Dentro do 04 e do 08 **não há checagem de permissão nenhuma**.

---

## 7. O que DIVERGE ou NÃO APARECE no prompt

**Divergências e contradições**
1. **Ativação de parcelas FUTURO**: o prompt diz que elas "ficam inativas até a data chegar" e pede um job. O original **não tem ativação nenhuma** (§3.4). O job é funcionalidade nova, não uma migração. Falta definir o que "ativar" faz: a parcela entra em qual sessão de caixa? Com qual data e hora? Os dias de liquidação contam a partir do vencimento?
2. **Venda de serviço sem baixa de estoque**: o PDV do original **não vende serviço** (§3.1). É funcionalidade nova no Caixa.
3. **Venda externa com 4 deduções**: no original só a **soma** é gravada, na coluna Taxa. Não há campos separados. Qtd = 1 e EAN/ID ficam vazios mesmo com produto vinculado. O prompt não diz como modelar. Sugestão: 4 campos estruturados + `produto_id` + qtd real.
4. **Crediário "com troco e taxa"**: no original, o troco e a taxa existem **no recebimento** (quitação). A venda no crediário tem taxa 0, nenhum troco e nenhum desconto. O prompt mistura os dois fluxos.
5. **Desconto**: o prompt não fala de desconto no PDV. O original tem desconto em R$ ou %, mas ele **não é persistido** (bug, §3.1). Decidir se entra e onde é gravado (linha ou venda).
6. **"Receita Bruta exceto Crediário" (DRE)**: no código (`03-ADMINISTRATIVO.gs:117, 637`) o filtro é pela **categoria "CREDIARIO"**, isto é, exclui as linhas de **recebimento de fiado**. As **vendas** feitas no crediário **entram** na receita (regime de competência). Não excluir as vendas a prazo por engano.
7. **Configurações**: o prompt fala em calcular a taxa "conforme forma de pagamento", sem dizer onde ficam os parâmetros. No original: DocumentProperties com padrões 1.5% / 7 d (débito), 3.5% / 7 d (crédito), PIX 0% D+0, **repasse** opcional por forma, e `TAXA_CREDIARIO` configurável mas nunca usada.
8. **Parcelamento no crédito**: não existe no original. O prompt também não pede.
9. **Histórico**: o prompt pede "valor bruto separado do líquido" e "recebimento em dias". Confere: G = bruto, L = líquido, J = dias. Mas a data do Histórico (A) é **texto**, e nas vendas externas e contratos é a data escolhida pelo usuário, não a hora do registro.
10. **Resumo do fechamento**: o prompt lista Dinheiro/PIX/Débito/Crédito/Crediário/Externa, igual ao original. Mas o original também tem **fundo de troco** (abertura), **sangria/valor a manter** e **sugestão do próximo fundo**, que o prompt não menciona.

**Funcionalidades do original que o prompt não cita**
- Abertura de caixa com fundo de troco. Status ABERTO/FECHADO bloqueia PDV e recebimento (mas não a venda externa).
- Painel ao vivo: gaveta (fundo + dinheiro) e entrada virtual.
- **Relatório de Vendas** (`04-CAIXA.gs:659-781`): bruto, líquido, taxas, "já disponível" × "a cair", por forma, por categoria, evolução mensal, filtro de mês e ano, Histórico + caixa aberto.
- **Excluir venda** do caixa aberto.
- **Cadastro completo de clientes**: limite, sem limite, aumento automático, somente titular, até 4 dependentes, observações pro caixa, parâmetros de juros, endereço, nascimento, sexo, e-mail, verificação de duplicidade por CPF/celular, bloqueio de exclusão com dívida, extrato imprimível.
- **Lista FIFO de itens em aberto** do cliente na hora de receber.
- **Repasse de taxa** de cartão ao cliente.
- Contrato com **tolerância de atraso** somada aos dias e sugestões de taxa/prazo por forma de cobrança.
- Autenticação por módulo (planilha USUÁRIOS).

---

## 8. Bugs, gambiarras e pontos frágeis (não repetir)

1. **Desconto do PDV é descartado** no servidor (`04-CAIXA.gs:1345` × `275-304`).
2. **Venda no crediário não aumenta a dívida do cliente** (nenhuma escrita em `CLIENTES!F`). O saldo só diminui.
3. **Parcelas FUTURO nunca são ativadas.** Ficam presas no Caixa pra sempre e nunca viram receita (`:224-226`, `:2162-2163`).
4. **Taxa ou dias = 0 não podem ser configurados** (`parseFloat(x) || padrão`, `:613-618`). Em Python: distinguir "não configurado" de 0.
5. **Coluna H de CLIENTES com dois significados** (aumento automático × data de vencimento). O atraso sai sempre 0 e o pagamento apaga o flag (`04-CAIXA.gs:353, 547`; `08-CLIENTES.gs:557, 588`).
6. **ID de cliente pela contagem de linhas** (`08-CLIENTES.gs:578`): repete depois de exclusão. Usar PK autoincrement.
7. **Crediário casado por NOME** (`04-CAIXA.gs:425-531`, `1322`): homônimos se misturam. Usar FK de cliente.
8. **`preco × qtd` sobre um preço que já é subtotal** na lista FIFO (`:514, 519`): conta a quantidade duas vezes. Em Python, guardar `preco_unitario` e `quantidade` e derivar o total.
9. **Baixa de estoque por número de linha em cache** + coluna K fixa + `max(0, …)` escondendo estoque negativo + erro engolido (`:307-321`, `:2131-2147`). Em Python: `UPDATE ... WHERE id=? AND estoque >= ?` na mesma transação da venda.
10. **Checagem de estoque só no cliente** e sem somar o mesmo item repetido no carrinho (`:1183`).
11. **Mapeamento de colunas por substring do cabeçalho** (`:796-819`): "VALOR VENDA" vira `preco`; "DATA DE RECEBIMENTO" casa com "RECEB" antes de "DATA"; renomear um cabeçalho quebra tudo em silêncio. Além disso, `03-ADMINISTRATIVO.gs` lê o mesmo CAIXA por posição fixa, e os fallbacks (`:70`) contradizem essas posições.
12. **Recebimento de fiado somado como venda** no "TOTAL VENDIDO" do fechamento e no relatório (`:176-180`, `669-692`). No relatório, crediário sem líquido usa `valorLiquido = bruto` (`:670`), o que infla o "Total Recebido". Modelar recebimento como outro tipo de movimento, não como venda.
13. **Contas a receber de crediário** (`03-ADMINISTRATIVO.gs:1510-1512, 1552-1554`) só abatem recebimentos quando `pagamento == CREDIARIO`. Só que o recebimento é gravado com a forma real (Dinheiro/PIX), então os pagamentos **nunca são abatidos** e o valor a receber fica superestimado. A fonte da verdade deve ser o saldo do cliente ou um razão (ledger) do cliente.
14. **Repasse de taxa não é persistido**: `valorCobradoCliente` é calculado e jogado fora. A coluna Taxa registra uma taxa que o cliente pagou. Troco e total da UI não batem.
15. **Taxa de venda externa = soma de taxa + frete + desconto + motoboy**. Mistura custos de naturezas diferentes numa coluna "Taxa" que o DRE trata como despesa financeira ou dedução.
16. **`setMonth(+k)` com estouro de fim de mês** nas parcelas do contrato (`:2183-2184`). Usar `dateutil.relativedelta`.
17. **Datas como texto** `dd/MM/yyyy HH:mm:ss` em CAIXA e Histórico, que o Sheets às vezes converte sozinho em Date (tratado em `03-ADMINISTRATIVO.gs:1493-1497`).
18. **Status padrão "ABERTO" sem sessão** gera o protocolo "CX-AVULSO". O protocolo tem resolução de minuto e pode colidir.
19. **Venda externa e contrato não exigem caixa aberto**. Linhas lançadas com o caixa fechado vão pra próxima sessão.
20. **Fechamento sem transação**: grava o Histórico e depois limpa o Caixa. Formas fora da lista exata viram "Dinheiro" no resumo. Sangria e resumo da sessão não são guardados (criar uma tabela `sessao_caixa` com abertura, fundo, fechamento, sangria, mantido e totais).
21. **Exclusão de venda sem estorno** de estoque e de crediário, sem log, pelo índice da linha.
22. **Proteção + onEdit + backup** é gambiarra da planilha: backup de uma versão só, sobrescrito a cada operação, sem autor. Substituir por transações + tabela de auditoria.
23. **Segurança**: SHA-256 sem salt; o login só abre um link público. Usar bcrypt/argon2 e checar permissão na camada de serviço.
24. **Funções duplicadas** entre `04` e `09` (`obterConfiguracoes`, `fecharCaixaEArquivar`) com semânticas diferentes. Ignorar o 09.
25. **Pagamento maior que a dívida é perdido** (`max(0, …)`, `:349`). O troco é só mensagem.
26. **Limite de crédito só avisado**, nunca bloqueado. "Somente titular" é só um aviso. Decidir explicitamente a política no sistema novo.
