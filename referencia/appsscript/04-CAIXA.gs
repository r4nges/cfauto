// ============================================================
// SISTEMA CAIXA ERP - ARQUIVO ÚNICO CONSOLIDADO (Code.gs)
// ============================================================

const ID_PLANILHA_ESTOQUE_PADRAO = "1aPr4-chXwNE19RWIXgOPceB-OmF31Ft5SgtugEPwoMA";
const ID_PLANILHA_CLIENTES = "1WrD5GmVXteevylzXZphNMQlcZEkgpxmogbZicK8Gq78";
const ID_PLANILHA_HISTORICO_EXTERNA = "1119HW8n6Ma-H83wbLw9I13bTJ9EgJhhpciPFyyaUXI8";

/**
 * 1. GATILHOS
 * O menu superior "🛒 SISTEMA CAIXA" foi removido a pedido — os botões/desenhos já
 * colados na planilha cobrem essas mesmas funções, então o menu ficava redundante.
 * onOpen continua existindo (vazio) só pra não sobrar nenhum gatilho "órfão" apontando
 * pra uma função que não existe mais (o mesmo tipo de erro que já corrigimos antes).
 */
function onOpen() {
  // Garante que a proteção está ativa toda vez que a planilha é aberta — sem precisar
  // clicar em nada. Se já estiver protegida, não faz nada (é rápido e seguro rodar sempre).
  protegerLinhasCaixaSilencioso();
  atualizarBackupCaixa(); // garante que já existe um backup pra restaurar, mesmo antes do 1º clique num botão
}

function onEdit(e) {
  if (!e || e.range.getSheet().getName() !== "CAIXA") return;

  const linha = e.range.getRow();
  // Da linha 5 pra baixo (cabeçalho + dados) é só pra VISUALIZAR — qualquer edição manual
  // (digitar, apagar, colar, Delete) é desfeita na hora, restaurando do último backup.
  // Só os botões (que escrevem por script, não por edição de usuário) conseguem mudar algo aqui.
  if (linha >= 5) {
    restaurarDoBackupCaixa(e.range);
    return;
  }
}

/**
 * 2. PAINEL E CONTROLE DO CAIXA
 */
function atualizarPainelCaixa() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheetCaixa = ss.getSheetByName("CAIXA") || ss.getActiveSheet();
  if (!sheetCaixa) return;

  const props = PropertiesService.getDocumentProperties();
  const status = props.getProperty('STATUS_CAIXA') || 'ABERTO';
  const saldoInicial = parseFloat(props.getProperty('SALDO_INICIAL')) || 0;
  const agora = new Date();
  const tz = Session.getScriptTimeZone();

  // H1:I1 — relogiozinho decorativo (fórmula NOW(), atualiza sozinho conforme o Sheets recalcula).
  const cellRelogio = sheetCaixa.getRange("H1");
  if (cellRelogio.getFormula() !== "=NOW()") {
    cellRelogio.setFormula("=NOW()").setNumberFormat("HH:mm:ss").setFontWeight("bold").setHorizontalAlignment("center");
  }

  // H2:I3 — voltou a ser só a data de hoje (referência visual pro fechamento de caixa).
  sheetCaixa.getRange("H2").setValue(Utilities.formatDate(agora, tz, "dd/MM/yyyy")).setFontWeight("bold").setHorizontalAlignment("center");

  const cellDinheiroGaveta = sheetCaixa.getRange("F2:G3");
  // ⚠️ CORRIGIDO: como J2:K2 (ou J2:K3) estão mescladas, o valor tem que ir na célula superior-esquerda do range (J2).
  const cellEntradaVirtual = sheetCaixa.getRange("J2");

  if (status === 'FECHADO') {
    cellDinheiroGaveta.setValue("FECHADO").setFontWeight("bold").setHorizontalAlignment("center").setFontSize(16);
    cellEntradaVirtual.setValue(0).setNumberFormat("R$ #,##0.00").setFontWeight("bold").setHorizontalAlignment("center");
    return;
  }

  const mapa = getMapeamentoColunas(sheetCaixa);
  const colPagto = mapa.pagto || 9, colPreco = mapa.preco || 7, colRecebido = mapa.recebido || 0, colLiquidado = mapa.liquidado || 0;
  const lastRow = sheetCaixa.getLastRow();

  let totalDinheiro = 0, totalVirtual = 0;

  if (lastRow >= 7) {
    const maxCol = Math.max(colPagto, colPreco, colRecebido, colLiquidado, 13);
    const dadosVendas = sheetCaixa.getRange(7, 1, lastRow - 6, maxCol).getValues();
    dadosVendas.forEach(row => {
      // ⚠️ NOVO: parcelas futuras de Contrato de Assinatura são marcadas com "FUTURO" na
      // coluna de Dias a Liquidar — elas ainda não aconteceram de verdade, então não podem
      // entrar no painel de HOJE (senão um contrato de 12x infla o caixa todo de uma vez).
      const marcadorLiquidado = colLiquidado ? String(row[colLiquidado - 1] || "").trim().toUpperCase() : "";
      if (marcadorLiquidado === "FUTURO") return;

      const forma = removerAcentos(row[colPagto - 1]);
      const valorBruto = parseValorMoeda(row[colPreco - 1]);
      // Usa o valor LÍQUIDO (pós-taxa, coluna "Venda") quando já foi calculado; senão cai pro valor bruto.
      const valorLiquido = colRecebido ? parseValorMoeda(row[colRecebido - 1]) : 0;
      const valorConsiderado = valorLiquido > 0 ? valorLiquido : valorBruto;

      // Dinheiro Virtual aqui mostra o TOTAL (já caído + a cair). O detalhe "já disponível x futuro"
      // fica só no Relatório de Vendas, pra não poluir o painel do caixa com caixinha extra.
      if (forma === "DINHEIRO") totalDinheiro += valorConsiderado;
      else if (["CREDITO", "DEBITO", "PIX", "EXTERNA"].includes(forma)) totalVirtual += valorConsiderado;
      // CREDIARIO não entra no caixa — é uma dívida do cliente, só vira caixa quando ele paga (processarPagamentoContaCliente).
    });
  }

  cellDinheiroGaveta.setValue(saldoInicial + totalDinheiro).setNumberFormat("R$ #,##0.00").setFontWeight("bold").setFontSize(18).setHorizontalAlignment("center");
  cellEntradaVirtual.setValue(totalVirtual).setNumberFormat("R$ #,##0.00").setFontWeight("bold").setFontSize(16).setHorizontalAlignment("center");

  atualizarBackupCaixa(); // mantém o backup fresquinho pra proteger contra edição manual
}

function abrirCaixa() {
  const ui = SpreadsheetApp.getUi(), props = PropertiesService.getDocumentProperties();
  if (props.getProperty('STATUS_CAIXA') === 'ABERTO') return ui.alert('⚠️ ATENÇÃO', 'O Caixa já está ABERTO!', ui.ButtonSet.OK);

  const sugestao = props.getProperty('SUGESTAO_PROXIMO_FUNDO');
  let msg = 'Informe o Saldo Inicial (Fundo de Troco) em R$:';
  if (sugestao) msg += '\n(Sugestão do caixa anterior: R$ ' + parseFloat(sugestao).toFixed(2).replace('.', ',') + ')';

  const resp = ui.prompt('🟢 ABRIR CAIXA', msg, ui.ButtonSet.OK_CANCEL);
  if (resp.getSelectedButton() !== ui.Button.OK) return;

  const txtResp = resp.getResponseText().trim();
  const saldoInicial = txtResp !== "" ? parseValorMoeda(txtResp) : (sugestao ? parseFloat(sugestao) : 0);
  const agora = new Date();
  const idSessao = "CX-" + Utilities.formatDate(agora, Session.getScriptTimeZone(), "yyyyMMdd-HHmm");

  props.setProperty('STATUS_CAIXA', 'ABERTO');
  props.setProperty('ID_SESSAO_CAIXA', idSessao);
  props.setProperty('DATA_ABERTURA', agora.toISOString());
  props.setProperty('SALDO_INICIAL', saldoInicial.toString());

  atualizarPainelCaixa();
  ui.alert('✅ CAIXA ABERTO!', 'Sessão: ' + idSessao + '\nTroco Inicial: R$ ' + saldoInicial.toFixed(2).replace('.', ','), ui.ButtonSet.OK);
}

function fecharCaixaEArquivar() {
  const ui = SpreadsheetApp.getUi(), ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheetCaixa = ss.getSheetByName("CAIXA") || ss.getActiveSheet();
  const props = PropertiesService.getDocumentProperties();

  if (props.getProperty('STATUS_CAIXA') === 'FECHADO') return ui.alert('⚠️ ATENÇÃO', 'O Caixa já está FECHADO!', ui.ButtonSet.OK);

  const idSessao = props.getProperty('ID_SESSAO_CAIXA') || "CX-AVULSO";
  const saldoInicial = parseFloat(props.getProperty('SALDO_INICIAL')) || 0;
  const lastRow = sheetCaixa.getLastRow();

  let resumo = { "Dinheiro": 0, "PIX": 0, "Débito": 0, "Crédito": 0, "Crediário": 0, "Externa": 0, TotalBruto: 0, TotalLiquido: 0 };
  const matrizHistorico = [];
  const linhasFuturasParaManter = []; // parcelas de contrato ainda não realizadas — não fecham com o caixa de hoje
  const mapa = getMapeamentoColunas(sheetCaixa);

  if (lastRow >= 7) {
    const valores = sheetCaixa.getRange(7, 1, lastRow - 6, sheetCaixa.getLastColumn()).getValues();
    valores.forEach(row => {
      // ⚠️ NOVO: parcelas futuras de Contrato de Assinatura (marcadas "FUTURO" na coluna de
      // Dias a Liquidar) não fazem parte do fechamento de hoje — ficam guardadas e voltam
      // pra planilha depois, esperando a data delas chegar de verdade.
      const marcadorLiquidado = mapa.liquidado ? String(row[mapa.liquidado - 1] || "").trim().toUpperCase() : "";
      if (marcadorLiquidado === "FUTURO") {
        linhasFuturasParaManter.push(row);
        return;
      }

      const desc = mapa.desc ? String(row[mapa.desc - 1]).trim() : "";
      const precoBruto = mapa.preco ? parseValorMoeda(row[mapa.preco - 1]) : 0;
      const qtd = mapa.qtd ? parseInt(row[mapa.qtd - 1], 10) || 1 : 1;
      const formaPagto = mapa.pagto ? String(row[mapa.pagto - 1]).trim() : "Dinheiro";
      const valRecebido = mapa.recebido ? parseValorMoeda(row[mapa.recebido - 1]) : precoBruto;

      let dataHoraVenda = "";
      if (mapa.hora && row[mapa.hora - 1] !== "") {
        const valHora = row[mapa.hora - 1];
        if (valHora instanceof Date) {
          dataHoraVenda = Utilities.formatDate(valHora, Session.getScriptTimeZone(), "dd/MM/yyyy HH:mm:ss");
        } else {
          dataHoraVenda = String(valHora).trim();
        }
      } else {
        dataHoraVenda = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "dd/MM/yyyy HH:mm:ss");
      }

      if (desc !== "" || precoBruto > 0) {
        const chavePagto = resumo.hasOwnProperty(formaPagto) ? formaPagto : "Dinheiro";
        resumo[chavePagto] += precoBruto;
        resumo.TotalBruto += precoBruto;
        resumo.TotalLiquido += valRecebido;

        // Estrutura exata da planilha externa (A até M):
        // Col A: Data/Hora | Col B: Protocolo | Col C: EAN | Col D: ID | Col E: Descrição | Col F: Categoria | Col G: Valor | Col H: Qtd | Col I: Pagamento | Col J: Recebimento | Col K: Taxa | Col L: Venda | Col M: Cliente
        matrizHistorico.push([
          dataHoraVenda, idSessao,
          mapa.ean ? row[mapa.ean - 1] : "", mapa.id ? row[mapa.id - 1] : "", desc,
          mapa.categoria ? row[mapa.categoria - 1] : "", precoBruto, qtd, formaPagto,
          mapa.liquidado ? row[mapa.liquidado - 1] : "", mapa.taxa ? parseValorMoeda(row[mapa.taxa - 1]) : 0,
          valRecebido, mapa.cliente ? row[mapa.cliente - 1] : ""
        ]);
      }
    });
  }

  const totalGaveta = saldoInicial + resumo["Dinheiro"];
  const respManter = ui.prompt('💸 FECHAMENTO DE CAIXA - SANGRIA', 'Dinheiro na Gaveta: R$ ' + totalGaveta.toFixed(2).replace('.', ',') + '\n\nQuanto deseja MANTER no caixa?', ui.ButtonSet.OK_CANCEL);
  if (respManter.getSelectedButton() !== ui.Button.OK) return;

  const valorManter = parseValorMoeda(respManter.getResponseText());
  if (valorManter > totalGaveta) return ui.alert('⚠️ ATENÇÃO', 'O valor a manter excede o total na gaveta!', ui.ButtonSet.OK);

  const valorRetirar = totalGaveta - valorManter;
  const msgRelatorio = `📊 FECHAMENTO DE CAIXA (${idSessao})\n-----------------------------------------\n💵 Fundo Inicial: R$ ${saldoInicial.toFixed(2).replace('.', ',')}\n• Vendas Dinheiro: R$ ${resumo["Dinheiro"].toFixed(2).replace('.', ',')}\n💰 TOTAL GAVETA: R$ ${totalGaveta.toFixed(2).replace('.', ',')}\n-----------------------------------------\n📌 MANTER: R$ ${valorManter.toFixed(2).replace('.', ',')}\n💸 SANGRIA: R$ ${valorRetirar.toFixed(2).replace('.', ',')}\n-----------------------------------------\n• PIX: R$ ${resumo["PIX"].toFixed(2).replace('.', ',')}\n• Débito: R$ ${resumo["Débito"].toFixed(2).replace('.', ',')}\n• Crédito: R$ ${resumo["Crédito"].toFixed(2).replace('.', ',')}\n• Crediário: R$ ${resumo["Crediário"].toFixed(2).replace('.', ',')}\n• Externa (Assinatura/Plataforma): R$ ${resumo["Externa"].toFixed(2).replace('.', ',')}\n-----------------------------------------\n🛍️ TOTAL VENDIDO: R$ ${resumo.TotalBruto.toFixed(2).replace('.', ',')}\n\nConfirma o fechamento e arquivamento no Histórico Externo?`;

  if (ui.alert('CONFIRMAR FECHAMENTO', msgRelatorio, ui.ButtonSet.YES_NO) !== ui.Button.YES) return;

  props.setProperty('SUGESTAO_PROXIMO_FUNDO', valorManter.toString());

  // Grava na planilha externa
  const ssHist = SpreadsheetApp.openById(ID_PLANILHA_HISTORICO_EXTERNA);
  let sheetHist = ssHist.getSheets()[0];

  if (sheetHist.getLastRow() === 0) {
    sheetHist.appendRow(["HORA E DATA", "PROTOCOLO", "EANO", "ID", "DESCRIÇÃO", "CATEGORIA", "VALOR", "QUANTIDADE", "PAGAMETO", "RECEBIMENTO", "TAXA", "VENDA", "CLIENTE"]);
  }

  if (matrizHistorico.length > 0) {
    sheetHist.getRange(sheetHist.getLastRow() + 1, 1, matrizHistorico.length, 13).setValues(matrizHistorico);
  }

  if (lastRow >= 7) sheetCaixa.getRange(7, 1, lastRow - 6, sheetCaixa.getLastColumn()).clearContent().clearFormat();

  // Devolve as parcelas futuras pra planilha, já que elas não fizeram parte desse fechamento.
  if (linhasFuturasParaManter.length > 0) {
    sheetCaixa.getRange(7, 1, linhasFuturasParaManter.length, linhasFuturasParaManter[0].length).setValues(linhasFuturasParaManter);
  }

  props.setProperty('STATUS_CAIXA', 'FECHADO');
  props.deleteProperty('ID_SESSAO_CAIXA');
  props.deleteProperty('SALDO_INICIAL');

  atualizarPainelCaixa();
  const avisoFuturas = linhasFuturasParaManter.length > 0 ? `\n\n📆 ${linhasFuturasParaManter.length} parcela(s) futura(s) de contrato foram mantidas na planilha, esperando a data certa.` : "";
  ui.alert("✅ CAIXA FECHADO!", `• Sangria: R$ ${valorRetirar.toFixed(2).replace('.', ',')}\n• Mantido: R$ ${valorManter.toFixed(2).replace('.', ',')}\n\nDados salvos com sucesso na planilha de histórico.${avisoFuturas}`, ui.ButtonSet.OK);
}

/**
 * 2.5 MOTOR DE TAXA / REPASSE / DATA DE LIQUIDAÇÃO
 * Usado tanto na venda (PDV) quanto no recebimento de conta de cliente.
 * - taxaValor: quanto a bandeira/adquirente cobra sobre o valor
 * - repasse: se TRUE, o cliente paga a taxa em cima (loja recebe o valor cheio do produto)
 *            se FALSE, a loja absorve a taxa (recebe o valor do produto menos a taxa)
 * - diasParaLiquidar: o número de dias que vai escrito na coluna "Liquidado" (0 = na hora)
 */
function calcularTaxaELiquidacao(formaPagamentoOriginal, valorBruto) {
  const cfg = obterConfiguracoes();
  const forma = removerAcentos(formaPagamentoOriginal);
  const tz = Session.getScriptTimeZone();

  let taxaPct = 0, dias = 0, repasse = false, pendente = false;

  if (forma === "DEBITO") { taxaPct = cfg.taxaDebito; dias = cfg.diasDebito; repasse = cfg.repasseDebito; }
  else if (forma === "CREDITO") { taxaPct = cfg.taxaCredito; dias = cfg.diasCredito; repasse = cfg.repasseCredito; }
  else if (forma === "PIX") { taxaPct = cfg.taxaPix; dias = 0; repasse = false; }
  else if (forma === "CREDIARIO") { taxaPct = 0; dias = 0; repasse = false; pendente = true; }
  else { taxaPct = 0; dias = 0; repasse = false; } // Dinheiro

  const taxaValor = valorBruto * (taxaPct / 100);
  const valorCobradoCliente = repasse ? (valorBruto + taxaValor) : valorBruto;
  const valorLiquidoLoja = pendente ? 0 : (repasse ? valorBruto : (valorBruto - taxaValor));

  // A coluna "Liquidado em" guarda só o NÚMERO DE DIAS até o dinheiro cair (editável manualmente).
  // A coluna "Recebido" mostra a DATA já calculada (dias + data de hoje), só pra leitura rápida.
  const diasParaLiquidar = pendente ? "" : dias;
  const dataRecebimentoTexto = pendente ? "Aguardando Pagamento" : Utilities.formatDate(
    (function() { const d = new Date(); d.setDate(d.getDate() + dias); return d; })(), tz, "dd/MM/yyyy"
  );

  return { taxaPct, taxaValor, repasse, pendente, valorCobradoCliente, valorLiquidoLoja, diasParaLiquidar, dataRecebimentoTexto };
}

