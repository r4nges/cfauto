// ============================================================
// SISTEMA DE GESTÃO DE CLIENTES E CREDIÁRIO
// ============================================================

/**
 * BOTÃO AZUL (+): Abre janela para novo cadastro.
 */
function abrirJanelaCliente() {
  const html = HtmlService.createHtmlOutput(getFormularioHtml(null))
    .setWidth(480)
    .setHeight(760);
  SpreadsheetApp.getUi().showModalDialog(html, "Novo Cadastro de Cliente");
}

/**
 * BOTÃO VERMELHO (-): Exclui o cliente selecionado na planilha.
 */
function apagarClienteSelecionado() {
  const ui = SpreadsheetApp.getUi();
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName("CLIENTES");
  
  if (!sheet) {
    ui.alert("Erro: Aba CLIENTES não encontrada.");
    return;
  }

  const linha = sheet.getActiveCell().getRow();
  if (linha < 7) {
    ui.alert("⚠️ Por favor, clique sobre uma linha válida de cliente (linha 7 em diante).");
    return;
  }

  const nome = sheet.getRange(linha, 2).getValue();
  const limiteUsado = parseFloat(sheet.getRange(linha, 6).getValue()) || 0;

  if (!nome) {
    ui.alert("A linha selecionada está vazia.");
    return;
  }

  if (limiteUsado > 0) {
    ui.alert(
      "❌ EXCLUSÃO IMPEDIDA!\n\n" +
      "O cliente \"" + nome + "\" possui débito pendente no valor de R$ " + limiteUsado.toFixed(2) + ".\n" +
      "Não é permitido apagar cadastros com saldo devedor em aberto."
    );
    return;
  }

  const resposta = ui.alert(
    "CONFIRMAR EXCLUSÃO",
    "Deseja realmente apagar o cadastro de \"" + nome + "\"?\nEsta ação é irreversível.",
    ui.ButtonSet.YES_NO
  );

  if (resposta === ui.Button.YES) {
    sheet.deleteRow(linha);
    ui.alert("✅ Cadastro do cliente removido com sucesso!");
  }
}

/**
 * BOTÃO LUPA (🔍): Busca Inteligente com Filtro Tolerante a Acentos/Codificação
 */
