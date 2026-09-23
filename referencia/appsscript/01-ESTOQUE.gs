// ============================================================
// 1. GATILHOS E NAVEGAÇÃO
// ============================================================
function onOpen() { voltarAoTopo(); }
function onEdit(e) { monitorarEntrada(e); }
function voltarAoTopo() { SpreadsheetApp.getActiveSpreadsheet().getActiveSheet().getRange("A1").activate(); }
function abrirMenuExterno() {
  const url = "https://docs.google.com/spreadsheets/d/1QHSqLPHPQla-SwxyBkZl7u0kpauWsy5VxdYZIyBxnIE/edit?gid=0#gid=0";
  const html = `<script>window.onload=()=>window.top.location.href="${url}";</script><p style="font-family:sans-serif;text-align:center;color:#666;">Redirecionando...</p>`;
  SpreadsheetApp.getUi().showModalDialog(HtmlService.createHtmlOutput(html).setWidth(220).setHeight(80), ' ');
}

// ============================================================
// 2. SEGURANÇA E BLOQUEIO DE PLANILHA
// ============================================================
function travarPlanilha() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const protections = sheet.getProtections(SpreadsheetApp.ProtectionType.SHEET);
  protections.forEach(p => p.remove());
  const protection = sheet.protect().setDescription('Planilha Protegida contra Edição Direta');
  const me = Session.getEffectiveUser();
  protection.addEditor(me);
  protection.removeEditors(protection.getEditors().filter(e => e.getEmail() !== me.getEmail()));
  if (protection.canDomainEdit()) protection.setDomainEdit(false);
  SpreadsheetApp.getUi().alert("🔒 PLANILHA TRAVADA!\n\nAs células manuais foram bloqueadas. Utilize os botões para Cadastrar, Editar, Importar ou Excluir produtos.");
}

function destravarPlanilha() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const protections = sheet.getProtections(SpreadsheetApp.ProtectionType.SHEET);
  protections.forEach(p => p.remove());
  SpreadsheetApp.getUi().alert("🔓 PLANILHA DESTRAVADA!\nEdição direta nas células temporariamente liberada.");
}

// ============================================================
// 3. ESTILIZAÇÃO DINÂMICA DE LINHAS
// ============================================================
function aplicarEstiloLinha(sheet, row, temProduto) {
  if (row < 6) return;
  const range = sheet.getRange(row, 1, 1, 13);

  if (temProduto) {
    range.setBorder(true, false, true, false, false, false, "#d9d9d9", SpreadsheetApp.BorderStyle.SOLID);
    const rule = SpreadsheetApp.newDataValidation()
      .requireValueInList(["1-Revenda", "2-Uso/Consumo", "3-Matéria-Prima"], true)
      .setAllowInvalid(false).build();
    sheet.getRange(row, 13).setDataValidation(rule);
  } else {
    range.clearContent().clearFormat().clearDataValidations();
    range.setBorder(false, false, false, false, false, false);
  }
}

// ============================================================
// 4. PESQUISA INTELIGENTE NO BANCO DE DADOS
// ============================================================
function pesquisarProdutosModal(termo) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const lastRow = sheet.getLastRow();
  if (lastRow < 6) return [];

  const buscaRaw = String(termo).trim().toLowerCase();
  const buscaNorm = normalizarTexto(termo);
  if (!buscaRaw) return [];

  const dados = sheet.getRange(6, 1, lastRow - 5, 13).getDisplayValues();
  const resultados = [];

  dados.forEach((row, idx) => {
    const ean = String(row[0]).trim();
    const id = String(row[1]).trim();
    const desc = String(row[2]).trim();
    const descNorm = normalizarTexto(desc);

    if (!desc && !ean) return;

    let pontuacao = 0;

    // Correspondência Exata em EAN ou ID
    if (ean.toLowerCase() === buscaRaw || id.toLowerCase() === buscaRaw || id.toLowerCase() === buscaRaw.padStart(4, '0')) {
      pontuacao += 100;
    }

    // Correspondência em Descrição
    if (descNorm) {
      if (descNorm === buscaNorm) {
        pontuacao += 90;
      } else {
        const regexPalavra = new RegExp('\\b' + buscaNorm + '\\b', 'i');
        if (regexPalavra.test(descNorm)) {
          pontuacao += 70;
        } else if (descNorm.startsWith(buscaNorm)) {
          pontuacao += 50;
        } else if (descNorm.includes(buscaNorm)) {
          pontuacao += 30;
        }
      }
    }

    if (pontuacao > 0) {
      resultados.push({
        pontuacao: pontuacao,
        row: idx + 6,
        ean: row[0],
        id: row[1],
        desc: row[2],
        cat: row[3],
        modo: row[4],
        frac: row[5],
        dataEntrada: row[6],
        pEntrada: row[7],
        pVenda: row[9],
        est: row[10],
        motivo: row[12]
      });
    }
  });

  // Ordena prioritariamente pela maior relevância
  resultados.sort((a, b) => b.pontuacao - a.pontuacao);
  return resultados;
}

function buscarProdutoGlobal() {
  const ui = SpreadsheetApp.getUi();
  const resp = ui.prompt('🔍 BUSCA RÁPIDA ERP', 'Digite a Descrição (Nome), ID ou EAN/Código de Barras (deixe em branco para limpar):', ui.ButtonSet.OK_CANCEL);
  if (resp.getSelectedButton() !== ui.Button.OK) return;
  const termo = resp.getResponseText().trim().toLowerCase();
  if (!termo || termo === "limpar") {
    limparBusca();
    return;
  }
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet(), lastRow = sheet.getLastRow();
  if (lastRow < 6) return;
  const range = sheet.getRange(6, 1, lastRow - 5, 13);
  range.setBackground(null);
  const dados = range.getDisplayValues();
  const matrizCores = dados.map(row => {
    const ean  = String(row[0]).trim().toLowerCase();
    const id   = String(row[1]).trim().toLowerCase();
    const desc = String(row[2]).trim().toLowerCase();
    const achou = desc.includes(termo) || id === termo || id === termo.padStart(4, '0') || ean === termo || row.some(cell => String(cell).toLowerCase().includes(termo));
    return Array(13).fill(achou ? '#FFF2CC' : null);
  });
  range.setBackgrounds(matrizCores);
  const total = matrizCores.filter(r => r[0] !== null).length;
  ui.alert(total > 0 ? `🔎 Encontrados ${total} item(ns).\nPara limpar o amarelo, use o botão 'Limpar Pesquisa' ou digite em branco na busca.` : `❌ Nenhum resultado para "${termo}".`);
}

function limparBusca() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const lastRow = sheet.getLastRow();
  if (lastRow >= 6) {
    sheet.getRange(6, 1, lastRow - 5, 13).setBackground(null);
  }
  SpreadsheetApp.getUi().alert("🧹 Destaques removidos! A planilha voltou ao normal.");
}

// ============================================================
// 5. FORMULÁRIO DE NOVO CADASTRO (MODAL CUSTOMIZADO)
// ============================================================
function cadastrarNovoProduto() {
  abrirJanelaNovoProduto();
}

function abrirJanelaNovoProduto() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const proximoID = obterProximoID(sheet);

  const html = `
  <!DOCTYPE html>
  <html>
  <head>
    <style>
      body { font-family: Arial, sans-serif; padding: 12px; background: #f8f9fa; color: #333; margin:0; }
      .box { background: #fff; padding: 14px; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.12); }
      label { font-size: 11px; font-weight: bold; color: #555; display: block; margin-top: 6px; }
      input, select { width: 100%; padding: 7px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; font-size: 12px; }
      input[readonly] { background: #e9ecef; color: #495057; font-weight: bold; cursor: not-allowed; }
      .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
      .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
      .btn { padding: 10px 14px; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 12px; width: 100%; margin-top: 10px; }
      .btn-primary { background: #107c41; color: #fff; }
      .st { font-size: 12px; text-align: center; margin-top: 8px; font-weight: bold; }
    </style>
  </head>
  <body>
    <form id="form-cad" class="box">
      <div class="grid-2">
        <div><label>EAN / Cód. Barras:</label><input type="text" id="f_ean" placeholder="Opcional"></div>
        <div><label>ID Sequencial (Automático):</label><input type="text" id="f_id" value="${proximoID}" readonly></div>
      </div>
      <div><label>Descrição do Produto (*):</label><input type="text" id="f_desc" placeholder="Ex: "></div>
      <div class="grid-2">
        <div><label>Categoria:</label><input type="text" id="f_cat" placeholder="Ex: "></div>
        <div><label>Modo de Compra / Embalagem:</label><input type="text" id="f_modo" value="Unidade"></div>
      </div>
      <div class="grid-3">
        <div><label>Fracionar Em:</label><input type="number" id="f_frac" value="1"></div>
        <div><label>Preço Entrada (R$):</label><input type="text" id="f_pentrada" placeholder="0,00"></div>
        <div><label>Preço Venda (R$):</label><input type="text" id="f_pvenda" placeholder="0,00"></div>
      </div>
      <div class="grid-2">
        <div><label>Estoque Inicial:</label><input type="number" id="f_est" value="0"></div>
        <div>
          <label>Motivo / Destino:</label>
          <select id="f_motivo">
            <option value="1-Revenda">1-Revenda</option>
            <option value="2-Uso/Consumo">2-Uso/Consumo</option>
            <option value="3-Matéria-Prima">3-Matéria-Prima</option>
          </select>
        </div>
      </div>
      <button type="button" class="btn btn-primary" onclick="cadastrar()">💾 Salvar Novo Produto</button>
      <div id="st" class="st"></div>
    </form>
    <script>
      function cadastrar(){
        var desc = document.getElementById('f_desc').value.trim();
        if(!desc){
          alert('Por favor, informe a Descrição do Produto!');
          return;
        }
        var dados = {
          ean: document.getElementById('f_ean').value,
          id: document.getElementById('f_id').value,
          desc: desc,
          cat: document.getElementById('f_cat').value,
          modo: document.getElementById('f_modo').value,
          frac: document.getElementById('f_frac').value,
          pEntrada: document.getElementById('f_pentrada').value,
          pVenda: document.getElementById('f_pvenda').value,
          est: document.getElementById('f_est').value,
          motivo: document.getElementById('f_motivo').value
        };
        document.getElementById('st').style.color = '#007bff';
        document.getElementById('st').innerText = '⏳ Cadastrando no estoque...';
        google.script.run.withSuccessHandler(m => {
          document.getElementById('st').style.color = '#107c41';
          document.getElementById('st').innerText = '✅ ' + m;
          setTimeout(() => google.script.host.close(), 1200);
        }).withFailureHandler(e => {
          document.getElementById('st').style.color = '#d9534f';
          document.getElementById('st').innerText = '❌ ' + e.message;
        }).salvarNovoProdutoModal(dados);
      }
    </script>
  </body>
  </html>`;
  SpreadsheetApp.getUi().showModalDialog(HtmlService.createHtmlOutput(html).setWidth(430).setHeight(420), '📦 NOVO CADASTRO DE PRODUTO');
}