/**
 * 3. PROCESSAMENTO DE VENDAS, CLIENTES E HISTÓRICO DE CREDIÁRIO
 */
function processarVendaPDV(dadosVenda) {
  try {
    const sheetCaixa = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("CAIXA") || SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    const mapa = getMapeamentoColunas(sheetCaixa);
    const maxCol = Math.max(...Object.values(mapa), 13);
    const dataHoraAtual = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "dd/MM/yyyy HH:mm:ss");

    dadosVenda.itens.forEach(item => {
      const targetRow = Math.max(sheetCaixa.getLastRow() + 1, 7);
      const rowData = new Array(maxCol).fill("");
      const info = calcularTaxaELiquidacao(dadosVenda.pagto, item.subtotal);

      if (mapa.ean) rowData[mapa.ean - 1] = item.ean;
      if (mapa.id) rowData[mapa.id - 1] = item.id;
      if (mapa.desc) rowData[mapa.desc - 1] = item.desc;
      if (mapa.categoria) rowData[mapa.categoria - 1] = item.categoria;
      if (mapa.preco) rowData[mapa.preco - 1] = item.subtotal;
      if (mapa.qtd) rowData[mapa.qtd - 1] = item.qtd;
      if (mapa.pagto) rowData[mapa.pagto - 1] = dadosVenda.pagto;
      if (mapa.liquidado) rowData[mapa.liquidado - 1] = info.diasParaLiquidar;
      if (mapa.dataRecebimento) rowData[mapa.dataRecebimento - 1] = info.dataRecebimentoTexto;
      if (mapa.taxa) rowData[mapa.taxa - 1] = Number(info.taxaValor.toFixed(2));
      if (mapa.recebido) rowData[mapa.recebido - 1] = Number(info.valorLiquidoLoja.toFixed(2));
      if (mapa.hora) rowData[mapa.hora - 1] = dataHoraAtual;
      if (mapa.cliente) rowData[mapa.cliente - 1] = dadosVenda.cliente;

      sheetCaixa.getRange(targetRow, 1, 1, maxCol).setValues([rowData]);
      if (mapa.taxa) sheetCaixa.getRange(targetRow, mapa.taxa).setNumberFormat('R$ #,##0.00');
      if (mapa.recebido) sheetCaixa.getRange(targetRow, mapa.recebido).setNumberFormat('R$ #,##0.00');
    });

    // Dá baixa no estoque (coluna K = Estoque, após o deslocamento da Data de Entrada) pra cada item vendido.
    try {
      const cfg = obterConfiguracoes();
      const ssEstoque = SpreadsheetApp.openById(cfg.idEstoque);
      const sheetEstoque = ssEstoque.getSheetByName("ESTOQUE") || ssEstoque.getSheets()[0];
      if (sheetEstoque) {
        dadosVenda.itens.forEach(item => {
          if (!item.rowEstoque) return; // item sem referência de linha — não dá pra baixar com segurança
          const cellEstoque = sheetEstoque.getRange(item.rowEstoque, 11); // Coluna K = Estoque
          const estoqueAtual = parseInt(cellEstoque.getValue(), 10) || 0;
          cellEstoque.setValue(Math.max(0, estoqueAtual - (item.qtd || 1)));
        });
      }
    } catch (eEstoque) {
      Logger.log("Erro ao dar baixa no estoque: " + eEstoque.message);
    }

    atualizarPainelCaixa();
    return "Venda concluída com sucesso!";
  } catch (e) {
    throw new Error("Erro ao processar venda: " + e.message);
  }
}

function processarPagamentoContaCliente(clienteId, valorPagamento, formaPagto, valorRecebidoDinheiro) {
  try {
    const valor = parseFloat(valorPagamento) || 0;
    if (valor <= 0) return { sucesso: false, mensagem: "Valor inválido." };
    // valorRecebidoDinheiro só é relevante quando formaPagto = Dinheiro (serve pra calcular o troco).
    // O troco NÃO abate a dívida do cliente — ele só sai do caixa físico, então não entra na conta do cliente.

    const ssClientes = SpreadsheetApp.openById(ID_PLANILHA_CLIENTES);
    const sheetClientes = ssClientes.getSheetByName("CLIENTES");
    if (!sheetClientes) throw new Error("Aba 'CLIENTES' não localizada.");

    const dados = sheetClientes.getDataRange().getValues();

    for (let i = 6; i < dados.length; i++) {
      if (String(dados[i][0]) === String(clienteId)) {
        const linha = i + 1, nomeCliente = dados[i][1];
        const limiteTotal = parseFloat(dados[i][4]) || 0, limiteUsadoAtual = parseFloat(dados[i][5]) || 0;
        const semLimite = String(dados[i][9] || "").toUpperCase() === "SIM";

        const novoLimiteUsado = Math.max(0, limiteUsadoAtual - valor);
        sheetClientes.getRange(linha, 6).setValue(novoLimiteUsado);
        sheetClientes.getRange(linha, 7).setValue(semLimite ? "ILIMITADO" : (limiteTotal - novoLimiteUsado));

        if (novoLimiteUsado === 0) sheetClientes.getRange(linha, 8).clearContent();

        const sheetCaixa = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("CAIXA") || SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
        const mapa = getMapeamentoColunas(sheetCaixa);
        const maxCol = Math.max(...Object.values(mapa), 13);
        const targetRow = Math.max(sheetCaixa.getLastRow() + 1, 7);

        const dataHoraAtual = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "dd/MM/yyyy HH:mm:ss");
        const rowData = new Array(maxCol).fill("");
        // Aqui a "forma de pagamento" é como o CLIENTE está quitando a dívida (Dinheiro/PIX/Débito/Crédito),
        // então a taxa e a data de liquidação seguem a mesma regra configurada em Configurações.
        const info = calcularTaxaELiquidacao(formaPagto, valor);

        if (mapa.desc) rowData[mapa.desc - 1] = "RECEBIMENTO DE CONTA / FIADO";
        if (mapa.categoria) rowData[mapa.categoria - 1] = "CREDIARIO";
        if (mapa.preco) rowData[mapa.preco - 1] = valor;
        if (mapa.qtd) rowData[mapa.qtd - 1] = 1;
        if (mapa.pagto) rowData[mapa.pagto - 1] = formaPagto;
        if (mapa.liquidado) rowData[mapa.liquidado - 1] = info.diasParaLiquidar;
      if (mapa.dataRecebimento) rowData[mapa.dataRecebimento - 1] = info.dataRecebimentoTexto;
        if (mapa.taxa) rowData[mapa.taxa - 1] = Number(info.taxaValor.toFixed(2));
        if (mapa.recebido) rowData[mapa.recebido - 1] = Number(info.valorLiquidoLoja.toFixed(2));
        if (mapa.hora) rowData[mapa.hora - 1] = dataHoraAtual;
        if (mapa.cliente) rowData[mapa.cliente - 1] = nomeCliente;

        sheetCaixa.getRange(targetRow, 1, 1, maxCol).setValues([rowData]);
        if (mapa.preco) sheetCaixa.getRange(targetRow, mapa.preco).setNumberFormat('R$ #,##0.00');
        if (mapa.taxa) sheetCaixa.getRange(targetRow, mapa.taxa).setNumberFormat('R$ #,##0.00');
        if (mapa.recebido) sheetCaixa.getRange(targetRow, mapa.recebido).setNumberFormat('R$ #,##0.00');

        atualizarPainelCaixa();

        let msgTroco = "";
        if (removerAcentos(formaPagto) === "DINHEIRO") {
          const recebidoDinheiro = parseFloat(valorRecebidoDinheiro) || valor;
          const troco = Math.max(0, recebidoDinheiro - valor);
          if (troco > 0) msgTroco = `\nTroco: R$ ${troco.toFixed(2)}`;
        }

        return { sucesso: true, mensagem: `✅ Pagamento de R$ ${valor.toFixed(2)} registrado para ${nomeCliente}!\nNovo Saldo: R$ ${novoLimiteUsado.toFixed(2)}${msgTroco}` };
      }
    }
    return { sucesso: false, mensagem: "Cliente não localizado." };
  } catch (e) {
    return { sucesso: false, mensagem: "Erro: " + e.message };
  }
}

/**
 * Converte um texto "dd/MM/yyyy HH:mm:ss" (ou similar) num objeto Date, pra dar pra ordenar por data.
 */
function parseDataBR(texto) {
  if (!texto) return new Date(0);
  const partes = String(texto).trim().split(' ');
  const dataParte = partes[0].split('/');
  if (dataParte.length !== 3) return new Date(0);
  const horaParte = (partes[1] || "00:00:00").split(':');
  return new Date(dataParte[2], dataParte[1] - 1, dataParte[0], horaParte[0] || 0, horaParte[1] || 0, horaParte[2] || 0);
}

/**
 * BUSCA PRODUTOS DO CLIENTE NO HISTÓRICO EXTERNO (Coluna M = Cliente, Coluna I = Pagamento, Coluna E = Produto)
 *
 * ⚠️ CORRIGIDO: antes, essa função listava TODAS as compras a prazo do cliente pra sempre, mesmo as já pagas
 * (o pagamento só abatia o total em "Débito Atual", mas não "apagava" os itens da lista). Isso fazia a conta
 * mostrar R$ 0,00 de dívida, mas ainda cobrar os produtos antigos de novo se o funcionário marcasse tudo.
 *
 * Agora a função usa o saldo devedor ATUAL do cliente (fonte da verdade: aba CLIENTES) como referência: ela
 * ordena as compras da mais antiga pra mais nova e vai "descontando" o que já foi pago, das mais antigas pra
 * mais novas (lógica de fila - a primeira dívida é a primeira a ser considerada quitada). Só sobra na lista o
 * que ainda está de fato em aberto, batendo com o "Débito Atual" mostrado.
 */
function obterItensCrediarioCliente(nomeCliente) {
  try {
    const clienteNorm = removerAcentos(nomeCliente);
    if (!clienteNorm) return [];

    // 0. Descobre quanto o cliente REALMENTE deve agora (fonte da verdade: aba CLIENTES)
    let limiteUsadoAtual = 0;
    try {
      const ssClientes = SpreadsheetApp.openById(ID_PLANILHA_CLIENTES);
      const sheetClientes = ssClientes.getSheetByName("CLIENTES");
      const dadosCli = sheetClientes.getDataRange().getValues();
      for (let i = 6; i < dadosCli.length; i++) {
        if (removerAcentos(dadosCli[i][1]) === clienteNorm) {
          limiteUsadoAtual = parseFloat(dadosCli[i][5]) || 0;
          break;
        }
      }
    } catch (eCli) {
      Logger.log("Erro ao buscar limiteUsado do cliente: " + eCli.message);
    }

    const itens = [];

    // 1. Busca na Planilha Externa de Histórico
    try {
      const ssHist = SpreadsheetApp.openById(ID_PLANILHA_HISTORICO_EXTERNA);
      const sheetHist = ssHist.getSheets()[0];
      if (sheetHist && sheetHist.getLastRow() >= 2) {
        const dadosHist = sheetHist.getRange(2, 1, sheetHist.getLastRow() - 1, Math.max(sheetHist.getLastColumn(), 13)).getValues();
        dadosHist.forEach(row => {
          const cli = removerAcentos(row[12]); // Coluna M (Cliente - Índice 12)
          const pagto = removerAcentos(row[8]); // Coluna I (PAGAMETO - Índice 8)
          const desc = String(row[4] || "").trim(); // Coluna E (DESCRIÇÃO - Índice 4)

          if (cli === clienteNorm && pagto.includes("CREDIARIO") && desc !== "" && !desc.includes("RECEBIMENTO DE CONTA")) {
            const preco = parseValorMoeda(row[6]); // Coluna G (VALOR - Índice 6)
            const qtd = parseInt(row[7], 10) || 1; // Coluna H (QUANTIDADE - Índice 7)
            
            let hora = "";
            if (row[0] instanceof Date) {
              hora = Utilities.formatDate(row[0], Session.getScriptTimeZone(), "dd/MM/yyyy HH:mm:ss");
            } else {
              hora = String(row[0] || "");
            }

            itens.push({ desc, qtd, preco, hora });
          }
        });
      }
    } catch (eHist) {
      Logger.log("Erro ao buscar histórico externo: " + eHist.message);
    }

    // 2. Busca no Caixa local aberto (caso a sessão ainda não tenha sido arquivada)
    try {
      const ssLocal = SpreadsheetApp.getActiveSpreadsheet();
      const sheetCaixa = ssLocal.getSheetByName("CAIXA");
      if (sheetCaixa && sheetCaixa.getLastRow() >= 7) {
        const mapa = getMapeamentoColunas(sheetCaixa);
        if (mapa.cliente && mapa.pagto && mapa.desc) {
          const dadosCaixa = sheetCaixa.getRange(7, 1, sheetCaixa.getLastRow() - 6, sheetCaixa.getLastColumn()).getValues();
          dadosCaixa.forEach(row => {
            const cli = removerAcentos(row[mapa.cliente - 1]);
            const pagto = removerAcentos(row[mapa.pagto - 1]);
            const desc = String(row[mapa.desc - 1] || "").trim();

            if (cli === clienteNorm && pagto.includes("CREDIARIO") && desc !== "" && !desc.includes("RECEBIMENTO DE CONTA")) {
              const preco = mapa.preco ? parseValorMoeda(row[mapa.preco - 1]) : 0;
              const qtd = mapa.qtd ? parseInt(row[mapa.qtd - 1], 10) || 1 : 1;
              let hora = "";
              if (mapa.hora && row[mapa.hora - 1] instanceof Date) {
                hora = Utilities.formatDate(row[mapa.hora - 1], Session.getScriptTimeZone(), "dd/MM/yyyy HH:mm:ss");
              } else {
                hora = mapa.hora ? String(row[mapa.hora - 1] || "") : "";
              }

              itens.push({ desc, qtd, preco, hora });
            }
          });
        }
      }
    } catch (eCaixa) {
      Logger.log("Erro ao buscar no caixa local: " + eCaixa.message);
    }

    // 3. Ordena da compra mais ANTIGA pra mais NOVA (pra saber qual já foi "coberta" por pagamentos)
    itens.sort((a, b) => parseDataBR(a.hora) - parseDataBR(b.hora));

    // 4. Quanto já foi pago no total = soma de tudo que ele comprou a prazo, menos o que ainda deve hoje
    const totalComprado = itens.reduce((soma, it) => soma + (it.preco * (it.qtd || 1)), 0);
    let jaQuitado = Math.max(0, totalComprado - limiteUsadoAtual);

    const itensPendentes = [];
    for (const item of itens) {
      const valorItem = item.preco * (item.qtd || 1);
      if (jaQuitado >= valorItem) {
        jaQuitado -= valorItem; // esse item já foi quitado por um pagamento anterior — não mostra mais
      } else {
        itensPendentes.push(item); // ainda está em aberto
      }
    }

    return itensPendentes;
  } catch (e) {
    return [];
  }
}

function obterClientesDaPlanilhaExterna() {
  try {
    const sheet = SpreadsheetApp.openById(ID_PLANILHA_CLIENTES).getSheetByName("CLIENTES");
    if (!sheet) throw new Error("Aba 'CLIENTES' não encontrada.");

    const dados = sheet.getDataRange().getValues();
    const lista = [], hoje = new Date();

    for (let i = 6; i < dados.length; i++) {
      if (dados[i][1]) {
        const limiteTotal = parseFloat(dados[i][4]) || 0, limiteUsado = parseFloat(dados[i][5]) || 0;
        const semLimite = String(dados[i][9] || "").toUpperCase() === "SIM";

        let diasAtraso = 0;
        if (limiteUsado > 0 && dados[i][7]) {
          const dataVenc = new Date(dados[i][7]);
          if (!isNaN(dataVenc.getTime()) && dataVenc < hoje) {
            diasAtraso = Math.floor(Math.abs(hoje - dataVenc) / (1000 * 60 * 60 * 24));
          }
        }

        lista.push({
          linhaIndex: i + 1,
          id: String(dados[i][0] || ""),
          nome: String(dados[i][1] || ""),
          celular: String(dados[i][2] || ""),
          cpf: String(dados[i][3] || ""),
          limiteTotal, limiteUsado,
          disponivel: semLimite ? "ILIMITADO" : (limiteTotal - limiteUsado),
          semLimite,
          somenteTitular: String(dados[i][10] || "").toUpperCase() === "SIM",
          obs: String(dados[i][11] || ""),
          dependentes: [dados[i][12], dados[i][13], dados[i][14], dados[i][15]].filter(Boolean).join(", "),
          diasAtraso
        });
      }
    }
    return lista;
  } catch (e) {
    throw new Error("Erro ao acessar clientes: " + e.message);
  }
}

function obterTodosProdutosEstoquePDV() {
  try {
    const cfg = obterConfiguracoes();
    const ssEstoque = SpreadsheetApp.openById(cfg.idEstoque);
    const sheetEstoque = ssEstoque.getSheetByName("ESTOQUE") || ssEstoque.getSheets()[0];
    if (!sheetEstoque) return [];

    const lastRow = sheetEstoque.getLastRow();
    if (lastRow < 6) return [];

    const dados = sheetEstoque.getRange(6, 1, lastRow - 5, 11).getValues();
    const lista = [];

    dados.forEach((row, idx) => {
      if (row[2] || row[0]) {
        lista.push({
          row: idx + 6,
          ean: String(row[0] || "").trim(),
          id: String(row[1] || "").trim(),
          desc: String(row[2] || "").trim(),
          categoria: String(row[3] || "Geral").trim(),
          pVenda: parseValorMoeda(row[9]),  // J = Preço de Venda (pós-deslocamento da Data de Entrada)
          est: parseInt(row[10], 10) || 0   // K = Estoque (qtd)
        });
      }
    });

    return lista;
  } catch (e) {
    return [];
  }
}

