# Análise de regras de negócio — ESTOQUE, COMPRAS, USUARIO, MENU

Fonte: `referencia/appsscript/01-ESTOQUE.gs` (1669 l.), `02-COMPRAS.gs` (1582 l.), `06-USUARIO.gs` (505 l.), `07-MENU.gs` (149 l.). Lidos por inteiro. Referências cruzadas pontuais em `03-ADMINISTRATIVO.gs`, `04-CAIXA.gs` e `09-HISTORICO.gs` só para confirmar layout/integrações.
Convenção: `arquivo:linha`. "Ambíguo" = o código não permite concluir com certeza.

---

## 1. Layout de dados

### 1.1 Planilhas (IDs) referenciadas

| ID | O que é | Onde |
|---|---|---|
| `1aPr4-chXwNE19RWIXgOPceB-OmF31Ft5SgtugEPwoMA` | ESTOQUE | `07-MENU.gs:13`, `02-COMPRAS.gs:27` (leitura de estoque/mínimo) |
| `1119HW8n6Ma-H83wbLw9I13bTJ9EgJhhpciPFyyaUXI8` | HISTÓRICO (vendas fechadas + aba "HISTORICO PEDIDOS") | `01-ESTOQUE.gs:1500` (média de vendas p/ estoque mínimo), `02-COMPRAS.gs:28` (grava pedidos), `07-MENU.gs:15` |
| `1UtU74AmVxtfjupGB9BZkr6AdSjUCE9cQWKO7mU-m8gs` | USUÁRIOS | `07-MENU.gs:6,12` |
| `1lIJzyVSwo1eZx0czw9fvfjtfNafo1lEhgtZUt1JHTl4` | COMPRAS (cotação) | `07-MENU.gs:16` |
| `16PD_PSyOKStz2QCVuB66PbFlHdIl6EsbZtP34oB0BJY` | SAÍDAS | `07-MENU.gs:10` |
| `1nBVAh4brJ6KiIgrokph58btEkdkydSlRwDbVBbPzCzA` | CAIXA | `07-MENU.gs:11` |
| `1WrD5GmVXteevylzXZphNMQlcZEkgpxmogbZicK8Gq78` | CLIENTES | `07-MENU.gs:14` |
| `1IuR2cYOMVWy_MTYJ2cPxIrN3KFZLHVEfGTve-s6JIjs` | RELATÓRIO (não há `.gs` dele na referência) | `07-MENU.gs:17` |
| `19qZGkj8FvFl2fv7qtxyHzOglh6AUNzH9pJbSN9hycOw` | ADMINISTRATIVO (= painel "CFAUTO": Markup/DRE/etc.) | `07-MENU.gs:18` |
| `1QHSqLPHPQla-SwxyBkZl7u0kpauWsy5VxdYZIyBxnIE` | Botão "voltar ao menu" do ESTOQUE; presumivelmente a planilha do MENU (onde roda `07-MENU.gs`) — **ambíguo**, não há outra referência a esse ID | `01-ESTOQUE.gs:8` |

Ou seja: o sistema real tem **9 planilhas de módulo + 1 planilha de menu**, não 5.

### 1.2 ESTOQUE — aba "ESTOQUE" (ou a aba ativa)
Cabeçalho na **linha 5**, dados a partir da **linha 6** (`01-ESTOQUE.gs:39,60,497`). Os títulos das colunas A–M não são escritos pelo código; o significado vem do uso:

| Col | Significado | Evidência |
|---|---|---|
| A | EAN / código de barras (formato texto `@`) | `01-ESTOQUE.gs:257,70` |
| B | ID interno sequencial, texto, 4 dígitos com zeros à esquerda ("0001") | `:258,505-516` |
| C | Descrição | `:259` |
| D | Categoria (texto livre) | `:260` |
| E | Modo de compra / embalagem (padrão "Unidade") | `:261,621` |
| F | Fator ("Fracionar em", unidades por pacote; padrão 1) | `:262,622` |
| G | Data da última entrada (texto `dd/MM/yyyy`) | `:575-578` |
| H | Preço de entrada (custo do pacote / unidade comercial da NF) | `:268,735` |
| I | Preço fracionado = H ÷ F (custo por unidade) | `:554-556` |
| J | Preço de venda | `:269` (também escrito pelo ADMINISTRATIVO: `03-ADMINISTRATIVO.gs:218,267,334`) |
| K | Estoque (quantidade) | `:270` (baixado pelo CAIXA: `04-CAIXA.gs:314,2138`) |
| L | Margem % = (J − I) ÷ J | `:562-564` |
| M | Motivo/Destino: `1-Revenda`, `2-Uso/Consumo`, `3-Matéria-Prima` (validação de lista estrita) | `:44-47,271` |
| N (14) | **CONFLITO**: é o início do bloco de Serviços (`COL_INICIO_SERVICOS_ESTOQUE = 14`, `:1186`) **e** também a coluna "ESTOQUE MÍNIMO" (`:1578,1661`; `02-COMPRAS.gs:467`) | ver §8 |
| N–S | Bloco de Serviços (cabeçalho na linha 5): N CÓDIGO SERVIÇO, O NOME DO SERVIÇO, P MATERIAL, Q CUSTO UNIT. (R$), R QTD, S % MÃO DE OBRA | `:1195-1197` |

`L1:L4` são limpos por `limparEFormatardalinha6` (`:1155`) — resto de um layout antigo (a coluna G foi inserida depois; ver comentários "pós-deslocamento" em `03-ADMINISTRATIVO.gs:69-70` e `04-CAIXA.gs:597-598`).

Configuração: `PropertiesService.getScriptProperties()` chave `SEMANAS_BASE_ESTOQUE_MINIMO` (padrão 1) — `01-ESTOQUE.gs:1506-1513`. Gatilho semanal (segunda, 6h) em `calcularEstoqueMinimoAutomaticoSilencioso` — `:1520-1530`.