function salvarNovoProdutoModal(d) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const target = obterProximaLinhaVazia(sheet);

  sheet.getRange(target, 1).setNumberFormat('@').setValue(d.ean || "");
  sheet.getRange(target, 2).setNumberFormat('@').setValue(d.id);
  sheet.getRange(target, 3).setValue(limparDescricao(d.desc));
  sheet.getRange(target, 4).setValue(d.cat || "");
  sheet.getRange(target, 5).setValue(d.modo || "Unidade");
  sheet.getRange(target, 6).setValue(parseFloat(d.frac) || 1);

  const pEnt = parseFloat(String(d.pEntrada).replace('R$', '').replace(/\./g, '').replace(',', '.').trim()) || 0;
  const pVen = parseFloat(String(d.pVenda).replace('R$', '').replace(/\./g, '').replace(',', '.').trim()) || 0;
  const est = parseInt(d.est, 10) || 0;

  sheet.getRange(target, 8).setValue(pEnt);
  sheet.getRange(target, 10).setValue(pVen);
  sheet.getRange(target, 11).setValue(est);
  sheet.getRange(target, 13).setValue(d.motivo || "1-Revenda");
  carimbarDataEntrada(sheet, target);

  aplicarEstiloLinha(sheet, target, true);
  atualizarValoresEMargem(sheet, target);

  return `Produto cadastrado com sucesso!`;
}

// ============================================================
// 6. FORMULÁRIO DE EDIÇÃO DE CADASTRO
// ============================================================
function abrirJanelaEditarCadastro() {
  const html = `
  <!DOCTYPE html>
  <html>
  <head>
    <style>
      body { font-family: Arial, sans-serif; padding: 12px; background: #f8f9fa; color: #333; margin:0; }
      .box { background: #fff; padding: 12px; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.12); margin-bottom: 10px; }
      label { font-size: 11px; font-weight: bold; color: #555; display: block; margin-top: 6px; }
      input, select { width: 100%; padding: 7px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; font-size: 12px; }
      input[readonly] { background: #e9ecef; color: #6c757d; font-weight: bold; }
      .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
      .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
      .btn { padding: 9px 14px; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 12px; }
      .btn-primary { background: #107c41; color: #fff; }
      .btn-search { background: #007bff; color: #fff; }
      .btn-secondary { background: #6c757d; color: #fff; }
      .st { font-size: 12px; text-align: center; margin-top: 8px; font-weight: bold; }
      .results-list { margin-top: 8px; max-height: 150px; overflow-y: auto; border: 1px solid #ddd; border-radius: 4px; background: #fff; }
      .result-item { padding: 8px; border-bottom: 1px solid #eee; cursor: pointer; font-size: 12px; text-align: left; }
      .result-item:hover { background: #e8f4fe; color: #007bff; font-weight: bold; }
    </style>
  </head>
  <body>
    <div id="step-busca" class="box">
      <label style="font-size:12px; margin-top:0;">Localizar Produto (EAN, ID ou Descrição):</label>
      <div style="display:flex; gap:6px; margin-top:6px;">
        <input type="text" id="term" placeholder="Ex: bis, 0001 ou 789..." onkeyup="if(event.key==='Enter') buscar()">
        <button class="btn btn-search" onclick="buscar()">Buscar</button>
      </div>
      <div id="lista-resultados" class="results-list" style="display:none;"></div>
      <div id="busca-st" class="st"></div>
    </div>
    <form id="form-edit" style="display:none;" class="box">
      <input type="hidden" id="rowIdx">
      <div class="grid-2">
        <div><label>EAN / Cód. Barras:</label><input type="text" id="f_ean"></div>
        <div><label>ID Sequencial:</label><input type="text" id="f_id" readonly></div>
      </div>
      <div><label>Descrição do Produto:</label><input type="text" id="f_desc"></div>
      <div class="grid-2">
        <div><label>Categoria:</label><input type="text" id="f_cat"></div>
        <div><label>Modo de Compra:</label><input type="text" id="f_modo"></div>
      </div>
      <div class="grid-3">
        <div><label>Fracionar Em:</label><input type="number" id="f_frac"></div>
        <div><label>Preço Entrada:</label><input type="text" id="f_pentrada"></div>
        <div><label>Preço Venda:</label><input type="text" id="f_pvenda"></div>
      </div>
      <div class="grid-2">
        <div><label>Estoque Atual:</label><input type="number" id="f_est"></div>
        <div>
          <label>Motivo / Destino:</label>
          <select id="f_motivo">
            <option value="1-Revenda">1-Revenda</option>
            <option value="2-Uso/Consumo">2-Uso/Consumo</option>
            <option value="3-Matéria-Prima">3-Matéria-Prima</option>
          </select>
        </div>
      </div>
      <div style="margin-top:12px; display:flex; justify-content:space-between;">
        <button type="button" class="btn btn-secondary" onclick="cancelar()">Voltar</button>
        <button type="button" class="btn btn-primary" onclick="salvar()">💾 Salvar Alterações</button>
      </div>
      <div id="save-st" class="st"></div>
    </form>
    <script>
      var listaCache = [];
      function buscar(){
        var t = document.getElementById('term').value.trim();
        if(!t) return alert('Digite algo para buscar!');
        document.getElementById('busca-st').style.color = '#007bff';
        document.getElementById('busca-st').innerText = '⏳ Buscando produtos...';
        document.getElementById('lista-resultados').style.display = 'none';
        google.script.run.withSuccessHandler(processarResultadoBusca).withFailureHandler(e => {
          document.getElementById('busca-st').style.color = '#d9534f';
          document.getElementById('busca-st').innerText = '❌ ' + e.message;
        }).pesquisarProdutosModal(t);
      }

      function processarResultadoBusca(lista){
        listaCache = lista;
        var st = document.getElementById('busca-st');
        var divLista = document.getElementById('lista-resultados');
        divLista.innerHTML = '';

        if(!lista || lista.length === 0){
          st.style.color = '#d9534f';
          st.innerText = '❌ Nenhum produto encontrado!';
          return;
        }

        if(lista.length === 1){
          st.innerText = '';
          exibirProduto(lista[0]);
          return;
        }

        st.style.color = '#107c41';
        st.innerText = '🔎 Encontrados ' + lista.length + ' produtos. Clique para selecionar:';

        lista.forEach((item, index) => {
          var itemDiv = document.createElement('div');
          itemDiv.className = 'result-item';
          itemDiv.innerHTML = '<strong>[ID ' + (item.id || 'N/A') + ']</strong> ' + item.desc + ' <span style="color:#888;">(Estoque: ' + item.est + ')</span>';
          itemDiv.onclick = function() { selecionarProduto(index); };
          divLista.appendChild(itemDiv);
        });
        divLista.style.display = 'block';
      }

      function selecionarProduto(index){
        document.getElementById('busca-st').innerText = '';
        document.getElementById('lista-resultados').style.display = 'none';
        exibirProduto(listaCache[index]);
      }

      function exibirProduto(p){
        document.getElementById('rowIdx').value = p.row;
        document.getElementById('f_ean').value = p.ean;
        document.getElementById('f_id').value = p.id;
        document.getElementById('f_desc').value = p.desc;
        document.getElementById('f_cat').value = p.cat;
        document.getElementById('f_modo').value = p.modo;
        document.getElementById('f_frac').value = p.frac;
        document.getElementById('f_pentrada').value = p.pEntrada;
        document.getElementById('f_pvenda').value = p.pVenda;
        document.getElementById('f_est').value = p.est;
        document.getElementById('f_motivo').value = p.motivo || "1-Revenda";
        document.getElementById('form-edit').style.display = 'block';
        document.getElementById('step-busca').style.display = 'none';
      }

      function cancelar(){
        document.getElementById('form-edit').style.display = 'none';
        document.getElementById('step-busca').style.display = 'block';
      }

      function salvar(){
        var dados = {
          row: document.getElementById('rowIdx').value,
          ean: document.getElementById('f_ean').value,
          id: document.getElementById('f_id').value,
          desc: document.getElementById('f_desc').value,
          cat: document.getElementById('f_cat').value,
          modo: document.getElementById('f_modo').value,
          frac: document.getElementById('f_frac').value,
          pEntrada: document.getElementById('f_pentrada').value,
          pVenda: document.getElementById('f_pvenda').value,
          est: document.getElementById('f_est').value,
          motivo: document.getElementById('f_motivo').value
        };
        document.getElementById('save-st').style.color = '#007bff';
        document.getElementById('save-st').innerText = '⏳ Salvando no estoque...';
        google.script.run.withSuccessHandler(m => {
          document.getElementById('save-st').style.color = '#107c41';
          document.getElementById('save-st').innerText = '✅ ' + m;
          setTimeout(() => google.script.host.close(), 1200);
        }).withFailureHandler(e => {
          document.getElementById('save-st').style.color = '#d9534f';
          document.getElementById('save-st').innerText = '❌ ' + e.message;
        }).salvarAlteracaoProduto(dados);
      }
    </script>
  </body>
  </html>`;
  SpreadsheetApp.getUi().showModalDialog(HtmlService.createHtmlOutput(html).setWidth(430).setHeight(450), '✏️ EDITAR CADASTRO DO PRODUTO');
}

