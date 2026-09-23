/**
 * ============================================================================
 * CFAUTO / ADM — ABA "MARKUP" (painel principal de precificação)
 * Cole este script na planilha NOVA do CFAUTO (Extensões > Apps Script).
 * ============================================================================
 *
 * Como funciona:
 * - Esta aba PUXA os produtos do Estoque (código, descrição, categoria, custo FRACIONADO — coluna H).
 * - Calcula aqui: rateio de gastos fixos EM PERCENTUAL sobre o custo de cada produto, custo real e preço final.
 * - Só o PREÇO FINAL é devolvido pro Estoque (coluna I) — o Estoque não calcula mais nada.
 * - Editar o Markup % aqui atualiza o preço na hora e já empurra pro Estoque sozinho.
 *
 * Por que percentual e não valor fixo por unidade: um rateio fixo em R$ (ex: R$465 por unidade
 * vendida) distorce tudo quando os produtos têm preços muito diferentes — um item de R$5,50 ficaria
 * com o MESMO rateio de um item de R$130,00, o que não faz sentido. Em percentual, cada produto
 * carrega uma fatia proporcional ao seu próprio custo.
 *
 * Layout da aba "Markup" (espelha as mesmas linhas do Estoque, pra facilitar):
 * Linha 5 = cabeçalho | Linha 6 em diante = produtos
 * A=Código | B=ID | C=Descrição | D=Categoria | E=Custo Compra Fracionado | F=Rateio (R$) |
 * G=Custo Real | H=Markup % (editável) | I=Preço Final
 * Painel de config: K1:L3 (Gastos do Mês, Receita Bruta do Mês, Rateio % sobre o custo)
 */

// ⚠️ IDs das planilhas do sistema.
const ID_PLANILHA_ESTOQUE_MKP = "1aPr4-chXwNE19RWIXgOPceB-OmF31Ft5SgtugEPwoMA";
const ID_PLANILHA_CAIXA_MKP = "1nBVAh4brJ6KiIgrokph58btEkdkydSlRwDbVBbPzCzA";
const ID_PLANILHA_HISTORICO_MKP = "1119HW8n6Ma-H83wbLw9I13bTJ9EgJhhpciPFyyaUXI8";
const ID_PLANILHA_SAIDAS_MKP = "16PD_PSyOKStz2QCVuB66PbFlHdIl6EsbZtP34oB0BJY";
const NOME_ABA_MARKUP = "Markup";

/**
 * Roda UMA VEZ pra criar a aba "Markup" (se não existir) com o painel e os cabeçalhos.
 */
function configurarAbaMarkup() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(NOME_ABA_MARKUP) || ss.insertSheet(NOME_ABA_MARKUP);

  sheet.getRange("K1").setValue("Gastos do Mês (Saídas):").setFontWeight("bold");
  sheet.getRange("L1").setNumberFormat("R$ #,##0.00");
  sheet.getRange("K2").setValue("Receita Bruta do Mês:").setFontWeight("bold");
  sheet.getRange("L2").setNumberFormat("R$ #,##0.00");
  sheet.getRange("K3").setValue("Rateio Fixo (% sobre o custo):").setFontWeight("bold");
  sheet.getRange("L3").setNumberFormat("0.00%");
  sheet.getRange("K1:K3").setBackground("#f1f5f9");

  sheet.getRange("A5:K5").setValues([[
    "CÓDIGO", "ID", "DESCRIÇÃO", "CATEGORIA", "CUSTO COMPRA (FRACIONADO)", "RATEIO (R$)", "CUSTO REAL", "MARKUP %", "PREÇO FINAL", "PREÇO PROMOCIONAL", "DATA ENTRADA"
  ]]).setFontWeight("bold");

  SpreadsheetApp.getUi().alert("✅ Aba Markup criada! Agora clique em '🔄 Atualizar Tudo' pra puxar os produtos do Estoque.");
}

/**
 * Soma os GASTOS DO MÊS na Saídas (Conta Fixa + Conta Variável + Salário), pela Data de Registro.
 */
function obterGastosDoMesSaidas() {
  const hoje = new Date();
  const mesAtual = hoje.getMonth(), anoAtual = hoje.getFullYear();
  let totalGastos = 0;
  const categoriasValidas = ["FIXA", "VARIAVEL", "SALARIO", "SALARIOS"];

  try {
    const ssSaidas = SpreadsheetApp.openById(ID_PLANILHA_SAIDAS_MKP);
    const sheetSaidas = ssSaidas.getSheets()[0];
    const lastRow = sheetSaidas.getLastRow();
    if (lastRow >= 7) {
      const dados = sheetSaidas.getRange(7, 1, lastRow - 6, 9).getValues();
      dados.forEach(row => {
        const dataRegistro = row[1]; // B
        const categoria = String(row[2] || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase().trim(); // C
        const valor = parseFloat(String(row[4]).replace(/[^\d,.-]/g, '').replace(',', '.')) || 0; // E

        if (!categoriasValidas.some(c => categoria.includes(c))) return;

        let dtReg = null;
        if (dataRegistro instanceof Date) dtReg = dataRegistro;
        else if (typeof dataRegistro === 'string' && dataRegistro.includes('/')) {
          const partes = dataRegistro.split('/');
          if (partes.length === 3) dtReg = new Date(partes[2], partes[1] - 1, partes[0]);
        }
        if (!dtReg || dtReg.getMonth() !== mesAtual || dtReg.getFullYear() !== anoAtual) return;

        totalGastos += valor;
      });
    }
  } catch (e) {
    Logger.log("Erro ao ler Saídas: " + e.message);
  }

  return totalGastos;
}

/**
 * Soma a RECEITA BRUTA DO MÊS (Histórico + Caixa aberto), base pro rateio em % (não mais valor fixo).
 */
function obterReceitaDoMes() {
  const hoje = new Date();
  const mesAtual = hoje.getMonth(), anoAtual = hoje.getFullYear();
  let totalReceita = 0;

  try {
    const ssHist = SpreadsheetApp.openById(ID_PLANILHA_HISTORICO_MKP);
    const sheetHist = ssHist.getSheets()[0];
    const lastRow = sheetHist.getLastRow();
    if (lastRow >= 2) {
      const dados = sheetHist.getRange(2, 1, lastRow - 1, 13).getValues();
      dados.forEach(row => {
        const dataHora = row[0];
        let dtObj = null;
        if (dataHora instanceof Date) dtObj = dataHora;
        else if (typeof dataHora === 'string' && dataHora.includes('/')) {
          const partes = dataHora.split(' ')[0].split('/');
          if (partes.length === 3) dtObj = new Date(partes[2], partes[1] - 1, partes[0]);
        }
        if (!dtObj || dtObj.getMonth() !== mesAtual || dtObj.getFullYear() !== anoAtual) return;
        if (String(row[5] || "") === "CREDIARIO") return;
        totalReceita += parseFloat(row[6]) || 0; // Coluna G = Valor
      });
    }
  } catch (e) {
    Logger.log("Erro ao ler histórico: " + e.message);
  }

  try {
    const ssCaixa = SpreadsheetApp.openById(ID_PLANILHA_CAIXA_MKP);
    const sheetCaixa = ssCaixa.getSheetByName("CAIXA") || ssCaixa.getSheets()[0];
    const lastRow = sheetCaixa.getLastRow();
    if (lastRow >= 7) {
      const dados = sheetCaixa.getRange(7, 1, lastRow - 6, sheetCaixa.getLastColumn()).getValues();
      dados.forEach(row => {
        const desc = String(row[2] || "").trim();
        if (desc === "" || desc.includes("RECEBIMENTO DE CONTA")) return;
        totalReceita += parseFloat(row[4]) || 0; // Coluna E = Preço
      });
    }
  } catch (e) {
    Logger.log("Erro ao ler caixa aberto: " + e.message);
  }

  return totalReceita;
}

/**
 * BOTÃO PRINCIPAL: puxa produtos do Estoque, recalcula rateio/custo/preço e
 * empurra o preço final de volta pro Estoque. Preserva os Markups já editados.
 */
function atualizarMarkupCompleto() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(NOME_ABA_MARKUP);
  if (!sheet) { SpreadsheetApp.getUi().alert("Rode '⚙️ Configurar Aba Markup' primeiro."); return; }

  const totalGastos = obterGastosDoMesSaidas();
  const totalReceita = obterReceitaDoMes();
  // ⚠️ CORRIGIDO: rateio agora é um PERCENTUAL sobre o custo de cada produto (não mais um valor fixo
  // por unidade). Um valor fixo distorcia tudo: um produto de R$5,50 levava o mesmo R$465 de rateio
  // que um de R$130, o que não faz sentido. Em percentual, cada produto carrega uma fatia proporcional
  // ao seu próprio custo — os gastos fixos representados como % da receita do mês.
  const rateioPercentual = totalReceita > 0 ? (totalGastos / totalReceita) : 0;
  sheet.getRange("L1").setValue(totalGastos);
  sheet.getRange("L2").setValue(totalReceita);
  sheet.getRange("L3").setValue(rateioPercentual);

  const ssEstoque = SpreadsheetApp.openById(ID_PLANILHA_ESTOQUE_MKP);
  const sheetEstoque = ssEstoque.getSheetByName("ESTOQUE") || ssEstoque.getSheets()[0];
  const lastRowEstoque = sheetEstoque.getLastRow();
  if (lastRowEstoque < 6) { SpreadsheetApp.getUi().alert("Nenhum produto encontrado no Estoque."); return; }

  // Layout atual do Estoque (após você inserir a coluna de Data de Entrada em G):
  // G=Data Entrada | H=Preço Entrada (pacote) | I=Preço Fracionado (custo real por unidade) |
  // J=Preço Venda | K=Estoque (qtd) | L=Margem | M=Destino
  const dadosEstoque = sheetEstoque.getRange(6, 1, lastRowEstoque - 5, 13).getValues(); // A até M

  // Preserva o Markup, o Preço Final manual e a Promoção já definidos antes de sobrescrever.
  const dadosAntigosMap = {};
  const lastRowAtual = sheet.getLastRow();
  if (lastRowAtual >= 6) {
    const dadosAntigos = sheet.getRange(6, 1, lastRowAtual - 5, 10).getValues();
    dadosAntigos.forEach((row, i) => {
      dadosAntigosMap[i + 6] = { markup: row[7], precoFinal: row[8], promocional: row[9] };
    });
  }

  const novaTabela = [];
  const precosParaEstoque = [];

  dadosEstoque.forEach((row, i) => {
    const linha = i + 6;
    const codigo = row[0], id = row[1], desc = row[2], categoria = row[3], custoCompra = parseFloat(row[8]) || 0; // I = índice 8 (fracionado, pós-inserção da coluna G)
    const dataEntrada = row[6] || ""; // G = índice 6 (Data de Entrada, agora antes do Preço de Entrada)

    if (!codigo && !desc) {
      novaTabela.push(["", "", "", "", "", "", "", "", "", "", ""]);
      precosParaEstoque.push([""]);
      return;
    }

    const antigo = dadosAntigosMap[linha] || {};
    const markup = (antigo.markup !== undefined && antigo.markup !== "") ? antigo.markup : 30;
    const rateio = custoCompra * rateioPercentual; // rateio proporcional ao custo deste produto (só informativo)
    const custoReal = custoCompra + rateio;

    // Se você já definiu um Preço Final manual pra esse produto (pela janela "Atualizar Preço"),
    // ele é respeitado aqui — a atualização não pisa em cima de um preço que você decidiu na mão.
    const precoFinal = (antigo.precoFinal !== undefined && antigo.precoFinal !== "")
      ? antigo.precoFinal
      : custoReal * (1 + markup / 100);
    const promocional = antigo.promocional || "";

    novaTabela.push([codigo, id, desc, categoria, custoCompra, rateio, custoReal, markup, precoFinal, promocional, dataEntrada]);
    // Se tiver preço promocional ativo, é ele que vai pro Estoque — senão, o preço final normal.
    precosParaEstoque.push([promocional !== "" ? promocional : precoFinal]);
  });

  sheet.getRange(6, 1, novaTabela.length, 11).setValues(novaTabela);
  sheet.getRange(6, 5, novaTabela.length, 3).setNumberFormat("R$ #,##0.00"); // E, F, G
  sheet.getRange(6, 9, novaTabela.length, 2).setNumberFormat("R$ #,##0.00"); // I, J

  sheetEstoque.getRange(6, 10, precosParaEstoque.length, 1).setValues(precosParaEstoque); // J = Preço de Venda

  SpreadsheetApp.getUi().alert(
    "✅ Markup atualizado e preços enviados pro Estoque!\n\n" +
    "Gastos do mês: R$ " + totalGastos.toFixed(2) + "\n" +
    "Receita bruta do mês: R$ " + totalReceita.toFixed(2) + "\n" +
    "Rateio: " + (rateioPercentual * 100).toFixed(2) + "% sobre o custo de cada produto"
  );
}

/**
 * Editar direto na planilha (Markup %, Preço Final ou Promoção) já recalcula e empurra pro
 * Estoque na hora — sem precisar abrir a janela "Atualizar Preço" ou clicar em "Atualizar Tudo".
 */
function onEdit(e) {
  if (!e || e.range.getSheet().getName() !== NOME_ABA_MARKUP) return;
  const linha = e.range.getRow();
  const coluna = e.range.getColumn();
  if (linha < 6) return;

  const sheet = e.range.getSheet();
  const custoReal = parseFloat(sheet.getRange(linha, 7).getValue()) || 0;
  let precoFinal;

  if (coluna === 8) { // H = Markup % editado → recalcula o Preço Final
    const markup = parseFloat(e.value) || 0;
    precoFinal = custoReal * (1 + markup / 100);
    sheet.getRange(linha, 9).setValue(precoFinal).setNumberFormat("R$ #,##0.00");
  } else if (coluna === 9) { // I = Preço Final editado direto → recalcula o Markup implícito
    precoFinal = parseFloat(e.value) || 0;
    const markupImplicito = custoReal > 0 ? ((precoFinal / custoReal) - 1) * 100 : 0;
    sheet.getRange(linha, 8).setValue(Number(markupImplicito.toFixed(2)));
  } else if (coluna === 10) { // J = Promoção editada → empurra ela (não o preço final) pro Estoque
    const promocional = parseFloat(e.value);
    empurrarPrecoParaEstoque(linha, !isNaN(promocional) ? promocional : parseFloat(sheet.getRange(linha, 9).getValue()) || 0);
    return;
  } else {
    return;
  }

  // Se já tiver uma promoção ativa nessa linha, ela continua valendo lá no Estoque; senão, vai o preço final.
  const promoAtual = parseFloat(sheet.getRange(linha, 10).getValue());
  empurrarPrecoParaEstoque(linha, !isNaN(promoAtual) ? promoAtual : precoFinal);
}

function empurrarPrecoParaEstoque(linha, valor) {
  try {
    const ssEstoque = SpreadsheetApp.openById(ID_PLANILHA_ESTOQUE_MKP);
    const sheetEstoque = ssEstoque.getSheetByName("ESTOQUE") || ssEstoque.getSheets()[0];
    sheetEstoque.getRange(linha, 10).setValue(valor); // J = Preço de Venda
  } catch (err) {
    Logger.log("Erro ao empurrar preço pro Estoque: " + err.message);
  }
}


/**
 * ============================================================================
 * JANELA "ATUALIZAR PREÇO" — busca um produto, mostra o custo/rateio como referência,
 * e deixa você decidir: Markup % OU Preço Final direto, mais uma Promoção opcional.
 * ============================================================================
 */
function abrirJanelaAtualizarPreco() {
  const html = HtmlService.createHtmlOutput(getHtmlAtualizarPreco()).setWidth(480).setHeight(600);
  SpreadsheetApp.getUi().showModalDialog(html, "💲 Atualizar Preço do Produto");
}

/**
 * Lê DIRETO do Estoque (não usa mais a cópia da aba Markup) — só o essencial:
 * Código, Descrição, Preço de Entrada (referência) e Preço de Venda atual.
 */
function obterProdutosSimples() {
  try {
    const ssEstoque = SpreadsheetApp.openById(ID_PLANILHA_ESTOQUE_MKP);
    const sheetEstoque = ssEstoque.getSheetByName("ESTOQUE") || ssEstoque.getSheets()[0];
    const lastRow = sheetEstoque.getLastRow();
    if (lastRow < 6) return [];

    const dados = sheetEstoque.getRange(6, 1, lastRow - 5, 10).getValues(); // A até J
    const resultados = [];

    dados.forEach((row, i) => {
      const linha = i + 6;
      const codigo = String(row[0] || ""), desc = String(row[2] || "");
      if (!desc) return;

      resultados.push({
        linha,
        codigo,
        desc,
        precoEntrada: parseFloat(row[7]) || 0,     // H = Preço de Entrada (pacote, só referência)
        precoFracionado: parseFloat(row[8]) || 0,  // I = Preço Fracionado (custo real por unidade)
        precoVendaAtual: parseFloat(row[9]) || 0   // J = Preço de Venda
      });
    });

    return resultados;
  } catch (e) {
    return { erro: e.message };
  }
}

/**
 * Salva o novo Preço de Venda direto na coluna J do Estoque, e sincroniza a aba
 * Markup (Custo Real, Markup% e Preço Final) na mesma linha, pra ela não ficar desatualizada.
 */
