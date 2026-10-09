# CFAUTO — Estilo base e identidade visual (Fase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao app a identidade visual do logo (gradiente preto → índigo, branco) de forma centralizada: pacote `cfauto/ui/tema/` com tokens, QSS gerado, Fusion, paleta, tradução pt_BR e ícone; faixa de topo na janela principal; painel de marca no login/licença/assistente.

**Architecture:** `Tokens` (único arquivo com literais de cor) alimenta `gerar_qss` (modelo `string.Template`) e `aplicar_tema` (Fusion + `QPalette` + fonte + QSS + `QTranslator` + ícone, cada passo isolado por `try/except`). Os widgets escolhem a aparência pela propriedade dinâmica `papel` e por `objectName` (`faixa`, `lateral`, `navegacao`). `PainelMarca` e `pixmap_marca` compartilham um único desenho (`desenhar_marca`). Nenhuma lógica de negócio, layout de tela ou permissão muda.

**Tech Stack:** Python 3.13, PySide6 6.11 (Qt Widgets, QtSvg), pytest + pytest-qt (`QT_QPA_PLATFORM=offscreen`), ruff, mypy, PyInstaller.

**Spec:** `docs/superpowers/specs/2026-10-09-estilo-base-design.md` (manda onde este plano for omisso; o plano pode ajustar um tom de cor se o teste de contraste reprovar). Contexto do projeto: `docs/superpowers/HANDOFF.md`.

## Global Constraints

- **Cores:** `cfauto/ui/tema/tokens.py` é o único arquivo de `cfauto/ui/**` com literais de cor (`#rrggbb`, `rgb(`/`rgba(`). `qss.py` monta o QSS só com `${token}`. Nenhum `setStyleSheet(` em `cfauto/ui/**` fora de `tema/aplicar.py`.
- **Escopo:** só tema claro. Sem ícones Lucide, chips de estoque, `papel=perigo` nas telas internas, polimento do PDV, tema escuro, mudança de layout, de ordem de itens, de permissões ou de navegação (tudo isso é Fase 2 ou fora).
- **Falhas:** logo, `.qm`, ícone, seta do combo ou QSS com problema nunca impedem o app de abrir: log + visual padrão. Mensagens ao usuário não mudam.
- **Atributos que os testes existentes usam não mudam de nome nem de comportamento:** `DialogoLogin` (`campo_login`, `campo_senha`, `rotulo_erro`, `entrar`, `ator`), `DialogoLicenca` (`campo_chave`, `rotulo_erro`, `instalar`, `estado`), `JanelaPrincipal` (`acao_menu`, `acao_configuracoes`, `acao_sair`, `aviso_licenca`, `logo`, `titulos_navegacao`, `selecionar_modulo`, `pagina_atual`, `navegacao_visivel`, `alternar_navegacao`, `fechar_sessao`).
- **Valores dos tokens (claro):** `indigo #3433cc`, `indigo_escuro #14124f`, `preto #000000`, `sobre_marca #ffffff`, `fundo #f6f7fb`, `superficie #ffffff`, `linha #dde0ee`, `linha_campo #c4c8dc`, `cabecalho_tabela #e9eaf8`, `zebra #f9faff`, `selecao #ecebff`, `texto #1f2233`, `texto_secundario #5b5f7a`, `sucesso #1d6b34/#dff3e4`, `aviso #8a5a00/#fdf0d3`, `perigo #a3231a/#fbdedb`, `erro #b3261e`, `aviso_sobre_marca #ffd27a`, raios 4 e 6 px, `Segoe UI`, 10 pt (navegação 12 pt). Todo par texto/fundo ≥ 4,5:1 (WCAG).
- **Idioma:** textos de interface e comentários em português, com acentuação correta. Nomes de classe/função em português, como no resto do repo.
- **Qualidade:** linha de 100 colunas (inclusive dentro do QSS), type hints, `# noqa: N802 - API do Qt` nos overrides do Qt. Antes de cada commit: `uv run -m ruff check cfauto tests tools`, `uv run -m ruff format --check cfauto tests tools` (o `.` falha só nos `.md` dos planos; não é regressão) e `uv run -m mypy` limpos; o pre-commit roda os mesmos.
- **Comandos de teste:** `rtk proxy uv run -m pytest <alvo>` (o hook RTK engole o resumo do pytest; `pytest.exe` é bloqueado pelo Smart App Control). Testes de UI rodam com `QT_QPA_PLATFORM=offscreen` (já no `tests/conftest.py`). Capturas visuais e scripts de olho usam `QT_QPA_PLATFORM=windows`.
- **Commits:** branch `feat/estilo-base`; Conventional Commits em português; cada mensagem termina com o rodapé (duas linhas, depois de uma linha em branco):
  `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` e
  `Claude-Session: https://claude.ai/code/session_01JC71423ZR21u5ifTM98XxN`.
  Não colar `\u00a0` nem escapes invisíveis na mensagem.
- **Ferramenta de olho (útil em todas as tarefas de tela):** com `QT_QPA_PLATFORM=windows`, `widget.grab().save("x.png")` funciona no Windows real e o PNG pode ser aberto com a ferramenta Read (capturas saem em escala ~1,25x). Salve capturas na pasta de scratch da sessão, nunca no repo.

## Notas do plano (desvios pequenos da spec, medidos em protótipo no Windows real)

1. QSS com `string.Template` (`${token}`) em vez de f-string: evita dobrar todas as chaves do QSS; o efeito é o mesmo (todo valor vem do `Tokens`). `gerar_qss(tokens, *, seta_baixo=ARQUIVO_SETA_BAIXO)`.
2. Dois tokens a mais: `sobre_marca` (`#ffffff`, texto sobre a marca) e `sobre_marca_hover` (`rgba(255, 255, 255, 40)`), para o QSS não ter literal de cor. Um papel a mais, `titulo` (QLabel), porque a spec §5 pede o título "Entrar" mas §3.2 não o lista. O papel `aviso` fica em negrito só dentro da faixa.
3. `QComboBox` perde a seta quando estilizado: `::drop-down` sem borda + `::down-arrow` com `seta-baixo.png` (12×12, cor `texto_secundario`), commitado em `cfauto/ui/recursos/` e gerado por `tools/gerar_recursos.py`.
4. `QSpinBox`/`QDoubleSpinBox`/`QDateEdit`/`QCheckBox`/`QRadioButton` ficam nativos do Fusion (coloridos pela paleta) na Fase 1; uma regra evita borda dobrada no `QLineEdit` interno deles e do combo editável.
5. Ordem de `aplicar_tema`: esquema claro **primeiro** (a troca de esquema recalcula a paleta), depois Fusion, paleta, fonte, QSS, tradutor, ícone.
6. Plano B da spec §11 adotado desde já: `qtbase_pt_BR.qm` é copiado para `cfauto/ui/recursos/` (já empacotado por `--add-data cfauto/ui/recursos`); a busca tenta a pasta de traduções do Qt e depois `recursos/`.
7. `*.spec` está no `.gitignore`: o ícone entra só no `build.ps1` e no comando do HANDOFF.

## Review Focus

Entradas e falhas que a spec implica e nenhuma tarefa exercitaria sozinha, da mais provável para a menos:

1. **Windows em modo escuro:** rótulos invisíveis ou fundo escuro. Esperado: texto escuro, superfícies claras. Teste na Tarefa 3 (paleta/`WindowText` e subprocesso no plugin `windows`).
2. **Recurso ausente** (`.qm`, ícone `.ico`, seta do combo): o app abre mesmo assim, só loga. Testes nas Tarefas 3 e 7.
3. **Fonte de 10 pt estoura diálogo ou PDV** (ex.: "Novo cliente", PDV em 1366×768). Medido na Tarefa 8.
4. **`aplicar_tema` chamado duas vezes** (testes, reinício de sessão): não pode empilhar tradutores. Teste na Tarefa 3.
5. **Botão padrão errado:** o diálogo de login tem o "Entrar" como padrão (pintado como primário) e o erro de login aparece com `papel=erro`. Teste na Tarefa 5.

---

## Estrutura de arquivos

```
cfauto/ui/tema/__init__.py      reexporta CLARO, Tokens, aplicar_tema, PainelMarca, pixmap_marca
cfauto/ui/tema/tokens.py        Tokens + CLARO (único com literais de cor)
cfauto/ui/tema/qss.py           gerar_qss(tokens, *, seta_baixo) + ARQUIVO_SETA_BAIXO
cfauto/ui/tema/aplicar.py       aplicar_tema(qapp, tokens=CLARO)
cfauto/ui/tema/marca.py         desenhar_marca, pixmap_marca, PainelMarca
cfauto/ui/recursos/seta-baixo.png, qtbase_pt_BR.qm, icone.ico   (novos, binários)
tools/gerar_recursos.py         gera seta-baixo.png e icone.ico
tools/capturar_telas.py         capturas PNG das telas (plugin windows)
tests/ui/conftest.py            fixture tema_isolado
tests/ui/test_tema_tokens.py, test_tema_qss.py, test_tema_aplicar.py, test_tema_marca.py,
tests/ui/test_estilo_guardas.py, test_assistente.py, tests/tools/test_gerar_recursos.py
```

Modificados: `cfauto/ui/app.py`, `janela_principal.py`, `comum.py`, `login.py`, `licenca.py`, `assistente.py`, `usuarios.py`, `auditoria.py`, `estoque/servicos.py`, `estoque/entradas.py`, `build.ps1`, `docs/superpowers/HANDOFF.md`, testes `test_app.py`, `test_login.py`, `test_licenca_ui.py`, `test_janela_principal.py`, `test_comum.py`.

**Antes da Tarefa 1:** `git switch -c feat/estilo-base` (a partir de `main`, no mesmo diretório; `.superpowers/` e `docs/superpowers/erros/` seguem untracked de propósito, não adicionar).

---

### Task 1: Tokens e teste de contraste

**Files:**
- Create: `cfauto/ui/tema/__init__.py`, `cfauto/ui/tema/tokens.py`
- Test: `tests/ui/test_tema_tokens.py`

**Interfaces:**
- Consumes: nada.
- Produces: `Tokens` (dataclass congelada) e `CLARO: Tokens` em `cfauto.ui.tema.tokens`, reexportados por `cfauto.ui.tema`. Campos: `indigo, indigo_escuro, preto, sobre_marca, sobre_marca_hover, fundo, superficie, linha, linha_campo, cabecalho_tabela, zebra, selecao, texto, texto_secundario, sucesso, sucesso_fundo, aviso, aviso_fundo, perigo, perigo_fundo, erro, aviso_sobre_marca` (str), `raio_controle, raio_painel, fonte_pt, fonte_navegacao_pt` (int), `fonte_familia` (str). As tarefas seguintes usam exatamente estes nomes.

- [ ] **Step 1: Escrever o teste que falha**

`tests/ui/test_tema_tokens.py`:

