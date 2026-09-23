/**
 * ============================================================================
 * COTAÇÃO DE COMPRAS — arquivo NOVO e SEPARADO (não é aba do CFAUTO nem do Estoque).
 * Cole esse código inteiro numa planilha do Google Sheets em branco (Extensões >
 * Apps Script). Precisa de 3 abas: "Cotação", "Fornecedores" e "Histórico de Pedidos"
 * — rode "configurarSistemaCotacao" uma vez que ele cria as 3 sozinho.
 * ============================================================================
 *
 * FLUXO COMPLETO:
 * 1. Cadastra os fornecedores (nome, representante, contatos, condições).
 * 2. Exporta uma cotação em branco (Produto/Preço/OBS) pra mandar pro representante.
 * 3. Quando ele devolve preenchida, importa de volta — tudo cai na MESMA aba
 *    Cotação (nunca cria aba nova), uma coluna por fornecedor.
 * 4. Recalcula: acha o menor preço, e sugere quanto comprar com base no preço
 *    (mais barato que o último pago = compra mais; mais caro = compra menos) e
 *    na venda semanal média, pra cobrir X semanas que você escolhe na hora.
 * 5. Janela de Finalizar Pedido: vai fornecedor por fornecedor, ajusta
 *    quantidade, respeita pedido mínimo, oferece a segunda opção se você
 *    recusar um item.
 * 6. Exporta o pedido final em texto, um arquivo por fornecedor.
 * 7. No final, limpa a Cotação pro próximo ciclo (o Último Preço Pago fica
 *    guardado, pra comparar da próxima vez).
 */

const NOME_ABA_COTACAO = "Cotação";
const NOME_ABA_HIST_PEDIDOS = "HISTORICO PEDIDOS"; // aba já existente no HISTÓRICO compartilhado
const ID_PLANILHA_ESTOQUE_COTACAO = "1aPr4-chXwNE19RWIXgOPceB-OmF31Ft5SgtugEPwoMA";
const ID_PLANILHA_HISTORICO_COTACAO = "1119HW8n6Ma-H83wbLw9I13bTJ9EgJhhpciPFyyaUXI8";
const COL_INICIO_RESUMO = 6; // Coluna F — tabela de comparação (Menor Preço, etc.)
const LINHA_TITULO = 7;
const LINHA_CABECALHO = 8;
const LINHA_PRIMEIRO_DADO = 9;

function onOpen() {
  // Intencionalmente vazio — use botões desenhados, sem menu.
}

function removerAcentosCotacao(txt) {
  return String(txt || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase().trim();
}

/**
 * Cria as 3 abas do zero, com os cabeçalhos certos. Rode uma vez, no começo.
 */
/**
 * Garante que a aba Cotação existe com a estrutura certa (área crua A-C +
 * resumo F+) — chamada automaticamente sempre que alguma ação precisa dela,
 * sem obrigar a pessoa a rodar "Configurar Sistema" antes. Fornecedores não
 * moram mais aqui — ficam nas Propriedades do documento (ver CHAVE_FORNECEDORES).
 */
function garantirEstruturaCotacao() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(NOME_ABA_COTACAO);
  const resumoOk = sheet && String(sheet.getRange(LINHA_CABECALHO, COL_INICIO_RESUMO).getValue()).trim().toUpperCase() === "PRODUTO";
  if (resumoOk) return sheet;

  if (!sheet) {
    // Não cria uma aba nova do zero — reaproveita a primeira aba da planilha
    // (a "Página1" padrão que o Google já cria) e só renomeia ela, pra não
    // ficar com duas abas soltas.
    sheet = ss.getSheets()[0];
    sheet.setName(NOME_ABA_COTACAO);
  }

  sheet.getRange(LINHA_TITULO, 1).setValue("📋 COTAÇÃO DE COMPRAS").setFontWeight("bold").setFontSize(14);

  // Área CRUA (A-C): cada cotação importada entra como um bloco — uma faixa preta
  // com o nome do fornecedor, seguida das linhas de Produto/Preço/OBS daquele
  // fornecedor. Vários fornecedores ficam empilhados, um bloco embaixo do outro.
  sheet.getRange(LINHA_CABECALHO, 1, 1, 3).setValues([["PRODUTO", "PREÇO", "OBS"]]).setFontWeight("bold").setBackground("#0f172a").setFontColor("#ffffff");
  sheet.setColumnWidth(1, 280);

  // Área de RESUMO (F em diante): tabela calculada — pra cada produto, o menor
  // preço achado entre todos os blocos de fornecedor, quem ofereceu, etc.
  const headersResumo = [
    "PRODUTO", "ESTOQUE ATUAL", "VENDA SEMANAL MÉDIA", "ÚLTIMO PREÇO PAGO",
    "MENOR PREÇO", "FORNECEDOR VENCEDOR", "SEGUNDA OPÇÃO", "SEGUNDO FORNECEDOR",
    "QTD SUGERIDA", "QTD A PEDIR", "VALOR DO PEDIDO"
  ];
  sheet.getRange(LINHA_CABECALHO, COL_INICIO_RESUMO, 1, headersResumo.length).setValues([headersResumo]).setFontWeight("bold").setBackground("#334155").setFontColor("#ffffff");
  sheet.setColumnWidth(COL_INICIO_RESUMO, 280);
  sheet.setFrozenRows(LINHA_CABECALHO);

  return sheet;
}

function configurarSistemaCotacao() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheetCot = ss.getSheetByName(NOME_ABA_COTACAO);
  if (sheetCot) sheetCot.clear(); // reconfiguração manual: limpa tudo e recria do zero

  garantirEstruturaCotacao();
  garantirAbaPedidosNoHistorico();

  SpreadsheetApp.getUi().alert(
    "✅ Sistema de Cotação configurado, tudo numa aba só!\n\n" +
    "O bloco de Fornecedores fica escondido (colunas P em diante) — mexa nele só pela janela " +
    "'🏢 Fornecedores', não precisa mostrar as colunas.\n\n" +
    "O Histórico de Pedidos vai direto pra planilha de Histórico compartilhada, não fica aqui."
  );
}

/**
 * Garante que existe uma aba "Pedidos de Compra" na planilha de Histórico
 * compartilhada (a mesma que o Caixa usa) — cria com cabeçalho se não existir.
 */
function garantirAbaPedidosNoHistorico() {
  const ssHist = SpreadsheetApp.openById(ID_PLANILHA_HISTORICO_COTACAO);
  let sheetHist = ssHist.getSheetByName(NOME_ABA_HIST_PEDIDOS);
  if (!sheetHist) {
    sheetHist = ssHist.insertSheet(NOME_ABA_HIST_PEDIDOS);
    sheetHist.getRange(1, 1, 1, 7).setValues([["DATA", "FORNECEDOR", "PRODUTO", "QUANTIDADE", "PREÇO UNIT.", "VALOR TOTAL", "ESTOQUE NO MOMENTO"]]).setFontWeight("bold");
    sheetHist.setFrozenRows(1);
  }
  return sheetHist;
}

// ============================================================================
// CADASTRO DE FORNECEDOR
// ============================================================================

function abrirJanelaFornecedores() {
  const html = HtmlService.createHtmlOutput(getHtmlFornecedores()).setWidth(520).setHeight(760);
  SpreadsheetApp.getUi().showModalDialog(html, "🏢 Fornecedores");
}

/**
/**
 * Fornecedores vivem nas Propriedades do documento (guardados como JSON) — não
 * numa célula, não numa coluna, não numa aba. Isso elimina de vez qualquer
 * bug de "achou a coluna errada", porque não existe coluna nenhuma envolvida.
 */
const CHAVE_FORNECEDORES = "FORNECEDORES_LISTA_JSON";

function obterListaFornecedoresCompleta() {
  const json = PropertiesService.getDocumentProperties().getProperty(CHAVE_FORNECEDORES);
  if (!json) return [];
  try {
    return JSON.parse(json);
  } catch (e) {
    return [];
  }
}

function salvarFornecedor(dados) {
  try {
    const lista = obterListaFornecedoresCompleta();

    if (dados.id) {
      const idx = lista.findIndex(f => f.id === dados.id);
      if (idx !== -1) {
        lista[idx] = { ...dados, pedidoMinimo: parseFloat(dados.pedidoMinimo) || 0 };
      } else {
        lista.push({ ...dados, pedidoMinimo: parseFloat(dados.pedidoMinimo) || 0 });
      }
    } else {
      dados.id = "forn_" + new Date().getTime();
      dados.pedidoMinimo = parseFloat(dados.pedidoMinimo) || 0;
      lista.push(dados);
    }

    PropertiesService.getDocumentProperties().setProperty(CHAVE_FORNECEDORES, JSON.stringify(lista));
    return { sucesso: true, mensagem: "✅ Fornecedor \"" + dados.nome + "\" salvo!" };
  } catch (e) {
    return { sucesso: false, mensagem: "❌ Erro: " + e.message };
  }
}

function excluirFornecedor(id) {
  try {
    const lista = obterListaFornecedoresCompleta().filter(f => f.id !== id);
    PropertiesService.getDocumentProperties().setProperty(CHAVE_FORNECEDORES, JSON.stringify(lista));
    return { sucesso: true, mensagem: "✅ Excluído!" };
  } catch (e) {
    return { sucesso: false, mensagem: "❌ Erro: " + e.message };
  }
}