function abrirJanelaBuscaInteligente() {
  const html = HtmlService.createHtmlOutput(`
    <!DOCTYPE html>
    <html>
      <head>
        <base target="_top">
        <style>
          body { font-family: Arial, sans-serif; padding: 10px; font-size: 13px; color: #333; background:#f4f6f9; }
          .busca-box { width: 100%; padding: 8px 10px; box-sizing: border-box; border: 2px solid #007bff; border-radius: 6px; font-size: 14px; margin-bottom: 12px; outline: none; }
          .card-cliente { background: white; border: 1px solid #dcdcdc; margin-bottom: 8px; border-radius: 6px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
          .topo-cliente { padding: 10px; display: flex; align-items: center; justify-content: space-between; cursor: pointer; user-select: none; }
          .topo-cliente:hover { background: #eef5ff; }
          .seta { display: inline-block; transition: transform 0.2s ease; margin-right: 6px; font-size: 11px; color: #007bff; }
          .seta.aberta { transform: rotate(90deg); }
          .tag-debito { font-weight: bold; padding: 3px 8px; border-radius: 4px; font-size: 11px; }
          .debito-alto { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
          .debito-ok { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
          
          .painel-detalhes { display: none; padding: 10px; background: #fafafa; border-top: 1px solid #eee; }
          .tabela-itens { width: 100%; border-collapse: collapse; margin-top: 8px; background: white; border: 1px solid #e0e0e0; font-size: 12px; }
          .tabela-itens th { background: #f1f3f5; color: #495057; text-align: left; padding: 6px; border-bottom: 1px solid #ddd; }
          .tabela-itens td { padding: 6px; border-bottom: 1px solid #eee; }
          .total-box { margin-top: 8px; font-weight: bold; text-align: right; color: #28a745; font-size: 13px; }
          .total-box.devendo { color: #dc3545; }
          
          .btn-exportar { display: inline-block; margin-top: 10px; padding: 6px 12px; background: #17a2b8; color: white; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 12px; }
          .btn-exportar:hover { background: #138496; }
        </style>
      </head>
      <body>
        <input type="text" id="campoBusca" class="busca-box" placeholder="🔎 Digite Nome, CPF, E-mail ou Telefone..." onkeyup="filtrar()">
        <div id="resultadoBusca">Carregando dados...</div>

        <script>
          let listaClientes = [];

          google.script.run.withSuccessHandler((dados) => {
            listaClientes = dados;
            renderizar(listaClientes);
          }).obterTodosClientesComItens();

          function normalizarTexto(txt) {
            if (!txt) return "";
            return txt.toString()
              .toLowerCase()
              .replace(/Ã£/gi, 'a').replace(/Ã¡/gi, 'a').replace(/Ã¢/gi, 'a').replace(/Ã /gi, 'a')
              .replace(/Ã©/gi, 'e').replace(/Ãª/gi, 'e')
              .replace(/Ã­/gi, 'i')
              .replace(/Ã³/gi, 'o').replace(/Ãµ/gi, 'o').replace(/Ã´/gi, 'o')
              .replace(/Ãº/gi, 'u')
              .replace(/Ã§/gi, 'c')
              .normalize("NFD")
              .replace(/[\u0300-\u036f]/g, "");
          }

          function renderizar(lista) {
            const cont = document.getElementById('resultadoBusca');
            if (lista.length === 0) {
              cont.innerHTML = '<p style="color:#6c757d; text-align:center;">Nenhum cliente encontrado.</p>';
              return;
            }
            let html = '';
            lista.forEach((c, idx) => {
              const tagClass = c.limiteUsado > 0 ? 'debito-alto' : 'debito-ok';
              const txtDebito = c.limiteUsado > 0 ? 'Devendo: R$ ' + c.limiteUsado.toFixed(2) : 'Sem Débito';
              
              html += \`
                <div class="card-cliente">
                  <div class="topo-cliente" onclick="alternarDetalhes('\${idx}')">
                    <div>
                      <span class="seta" id="seta-\${idx}">▶</span>
                      <strong>[\${c.id}] \${c.nome}</strong><br>
                      <small style="color:#666; margin-left: 18px;">📱 \${c.celular || 'S/ Tel'} | 📄 CPF: \${c.cpf || 'S/ CPF'}</small>
                    </div>
                    <span class="tag-debito \${tagClass}">\${txtDebito}</span>
                  </div>

                  <div class="painel-detalhes" id="detalhe-\${idx}">
                    <div style="font-size:11px; color:#555; margin-bottom:6px;">
                      \${c.email ? '✉️ ' + c.email + ' | ' : ''}
                      \${c.dataNascimento ? '🎂 Nasc: ' + c.dataNascimento + ' | ' : ''}
                      \${c.sexo ? '👤 Sexo: ' + c.sexo : ''}
                    </div>

                    <div style="display:flex; justify-content:space-between; margin-bottom: 6px;">
                      <span><strong>Limite Total:</strong> R$ \${c.limiteTotal.toFixed(2)}</span>
                      <span><strong>Disponível:</strong> \${c.disponivel}</span>
                    </div>

                    <table class="tabela-itens">
                      <thead>
                        <tr>
                          <th>Item / Descrição</th>
                          <th style="width:40px; text-align:center;">Qtd</th>
                          <th style="width:70px; text-align:right;">Unit.</th>
                          <th style="width:70px; text-align:right;">Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        \${gerarLinhasItens(c.itensDevendo)}
                      </tbody>
                    </table>

                    <div class="total-box \${c.limiteUsado > 0 ? 'devendo' : ''}">
                      TOTAL DEVENDO: R$ \${c.limiteUsado.toFixed(2)}
                    </div>

                    <button class="btn-exportar" onclick="exportarExtrato('\${c.id}')">🖨️ Exportar / Imprimir Extrato</button>
                  </div>
                </div>
              \`;
            });
            cont.innerHTML = html;
          }

          function gerarLinhasItens(itens) {
            if (!itens || itens.length === 0) {
              return '<tr><td colspan="4" style="text-align:center; color:#888;">Nenhuma compra em aberto registrada.</td></tr>';
            }
            return itens.map(i => \`
              <tr>
                <td>\${i.descricao}</td>
                <td style="text-align:center;">\${i.qtd}</td>
                <td style="text-align:right;">R$ \${parseFloat(i.unit).toFixed(2)}</td>
                <td style="text-align:right;">R$ \${parseFloat(i.total).toFixed(2)}</td>
              </tr>
            \`).join('');
          }

          function alternarDetalhes(idx) {
            const painel = document.getElementById('detalhe-' + idx);
            const seta = document.getElementById('seta-' + idx);
            const visivel = painel.style.display === 'block';

            painel.style.display = visivel ? 'none' : 'block';
            if (visivel) {
              seta.classList.remove('aberta');
            } else {
              seta.classList.add('aberta');
            }
          }

          function filtrar() {
            const q = normalizarTexto(document.getElementById('campoBusca').value);
            if (!q) { renderizar(listaClientes); return; }
            
            const filtrados = listaClientes.filter(c => 
              normalizarTexto(c.id).includes(q) ||
              normalizarTexto(c.nome).includes(q) ||
              normalizarTexto(c.cpf).includes(q) ||
              normalizarTexto(c.celular).includes(q) ||
              normalizarTexto(c.email).includes(q) ||
              normalizarTexto(c.dependentes).includes(q)
            );
            renderizar(filtrados);
          }

          function exportarExtrato(id) {
            google.script.run.gerarExtratoImpressao(id);
          }
        </script>
      </body>
    </html>
  `).setWidth(500).setHeight(600);
  
  SpreadsheetApp.getUi().showModalDialog(html, "Busca Inteligente & Crediário");
}

