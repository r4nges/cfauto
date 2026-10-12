"""Captura as telas do CFAUTO em PNG, com o tema aplicado, no plugin real do Windows.

Usa um banco temporário descartável: nunca toca nos dados reais. Serve para conferir o visual
sem abrir o app à mão (abra os PNGs numa ferramenta de imagem). As capturas saem na escala da
tela (~1,25x o tamanho lógico no Windows com 125%).

Uso: uv run python tools/capturar_telas.py [PASTA]   (padrão: %TEMP%/cfauto-capturas)
"""

import os
import sys
import tempfile
import unicodedata
from datetime import date
from decimal import Decimal
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "windows"

from PySide6.QtWidgets import QApplication, QMessageBox, QTabWidget, QWidget  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from cfauto.auth.service import NovoUsuario, criar_usuario  # noqa: E402
from cfauto.caixa.models import FormaPagamento  # noqa: E402
from cfauto.caixa.schemas import ItemVenda, NovaVenda  # noqa: E402
from cfauto.caixa.sessao import abrir_sessao, fechar_sessao  # noqa: E402
from cfauto.caixa.venda import registrar_venda  # noqa: E402
from cfauto.clientes.cadastro import buscar_clientes, criar_cliente, obter_cliente  # noqa: E402
from cfauto.clientes.models import MotivoLancamento, TipoLancamento  # noqa: E402
from cfauto.clientes.razao import lancar_manual  # noqa: E402
from cfauto.clientes.schemas import DadosCliente, DadosDependente, ResumoCliente  # noqa: E402
from cfauto.core.db import criar_engine, criar_fabrica, transacao  # noqa: E402
from cfauto.core.migracoes import migrar  # noqa: E402
from cfauto.core.permissoes import Ator  # noqa: E402
from cfauto.estoque import produtos, servicos  # noqa: E402
from cfauto.estoque.entrada import preparar_entrada  # noqa: E402
from cfauto.estoque.models import Produto  # noqa: E402
from cfauto.estoque.schemas import DadosMaterial, DadosProduto, DadosServico  # noqa: E402
from cfauto.licenca.formato import PayloadLicenca  # noqa: E402
from cfauto.licenca.service import EstadoLicenca, StatusLicenca  # noqa: E402
from cfauto.ui.assistente import AssistentePrimeiraExecucao  # noqa: E402
from cfauto.ui.caixa.abrir import DialogoAbrirCaixa  # noqa: E402
from cfauto.ui.caixa.autorizacao import DialogoAutorizacao  # noqa: E402
from cfauto.ui.caixa.fechamento import DialogoFechamento  # noqa: E402
from cfauto.ui.caixa.recebimento import DialogoRecebimento  # noqa: E402
from cfauto.ui.caixa.vendas_sessao import DialogoVendasSessao  # noqa: E402
from cfauto.ui.clientes.dialogo_cliente import DialogoCliente  # noqa: E402
from cfauto.ui.clientes.extrato import DialogoExtrato  # noqa: E402
from cfauto.ui.clientes.lancamento import DialogoLancamento  # noqa: E402
from cfauto.ui.estoque.entradas import DialogoConferencia, DialogoEscolherProduto  # noqa: E402
from cfauto.ui.estoque.produtos import DialogoAjusteEstoque, DialogoProduto  # noqa: E402
from cfauto.ui.estoque.servicos import DialogoServico  # noqa: E402
from cfauto.ui.janela_principal import JanelaPrincipal  # noqa: E402
from cfauto.ui.licenca import DialogoLicenca  # noqa: E402
from cfauto.ui.login import DialogoLogin  # noqa: E402
from cfauto.ui.tema import aplicar_tema  # noqa: E402

TELA_MENOR = (1366, 768)  # menor resolução que o cliente pode ter
RAIZ = Path(__file__).resolve().parent.parent
EAN_ADITIVO = "7891000100103"


