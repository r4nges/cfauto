// ============================================================================
// SISTEMA DE GESTÃO FINANCEIRA - GOOGLE APPS SCRIPT
// ============================================================================

// ============================================================================
// 0. MENU "GESTÃO FINANCEIRA" (recriado para corrigir o erro de onOpen ausente)
// ============================================================================
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('💰 Gestão Financeira')
    .addItem('➕ Novo Lançamento', 'abrirJanelaSaidaModal')
    .addItem('🔍 Buscar', 'abrirJanelaBuscarModal')
    .addItem('✏️ Editar', 'abrirJanelaEditarModal')
    .addItem('🗑️ Excluir', 'abrirJanelaExcluirModal')
    .addItem('📊 Dashboard', 'abrirJanelaDashboardModal')
    .addItem('📄 Pagar Boleto', 'abrirJanelaPagarBoletoModal')
    .addToUi();
}

// ============================================================================
// 1. ABRIR MODAL: NOVO LANÇAMENTO (SALÁRIO / PRÓ-LABORE / OUTROS)
// ============================================================================
function abrirJanelaSaidaModal() {
  const dataHoje = Utilities.formatDate(new Date(), SpreadsheetApp.getActiveSpreadsheet().getSpreadsheetTimeZone(), "yyyy-MM-dd");

  const html = HtmlService.createHtmlOutput(`
    <!DOCTYPE html>
    <html>
      <head>
        <base target="_top">
        <style>
          * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, sans-serif; }
          body { background: #f8f9fa; margin: 0; padding: 15px; font-size: 13px; color: #333; }
          .card-modal { background: #fff; border-radius: 12px; padding: 18px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); }
          .titulo-modal { font-size: 15px; font-weight: bold; color: #dc3545; display: flex; align-items: center; gap: 8px; margin-bottom: 15px; border-bottom: 2px solid #f1f3f5; padding-bottom: 10px; }
          .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
          .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px; }
          .campo { margin-bottom: 12px; }
          label { display: block; font-weight: 600; font-size: 11px; color: #495057; text-transform: uppercase; margin-bottom: 4px; }
          .req { color: #dc3545; font-weight: bold; }
          input, select { width: 100%; padding: 8px 10px; border: 1px solid #ced4da; border-radius: 6px; font-size: 13px; outline: none; }
          input:focus, select:focus { border-color: #dc3545; box-shadow: 0 0 0 2px rgba(220,53,69,0.15); }
          .box-especial { border-radius: 6px; padding: 10px; margin-bottom: 12px; }
          .box-boleto { background: #eef5ff; border: 1px solid #b6d4fe; }
          .card-parcela-boleto { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px; margin-top: 8px; }
          .box-emprestimo { background: #f3e8ff; border: 1px solid #d8b4fe; }
          .box-salario { background: #f0fdf4; border: 1px solid #bbf7d0; }
          .box-repeticao { background: #fff8e6; border: 1px solid #ffe199; }
          .btn-salvar { width: 100%; padding: 12px; background: #dc3545; color: white; border: none; border-radius: 6px; font-size: 14px; font-weight: bold; cursor: pointer; margin-top: 5px; transition: all 0.2s ease; }
          .btn-salvar:hover:not(:disabled) { background: #bb2d3b; }
          .btn-salvar:disabled { background: #6c757d; opacity: 0.5; cursor: not-allowed; }
          .destaque-valor { font-size: 12px; color: #581c87; margin-top: 6px; background: #fff; padding: 8px; border-radius: 6px; border: 1px solid #e9d5ff; }
          #containerParcelasBoleto { max-height: 220px; overflow-y: auto; padding-right: 4px; }
        </style>
      </head>
      <body>
        <div class="card-modal">
          <div class="titulo-modal">🔴 REGISTRAR DÍVIDA / DESPESA</div>
          
          <div class="campo">
            <label>Categoria:</label>
            <select id="categoria" onchange="alternarCategoria()">
              <option value="Conta Fixa">📌 Conta Fixa</option>
              <option value="Conta Variável">📈 Conta Variável</option>
              <option value="Despesa Prevista">🗓️ Despesa Prevista</option>
              <option value="Despesa Imprevista">⚠️ Despesa Imprevista</option>
              <option value="Boleto">📄 Boleto</option>
              <option value="Empréstimo">🏦 Empréstimo</option>
              <option value="Salário">💼 Salário</option>
              <option value="Pró-Labore">👔 Pró-Labore</option>
              <option value="Outros Proventos">🎁 Outros (Bonificação / Extras)</option>
            </select>
          </div>

          <!-- BLOCO USUÁRIOS (SALÁRIO / PRÓ-LABORE / OUTROS) -->
          <div class="box-especial box-salario" id="boxSalario" style="display:none;">
            <div class="campo">
              <label style="color:#166534;">Colaborador / Usuário (Planilha Linkada):</label>
              <select id="selectUsuario" onchange="selecionarUsuario()"></select>
            </div>
          </div>

          <div class="campo">
            <label>Descrição <span class="req">*</span>:</label>
            <input type="text" id="descricao" required>
          </div>

          <div class="box-especial box-boleto" id="boxBoleto" style="display:none;">
            <div class="campo">
              <label style="color:#0a58ca;">🔍 Código de Barras / Linha Digitável:</label>
              <input type="text" id="codigoBoleto">
            </div>
            <div class="campo" style="margin-bottom:8px;">
              <label style="color:#0a58ca;">N° de Parcelas:</label>
              <input type="number" id="parcelasBoleto" value="1" min="1" max="72" onchange="gerarCamposBoletos()" onkeyup="gerarCamposBoletos()">
            </div>
            <div id="containerParcelasBoleto"></div>
          </div>

          <div class="box-especial box-emprestimo" id="boxEmprestimo" style="display:none;">
            <div class="grid-2">
              <div class="campo"><label style="color:#581c87;">Valor Total Solicitado <span class="req">*</span>:</label><input type="text" id="empTotal"></div>
              <div class="campo"><label style="color:#581c87;">Tipo de Juros:</label><select id="empTipoJuros"><option value="TOTAL">Juros Total (%)</option><option value="MES">Juros ao Mês (%)</option></select></div>
            </div>
            <div class="grid-2">
              <div class="campo"><label style="color:#581c87;">Taxa de Juros (%):</label><input type="text" id="empJuros"></div>
              <div class="campo"><label style="color:#581c87;">Nº Parcelas:</label><input type="number" id="empParcelas" value="1" min="1"></div>
            </div>
            <div class="destaque-valor" id="resumoEmprestimo"><strong>Parcela: 1x de R$ 0,00</strong><br><small>Informe o valor total solicitado para ver a amortização.</small></div>
          </div>

          <div class="campo" id="campoValorNormal">
            <label>Valor Total / Parcela (R$) <span class="req">*</span>:</label>
            <input type="text" id="valor">
          </div>

          <div class="campo" id="campoRepeticaoNormal">
            <label>Repetição (Mensal)?</label>
            <select id="repeticao" onchange="document.getElementById('boxRepeticaoInfo').style.display = (this.value==='SIM'?'block':'none')">
              <option value="NAO">Não</option><option value="SIM">Sim</option>
            </select>
          </div>

          <div id="blocoDatasPadrao">
            <div class="grid-2">
              <div class="campo" id="campoDataInicial"><label>Data Inicial / Vencimento <span class="req">*</span>:</label><input type="date" id="dataInicial" value="${dataHoje}"></div>
              <div class="campo" id="campoDataFinal"><label>Data Final:</label><input type="date" id="dataFinal"></div>
            </div>
          </div>

          <div class="box-especial box-repeticao" id="boxRepeticaoInfo" style="display:none;"><small style="color:#856404;">ℹ️ O sistema gerará registros mensais automaticamente até a <strong>Data Final</strong>.</small></div>

          <div class="campo">
            <label>Status Inicial:</label>
            <select id="status"><option value="PENDENTE">⏳ PENDENTE (A Pagar)</option><option value="PAGO">✅ PAGO / QUITADO</option></select>
          </div>

          <button class="btn-salvar" id="btnSalvar" onclick="salvarSaida()" disabled>💾 SALVAR REGISTRO</button>
        </div>

        <script>
          let listaUsuarios = [];

          function parseMoedaParaFloat(val) { if (!val) return 0; let str = String(val).trim().replace(/[^0-9,-]/g, '').replace(',', '.'); let n = parseFloat(str); return isNaN(n) ? 0 : n; }
          function fmtBRL(n) { return (isNaN(n) || n === null) ? "0,00" : n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }

          function carregarUsuarios() {
            const sel = document.getElementById('selectUsuario');
            if (!sel) return;
            sel.innerHTML = '<option value="">Carregando colaboradores...</option>';

            google.script.run.withSuccessHandler(users => {
              listaUsuarios = users || [];
              sel.innerHTML = '';
              
              if (listaUsuarios.length === 0) {
                sel.innerHTML = '<option value="">⚠️ Nenhum usuário localizado na Coluna A (a partir da linha 7)</option>';
                return;
              }
              
              sel.innerHTML = '<option value="">Selecione um usuário...</option>';
              listaUsuarios.forEach(u => {
                const opt = document.createElement('option');
                opt.value = u.id;
                opt.textContent = u.nome;
                sel.appendChild(opt);
              });
            }).obterUsuariosAtivos();
          }

          function selecionarUsuario() {
            const id = document.getElementById('selectUsuario').value;
            const user = listaUsuarios.find(u => u.id === id);
            const cat = document.getElementById('categoria').value;
            if (user) {
              document.getElementById('descricao').value = cat + ' - ' + user.nome;
              if (user.salarioBase > 0) {
                document.getElementById('valor').value = fmtBRL(user.salarioBase);
              }
              validarFormulario();
            }
          }

          function gerarCamposBoletos() {
            const num = parseInt(document.getElementById('parcelasBoleto').value) || 1;
            const container = document.getElementById('containerParcelasBoleto');
            container.innerHTML = '';
            const dataHojePadrao = "${dataHoje}";

            for (let i = 1; i <= num; i++) {
              const div = document.createElement('div');
              div.className = 'card-parcela-boleto';
              div.innerHTML = 
                '<strong style="font-size:11px; color:#0284c7;">PARCELA ' + i + ' de ' + num + '</strong>' +
                '<div class="grid-3">' +
                  '<div><label style="font-size:9px; color:#0369a1;">DATA FINAL</label><input type="date" class="bol-data" value="' + dataHojePadrao + '"></div>' +
                  '<div><label style="font-size:9px; color:#0369a1;">VALOR (R$)</label><input type="text" class="bol-valor" placeholder="0,00"></div>' +
                  '<div><label style="font-size:9px; color:#0369a1;">TAXA BOLETO</label><input type="text" class="bol-taxa" value="0,00"></div>' +
                '</div>';
              container.appendChild(div);
            }

            container.querySelectorAll('input').forEach(el => {
              ['input', 'keyup', 'change', 'blur'].forEach(evt => el.addEventListener(evt, validarFormulario));
            });
            validarFormulario();
          }

          function validarFormulario() {
            const cat = document.getElementById('categoria').value;
            const desc = document.getElementById('descricao').value.trim();
            let valorValido = false;

            if (cat === 'Boleto') {
              const valores = document.querySelectorAll('.bol-valor');
              if (valores.length > 0) {
                valorValido = Array.from(valores).every(v => parseMoedaParaFloat(v.value) > 0);
              }
            } else if (cat === 'Empréstimo') {
              valorValido = parseMoedaParaFloat(document.getElementById('empTotal').value) > 0;
            } else {
              const dataInicial = document.getElementById('dataInicial').value;
              valorValido = dataInicial !== '' && parseMoedaParaFloat(document.getElementById('valor').value) > 0;
            }

            document.getElementById('btnSalvar').disabled = !(desc !== '' && valorValido);
          }

          function alternarCategoria() {
            const cat = document.getElementById('categoria').value;
            const isSalarioOuProLabore = (cat === 'Salário' || cat === 'Pró-Labore' || cat === 'Outros Proventos');

            document.getElementById('boxBoleto').style.display = (cat === 'Boleto') ? 'block' : 'none';
            document.getElementById('boxEmprestimo').style.display = (cat === 'Empréstimo') ? 'block' : 'none';
            document.getElementById('boxSalario').style.display = isSalarioOuProLabore ? 'block' : 'none';
            
            document.getElementById('campoValorNormal').style.display = (cat === 'Empréstimo' || cat === 'Boleto') ? 'none' : 'block';
            document.getElementById('campoRepeticaoNormal').style.display = (cat === 'Empréstimo' || cat === 'Boleto' || isSalarioOuProLabore) ? 'none' : 'block';
            document.getElementById('blocoDatasPadrao').style.display = (cat === 'Boleto') ? 'none' : 'block';
            document.getElementById('campoDataFinal').style.display = (cat === 'Empréstimo' || cat === 'Boleto' || isSalarioOuProLabore) ? 'none' : 'block';

            if (isSalarioOuProLabore && listaUsuarios.length === 0) carregarUsuarios();
            if (cat === 'Boleto') gerarCamposBoletos();
            if (cat === 'Empréstimo') calcularEmprestimo();
            validarFormulario();
          }

          function calcularEmprestimo() {
            const P = parseMoedaParaFloat(document.getElementById('empTotal').value);
            const tipo = document.getElementById('empTipoJuros').value;
            const taxa = parseMoedaParaFloat(document.getElementById('empJuros').value);
            const n = parseInt(document.getElementById('empParcelas').value) || 1;
            const resumoEl = document.getElementById('resumoEmprestimo');
            if (P <= 0) { resumoEl.innerHTML = '<strong>Parcela: ' + n + 'x de R$ 0,00</strong><br><small>Informe o valor total solicitado para ver a amortização.</small>'; validarFormulario(); return; }
            let pmt = 0, totalComJuros = 0, juros1a = 0, amort1a = 0;
            if (tipo === 'TOTAL') { totalComJuros = P * (1 + taxa / 100); pmt = totalComJuros / n; amort1a = P / n; juros1a = pmt - amort1a; } 
            else { const i = taxa / 100; pmt = (i > 0) ? P * (i * Math.pow(1 + i, n)) / (Math.pow(1 + i, n) - 1) : P / n; totalComJuros = pmt * n; juros1a = P * i; amort1a = pmt - juros1a; }
            resumoEl.innerHTML = '<strong>Parcela: ' + n + 'x de R$ ' + fmtBRL(pmt) + '</strong><br><small>Total: R$ ' + fmtBRL(totalComJuros) + ' | 1ª Amortização: R$ ' + fmtBRL(amort1a) + ' | 1º Juros: R$ ' + fmtBRL(juros1a) + '</small>';
            validarFormulario();
          }

          document.addEventListener('DOMContentLoaded', function() {
            carregarUsuarios();
            document.querySelectorAll('input, select').forEach(el => {
              ['input', 'keyup', 'change', 'blur', 'paste'].forEach(evt => el.addEventListener(evt, () => {
                if (['empTotal', 'empJuros', 'empParcelas', 'empTipoJuros'].includes(el.id)) calcularEmprestimo();
                validarFormulario();
              }));
            });
            validarFormulario();
          });

          function salvarSaida() {
            const cat = document.getElementById('categoria').value;
            const btn = document.getElementById('btnSalvar');
            btn.disabled = true; btn.innerText = "Gravando...";

            let itensBoleto = [];
            if (cat === 'Boleto') {
              const datas = document.querySelectorAll('.bol-data');
              const valores = document.querySelectorAll('.bol-valor');
              const taxas = document.querySelectorAll('.bol-taxa');
              for (let i = 0; i < datas.length; i++) {
                itensBoleto.push({
                  dataFinal: datas[i].value,
                  valor: parseMoedaParaFloat(valores[i].value),
                  taxa: parseMoedaParaFloat(taxas[i].value)
                });
              }
            }

            const dados = {
              categoria: cat,
              idUsuario: document.getElementById('selectUsuario') ? document.getElementById('selectUsuario').value : '',
              descricao: document.getElementById('descricao').value.trim(),
              dataInicial: document.getElementById('dataInicial').value,
              dataFinal: document.getElementById('dataFinal').value,
              status: document.getElementById('status').value,
              valor: parseMoedaParaFloat(document.getElementById('valor').value),
              repeticao: document.getElementById('repeticao').value,
              codigoBoleto: document.getElementById('codigoBoleto').value.trim(),
              parcelasBoleto: parseInt(document.getElementById('parcelasBoleto').value) || 1,
              itensBoleto: itensBoleto,
              empTotal: parseMoedaParaFloat(document.getElementById('empTotal').value),
              empTipoJuros: document.getElementById('empTipoJuros').value,
              empJuros: parseMoedaParaFloat(document.getElementById('empJuros').value),
              empParcelas: parseInt(document.getElementById('empParcelas').value) || 1
            };

            google.script.run.withSuccessHandler(() => google.script.host.close()).salvarRegistroComSalario(dados);
          }
        </script>
      </body>
    </html>
  `).setWidth(520).setHeight(680);
  SpreadsheetApp.getUi().showModalDialog(html, "Lançamento de Dívidas / Saídas / Salários");
}

