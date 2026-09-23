// ============================================================================
// SISTEMA DE GESTÃO DE USUÁRIOS E PERMISSÕES
// Estrutura das Colunas (Linha 7 em diante):
// Coluna A: NOME | Coluna B: FUNÇÃO | Coluna C: LOGIN | Coluna D: SENHA (HASH) | Coluna E: PERMISSÃO
// ============================================================================

// ----------------------------------------------------------------------------
// 1. BOTÃO (+): ADICIONAR NOVO USUÁRIO
// ----------------------------------------------------------------------------
function btnAdicionarUsuario() {
  var html = HtmlService.createHtmlOutput(`
    <!DOCTYPE html>
    <html>
      <head>
        <style>
          * { box-sizing: border-box; font-family: 'Segoe UI', sans-serif; }
          body { background: #f8fafc; padding: 15px; margin: 0; }
          .card { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
          h3 { margin: 0 0 10px 0; color: #16a34a; font-size: 15px; text-transform: uppercase; }
          label { display: block; font-size: 11px; font-weight: bold; color: #475569; margin-top: 8px; }
          .req { color: #dc2626; font-weight: bold; }
          input[type="text"], input[type="password"] { width: 100%; padding: 7px 10px; margin-top: 3px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 12px; outline: none; }
          input:focus { border-color: #16a34a; }
          
          .perm-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; margin-top: 6px; border: 1px solid #cbd5e1; padding: 8px; border-radius: 6px; background: #f8fafc; max-height: 120px; overflow-y: auto; }
          .perm-item { display: flex; align-items: center; gap: 6px; font-size: 11px; color: #334155; font-weight: 500; cursor: pointer; }
          .perm-item input { margin: 0; cursor: pointer; }
          .adm-box { grid-column: span 2; background: #fef3c7; border: 1px solid #f59e0b; padding: 5px 8px; border-radius: 4px; color: #92400e; font-weight: bold; margin-bottom: 2px; }
          
          .err-msg { color: #dc2626; font-size: 10px; font-weight: bold; margin-top: 3px; display: none; }
          
          .btn { width: 100%; padding: 10px; background: #16a34a; color: white; border: none; border-radius: 4px; font-weight: bold; margin-top: 14px; cursor: pointer; transition: background 0.2s, opacity 0.2s; }
          .btn:disabled { background: #94a3b8 !important; cursor: not-allowed !important; opacity: 0.6; }
          .btn:hover:not(:disabled) { background: #15803d; }
        </style>
      </head>
      <body>
        <div class="card">
          <h3>➕ Novo Usuário</h3>
          
          <label>Nome <span class="req">*</span></label>
          <input type="text" id="nome" oninput="validarFormulario()">
          
          <label>Função:</label>
          <input type="text" id="funcao">
          
          <label>Login <span class="req">*</span></label>
          <input type="text" id="login" oninput="validarFormulario()">
          
          <label>Senha <span class="req">*</span></label>
          <input type="password" id="senha" oninput="validarFormulario()">
          
          <label>Confirmar Senha <span class="req">*</span></label>
          <input type="password" id="confirmarSenha" oninput="validarFormulario()">
          <div id="errSenha" class="err-msg">As senhas não coincidem.</div>
          
          <label>Permissões de Acesso <span class="req">*</span></label>
          <div class="perm-grid">
            <label class="perm-item adm-box">
              <input type="checkbox" id="chkADM" onchange="toggleADM(this)"> 👑 ADM Principal (Acesso Total)
            </label>
            <label class="perm-item"><input type="checkbox" class="chk-mod" value="CAIXA" onchange="validarFormulario()"> CAIXA</label>
            <label class="perm-item"><input type="checkbox" class="chk-mod" value="SAIDAS" onchange="validarFormulario()"> SAIDAS</label>
            <label class="perm-item"><input type="checkbox" class="chk-mod" value="ESTOQUE" onchange="validarFormulario()"> ESTOQUE</label>
            <label class="perm-item"><input type="checkbox" class="chk-mod" value="CLIENTES" onchange="validarFormulario()"> CLIENTES</label>
            <label class="perm-item"><input type="checkbox" class="chk-mod" value="COMPRAS" onchange="validarFormulario()"> COMPRAS</label>
            <label class="perm-item"><input type="checkbox" class="chk-mod" value="HISTORICO" onchange="validarFormulario()"> HISTORICO</label>
            <label class="perm-item"><input type="checkbox" class="chk-mod" value="RELATORIO" onchange="validarFormulario()"> RELATORIO</label>
            <label class="perm-item"><input type="checkbox" class="chk-mod" value="USUARIO" onchange="validarFormulario()"> USUARIO</label>
            <label class="perm-item"><input type="checkbox" class="chk-mod" value="ADMINISTRATIVO" onchange="validarFormulario()"> ADMINISTRATIVO</label>
          </div>
          
          <button class="btn" id="btnSalvar" disabled onclick="salvar()">CADASTRAR</button>
        </div>

        <script>
          function toggleADM(master) {
            var checkboxes = document.querySelectorAll('.chk-mod');
            checkboxes.forEach(function(cb) { cb.checked = master.checked; });
            validarFormulario();
          }

          function obterPermissoes() {
            if (document.getElementById('chkADM').checked) return "ADMIN";
            var marcados = [];
            document.querySelectorAll('.chk-mod').forEach(function(cb) {
              if (cb.checked) marcados.push(cb.value);
            });
            return marcados.join(', ');
          }

          function validarFormulario() {
            var nome = document.getElementById('nome').value.trim();
            var login = document.getElementById('login').value.trim();
            var senha = document.getElementById('senha').value;
            var confirmar = document.getElementById('confirmarSenha').value;
            var errSenha = document.getElementById('errSenha');
            var btn = document.getElementById('btnSalvar');

            var permissoesValidas = obterPermissoes() !== "";
            var senhasCoincidem = (senha !== "" && senha === confirmar);

            if (senha !== "" && confirmar !== "" && senha !== confirmar) {
              errSenha.style.display = "block";
            } else {
              errSenha.style.display = "none";
            }

            if (nome && login && senhasCoincidem && permissoesValidas) {
              btn.disabled = false;
            } else {
              btn.disabled = true;
            }
          }

          function salvar() {
            var dados = {
              nome: document.getElementById('nome').value.trim(),
              funcao: document.getElementById('funcao').value.trim(),
              login: document.getElementById('login').value.trim(),
              senha: document.getElementById('senha').value,
              permissoes: obterPermissoes()
            };

            document.getElementById('btnSalvar').disabled = true;

            google.script.run
              .withSuccessHandler(function() {
                google.script.host.close();
              })
              .salvarNovoUsuario(dados);
          }
        </script>
      </body>
    </html>
  `).setWidth(420).setHeight(600);

  SpreadsheetApp.getUi().showModalDialog(html, "Cadastrar Usuário");
}

