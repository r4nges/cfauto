# CFAUTO — Estilo base e identidade visual (Fase 1) — Design

- **Data:** 2026-10-09
- **Status:** aprovado em brainstorming, aguardando revisão da spec escrita
- **Base:** `docs/superpowers/specs/2026-09-23-cfauto-arquitetura-design.md` (manda onde não houver decisão nova aqui). Escopo previsto do estilo base: memória de 27/09 e `docs/superpowers/HANDOFF.md` (seção "Decisões recentes").
- **Branch:** `feat/estilo-base` (criada na etapa do plano)

## 1. Objetivo e escopo

Tirar o app da cara "Qt cru do Windows": uma identidade visual coerente com o logo (gradiente preto → índigo `#3433cc`, branco), aplicada de forma centralizada, sem tocar na lógica de nenhum módulo e sem atrasar a fila de sub-projetos (4B, Saídas, CFAUTO I/II, Compras, Importador). Apresentação do hackathon em dezembro/2026.

Sucesso: abrir o app e passar por login, janela principal, Estoque, Clientes, Caixa/PDV, Histórico e Configurações já com o visual novo, em português, igual em qualquer Windows (inclusive em modo escuro); e as telas novas do 4B em diante nascerem no estilo só por usar widgets Qt comuns.

O projeto tem **duas fases**. Esta spec cobre a **Fase 1**; a Fase 2 é só listada (§10) e terá spec própria.

### 1.1 Decisões do brainstorming (09/10)

| # | Decisão | Alternativas descartadas |
|---|---|---|
| D1 | Ambição: **base + identidade** (estilo global, marca nas telas de entrada, ícones, ícone do app). | Só estilo base; mínimo (pt_BR + paleta + remover hex) |
| D2 | **Só tema claro.** Tokens semânticos nascem prontos para um 2º tema, mas nada de escuro é entregue nem conferido. | Escuro com alternância manual; escuro seguindo o Windows |
| D3 | Janela principal: **faixa de topo com o gradiente do logo** + menu lateral claro com marcador no item ativo. | Lateral índigo; tudo claro com índigo só em destaques |
| D4 | Login (e licença): **painel dividido** — marca à esquerda, formulário à direita. | Faixa de marca no topo do diálogo; cartão sobre fundo de marca |
| D5 | Ícones **Lucide** (contorno, licença ISC) no menu e nas ações recorrentes — **Fase 2**. | Só menu e topo; sem ícones |
| D6 | Cronograma: **Fase 1 agora (~1 semana); Fase 2 logo depois do 4B.** | As duas antes do 4B; Fase 2 só no fim |
| D7 | Infraestrutura: **pacote `cfauto/ui/tema/` com QSS gerado a partir de tokens**; widgets escolhem aparência pela propriedade `papel`. | `.qss` estático com placeholders; só Fusion + `QPalette` (exigiria `paintEvent`/delegates para faixa e cantos) |
| D8 | Assistente de primeira execução: `QWizard` de **tamanho fixo** com a marca na lateral via `WatermarkPixmap` (spike de 09/10 confirmou que aparece nas páginas do meio, em Classic e Modern). | Reescrever o assistente como `QDialog` próprio |

### 1.2 Fora da Fase 1

Ícones Lucide e helper de recolorir; chips coloridos de estoque nas tabelas (precisam de delegate de célula); `papel=perigo` nas telas internas; polimento do PDV; tema escuro; mudança de layout de qualquer tela; mudança de lógica de negócio.

## 2. Tokens (`cfauto/ui/tema/tokens.py`)

`@dataclass(frozen=True) class Tokens` e a instância `CLARO`. **É o único arquivo do app com literais de cor.** Valores vêm dos mockups aprovados; o plano pode ajustar um tom se a conferência de contraste (§8) reprovar.