### 1.3 HISTÓRICO (lido pelo ESTOQUE, escrito pelo COMPRAS)
- Aba de vendas = **primeira aba** (`getSheets()[0]`, `01-ESTOQUE.gs:1593`), dados da linha 2. Colunas usadas: A data/hora (só conta se for objeto `Date`), E descrição, F categoria, G valor, H quantidade (`:1597-1607`). O cabeçalho completo, escrito pelo CAIXA, é: `HORA E DATA, PROTOCOLO, EANO, ID, DESCRIÇÃO, CATEGORIA, VALOR, QUANTIDADE, PAGAMETO, RECEBIMENTO, TAXA, VENDA, CLIENTE` (`04-CAIXA.gs:214`).
- Aba **"HISTORICO PEDIDOS"** (criada pelo COMPRAS se não existir), cabeçalho na linha 1, dados da linha 2: A DATA (texto `dd/MM/yyyy`), B FORNECEDOR, C PRODUTO, D QUANTIDADE, E PREÇO UNIT., F VALOR TOTAL, G ESTOQUE NO MOMENTO (`02-COMPRAS.gs:107-116`).

### 1.4 COMPRAS — aba "Cotação"
Constantes `02-COMPRAS.gs:25-32`: título na linha 7, cabeçalho na **linha 8**, dados da **linha 9**. Se a aba não existe, **renomeia a primeira aba da planilha** para "Cotação" (`:57-63`).
- **Área crua A–C** (`:67-70`): blocos empilhados por fornecedor. Uma linha "faixa preta" (A:C mesclado, só A preenchido, B vazio) = nome do fornecedor; linhas seguintes = A PRODUTO, B PREÇO, C OBS. A distinção faixa × produto é "B vazio" (`:885-888`).
- **Área de resumo a partir da coluna F** (`:75-80`), mapeada **por texto do cabeçalho** (`getMapeamentoCotacao`, `:540-562`): PRODUTO, ESTOQUE ATUAL, VENDA SEMANAL MÉDIA, ÚLTIMO PREÇO PAGO, MENOR PREÇO, FORNECEDOR VENCEDOR, SEGUNDA OPÇÃO, SEGUNDO FORNECEDOR, QTD SUGERIDA, QTD A PEDIR, VALOR DO PEDIDO.
- **Fornecedores não ficam em aba**: são um JSON em `PropertiesService.getDocumentProperties()`, chave `FORNECEDORES_LISTA_JSON` (`:133-143`). O alerta de `configurarSistemaCotacao` ainda fala em "colunas P em diante" (`:97`) e o cabeçalho do arquivo em "3 abas" (`:5`) — ambos desatualizados.

### 1.5 USUÁRIOS
- Escrita (`06-USUARIO.gs:3-4,154,244`): aba **ativa** da planilha USUÁRIOS, dados a partir da **linha 7**: A NOME, B FUNÇÃO, C LOGIN, D SENHA (hash), E PERMISSÃO.
- Leitura (`07-MENU.gs:115-121`): aba "USUÁRIOS" (ou a primeira), a partir da **linha 6**, com comentário dizendo "A (ID), B (Nome), C (Login), D (Hash), E (Permissões)". Só C/D/E são usados, que coincidem com o layout real; a linha 6 (provável cabeçalho) é lida como dado sem efeito prático. **Os comentários divergem entre os dois arquivos** (A=ID × A=NOME).

---

## 2. Produto

### 2.1 Campos e cadastro manual (`salvarNovoProdutoModal`, `01-ESTOQUE.gs:253-278`)
- Formulário (`:188-216`): EAN (opcional), ID (automático, somente leitura), Descrição (**única obrigatória**, validada só no cliente `:219-223`), Categoria (texto livre), Modo/Embalagem (padrão "Unidade"), Fracionar Em (padrão 1), Preço Entrada, Preço Venda, Estoque Inicial (padrão 0), Motivo/Destino (select das 3 opções).
- Gravação: linha = primeira linha ≥6 com **C vazia** (`obterProximaLinhaVazia`, `:495-503`). EAN e ID como texto. Descrição passa por `limparDescricao` (§2.9). Fator `parseFloat || 1`. Preços: remove "R$", **remove todos os pontos**, troca vírgula por ponto (`:264-265`). Estoque `parseInt` (inteiro). Destino padrão "1-Revenda".
- **Carimba a data de entrada** (`:272`) mesmo com estoque inicial 0.
- Aplica estilo/validação da coluna M e recalcula I e L (`:274-275`).
- **Não valida EAN duplicado** (a checagem só existe no onEdit, que não dispara para escrita via script).

### 2.2 Geração de ID (`obterProximoID`, `:505-516`; `gerarIDSequencial`, `:532-538`)
- ID = maior número encontrado na coluna B (extraindo só dígitos de cada célula) + 1, com `padStart(4,'0')`.
- O ID é calculado **na abertura do formulário** (`:168`) e enviado pelo cliente; não há reserva nem lock.
- `gerarIDSequencial` só preenche se B estiver vazia (onEdit na descrição e importação de NF).
- Consequência: excluir o produto de maior ID faz o ID ser reutilizado.

### 2.3 EAN
- Guardado como texto (`@`). Na digitação manual (onEdit na coluna A), compara só dígitos com todas as outras linhas; se duplicado → alerta, **apaga o EAN digitado** e posiciona na linha original (`:595-613`).
- Na importação XML: `cEAN`; se vazio ou "SEM GTIN" usa `cProd`; mantém só dígitos; se < 8 dígitos, descarta (`:725-728`). Indexação de EANs existentes só considera ≥ 8 dígitos (`:717`).
- No PDF, EAN é reconhecido por regex `789\d{10}|790\d{10}|\d{13,14}` (`:846`).