function getHtmlFornecedores() {
  return `<!DOCTYPE html>
<html>
<head>
  <base target="_top">
  <style>
    * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, sans-serif; }
    body { margin: 0; padding: 16px; font-size: 12px; color: #333; background: #f8f9fa; }
    label { font-weight: bold; font-size: 11px; color: #475569; display: block; margin-bottom: 3px; margin-top: 8px; }
    input { width: 100%; padding: 7px; border-radius: 6px; border: 1px solid #cbd5e1; font-size: 12px; }
    .row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .btn { width: 100%; padding: 9px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; background: #16a34a; color: white; margin-top: 12px; }
    .box { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; margin-top: 10px; }
    #status { text-align: center; font-weight: bold; margin-top: 8px; min-height: 18px; }
    .secao-lista { margin-top: 18px; border-top: 2px solid #cbd5e1; padding-top: 10px; }
    .forn-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px 10px; margin-bottom: 6px; font-size: 11px; }
    .forn-card .nome { font-weight: bold; font-size: 12px; }
    .acoes { display: flex; gap: 10px; margin-top: 4px; }
    .acoes span { cursor: pointer; color: #0284c7; font-size: 10px; }
    .acoes .del { color: #dc3545; }
  </style>
</head>
<body>
  <div id="id-editando" style="display:none;"></div>
  <label>Nome da Empresa: <span style="color:#dc3545;">*</span></label>
  <input type="text" id="f-nome">

  <label>Representante: <span style="color:#dc3545;">*</span></label>
  <input type="text" id="f-representante">

  <label>Contato Pós-Venda (trocas / devolução / problemas): <span style="color:#dc3545;">*</span></label>
  <input type="text" id="f-posvenda" oninput="sincronizarContato()">

  <label style="display:flex;align-items:center;gap:5px;font-weight:normal;font-size:11px;margin-top:6px;">
    <input type="checkbox" id="f-mesmo-contato" style="width:auto;" onchange="alternarMesmoContato()"> É o mesmo contato pra cotação
  </label>

  <div id="bloco-contato-cotacao">
    <label>Contato pra Envio de Cotação (WhatsApp/e-mail do rep. de vendas): <span style="color:#dc3545;">*</span></label>
    <input type="text" id="f-cotacao">
  </div>

  <div class="row2">
    <div>
      <label>Forma de Pagamento</label>
      <select id="f-pagamento">
        <option value="Boleto">Boleto</option>
        <option value="Boleto Parcelado">Boleto Parcelado</option>
        <option value="Cartão">Cartão</option>
        <option value="PIX">PIX</option>
        <option value="Dinheiro">Dinheiro</option>
        <option value="Outros">Outros</option>
      </select>
    </div>
    <div><label>Pedido Mínimo (R$)</label><input type="number" step="0.01" id="f-minimo" value="0"></div>
  </div>
  <div class="row2">
    <div>
      <label>Prazo de Entrega</label>
      <div style="display:flex;gap:6px;align-items:center;">
        <input type="number" min="0" id="f-entrega-dias" placeholder="dias" oninput="document.getElementById('f-entrega-neg').checked=false;">
        <label style="display:flex;align-items:center;gap:4px;font-weight:normal;font-size:10px;white-space:nowrap;margin:0;">
          <input type="checkbox" id="f-entrega-neg" style="width:auto;" onchange="if(this.checked) document.getElementById('f-entrega-dias').value='';"> Negociável
        </label>
      </div>
    </div>
    <div>
      <label>Prazo de Faturamento</label>
      <div style="display:flex;gap:6px;align-items:center;">
        <input type="number" min="0" id="f-faturamento-dias" placeholder="dias" oninput="document.getElementById('f-faturamento-neg').checked=false;">
        <label style="display:flex;align-items:center;gap:4px;font-weight:normal;font-size:10px;white-space:nowrap;margin:0;">
          <input type="checkbox" id="f-faturamento-neg" style="width:auto;" onchange="if(this.checked) document.getElementById('f-faturamento-dias').value='';"> Negociável
        </label>
      </div>
    </div>
  </div>

  <button class="btn" onclick="salvar()">💾 Salvar Fornecedor</button>
  <div id="status"></div>

  <div class="secao-lista">
    <div style="font-weight:bold;font-size:12px;margin-bottom:8px;">📋 Fornecedores Cadastrados</div>
    <div id="lista-fornecedores">Carregando...</div>
  </div>

  <script>
    function alternarMesmoContato() {
      const marcado = document.getElementById('f-mesmo-contato').checked;
      document.getElementById('bloco-contato-cotacao').style.display = marcado ? 'none' : 'block';
      if (marcado) sincronizarContato();
    }

    function sincronizarContato() {
      if (document.getElementById('f-mesmo-contato').checked) {
        document.getElementById('f-cotacao').value = document.getElementById('f-posvenda').value;
      }
    }

    function limparForm() {
      document.getElementById('id-editando').innerText = '';
      document.getElementById('f-mesmo-contato').checked = false;
      document.getElementById('bloco-contato-cotacao').style.display = 'block';
      ['f-nome','f-representante','f-posvenda','f-cotacao','f-entrega-dias','f-faturamento-dias'].forEach(function(id) {
        document.getElementById(id).value = '';
      });
      document.getElementById('f-pagamento').value = 'Boleto';
      document.getElementById('f-entrega-neg').checked = false;
      document.getElementById('f-faturamento-neg').checked = false;
      document.getElementById('f-minimo').value = '0';
    }

    function lerPrazo(idDias, idNeg) {
      if (document.getElementById(idNeg).checked) return 'Negociável';
      const dias = document.getElementById(idDias).value;
      return dias ? 'Até ' + dias + ' dias' : '';
    }

    function preencherPrazo(valor, idDias, idNeg) {
      if (valor === 'Negociável') {
        document.getElementById(idNeg).checked = true;
        document.getElementById(idDias).value = '';
      } else {
        document.getElementById(idNeg).checked = false;
        const m = String(valor || '').match(/(\d+)/);
        document.getElementById(idDias).value = m ? m[1] : '';
      }
    }

    function salvar() {
      const nome = document.getElementById('f-nome').value.trim();
      const representante = document.getElementById('f-representante').value.trim();
      const posVenda = document.getElementById('f-posvenda').value.trim();
      const contatoCotacao = document.getElementById('f-mesmo-contato').checked ? posVenda : document.getElementById('f-cotacao').value.trim();
      const st = document.getElementById('status');

      if (!nome || !representante || !posVenda || !contatoCotacao) {
        st.style.color = '#dc3545';
        st.innerText = '⚠️ Preencha Nome, Representante e os dois contatos — são obrigatórios.';
        return;
      }

      st.style.color = '#007bff';
      st.innerText = '⏳ Salvando...';

      google.script.run.withSuccessHandler(function(res) {
        st.style.color = res.sucesso ? '#107c41' : '#dc3545';
        st.innerText = res.mensagem;
        if (res.sucesso) { limparForm(); carregarFornecedores(); }
      }).withFailureHandler(function(err) {
        st.style.color = '#dc3545';
        st.innerText = '❌ Erro: ' + (err.message || err);
      }).salvarFornecedor({
        id: document.getElementById('id-editando').innerText || null,
        nome: nome,
        representante: representante,
        contatoPosVenda: posVenda,
        contatoCotacao: contatoCotacao,
        formaPagamento: document.getElementById('f-pagamento').value,
        prazoEntrega: lerPrazo('f-entrega-dias', 'f-entrega-neg'),
        prazoFaturamento: lerPrazo('f-faturamento-dias', 'f-faturamento-neg'),
        pedidoMinimo: document.getElementById('f-minimo').value
      });
    }

    function editar(f) {
      document.getElementById('id-editando').innerText = f.id;
      document.getElementById('f-nome').value = f.nome || '';
      document.getElementById('f-representante').value = f.representante || '';
      document.getElementById('f-posvenda').value = f.contatoPosVenda || '';
      document.getElementById('f-cotacao').value = f.contatoCotacao || '';
      const mesmo = f.contatoPosVenda && f.contatoCotacao && f.contatoPosVenda === f.contatoCotacao;
      document.getElementById('f-mesmo-contato').checked = mesmo;
      document.getElementById('bloco-contato-cotacao').style.display = mesmo ? 'none' : 'block';
      document.getElementById('f-pagamento').value = f.formaPagamento || 'Boleto';
      preencherPrazo(f.prazoEntrega, 'f-entrega-dias', 'f-entrega-neg');
      preencherPrazo(f.prazoFaturamento, 'f-faturamento-dias', 'f-faturamento-neg');
      document.getElementById('f-minimo').value = f.pedidoMinimo || 0;
      window.scrollTo(0, 0);
    }

    function carregarFornecedores() {
      google.script.run.withSuccessHandler(function(lista) {
        const div = document.getElementById('lista-fornecedores');
        div.innerHTML = '';
        if (!lista || lista.length === 0) {
          div.innerHTML = '<div style="color:#888;font-size:11px;">Nenhum fornecedor cadastrado ainda.</div>';
          return;
        }
        lista.forEach(function(f) {
          const card = document.createElement('div');
          card.className = 'forn-card';
          card.innerHTML = '<div class="nome">' + f.nome + (f.representante ? ' — ' + f.representante : '') + '</div>' +
            '<div>📞 Cotação: ' + (f.contatoCotacao || '—') + ' · Pós-venda: ' + (f.contatoPosVenda || '—') + '</div>' +
            '<div>💰 ' + (f.formaPagamento || '—') + ' · Entrega: ' + (f.prazoEntrega || '—') + ' · Fatura: ' + (f.prazoFaturamento || '—') + ' · Mín: R$ ' + (f.pedidoMinimo || 0).toFixed(2) + '</div>' +
            '<div class="acoes"><span class="edit">✏️ Editar</span><span class="del">🗑️ Excluir</span></div>';
          card.querySelector('.edit').onclick = function() { editar(f); };
          card.querySelector('.del').onclick = function() {
            google.script.run.withSuccessHandler(function() { carregarFornecedores(); }).excluirFornecedor(f.id);
          };
          div.appendChild(card);
        });
      }).obterListaFornecedoresCompleta();
    }

    window.onload = carregarFornecedores;
  </script>
</body>
</html>`;
}

// ============================================================================
// MAPEAMENTO DE COLUNAS DA COTAÇÃO
// ============================================================================

/**
 * Score de parecença entre dois nomes de produto — conta palavras em comum, dá
 * bônus se um nome "contém" o outro inteiro.
 */
function calcularScoreSimilaridade(a, b) {
  const na = removerAcentosCotacao(a), nb = removerAcentosCotacao(b);
  if (na === nb) return 100;
  if (na.includes(nb) || nb.includes(na)) return 80;

  const palavrasA = na.split(/\s+/).filter(p => p.length > 1);
  const palavrasB = nb.split(/\s+/).filter(p => p.length > 1);
  if (palavrasA.length === 0 || palavrasB.length === 0) return 0;

  let comuns = 0;
  palavrasA.forEach(pa => { if (palavrasB.includes(pa)) comuns++; });
  return (comuns / Math.max(palavrasA.length, palavrasB.length)) * 60;
}

/**
 * Busca um produto no Estoque de verdade pelo nome, usando a pontuação de
 * parecença — pega o melhor resultado acima de um limiar mínimo.
 */