function salvarPrecoSimples(linha, novoPreco, precoPromocional, markupPct, rateioPct) {
  try {
    const l = parseInt(linha, 10);
    const ssEstoque = SpreadsheetApp.openById(ID_PLANILHA_ESTOQUE_MKP);
    const sheetEstoque = ssEstoque.getSheetByName("ESTOQUE") || ssEstoque.getSheets()[0];

    const temPromo = precoPromocional !== "" && precoPromocional !== null && precoPromocional !== undefined && !isNaN(parseFloat(precoPromocional));
    const precoFinal = parseFloat(novoPreco) || 0;
    const precoParaEstoque = temPromo ? parseFloat(precoPromocional) : precoFinal;

    sheetEstoque.getRange(l, 10).setValue(precoParaEstoque).setNumberFormat("R$ #,##0.00"); // J = Preço de Venda

    // Sincroniza a aba Markup (se ela existir), pra continuar batendo com o que foi salvo aqui.
    try {
      const sheetMarkup = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(NOME_ABA_MARKUP);
      if (sheetMarkup) {
        const custoFracionado = parseFloat(sheetEstoque.getRange(l, 9).getValue()) || 0; // I do Estoque
        const rateioValor = custoFracionado * ((parseFloat(rateioPct) || 0) / 100);
        const custoReal = custoFracionado + rateioValor;

        sheetMarkup.getRange(l, 5).setValue(custoFracionado).setNumberFormat("R$ #,##0.00"); // E = Custo Compra
        sheetMarkup.getRange(l, 6).setValue(rateioValor).setNumberFormat("R$ #,##0.00");     // F = Rateio (R$)
        sheetMarkup.getRange(l, 7).setValue(custoReal).setNumberFormat("R$ #,##0.00");       // G = Custo Real
        sheetMarkup.getRange(l, 8).setValue(parseFloat(markupPct) || 0);                     // H = Markup %
        sheetMarkup.getRange(l, 9).setValue(precoFinal).setNumberFormat("R$ #,##0.00");      // I = Preço Final
        sheetMarkup.getRange(l, 10).setValue(temPromo ? parseFloat(precoPromocional) : "").setNumberFormat("R$ #,##0.00"); // J = Promocional
      }
    } catch (eSync) {
      Logger.log("Aviso: não deu pra sincronizar a aba Markup: " + eSync.message);
    }

    return { sucesso: true, mensagem: temPromo ? "✅ Preço promocional aplicado no Estoque!" : "✅ Preço atualizado no Estoque!" };
  } catch (e) {
    return { sucesso: false, mensagem: "❌ Erro: " + e.message };
  }
}

function getHtmlAtualizarPreco() {
  return `<!DOCTYPE html>
<html>
<head>
  <base target="_top">
  <style>
    * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, sans-serif; }
    body { margin: 0; padding: 14px; font-size: 12px; color: #333; background: #f8f9fa; }
    input { width: 100%; padding: 8px; border-radius: 6px; border: 1px solid #cbd5e1; font-size: 12px; margin-bottom: 8px; }
    label { font-weight: bold; font-size: 11px; color: #475569; display: block; margin-bottom: 3px; }
    .lista { max-height: 320px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 6px; margin-bottom: 8px; background: #fff; }
    .item { padding: 10px; border-bottom: 1px solid #f1f5f9; cursor: pointer; }
    .item:hover { background: #f1f5f9; }
    .box { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; margin-bottom: 10px; }
    .info-line { display: flex; justify-content: space-between; font-size: 12px; padding: 3px 0; }
    .btn { width: 100%; padding: 10px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; font-size: 13px; }
    .btn-recarregar { background: #0f172a; color: white; margin-bottom: 8px; }
    .btn-salvar { background: #16a34a; color: white; }
    #status { text-align: center; font-weight: bold; margin-top: 8px; min-height: 16px; }
    #contador { font-size: 10px; color: #888; margin-bottom: 6px; }
  </style>
</head>
<body>
  <label>🔎 Buscar Produto (código ou descrição):</label>
  <div id="contador">Clique em "Recarregar" pra começar.</div>
  <button class="btn btn-recarregar" onclick="carregarProdutos()">🔄 Recarregar Produtos</button>
  <input type="text" id="busca" oninput="buscar()">
  <div class="lista" id="lista-resultados"></div>

  <div class="box" id="box-produto" style="display:none;">
    <div id="nome-produto" style="font-weight:bold;margin-bottom:6px;"></div>

    <label style="margin-top:4px;">Rateio % de custos fixos (baixo, pra cobrir sem distorcer):</label>
    <input type="number" step="0.1" id="in-rateio" value="10" oninput="recalcularTudo('rateio')">

    <div class="info-line"><span>Custo de Entrada (fracionado):</span><strong id="v-entrada">R$ 0,00</strong></div>
    <div class="info-line"><span>Custo com Rateio:</span><strong id="v-custorateio">R$ 0,00</strong></div>
    <div class="info-line"><span>Preço de Venda Atual:</span><strong id="v-atual">R$ 0,00</strong></div>

    <label style="margin-top:10px;">Markup %:</label>
    <input type="number" step="0.01" id="in-markup" oninput="recalcularTudo('markup')">

    <label>Preço de Venda (R$):</label>
    <input type="number" step="0.01" id="in-preco" oninput="recalcularTudo('preco')">

    <label style="margin-top:8px;">🏷️ Preço Promocional (opcional):</label>
    <input type="number" step="0.01" id="in-promo">

    <button class="btn btn-salvar" onclick="salvar()">💾 Salvar no Estoque</button>
    <div id="status"></div>
  </div>

  <script>
    var produtoAtual = null;
    var todosProdutos = [];

    function carregarProdutos() {
      const div = document.getElementById('lista-resultados');
      div.innerHTML = '<div class="item" style="color:#888;">⏳ Carregando...</div>';
      document.getElementById('contador').innerText = '⏳ Chamando o servidor...';

      google.script.run
        .withSuccessHandler(function(resultados) {
          if (resultados && resultados.erro) {
            div.innerHTML = '<div class="item" style="color:#dc3545;">❌ Erro: ' + resultados.erro + '</div>';
            document.getElementById('contador').innerText = '❌ Erro ao carregar';
            return;
          }
          todosProdutos = resultados || [];
          document.getElementById('contador').innerText = todosProdutos.length + ' produto(s) carregado(s) do Estoque';
          renderizarResultados(todosProdutos);
        })
        .withFailureHandler(function(err) {
          div.innerHTML = '<div class="item" style="color:#dc3545;">❌ Erro: ' + (err.message || err) + '</div>';
          document.getElementById('contador').innerText = '❌ Falha ao carregar';
        })
        .obterProdutosSimples();
    }

    function buscar() {
      const termo = document.getElementById('busca').value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase().trim();
      if (!termo) { renderizarResultados(todosProdutos); return; }
      const filtrados = todosProdutos.filter(function(p) {
        const texto = (p.codigo + ' ' + p.desc).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase();
        return texto.includes(termo);
      });
      renderizarResultados(filtrados);
    }

    function renderizarResultados(lista) {
      const div = document.getElementById('lista-resultados');
      div.innerHTML = '';
      if (!lista || lista.length === 0) {
        div.innerHTML = '<div class="item" style="color:#888;">Nenhum produto encontrado.</div>';
        return;
      }
      lista.slice(0, 100).forEach(function(p) {
        const item = document.createElement('div');
        item.className = 'item';
        item.innerHTML = '<strong>' + p.desc + '</strong><br><span style="color:#666;font-size:10px;">Preço atual: R$ ' + p.precoVendaAtual.toFixed(2).replace('.', ',') + '</span>';
        item.onclick = function() { selecionarProduto(p); };
        div.appendChild(item);
      });
    }

    function selecionarProduto(p) {
      produtoAtual = p;
      document.getElementById('busca').value = p.desc;
      document.getElementById('nome-produto').innerText = p.desc;
      document.getElementById('v-entrada').innerText = 'R$ ' + p.precoFracionado.toFixed(2).replace('.', ',');
      document.getElementById('v-atual').innerText = 'R$ ' + p.precoVendaAtual.toFixed(2).replace('.', ',');

      document.getElementById('in-rateio').value = '10';
      document.getElementById('in-preco').value = p.precoVendaAtual.toFixed(2);
      document.getElementById('in-promo').value = '';
      document.getElementById('box-produto').style.display = 'block';

      recalcularTudo('preco'); // recalcula o markup implícito a partir do preço atual
    }

    // origem indica qual campo o usuário acabou de editar, pra saber o que recalcular
    function recalcularTudo(origem) {
      if (!produtoAtual) return;

      const rateioPct = parseFloat(document.getElementById('in-rateio').value) || 0;
      const custoComRateio = produtoAtual.precoFracionado * (1 + rateioPct / 100);
      document.getElementById('v-custorateio').innerText = 'R$ ' + custoComRateio.toFixed(2).replace('.', ',');

      if (origem === 'preco') {
        // Preço editado -> recalcula o Markup % implícito
        const preco = parseFloat(document.getElementById('in-preco').value) || 0;
        const markup = custoComRateio > 0 ? ((preco / custoComRateio) - 1) * 100 : 0;
        document.getElementById('in-markup').value = markup.toFixed(2);
      } else {
        // Rateio ou Markup editado -> recalcula o Preço a partir do Markup
        const markup = parseFloat(document.getElementById('in-markup').value) || 0;
        const preco = custoComRateio * (1 + markup / 100);
        document.getElementById('in-preco').value = preco.toFixed(2);
      }
    }

    function salvar() {
      if (!produtoAtual) return;
      const st = document.getElementById('status');
      st.style.color = '#007bff';
      st.innerText = '⏳ Salvando...';

      const preco = document.getElementById('in-preco').value;
      const markup = document.getElementById('in-markup').value;
      const rateio = document.getElementById('in-rateio').value;
      const promoVal = document.getElementById('in-promo').value;
      const promo = promoVal === '' ? '' : promoVal;

      google.script.run
        .withSuccessHandler(function(res) {
          st.style.color = res.sucesso ? '#107c41' : '#dc3545';
          st.innerText = res.mensagem;
        })
        .withFailureHandler(function(err) {
          st.style.color = '#dc3545';
          st.innerText = '❌ Erro: ' + (err.message || err);
        })
        .salvarPrecoSimples(produtoAtual.linha, preco, promo, markup, rateio);
    }
  </script>
</body>
</html>`;
}


// ============================================================================
// MÓDULO: DRE
// ============================================================================
/**
 * ============================================================================
 * CFAUTO / ADM — ABA "DRE" (Demonstração de Resultado do Exercício)
 * Cole este script JUNTO com os outros (Markup, Balanço), na mesma planilha do CFAUTO.
 * ============================================================================
 *
 * Lógica de classificação (confirmada com o usuário):
 * - RECEITA: soma das vendas do período (Histórico + Caixa aberto).
 * - CMV (Custo da Mercadoria Vendida): quantidade vendida × custo fracionado atual de cada
 *   produto (busca no Estoque por ID). É uma aproximação — usa o custo ATUAL, não o custo
 *   histórico exato de quando a venda aconteceu.
 * - DESPESAS OPERACIONAIS: categorias Conta Fixa, Conta Variável, Despesa Prevista,
 *   Despesa Imprevista, Salário, Pró-Labore e Outros Proventos, todas puxadas da Saídas
 *   pelo valor total do registro.
 * - DESPESAS FINANCEIRAS: só os JUROS e TAXAS embutidos no texto de Observações dos
 *   registros de Empréstimo e Boleto (o valor principal desses dois NÃO entra aqui —
 *   Boleto de fornecedor já virou custo do produto, e Empréstimo é amortização de dívida,
 *   que mexe no Balanço, não no lucro do período).
 */

const NOME_ABA_DRE = "DRE";

function abrirJanelaDRE() {
  const html = HtmlService.createHtmlOutput(getHtmlDRE()).setWidth(560).setHeight(640);
  SpreadsheetApp.getUi().showModalDialog(html, "📈 DRE — Demonstração de Resultado");
}

/**
 * Monta um mapa {ID do produto: custo fracionado atual}, lendo do Estoque.
 */
function obterMapaCustoEstoqueDRE() {
  const mapa = {};
  try {
    const ssEstoque = SpreadsheetApp.openById(ID_PLANILHA_ESTOQUE_MKP);
    const sheetEstoque = ssEstoque.getSheetByName("ESTOQUE") || ssEstoque.getSheets()[0];
    const lastRow = sheetEstoque.getLastRow();
    if (lastRow >= 6) {
      const dados = sheetEstoque.getRange(6, 1, lastRow - 5, 9).getValues(); // A até I
      dados.forEach(row => {
        const id = String(row[1] || "").trim(); // B = ID
        const custoFracionado = parseFloat(row[8]) || 0; // I = Preço Fracionado
        if (id) mapa[id] = custoFracionado;
      });
    }
  } catch (e) {
    Logger.log("Erro ao montar mapa de custo do Estoque: " + e.message);
  }
  return mapa;
}

/**
 * Extrai um valor "Rótulo: R$ 123,45" de dentro de um texto livre (usado nas
 * Observações da Saídas para Juros e Taxa Boleto).
 */
function extrairValorDeTextoDRE(texto, rotulo) {
  const regex = new RegExp(rotulo + ":\\s*R\\$\\s*([\\d.,]+)");
  const m = String(texto || "").match(regex);
  if (!m) return 0;
  return parseFloat(m[1].replace(/\./g, '').replace(',', '.')) || 0;
}

/**
 * Gera o DRE completo do mês/ano informado (ou "TODOS" pra período completo).
 */