function salvarAlteracaoProduto(d) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const row = parseInt(d.row, 10);
  if (!row || row < 6) throw new Error("Linha inválida.");
  sheet.getRange(row, 1).setNumberFormat('@').setValue(d.ean);
  sheet.getRange(row, 3).setValue(d.desc);
  sheet.getRange(row, 4).setValue(d.cat);
  sheet.getRange(row, 5).setValue(d.modo);
  sheet.getRange(row, 6).setValue(parseFloat(d.frac) || 1);
  const pEnt = parseFloat(String(d.pEntrada).replace('R$', '').replace(/\./g, '').replace(',', '.').trim()) || 0;
  const pVen = parseFloat(String(d.pVenda).replace('R$', '').replace(/\./g, '').replace(',', '.').trim()) || 0;
  const estoque = parseInt(d.est, 10) || 0;
  sheet.getRange(row, 8).setValue(pEnt);
  sheet.getRange(row, 10).setValue(pVen);
  sheet.getRange(row, 11).setValue(estoque);
  sheet.getRange(row, 13).setValue(d.motivo || "1-Revenda");
  aplicarEstiloLinha(sheet, row, true);
  atualizarValoresEMargem(sheet, row);
  return "Cadastro atualizado com sucesso!";
}

// ============================================================
// 7. FUNÇÕES AUXILIARES E CÁLCULOS
// ============================================================
function limparDescricao(nome) {
  if (!nome) return "";
  return String(nome)
    .replace(/abaixo estão listados[\s\S]*?:/gi, '')
    .replace(/\btotal\s*:?/gi, '') // rótulo "Total:" de cupom fiscal (ex: "1x 28,90 Total: 28,90")
    .replace(/\b\d+[\.,]\d{2}\b/g, '')
    .replace(/\b(789\d{10}|790\d{10}|\d{13,14})\b/gi, '')
    .replace(/\b\d{4}\b/g, '')
    .replace(/\b(xUnidade|Unidade|xUN|UN|KG|PC)\b/gi, '')
    .replace(/\b\d+\s*x\b/gi, '') // "2x" de quantidade, em qualquer posição da linha (não só no final)
    .replace(/^[\d\.\-\*\#\:\s]+/, '')
    .replace(/\s+/g, ' ').trim();
}

function normalizarTexto(txt) {
  if (!txt) return "";
  return limparDescricao(txt).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]/g, ' ').replace(/\s+/g, ' ').trim();
}

function obterProximaLinhaVazia(sheet) {
  const lastRow = sheet.getLastRow();
  if (lastRow < 6) return 6;
  const descricoes = sheet.getRange(6, 3, lastRow - 5, 1).getValues();
  for (let i = 0; i < descricoes.length; i++) {
    if (!String(descricoes[i][0]).trim()) return i + 6;
  }
  return lastRow + 1;
}

function obterProximoID(sheet) {
  if (!sheet) sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const lastRow = sheet.getLastRow();
  let maior = 0;
  if (lastRow >= 6) {
    sheet.getRange(6, 2, lastRow - 5, 1).getDisplayValues().forEach(v => {
      const num = parseInt(String(v[0]).replace(/\D/g, ''), 10);
      if (num > maior) maior = num;
    });
  }
  return String(maior + 1).padStart(4, '0');
}

function extrairFator(textoEmbalagem, nomeProduto) {
  let t = ((textoEmbalagem || "") + " " + (nomeProduto || "")).toLowerCase().trim();
  t = t.replace(/(?:c\/|cx\b|caixa\b)?\s*\d+\s*(?:capsulas|capsula|caps|cap|comprimidos|comprimido|comp|drageas|dragea|softgel|gomas|goma|pastilhas|pastilha|saches|sache)\b/gi, '');
  t = t.replace(/\b\d+\s*(kg|g|mg|mcg|l|ml)\b/gi, '');

  const mMult = t.match(/(\d+)\s*x\s*\d+/);
  if (mMult) return parseInt(mMult[1], 10);
  const mCaixa = t.match(/(?:c\/|cx|caixa|fardo|pack|display)\s*(\d+)/);
  if (mCaixa) return parseInt(mCaixa[1], 10);
  const mUnid = t.match(/(\d+)\s*unidade[s]?\b/);
  if (mUnid) return parseInt(mUnid[1], 10);
  return 1;
}

function gerarIDSequencial(sheet, row) {
  if (row < 6) return;
  const idCell = sheet.getRange(row, 2);
  if (!idCell.getDisplayValue().trim()) {
    idCell.setNumberFormat('@').setValue(obterProximoID(sheet));
  }
}

function atualizarValoresEMargem(sheet, row) {
  if (!sheet) sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  if (!row || row < 6) return;
  const desc = sheet.getRange(row, 3).getDisplayValue().trim();
  const ean = sheet.getRange(row, 1).getDisplayValue().trim();

  if (!desc && !ean) {
    aplicarEstiloLinha(sheet, row, false);
    return;
  }
  try {
    const fator = parseFloat(sheet.getRange(row, 6).getValue()) || 1;
    const pEntrada = parseFloat(sheet.getRange(row, 8).getValue()) || 0;
    const pVenda = parseFloat(sheet.getRange(row, 10).getValue()) || 0;
    if (pEntrada > 0) {
      const vUnit = fator > 0 ? (pEntrada / fator) : pEntrada;
      sheet.getRange(row, 9).setValue(vUnit).setNumberFormat('R$ #,##0.00');
      sheet.getRange(row, 8).setNumberFormat('R$ #,##0.00');
    } else {
      sheet.getRange(row, 9).clearContent().clearFormat();
    }
    if (pVenda > 0) sheet.getRange(row, 10).setNumberFormat('R$ #,##0.00');
    if (pVenda > 0 && pEntrada > 0) {
      const vUnit = fator > 0 ? (pEntrada / fator) : pEntrada;
      sheet.getRange(row, 12).setValue((pVenda - vUnit) / pVenda).setNumberFormat('0.0%');
    } else {
      sheet.getRange(row, 12).clearContent().clearFormat();
    }
  } catch (e) {}
}

/**
 * Carimba a Data da Última Entrada (coluna G) — chamada só nos pontos em que
 * o estoque realmente RECEBE mercadoria nova (XML, PDF, Chave de Acesso ou cadastro manual).
 */
function carimbarDataEntrada(sheet, row) {
  const hoje = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "dd/MM/yyyy");
  sheet.getRange(row, 7).setValue(hoje);
}

// ============================================================
// 8. MONITORAMENTO DE EDIÇÕES MANUAIS (ONEDIT)
// ============================================================
function monitorarEntrada(e) {
  if (!e || !e.source) return;
  const sheet = e.source.getActiveSheet(), range = e.range;
  const startRow = range.getRow(), numRows = range.getNumRows(), col = range.getColumn();
  for (let i = 0; i < numRows; i++) {
    const row = startRow + i;
    if (row < 6) continue;
    const eanAtual = sheet.getRange(row, 1).getDisplayValue().trim();
    const descAtual = sheet.getRange(row, 3).getDisplayValue().trim();
    const temProduto = (eanAtual !== "" || descAtual !== "");
    aplicarEstiloLinha(sheet, row, temProduto);
    if (!temProduto) continue;
    if (col === 1) { // EAN
      const cell = sheet.getRange(row, 1);
      cell.setNumberFormat('@');
      const eanLimpo = eanAtual.replace(/\D/g, '');
      if (eanLimpo) {
        const lastRow = sheet.getLastRow();
        if (lastRow >= 6) {
          const eans = sheet.getRange(6, 1, lastRow - 5, 1).getDisplayValues();
          for (let r = 0; r < eans.length; r++) {
            if ((r + 6) !== row && String(eans[r][0]).replace(/\D/g, '') === eanLimpo) {
              SpreadsheetApp.getUi().alert(`⚠️ EAN DUPLICADO!\nO código ${eanAtual} já existe na linha ${r + 6}.`);
              cell.clearContent();
              sheet.getRange(r + 6, 3).activate();
              return;
            }
          }
        }
      }
    }
    if (col === 3) { // Descrição
      const descLimpa = limparDescricao(descAtual);
      if (descLimpa !== descAtual) sheet.getRange(row, 3).setValue(descLimpa);
      if (descLimpa) {
        sheet.getRange(row, 3).setBackground(null);
        gerarIDSequencial(sheet, row);
        if (!sheet.getRange(row, 5).getDisplayValue().trim()) {
          sheet.getRange(row, 5).setValue("Unidade");
          sheet.getRange(row, 6).setValue(1);
        }
        if (!sheet.getRange(row, 13).getDisplayValue().trim()) sheet.getRange(row, 13).setValue("1-Revenda");
      }
    }
    if (col === 5) { // Embalagem
      const emb = sheet.getRange(row, 5).getDisplayValue();
      const prod = sheet.getRange(row, 3).getDisplayValue();
      sheet.getRange(row, 6).setValue(extrairFator(emb, prod));
    }
    atualizarValoresEMargem(sheet, row);
  }
}

