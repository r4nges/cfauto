# Prompt para o Claude Code — CFAUTO em Python

Cole o conteúdo abaixo no Claude Code para iniciar a construção do sistema.

---

## Contexto

Você vai reconstruir em Python, do zero, um sistema de gestão para varejo/serviços chamado **CFAUTO**, hoje implementado em Google Sheets + Apps Script (5 planilhas interligadas, sem banco de dados central). O objetivo é migrar toda a lógica de negócio para uma **aplicação desktop própria**, com banco de dados local, mantendo o comportamento e as regras já validadas no sistema original. Isso é para um hackathon (Aceleração de Viçosa), então a aplicação precisa rodar de ponta a ponta (cadastro → venda → relatórios) e ser demonstrável — o usuário abre um executável/app na própria máquina, sem depender de navegador ou servidor externo.

## Stack

- **Interface**: Python com **PySide6** (Qt para Python). Use QMainWindow com navegação por abas/menu lateral entre os módulos (PDV, Estoque, Saídas, Histórico, CFAUTO). Para os gráficos dos painéis (DRE, Balancete, Curva ABC, Comparador de Investimento), embuta matplotlib nos widgets Qt (`FigureCanvasQTAgg`) ou use QtCharts — escolha o que for mais rápido de integrar sem perder qualidade visual.
- **Banco de dados**: SQLite embutido (um único arquivo `.db` local, sem servidor separado), acessado via **SQLAlchemy** como ORM.
- **Migrations**: Alembic, mesmo em SQLite, para não travar quando o modelo de dados evoluir durante o hackathon.
- Estruture o projeto com separação clara por camada e por domínio: uma camada de dados/lógica de negócio (`caixa/`, `estoque/`, `saidas/`, `historico/`, `cfauto/`) totalmente independente da interface, e uma camada de UI (`ui/`) que só consome essa lógica. Isso evita que regra de negócio fique espalhada dentro de código de tela do Qt.
- A camada de negócio deve ser testável sem subir nenhuma janela — os testes automatizados (ver "O que entregar") batem direto nela, não na UI.

## Modelo de dados — substituindo as 5 planilhas

O sistema original tinha 5 planilhas do Google Sheets, cada uma com seu papel. Migre isso para tabelas relacionais no banco (não recrie "planilhas" como conceito — isso é herança do sistema antigo, não um requisito). As referências abaixo (nomes de planilha, letras de coluna) são só para você entender de onde vem cada dado; modele como tabelas normalizadas.

### Produto (origem: planilha ESTOQUE)
- EAN / código de barras
- ID interno
- Descrição, categoria
- Modo/embalagem, fator (quantas unidades por pacote)
- Data da última entrada (carimbada automaticamente só quando entra mercadoria nova — nunca em edição manual de quantidade)
- Preço de entrada (custo do pacote fechado)
- **Preço fracionado = preço de entrada ÷ fator** — é o custo real por unidade, recalculado automaticamente sempre que preço de entrada ou data de entrada mudam
- Preço de venda (calculado pelo módulo de Markup, ou definido manualmente)
- Estoque (quantidade)
- Margem (calculada)
- Destino/motivo: Revenda, Uso/Consumo, ou Matéria-Prima

### Serviço (origem: bloco de colunas N+ da planilha ESTOQUE)
Serviços não são produtos — não têm baixa de estoque quando vendidos, porque o custo dos materiais já está embutido no preço calculado no cadastro.
- Código do serviço (SERV-001, SERV-002...)
- Nome
- Um serviço pode ter **vários materiais**: cada material tem custo unitário e quantidade usada
- % de mão de obra sobre o custo total dos materiais
- Preço final = total de materiais + (% mão de obra × total de materiais)

### Bem Físico (origem: bloco de colunas da aba Markup do CFAUTO)
- Código (BEM-001, BEM-002...)
- Descrição/tipo (Móvel, Intangível, Outros)
- Valor
- Data de cadastro
- Alimenta o Ativo Não Circulante do Balancete.