function gerarDRE(mes, ano) {
  const mapaCusto = obterMapaCustoEstoqueDRE();

  let receitaBruta = 0, taxasVenda = 0, cmv = 0;

  function dentroDoPeriodo(dtObj) {
    if (!dtObj) return true;
    const m = dtObj.getMonth() + 1, a = dtObj.getFullYear();
    if (mes && mes !== "TODOS" && parseInt(mes) !== m) return false;
    if (ano && ano !== "TODOS" && parseInt(ano) !== a) return false;
    return true;
  }

  function parseDataGenerica(valor) {
    if (valor instanceof Date) return valor;
    if (typeof valor === 'string' && valor.includes('/')) {
      const partes = valor.split(' ')[0].split('/');
      if (partes.length === 3) return new Date(partes[2], partes[1] - 1, partes[0]);
    }
    return null;
  }

  // 1. Histórico (caixas já fechados)
  try {
    const ssHist = SpreadsheetApp.openById(ID_PLANILHA_HISTORICO_MKP);
    const sheetHist = ssHist.getSheets()[0];
    const lastRow = sheetHist.getLastRow();
    if (lastRow >= 2) {
      const dados = sheetHist.getRange(2, 1, lastRow - 1, 13).getValues();
      dados.forEach(row => {
        const dtObj = parseDataGenerica(row[0]);
        if (!dentroDoPeriodo(dtObj)) return;

        const id = String(row[3] || "").trim();
        const categoria = String(row[5] || "");
        const valorBruto = parseFloat(row[6]) || 0;
        const qtd = parseFloat(row[7]) || 0;
        const taxa = parseFloat(row[10]) || 0;

        if (categoria === "CREDIARIO") return; // recebimento de conta não é uma venda nova

        receitaBruta += valorBruto;
        taxasVenda += taxa;
        if (mapaCusto[id] !== undefined) cmv += mapaCusto[id] * qtd;
      });
    }
  } catch (e) {
    Logger.log("Erro ao ler histórico no DRE: " + e.message);
  }

  // 2. Caixa aberto no momento (ainda não arquivado)
  try {
    const ssCaixa = SpreadsheetApp.openById(ID_PLANILHA_CAIXA_MKP);
    const sheetCaixa = ssCaixa.getSheetByName("CAIXA") || ssCaixa.getSheets()[0];
    const lastRow = sheetCaixa.getLastRow();
    if (lastRow >= 7) {
      const dados = sheetCaixa.getRange(7, 1, lastRow - 6, sheetCaixa.getLastColumn()).getValues();
      dados.forEach(row => {
        const desc = String(row[2] || "").trim();
        if (desc === "" || desc.includes("RECEBIMENTO DE CONTA")) return;

        const dtObj = parseDataGenerica(row[10]); // K = Data/Hora
        if (!dentroDoPeriodo(dtObj)) return;

        const id = String(row[1] || "").trim();
        const valorBruto = parseFloat(row[4]) || 0;
        const qtd = parseFloat(row[5]) || 0;
        const taxa = parseFloat(row[8]) || 0;

        receitaBruta += valorBruto;
        taxasVenda += taxa;
        if (mapaCusto[id] !== undefined) cmv += mapaCusto[id] * qtd;
      });
    }
  } catch (e) {
    Logger.log("Erro ao ler caixa aberto no DRE: " + e.message);
  }

  // 3. Saídas (despesas operacionais e financeiras)
  let despesasOperacionais = 0, despesasFinanceiras = 0;
  const categoriasOperacionais = ["CONTA FIXA", "CONTA VARIAVEL", "DESPESA PREVISTA", "DESPESA IMPREVISTA", "SALARIO", "PRO-LABORE", "OUTROS PROVENTOS"];

  try {
    const ssSaidas = SpreadsheetApp.openById(ID_PLANILHA_SAIDAS_MKP);
    const sheetSaidas = ssSaidas.getSheets()[0];
    const lastRow = sheetSaidas.getLastRow();
    if (lastRow >= 7) {
      const dados = sheetSaidas.getRange(7, 1, lastRow - 6, 10).getValues();
      dados.forEach(row => {
        // ⚠️ CORRIGIDO: usa a DATA DE VENCIMENTO (não a de registro) — se não, um empréstimo
        // parcelado cadastrado hoje jogaria TODAS as parcelas futuras dentro do mês atual.
        const dtObj = parseDataGenerica(row[6]); // G = Data de Vencimento
        if (!dentroDoPeriodo(dtObj)) return;

        const categoriaNorm = String(row[2] || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase().trim();
        const valor = parseFloat(row[4]) || 0;
        const obs = String(row[9] || "");

        if (categoriaNorm === "BOLETO" || categoriaNorm === "EMPRESTIMO") {
          despesasFinanceiras += extrairValorDeTextoDRE(obs, "Juros") + extrairValorDeTextoDRE(obs, "Taxa Boleto");
        } else if (categoriasOperacionais.includes(categoriaNorm)) {
          despesasOperacionais += valor;
        }
      });
    }
  } catch (e) {
    Logger.log("Erro ao ler Saídas no DRE: " + e.message);
  }

  const receitaLiquida = receitaBruta - taxasVenda;
  const lucroBruto = receitaLiquida - cmv;
  const lucroLiquido = lucroBruto - despesasOperacionais - despesasFinanceiras;
  const margemLiquida = receitaBruta > 0 ? (lucroLiquido / receitaBruta) : 0;

  return {
    receitaBruta, taxasVenda, receitaLiquida, cmv, lucroBruto,
    despesasOperacionais, despesasFinanceiras, lucroLiquido, margemLiquida
  };
}

function getHtmlDRE() {
  return `<!DOCTYPE html>
<html>
<head>
  <base target="_top">
  <style>
    * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, sans-serif; }
    body { background: #f8f9fa; margin: 0; padding: 16px; font-size: 13px; color: #333; }
    .titulo { font-size: 16px; font-weight: bold; color: #0f172a; margin-bottom: 10px; display: flex; align-items: center; gap: 6px; }
    .filtros { display: flex; gap: 8px; margin-bottom: 14px; }
    select { padding: 6px 10px; border-radius: 6px; border: 1px solid #cbd5e1; font-size: 12px; }
    .linha { display: flex; justify-content: space-between; padding: 8px 4px; border-bottom: 1px solid #f1f5f9; }
    .linha.total { font-weight: bold; border-top: 2px solid #334155; border-bottom: none; margin-top: 4px; padding-top: 10px; }
    .linha.subtotal { font-weight: bold; background: #f8fafc; }
    .neg { color: #dc3545; }
    .pos { color: #16a34a; }
    .destaque { background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px; padding: 14px; margin-top: 14px; text-align: center; }
    .destaque .valor { font-size: 22px; font-weight: bold; color: #047857; }
  </style>
</head>
<body>
  <div class="titulo">📈 DRE — Demonstração de Resultado</div>
  <div class="filtros">
    <select id="filtroMes" onchange="carregar()">
      <option value="TODOS">Todos os Meses</option>
      <option value="1">Janeiro</option><option value="2">Fevereiro</option><option value="3">Março</option>
      <option value="4">Abril</option><option value="5">Maio</option><option value="6">Junho</option>
      <option value="7">Julho</option><option value="8">Agosto</option><option value="9">Setembro</option>
      <option value="10">Outubro</option><option value="11">Novembro</option><option value="12">Dezembro</option>
    </select>
    <select id="filtroAno" onchange="carregar()">
      <option value="TODOS">Todos os Anos</option>
      <option>2024</option><option>2025</option><option selected>2026</option><option>2027</option>
    </select>
  </div>

  <div id="corpo">Carregando...</div>

  <script>
    function fmt(n) { return 'R$ ' + (n || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }

    function carregar() {
      const mes = document.getElementById('filtroMes').value;
      const ano = document.getElementById('filtroAno').value;
      document.getElementById('corpo').innerHTML = 'Calculando...';

      google.script.run.withSuccessHandler(renderizar).withFailureHandler(function(err) {
        document.getElementById('corpo').innerHTML = '<span style="color:#dc3545;">❌ Erro: ' + (err.message || err) + '</span>';
      }).gerarDRE(mes, ano);
    }

    function renderizar(d) {
      const centavos = (d.margemLiquida * 100).toFixed(1).replace('.', ',');
      document.getElementById('corpo').innerHTML = \`
        <div class="linha"><span>Receita Bruta de Vendas</span><strong>\${fmt(d.receitaBruta)}</strong></div>
        <div class="linha"><span>(-) Taxas de Cartão/Pagamento</span><strong class="neg">-\${fmt(d.taxasVenda)}</strong></div>
        <div class="linha subtotal"><span>(=) Receita Líquida</span><strong>\${fmt(d.receitaLiquida)}</strong></div>
        <div class="linha"><span>(-) CMV (Custo da Mercadoria Vendida)</span><strong class="neg">-\${fmt(d.cmv)}</strong></div>
        <div class="linha subtotal"><span>(=) Lucro Bruto</span><strong>\${fmt(d.lucroBruto)}</strong></div>
        <div class="linha"><span>(-) Despesas Operacionais</span><strong class="neg">-\${fmt(d.despesasOperacionais)}</strong></div>
        <div class="linha"><span>(-) Despesas Financeiras (juros/taxas)</span><strong class="neg">-\${fmt(d.despesasFinanceiras)}</strong></div>
        <div class="linha total"><span>(=) LUCRO LÍQUIDO DO PERÍODO</span><strong class="\${d.lucroLiquido >= 0 ? 'pos' : 'neg'}">\${fmt(d.lucroLiquido)}</strong></div>

        <div class="destaque">
          Pra cada <strong>R$ 1,00</strong> vendido, sobra de lucro líquido de verdade:<br>
          <span class="valor">R$ \${(d.margemLiquida).toFixed(2).replace('.', ',')}</span>
          <div style="font-size:11px;color:#555;margin-top:4px;">(\${centavos}% de margem líquida sobre a receita bruta)</div>
        </div>
      \`;
    }

    window.onload = carregar;
  </script>
</body>
</html>`;
}


// ============================================================================
// MÓDULO: INDICADORES FINANCEIROS
// ============================================================================
/**
 * ============================================================================
 * CFAUTO / ADM — ABA "INDICADORES" (Indicadores Financeiros estilo fundamentalista)
 * Cole junto com os outros módulos, na mesma planilha do CFAUTO.
 * ============================================================================
 *
 * De onde vem cada coisa:
 * - Patrimônio Líquido, Ativo Total, Passivo Total → aba Balanço (coluna do ano mais recente)
 * - Receita e Lucro Líquido do ano → função gerarDRE() do módulo DRE
 * - CAGR → compara a receita/lucro do primeiro e do último ano com dados no Histórico
 *
 * Sobre "Valor de Firma": como a loja não tem ação na bolsa, usamos o Patrimônio Líquido
 * como proxy do valor de mercado (abordagem padrão de "valor contábil" pra empresas fechadas).
 * Valor de Firma = Patrimônio Líquido + Dívida Líquida (Passivo Total − Ativo Circulante).
 */

const NOME_ABA_INDICADORES = "Indicadores";

function abrirJanelaIndicadores() {
  const html = HtmlService.createHtmlOutput(getHtmlIndicadores()).setWidth(700).setHeight(760);
  SpreadsheetApp.getUi().showModalDialog(html, "📊 Indicadores Financeiros");
}

/**
 * Salva o Patrimônio Líquido em duas partes, pra ficar claro de onde vem cada pedaço:
 * - Capital Social: o que VOCÊ investiu de dinheiro próprio na empresa (não é dívida).
 * - Lucros Retidos/Reservas: lucro que a empresa já gerou e ficou guardado nela — você
 *   não sacou esse dinheiro pra sua conta pessoal, ele continua "dentro" do negócio.
 * A soma dos dois é o Patrimônio Líquido total, salvo nas Propriedades do documento.
 */
function salvarPatrimonioLiquido(capitalSocial, lucrosRetidos) {
  try {
    PropertiesService.getDocumentProperties().setProperty('CAPITAL_SOCIAL', String(parseFloat(capitalSocial) || 0));
    PropertiesService.getDocumentProperties().setProperty('LUCROS_RETIDOS', String(parseFloat(lucrosRetidos) || 0));
    return { sucesso: true, mensagem: "✅ Patrimônio Líquido salvo!" };
  } catch (e) {
    return { sucesso: false, mensagem: "❌ Erro: " + e.message };
  }
}

function obterCapitalSocialSalvo() {
  const v = PropertiesService.getDocumentProperties().getProperty('CAPITAL_SOCIAL');
  return parseFloat(v) || 0;
}

function obterLucrosRetidosSalvos() {
  const v = PropertiesService.getDocumentProperties().getProperty('LUCROS_RETIDOS');
  return parseFloat(v) || 0;
}

function obterPatrimonioLiquidoSalvo() {
  return obterCapitalSocialSalvo() + obterLucrosRetidosSalvos();
}

/**
 * Monta o "retrato patrimonial" da loja usando só dados automáticos (Balancete) +
 * o Patrimônio Líquido que você salvou na mão. Substitui a antiga aba Balanço.
 */
function obterDadosPatrimoniais() {
  const ativo = calcularAtivoCirculanteAutomatico();
  const totalBens = somarBensFisicos();
  const passivo = calcularPassivoAutomatico();
  const patrimonioLiquido = obterPatrimonioLiquidoSalvo();

  return {
    ativoCirculante: ativo.ativoCirculante,
    ativoNaoCirculante: totalBens,
    ativoTotal: ativo.ativoCirculante + totalBens,
    passivoCirculante: passivo.passivoCirculante,
    passivoNaoCirculante: passivo.passivoNaoCirculante,
    passivoTotal: passivo.passivoCirculante + passivo.passivoNaoCirculante,
    patrimonioLiquido
  };
}

/**
 * Calcula a receita bruta anual de um ano específico, direto do Histórico
 * (usado pra CAGR — não depende de já ter rodado o DRE daquele ano).
 */
function obterReceitaAnual(ano) {
  let receita = 0, lucroAprox = 0;
  try {
    const ssHist = SpreadsheetApp.openById(ID_PLANILHA_HISTORICO_MKP);
    const sheetHist = ssHist.getSheets()[0];
    const lastRow = sheetHist.getLastRow();
    if (lastRow >= 2) {
      const dados = sheetHist.getRange(2, 1, lastRow - 1, 13).getValues();
      dados.forEach(row => {
        const dt = row[0];
        let dtObj = dt instanceof Date ? dt : null;
        if (!dtObj && typeof dt === 'string' && dt.includes('/')) {
          const p = dt.split(' ')[0].split('/');
          if (p.length === 3) dtObj = new Date(p[2], p[1] - 1, p[0]);
        }
        if (!dtObj || dtObj.getFullYear() !== parseInt(ano, 10)) return;
        if (String(row[5] || "") === "CREDIARIO") return;

        receita += parseFloat(row[6]) || 0;
        lucroAprox += parseFloat(row[11]) || 0;
      });
    }
  } catch (e) {
    Logger.log("Erro ao calcular receita anual: " + e.message);
  }
  return { receita, lucroAprox };
}

/**
 * Monta todos os indicadores financeiros de uma vez.
 */
function gerarIndicadores() {
  const balanco = obterDadosPatrimoniais();
  const balancete = gerarBalancete();
  const anoAtual = new Date().getFullYear();
  const dre = gerarDRE("TODOS", String(anoAtual));

  // ⚠️ CORRIGIDO: antes mostrava 0,0% quando o Patrimônio Líquido ainda não tinha sido
  // preenchido — o que parecia dizer "sua empresa não rende nada", quando na real é só
  // "ainda não temos essa informação". Agora mostra null (a tela exibe "N/A").
  const roe = balanco.patrimonioLiquido !== 0 ? dre.lucroLiquido / balanco.patrimonioLiquido : null;
  const roa = balanco.ativoTotal > 0 ? dre.lucroLiquido / balanco.ativoTotal : 0;

  const margemBruta = dre.receitaBruta > 0 ? dre.lucroBruto / dre.receitaBruta : 0;
  const margemLiquida = dre.margemLiquida;

  const dividaLiquida = balanco.passivoTotal - balanco.ativoCirculante;
  const dividaBrutaSobrePatrimonio = balanco.patrimonioLiquido > 0 ? balanco.passivoTotal / balanco.patrimonioLiquido : 0;
  const dividaLiquidaSobrePatrimonio = balanco.patrimonioLiquido > 0 ? dividaLiquida / balanco.patrimonioLiquido : 0;
  const passivoSobreAtivos = balanco.ativoTotal > 0 ? balanco.passivoTotal / balanco.ativoTotal : 0;

  const valorDeFirma = balanco.patrimonioLiquido + dividaLiquida;

  let cagrReceita = null, cagrLucro = null, anoInicial = null, anoFinal = anoAtual;
  try {
    const ssHist = SpreadsheetApp.openById(ID_PLANILHA_HISTORICO_MKP);
    const sheetHist = ssHist.getSheets()[0];
    const lastRow = sheetHist.getLastRow();
    const anosSet = new Set();
    if (lastRow >= 2) {
      const datas = sheetHist.getRange(2, 1, lastRow - 1, 1).getValues();
      datas.forEach(row => {
        const dt = row[0];
        let dtObj = dt instanceof Date ? dt : null;
        if (!dtObj && typeof dt === 'string' && dt.includes('/')) {
          const p = dt.split(' ')[0].split('/');
          if (p.length === 3) dtObj = new Date(p[2], p[1] - 1, p[0]);
        }
        if (dtObj) anosSet.add(dtObj.getFullYear());
      });
    }
    const anos = Array.from(anosSet).sort((a, b) => a - b);
    if (anos.length >= 2) {
      anoInicial = anos[0];
      anoFinal = anos[anos.length - 1];
      const nAnos = anoFinal - anoInicial;
      if (nAnos > 0) {
        const inicial = obterReceitaAnual(anoInicial);
        const final = obterReceitaAnual(anoFinal);
        if (inicial.receita > 0) cagrReceita = Math.pow(final.receita / inicial.receita, 1 / nAnos) - 1;
        if (inicial.lucroAprox > 0) cagrLucro = Math.pow(final.lucroAprox / inicial.lucroAprox, 1 / nAnos) - 1;
      }
    }
  } catch (e) {
    Logger.log("Erro ao calcular CAGR: " + e.message);
  }

  const comparador = gerarComparadorInvestimento(cagrReceita);

  return {
    balanco, balancete, dre, roe, roa, margemBruta, margemLiquida,
    dividaLiquida, dividaBrutaSobrePatrimonio, dividaLiquidaSobrePatrimonio, passivoSobreAtivos,
    valorDeFirma, cagrReceita, cagrLucro, anoInicial, anoFinal, comparador
  };
}

function getHtmlIndicadores() {
  return `<!DOCTYPE html>
<html>
<head>
  <base target="_top">
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, sans-serif; }
    body { background: #f8f9fa; margin: 0; padding: 16px; font-size: 12px; color: #333; }
    .titulo { font-size: 16px; font-weight: bold; color: #0f172a; margin-bottom: 4px; }
    .subtitulo { font-size: 11px; color: #888; margin-bottom: 14px; }
    .secao { font-size: 12px; font-weight: bold; color: #334155; margin: 14px 0 8px; border-left: 3px solid #0f172a; padding-left: 8px; }
    .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
    .card { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; }
    .card .label { font-size: 9px; text-transform: uppercase; color: #64748b; font-weight: 700; }
    .card .valor { font-size: 15px; font-weight: bold; margin-top: 3px; }
    .pos { color: #16a34a; } .neg { color: #dc3545; } .neutro { color: #0f172a; }
    .linha { display: flex; justify-content: space-between; padding: 5px 4px; border-bottom: 1px solid #f1f5f9; font-size: 11px; }
    .linha.total { font-weight: bold; background: #f8fafc; border-top: 1px solid #cbd5e1; }
    .card[onclick] { cursor: pointer; transition: opacity 0.15s; }
    .card[onclick]:hover { opacity: 0.75; }
    .card.desligado { opacity: 0.35; background: #f1f5f9; }
    .card.desligado .valor { text-decoration: line-through; }
    .card .fonte { font-size: 8px; color: #999; margin-top: 2px; }
    .sugestao { background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 12px; margin-top: 10px; font-size: 12px; line-height: 1.5; }
    .config { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px; }
    .config label { font-size: 10px; font-weight: bold; color: #475569; display: block; margin-bottom: 2px; }
    .config input { width: 100%; padding: 6px; border-radius: 6px; border: 1px solid #cbd5e1; font-size: 11px; }
    .btn { padding: 8px 14px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; background: #0f172a; color: white; font-size: 11px; margin-top: 8px; }
    .chart-box { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; margin-top: 8px; }
    .chart-container { position: relative; height: 220px; width: 100%; }
  </style>
</head>
<body>
  <div class="titulo">📊 Indicadores Financeiros</div>
  <div class="subtitulo" id="subtitulo">Carregando...</div>
  <div id="corpo"></div>

  <script>
    function fmtR(n) { return 'R$ ' + (n || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
    function fmtP(n) { return n === null || n === undefined ? '—' : ((n * 100).toFixed(1).replace('.', ',') + '%'); }
    function corDe(n) { return n === null || n === undefined ? 'neutro' : (n >= 0 ? 'pos' : 'neg'); }

    function carregarIndicadores() {
      google.script.run.withSuccessHandler(function(d) {
      if (d.erro) {
        document.getElementById('subtitulo').innerText = '';
        document.getElementById('corpo').innerHTML = '<div style="color:#dc3545;font-weight:bold;">⚠️ ' + d.erro + '</div>';
        return;
      }

      document.getElementById('subtitulo').innerText = 'Dados patrimoniais em tempo real · DRE do ano atual';

      document.getElementById('corpo').innerHTML = \`
        <div class="secao">📈 DRE Completo (ano atual)</div>
        <div class="linha"><span>Receita Bruta de Vendas</span><strong>\${fmtR(d.dre.receitaBruta)}</strong></div>
        <div class="linha"><span>(-) Taxas de Cartão/Pagamento</span><strong class="neg">-\${fmtR(d.dre.taxasVenda)}</strong></div>
        <div class="linha total"><span>(=) Receita Líquida</span><strong>\${fmtR(d.dre.receitaLiquida)}</strong></div>
        <div class="linha"><span>(-) CMV (Custo da Mercadoria Vendida)</span><strong class="neg">-\${fmtR(d.dre.cmv)}</strong></div>
        <div class="linha total"><span>(=) Lucro Bruto</span><strong>\${fmtR(d.dre.lucroBruto)}</strong></div>
        <div class="linha"><span>(-) Despesas Operacionais</span><strong class="neg">-\${fmtR(d.dre.despesasOperacionais)}</strong></div>
        <div class="linha"><span>(-) Despesas Financeiras (juros/taxas)</span><strong class="neg">-\${fmtR(d.dre.despesasFinanceiras)}</strong></div>
        <div class="linha total" style="background:#0f172a;color:#fff;"><span>(=) LUCRO LÍQUIDO DO PERÍODO</span><strong>\${fmtR(d.dre.lucroLiquido)}</strong></div>

        <div class="secao">📋 Balancete Completo</div>
        <div class="linha"><span>Caixa Físico</span><strong>\${fmtR(d.balancete.ativo.caixaFisico)}</strong></div>
        <div class="linha"><span>Caixa Virtual (cartão/PIX)</span><strong>\${fmtR(d.balancete.ativo.caixaVirtual)}</strong></div>
        <div class="linha"><span>Mercadoria (Estoque)</span><strong>\${fmtR(d.balancete.ativo.valorEstoque)}</strong></div>
        <div class="linha"><span>Contas a Receber (Crediário)</span><strong>\${fmtR(d.balancete.ativo.contasReceberCrediario)}</strong></div>
        <div class="linha"><span>Contas a Receber (Cartão a Cair)</span><strong>\${fmtR(d.balancete.ativo.contasReceberCartao)}</strong></div>
        <div class="linha total"><span>Ativo Circulante</span><strong>\${fmtR(d.balancete.ativo.ativoCirculante)}</strong></div>
        <div class="linha"><span>Bens Físicos (Ativo Não Circulante)</span><strong>\${fmtR(d.balancete.totalBens)}</strong></div>
        <div class="linha total" style="background:#0f172a;color:#fff;"><span>ATIVO TOTAL</span><strong>\${fmtR(d.balancete.ativoTotal)}</strong></div>
        <div class="linha"><span>Passivo Circulante (Boletos pendentes)</span><strong>\${fmtR(d.balancete.passivo.passivoCirculante)}</strong></div>
        <div class="linha"><span>Passivo Não Circulante (Empréstimos pendentes)</span><strong>\${fmtR(d.balancete.passivo.passivoNaoCirculante)}</strong></div>
        <div class="linha total" style="background:#0f172a;color:#fff;"><span>PASSIVO TOTAL</span><strong>\${fmtR(d.balancete.passivoTotal)}</strong></div>
        <div class="linha"><span>Patrimônio Líquido</span><strong>\${fmtR(d.balancete.patrimonioLiquido)}</strong></div>

        <div class="secao">💰 Informações da Empresa</div>
        <div class="grid">
          <div class="card"><div class="label">Patrimônio Líquido</div><div class="valor neutro">\${fmtR(d.balanco.patrimonioLiquido)}</div></div>
          <div class="card"><div class="label">Ativo Total</div><div class="valor neutro">\${fmtR(d.balanco.ativoTotal)}</div></div>
          <div class="card"><div class="label">Valor de Firma (proxy)</div><div class="valor neutro">\${fmtR(d.valorDeFirma)}</div></div>
        </div>

        <div class="secao">📈 Rentabilidade</div>
        <div class="grid">
          <div class="card"><div class="label">ROE (Lucro / Patrimônio)</div><div class="valor \${corDe(d.roe)}">\${fmtP(d.roe)}</div></div>
          <div class="card"><div class="label">ROA (Lucro / Ativos)</div><div class="valor \${corDe(d.roa)}">\${fmtP(d.roa)}</div></div>
          <div class="card"><div class="label">Margem Líquida</div><div class="valor \${corDe(d.margemLiquida)}">\${fmtP(d.margemLiquida)}</div></div>
        </div>

        <div class="secao">⚙️ Eficiência</div>
        <div class="grid">
          <div class="card"><div class="label">Margem Bruta</div><div class="valor \${corDe(d.margemBruta)}">\${fmtP(d.margemBruta)}</div></div>
          <div class="card"><div class="label">Receita (ano atual)</div><div class="valor neutro">\${fmtR(d.dre.receitaBruta)}</div></div>
          <div class="card"><div class="label">Lucro Líquido (ano atual)</div><div class="valor \${corDe(d.dre.lucroLiquido)}">\${fmtR(d.dre.lucroLiquido)}</div></div>
        </div>

        <div class="secao">🏦 Endividamento</div>
        <div class="grid">
          <div class="card"><div class="label">Dívida Líquida</div><div class="valor neutro">\${fmtR(d.dividaLiquida)}</div></div>
          <div class="card"><div class="label">Dívida Bruta / Patrimônio</div><div class="valor neutro">\${fmtP(d.dividaBrutaSobrePatrimonio)}</div></div>
          <div class="card"><div class="label">Passivo / Ativos</div><div class="valor neutro">\${fmtP(d.passivoSobreAtivos)}</div></div>
        </div>

        <div class="secao">🚀 Crescimento\${d.anoInicial ? ' (' + d.anoInicial + ' → ' + d.anoFinal + ')' : ''}</div>
        <div class="grid">
          <div class="card"><div class="label">CAGR Receita</div><div class="valor \${d.cagrReceita === null ? 'neutro' : corDe(d.cagrReceita)}">\${d.cagrReceita === null ? 'Precisa de 2+ anos' : fmtP(d.cagrReceita)}</div></div>
          <div class="card"><div class="label">CAGR Lucro (aprox.)</div><div class="valor \${d.cagrLucro === null ? 'neutro' : corDe(d.cagrLucro)}">\${d.cagrLucro === null ? 'Precisa de 2+ anos' : fmtP(d.cagrLucro)}</div></div>
        </div>

        <div class="secao">🎯 Comparador de Investimento</div>
        <div class="grid">
          <div class="card destaque"><div class="label">🏪 Sua Empresa (CAGR Receita)</div><div class="valor \${corDe(d.comparador.crescimentoEmpresa)}">\${fmtP(d.comparador.crescimentoEmpresa)}</div></div>
          <div class="card"><div class="label">📈 BOVA11 (Ibovespa)</div><div class="valor \${corDe(d.comparador.crescimentoBova)}">\${fmtP(d.comparador.crescimentoBova)}</div></div>
          <div class="card"><div class="label">💵 Dólar</div><div class="valor \${corDe(d.comparador.crescimentoDolar)}">\${fmtP(d.comparador.crescimentoDolar)}</div></div>
        </div>

        <div class="chart-box">
          <div style="font-size:11px;font-weight:bold;color:#334155;margin-bottom:6px;">📊 Evolução em "Cotas" — Empresa x BOVA11 x CDI x Dólar (base 100 no primeiro mês)</div>
          <div class="chart-container"><canvas id="chartEvolucao"></canvas></div>
        </div>

        <div style="font-size:10px;color:#888;margin:8px 0 4px;">Clique num cartão pra tirar ele da comparação:</div>
        <div class="grid">
          <div class="card \${d.comparador.ativos.cdi ? '' : 'desligado'}" onclick="alternarRF('cdi')"><div class="label">CDI</div><div class="valor pos">\${fmtP(d.comparador.cdiUsado)}</div><div class="fonte">\${d.comparador.cdiFonte}</div></div>
          <div class="card \${d.comparador.ativos.poupanca ? '' : 'desligado'}" onclick="alternarRF('poupanca')"><div class="label">Poupança</div><div class="valor pos">\${fmtP(d.comparador.poupanca)}</div></div>
          <div class="card \${d.comparador.ativos.simples ? '' : 'desligado'}" onclick="alternarRF('simples')"><div class="label">Investimento Simples</div><div class="valor pos">\${fmtP(d.comparador.investSimples)}</div></div>
          <div class="card \${d.comparador.ativos.cdb ? '' : 'desligado'}" onclick="alternarRF('cdb')"><div class="label">CDB Médio</div><div class="valor pos">\${fmtP(d.comparador.cdb)}</div></div>
        </div>

        <div class="sugestao">💡 <strong>Sugestão:</strong> \${d.comparador.sugestao}</div>

        <div class="secao">⚙️ Configuração do Comparador</div>
        <div class="config">
          <div><label>CDI manual (% a.a., se a busca automática falhar)</label><input type="number" step="0.01" id="in-cdi" value="\${d.comparador.cfg.cdiManual}"></div>
          <div><label>Poupança (% a.a.)</label><input type="number" step="0.01" id="in-poup" value="\${d.comparador.cfg.poupancaAnual}"></div>
          <div><label>Investimento simples fixo (% a.a.)</label><input type="number" step="0.01" id="in-simples" value="\${d.comparador.cfg.investSimplesAnual}"></div>
          <div><label>CDB médio (% do CDI)</label><input type="number" step="0.01" id="in-cdb" value="\${d.comparador.cfg.cdbPercCDI}"></div>
        </div>
        <button class="btn" onclick="salvarConfigRF()">💾 Salvar Configuração</button>
        <div id="status-rf" style="text-align:center;font-weight:bold;margin-top:8px;"></div>
      \`;

      carregarGraficoEvolucao();
    }).withFailureHandler(function(err) {
      document.getElementById('corpo').innerHTML = '<div style="color:#dc3545;">❌ Erro: ' + (err.message || err) + '</div>';
    }).gerarIndicadores();
    }

    var chartEvolucaoObj = null;

    function carregarGraficoEvolucao() {
      google.script.run.withSuccessHandler(function(ev) {
        const canvas = document.getElementById('chartEvolucao');
        if (!canvas) return;
        if (ev.erro) {
          canvas.parentElement.innerHTML = '<div style="font-size:11px;color:#888;padding:10px;text-align:center;">' + ev.erro + '</div>';
          return;
        }

        const datasets = [
          { label: 'Sua Empresa', data: ev.empresa, borderColor: '#dc3545', borderWidth: 2, tension: 0.2, pointRadius: 0 }
        ];
        if (ev.bova && ev.bova.length) datasets.push({ label: 'BOVA11', data: ev.bova, borderColor: '#0284c7', borderWidth: 2, tension: 0.2, pointRadius: 0 });
        if (ev.dolar && ev.dolar.length) datasets.push({ label: 'Dólar', data: ev.dolar, borderColor: '#16a34a', borderWidth: 2, tension: 0.2, pointRadius: 0 });
        if (ev.cdi && ev.cdi.length) datasets.push({ label: 'CDI', data: ev.cdi, borderColor: '#64748b', borderWidth: 2, tension: 0.2, pointRadius: 0 });

        if (chartEvolucaoObj) chartEvolucaoObj.destroy();
        chartEvolucaoObj = new Chart(canvas.getContext('2d'), {
          type: 'line',
          data: { labels: ev.labels, datasets: datasets },
          options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'top', labels: { boxWidth: 10, font: { size: 9 } } } },
            scales: {
              y: { ticks: { font: { size: 9 }, callback: function(v) { return v + '%'; } } },
              x: { ticks: { font: { size: 8 } } }
            }
          }
        });
      }).withFailureHandler(function(err) {
        const canvas = document.getElementById('chartEvolucao');
        if (canvas) canvas.parentElement.innerHTML = '<div style="font-size:11px;color:#dc3545;">❌ ' + (err.message || err) + '</div>';
      }).gerarEvolucaoComparativa();
    }

    carregarIndicadores();

    function alternarRF(chave) {
      google.script.run.withSuccessHandler(function() { carregarIndicadores(); }).alternarRendaFixa(chave);
    }

    function salvarConfigRF() {
      const st = document.getElementById('status-rf');
      st.style.color = '#007bff';
      st.innerText = '⏳ Salvando...';
      google.script.run.withSuccessHandler(function(res) {
        st.style.color = res.sucesso ? '#107c41' : '#dc3545';
        st.innerText = res.mensagem;
        carregarIndicadores();
      }).withFailureHandler(function(err) {
        st.style.color = '#dc3545';
        st.innerText = '❌ Erro: ' + (err.message || err);
      }).salvarConfigComparador(
        document.getElementById('in-cdi').value,
        document.getElementById('in-poup').value,
        document.getElementById('in-simples').value,
        document.getElementById('in-cdb').value
      );
    }
  </script>
</body>
</html>`;
}


// ============================================================================
// MÓDULO: BENS FÍSICOS — vive DENTRO da aba Markup (colunas N em diante), não numa
// aba separada. Fica num bloco de COLUNAS (não linhas) de propósito: assim nunca
// colide com a lista de produtos, que cresce/encolhe toda vez que "Atualizar Tudo"
// roda. Cada bem ganha um código próprio ("BEM-001", "BEM-002"...) pra identificar
// que aquele registro é um bem, não um produto — o mesmo padrão que o Serviço vai usar.
// ============================================================================

const COL_INICIO_BENS = 14; // Coluna N

function abrirJanelaBensFisicos() {
  const html = HtmlService.createHtmlOutput(getHtmlBensFisicos()).setWidth(420).setHeight(540);
  SpreadsheetApp.getUi().showModalDialog(html, "🏠 Bens Físicos");
}

function configurarAbaBens() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(NOME_ABA_MARKUP);
  if (!sheet) { SpreadsheetApp.getUi().alert("Rode '⚙️ Configurar Aba Markup' primeiro."); return; }

  sheet.getRange(5, COL_INICIO_BENS, 1, 4).setValues([["CÓDIGO", "DESCRIÇÃO / TIPO", "VALOR (R$)", "DATA DE CADASTRO"]]).setFontWeight("bold");
  sheet.setColumnWidth(COL_INICIO_BENS, 90);
  sheet.setColumnWidth(COL_INICIO_BENS + 1, 220);

  SpreadsheetApp.getUi().alert("✅ Bloco de Bens Físicos criado na própria aba Markup (colunas N em diante)!");
}