// ============================================================
// 9. OPERAÇÕES DE EXCLUSÃO DE PRODUTO
// ============================================================
function deletarProduto() {
  const ui = SpreadsheetApp.getUi();
  const resp = ui.prompt('🗑️ APAGAR PRODUTO', 'Digite a Descrição (Nome), ID ou EAN do produto:', ui.ButtonSet.OK_CANCEL);
  if (resp.getSelectedButton() !== ui.Button.OK) return;

  const busca = resp.getResponseText().trim().toLowerCase();
  if (!busca) return;

  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const lastRow = sheet.getLastRow();
  if (lastRow < 6) return;

  const dados = sheet.getRange(6, 1, lastRow - 5, 3).getDisplayValues();
  let linhaDel = -1;
  let nome = "";
  let idEncontrado = "";

  for (let i = dados.length - 1; i >= 0; i--) {
    const ean  = String(dados[i][0]).trim().toLowerCase();
    const id   = String(dados[i][1]).trim().toLowerCase();
    const desc = String(dados[i][2]).trim().toLowerCase();

    if (desc.includes(busca) || id === busca || id === busca.padStart(4, '0') || ean === busca) {
      linhaDel = i + 6;
      idEncontrado = dados[i][1] || "N/A";
      nome = dados[i][2] || "Produto sem descrição";
      break;
    }
  }

  if (linhaDel !== -1) {
    const confirm = ui.alert('⚠️ CONFIRMAÇÃO', `Apagar produto?\n\n- ID: ${idEncontrado}\n- Nome: ${nome}`, ui.ButtonSet.YES_NO);
    if (confirm === ui.Button.YES) {
      sheet.deleteRow(linhaDel);
      ui.alert('✅ Apagado com sucesso!');
    }
  } else {
    ui.alert(`❌ Nenhum produto encontrado com "${busca}".`);
  }
}

// ============================================================
// 10. ENTRADA DE NOTAS FISCAIS (XML, PDF E CHAVE DE ACESSO)
// ============================================================
function abrirJanelaEntradaNota() {
  const html = `<body style="font-family:sans-serif;text-align:center;padding:15px;background:#f8f9fa;">
    <h3 style="margin-top:5px;">📦 Entrada de Estoque</h3>
    <button style="width:100%;padding:10px;margin:5px 0;background:#107c41;color:#fff;border:none;border-radius:5px;font-weight:bold;cursor:pointer;" onclick="google.script.run.abrirJanelaImportarNFe();google.script.host.close();">📄 XML Nota Fiscal</button>
    <button style="width:100%;padding:10px;margin:5px 0;background:#007bff;color:#fff;border:none;border-radius:5px;font-weight:bold;cursor:pointer;" onclick="google.script.run.abrirJanelaImportarPDF();google.script.host.close();">🧾 Arquivo PDF</button>
    <button style="width:100%;padding:10px;margin:5px 0;background:#6f42c1;color:#fff;border:none;border-radius:5px;font-weight:bold;cursor:pointer;" onclick="google.script.run.abrirJanelaImportarChave();google.script.host.close();">🔑 Importar por Chave de Acesso</button>
  </body>`;
  SpreadsheetApp.getUi().showModalDialog(HtmlService.createHtmlOutput(html).setWidth(360).setHeight(240), ' ');
}

function abrirJanelaImportarNFe() {
  const html = `<body style="font-family:sans-serif;text-align:center;padding:15px;">
    <h3 style="color:#107c41;">📄 Importar XML</h3>
    <input type="file" id="f" accept=".xml" style="margin:10px 0;"><br>
    <button id="b" style="background:#107c41;color:#fff;border:none;padding:10px 20px;font-weight:bold;border-radius:4px;cursor:pointer;" onclick="p()">Importar</button>
    <div id="st" style="margin-top:10px;font-size:12px;"></div>
    <script>
      function p(){
        var f=document.getElementById('f').files[0]; if(!f) return alert('Selecione XML!');
        document.getElementById('b').disabled=true; document.getElementById('st').innerText='⏳ Lendo XML...';
        var r=new FileReader(); r.onload=e=>google.script.run.withSuccessHandler(m=>{document.getElementById('st').innerText='✅ '+m; setTimeout(()=>google.script.host.close(),2000)}).withFailureHandler(e=>{document.getElementById('st').innerText='❌ '+e.message; document.getElementById('b').disabled=false;}).processarXMLNFe(e.target.result);
        r.readAsText(f);
      }
    </script>
  </body>`;
  SpreadsheetApp.getUi().showModalDialog(HtmlService.createHtmlOutput(html).setWidth(350).setHeight(200), ' ');
}

function processarXMLNFe(xmlString) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet(), lastRow = sheet.getLastRow();
  const eans = {};
  if (lastRow >= 6) {
    sheet.getRange(6, 1, lastRow - 5, 1).getValues().forEach((v, r) => {
      const ean = String(v[0]).replace(/\D/g, '').trim();
      if (ean.length >= 8) eans[ean] = r + 6;
    });
  }
  const itens = xmlString.match(/<det[\s\S]*?<\/det>/g);
  if (!itens) throw new Error("Nenhum item válido no XML.");
  let at = 0, nv = 0;
  const tag = (xml, t) => (xml.match(new RegExp(`<${t}>([\\s\\S]*?)<\/${t}>`, "i")) || [])[1]?.trim() || "";
  itens.forEach(item => {
    let ean = tag(item, 'cEAN');
    if (!ean || ean.toUpperCase() === 'SEM GTIN') ean = tag(item, 'cProd');
    ean = String(ean).replace(/\D/g, '').trim();
    if (ean.length < 8) ean = "";
    const xProd = limparDescricao(tag(item, 'xProd')), qCom = parseFloat(tag(item, 'qCom')) || 0, vUnCom = parseFloat(tag(item, 'vUnCom')) || 0;
    const fator = extrairFator("", xProd), qtdEnt = qCom * fator, pUnEnt = fator > 0 ? (vUnCom / fator) : vUnCom;
    if (ean && eans[ean]) {
      const row = eans[ean], qAtual = parseFloat(sheet.getRange(row, 11).getValue()) || 0, pAtual = parseFloat(sheet.getRange(row, 9).getValue()) || 0;
      const qTot = qAtual + qtdEnt, pMed = qTot > 0 ? ((qAtual * pAtual) + (qtdEnt * pUnEnt)) / qTot : pUnEnt;
      sheet.getRange(row, 11).setValue(qTot);
      sheet.getRange(row, 8).setValue(vUnCom).setNumberFormat('R$ #,##0.00');
      sheet.getRange(row, 9).setValue(pMed).setNumberFormat('R$ #,##0.00');
      if (!sheet.getRange(row, 13).getDisplayValue().trim()) sheet.getRange(row, 13).setValue("1-Revenda");
      aplicarEstiloLinha(sheet, row, true);
      atualizarValoresEMargem(sheet, row);
      carimbarDataEntrada(sheet, row); at++;
    } else {
      const target = obterProximaLinhaVazia(sheet);
      if (ean) sheet.getRange(target, 1).setNumberFormat('@').setValue(ean);
      sheet.getRange(target, 3).setValue(xProd);
      sheet.getRange(target, 5).setValue("Unidade");
      sheet.getRange(target, 6).setValue(fator);
      sheet.getRange(target, 8).setValue(vUnCom).setNumberFormat('R$ #,##0.00');
      sheet.getRange(target, 9).setValue(pUnEnt).setNumberFormat('R$ #,##0.00');
      sheet.getRange(target, 11).setValue(qtdEnt);
      sheet.getRange(target, 13).setValue("1-Revenda");
      gerarIDSequencial(sheet, target);
      aplicarEstiloLinha(sheet, target, true);
      atualizarValoresEMargem(sheet, target);
      carimbarDataEntrada(sheet, target); nv++;
    }
  });
  return `Importado! Atualizados: ${at} | Novos: ${nv}`;
}

function abrirJanelaImportarPDF() {
  const html = `<body style="font-family:sans-serif;text-align:center;padding:15px;">
    <h3 style="color:#007bff;">🧾 Importar PDF</h3>
    <input type="file" id="f" accept=".pdf" style="margin:10px 0;"><br>
    <button id="b" style="background:#007bff;color:#fff;border:none;padding:10px 20px;font-weight:bold;border-radius:4px;cursor:pointer;" onclick="p()">Processar PDF</button>
    <div id="st" style="margin-top:10px;font-size:12px;"></div>
    <script>
      function p(){
        var f=document.getElementById('f').files[0]; if(!f) return alert('Selecione PDF!');
        document.getElementById('b').disabled=true; document.getElementById('st').innerText='⏳ OCR com Drive...';
        var r=new FileReader(); r.onload=e=>google.script.run.withSuccessHandler(m=>{document.getElementById('st').innerText='✅ '+m; setTimeout(()=>google.script.host.close(),2500)}).withFailureHandler(e=>{document.getElementById('st').innerText='❌ '+e.message; document.getElementById('b').disabled=false;}).processarPDF(e.target.result.split(',')[1], f.name);
        r.readAsDataURL(f);
      }
    </script>
  </body>`;
  SpreadsheetApp.getUi().showModalDialog(HtmlService.createHtmlOutput(html).setWidth(350).setHeight(200), ' ');
}

