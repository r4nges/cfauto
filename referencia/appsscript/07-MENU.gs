// ============================================================================
// SISTEMA DE NAVEGAÇÃO E AUTENTICAÇÃO POR BOTÕES (MENU PRINCIPAL)
// ============================================================================

// ID da sua planilha central de USUÁRIOS
var ID_PLANILHA_USUARIOS = "1UtU74AmVxtfjupGB9BZkr6AdSjUCE9cQWKO7mU-m8gs";

// Links de destino para cada módulo/botão
var MAPA_LINKS = {
  "SAIDAS": "https://docs.google.com/spreadsheets/d/16PD_PSyOKStz2QCVuB66PbFlHdIl6EsbZtP34oB0BJY/edit",
  "CAIXA": "https://docs.google.com/spreadsheets/d/1nBVAh4brJ6KiIgrokph58btEkdkydSlRwDbVBbPzCzA/edit",
  "USUARIO": "https://docs.google.com/spreadsheets/d/1UtU74AmVxtfjupGB9BZkr6AdSjUCE9cQWKO7mU-m8gs/edit",
  "ESTOQUE": "https://docs.google.com/spreadsheets/d/1aPr4-chXwNE19RWIXgOPceB-OmF31Ft5SgtugEPwoMA/edit",
  "CLIENTES": "https://docs.google.com/spreadsheets/u/0/d/1WrD5GmVXteevylzXZphNMQlcZEkgpxmogbZicK8Gq78/edit",
  "HISTORICO": "https://docs.google.com/spreadsheets/d/1119HW8n6Ma-H83wbLw9I13bTJ9EgJhhpciPFyyaUXI8/edit",
  "COMPRAS": "https://docs.google.com/spreadsheets/d/1lIJzyVSwo1eZx0czw9fvfjtfNafo1lEhgtZUt1JHTl4/edit",
  "RELATORIO": "https://docs.google.com/spreadsheets/d/1IuR2cYOMVWy_MTYJ2cPxIrN3KFZLHVEfGTve-s6JIjs/edit",
  "ADMINISTRATIVO": "https://docs.google.com/spreadsheets/d/19qZGkj8FvFl2fv7qtxyHzOglh6AUNzH9pJbSN9hycOw/edit"
};

// ----------------------------------------------------------------------------
// FUNÇÕES ATRIBUÍDAS AOS BOTÕES DA PLANILHA
// ----------------------------------------------------------------------------
function btnCaixa() { solicitarAcessoModulo("CAIXA"); }
function btnSaidas() { solicitarAcessoModulo("SAIDAS"); }
function btnEstoque() { solicitarAcessoModulo("ESTOQUE"); }
function btnClientes() { solicitarAcessoModulo("CLIENTES"); }
function btnCompras() { solicitarAcessoModulo("COMPRAS"); }
function btnHistorico() { solicitarAcessoModulo("HISTORICO"); }
function btnRelatorio() { solicitarAcessoModulo("RELATORIO"); }
function btnUsuario() { solicitarAcessoModulo("USUARIO"); }
function btnAdministrativo() { solicitarAcessoModulo("ADMINISTRATIVO"); }