// ============================================================================
// 2. ABRIR MODAL: BUSCAR / CONSULTAR DÍVIDA
// ============================================================================
function abrirJanelaBuscarModal() {
  const html = HtmlService.createHtmlOutput(`
    <!DOCTYPE html>
    <html>
      <head>
        <base target="_top">
        <style>
          * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, sans-serif; }
          body { background: #f8f9fa; margin: 0; padding: 15px; font-size: 13px; color: #333; }
          .card-modal { background: #fff; border-radius: 12px; padding: 18px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); }
          .titulo-modal { font-size: 15px; font-weight: bold; color: #0284c7; display: flex; align-items: center; gap: 8px; margin-bottom: 15px; border-bottom: 2px solid #f1f3f5; padding-bottom: 10px; }
          .box-busca { background: #f0f9ff; padding: 10px; border-radius: 8px; border: 1px solid #bae6fd; margin-bottom: 15px; }
          label { display: block; font-weight: 600; font-size: 11px; color: #0369a1; text-transform: uppercase; margin-bottom: 4px; }
          input, select { width: 100%; padding: 8px 10px; border: 1px solid #ced4da; border-radius: 6px; font-size: 13px; outline: none; }
          .card-detalhes { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; margin-top: 10px; }
          .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 6px; }
          .badge { padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; display: inline-block; }
          .badge-pago { background: #dcfce7; color: #15803d; }
          .badge-pendente { background: #fee2e2; color: #b91c1c; }
        </style>
      </head>
      <body>
        <div class="card-modal">
          <div class="titulo-modal">🔍 CONSULTAR / BUSCAR DÍVIDA</div>
          <div class="box-busca">
            <label>🔍 Digite ID, Descrição ou Categoria:</label>
            <input type="text" id="filtroBusca" placeholder="Ex: SAI-1 ou Aluguel" oninput="filtrarBusca()">
            <select id="selectBusca" size="4" style="margin-top:5px; height:90px;" onchange="exibirDetalhes()">
              <option value="">Carregando...</option>
            </select>
          </div>

          <div id="painelDetalhes" class="card-detalhes" style="display:none;">
            <div class="grid-2">
              <div><strong>ID:</strong> <span id="detId"></span></div>
              <div><strong>Data Registro:</strong> <span id="detDataReg"></span></div>
            </div>
            <div class="grid-2">
              <div><strong>Categoria:</strong> <span id="detCat"></span></div>
              <div><strong>Status:</strong> <span id="detStatus"></span></div>
            </div>
            <div style="margin-bottom:6px;"><strong>Descrição:</strong> <span id="detDesc"></span></div>
            <div class="grid-2">
              <div><strong>Valor:</strong> R$ <span id="detValor"></span></div>
              <div><strong>Parcela:</strong> <span id="detParcela"></span></div>
            </div>
            <div class="grid-2">
              <div><strong>Vencimento:</strong> <span id="detVenc"></span></div>
              <div><strong>Repetição:</strong> <span id="detRepet"></span></div>
            </div>
            <div style="margin-top:6px; font-size:12px; color:#475569;">
              <strong>Obs / Amortização:</strong><br>
              <span id="detObs" style="word-break: break-all;"></span>
            </div>
          </div>
        </div>

        <script>
          let listaBusca = [];
          document.addEventListener('DOMContentLoaded', function() {
            google.script.run.withSuccessHandler(dados => {
              listaBusca = dados;
              renderizarBusca(listaBusca);
            }).obterListaSaidas();
          });

          function renderizarBusca(lista) {
            const sel = document.getElementById('selectBusca');
            sel.innerHTML = '';
            if(lista.length === 0) { sel.innerHTML = '<option value="">Nenhum registro encontrado</option>'; return; }
            lista.forEach(item => {
              const opt = document.createElement('option');
              opt.value = item.row;
              opt.textContent = '[' + item.id + '] ' + item.descricao + ' - R$ ' + item.valor;
              sel.appendChild(opt);
            });
          }

          function filtrarBusca() {
            const txt = document.getElementById('filtroBusca').value.toLowerCase();
            const filtrados = listaBusca.filter(i => 
              i.id.toLowerCase().includes(txt) || 
              i.descricao.toLowerCase().includes(txt) ||
              i.categoria.toLowerCase().includes(txt)
            );
            renderizarBusca(filtrados);
          }

          function exibirDetalhes() {
            const rowSelected = document.getElementById('selectBusca').value;
            const item = listaBusca.find(i => i.row == rowSelected);
            if(!item) return;

            document.getElementById('detId').innerText = item.id;
            document.getElementById('detDataReg').innerText = item.dataReg;
            document.getElementById('detCat').innerText = item.categoria;
            document.getElementById('detDesc').innerText = item.descricao;
            document.getElementById('detValor').innerText = item.valor;
            document.getElementById('detParcela').innerText = item.parcela;
            document.getElementById('detVenc').innerText = item.vencimento;
            document.getElementById('detRepet').innerText = item.repeticao;
            document.getElementById('detObs').innerText = item.obs || '-';

            const stEl = document.getElementById('detStatus');
            if(item.status.toUpperCase().includes('PAGO')) {
              stEl.innerHTML = '<span class="badge badge-pago">✅ PAGO</span>';
            } else {
              stEl.innerHTML = '<span class="badge badge-pendente">⏳ EM ABERTO</span>';
            }

            document.getElementById('painelDetalhes').style.display = 'block';
          }
        </script>
      </body>
    </html>
  `).setWidth(500).setHeight(520);
  SpreadsheetApp.getUi().showModalDialog(html, "Buscar Dívida");
}