def _slug(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return "".join(c for c in sem_acento.title() if c.isalnum())


def _salvar(app: QApplication, widget: QWidget, pasta: Path, nome: str) -> None:
    """Grava o PNG do widget e imprime o tamanho e se o mínimo cabe em 1366x768."""
    app.processEvents()
    widget.grab().save(str(pasta / f"{nome}.png"))
    tamanho, dica = widget.size(), widget.minimumSizeHint()
    cabe = dica.width() <= TELA_MENOR[0] and dica.height() <= TELA_MENOR[1]
    print(
        f"{nome}: {tamanho.width()}x{tamanho.height()} mínimo {dica.width()}x{dica.height()}"
        f" {'ok' if cabe else 'NÃO CABE EM 1366x768'}"
    )


def _mostrar(app: QApplication, widget: QWidget, pasta: Path, nome: str) -> None:
    """Mostra sem modal, captura e fecha."""
    widget.show()
    _salvar(app, widget, pasta, nome)
    widget.close()


def _semear(fabrica: sessionmaker[Session], ator: Ator) -> dict[str, int]:
    """Catálogo, clientes (um deles devedor) e uma sessão de caixa já fechada com vendas."""
    with transacao(fabrica) as s:
        oleo = produtos.criar_produto(
            s,
            ator,
            DadosProduto(
                descricao="Óleo 5W30",
                categoria="Lubrificantes",
                preco_entrada=Decimal("18.00"),
                preco_venda=Decimal("30.00"),
                estoque_inicial=Decimal("10"),
            ),
        ).id
        filtro = produtos.criar_produto(
            s,
            ator,
            DadosProduto(
                descricao="Filtro de ar",
                categoria="Filtros",
                preco_entrada=Decimal("25.00"),
                preco_venda=Decimal("45.90"),
                estoque_inicial=Decimal("8"),
            ),
        ).id
        produtos.criar_produto(
            s,
            ator,
            DadosProduto(
                descricao="Pastilha de freio",
                categoria="Freios",
                preco_entrada=Decimal("70.00"),
                preco_venda=Decimal("120.00"),
                estoque_inicial=Decimal("2"),
                estoque_minimo=Decimal("5"),
            ),
        )
        produtos.criar_produto(
            s,
            ator,
            DadosProduto(
                descricao="Aditivo de radiador",
                ean=EAN_ADITIVO,
                categoria="Lubrificantes",
                preco_venda=Decimal("22.50"),
                estoque_inicial=Decimal("6"),
            ),
        )
        descontinuado = produtos.criar_produto(
            s,
            ator,
            DadosProduto(
                descricao="Correia dentada", categoria="Motor", estoque_inicial=Decimal(1)
            ),
        ).id
        produtos.desativar_produto(s, ator, descontinuado)
        servicos.criar_servico(
            s,
            ator,
            DadosServico(
                nome="Troca de óleo",
                materiais=(DadosMaterial(descricao="Mão de obra", custo_unit=Decimal("20.00")),),
            ),
        )
        ana = criar_cliente(
            s,
            ator,
            DadosCliente(
                nome="Ana Souza",
                celular="11987654321",
                cpf="52998224725",
                limite=Decimal("500.00"),
                dependentes=(DadosDependente(nome="Pedro Souza", parentesco="Filho"),),
            ),
        )
        criar_cliente(
            s,
            ator,
            DadosCliente(nome="Bruno Lima", celular="11912345678", limite=Decimal("300.00")),
        )
        lancar_manual(
            s, ator, ana, TipoLancamento.DEBITO, Decimal("150.00"), MotivoLancamento.COMPRA_ANOTADA
        )
        abrir_sessao(s, ator, Decimal("100.00"))
        registrar_venda(
            s,
            ator,
            NovaVenda(
                itens=(
                    ItemVenda(Decimal(2), produto_id=oleo),
                    ItemVenda(Decimal(1), produto_id=filtro),
                ),
                forma=FormaPagamento.PIX,
            ),
        )
        registrar_venda(
            s,
            ator,
            NovaVenda(
                itens=(ItemVenda(Decimal(1), produto_id=oleo),),
                forma=FormaPagamento.CREDIARIO,
                cliente_id=ana,
            ),
        )
        fechar_sessao(s, ator, Decimal("100.00"))
    return {"ana": ana, "oleo": oleo, "filtro": filtro}


def _abas(pagina: QWidget | None) -> QTabWidget | None:
    if isinstance(pagina, QTabWidget):
        return pagina
    return None if pagina is None else pagina.findChild(QTabWidget)


def _capturar_abas(app: QApplication, janela: JanelaPrincipal, pasta: Path, prefixo: str) -> None:
    """Uma captura da janela por aba da página atual (se ela tiver abas)."""
    abas = _abas(janela.pagina_atual())
    if abas is None:
        return
    for indice in range(abas.count()):
        abas.setCurrentIndex(indice)
        _salvar(app, janela, pasta, f"{prefixo}-aba{indice}-{_slug(abas.tabText(indice))}")


def _capturar_entrada(
    app: QApplication, janela: JanelaPrincipal, pasta: Path, titulo: str, nome: str
) -> None:
    """Abre a página com esse título e captura a janela."""
    janela.selecionar_modulo(janela.titulos_navegacao().index(titulo))
    _salvar(app, janela, pasta, nome)


def _autenticacao(app: QApplication, fabrica: sessionmaker[Session], pasta: Path) -> None:
    login = DialogoLogin(fabrica)
    login.rotulo_erro.setText("Login ou senha inválidos.")
    _mostrar(app, login, pasta, "01-login")
    _mostrar(app, DialogoLogin(fabrica, login_fixo="dono"), pasta, "02-bloqueio")
    licenca = DialogoLicenca(fabrica, EstadoLicenca(StatusLicenca.AUSENTE))
    licenca.rotulo_erro.setText("Chave de licença inválida.")
    _mostrar(app, licenca, pasta, "03-licenca")


def _assistente(app: QApplication, fabrica: sessionmaker[Session], pasta: Path) -> None:
    """As três páginas do assistente."""
    assistente = AssistentePrimeiraExecucao(fabrica)
    assistente.show()
    _salvar(app, assistente, pasta, "04-assistente-1")
    admin = assistente._admin  # noqa: SLF001 - ferramenta de desenvolvimento
    admin.nome.setText("Dono da Loja")
    admin.login.setText("dono")
    admin.senha.setText("segredo1")
    admin.confirmacao.setText("segredo1")
    assistente.next()
    _salvar(app, assistente, pasta, "04-assistente-2")
    assistente.close()
    # A página 3 só se alcança com uma chave de licença válida; aqui o assistente já começa nela.
    final = AssistentePrimeiraExecucao(fabrica)
    final.setStartId(final.pageIds()[2])
    final._empresa.nome.setText("Auto Peças Boa Vista")  # noqa: SLF001
    _mostrar(app, final, pasta, "04-assistente-3")


def _janela(
    app: QApplication, fabrica: sessionmaker[Session], ator: Ator, pasta: Path
) -> JanelaPrincipal:
    estado = EstadoLicenca(
        StatusLicenca.VALIDA, PayloadLicenca("Loja", date(2026, 1, 1), date(2027, 1, 1)), 5
    )
    janela = JanelaPrincipal(fabrica, ator, estado)
    janela.resize(*TELA_MENOR)
    janela.show()
    for linha, titulo in enumerate(janela.titulos_navegacao()):
        janela.selecionar_modulo(linha)
        prefixo = f"10-janela-{linha:02d}-{_slug(titulo)}"
        _salvar(app, janela, pasta, prefixo)
        _capturar_abas(app, janela, pasta, prefixo)
    return janela


def _pdv(
    app: QApplication,
    fabrica: sessionmaker[Session],
    ator: Ator,
    janela: JanelaPrincipal,
    ids: dict[str, int],
    pasta: Path,
) -> None:
    """Abre um caixa novo e monta uma venda em andamento."""
    with transacao(fabrica) as s:
        abrir_sessao(s, ator, Decimal("100.00"))
    janela.selecionar_modulo(1)
    janela.selecionar_modulo(0)
    pagina = janela.pagina_atual()
    pdv = pagina.pdv  # type: ignore[union-attr]
    _salvar(app, janela, pasta, "11-pdv-caixa-aberto-vazio")
    pdv.busca.setText("filtro")
    pdv.buscar()
    pdv.adicionar_produto(ids["oleo"])
    pdv.adicionar_produto(ids["oleo"])
    pdv.adicionar_produto(ids["filtro"])
    pdv.definir_cliente(ids["ana"])
    pdv.busca.setText("o")
    pdv.buscar()
    pdv.desconto.setText("5,00")
    pdv.carrinho.selectRow(0)
    _salvar(app, janela, pasta, "11-pdv-venda-em-andamento")


def _estados_de_tabela(app: QApplication, janela: JanelaPrincipal, pasta: Path) -> None:
    """Linha de produto inativo e linhas selecionadas (as cores que mais variam por tela)."""
    janela.selecionar_modulo(janela.titulos_navegacao().index("Estoque"))
    estoque = janela.pagina_atual()
    estoque.setCurrentIndex(0)  # type: ignore[union-attr]
    produtos_tela = estoque.produtos  # type: ignore[union-attr]
    produtos_tela.mostrar_inativos.setChecked(True)
    produtos_tela.selecionar(1)
    _salvar(app, janela, pasta, "12-estoque-inativos-e-selecao")
    produtos_tela.mostrar_inativos.setChecked(False)
    janela.selecionar_modulo(janela.titulos_navegacao().index("Clientes"))
    janela.pagina_atual().selecionar(0)  # type: ignore[union-attr]
    _salvar(app, janela, pasta, "12-clientes-selecao")


def _configuracoes(app: QApplication, janela: JanelaPrincipal, pasta: Path) -> None:
    janela.acao_configuracoes.trigger()
    abas = janela.configuracoes
    if abas is None:
        return
    for indice in range(abas.count()):
        abas.setCurrentIndex(indice)
        nome = f"20-configuracoes-{indice}-{_slug(abas.tabText(indice))}"
        _salvar(app, janela, pasta, nome)


def _dialogos_cliente(
    app: QApplication,
    fabrica: sessionmaker[Session],
    ator: Ator,
    ids: dict[str, int],
    pasta: Path,
) -> None:
    with transacao(fabrica) as s:
        ficha = obter_cliente(s, ator, ids["ana"])
    _mostrar(app, DialogoCliente(fabrica, ator), pasta, "30-dialogo-cliente-novo")
    _mostrar(app, DialogoCliente(fabrica, ator, ficha), pasta, "30-dialogo-cliente-editar")
    resumo_ana = _resumo_cliente(fabrica, ator, ids["ana"])
    _mostrar(app, DialogoLancamento(fabrica, ator, resumo_ana), pasta, "31-dialogo-lancamento")
    extrato = DialogoExtrato(fabrica, ator, ids["ana"])
    _mostrar(app, extrato, pasta, "32-dialogo-extrato")


def _resumo_cliente(fabrica: sessionmaker[Session], ator: Ator, cliente_id: int) -> ResumoCliente:
    with transacao(fabrica) as s:
        return next(c for c in buscar_clientes(s, ator, "") if c.id == cliente_id)


def _dialogos_estoque(
    app: QApplication, fabrica: sessionmaker[Session], ator: Ator, pasta: Path
) -> None:
    with transacao(fabrica) as s:
        todos = produtos.buscar_produtos(s, ator, "")
        servico = servicos.listar_servicos(s, ator)[0]
    produto: Produto = todos[0]
    _mostrar(app, DialogoProduto(fabrica, ator), pasta, "40-dialogo-produto-novo")
    _mostrar(app, DialogoProduto(fabrica, ator, produto), pasta, "40-dialogo-produto-editar")
    _mostrar(app, DialogoAjusteEstoque(fabrica, ator, produto), pasta, "41-dialogo-ajuste-estoque")
    _mostrar(app, DialogoServico(fabrica, ator, servico), pasta, "42-dialogo-servico-editar")
    _mostrar(app, DialogoEscolherProduto(fabrica, ator), pasta, "43-dialogo-escolher-produto")


def _conferencia_nfe(
    app: QApplication, fabrica: sessionmaker[Session], ator: Ator, pasta: Path
) -> None:
    """Conferência de uma NF-e sintética: um item casa pelo EAN e outro vira produto novo."""
    sys.path.insert(0, str(RAIZ))
    from tests.estoque.xml_nfe import ItemXml, montar_nfe

    xml = montar_nfe(
        7,
        [
            ItemXml("A-100", "ADITIVO RADIADOR 1L", "10", "150.00", ean=EAN_ADITIVO),
            ItemXml("B-200", "PARAFUSO SEXTAVADO", "2", "30.00", unidade="CX"),
            ItemXml("C-300", "JUNTA DO CABECOTE", "1", "89.90"),
        ],
    )
    with transacao(fabrica) as s:
        conferencia = preparar_entrada(s, ator, xml)
    dialogo = DialogoConferencia(fabrica, ator, xml, conferencia)
    dialogo.show()
    dialogo.avisos.setText("Destinatário da nota difere do CNPJ cadastrado.")
    dialogo.avisos.setVisible(True)
    dialogo.tabela.selectRow(0)
    _salvar(app, dialogo, pasta, "44-dialogo-conferencia-nfe")
    dialogo.close()


def _dialogos_caixa(
    app: QApplication,
    fabrica: sessionmaker[Session],
    ator: Ator,
    ids: dict[str, int],
    pasta: Path,
) -> None:
    """O caixa está aberto aqui (aberto por `_pdv`); o de abertura é capturado antes."""
    with transacao(fabrica) as s:
        registrar_venda(
            s,
            ator,
            NovaVenda(
                itens=(ItemVenda(Decimal(1), produto_id=ids["filtro"]),),
                forma=FormaPagamento.DINHEIRO,
            ),
        )
    _mostrar(app, DialogoRecebimento(fabrica, ator), pasta, "50-dialogo-recebimento")
    _mostrar(app, DialogoVendasSessao(fabrica, ator), pasta, "51-dialogo-vendas-da-sessao")
    _mostrar(app, DialogoFechamento(fabrica, ator), pasta, "52-dialogo-fechamento")
    texto = "Estoque insuficiente de Óleo 5W30.\nPeça a autorização de um administrador."
    _mostrar(app, DialogoAutorizacao(fabrica, texto), pasta, "53-dialogo-autorizacao")


def _caixas_de_mensagem(app: QApplication, pasta: Path) -> None:
    aviso = QMessageBox(
        QMessageBox.Icon.Warning, "CFAUTO", "Informe nome e login.", QMessageBox.StandardButton.Ok
    )
    _mostrar(app, aviso, pasta, "60-mensagem-aviso")
    botoes = QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    pergunta = QMessageBox(
        QMessageBox.Icon.Question,
        "CFAUTO",
        "Estornar esta nota? As quantidades saem do estoque.",
        botoes,
    )
    _mostrar(app, pergunta, pasta, "61-mensagem-pergunta")


def _capturar_tudo(
    app: QApplication,
    fabrica: sessionmaker[Session],
    ator: Ator,
    ids: dict[str, int],
    pasta: Path,
) -> None:
    _autenticacao(app, fabrica, pasta)
    _assistente(app, fabrica, pasta)
    _mostrar(app, DialogoAbrirCaixa(fabrica, ator), pasta, "50-dialogo-abrir-caixa")
    janela = _janela(app, fabrica, ator, pasta)
    _pdv(app, fabrica, ator, janela, ids, pasta)
    _estados_de_tabela(app, janela, pasta)
    _configuracoes(app, janela, pasta)
    _dialogos_cliente(app, fabrica, ator, ids, pasta)
    _dialogos_estoque(app, fabrica, ator, pasta)
    _conferencia_nfe(app, fabrica, ator, pasta)
    _dialogos_caixa(app, fabrica, ator, ids, pasta)
    _caixas_de_mensagem(app, pasta)
    janela.fechar_sessao()


def main() -> int:
    padrao = Path(tempfile.gettempdir()) / "cfauto-capturas"
    pasta = Path(sys.argv[1]) if len(sys.argv) > 1 else padrao
    pasta.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    app.setApplicationName("CFAUTO")
    print(f"esquema de cor do Windows: {app.styleHints().colorScheme().name}")
    aplicar_tema(app)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        engine = criar_engine(f"sqlite:///{Path(tmp) / 'capturas.db'}")
        try:
            migrar(engine)
            fabrica = criar_fabrica(engine)
            with transacao(fabrica) as s:
                ator = criar_usuario(
                    s, None, NovoUsuario(nome="Dono", login="dono", senha="segredo1", admin=True)
                )
            _capturar_tudo(app, fabrica, ator, _semear(fabrica, ator), pasta)
        finally:
            engine.dispose()
    print(f"capturas em {pasta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