function buscarProdutoNoEstoqueReal(nomeProduto) {
  try {
    const ssEstoque = SpreadsheetApp.openById(ID_PLANILHA_ESTOQUE_COTACAO);
    const sheetEstoque = ssEstoque.getSheetByName("ESTOQUE") || ssEstoque.getSheets()[0];
    const lastRow = sheetEstoque.getLastRow();
    if (lastRow < 6) return null;

    const dados = sheetEstoque.getRange(6, 1, lastRow - 5, 11).getValues();
    let melhor = null, melhorScore = 0;

    dados.forEach(row => {
      const desc = String(row[2] || "").trim();
      if (!desc) return;
      const score = calcularScoreSimilaridade(nomeProduto, desc);
      if (score > melhorScore) {
        melhorScore = score;
        melhor = { desc, estoque: parseInt(row[10], 10) || 0, precoVenda: parseFloat(row[9]) || 0 };
      }
    });

    return melhorScore >= 40 ? melhor : null;
  } catch (e) {
    Logger.log("Erro ao buscar no Estoque: " + e.message);
    return null;
  }
}

/**
 * Pra cada produto da Cotação, busca no Estoque de verdade e atualiza a coluna
 * ESTOQUE ATUAL sozinho — sem precisar digitar na mão.
 */
/**
 * Varre o Estoque de verdade inteiro e traz pra Cotação só os produtos que
 * estão com a quantidade ABAIXO do Estoque Mínimo definido lá (coluna N do
 * Estoque — precisa rodar 'adicionarColunaEstoqueMinimo' lá uma vez e
 * preencher o mínimo de cada produto). Não duplica quem já está na Cotação.
 */
function puxarProdutosAbaixoDoMinimo() {
  const sheet = garantirEstruturaCotacao();
  const mapa = getMapeamentoCotacao(sheet);

  let produtosParaTrazer = [];
  try {
    const ssEstoque = SpreadsheetApp.openById(ID_PLANILHA_ESTOQUE_COTACAO);
    const sheetEstoque = ssEstoque.getSheetByName("ESTOQUE") || ssEstoque.getSheets()[0];
    const lastRow = sheetEstoque.getLastRow();
    if (lastRow < 6) { SpreadsheetApp.getUi().alert("Nenhum produto encontrado no Estoque."); return; }

    const dados = sheetEstoque.getRange(6, 1, lastRow - 5, 14).getValues();
    dados.forEach(row => {
      const desc = String(row[2] || "").trim();
      const estoqueAtual = parseInt(row[10], 10) || 0;
      const estoqueMinimo = parseFloat(row[13]) || 0; // coluna N
      if (desc && estoqueMinimo > 0 && estoqueAtual < estoqueMinimo) {
        produtosParaTrazer.push({ desc, estoqueAtual, estoqueMinimo });
      }
    });
  } catch (e) {
    SpreadsheetApp.getUi().alert("❌ Erro ao ler o Estoque: " + e.message);
    return;
  }

  if (produtosParaTrazer.length === 0) {
    SpreadsheetApp.getUi().alert("Nenhum produto está abaixo do Estoque Mínimo agora — ou a coluna Estoque Mínimo ainda não foi preenchida no Estoque (rode 'adicionarColunaEstoqueMinimo' lá e preencha o mínimo de cada produto).");
    return;
  }

  const lastRow = sheet.getLastRow();
  const produtosJaNaCotacao = lastRow >= LINHA_PRIMEIRO_DADO
    ? sheet.getRange(LINHA_PRIMEIRO_DADO, mapa.produto, lastRow - LINHA_PRIMEIRO_DADO + 1, 1).getValues().map(r => removerAcentosCotacao(r[0]))
    : [];

  // Acha a primeira linha livre DENTRO da coluna do resumo — não usa o lastRow
  // geral da aba, porque a área crua (importações) pode ter crescido bem mais.
  let proximaLinhaLivre = LINHA_PRIMEIRO_DADO;
  while (String(sheet.getRange(proximaLinhaLivre, mapa.produto).getValue()).trim() !== "") proximaLinhaLivre++;

  let adicionados = 0;
  produtosParaTrazer.forEach(p => {
    if (produtosJaNaCotacao.includes(removerAcentosCotacao(p.desc))) return; // já está lá, não duplica

    sheet.getRange(proximaLinhaLivre, mapa.produto).setValue(p.desc);
    if (mapa.estoqueAtual) sheet.getRange(proximaLinhaLivre, mapa.estoqueAtual).setValue(p.estoqueAtual);
    produtosJaNaCotacao.push(removerAcentosCotacao(p.desc));
    proximaLinhaLivre++;
    adicionados++;
  });

  SpreadsheetApp.getUi().alert("✅ " + adicionados + " produto(s) abaixo do mínimo trazido(s) pra Cotação!" + (adicionados < produtosParaTrazer.length ? " (" + (produtosParaTrazer.length - adicionados) + " já estavam lá)" : ""));
}

function atualizarEstoqueDaCotacao() {
  const sheet = garantirEstruturaCotacao();
  const mapa = getMapeamentoCotacao(sheet);
  const lastRow = sheet.getLastRow();
  if (lastRow < 9) { SpreadsheetApp.getUi().alert("Nenhum produto cadastrado ainda na coluna PRODUTO."); return; }

  let atualizados = 0, naoEncontrados = [];

  for (let linha = 9; linha <= lastRow; linha++) {
    const nomeProduto = String(sheet.getRange(linha, mapa.produto).getValue() || "").trim();
    if (!nomeProduto) continue;

    const encontrado = buscarProdutoNoEstoqueReal(nomeProduto);
    if (encontrado) {
      sheet.getRange(linha, mapa.estoqueAtual).setValue(encontrado.estoque);
      atualizados++;
    } else {
      naoEncontrados.push(nomeProduto);
    }
  }

  let msg = "✅ " + atualizados + " produto(s) atualizado(s) com o estoque real.";
  if (naoEncontrados.length > 0) {
    msg += "\n\n⚠️ Não encontrei no Estoque (confira o nome): \n" + naoEncontrados.slice(0, 15).join("\n");
    if (naoEncontrados.length > 15) msg += "\n... e mais " + (naoEncontrados.length - 15) + ".";
  }
  SpreadsheetApp.getUi().alert(msg);
}

/**
 * Mapeia as colunas do bloco de RESUMO (a partir da coluna F) pelo texto do
 * cabeçalho — não depende mais de posição fixa nem de colunas dinâmicas de
 * fornecedor (isso agora vive na área crua A-C, empilhada por fornecedor).
 */
function getMapeamentoCotacao(sheet) {
  const lastCol = sheet.getLastColumn();
  const headers = sheet.getRange(LINHA_CABECALHO, COL_INICIO_RESUMO, 1, Math.max(lastCol - COL_INICIO_RESUMO + 1, 11)).getValues()[0];
  const mapa = {};

  headers.forEach((h, idx) => {
    const nome = String(h || "").trim().toUpperCase();
    const col = COL_INICIO_RESUMO + idx;
    if (nome === "PRODUTO") mapa.produto = col;
    else if (nome === "ESTOQUE ATUAL") mapa.estoqueAtual = col;
    else if (nome === "VENDA SEMANAL MÉDIA" || nome === "VENDA SEMANAL MEDIA") mapa.vendaSemanal = col;
    else if (nome === "ÚLTIMO PREÇO PAGO" || nome === "ULTIMO PRECO PAGO") mapa.ultimoPreco = col;
    else if (nome === "MENOR PREÇO" || nome === "MENOR PRECO") mapa.menorPreco = col;
    else if (nome === "FORNECEDOR VENCEDOR") mapa.fornecedorVencedor = col;
    else if (nome === "SEGUNDA OPÇÃO" || nome === "SEGUNDA OPCAO") mapa.segundaOpcao = col;
    else if (nome === "SEGUNDO FORNECEDOR") mapa.segundoFornecedor = col;
    else if (nome === "QTD SUGERIDA") mapa.qtdSugerida = col;
    else if (nome === "QTD A PEDIR") mapa.qtdPedir = col;
    else if (nome === "VALOR DO PEDIDO") mapa.valorPedido = col;
  });

  return mapa;
}

// ============================================================================
// EXPORTAR COTAÇÃO EM BRANCO (pra mandar pro representante preencher)
// ============================================================================

/**
 * Cria uma planilha Google Sheets NOVA (fica no seu Drive) só com Produto/Preço/OBS,
 * usando a lista de produtos que já está na aba Cotação. Devolve o link — dá pra
 * mandar direto pro representante preencher online, ou baixar como Excel de lá
 * (Arquivo > Fazer Download > Microsoft Excel).
 */
function exportarCotacaoEmBranco() {
  const ui = SpreadsheetApp.getUi();
  const sheet = garantirEstruturaCotacao();

  const resp = ui.prompt("📤 Exportar Cotação", "Pra qual fornecedor é essa cotação? (nome exato, igual está cadastrado)", ui.ButtonSet.OK_CANCEL);
  if (resp.getSelectedButton() !== ui.Button.OK) return;
  const fornecedor = resp.getResponseText().trim();
  if (!fornecedor) { ui.alert("⚠️ Precisa dizer o nome do fornecedor."); return; }

  const mapa = getMapeamentoCotacao(sheet);
  const lastRow = sheet.getLastRow();
  if (lastRow < 9) { ui.alert("Preencha a coluna PRODUTO na aba Cotação primeiro."); return; }

  const produtos = sheet.getRange(9, mapa.produto, lastRow - 8, 1).getValues()
    .map(r => String(r[0] || "").trim())
    .filter(p => p !== "");

  if (produtos.length === 0) { ui.alert("Nenhum produto encontrado na coluna PRODUTO."); return; }

  const nomeArquivo = "Cotação - " + fornecedor + " - " + Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "dd-MM-yyyy HH-mm");
  const novaSS = SpreadsheetApp.create(nomeArquivo);
  const novaSheet = novaSS.getSheets()[0];

  // Cabeçalho direto na linha 1, do jeito que já funcionava — o nome do fornecedor
  // fica só no nome do arquivo mesmo, sem mexer na estrutura da planilha.
  novaSheet.getRange(1, 1, 1, 3).setValues([["PRODUTO", "PREÇO", "OBS"]]).setFontWeight("bold");
  novaSheet.getRange(2, 1, produtos.length, 1).setValues(produtos.map(p => [p]));
  novaSheet.setColumnWidth(1, 300);
  novaSheet.setFrozenRows(1);

  const url = novaSS.getUrl();
  const html = HtmlService.createHtmlOutput(
    '<div style="font-family:sans-serif;padding:16px;font-size:13px;">' +
    '<p>✅ Cotação em branco criada pra <strong>' + fornecedor + '</strong>, com ' + produtos.length + ' produto(s)!</p>' +
    '<p><a href="' + url + '" target="_blank" style="color:#0284c7;font-weight:bold;">🔗 Abrir Planilha</a></p>' +
    '<p style="font-size:11px;color:#888;">Pra baixar como Excel: abra o link, vá em Arquivo &gt; Fazer Download &gt; Microsoft Excel. Ou mande o link direto pro representante preencher online.</p>' +
    '</div>'
  ).setWidth(400).setHeight(220);
  SpreadsheetApp.getUi().showModalDialog(html, "📤 Exportar Cotação");
}