function obterConfiguracoes() {
  const props = PropertiesService.getDocumentProperties();
  return {
    idEstoque: props.getProperty('ID_PLANILHA_ESTOQUE') || ID_PLANILHA_ESTOQUE_PADRAO,
    taxaDebito: parseFloat(props.getProperty('TAXA_DEBITO')) || 1.5,
    diasDebito: parseInt(props.getProperty('DIAS_DEBITO'), 10) || 7,
    taxaCredito: parseFloat(props.getProperty('TAXA_CREDITO')) || 3.5,
    diasCredito: parseInt(props.getProperty('DIAS_CREDITO'), 10) || 7,
    taxaPix: parseFloat(props.getProperty('TAXA_PIX')) || 0,
    taxaCrediario: parseFloat(props.getProperty('TAXA_CREDIARIO')) || 0,
    repasseDebito: props.getProperty('REPASSE_DEBITO') === 'SIM',
    repasseCredito: props.getProperty('REPASSE_CREDITO') === 'SIM'
  };
}

function salvarConfiguracoes(cfg) {
  const props = PropertiesService.getDocumentProperties();
  if (cfg.idEstoque) props.setProperty('ID_PLANILHA_ESTOQUE', cfg.idEstoque);
  props.setProperty('TAXA_DEBITO', cfg.taxaDebito.toString());
  props.setProperty('DIAS_DEBITO', cfg.diasDebito.toString());
  props.setProperty('TAXA_CREDITO', cfg.taxaCredito.toString());
  props.setProperty('DIAS_CREDITO', cfg.diasCredito.toString());
  props.setProperty('TAXA_PIX', cfg.taxaPix.toString());
  props.setProperty('TAXA_CREDIARIO', cfg.taxaCrediario.toString());
  props.setProperty('REPASSE_DEBITO', cfg.repasseDebito ? 'SIM' : 'NAO');
  props.setProperty('REPASSE_CREDITO', cfg.repasseCredito ? 'SIM' : 'NAO');
  return "Configurações atualizadas!";
}

/**
 * 4. FUNÇÕES AUXILIARES UNIFICADAS
 */
/**
 * DADOS DO RELATÓRIO DE VENDAS
 * Lê a planilha de HISTÓRICO EXTERNO (caixas já fechados) e monta os totais/gráficos.
 * Estrutura das colunas (igual ao que é gravado em fecharCaixaEArquivar):
 * A Data/Hora | B Protocolo | C EAN | D ID | E Descrição | F Categoria | G Valor |
 * H Quantidade | I Pagamento | J Liquidado em | K Taxa | L Venda (líquido) | M Cliente
 */
/**
 * DADOS DO RELATÓRIO DE VENDAS
 * Lê a planilha de HISTÓRICO EXTERNO (caixas já fechados) E TAMBÉM o caixa aberto no momento (ainda não
 * arquivado), pra que o "Dinheiro Futuro (A Cair)" apareça na hora, sem precisar fechar o caixa primeiro.
 * Nunca há risco de contar a mesma venda duas vezes: assim que o caixa é fechado, a linha some do CAIXA
 * e passa a existir só no Histórico (fecharCaixaEArquivar limpa a aba depois de arquivar).
 *
 * Estrutura das colunas do Histórico:
 * A Data/Hora | B Protocolo | C EAN | D ID | E Descrição | F Categoria | G Valor |
 * H Quantidade | I Pagamento | J Liquidado em | K Taxa | L Venda (líquido) | M Cliente
 */
function obterDadosRelatorioVendas(filtroMes, filtroAno) {
  const tz = Session.getScriptTimeZone();
  const hoje = new Date(); hoje.setHours(0, 0, 0, 0);

  const acc = {
    totalVendidoBruto: 0, totalRecebidoLiquido: 0, totalTaxas: 0,
    dinheiroJaDisponivel: 0, dinheiroFuturo: 0,
    porFormaPagamento: {}, porCategoria: {}, mapaMensal: {}, anosSet: new Set()
  };

  function processarLinha(dataHora, categoria, valorBruto, formaPagto, diasLiquidarRaw, taxa, valorLiquidoBruto) {
    const valorLiquido = valorLiquidoBruto || valorBruto;
    if (!valorBruto && !categoria) return;

    let dtObj = null;
    if (dataHora instanceof Date) dtObj = dataHora;
    else if (typeof dataHora === 'string' && dataHora.includes('/')) {
      const partes = dataHora.split(' ')[0].split('/');
      if (partes.length === 3) dtObj = new Date(partes[2], partes[1] - 1, partes[0]);
    }

    if (dtObj) acc.anosSet.add(dtObj.getFullYear());
    if (dtObj) {
      const m = dtObj.getMonth() + 1, a = dtObj.getFullYear();
      if (filtroMes && filtroMes !== "TODOS" && parseInt(filtroMes) !== m) return;
      if (filtroAno && filtroAno !== "TODOS" && parseInt(filtroAno) !== a) return;
    }

    acc.totalVendidoBruto += valorBruto;
    acc.totalRecebidoLiquido += valorLiquido;
    acc.totalTaxas += taxa;

    acc.porFormaPagamento[formaPagto] = (acc.porFormaPagamento[formaPagto] || 0) + valorBruto;
    acc.porCategoria[categoria] = (acc.porCategoria[categoria] || 0) + valorBruto;

    // Dinheiro Já Disponível x Dinheiro Futuro — a coluna "Liquidado" guarda quantos DIAS depois da
    // venda o dinheiro cai (0 = na hora). A data real de queda = data da venda + esses dias.
    const normPagto = removerAcentos(formaPagto);
    if (normPagto === "CREDIARIO") {
      // Ainda não é dinheiro nenhum — é dívida do cliente, só conta quando ele pagar.
    } else if (String(diasLiquidarRaw).trim().toUpperCase() === "FUTURO") {
      // Parcela de Contrato de Assinatura ainda não realizada — nem entra na conta ainda.
      acc.totalVendidoBruto -= valorBruto; // desfaz o que já foi somado acima, pra ela não aparecer em nenhum total
      acc.totalRecebidoLiquido -= valorLiquido;
      acc.totalTaxas -= taxa;
      acc.porFormaPagamento[formaPagto] -= valorBruto;
      acc.porCategoria[categoria] -= valorBruto;
    } else {
      const dias = parseInt(diasLiquidarRaw, 10) || 0;
      const dataBase = dtObj || new Date();
      const dataQueCai = new Date(dataBase.getTime());
      dataQueCai.setDate(dataQueCai.getDate() + dias);
      dataQueCai.setHours(0, 0, 0, 0);

      if (dataQueCai <= hoje) acc.dinheiroJaDisponivel += valorLiquido;
      else acc.dinheiroFuturo += valorLiquido;
    }

    if (dtObj) {
      const chave = Utilities.formatDate(dtObj, tz, "yyyy-MM");
      const label = Utilities.formatDate(dtObj, tz, "MMM/yy");
      if (!acc.mapaMensal[chave]) acc.mapaMensal[chave] = { label, bruto: 0, liquido: 0 };
      acc.mapaMensal[chave].bruto += valorBruto;
      acc.mapaMensal[chave].liquido += valorLiquido;
    }
  }

  // 1. Histórico externo (caixas já fechados)
  try {
    const ssHist = SpreadsheetApp.openById(ID_PLANILHA_HISTORICO_EXTERNA);
    const sheetHist = ssHist.getSheets()[0];
    const lastRow = sheetHist.getLastRow();
    if (lastRow >= 2) {
      const dados = sheetHist.getRange(2, 1, lastRow - 1, 13).getValues();
      dados.forEach(row => {
        processarLinha(row[0], String(row[5] || "Outros"), parseValorMoeda(row[6]), String(row[8] || "Outros").trim(), String(row[9] || ""), parseValorMoeda(row[10]), parseValorMoeda(row[11]));
      });
    }
  } catch (eHist) {
    Logger.log("Erro ao ler histórico externo no relatório: " + eHist.message);
  }

  // 2. Caixa aberto no momento (ainda não arquivado) — pra "Dinheiro Futuro" aparecer sem precisar fechar o caixa
  try {
    const sheetCaixa = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("CAIXA");
    if (sheetCaixa && sheetCaixa.getLastRow() >= 7) {
      const mapa = getMapeamentoColunas(sheetCaixa);
      const dadosCaixa = sheetCaixa.getRange(7, 1, sheetCaixa.getLastRow() - 6, sheetCaixa.getLastColumn()).getValues();
      dadosCaixa.forEach(row => {
        const desc = mapa.desc ? String(row[mapa.desc - 1] || "").trim() : "";
        if (desc === "") return;
        processarLinha(
          mapa.hora ? row[mapa.hora - 1] : "",
          mapa.categoria ? String(row[mapa.categoria - 1] || "Outros") : "Outros",
          mapa.preco ? parseValorMoeda(row[mapa.preco - 1]) : 0,
          mapa.pagto ? String(row[mapa.pagto - 1] || "Outros").trim() : "Outros",
          mapa.liquidado ? String(row[mapa.liquidado - 1] || "") : "",
          mapa.taxa ? parseValorMoeda(row[mapa.taxa - 1]) : 0,
          mapa.recebido ? parseValorMoeda(row[mapa.recebido - 1]) : 0
        );
      });
    }
  } catch (eCaixa) {
    Logger.log("Erro ao ler caixa aberto no relatório: " + eCaixa.message);
  }

  const chavesOrdenadas = Object.keys(acc.mapaMensal).sort();
  const evolucaoMensal = { labels: [], bruto: [], liquido: [] };
  chavesOrdenadas.forEach(chave => {
    evolucaoMensal.labels.push(acc.mapaMensal[chave].label);
    evolucaoMensal.bruto.push(acc.mapaMensal[chave].bruto);
    evolucaoMensal.liquido.push(acc.mapaMensal[chave].liquido);
  });

  const anosDisponiveis = Array.from(acc.anosSet).sort((a, b) => b - a);
  if (anosDisponiveis.length === 0) anosDisponiveis.push(new Date().getFullYear());

  return {
    totalVendidoBruto: acc.totalVendidoBruto, totalRecebidoLiquido: acc.totalRecebidoLiquido, totalTaxas: acc.totalTaxas,
    dinheiroJaDisponivel: acc.dinheiroJaDisponivel, dinheiroFuturo: acc.dinheiroFuturo,
    porFormaPagamento: acc.porFormaPagamento, porCategoria: acc.porCategoria, evolucaoMensal, anosDisponiveis
  };
}

function removerAcentos(str) {
  return str ? String(str).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase().trim() : "";
}

function parseValorMoeda(val) {
  if (typeof val === 'number') return val;
  if (!val) return 0;
  let str = String(val).replace(/[^0-9,-.]/g, '').trim();
  if (str.includes(',') && str.includes('.')) str = str.replace(/\./g, '').replace(',', '.');
  else if (str.includes(',')) str = str.replace(',', '.');
  return parseFloat(str) || 0;
}

function getMapeamentoColunas(sheet) {
  const headers = sheet.getRange(6, 1, 1, Math.max(sheet.getLastColumn(), 15)).getValues()[0];
  const mapa = {};
  headers.forEach((h, idx) => {
    const nome = removerAcentos(h);
    if (nome.includes("BARRA") || nome.includes("EAN")) mapa.ean = idx + 1;
    else if (nome === "ID" || nome.includes("ID ")) mapa.id = idx + 1;
    else if (nome.includes("DESCRIC") || nome.includes("PRODUTO")) mapa.desc = idx + 1;
    else if (nome.includes("CATEGOR")) mapa.categoria = idx + 1;
    else if (nome.includes("PRECO") || nome.includes("VALOR")) mapa.preco = idx + 1;
    else if (nome.includes("QUANT") || nome.includes("QTD")) mapa.qtd = idx + 1;
    else if (nome.includes("PAGAMEN") || nome.includes("PAGAMET")) mapa.pagto = idx + 1; // Suporta digitação com ou sem N
    // ⚠️ CORRIGIDO: antes "RECEB" e "LIQUID" caíam na mesma regra, e como "RECEBIDO" vem depois de
    // "LIQUIDADO EM" na planilha, ele sobrescrevia o mapeamento e "LIQUIDADO EM" ficava sem nada.
    // Agora cada um tem seu papel: "Liquidado em" = dias até cair (editável), "Recebido" = a data já calculada.
    else if (nome.includes("LIQUID")) mapa.liquidado = idx + 1;
    else if (nome.includes("RECEB")) mapa.dataRecebimento = idx + 1;
    else if (nome.includes("TAXA")) mapa.taxa = idx + 1;
    else if (nome.includes("VENDA")) mapa.recebido = idx + 1;
    else if (nome.includes("HORA") || nome.includes("DATA")) mapa.hora = idx + 1;
    else if (nome.includes("CLIEN")) mapa.cliente = idx + 1;
  });
  return mapa;
}

/**
 * 5. GERENCIAMENTO DE DIÁLOGOS E INTERFACES VISUAIS
 */
function abrirJanelaNovaVenda() {
  if (PropertiesService.getDocumentProperties().getProperty('STATUS_CAIXA') === 'FECHADO') {
    return SpreadsheetApp.getUi().alert('🛑 CAIXA FECHADO!', 'Abra o caixa antes de realizar vendas.', SpreadsheetApp.getUi().ButtonSet.OK);
  }
  const html = HtmlService.createHtmlOutput(getHtmlNovaVenda()).setWidth(520).setHeight(700);
  SpreadsheetApp.getUi().showModalDialog(html, '🛒 NOVA VENDA / PDV');
}

function abrirJanelaPagamentoCliente() {
  if (PropertiesService.getDocumentProperties().getProperty('STATUS_CAIXA') === 'FECHADO') {
    return SpreadsheetApp.getUi().alert('🛑 CAIXA FECHADO!', 'Abra o caixa antes de receber pagamentos.', SpreadsheetApp.getUi().ButtonSet.OK);
  }
  const html = HtmlService.createHtmlOutput(getHtmlPagamentoCliente()).setWidth(500).setHeight(820);
  SpreadsheetApp.getUi().showModalDialog(html, '💳 RECEBER PAGAMENTO DE CONTA');
}

function abrirBuscaClientesCaixa() {
  const html = HtmlService.createHtmlOutput(getHtmlBuscaClientes()).setWidth(520).setHeight(680);
  SpreadsheetApp.getUi().showModalDialog(html, "🔎 Buscar Cliente");
}

function abrirJanelaRelatorioVendas() {
  const html = HtmlService.createHtmlOutput(getHtmlRelatorioVendas()).setWidth(820).setHeight(600);
  SpreadsheetApp.getUi().showModalDialog(html, "📊 Relatório de Vendas");
}

function abrirJanelaExcluirVenda() {
  const html = HtmlService.createHtmlOutput(getHtmlExcluirVenda()).setWidth(650).setHeight(600);
  SpreadsheetApp.getUi().showModalDialog(html, "🗑️ Excluir Venda");
}

/**
 * Lista as vendas do caixa ATUALMENTE ABERTO (linha 7 em diante), da mais recente pra mais antiga,
 * pra alimentar a janela de exclusão — assim o usuário escolhe pelo nome/valor, sem precisar
 * clicar na célula certa da planilha antes de rodar o comando.
 */
function obterVendasParaExclusao() {
  const sheetCaixa = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("CAIXA");
  if (!sheetCaixa) return [];
  const mapa = getMapeamentoColunas(sheetCaixa);
  const lastRow = sheetCaixa.getLastRow();
  const vendas = [];

  if (lastRow >= 7) {
    const dados = sheetCaixa.getRange(7, 1, lastRow - 6, sheetCaixa.getLastColumn()).getValues();
    dados.forEach((row, idx) => {
      const desc = mapa.desc ? String(row[mapa.desc - 1] || "").trim() : "";
      if (desc === "") return; // linha vazia — ignora

      let hora = "";
      if (mapa.hora && row[mapa.hora - 1] instanceof Date) {
        hora = Utilities.formatDate(row[mapa.hora - 1], Session.getScriptTimeZone(), "dd/MM HH:mm");
      } else if (mapa.hora) {
        hora = String(row[mapa.hora - 1] || "");
      }

      vendas.push({
        linha: idx + 7,
        desc,
        preco: mapa.preco ? parseValorMoeda(row[mapa.preco - 1]) : 0,
        qtd: mapa.qtd ? row[mapa.qtd - 1] : 1,
        pagto: mapa.pagto ? String(row[mapa.pagto - 1] || "") : "",
        hora,
        cliente: mapa.cliente ? String(row[mapa.cliente - 1] || "") : ""
      });
    });
  }

  return vendas.reverse(); // mais recente primeiro, fica mais fácil de achar
}

/**
 * Exclui a linha inteira de uma venda específica do caixa aberto e atualiza o painel.
 */
function excluirVendaPorLinha(numeroLinha) {
  try {
    const sheetCaixa = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("CAIXA");
    if (!sheetCaixa) throw new Error("Aba CAIXA não encontrada.");
    const linha = parseInt(numeroLinha, 10);
    if (!linha || linha < 7) throw new Error("Linha inválida.");

    sheetCaixa.deleteRow(linha);
    atualizarPainelCaixa();
    return { sucesso: true, mensagem: "✅ Venda excluída e painel atualizado!" };
  } catch (e) {
    return { sucesso: false, mensagem: "❌ Erro: " + e.message };
  }
}

function abrirJanelaConfiguracoes() {
  const html = HtmlService.createHtmlOutput(getHtmlConfiguracoes()).setWidth(480).setHeight(540);
  SpreadsheetApp.getUi().showModalDialog(html, '⚙️ CONFIGURAÇÕES');
}

/**
 * 6. TEMPLATES HTML/CSS/JS INLINE
 */