/**
 * Corta o texto extraído do PDF logo antes da seção de rodapé fiscal
 * ("DADOS ADICIONAIS" / "INFORMAÇÕES COMPLEMENTARES"), onde a NF-e imprime
 * observações do contribuinte, cálculo de IBPT, protocolo, MD5 etc.
 * Sem isso, qualquer número nesse texto no formato "99,99" era lido como
 * preço de produto e virava linha nova (ou entrada fantasma) no Estoque —
 * foi o que aconteceu com "Inf. Contribuinte..." e "Valor Aproximado dos
 * Tributos" virando produtos fantasma numa importação real.
 * Se nenhum dos marcadores aparecer no texto, devolve o texto inteiro sem cortar.
 */
function cortarRodapeNota(texto) {
  const idx = texto.search(/DADOS\s+ADICIONAIS|INFORMA[ÇC][ÕO]ES\s+COMPLEMENTARES/i);
  return idx > -1 ? texto.slice(0, idx) : texto;
}

/**
 * Procura no texto do PDF a Chave de Acesso da NF-e: sempre 44 dígitos,
 * impressos em 11 blocos de 4 dígitos separados por espaço (ex: "3126 0946
 * 7989 5300 0148 5500 1000 0000 6011 9101 5361"). Esse formato é bem
 * específico — não bate com datas, números de nota, CNPJ etc. — então dá
 * pra achar com segurança em qualquer lugar do texto, mesmo que o OCR tenha
 * embaralhado a ordem de leitura da tabela de produtos mais abaixo.
 * Devolve os 44 dígitos sem espaço, ou "" se não achou.
 */
function extrairChaveAcessoPDF(texto) {
  const m = texto.match(/\b(?:\d{4}\s){10}\d{4}\b/);
  if (!m) return "";
  const chave = m[0].replace(/\D/g, '');
  return chave.length === 44 ? chave : "";
}

function processarPDF(base64Data, fileName) {
  if (!base64Data) throw new Error("PDF inválido.");
  const blob = Utilities.newBlob(Utilities.base64Decode(base64Data), 'application/pdf', fileName);
  let docFile;
  try {
    docFile = Drive.Files.create({ name: fileName, mimeType: MimeType.GOOGLE_DOCS }, blob, { ocrLanguage: 'pt' });
  } catch (e) {
    throw new Error("Ative a 'Drive API' nos Serviços Avançados do Google Apps Script.");
  }
  const doc = DocumentApp.openById(docFile.id);
  const textoPDF = doc.getBody().getText();
  try { DriveApp.getFileById(docFile.id).setTrashed(true); } catch (e) {}
  if (!textoPDF.trim()) throw new Error("Texto em branco no PDF.");

  // Lê direto do texto do OCR — sem chamar nenhuma API externa (SEFAZ fica
  // pra quando a parte fiscal do sistema for construída). Pensado pro formato
  // de cupom fiscal (recibo estreito, itens em lista simples), que o OCR
  // reconstrói de forma bem mais limpa do que uma DANFE de tabela larga.
  const textoProdutos = cortarRodapeNota(textoPDF);

  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet(), lastRow = sheet.getLastRow();
  const pEan = {}, pDesc = {};
  if (lastRow >= 6) {
    sheet.getRange(6, 1, lastRow - 5, 3).getValues().forEach((v, r) => {
      const ean = String(v[0]).replace(/\D/g, '').trim(), norm = normalizarTexto(v[2]), row = r + 6;
      if (ean.length >= 8) pEan[ean] = row;
      if (norm) pDesc[norm] = row;
    });
  }
  const linhasBrutas = textoProdutos.replace(/\r\n/g, '\n').replace(/(789\d{10}|790\d{10}|\b\d{13,14}\b)/g, '\n$1').split('\n');
  const linhas = mesclarLinhasProdutoPDF(linhasBrutas);
  let at = 0, nv = 0;
  linhas.forEach(linha => {
    const l = linha.trim();
    if (l.length < 5 || /^(danfe|nota fiscal|cnpj\b|total\b|subtotal\b)/i.test(l)) return;
    const precos = l.match(/\b\d+[\.,]\d{2}\b/g);
    if (precos) {
      const eanLido = (l.match(/\b(789\d{10}|790\d{10}|\d{13,14})\b/) || [])[0] || "";
      // Se a linha tem "Nx <preço>" (padrão de cupom: quantidade seguida do
      // preço unitário), usa esse preço específico — não o último número da
      // linha, que pode ser um "Total:" do item e não o valor unitário.
      const matchQtdPreco = l.match(/(\d+)\s*x\s*(\d+[\.,]\d{2})/i);
      let qtd, pUnit;
      if (matchQtdPreco) {
        qtd = parseFloat(matchQtdPreco[1]) || 1;
        pUnit = parseFloat(matchQtdPreco[2].replace(',', '.'));
      } else {
        qtd = 1;
        pUnit = parseFloat(precos[precos.length - 1].replace(',', '.'));
      }
      const nomeProd = limparDescricao(l), norm = normalizarTexto(nomeProd);
      if (norm.length >= 3 && pUnit > 0) {
        let row = pEan[eanLido] || pDesc[norm];
        if (!row) {
          for (let k in pDesc) { if (k.includes(norm) || norm.includes(k)) { row = pDesc[k]; break; } }
        }
        const fator = extrairFator("", nomeProd), qtdEnt = qtd * fator;
        if (row) {
          const qAtual = parseFloat(sheet.getRange(row, 11).getValue()) || 0, pAtual = parseFloat(sheet.getRange(row, 9).getValue()) || 0;
          const qTot = qAtual + qtdEnt, pMed = qTot > 0 ? ((qAtual * pAtual) + (qtdEnt * pUnit)) / qTot : pUnit;
          sheet.getRange(row, 3).setValue(nomeProd);
          sheet.getRange(row, 11).setValue(qTot);
          sheet.getRange(row, 8).setValue(pUnit * fator).setNumberFormat('R$ #,##0.00');
          sheet.getRange(row, 9).setValue(pMed).setNumberFormat('R$ #,##0.00');
          if (!sheet.getRange(row, 13).getDisplayValue().trim()) sheet.getRange(row, 13).setValue("1-Revenda");
          aplicarEstiloLinha(sheet, row, true);
          atualizarValoresEMargem(sheet, row);
          carimbarDataEntrada(sheet, row); at++;
        } else {
          const target = obterProximaLinhaVazia(sheet);
          if (eanLido) sheet.getRange(target, 1).setNumberFormat('@').setValue(eanLido);
          sheet.getRange(target, 3).setValue(nomeProd);
          sheet.getRange(target, 5).setValue("Unidade");
          sheet.getRange(target, 6).setValue(fator);
          sheet.getRange(target, 8).setValue(pUnit * fator).setNumberFormat('R$ #,##0.00');
          sheet.getRange(target, 9).setValue(pUnit).setNumberFormat('R$ #,##0.00');
          sheet.getRange(target, 11).setValue(qtdEnt);
          sheet.getRange(target, 13).setValue("1-Revenda");
          gerarIDSequencial(sheet, target);
          aplicarEstiloLinha(sheet, target, true);
          atualizarValoresEMargem(sheet, target);
          carimbarDataEntrada(sheet, target);
          pDesc[norm] = target; if (eanLido) pEan[eanLido] = target; nv++;
        }
      }
    }
  });
  if (at === 0 && nv === 0) {
    throw new Error("Não consegui reconhecer nenhum produto no texto do PDF. Confira se o arquivo é legível (não é uma foto torta/borrada) ou cadastre manualmente.");
  }
  return `Concluído! Atualizados: ${at} | Novos: ${nv}`;
}

/**
 * Alguns cupons imprimem a descrição do produto numa linha e a quantidade/
 * preço na linha seguinte (em vez de tudo numa linha só). O parser original
 * olha uma linha de cada vez, então perdia esses produtos. Esta função junta
 * uma linha "de descrição" (sem preço) com a próxima linha, quando essa
 * próxima é "só valores" (quantidade, preço, "x", "Total:" etc, sem nome de
 * produto) — assim vira uma linha só, no formato que o parser já entende.
 * Linhas separadoras (----, ====) e vazias são descartadas antes de mesclar.
 */
function mesclarLinhasProdutoPDF(linhas) {
  const limpas = linhas.map(l => l.trim()).filter(l => l.length >= 3 && !/^[-=*_\s]+$/.test(l));
  const ehSoValores = (l) => {
    const semNumerosEChaves = l
      .replace(/total\s*:?/gi, '')
      .replace(/r\$/gi, '')
      .replace(/[\d.,xX:\s]/g, '');
    return semNumerosEChaves.length === 0 && /\d/.test(l);
  };
  const resultado = [];
  for (let i = 0; i < limpas.length; i++) {
    let atual = limpas[i];
    const temPreco = /\b\d+[\.,]\d{2}\b/.test(atual);
    if (!temPreco && i + 1 < limpas.length && ehSoValores(limpas[i + 1])) {
      atual = atual + ' ' + limpas[i + 1];
      i++; // já usou a próxima linha, pula ela
    }
    resultado.push(atual);
  }
  return resultado;
}