/**
 * BOTÃO LARANJA (SETAS): Abre janela de busca para selecionar o cliente a ser editado.
 */
function editarClienteSelecionado() {
  const html = HtmlService.createHtmlOutput(`
    <!DOCTYPE html>
    <html>
      <head>
        <base target="_top">
        <style>
          body { font-family: Arial, sans-serif; padding: 10px; font-size: 13px; color: #333; background: #f4f6f9; }
          .busca-box { width: 100%; padding: 8px 10px; box-sizing: border-box; border: 2px solid #fd7e14; border-radius: 6px; font-size: 14px; margin-bottom: 12px; outline: none; }
          .card-cliente { background: white; border: 1px solid #dcdcdc; margin-bottom: 8px; border-radius: 6px; padding: 10px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
          .card-cliente:hover { background: #fff8f0; border-color: #fd7e14; }
          .info-cliente { flex-grow: 1; }
          .btn-selecionar { background: #fd7e14; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-weight: bold; cursor: pointer; transition: background 0.2s; }
          .btn-selecionar:hover { background: #e06805; }
        </style>
      </head>
      <body>
        <input type="text" id="campoBusca" class="busca-box" placeholder="🔎 Digite Nome, CPF ou Telefone do Cliente..." onkeyup="filtrar()" autofocus>
        <div id="resultadoBusca">Carregando clientes...</div>

        <script>
          let listaClientes = [];

          google.script.run.withSuccessHandler((dados) => {
            listaClientes = dados;
            renderizar(listaClientes);
          }).obterTodosClientesComItens();

          function normalizarTexto(txt) {
            if (!txt) return "";
            return txt.toString()
              .toLowerCase()
              .normalize("NFD")
              .replace(/[\u0300-\u036f]/g, "");
          }

          function renderizar(lista) {
            const cont = document.getElementById('resultadoBusca');
            if (lista.length === 0) {
              cont.innerHTML = '<p style="color:#6c757d; text-align:center;">Nenhum cliente encontrado.</p>';
              return;
            }
            let html = '';
            lista.forEach((c) => {
              html += \`
                <div class="card-cliente">
                  <div class="info-cliente">
                    <strong>[\${c.id}] \${c.nome}</strong><br>
                    <small style="color:#666;">📱 \${c.celular || 'S/ Tel'} | 📄 CPF: \${c.cpf || 'S/ CPF'}</small>
                  </div>
                  <button class="btn-selecionar" onclick="selecionar('\${c.id}')">✏️ Editar</button>
                </div>
              \`;
            });
            cont.innerHTML = html;
          }

          function filtrar() {
            const q = normalizarTexto(document.getElementById('campoBusca').value);
            if (!q) { renderizar(listaClientes); return; }
            
            const filtrados = listaClientes.filter(c => 
              normalizarTexto(c.id).includes(q) ||
              normalizarTexto(c.nome).includes(q) ||
              normalizarTexto(c.cpf).includes(q) ||
              normalizarTexto(c.celular).includes(q)
            );
            renderizar(filtrados);
          }

          function selecionar(id) {
            google.script.run.abrirEdicaoClientePorId(id);
            google.script.host.close();
          }
        </script>
      </body>
    </html>
  `).setWidth(500).setHeight(550);

  SpreadsheetApp.getUi().showModalDialog(html, "Selecione o Cliente para Editar");
}

/**
 * GERA TELA DE IMPRESSÃO/PDF DO EXTRATO
 */