function obterListaBens() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(NOME_ABA_MARKUP);
  if (!sheet) return [];
  const lastRow = sheet.getLastRow();
  if (lastRow < 6) return [];

  const dados = sheet.getRange(6, COL_INICIO_BENS, lastRow - 5, 4).getValues();
  return dados
    .map((r, i) => ({ linha: i + 6, codigo: r[0], descTipo: r[1], valor: parseFloat(r[2]) || 0 }))
    .filter(b => b.codigo && String(b.codigo).trim() !== "")
    .map(b => {
      // "descTipo" foi salvo como "Descrição — Tipo": separa de volta os dois pra exibir.
      const partes = String(b.descTipo).split(" — ");
      return { linha: b.linha, codigo: b.codigo, desc: partes[0] || b.descTipo, tipo: partes[1] || "Outros", valor: b.valor };
    });
}

function obterProximoCodigoBem() {
  const bens = obterListaBens();
  let maiorNumero = 0;
  bens.forEach(b => {
    const m = String(b.codigo).match(/BEM-(\d+)/);
    if (m) maiorNumero = Math.max(maiorNumero, parseInt(m[1], 10));
  });
  return "BEM-" + String(maiorNumero + 1).padStart(3, "0");
}

function adicionarBemFisico(desc, tipo, valor) {
  try {
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(NOME_ABA_MARKUP);
    if (!sheet) return { sucesso: false, mensagem: "❌ Rode 'Configurar Aba Markup' primeiro." };

    // Garante que o cabeçalho do bloco de Bens existe (autoconfigurações na primeira vez).
    if (String(sheet.getRange(5, COL_INICIO_BENS).getValue()).trim() === "") {
      sheet.getRange(5, COL_INICIO_BENS, 1, 4).setValues([["CÓDIGO", "DESCRIÇÃO / TIPO", "VALOR (R$)", "DATA DE CADASTRO"]]).setFontWeight("bold");
    }

    const codigo = obterProximoCodigoBem();
    const lastRow = Math.max(sheet.getLastRow(), 5);

    // Acha a primeira linha livre DENTRO do bloco de bens (pode ser bem menor que o
    // lastRow geral da aba, que é ditado pela lista de produtos).
    let linha = 6;
    while (String(sheet.getRange(linha, COL_INICIO_BENS).getValue()).trim() !== "") linha++;

    const hoje = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "dd/MM/yyyy");
    sheet.getRange(linha, COL_INICIO_BENS, 1, 4).setValues([[codigo, desc + " — " + (tipo || "Outros"), parseFloat(valor) || 0, hoje]]);
    sheet.getRange(linha, COL_INICIO_BENS + 2).setNumberFormat("R$ #,##0.00");

    return { sucesso: true, mensagem: "✅ Bem cadastrado como " + codigo + "!" };
  } catch (e) {
    return { sucesso: false, mensagem: "❌ Erro: " + e.message };
  }
}

function excluirBemFisico(linha) {
  try {
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(NOME_ABA_MARKUP);
    // Não usa deleteRow aqui — isso deletaria a linha inteira e bagunçaria a lista de
    // produtos, que mora nas colunas A-K dessa mesma linha. Só limpa o bloco de bens.
    sheet.getRange(parseInt(linha, 10), COL_INICIO_BENS, 1, 4).clearContent();
    return { sucesso: true, mensagem: "✅ Excluído!" };
  } catch (e) {
    return { sucesso: false, mensagem: "❌ Erro: " + e.message };
  }
}

function somarBensFisicos() {
  return obterListaBens().reduce((soma, b) => soma + b.valor, 0);
}

/**
 * Soma o Passivo direto da Saídas: Boletos PENDENTES = Passivo Circulante (curto prazo),
 * Empréstimos PENDENTES = Passivo Não Circulante (financiamento mais longo).
 */
/**
 * Soma o Passivo olhando TODAS as contas PENDENTES da Saídas (Conta Fixa, Boleto,
 * Empréstimo, etc.) — qualquer coisa pendente é um compromisso futuro real, tipo o
 * aluguel de 12x que ainda não foi todo pago.
 *
 * Classifica pela DATA DE VENCIMENTO de verdade: vence dentro de 1 ano a partir de
 * hoje = Passivo Circulante; vence depois disso = Passivo Não Circulante. Também
 * devolve o detalhamento item a item, pra não ficar só um número solto no Balancete.
 */