// ============================================================================
// 3. ABRIR MODAL: EDITAR DÍVIDA
// ============================================================================
function abrirJanelaEditarModal() {
  const html = HtmlService.createHtmlOutput(`
    <!DOCTYPE html>
    <html>
      <head>
        <base target="_top">
        <style>
          * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, sans-serif; }
          body { background: #f8f9fa; margin: 0; padding: 15px; font-size: 13px; color: #333; }
          .card-modal { background: #fff; border-radius: 12px; padding: 18px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); }
          .titulo-modal { font-size: 15px; font-weight: bold; color: #d97706; display: flex; align-items: center; gap: 8px; margin-bottom: 15px; border-bottom: 2px solid #f1f3f5; padding-bottom: 10px; }
          .campo { margin-bottom: 12px; }
          label { display: block; font-weight: 600; font-size: 11px; color: #495057; text-transform: uppercase; margin-bottom: 4px; }
          input, select { width: 100%; padding: 8px 10px; border: 1px solid #ced4da; border-radius: 6px; font-size: 13px; outline: none; }
          .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
          .btn-salvar { width: 100%; padding: 12px; background: #d97706; color: white; border: none; border-radius: 6px; font-size: 14px; font-weight: bold; cursor: pointer; margin-top: 10px; }
          .btn-salvar:disabled { background: #6c757d; opacity: 0.5; cursor: not-allowed; }
          .box-busca { background: #fffbe3; padding: 10px; border-radius: 8px; border: 1px solid #fde68a; margin-bottom: 15px; }
        </style>
      </head>
      <body>
        <div class="card-modal">
          <div class="titulo-modal">✏️ EDITAR DÍVIDA REGISTRADA</div>
          <div class="box-busca">
            <label style="color:#b45309;">🔍 Selecionar Dívida para Editar:</label>
            <input type="text" id="filtro" placeholder="Digite ID ou Descrição para buscar..." oninput="filtrarOpcoes()">
            <select id="selectRegistro" size="4" style="margin-top:5px; height:80px;" onchange="carregarDadosEdicao()">
              <option value="">Carregando registros...</option>
            </select>
          </div>
          <div id="formEdicao" style="opacity:0.5; pointer-events:none;">
            <input type="hidden" id="editRow">
            <input type="hidden" id="editId">
            <div class="campo"><label>Descrição:</label><input type="text" id="editDescricao"></div>
            <div class="grid-2">
              <div class="campo"><label>Categoria:</label>
                <select id="editCategoria">
                  <option value="Conta Fixa">📌 Conta Fixa</option>
                  <option value="Conta Variável">📈 Conta Variável</option>
                  <option value="Despesa Prevista">🗓️ Despesa Prevista</option>
                  <option value="Despesa Imprevista">⚠️ Despesa Imprevista</option>
                  <option value="Boleto">📄 Boleto</option>
                  <option value="Empréstimo">🏦 Empréstimo</option>
                  <option value="Salário">💼 Salário</option>
                  <option value="Pró-Labore">👔 Pró-Labore</option>
                  <option value="Outros Proventos">🎁 Outros (Bonificação / Extras)</option>
                </select>
              </div>
              <div class="campo"><label>Valor (R$):</label><input type="text" id="editValor"></div>
            </div>
            <div class="grid-2">
              <div class="campo"><label>Vencimento:</label><input type="text" id="editVencimento" placeholder="DD/MM/AAAA"></div>
              <div class="campo"><label>Status:</label>
                <select id="editStatus"><option value="PENDENTE">⏳ PENDENTE</option><option value="PAGO">✅ PAGO</option></select>
              </div>
            </div>
            <div class="campo"><label>Obs / Amortização:</label><input type="text" id="editObs"></div>
            <button class="btn-salvar" id="btnSalvarEdit" onclick="salvarEdicao()" disabled>💾 ATUALIZAR REGISTRO</button>
          </div>
        </div>
        <script>
          let listaGlobal = [];
          document.addEventListener('DOMContentLoaded', function() {
            google.script.run.withSuccessHandler(dados => {
              listaGlobal = dados;
              renderizarOpcoes(listaGlobal);
            }).obterListaSaidas();
          });
          function renderizarOpcoes(lista) {
            const sel = document.getElementById('selectRegistro');
            sel.innerHTML = '';
            if(lista.length === 0) { sel.innerHTML = '<option value="">Nenhum registro encontrado</option>'; return; }
            lista.forEach(item => {
              const opt = document.createElement('option');
              opt.value = item.row;
              opt.textContent = '[' + item.id + '] ' + item.descricao + ' - R$ ' + item.valor + ' (' + item.status + ')';
              sel.appendChild(opt);
            });
          }
          function filtrarOpcoes() {
            const txt = document.getElementById('filtro').value.toLowerCase();
            const filtrados = listaGlobal.filter(i => i.id.toLowerCase().includes(txt) || i.descricao.toLowerCase().includes(txt));
            renderizarOpcoes(filtrados);
          }
          function carregarDadosEdicao() {
            const rowSelected = document.getElementById('selectRegistro').value;
            const item = listaGlobal.find(i => i.row == rowSelected);
            if (!item) return;
            document.getElementById('editRow').value = item.row;
            document.getElementById('editId').value = item.id;
            document.getElementById('editDescricao').value = item.descricao;
            document.getElementById('editCategoria').value = item.categoria;
            document.getElementById('editValor').value = item.valor;
            document.getElementById('editVencimento').value = item.vencimento;
            document.getElementById('editStatus').value = item.status;
            document.getElementById('editObs').value = item.obs;
            
            const form = document.getElementById('formEdicao');
            form.style.opacity = '1'; form.style.pointerEvents = 'auto';
            document.getElementById('btnSalvarEdit').disabled = false;
          }
          function salvarEdicao() {
            const btn = document.getElementById('btnSalvarEdit');
            btn.disabled = true; btn.innerText = "Atualizando...";
            const payload = {
              row: document.getElementById('editRow').value,
              descricao: document.getElementById('editDescricao').value.trim(),
              categoria: document.getElementById('editCategoria').value,
              valor: document.getElementById('editValor').value,
              vencimento: document.getElementById('editVencimento').value,
              status: document.getElementById('editStatus').value,
              obs: document.getElementById('editObs').value
            };
            google.script.run.withSuccessHandler(() => google.script.host.close()).atualizarSaidaScript(payload);
          }
        </script>
      </body>
    </html>
  `).setWidth(500).setHeight(620);
  SpreadsheetApp.getUi().showModalDialog(html, "Editar Dívida");
}