// ----------------------------------------------------------------------------
// 2. BOTÃO (-): JANELA DE SELEÇÃO PARA EXCLUIR USUÁRIO
// ----------------------------------------------------------------------------
function btnExcluirUsuario() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getActiveSheet();
  var lastRow = sheet.getLastRow();

  if (lastRow < 7) {
    ss.toast("Não há usuários cadastrados para excluir.", "Atenção ⚠️", 3);
    return;
  }

  var dados = sheet.getRange(7, 1, lastRow - 6, 3).getValues();
  var listaUsuarios = [];

  for (var i = 0; i < dados.length; i++) {
    var nome = dados[i][0];
    var login = dados[i][2];
    var linhaReal = i + 7;
    if (nome && String(nome).trim() !== "") {
      listaUsuarios.push({
        linha: linhaReal,
        nome: nome,
        login: login ? login : "Sem Login"
      });
    }
  }

  if (listaUsuarios.length === 0) {
    ss.toast("Nenhum usuário encontrado na planilha.", "Atenção ⚠️", 3);
    return;
  }

  var htmlOptions = listaUsuarios.map(function(u) {
    return `<option value="${u.linha}">${u.nome} (Login: ${u.login})</option>`;
  }).join('');

  var html = HtmlService.createHtmlOutput(`
    <!DOCTYPE html>
    <html>
      <head>
        <style>
          * { box-sizing: border-box; font-family: 'Segoe UI', sans-serif; }
          body { background: #f8fafc; padding: 15px; margin: 0; }
          .card { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
          h3 { margin: 0 0 10px 0; color: #dc2626; font-size: 15px; text-transform: uppercase; }
          label { display: block; font-size: 11px; font-weight: bold; color: #475569; margin-top: 8px; }
          select { width: 100%; padding: 8px 10px; margin-top: 5px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 12px; outline: none; background: white; }
          select:focus { border-color: #dc2626; }
          .btn-danger { width: 100%; padding: 10px; background: #dc2626; color: white; border: none; border-radius: 4px; font-weight: bold; margin-top: 18px; cursor: pointer; transition: background 0.2s; }
          .btn-danger:hover { background: #b91c1c; }
          .btn-danger:disabled { background: #94a3b8; cursor: not-allowed; }
        </style>
      </head>
      <body>
        <div class="card">
          <h3>🗑️ Excluir Usuário</h3>
          <label>Selecione o usuário que deseja apagar:</label>
          <select id="selectUsuario">
            ${htmlOptions}
          </select>

          <button class="btn-danger" id="btnExcluir" onclick="executarExclusao()">EXCLUIR</button>
        </div>

        <script>
          function executarExclusao() {
            var select = document.getElementById('selectUsuario');
            var linha = select.value;

            if (!linha) return;

            document.getElementById('btnExcluir').disabled = true;
            document.getElementById('btnExcluir').innerText = "EXCLUINDO...";

            google.script.run
              .withSuccessHandler(function() {
                google.script.host.close();
              })
              .excluirUsuarioPorLinha(linha);
          }
        </script>
      </body>
    </html>
  `).setWidth(380).setHeight(210);

  SpreadsheetApp.getUi().showModalDialog(html, "Excluir Usuário");
}