function getHtmlNovaVenda() {
  return `<!DOCTYPE html>
<html>
<head>
  <style>
    body{font-family:Arial,sans-serif;padding:12px;background:#f8f9fa;color:#333;margin:0}
    .box{background:#fff;padding:10px 12px;border-radius:6px;box-shadow:0 1px 3px rgba(0,0,0,0.12);margin-bottom:8px}
    label{font-size:11px;font-weight:bold;color:#555;display:block;margin-top:4px}
    input,select{width:100%;padding:7px;border:1px solid #ccc;border-radius:4px;box-sizing:border-box;font-size:12px}
    input:disabled,select:disabled{background-color:#e9ecef;cursor:not-allowed;}
    .grid-2{display:grid;grid-template-columns:1fr 1fr;gap:8px}
    .grid-3{display:grid;grid-template-columns:2fr 1fr 1fr;gap:6px;align-items:end}
    .btn{padding:8px;border:none;border-radius:4px;font-weight:bold;cursor:pointer;font-size:12px}
    .btn-add{background:#007bff;color:#fff}
    .btn-pay{background:#107c41;color:#fff;width:100%;font-size:14px;padding:10px;margin-top:8px}
    .btn-del{background:#d9534f;color:#fff;padding:2px 6px;font-size:10px;border-radius:3px;cursor:pointer}
    table{width:100%;border-collapse:collapse;margin-top:6px;font-size:11px}
    th,td{border:1px solid #dee2e6;padding:5px;text-align:left}th{background:#e9ecef}
    .total-box{font-size:15px;font-weight:bold;color:#107c41;text-align:right}
    .info-card{background:#f1f3f5;padding:8px;border-radius:6px;margin-top:6px;font-size:11px;border:1px solid #dee2e6}
    .info-line{display:flex;justify-content:space-between;margin-bottom:3px}
    .results-list { margin-top: 4px; max-height: 150px; overflow-y: auto; border: 1px solid #007bff; border-radius: 4px; background: #fff; position: absolute; width: 92%; z-index: 1000; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .result-item { padding: 8px; border-bottom: 1px solid #eee; cursor: pointer; font-size: 11px; }
    .result-item:hover { background: #e8f4fe; color: #007bff; font-weight: bold; }
    .desconto-container { display: flex; gap: 4px; }
    .desconto-container select { width: 65px; flex-shrink: 0; }
    .desconto-inverso { font-size: 11px; font-weight: bold; color: #007bff; margin-top: 3px; min-height: 15px; }
  </style>
</head>
<body>
  <div class="box">
    <div class="grid-2">
      <div>
        <label>Pagamento:</label>
        <select id="v_pagto" onchange="togglePagamento()">
          <option value="Dinheiro">Dinheiro</option>
          <option value="PIX">PIX</option>
          <option value="Débito">Débito</option>
          <option value="Crédito">Crédito</option>
          <option value="Crediário">Crediário</option>
        </select>
      </div>
      <div style="position:relative;">
        <label>Cliente (Crediário):</label>
        <input type="text" id="v_cliente_busca" placeholder="🔎 Buscar..." oninput="filtrarClientesDinamico()" autocomplete="off" disabled>
        <div id="lista-resultados-cli" class="results-list" style="display:none;"></div>
      </div>
    </div>
    <div id="box_info_cliente" class="info-card" style="display:none;">
      <div class="info-line"><span>Saldo Devedor:</span><strong id="pdv_debito" style="color:#dc3545">R$ 0,00</strong></div>
      <div class="info-line"><span>Disponível:</span><strong id="pdv_disponivel" style="color:#28a745">R$ 0,00</strong></div>
      <div class="info-line"><span>Atraso:</span><strong id="pdv_atraso">0 dias</strong></div>
      <div id="pdv_alerta_limite" style="display:none;color:#dc3545;font-weight:bold;font-size:11px;margin-top:4px;text-align:center;background:#f8d7da;padding:4px;border-radius:4px;">⚠️ VENDA EXCEDE O LIMITE DISPONÍVEL!</div>
    </div>
  </div>

  <div class="box" style="position:relative;">
    <div class="grid-3">
      <div style="position:relative;">
        <label>Buscar Produto (EAN, ID, Nome):</label>
        <input type="text" id="p_busca" placeholder="Digite para filtrar..." oninput="filtrarProdutosDinamico()" autocomplete="off">
        <div id="lista-resultados-prod" class="results-list" style="display:none;"></div>
      </div>
      <div><label>Qtd:</label><input type="number" id="p_qtd" value="1" min="1"></div>
      <div><button class="btn btn-add" style="width:100%" onclick="confirmarAdicaoProduto()">✅ Confirmar</button></div>
    </div>
    <div id="p_status" style="font-size:11px;text-align:center;margin-top:6px;font-weight:bold;"></div>
  </div>

  <div class="box" id="box_taxa_cartao" style="display:none;">
    <div class="info-line"><span>Taxa da forma de pagamento:</span><strong id="txt_taxa_pct">0%</strong></div>
    <div class="info-line"><span id="txt_taxa_label">Taxa (absorvida pela loja):</span><strong id="txt_taxa_valor">R$ 0,00</strong></div>
  </div>

  <div class="box" style="max-height:120px;overflow-y:auto;">
    <table>
      <thead><tr><th>Item</th><th>Qtd</th><th>Unit.</th><th>Total</th><th></th></tr></thead>
      <tbody id="cart_body"><tr><td colspan="5" style="text-align:center;color:#999;">Carrinho vazio.</td></tr></tbody>
    </table>
  </div>

  <div class="box">
    <div class="grid-2" style="margin-bottom:8px;">
      <div>
        <label>Desconto:</label>
        <div class="desconto-container">
          <select id="v_tipo_desconto" onchange="renderCarrinho()">
            <option value="R$">R$</option>
            <option value="%">%</option>
          </select>
          <input type="number" id="v_desconto" step="0.01" value="0.00" min="0" oninput="renderCarrinho()">
        </div>
        <div id="v_desconto_inverso" class="desconto-inverso"></div>
      </div>
      <div id="box_dinheiro_pago">
        <label>Valor Recebido (R$):</label>
        <input type="number" id="v_pago" step="0.01" oninput="calcularTroco()">
      </div>
    </div>
    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:6px;">
      <div id="box_dinheiro_troco" style="font-size:13px; font-weight:bold;">
        Troco: <span id="v_troco" style="color:#007bff;">R$ 0,00</span>
      </div>
      <div class="total-box">TOTAL: R$ <span id="v_total">0,00</span></div>
    </div>
    <button class="btn btn-pay" onclick="finalizarVenda()">💾 FINALIZAR VENDA (<span id="count_itens">0</span> ITENS)</button>
    <div id="v_status" style="font-size:12px;text-align:center;margin-top:8px;font-weight:bold;min-height:18px;"></div>
  </div>

  <script>
    var carrinho = [], subtotalVendaGlobal = 0, totalVendaGlobal = 0, clientesGlobal = [], produtosEstoqueCache = [], clienteSelecionadoObj = null;
    var produtoSelecionado = null, cfgGlobal = { taxaDebito: 0, diasDebito: 0, taxaCredito: 0, diasCredito: 0, taxaPix: 0, repasseDebito: false, repasseCredito: false };

    window.onload = function() {
      togglePagamento();
      google.script.run.withSuccessHandler(function(prods){ produtosEstoqueCache = prods || []; }).obterTodosProdutosEstoquePDV();
      google.script.run.withSuccessHandler(function(d){ clientesGlobal = d || []; }).obterClientesDaPlanilhaExterna();
      google.script.run.withSuccessHandler(function(cfg){ cfgGlobal = cfg || cfgGlobal; renderCarrinho(); }).obterConfiguracoes();
    };

    function norm(t){ return t ? t.toString().toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim() : ""; }
    
    function togglePagamento() {
      var pagto = norm(document.getElementById('v_pagto').value);
      var inputC = document.getElementById('v_cliente_busca');
      var listaC = document.getElementById('lista-resultados-cli');
      var inputDesc = document.getElementById('v_desconto');
      var selectTipoDesc = document.getElementById('v_tipo_desconto');

      if (pagto === 'crediario') {
        inputC.disabled = false;
        inputC.focus();
        filtrarClientesDinamico();
        if (inputDesc) { inputDesc.value = '0.00'; inputDesc.disabled = true; }
        if (selectTipoDesc) { selectTipoDesc.disabled = true; }
      } else {
        inputC.value = '';
        inputC.disabled = true;
        if (listaC) listaC.style.display = 'none';
        clienteSelecionadoObj = null; 
        document.getElementById('box_info_cliente').style.display = 'none';
        if (inputDesc) { inputDesc.disabled = false; }
        if (selectTipoDesc) { selectTipoDesc.disabled = false; }
      }
      renderCarrinho();
      calcularTroco(); 
      validarLimiteCrediario();
      atualizarVisorTaxa();
    }

    function filtrarClientesDinamico() {
      var termo = norm(document.getElementById('v_cliente_busca').value);
      var divLista = document.getElementById('lista-resultados-cli');

      if (norm(document.getElementById('v_pagto').value) !== 'crediario') {
        divLista.style.display = 'none';
        return;
      }

      var filtrados = clientesGlobal.filter(function(c) {
        return norm(c.nome).includes(termo) || norm(c.id).includes(termo) || (c.cpf && norm(c.cpf).includes(termo));
      });

      divLista.innerHTML = '';
      if (!filtrados.length) {
        divLista.style.display = 'none';
        return;
      }

      filtrados.slice(0, 10).forEach(function(c) {
        var itemDiv = document.createElement('div');
        itemDiv.className = 'result-item';
        itemDiv.innerHTML = '<strong>' + c.nome + '</strong>' + (c.cpf ? ' <span style="color:#666;">(' + c.cpf + ')</span>' : '');
        itemDiv.onclick = function() { selecionarClienteObj(c); };
        divLista.appendChild(itemDiv);
      });
      divLista.style.display = 'block';
    }

    function selecionarClienteObj(c) {
      clienteSelecionadoObj = c;
      document.getElementById('v_cliente_busca').value = c.nome;
      document.getElementById('lista-resultados-cli').style.display = 'none';

      var infoBox = document.getElementById('box_info_cliente');
      infoBox.style.display = 'block';
      document.getElementById('pdv_debito').innerText = 'R$ ' + (c.limiteUsado||0).toFixed(2).replace('.', ',');
      document.getElementById('pdv_disponivel').innerText = c.semLimite ? 'ILIMITADO' : 'R$ ' + ((c.limiteTotal||0) - (c.limiteUsado||0)).toFixed(2).replace('.', ',');
      document.getElementById('pdv_atraso').innerText = (c.diasAtraso||0) + ' dias.';
      document.getElementById('pdv_atraso').style.color = (c.diasAtraso > 0) ? '#dc3545' : '#28a745';
      validarLimiteCrediario();
    }

    function validarLimiteCrediario() {
      var alerta = document.getElementById('pdv_alerta_limite'), dispEl = document.getElementById('pdv_disponivel');
      if (!clienteSelecionadoObj || norm(document.getElementById('v_pagto').value) !== 'crediario' || clienteSelecionadoObj.semLimite) {
        if (alerta) alerta.style.display = 'none'; if (dispEl) dispEl.style.color = '#28a745'; return;
      }
      var disp = clienteSelecionadoObj.limiteTotal - clienteSelecionadoObj.limiteUsado;
      dispEl.style.color = totalVendaGlobal > disp ? '#dc3545' : '#28a745';
      alerta.style.display = totalVendaGlobal > disp ? 'block' : 'none';
    }

    function filtrarProdutosDinamico() {
      var termo = norm(document.getElementById('p_busca').value);
      var divLista = document.getElementById('lista-resultados-prod');
      var st = document.getElementById('p_status');

      if (!termo) {
        divLista.style.display = 'none';
        st.innerText = '';
        return;
      }

      var filtrados = produtosEstoqueCache.filter(function(p) {
        return norm(p.desc).includes(termo) || norm(p.id).includes(termo) || norm(p.ean).includes(termo);
      });

      divLista.innerHTML = '';
      if (!filtrados.length) {
        st.style.color = '#dc3545';
        st.innerText = '❌ Nenhum produto encontrado.';
        divLista.style.display = 'none';
        return;
      }

      st.innerText = '';
      filtrados.slice(0, 10).forEach(function(p) {
        var itemDiv = document.createElement('div');
        itemDiv.className = 'result-item';
        itemDiv.innerHTML = '<strong>' + p.desc + '</strong> <span style="color:#666;">(ID: ' + p.id + ' | R$ ' + p.pVenda.toFixed(2).replace('.',',') + ' | Est: ' + p.est + ')</span>';
        itemDiv.onclick = function() { selecionarProdutoResultado(p); };
        divLista.appendChild(itemDiv);
      });
      divLista.style.display = 'block';
    }

    // Passo 1: clicar num resultado da busca só SELECIONA o produto (não adiciona ainda ao carrinho).
    function selecionarProdutoResultado(p) {
      produtoSelecionado = p;
      document.getElementById('p_busca').value = p.desc;
      document.getElementById('lista-resultados-prod').style.display = 'none';
      document.getElementById('p_status').style.color = '#007bff';
      document.getElementById('p_status').innerText = 'ℹ️ Produto selecionado. Informe a quantidade e clique em Confirmar.';
      document.getElementById('p_qtd').focus();
      document.getElementById('p_qtd').select();
    }

    // Passo 2: depois de ajustar a quantidade, clicar em "Confirmar" manda pro carrinho.
    function confirmarAdicaoProduto() {
      var st = document.getElementById('p_status');
      if (!produtoSelecionado) {
        st.style.color = '#dc3545';
        st.innerText = '⚠️ Selecione um produto na lista antes de confirmar.';
        return;
      }
      adicionarAoCarrinhoObj(produtoSelecionado);
      produtoSelecionado = null;
    }

    function adicionarAoCarrinhoObj(p) {
      var qtd = parseInt(document.getElementById('p_qtd').value, 10) || 1;
      if (p.est < qtd) {
        document.getElementById('p_status').style.color = '#dc3545';
        return document.getElementById('p_status').innerText = '⚠️ Est. insuficiente: ' + p.est;
      }

      carrinho.push({
        rowEstoque: p.row,
        ean: p.ean,
        id: p.id,
        desc: p.desc,
        categoria: p.categoria || "Geral",
        preco: p.pVenda,
        qtd: qtd,
        subtotal: p.pVenda * qtd
      });

      document.getElementById('p_status').style.color = '#28a745';
      document.getElementById('p_status').innerText = '✅ Adicionado ao carrinho!';
      document.getElementById('p_busca').value = '';
      document.getElementById('p_qtd').value = '1';
      document.getElementById('lista-resultados-prod').style.display = 'none';
      document.getElementById('p_busca').focus();
      renderCarrinho();
    }

    // Calcula e exibe a taxa da forma de pagamento selecionada (Débito/Crédito), conforme config global.
    function atualizarVisorTaxa() {
      var pagto = norm(document.getElementById('v_pagto').value);
      var box = document.getElementById('box_taxa_cartao');
      if (pagto !== 'debito' && pagto !== 'credito') {
        box.style.display = 'none';
        return 0;
      }
      var taxaPct = pagto === 'debito' ? cfgGlobal.taxaDebito : cfgGlobal.taxaCredito;
      var repasse = pagto === 'debito' ? cfgGlobal.repasseDebito : cfgGlobal.repasseCredito;
      var taxaValor = totalVendaGlobal * (taxaPct / 100);

      box.style.display = 'block';
      document.getElementById('txt_taxa_pct').innerText = taxaPct.toFixed(2).replace('.', ',') + '%';
      document.getElementById('txt_taxa_label').innerText = repasse ? 'Taxa repassada ao cliente:' : 'Taxa (absorvida pela loja):';
      document.getElementById('txt_taxa_valor').innerText = 'R$ ' + taxaValor.toFixed(2).replace('.', ',');
      return repasse ? taxaValor : 0;
    }

    function renderCarrinho() {
      var tbody = document.getElementById('cart_body');
      var elInverso = document.getElementById('v_desconto_inverso');
      tbody.innerHTML = ''; subtotalVendaGlobal = 0;

      if (!carrinho.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#999;">Carrinho vazio.</td></tr>';
        document.getElementById('v_total').innerText = '0,00';
        document.getElementById('count_itens').innerText = '0';
        document.getElementById('v_desconto').value = '0.00';
        if (elInverso) elInverso.innerText = '';
        totalVendaGlobal = 0;
        return calcularTroco();
      }

      carrinho.forEach(function(item, idx){
        subtotalVendaGlobal += item.subtotal;
        tbody.innerHTML += '<tr><td>'+item.desc+'</td><td>'+item.qtd+'</td><td>R$ '+item.preco.toFixed(2).replace('.',',')+'</td><td>R$ '+item.subtotal.toFixed(2).replace('.',',')+'</td><td><button class="btn-del" onclick="removerItem('+idx+')">X</button></td></tr>';
      });

      var pagto = norm(document.getElementById('v_pagto').value);
      var tipoDesc = document.getElementById('v_tipo_desconto') ? document.getElementById('v_tipo_desconto').value : 'R$';
      var descInput = parseFloat(document.getElementById('v_desconto').value) || 0;
      var descMoeda = 0;

      if (pagto === 'crediario') {
        descMoeda = 0;
        document.getElementById('v_desconto').value = '0.00';
        if (elInverso) elInverso.innerText = '';
      } else {
        if (tipoDesc === '%') {
          if (descInput > 100) { descInput = 100; document.getElementById('v_desconto').value = '100'; }
          if (descInput < 0) { descInput = 0; document.getElementById('v_desconto').value = '0'; }
          descMoeda = subtotalVendaGlobal * (descInput / 100);
          if (elInverso) elInverso.innerText = descInput > 0 ? '= R$ ' + descMoeda.toFixed(2).replace('.', ',') : '';
        } else {
          if (descInput > subtotalVendaGlobal) { descInput = subtotalVendaGlobal; document.getElementById('v_desconto').value = descInput.toFixed(2); }
          if (descInput < 0) { descInput = 0; document.getElementById('v_desconto').value = '0.00'; }
          descMoeda = descInput;
          if (elInverso) {
            var porc = subtotalVendaGlobal > 0 ? (descInput / subtotalVendaGlobal) * 100 : 0;
            elInverso.innerText = descInput > 0 ? '= ' + porc.toFixed(2).replace('.', ',') + '%' : '';
          }
        }
      }

      totalVendaGlobal = Math.max(0, subtotalVendaGlobal - descMoeda);

      // Se a taxa de Débito/Crédito estiver configurada pra ser repassada, soma no total cobrado do cliente.
      var taxaRepassadaValor = atualizarVisorTaxa();
      var totalComTaxa = totalVendaGlobal + taxaRepassadaValor;

      document.getElementById('v_total').innerText = totalComTaxa.toFixed(2).replace('.',',');
      document.getElementById('count_itens').innerText = carrinho.length;
      calcularTroco();
      validarLimiteCrediario();
    }

    function calcularTroco() {
      var pagto = norm(document.getElementById('v_pagto').value);
      var boxPago = document.getElementById('box_dinheiro_pago');
      var boxTroco = document.getElementById('box_dinheiro_troco');
     
      if (pagto !== 'dinheiro') {
        if(boxPago) boxPago.style.visibility = 'hidden';
        if(boxTroco) boxTroco.style.visibility = 'hidden';
        return;
      } else {
        if(boxPago) boxPago.style.visibility = 'visible';
        if(boxTroco) boxTroco.style.visibility = 'visible';
      }

      var p = parseFloat(document.getElementById('v_pago').value) || 0, el = document.getElementById('v_troco');
      if (p <= 0) { el.innerText = 'R$ 0,00'; el.style.color = '#007bff'; return; }
      var diff = p - totalVendaGlobal;
      el.innerText = diff < 0 ? 'Falta R$ ' + Math.abs(diff).toFixed(2).replace('.',',') : 'R$ ' + diff.toFixed(2).replace('.',',');
      el.style.color = diff < 0 ? '#d9534f' : '#107c41';
    }

    function removerItem(i){ carrinho.splice(i, 1); renderCarrinho(); }

    function finalizarVenda() {
      var st = document.getElementById('v_status');
      if (!carrinho.length) {
        st.style.color = '#dc3545';
        st.innerText = '⚠️ Carrinho vazio!';
        return;
      }
      var pagtoSel = document.getElementById('v_pagto').value, pagto = norm(pagtoSel), clienteFinal = "À Vista / Consumidor Final";
      if (pagto === 'crediario') {
        if (!clienteSelecionadoObj) {
          st.style.color = '#dc3545';
          st.innerText = '⚠️ Selecione um cliente válido!';
          return;
        }
        clienteFinal = clienteSelecionadoObj.nome;
      }
      
      var tipoDesc = document.getElementById('v_tipo_desconto').value;
      var descInput = parseFloat(document.getElementById('v_desconto').value) || 0;
      var descontoEmReais = 0;
      
      if (pagto !== 'crediario') {
        descontoEmReais = (tipoDesc === '%') ? (subtotalVendaGlobal * (descInput / 100)) : descInput;
      }

      st.style.color = '#007bff';
      st.innerText = '⏳ Processando...';
      google.script.run
        .withSuccessHandler(function(m){
          st.style.color = '#107c41';
          st.innerText = '✅ ' + m;
          setTimeout(function(){ google.script.host.close(); }, 1200);
        })
        .withFailureHandler(function(err){
          st.style.color = '#dc3545';
          st.innerText = '❌ Erro: ' + (err.message || err);
        })
        .processarVendaPDV({ cliente: clienteFinal, pagto: pagtoSel, itens: carrinho, desconto: descontoEmReais });
    }
  </script>
</body>
</html>`;
}