// ============================================================================
// 4. ABRIR MODAL: EXCLUIR DÍVIDA
// ============================================================================
function abrirJanelaExcluirModal() {
  const html = HtmlService.createHtmlOutput(`
    <!DOCTYPE html>
    <html>
      <head>
        <base target="_top">
        <style>
          * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, sans-serif; }
          body { background: #f8f9fa; margin: 0; padding: 15px; font-size: 13px; color: #333; }
          .card-modal { background: #fff; border-radius: 12px; padding: 18px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); }
          .titulo-modal { font-size: 15px; font-weight: bold; color: #dc3545; display: flex; align-items: center; gap: 8px; margin-bottom: 15px; border-bottom: 2px solid #f1f3f5; padding-bottom: 10px; }
          .box-busca { background: #ffeef0; padding: 10px; border-radius: 8px; border: 1px solid #fecdd3; margin-bottom: 15px; }
          label { display: block; font-weight: 600; font-size: 11px; color: #991b1b; text-transform: uppercase; margin-bottom: 4px; }
          input, select { width: 100%; padding: 8px 10px; border: 1px solid #ced4da; border-radius: 6px; font-size: 13px; outline: none; }
          .btn-excluir { width: 100%; padding: 12px; background: #dc3545; color: white; border: none; border-radius: 6px; font-size: 14px; font-weight: bold; cursor: pointer; margin-top: 15px; }
          .btn-excluir:disabled { background: #6c757d; opacity: 0.5; cursor: not-allowed; }
          .card-info { background: #f8f9fa; border: 1px dashed #ced4da; border-radius: 6px; padding: 10px; margin-top: 10px; }
        </style>
      </head>
      <body>
        <div class="card-modal">
          <div class="titulo-modal">🗑️ EXCLUIR REGISTRO DE DÍVIDA</div>
          <div class="box-busca">
            <label>🔍 Digite o ID ou Descrição para localizar:</label>
            <input type="text" id="filtroExcluir" placeholder="Ex: SAI-1 ou Luz" oninput="filtrarExcluir()">
            <select id="selectExcluir" size="4" style="margin-top:5px; height:90px;" onchange="selecionarParaExcluir()">
              <option value="">Carregando...</option>
            </select>
          </div>
          <div class="card-info" id="infoBox">
            <small style="color:#6c757d;">Selecione um registro acima para confirmar a exclusão.</small>
          </div>
          <button class="btn-excluir" id="btnConfirmarExcluir" onclick="confirmarExclusao()" disabled>🗑️ EXCLUIR DEFINITIVAMENTE</button>
        </div>
        <script>
          let listaExcluir = [];
          document.addEventListener('DOMContentLoaded', function() {
            google.script.run.withSuccessHandler(dados => {
              listaExcluir = dados;
              renderizarExcluir(listaExcluir);
            }).obterListaSaidas();
          });
          function renderizarExcluir(lista) {
            const sel = document.getElementById('selectExcluir');
            sel.innerHTML = '';
            if(lista.length === 0) { sel.innerHTML = '<option value="">Nenhum registro encontrado</option>'; return; }
            lista.forEach(item => {
              const opt = document.createElement('option');
              opt.value = item.row;
              opt.textContent = '[' + item.id + '] ' + item.descricao + ' - R$ ' + item.valor;
              sel.appendChild(opt);
            });
          }
          function filtrarExcluir() {
            const txt = document.getElementById('filtroExcluir').value.toLowerCase();
            const filtrados = listaExcluir.filter(i => i.id.toLowerCase().includes(txt) || i.descricao.toLowerCase().includes(txt));
            renderizarExcluir(filtrados);
          }
          function selecionarParaExcluir() {
            const rowSelected = document.getElementById('selectExcluir').value;
            const item = listaExcluir.find(i => i.row == rowSelected);
            if(!item) return;
            document.getElementById('infoBox').innerHTML = 
              '<strong>Registro Selecionado:</strong><br>' +
              'ID: ' + item.id + ' | Descrição: ' + item.descricao + '<br>' +
              'Valor: R$ ' + item.valor + ' | Vencimento: ' + item.vencimento;
            document.getElementById('btnConfirmarExcluir').disabled = false;
          }
          function confirmarExclusao() {
            const rowSelected = document.getElementById('selectExcluir').value;
            const btn = document.getElementById('btnConfirmarExcluir');
            btn.disabled = true; btn.innerText = "Excluindo...";
            google.script.run.withSuccessHandler(() => google.script.host.close()).excluirSaidaScript(rowSelected);
          }
        </script>
      </body>
    </html>
  `).setWidth(480).setHeight(420);
  SpreadsheetApp.getUi().showModalDialog(html, "Excluir Dívida");
}