```python
import dataclasses

import pytest

from cfauto.ui.tema import CLARO, Tokens


def _luminancia(cor: str) -> float:
    r, g, b = (int(cor[i : i + 2], 16) / 255 for i in (1, 3, 5))

    def canal(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b)


def _contraste(a: str, b: str) -> float:
    claro, escuro = sorted((_luminancia(a), _luminancia(b)), reverse=True)
    return (claro + 0.05) / (escuro + 0.05)


PARES = [
    ("texto", "fundo"),
    ("texto", "superficie"),
    ("texto", "zebra"),
    ("texto", "selecao"),
    ("texto", "cabecalho_tabela"),
    ("texto_secundario", "fundo"),
    ("texto_secundario", "superficie"),
    ("sucesso", "sucesso_fundo"),
    ("sucesso", "superficie"),
    ("aviso", "aviso_fundo"),
    ("aviso", "superficie"),
    ("perigo", "perigo_fundo"),
    ("perigo", "superficie"),
    ("erro", "superficie"),
    ("aviso_sobre_marca", "indigo_escuro"),
    ("aviso_sobre_marca", "indigo"),
    ("sobre_marca", "indigo"),
    ("sobre_marca", "indigo_escuro"),
    ("sobre_marca", "preto"),
    ("indigo", "selecao"),
    ("indigo", "superficie"),
    ("indigo", "fundo"),
]


@pytest.mark.parametrize(("texto", "fundo"), PARES)
def test_contraste_minimo_wcag(texto, fundo):
    razao = _contraste(getattr(CLARO, texto), getattr(CLARO, fundo))
    assert razao >= 4.5, f"{texto} sobre {fundo}: {razao:.2f}:1"


def test_tokens_sao_imutaveis():
    with pytest.raises(dataclasses.FrozenInstanceError):
        CLARO.indigo = "#000000"  # type: ignore[misc]


def test_cores_hex_sao_rrggbb():
    for campo in dataclasses.fields(Tokens):
        valor = getattr(CLARO, campo.name)
        if isinstance(valor, str) and valor.startswith("#"):
            assert len(valor) == 7, campo.name
            int(valor[1:], 16)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `rtk proxy uv run -m pytest tests/ui/test_tema_tokens.py -v`
Expected: FAIL/ERRO de coleta — `ModuleNotFoundError: No module named 'cfauto.ui.tema'`.

- [ ] **Step 3: Implementar**

`cfauto/ui/tema/tokens.py`:

```python
"""Tokens do tema. É o único arquivo de cfauto/ui com literais de cor."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Tokens:
    indigo: str
    indigo_escuro: str
    preto: str
    sobre_marca: str
    sobre_marca_hover: str
    fundo: str
    superficie: str
    linha: str
    linha_campo: str
    cabecalho_tabela: str
    zebra: str
    selecao: str
    texto: str
    texto_secundario: str
    sucesso: str
    sucesso_fundo: str
    aviso: str
    aviso_fundo: str
    perigo: str
    perigo_fundo: str
    erro: str
    aviso_sobre_marca: str
    raio_controle: int
    raio_painel: int
    fonte_familia: str
    fonte_pt: int
    fonte_navegacao_pt: int


CLARO = Tokens(
    indigo="#3433cc",
    indigo_escuro="#14124f",
    preto="#000000",
    sobre_marca="#ffffff",
    sobre_marca_hover="rgba(255, 255, 255, 40)",
    fundo="#f6f7fb",
    superficie="#ffffff",
    linha="#dde0ee",
    linha_campo="#c4c8dc",
    cabecalho_tabela="#e9eaf8",
    zebra="#f9faff",
    selecao="#ecebff",
    texto="#1f2233",
    texto_secundario="#5b5f7a",
    sucesso="#1d6b34",
    sucesso_fundo="#dff3e4",
    aviso="#8a5a00",
    aviso_fundo="#fdf0d3",
    perigo="#a3231a",
    perigo_fundo="#fbdedb",
    erro="#b3261e",
    aviso_sobre_marca="#ffd27a",
    raio_controle=4,
    raio_painel=6,
    fonte_familia="Segoe UI",
    fonte_pt=10,
    fonte_navegacao_pt=12,
)
```

`cfauto/ui/tema/__init__.py`:

```python
from cfauto.ui.tema.tokens import CLARO, Tokens

__all__ = ["CLARO", "Tokens"]
```

- [ ] **Step 4: Rodar e ver passar**

Run: `rtk proxy uv run -m pytest tests/ui/test_tema_tokens.py -v`
Expected: PASS (24 testes: 22 pares + 2).

- [ ] **Step 5: Lint e commit**

Run: `uv run -m ruff check cfauto tests tools && uv run -m ruff format --check cfauto tests tools && uv run -m mypy`

```bash
git add cfauto/ui/tema tests/ui/test_tema_tokens.py
git commit -m "feat(ui): tokens do tema claro com teste de contraste WCAG" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JC71423ZR21u5ifTM98XxN"
```

---

### Task 2: QSS gerado, seta do combo e fixture `tema_isolado`

**Files:**
- Create: `cfauto/ui/tema/qss.py`, `tools/gerar_recursos.py`, `cfauto/ui/recursos/seta-baixo.png` (gerado), `tests/ui/conftest.py`
- Test: `tests/ui/test_tema_qss.py`

**Interfaces:**
- Consumes: `Tokens`, `CLARO` (Tarefa 1).
- Produces: `cfauto.ui.tema.qss.gerar_qss(tokens: Tokens, *, seta_baixo: Path = ARQUIVO_SETA_BAIXO) -> str`; `ARQUIVO_SETA_BAIXO: Path`; fixture `tema_isolado(qapp)` em `tests/ui/conftest.py` (devolve a `QApplication` e desfaz folha/estilo/paleta/fonte/esquema ao fim; as tarefas 3 e 7 acrescentam tradutor e ícone ao desfazer). O QSS já cobre os seletores que as tarefas 4–6 usam: `QToolBar#faixa`, `QFrame#lateral`, `QListWidget#navegacao`, `QLabel[papel=...]` (`titulo`, `erro`, `aviso`, `sucesso`), `QPushButton[papel="primario"|"perigo"]`, `QPushButton:default`.

- [ ] **Step 1: Escrever o teste que falha**

`tests/ui/test_tema_qss.py`:

```python
from pathlib import Path

from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QPushButton

from cfauto.ui.tema.qss import ARQUIVO_SETA_BAIXO, gerar_qss
from cfauto.ui.tema.tokens import CLARO


def test_qss_sem_placeholder_pendente():
    assert "$" not in gerar_qss(CLARO)


def test_qss_cobre_papeis_e_objetos_nomeados():
    qss = gerar_qss(CLARO)
    for trecho in (
        'QPushButton[papel="primario"]',
        'QPushButton[papel="perigo"]',
        "QPushButton:default",
        'QLabel[papel="titulo"]',
        'QLabel[papel="erro"]',
        'QLabel[papel="aviso"]',
        'QLabel[papel="sucesso"]',
        "QToolBar#faixa",
        "QFrame#lateral",
        "QListWidget#navegacao",
        "QTabBar::tab:selected",
        "QHeaderView::section",
        "QMessageBox",
        "QScrollBar",
        "QToolTip",
        "QGroupBox",
    ):
        assert trecho in qss, trecho


def test_qss_usa_os_valores_dos_tokens():
    qss = gerar_qss(CLARO)
    for valor in (
        CLARO.indigo,
        CLARO.indigo_escuro,
        CLARO.preto,
        CLARO.erro,
        CLARO.aviso,
        CLARO.sucesso,
        CLARO.perigo,
        CLARO.aviso_sobre_marca,
        CLARO.zebra,
        CLARO.sobre_marca_hover,
    ):
        assert valor in qss, valor


def test_seta_do_combo_existe_e_carrega():
    imagem = QImage(str(ARQUIVO_SETA_BAIXO))
    assert not imagem.isNull()
    assert (imagem.width(), imagem.height()) == (12, 12)


def test_qss_aponta_para_a_seta_informada():
    assert ARQUIVO_SETA_BAIXO.as_posix() in gerar_qss(CLARO)
    assert "C:/outra/seta.png" in gerar_qss(CLARO, seta_baixo=Path("C:/outra/seta.png"))


def test_qss_nao_gera_erro_de_parse(tema_isolado):
    mensagens: list[str] = []
    anterior = qInstallMessageHandler(lambda tipo, contexto, texto: mensagens.append(texto))
    try:
        # Sanidade: o handler tem que enxergar uma folha inválida, senão o teste seria vazio.
        tema_isolado.setStyleSheet("}{ isto nao e qss")
        invalida = [m for m in mensagens if "parse" in m.lower()]
        mensagens.clear()
        tema_isolado.setStyleSheet(gerar_qss(CLARO))
        QPushButton("x").ensurePolished()
    finally:
        qInstallMessageHandler(anterior)
    assert invalida, "o handler não capturou o erro de uma folha inválida"
    assert not [m for m in mensagens if "parse" in m.lower()]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `rtk proxy uv run -m pytest tests/ui/test_tema_qss.py -v`
Expected: ERRO de coleta — `ModuleNotFoundError: cfauto.ui.tema.qss` (e fixture `tema_isolado` ausente).

- [ ] **Step 3: Fixture, gerador da seta e `qss.py`**

`tests/ui/conftest.py`:

```python
import pytest
from PySide6.QtGui import QFont, QPalette


@pytest.fixture
def tema_isolado(qapp):
    """Entrega a QApplication e desfaz no fim o que `aplicar_tema` mudou nela."""
    estilo = qapp.style().objectName()
    paleta = QPalette(qapp.palette())
    fonte = QFont(qapp.font())
    folha = qapp.styleSheet()
    yield qapp
    qapp.setStyleSheet(folha)
    qapp.setStyle(estilo)
    qapp.setPalette(paleta)
    qapp.setFont(fonte)
    qapp.styleHints().unsetColorScheme()
```

`tools/gerar_recursos.py`:

```python
"""Gera os recursos binários do tema em cfauto/ui/recursos.

Rode de novo só quando o logo ou os tokens mudarem; o resultado é commitado.