### Venda / Movimento de Caixa (origem: planilha CAIXA, linha por venda)
- Produto ou serviço vendido, EAN, descrição, categoria
- Preço, quantidade
- Forma de pagamento
- Dias a liquidar (número, ou flag "FUTURO" para parcela de contrato ainda não realizada)
- Taxa (R$) cobrada na transação
- Data/hora em que o dinheiro efetivamente cai na conta (pode ser calculada) — trate isso como campo derivado, não texto livre como no Sheets
- Data/hora da venda
- Cliente

Regras de cálculo na hora da venda:
- **calcularTaxaELiquidacao**: calcula taxa de cartão e prazo de liquidação conforme forma de pagamento.
- Venda de produto: busca preço e estoque no cadastro de Produto, dá baixa de estoque em tempo real.
- Venda de serviço: busca no cadastro de Serviço, **não** dá baixa de estoque.
- **Venda Externa (marketplace/delivery)**: até 4 deduções — taxa da plataforma, frete, desconto, motoboy. Pode opcionalmente vincular a um produto real do estoque (nesse caso dá baixa).
- **Contrato/Assinatura**: gera todas as parcelas futuras de uma vez, como receita recorrente. A 1ª parcela conta como venda de hoje; as demais são gravadas com flag FUTURO e ficam inativas até a data de vencimento chegar.
- **Crediário** (Receber Pagamento de Cliente): venda a prazo, com troco e taxa.

### Fechamento de Caixa
- Ao fechar, gera um resumo por forma de pagamento (Dinheiro, PIX, Débito, Crédito, Crediário, Externa).
- Arquiva todas as vendas do período em Histórico.
- Limpa o caixa aberto, **exceto** as linhas marcadas FUTURO, que devem ser preservadas e continuar ativas depois do fechamento.

### Histórico (origem: planilha HISTÓRICO — vendas já fechadas)
- Mesma estrutura de Venda, mas com: protocolo/ID da sessão de caixa que gerou o fechamento, valor bruto separado de valor líquido (venda).
- **Importante**: aqui "recebimento" é guardado como número de **dias**, diferente do dado equivalente em Venda (que é uma data calculada). Modele como campos com semânticas explicitamente diferentes, não reaproveite o mesmo campo.
- É a fonte principal do DRE, da Curva ABC e do cálculo de CAGR nos indicadores.

### Conta a Pagar (origem: planilha SAÍDAS)
- ID, data de registro, categoria, descrição, valor
- Parcela (ex: "3/12")
- Data de vencimento
- Status: PAGO / PENDENTE
- Repetição: sim/não
- Observações — no sistema original isso guardava texto livre tipo "Juros: R$ X" e "Taxa Boleto: R$ X" extraído por regex. **Modele isso como campos estruturados desde o início** (juros, taxa de boleto como colunas próprias) em vez de reproduzir o hack de regex sobre texto livre.
- Categorias: Conta Fixa, Conta Variável, Despesa Prevista, Despesa Imprevista, Boleto, Empréstimo, Salário, Pró-Labore, Outros Proventos.
- Esse módulo é só consumido (leitura) pelo CFAUTO para alimentar DRE, Balancete e Saldo Real de Caixa/Banco — nunca é escrito por outro módulo.

## Módulos do CFAUTO (painel de gestão — consolida os dados acima, somente leitura sobre eles)

### Markup
- Custo de Entrada = preço fracionado do Produto (não o preço do pacote inteiro — esse foi um bug real no sistema original, veja seção de atenção abaixo).
- Rateio (R$) = gastos do mês (Conta Fixa + Conta Variável + Salário, filtrados em Conta a Pagar) ÷ receita bruta do mês, aplicado proporcionalmente ao custo de cada produto.
- Custo Real = Custo de Entrada + Rateio.
- Markup % e Preço Final são bidirecionais: editar um recalcula o outro.
- Reprocessamento em lote deve preservar markups editados manualmente e escrever o preço final de volta no cadastro do Produto.
- Tela de "Atualizar Preço" produto a produto, com preço promocional opcional.