// ============================================================================
// IMPORTAR COTAÇÃO PREENCHIDA (uma por fornecedor, tudo cai na mesma aba Cotação)
// ============================================================================

function abrirJanelaImportarCotacao() {
  const html = HtmlService.createHtmlOutput(getHtmlImportarCotacao()).setWidth(480).setHeight(500);
  SpreadsheetApp.getUi().showModalDialog(html, "📥 Importar Cotação");
}

/**
 * Lê a planilha preenchida pelo representante (pelo link/ID que ele mandou de volta),
 * casa cada produto por nome com a aba Cotação (criando a linha se o produto for novo),
 * e escreve o preço na coluna daquele fornecedor — criando a coluna se ainda não existir.
 */
function importarCotacaoPreenchida(fornecedor, linkOuId) {
  let idPlanilha = linkOuId.trim();
  const match = idPlanilha.match(/\/d\/([a-zA-Z0-9-_]+)/);
  if (match) idPlanilha = match[1];

  return mesclarCotacaoNaAba(fornecedor, idPlanilha, false);
}

/**
 * Recebe um arquivo .xlsx enviado direto pela janela (sem precisar converter
 * pra Google Sheets na mão primeiro). Converte pra Sheets temporariamente só
 * pra ler os dados, e apaga o temporário no final.
 *
 * ⚠️ Precisa do serviço avançado "Drive API" ativado no projeto (no editor do
 * Apps Script: Serviços (+) → Drive API → Adicionar).
 */
function importarCotacaoDeArquivo(fornecedor, base64Data, nomeArquivo) {
  if (!base64Data) return { sucesso: false, mensagem: "⚠️ Escolha um arquivo." };

  let idTemp = null;
  try {
    const base64Limpo = base64Data.includes(',') ? base64Data.split(',')[1] : base64Data;
    const bytes = Utilities.base64Decode(base64Limpo);
    const blob = Utilities.newBlob(bytes, MimeType.MICROSOFT_EXCEL, nomeArquivo || "cotacao.xlsx");

    const arquivoConvertido = Drive.Files.insert(
      { title: "TEMP_Importacao_Cotacao_" + new Date().getTime(), mimeType: MimeType.GOOGLE_SHEETS },
      blob,
      { convert: true }
    );
    idTemp = arquivoConvertido.id;

    return mesclarCotacaoNaAba(fornecedor, idTemp, true);
  } catch (e) {
    return {
      sucesso: false,
      mensagem: "❌ Erro: " + e.message + " — pra importar arquivo direto, precisa ativar o serviço 'Drive API' no editor do Apps Script (Serviços → + → Drive API → Adicionar). Enquanto isso, use a opção de colar o link."
    };
  } finally {
    if (idTemp) { try { DriveApp.getFileById(idTemp).setTrashed(true); } catch (e2) {} }
  }
}

/**
 * O miolo compartilhado: lê Produto/Preço de uma planilha (por ID) e mescla na
 * aba única de Cotação, na coluna daquele fornecedor. Se "fornecedor" vier
 * vazio, tenta detectar sozinho pelo título (linha 1) do arquivo — funciona
 * quando o arquivo foi gerado pelo "Exportar Cotação" (que já grava o nome lá).
 */
function mesclarCotacaoNaAba(fornecedor, idPlanilha, ehArquivoTemporario) {
  if (!fornecedor || !fornecedor.trim()) return { sucesso: false, mensagem: "⚠️ Diga de qual fornecedor é essa cotação." };

  try {
    const ssImportada = SpreadsheetApp.openById(idPlanilha);
    const sheetImportada = ssImportada.getSheets()[0];
    const lastRow = sheetImportada.getLastRow();
    if (lastRow < 2) return { sucesso: false, mensagem: "⚠️ Essa planilha não tem produtos preenchidos." };

    const dadosImportados = sheetImportada.getRange(2, 1, lastRow - 1, 3).getValues()
      .filter(row => String(row[0] || "").trim() !== "" && (parseFloat(row[1]) || 0) > 0);

    if (dadosImportados.length === 0) return { sucesso: false, mensagem: "⚠️ Nenhum produto com preço preenchido nessa planilha." };

    const sheetCot = garantirEstruturaCotacao();

    // Acha a primeira linha livre na área crua (coluna A), a partir da linha 9 —
    // é onde o bloco desse fornecedor vai entrar, embaixo de qualquer bloco que já exista.
    let linha = LINHA_PRIMEIRO_DADO;
    while (String(sheetCot.getRange(linha, 1).getValue()).trim() !== "") linha++;

    // Faixa preta com o nome do fornecedor, mesclada A:C.
    sheetCot.getRange(linha, 1, 1, 3).merge()
      .setValue(fornecedor)
      .setBackground("#000000")
      .setFontColor("#ffffff")
      .setFontWeight("bold")
      .setHorizontalAlignment("center");
    linha++;

    // As linhas de Produto / Preço / OBS desse fornecedor, logo abaixo da faixa.
    const linhaInicioProdutos = linha;
    dadosImportados.forEach(row => {
      sheetCot.getRange(linha, 1).setValue(String(row[0]).trim());
      sheetCot.getRange(linha, 2).setValue(parseFloat(row[1]) || 0).setNumberFormat("R$ #,##0.00");
      sheetCot.getRange(linha, 3).setValue(row[2] || "");
      linha++;
    });

    return {
      sucesso: true,
      mensagem: "✅ Importado de " + fornecedor + "! " + dadosImportados.length + " produto(s) adicionados (linhas " + linhaInicioProdutos + " a " + (linha - 1) + "). Roda '🧮 Recalcular Cotação' pra atualizar o resumo comparativo."
    };
  } catch (e) {
    const dica = ehArquivoTemporario ? "" : " (confira se o link está certo e se você tem acesso à planilha)";
    return { sucesso: false, mensagem: "❌ Erro: " + e.message + dica };
  }
}

function getHtmlImportarCotacao() {
  return `<!DOCTYPE html>
<html>
<head>
  <base target="_top">
  <style>
    * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, sans-serif; }
    body { margin: 0; padding: 16px; font-size: 12px; color: #333; background: #f8f9fa; }
    label { font-weight: bold; font-size: 11px; color: #475569; display: block; margin-bottom: 4px; margin-top: 10px; }
    select, input { width: 100%; padding: 8px; border-radius: 6px; border: 1px solid #cbd5e1; font-size: 12px; }
    .btn { width: 100%; padding: 10px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; background: #0284c7; color: white; margin-top: 14px; }
    #status { text-align: center; font-weight: bold; margin-top: 10px; min-height: 18px; }
    .aviso { font-size: 10px; color: #888; margin-top: 4px; }
    .abas { display: flex; gap: 6px; margin-top: 12px; }
    .aba-btn { flex: 1; padding: 7px; border: 1px solid #cbd5e1; border-radius: 6px; background: #fff; cursor: pointer; font-size: 11px; font-weight: bold; color: #475569; text-align: center; }
    .aba-btn.ativa { background: #0284c7; color: #fff; border-color: #0284c7; }
    input[type=file] { padding: 6px; }
  </style>
</head>
<body>
  <label>Fornecedor:</label>
  <select id="in-fornecedor"></select>

  <div class="abas">
    <div class="aba-btn ativa" id="aba-link" onclick="mostrarAba('link')">🔗 Colar Link</div>
    <div class="aba-btn" id="aba-arquivo" onclick="mostrarAba('arquivo')">📎 Enviar Arquivo</div>
  </div>

  <div id="painel-link">
    <div style="font-size:11px;color:#666;margin-top:8px;">Peça pro representante preencher a planilha exportada e te mandar de volta o link.</div>
    <label>Link (ou ID) da planilha preenchida:</label>
    <input type="text" id="in-link" placeholder="https://docs.google.com/spreadsheets/d/...">
  </div>

  <div id="painel-arquivo" style="display:none;">
    <div style="font-size:11px;color:#666;margin-top:8px;">Se o representante te mandou um .xlsx direto (por e-mail, WhatsApp), envia ele aqui sem precisar converter pra Google Sheets antes.</div>
    <label>Arquivo (.xlsx):</label>
    <input type="file" id="in-arquivo" accept=".xlsx">
  </div>

  <div class="aviso">A planilha (ou arquivo) precisa ter Produto na coluna A e Preço na coluna B.</div>

  <button class="btn" onclick="importar()">📥 Importar</button>
  <div id="status"></div>

  <script>
    var modoAtual = 'link';

    window.onload = function() {
      google.script.run.withSuccessHandler(function(lista) {
        const sel = document.getElementById('in-fornecedor');
        sel.innerHTML = '<option value="">Selecione...</option>';
        (lista || []).forEach(function(f) {
          const opt = document.createElement('option');
          opt.value = f.nome; opt.innerText = f.nome;
          sel.appendChild(opt);
        });
      }).obterListaFornecedoresCompleta();
    };

    function mostrarAba(qual) {
      modoAtual = qual;
      document.getElementById('painel-link').style.display = qual === 'link' ? 'block' : 'none';
      document.getElementById('painel-arquivo').style.display = qual === 'arquivo' ? 'block' : 'none';
      document.getElementById('aba-link').className = 'aba-btn' + (qual === 'link' ? ' ativa' : '');
      document.getElementById('aba-arquivo').className = 'aba-btn' + (qual === 'arquivo' ? ' ativa' : '');
      document.getElementById('status').innerText = '';
    }

    function importar() {
      const fornecedor = document.getElementById('in-fornecedor').value;
      const st = document.getElementById('status');
      if (!fornecedor) { st.style.color = '#dc3545'; st.innerText = '⚠️ Escolha o fornecedor.'; return; }

      if (modoAtual === 'link') {
        const link = document.getElementById('in-link').value.trim();
        if (!link) { st.style.color = '#dc3545'; st.innerText = '⚠️ Cole o link da planilha.'; return; }

        st.style.color = '#007bff';
        st.innerText = '⏳ Importando...';

        google.script.run.withSuccessHandler(function(res) {
          st.style.color = res.sucesso ? '#107c41' : '#dc3545';
          st.innerText = res.mensagem;
          if (res.sucesso) setTimeout(function() { google.script.host.close(); }, 2000);
        }).withFailureHandler(function(err) {
          st.style.color = '#dc3545';
          st.innerText = '❌ Erro: ' + (err.message || err);
        }).importarCotacaoPreenchida(fornecedor, link);
      } else {
        const inputArquivo = document.getElementById('in-arquivo');
        if (!inputArquivo.files || inputArquivo.files.length === 0) { st.style.color = '#dc3545'; st.innerText = '⚠️ Escolha um arquivo .xlsx.'; return; }

        const arquivo = inputArquivo.files[0];
        st.style.color = '#007bff';
        st.innerText = '⏳ Lendo o arquivo...';

        const leitor = new FileReader();
        leitor.onload = function(e) {
          st.innerText = '⏳ Importando...';
          google.script.run.withSuccessHandler(function(res) {
            st.style.color = res.sucesso ? '#107c41' : '#dc3545';
            st.innerText = res.mensagem;
            if (res.sucesso) setTimeout(function() { google.script.host.close(); }, 2500);
          }).withFailureHandler(function(err) {
            st.style.color = '#dc3545';
            st.innerText = '❌ Erro: ' + (err.message || err);
          }).importarCotacaoDeArquivo(fornecedor, e.target.result, arquivo.name);
        };
        leitor.readAsDataURL(arquivo);
      }
    }
  </script>
</body>
</html>`;
}