Uso: uv run python tools/gerar_recursos.py
"""

import sys
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPolygonF

from cfauto.ui.tema.tokens import CLARO

RECURSOS = Path(__file__).resolve().parent.parent / "cfauto" / "ui" / "recursos"
LADO_SETA = 12


def gerar_seta(destino: Path, cor: str = CLARO.texto_secundario) -> None:
    """Triângulo para baixo (seta do QComboBox), 12x12 com fundo transparente."""
    imagem = QImage(LADO_SETA, LADO_SETA, QImage.Format.Format_ARGB32)
    imagem.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    pintor.setPen(Qt.PenStyle.NoPen)
    pintor.setBrush(QColor(cor))
    pintor.drawPolygon(QPolygonF([QPointF(1.5, 3.5), QPointF(10.5, 3.5), QPointF(6.0, 8.5)]))
    pintor.end()
    if not imagem.save(str(destino), "PNG"):
        raise OSError(f"não consegui gravar {destino}")


def main() -> int:
    gerar_seta(RECURSOS / "seta-baixo.png")
    print(f"gerado: {RECURSOS / 'seta-baixo.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Run: `uv run python tools/gerar_recursos.py` (cria `cfauto/ui/recursos/seta-baixo.png`).

`cfauto/ui/tema/qss.py`:

```python
"""QSS do tema, gerado dos tokens. Sem literal de cor aqui: tudo vem de `${token}`."""

from dataclasses import asdict
from pathlib import Path
from string import Template

from cfauto.ui.tema.tokens import Tokens

ARQUIVO_SETA_BAIXO = Path(__file__).resolve().parent.parent / "recursos" / "seta-baixo.png"

_MODELO = Template(
    """
QMainWindow { background: ${fundo}; }
QDialog, QWizard, QWizardPage, QMessageBox { background: ${superficie}; }

QLabel[papel="titulo"] { color: ${indigo_escuro}; font-size: 13pt; font-weight: 600; }
QLabel[papel="erro"] { color: ${erro}; }
QLabel[papel="aviso"] { color: ${aviso}; }
QLabel[papel="sucesso"] { color: ${sucesso}; }

QToolBar#faixa {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 ${preto}, stop:0.4 ${indigo_escuro}, stop:1 ${indigo});
    border: none;
    padding: 4px 8px;
    spacing: 6px;
}
QToolBar#faixa QLabel { color: ${sobre_marca}; background: transparent; }
QToolBar#faixa QLabel[papel="aviso"] { color: ${aviso_sobre_marca}; font-weight: bold; }
QToolBar#faixa QToolButton {
    color: ${sobre_marca};
    background: transparent;
    border: none;
    border-radius: ${raio_controle}px;
    padding: 5px 10px;
}
QToolBar#faixa QToolButton:hover { background: ${sobre_marca_hover}; }

QFrame#lateral { background: ${superficie}; border: none; border-right: 1px solid ${linha}; }
QListWidget#navegacao { background: ${superficie}; border: none; outline: none; }
QListWidget#navegacao::item {
    color: ${texto};
    padding: 8px 14px;
    border-left: 3px solid transparent;
}
QListWidget#navegacao::item:hover { background: ${fundo}; }
QListWidget#navegacao::item:selected {
    background: ${selecao};
    color: ${indigo};
    border-left: 3px solid ${indigo};
}

QTabWidget::pane { border: 1px solid ${linha}; background: ${superficie}; }
QTabBar::tab {
    background: transparent;
    color: ${texto_secundario};
    padding: 8px 16px;
    border: none;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected { color: ${indigo}; border-bottom: 2px solid ${indigo}; }
QTabBar::tab:hover:!selected { color: ${texto}; }

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
    background: ${superficie};
    color: ${texto};
    border: 1px solid ${linha_campo};
    border-radius: ${raio_controle}px;
    padding: 5px 8px;
    selection-background-color: ${indigo};
    selection-color: ${sobre_marca};
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid ${indigo};
}
QAbstractSpinBox QLineEdit, QComboBox QLineEdit {
    border: none;
    background: transparent;
    padding: 0;
}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled {
    background: ${fundo};
    color: ${texto_secundario};
}
QComboBox::drop-down { border: none; width: 22px; }
QComboBox::down-arrow { image: url("${seta_baixo}"); width: 12px; height: 12px; }
QComboBox QAbstractItemView {
    background: ${superficie};
    color: ${texto};
    border: 1px solid ${linha_campo};
    selection-background-color: ${selecao};
    selection-color: ${indigo};
    outline: none;
}

QPushButton {
    background: ${superficie};
    color: ${texto};
    border: 1px solid ${linha_campo};
    border-radius: ${raio_controle}px;
    padding: 6px 18px;
}
QPushButton:hover { border-color: ${indigo}; }
QPushButton:pressed { background: ${selecao}; }
QPushButton:disabled {
    background: ${fundo};
    color: ${texto_secundario};
    border-color: ${linha};
}
QPushButton[papel="primario"], QPushButton:default {
    background: ${indigo};
    color: ${sobre_marca};
    border: 1px solid ${indigo};
    font-weight: 600;
}
QPushButton[papel="primario"]:hover, QPushButton:default:hover { background: ${indigo_escuro}; }
QPushButton[papel="primario"]:disabled, QPushButton:default:disabled {
    background: ${linha_campo};
    border-color: ${linha_campo};
    color: ${superficie};
}
QPushButton[papel="perigo"] { color: ${perigo}; border: 1px solid ${perigo}; }
QPushButton[papel="perigo"]:hover { background: ${perigo_fundo}; }

QTableView, QTableWidget {
    background: ${superficie};
    alternate-background-color: ${zebra};
    color: ${texto};
    gridline-color: ${linha};
    border: 1px solid ${linha};
    selection-background-color: ${selecao};
    selection-color: ${texto};
}
QHeaderView { background: ${cabecalho_tabela}; border: none; }
QTableCornerButton::section { background: ${cabecalho_tabela}; border: none; }
QHeaderView::section {
    background: ${cabecalho_tabela};
    color: ${texto};
    padding: 6px 8px;
    border: none;
    border-right: 1px solid ${linha};
    border-bottom: 1px solid ${linha};
    font-weight: 600;
}

QGroupBox {
    border: 1px solid ${linha};
    border-radius: ${raio_painel}px;
    margin-top: 12px;
    padding-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: ${texto_secundario};
}