// ============================================================================
// 5. ABRIR MODAL: DASHBOARD CORPORATIVO
// ============================================================================
function abrirJanelaDashboardModal() {
  const html = HtmlService.createHtmlOutput(`
    <!DOCTYPE html>
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
          .chart-title { font-weight: bold; font-size: 11px; color: #334155; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }
          .chart-container { position: relative; height: 180px; width: 100%; }
          .btn-fechar { padding: 8px 16px; background: #0f172a; color: white; border: none; border-radius: 20px; font-weight: bold; cursor: pointer; float: right; margin-top: 5px; font-size: 11px; }
          .btn-fechar:hover { background: #334155; }
        </style>
      </head>
      <body>
        <div class="card-modal">
          <div class="header-dash">
            <div class="titulo-modal">📊 DASHBOARD DE GESTÃO E ENDIVIDAMENTO EMPRESARIAL</div>
            <div class="filtros-bar">
              <label>📅 Mês:</label>
              <select id="filtroMes" onchange="carregarDashboard()">
                <option value="TODOS">Todos os Meses</option>
                <option value="1">Janeiro</option><option value="2">Fevereiro</option><option value="3">Março</option>
                <option value="4">Abril</option><option value="5">Maio</option><option value="6">Junho</option>
                <option value="7">Julho</option><option value="8">Agosto</option><option value="9">Setembro</option>
                <option value="10">Outubro</option><option value="11">Novembro</option><option value="12">Dezembro</option>
              </select>

              <label>Ano:</label>
              <select id="filtroAno" onchange="carregarDashboard()">
                <option value="TODOS">Todos</option>
              </select>
            </div>
          </div>

          <div class="kpi-grid">
            <div class="kpi-box"><div class="kpi-title">Total Dívidas Geradas</div><div class="kpi-val" id="kpiTotal" style="color:#0f172a;">R$ 0,00</div></div>
            <div class="kpi-box"><div class="kpi-title">Total Pago no Período</div><div class="kpi-val" id="kpiPago" style="color:#16a34a;">R$ 0,00</div></div>
            <div class="kpi-box"><div class="kpi-title">Ativas (A Vencer)</div><div class="kpi-val" id="kpiAtivas" style="color:#d97706;">R$ 0,00</div></div>
            <div class="kpi-box" style="background:#fff5f5; border-color:#fecdd3;"><div class="kpi-title" style="color:#991b1b;">⚠️ Vencidas</div><div class="kpi-val" id="kpiVencidas" style="color:#dc3545;">R$ 0,00</div></div>
            <div class="kpi-box" style="background:#f3e8ff; border-color:#d8b4fe;"><div class="kpi-title" style="color:#6b21a8;">💸 Custo Juros/Taxas</div><div class="kpi-val" id="kpiJuros" style="color:#7c3aed;">R$ 0,00</div></div>
          </div>

          <div class="charts-grid">
            <div class="chart-card">
              <div class="chart-title">📌 Dívidas por Categoria (%)</div>
              <div class="chart-container"><canvas id="chartCategorias"></canvas></div>
            </div>

            <!-- Alterado: Gráfico de Contas Fixas Mensal no lugar do Top 5 -->
            <div class="chart-card">
              <div class="chart-title">📌 Evolução Mensal - Contas Fixas</div>
              <div class="chart-container"><canvas id="chartContasFixas"></canvas></div>
            </div>

            <div class="chart-card">
              <div class="chart-title">📉 Curva de Amortização (Decaimento Devedor)</div>
              <div class="chart-container"><canvas id="chartCurvaAmortizacao"></canvas></div>
            </div>

            <div class="chart-card">
              <div class="chart-title">📈 Crescimento e Evolução da Dívida</div>
              <div class="chart-container"><canvas id="chartCrescimentoDivida"></canvas></div>
            </div>
          </div>

          <button class="btn-fechar" onclick="google.script.host.close()">Fechar Painel</button>
        </div>

        <script>
          let chartCatObj = null, chartCFObj = null, chartCurvaObj = null, chartCrescObj = null;

          function fmtBRL(n) { return 'R$ ' + (n || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }

          document.addEventListener('DOMContentLoaded', function() {
            carregarDashboard(true);
          });

          function carregarDashboard(primeiraCarga = false) {
            const m = document.getElementById('filtroMes').value;
            const a = document.getElementById('filtroAno').value;

            google.script.run.withSuccessHandler(data => {
              document.getElementById('kpiTotal').innerText = fmtBRL(data.totalGeral);
              document.getElementById('kpiPago').innerText = fmtBRL(data.totalQuitadas);
              document.getElementById('kpiAtivas').innerText = fmtBRL(data.totalAtivas);
              document.getElementById('kpiVencidas').innerText = fmtBRL(data.totalVencidas);
              document.getElementById('kpiJuros').innerText = fmtBRL(data.totalJurosTaxas);

              if (primeiraCarga) {
                const selAno = document.getElementById('filtroAno');
                selAno.innerHTML = '<option value="TODOS">Todos os Anos</option>';
                data.anosDisponiveis.forEach(ano => {
                  const opt = document.createElement('option');
                  opt.value = ano; opt.textContent = ano;
                  selAno.appendChild(opt);
                });
              }

              renderizarGraficoCategorias(data.categorias);
              renderizarGraficoContasFixas(data.contasFixasMensal);
              renderizarCurvaAmortizacao(data.evolucaoMensal);
              renderizarCrescimentoDivida(data.evolucaoMensal);

            }).obterDadosDashboard(m, a);
          }

          function renderizarGraficoCategorias(categoriasMap) {
            const ctx = document.getElementById('chartCategorias').getContext('2d');
            if (chartCatObj) chartCatObj.destroy();
            const labels = Object.keys(categoriasMap);
            const valores = Object.values(categoriasMap);
            const totalSuma = valores.reduce((a, b) => a + b, 0);

            chartCatObj = new Chart(ctx, {
              type: 'doughnut',
              data: {
                labels: labels.length > 0 ? labels : ['Sem dados'],
                datasets: [{
                  data: valores.length > 0 ? valores : [1],
                  backgroundColor: ['#dc3545', '#0284c7', '#d97706', '#16a34a', '#8b5cf6', '#ec4899', '#64748b', '#10b981', '#f59e0b']
                }]
              },
              options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                  legend: {
                    position: 'right',
                    labels: {
                      boxWidth: 8, font: { size: 9 },
                      generateLabels: function(chart) {
                        const data = chart.data;
                        if (data.labels.length && data.datasets.length) {
                          return data.labels.map((label, i) => {
                            const val = data.datasets[0].data[i] || 0;
                            const pct = totalSuma > 0 ? ((val / totalSuma) * 100).toFixed(1) + '%' : '0%';
                            return { text: label + ' (' + pct + ')', fillStyle: data.datasets[0].backgroundColor[i], index: i };
                          });
                        }
                        return [];
                      }
                    }
                  }
                }
              }
            });
          }

          // Gráfico de Contas Fixas por mês
          function renderizarGraficoContasFixas(cfData) {
            const ctx = document.getElementById('chartContasFixas').getContext('2d');
            if (chartCFObj) chartCFObj.destroy();

            chartCFObj = new Chart(ctx, {
              type: 'bar',
              data: {
                labels: cfData.labels.length > 0 ? cfData.labels : ['Sem dados'],
                datasets: [{
                  label: 'Contas Fixas (R$)', 
                  data: cfData.valores.length > 0 ? cfData.valores : [0], 
                  backgroundColor: '#0ea5e9', 
                  borderRadius: 4 
                }]
              },
              options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { 
                  legend: { display: false },
                  tooltip: { callbacks: { label: (c) => ' Total: ' + fmtBRL(c.raw) } }
                },
                scales: { 
                  x: { ticks: { font: { size: 9 } } }, 
                  y: { ticks: { font: { size: 9 } } } 
                }
              }
            });
          }

          function renderizarCurvaAmortizacao(evolucao) {
            const ctx = document.getElementById('chartCurvaAmortizacao').getContext('2d');
            if (chartCurvaObj) chartCurvaObj.destroy();

            chartCurvaObj = new Chart(ctx, {
              type: 'line',
              data: {
                labels: evolucao.labels,
                datasets: [{
                  label: 'Saldo Devedor Das Dívidas Atuais (R$)',
                  data: evolucao.saldoDevedor,
                  borderColor: '#dc3545',
                  backgroundColor: 'rgba(220, 53, 69, 0.1)',
                  fill: true,
                  tension: 0.3,
                  pointRadius: 3
                }]
              },
              options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                  tooltip: { callbacks: { label: (c) => ' Saldo Devedor: ' + fmtBRL(c.raw) } }
                },
                scales: { y: { ticks: { font: { size: 8 } } }, x: { ticks: { font: { size: 8 } } } }
              }
            });
          }

          function renderizarCrescimentoDivida(evolucao) {
            const ctx = document.getElementById('chartCrescimentoDivida').getContext('2d');
            if (chartCrescObj) chartCrescObj.destroy();

            chartCrescObj = new Chart(ctx, {
              type: 'bar',
              data: {
                labels: evolucao.labels,
                datasets: [
                  {
                    type: 'line',
                    label: 'Endividamento Acumulado (R$)',
                    data: evolucao.crescimentoAcumulado,
                    borderColor: '#7c3aed',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.3,
                    yAxisID: 'y'
                  },
                  {
                    type: 'bar',
                    label: 'Novas Dívidas no Mês (R$)',
                    data: evolucao.novasDividasMes,
                    backgroundColor: '#0284c7',
                    borderRadius: 4,
                    yAxisID: 'y'
                  }
                ]
              },
              options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                  legend: { position: 'top', labels: { boxWidth: 8, font: { size: 9 } } },
                  tooltip: { callbacks: { label: (c) => ' ' + c.dataset.label + ': ' + fmtBRL(c.raw) } }
                },
                scales: {
                  x: { ticks: { font: { size: 8 } } },
                  y: { ticks: { font: { size: 8 } } }
                }
              }
            });
          }
        </script>
      </body>
    </html>
  `).setWidth(800).setHeight(560);
  SpreadsheetApp.getUi().showModalDialog(html, "Dashboard de Gestão de Dívidas");
}