function gerarExtratoImpressao(clienteId) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName("CLIENTES");
  const dados = sheet.getDataRange().getValues();

  let cliente = null;
  for (let i = 6; i < dados.length; i++) {
    if (String(dados[i][0]) === String(clienteId)) {
      cliente = {
        id: dados[i][0],
        nome: dados[i][1],
        celular: dados[i][2],
        cpf: dados[i][3],
        limiteTotal: parseFloat(dados[i][4]) || 0,
        limiteUsado: parseFloat(dados[i][5]) || 0,
        disponivel: dados[i][6]
      };
      break;
    }
  }

  if (!cliente) return;

  const html = HtmlService.createHtmlOutput(`
    <!DOCTYPE html>
    <html>
      <head>
        <base target="_top">
        <style>
          body { font-family: Arial, sans-serif; padding: 20px; font-size: 12px; }
          h2 { margin-bottom: 2px; }
          .linha-header { border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 15px; }
          .tabela { width: 100%; border-collapse: collapse; margin-top: 15px; }
          .tabela th, .tabela td { border: 1px solid #ccc; padding: 8px; text-align: left; }
          .tabela th { background: #f2f2f2; }
          .total { text-align: right; margin-top: 15px; font-size: 14px; font-weight: bold; }
          .btn-print { margin-bottom: 15px; padding: 8px 15px; background: #28a745; color: white; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; }
          @media print { .btn-print { display: none; } }
        </style>
      </head>
      <body>
        <button class="btn-print" onclick="window.print()">🖨️ Imprimir / Salvar PDF</button>
        <div class="linha-header">
          <h2>EXTRATO DE DEBITOS DA CONTA</h2>
          <span>Data de emissão: ${new Date().toLocaleDateString('pt-BR')}</span>
        </div>
        <div>
          <strong>Cliente:</strong> ${cliente.nome} [${cliente.id}]<br>
          <strong>CPF:</strong> ${cliente.cpf || 'N/A'} | <strong>WhatsApp:</strong> ${cliente.celular || 'N/A'}<br>
          <strong>Limite Total:</strong> R$ ${cliente.limiteTotal.toFixed(2)}
        </div>

        <table class="tabela">
          <thead>
            <tr>
              <th>Item / Descrição</th>
              <th style="width:50px; text-align:center;">Qtd</th>
              <th style="width:80px; text-align:right;">Valor Unit.</th>
              <th style="width:80px; text-align:right;">Total</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td colspan="3">Saldo Em Aberto (Crediário)</td>
              <td style="text-align:right;">R$ ${cliente.limiteUsado.toFixed(2)}</td>
            </tr>
          </tbody>
        </table>

        <div class="total">
          TOTAL A PAGAR: R$ ${cliente.limiteUsado.toFixed(2)}
        </div>
      </body>
    </html>
  `).setWidth(550).setHeight(650);

  SpreadsheetApp.getUi().showModalDialog(html, "Extrato do Cliente - " + cliente.nome);
}

// ============================================================
// FUNÇÕES AUXILIARES E INTEGRAÇÃO DE DADOS
// ============================================================

function abrirEdicaoClientePorId(id) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName("CLIENTES");
  const dados = sheet.getDataRange().getValues();

  for (let i = 6; i < dados.length; i++) {
    if (String(dados[i][0]) === String(id)) {
      let dataNascFormatada = "";
      if (dados[i][21]) {
        if (dados[i][21] instanceof Date) {
          dataNascFormatada = Utilities.formatDate(dados[i][21], ss.getSpreadsheetTimeZone(), "yyyy-MM-dd");
        } else {
          dataNascFormatada = String(dados[i][21]);
        }
      }

      const clienteObj = {
        linhaIndex: i + 1,
        id: dados[i][0],
        nome: dados[i][1],
        celular: dados[i][2],
        cpf: dados[i][3],
        limiteTotal: dados[i][4],
        limiteUsado: dados[i][5],
        aumentoAut: dados[i][7],
        taxa: (parseFloat(dados[i][8]) || 0) * 100,
        semLimite: dados[i][9],
        somenteTitular: dados[i][10],
        obs: dados[i][11],
        dep1: dados[i][12],
        dep2: dados[i][13],
        dep3: dados[i][14],
        dep4: dados[i][15],
        diasJuros: dados[i][16],
        freqJuros: dados[i][17],
        taxaJuros: (parseFloat(dados[i][18]) || 0) * 100,
        jurosMora: dados[i][19],
        endereco: dados[i][20],
        dataNascimento: dataNascFormatada,
        sexo: dados[i][22] || '',
        email: dados[i][23] || ''
      };

      const html = HtmlService.createHtmlOutput(getFormularioHtml(clienteObj))
        .setWidth(480)
        .setHeight(760);
      SpreadsheetApp.getUi().showModalDialog(html, "Editar Cliente - " + clienteObj.nome);
      return;
    }
  }
}