### 2.4 Fator / fracionamento (`extrairFator`, `:518-530`)
Aplica-se sobre "embalagem + nome":
1. Remove contagens de cápsulas/comprimidos/drágeas/softgel/gomas/pastilhas/sachês (ex.: "c/ 60 caps") e pesos/volumes (`\d+ kg|g|mg|mcg|l|ml`).
2. `N x M` → N.
3. `c/ N`, `cx N`, `caixa N`, `fardo N`, `pack N`, `display N` → N.
4. `N unidade(s)` → N.
5. Caso contrário, 1.

Quando roda: onEdit na coluna E (sobrescreve F, mesmo que o usuário tenha digitado F à mão) (`:627-631`); importação XML/PDF (usa só o nome do produto, `:730,865`). No formulário de cadastro/edição o fator é digitado, sem extração.

### 2.5 Preço fracionado e margem (`atualizarValoresEMargem`, `:540-569`)
- Se H > 0: I = H ÷ F (F ≤ 0 → I = H). Se H ≤ 0: limpa I.
- Se J > 0 e H > 0: L = (J − I) ÷ J (margem sobre o preço de venda, formato `0.0%`). Senão limpa L.
- Roda em **qualquer** edição da linha (onEdit), cadastro, edição, importação, estorno e reformatação. Não depende da data.
- Erros são engolidos (`catch (e) {}`, `:568`).
- Como ADMINISTRATIVO escreve J em outra planilha via script, o onEdit do ESTOQUE **não dispara** e L fica desatualizada até a próxima edição da linha. Ambíguo se ADMINISTRATIVO recalcula L; nos trechos vistos ele só escreve J.

### 2.6 Carimbo da data da última entrada (`carimbarDataEntrada`, `:575-578`)
Grava `dd/MM/yyyy` (texto, fuso do script) na coluna G.

**Carimba em:**
- cadastro manual pelo formulário (`:272`), mesmo com estoque 0;
- importação XML, tanto em produto existente quanto em produto novo (`:740,754`);
- importação por Chave de Acesso (via `processarXMLNFe`, `:946`);
- importação PDF, em produto existente e novo (`:876,890`).

**Não carimba em:**
- edição pelo formulário (`salvarAlteracaoProduto`, `:452-471`), mesmo que o estoque aumente;
- digitação direta na planilha (onEdit), inclusive quando um produto novo é criado digitando na linha;
- estorno de nota (`:986-1052`, `:1072-1145`);
- baixa de venda do CAIXA.

### 2.7 Entrada de mercadoria × edição

| | Entrada (XML/PDF/Chave) | Edição (formulário) |
|---|---|---|
| Estoque | soma `qCom × fator` ao K atual (`:733-734`) | sobrescreve K com o valor digitado (`parseInt`) |
| Preço entrada H | XML: `vUnCom`; PDF: `pUnit × fator` | valor digitado |
| Preço fracionado I | calcula **média ponderada** `((qAtual·pAtual)+(qtdEnt·pUnEnt))/qTot` e grava em I (`:733,736`)… **mas logo em seguida `atualizarValoresEMargem` sobrescreve I com H÷F** (`:739`). Na prática a média ponderada é descartada (bug, §8) | H÷F |
| Descrição | PDF **renomeia** o produto existente com o texto do cupom (`:869`) | valor digitado (sem `limparDescricao`) |
| Data G | carimba | não carimba |
| Destino M | preenche "1-Revenda" se vazio | valor do select |
| Produto não encontrado | cria linha nova: EAN, descrição, E="Unidade", F=fator, H, I, K=qtdEnt, M="1-Revenda", ID automático (`:741-755`, `:877-892`). Não define categoria nem preço de venda | — |

Casamento de produto na entrada:
- XML: **só por EAN** (`:731`).
- PDF: EAN → descrição normalizada exata → **substring nos dois sentidos** sobre qualquer produto (`:861-864`), o que é arriscado.

### 2.8 Importação em lote (entrada de NF)
Menu `abrirJanelaEntradaNota` (`:683-691`) com três caminhos:
- **XML NF-e** (`processarXMLNFe`, `:711-758`): parse por regex de `<det>`, `cEAN`, `cProd`, `xProd`, `qCom`, `vUnCom`. Não lê impostos, frete nem descontos.
- **PDF** (`processarPDF`, `:809-900`): converte em Google Docs com OCR (Drive API avançada v3 `Drive.Files.create`), lê o texto e manda o arquivo para a lixeira. Corta o rodapé a partir de "DADOS ADICIONAIS/INFORMAÇÕES COMPLEMENTARES" (`cortarRodapeNota`, `:788-791`), quebra linhas antes de EANs, mescla linhas "descrição" + "só valores" (`mesclarLinhasProdutoPDF`, `:911-931`), ignora linhas <5 caracteres ou iniciadas por danfe/nota fiscal/cnpj/total/subtotal. Preço: se houver `Nx preço` usa esse par; senão o **último** número `\d+[.,]\d{2}` da linha, com qtd 1. Exige nome normalizado ≥3 caracteres e preço >0. Se nada for reconhecido, lança erro. Pensado para cupom fiscal estreito, não para DANFE larga (comentário `:823-826`). `extrairChaveAcessoPDF` (`:802-807`) está definida mas **não é chamada**.
- **Chave de acesso** (`abrirJanelaImportarChave`, `:933-954`): 44 dígitos, busca `https://ws.meudanfe.com.br/api/v1/get/xml/{chave}` (serviço externo de terceiro). Aceita a resposta se o HTTP for 200 **e** o texto contiver `'<xml'`. Um XML de NF-e normalmente começa com `<?xml`, que não contém a substring `<xml`, então essa checagem provavelmente sempre falha. **Ambíguo**: depende do formato de resposta da API.