// ============================================================================
// RECALCULAR COTAÇÃO — menor preço, segunda opção, e quantidade sugerida
// ============================================================================

/**
 * A ideia: se o preço cotado está MAIS BARATO que o último preço pago, vale a
 * pena aproveitar e comprar mais. Se está MAIS CARO, compra só o necessário
 * (ou menos ainda). O fator de ajuste é proporcional à variação de preço.
 *
 * qtdBase = venda semanal média × semanas de cobertura
 * variação = (preçoCotado − últimoPreço) / últimoPreço
 * fatorAjuste = 1 − variação   (variação negativa = preço menor = fator > 1 = compra mais)
 * fatorAjuste é limitado entre 0,5 e 2 pra não disparar pra nenhum lado.
 */
function calcularFatorAjustePreco(precoCotado, ultimoPreco) {
  if (!ultimoPreco || ultimoPreco <= 0) return 1;
  const variacao = (precoCotado - ultimoPreco) / ultimoPreco;
  let fator = 1 - variacao;
  fator = Math.max(0.5, Math.min(2, fator));
  return fator;
}

function recalcularCotacaoCompleta(semanasCobertura) {
  const sheet = garantirEstruturaCotacao();
  const semanas = parseFloat(semanasCobertura) || 4;

  // 1. Lê a área CRUA (A-C), rastreando qual fornecedor está "ativo" conforme desce:
  // uma linha com A preenchido e B vazio é a faixa preta (nome do fornecedor);
  // uma linha com B preenchido é um produto daquele fornecedor.
  const lastRow = sheet.getLastRow();
  if (lastRow < LINHA_PRIMEIRO_DADO) { SpreadsheetApp.getUi().alert("Nenhuma cotação importada ainda — importe pelo menos um fornecedor primeiro."); return; }

  const dadosCrus = sheet.getRange(LINHA_PRIMEIRO_DADO, 1, lastRow - LINHA_PRIMEIRO_DADO + 1, 3).getValues();
  let fornecedorAtual = null;
  const cotacoesPorProduto = {}; // chave normalizada -> { nomeOriginal, ofertas: [{fornecedor, preco}] }

  dadosCrus.forEach(row => {
    const colA = String(row[0] || "").trim();
    const colB = row[1];
    if (colA === "") return;

    if (colB === "" || colB === null) {
      fornecedorAtual = colA; // faixa preta = nome do fornecedor
      return;
    }

    const preco = parseFloat(colB) || 0;
    if (!fornecedorAtual || preco <= 0) return;

    const chave = removerAcentosCotacao(colA);
    if (!cotacoesPorProduto[chave]) cotacoesPorProduto[chave] = { nomeOriginal: colA, ofertas: [] };
    cotacoesPorProduto[chave].ofertas.push({ fornecedor: fornecedorAtual, preco });
  });

  if (Object.keys(cotacoesPorProduto).length === 0) { SpreadsheetApp.getUi().alert("Não achei nenhum produto com preço nos blocos importados."); return; }

  // 2. Pra cada produto, acha o menor preço e a segunda opção.
  const mapa = getMapeamentoCotacao(sheet);
  const lastRowResumo = sheet.getLastRow();
  const produtosResumoExistentes = lastRowResumo >= LINHA_PRIMEIRO_DADO
    ? sheet.getRange(LINHA_PRIMEIRO_DADO, mapa.produto, lastRowResumo - LINHA_PRIMEIRO_DADO + 1, 1).getValues().map(r => removerAcentosCotacao(r[0]))
    : [];

  let atualizados = 0, criados = 0;

  Object.values(cotacoesPorProduto).forEach(info => {
    const ofertas = info.ofertas.sort((a, b) => a.preco - b.preco);
    const chave = removerAcentosCotacao(info.nomeOriginal);

    // Acha a linha desse produto no Resumo, ou cria uma nova na primeira linha livre.
    let linhaResumo = -1;
    produtosResumoExistentes.forEach((p, i) => { if (p === chave) linhaResumo = LINHA_PRIMEIRO_DADO + i; });

    if (linhaResumo === -1) {
      linhaResumo = LINHA_PRIMEIRO_DADO;
      while (String(sheet.getRange(linhaResumo, mapa.produto).getValue()).trim() !== "") linhaResumo++;
      sheet.getRange(linhaResumo, mapa.produto).setValue(info.nomeOriginal);
      produtosResumoExistentes.push(chave);
      criados++;
    } else {
      atualizados++;
    }

    sheet.getRange(linhaResumo, mapa.menorPreco).setValue(ofertas[0].preco).setNumberFormat("R$ #,##0.00");
    if (mapa.fornecedorVencedor) sheet.getRange(linhaResumo, mapa.fornecedorVencedor).setValue(ofertas[0].fornecedor);
    if (mapa.segundaOpcao && ofertas.length > 1) {
      sheet.getRange(linhaResumo, mapa.segundaOpcao).setValue(ofertas[1].preco).setNumberFormat("R$ #,##0.00");
      if (mapa.segundoFornecedor) sheet.getRange(linhaResumo, mapa.segundoFornecedor).setValue(ofertas[1].fornecedor);
    } else {
      if (mapa.segundaOpcao) sheet.getRange(linhaResumo, mapa.segundaOpcao).setValue("");
      if (mapa.segundoFornecedor) sheet.getRange(linhaResumo, mapa.segundoFornecedor).setValue("");
    }

    if (mapa.qtdSugerida && mapa.vendaSemanal) {
      const vendaSemanal = parseFloat(sheet.getRange(linhaResumo, mapa.vendaSemanal).getValue()) || 0;
      const ultimoPreco = mapa.ultimoPreco ? parseFloat(sheet.getRange(linhaResumo, mapa.ultimoPreco).getValue()) || 0 : 0;

      const qtdBase = vendaSemanal * semanas;
      const fator = calcularFatorAjustePreco(ofertas[0].preco, ultimoPreco);
      const qtdSugerida = Math.round(qtdBase * fator);

      sheet.getRange(linhaResumo, mapa.qtdSugerida).setValue(qtdSugerida);
    }
  });

  SpreadsheetApp.getUi().alert(
    "✅ Cotação recalculada com cobertura de " + semanas + " semana(s)!\n\n" +
    atualizados + " produto(s) atualizado(s), " + criados + " novo(s) no resumo.\n\n" +
    "Preço mais barato que o último pago → sugere comprar mais.\n" +
    "Preço mais caro → sugere comprar menos."
  );
}

function abrirJanelaRecalcularCotacao() {
  const ui = SpreadsheetApp.getUi();
  const resp = ui.prompt("🧮 Recalcular Cotação", "Quantas semanas de cobertura de estoque você quer considerar?", ui.ButtonSet.OK_CANCEL);
  if (resp.getSelectedButton() !== ui.Button.OK) return;
  recalcularCotacaoCompleta(resp.getResponseText());
}

/**
 * Limpa a Cotação pro próximo ciclo — mas antes de limpar, grava o preço pedido
 * de cada produto como o novo "Último Preço Pago", pra comparar da próxima vez.
 */