// ----------------------------------------------------------------------------
// 3. BOTÃO (SETAS): JANELA DE SELEÇÃO E EDIÇÃO DE USUÁRIO
// ----------------------------------------------------------------------------
function btnEditarUsuario() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getActiveSheet();
  var lastRow = sheet.getLastRow();

  if (lastRow < 7) {
    ss.toast("Não há usuários cadastrados para editar.", "Atenção ⚠️", 3);
    return;
  }

  var dados = sheet.getRange(7, 1, lastRow - 6, 5).getValues();
  var listaUsuarios = [];

  for (var i = 0; i < dados.length; i++) {
    var nome = dados[i][0];
    var funcao = dados[i][1];
    var login = dados[i][2];
    var permissoes = String(dados[i][4] || "");
    var linhaReal = i + 7;

    if (nome && String(nome).trim() !== "") {
      listaUsuarios.push({
        linha: linhaReal,
        nome: nome,
        funcao: funcao,
        login: login,
        permissoes: permissoes
      });
    }
  }

  if (listaUsuarios.length === 0) {
    ss.toast("Nenhum usuário encontrado na planilha.", "Atenção ⚠️", 3);
    return;
  }

  var usuariosJson = JSON.stringify(listaUsuarios);

  var html = HtmlService.createHtmlOutput(`
    <!DOCTYPE html>
    <html>
      <head>
        <style>
          * { box-sizing: border-box; font-family: 'Segoe UI', sans-serif; }
          body { background: #f8fafc; padding: 15px; margin: 0; }
          .card { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
          h3 { margin: 0 0 10px 0; color: #ea580c; font-size: 15px; text-transform: uppercase; }
          label { display: block; font-size: 11px; font-weight: bold; color: #475569; margin-top: 8px; }
          .req { color: #dc2626; font-weight: bold; }
          select, input[type="text"], input[type="password"] { width: 100%; padding: 7px 10px; margin-top: 3px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 12px; outline: none; background: white; }
          select:focus, input:focus { border-color: #ea580c; }
          
          .perm-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; margin-top: 6px; border: 1px solid #cbd5e1; padding: 8px; border-radius: 6px; background: #f8fafc; max-height: 120px; overflow-y: auto; }
          .perm-item { display: flex; align-items: center; gap: 6px; font-size: 11px; color: #334155; font-weight: 500; cursor: pointer; }
          .perm-item input { margin: 0; cursor: pointer; }
          .adm-box { grid-column: span 2; background: #fef3c7; border: 1px solid #f59e0b; padding: 5px 8px; border-radius: 4px; color: #92400e; font-weight: bold; margin-bottom: 2px; }
          
          .err-msg { color: #dc2626; font-size: 10px; font-weight: bold; margin-top: 3px; display: none; }
          
          .btn { width: 100%; padding: 10px; background: #ea580c; color: white; border: none; border-radius: 4px; font-weight: bold; margin-top: 14px; cursor: pointer; transition: background 0.2s, opacity 0.2s; }
          .btn:disabled { background: #94a3b8 !important; cursor: not-allowed !important; opacity: 0.6; }
          .btn:hover:not(:disabled) { background: #c2410c; }
        </style>
      </head>
      <body>
        <div class="card">
          <h3>✏️ Editar Usuário</h3>
          
          <label>Selecione o Usuário <span class="req">*</span></label>
          <select id="selectUsuario" onchange="carregarUsuarioSelecionado()"></select>

          <label>Nome <span class="req">*</span></label>
          <input type="text" id="nome" oninput="validarFormulario()">
          
          <label>Função:</label>
          <input type="text" id="funcao">
          
          <label>Login <span class="req">*</span></label>
          <input type="text" id="login" oninput="validarFormulario()">
          
          <label>Nova Senha (opcional):</label>
          <input type="password" id="senha" placeholder="Deixe em branco para manter a atual" oninput="validarFormulario()">
          
          <label>Confirmar Nova Senha:</label>
          <input type="password" id="confirmarSenha" placeholder="Confirme a nova senha" oninput="validarFormulario()">
          <div id="errSenha" class="err-msg">As senhas não coincidem.</div>
          
          <label>Permissões de Acesso <span class="req">*</span></label>
          <div class="perm-grid">
            <label class="perm-item adm-box">
              <input type="checkbox" id="chkADM" onchange="toggleADM(this)"> 👑 ADM Principal (Acesso Total)
            </label>
            <label class="perm-item"><input type="checkbox" class="chk-mod" value="CAIXA" onchange="validarFormulario()"> CAIXA</label>
            <label class="perm-item"><input type="checkbox" class="chk-mod" value="SAIDAS" onchange="validarFormulario()"> SAIDAS</label>
            <label class="perm-item"><input type="checkbox" class="chk-mod" value="ESTOQUE" onchange="validarFormulario()"> ESTOQUE</label>
            <label class="perm-item"><input type="checkbox" class="chk-mod" value="CLIENTES" onchange="validarFormulario()"> CLIENTES</label>
            <label class="perm-item"><input type="checkbox" class="chk-mod" value="COMPRAS" onchange="validarFormulario()"> COMPRAS</label>
            <label class="perm-item"><input type="checkbox" class="chk-mod" value="HISTORICO" onchange="validarFormulario()"> HISTORICO</label>
            <label class="perm-item"><input type="checkbox" class="chk-mod" value="RELATORIO" onchange="validarFormulario()"> RELATORIO</label>
            <label class="perm-item"><input type="checkbox" class="chk-mod" value="USUARIO" onchange="validarFormulario()"> USUARIO</label>
            <label class="perm-item"><input type="checkbox" class="chk-mod" value="ADMINISTRATIVO" onchange="validarFormulario()"> ADMINISTRATIVO</label>
          </div>
          
          <button class="btn" id="btnAtualizar" onclick="atualizar()">SALVAR ALTERAÇÕES</button>
        </div>

        <script>
          var usuarios = ${usuariosJson};

          window.onload = function() {
            var select = document.getElementById('selectUsuario');
            select.innerHTML = '';
            usuarios.forEach(function(u, index) {
              var opt = document.createElement('option');
              opt.value = index;
              opt.innerText = u.nome + ' (Login: ' + (u.login || 'Sem Login') + ')';
              select.appendChild(opt);
            });

            if (usuarios.length > 0) {
              carregarUsuarioSelecionado();
            }
          };

          function carregarUsuarioSelecionado() {
            var index = document.getElementById('selectUsuario').value;
            var u = usuarios[index];
            if (!u) return;

            document.getElementById('nome').value = u.nome || '';
            document.getElementById('funcao').value = u.funcao || '';
            document.getElementById('login').value = u.login || '';
            document.getElementById('senha').value = '';
            document.getElementById('confirmarSenha').value = '';

            document.getElementById('chkADM').checked = false;
            document.querySelectorAll('.chk-mod').forEach(function(cb) { cb.checked = false; });

            var permsSalvas = String(u.permissoes || "").toUpperCase();
            if (permsSalvas.indexOf("ADMIN") !== -1 || permsSalvas.indexOf("TODOS") !== -1) {
              document.getElementById('chkADM').checked = true;
              toggleADM(document.getElementById('chkADM'));
            } else {
              var lista = permsSalvas.split(',').map(function(s) { return s.trim(); });
              document.querySelectorAll('.chk-mod').forEach(function(cb) {
                if (lista.indexOf(cb.value) !== -1) cb.checked = true;
              });
            }
            validarFormulario();
          }

          function toggleADM(master) {
            var checkboxes = document.querySelectorAll('.chk-mod');
            checkboxes.forEach(function(cb) { cb.checked = master.checked; });
            validarFormulario();
          }

          function obterPermissoes() {
            if (document.getElementById('chkADM').checked) return "ADMIN";
            var marcados = [];
            document.querySelectorAll('.chk-mod').forEach(function(cb) {
              if (cb.checked) marcados.push(cb.value);
            });
            return marcados.join(', ');
          }

          function validarFormulario() {
            var nome = document.getElementById('nome').value.trim();
            var login = document.getElementById('login').value.trim();
            var senha = document.getElementById('senha').value;
            var confirmar = document.getElementById('confirmarSenha').value;
            var errSenha = document.getElementById('errSenha');
            var btn = document.getElementById('btnAtualizar');

            var permissoesValidas = obterPermissoes() !== "";
            var senhaValida = true;

            if (senha !== "" || confirmar !== "") {
              if (senha !== confirmar) {
                senhaValida = false;
                errSenha.style.display = "block";
              } else {
                errSenha.style.display = "none";
              }
            } else {
              errSenha.style.display = "none";
            }

            if (nome && login && senhaValida && permissoesValidas) {
              btn.disabled = false;
            } else {
              btn.disabled = true;
            }
          }

          function atualizar() {
            var index = document.getElementById('selectUsuario').value;
            var u = usuarios[index];
            if (!u) return;

            var dados = {
              linha: u.linha,
              nome: document.getElementById('nome').value.trim(),
              funcao: document.getElementById('funcao').value.trim(),
              login: document.getElementById('login').value.trim(),
              senha: document.getElementById('senha').value,
              permissoes: obterPermissoes()
            };

            document.getElementById('btnAtualizar').disabled = true;

            google.script.run
              .withSuccessHandler(function() {
                google.script.host.close();
              })
              .atualizarUsuarioExistente(dados);
          }
        </script>
      </body>
    </html>
  `).setWidth(420).setHeight(620);

  SpreadsheetApp.getUi().showModalDialog(html, "Editar Usuário");
}