function getHtmlPagamentoCliente() {
  return `<!DOCTYPE html>
<html>
<head>
  <style>
    body{font-family:sans-serif;padding:12px;background:#f8f9fa;margin:0}
    .box{background:#fff;padding:12px;border-radius:6px;box-shadow:0 1px 3px rgba(0,0,0,0.1);margin-bottom:10px;position:relative}
    label{font-size:11px;font-weight:bold;color:#555;display:block;margin-top:6px}
    input,select{width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;box-sizing:border-box;font-size:13px}
    .btn{padding:10px;border:none;border-radius:4px;font-weight:bold;cursor:pointer;width:100%;margin-top:10px;background:#28a745;color:#fff}
    .info-card{background:#f1f3f5;padding:10px;border-radius:6px;margin-top:8px;font-size:12px;border:1px solid #dee2e6}
    .info-line{display:flex;justify-content:space-between;margin-bottom:4px}
    .results-list { margin-top: 4px; max-height: 150px; overflow-y: auto; border: 1px solid #007bff; border-radius: 4px; background: #fff; position: absolute; left: 12px; right: 12px; z-index: 1000; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .result-item { padding: 8px; border-bottom: 1px solid #eee; cursor: pointer; font-size: 12px; }
    .result-item:hover { background: #e8f4fe; color: #007bff; font-weight: bold; }
    .table-prod { width:100%; border-collapse:collapse; margin-top:6px; font-size:11px; }
    .table-prod th, .table-prod td { border:1px solid #dee2e6; padding:6px; text-align:left; }
    .table-prod th { background:#e9ecef; }
  </style>
</head>
<body>
  <div class="box">
    <label>🔎 Buscar Cliente:</label>
    <input type="text" id="pag_cliente_busca" placeholder="Digite Nome, CPF ou ID..." oninput="filtrarClientes()" autocomplete="off">
    <div id="lista-resultados-pag" class="results-list" style="display:none;"></div>
    
    <div id="card_info" class="info-card" style="display:none;">
      <div class="info-line"><span>Limite Total:</span><strong id="txt_limite_total">R$ 0,00</strong></div>
      <div class="info-line"><span>Débito Atual:</span><strong id="txt_debito">R$ 0,00</strong></div>
      <div class="info-line"><span>Uso:</span><strong id="txt_pct_uso">0%</strong></div>
      <div class="info-line" style="margin-top:6px;border-top:1px dashed #ccc;padding-top:6px;"><strong>Status:</strong><strong id="txt_atraso">Atraso: 0 dias.</strong></div>
    </div>
  </div>

  <div id="box_produtos_crediario" class="box" style="display:none; max-height:160px; overflow-y:auto;">
    <div style="font-size:11px; font-weight:bold; color:#007bff; display:flex; justify-content:space-between; align-items:center;">
      <span>🛍️ PRODUTOS COMPRADOS:</span>
      <label style="font-size:11px; font-weight:bold; cursor:pointer; margin:0;">
        <input type="checkbox" id="chk_todos" checked onchange="marcarTodosProdutos(this.checked)"> Selecionar Todos
      </label>
    </div>
    <table class="table-prod">
      <thead>
        <tr>
          <th style="width:30px; text-align:center;">Pagar</th>
          <th>Produto</th>
          <th style="text-align:center; width:40px;">Qtd</th>
          <th style="text-align:right; width:70px;">Valor</th>
        </tr>
      </thead>
      <tbody id="lista_produtos_body"></tbody>
    </table>
  </div>

  <div class="box">
    <label>Forma de Recebimento:</label>
    <select id="pag_forma" onchange="atualizarModoRecebimento()"><option value="Dinheiro">Dinheiro</option><option value="PIX">PIX</option><option value="Débito">Débito</option><option value="Crédito">Crédito</option></select>

    <div class="info-line" style="margin-top:8px;">
      <span>Total dos itens selecionados:</span>
      <strong id="txt_total_selecionado">R$ 0,00</strong>
    </div>

    <label>Valor a Registrar como Pago (R$):</label>
    <input type="number" step="0.01" id="pag_valor" oninput="atualizarModoRecebimento()">
    <div style="font-size:10px;color:#777;margin-top:2px;">Vem preenchido com a soma dos itens marcados acima. Só mude aqui se for um pagamento parcial ou diferente.</div>

    <div id="box_dinheiro_conta" style="display:none;margin-top:10px;">
      <label>Valor Recebido em Dinheiro (R$):</label>
      <input type="number" step="0.01" id="pag_recebido_dinheiro" oninput="calcularTrocoConta()">
      <div class="info-line" style="margin-top:6px;">
        <span>Troco:</span>
        <strong id="txt_troco_conta" style="color:#007bff;">R$ 0,00</strong>
      </div>
    </div>

    <div id="box_taxa_conta" class="info-card" style="display:none;margin-top:10px;">
      <div class="info-line"><span>Taxa da forma de pagamento:</span><strong id="txt_taxa_pct_conta">0%</strong></div>
      <div class="info-line"><span id="txt_taxa_label_conta">Taxa (absorvida pela loja):</span><strong id="txt_taxa_valor_conta">R$ 0,00</strong></div>
    </div>

    <button class="btn" onclick="confirmarPagamento()">💵 CONFIRMAR RECEBIMENTO</button>
    <div id="pag_status" style="font-size:12px;text-align:center;margin-top:10px;font-weight:bold;min-height:18px;"></div>
  </div>

  <script>
    var listaClientes = [], clienteSelecionado = null;
    var cfgGlobal = { taxaDebito: 0, diasDebito: 0, taxaCredito: 0, diasCredito: 0, taxaPix: 0, repasseDebito: false, repasseCredito: false };

    window.onload = function() {
      google.script.run.withSuccessHandler(function(d){ listaClientes = d || []; }).obterClientesDaPlanilhaExterna();
      google.script.run.withSuccessHandler(function(cfg){ cfgGlobal = cfg || cfgGlobal; atualizarModoRecebimento(); }).obterConfiguracoes();
      atualizarModoRecebimento();
    };

    function norm(t){ return t ? t.toString().toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim() : ""; }

    function filtrarClientes() {
      var termo = norm(document.getElementById('pag_cliente_busca').value);
      var divLista = document.getElementById('lista-resultados-pag');
      var card = document.getElementById('card_info');
      var boxProd = document.getElementById('box_produtos_crediario');

      if (!termo) {
        divLista.style.display = 'none';
        card.style.display = 'none';
        if (boxProd) boxProd.style.display = 'none';
        clienteSelecionado = null;
        return;
      }

      var filtrados = listaClientes.filter(function(c) {
        return norm(c.nome).includes(termo) || norm(c.id).includes(termo) || (c.cpf && norm(c.cpf).includes(termo));
      });

      divLista.innerHTML = '';
      if (!filtrados.length) {
        divLista.style.display = 'none';
        return;
      }

      filtrados.slice(0, 10).forEach(function(c) {
        var itemDiv = document.createElement('div');
        itemDiv.className = 'result-item';
        itemDiv.innerHTML = '<strong>' + c.nome + '</strong>' + (c.cpf ? ' <span style="color:#666;">(' + c.cpf + ')</span>' : '');
        itemDiv.onclick = function() { selecionarCliente(c); };
        divLista.appendChild(itemDiv);
      });
      divLista.style.display = 'block';
    }

    function selecionarCliente(c) {
      clienteSelecionado = c;
      document.getElementById('pag_cliente_busca').value = c.nome;
      document.getElementById('lista-resultados-pag').style.display = 'none';

      var card = document.getElementById('card_info');
      var debito = c.limiteUsado, limite = c.limiteTotal, semLimite = c.semLimite;
      var pct = (!semLimite && limite > 0) ? (debito / limite) * 100 : (!semLimite && debito > 0 ? 100 : 0);
      var cor = (pct >= 100 || (!semLimite && limite > 0 && debito >= limite)) ? '#dc3545' : (pct > 80 ? '#d39e00' : '#28a745');
      
      document.getElementById('txt_limite_total').innerText = semLimite ? 'ILIMITADO' : 'R$ ' + limite.toFixed(2).replace('.', ',');
      document.getElementById('txt_debito').innerText = 'R$ ' + debito.toFixed(2).replace('.', ',');
      document.getElementById('txt_debito').style.color = cor;
      document.getElementById('txt_pct_uso').innerText = semLimite ? 'N/A' : pct.toFixed(1).replace('.', ',') + '%';
      document.getElementById('txt_pct_uso').style.color = cor;
      document.getElementById('txt_atraso').innerText = 'Atraso: ' + (c.diasAtraso || 0) + ' dias.';
      document.getElementById('txt_atraso').style.color = (c.diasAtraso > 0) ? '#dc3545' : '#28a745';
      card.style.display = 'block';

      carregarProdutosCrediario(c.nome);
    }

    function carregarProdutosCrediario(nomeCliente) {
      var boxProd = document.getElementById('box_produtos_crediario');
      var tbody = document.getElementById('lista_produtos_body');
      tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:8px;">⏳ Buscando produtos...</td></tr>';
      boxProd.style.display = 'block';

      google.script.run.withSuccessHandler(function(itens) {
        tbody.innerHTML = '';
        if (!itens || !itens.length) {
          tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:#777; padding:8px;">Nenhum produto individual no histórico. Digite o valor abaixo.</td></tr>';
          document.getElementById('chk_todos').checked = false;
          return;
        }

        document.getElementById('chk_todos').checked = true;
        itens.forEach(function(item) {
          var tr = document.createElement('tr');
          tr.innerHTML = '<td style="text-align:center;"><input type="checkbox" class="chk-prod-item" data-preco="' + item.preco + '" checked onchange="recalcularTotalProdutos()"></td>' +
                         '<td>' + item.desc + '</td>' +
                         '<td style="text-align:center;">' + item.qtd + '</td>' +
                         '<td style="text-align:right;">R$ ' + item.preco.toFixed(2).replace('.', ',') + '</td>';
          tbody.appendChild(tr);
        });

        recalcularTotalProdutos();
      }).obterItensCrediarioCliente(nomeCliente);
    }

    function marcarTodosProdutos(status) {
      var chks = document.querySelectorAll('.chk-prod-item');
      chks.forEach(function(c) { c.checked = status; });
      recalcularTotalProdutos();
    }

    function recalcularTotalProdutos() {
      var chks = document.querySelectorAll('.chk-prod-item');
      var total = 0, todosMarcados = chks.length > 0;

      chks.forEach(function(c) {
        if (c.checked) {
          total += parseFloat(c.getAttribute('data-preco')) || 0;
        } else {
          todosMarcados = false;
        }
      });

      if (chks.length > 0) {
        document.getElementById('chk_todos').checked = todosMarcados;
        document.getElementById('pag_valor').value = total.toFixed(2);
      }
      document.getElementById('txt_total_selecionado').innerText = 'R$ ' + total.toFixed(2).replace('.', ',');
      atualizarModoRecebimento();
    }

    // Mostra/esconde o bloco de troco (Dinheiro) ou o bloco de taxa (Débito/Crédito), conforme a forma escolhida.
    function atualizarModoRecebimento() {
      var forma = norm(document.getElementById('pag_forma').value);
      var boxDinheiro = document.getElementById('box_dinheiro_conta');
      var boxTaxa = document.getElementById('box_taxa_conta');
      var valor = parseFloat(document.getElementById('pag_valor').value) || 0;

      if (forma === 'dinheiro') {
        boxDinheiro.style.display = 'block';
        boxTaxa.style.display = 'none';
        calcularTrocoConta();
      } else if (forma === 'debito' || forma === 'credito') {
        boxDinheiro.style.display = 'none';
        boxTaxa.style.display = 'block';

        var taxaPct = forma === 'debito' ? cfgGlobal.taxaDebito : cfgGlobal.taxaCredito;
        var repasse = forma === 'debito' ? cfgGlobal.repasseDebito : cfgGlobal.repasseCredito;
        var taxaValor = valor * (taxaPct / 100);

        document.getElementById('txt_taxa_pct_conta').innerText = taxaPct.toFixed(2).replace('.', ',') + '%';
        document.getElementById('txt_taxa_label_conta').innerText = repasse ? 'Taxa repassada ao cliente:' : 'Taxa (absorvida pela loja):';
        document.getElementById('txt_taxa_valor_conta').innerText = 'R$ ' + taxaValor.toFixed(2).replace('.', ',');
      } else {
        boxDinheiro.style.display = 'none';
        boxTaxa.style.display = 'none';
      }
    }

    function calcularTrocoConta() {
      var valor = parseFloat(document.getElementById('pag_valor').value) || 0;
      var recebido = parseFloat(document.getElementById('pag_recebido_dinheiro').value) || 0;
      var troco = Math.max(0, recebido - valor);
      document.getElementById('txt_troco_conta').innerText = 'R$ ' + troco.toFixed(2).replace('.', ',');
    }

    function confirmarPagamento() {
      var val = parseFloat(document.getElementById('pag_valor').value), forma = document.getElementById('pag_forma').value;
      var st = document.getElementById('pag_status');

      if (!clienteSelecionado || !val || val <= 0) {
        st.style.color = '#dc3545';
        st.innerText = '⚠️ Selecione um cliente e um valor válido!';
        return;
      }

      var recebidoDinheiro = val;
      if (norm(forma) === 'dinheiro') {
        recebidoDinheiro = parseFloat(document.getElementById('pag_recebido_dinheiro').value) || 0;
        if (recebidoDinheiro < val) {
          st.style.color = '#dc3545';
          st.innerText = '⚠️ Valor recebido em dinheiro é menor que o valor a pagar!';
          return;
        }
      }

      st.style.color = '#007bff';
      st.innerText = '⏳ Processando pagamento...';
      google.script.run
        .withSuccessHandler(function(res){
          if (res.sucesso) {
            st.style.color = '#107c41';
            st.innerText = res.mensagem;
            setTimeout(function(){ google.script.host.close(); }, 1500);
          } else {
            st.style.color = '#dc3545';
            st.innerText = '❌ ' + res.mensagem;
          }
        })
        .withFailureHandler(function(err){
          st.style.color = '#dc3545';
          st.innerText = '❌ Erro: ' + (err.message || err);
        })
        .processarPagamentoContaCliente(clienteSelecionado.id, val, forma, recebidoDinheiro);
    }
  </script>
</body>
</html>`;
}