// ============================================================================
// 6. ABRIR MODAL: PAGAR DÍVIDA / BOLETO
// ============================================================================
function abrirJanelaPagarBoletoModal() {
  const dataHoje = Utilities.formatDate(new Date(), SpreadsheetApp.getActiveSpreadsheet().getSpreadsheetTimeZone(), "yyyy-MM-dd");

  const html = HtmlService.createHtmlOutput(`
    <!DOCTYPE html>
    <html>
      <head>
        <base target="_top">
        <style>
          * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, sans-serif; }
          body { background: #f8f9fa; margin: 0; padding: 15px; font-size: 13px; color: #333; }
          .card-modal { background: #fff; border-radius: 12px; padding: 18px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); }
          .titulo-modal { font-size: 15px; font-weight: bold; color: #15803d; display: flex; align-items: center; gap: 8px; margin-bottom: 15px; border-bottom: 2px solid #f1f3f5; padding-bottom: 10px; }
          .box-busca { background: #f0fdf4; padding: 10px; border-radius: 8px; border: 1px solid #bbf7d0; margin-bottom: 12px; }
          label { display: block; font-weight: 600; font-size: 11px; color: #166534; text-transform: uppercase; margin-bottom: 4px; }
          input, select { width: 100%; padding: 8px 10px; border: 1px solid #ced4da; border-radius: 6px; font-size: 13px; outline: none; }
          .card-detalhes { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; margin-top: 10px; }
          .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
          .btn-pagar { width: 100%; padding: 12px; background: #16a34a; color: white; border: none; border-radius: 6px; font-size: 14px; font-weight: bold; cursor: pointer; margin-top: 12px; transition: all 0.2s ease; }
          .btn-pagar:hover:not(:disabled) { background: #15803d; }
          .btn-pagar:disabled { background: #6c757d; opacity: 0.5; cursor: not-allowed; }
          .status-tag { display: inline-block; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; margin-top: 4px; }
          .tag-verde { background: #dcfce7; color: #15803d; }
          .tag-amarelo { background: #fef9c3; color: #a16207; }
          .tag-laranja { background: #ffedd5; color: #c2410c; }
          .tag-vermelho { background: #fee2e2; color: #b91c1c; }
        </style>
      </head>
      <body>
        <div class="card-modal">
          <div class="titulo-modal">💳 REGISTRAR PAGAMENTO DE DÍVIDA</div>
          
          <div class="box-busca">
            <label>🔍 Selecionar Dívida Pendente (Ordenado por Vencimento):</label>
            <input type="text" id="filtroBoleto" placeholder="Filtrar por nome ou código..." oninput="filtrarBoletos()">
            
            <select id="selectBoleto" size="10" style="margin-top:6px; height:220px;" onchange="exibirDetalhesBoleto()">
              <option value="">Carregando dívidas pendentes...</option>
            </select>
          </div>

          <div id="painelDetalhesBoleto" class="card-detalhes" style="display:none;">
            <div class="grid-2">
              <div><strong>ID:</strong> <span id="pagId"></span></div>
              <div><strong>Categoria:</strong> <span id="pagCat"></span></div>
            </div>
            <div style="margin-top:5px;"><strong>Descrição:</strong> <span id="pagDesc"></span></div>
            <div class="grid-2" style="margin-top:5px;">
              <div><strong>Valor:</strong> <span style="font-weight:bold; color:#16a34a;">R$ <span id="pagValor"></span></span></div>
              <div><strong>Vencimento:</strong> <span id="pagVenc"></span></div>
            </div>
            <div style="margin-top:5px;">
              <strong>Prazo / Status:</strong><br>
              <div id="pagBadge"></div>
            </div>
            <div style="margin-top:5px; font-size:11px; color:#475569;" id="boxObsContainer">
              <strong>Obs / Código de Barras:</strong> <span id="pagObs" style="word-break: break-all;"></span>
            </div>
            <hr style="border:none; border-top:1px solid #e2e8f0; margin:10px 0;">
            <div class="campo">
              <label style="color:#166534;">Data do Pagamento:</label>
              <input type="date" id="dataPagamento" value="${dataHoje}">
            </div>
            <button class="btn-pagar" id="btnConfirmarPagamento" onclick="confirmarPagamento()">✅ REGISTRAR PAGAMENTO</button>
          </div>
        </div>

        <script>
          let listaBoletos = [];

          document.addEventListener('DOMContentLoaded', function() {
            google.script.run.withSuccessHandler(dados => {
              listaBoletos = dados;
              renderizarBoletos(listaBoletos);
            }).obterBoletosPendentes();
          });

          function renderizarBoletos(lista) {
            const sel = document.getElementById('selectBoleto');
            sel.innerHTML = '';
            if(lista.length === 0) { 
              sel.innerHTML = '<option value="">Nenhuma dívida pendente encontrada</option>'; 
              return; 
            }
            lista.forEach(item => {
              const opt = document.createElement('option');
              opt.value = item.row;
              opt.textContent = item.corBolinha + ' [' + item.vencimento + '] ' + item.descricao + ' - R$ ' + item.valor;
              sel.appendChild(opt);
            });
          }

          function filtrarBoletos() {
            const txt = document.getElementById('filtroBoleto').value.toLowerCase();
            const filtrados = listaBoletos.filter(i => 
              i.id.toLowerCase().includes(txt) || 
              i.descricao.toLowerCase().includes(txt) ||
              i.categoria.toLowerCase().includes(txt)
            );
            renderizarBoletos(filtrados);
          }

          function exibirDetalhesBoleto() {
            const rowSelected = document.getElementById('selectBoleto').value;
            const item = listaBoletos.find(i => i.row == rowSelected);
            if(!item) return;

            document.getElementById('pagId').innerText = item.id;
            document.getElementById('pagCat').innerText = item.categoria;
            document.getElementById('pagDesc').innerText = item.descricao;
            document.getElementById('pagValor').innerText = item.valor;
            document.getElementById('pagVenc').innerText = item.vencimento;
            document.getElementById('pagObs').innerText = item.obs || '-';

            const badgeEl = document.getElementById('pagBadge');
            let classeTag = 'tag-verde';
            if(item.corBolinha === '🔴') classeTag = 'tag-vermelho';
            else if(item.corBolinha === '🟠') classeTag = 'tag-laranja';
            else if(item.corBolinha === '🟡') classeTag = 'tag-amarelo';

            badgeEl.innerHTML = '<span class="status-tag ' + classeTag + '">' + item.corBolinha + ' ' + item.statusTexto + '</span>';
            document.getElementById('painelDetalhesBoleto').style.display = 'block';
          }

          function confirmarPagamento() {
            const rowSelected = document.getElementById('selectBoleto').value;
            const dataPag = document.getElementById('dataPagamento').value;
            const btn = document.getElementById('btnConfirmarPagamento');
            btn.disabled = true; 
            btn.innerText = "Processando...";

            const payload = {
              row: rowSelected,
              dataPagamento: dataPag
            };

            google.script.run.withSuccessHandler(() => {
              google.script.host.close();
            }).confirmarPagamentoSaidaScript(payload);
          }
        </script>
      </body>
    </html>
  `).setWidth(520).setHeight(660);
  SpreadsheetApp.getUi().showModalDialog(html, "Pagar Dívidas");
}

// ============================================================================
// 7. FUNÇÕES BACKEND / OPERAÇÕES DA PLANILHA
// ============================================================================

function obterOuCriarAba(nomeAba) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(nomeAba);
  if (!sheet) {
    sheet = ss.insertSheet(nomeAba);
  }
  return sheet;
}

// BUSCA DIRETA DOS USUÁRIOS NA COLUNA A DO LINK ENVIADO (A PARTIR DA LINHA 7)
function obterUsuariosAtivos() {
  const idPlanilha = "1UtU74AmVxtfjupGB9BZkr6AdSjUCE9cQWKO7mU-m8gs";
  let ss;
  
  try {
    ss = SpreadsheetApp.openById(idPlanilha);
  } catch (e) {
    ss = SpreadsheetApp.getActiveSpreadsheet();
  }

  if (!ss) return [];

  const aba = ss.getSheets()[0];
  if (!aba) return [];

  const ultimaLinha = aba.getLastRow();
  // Se a última linha da planilha com dados for menor que 7, não tem usuários.
  if (ultimaLinha < 7) return [];

  // Pega os valores da COLUNA A a partir da LINHA 7
  const valoresA = aba.getRange(7, 1, ultimaLinha - 6, 1).getValues();
  const lista = [];

  for (let r = 0; r < valoresA.length; r++) {
    const nomeVal = String(valoresA[r][0] || "").trim();
    if (!nomeVal) continue;

    lista.push({
      id: 'USR-' + (lista.length + 1),
      nome: nomeVal,
      salarioBase: 0
    });
  }

  return lista;
}

function salvarRegistroComSalario(d) {
  salvarSaidaModalScript(d);
}