function limparCotacaoParaProximoCiclo() {
  const ui = SpreadsheetApp.getUi();
  const confirmacao = ui.alert("🧹 Limpar Cotação", "Isso apaga todos os blocos de fornecedor importados e os resultados calculados, mas guarda o preço pedido como referência pro próximo ciclo. Confirma?", ui.ButtonSet.YES_NO);
  if (confirmacao !== ui.Button.YES) return;

  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(NOME_ABA_COTACAO);
  const mapa = getMapeamentoCotacao(sheet);
  const lastRow = sheet.getLastRow();
  if (lastRow < LINHA_PRIMEIRO_DADO) return;

  // No Resumo: guarda o preço pedido como Último Preço Pago antes de limpar, pra
  // servir de referência de comparação no próximo ciclo.
  for (let linha = LINHA_PRIMEIRO_DADO; linha <= lastRow; linha++) {
    if (mapa.qtdPedir && mapa.menorPreco && mapa.ultimoPreco) {
      const qtdPedida = parseFloat(sheet.getRange(linha, mapa.qtdPedir).getValue()) || 0;
      if (qtdPedida > 0) {
        const precoPedido = parseFloat(sheet.getRange(linha, mapa.menorPreco).getValue()) || 0;
        sheet.getRange(linha, mapa.ultimoPreco).setValue(precoPedido).setNumberFormat("R$ #,##0.00");
      }
    }

    if (mapa.menorPreco) sheet.getRange(linha, mapa.menorPreco).clearContent();
    if (mapa.fornecedorVencedor) sheet.getRange(linha, mapa.fornecedorVencedor).clearContent();
    if (mapa.segundaOpcao) sheet.getRange(linha, mapa.segundaOpcao).clearContent();
    if (mapa.segundoFornecedor) sheet.getRange(linha, mapa.segundoFornecedor).clearContent();
    if (mapa.qtdSugerida) sheet.getRange(linha, mapa.qtdSugerida).clearContent();
    if (mapa.qtdPedir) sheet.getRange(linha, mapa.qtdPedir).clearContent();
    if (mapa.valorPedido) sheet.getRange(linha, mapa.valorPedido).clearContent();
  }

  // Área crua (A-C): apaga TODOS os blocos de fornecedor importados (faixas pretas
  // + produtos), incluindo a formatação da faixa e a mesclagem de células.
  const rangeArea = sheet.getRange(LINHA_PRIMEIRO_DADO, 1, lastRow - LINHA_PRIMEIRO_DADO + 1, 3);
  rangeArea.breakApart();
  rangeArea.clearContent().clearFormat();

  ui.alert("✅ Cotação limpa! Pronto pro próximo ciclo — o Último Preço Pago foi mantido como referência.");
}

// ============================================================================
// FINALIZAR PEDIDO — vai fornecedor por fornecedor, respeita pedido mínimo,
// oferece a segunda opção quando um item é recusado.
// ============================================================================

function abrirJanelaFinalizarPedido() {
  const html = HtmlService.createHtmlOutput(getHtmlFinalizarPedido()).setWidth(650).setHeight(720);
  SpreadsheetApp.getUi().showModalDialog(html, "✅ Finalizar Pedido");
}

/**
 * Lista TODOS os fornecedores que têm pelo menos uma cotação importada (área
 * crua A-C) — não só os que ganharam algum produto. Assim dá pra fazer pedido
 * de um fornecedor mesmo que ele não tenha sido o mais barato em nada.
 */
function obterFornecedoresComPedidoPendente() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(NOME_ABA_COTACAO);
  const lastRow = sheet.getLastRow();
  if (lastRow < LINHA_PRIMEIRO_DADO) return [];

  const dadosCrus = sheet.getRange(LINHA_PRIMEIRO_DADO, 1, lastRow - LINHA_PRIMEIRO_DADO + 1, 2).getValues();
  const fornecedores = new Set();

  dadosCrus.forEach(row => {
    const colA = String(row[0] || "").trim();
    const colB = row[1];
    if (colA !== "" && (colB === "" || colB === null)) fornecedores.add(colA); // faixa preta = fornecedor
  });

  return Array.from(fornecedores);
}

/**
 * Lê todas as linhas de Produto/Preço/OBS cotadas por UM fornecedor específico,
 * direto da área crua A-C (rastreando qual bloco pertence a ele).
 */
function obterOfertasDoFornecedor(sheet, fornecedor) {
  const lastRow = sheet.getLastRow();
  if (lastRow < LINHA_PRIMEIRO_DADO) return [];

  const dadosCrus = sheet.getRange(LINHA_PRIMEIRO_DADO, 1, lastRow - LINHA_PRIMEIRO_DADO + 1, 3).getValues();
  let fornecedorAtual = null;
  const ofertas = [];

  dadosCrus.forEach((row, i) => {
    const colA = String(row[0] || "").trim();
    const colB = row[1];
    if (colA === "") return;

    if (colB === "" || colB === null) {
      fornecedorAtual = colA;
      return;
    }

    if (removerAcentosCotacao(fornecedorAtual) === removerAcentosCotacao(fornecedor)) {
      ofertas.push({ linha: LINHA_PRIMEIRO_DADO + i, produto: colA, preco: parseFloat(colB) || 0, obs: row[2] || "" });
    }
  });

  return ofertas;
}

/**
 * Monta os itens do pedido de UM fornecedor — TODOS os produtos que ele cotou,
 * não só os que ele ganhou. Cada item mostra se ele é o vencedor daquele
 * produto (pra sugerir quantidade) ou não (você decide manualmente).
 */
function obterItensPedidoCompleto(fornecedor) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(NOME_ABA_COTACAO);
  const mapa = getMapeamentoCotacao(sheet);
  const lastRow = sheet.getLastRow();

  const ofertas = obterOfertasDoFornecedor(sheet, fornecedor);
  if (ofertas.length === 0) return { itens: [], pedidoMinimo: 0 };

  // Lê o Resumo inteiro uma vez, pra cruzar cada oferta com estoque/vencedor/qtd sugerida.
  const resumoPorProduto = {};
  if (lastRow >= LINHA_PRIMEIRO_DADO) {
    const dadosResumo = sheet.getRange(LINHA_PRIMEIRO_DADO, mapa.produto, lastRow - LINHA_PRIMEIRO_DADO + 1, 11 - (mapa.produto - COL_INICIO_RESUMO)).getValues();
    dadosResumo.forEach(r => {
      const nome = String(r[0] || "").trim();
      if (!nome) return;
      resumoPorProduto[removerAcentosCotacao(nome)] = {
        estoqueAtual: parseFloat(r[mapa.estoqueAtual - mapa.produto]) || 0,
        fornecedorVencedor: String(r[mapa.fornecedorVencedor - mapa.produto] || "").trim(),
        qtdSugerida: parseFloat(r[mapa.qtdSugerida - mapa.produto]) || 0,
        segundaOpcaoPreco: parseFloat(r[mapa.segundaOpcao - mapa.produto]) || 0,
        segundoFornecedor: String(r[mapa.segundoFornecedor - mapa.produto] || "").trim()
      };
    });
  }

  const itens = ofertas.map(oferta => {
    const info = resumoPorProduto[removerAcentosCotacao(oferta.produto)] || {};
    const ehVencedor = removerAcentosCotacao(info.fornecedorVencedor || "") === removerAcentosCotacao(fornecedor);

    return {
      linha: oferta.linha, // linha da OFERTA (área crua) — não usada pra escrever no resumo, só referência
      produto: oferta.produto,
      preco: oferta.preco, // preço que ESSE fornecedor cotou (pode não ser o menor)
      ehVencedor,
      qtdSugerida: ehVencedor ? (info.qtdSugerida || 0) : 0,
      estoqueAtual: info.estoqueAtual || 0,
      segundaOpcaoPreco: info.segundaOpcaoPreco || 0,
      segundoFornecedor: info.segundoFornecedor || ""
    };
  });

  const fornecedores = obterListaFornecedoresCompleta();
  const infoFornecedor = fornecedores.find(f => removerAcentosCotacao(f.nome) === removerAcentosCotacao(fornecedor));

  return { itens, pedidoMinimo: infoFornecedor ? infoFornecedor.pedidoMinimo : 0 };
}

/**
 * Move um item recusado (Qtd a Pedir = 0) pro segundo fornecedor: some da lista
 * desse fornecedor e devolve pra fila do outro, se ele tiver uma 2ª opção.
 */
function moverItemParaSegundaOpcao(produto) {
  try {
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(NOME_ABA_COTACAO);
    const mapa = getMapeamentoCotacao(sheet);
    const lastRow = sheet.getLastRow();
    if (lastRow < LINHA_PRIMEIRO_DADO) return { sucesso: false, mensagem: "⚠️ Resumo vazio." };

    // Acha a linha desse produto no RESUMO (não na área crua) pelo nome.
    const produtosResumo = sheet.getRange(LINHA_PRIMEIRO_DADO, mapa.produto, lastRow - LINHA_PRIMEIRO_DADO + 1, 1).getValues();
    let linhaNum = -1;
    produtosResumo.forEach((r, i) => {
      if (removerAcentosCotacao(r[0]) === removerAcentosCotacao(produto)) linhaNum = LINHA_PRIMEIRO_DADO + i;
    });
    if (linhaNum === -1) return { sucesso: false, mensagem: "⚠️ Não achei esse produto no resumo." };

    const segundoFornecedor = mapa.segundoFornecedor ? String(sheet.getRange(linhaNum, mapa.segundoFornecedor).getValue() || "").trim() : "";
    const segundaOpcaoPreco = mapa.segundaOpcao ? parseFloat(sheet.getRange(linhaNum, mapa.segundaOpcao).getValue()) || 0 : 0;

    if (!segundoFornecedor || segundaOpcaoPreco <= 0) {
      return { sucesso: false, mensagem: "⚠️ Esse item não tem uma segunda opção de fornecedor cotada." };
    }

    if (mapa.fornecedorVencedor) sheet.getRange(linhaNum, mapa.fornecedorVencedor).setValue(segundoFornecedor);
    if (mapa.menorPreco) sheet.getRange(linhaNum, mapa.menorPreco).setValue(segundaOpcaoPreco).setNumberFormat("R$ #,##0.00");

    return { sucesso: true, mensagem: "✅ Movido pra " + segundoFornecedor + " (R$ " + segundaOpcaoPreco.toFixed(2) + ")", novoFornecedor: segundoFornecedor };
  } catch (e) {
    return { sucesso: false, mensagem: "❌ Erro: " + e.message };
  }
}

/**
 * Salva o pedido de um fornecedor no Histórico, ajustando quantidades se
 * precisar forçar o mínimo (aumenta proporcionalmente todos os itens até bater).
 */