**Estorno de nota** (`estornarXMLNFe` `:986-1052`, `estornarPDF` `:1072-1145`): localiza pela mesma lógica (XML por EAN ou descrição/substring; PDF igual) e subtrai `qtd × fator` de K. **Se o resultado for ≤ 0, apaga a linha inteira do produto** (`:1041-1050`). Não reverte preço nem data.

Não existe importação CSV/planilha de produtos.

### 2.9 Limpeza de descrição (`limparDescricao`, `:476-488`; `normalizarTexto`, `:490-493`)
Remove: texto "abaixo estão listados…:", "Total:", números no formato preço (`\d+[.,]\d{2}`), EANs de 13–14 dígitos, **qualquer número de exatamente 4 dígitos isolado**, as palavras Unidade/xUnidade/UN/xUN/KG/PC, "Nx", e prefixos numéricos/pontuação. Colapsa espaços.
Aplicada no cadastro pelo formulário, no onEdit da coluna C e nas importações; **não** na edição pelo formulário.
`normalizarTexto` = limparDescricao + minúsculas + sem acento + só `[a-z0-9 ]`.

### 2.10 Busca
- **Modal de edição** (`pesquisarProdutosModal`, `:57-122`): pontua cada linha. EAN ou ID exatos (ou ID com zeros à esquerda) valem +100. Na descrição normalizada: igual +90, palavra inteira +70, prefixo +50, contém +30. Ordena por pontuação; se houver 1 resultado, abre direto (`:375-379`).
- **Busca global** (`buscarProdutoGlobal`, `:124-148`): pinta de amarelo `#FFF2CC` as linhas onde descrição contém o termo, ID/EAN exato **ou qualquer célula A–M contém o termo**. Digitar "limpar" ou deixar vazio limpa. `limparBusca` (`:150-157`) remove as cores.

### 2.11 Exclusão (`deletarProduto`, `:639-678`)
Prompt com o termo; percorre **de baixo para cima** e pega o **primeiro** que casar (descrição *contém*, ID exato/com zeros, EAN exato); confirma com ID/nome; faz `deleteRow`. Não há exclusão lógica, verificação de vendas/histórico vinculados nem log.

### 2.12 Destino e categorias
- Destino: 3 valores fixos com prefixo numérico (`:45`). **Nenhum código nos 4 arquivos (nem nos outros .gs) usa o destino em cálculo**: só é gravado e validado.
- Categoria: texto livre, sem cadastro nem lista. O PDV usa "Geral" como padrão quando vazia (`04-CAIXA.gs:596`).

### 2.13 Estoque Mínimo automático (`:1475-1670`, não citado no prompt)
- Pré-requisito: N5 = "ESTOQUE MÍNIMO" (`:1578`). A função `adicionarColunaEstoqueMinimo`, citada em mensagens (`:1579`; `02-COMPRAS.gs:449,478`), **não existe em nenhum .gs**.
- Lê o Histórico (1ª aba) e ignora categorias exatamente `"CREDIARIO"`, `"Assinatura"` e `"Serviço"` (`:1601`). Casa venda com produto **por descrição** (igualdade = 100, substring = 80, mínimo 80), não por ID/EAN (`:1609-1621`). Soma `receita += G` e `qtdVendida += H`. **Ambíguo** se G (VALOR) é unitário ou total da linha.
- Período em semanas = (data mais recente − mais antiga de **todo** o histórico) ÷ 7 dias, mínimo 1 (`:1639`). Só conta datas que chegaram como objeto `Date`.
- Curva ABC: ordena por receita e acumula; A se ≤80%, B se ≤95%, senão C (`:1641-1650`).
- Mínimo = `ceil(qtdVendida / semanas × semanasBase × {A:3, B:2, C:1})`. Só escreve se > 0: **mínimos antigos nunca são zerados** (`:1655-1664`).
- Execução manual pergunta o `semanasBase` e salva nas propriedades; o gatilho semanal usa o valor salvo.

---

## 3. Serviço (bloco N–S do ESTOQUE, `01-ESTOQUE.gs:1170-1473`)
- **Estrutura**: uma linha por material. Colunas: código, nome, material (texto livre, **sem vínculo com produto do estoque**), custo unitário, qtd, % mão de obra. Nome e % se repetem em cada linha do serviço (`:1268-1270`).
- **Código**: `SERV-` + (maior número existente + 1) com 3 dígitos (`:1203-1215`). Pode ser reutilizado após exclusão.
- **Cálculo** (na leitura; o preço final **não é gravado**, `:1239-1244`): totalMateriais = Σ custo × qtd; valorMaoObra = totalMateriais × %/100; precoFinal = totalMateriais + valorMaoObra. A % vem da **primeira** linha do grupo (`:1230`).
- **Validações**: nome obrigatório; ao menos 1 material; material precisa de descrição e custo > 0; qtd padrão 1; % padrão 50 no formulário (`:1329`), `parseFloat || 0` no servidor (`:1262`).
- **Gravação**: para cada material, procura a primeira linha ≥6 com N vazia (preenche buracos) (`:1264-1266`).
- **Sem edição**: só cria e exclui. A exclusão limpa o conteúdo N:S das linhas daquele código (`:1280-1297`) e deixa buracos.
- **Duplicidade**: existe **outro cadastro de serviços idêntico** no ADMINISTRATIVO, aba Markup, colunas S+ (`03-ADMINISTRATIVO.gs:2436-2476`), com numeração `SERV-` independente, então os códigos podem colidir entre as duas planilhas. Não achei no CAIXA leitura de nenhum dos dois blocos (grep por `SERV-`/`COL_INICIO_SERVICOS` em `04-CAIXA.gs` sem resultado). **Ambíguo** como o PDV vende serviço: ver a análise do CAIXA.

---

## 4. COMPRAS / Cotação (`02-COMPRAS.gs`)
Planilha própria e separada. Fluxo descrito no cabeçalho (`:9-22`).