function salvarSaidaModalScript(d) {
  const sheet = obterOuCriarAba("SAÍDAS");
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const tz = ss.getSpreadsheetTimeZone();
  const dtHojeStr = Utilities.formatDate(new Date(), tz, "dd/MM/yyyy");

  const [y, m, day] = (d.dataInicial || "").split("-").map(Number);
  let dt = (y && m && day) ? new Date(y, m - 1, day) : new Date();
  const rows = [];

  function fmtBRL(n) { return (n || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }

  if (d.categoria === "Empréstimo") {
    const P = d.empTotal, n = d.empParcelas, taxa = d.empJuros, tipo = d.empTipoJuros;
    const iRate = (tipo === "MES") ? taxa / 100 : 0;
    const pmt = (tipo === "TOTAL") ? (P * (1 + taxa / 100)) / n : (iRate > 0 ? P * (iRate * Math.pow(1 + iRate, n)) / (Math.pow(1 + iRate, n) - 1) : P / n);

    let saldo = P;
    for (let k = 1; k <= n; k++) {
      let jurosK = (tipo === "TOTAL") ? (pmt - P / n) : (saldo * iRate);
      let amortK = (tipo === "TOTAL") ? (P / n) : (pmt - jurosK);
      saldo = (k === n) ? 0 : Math.max(0, saldo - amortK);
      const dtVencStr = Utilities.formatDate(dt, tz, "dd/MM/yyyy");
      const obs = "Amortização: R$ " + fmtBRL(amortK) + " | Juros: R$ " + fmtBRL(jurosK) + " | Saldo: R$ " + fmtBRL(saldo);
      rows.push(["", dtHojeStr, "Empréstimo", d.descricao, pmt, k + "/" + n, dtVencStr, k === 1 ? d.status : "PENDENTE", "SIM", obs]);
      dt.setMonth(dt.getMonth() + 1);
    }
  } else if (d.categoria === "Boleto" && d.itensBoleto && d.itensBoleto.length > 0) {
    const total = d.itensBoleto.length;
    d.itensBoleto.forEach((item, idx) => {
      const k = idx + 1;
      const [by, bm, bd] = item.dataFinal.split("-").map(Number);
      const dtItem = new Date(by, bm - 1, bd);
      const dtVencStr = Utilities.formatDate(dtItem, tz, "dd/MM/yyyy");
      
      const valorTotalComTaxa = item.valor + item.taxa;
      let obsBoleto = d.codigoBoleto ? "Código: " + d.codigoBoleto : "";
      if (item.taxa > 0) {
        obsBoleto += (obsBoleto ? " | " : "") + "Taxa Boleto: R$ " + fmtBRL(item.taxa);
      }

      const descItem = total > 1 ? d.descricao + " (" + k + "/" + total + ")" : d.descricao;
      rows.push(["", dtHojeStr, "Boleto", descItem, valorTotalComTaxa, k + "/" + total, dtVencStr, k === 1 ? d.status : "PENDENTE", "SIM", obsBoleto]);
    });
  } else if (d.repeticao === "SIM" && d.dataFinal) {
    const [fy, fm, fd] = d.dataFinal.split("-").map(Number);
    const dtEnd = new Date(fy, fm - 1, fd);
    const totalMeses = (fy - y) * 12 + (fm - m) + 1;
    let k = 1;
    while (dt <= dtEnd) {
      const dtVencStr = Utilities.formatDate(dt, tz, "dd/MM/yyyy");
      rows.push(["", dtHojeStr, d.categoria, d.descricao, d.valor, totalMeses > 0 ? (k + "/" + totalMeses) : (k + "ª"), dtVencStr, k === 1 ? d.status : "PENDENTE", "SIM", d.codigoBoleto || ""]);
      dt.setMonth(dt.getMonth() + 1); k++;
    }
  } else {
    const dtVencStr = Utilities.formatDate(dt, tz, "dd/MM/yyyy");
    rows.push(["", dtHojeStr, d.categoria, d.descricao, d.valor, "1/1", dtVencStr, d.status, d.repeticao, d.codigoBoleto || ""]);
  }

  const startRow = Math.max(7, sheet.getLastRow() + 1);
  rows.forEach((r, idx) => { r[0] = "SAI-" + (startRow + idx - 6); });
  sheet.getRange(startRow, 1, rows.length, 10).setValues(rows);
}

function obterListaSaidas() {
  const sheet = obterOuCriarAba("SAÍDAS");
  const lastRow = sheet.getLastRow();
  if (lastRow < 7) return [];
  const dados = sheet.getRange(7, 1, lastRow - 6, 10).getValues();
  const lista = [];
  
  dados.forEach((row, idx) => {
    if (row[0]) {
      let valFormatted = row[4];
      if (typeof valFormatted === 'number') valFormatted = valFormatted.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      let dataRegFormatted = row[1];
      if (dataRegFormatted instanceof Date) dataRegFormatted = Utilities.formatDate(dataRegFormatted, SpreadsheetApp.getActiveSpreadsheet().getSpreadsheetTimeZone(), "dd/MM/yyyy");
      let vencFormatted = row[6];
      if (vencFormatted instanceof Date) vencFormatted = Utilities.formatDate(vencFormatted, SpreadsheetApp.getActiveSpreadsheet().getSpreadsheetTimeZone(), "dd/MM/yyyy");

      lista.push({
        row: idx + 7,
        id: String(row[0]),
        dataReg: dataRegFormatted || "-",
        categoria: String(row[2]),
        descricao: String(row[3]),
        valor: valFormatted,
        parcela: String(row[5]),
        vencimento: vencFormatted || "-",
        status: String(row[7]),
        repeticao: String(row[8]),
        obs: String(row[9])
      });
    }
  });
  return lista.reverse();
}

function obterBoletosPendentes() {
  const sheet = obterOuCriarAba("SAÍDAS");
  const lastRow = sheet.getLastRow();
  if (lastRow < 7) return [];
  
  const dados = sheet.getRange(7, 1, lastRow - 6, 10).getValues();
  const tz = SpreadsheetApp.getActiveSpreadsheet().getSpreadsheetTimeZone();
  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);

  const lista = [];

  dados.forEach((row, idx) => {
    const status = String(row[7]).toUpperCase();
    if (row[0] && !status.includes("PAGO")) {
      let dtVenc = row[6];
      let dtVencObj = null;

      if (dtVenc instanceof Date) {
        dtVencObj = new Date(dtVenc.getTime());
      } else if (typeof dtVenc === 'string' && dtVenc.includes('/')) {
        const parts = dtVenc.split('/');
        dtVencObj = new Date(parts[2], parts[1] - 1, parts[0]);
      }

      let diasDiff = 0;
      let corBolinha = '🟢';
      let statusTexto = '';
      let vencFormatted = dtVencObj ? Utilities.formatDate(dtVencObj, tz, "dd/MM/yyyy") : (String(row[6]) || "-");

      if (dtVencObj) {
        dtVencObj.setHours(0, 0, 0, 0);
        const diffTime = dtVencObj.getTime() - hoje.getTime();
        diasDiff = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

        if (diasDiff < 0) {
          corBolinha = '🔴';
          const diasAtraso = Math.abs(diasDiff);
          statusTexto = `VENCIDO há ${diasAtraso} ${diasAtraso === 1 ? 'dia' : 'dias'}`;
        } else if (diasDiff <= 1) {
          corBolinha = '🟠';
          statusTexto = diasDiff === 0 ? 'Vence HOJE' : 'Vence AMANHÃ';
        } else if (diasDiff <= 9) {
          corBolinha = '🟡';
          statusTexto = `Vence em ${diasDiff} dias`;
        } else {
          corBolinha = '🟢';
          statusTexto = `Prazo de ${diasDiff} dias`;
        }
      }

      let valFormatted = row[4];
      if (typeof valFormatted === 'number') valFormatted = valFormatted.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

      lista.push({
        row: idx + 7,
        id: String(row[0]),
        categoria: String(row[2]),
        descricao: String(row[3]),
        valor: valFormatted,
        vencimento: vencFormatted,
        dtVencTimestamp: dtVencObj ? dtVencObj.getTime() : 0,
        status: String(row[7]),
        obs: String(row[9]),
        diasDiff: diasDiff,
        corBolinha: corBolinha,
        statusTexto: statusTexto
      });
    }
  });

  lista.sort((a, b) => a.dtVencTimestamp - b.dtVencTimestamp);
  return lista;
}