function finalizarPedidoFornecedor(fornecedor, itens, forcarMinimo) {
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheetCotacao = ss.getSheetByName(NOME_ABA_COTACAO);
    const sheetHist = garantirAbaPedidosNoHistorico();
    const mapa = getMapeamentoCotacao(sheetCotacao);
    const hoje = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "dd/MM/yyyy");

    let valorTotal = itens.reduce((s, i) => s + ((parseFloat(i.qtdFinal) || 0) * i.preco), 0);

    const fornecedores = obterListaFornecedoresCompleta();
    const infoFornecedor = fornecedores.find(f => removerAcentosCotacao(f.nome) === removerAcentosCotacao(fornecedor));
    const pedidoMinimo = infoFornecedor ? infoFornecedor.pedidoMinimo : 0;

    if (forcarMinimo && pedidoMinimo > 0 && valorTotal > 0 && valorTotal < pedidoMinimo) {
      const fatorAumento = pedidoMinimo / valorTotal;
      itens.forEach(i => { i.qtdFinal = Math.ceil((parseFloat(i.qtdFinal) || 0) * fatorAumento); });
      valorTotal = itens.reduce((s, i) => s + ((parseFloat(i.qtdFinal) || 0) * i.preco), 0);
    }

    const lastRowResumo = sheetCotacao.getLastRow();
    const produtosResumo = lastRowResumo >= LINHA_PRIMEIRO_DADO
      ? sheetCotacao.getRange(LINHA_PRIMEIRO_DADO, mapa.produto, lastRowResumo - LINHA_PRIMEIRO_DADO + 1, 1).getValues().map(r => removerAcentosCotacao(r[0]))
      : [];

    const linhasHist = [];
    itens.forEach(item => {
      const qtd = parseFloat(item.qtdFinal) || 0;
      if (qtd <= 0) return;
      const valorItem = qtd * item.preco;
      linhasHist.push([hoje, fornecedor, item.produto, qtd, item.preco, valorItem, item.estoqueAtual]);

      const idxResumo = produtosResumo.indexOf(removerAcentosCotacao(item.produto));
      if (idxResumo !== -1) {
        const linhaResumo = LINHA_PRIMEIRO_DADO + idxResumo;
        if (mapa.qtdPedir) sheetCotacao.getRange(linhaResumo, mapa.qtdPedir).setValue(qtd);
        if (mapa.valorPedido) sheetCotacao.getRange(linhaResumo, mapa.valorPedido).setValue(valorItem).setNumberFormat("R$ #,##0.00");
      }
    });

    if (linhasHist.length > 0) {
      // Antes de gravar, apaga qualquer pedido já existente HOJE, desse mesmo
      // fornecedor + produto — evita duplicar se "Finalizar" for clicado mais
      // de uma vez (por engano, ou pra corrigir uma quantidade).
      const tz = Session.getScriptTimeZone();
      const lastRowHist = sheetHist.getLastRow();
      if (lastRowHist >= 2) {
        const dadosHist = sheetHist.getRange(2, 1, lastRowHist - 1, 2).getValues();
        const linhasParaApagar = [];
        dadosHist.forEach((row, i) => {
          const dataTexto = row[0] instanceof Date ? Utilities.formatDate(row[0], tz, "dd/MM/yyyy") : String(row[0]).trim();
          const mesmoFornecedor = removerAcentosCotacao(String(row[1] || "")) === removerAcentosCotacao(fornecedor);
          if (dataTexto === hoje && mesmoFornecedor) linhasParaApagar.push(i + 2);
        });
        // Apaga de baixo pra cima, pra não bagunçar os números de linha ao deletar.
        linhasParaApagar.sort((a, b) => b - a).forEach(l => sheetHist.deleteRow(l));
      }

      const startRow = sheetHist.getLastRow() + 1;
      sheetHist.getRange(startRow, 1, linhasHist.length, 7).setValues(linhasHist);
      sheetHist.getRange(startRow, 5, linhasHist.length, 2).setNumberFormat("R$ #,##0.00");
    }

    return {
      sucesso: true,
      mensagem: "✅ Pedido de " + fornecedor + " salvo! " + linhasHist.length + " item(ns), total R$ " + valorTotal.toFixed(2).replace('.', ','),
      valorTotal, abaixoDoMinimo: pedidoMinimo > 0 && valorTotal < pedidoMinimo
    };
  } catch (e) {
    return { sucesso: false, mensagem: "❌ Erro: " + e.message };
  }
}

function getHtmlFinalizarPedido() {
  return `<!DOCTYPE html>
<html>
<head>
  <base target="_top">
  <style>
    * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, sans-serif; }
    body { margin: 0; padding: 16px; font-size: 12px; color: #333; background: #f8f9fa; }
    label { font-weight: bold; font-size: 11px; color: #475569; display: block; margin-bottom: 4px; }
    select { width: 100%; padding: 8px; border-radius: 6px; border: 1px solid #cbd5e1; font-size: 12px; }
    table { width: 100%; border-collapse: collapse; font-size: 11px; margin-top: 12px; }
    th { text-align: left; padding: 6px; background: #f1f5f9; font-size: 10px; text-transform: uppercase; color: #475569; }
    td { padding: 6px; border-bottom: 1px solid #f1f5f9; vertical-align: middle; }
    input[type=number] { width: 65px; padding: 4px; border-radius: 4px; border: 1px solid #cbd5e1; }
    .box { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; margin-top: 10px; }
    .btn { padding: 9px 14px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; }
    .btn-ok { background: #16a34a; color: white; }
    .btn-2op { background: #d97706; color: white; font-size: 10px; padding: 4px 8px; }
    #status { text-align: center; font-weight: bold; margin-top: 10px; min-height: 18px; }
    #total { text-align: right; font-weight: bold; font-size: 13px; margin-top: 8px; }
    .aviso-minimo { background: #fef3c7; border: 1px solid #fcd34d; border-radius: 8px; padding: 10px; margin-top: 10px; font-size: 11px; }
    .aviso-minimo button { margin-right: 8px; margin-top: 6px; }
  </style>
</head>
<body>
  <label>Fornecedor:</label>
  <select id="in-fornecedor" onchange="carregarItens()"></select>

  <label style="display:flex;align-items:center;gap:5px;font-weight:normal;font-size:11px;margin-top:8px;">
    <input type="checkbox" id="in-so-vencedores" checked style="width:auto;" onchange="renderizarItens()"> Mostrar só os produtos que ele ganhou
  </label>

  <div id="corpo-itens"></div>
  <div id="total"></div>
  <div id="aviso-minimo-box"></div>

  <div style="display:flex;gap:8px;margin-top:14px;">
    <button class="btn btn-ok" style="flex:1;" onclick="finalizar(false)">✅ Finalizar Pedido Desse Fornecedor</button>
  </div>
  <div id="status"></div>

  <script>
    var itensAtuais = [];
    var fornecedoresPendentes = [];
    var pedidoMinimoAtual = 0;

    function fmt(n) { return 'R$ ' + (n || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }

    window.onload = function() {
      google.script.run.withSuccessHandler(function(lista) {
        fornecedoresPendentes = lista || [];
        const sel = document.getElementById('in-fornecedor');
        sel.innerHTML = '<option value="">Selecione...</option>';
        fornecedoresPendentes.forEach(function(f) {
          const opt = document.createElement('option');
          opt.value = f; opt.innerText = f;
          sel.appendChild(opt);
        });
        if (fornecedoresPendentes.length > 0) { sel.value = fornecedoresPendentes[0]; carregarItens(); }
      }).obterFornecedoresComPedidoPendente();
    };

    function carregarItens() {
      const fornecedor = document.getElementById('in-fornecedor').value;
      document.getElementById('aviso-minimo-box').innerHTML = '';
      document.getElementById('status').innerText = '';
      if (!fornecedor) { document.getElementById('corpo-itens').innerHTML = ''; return; }

      document.getElementById('corpo-itens').innerHTML = '⏳ Carregando...';
      google.script.run.withSuccessHandler(function(res) {
        itensAtuais = res.itens || [];
        pedidoMinimoAtual = res.pedidoMinimo || 0;
        renderizarItens();
      }).obterItensPedidoCompleto(fornecedor);
    }

    function renderizarItens() {
      if (itensAtuais.length === 0) {
        document.getElementById('corpo-itens').innerHTML = '<div class="box">Esse fornecedor ainda não tem nenhuma cotação importada.</div>';
        document.getElementById('total').innerText = '';
        return;
      }

      const soVencedores = document.getElementById('in-so-vencedores').checked;
      let html = '<table><thead><tr><th>Produto</th><th>Situação</th><th>Estoque</th><th>Preço</th><th>Qtd a Pedir</th><th></th></tr></thead><tbody>';
      let algumVisivel = false;

      itensAtuais.forEach(function(item, idx) {
        if (soVencedores && !item.ehVencedor) return; // mantém o índice original, só não desenha a linha
        algumVisivel = true;

        const situacao = item.ehVencedor
          ? '<span style="color:#16a34a;font-weight:bold;">✓ Melhor preço</span>'
          : '<span style="color:#94a3b8;">— não venceu</span>';
        html += '<tr id="linha-' + idx + '"><td>' + item.produto + '</td><td>' + situacao + '</td><td>' + item.estoqueAtual + '</td><td>' + fmt(item.preco) + '</td>' +
          '<td><input type="number" min="0" value="' + item.qtdSugerida + '" id="qtd-' + idx + '" oninput="atualizarTotal()"></td>' +
          '<td id="cel2op-' + idx + '">' + (item.ehVencedor && item.segundoFornecedor ? '<button class="btn btn-2op" onclick="pedirConfirmacao2op(' + idx + ')">2ª opção</button>' : '') + '</td></tr>';
      });
      html += '</tbody></table>';

      if (!algumVisivel) html = '<div class="box">Nenhum produto ' + (soVencedores ? 'vencedor pra esse fornecedor ainda' : 'cotado por esse fornecedor') + '.</div>';

      document.getElementById('corpo-itens').innerHTML = html;
      atualizarTotal();
    }

    function pedirConfirmacao2op(idx) {
      const item = itensAtuais[idx];
      const cel = document.getElementById('cel2op-' + idx);
      cel.innerHTML =
        '<div style="font-size:10px;line-height:1.4;">Mover pra <strong>' + item.segundoFornecedor + '</strong> (R$ ' + item.segundaOpcaoPreco.toFixed(2) + ')?<br>' +
        '<button class="btn btn-2op" style="background:#16a34a;margin-right:4px;" onclick="verSegundaOpcao(' + idx + ')">Sim</button>' +
        '<button class="btn btn-2op" style="background:#64748b;" onclick="cancelar2op(' + idx + ')">Não</button></div>';
    }

    function cancelar2op(idx) {
      const cel = document.getElementById('cel2op-' + idx);
      cel.innerHTML = '<button class="btn btn-2op" onclick="pedirConfirmacao2op(' + idx + ')">2ª opção</button>';
    }

    function verSegundaOpcao(idx) {
      const item = itensAtuais[idx];

      google.script.run.withSuccessHandler(function(res) {
        document.getElementById('status').style.color = res.sucesso ? '#107c41' : '#dc3545';
        document.getElementById('status').innerText = res.mensagem;
        if (res.sucesso) carregarItens(); // recarrega, o item já saiu da lista desse fornecedor
      }).moverItemParaSegundaOpcao(item.produto);
    }

    function atualizarTotal() {
      let total = 0;
      itensAtuais.forEach(function(item, idx) {
        const el = document.getElementById('qtd-' + idx);
        if (!el) return;
        const qtd = parseFloat(el.value) || 0;
        total += qtd * item.preco;
      });
      document.getElementById('total').innerText = 'Total do Pedido: ' + fmt(total);
      document.getElementById('aviso-minimo-box').innerHTML = '';

      if (pedidoMinimoAtual > 0 && total > 0 && total < pedidoMinimoAtual) {
        document.getElementById('aviso-minimo-box').innerHTML =
          '<div class="aviso-minimo">⚠️ Esse pedido (' + fmt(total) + ') está abaixo do mínimo desse fornecedor (' + fmt(pedidoMinimoAtual) + ').<br>' +
          '<button class="btn btn-ok" onclick="finalizar(true)">Forçar até o mínimo</button>' +
          '<button class="btn" style="background:#64748b;color:#fff;" onclick="finalizar(false)">Enviar assim mesmo</button></div>';
      }
    }

    function finalizar(forcarMinimo) {
      const fornecedor = document.getElementById('in-fornecedor').value;
      const st = document.getElementById('status');
      if (!fornecedor || itensAtuais.length === 0) { st.style.color = '#dc3545'; st.innerText = '⚠️ Selecione um fornecedor com itens.'; return; }

      itensAtuais.forEach(function(item, idx) {
        const el = document.getElementById('qtd-' + idx);
        item.qtdFinal = el ? (parseFloat(el.value) || 0) : 0;
      });

      st.style.color = '#007bff';
      st.innerText = '⏳ Salvando...';

      google.script.run.withSuccessHandler(function(res) {
        st.style.color = res.sucesso ? '#107c41' : '#dc3545';
        st.innerText = res.mensagem;
        if (res.sucesso) {
          // Pula pro próximo fornecedor da fila, se tiver.
          fornecedoresPendentes = fornecedoresPendentes.filter(function(f) { return f !== fornecedor; });
          const sel = document.getElementById('in-fornecedor');
          sel.innerHTML = '<option value="">Selecione...</option>';
          fornecedoresPendentes.forEach(function(f) {
            const opt = document.createElement('option');
            opt.value = f; opt.innerText = f;
            sel.appendChild(opt);
          });
          if (fornecedoresPendentes.length > 0) {
            sel.value = fornecedoresPendentes[0];
            setTimeout(function() { carregarItens(); }, 1200);
          } else {
            document.getElementById('corpo-itens').innerHTML = '<div class="box">🎉 Todos os fornecedores com pedido pendente foram finalizados!</div>';
            document.getElementById('total').innerText = '';
          }
        }
      }).withFailureHandler(function(err) {
        st.style.color = '#dc3545';
        st.innerText = '❌ Erro: ' + (err.message || err);
      }).finalizarPedidoFornecedor(fornecedor, itensAtuais, forcarMinimo);
    }
  </script>
</body>
</html>`;
}