function obterTodosClientesComItens() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName("CLIENTES");
  if (!sheet) return [];

  const dados = sheet.getDataRange().getValues();
  const lista = [];

  for (let i = 6; i < dados.length; i++) {
    if (dados[i][1]) {
      const deps = [dados[i][12], dados[i][13], dados[i][14], dados[i][15]]
        .filter(d => d !== "" && d !== undefined).join(", ");

      const limiteUsado = parseFloat(dados[i][5]) || 0;
      
      let itens = [];
      if (limiteUsado > 0) {
        itens.push({
          descricao: "Compras em Aberto no Crediário",
          qtd: 1,
          unit: limiteUsado,
          total: limiteUsado
        });
      }

      let dataNasc = "";
      if (dados[i][21]) {
        if (dados[i][21] instanceof Date) {
          dataNasc = Utilities.formatDate(dados[i][21], ss.getSpreadsheetTimeZone(), "dd/MM/yyyy");
        } else {
          dataNasc = String(dados[i][21]);
        }
      }

      lista.push({
        id: String(dados[i][0]),
        nome: String(dados[i][1]),
        celular: String(dados[i][2] || ""),
        cpf: String(dados[i][3] || ""),
        limiteTotal: parseFloat(dados[i][4]) || 0,
        limiteUsado: limiteUsado,
        disponivel: dados[i][6] === "ILIMITADO" ? "ILIMITADO" : "R$ " + (parseFloat(dados[i][6])||0).toFixed(2),
        dependentes: deps,
        dataNascimento: dataNasc,
        sexo: String(dados[i][22] || ""),
        email: String(dados[i][23] || ""),
        itensDevendo: itens
      });
    }
  }
  return lista;
}

function verificarDuplicado(cpf, celular, idAtual) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName("CLIENTES");
  if (!sheet) return { duplicado: false };

  const dados = sheet.getDataRange().getValues();
  const cpfLimpo = (cpf || "").replace(/\D/g, "");
  const celLimpo = (celular || "").replace(/\D/g, "");

  for (let i = 6; i < dados.length; i++) {
    if (idAtual && String(dados[i][0]) === String(idAtual)) continue;

    const nomeExistente = dados[i][1];
    const celExistente = String(dados[i][2] || "").replace(/\D/g, "");
    const cpfExistente = String(dados[i][3] || "").replace(/\D/g, "");

    let conflitos = [];
    if (celLimpo && celExistente && celLimpo === celExistente) conflitos.push("Telefone (" + dados[i][2] + ")");
    if (cpfLimpo && cpfExistente && cpfLimpo === cpfExistente) conflitos.push("CPF (" + dados[i][3] + ")");

    if (conflitos.length > 0) {
      return {
        duplicado: true,
        mensagem: "⚠️ ATENÇÃO: Encontrado cadastro com o mesmo " + conflitos.join(" e ") + " pertencente ao cliente:\n» " + nomeExistente
      };
    }
  }
  return { duplicado: false };
}