### 4.1 Fornecedores (`:122-387`)
- Campos: `id` (`"forn_" + timestamp`, `:157`), `nome`*, `representante`*, `contatoPosVenda`*, `contatoCotacao`* (checkbox "mesmo contato" copia o pós-venda), `formaPagamento` ∈ {Boleto, Boleto Parcelado, Cartão, PIX, Dinheiro, Outros}, `prazoEntrega` e `prazoFaturamento` como **texto** ("Até N dias" | "Negociável" | ""), `pedidoMinimo` (R$, float). \* obrigatórios, validados só no cliente (`:314-318`).
- CRUD completo (salvar novo ou editar por id, excluir). **Nome não é único**, e o resto do módulo liga fornecedor **pelo nome normalizado**, não pelo id (`:1116,1171`).
- Armazenamento: JSON numa única DocumentProperty (limite de tamanho por valor do Apps Script, cerca de 9 KB, que pode estourar com muitos fornecedores).

### 4.2 Montagem da lista de produtos a cotar
- `puxarProdutosAbaixoDoMinimo` (`:452-504`): lê ESTOQUE A:N; traz para o resumo (coluna PRODUTO + ESTOQUE ATUAL) os produtos com `N > 0` e `K < N`. Não duplica (compara nome sem acento/maiúsculo). **Não checa o cabeçalho N5**, então lê o que estiver em N.
- `atualizarEstoqueDaCotacao` (`:506-533`): para cada produto do resumo, busca no ESTOQUE por **similaridade de nome** (`calcularScoreSimilaridade`, `:397-409`: igual 100, substring 80, senão proporção de palavras em comum × 60, limiar ≥ 40, `:435`) e grava ESTOQUE ATUAL (`parseInt`).
- Produtos também podem ser digitados à mão na coluna PRODUTO, e o recálculo cria linhas para produtos cotados que ainda não estão no resumo (`:917-923`).

### 4.3 Exportar / importar cotação
- **Exportar** (`:574-613`): pergunta o nome do fornecedor (texto livre) e **cria uma planilha Google nova no Drive** com PRODUTO/PREÇO/OBS e os produtos do resumo. Mostra o link. O comentário de `mesclarCotacaoNaAba` diz que o nome do fornecedor iria para a linha 1, mas o código **não grava** (`:597-599`) e a importação exige o fornecedor escolhido (`:679`).
- **Importar** por link/ID (`:629-635`) ou por .xlsx (Drive API v2 `Drive.Files.insert` com `convert:true`, apagado depois, `:645-670`). Lê a 1ª aba da linha 2 em diante, A produto e B preço, **só linhas com preço > 0** (`:687-688`), e **empilha um bloco novo** na área crua (faixa preta + linhas). Reimportar o mesmo fornecedor **duplica** o bloco; não há substituição.

### 4.4 Recalcular (`recalcularCotacaoCompleta`, `:866-955`)
- Pergunta as semanas de cobertura (inválido → **4**, `:868`).
- Lê a área crua e agrupa ofertas por nome normalizado (sem acento, maiúsculo). Ordena por preço: 1ª = MENOR PREÇO / FORNECEDOR VENCEDOR, 2ª = SEGUNDA OPÇÃO / SEGUNDO FORNECEDOR (limpa se não houver).
- **Quantidade sugerida**: `qtdBase = VENDA SEMANAL MÉDIA × semanas`; `fator = clamp(1 − (preçoCotado − últimoPreço)/últimoPreço, 0,5, 2)` (1 se não houver último preço) (`:858-864`); `QTD SUGERIDA = round(qtdBase × fator)`.
- **A coluna VENDA SEMANAL MÉDIA nunca é preenchida por código** (grep: só é lida em `:938`). Precisa ser digitada à mão; se ficar vazia, a sugestão é 0.
- **A sugestão ignora o estoque atual**: não subtrai K e não usa o estoque mínimo.

### 4.5 Finalizar pedido (`:1012-1231`)
- A lista de fornecedores vem das faixas pretas da área crua (`:1022-1037`), inclusive dos que não venceram nada.
- Itens: todas as ofertas daquele fornecedor, cruzadas com o resumo. `qtdSugerida` só aparece se ele for o vencedor; o checkbox "só os que ele ganhou" vem marcado (`:1262`).
- **2ª opção** (`moverItemParaSegundaOpcao`, `:1125-1154`): no resumo, troca FORNECEDOR VENCEDOR e MENOR PREÇO pela 2ª opção. Não limpa a 2ª opção (continua apontando para o novo vencedor) e não recalcula QTD SUGERIDA.
- **Pedido mínimo**: o cliente avisa quando o total > 0 e abaixo do mínimo, com as opções "Forçar até o mínimo" ou "Enviar assim mesmo". Forçar multiplica todas as quantidades por `mínimo/total` com `ceil` (`:1174-1178`).
- **Gravação**: linhas com qtd > 0 vão para HISTÓRICO › "HISTORICO PEDIDOS" (`[hoje, fornecedor, produto, qtd, preço, valor, estoqueAtual]`). Antes, **apaga todas as linhas de hoje daquele fornecedor**, de qualquer produto (`:1204-1216`); o comentário fala em "fornecedor + produto". Também grava QTD A PEDIR e VALOR DO PEDIDO no resumo, por nome do produto (se dois fornecedores recebem o mesmo produto, o último sobrescreve).
- **Não há integração de escrita com o ESTOQUE**: finalizar o pedido não dá entrada de mercadoria nem altera preço. A entrada acontece depois, pela importação de NF no ESTOQUE.