function abrirJanelaImportarChave() {
  const ui = SpreadsheetApp.getUi();
  const resp = ui.prompt('🔑 Importar por Chave de Acesso', 'Digite ou bipe a Chave de Acesso (44 dígitos):', ui.ButtonSet.OK_CANCEL);
  if (resp.getSelectedButton() !== ui.Button.OK) return;
  const chave = resp.getResponseText().replace(/\D/g, '').trim();
  if (chave.length !== 44) {
    ui.alert('❌ Chave de acesso inválida! Deve conter exatamente 44 dígitos.');
    return;
  }
  try {
    const url = `https://ws.meudanfe.com.br/api/v1/get/xml/${chave}`;
    const res = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
    if (res.getResponseCode() === 200 && res.getContentText().includes('<xml')) {
      const msg = processarXMLNFe(res.getContentText());
      ui.alert(msg);
    } else {
      ui.alert('⚠️ XML não disponível publicamente para esta chave. Faça a importação enviando o arquivo XML ou PDF diretamente.');
    }
  } catch (e) {
    ui.alert(`❌ Erro ao buscar dados da chave: ${e.message}`);
  }
}

// ============================================================
// 11. EXCLUSÃO / ESTORNO DE NOTA FISCAL
// ============================================================
function abrirJanelaExcluirNota() {
  const html = `<body style="font-family:sans-serif;text-align:center;padding:15px;background:#f8f9fa;">
    <h3 style="margin-top:5px;color:#d9534f;">🗑️ Excluir Nota / Estorno</h3>
    <button style="width:100%;padding:10px;margin:5px 0;background:#d9534f;color:#fff;border:none;border-radius:5px;font-weight:bold;cursor:pointer;" onclick="google.script.run.abrirJanelaEstornarNFe();google.script.host.close();">📄 Estornar via XML</button>
    <button style="width:100%;padding:10px;margin:5px 0;background:#007bff;color:#fff;border:none;border-radius:5px;font-weight:bold;cursor:pointer;" onclick="google.script.run.abrirJanelaEstornarPDF();google.script.host.close();">🧾 Estornar via PDF</button>
  </body>`;
  SpreadsheetApp.getUi().showModalDialog(HtmlService.createHtmlOutput(html).setWidth(360).setHeight(200), ' ');
}

function abrirJanelaEstornarNFe() {
  const html = `<body style="font-family:sans-serif;text-align:center;padding:15px;">
    <h3 style="color:#d9534f;">📄 Estornar Nota (XML)</h3>
    <input type="file" id="f" accept=".xml" style="margin:10px 0;"><br>
    <button id="b" style="background:#d9534f;color:#fff;border:none;padding:10px 20px;font-weight:bold;border-radius:4px;cursor:pointer;" onclick="p()">Estornar</button>
    <div id="st" style="margin-top:10px;font-size:12px;"></div>
    <script>
      function p(){
        var f=document.getElementById('f').files[0]; if(!f) return alert('Selecione XML!');
        document.getElementById('b').disabled=true; document.getElementById('st').innerText='⏳ Lendo XML para estorno...';
        var r=new FileReader(); r.onload=e=>google.script.run.withSuccessHandler(m=>{document.getElementById('st').innerText='✅ '+m; setTimeout(()=>google.script.host.close(),2000)}).withFailureHandler(e=>{document.getElementById('st').innerText='❌ '+e.message; document.getElementById('b').disabled=false;}).estornarXMLNFe(e.target.result);
        r.readAsText(f);
      }
    </script>
  </body>`;
  SpreadsheetApp.getUi().showModalDialog(HtmlService.createHtmlOutput(html).setWidth(350).setHeight(200), ' ');
}

function estornarXMLNFe(xmlString) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet(), lastRow = sheet.getLastRow();
  if (lastRow < 6) throw new Error("A planilha está vazia.");

  const pEan = {}, pDesc = {};
  sheet.getRange(6, 1, lastRow - 5, 3).getValues().forEach((v, r) => {
    const ean = String(v[0]).replace(/\D/g, '').trim();
    const norm = normalizarTexto(v[2]);
    const row = r + 6;
    if (ean.length >= 8) pEan[ean] = row;
    if (norm) pDesc[norm] = row;
  });

  const itens = xmlString.match(/<det[\s\S]*?<\/det>/g);
  if (!itens) throw new Error("Nenhum item válido no XML.");

  const tag = (xml, t) => (xml.match(new RegExp(`<${t}>([\\s\\S]*?)<\/${t}>`, "i")) || [])[1]?.trim() || "";
  const alteracoes = {};

  itens.forEach(item => {
    let ean = tag(item, 'cEAN');
    if (!ean || ean.toUpperCase() === 'SEM GTIN') ean = "";
    ean = String(ean).replace(/\D/g, '').trim();

    const xProd = limparDescricao(tag(item, 'xProd'));
    const norm = normalizarTexto(xProd);
    const qCom = parseFloat(tag(item, 'qCom')) || 0;
    const fator = extrairFator("", xProd);
    const qtdEnt = qCom * fator;

    let row = (ean && pEan[ean]) ? pEan[ean] : pDesc[norm];

    if (!row && norm.length >= 3) {
      for (let k in pDesc) {
        if (k.includes(norm) || norm.includes(k)) {
          row = pDesc[k];
          break;
        }
      }
    }

    if (row) {
      alteracoes[row] = (alteracoes[row] || 0) + qtdEnt;
    }
  });

  const rowsToDel = [];
  let at = 0;
  const rows = Object.keys(alteracoes).map(Number).sort((a, b) => b - a);

  rows.forEach(row => {
    const qSub = alteracoes[row];
    const qAtual = parseFloat(sheet.getRange(row, 11).getValue()) || 0;
    const qTot = qAtual - qSub;

    if (qTot <= 0) {
      rowsToDel.push(row);
    } else {
      sheet.getRange(row, 11).setValue(qTot);
      atualizarValoresEMargem(sheet, row);
      at++;
    }
  });

  rowsToDel.forEach(r => sheet.deleteRow(r));
  return `Estorno concluído! Atualizados: ${at} | Itens Removidos: ${rowsToDel.length}`;
}

function abrirJanelaEstornarPDF() {
  const html = `<body style="font-family:sans-serif;text-align:center;padding:15px;">
    <h3 style="color:#d9534f;">🧾 Estornar Nota (PDF)</h3>
    <input type="file" id="f" accept=".pdf" style="margin:10px 0;"><br>
    <button id="b" style="background:#d9534f;color:#fff;border:none;padding:10px 20px;font-weight:bold;border-radius:4px;cursor:pointer;" onclick="p()">Estornar PDF</button>
    <div id="st" style="margin-top:10px;font-size:12px;"></div>
    <script>
      function p(){
        var f=document.getElementById('f').files[0]; if(!f) return alert('Selecione PDF!');
        document.getElementById('b').disabled=true; document.getElementById('st').innerText='⏳ Lendo PDF para estorno...';
        var r=new FileReader(); r.onload=e=>google.script.run.withSuccessHandler(m=>{document.getElementById('st').innerText='✅ '+m; setTimeout(()=>google.script.host.close(),2500)}).withFailureHandler(e=>{document.getElementById('st').innerText='❌ '+e.message; document.getElementById('b').disabled=false;}).estornarPDF(e.target.result.split(',')[1], f.name);
        r.readAsDataURL(f);
      }
    </script>
  </body>`;
  SpreadsheetApp.getUi().showModalDialog(HtmlService.createHtmlOutput(html).setWidth(350).setHeight(200), ' ');
}

