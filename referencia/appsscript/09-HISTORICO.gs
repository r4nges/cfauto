/**
 * Obtém as configurações da aba 'Configurações' da planilha atual.
 */
function obterConfiguracoes() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const cfgSheet = ss.getSheetByName("Configurações");
  
  // Configurações padrão
  const config = {
    idPlanilhaExterna: "COLE_O_ID_DA_SUA_OUTRA_PLANILHA_AQUI", // ID da planilha externa de Histórico/Estoque
    nomeAbaHistoricoCaixa: "HIST"                             // Nome da aba do histórico na outra planilha
  };

  if (!cfgSheet) return config;

  const data = cfgSheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    const chave = String(data[i][0]).trim().toUpperCase();
    const valor = String(data[i][1]).trim();
    if (!valor) continue;

    if (chave === "ID_PLANILHA_ESTOQUE" || chave === "ID_PLANILHA_HISTORICO" || chave === "ID_EXTERNO") {
      config.idPlanilhaExterna = valor;
    } else if (chave === "NOME_ABA_HISTORICO" || chave === "NOME_ABA_CAIXA") {
      config.nomeAbaHistoricoCaixa = valor;
    }
  }

  return config;
}

/**
 * Fecha o caixa atual e envia todo o histórico de vendas diretamente
 * para a aba de histórico na OUTRA planilha (planilha externa).
 */
function fecharCaixaEArquivar() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheetVendas = ss.getSheetByName("VENDAS_HOJE") || ss.getSheetByName("CAIXA") || ss.getActiveSheet();
  const config = obterConfiguracoes();

  // 1. Valida o ID da planilha externa
  if (!config.idPlanilhaExterna || config.idPlanilhaExterna === "COLE_O_ID_DA_SUA_OUTRA_PLANILHA_AQUI") {
    SpreadsheetApp.getUi().alert("Por favor, informe o ID da outra planilha na função obterConfiguracoes() ou na aba 'Configurações'.");
    return;
  }

  // 2. Abre a Planilha Externa (onde fica o histórico)
  let extSS;
  try {
    extSS = SpreadsheetApp.openById(config.idPlanilhaExterna);
  } catch (e) {
    SpreadsheetApp.getUi().alert("Erro ao abrir a outra planilha. Verifique se o ID está correto e se você tem permissão de acesso.\nDetalhes: " + e.message);
    return;
  }

  // 3. Procura a aba de histórico na planilha externa (procura 'HIST', 'HISTORICO', 'HISTÓRICO' ou 'CAIXA')
  let sheetHist = extSS.getSheetByName(config.nomeAbaHistoricoCaixa) || 
                  extSS.getSheetByName("HIST") || 
                  extSS.getSheetByName("HISTORICO") || 
                  extSS.getSheetByName("HISTÓRICO") ||
                  extSS.getSheetByName("CAIXA");

  // Se a aba ainda não existir na planilha externa, ela é criada automaticamente com os cabeçalhos
  if (!sheetHist) {
    sheetHist = extSS.insertSheet(config.nomeAbaHistoricoCaixa || "HIST");
    const cabecalhos = [
      "Horário", "ID Sessão", "Código de Barras", "ID Produto", "Descrição", 
      "Categoria", "Preço Bruto", "Quantidade", "Pagamento", "Liquidado Em", 
      "Taxa", "Recebido Líquido", "Cliente"
    ];
    sheetHist.appendRow(cabecalhos);
    sheetHist.getRange(1, 1, 1, cabecalhos.length).setFontWeight("bold").setBackground("#d9ea34");
  }

  // 4. Lê as vendas da aba atual de caixa
  const lastRow = sheetVendas.getLastRow();
  if (lastRow < 2) {
    SpreadsheetApp.getUi().alert("Não há vendas registradas para fechar o caixa.");
    return;
  }

  const rangeVendas = sheetVendas.getRange(2, 1, lastRow - 1, 13);
  const dadosVendas = rangeVendas.getValues();

  // Filtra apenas as linhas com dados reais
  const vendasParaArquivar = dadosVendas.filter(row => row[0] !== "" || row[2] !== "" || row[4] !== "");

  if (vendasParaArquivar.length === 0) {
    SpreadsheetApp.getUi().alert("Nenhuma venda válida encontrada na aba atual.");
    return;
  }

  // 5. Salva os registros na planilha EXTERNA
  sheetHist.getRange(sheetHist.getLastRow() + 1, 1, vendasParaArquivar.length, 13).setValues(vendasParaArquivar);

  // 6. Limpa os registros da aba de caixa atual (mantendo o cabeçalho)
  rangeVendas.clearContent();

  SpreadsheetApp.getUi().alert(
    `Caixa fechado com sucesso!\n\n` +
    ` Foram salvos ${vendasParaArquivar.length} registros na aba '${sheetHist.getName()}' da planilha externa.`
  );
}
// ============================================================
// NAVEGAÇÃO POR ABAS NO TOPO
// ============================================================

function irParaInicio() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const aba = ss.getSheetByName("INÍCIO") || ss.getSheetByName("PAINEL");
  if (aba) aba.activate();
}

function irParaCaixa() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const aba = ss.getSheetByName("CAIXA") || ss.getSheetByName("VENDAS");
  if (aba) aba.activate();
}

function irParaClientes() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const aba = ss.getSheetByName("CLIENTES");
  if (aba) aba.activate();
}

function irParaHistorico() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const aba = ss.getSheetByName("HIST") || ss.getSheetByName("HISTORICO");
  if (aba) aba.activate();
}