function getHtmlBuscaClientes() {
  return `<!DOCTYPE html>
<html>
<head>
  <base target="_top">
  <style>
    body{font-family:Arial,sans-serif;padding:10px;font-size:13px;color:#333;background:#f4f6f9}
    .busca-box{width:100%;padding:10px;box-sizing:border-box;border:2px solid #007bff;border-radius:6px;font-size:14px;margin-bottom:12px}
    .card-cliente{background:#fff;border:1px solid #dcdcdc;margin-bottom:10px;border-radius:6px;padding:12px}
    .topo-card{display:flex;justify-content:space-between;margin-bottom:6px}
    .nome-cliente{font-size:15px;font-weight:bold;color:#0056b3}
    .badge-id{background:#e9ecef;padding:2px 6px;border-radius:4px;font-size:11px;font-weight:bold}
    .alerta-obs{background:#fff3cd;color:#856404;padding:6px;border-radius:4px;margin:6px 0;font-size:12px;font-weight:bold}
    .alerta-trava{background:#f8d7da;color:#721c24;padding:6px;border-radius:4px;margin:6px 0;font-size:12px;font-weight:bold}
    .info-linha{display:flex;justify-content:space-between;margin:4px 0;font-size:12px}
  </style>
</head>
<body>
  <input type="text" id="campoBusca" class="busca-box" placeholder="🔎 Digite Nome, CPF ou Telefone..." onkeyup="filtrar()">
  <div id="resultado">Carregando clientes...</div>
  <script>
    var listaClientes = [];
    google.script.run.withSuccessHandler(function(d){ listaClientes = d || []; renderizar(listaClientes); }).obterClientesDaPlanilhaExterna();
    function norm(t){ return t ? t.toString().toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim() : ""; }
    function renderizar(lista) {
      var cont = document.getElementById('resultado');
      if (!lista.length) return cont.innerHTML = '<p style="color:#6c757d;text-align:center;">Nenhum cliente encontrado.</p>';
      var html = '';
      lista.forEach(function(c) {
        var dispTexto = typeof c.disponivel === 'number' ? 'R$ ' + c.disponivel.toFixed(2) : c.disponivel;
        html += '<div class="card-cliente"><div class="topo-card"><span class="nome-cliente">' + c.nome + '</span><span class="badge-id">' + c.id + '</span></div>' +
          '<div style="font-size:11px;color:#666;margin-bottom:6px;">📱 ' + (c.celular||'S/ Tel') + ' | 📄 CPF: ' + (c.cpf||'S/ CPF') + '</div>' +
          (c.somenteTitular ? '<div class="alerta-trava">🚫 APENAS TITULAR PODE COMPRAR</div>' : '') +
          (c.obs ? '<div class="alerta-obs">⚠️ AVISO: ' + c.obs + '</div>' : '') +
          (c.dependentes ? '<div style="font-size:11px;color:#555;">👥 Autorizados: ' + c.dependentes + '</div>' : '') +
          '<div class="info-linha"><span>Débito: <strong style="color:#dc3545">R$ ' + c.limiteUsado.toFixed(2) + '</strong></span><span>Disp: <strong style="color:#28a745">' + dispTexto + '</strong></span></div>' +
          '<div class="info-linha"><span style="font-weight:bold;color:' + (c.diasAtraso>0?'#dc3545':'#28a745') + ';">Atraso: ' + (c.diasAtraso||0) + ' dias.</span></div></div>';
      });
      cont.innerHTML = html;
    }
    function filtrar() {
      var q = norm(document.getElementById('campoBusca').value);
      renderizar(!q ? listaClientes : listaClientes.filter(function(c){
        return norm(c.id).includes(q) || norm(c.nome).includes(q) || norm(c.cpf).includes(q) || norm(c.celular).includes(q) || norm(c.dependentes).includes(q);
      }));
    }
  </script>
</body>
</html>`;
}

function getHtmlConfiguracoes() {
  return `<!DOCTYPE html>
<html>
<head>
  <style>
    body{font-family:Arial,sans-serif;padding:12px;background:#f8f9fa;margin:0}
    .box{background:#fff;padding:12px;border-radius:6px;box-shadow:0 1px 3px rgba(0,0,0,0.12);margin-bottom:10px}
    label{font-size:11px;font-weight:bold;color:#555;display:block;margin-top:6px}
    input{width:100%;padding:6px;border:1px solid #ccc;border-radius:4px;box-sizing:border-box;font-size:12px}
    .grid-2{display:grid;grid-template-columns:1fr 1fr;gap:8px}
    .btn{padding:10px;border:none;border-radius:4px;font-weight:bold;cursor:pointer;width:100%;margin-top:10px;background:#107c41;color:#fff}
    .title{font-size:14px;font-weight:bold;margin-bottom:8px;color:#107c41;border-bottom:1px solid #ddd;padding-bottom:4px}
  </style>
</head>
<body>
  <div class="box">
    <div class="title">💳 Taxas de Pagamento (%)</div>
    <div class="grid-2">
      <div><label>Taxa Débito (%):</label><input type="number" step="0.01" id="cfg_taxa_debito"></div>
      <div><label>Dias Débito:</label><input type="number" id="cfg_dias_debito"></div>
      <div><label>Taxa Crédito (%):</label><input type="number" step="0.01" id="cfg_taxa_credito"></div>
      <div><label>Dias Crédito:</label><input type="number" id="cfg_dias_credito"></div>
      <div><label>Taxa PIX (%):</label><input type="number" step="0.01" id="cfg_taxa_pix"></div>
      <div><label>Taxa Crediário (%):</label><input type="number" step="0.01" id="cfg_taxa_crediario"></div>
    </div>
  </div>
  <div class="box">
    <div class="title">🔁 Repasse de Taxa ao Cliente</div>
    <label style="display:flex;align-items:center;gap:6px;font-size:12px;margin-top:8px;cursor:pointer;">
      <input type="checkbox" id="cfg_repasse_debito" style="width:auto;"> Repassar taxa de Débito ao cliente (cliente paga o valor + a taxa)
    </label>
    <label style="display:flex;align-items:center;gap:6px;font-size:12px;margin-top:10px;cursor:pointer;">
      <input type="checkbox" id="cfg_repasse_credito" style="width:auto;"> Repassar taxa de Crédito ao cliente (cliente paga o valor + a taxa)
    </label>
    <div style="font-size:10px;color:#777;margin-top:8px;">Se desmarcado, a loja absorve a taxa (recebe o valor do produto menos a taxa).</div>
  </div>
  <button class="btn" onclick="salvar()">💾 SALVAR CONFIGURAÇÕES</button>
  <script>
    window.onload = function() {
      google.script.run.withSuccessHandler(function(cfg){
        document.getElementById('cfg_taxa_debito').value = cfg.taxaDebito;
        document.getElementById('cfg_dias_debito').value = cfg.diasDebito;
        document.getElementById('cfg_taxa_credito').value = cfg.taxaCredito;
        document.getElementById('cfg_dias_credito').value = cfg.diasCredito;
        document.getElementById('cfg_taxa_pix').value = cfg.taxaPix;
        document.getElementById('cfg_taxa_crediario').value = cfg.taxaCrediario;
        document.getElementById('cfg_repasse_debito').checked = !!cfg.repasseDebito;
        document.getElementById('cfg_repasse_credito').checked = !!cfg.repasseCredito;
      }).obterConfiguracoes();
    };
    function salvar() {
      google.script.run.withSuccessHandler(function(m){ alert(m); google.script.host.close(); }).salvarConfiguracoes({
        taxaDebito: parseFloat(document.getElementById('cfg_taxa_debito').value) || 0,
        diasDebito: parseInt(document.getElementById('cfg_dias_debito').value, 10) || 0,
        taxaCredito: parseFloat(document.getElementById('cfg_taxa_credito').value) || 0,
        diasCredito: parseInt(document.getElementById('cfg_dias_credito').value, 10) || 0,
        taxaPix: parseFloat(document.getElementById('cfg_taxa_pix').value) || 0,
        taxaCrediario: parseFloat(document.getElementById('cfg_taxa_crediario').value) || 0,
        repasseDebito: document.getElementById('cfg_repasse_debito').checked,
        repasseCredito: document.getElementById('cfg_repasse_credito').checked
      });
    }
  </script>
</body>
</html>`;
}

/**
 * RELATÓRIO DE VENDAS — usa a mesma ideia visual do dashboard de gestão financeira,
 * adaptada pros dados de venda (histórico dos caixas fechados).
 */
function getHtmlRelatorioVendas() {
  return `<!DOCTYPE html>
<html>
<head>
  <base target="_top">
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, sans-serif; }
    body { background: #f8f9fa; margin: 0; padding: 12px; font-size: 12px; color: #333; }
    .card-modal { background: #fff; border-radius: 12px; padding: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); }
    .header-dash { display: flex; align-items: center; justify-content: space-between; border-bottom: 2px solid #f1f3f5; padding-bottom: 8px; margin-bottom: 12px; }
    .titulo-modal { font-size: 15px; font-weight: bold; color: #0f172a; display: flex; align-items: center; gap: 6px; }
    .filtros-bar { display: flex; gap: 8px; align-items: center; background: #f1f5f9; padding: 6px 12px; border-radius: 8px; }
    .filtros-bar label { font-size: 10px; font-weight: bold; color: #475569; text-transform: uppercase; margin-right: 2px; }
    .filtros-bar select { padding: 4px 8px; border-radius: 6px; border: 1px solid #cbd5e1; font-size: 11px; background: white; outline: none; }
    .kpi-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-bottom: 12px; }
    .kpi-box { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px; text-align: center; }
    .kpi-val { font-size: 13px; font-weight: bold; margin-top: 3px; }
    .kpi-title { font-size: 8px; text-transform: uppercase; color: #64748b; font-weight: 700; }
    .charts-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .chart-card { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; margin-bottom: 10px; }
    .chart-title { font-weight: bold; font-size: 11px; color: #334155; margin-bottom: 8px; }
    .chart-container { position: relative; height: 200px; width: 100%; }
    .btn-fechar { padding: 8px 16px; background: #0f172a; color: white; border: none; border-radius: 20px; font-weight: bold; cursor: pointer; float: right; margin-top: 5px; font-size: 11px; }
    .btn-fechar:hover { background: #334155; }
  </style>
</head>
<body>
  <div class="card-modal">
    <div class="header-dash">
      <div class="titulo-modal">📊 RELATÓRIO DE VENDAS</div>
      <div class="filtros-bar">
        <label>📅 Mês:</label>
        <select id="filtroMes" onchange="carregarRelatorio()">
          <option value="TODOS">Todos os Meses</option>
          <option value="1">Janeiro</option><option value="2">Fevereiro</option><option value="3">Março</option>
          <option value="4">Abril</option><option value="5">Maio</option><option value="6">Junho</option>
          <option value="7">Julho</option><option value="8">Agosto</option><option value="9">Setembro</option>
          <option value="10">Outubro</option><option value="11">Novembro</option><option value="12">Dezembro</option>
        </select>
        <label>Ano:</label>
        <select id="filtroAno" onchange="carregarRelatorio()"><option value="TODOS">Todos</option></select>
      </div>
    </div>

    <div class="kpi-grid">
      <div class="kpi-box"><div class="kpi-title">Total Vendido (Bruto)</div><div class="kpi-val" id="kpiBruto" style="color:#0f172a;">R$ 0,00</div></div>
      <div class="kpi-box"><div class="kpi-title">Total Recebido (Líquido)</div><div class="kpi-val" id="kpiLiquido" style="color:#16a34a;">R$ 0,00</div></div>
      <div class="kpi-box" style="background:#f3e8ff;border-color:#d8b4fe;"><div class="kpi-title" style="color:#6b21a8;">💸 Custo em Taxas</div><div class="kpi-val" id="kpiTaxas" style="color:#7c3aed;">R$ 0,00</div></div>
      <div class="kpi-box"><div class="kpi-title">💵 Dinheiro Já Disponível</div><div class="kpi-val" id="kpiDisponivel" style="color:#0ea5e9;">R$ 0,00</div></div>
      <div class="kpi-box" style="background:#fff8e6;border-color:#ffe199;"><div class="kpi-title" style="color:#856404;">⏳ Dinheiro Futuro (A Cair)</div><div class="kpi-val" id="kpiFuturo" style="color:#d97706;">R$ 0,00</div></div>
    </div>

    <div class="charts-grid">
      <div class="chart-card">
        <div class="chart-title">💳 Vendas por Forma de Pagamento</div>
        <div class="chart-container"><canvas id="chartFormaPagto"></canvas></div>
      </div>
      <div class="chart-card">
        <div class="chart-title">📌 Vendas por Categoria</div>
        <div class="chart-container"><canvas id="chartCategoria"></canvas></div>
      </div>
      <div class="chart-card" style="grid-column: span 2;">
        <div class="chart-title">📈 Evolução Mensal — Bruto x Líquido</div>
        <div class="chart-container"><canvas id="chartEvolucao"></canvas></div>
      </div>
    </div>

    <button class="btn-fechar" onclick="google.script.host.close()">Fechar Painel</button>
  </div>

  <script>
    let chartFormaObj = null, chartCatObj = null, chartEvolObj = null;
    function fmtBRL(n) { return 'R$ ' + (n || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }

    document.addEventListener('DOMContentLoaded', function() { carregarRelatorio(true); });

    function carregarRelatorio(primeiraCarga) {
      const m = document.getElementById('filtroMes').value;
      const a = document.getElementById('filtroAno').value;

      google.script.run.withSuccessHandler(function(data) {
        document.getElementById('kpiBruto').innerText = fmtBRL(data.totalVendidoBruto);
        document.getElementById('kpiLiquido').innerText = fmtBRL(data.totalRecebidoLiquido);
        document.getElementById('kpiTaxas').innerText = fmtBRL(data.totalTaxas);
        document.getElementById('kpiDisponivel').innerText = fmtBRL(data.dinheiroJaDisponivel);
        document.getElementById('kpiFuturo').innerText = fmtBRL(data.dinheiroFuturo);

        if (primeiraCarga) {
          const selAno = document.getElementById('filtroAno');
          selAno.innerHTML = '<option value="TODOS">Todos os Anos</option>';
          data.anosDisponiveis.forEach(function(ano) {
            const opt = document.createElement('option');
            opt.value = ano; opt.textContent = ano;
            selAno.appendChild(opt);
          });
        }

        renderizarFormaPagamento(data.porFormaPagamento);
        renderizarCategoria(data.porCategoria);
        renderizarEvolucao(data.evolucaoMensal);
      }).obterDadosRelatorioVendas(m, a);
    }

    function renderizarFormaPagamento(mapa) {
      const ctx = document.getElementById('chartFormaPagto').getContext('2d');
      if (chartFormaObj) chartFormaObj.destroy();
      const labels = Object.keys(mapa), valores = Object.values(mapa);
      chartFormaObj = new Chart(ctx, {
        type: 'doughnut',
        data: { labels: labels.length ? labels : ['Sem dados'], datasets: [{ data: valores.length ? valores : [1], backgroundColor: ['#16a34a','#0284c7','#d97706','#8b5cf6','#dc3545','#ec4899'] }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { boxWidth: 8, font: { size: 9 } } } } }
      });
    }

    function renderizarCategoria(mapa) {
      const ctx = document.getElementById('chartCategoria').getContext('2d');
      if (chartCatObj) chartCatObj.destroy();
      const labels = Object.keys(mapa), valores = Object.values(mapa);
      chartCatObj = new Chart(ctx, {
        type: 'bar',
        data: { labels: labels.length ? labels : ['Sem dados'], datasets: [{ label: 'Vendas (R$)', data: valores.length ? valores : [0], backgroundColor: '#0ea5e9', borderRadius: 4 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { ticks: { font: { size: 9 } } }, y: { ticks: { font: { size: 9 } } } } }
      });
    }

    function renderizarEvolucao(evol) {
      const ctx = document.getElementById('chartEvolucao').getContext('2d');
      if (chartEvolObj) chartEvolObj.destroy();
      chartEvolObj = new Chart(ctx, {
        data: {
          labels: evol.labels,
          datasets: [
            { type: 'bar', label: 'Vendido (Bruto)', data: evol.bruto, backgroundColor: '#94a3b8', borderRadius: 4 },
            { type: 'line', label: 'Recebido (Líquido)', data: evol.liquido, borderColor: '#16a34a', borderWidth: 2, tension: 0.3, fill: false }
          ]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top', labels: { boxWidth: 8, font: { size: 9 } } } }, scales: { x: { ticks: { font: { size: 8 } } }, y: { ticks: { font: { size: 8 } } } } }
      });
    }
  </script>
</body>
</html>`;
}


/**
 * TELA DE EXCLUIR VENDA — lista as vendas do caixa aberto pra escolher qual apagar,
 * sem precisar selecionar a linha certa na planilha antes.
 */