| Grupo | Token | Valor |
|---|---|---|
| Marca | `indigo` / `indigo_escuro` / `preto` | `#3433cc` / `#14124f` / `#000000` |
| Superfície | `fundo` / `superficie` / `linha` / `linha_campo` | `#f6f7fb` / `#ffffff` / `#dde0ee` / `#c4c8dc` |
| Tabela | `cabecalho_tabela` / `zebra` / `selecao` | `#e9eaf8` / `#f9faff` / `#ecebff` |
| Texto | `texto` / `texto_secundario` | `#1f2233` / `#5b5f7a` |
| Semânticas (texto, fundo) | `sucesso` | `#1d6b34`, `#dff3e4` |
| | `aviso` | `#8a5a00`, `#fdf0d3` |
| | `perigo` | `#a3231a`, `#fbdedb` |
| | `erro` (texto de erro de formulário) | `#b3261e` |
| Sobre a marca | `aviso_sobre_marca` | `#ffd27a` |
| Geometria | `raio_controle` / `raio_painel` | 4 px / 6 px |
| Tipografia | `fonte_familia` / `fonte_pt` / `fonte_navegacao_pt` | Segoe UI / 10 / 12 |

Notas: o aviso de licença (`#b9770e` hoje, em `janela_principal.py` e `estoque/entradas.py`) tem contraste insuficiente sobre branco e sobre o gradiente; passa a `aviso` (texto claro) e `aviso_sobre_marca` (faixa). `fonte_pt` sobe de 9 para 10 pt; a conferência manual (§9) checa que o diálogo "Novo cliente" e o PDV continuam cabendo na tela.

## 3. Pacote `tema`

```
cfauto/ui/tema/
  __init__.py   reexporta aplicar_tema, CLARO, PainelMarca
  tokens.py     Tokens + CLARO
  qss.py        gerar_qss(tokens: Tokens) -> str
  aplicar.py    aplicar_tema(qapp, tokens=CLARO) -> None
  marca.py      PainelMarca (QFrame) + pixmap_marca(largura, altura)
```

### 3.1 `aplicar_tema(qapp, tokens=CLARO)`

Ordem: (1) `qapp.setStyle("Fusion")`; (2) `QPalette` montada dos tokens (janela, base, texto, destaque, desabilitado); (3) `qapp.setFont(Segoe UI, fonte_pt)`; (4) `qapp.setStyleSheet(gerar_qss(tokens))`; (5) `qapp.styleHints().setColorScheme(Qt.ColorScheme.Light)` (mantém o comportamento de `configurar_aparencia`); (6) instala `QTranslator` com `qtbase_pt_BR.qm` (de `QLibraryInfo.TranslationsPath`; se ausente, tenta `recursos/`; se também ausente, loga `warning` e segue em inglês). Também chama `qapp.setWindowIcon` com o ícone do app (§7).

Substitui `configurar_aparencia` em `cfauto/ui/app.py` (`main` chama `aplicar_tema(qapp)`). Cada passo falho é logado e não interrompe os seguintes: o pior caso é abrir com visual padrão.

### 3.2 Papéis

O QSS seleciona por propriedade dinâmica `papel`:

| Papel | Em | Efeito |
|---|---|---|
| `primario` | `QPushButton` | fundo índigo, texto branco |
| `perigo` | `QPushButton` | contorno e texto `perigo` |
| `erro` / `aviso` / `sucesso` | `QLabel` | cor do token |

Além disso, `QPushButton:default` é pintado como primário. O `QDialogButtonBox` já marca o botão de aceitar como padrão, então os ~20 diálogos ganham botão primário **sem alteração**. Onde o padrão for outro botão, o diálogo ajusta `setDefault` (verificado na conferência manual).

### 3.3 Cobertura do QSS

`QMainWindow`/páginas (`fundo`), `QDialog`/`QWizard` (`superficie`), `QToolBar#faixa` (gradiente `preto → indigo_escuro (40%) → indigo`, texto branco, `QToolButton` com hover translúcido), `QFrame#lateral` e `QListWidget#navegacao` (§4), `QTabWidget`/`QTabBar` (aba ativa com sublinhado índigo), `QLineEdit`/`QTextEdit`/`QComboBox`/`QSpinBox` (borda `linha_campo`, foco índigo, `raio_controle`), `QPushButton` (padrão, `primario`, `perigo`, desabilitado), `QTableView`/`QTableWidget`/`QHeaderView` (cabeçalho, zebra, seleção), `QGroupBox`, `QMessageBox`, `QScrollBar`, `QToolTip`.

Todo valor do QSS vem do `Tokens` por f-string; `qss.py` não contém literal de cor.

## 4. Janela principal (`cfauto/ui/janela_principal.py`)