### 4.6 Exportar texto e limpar ciclo
- `gerarTextoPedido` (`:1462-1489`): texto monoespaçado (descrição até 33 caracteres, qtd, preço, TOTAL) a partir do histórico de pedidos **de hoje**, para copiar e colar (WhatsApp). O comentário fala em "um arquivo por fornecedor", mas é só um textarea.
- `limparCotacaoParaProximoCiclo` (`:968-1005`): para linhas com QTD A PEDIR > 0, grava ÚLTIMO PREÇO PAGO = MENOR PREÇO; limpa MENOR…VALOR; apaga a área crua (desfaz mesclagem, conteúdo e formato). **Mantém** PRODUTO, ESTOQUE ATUAL, VENDA SEMANAL MÉDIA e ÚLTIMO PREÇO PAGO.
- `limparPedidosDuplicadosDeHoje` (`:1553-1583`): faxina manual; mantém a última ocorrência de fornecedor + produto de hoje.

---

## 5. Usuários, permissões e autenticação

### 5.1 Perfis / funções
- **Não existem perfis ou roles**. "FUNÇÃO" (coluna B) é texto livre informativo, sem efeito em nenhuma regra (`06-USUARIO.gs:44-45`).
- Permissão (coluna E) é uma destas duas formas:
  - `"ADMIN"`: checkbox "ADM Principal (Acesso Total)", que marca todos os módulos (`:59-60,84`);
  - lista separada por vírgula, em maiúsculas, dos módulos: `CAIXA, SAIDAS, ESTOQUE, CLIENTES, COMPRAS, HISTORICO, RELATORIO, USUARIO, ADMINISTRATIVO` (`:62-70`).
  - `07-MENU.gs:132` aceita também `"TODOS"` (legado; a UI nunca grava isso).
- **O que cada permissão libera**: apenas **abrir o link da planilha do módulo** a partir do MENU (`07-MENU.gs:132-133`). Não há permissão por ação (ler × escrever, excluir, ver custo…). Dentro das planilhas nenhum código verifica usuário.

### 5.2 Cadastro / edição / exclusão (`06-USUARIO.gs`)
- Novo (`:10-139`, `salvarNovoUsuario` `:462-469`): nome\*, função, login\*, senha\*, confirmação\*, ≥1 permissão\*. Validação **só no cliente**. `appendRow([nome, função, login, hash, permissões.toUpperCase()])` na **aba ativa**.
- **Sem checagem de login duplicado**, sem política de senha (senha só de espaços é aceita no cadastro, `:101`), login não normalizado além de `trim`.
- Edição (`:234-457`, `:471-486`): seleciona o usuário por índice. Senha em branco mantém a atual; senha nova só é aplicada se `trim() !== ""` (`:481`). Na UI, permissão contendo "ADMIN" ou "TODOS" em **qualquer posição** (`indexOf`) é tratada como ADM (`:373`).
- Exclusão (`:144-229`, `:488-498`): `deleteRow` pelo **número da linha** enviado pelo cliente (≥7). Se a planilha mudar entre abrir o diálogo e confirmar, apaga o usuário errado.
- `onOpen() {}` vazio (`:506`).

### 5.3 Hash de senha
`gerarHash` (`06-USUARIO.gs:500-504` e cópia em `07-MENU.gs:146-150`): **SHA-256 simples, sem sal e sem iterações**, via `Utilities.computeDigest(SHA_256, texto)` (sem charset explícito, usa o padrão do Apps Script), em hex minúsculo. Senha vazia → `""`.

### 5.4 Login e navegação (MENU)
1. A planilha MENU tem botões desenhados ligados a `btnCaixa`, `btnSaidas`, … `btnAdministrativo` (`07-MENU.gs:24-32`).
2. Cada botão abre o modal "Controle de Acesso" com login/senha (`:37-107`).
3. `validarEBuscarLink(login, senha, modulo)` (`:112-143`): abre a planilha USUÁRIOS por ID, lê C/D/E da linha 6 em diante, calcula SHA-256 da senha e procura a **primeira** linha com `login === C` (case-sensitive; login com trim só no cliente) e `hash === D`.
4. Encontrou: se E == "ADMIN" ou "TODOS" (**igualdade exata**) ou a lista contém o módulo → devolve `MAPA_LINKS[modulo]`; senão, "Acesso bloqueado para o módulo".
5. O cliente faz `window.open(url, '_blank')` e fecha o modal.
- **Não há sessão**: cada clique pede login de novo. Não há logout, bloqueio por tentativas, log de acesso nem expiração.
- **A segurança é só aparente**: o URL de cada planilha é fixo e está no código. O acesso real às planilhas depende do compartilhamento do Google Drive; quem tem o link e permissão no Drive abre sem passar pelo MENU. A planilha USUÁRIOS também não protege o próprio cadastro: quem a abre pode criar um ADMIN.
- Mensagens distintas para "Sem usuários registrados", "Usuário ou senha incorretos" e "Acesso bloqueado".
- O ESTOQUE volta ao menu por `abrirMenuExterno` (`01-ESTOQUE.gs:7-11`), que redireciona `window.top` para o ID `1QHS…`.

---

## 6. Proteção de planilha, auditoria e onEdit (nestes 4 arquivos)
- **ESTOQUE `travarPlanilha`** (`01-ESTOQUE.gs:16-26`): remove as proteções de aba existentes, protege a aba ativa inteira, deixa só o usuário efetivo como editor e desliga a edição por domínio. `destravarPlanilha` remove tudo (`:28-33`). O alerta diz "utilize os botões", mas os scripts de botão rodam **como o usuário que clica**, então para quem não é editor as escritas via botão também devem falhar. **Ambíguo** como isso funcionava na prática com mais de um operador.
- **ESTOQUE `onEdit` → `monitorarEntrada`** (`:583-634`): não é auditoria nem reversão. Para cada linha ≥6 editada:
  - aplica ou remove estilo e a validação de M (linha sem EAN e sem descrição → **limpa A–M inteira**, `:49`);
  - coluna A: checa EAN duplicado;
  - coluna C: aplica limparDescricao, gera ID e preenche E="Unidade", F=1 e M="1-Revenda" se vazios;
  - coluna E: recalcula F por `extrairFator`;
  - sempre recalcula I e L.

  Só olha a **primeira coluna** do range editado (`col`), então colar várias colunas de uma vez não dispara as regras das demais.