function getHtmlExcluirVenda() {
  return `<!DOCTYPE html>
<html>
<head>
  <base target="_top">
  <style>
    * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, sans-serif; }
    body { background: #f8f9fa; margin: 0; padding: 14px; font-size: 12px; color: #333; }
    .titulo { font-size: 15px; font-weight: bold; color: #0f172a; margin-bottom: 10px; display: flex; align-items: center; gap: 6px; }
    input#busca { width: 100%; padding: 8px; border-radius: 6px; border: 1px solid #cbd5e1; margin-bottom: 10px; font-size: 12px; }
    .lista { max-height: 440px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 8px; }
    .venda-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border-bottom: 1px solid #f1f5f9; }
    .venda-item:last-child { border-bottom: none; }
    .venda-info { flex: 1; }
    .venda-desc { font-weight: bold; color: #1e293b; }
    .venda-meta { font-size: 10px; color: #64748b; margin-top: 2px; }
    .venda-preco { font-weight: bold; color: #16a34a; margin-right: 10px; white-space: nowrap; }
    .btn-excluir { background: #dc3545; color: white; border: none; border-radius: 6px; padding: 6px 10px; font-size: 11px; font-weight: bold; cursor: pointer; }
    .btn-excluir:hover { background: #b02a37; }
    .vazio { text-align: center; padding: 30px; color: #94a3b8; }
    #status { text-align: center; font-weight: bold; margin-top: 10px; min-height: 18px; }
  </style>
</head>
<body>
  <div class="titulo">🗑️ Excluir Venda do Caixa Aberto</div>
  <input type="text" id="busca" placeholder="🔎 Filtrar por produto, cliente ou forma de pagamento..." oninput="renderizarLista()">
  <div class="lista" id="lista-vendas"><div class="vazio">Carregando vendas...</div></div>
  <div id="status"></div>

  <script>
    var todasVendas = [];

    window.onload = function() {
      google.script.run.withSuccessHandler(function(vendas) {
        todasVendas = vendas || [];
        renderizarLista();
      }).obterVendasParaExclusao();
    };

    function renderizarLista() {
      var filtro = document.getElementById('busca').value.toLowerCase();
      var div = document.getElementById('lista-vendas');
      div.innerHTML = '';

      var filtradas = todasVendas.filter(function(v) {
        var texto = (v.desc + ' ' + v.pagto + ' ' + v.cliente).toLowerCase();
        return texto.includes(filtro);
      });

      if (filtradas.length === 0) {
        div.innerHTML = '<div class="vazio">Nenhuma venda encontrada no caixa aberto.</div>';
        return;
      }

      filtradas.forEach(function(v) {
        var item = document.createElement('div');
        item.className = 'venda-item';
        var meta = v.hora + ' • ' + v.pagto + (v.cliente ? ' • ' + v.cliente : '') + ' • Qtd: ' + v.qtd;
        item.innerHTML =
          '<div class="venda-info"><div class="venda-desc">' + v.desc + '</div><div class="venda-meta">' + meta + '</div></div>' +
          '<div class="venda-preco">R$ ' + v.preco.toFixed(2).replace('.', ',') + '</div>' +
          '<button class="btn-excluir" data-linha="' + v.linha + '" data-desc="' + v.desc.replace(/"/g, '&quot;') + '">🗑️ Excluir</button>';
        item.querySelector('.btn-excluir').onclick = function() { confirmarExclusao(v.linha, v.desc); };
        div.appendChild(item);
      });
    }

    function confirmarExclusao(linha, desc) {
      if (!confirm('Tem certeza que quer excluir esta venda?\\n\\n' + desc + '\\n\\nEssa ação não pode ser desfeita.')) return;

      var st = document.getElementById('status');
      st.style.color = '#007bff';
      st.innerText = '⏳ Excluindo...';

      google.script.run
        .withSuccessHandler(function(res) {
          st.style.color = res.sucesso ? '#107c41' : '#dc3545';
          st.innerText = res.mensagem;
          if (res.sucesso) {
            todasVendas = todasVendas.filter(function(v) { return v.linha !== linha; });
            renderizarLista();
          }
        })
        .withFailureHandler(function(err) {
          st.style.color = '#dc3545';
          st.innerText = '❌ Erro: ' + (err.message || err);
        })
        .excluirVendaPorLinha(linha);
    }
  </script>
</body>
</html>`;
}
/**
 * DIAGNÓSTICO: roda essa função direto pelo editor (selecionar no menu > Executar)
 * e olha o Registro de Execução. Ela mostra o cabeçalho real da linha 6 e pra qual
 * campo cada coluna foi mapeada — assim a gente vê exatamente onde "Dias a Liquidar"
 * está caindo (ou não caindo em lugar nenhum).
 */
function debugMapeamentoColunas() {
  const sheetCaixa = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("CAIXA") || SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const headers = sheetCaixa.getRange(6, 1, 1, Math.max(sheetCaixa.getLastColumn(), 15)).getValues()[0];

  Logger.log("=== CABEÇALHO BRUTO DA LINHA 6 ===");
  headers.forEach((h, idx) => {
    Logger.log("Coluna " + colunaParaLetraDebug(idx + 1) + " (índice " + (idx + 1) + "): \"" + h + "\"");
  });

  Logger.log("=== MAPEAMENTO RESULTANTE ===");
  const mapa = getMapeamentoColunas(sheetCaixa);
  Logger.log(JSON.stringify(mapa, null, 2));

  if (mapa.liquidado) {
    Logger.log("✅ 'Dias a Liquidar' mapeado pra coluna " + colunaParaLetraDebug(mapa.liquidado));
  } else {
    Logger.log("❌ 'Dias a Liquidar' NÃO FOI ENCONTRADO em nenhuma coluna!");
  }
}

function colunaParaLetraDebug(col) {
  let letra = "";
  while (col > 0) {
    const resto = (col - 1) % 26;
    letra = String.fromCharCode(65 + resto) + letra;
    col = Math.floor((col - 1) / 26);
  }
  return letra;
}

/**
 * ============================================================================
 * CAIXA — VENDA EXTERNA / OUTRAS ENTRADAS + CONTRATO DE ASSINATURA
 * Cole no FINAL do Código.gs do Caixa (não apaga nada, só acrescenta).
 * ============================================================================
 *
 * VENDA EXTERNA: vendas feitas fora do balcão — marketplace, delivery, WhatsApp com
 * entrega, etc. Cada uma pode ter várias deduções diferentes ao mesmo tempo:
 * Taxa da Plataforma (%), Frete, Desconto e Custo de Entrega/Motoboy — tudo somado
 * separado, pra você ver exatamente pra onde foi cada pedacinho do valor bruto.
 *
 * CONTRATO DE ASSINATURA: pra receita recorrente (assinatura de cliente, aluguel de
 * imóvel, mensalidade) — você cadastra o contrato uma vez (valor, duração) e o sistema
 * já cria TODAS as parcelas futuras de uma vez, cada uma na data certa — igual o
 * empréstimo faz na aba Saídas, só que aqui é dinheiro ENTRANDO, não saindo.
 *
 * As linhas criadas aqui entram na mesma planilha CAIXA, nas mesmas colunas de sempre —
 * então já aparecem sozinhas no Relatório de Vendas, no DRE e no Balancete do CFAUTO.
 */

function abrirJanelaVendaExterna() {
  const html = HtmlService.createHtmlOutput(getHtmlVendaExterna()).setWidth(460).setHeight(900);
  SpreadsheetApp.getUi().showModalDialog(html, "💻 Venda Externa / Assinatura");
}

function parseDataInputExterna(str) {
  if (!str) return new Date();
  const partes = str.split("-").map(Number);
  return new Date(partes[0], partes[1] - 1, partes[2]);
}

/**
 * Escreve UMA linha de entrada na planilha CAIXA — usada tanto pela Venda Externa
 * (uma vez) quanto pelo Contrato de Assinatura (uma vez pra cada parcela).
 * ehFutura=true grava "FUTURO" na coluna de Dias a Liquidar em vez de um número —
 * isso avisa o painel e o fechamento de caixa que essa linha ainda não aconteceu de
 * verdade, então não deve contar no total de hoje.
 */
function escreverLinhaEntradaExterna(sheetCaixa, mapa, dados, ehFutura) {
  const maxCol = Math.max(...Object.values(mapa), 13);
  const targetRow = Math.max(sheetCaixa.getLastRow() + 1, 7);
  const rowData = new Array(maxCol).fill("");
  const tz = Session.getScriptTimeZone();

  const dataHoraTexto = Utilities.formatDate(dados.dataVenda, tz, "dd/MM/yyyy HH:mm:ss");
  const dataRecalc = new Date(dados.dataVenda.getTime());
  dataRecalc.setDate(dataRecalc.getDate() + dados.dias);
  const dataRecebidoTexto = Utilities.formatDate(dataRecalc, tz, "dd/MM/yyyy");

  if (mapa.desc) rowData[mapa.desc - 1] = dados.descricao;
  if (mapa.categoria) rowData[mapa.categoria - 1] = dados.categoria;
  if (mapa.preco) rowData[mapa.preco - 1] = dados.valorBruto;
  if (mapa.qtd) rowData[mapa.qtd - 1] = 1;
  if (mapa.pagto) rowData[mapa.pagto - 1] = "Externa";
  if (mapa.liquidado) rowData[mapa.liquidado - 1] = ehFutura ? "FUTURO" : dados.dias;
  if (mapa.dataRecebimento) rowData[mapa.dataRecebimento - 1] = dataRecebidoTexto;
  if (mapa.taxa) rowData[mapa.taxa - 1] = Number(dados.totalDeducoes.toFixed(2));
  if (mapa.recebido) rowData[mapa.recebido - 1] = Number(dados.valorLiquido.toFixed(2));
  if (mapa.hora) rowData[mapa.hora - 1] = dataHoraTexto;
  if (mapa.cliente) rowData[mapa.cliente - 1] = dados.origem || "";

  sheetCaixa.getRange(targetRow, 1, 1, maxCol).setValues([rowData]);
  if (mapa.taxa) sheetCaixa.getRange(targetRow, mapa.taxa).setNumberFormat('R$ #,##0.00');
  if (mapa.recebido) sheetCaixa.getRange(targetRow, mapa.recebido).setNumberFormat('R$ #,##0.00');
}

function salvarVendaExterna(dados) {
  try {
    const sheetCaixa = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("CAIXA") || SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    const mapa = getMapeamentoColunas(sheetCaixa);

    const valorBruto = parseFloat(dados.valor) || 0;
    const taxaPct = parseFloat(dados.taxaPct) || 0;
    const frete = parseFloat(dados.frete) || 0;
    const desconto = parseFloat(dados.desconto) || 0;
    const custoEntrega = parseFloat(dados.custoEntrega) || 0;
    const dias = parseInt(dados.dias, 10) || 0;

    const taxaValor = valorBruto * (taxaPct / 100);
    const totalDeducoes = taxaValor + frete + desconto + custoEntrega;
    const valorLiquido = Math.max(0, valorBruto - totalDeducoes);

    escreverLinhaEntradaExterna(sheetCaixa, mapa, {
      descricao: dados.descricao,
      categoria: dados.categoria || "Venda Externa",
      valorBruto, dias, totalDeducoes, valorLiquido,
      origem: dados.origem,
      dataVenda: parseDataInputExterna(dados.data)
    }, false);

    // Se a venda externa foi vinculada a um produto real do Estoque, dá baixa na quantidade.
    let avisoEstoque = "";
    if (dados.rowEstoque) {
      try {
        const cfg = obterConfiguracoes();
        const ssEstoque = SpreadsheetApp.openById(cfg.idEstoque);
        const sheetEstoque = ssEstoque.getSheetByName("ESTOQUE") || ssEstoque.getSheets()[0];
        if (sheetEstoque) {
          const qtdVendida = parseInt(dados.qtdEstoque, 10) || 1;
          const cellEstoque = sheetEstoque.getRange(parseInt(dados.rowEstoque, 10), 11); // Coluna K = Estoque
          const estoqueAtual = parseInt(cellEstoque.getValue(), 10) || 0;
          cellEstoque.setValue(Math.max(0, estoqueAtual - qtdVendida));
          avisoEstoque = " Baixa de " + qtdVendida + " unidade(s) no Estoque feita.";
        }
      } catch (eEstoque) {
        Logger.log("Erro ao dar baixa no estoque (venda externa): " + eEstoque.message);
        avisoEstoque = " ⚠️ Não deu pra dar baixa no Estoque (verifique o produto).";
      }
    }

    atualizarPainelCaixa();
    return {
      sucesso: true,
      mensagem: "✅ Venda externa registrada! Líquido: R$ " + valorLiquido.toFixed(2) +
        " (deduções: R$ " + totalDeducoes.toFixed(2) + ")." + avisoEstoque
    };
  } catch (e) {
    return { sucesso: false, mensagem: "❌ Erro: " + e.message };
  }
}

/**
 * Cria TODAS as parcelas futuras de um contrato de assinatura de uma vez só. A primeira
 * (mês atual) entra como uma venda normal; as demais entram marcadas "FUTURO", só sendo
 * contadas de verdade quando a data delas chegar (via Histórico/DRE, que já filtram por data).
 */
function salvarContratoAssinatura(dados) {
  try {
    const sheetCaixa = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("CAIXA") || SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    const mapa = getMapeamentoColunas(sheetCaixa);

    const valorMensal = parseFloat(dados.valorMensal) || 0;
    const qtdParcelas = parseInt(dados.qtdParcelas, 10) || 1;
    const dataInicio = parseDataInputExterna(dados.dataInicio);
    const taxaPct = parseFloat(dados.taxaPct) || 0;
    const diasBase = parseInt(dados.dias, 10) || 0;
    const diasAtraso = parseInt(dados.diasAtraso, 10) || 0;
    const diasParaLiquidar = diasBase + diasAtraso; // prazo real = prazo da forma de cobrança + tolerância de atraso esperada

    const taxaValor = valorMensal * (taxaPct / 100);
    const valorLiquidoParcela = Math.max(0, valorMensal - taxaValor);
    const descricaoComForma = dados.descricao + (dados.formaCobranca ? " [" + dados.formaCobranca + "]" : "");

    for (let k = 0; k < qtdParcelas; k++) {
      const dataParcela = new Date(dataInicio.getTime());
      dataParcela.setMonth(dataParcela.getMonth() + k);

      escreverLinhaEntradaExterna(sheetCaixa, mapa, {
        descricao: descricaoComForma + " (" + (k + 1) + "/" + qtdParcelas + ")",
        categoria: "Assinatura",
        valorBruto: valorMensal,
        dias: diasParaLiquidar,
        totalDeducoes: taxaValor,
        valorLiquido: valorLiquidoParcela,
        origem: dados.cliente,
        dataVenda: dataParcela
      }, k >= 1); // só a primeira parcela é "de hoje" — as demais são FUTURO
    }

    atualizarPainelCaixa();
    return { sucesso: true, mensagem: "✅ Contrato criado! " + qtdParcelas + " parcela(s) de R$ " + valorMensal.toFixed(2) + " (líquido R$ " + valorLiquidoParcela.toFixed(2) + " cada, prazo " + diasParaLiquidar + " dias). As futuras estão marcadas e fora do total de hoje." };
  } catch (e) {
    return { sucesso: false, mensagem: "❌ Erro: " + e.message };
  }
}