- `QToolBar` ganha `setObjectName("faixa")`. O rótulo do usuário e os botões ☰ / Configurações / Sair herdam texto branco pelo QSS. O aviso de licença usa `papel=aviso` na faixa com a variante `aviso_sobre_marca` (regra QSS `QToolBar#faixa QLabel[papel="aviso"]`); o `setStyleSheet` inline sai.
- Lateral: `_lateral` ganha `objectName("lateral")` (fundo branco, borda direita `linha`); `_navegacao` ganha `objectName("navegacao")` (item ativo: fundo `selecao`, texto índigo, `border-left: 3px solid indigo`). Saem `setFrameShape(StyledPanel)`, `setBackgroundRole` e `setAutoFillBackground` da lateral. O logo continua embaixo (`LADO_LOGO`, `MARGEM_LOGO`) e `FONTE_NAVEGACAO_PT` vira `tokens.fonte_navegacao_pt`.
- `criar_tabela` (`cfauto/ui/comum.py`) passa a chamar `setAlternatingRowColors(True)`; as tabelas montadas à mão (ex.: conferência de NF-e em `estoque/entradas.py`) recebem a zebra pelo mesmo QSS, ligando o atributo onde faltar.
- Nenhuma mudança de layout, ordem de itens, permissões ou navegação.

## 5. `PainelMarca`, login e licença

`PainelMarca(QFrame)` (`tema/marca.py`): 210 px de largura, fundo em gradiente diagonal (`preto → indigo_escuro (45%) → indigo`), logo (`QSvgWidget` de `recursos/logo.svg`, ~104 px) centralizado, "CFAUTO" em negrito e o slogan "O SEU CFO AUTOMÁTICO" em caixa alta com espaçamento. Sem lógica. `pixmap_marca(largura, altura)` renderiza o mesmo desenho num `QPixmap` (usado pelo assistente).

**`DialogoLogin`** (`ui/login.py`): layout horizontal `[PainelMarca | coluna do formulário]`; coluna com título "Entrar" (ou "Tela bloqueada" quando há `login_fixo`), campos Login/Senha, `rotulo_erro` com `papel=erro`, botões Cancelar/Entrar. Tamanho mínimo ~580×270. Os atributos usados pelos testes (`campo_login`, `campo_senha`, `rotulo_erro`, `entrar`, `ator`) mantêm nome e comportamento; o `setStyleSheet` inline sai.

**`DialogoLicenca`** (`ui/licenca.py`): mesmo molde, título "Ativar licença", campos ID desta máquina e Chave, botões Instalar/Sair, `rotulo_erro` com `papel=erro`. Atributos de teste preservados.

O bloqueio por inatividade reaproveita `DialogoLogin(login_fixo=…)`, sem mudança em `app.py` além de `aplicar_tema`.

## 6. Assistente de primeira execução (`ui/assistente.py`)

`AssistentePrimeiraExecucao` continua `QWizard` com as mesmas três páginas e a mesma lógica de `accept`. Muda a apresentação: `setWizardStyle(ModernStyle)`, `setPixmap(WatermarkPixmap, pixmap_marca(210, h))` e **tamanho fixo** (~640×440), com `h` calculado para preencher a área acima da barra de botões (valor exato conferido no Windows na implementação). Botões "Avançar/Cancelar/Concluir" vêm do tradutor pt_BR. Se o spike não se repetir no plugin real do Windows (watermark ausente em alguma página), o plano cai para `BannerPixmap` com a faixa de gradiente — o teste de página não depende disso.

## 7. Ícone do app

Gerar uma vez `cfauto/ui/recursos/icone.ico` (multi-tamanho 16/32/48/256) a partir do `logo.svg` e commitar. `aplicar_tema` usa `QIcon` do logo/ico como ícone padrão das janelas; `CFAUTO.spec` ganha `icon='cfauto/ui/recursos/icone.ico'` e o `build.ps1`/comando de build do HANDOFF recebem `--icon`.

## 8. Falhas e testes

**Falhas:** logo, `.qm` ou QSS com problema nunca impedem o app de abrir (log + visual padrão). Mensagens ao usuário não mudam.

**Testes novos** (a suíte atual continua verde; `QT_QPA_PLATFORM=offscreen` como hoje):