// ----------------------------------------------------------------------------
// 4. FUNÇÕES DE BANCO DE DADOS E OPERAÇÕES
// ----------------------------------------------------------------------------
function salvarNovoUsuario(dados) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getActiveSheet();
  var hash = gerarHash(dados.senha);
  
  sheet.appendRow([dados.nome, dados.funcao, dados.login, hash, dados.permissoes.toUpperCase()]);
  ss.toast("Usuário " + dados.nome + " cadastrado com sucesso!", "Sucesso 💾", 3);
}

function atualizarUsuarioExistente(dados) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getActiveSheet();
  var linha = dados.linha;

  sheet.getRange(linha, 1).setValue(dados.nome);
  sheet.getRange(linha, 2).setValue(dados.funcao);
  sheet.getRange(linha, 3).setValue(dados.login);
  sheet.getRange(linha, 5).setValue(dados.permissoes.toUpperCase());

  if (dados.senha && dados.senha.trim() !== "") {
    sheet.getRange(linha, 4).setValue(gerarHash(dados.senha));
  }

  ss.toast("Usuário " + dados.nome + " atualizado!", "Sucesso ✏️", 3);
}

function excluirUsuarioPorLinha(linha) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getActiveSheet();
  var linhaNum = parseInt(linha, 10);

  if (linhaNum >= 7) {
    var nome = sheet.getRange(linhaNum, 1).getValue();
    sheet.deleteRow(linhaNum);
    ss.toast("Usuário '" + nome + "' excluído com sucesso!", "Sucesso 🗑️", 3);
  }
}

function gerarHash(texto) {
  if (!texto) return "";
  var raw = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, texto);
  return raw.map(b => ('0' + (b & 0xFF).toString(16)).slice(-2)).join('');
}

function onOpen() {}