### DRE (Demonstrativo de Resultado)
Ordem do cálculo:
1. Receita Bruta = Histórico + vendas do caixa aberto, **exceto Crediário**
2. (−) Taxas
3. = Receita Líquida
4. (−) CMV = quantidade vendida × custo fracionado **atual** (não o custo histórico da venda)
5. = Lucro Bruto
6. (−) Despesas Operacionais — filtradas pela **data de vencimento**, não pela data de registro (importante para parcelas de empréstimo caírem no mês certo)
7. (−) Despesas Financeiras (juros/taxas das contas a pagar)
8. = Lucro Líquido

### Balancete
Não existe "Balanço Patrimonial" formal que precise fechar em zero — isso foi tentado antes e removido de propósito (num sistema baseado em aproximações, forçar Ativo = Passivo + PL sempre bate errado e passa impressão de bug). Implemente como Balancete informativo:
- **Ativo Circulante** = Caixa Físico + Caixa Virtual já disponível + Mercadoria (estoque × custo fracionado) + Contas a Receber (Crediário + Cartão a cair). "Já disponível x a cair" é definido comparando a data de liquidação calculada da venda com hoje.
- **Ativo Não Circulante** = soma dos Bens Físicos.
- **Passivo** = todas as contas PENDENTES (não só Boleto/Empréstimo), classificadas em Circulante/Não Circulante conforme vencem dentro ou fora de 1 ano a partir de hoje, agrupadas por descrição (não parcela a parcela).
- **Patrimônio Líquido** = Capital Social + Lucros Retidos — únicos valores inseridos manualmente pelo usuário no sistema inteiro. Modele como configuração editável, não como dado calculado.
- **Saldo Real de Caixa/Banco** = todo o dinheiro virtual já recebido historicamente (sem filtro de período) − todas as contas já pagas historicamente. Assume que contas são pagas do banco, não da gaveta física.

### Indicadores Financeiros
ROE, ROA, Margem Bruta, Margem Líquida, Dívida Líquida, Dívida/Patrimônio, Passivo/Ativos, CAGR de Receita e CAGR de Lucro (precisa de 2+ anos de Histórico para calcular).
- ROE deve mostrar **"N/A"**, não 0%, quando o Patrimônio Líquido ainda não foi preenchido — para não dar a impressão errada de que a empresa não rende nada.

### Comparador de Investimento
Compara o CAGR de Receita da empresa com:
- BOVA11 e Dólar — via alguma fonte de cotação (o original usava GOOGLEFINANCE; aqui use uma API de mercado, ex: uma API de cotações públicas, ou permita input manual como fallback), comparando preço atual x preço de ~1 ano atrás.
- CDI — via API do Banco Central (SGS), com fallback manual se a chamada falhar.
- Poupança e CDB — taxas configuráveis pelo usuário.
- Os 4 "cartões" de renda fixa devem ser ativáveis/desativáveis individualmente, afetando o cálculo de "melhor opção".
- Gráfico de evolução mensal em "cotas" (índice 100 no primeiro mês com vendas), comparando empresa vs. BOVA11/CDI/Dólar mês a mês. Filtre datas implausíveis (fora de uma janela de ~10 anos) para uma data corrompida não distorcer o gráfico inteiro.

### Curva ABC
- Soma a receita por produto (Histórico + caixa aberto, agrupado por ID de produto), ordena do maior para o menor, calcula % acumulado.
- Classifica: **A** = produtos que somados chegam a 80% da receita; **B** = próximos até 95%; **C** = resto até 100%.
- Crediário e Assinatura ficam de fora (é uma análise sobre produto físico vendido, não sobre forma de recebimento).
- Precisa de filtro por mês/ano e visualização de rosca/pizza por classe.