function salvarClienteScript(dados) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName("CLIENTES");
  if (!sheet) return;

  const limiteTotal = parseFloat(dados.limite) || 0;
  
  if (dados.linhaIndex) {
    const linha = parseInt(dados.linhaIndex);
    const limiteUsado = parseFloat(sheet.getRange(linha, 6).getValue()) || 0;
    const disponivelCalculado = (dados.semLimite === "SIM") ? "ILIMITADO" : (limiteTotal - limiteUsado);

    sheet.getRange(linha, 2).setValue(dados.nome);
    sheet.getRange(linha, 3).setValue(dados.celular);
    sheet.getRange(linha, 4).setValue(dados.cpf);
    sheet.getRange(linha, 5).setValue(limiteTotal);
    sheet.getRange(linha, 7).setValue(disponivelCalculado);
    sheet.getRange(linha, 8).setValue(dados.aumentoAut);
    sheet.getRange(linha, 9).setValue(dados.taxa);
    sheet.getRange(linha, 10).setValue(dados.semLimite);
    sheet.getRange(linha, 11).setValue(dados.somenteTitular);
    sheet.getRange(linha, 12).setValue(dados.obs);
    sheet.getRange(linha, 13).setValue(dados.dep1);
    sheet.getRange(linha, 14).setValue(dados.dep2);
    sheet.getRange(linha, 15).setValue(dados.dep3);
    sheet.getRange(linha, 16).setValue(dados.dep4);
    sheet.getRange(linha, 17).setValue(dados.diasJuros);
    sheet.getRange(linha, 18).setValue(dados.freqJuros);
    sheet.getRange(linha, 19).setValue(dados.taxaJuros);
    sheet.getRange(linha, 20).setValue(dados.jurosMora);
    sheet.getRange(linha, 21).setValue(dados.endereco);
    sheet.getRange(linha, 22).setValue(dados.dataNascimento);
    sheet.getRange(linha, 23).setValue(dados.sexo);
    sheet.getRange(linha, 24).setValue(dados.email);
  } else {
    const limiteUsado = 0;
    const disponivelCalculado = (dados.semLimite === "SIM") ? "ILIMITADO" : (limiteTotal - limiteUsado);
    const totalLinhas = sheet.getLastRow();
    const proximoID = "CLI-" + Math.max(1, totalLinhas - 5);

    sheet.appendRow([
      proximoID,            // A: ID
      dados.nome,           // B: Nome
      dados.celular,        // C: WhatsApp
      dados.cpf,            // D: CPF
      limiteTotal,          // E: Limite Total
      limiteUsado,          // F: Limite Usado
      disponivelCalculado,  // G: Disponível
      dados.aumentoAut,     // H: Aumento Aut.?
      dados.taxa,           // I: % Aumento
      dados.semLimite,      // J: Sem Limite?
      dados.somenteTitular, // K: Somente Titular?
      dados.obs,            // L: Observações
      dados.dep1,           // M: Dependente 1
      dados.dep2,           // N: Dependente 2
      dados.dep3,           // O: Dependente 3
      dados.dep4,           // P: Dependente 4
      dados.diasJuros,      // Q: Dias p/ Juros
      dados.freqJuros,      // R: Frequência Juros
      dados.taxaJuros,      // S: % Juros
      dados.jurosMora,      // T: Juros Mora Legal?
      dados.endereco,       // U: Endereço Completo
      dados.dataNascimento, // V: Data de Nascimento
      dados.sexo,           // W: Sexo
      dados.email           // X: E-mail
    ]);
  }
}