function getHtmlVendaExterna() {
  return `<!DOCTYPE html>
<html>
<head>
  <base target="_top">
  <style>
    * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, sans-serif; }
    body { margin: 0; padding: 16px; font-size: 12px; color: #333; background: #f8f9fa; }
    label { font-weight: bold; font-size: 11px; color: #475569; display: block; margin-bottom: 3px; margin-top: 8px; }
    input, select { width: 100%; padding: 8px; border-radius: 6px; border: 1px solid #cbd5e1; font-size: 12px; }
    .row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .info-line { display: flex; justify-content: space-between; font-size: 12px; padding: 3px 0; }
    .box { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; margin-top: 12px; }
    .btn { width: 100%; padding: 10px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; background: #0f172a; color: white; margin-top: 14px; }
    #status { text-align: center; font-weight: bold; margin-top: 10px; min-height: 18px; }
    .abas { display: flex; gap: 6px; margin-bottom: 12px; }
    .aba-btn { flex: 1; padding: 8px; border: 1px solid #cbd5e1; border-radius: 6px; background: #fff; cursor: pointer; font-size: 11px; font-weight: bold; color: #475569; text-align: center; }
    .aba-btn.ativa { background: #0f172a; color: #fff; border-color: #0f172a; }
    .aviso { font-size: 10px; color: #888; margin-top: 4px; }
  </style>
</head>
<body>
  <div class="abas">
    <div class="aba-btn ativa" id="aba-venda" onclick="mostrarAba('venda')">🛒 Venda Única</div>
    <div class="aba-btn" id="aba-contrato" onclick="mostrarAba('contrato')">📆 Contrato / Assinatura</div>
  </div>

  <div id="painel-venda">
    <label style="display:flex;align-items:center;gap:6px;font-size:11px;cursor:pointer;margin-top:0;">
      <input type="checkbox" id="in-vincular" style="width:auto;" onchange="alternarVinculo()"> 🔗 Dar baixa no Estoque (vincular a um produto real)
    </label>

    <div id="box-busca-produto" style="display:none;margin-top:8px;">
      <label>Buscar Produto (código, ID ou descrição):</label>
      <input type="text" id="in-busca-produto" oninput="buscarProdutoVE()">
      <div id="lista-produtos-ve" style="max-height:140px;overflow-y:auto;border:1px solid #e2e8f0;border-radius:6px;background:#fff;margin-top:4px;"></div>
      <div id="produto-selecionado-ve" style="display:none;background:#ecfdf5;border:1px solid #a7f3d0;border-radius:6px;padding:8px;margin-top:6px;font-size:11px;"></div>
      <label>Quantidade Vendida:</label>
      <input type="number" id="in-qtd-produto" value="1" min="1" oninput="atualizarQtdProdutoVE()">
    </div>

    <label>Descrição:</label>
    <input type="text" id="in-desc">

    <label>Categoria:</label>
    <select id="in-categoria">
      <option value="Venda Externa">Venda em Plataforma</option>
      <option value="Delivery">Delivery / Entrega</option>
      <option value="Outras Entradas">Outras Entradas</option>
    </select>

    <label>Origem / Plataforma (opcional):</label>
    <input type="text" id="in-origem">

    <label>Data da Venda:</label>
    <input type="date" id="in-data">

    <label>Valor Bruto (R$):</label>
    <input type="number" step="0.01" id="in-valor" oninput="recalcular()">

    <div class="row2">
      <div><label>Taxa da Plataforma (%)</label><input type="number" step="0.01" id="in-taxa" value="0" oninput="recalcular()"></div>
      <div><label>Frete (R$)</label><input type="number" step="0.01" id="in-frete" value="0" oninput="recalcular()"></div>
    </div>
    <div class="row2">
      <div><label>Desconto (R$)</label><input type="number" step="0.01" id="in-desconto" value="0" oninput="recalcular()"></div>
      <div><label>Motoboy / Entrega (R$)</label><input type="number" step="0.01" id="in-entrega" value="0" oninput="recalcular()"></div>
    </div>

    <label>Dias até o dinheiro cair:</label>
    <input type="number" id="in-dias" value="0" oninput="recalcular()">

    <div class="box">
      <div class="info-line"><span>Total de Deduções:</span><strong id="v-deducoes" style="color:#dc3545;">R$ 0,00</strong></div>
      <div class="info-line"><span>Valor Líquido a Receber:</span><strong id="v-liquido" style="color:#16a34a;">R$ 0,00</strong></div>
    </div>

    <button class="btn" onclick="salvarVenda()">💾 Registrar Venda Externa</button>
  </div>

  <div id="painel-contrato" style="display:none;">
    <div style="font-size:11px;color:#666;margin-bottom:6px;">Serve pra qualquer receita recorrente: assinatura de cliente, aluguel de imóvel, mensalidade — cria todas as parcelas de uma vez, cada uma na data certa.</div>

    <label>Descrição do Contrato:</label>
    <input type="text" id="ct-desc">

    <label>Cliente / Contratante:</label>
    <input type="text" id="ct-cliente">

    <label>Data de Início:</label>
    <input type="date" id="ct-inicio">

    <div class="row2">
      <div><label>Valor Mensal (R$)</label><input type="number" step="0.01" id="ct-valor" oninput="recalcularContrato()"></div>
      <div><label>Duração (meses)</label><input type="number" id="ct-parcelas" value="12" oninput="recalcularContrato()"></div>
    </div>

    <label>Forma de Cobrança:</label>
    <select id="ct-forma" onchange="aplicarSugestaoForma()">
      <option value="Cartão">Cartão de Crédito Recorrente</option>
      <option value="Boleto">Boleto</option>
      <option value="PIX">PIX</option>
      <option value="Dinheiro">Dinheiro / Transferência</option>
      <option value="Outros">Outros</option>
    </select>

    <div class="row2">
      <div><label>Taxa da Forma de Cobrança (%)</label><input type="number" step="0.01" id="ct-taxa" value="0" oninput="recalcularContrato()"></div>
      <div><label>Dias até cair (base)</label><input type="number" id="ct-dias" value="0" oninput="recalcularContrato()"></div>
    </div>

    <label>Tolerância de Atraso Esperado (dias):</label>
    <input type="number" id="ct-atraso" value="0" oninput="recalcularContrato()">
    <div class="aviso">Se o cliente costuma atrasar uns dias, soma aqui — o prazo final usado é "Dias até cair" + essa tolerância.</div>

    <div class="box">
      <div class="info-line"><span>Total do Contrato:</span><strong id="ct-total">R$ 0,00</strong></div>
      <div class="info-line"><span>Última Parcela:</span><strong id="ct-fim">—</strong></div>
    </div>
    <div class="aviso">Só a 1ª parcela conta no caixa de hoje — as demais ficam marcadas "FUTURO" e só entram quando a data chegar.</div>

    <button class="btn" onclick="salvarContrato()">📆 Criar Contrato (todas as parcelas)</button>
  </div>

  <div id="status"></div>

  <script>
    window.onload = function() {
      const hoje = new Date().toISOString().split('T')[0];
      document.getElementById('in-data').value = hoje;
      document.getElementById('ct-inicio').value = hoje;
      aplicarSugestaoForma();
    };

    function mostrarAba(qual) {
      document.getElementById('painel-venda').style.display = qual === 'venda' ? 'block' : 'none';
      document.getElementById('painel-contrato').style.display = qual === 'contrato' ? 'block' : 'none';
      document.getElementById('aba-venda').className = 'aba-btn' + (qual === 'venda' ? ' ativa' : '');
      document.getElementById('aba-contrato').className = 'aba-btn' + (qual === 'contrato' ? ' ativa' : '');
      document.getElementById('status').innerText = '';
    }

    function recalcular() {
      const valor = parseFloat(document.getElementById('in-valor').value) || 0;
      const taxaPct = parseFloat(document.getElementById('in-taxa').value) || 0;
      const frete = parseFloat(document.getElementById('in-frete').value) || 0;
      const desconto = parseFloat(document.getElementById('in-desconto').value) || 0;
      const entrega = parseFloat(document.getElementById('in-entrega').value) || 0;

      const taxaValor = valor * (taxaPct / 100);
      const totalDeducoes = taxaValor + frete + desconto + entrega;

      document.getElementById('v-deducoes').innerText = 'R$ ' + totalDeducoes.toFixed(2).replace('.', ',');
      document.getElementById('v-liquido').innerText = 'R$ ' + Math.max(0, valor - totalDeducoes).toFixed(2).replace('.', ',');
    }

    var produtosEstoqueCacheVE = [];
    var produtoVinculadoVE = null;

    function alternarVinculo() {
      const ligado = document.getElementById('in-vincular').checked;
      document.getElementById('box-busca-produto').style.display = ligado ? 'block' : 'none';
      if (!ligado) {
        produtoVinculadoVE = null;
        document.getElementById('produto-selecionado-ve').style.display = 'none';
        return;
      }
      if (produtosEstoqueCacheVE.length === 0) {
        document.getElementById('lista-produtos-ve').innerHTML = '<div style="padding:6px;color:#888;font-size:11px;">⏳ Carregando produtos...</div>';
        google.script.run.withSuccessHandler(function(prods) {
          produtosEstoqueCacheVE = prods || [];
          document.getElementById('lista-produtos-ve').innerHTML = '';
        }).obterTodosProdutosEstoquePDV();
      }
    }

    function buscarProdutoVE() {
      const termo = document.getElementById('in-busca-produto').value.trim().toUpperCase();
      const div = document.getElementById('lista-produtos-ve');
      if (termo.length < 2) { div.innerHTML = ''; return; }

      const filtrados = produtosEstoqueCacheVE.filter(function(p) {
        return (p.ean + ' ' + p.id + ' ' + p.desc).toUpperCase().includes(termo);
      }).slice(0, 20);

      div.innerHTML = '';
      if (filtrados.length === 0) {
        div.innerHTML = '<div style="padding:6px;color:#888;font-size:11px;">Nenhum produto encontrado.</div>';
        return;
      }
      filtrados.forEach(function(p) {
        const item = document.createElement('div');
        item.style.cssText = 'padding:6px 8px;border-bottom:1px solid #f1f5f9;cursor:pointer;font-size:11px;';
        item.innerHTML = '<strong>' + p.desc + '</strong> <span style="color:#888;">— R$ ' + p.pVenda.toFixed(2).replace('.', ',') + ' (est: ' + p.est + ')</span>';
        item.onclick = function() { selecionarProdutoVE(p); };
        div.appendChild(item);
      });
    }

    function atualizarQtdProdutoVE() {
      if (produtoVinculadoVE) {
        const qtd = parseInt(document.getElementById('in-qtd-produto').value, 10) || 1;
        document.getElementById('in-valor').value = (produtoVinculadoVE.pVenda * qtd).toFixed(2);
      }
      recalcular();
    }

    function selecionarProdutoVE(p) {
      produtoVinculadoVE = p;
      document.getElementById('in-busca-produto').value = '';
      document.getElementById('lista-produtos-ve').innerHTML = '';
      document.getElementById('produto-selecionado-ve').style.display = 'block';
      document.getElementById('produto-selecionado-ve').innerHTML = '✅ <strong>' + p.desc + '</strong><br>Preço no Estoque: R$ ' + p.pVenda.toFixed(2).replace('.', ',') + ' (estoque atual: ' + p.est + ')';

      document.getElementById('in-desc').value = p.desc;
      const qtd = parseInt(document.getElementById('in-qtd-produto').value, 10) || 1;
      document.getElementById('in-valor').value = (p.pVenda * qtd).toFixed(2);
      recalcular();
    }

    function salvarVenda() {
      const desc = document.getElementById('in-desc').value.trim();
      const valor = document.getElementById('in-valor').value;
      const st = document.getElementById('status');

      if (!desc || !valor || parseFloat(valor) <= 0) {
        st.style.color = '#dc3545';
        st.innerText = '⚠️ Preencha ao menos a descrição e o valor.';
        return;
      }

      st.style.color = '#007bff';
      st.innerText = '⏳ Salvando...';

      google.script.run
        .withSuccessHandler(function(res) {
          st.style.color = res.sucesso ? '#107c41' : '#dc3545';
          st.innerText = res.mensagem;
          if (res.sucesso) setTimeout(function() { google.script.host.close(); }, 2000);
        })
        .withFailureHandler(function(err) {
          st.style.color = '#dc3545';
          st.innerText = '❌ Erro: ' + (err.message || err);
        })
        .salvarVendaExterna({
          descricao: desc,
          categoria: document.getElementById('in-categoria').value,
          origem: document.getElementById('in-origem').value.trim(),
          data: document.getElementById('in-data').value,
          valor: valor,
          taxaPct: document.getElementById('in-taxa').value,
          frete: document.getElementById('in-frete').value,
          desconto: document.getElementById('in-desconto').value,
          custoEntrega: document.getElementById('in-entrega').value,
          dias: document.getElementById('in-dias').value,
          rowEstoque: produtoVinculadoVE ? produtoVinculadoVE.row : null,
          qtdEstoque: produtoVinculadoVE ? (parseInt(document.getElementById('in-qtd-produto').value, 10) || 1) : null
        });
    }

    function aplicarSugestaoForma() {
      const forma = document.getElementById('ct-forma').value;
      const sugestoes = {
        "Cartão": { taxa: 4.5, dias: 30 },
        "Boleto": { taxa: 2, dias: 2 },
        "PIX": { taxa: 0, dias: 0 },
        "Dinheiro": { taxa: 0, dias: 0 },
        "Outros": { taxa: 0, dias: 0 }
      };
      const s = sugestoes[forma] || { taxa: 0, dias: 0 };
      document.getElementById('ct-taxa').value = s.taxa;
      document.getElementById('ct-dias').value = s.dias;
      recalcularContrato();
    }

    function recalcularContrato() {
      const valor = parseFloat(document.getElementById('ct-valor').value) || 0;
      const parcelas = parseInt(document.getElementById('ct-parcelas').value, 10) || 0;
      const taxaPct = parseFloat(document.getElementById('ct-taxa').value) || 0;
      const taxaValor = valor * (taxaPct / 100);
      const liquidoPorParcela = Math.max(0, valor - taxaValor);

      document.getElementById('ct-total').innerText = 'R$ ' + (valor * parcelas).toFixed(2).replace('.', ',') +
        ' (líquido/parcela: R$ ' + liquidoPorParcela.toFixed(2).replace('.', ',') + ')';

      const inicioStr = document.getElementById('ct-inicio').value;
      if (inicioStr && parcelas > 0) {
        const partes = inicioStr.split('-').map(Number);
        const fim = new Date(partes[0], partes[1] - 1, partes[2]);
        fim.setMonth(fim.getMonth() + parcelas - 1);
        document.getElementById('ct-fim').innerText = String(fim.getDate()).padStart(2, '0') + '/' + String(fim.getMonth() + 1).padStart(2, '0') + '/' + fim.getFullYear();
      }
    }

    function salvarContrato() {
      const desc = document.getElementById('ct-desc').value.trim();
      const valor = document.getElementById('ct-valor').value;
      const parcelas = document.getElementById('ct-parcelas').value;
      const st = document.getElementById('status');

      if (!desc || !valor || parseFloat(valor) <= 0 || !parcelas || parseInt(parcelas, 10) <= 0) {
        st.style.color = '#dc3545';
        st.innerText = '⚠️ Preencha descrição, valor mensal e duração.';
        return;
      }

      st.style.color = '#007bff';
      st.innerText = '⏳ Criando parcelas...';

      google.script.run
        .withSuccessHandler(function(res) {
          st.style.color = res.sucesso ? '#107c41' : '#dc3545';
          st.innerText = res.mensagem;
          if (res.sucesso) setTimeout(function() { google.script.host.close(); }, 2500);
        })
        .withFailureHandler(function(err) {
          st.style.color = '#dc3545';
          st.innerText = '❌ Erro: ' + (err.message || err);
        })
        .salvarContratoAssinatura({
          descricao: desc,
          cliente: document.getElementById('ct-cliente').value.trim(),
          dataInicio: document.getElementById('ct-inicio').value,
          valorMensal: valor,
          qtdParcelas: parcelas,
          formaCobranca: document.getElementById('ct-forma').value,
          taxaPct: document.getElementById('ct-taxa').value,
          dias: document.getElementById('ct-dias').value,
          diasAtraso: document.getElementById('ct-atraso').value
        });
    }
  </script>
</body>
</html>`;
}


/**
 * ============================================================================
 * PROTEÇÃO DA PLANILHA — trava a área de dados (linha 5 pra baixo) contra edição
 * manual pelo cursor. Só os botões (que rodam script) conseguem alterar essa área
 * depois disso — editar direto na célula não funciona mais.
 *
 * Fica ativa PRA SEMPRE por padrão: o onOpen (lá no topo do arquivo) já garante isso
 * toda vez que a planilha é aberta, sem precisar clicar em nada. O botão "Desproteger"
 * só existe pra quando você mesmo precisar corrigir algo direto na célula.
 * ============================================================================
 */
const DESCRICAO_PROTECAO_CAIXA = "Área de dados — só os botões mexem aqui";

function protegerLinhasCaixaSilencioso() {
  try {
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("CAIXA") || SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    if (!sheet) return;

    // Já protegida? Não faz nada — evita ficar empilhando proteção toda vez que abre.
    const jaProtegido = sheet.getProtections(SpreadsheetApp.ProtectionType.RANGE)
      .some(p => p.getDescription() === DESCRICAO_PROTECAO_CAIXA);
    if (jaProtegido) return;

    const maxRow = Math.max(sheet.getMaxRows(), 2000);
    const maxCol = Math.max(sheet.getMaxColumns(), 26);
    const range = sheet.getRange(5, 1, maxRow - 4, maxCol);

    const protection = range.protect().setDescription(DESCRICAO_PROTECAO_CAIXA);
    protection.removeEditors(protection.getEditors());
    if (protection.canDomainEdit()) protection.setDomainEdit(false);
  } catch (e) {
    Logger.log("Erro ao proteger automaticamente: " + e.message);
  }
}

function protegerLinhasCaixa() {
  // Remove qualquer proteção antiga nessa aba antes, pra não empilhar proteções repetidas.
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("CAIXA") || SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  sheet.getProtections(SpreadsheetApp.ProtectionType.RANGE).forEach(p => {
    if (p.getDescription() === DESCRICAO_PROTECAO_CAIXA) p.remove();
  });

  protegerLinhasCaixaSilencioso();

  SpreadsheetApp.getUi().alert(
    "🔒 Planilha protegida!",
    "A partir da linha 5, ninguém consegue mais editar direto na célula — só os botões (que rodam por script) conseguem alterar os dados.\n\n" +
    "Ela agora fica protegida PRA SEMPRE sozinha (o onOpen garante isso toda vez que a planilha abrir). Se precisar mexer manualmente algum dia, use o botão '🔓 Desproteger Planilha' — mas lembre que, ao reabrir a planilha, ela volta a travar automaticamente.",
    SpreadsheetApp.getUi().ButtonSet.OK
  );
}

function desprotegerLinhasCaixa() {
  const ui = SpreadsheetApp.getUi();
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("CAIXA") || SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

  let removeu = false;
  sheet.getProtections(SpreadsheetApp.ProtectionType.RANGE).forEach(p => {
    if (p.getDescription() === DESCRICAO_PROTECAO_CAIXA) { p.remove(); removeu = true; }
  });

  ui.alert(removeu
    ? "🔓 Planilha destravada! Você já pode editar direto na célula.\n\n⚠️ Atenção: se fechar e abrir a planilha de novo, ela volta a travar sozinha — termine sua correção antes de recarregar a página."
    : "Não havia proteção ativa pra remover."
  );
}


/**
 * ============================================================================
 * BACKUP E RESTAURAÇÃO AUTOMÁTICA — como o Google Sheets nunca bloqueia o DONO
 * da planilha via proteção nativa (só bloqueia outras pessoas), a defesa de verdade
 * pra "nem eu consigo editar sem querer" é essa: guardamos uma cópia fiel da área de
 * dados toda vez que um botão roda de verdade, e qualquer edição manual detectada
 * (digitar, colar, apertar Delete) é desfeita na hora, restaurando dessa cópia.
 * ============================================================================
 */
const NOME_ABA_BACKUP_CAIXA = "_BACKUP_CAIXA";

function atualizarBackupCaixa() {
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheetCaixa = ss.getSheetByName("CAIXA");
    if (!sheetCaixa) return;

    let backup = ss.getSheetByName(NOME_ABA_BACKUP_CAIXA);
    if (!backup) {
      backup = ss.insertSheet(NOME_ABA_BACKUP_CAIXA);
      backup.hideSheet();
    }

    const lastRow = Math.max(sheetCaixa.getLastRow(), 6);
    const lastCol = Math.max(sheetCaixa.getLastColumn(), 15);

    backup.clearContents();
    const dados = sheetCaixa.getRange(1, 1, lastRow, lastCol).getValues();
    backup.getRange(1, 1, dados.length, dados[0].length).setValues(dados);
  } catch (e) {
    Logger.log("Erro ao atualizar backup do Caixa: " + e.message);
  }
}

/**
 * Restaura EXATAMENTE a área que foi editada manualmente, usando o backup mais recente.
 * Se a edição foi numa área que o backup nem tinha ainda (linha/coluna nova), simplesmente limpa.
 */
function restaurarDoBackupCaixa(range) {
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const backup = ss.getSheetByName(NOME_ABA_BACKUP_CAIXA);
    const sheetCaixa = ss.getSheetByName("CAIXA");
    if (!backup || !sheetCaixa) return;

    const linha = range.getRow(), col = range.getColumn();
    const numRows = range.getNumRows(), numCols = range.getNumColumns();
    const backupLastRow = backup.getLastRow(), backupLastCol = backup.getLastColumn();

    if (linha > backupLastRow || col > backupLastCol) {
      sheetCaixa.getRange(linha, col, numRows, numCols).clearContent();
      return;
    }

    const numRowsSeguro = Math.min(numRows, backupLastRow - linha + 1);
    const numColsSeguro = Math.min(numCols, backupLastCol - col + 1);
    const valoresOriginais = backup.getRange(linha, col, numRowsSeguro, numColsSeguro).getValues();
    sheetCaixa.getRange(linha, col, numRowsSeguro, numColsSeguro).setValues(valoresOriginais);

    if (numRows > numRowsSeguro) sheetCaixa.getRange(linha + numRowsSeguro, col, numRows - numRowsSeguro, numCols).clearContent();
    if (numCols > numColsSeguro) sheetCaixa.getRange(linha, col + numColsSeguro, numRowsSeguro, numCols - numColsSeguro).clearContent();
  } catch (e) {
    Logger.log("Erro ao restaurar backup do Caixa: " + e.message);
  }
}