function calcularPassivoAutomatico() {
  let passivoCirculante = 0, passivoNaoCirculante = 0;
  const detalhamento = [];
  const hoje = new Date(); hoje.setHours(0, 0, 0, 0);
  const umAnoDepois = new Date(hoje.getTime());
  umAnoDepois.setDate(umAnoDepois.getDate() + 365);

  try {
    const ssSaidas = SpreadsheetApp.openById(ID_PLANILHA_SAIDAS_MKP);
    const sheetSaidas = ssSaidas.getSheets()[0];
    const lastRow = sheetSaidas.getLastRow();
    if (lastRow >= 7) {
      const dados = sheetSaidas.getRange(7, 1, lastRow - 6, 10).getValues();
      dados.forEach(row => {
        const status = String(row[7] || "").toUpperCase().trim();
        if (status !== "PENDENTE") return;

        const categoria = String(row[2] || "").trim();
        const descricao = String(row[3] || "").trim();
        const valor = parseFloat(row[4]) || 0;
        const parcela = String(row[5] || "").trim();
        const vencimentoRaw = row[6];

        let dtVenc = vencimentoRaw instanceof Date ? vencimentoRaw : parseDataBrGenerica(vencimentoRaw);
        const ehCirculante = !dtVenc || dtVenc <= umAnoDepois;

        if (ehCirculante) passivoCirculante += valor;
        else passivoNaoCirculante += valor;

        detalhamento.push({
          categoria, descricao, valor, parcela,
          vencimento: dtVenc ? Utilities.formatDate(dtVenc, Session.getScriptTimeZone(), "dd/MM/yyyy") : "—",
          prazo: ehCirculante ? "Circulante" : "Não Circulante"
        });
      });
    }
  } catch (e) {
    Logger.log("Erro ao calcular passivo automático: " + e.message);
  }

  detalhamento.sort((a, b) => a.vencimento.localeCompare(b.vencimento));
  return { passivoCirculante, passivoNaoCirculante, detalhamento };
}

/**
 * Não existe mais aba Balanço pra sincronizar — Ativo, Passivo e Patrimônio Líquido
 * agora são só lidos ao vivo (calcularAtivoCirculanteAutomatico, somarBensFisicos,
 * calcularPassivoAutomatico, obterPatrimonioLiquidoSalvo) direto no Balancete e nos
 * Indicadores, sem precisar "empurrar" nada pra lugar nenhum.
 */

function getHtmlBensFisicos() {
  return `<!DOCTYPE html>
<html>
<head>
  <base target="_top">
  <style>
    * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, sans-serif; }
    body { margin: 0; padding: 14px; font-size: 12px; color: #333; background: #f8f9fa; }
    label { font-weight: bold; font-size: 11px; color: #475569; display: block; margin-bottom: 3px; }
    input { width: 100%; padding: 8px; border-radius: 6px; border: 1px solid #cbd5e1; font-size: 12px; margin-bottom: 8px; }
    .btn { width: 100%; padding: 9px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; background: #16a34a; color: white; }
    .lista { margin-top: 14px; max-height: 220px; overflow-y: auto; }
    .item { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid #eee; }
    .del { color: #dc3545; cursor: pointer; font-weight: bold; }
    .total { text-align: right; font-weight: bold; margin-top: 8px; padding-top: 8px; border-top: 2px solid #334155; }
    #status { text-align: center; font-weight: bold; margin-top: 8px; min-height: 16px; }
  </style>
</head>
<body>
  <label>Descrição do bem:</label>
  <input type="text" id="in-desc">
  <label>Tipo:</label>
  <select id="in-tipo">
    <option value="Móvel">Móvel (equipamento, móvel, veículo)</option>
    <option value="Intangível">Intangível (marca, software, ponto comercial)</option>
    <option value="Outros">Outros</option>
  </select>
  <label>Valor (R$):</label>
  <input type="number" step="0.01" id="in-valor">
  <button class="btn" onclick="adicionar()">➕ Adicionar Bem</button>
  <div id="status"></div>

  <div class="lista" id="lista"></div>
  <div class="total" id="total"></div>

  <script>
    function fmt(n) { return 'R$ ' + (n || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }

    function carregar() {
      google.script.run.withSuccessHandler(renderizar).obterListaBens();
    }

    function renderizar(lista) {
      const div = document.getElementById('lista');
      div.innerHTML = '';
      let total = 0;
      (lista || []).forEach(function(b) {
        total += b.valor;
        const item = document.createElement('div');
        item.className = 'item';
        item.innerHTML = '<span><strong style="color:#0f172a;">' + b.codigo + '</strong> — ' + b.desc + ' <span style="color:#888;font-size:10px;">(' + b.tipo + ')</span> — ' + fmt(b.valor) + '</span><span class="del">🗑️</span>';
        item.querySelector('.del').onclick = function() { excluir(b.linha); };
        div.appendChild(item);
      });
      document.getElementById('total').innerText = 'Total: ' + fmt(total);
    }

    function adicionar() {
      const desc = document.getElementById('in-desc').value.trim();
      const tipo = document.getElementById('in-tipo').value;
      const valor = document.getElementById('in-valor').value;
      if (!desc || !valor) { document.getElementById('status').innerText = '⚠️ Preencha descrição e valor.'; return; }

      google.script.run.withSuccessHandler(function(res) {
        document.getElementById('status').style.color = res.sucesso ? '#107c41' : '#dc3545';
        document.getElementById('status').innerText = res.mensagem;
        if (res.sucesso) {
          document.getElementById('in-desc').value = '';
          document.getElementById('in-valor').value = '';
          carregar();
        }
      }).adicionarBemFisico(desc, tipo, valor);
    }

    function excluir(linha) {
      google.script.run.withSuccessHandler(function() { carregar(); }).excluirBemFisico(linha);
    }

    window.onload = carregar;
  </script>
</body>
</html>`;
}


// ============================================================================
// MÓDULO: BALANCETE (detalha o que forma o Ativo Circulante) + sincronização completa
// ============================================================================

/**
 * Calcula o Ativo Circulante automaticamente:
 * - Caixa Físico e Virtual: direto do painel ao vivo da planilha Caixa (F2 e J2).
 * - Mercadoria (Estoque): soma de custo fracionado × quantidade de cada produto.
 * - Contas a Receber (Crediário): compras a prazo no Histórico menos os recebimentos já feitos.
 * - Contas a Receber (Cartão Futuro): vendas do Histórico cuja "Liquidado em" (dias) ainda
 *   não chegou — ou seja, dinheiro que ainda vai cair.
 */
/**
 * Converte uma data em texto "dd/MM/yyyy..." (ou já um objeto Date) num objeto Date.
 */
function parseDataBrGenerica(valor) {
  if (valor instanceof Date) return valor;
  if (typeof valor === 'string' && valor.includes('/')) {
    const partes = valor.split(' ')[0].split('/');
    if (partes.length === 3) return new Date(partes[2], partes[1] - 1, partes[0]);
  }
  return null;
}