- **`onOpen`** do ESTOQUE só posiciona em A1 (`:4-6`). COMPRAS: `onOpen` vazio de propósito (`02-COMPRAS.gs:34-36`). USUARIO: vazio.
- **Nenhum log de auditoria** (quem alterou o quê) em ESTOQUE, COMPRAS, USUARIO ou MENU. O mecanismo de reverter edição com backup citado no prompt é do CAIXA (`04-CAIXA.gs:2557-2660`), fora deste escopo.
- Não há `LockService` em nenhum desses arquivos: gerar ID, achar a próxima linha e montar códigos SERV podem colidir com uso simultâneo.

---

## 7. O que diverge ou não aparece no `prompt-claude-code-cfauto.md`

### 7.1 Módulos ausentes no prompt
- **COMPRAS** (§4): fornecedores com contatos, prazos, forma de pagamento e pedido mínimo; cotação multi-fornecedor importada de planilhas/xlsx; menor preço e 2ª opção; quantidade sugerida (venda semanal × semanas × fator de preço limitado a [0,5; 2]); pedido mínimo com "forçar"; histórico de pedidos; texto do pedido para WhatsApp; "último preço pago" entre ciclos; puxar produtos abaixo do estoque mínimo. Tabelas sugeridas: `fornecedor`, `cotacao`/`cotacao_oferta`, `pedido_compra`/`pedido_compra_item`, e `ultimo_preco_pago` (por produto, ou derivado do histórico de pedidos).
- **USUARIO + MENU** (§5): login, usuários e permissões por módulo, navegação. O prompt pede "controle de acesso adequado", mas não descreve o modelo. O mínimo a replicar: usuário (nome, função, login único, hash) + conjunto de módulos permitidos + flag admin. Os módulos originais são CAIXA, SAIDAS, ESTOQUE, CLIENTES, COMPRAS, HISTORICO, RELATORIO, USUARIO e ADMINISTRATIVO; os da UI do prompt são PDV, Estoque, Saídas, Histórico e CFAUTO, então **o mapeamento precisa ser decidido** (ex.: ADMINISTRATIVO → CFAUTO, CAIXA → PDV).
- **CLIENTES** e **RELATORIO** existem como planilhas no MENU. O prompt só cita "Cliente" dentro de Venda e "Crediário". RELATORIO não tem código na referência.
- O prompt diz "5 planilhas"; o MENU lista 9 + menu (§1.1).

### 7.2 Funcionalidades do ESTOQUE ausentes no prompt
- Entrada de mercadoria por **XML NF-e, PDF/OCR e Chave de Acesso** (API externa meudanfe), e **estorno de nota** (§2.8).
- **Estoque Mínimo automático** por Curva ABC + média semanal, com job semanal (§2.13). O prompt trata "alerta de estoque baixo" como roadmap não construído, mas o original já tem o cálculo do mínimo e o COMPRAS usa esse mínimo.
- Busca com ranking, busca global com destaque, limpeza automática de descrição, extração automática de fator pelo nome, bloqueio de EAN duplicado e travar/destravar planilha.

### 7.3 Divergências de regra
- **Preço fracionado**: o prompt diz "recalculado sempre que preço de entrada ou data de entrada mudam". No original é recalculado em qualquer edição da linha e **não depende da data**. Na entrada de NF existe uma média ponderada que é **sobrescrita** (§2.7). Decidir se o custo deve ser média ponderada (mais correto para CMV) ou último custo ÷ fator (o comportamento efetivo hoje).
- **Carimbo da data**: bate com o prompt (edição não carimba), mas o original também carimba no **cadastro manual com estoque 0** e **não carimba** produto criado digitando direto na planilha.
- **Margem** (coluna L) = (venda − custo fracionado)/venda. O prompt só diz "calculada", sem fórmula.
- **Destino**: o prompt lista os 3 valores; no original eles têm prefixo numérico ("1-Revenda"…) e **não afetam nenhum cálculo**. Decidir se Uso/Consumo e Matéria-Prima devem sair do PDV, da Curva ABC ou do Markup (hoje não saem).
- **Serviço**: o prompt diz "bloco N+ do ESTOQUE". Na verdade há **dois cadastros** (ESTOQUE N–S e ADMINISTRATIVO/Markup S+), com numeração SERV independente, e a coluna N do ESTOQUE **conflita** com "ESTOQUE MÍNIMO". Material de serviço é texto livre com custo digitado (sem ligação com Produto). Não há edição de serviço. O preço final não é persistido.
- **Categoria**: texto livre, sem tabela.
- **ID**: 4 dígitos sequenciais (texto). **Código de serviço**: `SERV-NNN`.
- **Estoque** é tratado como inteiro em vários pontos (`parseInt` no formulário, `01-ESTOQUE.gs:266,463`, e no CAIXA), mas a entrada de NF pode gerar fração (`qCom` decimal × fator). No modelo novo, decidir `Numeric` vs `Integer`.
- Histórico de vendas × produto: o estoque mínimo casa **por descrição**, não por ID. O prompt (Curva ABC) diz "agrupado por ID de produto", que é o correto.

---

## 8. Bugs, gambiarras e pontos frágeis a NÃO repetir