function estornarPDF(base64Data, fileName) {
  if (!base64Data) throw new Error("PDF inválido.");
  const blob = Utilities.newBlob(Utilities.base64Decode(base64Data), 'application/pdf', fileName);
  let docFile;
  try {
    docFile = Drive.Files.create({ name: fileName, mimeType: MimeType.GOOGLE_DOCS }, blob, { ocrLanguage: 'pt' });
  } catch (e) {
    throw new Error("Ative a 'Drive API' nos Serviços Avançados do Google Apps Script.");
  }
  const doc = DocumentApp.openById(docFile.id);
  const textoPDF = doc.getBody().getText();
  try { DriveApp.getFileById(docFile.id).setTrashed(true); } catch (e) {}
  if (!textoPDF.trim()) throw new Error("Texto em branco no PDF.");

  // Mesma abordagem do processarPDF: lê direto do texto do OCR, sem API externa.
  const textoProdutos = cortarRodapeNota(textoPDF);

  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet(), lastRow = sheet.getLastRow();
  if (lastRow < 6) throw new Error("Planilha vazia.");

  const pEan = {}, pDesc = {};
  sheet.getRange(6, 1, lastRow - 5, 3).getValues().forEach((v, r) => {
    const ean = String(v[0]).replace(/\D/g, '').trim(), norm = normalizarTexto(v[2]), row = r + 6;
    if (ean.length >= 8) pEan[ean] = row;
    if (norm) pDesc[norm] = row;
  });

  const linhasBrutas = textoProdutos.replace(/\r\n/g, '\n').replace(/(789\d{10}|790\d{10}|\b\d{13,14}\b)/g, '\n$1').split('\n');
  const linhas = mesclarLinhasProdutoPDF(linhasBrutas);
  const alteracoes = {};

  linhas.forEach(linha => {
    const l = linha.trim();
    if (l.length < 5 || /^(danfe|nota fiscal|cnpj\b|total\b|subtotal\b)/i.test(l)) return;
    const precos = l.match(/\b\d+[\.,]\d{2}\b/g);
    if (precos) {
      const eanLido = (l.match(/\b(789\d{10}|790\d{10}|\d{13,14})\b/) || [])[0] || "";
      const matchQtd = l.match(/(\d+)\s*x\s*/i);
      const qtd = matchQtd ? (parseFloat(matchQtd[1]) || 1) : 1;
      const nomeProd = limparDescricao(l), norm = normalizarTexto(nomeProd);

      if (norm.length >= 3) {
        let row = (eanLido && pEan[eanLido]) ? pEan[eanLido] : pDesc[norm];
        if (!row) {
          for (let k in pDesc) { if (k.includes(norm) || norm.includes(k)) { row = pDesc[k]; break; } }
        }
        if (row) {
          const fator = extrairFator("", nomeProd), qtdEnt = qtd * fator;
          alteracoes[row] = (alteracoes[row] || 0) + qtdEnt;
        }
      }
    }
  });

  const rowsToDel = [];
  let at = 0;
  const rows = Object.keys(alteracoes).map(Number).sort((a, b) => b - a);

  rows.forEach(row => {
    const qSub = alteracoes[row];
    const qAtual = parseFloat(sheet.getRange(row, 11).getValue()) || 0;
    const qTot = qAtual - qSub;
    if (qTot <= 0) {
      rowsToDel.push(row);
    } else {
      sheet.getRange(row, 11).setValue(qTot);
      atualizarValoresEMargem(sheet, row);
      at++;
    }
  });

  rowsToDel.forEach(r => sheet.deleteRow(r));
  return `Estorno concluído! Atualizados: ${at} | Itens Removidos: ${rowsToDel.length}`;
}

// ============================================================
// 12. MANUTENÇÃO E FORMATAÇÃO DA TABELA
// ============================================================
function limparEFormatardalinha6() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const maxRows = sheet.getMaxRows();
  if (maxRows < 6) return;
  const maxCols = Math.max(sheet.getMaxColumns(), 13);
  sheet.getRange("L1:L4").clearContent().clearDataValidations();
  sheet.getRange(6, 1, maxRows - 5, maxCols)
    .clearDataValidations()
    .setBorder(false, false, false, false, false, false);
  const descricoes = sheet.getRange(6, 3, maxRows - 5, 1).getValues();
  const eans = sheet.getRange(6, 1, maxRows - 5, 1).getValues();
  for (let i = 0; i < descricoes.length; i++) {
    const row = i + 6;
    const temProduto = String(descricoes[i][0]).trim() !== "" || String(eans[i][0]).trim() !== "";
    aplicarEstiloLinha(sheet, row, temProduto);
    if (temProduto) atualizarValoresEMargem(sheet, row);
  }
  SpreadsheetApp.getUi().alert("✅ Coluna L e tabela formatadas com sucesso!");
}

/**
 * ============================================================================
 * ESTOQUE — CADASTRO DE SERVIÇO / FÓRMULA
 * Cole no FINAL do Código.gs do Estoque (não apaga nada, só acrescenta).
 * ============================================================================
 *
 * Serve pra serviços compostos por vários materiais (tipo uma receita/fórmula):
 * você cadastra os materiais usados com seus custos, define uma % de mão de obra
 * em cima do custo total dos materiais, e o preço final do serviço calcula sozinho.
 *
 * Fica guardado num bloco de COLUNAS PRÓPRIO (N em diante), separado da lista de
 * produtos — assim nunca colide com o cadastro normal de produtos de revenda.
 * Cada serviço ganha um código próprio ("SERV-001", "SERV-002"...) compartilhado
 * entre todas as suas linhas de material.
 */

const COL_INICIO_SERVICOS_ESTOQUE = 14; // Coluna N

function abrirJanelaServicosEstoque() {
  const html = HtmlService.createHtmlOutput(getHtmlServicosEstoque()).setWidth(520).setHeight(760);
  SpreadsheetApp.getUi().showModalDialog(html, "🛠️ Serviço / Fórmula");
}

function configurarBlocoServicosEstoque() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  sheet.getRange(5, COL_INICIO_SERVICOS_ESTOQUE, 1, 6).setValues([[
    "CÓDIGO SERVIÇO", "NOME DO SERVIÇO", "MATERIAL", "CUSTO UNIT. (R$)", "QTD", "% MÃO DE OBRA"
  ]]).setFontWeight("bold");
  sheet.setColumnWidth(COL_INICIO_SERVICOS_ESTOQUE + 1, 180);
  sheet.setColumnWidth(COL_INICIO_SERVICOS_ESTOQUE + 2, 180);
  SpreadsheetApp.getUi().alert("✅ Bloco de Serviços criado (colunas N em diante)!");
}

function obterProximoCodigoServicoEstoque() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const lastRow = sheet.getLastRow();
  if (lastRow < 6) return "SERV-001";

  const codigos = sheet.getRange(6, COL_INICIO_SERVICOS_ESTOQUE, lastRow - 5, 1).getValues();
  let maiorNumero = 0;
  codigos.forEach(r => {
    const m = String(r[0] || "").match(/SERV-(\d+)/);
    if (m) maiorNumero = Math.max(maiorNumero, parseInt(m[1], 10));
  });
  return "SERV-" + String(maiorNumero + 1).padStart(3, "0");
}

function obterListaServicosEstoque() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const lastRow = sheet.getLastRow();
  if (lastRow < 6) return [];

  const dados = sheet.getRange(6, COL_INICIO_SERVICOS_ESTOQUE, lastRow - 5, 6).getValues();
  const grupos = {};

  dados.forEach(row => {
    const codigo = String(row[0] || "").trim();
    if (!codigo) return;

    if (!grupos[codigo]) {
      grupos[codigo] = { codigo, nome: row[1] || "", percMaoObra: parseFloat(row[5]) || 0, materiais: [] };
    }
    grupos[codigo].materiais.push({
      material: row[2] || "",
      custoUnit: parseFloat(row[3]) || 0,
      qtd: parseFloat(row[4]) || 0
    });
  });

  return Object.values(grupos).map(s => {
    const totalMateriais = s.materiais.reduce((soma, m) => soma + (m.custoUnit * m.qtd), 0);
    const valorMaoObra = totalMateriais * (s.percMaoObra / 100);
    const precoFinal = totalMateriais + valorMaoObra;
    return { ...s, totalMateriais, valorMaoObra, precoFinal };
  });
}

function salvarServicoEstoque(dados) {
  try {
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

    if (String(sheet.getRange(5, COL_INICIO_SERVICOS_ESTOQUE).getValue()).trim() === "") {
      sheet.getRange(5, COL_INICIO_SERVICOS_ESTOQUE, 1, 6).setValues([[
        "CÓDIGO SERVIÇO", "NOME DO SERVIÇO", "MATERIAL", "CUSTO UNIT. (R$)", "QTD", "% MÃO DE OBRA"
      ]]).setFontWeight("bold");
    }

    if (!dados.materiais || dados.materiais.length === 0) {
      return { sucesso: false, mensagem: "⚠️ Adicione pelo menos um material." };
    }

    const codigo = obterProximoCodigoServicoEstoque();
    const percMaoObra = parseFloat(dados.percMaoObra) || 0;

    dados.materiais.forEach(mat => {
      let linha = 6;
      while (String(sheet.getRange(linha, COL_INICIO_SERVICOS_ESTOQUE).getValue()).trim() !== "") linha++;

      sheet.getRange(linha, COL_INICIO_SERVICOS_ESTOQUE, 1, 6).setValues([[
        codigo, dados.nome, mat.desc, parseFloat(mat.custo) || 0, parseFloat(mat.qtd) || 1, percMaoObra
      ]]);
      sheet.getRange(linha, COL_INICIO_SERVICOS_ESTOQUE + 3).setNumberFormat("R$ #,##0.00");
    });

    return { sucesso: true, mensagem: "✅ Serviço \"" + dados.nome + "\" cadastrado como " + codigo + "!" };
  } catch (e) {
    return { sucesso: false, mensagem: "❌ Erro: " + e.message };
  }
}

function excluirServicoEstoque(codigo) {
  try {
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    const lastRow = sheet.getLastRow();
    if (lastRow < 6) return { sucesso: true, mensagem: "Nada pra excluir." };

    const codigos = sheet.getRange(6, COL_INICIO_SERVICOS_ESTOQUE, lastRow - 5, 1).getValues();
    codigos.forEach((row, i) => {
      if (String(row[0] || "").trim() === codigo) {
        sheet.getRange(i + 6, COL_INICIO_SERVICOS_ESTOQUE, 1, 6).clearContent();
      }
    });

    return { sucesso: true, mensagem: "✅ Serviço excluído!" };
  } catch (e) {
    return { sucesso: false, mensagem: "❌ Erro: " + e.message };
  }
}

function getHtmlServicosEstoque() {
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
        .salvarServicoEstoque({
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
            google.script.run.withSuccessHandler(function() { carregarServicos(); }).excluirServicoEstoque(s.codigo);
          };
          div.appendChild(card);
        });
      }).obterListaServicosEstoque();
    }

    window.onload = carregarServicos;
  </script>