function calcularAtivoCirculanteAutomatico() {
  const hoje = new Date(); hoje.setHours(0, 0, 0, 0);
  let caixaFisico = 0, caixaVirtual = 0, valorEstoque = 0, contasReceberCrediario = 0, contasReceberCartao = 0;

  // 1. Caixa Físico: direto do painel (F2) — dinheiro é sempre imediato, sem liquidação futura.
  try {
    const ssCaixa = SpreadsheetApp.openById(ID_PLANILHA_CAIXA_MKP);
    const sheetCaixa = ssCaixa.getSheetByName("CAIXA") || ssCaixa.getSheets()[0];
    caixaFisico = parseFloat(sheetCaixa.getRange("F2").getValue()) || 0;

    // ⚠️ CORRIGIDO: em vez de usar o J2 (que junta já-disponível + a-cair numa coisa só),
    // lê linha por linha as vendas do caixa ABERTO e separa certo pela data de liquidação —
    // exatamente como já fazíamos pro Histórico, mas que faltava aqui pro caixa ainda aberto.
    // ⚠️ SIMPLIFICADO: em vez de recalcular a data de liquidação do zero (dias + data da
    // venda), usa direto a coluna J (Recebido), que o próprio Caixa já calcula. Se a data
    // ali for diferente de hoje, o valor da coluna E ainda não caiu — vira "a receber".
    // Isso só pega Débito/Crédito/PIX na prática, porque Dinheiro sempre cai no mesmo dia
    // (J = hoje) e Crediário já foi filtrado antes.
    const hojeTexto = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "dd/MM/yyyy");

    const lastRow = sheetCaixa.getLastRow();
    if (lastRow >= 7) {
      const dados = sheetCaixa.getRange(7, 1, lastRow - 6, sheetCaixa.getLastColumn()).getValues();
      dados.forEach(row => {
        const desc = String(row[2] || "").trim();
        if (desc === "" || desc.includes("RECEBIMENTO DE CONTA")) return; // crediário tratado à parte

        const pagamentoNorm = String(row[6] || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase();
        if (!["CREDITO", "DEBITO", "PIX", "EXTERNA"].includes(pagamentoNorm)) return; // dinheiro já está no F2

        const valorBruto = parseFloat(row[4]) || 0; // E = Valor
        // ⚠️ CORRIGIDO: a coluna J às vezes vem como DATA de verdade (o Sheets converte
        // sozinho um texto "dd/MM/yyyy"), não como texto puro — precisa tratar os dois casos.
        const recebidoTexto = row[9] instanceof Date
          ? Utilities.formatDate(row[9], Session.getScriptTimeZone(), "dd/MM/yyyy")
          : String(row[9] || "").trim();

        if (recebidoTexto === hojeTexto) caixaVirtual += valorBruto;
        else contasReceberCartao += valorBruto;
      });
    }

    // Crediário do caixa ainda aberto (venda a prazo feita hoje, antes de fechar o caixa)
    if (lastRow >= 7) {
      const dados2 = sheetCaixa.getRange(7, 1, lastRow - 6, sheetCaixa.getLastColumn()).getValues();
      dados2.forEach(row => {
        const desc = String(row[2] || "").trim();
        const pagamentoNorm = String(row[6] || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase();
        if (pagamentoNorm !== "CREDIARIO") return;
        const valorBruto = parseFloat(row[4]) || 0;
        if (desc.includes("RECEBIMENTO DE CONTA")) contasReceberCrediario -= valorBruto;
        else contasReceberCrediario += valorBruto;
      });
    }
  } catch (e) {
    Logger.log("Erro ao ler painel/linhas do Caixa: " + e.message);
  }

  // 2. Mercadoria (valor total em Estoque)
  try {
    const ssEstoque = SpreadsheetApp.openById(ID_PLANILHA_ESTOQUE_MKP);
    const sheetEstoque = ssEstoque.getSheetByName("ESTOQUE") || ssEstoque.getSheets()[0];
    const lastRow = sheetEstoque.getLastRow();
    if (lastRow >= 6) {
      const dados = sheetEstoque.getRange(6, 1, lastRow - 5, 11).getValues(); // A até K
      dados.forEach(row => {
        const custoFracionado = parseFloat(row[8]) || 0; // I
        const qtd = parseFloat(row[10]) || 0; // K = Estoque (qtd)
        valorEstoque += custoFracionado * qtd;
      });
    }
  } catch (e) {
    Logger.log("Erro ao ler Estoque: " + e.message);
  }

  // 3. Crediário em aberto + Dinheiro Futuro (cartão ainda não liquidado), do Histórico (caixas já fechados)
  try {
    const ssHist = SpreadsheetApp.openById(ID_PLANILHA_HISTORICO_MKP);
    const sheetHist = ssHist.getSheets()[0];
    const lastRow = sheetHist.getLastRow();
    if (lastRow >= 2) {
      const dados = sheetHist.getRange(2, 1, lastRow - 1, 13).getValues();
      dados.forEach(row => {
        const desc = String(row[4] || "");
        const pagamentoNorm = String(row[8] || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase();
        const valorBruto = parseFloat(row[6]) || 0;
        const valorLiquido = parseFloat(row[11]) || valorBruto;
        const diasNum = parseInt(row[9], 10) || 0;
        const dtObj = row[0] instanceof Date ? row[0] : null;

        if (pagamentoNorm === "CREDIARIO") {
          if (desc.includes("RECEBIMENTO DE CONTA")) contasReceberCrediario -= valorBruto;
          else contasReceberCrediario += valorBruto;
          return;
        }

        if (dtObj) {
          const dataQueCai = new Date(dtObj.getTime());
          dataQueCai.setDate(dataQueCai.getDate() + diasNum);
          dataQueCai.setHours(0, 0, 0, 0);
          if (dataQueCai > hoje) contasReceberCartao += valorLiquido;
        }
      });
    }
  } catch (e) {
    Logger.log("Erro ao ler Histórico: " + e.message);
  }

  contasReceberCrediario = Math.max(0, contasReceberCrediario);
  const ativoCirculante = caixaFisico + caixaVirtual + valorEstoque + contasReceberCrediario + contasReceberCartao;

  return { caixaFisico, caixaVirtual, valorEstoque, contasReceberCrediario, contasReceberCartao, ativoCirculante };
}

/**
 * Soma quanto de dívida (Boleto + Empréstimo) foi efetivamente PAGO no ano atual,
 * pela data de vencimento de cada parcela — só informativo, pro Balancete.
 */
function calcularDividaPagaNoAno() {
  const anoAtual = new Date().getFullYear();
  let totalPago = 0;
  try {
    const ssSaidas = SpreadsheetApp.openById(ID_PLANILHA_SAIDAS_MKP);
    const sheetSaidas = ssSaidas.getSheets()[0];
    const lastRow = sheetSaidas.getLastRow();
    if (lastRow >= 7) {
      const dados = sheetSaidas.getRange(7, 1, lastRow - 6, 10).getValues();
      dados.forEach(row => {
        const categoriaNorm = String(row[2] || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase().trim();
        const status = String(row[7] || "").toUpperCase().trim();
        const vencimento = row[6];
        const valor = parseFloat(row[4]) || 0;

        if (status !== "PAGO") return;
        if (categoriaNorm !== "BOLETO" && categoriaNorm !== "EMPRESTIMO") return;

        let dtObj = vencimento instanceof Date ? vencimento : null;
        if (!dtObj && typeof vencimento === 'string' && vencimento.includes('/')) {
          const p = vencimento.split('/');
          if (p.length === 3) dtObj = new Date(p[2], p[1] - 1, p[0]);
        }
        if (dtObj && dtObj.getFullYear() === anoAtual) totalPago += valor;
      });
    }
  } catch (e) {
    Logger.log("Erro ao calcular dívida paga no ano: " + e.message);
  }
  return totalPago;
}

function abrirJanelaBalancete() {
  const html = HtmlService.createHtmlOutput(getHtmlBalancete()).setWidth(560).setHeight(800);
  SpreadsheetApp.getUi().showModalDialog(html, "📋 Balancete");
}

function gerarBalancete() {
  const ativo = calcularAtivoCirculanteAutomatico();
  const totalBens = somarBensFisicos();
  const passivo = calcularPassivoAutomatico();
  const dividaPagaAno = calcularDividaPagaNoAno();
  const bens = obterListaBens();
  const capitalSocial = obterCapitalSocialSalvo();
  const lucrosRetidos = obterLucrosRetidosSalvos();
  const patrimonioLiquido = capitalSocial + lucrosRetidos;
  const saldoReal = calcularSaldoRealCaixaEBanco();

  const bensPorTipo = {};
  bens.forEach(b => { bensPorTipo[b.tipo] = (bensPorTipo[b.tipo] || 0) + b.valor; });

  const ativoTotal = ativo.ativoCirculante + totalBens;
  const passivoTotal = passivo.passivoCirculante + passivo.passivoNaoCirculante;

  return { ativo, totalBens, bensPorTipo, passivo, dividaPagaAno, capitalSocial, lucrosRetidos, patrimonioLiquido, ativoTotal, passivoTotal, saldoReal };
}

function getHtmlBalancete() {
  return `<!DOCTYPE html>
<html>
<head>
  <base target="_top">
  <style>
    * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, sans-serif; }
    body { background: #f8f9fa; margin: 0; padding: 16px; font-size: 12px; color: #333; }
    .titulo { font-size: 16px; font-weight: bold; color: #0f172a; margin-bottom: 12px; }
    .secao { font-size: 12px; font-weight: bold; color: #334155; margin: 14px 0 6px; border-left: 3px solid #0f172a; padding-left: 8px; }
    .linha { display: flex; justify-content: space-between; padding: 5px 4px; border-bottom: 1px solid #f1f5f9; }
    .linha.total { font-weight: bold; background: #f8fafc; border-top: 1px solid #cbd5e1; }
    .btn { width: 100%; padding: 9px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; background: #0f172a; color: white; margin-top: 14px; }
  </style>
</head>
<body>
  <div class="titulo">📋 Balancete</div>
  <div id="subtitulo-data" style="font-size:10px;color:#888;margin-bottom:10px;"></div>
  <div id="corpo">Carregando...</div>

  <div class="secao">PATRIMÔNIO LÍQUIDO</div>
  <div style="font-size:10px;color:#888;margin-bottom:10px;">É o quanto a empresa realmente "vale" pra você, dono — sem contar dívida nenhuma. Se divide em duas partes:</div>

  <label style="font-size:11px;font-weight:bold;color:#334155;">💰 Capital Social</label>
  <div style="font-size:10px;color:#888;margin-bottom:4px;">O dinheiro que VOCÊ colocou do seu bolso pra abrir ou capitalizar a empresa. Não é empréstimo, é seu, investido no negócio.</div>
  <input type="number" step="0.01" id="in-capital" style="width:100%;padding:8px;border-radius:6px;border:1px solid #cbd5e1;font-size:13px;margin-bottom:10px;">

  <label style="font-size:11px;font-weight:bold;color:#334155;">📈 Lucros Retidos / Reservas</label>
  <div style="font-size:10px;color:#888;margin-bottom:4px;">Lucro que a empresa já gerou e ficou guardado dentro dela — dinheiro que você NÃO sacou pra sua conta pessoal, continua "no negócio".</div>
  <input type="number" step="0.01" id="in-lucros" style="width:100%;padding:8px;border-radius:6px;border:1px solid #cbd5e1;font-size:13px;margin-bottom:6px;">

  <div style="font-size:11px;font-weight:bold;text-align:right;margin-bottom:8px;">Patrimônio Líquido Total: <span id="txt-pl-total">R$ 0,00</span></div>

  <button class="btn" onclick="salvarPL()">💾 Salvar Patrimônio Líquido</button>
  <div id="status" style="text-align:center;font-weight:bold;margin-top:8px;"></div>

  <script>
    function fmt(n) { return 'R$ ' + (n || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }

    function carregar() {
      google.script.run.withSuccessHandler(renderizar).withFailureHandler(function(err) {
        document.getElementById('corpo').innerHTML = '<span style="color:#dc3545;">❌ ' + (err.message || err) + '</span>';
      }).gerarBalancete();
    }

    function renderizar(d) {
      let bensHtml = '';
      Object.keys(d.bensPorTipo).forEach(function(tipo) {
        bensHtml += '<div class="linha"><span>&nbsp;&nbsp;' + tipo + '</span><strong>' + fmt(d.bensPorTipo[tipo]) + '</strong></div>';
      });

      const hoje = new Date();
      document.getElementById('subtitulo-data').innerText = 'Balancete em ' + String(hoje.getDate()).padStart(2, '0') + '/' + String(hoje.getMonth() + 1).padStart(2, '0') + '/' + hoje.getFullYear();

      // Agrupa por descrição + categoria (ex: todas as parcelas de "Tio (Empréstimo)" viram 1 linha só),
      // em vez de listar parcela por parcela — mostra quantas parcelas e o intervalo de vencimento.
      function agruparDetalhamento(lista) {
        const grupos = {};
        lista.forEach(function(item) {
          const chave = item.categoria + '|' + item.descricao;
          if (!grupos[chave]) grupos[chave] = { categoria: item.categoria, descricao: item.descricao, valor: 0, qtdParcelas: 0, vencimentos: [] };
          grupos[chave].valor += item.valor;
          grupos[chave].qtdParcelas++;
          grupos[chave].vencimentos.push(item.vencimento);
        });

        return Object.values(grupos).map(function(g) {
          g.vencimentos.sort();
          const parcelasTexto = g.qtdParcelas > 1 ? g.qtdParcelas + ' parcela(s), ' : '';
          const periodoTexto = g.qtdParcelas > 1
            ? 'de ' + g.vencimentos[0] + ' até ' + g.vencimentos[g.vencimentos.length - 1]
            : 'vence ' + g.vencimentos[0];
          return '<div class="linha"><span>&nbsp;&nbsp;' + g.descricao + ' (' + g.categoria + ') — ' + parcelasTexto + periodoTexto + '</span><strong>' + fmt(g.valor) + '</strong></div>';
        }).join('');
      }

      const circulantes = (d.passivo.detalhamento || []).filter(function(item) { return item.prazo === 'Circulante'; });
      const naoCirculantes = (d.passivo.detalhamento || []).filter(function(item) { return item.prazo === 'Não Circulante'; });
      const detalhesCirculante = agruparDetalhamento(circulantes);
      const detalhesNaoCirculante = agruparDetalhamento(naoCirculantes);

      document.getElementById('corpo').innerHTML = \`
        <div class="secao">💰 Dinheiro Real Disponível (recebido − contas pagas)</div>
        <div class="linha"><span>Dinheiro em Caixa (físico, gaveta)</span><strong>\${fmt(d.saldoReal.dinheiroFisico)}</strong></div>
        <div class="linha"><span>Total já recebido no Banco/Virtual (histórico completo)</span><strong>\${fmt(d.saldoReal.totalVirtualRecebido)}</strong></div>
        <div class="linha"><span>(-) Total de Contas Já Pagas (Saídas)</span><strong class="neg" style="color:#dc3545;">-\${fmt(d.saldoReal.totalSaidasPagas)}</strong></div>
        <div class="linha total" style="background:#ecfdf5;color:#047857;"><span>SALDO REAL NO BANCO</span><strong>\${fmt(d.saldoReal.saldoBancoDisponivel)}</strong></div>

        <div class="secao">ATIVO CIRCULANTE</div>
        <div class="linha"><span>Caixa Físico</span><strong>\${fmt(d.ativo.caixaFisico)}</strong></div>
        <div class="linha"><span>Caixa Virtual (cartão/PIX)</span><strong>\${fmt(d.ativo.caixaVirtual)}</strong></div>
        <div class="linha"><span>Mercadoria (Estoque)</span><strong>\${fmt(d.ativo.valorEstoque)}</strong></div>
        <div class="linha"><span>Contas a Receber (Crediário)</span><strong>\${fmt(d.ativo.contasReceberCrediario)}</strong></div>
        <div class="linha"><span>Contas a Receber (Cartão a Cair)</span><strong>\${fmt(d.ativo.contasReceberCartao)}</strong></div>
        <div class="linha total"><span>TOTAL ATIVO CIRCULANTE</span><strong>\${fmt(d.ativo.ativoCirculante)}</strong></div>

        <div class="secao">ATIVO NÃO CIRCULANTE (Bens Físicos)</div>
        \${bensHtml || '<div class="linha"><span>Nenhum bem cadastrado</span><strong>R$ 0,00</strong></div>'}
        <div class="linha total"><span>TOTAL BENS FÍSICOS</span><strong>\${fmt(d.totalBens)}</strong></div>

        <div class="linha total" style="background:#0f172a;color:#fff;margin-top:6px;"><span>ATIVO TOTAL</span><strong>\${fmt(d.ativoTotal)}</strong></div>

        <div class="secao">PASSIVO (Circulante — vence dentro de 1 ano)</div>
        \${detalhesCirculante || '<div class="linha"><span>Nenhuma pendência circulante</span><strong>R$ 0,00</strong></div>'}
        <div class="linha total"><span>Subtotal Circulante</span><strong>\${fmt(d.passivo.passivoCirculante)}</strong></div>

        <div class="secao">PASSIVO (Não Circulante — vence depois de 1 ano)</div>
        \${detalhesNaoCirculante || '<div class="linha"><span>Nenhuma pendência de longo prazo</span><strong>R$ 0,00</strong></div>'}
        <div class="linha total"><span>Subtotal Não Circulante</span><strong>\${fmt(d.passivo.passivoNaoCirculante)}</strong></div>

        <div class="linha total" style="background:#0f172a;color:#fff;"><span>PASSIVO TOTAL</span><strong>\${fmt(d.passivoTotal)}</strong></div>

        <div class="secao">INFORMATIVO</div>
        <div class="linha"><span>Dívida Paga no Ano (Boleto + Empréstimo)</span><strong>\${fmt(d.dividaPagaAno)}</strong></div>
        <div class="linha"><span>Ativo Total − Passivo Total (referência pro Patrimônio)</span><strong>\${fmt(d.ativoTotal - d.passivoTotal)}</strong></div>
      \`;

      document.getElementById('in-capital').value = d.capitalSocial.toFixed(2);
      document.getElementById('in-lucros').value = d.lucrosRetidos.toFixed(2);
      document.getElementById('txt-pl-total').innerText = fmt(d.patrimonioLiquido);
      atualizarTotalPL();
    }

    function atualizarTotalPL() {
      const capital = parseFloat(document.getElementById('in-capital').value) || 0;
      const lucros = parseFloat(document.getElementById('in-lucros').value) || 0;
      document.getElementById('txt-pl-total').innerText = fmt(capital + lucros);
    }

    document.addEventListener('DOMContentLoaded', function() {
      document.getElementById('in-capital').addEventListener('input', atualizarTotalPL);
      document.getElementById('in-lucros').addEventListener('input', atualizarTotalPL);
    });

    function salvarPL() {
      const st = document.getElementById('status');
      st.style.color = '#007bff';
      st.innerText = '⏳ Salvando...';
      google.script.run.withSuccessHandler(function(res) {
        st.style.color = res.sucesso ? '#107c41' : '#dc3545';
        st.innerText = res.mensagem;
      }).withFailureHandler(function(err) {
        st.style.color = '#dc3545';
        st.innerText = '❌ Erro: ' + (err.message || err);
      }).salvarPatrimonioLiquido(document.getElementById('in-capital').value, document.getElementById('in-lucros').value);
    }

    window.onload = carregar;
  </script>
</body>
</html>`;
}


// ============================================================================
// MÓDULO: COMPARADOR DE INVESTIMENTO (BOVA11, Dólar, CDI, Poupança, CDB, 10% a.a.)
// ============================================================================

const NOME_ABA_COMPARADOR = "Comparador";


/**
 * Cria (se não existir) uma aba auxiliar com fórmulas GOOGLEFINANCE — o Apps Script não
 * calcula GOOGLEFINANCE sozinho, precisa de uma célula de planilha pra isso.
 */
function garantirAbaComparador() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(NOME_ABA_COMPARADOR);
  if (!sheet) sheet = ss.insertSheet(NOME_ABA_COMPARADOR);

  if (sheet.getRange("A1").getValue() !== "BOVA11 Atual") {
    sheet.getRange("A1").setValue("BOVA11 Atual");
    sheet.getRange("B1").setFormula('=GOOGLEFINANCE("BVMF:BOVA11")');
    sheet.getRange("A2").setValue("BOVA11 há 1 ano");
    sheet.getRange("B2").setFormula('=INDEX(GOOGLEFINANCE("BVMF:BOVA11","close",TODAY()-370,TODAY()-355),2,2)');
    sheet.getRange("A3").setValue("Dólar Atual (USD/BRL)");
    sheet.getRange("B3").setFormula('=GOOGLEFINANCE("CURRENCY:USDBRL")');
    sheet.getRange("A4").setValue("Dólar há 1 ano");
    sheet.getRange("B4").setFormula('=INDEX(GOOGLEFINANCE("CURRENCY:USDBRL","close",TODAY()-370,TODAY()-355),2,2)');
    sheet.hideSheet();
  }
}

/**
 * Tenta buscar o CDI acumulado dos últimos 12 meses direto do Banco Central (API pública,
 * série 4391 = CDI mensal). Se falhar por qualquer motivo, devolve null — o Comparador
 * então usa o valor manual configurado.
 */
function obterCDIAnualAutomatico() {
  try {
    const url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.4391/dados/ultimos/12?formato=json";
    const resp = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
    if (resp.getResponseCode() !== 200) return null;

    const dados = JSON.parse(resp.getContentText());
    if (!dados || !dados.length) return null;

    let fator = 1;
    dados.forEach(item => {
      const taxaMes = parseFloat(String(item.valor).replace(',', '.')) / 100;
      fator *= (1 + taxaMes);
    });
    return fator - 1; // CDI acumulado nos últimos 12 meses
  } catch (e) {
    Logger.log("Erro ao buscar CDI no Banco Central: " + e.message);
    return null;
  }
}

/**
 * ============================================================================
 * EVOLUÇÃO EM "COTAS" — simula a empresa como se fosse um fundo, indexando a
 * receita mensal (base 100 no primeiro mês com dados) e compara lado a lado
 * com BOVA11, CDI e Dólar no MESMO período, mês a mês, pra plotar num gráfico.
 * ============================================================================
 */

/**
 * Lista todos os "ano-mês" (ex: "2025-03") que têm pelo menos uma venda no Histórico.
 */
function obterMesesComVendas() {
  const meses = new Set();
  const anoAtual = new Date().getFullYear();
  try {
    const ssHist = SpreadsheetApp.openById(ID_PLANILHA_HISTORICO_MKP);
    const sheetHist = ssHist.getSheets()[0];
    const lastRow = sheetHist.getLastRow();
    if (lastRow >= 2) {
      const datas = sheetHist.getRange(2, 1, lastRow - 1, 1).getValues();
      datas.forEach(row => {
        const dtObj = row[0] instanceof Date ? row[0] : parseDataBrGenerica(row[0]);
        if (!dtObj) return;
        const ano = dtObj.getFullYear();
        // ⚠️ Blindagem: ignora datas absurdas (linha de teste corrompida, ex: ano "99" virando 1999),
        // pra uma linha ruim não esticar o gráfico inteiro pra décadas atrás sem sentido.
        if (ano < anoAtual - 10 || ano > anoAtual + 1) return;
        meses.add(ano + "-" + String(dtObj.getMonth() + 1).padStart(2, "0"));
      });
    }
  } catch (e) {
    Logger.log("Erro ao listar meses com vendas: " + e.message);
  }
  return Array.from(meses).sort();
}

/**
 * Soma a receita bruta de vendas de UM mês específico (ex: "2025-03").
 */
function obterReceitaDoMesEspecifico(anoMesStr) {
  const [ano, mes] = anoMesStr.split("-").map(Number);
  let receita = 0;
  try {
    const ssHist = SpreadsheetApp.openById(ID_PLANILHA_HISTORICO_MKP);
    const sheetHist = ssHist.getSheets()[0];
    const lastRow = sheetHist.getLastRow();
    if (lastRow >= 2) {
      const dados = sheetHist.getRange(2, 1, lastRow - 1, 13).getValues();
      dados.forEach(row => {
        const dtObj = row[0] instanceof Date ? row[0] : parseDataBrGenerica(row[0]);
        if (!dtObj || dtObj.getFullYear() !== ano || (dtObj.getMonth() + 1) !== mes) return;
        if (String(row[5] || "") === "CREDIARIO") return;
        receita += parseFloat(row[6]) || 0;
      });
    }
  } catch (e) {
    Logger.log("Erro ao calcular receita do mês " + anoMesStr + ": " + e.message);
  }
  return receita;
}

/**
 * Escreve na aba auxiliar as fórmulas GOOGLEFINANCE de fechamento MENSAL de BOVA11 e
 * Dólar, cobrindo do primeiro ao último mês informado.
 */
function garantirEvolucaoMensalMercado(primeiroMesStr, ultimoMesStr) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(NOME_ABA_COMPARADOR) || ss.insertSheet(NOME_ABA_COMPARADOR);

  const [anoI, mesI] = primeiroMesStr.split("-").map(Number);
  const [anoF, mesF] = ultimoMesStr.split("-").map(Number);

  sheet.getRange("D1").setValue("Evolução Mensal BOVA11 (não mexer)");
  sheet.getRange("D2").setFormula(`=GOOGLEFINANCE("BVMF:BOVA11","close",DATE(${anoI},${mesI},1),DATE(${anoF},${mesF},28),"MONTHLY")`);
  sheet.getRange("G1").setValue("Evolução Mensal Dólar (não mexer)");
  sheet.getRange("G2").setFormula(`=GOOGLEFINANCE("CURRENCY:USDBRL","close",DATE(${anoI},${mesI},1),DATE(${anoF},${mesF},28),"MONTHLY")`);
}

/**
 * Busca o CDI mês a mês (Banco Central) pros últimos N meses.
 */
function obterCDIMensal(qtdMeses) {
  try {
    const url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.4391/dados/ultimos/" + qtdMeses + "?formato=json";
    const resp = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
    if (resp.getResponseCode() !== 200) return null;
    const dados = JSON.parse(resp.getContentText());
    if (!dados || !dados.length) return null;
    return dados.map(item => parseFloat(String(item.valor).replace(',', '.')) / 100);
  } catch (e) {
    Logger.log("Erro ao buscar CDI mensal: " + e.message);
    return null;
  }
}

/**
 * Monta a série completa (Empresa, BOVA11, CDI, Dólar), todas indexadas a 100 no
 * primeiro mês com dados, prontas pra virar um gráfico de linha.
 */
function gerarEvolucaoComparativa() {
  const meses = obterMesesComVendas();
  if (meses.length < 2) {
    return { erro: "Precisa de pelo menos 2 meses com vendas no Histórico pra montar esse gráfico." };
  }

  // Limita aos últimos 24 meses, pra não pesar demais o GOOGLEFINANCE.
  const mesesUsados = meses.length > 24 ? meses.slice(meses.length - 24) : meses;
  const primeiroMes = mesesUsados[0], ultimoMes = mesesUsados[mesesUsados.length - 1];

  // 1. Receita da empresa, mês a mês, indexada a 100 no primeiro mês
  const receitasMensais = mesesUsados.map(m => obterReceitaDoMesEspecifico(m));
  const baseReceita = receitasMensais[0] || 1;
  const empresaIndexada = receitasMensais.map(r => (r / baseReceita) * 100);

  // 2. BOVA11 e Dólar, mês a mês, via GOOGLEFINANCE
  garantirEvolucaoMensalMercado(primeiroMes, ultimoMes);
  SpreadsheetApp.flush();

  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(NOME_ABA_COMPARADOR);
  const bovaBruto = sheet.getRange(2, 4, mesesUsados.length + 3, 2).getValues().filter(r => r[0] instanceof Date);
  const dolarBruto = sheet.getRange(2, 7, mesesUsados.length + 3, 2).getValues().filter(r => r[0] instanceof Date);

  const bovaValores = bovaBruto.map(r => r[1]);
  const dolarValores = dolarBruto.map(r => r[1]);

  const bovaBase = bovaValores[0] || 1;
  const dolarBase = dolarValores[0] || 1;
  const bovaIndexado = bovaValores.map(v => (v / bovaBase) * 100);
  const dolarIndexado = dolarValores.map(v => (v / dolarBase) * 100);

  // 3. CDI, mês a mês, composto (indexado a 100 no primeiro mês)
  const cdiMensal = obterCDIMensal(mesesUsados.length);
  let cdiIndexado = [];
  if (cdiMensal) {
    let acumulado = 100;
    cdiIndexado.push(acumulado);
    for (let i = 1; i < mesesUsados.length; i++) {
      acumulado *= (1 + (cdiMensal[i] || 0));
      cdiIndexado.push(acumulado);
    }
  }

  const labels = mesesUsados.map(m => {
    const [ano, mes] = m.split("-");
    const nomes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
    return nomes[parseInt(mes, 10) - 1] + "/" + ano.slice(2);
  });

  return {
    labels,
    empresa: empresaIndexada,
    bova: bovaIndexado.length === labels.length ? bovaIndexado : [],
    dolar: dolarIndexado.length === labels.length ? dolarIndexado : [],
    cdi: cdiIndexado.length === labels.length ? cdiIndexado : []
  };
}

function obterConfigComparador() {
  const props = PropertiesService.getDocumentProperties();
  return {
    cdiManual: parseFloat(props.getProperty('CDI_MANUAL')) || 10.5,
    poupancaAnual: parseFloat(props.getProperty('POUPANCA_ANUAL')) || 6.17,
    investSimplesAnual: parseFloat(props.getProperty('INVEST_SIMPLES_ANUAL')) || 10,
    cdbPercCDI: parseFloat(props.getProperty('CDB_PERC_CDI')) || 100
  };
}

function salvarConfigComparador(cdiManual, poupancaAnual, investSimplesAnual, cdbPercCDI) {
  try {
    const props = PropertiesService.getDocumentProperties();
    props.setProperty('CDI_MANUAL', String(parseFloat(cdiManual) || 0));
    props.setProperty('POUPANCA_ANUAL', String(parseFloat(poupancaAnual) || 0));
    props.setProperty('INVEST_SIMPLES_ANUAL', String(parseFloat(investSimplesAnual) || 0));
    props.setProperty('CDB_PERC_CDI', String(parseFloat(cdbPercCDI) || 0));
    return { sucesso: true, mensagem: "✅ Configuração salva!" };
  } catch (e) {
    return { sucesso: false, mensagem: "❌ Erro: " + e.message };
  }
}

/**
 * Liga/desliga uma das 4 opções de renda fixa (cdi, poupanca, simples, cdb) na
 * comparação — clicar no cartão desativa ele (fica de fora do "melhor opção" e
 * da sugestão), clicar de novo reativa.
 */
function obterRendaFixaAtivos() {
  const props = PropertiesService.getDocumentProperties();
  const salvo = props.getProperty('RENDA_FIXA_DESATIVADOS');
  const desativados = salvo ? JSON.parse(salvo) : [];
  return { cdi: !desativados.includes('cdi'), poupanca: !desativados.includes('poupanca'), simples: !desativados.includes('simples'), cdb: !desativados.includes('cdb') };
}

function alternarRendaFixa(chave) {
  try {
    const props = PropertiesService.getDocumentProperties();
    const salvo = props.getProperty('RENDA_FIXA_DESATIVADOS');
    let desativados = salvo ? JSON.parse(salvo) : [];

    if (desativados.includes(chave)) desativados = desativados.filter(c => c !== chave);
    else desativados.push(chave);

    props.setProperty('RENDA_FIXA_DESATIVADOS', JSON.stringify(desativados));
    return { sucesso: true, ativos: obterRendaFixaAtivos() };
  } catch (e) {
    return { sucesso: false, mensagem: "❌ Erro: " + e.message };
  }
}

/**
 * Monta a comparação completa: crescimento da empresa (CAGR de Receita, já calculado nos
 * Indicadores) contra BOVA11, Dólar, CDI, Poupança, CDB e um investimento simples fixo.
 */
function gerarComparadorInvestimento(crescimentoEmpresa) {
  garantirAbaComparador();
  SpreadsheetApp.flush(); // força o Google Sheets a calcular as fórmulas GOOGLEFINANCE antes de ler

  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(NOME_ABA_COMPARADOR);
  const bovaAtual = parseFloat(sheet.getRange("B1").getValue()) || 0;
  const bovaAno = parseFloat(sheet.getRange("B2").getValue()) || 0;
  const dolarAtual = parseFloat(sheet.getRange("B3").getValue()) || 0;
  const dolarAno = parseFloat(sheet.getRange("B4").getValue()) || 0;

  const crescimentoBova = bovaAno > 0 ? (bovaAtual / bovaAno - 1) : null;
  const crescimentoDolar = dolarAno > 0 ? (dolarAtual / dolarAno - 1) : null;

  const cfg = obterConfigComparador();
  const cdiAuto = obterCDIAnualAutomatico();
  const cdiUsado = cdiAuto !== null ? cdiAuto : (cfg.cdiManual / 100);
  const cdiFonte = cdiAuto !== null ? "Banco Central (automático)" : "Configurado manualmente";

  const poupanca = cfg.poupancaAnual / 100;
  const investSimples = cfg.investSimplesAnual / 100;
  const cdb = cdiUsado * (cfg.cdbPercCDI / 100);

  // Sugestão: compara o crescimento da empresa com a melhor opção de renda fixa ATIVA
  // (as que você desligou clicando no cartão ficam de fora dessa conta).
  const ativos = obterRendaFixaAtivos();
  const opcoesAtivas = [];
  if (ativos.cdi) opcoesAtivas.push(cdiUsado);
  if (ativos.poupanca) opcoesAtivas.push(poupanca);
  if (ativos.simples) opcoesAtivas.push(investSimples);
  if (ativos.cdb) opcoesAtivas.push(cdb);
  const melhorRendaFixa = opcoesAtivas.length > 0 ? Math.max(...opcoesAtivas) : Math.max(cdiUsado, poupanca, investSimples, cdb);

  let sugestao;
  if (crescimentoEmpresa === null) {
    sugestao = "Ainda não dá pra comparar — falta ter pelo menos 2 anos de vendas registradas no Histórico pra calcular o crescimento da empresa.";
  } else if (crescimentoEmpresa > melhorRendaFixa) {
    sugestao = "O crescimento da sua empresa (" + (crescimentoEmpresa * 100).toFixed(1).replace('.', ',') + "% ao ano) está MAIOR que a melhor opção de renda fixa ativa (" + (melhorRendaFixa * 100).toFixed(1).replace('.', ',') + "%). Faz mais sentido reinvestir o lucro dentro do negócio do que tirar pra aplicar fora.";
  } else {
    sugestao = "O crescimento da sua empresa (" + (crescimentoEmpresa * 100).toFixed(1).replace('.', ',') + "% ao ano) está MENOR que a melhor opção de renda fixa ativa (" + (melhorRendaFixa * 100).toFixed(1).replace('.', ',') + "%). Pode valer mais a pena proteger parte do capital numa aplicação de renda fixa do que reinvestir tudo no negócio agora.";
  }

  return {
    crescimentoEmpresa, crescimentoBova, crescimentoDolar,
    cdiUsado, cdiFonte, poupanca, investSimples, cdb,
    cfg, sugestao, ativos
  };
}


// ============================================================================
// MÓDULO: CURVA ABC — classifica os produtos por quanto cada um representa da receita
// ============================================================================

function abrirJanelaCurvaABC() {
  const html = HtmlService.createHtmlOutput(getHtmlCurvaABC()).setWidth(760).setHeight(760);
  SpreadsheetApp.getUi().showModalDialog(html, "📊 Curva ABC de Produtos");
}

/**
 * Soma a receita bruta de cada produto (por ID), olhando Histórico + Caixa aberto,
 * ordena do maior pro menor, calcula o % acumulado e classifica em A/B/C.
 *
 * Classe A = produtos que, somados, chegam a 80% da receita (os mais importantes).
 * Classe B = os próximos até 95%.
 * Classe C = o resto até 100% (geralmente muitos produtos, pouca contribuição cada).
 */
function gerarCurvaABC(mes, ano) {
  const receitaPorProduto = {}; // { id: { desc, categoria, receita, qtd } }

  function dentroDoPeriodo(dtObj) {
    if (!dtObj) return true;
    const m = dtObj.getMonth() + 1, a = dtObj.getFullYear();
    if (mes && mes !== "TODOS" && parseInt(mes) !== m) return false;
    if (ano && ano !== "TODOS" && parseInt(ano) !== a) return false;
    return true;
  }

  // 1. Histórico (caixas já fechados)
  try {
    const ssHist = SpreadsheetApp.openById(ID_PLANILHA_HISTORICO_MKP);
    const sheetHist = ssHist.getSheets()[0];
    const lastRow = sheetHist.getLastRow();
    if (lastRow >= 2) {
      const dados = sheetHist.getRange(2, 1, lastRow - 1, 13).getValues();
      dados.forEach(row => {
        const dtObj = row[0] instanceof Date ? row[0] : parseDataBrGenerica(row[0]);
        if (!dentroDoPeriodo(dtObj)) return;

        const categoria = String(row[5] || "");
        if (categoria === "CREDIARIO" || categoria === "Assinatura") return; // não é venda de produto físico

        const id = String(row[3] || "").trim();
        const desc = String(row[4] || "").trim();
        const valor = parseFloat(row[6]) || 0;
        const qtd = parseFloat(row[7]) || 0;
        if (!desc) return;

        const chave = id || desc;
        if (!receitaPorProduto[chave]) receitaPorProduto[chave] = { desc, categoria: String(row[5] || ""), receita: 0, qtd: 0 };
        receitaPorProduto[chave].receita += valor;
        receitaPorProduto[chave].qtd += qtd;
      });
    }
  } catch (e) {
    Logger.log("Erro ao ler Histórico na Curva ABC: " + e.message);
  }

  // 2. Caixa aberto no momento
  try {
    const ssCaixa = SpreadsheetApp.openById(ID_PLANILHA_CAIXA_MKP);
    const sheetCaixa = ssCaixa.getSheetByName("CAIXA") || ssCaixa.getSheets()[0];
    const lastRow = sheetCaixa.getLastRow();
    if (lastRow >= 7) {
      const dados = sheetCaixa.getRange(7, 1, lastRow - 6, sheetCaixa.getLastColumn()).getValues();
      dados.forEach(row => {
        const desc = String(row[2] || "").trim();
        if (desc === "" || desc.includes("RECEBIMENTO DE CONTA")) return;

        const categoriaNorm = String(row[3] || "");
        if (categoriaNorm === "Assinatura") return;

        const dtObj = row[10] instanceof Date ? row[10] : parseDataBrGenerica(row[10]);
        if (!dentroDoPeriodo(dtObj)) return;

        const id = String(row[1] || "").trim();
        const valor = parseFloat(row[4]) || 0;
        const qtd = parseFloat(row[5]) || 0;

        const chave = id || desc;
        if (!receitaPorProduto[chave]) receitaPorProduto[chave] = { desc, categoria: categoriaNorm, receita: 0, qtd: 0 };
        receitaPorProduto[chave].receita += valor;
        receitaPorProduto[chave].qtd += qtd;
      });
    }
  } catch (e) {
    Logger.log("Erro ao ler Caixa aberto na Curva ABC: " + e.message);
  }

  const lista = Object.values(receitaPorProduto).sort((a, b) => b.receita - a.receita);
  const receitaTotal = lista.reduce((soma, p) => soma + p.receita, 0);

  if (lista.length === 0 || receitaTotal === 0) {
    return { erro: "Nenhuma venda de produto encontrada nesse período." };
  }

  let acumulado = 0;
  const resultado = lista.map(p => {
    acumulado += p.receita;
    const pctAcumulado = acumulado / receitaTotal;
    let classe;
    if (pctAcumulado <= 0.80) classe = "A";
    else if (pctAcumulado <= 0.95) classe = "B";
    else classe = "C";

    return {
      desc: p.desc, categoria: p.categoria, qtd: p.qtd,
      receita: p.receita,
      pctReceita: p.receita / receitaTotal,
      pctAcumulado, classe
    };
  });

  const resumo = { A: { qtd: 0, receita: 0 }, B: { qtd: 0, receita: 0 }, C: { qtd: 0, receita: 0 } };
  resultado.forEach(p => { resumo[p.classe].qtd++; resumo[p.classe].receita += p.receita; });

  return { produtos: resultado, receitaTotal, resumo, totalProdutos: resultado.length };
}

function getHtmlCurvaABC() {
  return `<!DOCTYPE html>
<html>
<head>
  <base target="_top">
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, sans-serif; }
    body { background: #f8f9fa; margin: 0; padding: 16px; font-size: 12px; color: #333; }
    .titulo { font-size: 16px; font-weight: bold; color: #0f172a; margin-bottom: 10px; display: flex; align-items: center; justify-content: space-between; }
    .filtros select { padding: 6px 10px; border-radius: 6px; border: 1px solid #cbd5e1; font-size: 11px; margin-left: 6px; }
    .resumo-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 14px; }
    .card-classe { border-radius: 8px; padding: 10px; text-align: center; color: #fff; }
    .card-classe .letra { font-size: 20px; font-weight: bold; }
    .card-classe .info { font-size: 10px; opacity: 0.9; margin-top: 2px; }
    .classeA { background: #16a34a; }
    .classeB { background: #d97706; }
    .classeC { background: #64748b; }
    table { width: 100%; border-collapse: collapse; font-size: 11px; }
    th { text-align: left; padding: 6px 8px; background: #f1f5f9; position: sticky; top: 0; font-size: 10px; text-transform: uppercase; color: #475569; }
    td { padding: 6px 8px; border-bottom: 1px solid #f1f5f9; }
    .tabela-scroll { max-height: 320px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 8px; }
    .badge { padding: 2px 8px; border-radius: 10px; font-weight: bold; font-size: 10px; color: #fff; }
    .badgeA { background: #16a34a; } .badgeB { background: #d97706; } .badgeC { background: #64748b; }
    .chart-box { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; margin: 14px 0; }
    .chart-container { position: relative; height: 200px; width: 100%; }
  </style>
</head>
<body>
  <div class="titulo">
    <span>📊 Curva ABC de Produtos</span>
    <div class="filtros">
      <select id="filtroMes" onchange="carregar()">
        <option value="TODOS">Todos os Meses</option>
        <option value="1">Jan</option><option value="2">Fev</option><option value="3">Mar</option>
        <option value="4">Abr</option><option value="5">Mai</option><option value="6">Jun</option>
        <option value="7">Jul</option><option value="8">Ago</option><option value="9">Set</option>
        <option value="10">Out</option><option value="11">Nov</option><option value="12">Dez</option>
      </select>
      <select id="filtroAno" onchange="carregar()">
        <option value="TODOS">Todos os Anos</option>
        <option>2024</option><option>2025</option><option selected>2026</option><option>2027</option>
      </select>
    </div>
  </div>

  <div id="corpo">Carregando...</div>

  <script>
    function fmtR(n) { return 'R$ ' + (n || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
    function fmtP(n) { return ((n || 0) * 100).toFixed(1).replace('.', ',') + '%'; }
    var chartABCObj = null;

    function carregar() {
      const mes = document.getElementById('filtroMes').value;
      const ano = document.getElementById('filtroAno').value;
      document.getElementById('corpo').innerHTML = 'Calculando...';

      google.script.run.withSuccessHandler(renderizar).withFailureHandler(function(err) {
        document.getElementById('corpo').innerHTML = '<span style="color:#dc3545;">❌ Erro: ' + (err.message || err) + '</span>';
      }).gerarCurvaABC(mes, ano);
    }

    function renderizar(d) {
      if (d.erro) {
        document.getElementById('corpo').innerHTML = '<div style="color:#888;padding:20px;text-align:center;">⚠️ ' + d.erro + '</div>';
        return;
      }

      let linhas = '';
      d.produtos.forEach(function(p) {
        linhas += '<tr>' +
          '<td>' + p.desc + '</td>' +
          '<td>' + p.qtd + '</td>' +
          '<td>' + fmtR(p.receita) + '</td>' +
          '<td>' + fmtP(p.pctReceita) + '</td>' +
          '<td>' + fmtP(p.pctAcumulado) + '</td>' +
          '<td><span class="badge badge' + p.classe + '">' + p.classe + '</span></td>' +
          '</tr>';
      });

      document.getElementById('corpo').innerHTML = \`
        <div class="resumo-grid">
          <div class="card-classe classeA">
            <div class="letra">A</div>
            <div class="info">\${d.resumo.A.qtd} produto(s)</div>
            <div class="info">\${fmtR(d.resumo.A.receita)} (\${fmtP(d.resumo.A.receita / d.receitaTotal)})</div>
          </div>
          <div class="card-classe classeB">
            <div class="letra">B</div>
            <div class="info">\${d.resumo.B.qtd} produto(s)</div>
            <div class="info">\${fmtR(d.resumo.B.receita)} (\${fmtP(d.resumo.B.receita / d.receitaTotal)})</div>
          </div>
          <div class="card-classe classeC">
            <div class="letra">C</div>
            <div class="info">\${d.resumo.C.qtd} produto(s)</div>
            <div class="info">\${fmtR(d.resumo.C.receita)} (\${fmtP(d.resumo.C.receita / d.receitaTotal)})</div>
          </div>
        </div>

        <div class="chart-box">
          <div style="font-size:11px;font-weight:bold;color:#334155;margin-bottom:6px;">Distribuição da Receita por Classe</div>
          <div class="chart-container"><canvas id="chartABC"></canvas></div>
        </div>

        <div class="tabela-scroll">
          <table>
            <thead><tr><th>Produto</th><th>Qtd Vendida</th><th>Receita</th><th>% da Receita</th><th>% Acumulado</th><th>Classe</th></tr></thead>
            <tbody>\${linhas}</tbody>
          </table>
        </div>
      \`;

      if (chartABCObj) chartABCObj.destroy();
      chartABCObj = new Chart(document.getElementById('chartABC').getContext('2d'), {
        type: 'doughnut',
        data: {
          labels: ['Classe A', 'Classe B', 'Classe C'],
          datasets: [{ data: [d.resumo.A.receita, d.resumo.B.receita, d.resumo.C.receita], backgroundColor: ['#16a34a', '#d97706', '#64748b'] }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { boxWidth: 10, font: { size: 10 } } } } }
      });
    }

    window.onload = carregar;
  </script>
</body>
</html>`;
}


// ============================================================================
// SALDO REAL DE CAIXA E BANCO — líquido de verdade: dinheiro recebido menos contas pagas
// ============================================================================

/**
 * Calcula quanto dinheiro você REALMENTE tem disponível: soma tudo que já caiu de
 * verdade (histórico completo de vendas virtuais + caixa aberto) e desconta TODAS as
 * contas já pagas na Saídas (boletos, salários, etc.) — porque pagar uma conta reduz
 * o dinheiro disponível de verdade, mesmo que o sistema de vendas não "saiba" disso.
 */
function calcularSaldoRealCaixaEBanco() {
  const hoje = new Date(); hoje.setHours(0, 0, 0, 0);
  let totalVirtualRecebidoHistorico = 0;

  try {
    const ssHist = SpreadsheetApp.openById(ID_PLANILHA_HISTORICO_MKP);
    const sheetHist = ssHist.getSheets()[0];
    const lastRow = sheetHist.getLastRow();
    if (lastRow >= 2) {
      const dados = sheetHist.getRange(2, 1, lastRow - 1, 13).getValues();
      dados.forEach(row => {
        const pagamentoNorm = String(row[8] || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase();
        if (!["CREDITO", "DEBITO", "PIX", "EXTERNA"].includes(pagamentoNorm)) return;

        const diasRaw = row[9];
        if (String(diasRaw).trim().toUpperCase() === "FUTURO") return; // parcela de contrato ainda não realizada

        const valorLiquido = parseFloat(row[11]) || parseFloat(row[6]) || 0;
        const dtObj = row[0] instanceof Date ? row[0] : parseDataBrGenerica(row[0]);
        const diasNum = parseInt(diasRaw, 10) || 0;

        if (dtObj) {
          const dataQueCai = new Date(dtObj.getTime());
          dataQueCai.setDate(dataQueCai.getDate() + diasNum);
          dataQueCai.setHours(0, 0, 0, 0);
          if (dataQueCai <= hoje) totalVirtualRecebidoHistorico += valorLiquido;
        } else {
          totalVirtualRecebidoHistorico += valorLiquido;
        }
      });
    }
  } catch (e) {
    Logger.log("Erro ao calcular virtual recebido histórico: " + e.message);
  }

  let dinheiroFisico = 0, caixaVirtualAberto = 0;
  try {
    const ssCaixa = SpreadsheetApp.openById(ID_PLANILHA_CAIXA_MKP);
    const sheetCaixa = ssCaixa.getSheetByName("CAIXA") || ssCaixa.getSheets()[0];
    dinheiroFisico = parseFloat(sheetCaixa.getRange("F2").getValue()) || 0;
    caixaVirtualAberto = parseFloat(sheetCaixa.getRange("J2").getValue()) || 0;
  } catch (e) {
    Logger.log("Erro ao ler painel do Caixa: " + e.message);
  }

  let totalSaidasPagas = 0;
  try {
    const ssSaidas = SpreadsheetApp.openById(ID_PLANILHA_SAIDAS_MKP);
    const sheetSaidas = ssSaidas.getSheets()[0];
    const lastRow = sheetSaidas.getLastRow();
    if (lastRow >= 7) {
      const dados = sheetSaidas.getRange(7, 1, lastRow - 6, 10).getValues();
      dados.forEach(row => {
        const status = String(row[7] || "").toUpperCase().trim();
        if (status !== "PAGO") return;
        totalSaidasPagas += parseFloat(row[4]) || 0;
      });
    }
  } catch (e) {
    Logger.log("Erro ao ler Saídas pagas: " + e.message);
  }

  const totalVirtualRecebido = totalVirtualRecebidoHistorico + caixaVirtualAberto;
  const saldoBancoDisponivel = totalVirtualRecebido - totalSaidasPagas;

  return { dinheiroFisico, totalVirtualRecebido, totalSaidasPagas, saldoBancoDisponivel };
}


// ============================================================================
// MÓDULO: CADASTRO DE SERVIÇO / FÓRMULA — vive na aba Markup (colunas S em diante),
// mesmo padrão dos Bens Físicos: bloco de colunas próprio, não interfere com a lista
// de produtos nem com os Bens. Cada serviço ganha um código ("SERV-001", "SERV-002"...)
// compartilhado entre todas as suas linhas de material — é assim que sabemos quais
// materiais pertencem a qual serviço.
// ============================================================================

const COL_INICIO_SERVICOS = 19; // Coluna S

function abrirJanelaServicos() {
  const html = HtmlService.createHtmlOutput(getHtmlServicos()).setWidth(520).setHeight(760);
  SpreadsheetApp.getUi().showModalDialog(html, "🛠️ Serviço / Fórmula");
}

function configurarBlocoServicos() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(NOME_ABA_MARKUP);
  if (!sheet) { SpreadsheetApp.getUi().alert("Rode '⚙️ Configurar Aba Markup' primeiro."); return; }

  sheet.getRange(5, COL_INICIO_SERVICOS, 1, 6).setValues([[
    "CÓDIGO SERVIÇO", "NOME DO SERVIÇO", "MATERIAL", "CUSTO UNIT. (R$)", "QTD", "% MÃO DE OBRA"
  ]]).setFontWeight("bold");
  sheet.setColumnWidth(COL_INICIO_SERVICOS + 1, 180);
  sheet.setColumnWidth(COL_INICIO_SERVICOS + 2, 180);

  SpreadsheetApp.getUi().alert("✅ Bloco de Serviços criado na aba Markup (colunas S em diante)!");
}

function obterProximoCodigoServico() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(NOME_ABA_MARKUP);
  if (!sheet) return "SERV-001";
  const lastRow = sheet.getLastRow();
  if (lastRow < 6) return "SERV-001";

  const codigos = sheet.getRange(6, COL_INICIO_SERVICOS, lastRow - 5, 1).getValues();
  let maiorNumero = 0;
  codigos.forEach(r => {
    const m = String(r[0] || "").match(/SERV-(\d+)/);
    if (m) maiorNumero = Math.max(maiorNumero, parseInt(m[1], 10));
  });
  return "SERV-" + String(maiorNumero + 1).padStart(3, "0");
}