QScrollBar:vertical { background: transparent; width: 12px; margin: 0; }
QScrollBar::handle:vertical {
    background: ${linha_campo};
    border-radius: 4px;
    min-height: 24px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover { background: ${texto_secundario}; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 0; }
QScrollBar::handle:horizontal {
    background: ${linha_campo};
    border-radius: 4px;
    min-width: 24px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover { background: ${texto_secundario}; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QToolTip {
    background: ${indigo_escuro};
    color: ${sobre_marca};
    border: 1px solid ${indigo};
    padding: 4px 6px;
}
"""
)


def gerar_qss(tokens: Tokens, *, seta_baixo: Path = ARQUIVO_SETA_BAIXO) -> str:
    return _MODELO.substitute(asdict(tokens), seta_baixo=seta_baixo.as_posix())
```

- [ ] **Step 4: Rodar e ver passar**

Run: `rtk proxy uv run -m pytest tests/ui/test_tema_qss.py tests/ui/test_tema_tokens.py -v`
Expected: PASS. Se a asserção de sanidade do parse falhar (Qt não reportou a folha inválida), troque a folha inválida até o handler capturar a mensagem "Could not parse application stylesheet" — a sanidade é o que impede o teste de ser vazio.

- [ ] **Step 5: Conferência visual rápida (obrigatória, não commitar a imagem)**

Num script de scratch com `QT_QPA_PLATFORM=windows`, aplique `gerar_qss(CLARO)` numa `QApplication` com estilo Fusion, monte um `QDialog` com `QLineEdit`, `QComboBox` (com itens), `QTableWidget` 3×3 com `setAlternatingRowColors(True)`, `QTabWidget` e um `QDialogButtonBox` Ok/Cancel, salve `dialogo.grab()` em PNG e abra com Read. Confirme: seta do combo visível, cabeçalho da tabela sem área preta, botão OK índigo (padrão), aba ativa com sublinhado índigo. Se algo estiver errado, corrija o QSS antes de seguir.

- [ ] **Step 6: Lint e commit**

Run: `uv run -m ruff check cfauto tests tools && uv run -m ruff format --check cfauto tests tools && uv run -m mypy`

```bash
git add cfauto/ui/tema/qss.py cfauto/ui/recursos/seta-baixo.png tools/gerar_recursos.py tests/ui/conftest.py tests/ui/test_tema_qss.py
git commit -m "feat(ui): QSS gerado dos tokens e seta do combo" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JC71423ZR21u5ifTM98XxN"
```

---

### Task 3: `aplicar_tema`, tradução pt_BR e troca em `app.py`

**Files:**
- Create: `cfauto/ui/tema/aplicar.py`, `cfauto/ui/recursos/qtbase_pt_BR.qm` (cópia)
- Modify: `cfauto/ui/tema/__init__.py`, `cfauto/ui/app.py`, `tests/ui/conftest.py`, `tests/ui/test_app.py`
- Test: `tests/ui/test_tema_aplicar.py`

**Interfaces:**
- Consumes: `gerar_qss`, `CLARO`, `Tokens`.
- Produces: `aplicar_tema(qapp: QApplication, tokens: Tokens = CLARO) -> None` (reexportado por `cfauto.ui.tema`); `aplicar.RECURSOS: Path`; `aplicar._pastas_traducao() -> list[Path]` (monkeypatchável); `aplicar._tradutor: QTranslator | None`. `configurar_aparencia` deixa de existir.

- [ ] **Step 1: Copiar o `.qm` e escrever os testes que falham**

Run (PowerShell, na raiz do repo): `Copy-Item .venv\Lib\site-packages\PySide6\translations\qtbase_pt_BR.qm cfauto\ui\recursos\qtbase_pt_BR.qm`

`tests/ui/test_tema_aplicar.py`:

```python
import logging

from PySide6.QtGui import QColor, QPalette

from cfauto.ui.tema import CLARO, aplicar, aplicar_tema


def test_aplica_fusion_paleta_fonte_e_folha(tema_isolado):
    aplicar_tema(tema_isolado)
    assert tema_isolado.style().objectName().lower() == "fusion"
    assert tema_isolado.styleSheet()
    paleta = tema_isolado.palette()
    assert paleta.color(QPalette.ColorRole.WindowText) == QColor(CLARO.texto)
    assert paleta.color(QPalette.ColorRole.Window) == QColor(CLARO.superficie)
    assert paleta.color(QPalette.ColorRole.Highlight) == QColor(CLARO.indigo)
    assert tema_isolado.font().pointSize() == CLARO.fonte_pt


def test_traducao_pt_br_instalada(tema_isolado):
    aplicar_tema(tema_isolado)
    assert tema_isolado.translate("QPlatformTheme", "Cancel") == "Cancelar"


def test_arquivo_de_traducao_vai_junto_no_repo():
    assert (aplicar.RECURSOS / "qtbase_pt_BR.qm").is_file()


def test_sem_arquivo_de_traducao_nao_levanta_e_loga(tema_isolado, monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(aplicar, "_pastas_traducao", lambda: [tmp_path])
    with caplog.at_level(logging.WARNING, logger="cfauto.ui"):
        aplicar_tema(tema_isolado)
    assert any("qtbase_pt_BR.qm" in r.getMessage() for r in caplog.records)
    assert tema_isolado.style().objectName().lower() == "fusion"


def test_passo_com_falha_nao_interrompe_os_seguintes(tema_isolado, monkeypatch, caplog):
    def quebrar(*args, **kwargs):
        raise RuntimeError("qss quebrado")

    monkeypatch.setattr(aplicar, "gerar_qss", quebrar)
    with caplog.at_level(logging.ERROR, logger="cfauto.ui"):
        aplicar_tema(tema_isolado)
    assert any(r.levelno == logging.ERROR for r in caplog.records)
    assert tema_isolado.translate("QPlatformTheme", "Cancel") == "Cancelar"


def test_aplicar_duas_vezes_nao_empilha_tradutores(tema_isolado):
    aplicar_tema(tema_isolado)
    primeiro = aplicar._tradutor
    aplicar_tema(tema_isolado)
    assert aplicar._tradutor is not primeiro
    assert tema_isolado.translate("QPlatformTheme", "Cancel") == "Cancelar"
    tema_isolado.removeTranslator(aplicar._tradutor)
    aplicar._tradutor = None
    assert tema_isolado.translate("QPlatformTheme", "Cancel") == "Cancel"
```

Em `tests/ui/test_app.py`, o script do subprocesso passa a usar o tema novo (troque o bloco `_SCRIPT_APARENCIA`):

```python
_SCRIPT_APARENCIA = """
import sys
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication
from cfauto.ui.tema import aplicar_tema
qapp = QApplication(sys.argv)
aplicar_tema(qapp)
print(qapp.palette().color(QPalette.ColorRole.WindowText).lightness())
"""
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `rtk proxy uv run -m pytest tests/ui/test_tema_aplicar.py tests/ui/test_app.py -v`
Expected: FAIL — `ImportError: cannot import name 'aplicar_tema'` (e o teste de aparência no subprocesso).

- [ ] **Step 3: Implementar**

`cfauto/ui/tema/aplicar.py`:

```python
import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, Qt, QTranslator
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from cfauto.ui.tema.qss import gerar_qss
from cfauto.ui.tema.tokens import CLARO, Tokens

log = logging.getLogger("cfauto.ui")
RECURSOS = Path(__file__).resolve().parent.parent / "recursos"
ARQUIVO_TRADUCAO = "qtbase_pt_BR.qm"
_tradutor: QTranslator | None = None


def _paleta(t: Tokens) -> QPalette:
    paleta = QPalette(QColor(t.superficie))
    cores = {
        QPalette.ColorRole.Window: t.superficie,
        QPalette.ColorRole.WindowText: t.texto,
        QPalette.ColorRole.Base: t.superficie,
        QPalette.ColorRole.AlternateBase: t.zebra,
        QPalette.ColorRole.Text: t.texto,
        QPalette.ColorRole.Button: t.superficie,
        QPalette.ColorRole.ButtonText: t.texto,
        QPalette.ColorRole.Highlight: t.indigo,
        QPalette.ColorRole.HighlightedText: t.sobre_marca,
        QPalette.ColorRole.PlaceholderText: t.texto_secundario,
        QPalette.ColorRole.ToolTipBase: t.indigo_escuro,
        QPalette.ColorRole.ToolTipText: t.sobre_marca,
    }
    for papel, cor in cores.items():
        paleta.setColor(papel, QColor(cor))
    for papel in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        paleta.setColor(QPalette.ColorGroup.Disabled, papel, QColor(t.texto_secundario))
    return paleta


def _pastas_traducao() -> list[Path]:
    return [Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)), RECURSOS]


def _instalar_traducao(qapp: QApplication) -> None:
    global _tradutor
    if _tradutor is not None:
        qapp.removeTranslator(_tradutor)
        _tradutor = None
    for pasta in _pastas_traducao():
        tradutor = QTranslator(qapp)
        if tradutor.load(ARQUIVO_TRADUCAO, str(pasta)):
            qapp.installTranslator(tradutor)
            _tradutor = tradutor
            return
    log.warning("%s não encontrado; os botões do Qt ficam em inglês", ARQUIVO_TRADUCAO)


def aplicar_tema(qapp: QApplication, tokens: Tokens = CLARO) -> None:
    """Aplica o tema na aplicação. Cada passo falho é logado e não impede os seguintes."""
    passos: list[tuple[str, Callable[[], object]]] = [
        ("esquema de cor", lambda: qapp.styleHints().setColorScheme(Qt.ColorScheme.Light)),
        ("estilo Fusion", lambda: qapp.setStyle("Fusion")),
        ("paleta", lambda: qapp.setPalette(_paleta(tokens))),
        ("fonte", lambda: qapp.setFont(QFont(tokens.fonte_familia, tokens.fonte_pt))),
        ("folha de estilo", lambda: qapp.setStyleSheet(gerar_qss(tokens))),
        ("tradução", lambda: _instalar_traducao(qapp)),
    ]
    for nome, passo in passos:
        try:
            passo()
        except Exception:
            log.exception("tema: falha ao aplicar %s", nome)
```

`cfauto/ui/tema/__init__.py`:

```python
from cfauto.ui.tema.aplicar import aplicar_tema
from cfauto.ui.tema.tokens import CLARO, Tokens

__all__ = ["CLARO", "Tokens", "aplicar_tema"]
```

`cfauto/ui/app.py`: apague `configurar_aparencia` inteira (e a linha `from PySide6.QtCore import Qt`, que fica sem uso), importe `from cfauto.ui.tema import aplicar_tema` (depois de `from cfauto.ui.login import DialogoLogin`) e troque em `main` a linha `configurar_aparencia(qapp)` por `aplicar_tema(qapp)`.

`tests/ui/conftest.py`: no fim da fixture, depois de `qapp.styleHints().unsetColorScheme()`, acrescente o desfazer do tradutor (e `from cfauto.ui.tema import aplicar` no topo do arquivo):

```python
    if aplicar._tradutor is not None:
        qapp.removeTranslator(aplicar._tradutor)
        aplicar._tradutor = None
```

- [ ] **Step 4: Rodar e ver passar**

Run: `rtk proxy uv run -m pytest tests/ui/test_tema_aplicar.py tests/ui/test_app.py tests/ui/test_tema_qss.py -v`
Expected: PASS (o teste de aparência no `windows` roda no Windows e exige `WindowText` com luminosidade < 128).

- [ ] **Step 5: Suíte, lint e commit**

Run: `rtk proxy uv run -m pytest -q` (suíte inteira verde) e `uv run -m ruff check cfauto tests tools && uv run -m ruff format --check cfauto tests tools && uv run -m mypy`

```bash
git add cfauto/ui/tema cfauto/ui/app.py cfauto/ui/recursos/qtbase_pt_BR.qm tests/ui
git commit -m "feat(ui): aplicar_tema com Fusion, paleta, QSS e tradução pt_BR" -m "Substitui configurar_aparencia. Cada passo é isolado: se algo falhar o app abre com o visual padrão." -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JC71423ZR21u5ifTM98XxN"
```

---

### Task 4: Casca da janela principal, zebra e fim dos estilos inline da casca

**Files:**
- Modify: `cfauto/ui/janela_principal.py`, `cfauto/ui/comum.py`, `cfauto/ui/usuarios.py` (tabela ~linha 138), `cfauto/ui/auditoria.py` (~58), `cfauto/ui/estoque/servicos.py` (~60, tabela de materiais), `cfauto/ui/estoque/entradas.py` (tabela ~187 e `avisos` ~179)
- Test: `tests/ui/test_janela_principal.py`, `tests/ui/test_comum.py`, `tests/ui/test_estilo_guardas.py` (novo)

**Interfaces:**
- Consumes: `CLARO` (`fonte_navegacao_pt`), `aplicar_tema`, fixture `tema_isolado`; seletores do QSS da Tarefa 2.
- Produces: `QToolBar` com `objectName("faixa")`, `QFrame` `objectName("lateral")`, `QListWidget` `objectName("navegacao")`, `aviso_licenca.property("papel") == "aviso"`; `criar_tabela` liga a zebra; constante `FONTE_NAVEGACAO_PT` deixa de existir (nenhum teste a usa).

- [ ] **Step 1: Escrever os testes que falham**

Acrescente a `tests/ui/test_janela_principal.py` (imports novos: `from PySide6.QtWidgets import QFrame, QListWidget, QToolBar` e `from cfauto.ui.tema import aplicar_tema`):

```python
def test_casca_tem_os_nomes_que_o_tema_usa(qtbot, fabrica):
    ator = Ator(1, "Dono", "dono", True, frozenset())
    janela = JanelaPrincipal(fabrica, ator, _estado(100))
    qtbot.addWidget(janela)
    assert janela.findChild(QToolBar).objectName() == "faixa"
    assert janela.findChild(QFrame, "lateral") is not None
    assert janela.findChild(QListWidget, "navegacao") is not None
    assert janela.aviso_licenca.property("papel") == "aviso"
    assert janela.aviso_licenca.styleSheet() == ""


def test_constroi_todas_as_paginas_com_o_tema_aplicado(qtbot, fabrica, tema_isolado):
    aplicar_tema(tema_isolado)
    ator = Ator(1, "Dono", "dono", True, frozenset())
    janela = JanelaPrincipal(fabrica, ator, _estado(5))
    qtbot.addWidget(janela)
    janela.show()
    for linha in range(len(janela.titulos_navegacao())):
        janela.selecionar_modulo(linha)
    janela.acao_configuracoes.trigger()
    assert janela.pagina_atual() is janela.configuracoes
    assert janela.aviso_licenca.text().strip() == "Licença expira em 5 dias"
```

Acrescente a `tests/ui/test_comum.py` (importe `criar_tabela` se ainda não estiver importado):

```python
def test_criar_tabela_liga_a_zebra():
    assert criar_tabela(["A", "B"]).alternatingRowColors() is True
```

`tests/ui/test_estilo_guardas.py` (novo):

```python
from pathlib import Path

import cfauto.ui

RAIZ_UI = Path(cfauto.ui.__file__).parent


def test_tabelas_montadas_a_mao_ligam_a_zebra():
    sem_zebra = []
    for arquivo in sorted(RAIZ_UI.rglob("*.py")):
        if arquivo.name == "comum.py":
            continue
        texto = arquivo.read_text(encoding="utf-8")
        if "QTableWidget(" in texto and "setAlternatingRowColors(True)" not in texto:
            sem_zebra.append(arquivo.relative_to(RAIZ_UI).as_posix())
    assert not sem_zebra, f"tabelas sem zebra: {sem_zebra}"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `rtk proxy uv run -m pytest tests/ui/test_janela_principal.py tests/ui/test_comum.py tests/ui/test_estilo_guardas.py -v`
Expected: FAIL (objectNames ausentes, zebra desligada, 4 arquivos sem zebra).

- [ ] **Step 3: Implementar**

`cfauto/ui/janela_principal.py`:
- Imports: tire `QPalette` de `from PySide6.QtGui import QAction, QCloseEvent, QPalette` (fica `QAction, QCloseEvent`); acrescente `from cfauto.ui.tema import CLARO`; apague a constante `FONTE_NAVEGACAO_PT = 12`.
- Logo depois de `barra.setMovable(False)`: `barra.setObjectName("faixa")`.
- Troque

```python
        self.aviso_licenca.setStyleSheet("color: #b9770e; font-weight: bold;")
```

por

```python
        self.aviso_licenca.setProperty("papel", "aviso")
```

- Na lista de navegação: depois de `self._navegacao = QListWidget()` acrescente `self._navegacao.setObjectName("navegacao")` e troque `fonte.setPointSize(FONTE_NAVEGACAO_PT)` por `fonte.setPointSize(CLARO.fonte_navegacao_pt)`.
- Na lateral, troque o bloco

```python
        self._lateral = QFrame()
        self._lateral.setFrameShape(QFrame.Shape.StyledPanel)
        self._lateral.setBackgroundRole(QPalette.ColorRole.Base)
        self._lateral.setAutoFillBackground(True)
        self._lateral.setFixedWidth(LARGURA_NAVEGACAO)
```

por

```python
        self._lateral = QFrame()
        self._lateral.setObjectName("lateral")
        self._lateral.setFixedWidth(LARGURA_NAVEGACAO)
```

e ajuste o comentário anterior ("Um só painel (moldura e fundo da lista)...") para "Um só painel (fundo e borda vêm do tema) com o logo no espaço vazio embaixo.".

`cfauto/ui/comum.py`: em `criar_tabela`, depois de `tabela.verticalHeader().setVisible(False)` acrescente `tabela.setAlternatingRowColors(True)`.

Nas quatro tabelas montadas à mão, logo depois da criação, acrescente `<atributo>.setAlternatingRowColors(True)`: `usuarios.py` (`self.tabela`), `auditoria.py` (`self.tabela`), `estoque/servicos.py` (`self.materiais`), `estoque/entradas.py` (`self.tabela` de `QTableWidget(len(self._estados), ...)`).

`cfauto/ui/estoque/entradas.py`: troque `self.avisos.setStyleSheet("color: #b9770e;")` por `self.avisos.setProperty("papel", "aviso")`.

- [ ] **Step 4: Rodar e ver passar**

Run: `rtk proxy uv run -m pytest tests/ui -q`
Expected: PASS (todas as telas de UI).

- [ ] **Step 5: Conferência visual (obrigatória, não commitar a imagem)**

Em script de scratch com `QT_QPA_PLATFORM=windows`: aplique `aplicar_tema`, crie um BD temporário (`criar_engine`/`migrar`/`criar_fabrica`, como `tests/conftest.py`), construa `JanelaPrincipal` como admin com licença expirando em 5 dias, `show()`, salve `janela.grab()` e abra com Read. Confirme: faixa com gradiente e texto branco, aviso âmbar legível sobre a faixa, item ativo da lateral com marcador índigo, logo embaixo. Registre no relatório o que viu; corrija só QSS/tokens se estiver errado.

- [ ] **Step 6: Suíte, lint e commit**

Run: `rtk proxy uv run -m pytest -q` e `uv run -m ruff check cfauto tests tools && uv run -m ruff format --check cfauto tests tools && uv run -m mypy`

```bash
git add cfauto/ui tests/ui
git commit -m "feat(ui): faixa de topo, lateral com marcador e zebra nas tabelas" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JC71423ZR21u5ifTM98XxN"
```

---

### Task 5: `PainelMarca`, login e licença com painel dividido

**Files:**
- Create: `cfauto/ui/tema/marca.py`
- Modify: `cfauto/ui/tema/__init__.py`, `cfauto/ui/login.py`, `cfauto/ui/licenca.py`
- Test: `tests/ui/test_tema_marca.py` (novo), `tests/ui/test_login.py`, `tests/ui/test_licenca_ui.py`

**Interfaces:**
- Consumes: `CLARO`, `Tokens`; `ARQUIVO_LOGO` = `cfauto/ui/recursos/logo.svg`; papéis `titulo`/`erro` do QSS.
- Produces: `desenhar_marca(pintor: QPainter, largura: float, altura: float, tokens: Tokens = CLARO) -> None`, `pixmap_marca(largura: int, altura: int, tokens: Tokens = CLARO) -> QPixmap`, `PainelMarca(QFrame)` (largura fixa 210, reexportados por `cfauto.ui.tema`); novo atributo `rotulo_titulo` em `DialogoLogin` e `DialogoLicenca`. A Tarefa 6 usa `pixmap_marca`.

- [ ] **Step 1: Escrever os testes que falham**

`tests/ui/test_tema_marca.py`:

```python
from cfauto.ui.tema import PainelMarca, pixmap_marca


def test_pixmap_marca_tem_o_tamanho_pedido(qapp):
    pixmap = pixmap_marca(210, 300)
    assert (pixmap.width(), pixmap.height()) == (210, 300)


def test_pixmap_marca_desenha_o_gradiente_da_marca(qapp):
    imagem = pixmap_marca(210, 300).toImage()
    assert imagem.pixelColor(2, 2).lightness() < 40  # canto alto: preto
    baixo = imagem.pixelColor(207, 297)  # canto baixo: índigo
    assert baixo.blue() > 150 and baixo.red() < 90


def test_painel_de_marca_tem_largura_fixa_e_pinta(qtbot):
    painel = PainelMarca()
    qtbot.addWidget(painel)
    painel.resize(210, 300)
    assert painel.minimumWidth() == painel.maximumWidth() == 210
    assert painel.grab().toImage().pixelColor(2, 2).lightness() < 40
```

Acrescente a `tests/ui/test_login.py` (imports: `from PySide6.QtWidgets import QDialogButtonBox`, `from cfauto.ui.tema import PainelMarca`):

```python
def test_login_tem_painel_de_marca_titulo_e_papel_de_erro(qtbot, fabrica):
    dlg = DialogoLogin(fabrica)
    qtbot.addWidget(dlg)
    assert dlg.findChild(PainelMarca) is not None
    assert dlg.rotulo_titulo.text() == "Entrar"
    assert dlg.rotulo_titulo.property("papel") == "titulo"
    assert dlg.rotulo_erro.property("papel") == "erro"
    assert dlg.rotulo_erro.styleSheet() == ""


def test_login_bloqueado_tem_titulo_proprio(qtbot, fabrica):
    dlg = DialogoLogin(fabrica, login_fixo="dono")
    qtbot.addWidget(dlg)
    assert dlg.rotulo_titulo.text() == "Tela bloqueada"


def test_botao_entrar_e_o_padrao_do_dialogo(qtbot, fabrica):
    dlg = DialogoLogin(fabrica)
    qtbot.addWidget(dlg)
    dlg.show()
    botoes = dlg.findChild(QDialogButtonBox)
    assert botoes.button(QDialogButtonBox.StandardButton.Ok).text() == "Entrar"
    assert botoes.button(QDialogButtonBox.StandardButton.Ok).isDefault()
```

Acrescente a `tests/ui/test_licenca_ui.py` (imports: `from cfauto.ui.tema import PainelMarca`):

```python
def test_dialogo_de_licenca_tem_painel_de_marca_e_papeis(qtbot, fabrica):
    dlg = DialogoLicenca(fabrica, EstadoLicenca(StatusLicenca.AUSENTE))
    qtbot.addWidget(dlg)
    assert dlg.findChild(PainelMarca) is not None
    assert dlg.rotulo_titulo.text() == "Ativar licença"
    assert dlg.rotulo_erro.property("papel") == "erro"
    assert dlg.rotulo_erro.styleSheet() == ""
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `rtk proxy uv run -m pytest tests/ui/test_tema_marca.py tests/ui/test_login.py tests/ui/test_licenca_ui.py -v`
Expected: FAIL (`ImportError: PainelMarca`, `rotulo_titulo` ausente).

- [ ] **Step 3: Implementar `marca.py` e reexportar**

`cfauto/ui/tema/marca.py`:

```python
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPaintEvent,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QSizePolicy, QWidget

from cfauto.ui.tema.tokens import CLARO, Tokens

ARQUIVO_LOGO = Path(__file__).resolve().parent.parent / "recursos" / "logo.svg"
LARGURA_PAINEL = 210
LADO_LOGO = 104
NOME = "CFAUTO"
SLOGAN = "O SEU CFO AUTOMÁTICO"
_ESPACO_LOGO_NOME = 14
_ESPACO_NOME_SLOGAN = 4


def desenhar_marca(
    pintor: QPainter, largura: float, altura: float, tokens: Tokens = CLARO
) -> None:
    """Fundo em gradiente, logo, nome e slogan; compartilhado pelo painel e pelo pixmap."""
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    pintor.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    gradiente = QLinearGradient(0, 0, largura * 0.5, altura)
    gradiente.setColorAt(0.0, QColor(tokens.preto))
    gradiente.setColorAt(0.45, QColor(tokens.indigo_escuro))
    gradiente.setColorAt(1.0, QColor(tokens.indigo))
    pintor.fillRect(QRectF(0, 0, largura, altura), gradiente)

    fonte_nome = QFont(tokens.fonte_familia, 14, QFont.Weight.Bold)
    fonte_nome.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
    fonte_slogan = QFont(tokens.fonte_familia, 8)
    fonte_slogan.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1)
    altura_nome = QFontMetrics(fonte_nome).height()
    altura_slogan = QFontMetrics(fonte_slogan).height()
    bloco = LADO_LOGO + _ESPACO_LOGO_NOME + altura_nome + _ESPACO_NOME_SLOGAN + altura_slogan
    topo = (altura - bloco) / 2

    logo = QSvgRenderer(str(ARQUIVO_LOGO))
    logo.render(pintor, QRectF((largura - LADO_LOGO) / 2, topo, LADO_LOGO, LADO_LOGO))

    y = topo + LADO_LOGO + _ESPACO_LOGO_NOME
    pintor.setPen(QColor(tokens.sobre_marca))
    pintor.setFont(fonte_nome)
    pintor.drawText(QRectF(0, y, largura, altura_nome), Qt.AlignmentFlag.AlignHCenter, NOME)
    y += altura_nome + _ESPACO_NOME_SLOGAN
    cor_slogan = QColor(tokens.sobre_marca)
    cor_slogan.setAlphaF(0.85)
    pintor.setPen(cor_slogan)
    pintor.setFont(fonte_slogan)
    pintor.drawText(QRectF(0, y, largura, altura_slogan), Qt.AlignmentFlag.AlignHCenter, SLOGAN)


def pixmap_marca(largura: int, altura: int, tokens: Tokens = CLARO) -> QPixmap:
    pixmap = QPixmap(largura, altura)
    pintor = QPainter(pixmap)
    try:
        desenhar_marca(pintor, largura, altura, tokens)
    finally:
        pintor.end()
    return pixmap


class PainelMarca(QFrame):
    """Coluna de marca dos diálogos de entrada. Só desenha; não tem lógica."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(LARGURA_PAINEL)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def paintEvent(self, evento: QPaintEvent) -> None:  # noqa: N802 - API do Qt
        pintor = QPainter(self)
        try:
            desenhar_marca(pintor, self.width(), self.height())
        finally:
            pintor.end()
```

`cfauto/ui/tema/__init__.py`:

```python
from cfauto.ui.tema.aplicar import aplicar_tema
from cfauto.ui.tema.marca import PainelMarca, pixmap_marca
from cfauto.ui.tema.tokens import CLARO, Tokens

__all__ = ["CLARO", "PainelMarca", "Tokens", "aplicar_tema", "pixmap_marca"]
```

- [ ] **Step 4: Implementar login e licença**

`cfauto/ui/login.py` — o corpo de `__init__` passa a ser (o resto do arquivo, `entrar` incluído, não muda; acrescente `QHBoxLayout` aos imports de `QtWidgets` e `from cfauto.ui.tema import PainelMarca`; `QVBoxLayout` continua em uso):

```python
TAMANHO_MINIMO = (580, 270)


class DialogoLogin(QDialog):
    def __init__(
        self,
        fabrica: sessionmaker[Session],
        *,
        login_fixo: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self.ator: Ator | None = None
        self.setWindowTitle("CFAUTO — Entrar" if login_fixo is None else "CFAUTO — Tela bloqueada")
        self.setMinimumSize(*TAMANHO_MINIMO)

        self.rotulo_titulo = QLabel("Entrar" if login_fixo is None else "Tela bloqueada")
        self.rotulo_titulo.setProperty("papel", "titulo")
        self.campo_login = QLineEdit()
        self.campo_senha = QLineEdit()
        self.campo_senha.setEchoMode(QLineEdit.EchoMode.Password)
        if login_fixo is not None:
            self.campo_login.setText(login_fixo)
            self.campo_login.setEnabled(False)
        self.rotulo_erro = QLabel("")
        self.rotulo_erro.setProperty("papel", "erro")

        form = QFormLayout()
        form.setVerticalSpacing(10)
        form.addRow("Login", self.campo_login)
        form.addRow("Senha", self.campo_senha)
        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Entrar")
        botoes.accepted.connect(self.entrar)
        botoes.rejected.connect(self.reject)

        coluna = QVBoxLayout()
        coluna.setContentsMargins(26, 22, 26, 20)
        coluna.addWidget(self.rotulo_titulo)
        coluna.addSpacing(8)
        coluna.addLayout(form)
        coluna.addWidget(self.rotulo_erro)
        coluna.addStretch(1)
        coluna.addWidget(botoes)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(PainelMarca())
        layout.addLayout(coluna, 1)
        (self.campo_senha if login_fixo else self.campo_login).setFocus()
```

`cfauto/ui/licenca.py` — mesmo molde (acrescente `QHBoxLayout` e `from cfauto.ui.tema import PainelMarca`; `instalar` não muda):

```python
TAMANHO_MINIMO = (640, 360)


class DialogoLicenca(QDialog):
    def __init__(
        self,
        fabrica: sessionmaker[Session],
        estado: service.EstadoLicenca,
        *,
        publica: Ed25519PublicKey | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._publica = publica
        self.estado = estado
        self.setWindowTitle("CFAUTO — Licença")
        self.setMinimumSize(*TAMANHO_MINIMO)

        self.rotulo_titulo = QLabel("Ativar licença")
        self.rotulo_titulo.setProperty("papel", "titulo")
        motivo = QLabel(estado.mensagem)
        motivo.setWordWrap(True)
        campo_maquina = QLineEdit(id_maquina())
        campo_maquina.setReadOnly(True)
        self.campo_chave = QPlainTextEdit()
        self.campo_chave.setPlaceholderText("Cole aqui a chave de licença")
        self.rotulo_erro = QLabel("")
        self.rotulo_erro.setProperty("papel", "erro")

        form = QFormLayout()
        form.setVerticalSpacing(10)
        form.addRow("ID desta máquina", campo_maquina)
        form.addRow("Chave", self.campo_chave)
        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Instalar")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Sair")
        botoes.accepted.connect(self.instalar)
        botoes.rejected.connect(self.reject)

        coluna = QVBoxLayout()
        coluna.setContentsMargins(26, 22, 26, 20)
        coluna.addWidget(self.rotulo_titulo)
        coluna.addSpacing(4)
        coluna.addWidget(motivo)
        coluna.addSpacing(8)
        coluna.addLayout(form)
        coluna.addWidget(self.rotulo_erro)
        coluna.addWidget(botoes)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(PainelMarca())
        layout.addLayout(coluna, 1)
```

- [ ] **Step 5: Rodar e ver passar**

Run: `rtk proxy uv run -m pytest tests/ui/test_tema_marca.py tests/ui/test_login.py tests/ui/test_licenca_ui.py tests/ui -q`
Expected: PASS.

- [ ] **Step 6: Conferência visual (obrigatória, não commitar as imagens)**

Script de scratch com `QT_QPA_PLATFORM=windows` e `aplicar_tema`: capture `DialogoLogin(fabrica)` (com `rotulo_erro.setText("Login ou senha inválidos.")`), `DialogoLogin(fabrica, login_fixo="dono")` e `DialogoLicenca(fabrica, EstadoLicenca(StatusLicenca.AUSENTE))`; abra com Read. Confirme: painel de marca à esquerda (logo, "CFAUTO", slogan inteiro dentro dos 210 px), título índigo, erro em vermelho, botão "Entrar"/"Instalar" índigo, nada cortado. Se o slogan não couber, reduza `letterSpacing` ou a fonte do slogan em `marca.py`.

- [ ] **Step 7: Suíte, lint e commit**

Run: `rtk proxy uv run -m pytest -q` e `uv run -m ruff check cfauto tests tools && uv run -m ruff format --check cfauto tests tools && uv run -m mypy`

```bash
git add cfauto/ui tests/ui
git commit -m "feat(ui): painel de marca no login e na licença" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JC71423ZR21u5ifTM98XxN"
```

---

### Task 6: Assistente de primeira execução com a marca na lateral

**Files:**
- Modify: `cfauto/ui/assistente.py`
- Test: `tests/ui/test_assistente.py` (novo)

**Interfaces:**
- Consumes: `pixmap_marca(largura, altura)`; `aplicar_tema`.
- Produces: `AssistentePrimeiraExecucao` com `ModernStyle`, tamanho fixo e `WatermarkPixmap`; constantes `LARGURA_JANELA=640`, `ALTURA_JANELA=440`, `LARGURA_MARCA=210`, `ALTURA_MARCA=314` em `cfauto/ui/assistente.py`. Lógica de `accept` e das três páginas não muda.

- [ ] **Step 1: Escrever o teste que falha**

`tests/ui/test_assistente.py`:

```python
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QWizard

from cfauto.ui.assistente import AssistentePrimeiraExecucao


def test_assistente_tem_tamanho_fixo_estilo_moderno_e_marca_lateral(qtbot, fabrica):
    assistente = AssistentePrimeiraExecucao(fabrica)
    qtbot.addWidget(assistente)
    assert assistente.wizardStyle() == QWizard.WizardStyle.ModernStyle
    assert assistente.minimumSize() == assistente.maximumSize() == QSize(640, 440)
    marca = assistente.pixmap(QWizard.WizardPixmap.WatermarkPixmap)
    assert not marca.isNull()
    assert marca.width() == 210


def test_assistente_continua_com_as_tres_paginas(qtbot, fabrica):
    assistente = AssistentePrimeiraExecucao(fabrica)
    qtbot.addWidget(assistente)
    assert len(assistente.pageIds()) == 3
    assert assistente.windowTitle() == "CFAUTO — Primeira execução"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `rtk proxy uv run -m pytest tests/ui/test_assistente.py -v`
Expected: FAIL (estilo não moderno, tamanho livre, sem watermark).

- [ ] **Step 3: Implementar**

Em `cfauto/ui/assistente.py` acrescente `from cfauto.ui.tema import pixmap_marca` (depois de `from cfauto.ui.comum import mostrar_erro`), as constantes abaixo antes de `class AssistentePrimeiraExecucao` e, em `__init__`, logo depois de `self.setWindowTitle("CFAUTO — Primeira execução")`:

```python
LARGURA_JANELA = 640
ALTURA_JANELA = 440
LARGURA_MARCA = 210
ALTURA_MARCA = 314  # altura útil entre o cabeçalho e a barra de botões (conferida no Windows)
```

```python
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setFixedSize(LARGURA_JANELA, ALTURA_JANELA)
        self.setPixmap(
            QWizard.WizardPixmap.WatermarkPixmap, pixmap_marca(LARGURA_MARCA, ALTURA_MARCA)
        )
```

- [ ] **Step 4: Rodar e ver passar**

Run: `rtk proxy uv run -m pytest tests/ui/test_assistente.py -v`
Expected: PASS.

- [ ] **Step 5: Conferência visual das três páginas (obrigatória, não commitar as imagens)**

Script de scratch com `QT_QPA_PLATFORM=windows` e `aplicar_tema`: construa o assistente com um BD temporário, `show()`, capture `assistente.grab()` na página 1; depois `assistente.next()` (a validação das páginas pode recusar com campos vazios: preencha `assistente._admin.nome/login/senha/confirmacao` e `assistente._licenca.chave` não é necessária para só navegar — se `next()` for recusado, use `assistente.setCurrentId(...)`/`restart()` e `assistente.button(...)` conforme precisar) e capture as páginas 2 e 3. Abra com Read. Confirme em **todas as três** páginas: marca à esquerda sem folga nem corte (ajuste `ALTURA_MARCA` ±10 até preencher a área entre o cabeçalho e a barra de botões), cabeçalho claro, botões "Voltar/Próximo/Cancelar" em português, formulário legível. Se a marca sumir em alguma página, troque para `BannerPixmap` com a faixa de gradiente (spec §6) e registre no relatório.

- [ ] **Step 6: Suíte, lint e commit**

Run: `rtk proxy uv run -m pytest -q` e `uv run -m ruff check cfauto tests tools && uv run -m ruff format --check cfauto tests tools && uv run -m mypy`

```bash
git add cfauto/ui/assistente.py tests/ui/test_assistente.py
git commit -m "feat(ui): assistente de primeira execução com a marca na lateral" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JC71423ZR21u5ifTM98XxN"
```

---

### Task 7: Ícone do app, guardas de estilo e build

**Files:**
- Modify: `tools/gerar_recursos.py`, `cfauto/ui/tema/aplicar.py`, `tests/ui/conftest.py`, `tests/ui/test_tema_aplicar.py`, `tests/ui/test_estilo_guardas.py`, `build.ps1`
- Create: `cfauto/ui/recursos/icone.ico` (gerado), `tests/tools/test_gerar_recursos.py`

**Interfaces:**
- Consumes: `aplicar_tema`, `RECURSOS`; `logo.svg`.
- Produces: `tools.gerar_recursos.montar_ico(imagens: list[tuple[int, bytes]]) -> bytes` (lista de `(lado, png)`); `aplicar.ARQUIVO_ICONE`; passo "ícone" em `aplicar_tema`; guardas anti-hex e anti-`setStyleSheet`.

- [ ] **Step 1: Escrever os testes que falham**

`tests/tools/test_gerar_recursos.py`:

```python
import importlib.util
import struct
from pathlib import Path


def _carregar():
    caminho = Path(__file__).resolve().parents[2] / "tools" / "gerar_recursos.py"
    spec = importlib.util.spec_from_file_location("gerar_recursos", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_montar_ico_tem_cabecalho_entradas_e_dados():
    modulo = _carregar()
    ico = modulo.montar_ico([(16, b"A" * 10), (256, b"B" * 20)])
    assert struct.unpack_from("<HHH", ico) == (0, 1, 2)
    largura, altura, _, _, planos, bits, tamanho, deslocamento = struct.unpack_from(
        "<BBBBHHII", ico, 6
    )
    assert (largura, altura, planos, bits, tamanho) == (16, 16, 1, 32, 10)
    assert ico[deslocamento : deslocamento + 10] == b"A" * 10
    assert struct.unpack_from("<B", ico, 6 + 16)[0] == 0  # 256 px é gravado como 0


def test_icone_do_repo_e_um_ico_com_quatro_tamanhos():
    modulo = _carregar()
    dados = (modulo.RECURSOS / "icone.ico").read_bytes()
    assert struct.unpack_from("<HHH", dados) == (0, 1, 4)
    larguras = [struct.unpack_from("<B", dados, 6 + 16 * i)[0] for i in range(4)]
    assert larguras == [16, 32, 48, 0]
```

Acrescente a `tests/ui/test_tema_aplicar.py`:

```python
def test_icone_do_app_e_definido(tema_isolado):
    aplicar_tema(tema_isolado)
    assert not tema_isolado.windowIcon().isNull()


def test_icone_ausente_nao_levanta_e_loga(tema_isolado, monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(aplicar, "ARQUIVO_ICONE", tmp_path / "nao-existe.ico")
    with caplog.at_level(logging.ERROR, logger="cfauto.ui"):
        aplicar_tema(tema_isolado)
    assert any("ícone" in r.getMessage() for r in caplog.records)
    assert tema_isolado.style().objectName().lower() == "fusion"
```

Acrescente a `tests/ui/test_estilo_guardas.py` (imports: `import re`):

```python
_COR_HEX = re.compile(r"#[0-9a-fA-F]{6}\b")
_COR_FUNCAO = re.compile(r"\brgba?\(")


def _arquivos_ui_fora_dos_tokens():
    tokens = RAIZ_UI / "tema" / "tokens.py"
    return [a for a in sorted(RAIZ_UI.rglob("*.py")) if a != tokens]


def test_nenhum_literal_de_cor_fora_dos_tokens():
    achados = []
    for arquivo in _arquivos_ui_fora_dos_tokens():
        texto = arquivo.read_text(encoding="utf-8")
        if _COR_HEX.search(texto) or _COR_FUNCAO.search(texto):
            achados.append(arquivo.relative_to(RAIZ_UI).as_posix())
    assert not achados, f"literais de cor fora de tema/tokens.py: {achados}"


def test_setstylesheet_so_no_aplicar_tema():
    permitido = RAIZ_UI / "tema" / "aplicar.py"
    achados = [
        a.relative_to(RAIZ_UI).as_posix()
        for a in _arquivos_ui_fora_dos_tokens()
        if a != permitido and "setStyleSheet(" in a.read_text(encoding="utf-8")
    ]
    assert not achados, f"setStyleSheet fora do tema: {achados}"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `rtk proxy uv run -m pytest tests/tools/test_gerar_recursos.py tests/ui/test_tema_aplicar.py tests/ui/test_estilo_guardas.py -v`
Expected: FAIL (`montar_ico` ausente, sem ícone, sem passo de ícone). As guardas já devem passar se as Tarefas 4–5 removeram todos os hex e `setStyleSheet`; se uma falhar, corrija o arquivo apontado (troque por `papel`/token) — é exatamente o que a guarda existe para pegar.

- [ ] **Step 3: Implementar o gerador do ícone**

Em `tools/gerar_recursos.py` acrescente aos imports `import struct`, `from PySide6.QtCore import QBuffer, QByteArray, QIODevice` (junto do `QPointF, Qt`) e `from PySide6.QtSvg import QSvgRenderer`; depois de `gerar_seta`:

```python
TAMANHOS_ICONE = (16, 32, 48, 256)


def montar_ico(imagens: list[tuple[int, bytes]]) -> bytes:
    """Container .ico com uma entrada PNG por tamanho (formato aceito desde o Vista)."""
    cabecalho = struct.pack("<HHH", 0, 1, len(imagens))
    deslocamento = 6 + 16 * len(imagens)
    entradas = b""
    corpo = b""
    for lado, png in imagens:
        entradas += struct.pack(
            "<BBBBHHII", lado % 256, lado % 256, 0, 0, 1, 32, len(png), deslocamento + len(corpo)
        )
        corpo += png
    return cabecalho + entradas + corpo


def _png_do_logo(renderizador: QSvgRenderer, lado: int) -> bytes:
    imagem = QImage(lado, lado, QImage.Format.Format_ARGB32)
    imagem.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(imagem)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderizador.render(pintor)
    pintor.end()
    dados = QByteArray()
    buffer = QBuffer(dados)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    imagem.save(buffer, "PNG")
    return bytes(dados.data())


def gerar_icone(destino: Path) -> None:
    renderizador = QSvgRenderer(str(RECURSOS / "logo.svg"))
    imagens = [(lado, _png_do_logo(renderizador, lado)) for lado in TAMANHOS_ICONE]
    destino.write_bytes(montar_ico(imagens))
```

e em `main()` acrescente, depois da seta:

```python
    gerar_icone(RECURSOS / "icone.ico")
    print(f"gerado: {RECURSOS / 'icone.ico'}")
```

Run: `uv run python tools/gerar_recursos.py` (cria `cfauto/ui/recursos/icone.ico`).

- [ ] **Step 4: Passo de ícone no tema**

Em `cfauto/ui/tema/aplicar.py`: importe `QIcon` (`from PySide6.QtGui import QColor, QFont, QIcon, QPalette`), defina `ARQUIVO_ICONE = RECURSOS / "icone.ico"` junto de `ARQUIVO_TRADUCAO` e a função

```python
def _instalar_icone(qapp: QApplication) -> None:
    icone = QIcon(str(ARQUIVO_ICONE))
    if icone.isNull():
        raise FileNotFoundError(f"ícone do app ausente ou ilegível: {ARQUIVO_ICONE}")
    qapp.setWindowIcon(icone)
```

e acrescente ao fim da lista `passos` de `aplicar_tema`: `("ícone", lambda: _instalar_icone(qapp)),`. O `log.exception` do laço registra a mensagem com o texto "ícone" (o teste acima procura por ele no nome do passo/mensagem: `"tema: falha ao aplicar ícone"`).

Em `tests/ui/conftest.py`, ao fim da fixture, acrescente `qapp.setWindowIcon(QIcon())` (importe `QIcon` de `PySide6.QtGui`).

- [ ] **Step 5: Build com ícone**

Em `build.ps1`, na chamada do PyInstaller, acrescente a linha `--icon "cfauto/ui/recursos/icone.ico" \`` (com a crase de continuação do PowerShell, igual às vizinhas) logo depois de `--name CFAUTO \``. (`CFAUTO.spec` está no `.gitignore`: não editar.)

Rode o build como o HANDOFF manda (o `build.ps1` ainda chama `pytest.exe`, bloqueado): `uv run -m PyInstaller --noconfirm --clean --onefile --windowed --name CFAUTO --icon "cfauto/ui/recursos/icone.ico" --add-data "cfauto/migrations;cfauto/migrations" --add-data "cfauto/ui/recursos;cfauto/ui/recursos" --collect-submodules cfauto --collect-submodules apscheduler cfauto/__main__.py` e então `$env:CFAUTO_HOME = "$env:TEMP\cfauto-build-teste"; dist\CFAUTO.exe --verificar-instalacao; $LASTEXITCODE` (esperado 0 e `cfauto.db` criado). O Smart App Control pode bloquear o `.exe` não assinado e um `.exe` aberto trava o rebuild: se o build falhar por isso, ou o `.exe` for bloqueado, **não é falha da tarefa** — registre como concern no relatório com a mensagem exata.

- [ ] **Step 6: Rodar tudo, lint e commit**

Run: `rtk proxy uv run -m pytest -q` e `uv run -m ruff check cfauto tests tools && uv run -m ruff format --check cfauto tests tools && uv run -m mypy`

```bash
git add tools/gerar_recursos.py cfauto/ui/recursos/icone.ico cfauto/ui/tema/aplicar.py tests build.ps1
git commit -m "feat(ui): ícone do app, guardas anti-hex e build com --icon" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JC71423ZR21u5ifTM98XxN"
```

---

### Task 8: Capturas de todas as telas, conferência visual e HANDOFF

**Files:**
- Create: `tools/capturar_telas.py`
- Modify: `cfauto/ui/tema/tokens.py`, `cfauto/ui/tema/qss.py` (só se a conferência achar defeito de aparência), `docs/superpowers/HANDOFF.md`

**Interfaces:**
- Consumes: tudo das tarefas 1–7; `criar_engine`, `migrar`, `criar_fabrica`, `transacao`, `criar_usuario`/`NovoUsuario` (como `tests/conftest.py`), `produtos.criar_produto`/`DadosProduto` e `criar_cliente`/`DadosCliente` (como `tests/fabricas.py`), `JanelaPrincipal`, `DialogoLogin`, `DialogoLicenca`, `AssistentePrimeiraExecucao`.
- Produces: `tools/capturar_telas.py [PASTA]` (padrão `%TEMP%/cfauto-capturas`; banco temporário descartável, nunca toca nos dados reais); relatório de conferência na resposta do implementador; HANDOFF atualizado.

- [ ] **Step 1: Escrever a ferramenta**

`tools/capturar_telas.py` (esqueleto completo; complete os trechos marcados com os nomes reais lendo `tests/fabricas.py`, `cfauto/ui/clientes/dialogo_cliente.py` e `cfauto/ui/configuracoes.py`):

```python
"""Captura as telas do CFAUTO em PNG, com o tema aplicado, no plugin real do Windows.

Usa um banco temporário descartável. Serve para conferir o visual sem abrir o app à mão.

Uso: uv run python tools/capturar_telas.py [PASTA]   (padrão: %TEMP%/cfauto-capturas)
"""

import os
import sys
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from PySide6.QtWidgets import QApplication, QTabWidget, QWidget

from cfauto.auth.service import NovoUsuario, criar_usuario
from cfauto.clientes.cadastro import criar_cliente
from cfauto.clientes.schemas import DadosCliente
from cfauto.core.db import criar_engine, criar_fabrica, transacao
from cfauto.core.migracoes import migrar
from cfauto.estoque import produtos
from cfauto.estoque.schemas import DadosProduto
from cfauto.licenca.formato import PayloadLicenca
from cfauto.licenca.service import EstadoLicenca, StatusLicenca
from cfauto.ui.assistente import AssistentePrimeiraExecucao
from cfauto.ui.janela_principal import JanelaPrincipal
from cfauto.ui.licenca import DialogoLicenca
from cfauto.ui.login import DialogoLogin
from cfauto.ui.tema import aplicar_tema

TELA_MENOR = (1366, 768)  # menor resolução que o cliente pode ter


def _salvar(app: QApplication, widget: QWidget, pasta: Path, nome: str) -> None:
    app.processEvents()
    destino = pasta / f"{nome}.png"
    widget.grab().save(str(destino))
    tamanho, dica = widget.size(), widget.minimumSizeHint()
    cabe = dica.width() <= TELA_MENOR[0] and dica.height() <= TELA_MENOR[1]
    print(f"{nome}: {tamanho.width()}x{tamanho.height()} mínimo {dica.width()}x{dica.height()}"
          f" {'ok' if cabe else 'NÃO CABE EM 1366x768'}")


def _semear(fabrica, ator) -> None:
    with transacao(fabrica) as s:
        for descricao, preco in (("Óleo 5W30", "30.00"), ("Filtro de ar", "45.90"),
                                 ("Pastilha de freio", "120.00")):
            produtos.criar_produto(
                s, ator,
                DadosProduto(descricao=descricao, categoria="Peças", preco_venda=Decimal(preco),
                             estoque_inicial=Decimal("10")),
            )
        criar_cliente(s, ator, DadosCliente(nome="Ana Souza", celular="11987654321",
                                            limite=Decimal("500.00")))
        criar_cliente(s, ator, DadosCliente(nome="Bruno Lima", celular="11912345678",
                                            limite=Decimal("300.00")))


def main() -> int:
    pasta = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.gettempdir()) / "cfauto-capturas"
    pasta.mkdir(parents=True, exist_ok=True)
    os.environ["QT_QPA_PLATFORM"] = "windows"
    app = QApplication(sys.argv)
    aplicar_tema(app)
    with tempfile.TemporaryDirectory() as tmp:
        engine = criar_engine(f"sqlite:///{Path(tmp) / 'capturas.db'}")
        migrar(engine)
        fabrica = criar_fabrica(engine)
        with transacao(fabrica) as s:
            ator = criar_usuario(
                s, None, NovoUsuario(nome="Dono", login="dono", senha="segredo1", admin=True)
            )
        _semear(fabrica, ator)
        estado = EstadoLicenca(
            StatusLicenca.VALIDA, PayloadLicenca("Loja", date(2026, 1, 1), date(2027, 1, 1)), 5
        )

        login = DialogoLogin(fabrica)
        login.rotulo_erro.setText("Login ou senha inválidos.")
        login.show()
        _salvar(app, login, pasta, "01-login")
        login.close()
        bloqueio = DialogoLogin(fabrica, login_fixo="dono")
        bloqueio.show()
        _salvar(app, bloqueio, pasta, "02-bloqueio")
        bloqueio.close()
        licenca = DialogoLicenca(fabrica, EstadoLicenca(StatusLicenca.AUSENTE))
        licenca.show()
        _salvar(app, licenca, pasta, "03-licenca")
        licenca.close()

        assistente = AssistentePrimeiraExecucao(fabrica)
        assistente.show()
        _salvar(app, assistente, pasta, "04-assistente-1")
        assistente.close()

        janela = JanelaPrincipal(fabrica, ator, estado)
        janela.resize(*TELA_MENOR)
        janela.show()
        for linha, titulo in enumerate(janela.titulos_navegacao()):
            janela.selecionar_modulo(linha)
            _salvar(app, janela, pasta, f"10-janela-{linha:02d}-{titulo.replace(' ', '').replace('/', '')}")
        janela.acao_configuracoes.trigger()
        abas = janela.configuracoes.findChild(QTabWidget) if janela.configuracoes else None
        if abas is not None:
            for indice in range(abas.count()):
                abas.setCurrentIndex(indice)
                _salvar(app, janela, pasta, f"20-configuracoes-{indice}")
        janela.close()
    engine.dispose()
    print(f"capturas em {pasta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

O esqueleto cobre login, bloqueio, licença, a primeira página do assistente, cada módulo da navegação e cada aba de Configurações. **Acrescente a ele, antes de commitar**, lendo o código das telas para achar nomes e dados:
- as páginas 2 e 3 do assistente (preencha `assistente._admin.nome/login/senha/confirmacao` e avance com `assistente.next()`; salve como `04-assistente-2` e `04-assistente-3`);
- o diálogo "Novo cliente" (`cfauto/ui/clientes/dialogo_cliente.py`), que tem que caber em 1366×768;
- o editor de produto de `cfauto/ui/estoque/produtos.py`;
- o PDV com a sessão de caixa aberta (`cfauto.caixa.sessao.abrir_sessao(s, ator, Decimal("100.00"))`) e pelo menos um item no carrinho, se isso se montar sem mexer em lógica; senão capture o PDV com o caixa aberto e o carrinho vazio.

Se algum diálogo exigir dados demais para semear, capture-o vazio e registre a limitação no relatório. O script commitado não pode conter `TODO`.

- [ ] **Step 2: Rodar e olhar cada captura**

Run: `uv run python tools/capturar_telas.py` e abra **cada PNG** com Read. Para cada tela escreva no relatório uma linha: `ok` ou o defeito. Critérios (spec §9 e Review Focus):
- faixa de topo com gradiente e texto branco; item ativo da lateral com marcador; logo embaixo; aviso de licença legível;
- tabelas com zebra, cabeçalho e seleção coerentes; abas com sublinhado índigo;
- botão padrão correto em cada diálogo (índigo = o que o Enter aciona); **nenhum rótulo invisível ou fundo escuro** (o Windows do ambiente de teste pode estar em modo escuro — o tema tem de prevalecer);
- PDV e "Novo cliente" **cabem em 1366×768** com a fonte de 10 pt (a ferramenta imprime `NÃO CABE` quando o `minimumSizeHint` estoura). Se estourar: primeiro `fonte_pt` volta a 9 em `tokens.py` (token único), refaça as capturas e registre; não mexa em layout de tela.

- [ ] **Step 3: Corrigir só defeitos de aparência**

Corrija em `tokens.py`/`qss.py` (e `papel`/`objectName` onde faltar) o que as capturas mostraram; rode a suíte de UI. **Não mude layout, lógica, ordem de itens nem permissões** — se uma tela precisar disso, descreva no relatório como "adiado para a Fase 2/decisão do usuário". Refaça as capturas afetadas e confirme.

- [ ] **Step 4: Atualizar o HANDOFF**

Em `docs/superpowers/HANDOFF.md`:
- "Onde estamos": acrescente o bullet "**Estilo base — Fase 1: concluída** na branch `feat/estilo-base` (pacote `cfauto/ui/tema/`, faixa de topo, painel de marca no login/licença/assistente, tradução pt_BR, ícone). Falta o roteiro de QA manual da spec §9 (modo claro e escuro do Windows) pelo usuário; Fase 2 (ícones Lucide, chips de estoque, `papel=perigo`, polimento do PDV) logo depois do 4B."
- Seção "Decisões recentes": troque o bullet "**Estilo base adiado para depois dos módulos principais**…" por um que diga que o estilo foi puxado em 09/10 e entregue na Fase 1, apontando spec e plano; telas novas (4B em diante) usam widgets Qt comuns, `papel` e nada de `setStyleSheet`/hex inline (as guardas em `tests/ui/test_estilo_guardas.py` falham se violar).
- "Armadilhas do ambiente": corrija o comando de build (acrescente `--icon "cfauto/ui/recursos/icone.ico"` e `--add-data "cfauto/ui/recursos;cfauto/ui/recursos"`), e acrescente "`tools/capturar_telas.py` gera PNGs de todas as telas no plugin `windows`; `widget.grab().save()` + Read permite conferir o visual sem abrir o app. `*.spec` é ignorado pelo git."
- Tabela "Documentos": linhas para a spec `2026-10-09-estilo-base-design.md` e este plano.

- [ ] **Step 5: Suíte final, lint e commit**

Run: `rtk proxy uv run -m pytest -q` e `uv run -m ruff check cfauto tests tools && uv run -m ruff format --check cfauto tests tools && uv run -m mypy`

```bash
git add tools/capturar_telas.py cfauto/ui/tema docs/superpowers/HANDOFF.md
git commit -m "feat(ui): captura de telas, conferência visual e HANDOFF da Fase 1" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01JC71423ZR21u5ifTM98XxN"
```

---

## Auto-revisão do plano

**Cobertura da spec:** §2 tokens → T1 · §3.1 `aplicar_tema` → T3 (+ícone T7) · §3.2 papéis → T2 (+`titulo`, nota 2) · §3.3 QSS → T2 · §4 janela → T4 · §5 `PainelMarca`/login/licença → T5 · §6 assistente → T6 · §7 ícone/build → T7 · §8 testes (contraste T1, QSS/parse T2, `aplicar_tema` e aparência no subprocesso T3, guarda anti-hex T7, telas T4–T6) · §9 QA → T8 (capturas automáticas; o roteiro manual em modo escuro fica com o usuário e está no HANDOFF) · §10 ordem → T1–T8 · §11 riscos → T2 (parse, seta), T6 (altura do watermark), T8 (fonte 10 pt).

**Placeholders:** nenhum no código dos passos. A Tarefa 8 entrega um esqueleto funcional de `tools/capturar_telas.py` e lista, como instrução, as capturas extras (assistente 2–3, "Novo cliente", editor de produto, PDV) que o implementador completa lendo o código das telas.

**Consistência de tipos/nomes:** `Tokens`/`CLARO` (T1) · `gerar_qss(tokens, *, seta_baixo)`/`ARQUIVO_SETA_BAIXO` (T2) · `aplicar_tema`, `aplicar.RECURSOS`, `aplicar._pastas_traducao`, `aplicar._tradutor`, `aplicar.ARQUIVO_ICONE` (T3/T7) · `desenhar_marca`, `pixmap_marca(largura, altura)`, `PainelMarca` (T5, usado em T6) · `rotulo_titulo` (T5) · `tema_isolado` (T2, estendida em T3/T7) · `montar_ico`, `gerar_icone`, `RECURSOS` em `tools/gerar_recursos.py` (T2/T7). Papéis usados nas telas (`titulo`, `erro`, `aviso`) existem no QSS (T2).