**ESTOQUE**
1. **Média ponderada de custo descartada**: `processarXMLNFe`/`processarPDF` gravam a média em I e em seguida `atualizarValoresEMargem` sobrescreve com H÷F (`01-ESTOQUE.gs:736→739`, `:872→875`). Em produto existente, a quantidade usa o fator extraído do nome da NF, mas I usa o F já cadastrado, o que é inconsistente.
2. **Coluna N com dois significados** (serviços × estoque mínimo, `:1186` × `:1578,1661`; `02-COMPRAS.gs:467`). Um "estoque mínimo" numérico em N aparece como "serviço"; um "SERV-001" em N vira mínimo 0 no COMPRAS.
3. **`deleteRow` apaga a linha inteira** (`:672,1050,1143`), inclusive o bloco de serviços N–S e o estoque mínimo que estiverem na mesma linha, e **desloca linhas**. O CAIXA baixa estoque pelo **número de linha** guardado (`04-CAIXA.gs:313-314,2138`), então excluir um produto com o PDV aberto pode dar baixa no produto errado. Usar chave primária e nunca posição.
4. **Estorno apaga o produto** quando o estoque fica ≤ 0 (`:1041,1134`). O cadastro some.
5. **Casamento por substring de nome** (PDF, estorno, estoque mínimo, COMPRAS com limiar 40): associa com facilidade o produto errado. O PDF ainda **renomeia** o produto existente (`:869`).
6. **Parse de moeda** remove todos os pontos (`:264`): "10.5" vira 105. Aceitar Decimal com locale explícito.
7. **Exclusão por "contém"**: `deletarProduto` apaga o primeiro match de baixo para cima (`:656-667`).
8. `limparDescricao` apaga dados legítimos: números de 4 dígitos ("Bateria 5000 mAh"), medidas "2,50", "UN", "KG" (`:476-488`). Útil só para OCR de cupom; não aplicar em cadastro manual.
9. Checagem da Chave de Acesso por `'<xml'` (`:945`) provavelmente nunca passa. Dependência de API de terceiro sem contrato.
10. `obterProximaLinhaVazia` usa só a coluna C vazia (`:495-503`): uma linha com EAN e sem descrição é sobrescrita.
11. ID e SERV gerados por max+1 sem lock, com reutilização após exclusão. Usar autoincremento/sequence e nunca reusar.
12. EAN duplicado só é checado no onEdit manual; formulário e importação não checam. Usar UNIQUE (parcial, permitindo nulo).
13. Data gravada como **texto** `dd/MM/yyyy` (`:576-577`); o estoque mínimo ignora datas não-`Date` (`:1607`). Usar `date` desde a borda.
14. Erros engolidos: `catch(e){}` em `atualizarValoresEMargem` (`:568`); baixa de estoque do CAIXA só loga.
15. `adicionarColunaEstoqueMinimo` é citada mas não existe. `extrairChaveAcessoPDF` existe mas não é usada.
16. Estoque mínimo nunca zera valores antigos (`:1660`) e usa o período do histórico inteiro, o que dilui produtos novos.
17. Uso de `getActiveSheet()` em quase tudo: se o usuário estiver em outra aba, o script escreve nela.

**COMPRAS**
18. **VENDA SEMANAL MÉDIA nunca é calculada** (só lida em `:938`). A sugestão de compra depende de digitação manual e **ignora o estoque atual**. No sistema novo, calcular a partir do Histórico por produto (ID) e descontar o estoque.
19. Fornecedor ligado **por nome**, não por id; nome não é único; tudo guardado num JSON em DocumentProperties (limite de tamanho, sem integridade).
20. "Anti-duplicação" do finalizar apaga **todos** os pedidos do dia daquele fornecedor, não só do produto (`:1204-1216`). Refinalizar com menos itens perde linhas. Usar pedido com id e status (rascunho/finalizado).
21. ÚLTIMO PREÇO PAGO = MENOR PREÇO do resumo (`:984-985`), não o preço efetivamente pedido (errado quando se pediu de um fornecedor não vencedor). QTD A PEDIR e VALOR são gravados por nome de produto e sobrescritos se dois fornecedores recebem o mesmo item.
22. Reimportar a cotação de um fornecedor duplica o bloco; o recálculo passa a contar as ofertas em dobro.
23. Área crua depende de "B vazio = faixa de fornecedor", um formato posicional frágil. O resumo, pelo menos, é mapeado por cabeçalho (padrão bom).
24. `garantirEstruturaCotacao` renomeia a 1ª aba qualquer para "Cotação" (`:61-62`).
25. Mistura Drive API v2 (`Drive.Files.insert`, `:654`) e v3 (`Drive.Files.create`, `01-ESTOQUE.gs:814`).
26. Mensagens e comentários desatualizados (fornecedores em "colunas P", "3 abas", "um arquivo por fornecedor").

**USUARIO / MENU**
27. **SHA-256 sem sal**: vulnerável a rainbow table e senhas iguais geram hashes iguais. Usar argon2/bcrypt (`passlib`/`argon2-cffi`). Se for migrar usuários existentes, aceitar o hash legado SHA-256 uma vez e re-hashear no login.
28. Login sem unicidade; o primeiro match vence (`07-MENU.gs:124-129`). Tornar UNIQUE, com normalização (casefold) definida.
29. Autorização só no portão do menu. Links fixos e públicos no código (`07-MENU.gs:9-19`); nada é checado dentro dos módulos. No app desktop, checar a permissão na **camada de serviço**, não só esconder a aba na UI.
30. Checagens divergentes de ADMIN: MENU usa igualdade exata "ADMIN"/"TODOS", a UI de edição usa `indexOf`. Permissões como string CSV em vez de relação N:N.
31. Exclusão e edição por **número de linha** vindo do cliente (`06-USUARIO.gs:435,491`).
32. Validação apenas no cliente (HTML), sem política de senha; nomes injetados em HTML sem escape (`06-USUARIO.gs:176,341`).
33. Comentários de layout divergentes (A=NOME × A=ID; linha 6 × 7) entre `06-USUARIO.gs:3-4` e `07-MENU.gs:120-121`.
34. `gerarHash` duplicada em dois projetos. Sem sessão, logout, bloqueio por tentativas ou log de acesso.
35. Nenhum dos 4 arquivos tem auditoria. O prompt pede log de auditoria para dados financeiros; recomenda-se estender a custo/preço/estoque de Produto e a usuários/permissões.