- **Contraste:** cada par texto/fundo dos tokens (texto, texto_secundario, semânticas, `aviso_sobre_marca` sobre `indigo_escuro` e `indigo`, branco sobre `indigo`) ≥ 4,5:1 (fórmula WCAG).
- **QSS:** `gerar_qss(CLARO)` não deixa placeholder, cobre os papéis da §3.2 e, com `qInstallMessageHandler`, aplicá-lo a uma `QApplication` não gera "Could not parse stylesheet".
- **`aplicar_tema`:** estilo vira `Fusion`; folha de estilo não vazia; tradutor instalado quando o `.qm` existe; ausência do `.qm` não levanta e loga. O teste de aparência de `tests/ui/test_app.py` (subprocesso com plugin `windows`) passa a chamar `aplicar_tema` e continua exigindo `WindowText` escuro.
- **Guarda anti-hex:** nenhum `#rrggbb` em `cfauto/ui/**/*.py` fora de `tema/tokens.py`.
- **Telas:** `PainelMarca` constrói e `pixmap_marca` devolve pixmap do tamanho pedido; `DialogoLogin`/`DialogoLicenca` contêm um `PainelMarca`; o assistente tem tamanho fixo e watermark definido; `JanelaPrincipal` constrói com o tema aplicado e a faixa tem `objectName("faixa")`; todas as páginas dos módulos constroem com o tema aplicado.

O offscreen não tem fontes nem rende fielmente QSS, então **não há comparação de pixels**: a conferência visual é o roteiro manual (§9).

## 9. Roteiro de QA manual (Windows, modo claro e modo escuro do sistema)

Login; bloqueio de tela; licença; assistente (3 páginas, tamanho e marca lateral); janela principal (faixa, ☰ retrai o menu, aviso de licença, item ativo, logo); Estoque (abas, tabela com zebra e seleção, editor de produto); Entradas de NF-e (tabela de conferência); Clientes (diálogo "Novo cliente" cabe na tela, extrato com preview de impressão); Caixa/PDV (fontes e botões cabem; carrinho); Histórico; Configurações (abas, Usuários, Parâmetros); `QMessageBox` em português; botão padrão correto em cada diálogo; nenhum rótulo invisível em modo escuro do Windows.

## 10. Ordem de implementação e Fase 2

**Tarefas da Fase 1** (cada uma testada e commitada; o plano detalha):

1. `tokens.py` + testes de contraste.
2. `qss.py` + `aplicar.py` (Fusion, paleta, fonte, tradutor) + testes; `main` troca `configurar_aparencia` por `aplicar_tema`.
3. Casca da janela principal (faixa, lateral, zebra) + remoção dos `setStyleSheet` de `janela_principal.py`.
4. `PainelMarca` + `DialogoLogin` e `DialogoLicenca`.
5. Assistente (watermark, tamanho fixo).
6. Limpeza do último hex (`estoque/entradas.py`), guarda anti-hex, ícone do app e build com `--icon`; confirmar o `.qm` no `.exe`.
7. Roteiro de QA manual (§9) e ajustes.

**Fase 2** (depois do 4B, spec própria): conjunto Lucide e helper de recolorir por estado; ícones no menu, em Configurações/Sair e nas ações recorrentes (Novo, Buscar, Imprimir, Excluir, Salvar); chips coloridos de estoque via delegate; `papel=perigo` nas telas internas; polimento do PDV; revisão tela a tela.

## 11. Riscos

- **Manhas de QSS com Fusion** (`QHeaderView`, `QTabBar`, itens de `QListWidget`): mitigado pelo teste de parse e pela conferência manual.
- **Fonte base de 10 pt** pode estourar diálogos já ajustados (ex.: "Novo cliente"): checado no roteiro; se estourar, `fonte_pt` volta a 9 num único token.
- **`qtbase_pt_BR.qm` no `.exe`:** confirmado na tarefa 6; plano B é copiar o arquivo para `recursos/`, que o spec já empacota.
- **Watermark de altura fixa** no assistente: por isso o tamanho fixo da janela.
- **Esforço de ~1 semana** pressupõe que a Fase 2 fique de fora; qualquer pedido de ícone ou chip na Fase 1 é Fase 2.