function getFormularioHtml(c) {
  const isEdit = c !== null;
  const cData = c || {
    linhaIndex: '', id: '', nome: '', celular: '', cpf: '', limiteTotal: 500, limiteUsado: 0,
    aumentoAut: 'NÃO', taxa: 0, semLimite: 'NÃO', somenteTitular: 'NÃO', obs: '',
    dep1: '', dep2: '', dep3: '', dep4: '', diasJuros: 30, freqJuros: 'Mensal',
    taxaJuros: 2, jurosMora: 'NÃO', endereco: '', dataNascimento: '', sexo: '', email: ''
  };

  return `
    <!DOCTYPE html>
    <html>
      <head>
        <base target="_top">
        <style>
          body { font-family: Arial, sans-serif; padding: 12px; font-size: 13px; color: #333; }
          .campo { margin-bottom: 8px; }
          label { display: block; font-weight: bold; margin-bottom: 2px; }
          .req { color: #dc3545; font-weight: bold; }
          input[type="text"], input[type="date"], input[type="email"], input[type="number"], select, textarea { 
            width: 100%; padding: 6px; box-sizing: border-box; border: 1px solid #ccc; border-radius: 4px; 
          }
          input:disabled { background-color: #e9ecef; cursor: not-allowed; }
          textarea { height: 45px; resize: none; }
          .row-check { display: flex; align-items: center; gap: 6px; margin: 6px 0; }
          .box-secao { background: #f8f9fa; border: 1px solid #e0e0e0; padding: 8px; border-radius: 4px; margin-top: 8px; transition: opacity 0.2s; }
          .box-juros { background: #fff8e1; border: 1px solid #ffe082; padding: 8px; border-radius: 4px; margin-top: 8px; }
          .box-debito { background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; padding: 8px; border-radius: 4px; margin-bottom: 8px; font-weight: bold; }
          .btn-salvar { 
            width:100%; padding:10px; background:#28a745; color:white; border:none; 
            border-radius:4px; font-weight:bold; cursor:pointer; margin-top:12px; 
          }
          .btn-salvar:hover { background: #218838; }
        </style>
      </head>
      <body>
        <div>
          ${isEdit ? `<div class="box-debito">🔴 Saldo Devedor Atual: R$ ${(parseFloat(cData.limiteUsado)||0).toFixed(2)}</div>` : ''}

          <input type="hidden" id="linhaIndex" value="${cData.linhaIndex}">
          <input type="hidden" id="clienteId" value="${cData.id}">

          <div class="campo">
            <label>Nome Completo: <span class="req">*</span></label>
            <input type="text" id="nome" value="${cData.nome}" placeholder="Ex: João da Silva" required>
          </div>
          
          <div style="display:flex; gap:8px;">
            <div class="campo" style="flex:1;">
              <label>CPF:</label>
              <input type="text" id="cpf" value="${cData.cpf}" placeholder="000.000.000-00">
            </div>
            <div class="campo" style="flex:1;">
              <label>Celular / WhatsApp: <span class="req">*</span></label>
              <input type="text" id="celular" value="${cData.celular}" placeholder="Ex: 11999998888">
            </div>
          </div>

          <div style="display:flex; gap:8px;">
            <div class="campo" style="flex:1;">
              <label>Data de Nascimento:</label>
              <input type="date" id="dataNascimento" value="${cData.dataNascimento}">
            </div>
            <div class="campo" style="flex:1;">
              <label>Sexo:</label>
              <select id="sexo">
                <option value="" ${cData.sexo === '' ? 'selected' : ''}>Selecione...</option>
                <option value="Masculino" ${cData.sexo === 'Masculino' ? 'selected' : ''}>Masculino</option>
                <option value="Feminino" ${cData.sexo === 'Feminino' ? 'selected' : ''}>Feminino</option>
                <option value="Outro" ${cData.sexo === 'Outro' ? 'selected' : ''}>Outro</option>
              </select>
            </div>
          </div>

          <div class="campo">
            <label>E-mail:</label>
            <input type="email" id="email" value="${cData.email}" placeholder="cliente@exemplo.com">
          </div>

          <div class="campo"><label>Endereço Completo:</label><input type="text" id="endereco" value="${cData.endereco}" placeholder="Rua, Nº, Bairro, Cidade"></div>
          
          <div style="display:flex; gap:8px;">
            <div class="campo" style="flex:1;"><label>Limite Total (R$):</label><input type="number" id="limite" value="${cData.limiteTotal}"></div>
            <div class="campo" style="flex:1;"><label>% Aumento Aut.:</label><input type="number" id="taxa" value="${cData.taxa}" ${cData.aumentoAut === 'SIM' ? '' : 'disabled'}></div>
          </div>

          <div class="row-check">
            <input type="checkbox" id="semLimite" ${cData.semLimite === 'SIM' ? 'checked' : ''}>
            <label for="semLimite">Cliente Sem Limite (Ilimitado)</label>
          </div>

          <div class="row-check">
            <input type="checkbox" id="aumentoAut" onchange="alternarAumento()" ${cData.aumentoAut === 'SIM' ? 'checked' : ''}>
            <label for="aumentoAut">Permitir Aumento Automático</label>
          </div>

          <div class="row-check" style="color: #c82333;">
            <input type="checkbox" id="somenteTitular" onchange="alternarDependentes()" ${cData.somenteTitular === 'SIM' ? 'checked' : ''}>
            <label for="somenteTitular"><strong>Apenas Titular Pode Comprar</strong></label>
          </div>

          <div class="box-juros">
            <label style="color:#b78103;">⚙️ Configuração de Juros por Atraso:</label>
            <div style="display:flex; gap:8px; margin-top:4px;">
              <div class="campo" style="flex:1;">
                <label>Cobrar após (dias):</label>
                <input type="number" id="diasJuros" value="${cData.diasJuros}" min="0">
              </div>
              <div class="campo" style="flex:1;">
                <label>Frequência:</label>
                <select id="freqJuros">
                  <option value="Diário" ${cData.freqJuros === 'Diário' ? 'selected' : ''}>Diário</option>
                  <option value="Mensal" ${cData.freqJuros === 'Mensal' ? 'selected' : ''}>Mensal</option>
                  <option value="Bimestral" ${cData.freqJuros === 'Bimestral' ? 'selected' : ''}>Bimestral</option>
                </select>
              </div>
            </div>
            <div style="display:flex; gap:8px;">
              <div class="campo" style="flex:1;">
                <label>% Juros por Tempo:</label>
                <input type="number" id="taxaJuros" value="${cData.taxaJuros}" step="0.1">%
              </div>
            </div>
            <div class="row-check" style="margin-top:2px;">
              <input type="checkbox" id="jurosMora" ${cData.jurosMora === 'SIM' ? 'checked' : ''}>
              <label for="jurosMora">Aplicar Juros de Mora Legal (Teto Regulado)</label>
            </div>
          </div>

          <div class="campo" style="margin-top:8px;">
            <label>Observações do Caixa (Avisos):</label>
            <textarea id="obs" placeholder="Ex: Liberar somente com autorização de Maria.">${cData.obs}</textarea>
          </div>

          <div class="box-secao" id="areaDependentes">
            <label style="color:#0056b3;">Dependentes Autorizados (Até 4):</label>
            <input type="text" id="dep1" value="${cData.dep1}" placeholder="Dependente 1 (ex: Marido - Carlos)" style="margin-bottom:4px;">
            <input type="text" id="dep2" value="${cData.dep2}" placeholder="Dependente 2" style="margin-bottom:4px;">
            <input type="text" id="dep3" value="${cData.dep3}" placeholder="Dependente 3" style="margin-bottom:4px;">
            <input type="text" id="dep4" value="${cData.dep4}" placeholder="Dependente 4">
          </div>

          <button class="btn-salvar" id="btnSalvar" onclick="salvar()">${isEdit ? 'Atualizar Cliente' : 'Salvar Cliente'}</button>
        </div>

        <script>
          function alternarAumento() {
            const ativo = document.getElementById('aumentoAut').checked;
            const campoTaxa = document.getElementById('taxa');
            campoTaxa.disabled = !ativo;
            if (!ativo) campoTaxa.value = 0;
            else if (campoTaxa.value == 0) campoTaxa.value = 5;
          }

          function alternarDependentes() {
            const trava = document.getElementById('somenteTitular').checked;
            const area = document.getElementById('areaDependentes');
            const listaDep = ['dep1', 'dep2', 'dep3', 'dep4'];

            area.style.opacity = trava ? "0.5" : "1";
            listaDep.forEach(id => {
              const campo = document.getElementById(id);
              campo.disabled = trava;
              if (trava) campo.value = "";
            });
          }

          function salvar() {
            const nome = document.getElementById('nome').value.trim();
            const celular = document.getElementById('celular').value.trim();
            const celApenasNumeros = celular.replace(/\D/g, "");
            const cpf = document.getElementById('cpf').value.trim();
            const clienteId = document.getElementById('clienteId').value;

            if (!nome || nome.split(" ").filter(w => w.length > 0).length < 2) {
              alert('Informe o NOME COMPLETO do cliente.');
              document.getElementById('nome').focus();
              return;
            }

            if (!celular || celApenasNumeros.length < 8) {
              alert('Informe um número de Celular/WhatsApp válido.');
              document.getElementById('celular').focus();
              return;
            }

            const btn = document.getElementById('btnSalvar');
            btn.disabled = true;
            btn.innerText = "Verificando dados...";

            google.script.run
              .withSuccessHandler((res) => {
                if (res.duplicado) {
                  const confirma = confirm(res.mensagem + "\\n\\nDeseja realmente prosseguir?");
                  if (!confirma) {
                    btn.disabled = false;
                    btn.innerText = "${isEdit ? 'Atualizar Cliente' : 'Salvar Cliente'}";
                    return;
                  }
                }
                executarSalvamento();
              })
              .verificarDuplicado(cpf, celular, clienteId);
          }

          function executarSalvamento() {
            const btn = document.getElementById('btnSalvar');
            btn.innerText = "Salvando...";

            const aumentoAut = document.getElementById('aumentoAut').checked;

            const dados = {
              linhaIndex: document.getElementById('linhaIndex').value,
              nome: document.getElementById('nome').value.trim(),
              cpf: document.getElementById('cpf').value.trim(),
              celular: document.getElementById('celular').value.trim(),
              dataNascimento: document.getElementById('dataNascimento').value,
              sexo: document.getElementById('sexo').value,
              email: document.getElementById('email').value.trim(),
              endereco: document.getElementById('endereco').value.trim(),
              limite: document.getElementById('limite').value,
              taxa: aumentoAut ? (parseFloat(document.getElementById('taxa').value) / 100) : 0,
              semLimite: document.getElementById('semLimite').checked ? "SIM" : "NÃO",
              aumentoAut: aumentoAut ? "SIM" : "NÃO",
              somenteTitular: document.getElementById('somenteTitular').checked ? "SIM" : "NÃO",
              diasJuros: document.getElementById('diasJuros').value,
              freqJuros: document.getElementById('freqJuros').value,
              taxaJuros: parseFloat(document.getElementById('taxaJuros').value) / 100,
              jurosMora: document.getElementById('jurosMora').checked ? "SIM" : "NÃO",
              obs: document.getElementById('obs').value,
              dep1: document.getElementById('dep1').value,
              dep2: document.getElementById('dep2').value,
              dep3: document.getElementById('dep3').value,
              dep4: document.getElementById('dep4').value
            };

            google.script.run
              .withSuccessHandler(() => google.script.host.close())
              .salvarClienteScript(dados);
          }

          window.onload = function() {
            alternarDependentes();
          };
        </script>
      </body>
    </html>
  `;
}