/**
 * Lê todas as linhas de material do bloco de Serviços e agrupa por Código Serviço,
 * calculando o total de materiais, o valor da mão de obra e o preço final de cada um.
 */
function obterListaServicos() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(NOME_ABA_MARKUP);
  if (!sheet) return [];
  const lastRow = sheet.getLastRow();
  if (lastRow < 6) return [];

  const dados = sheet.getRange(6, COL_INICIO_SERVICOS, lastRow - 5, 6).getValues();
  const grupos = {};

  dados.forEach((row, i) => {
    const codigo = String(row[0] || "").trim();
    if (!codigo) return;
    const linha = i + 6;

    if (!grupos[codigo]) {
      grupos[codigo] = { codigo, nome: row[1] || "", percMaoObra: parseFloat(row[5]) || 0, materiais: [], linhas: [] };
    }
    grupos[codigo].materiais.push({
      material: row[2] || "",
      custoUnit: parseFloat(row[3]) || 0,
      qtd: parseFloat(row[4]) || 0
    });
    grupos[codigo].linhas.push(linha);
  });

  return Object.values(grupos).map(s => {
    const totalMateriais = s.materiais.reduce((soma, m) => soma + (m.custoUnit * m.qtd), 0);
    const valorMaoObra = totalMateriais * (s.percMaoObra / 100);
    const precoFinal = totalMateriais + valorMaoObra;
    return { ...s, totalMateriais, valorMaoObra, precoFinal };
  });
}