// ============================================================================
// EXPORTAR PEDIDO EM TEXTO (um arquivo por fornecedor, pra mandar no WhatsApp)
// ============================================================================

function abrirJanelaExportarPedidos() {
  const html = HtmlService.createHtmlOutput(getHtmlExportarPedidos()).setWidth(480).setHeight(420);
  SpreadsheetApp.getUi().showModalDialog(html, "📤 Exportar Pedidos em Texto");
}

/**
 * Lista os fornecedores que aparecem no Histórico de Pedidos na data de hoje —
 * são os que acabaram de ser finalizados nessa rodada.
 */
function obterFornecedoresPedidosDeHoje() {
  const sheet = garantirAbaPedidosNoHistorico();
  if (!sheet) return [];
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];

  const tz = Session.getScriptTimeZone();
  const hoje = Utilities.formatDate(new Date(), tz, "dd/MM/yyyy");
  const dados = sheet.getRange(2, 1, lastRow - 1, 2).getValues();
  const fornecedores = new Set();
  dados.forEach(row => {
    const dataTexto = row[0] instanceof Date ? Utilities.formatDate(row[0], tz, "dd/MM/yyyy") : String(row[0]).trim();
    if (dataTexto === hoje) fornecedores.add(row[1]);
  });

  return Array.from(fornecedores);
}

/**
 * Monta o texto do pedido (Descrição / Quantidade / Preço) pra UM fornecedor,
 * pegando os itens do Histórico de Pedidos de hoje, e devolve pronto pra copiar
 * e colar (ou baixar como .txt).
 */
function gerarTextoPedido(fornecedor) {
  const sheet = garantirAbaPedidosNoHistorico();
  const lastRow = sheet.getLastRow();
  const tz = Session.getScriptTimeZone();
  const hoje = Utilities.formatDate(new Date(), tz, "dd/MM/yyyy");
  const dados = sheet.getRange(2, 1, lastRow - 1, 6).getValues();

  let texto = "PEDIDO — " + fornecedor + " — " + hoje + "\n";
  texto += "=".repeat(50) + "\n\n";
  texto += "Descrição".padEnd(35) + "Qtd".padEnd(8) + "Preço\n";
  texto += "-".repeat(50) + "\n";

  let totalGeral = 0;
  dados.forEach(row => {
    const dataTexto = row[0] instanceof Date ? Utilities.formatDate(row[0], tz, "dd/MM/yyyy") : String(row[0]).trim();
    if (dataTexto !== hoje || row[1] !== fornecedor) return;
    const desc = String(row[2] || "").substring(0, 33);
    const qtd = row[3];
    const preco = parseFloat(row[4]) || 0;
    totalGeral += (parseFloat(row[3]) || 0) * preco;
    texto += desc.padEnd(35) + String(qtd).padEnd(8) + "R$ " + preco.toFixed(2) + "\n";
  });

  texto += "-".repeat(50) + "\n";
  texto += "TOTAL: R$ " + totalGeral.toFixed(2).replace('.', ',') + "\n";

  return texto;
}

function getHtmlExportarPedidos() {
  return `<!DOCTYPE html>
<html>
<head>
  <base target="_top">
  <style>
    * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, sans-serif; }
    body { margin: 0; padding: 16px; font-size: 12px; color: #333; background: #f8f9fa; }
    label { font-weight: bold; font-size: 11px; color: #475569; display: block; margin-bottom: 4px; }
    select { width: 100%; padding: 8px; border-radius: 6px; border: 1px solid #cbd5e1; font-size: 12px; }
    textarea { width: 100%; height: 260px; font-family: monospace; font-size: 11px; padding: 8px; border-radius: 6px; border: 1px solid #cbd5e1; margin-top: 10px; }
    .btn { width: 100%; padding: 9px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; background: #0f172a; color: white; margin-top: 8px; }
    #status { text-align: center; font-weight: bold; margin-top: 8px; min-height: 18px; }
  </style>
</head>
<body>
  <label>Fornecedor:</label>
  <select id="in-fornecedor" onchange="carregarTexto()"></select>

  <textarea id="texto-pedido" readonly></textarea>
  <button class="btn" onclick="copiar()">📋 Copiar Texto</button>
  <div id="status"></div>

  <script>
    window.onload = function() {
      google.script.run.withSuccessHandler(function(lista) {
        const sel = document.getElementById('in-fornecedor');
        sel.innerHTML = '<option value="">Selecione...</option>';
        (lista || []).forEach(function(f) {
          const opt = document.createElement('option');
          opt.value = f; opt.innerText = f;
          sel.appendChild(opt);
        });
        if (lista && lista.length > 0) { sel.value = lista[0]; carregarTexto(); }
      }).obterFornecedoresPedidosDeHoje();
    };

    function carregarTexto() {
      const fornecedor = document.getElementById('in-fornecedor').value;
      if (!fornecedor) { document.getElementById('texto-pedido').value = ''; return; }
      google.script.run.withSuccessHandler(function(texto) {
        document.getElementById('texto-pedido').value = texto;
      }).gerarTextoPedido(fornecedor);
    }

    function copiar() {
      const el = document.getElementById('texto-pedido');
      el.select();
      document.execCommand('copy');
      document.getElementById('status').style.color = '#107c41';
      document.getElementById('status').innerText = '✅ Copiado! Cola no WhatsApp ou onde precisar.';
    }
  </script>
</body>
</html>`;
}

/**
 * FAXINA ÚNICA: remove pedidos duplicados de hoje no Histórico compartilhado
 * (mesmo fornecedor + mesmo produto + hoje), deixando só a última ocorrência
 * de cada um. Rode uma vez pelo editor pra limpar a bagunça que ficou de testes.
 */
function limparPedidosDuplicadosDeHoje() {
  const sheet = garantirAbaPedidosNoHistorico();
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) { SpreadsheetApp.getUi().alert("Nada pra limpar."); return; }

  const tz = Session.getScriptTimeZone();
  const hoje = Utilities.formatDate(new Date(), tz, "dd/MM/yyyy");
  const dados = sheet.getRange(2, 1, lastRow - 1, 3).getValues();

  const vistos = new Set();
  const linhasParaApagar = [];

  // Percorre de baixo pra cima, guardando a ÚLTIMA ocorrência de cada
  // fornecedor+produto de hoje e marcando as anteriores (duplicadas) pra apagar.
  for (let i = dados.length - 1; i >= 0; i--) {
    const row = dados[i];
    const dataTexto = row[0] instanceof Date ? Utilities.formatDate(row[0], tz, "dd/MM/yyyy") : String(row[0]).trim();
    if (dataTexto !== hoje) continue;

    const chave = removerAcentosCotacao(row[1]) + "|" + removerAcentosCotacao(row[2]);
    if (vistos.has(chave)) {
      linhasParaApagar.push(i + 2);
    } else {
      vistos.add(chave);
    }
  }

  linhasParaApagar.sort((a, b) => b - a).forEach(l => sheet.deleteRow(l));

  SpreadsheetApp.getUi().alert("✅ " + linhasParaApagar.length + " linha(s) duplicada(s) removida(s) — sobrou só a última versão de cada produto.");
}