// ----------------------------------------------------------------------------
// INTERFACE DE LOGIN (MODAL)
// ----------------------------------------------------------------------------
function solicitarAcessoModulo(nomeModulo) {
  var html = HtmlService.createHtmlOutput(`
    <!DOCTYPE html>
    <html>
      <head>
        <style>
          * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, sans-serif; }
          body { background: #f1f5f9; padding: 18px; margin: 0; }
          .card { background: white; padding: 18px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
          h3 { margin: 0 0 4px 0; color: #0f172a; font-size: 15px; text-transform: uppercase; }
          .modulo-tag { font-size: 11px; background: #e2e8f0; color: #475569; padding: 3px 8px; border-radius: 4px; font-weight: bold; }
          label { display: block; font-size: 11px; font-weight: 700; color: #64748b; margin-top: 12px; text-transform: uppercase; }
          input { width: 100%; padding: 9px; margin-top: 4px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 13px; outline: none; }
          input:focus { border-color: #2563eb; }
          button { width: 100%; padding: 11px; background: #2563eb; color: white; border: none; border-radius: 6px; margin-top: 16px; font-weight: bold; font-size: 13px; cursor: pointer; }
          button:hover { background: #1d4ed8; }
          .erro { color: #ef4444; font-size: 11px; font-weight: bold; margin-top: 10px; text-align: center; }
        </style>
      </head>
      <body>
        <div class="card">
          <h3>🔐 Autenticação</h3>
          <span class="modulo-tag">Módulo: ${nomeModulo}</span>
          
          <label>Usuário / Login:</label>
          <input type="text" id="userInput" placeholder="Digite seu login...">
          
          <label>Senha:</label>
          <input type="password" id="passInput" placeholder="Digite sua senha...">
          
          <div id="msgErro" class="erro"></div>
          
          <button id="btn" onclick="autenticar()">ACESSAR PLANILHA</button>
        </div>

        <script>
          function autenticar() {
            var u = document.getElementById('userInput').value.trim();
            var p = document.getElementById('passInput').value;
            var btn = document.getElementById('btn');
            var erro = document.getElementById('msgErro');

            if(!u || !p) {
              erro.innerText = "Informe login e senha.";
              return;
            }

            btn.disabled = true;
            btn.innerText = "Verificando...";
            erro.innerText = "";

            google.script.run
              .withSuccessHandler(function(res) {
                if(res.ok) {
                  window.open(res.url, '_blank');
                  google.script.host.close();
                } else {
                  btn.disabled = false;
                  btn.innerText = "ACESSAR PLANILHA";
                  erro.innerText = res.msg;
                }
              })
              .validarEBuscarLink(u, p, "${nomeModulo}");
          }
        </script>
      </body>
    </html>
  `).setWidth(350).setHeight(310);
  
  SpreadsheetApp.getUi().showModalDialog(html, "Controle de Acesso");
}

// ----------------------------------------------------------------------------
// LÓGICA DE BANCO DE DADOS E SEGURANÇA
// ----------------------------------------------------------------------------
function validarEBuscarLink(login, senha, modulo) {
  try {
    var ssUsuarios = SpreadsheetApp.openById(ID_PLANILHA_USUARIOS);
    var sheet = ssUsuarios.getSheetByName("USUÁRIOS") || ssUsuarios.getSheets()[0];
    
    var total = sheet.getLastRow();
    if (total < 6) return { ok: false, msg: "Sem usuários registrados no sistema." };
    
    // Lê Colunas: A (ID), B (Nome), C (Login), D (Senha Hash), E (Permissões) a partir da linha 6
    var dados = sheet.getRange(6, 1, total - 5, 5).getValues();
    var hashSenha = gerarHash(senha);

    for (var i = 0; i < dados.length; i++) {
      var uLogin = String(dados[i][2]).trim();
      var uHash = String(dados[i][3]).trim();
      var uPerms = String(dados[i][4]).toUpperCase().trim();

      if (uLogin === login && uHash === hashSenha) {
        var listaPermissoes = uPerms.split(',').map(s => s.trim());
        
        if (uPerms === "ADMIN" || uPerms === "TODOS" || listaPermissoes.includes(modulo.toUpperCase())) {
          return { ok: true, url: MAPA_LINKS[modulo] };
        } else {
          return { ok: false, msg: "Acesso bloqueado para o módulo: " + modulo };
        }
      }
    }
    return { ok: false, msg: "Usuário ou senha incorretos." };
  } catch (err) {
    return { ok: false, msg: "Erro ao conectar com a planilha de usuários: " + err.message };
  }
}

// Gerador de Hash SHA-256
function gerarHash(texto) {
  if (!texto) return "";
  var raw = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, texto);
  return raw.map(b => ('0' + (b & 0xFF).toString(16)).slice(-2)).join('');
}