</body>
</html>`;
}

/**
 * ============================================================================
 * ESTOQUE — ESTOQUE MÍNIMO AUTOMÁTICO (Curva ABC + Média de Vendas)
 * Cole no FINAL do Código.gs do Estoque (não apaga nada, só acrescenta).
 * Precisa da coluna N "ESTOQUE MÍNIMO" já criada (rode adicionarColunaEstoqueMinimo
 * antes, se ainda não tiver).
 * ============================================================================
 *
 * A ideia: em vez de você decidir um mínimo "no olho" pra cada produto, o
 * sistema calcula sozinho combinando duas coisas:
 *
 * 1. CURVA ABC — quanto cada produto representa da receita (Classe A = os que
 *    mais vendem, C = os que menos vendem), olhando o Histórico de vendas.
 * 2. MÉDIA DE VENDAS — quantas unidades esse produto vende por semana, em média.
 *
 * Estoque Mínimo = Média Semanal × Semanas de Cobertura, onde as semanas de
 * cobertura variam pela classe: produto Classe A (seus "carros-chefe") ganha
 * mais semanas de reserva, porque um estoque zerado neles pesa mais no caixa;
 * Classe C ganha menos, porque é giro baixo e não compensa empatar capital.
 *
 * ⚠️ Confira o nome da aba principal de vendas dentro do Histórico compartilhado
 * — esse código assume que é a PRIMEIRA aba daquela planilha. Se não for, troca
 * a linha `ssHist.getSheets()[0]` pelo nome certo (ex: `.getSheetByName("Vendas")`).
 */

const ID_PLANILHA_HISTORICO_VENDAS = "1119HW8n6Ma-H83wbLw9I13bTJ9EgJhhpciPFyyaUXI8";

/**
 * Config salva (sem precisar perguntar toda vez): quantas semanas de cobertura
 * pra Classe C. Muda uma vez aqui, ou chama salvarSemanasBaseEstoqueMinimo(x).
 */
function obterSemanasBaseEstoqueMinimo() {
  const v = PropertiesService.getScriptProperties().getProperty('SEMANAS_BASE_ESTOQUE_MINIMO');
  return parseFloat(v) || 1;
}

function salvarSemanasBaseEstoqueMinimo(semanas) {
  PropertiesService.getScriptProperties().setProperty('SEMANAS_BASE_ESTOQUE_MINIMO', String(parseFloat(semanas) || 1));
}

/**
 * Liga o cálculo automático: cria um gatilho que roda sozinho toda
 * segunda-feira de manhã, sem precisar clicar em nada. Rode essa função UMA
 * VEZ (pelo editor do Apps Script) pra ativar.
 */
function ativarCalculoEstoqueMinimoAutomatico() {
  // Remove gatilho antigo, se já existir, pra não ficar duplicando.
  ScriptApp.getProjectTriggers().forEach(t => {
    if (t.getHandlerFunction() === 'calcularEstoqueMinimoAutomaticoSilencioso') ScriptApp.deleteTrigger(t);
  });

  ScriptApp.newTrigger('calcularEstoqueMinimoAutomaticoSilencioso')
    .timeBased()
    .onWeekDay(ScriptApp.WeekDay.MONDAY)
    .atHour(6)
    .create();

  SpreadsheetApp.getUi().alert(
    "✅ Cálculo automático ativado! Vai rodar sozinho toda segunda-feira de manhã, " +
    "usando " + obterSemanasBaseEstoqueMinimo() + " semana(s) de base pra Classe C.\n\n" +
    "Pra mudar esse número, rode salvarSemanasBaseEstoqueMinimo(x) pelo editor, " +
    "trocando x pelo valor que quiser."
  );
}

/**
 * Versão que roda sozinha pelo gatilho — sem prompt, sem alert (gatilhos automáticos
 * não têm tela pra mostrar nada). Os resultados vão pro Registro de Execução (Logger).
 */
function calcularEstoqueMinimoAutomaticoSilencioso() {
  calcularEstoqueMinimoAutomaticoInterno(obterSemanasBaseEstoqueMinimo(), false);
}

/**
 * Versão manual, com pergunta na tela — pra rodar avulsa quando quiser testar
 * ou forçar um recálculo na hora, sem esperar a segunda-feira.
 */
function calcularEstoqueMinimoAutomatico() {
  const ui = SpreadsheetApp.getUi();
  const resp = ui.prompt(
    "📊 Estoque Mínimo Automático",
    "Quantas semanas de cobertura pra Classe C (giro baixo)? Classe B usa o dobro, Classe A usa o triplo.\n(Ex: digite 1)",
    ui.ButtonSet.OK_CANCEL
  );
  if (resp.getSelectedButton() !== ui.Button.OK) return;
  const semanasBase = parseFloat(resp.getResponseText()) || 1;
  salvarSemanasBaseEstoqueMinimo(semanasBase); // guarda pra o gatilho automático usar o mesmo valor depois
  calcularEstoqueMinimoAutomaticoInterno(semanasBase, true);
}

/**
 * O cálculo de verdade — mostraAlerta=true só quando chamado manualmente.
 */
function calcularEstoqueMinimoAutomaticoInterno(semanasBase, mostrarAlerta) {
  function avisar(msg) {
    if (mostrarAlerta) SpreadsheetApp.getUi().alert(msg);
    else Logger.log(msg);
  }

  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("ESTOQUE") || SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const lastRow = sheet.getLastRow();
  if (lastRow < 6) { avisar("Nenhum produto cadastrado."); return; }

  if (String(sheet.getRange(5, 14).getValue()).trim().toUpperCase() !== "ESTOQUE MÍNIMO") {
    avisar("A coluna N \"ESTOQUE MÍNIMO\" ainda não existe. Rode 'adicionarColunaEstoqueMinimo' primeiro.");
    return;
  }

  const produtos = sheet.getRange(6, 1, lastRow - 5, 11).getValues()
    .map((row, i) => ({ linha: i + 6, desc: String(row[2] || "").trim(), receita: 0, qtdVendida: 0 }))
    .filter(p => p.desc);

  if (produtos.length === 0) { avisar("Nenhum produto com descrição encontrado."); return; }

  let dataMaisAntiga = null, dataMaisRecente = null;

  try {
    const ssHist = SpreadsheetApp.openById(ID_PLANILHA_HISTORICO_VENDAS);
    const sheetHist = ssHist.getSheets()[0]; // ⚠️ confira se essa é mesmo a aba principal de vendas
    const lastRowHist = sheetHist.getLastRow();

    if (lastRowHist >= 2) {
      const dadosHist = sheetHist.getRange(2, 1, lastRowHist - 1, 13).getValues();

      dadosHist.forEach(row => {
        const categoria = String(row[5] || "");
        if (categoria === "CREDIARIO" || categoria === "Assinatura" || categoria === "Serviço") return;

        const descVenda = normalizarTexto(String(row[4] || ""));
        if (!descVenda) return;
        const valor = parseFloat(row[6]) || 0;
        const qtd = parseFloat(row[7]) || 0;
        const dtObj = row[0] instanceof Date ? row[0] : null;

        let melhorProduto = null, melhorScore = 0;
        produtos.forEach(p => {
          const descProd = normalizarTexto(p.desc);
          let score = 0;
          if (descProd === descVenda) score = 100;
          else if (descProd.includes(descVenda) || descVenda.includes(descProd)) score = 80;
          if (score > melhorScore) { melhorScore = score; melhorProduto = p; }
        });

        if (melhorProduto && melhorScore >= 80) {
          melhorProduto.receita += valor;
          melhorProduto.qtdVendida += qtd;
        }

        if (dtObj) {
          if (!dataMaisAntiga || dtObj < dataMaisAntiga) dataMaisAntiga = dtObj;
          if (!dataMaisRecente || dtObj > dataMaisRecente) dataMaisRecente = dtObj;
        }
      });
    }
  } catch (e) {
    avisar("❌ Erro ao ler o Histórico de vendas: " + e.message);
    return;
  }

  if (!dataMaisAntiga || !dataMaisRecente) {
    avisar("Não encontrei vendas no Histórico pra calcular a média — confira se o link e a aba estão certos.");
    return;
  }

  const semanasNoPeriodo = Math.max(1, (dataMaisRecente.getTime() - dataMaisAntiga.getTime()) / (7 * 24 * 60 * 60 * 1000));

  const receitaTotal = produtos.reduce((s, p) => s + p.receita, 0);
  const ordenados = produtos.slice().sort((a, b) => b.receita - a.receita);
  let acumulado = 0;
  ordenados.forEach(p => {
    acumulado += p.receita;
    const pctAcumulado = receitaTotal > 0 ? acumulado / receitaTotal : 1;
    if (pctAcumulado <= 0.80) p.classe = "A";
    else if (pctAcumulado <= 0.95) p.classe = "B";
    else p.classe = "C";
  });

  const multiplicador = { A: 3, B: 2, C: 1 };
  let atualizados = 0;

  produtos.forEach(p => {
    const mediaSemanal = p.qtdVendida / semanasNoPeriodo;
    const semanasCobertura = semanasBase * (multiplicador[p.classe] || 1);
    const minimoSugerido = Math.ceil(mediaSemanal * semanasCobertura);

    if (minimoSugerido > 0) {
      sheet.getRange(p.linha, 14).setValue(minimoSugerido);
      atualizados++;
    }
  });

  avisar(
    "✅ Estoque Mínimo calculado pra " + atualizados + " produto(s)! " +
    "(Classe A: " + (semanasBase * 3) + " sem., B: " + (semanasBase * 2) + " sem., C: " + semanasBase + " sem.)"
  );
}