/**
 * Salva um serviço inteiro (nome + % mão de obra + lista de materiais), escrevendo
 * uma linha por material, todas com o mesmo código de serviço.
 */
function salvarServico(dados) {
  try {
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(NOME_ABA_MARKUP);
    if (!sheet) return { sucesso: false, mensagem: "❌ Rode 'Configurar Aba Markup' primeiro." };

    if (String(sheet.getRange(5, COL_INICIO_SERVICOS).getValue()).trim() === "") {
      sheet.getRange(5, COL_INICIO_SERVICOS, 1, 6).setValues([[
        "CÓDIGO SERVIÇO", "NOME DO SERVIÇO", "MATERIAL", "CUSTO UNIT. (R$)", "QTD", "% MÃO DE OBRA"
      ]]).setFontWeight("bold");
    }

    if (!dados.materiais || dados.materiais.length === 0) {
      return { sucesso: false, mensagem: "⚠️ Adicione pelo menos um material." };
    }

    const codigo = obterProximoCodigoServico();
    const percMaoObra = parseFloat(dados.percMaoObra) || 0;

    dados.materiais.forEach(mat => {
      let linha = 6;
      while (String(sheet.getRange(linha, COL_INICIO_SERVICOS).getValue()).trim() !== "") linha++;

      sheet.getRange(linha, COL_INICIO_SERVICOS, 1, 6).setValues([[
        codigo, dados.nome, mat.desc, parseFloat(mat.custo) || 0, parseFloat(mat.qtd) || 1, percMaoObra
      ]]);
      sheet.getRange(linha, COL_INICIO_SERVICOS + 3).setNumberFormat("R$ #,##0.00");
    });

    return { sucesso: true, mensagem: "✅ Serviço \"" + dados.nome + "\" cadastrado como " + codigo + "!" };
  } catch (e) {
    return { sucesso: false, mensagem: "❌ Erro: " + e.message };
  }
}

function excluirServico(codigo) {
  try {
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(NOME_ABA_MARKUP);
    const lastRow = sheet.getLastRow();
    if (lastRow < 6) return { sucesso: true, mensagem: "Nada pra excluir." };

    const codigos = sheet.getRange(6, COL_INICIO_SERVICOS, lastRow - 5, 1).getValues();
    codigos.forEach((row, i) => {
      if (String(row[0] || "").trim() === codigo) {
        sheet.getRange(i + 6, COL_INICIO_SERVICOS, 1, 6).clearContent();
      }
    });

    return { sucesso: true, mensagem: "✅ Serviço excluído!" };
  } catch (e) {
    return { sucesso: false, mensagem: "❌ Erro: " + e.message };
  }
}

function getHtmlServicos() {
  return `<!DOCTYPE html>
<html>
<head>
  <base target="_top">
  <style>
    * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, sans-serif; }
    body { margin: 0; padding: 16px; font-size: 12px; color: #333; background: #f8f9fa; }
    label { font-weight: bold; font-size: 11px; color: #475569; display: block; margin-bottom: 3px; margin-top: 10px; }
    input { width: 100%; padding: 8px; border-radius: 6px; border: 1px solid #cbd5e1; font-size: 12px; }
    .row3 { display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 6px; align-items: end; }
    .btn { width: 100%; padding: 9px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; }
    .btn-add { background: #0284c7; color: white; margin-top: 6px; }
    .btn-salvar { background: #16a34a; color: white; margin-top: 14px; }
    .box { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; margin-top: 10px; }
    .info-line { display: flex; justify-content: space-between; font-size: 12px; padding: 3px 0; }
    .mat-item { display: flex; justify-content: space-between; align-items: center; padding: 5px 0; border-bottom: 1px solid #f1f5f9; font-size: 11px; }
    .del { color: #dc3545; cursor: pointer; font-weight: bold; }
    #status { text-align: center; font-weight: bold; margin-top: 10px; min-height: 18px; }
    .secao-lista { margin-top: 20px; border-top: 2px solid #cbd5e1; padding-top: 12px; }
    .servico-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; margin-bottom: 8px; }
    .servico-card .nome { font-weight: bold; }
    .servico-card .mat-linha { font-size: 10px; color: #666; }
  </style>
</head>
<body>
  <label>Nome do Serviço:</label>
  <input type="text" id="in-nome">

  <label>% de Mão de Obra (sobre o custo total dos materiais):</label>
  <input type="number" step="0.01" id="in-perc-mo" value="50" oninput="atualizarTotais()">

  <div class="box">
    <div style="font-weight:bold;font-size:11px;margin-bottom:6px;">➕ Adicionar Material</div>
    <div class="row3">
      <div><label>Material</label><input type="text" id="mat-desc"></div>
      <div><label>Custo Unit. (R$)</label><input type="number" step="0.01" id="mat-custo"></div>
      <div><label>Qtd</label><input type="number" step="0.01" id="mat-qtd" value="1"></div>
    </div>
    <button class="btn btn-add" onclick="adicionarMaterial()">➕ Adicionar à Lista</button>
  </div>

  <div id="lista-materiais" style="margin-top:8px;"></div>

  <div class="box">
    <div class="info-line"><span>Total de Materiais:</span><strong id="v-materiais">R$ 0,00</strong></div>
    <div class="info-line"><span>Valor da Mão de Obra:</span><strong id="v-maoobra">R$ 0,00</strong></div>
    <div class="info-line" style="font-size:13px;font-weight:bold;border-top:1px solid #e2e8f0;padding-top:6px;margin-top:4px;"><span>PREÇO FINAL DO SERVIÇO:</span><strong style="color:#16a34a;" id="v-final">R$ 0,00</strong></div>
  </div>

  <button class="btn btn-salvar" onclick="salvarServicoCompleto()">💾 Salvar Serviço</button>
  <div id="status"></div>

  <div class="secao-lista">
    <div style="font-weight:bold;font-size:12px;margin-bottom:8px;">📋 Serviços Já Cadastrados</div>
    <div id="lista-servicos">Carregando...</div>
  </div>

  <script>
    var materiaisAtuais = [];

    function fmt(n) { return 'R$ ' + (n || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }

    function adicionarMaterial() {
      const desc = document.getElementById('mat-desc').value.trim();
      const custo = parseFloat(document.getElementById('mat-custo').value) || 0;
      const qtd = parseFloat(document.getElementById('mat-qtd').value) || 1;

      if (!desc || custo <= 0) {
        document.getElementById('status').style.color = '#dc3545';
        document.getElementById('status').innerText = '⚠️ Preencha o material e o custo.';
        return;
      }

      materiaisAtuais.push({ desc: desc, custo: custo, qtd: qtd });
      document.getElementById('mat-desc').value = '';
      document.getElementById('mat-custo').value = '';
      document.getElementById('mat-qtd').value = '1';
      document.getElementById('status').innerText = '';
      renderizarMateriais();
    }

    function removerMaterial(idx) {
      materiaisAtuais.splice(idx, 1);
      renderizarMateriais();
    }

    function renderizarMateriais() {
      const div = document.getElementById('lista-materiais');
      div.innerHTML = '';
      materiaisAtuais.forEach(function(m, idx) {
        const item = document.createElement('div');
        item.className = 'mat-item';
        item.innerHTML = '<span>' + m.desc + ' — ' + m.qtd + ' x ' + fmt(m.custo) + ' = ' + fmt(m.custo * m.qtd) + '</span><span class="del">🗑️</span>';
        item.querySelector('.del').onclick = function() { removerMaterial(idx); };
        div.appendChild(item);
      });
      atualizarTotais();
    }

    function atualizarTotais() {
      const totalMateriais = materiaisAtuais.reduce(function(s, m) { return s + (m.custo * m.qtd); }, 0);
      const percMO = parseFloat(document.getElementById('in-perc-mo').value) || 0;
      const valorMO = totalMateriais * (percMO / 100);
      document.getElementById('v-materiais').innerText = fmt(totalMateriais);
      document.getElementById('v-maoobra').innerText = fmt(valorMO);
      document.getElementById('v-final').innerText = fmt(totalMateriais + valorMO);
    }

    function salvarServicoCompleto() {
      const nome = document.getElementById('in-nome').value.trim();
      const st = document.getElementById('status');

      if (!nome) { st.style.color = '#dc3545'; st.innerText = '⚠️ Dê um nome pro serviço.'; return; }
      if (materiaisAtuais.length === 0) { st.style.color = '#dc3545'; st.innerText = '⚠️ Adicione pelo menos um material.'; return; }

      st.style.color = '#007bff';
      st.innerText = '⏳ Salvando...';

      google.script.run
        .withSuccessHandler(function(res) {
          st.style.color = res.sucesso ? '#107c41' : '#dc3545';
          st.innerText = res.mensagem;
          if (res.sucesso) {
            document.getElementById('in-nome').value = '';
            materiaisAtuais = [];
            renderizarMateriais();
            carregarServicos();
          }
        })
        .withFailureHandler(function(err) {
          st.style.color = '#dc3545';
          st.innerText = '❌ Erro: ' + (err.message || err);
        })
        .salvarServico({
          nome: nome,
          percMaoObra: document.getElementById('in-perc-mo').value,
          materiais: materiaisAtuais
        });
    }

    function carregarServicos() {
      google.script.run.withSuccessHandler(function(servicos) {
        const div = document.getElementById('lista-servicos');
        div.innerHTML = '';
        if (!servicos || servicos.length === 0) {
          div.innerHTML = '<div style="color:#888;font-size:11px;">Nenhum serviço cadastrado ainda.</div>';
          return;
        }
        servicos.forEach(function(s) {
          const card = document.createElement('div');
          card.className = 'servico-card';
          let matHtml = '';
          s.materiais.forEach(function(m) {
            matHtml += '<div class="mat-linha">• ' + m.material + ' — ' + m.qtd + ' x ' + fmt(m.custoUnit) + '</div>';
          });
          card.innerHTML = '<div style="display:flex;justify-content:space-between;">' +
            '<span class="nome">' + s.codigo + ' — ' + s.nome + '</span>' +
            '<span class="del" style="cursor:pointer;">🗑️</span></div>' +
            matHtml +
            '<div style="font-size:11px;margin-top:4px;">Materiais: ' + fmt(s.totalMateriais) + ' + Mão de obra (' + s.percMaoObra + '%): ' + fmt(s.valorMaoObra) + '</div>' +
            '<div style="font-weight:bold;color:#16a34a;">Preço Final: ' + fmt(s.precoFinal) + '</div>';
          card.querySelector('.del').onclick = function() {
            google.script.run.withSuccessHandler(function() { carregarServicos(); }).excluirServico(s.codigo);
          };
          div.appendChild(card);
        });
      }).obterListaServicos();
    }

    window.onload = carregarServicos;
  </script>
</body>
</html>`;
}