## Regras transversais importantes

- **Datas**: no sistema original, datas às vezes chegavam como texto ("17/09/2026") e às vezes como objeto Date real, e o código precisava tratar os dois casos. Em Python, evite recriar esse problema: normalize toda entrada de data para um tipo `date`/`datetime` real na borda (validação de input), nunca deixe data circular como string solta internamente.
- **Auto-provisionamento e licenciamento** (funcionalidade que ainda não existia no sistema original — está no roadmap): na primeira execução do app numa máquina nova, ele deve criar sozinho o banco `.db` local e todas as tabelas/estruturas necessárias, sem configuração manual de IDs. Inclua também um sistema de licença (chave de ativação local, verificada offline ou contra um endpoint simples) que bloqueia o acesso ao app automaticamente se a assinatura vencer.
- **Alertas automáticos** (também roadmap, ainda não construído no original): notificar quando um produto com boa saída de vendas está com estoque baixo, e quando a margem líquida do mês fica negativa.
- **Parcelas FUTURO**: quando a data de vencimento de uma parcela de contrato/assinatura chega, ela precisa deixar de ser "futura" e virar uma venda ativa automaticamente. Implemente isso como um job agendado (ex: Celery beat, APScheduler, ou cron) que roda diariamente — não dependa de uma ação manual do usuário.
- **Proteção de dados / auditoria**: o sistema original tinha um mecanismo que revertia qualquer edição manual não autorizada nas linhas de dados do caixa, com backup automático. Não precisa reproduzir esse mecanismo específico (é uma gambiarra do modelo de planilha), mas garanta integridade equivalente por design: transações no banco de dados, controle de acesso adequado, e um histórico de auditoria (log de quem alterou o quê) para os dados financeiros sensíveis.

## Pontos de atenção — bugs do sistema original a **não** repetir

1. Um bug real fez o PDV ler/gravar nas colunas erradas do estoque depois que uma coluna foi inserida no meio da planilha, confundindo preço fracionado com preço de venda, e descontando o *preço* em vez da *quantidade* a cada venda. A causa raiz foi acoplamento por posição de coluna. Em Python isso não deveria existir (campos nomeados em vez de colunas posicionais) — mas fique atento a não introduzir o equivalente com índices de lista/tupla ao invés de campos nomeados ou objetos.
2. Custo de produto usado no Markup e no DRE deve **sempre** ser o preço fracionado (custo por unidade), nunca o preço de entrada do pacote fechado — esse foi motivo de erro de preço no sistema original.

## O que entregar

Construa o sistema completo, com todos os módulos acima. Priorize nesta ordem para ter algo demonstrável o quanto antes:

1. Modelo de dados + migrations.
2. Cadastro de Produto e Serviço (Estoque).
3. PDV / Venda (Caixa) com baixa de estoque, cálculo de taxa/liquidação, e fechamento de caixa.
4. Contas a Pagar (Saídas).
5. Histórico + DRE.
6. Markup.
7. Balancete + Indicadores.
8. Curva ABC.
9. Bens Físicos.
10. Comparador de Investimento (depende de API externa — deixe por último, com fallback manual funcionando).
11. Auto-provisionamento, licenciamento, alertas e o job de ativação de parcelas FUTURO.

Ao final de cada módulo, escreva testes automatizados cobrindo pelo menos as regras de cálculo descritas acima (markup bidirecional, DRE na ordem certa, classificação ABC, parcelas FUTURO virando venda ativa) — essas são as partes com mais lógica e mais risco de erro silencioso.

Ao final, empacote a aplicação com **PyInstaller** (ou equivalente) gerando um executável único, pra poder demonstrar rodando direto sem precisar instalar Python/dependências na máquina de apresentação do hackathon.