function confirmarPagamentoSaidaScript(p) {
  const sheet = obterOuCriarAba("SAÍDAS");
  const r = parseInt(p.row);
  if (r >= 7) {
    sheet.getRange(r, 8).setValue("PAGO");
    if (p.dataPagamento) {
      const tz = SpreadsheetApp.getActiveSpreadsheet().getSpreadsheetTimeZone();
      const [y, m, d] = p.dataPagamento.split("-").map(Number);
      const dtPag = new Date(y, m - 1, d);
      const dtPagStr = Utilities.formatDate(dtPag, tz, "dd/MM/yyyy");
      let obsAtual = String(sheet.getRange(r, 10).getValue() || "");
      let novaObs = obsAtual ? `${obsAtual} | Pago em: ${dtPagStr}` : `Pago em: ${dtPagStr}`;
      sheet.getRange(r, 10).setValue(novaObs);
    }
    
    // =========================================================================
    // TRANSFERÊNCIA AUTOMÁTICA DE DADOS AO CONFIRMAR PAGAMENTO (MODAL)
    // =========================================================================
    const urlPlanilhaDestino = "https://docs.google.com/spreadsheets/d/1119HW8n6Ma-H83wbLw9I13bTJ9EgJhhpciPFyyaUXI8/edit";
    const gidDestino = 568036251;
    try {
      const ultimaColuna = sheet.getLastColumn();
      const dadosDaConta = sheet.getRange(r, 1, 1, ultimaColuna).getValues()[0];
      const planilhaDestino = SpreadsheetApp.openByUrl(urlPlanilhaDestino);
      const abaDestino = planilhaDestino.getSheets().find(function(aba) {
        return aba.getSheetId() === gidDestino;
      });
      if (abaDestino) {
        abaDestino.appendRow(dadosDaConta);
      } else {
        Logger.log("Não encontrei a aba com o gid " + gidDestino);
      }
    } catch (erro) {
      Logger.log("Erro ao transferir os dados da dívida paga: " + erro);
    }
    // =========================================================================
  }
}

function atualizarSaidaScript(p) {
  const sheet = obterOuCriarAba("SAÍDAS");
  const r = parseInt(p.row);
  if (r >= 7) {
    let numVal = String(p.valor).replace(/[^0-9,-]/g, '').replace(',', '.');
    sheet.getRange(r, 3).setValue(p.categoria);
    sheet.getRange(r, 4).setValue(p.descricao);
    sheet.getRange(r, 5).setValue(parseFloat(numVal) || 0);
    sheet.getRange(r, 7).setValue(p.vencimento);
    sheet.getRange(r, 8).setValue(p.status);
    sheet.getRange(r, 10).setValue(p.obs);

    // =========================================================================
    // TRANSFERÊNCIA AUTOMÁTICA SE A CONTA FOR EDITADA MANUALMENTE PARA "PAGO"
    // =========================================================================
    if (p.status === "PAGO") {
      const urlPlanilhaDestino = "https://docs.google.com/spreadsheets/d/1119HW8n6Ma-H83wbLw9I13bTJ9EgJhhpciPFyyaUXI8/edit";
      const gidDestino = 568036251;
      try {
        const ultimaColuna = sheet.getLastColumn();
        const dadosDaConta = sheet.getRange(r, 1, 1, ultimaColuna).getValues()[0];
        const planilhaDestino = SpreadsheetApp.openByUrl(urlPlanilhaDestino);
        const abaDestino = planilhaDestino.getSheets().find(function(aba) {
          return aba.getSheetId() === gidDestino;
        });
        if (abaDestino) {
          abaDestino.appendRow(dadosDaConta);
        } else {
          Logger.log("Não encontrei a aba com o gid " + gidDestino);
        }
      } catch (erro) {
        Logger.log("Erro ao transferir os dados da dívida paga: " + erro);
      }
    }
    // =========================================================================
  }
}

function excluirSaidaScript(rowNum) {
  const sheet = obterOuCriarAba("SAÍDAS");
  const r = parseInt(rowNum);
  if (r >= 7) {
    sheet.deleteRow(r);
  }
}

function obterDadosDashboard(filtroMes, filtroAno) {
  const sheet = obterOuCriarAba("SAÍDAS");
  const lastRow = sheet.getLastRow();
  const tz = SpreadsheetApp.getActiveSpreadsheet().getSpreadsheetTimeZone();
  
  let totalGeral = 0, totalQuitadas = 0, totalAtivas = 0, totalVencidas = 0, totalJurosTaxas = 0;
  const categorias = {}, anosSet = new Set(), mapaMensal = {};
  const mapaContasFixas = {}; // Novo mapa para as Contas Fixas

  const hoje = new Date(); hoje.setHours(0, 0, 0, 0);

  if (lastRow >= 7) {
    const dados = sheet.getRange(7, 1, lastRow - 6, 10).getValues();

    dados.forEach(row => {
      if (!row[0]) return;

      let dtVencObj = null;
      let dtVenc = row[6];
      if (dtVenc instanceof Date) {
        dtVencObj = new Date(dtVenc.getTime());
      } else if (typeof dtVenc === 'string' && dtVenc.includes('/')) {
        const parts = dtVenc.split('/');
        dtVencObj = new Date(parts[2], parts[1] - 1, parts[0]);
      }

      if (dtVencObj) anosSet.add(dtVencObj.getFullYear());

      if (dtVencObj) {
        const m = dtVencObj.getMonth() + 1;
        const a = dtVencObj.getFullYear();
        if (filtroMes && filtroMes !== "TODOS" && parseInt(filtroMes) !== m) return;
        if (filtroAno && filtroAno !== "TODOS" && parseInt(filtroAno) !== a) return;
      }

      const cat = String(row[2] || "Outros");
      const val = parseFloat(row[4]) || 0;
      const st = String(row[7]).toUpperCase();
      const obs = String(row[9] || "");

      totalGeral += val;

      if (obs.includes("Taxa Boleto: R$")) {
        const match = obs.match(/Taxa Boleto: R\$\s*([\d.,]+)/);
        if (match) {
          const valTaxa = parseFloat(match[1].replace(/\./g, '').replace(',', '.'));
          if (!isNaN(valTaxa)) totalJurosTaxas += valTaxa;
        }
      }
      if (obs.includes("Juros: R$")) {
        const match = obs.match(/Juros: R\$\s*([\d.,]+)/);
        if (match) {
          const valJuros = parseFloat(match[1].replace(/\./g, '').replace(',', '.'));
          if (!isNaN(valJuros)) totalJurosTaxas += valJuros;
        }
      }

      if (dtVencObj) {
        const chaveMesAno = Utilities.formatDate(dtVencObj, tz, "yyyy-MM");
        const labelMesAno = Utilities.formatDate(dtVencObj, tz, "MMM/yy");

        // Agrupamento Geral Mensal
        if (!mapaMensal[chaveMesAno]) {
          mapaMensal[chaveMesAno] = { pago: 0, pendente: 0, totalMes: 0, label: labelMesAno };
        }
        mapaMensal[chaveMesAno].totalMes += val;
        if (st.includes("PAGO")) {
          mapaMensal[chaveMesAno].pago += val;
        } else {
          mapaMensal[chaveMesAno].pendente += val;
        }

        // Agrupamento Específico para Contas Fixas
        if (cat === "Conta Fixa") {
          if (!mapaContasFixas[chaveMesAno]) {
            mapaContasFixas[chaveMesAno] = { label: labelMesAno, valor: 0 };
          }
          mapaContasFixas[chaveMesAno].valor += val;
        }
      }

      if (st.includes("PAGO")) {
        totalQuitadas += val;
      } else {
        if (dtVencObj) {
          const dtComparar = new Date(dtVencObj.getTime());
          dtComparar.setHours(0, 0, 0, 0);
          if (dtComparar < hoje) {
            totalVencidas += val;
          } else {
            totalAtivas += val;
          }
        } else {
          totalAtivas += val;
        }
      }

      categorias[cat] = (categorias[cat] || 0) + val;
    });
  }

  // Prepara Evolução Mensal Geral
  const chavesOrdenadas = Object.keys(mapaMensal).sort();
  const evolucaoMensal = { labels: [], saldoDevedor: [], novasDividasMes: [], crescimentoAcumulado: [] };

  let saldoDevedorProjetado = totalGeral;
  let endividamentoAcumuladoEmpresa = 0;

  chavesOrdenadas.forEach(chave => {
    const item = mapaMensal[chave];
    endividamentoAcumuladoEmpresa += item.totalMes;
    saldoDevedorProjetado -= (item.pago + item.pendente);

    evolucaoMensal.labels.push(item.label);
    evolucaoMensal.novasDividasMes.push(item.totalMes);
    evolucaoMensal.crescimentoAcumulado.push(endividamentoAcumuladoEmpresa);
    evolucaoMensal.saldoDevedor.push(Math.max(0, saldoDevedorProjetado));
  });

  // Prepara Dados para o Gráfico de Contas Fixas (Ordenado por mês)
  const contasFixasMensal = { labels: [], valores: [] };
  Object.keys(mapaContasFixas).sort().forEach(chave => {
    contasFixasMensal.labels.push(mapaContasFixas[chave].label);
    contasFixasMensal.valores.push(mapaContasFixas[chave].valor);
  });

  const anosDisponiveis = Array.from(anosSet).sort((a, b) => b - a);
  if (anosDisponiveis.length === 0) anosDisponiveis.push(new Date().getFullYear());

  return {
    totalGeral: totalGeral,
    totalQuitadas: totalQuitadas,
    totalAtivas: totalAtivas,
    totalVencidas: totalVencidas,
    totalJurosTaxas: totalJurosTaxas,
    categorias: categorias,
    contasFixasMensal: contasFixasMensal, // Exporta o novo grupo pro dashboard
    anosDisponiveis: anosDisponiveis,
    evolucaoMensal: evolucaoMensal
  };
}