"""PDV: busca (leitor de código de barras), carrinho, cliente, prévia ao vivo e finalização."""

from dataclasses import dataclass
from decimal import Decimal

from PySide6.QtCore import QModelIndex, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session, sessionmaker

from cfauto.caixa.calculo import (
    calcular_pagamento,
    preco_de_venda,
    subtotal_item,
    troco,
    valor_desconto,
)
from cfauto.caixa.models import TITULOS_FORMA, FormaPagamento
from cfauto.caixa.schemas import (
    Desconto,
    ItemVenda,
    NovaVenda,
    Pagamento,
    TaxaForma,
    TipoDesconto,
)
from cfauto.caixa.sessao import sessao_aberta
from cfauto.caixa.taxas import listar_taxas
from cfauto.caixa.venda import registrar_venda, vendas_da_sessao
from cfauto.clientes.cadastro import obter_cliente
from cfauto.clientes.schemas import FichaCliente
from cfauto.clientes.validacao import formatar_saldo
from cfauto.core import clock
from cfauto.core.db import transacao
from cfauto.core.errors import (
    ErroDominio,
    EstoqueInsuficiente,
    LimiteExcedido,
    SessaoFechada,
    ValorInvalido,
)
from cfauto.core.money import arredondar_qtd, formatar_brl, formatar_qtd
from cfauto.core.permissoes import Ator
from cfauto.core.texto import normalizar_texto
from cfauto.estoque.models import Produto, Servico
from cfauto.estoque.produtos import buscar_produtos
from cfauto.estoque.servicos import listar_servicos
from cfauto.ui.caixa.autorizacao import Autorizar, Perguntar, pedir_autorizacao, perguntar_padrao
from cfauto.ui.caixa.fechamento import DialogoFechamento
from cfauto.ui.caixa.formatos import BuscaCliente
from cfauto.ui.caixa.recebimento import DialogoRecebimento
from cfauto.ui.caixa.vendas_sessao import DialogoVendasSessao
from cfauto.ui.comum import (
    criar_tabela,
    ler_decimal,
    ler_decimal_opcional,
    mostrar_erro,
    preencher_tabela,
)

_COLUNAS_RESULTADOS = ["Tipo", "Código", "Descrição", "Preço", "Estoque"]
_COLUNAS_CARRINHO = ["Descrição", "Qtd", "Unit.", "Subtotal"]
_COLUNA_QTD = 1
NENHUM_RESULTADO = "Nenhum produto ou serviço encontrado."
SEM_CLIENTE = "Sem cliente (consumidor final)."


@dataclass(frozen=True)
class _Resultado:
    produto: bool
    id: int
    codigo: str
    ean: str | None
    descricao: str
    preco: Decimal
    estoque: Decimal | None  # None = serviço


@dataclass
class _ItemCarrinho:
    produto: bool
    id: int
    descricao: str
    preco_unit: Decimal
    qtd: Decimal = Decimal(1)


@dataclass(frozen=True)
class _Previa:
    subtotal: Decimal
    desconto: Decimal
    bruto: Decimal
    pagamento: Pagamento


def _de_produto(p: Produto) -> _Resultado:
    preco = preco_de_venda(p.preco_venda, p.preco_promocional)
    return _Resultado(True, p.id, p.codigo, p.ean, p.descricao, preco, p.estoque)


def _de_servico(sv: Servico) -> _Resultado:
    return _Resultado(False, sv.id, sv.codigo, None, sv.nome, sv.preco, None)


def _codigo_exato(termo: str, codigo: str, ean: str | None) -> bool:
    chave = termo.strip().upper()
    if chave == codigo.upper() or (ean is not None and chave == ean):
        return True
    return chave.isdigit() and codigo.isdigit() and int(chave) == int(codigo)


def _texto_cliente(c: FichaCliente) -> str:
    disponivel = "Sem limite" if c.disponivel is None else formatar_brl(c.disponivel)
    linhas = [
        f"{c.codigo} — {c.dados.nome} · Saldo: {formatar_saldo(c.saldo_devedor)}"
        f" · Disponível: {disponivel}"
    ]
    if c.dados.observacoes:
        linhas.append(f"⚠ Observações: {c.dados.observacoes}")
    if c.dados.somente_titular:
        linhas.append("⚠ Somente titular")
    elif c.dados.dependentes:
        nomes = ", ".join(
            f"{d.nome} ({d.parentesco})" if d.parentesco else d.nome for d in c.dados.dependentes
        )
        linhas.append(f"Dependentes: {nomes}")
    return "\n".join(linhas)


class TelaPdv(QWidget):
    sessao_encerrada = Signal()

    def __init__(
        self,
        fabrica: sessionmaker[Session],
        ator: Ator,
        parent: QWidget | None = None,
        *,
        perguntar: Perguntar | None = None,
        autorizar: Autorizar | None = None,
    ) -> None:
        super().__init__(parent)
        self._fabrica = fabrica
        self._ator = ator
        self._perguntar: Perguntar = perguntar or (lambda texto: perguntar_padrao(self, texto))
        self._autorizar: Autorizar = autorizar or self._autorizar_padrao
        self._taxas: dict[FormaPagamento, TaxaForma] = {}
        self._resultados: list[_Resultado] = []
        self._itens: list[_ItemCarrinho] = []
        self._cliente: FichaCliente | None = None
        self._preenchendo = False

        self.cabecalho = QLabel()
        fonte = self.cabecalho.font()
        fonte.setBold(True)
        self.cabecalho.setFont(fonte)
        self.botao_receber = QPushButton("Receber crediário")
        self.botao_receber.clicked.connect(self._receber)
        self.botao_vendas = QPushButton("Vendas da sessão")
        self.botao_vendas.clicked.connect(self._abrir_vendas)
        self.botao_fechar = QPushButton("Fechar caixa")
        self.botao_fechar.clicked.connect(self._fechar_caixa)
        topo = QHBoxLayout()
        topo.addWidget(self.cabecalho)
        topo.addStretch()
        for botao in (self.botao_receber, self.botao_vendas, self.botao_fechar):
            topo.addWidget(botao)

        self.busca = QLineEdit()
        self.busca.setPlaceholderText("EAN, código ou nome — Enter para buscar")
        self.busca.returnPressed.connect(self.buscar)
        self.resultados = criar_tabela(_COLUNAS_RESULTADOS)
        self.resultados.doubleClicked.connect(self._adicionar_resultado)

        self.carrinho = criar_tabela(_COLUNAS_CARRINHO)
        # Sem AnyKeyPressed: com a célula do carrinho em foco, o código lido pelo leitor
        # (ex.: "15") viraria a quantidade da linha em vez de buscar o produto.
        self.carrinho.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.carrinho.itemChanged.connect(self._ao_editar_celula)
        remover = QPushButton("Remover item")
        remover.clicked.connect(lambda: self.remover_item(self.carrinho.currentRow()))

        self._busca_cliente = BuscaCliente(
            fabrica,
            ator,
            "Cliente: nome, código, CPF ou celular — Enter",
            ao_escolher=self.definir_cliente,
            ao_avisar=lambda aviso: self.mensagem.setText(aviso),
        )
        self.busca_cliente = self._busca_cliente.campo
        sem_cliente = QPushButton("Sem cliente")
        sem_cliente.clicked.connect(lambda: self.definir_cliente(None))
        self.painel_cliente = QLabel(SEM_CLIENTE)
        self.painel_cliente.setTextFormat(Qt.TextFormat.PlainText)
        self.painel_cliente.setWordWrap(True)

        self.tipo_desconto = QComboBox()
        self.tipo_desconto.addItem("R$", TipoDesconto.REAIS)
        self.tipo_desconto.addItem("%", TipoDesconto.PERCENTUAL)
        self.desconto = QLineEdit()
        self.desconto.setPlaceholderText("0,00")
        self.forma = QComboBox()
        for forma in FormaPagamento:
            self.forma.addItem(TITULOS_FORMA[forma], forma)
        self.recebido = QLineEdit()
        self.troco = QLabel()
        self.totais = QLabel()
        self.totais.setTextFormat(Qt.TextFormat.PlainText)
        self.mensagem = QLabel()
        limpar = QPushButton("Limpar")
        limpar.clicked.connect(self.limpar)
        self.botao_finalizar = QPushButton("Finalizar")
        self.botao_finalizar.clicked.connect(self.finalizar)

        self.desconto.textChanged.connect(self._atualizar_totais)
        self.recebido.textChanged.connect(self._atualizar_totais)
        self.tipo_desconto.currentIndexChanged.connect(self._atualizar_totais)
        self.forma.currentIndexChanged.connect(self._ao_trocar_forma)

        linha_cliente = QHBoxLayout()
        linha_cliente.addWidget(self.busca_cliente, 1)
        linha_cliente.addWidget(self._busca_cliente.opcoes)
        linha_cliente.addWidget(sem_cliente)
        linha_desconto = QHBoxLayout()
        linha_desconto.addWidget(self.desconto)
        linha_desconto.addWidget(self.tipo_desconto)
        linha_recebido = QHBoxLayout()
        linha_recebido.addWidget(self.recebido)
        linha_recebido.addWidget(self.troco)
        pagamento = QFormLayout()
        pagamento.addRow("Desconto", linha_desconto)
        pagamento.addRow("Forma", self.forma)
        pagamento.addRow("Recebido", linha_recebido)
        rodape = QHBoxLayout()
        rodape.addWidget(self.mensagem, 1)
        rodape.addWidget(limpar)
        rodape.addWidget(self.botao_finalizar)

        layout = QVBoxLayout(self)
        layout.addLayout(topo)
        layout.addWidget(self.busca)
        layout.addWidget(self.resultados)
        layout.addWidget(QLabel("Carrinho"))
        layout.addWidget(self.carrinho)
        layout.addWidget(remover, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addLayout(linha_cliente)
        layout.addWidget(self.painel_cliente)
        layout.addLayout(pagamento)
        layout.addWidget(self.totais)
        layout.addLayout(rodape)

        self.recarregar()
        self._preencher_carrinho()
        self._ao_trocar_forma()

    # --- sessão e taxas -------------------------------------------------------------

    def recarregar(self) -> None:
        """Cabeçalho da sessão, taxas e preços do carrinho; sem sessão aberta, avisa com
        `sessao_encerrada`."""
        with transacao(self._fabrica) as s:
            painel = sessao_aberta(s, self._ator)
            taxas = listar_taxas(s, self._ator)
        self._taxas = {taxa.forma: taxa for taxa in taxas}
        if painel is None:
            self.cabecalho.setText("Caixa fechado")
            self.sessao_encerrada.emit()
            return
        self.cabecalho.setText(
            f"{painel.protocolo} · fundo {formatar_brl(painel.fundo_troco)}"
            f" · gaveta {formatar_brl(painel.gaveta)}"
        )
        self._atualizar_precos()
        self._atualizar_totais()

    def _atualizar_precos(self) -> None:
        """Reprecifica o carrinho pelo cadastro: `registrar_venda` grava o preço do banco, e a
        prévia tem de mostrar o mesmo. Avisa o que mudou e o que saiu de venda (sem modal)."""
        if not self._itens:
            return
        with transacao(self._fabrica) as s:
            vigentes = {(r.produto, r.id): r for r in self._cadastro_ativo(s)}
        avisos: list[str] = []
        for item in self._itens:
            atual = vigentes.get((item.produto, item.id))
            if atual is None:
                avisos.append(f"{item.descricao} não está mais disponível para venda.")
            elif atual.preco != item.preco_unit:
                avisos.append(
                    f"Preço de {item.descricao} mudou de {formatar_brl(item.preco_unit)}"
                    f" para {formatar_brl(atual.preco)}."
                )
                item.preco_unit = atual.preco
        if avisos:
            self._preencher_carrinho()
            self.mensagem.setText(" ".join(avisos))

    def _cadastro_ativo(self, s: Session) -> list[_Resultado]:
        return [_de_produto(p) for p in buscar_produtos(s, self._ator)] + [
            _de_servico(sv) for sv in listar_servicos(s, self._ator)
        ]

    # --- busca e carrinho ----------------------------------------------------------

    def buscar(self) -> None:
        termo = self.busca.text().strip()
        if not termo:
            self._mostrar_resultados([])
            return
        with transacao(self._fabrica) as s:
            produtos = buscar_produtos(s, self._ator, termo)
            servicos = listar_servicos(s, self._ator)
        palavras = normalizar_texto(termo).split()
        encontrados = [_de_produto(p) for p in produtos] + [
            _de_servico(sv)
            for sv in servicos
            if _codigo_exato(termo, sv.codigo, None)
            or all(palavra in normalizar_texto(sv.nome) for palavra in palavras)
        ]
        exatos = [r for r in encontrados if _codigo_exato(termo, r.codigo, r.ean)]
        if len(exatos) == 1:
            # Leitor de código de barras: código/EAN exato entra direto no carrinho.
            self.busca.clear()
            self._mostrar_resultados([])
            self._adicionar(exatos[0])
            return
        self._mostrar_resultados(encontrados)
        self.mensagem.setText("" if encontrados else NENHUM_RESULTADO)

    def _mostrar_resultados(self, resultados: list[_Resultado]) -> None:
        self._resultados = resultados
        preencher_tabela(
            self.resultados,
            [
                [
                    "Produto" if r.produto else "Serviço",
                    r.codigo,
                    r.descricao,
                    formatar_brl(r.preco),
                    "—" if r.estoque is None else formatar_qtd(r.estoque),
                ]
                for r in resultados
            ],
        )

    def _adicionar_resultado(self, indice: QModelIndex) -> None:
        linha = indice.row()
        if 0 <= linha < len(self._resultados):
            self._adicionar(self._resultados[linha])

    def adicionar_produto(self, produto_id: int) -> None:
        resultado = self._localizar(True, produto_id)
        if resultado is None:
            self.mensagem.setText("Produto não encontrado ou inativo.")
            return
        self._adicionar(resultado)

    def adicionar_servico(self, servico_id: int) -> None:
        resultado = self._localizar(False, servico_id)
        if resultado is None:
            self.mensagem.setText("Serviço não encontrado ou inativo.")
            return
        self._adicionar(resultado)

    def _localizar(self, produto: bool, id_: int) -> _Resultado | None:
        for resultado in self._resultados:
            if resultado.produto == produto and resultado.id == id_:
                return resultado
        with transacao(self._fabrica) as s:
            if produto:
                candidatos = [_de_produto(p) for p in buscar_produtos(s, self._ator)]
            else:
                candidatos = [_de_servico(sv) for sv in listar_servicos(s, self._ator)]
        return next((c for c in candidatos if c.id == id_), None)

    def _adicionar(self, resultado: _Resultado) -> None:
        for item in self._itens:
            if item.produto == resultado.produto and item.id == resultado.id:
                item.qtd = item.qtd + 1
                break
        else:
            self._itens.append(
                _ItemCarrinho(resultado.produto, resultado.id, resultado.descricao, resultado.preco)
            )
        self.mensagem.clear()
        self._preencher_carrinho()
        self._atualizar_totais()
        self.busca.setFocus()

    def _preencher_carrinho(self) -> None:
        self._preenchendo = True
        try:
            preencher_tabela(
                self.carrinho,
                [
                    [
                        item.descricao,
                        formatar_qtd(item.qtd),
                        formatar_brl(item.preco_unit),
                        formatar_brl(subtotal_item(item.qtd, item.preco_unit)),
                    ]
                    for item in self._itens
                ],
            )
            for linha in range(self.carrinho.rowCount()):
                for coluna in range(len(_COLUNAS_CARRINHO)):
                    celula = self.carrinho.item(linha, coluna)
                    if celula is not None and coluna != _COLUNA_QTD:
                        celula.setFlags(celula.flags() & ~Qt.ItemFlag.ItemIsEditable)
        finally:
            self._preenchendo = False
        self.botao_finalizar.setEnabled(bool(self._itens))

    def _ao_editar_celula(self, celula: QTableWidgetItem) -> None:
        if self._preenchendo or celula.column() != _COLUNA_QTD:
            return
        linha, texto = celula.row(), celula.text()
        # Adiado: refazer a tabela dentro do sinal da própria célula apagaria a célula emissora.
        QTimer.singleShot(0, lambda: self.definir_qtd(linha, texto))

    def definir_qtd(self, linha: int, texto: str) -> None:
        if not 0 <= linha < len(self._itens):
            return
        try:
            qtd = arredondar_qtd(ler_decimal(texto, "Quantidade"))
            if qtd <= 0:
                raise ValorInvalido("Quantidade: informe um valor maior que zero.")
        except ValorInvalido as erro:
            mostrar_erro(self, erro)
            self._preencher_carrinho()  # a célula volta ao valor anterior
            self.busca.setFocus()
            return
        self._itens[linha].qtd = qtd
        self._preencher_carrinho()
        self._atualizar_totais()
        self.busca.setFocus()

    def remover_item(self, linha: int) -> None:
        if 0 <= linha < len(self._itens):
            del self._itens[linha]
            self._preencher_carrinho()
            self._atualizar_totais()
            self.busca.setFocus()

    # --- cliente --------------------------------------------------------------------

    def definir_cliente(self, cliente_id: int | None) -> None:
        if cliente_id is None:
            self._cliente = None
        else:
            try:
                with transacao(self._fabrica) as s:
                    self._cliente = obter_cliente(s, self._ator, cliente_id)
            except ErroDominio as erro:
                mostrar_erro(self, erro)
                return
        self.painel_cliente.setText(
            SEM_CLIENTE if self._cliente is None else _texto_cliente(self._cliente)
        )
        self._atualizar_totais()

    # --- pagamento e prévia ---------------------------------------------------------

    def _forma(self) -> FormaPagamento:
        return FormaPagamento(self.forma.currentData())

    def _ao_trocar_forma(self) -> None:
        crediario = self._forma() == FormaPagamento.CREDIARIO
        if crediario:
            self.desconto.clear()
        self.desconto.setEnabled(not crediario)
        self.tipo_desconto.setEnabled(not crediario)
        dinheiro = self._forma() == FormaPagamento.DINHEIRO
        if not dinheiro:
            self.recebido.clear()
        self.recebido.setEnabled(dinheiro)
        self._atualizar_totais()

    def _desconto_informado(self) -> Desconto:
        if self._forma() == FormaPagamento.CREDIARIO:
            return Desconto()
        valor = ler_decimal_opcional(self.desconto.text(), "Desconto")
        return Desconto(
            TipoDesconto(self.tipo_desconto.currentData()),
            Decimal(0) if valor is None else valor,
        )

    def _calcular(self) -> _Previa:
        subtotal = sum(
            (subtotal_item(item.qtd, item.preco_unit) for item in self._itens), Decimal(0)
        )
        desconto = valor_desconto(subtotal, self._desconto_informado())
        bruto = subtotal - desconto
        forma = self._forma()
        pagamento = calcular_pagamento(bruto, forma, self._taxas.get(forma), clock.hoje())
        return _Previa(subtotal, desconto, bruto, pagamento)

    def _aviso_limite(self, bruto: Decimal) -> str:
        cliente = self._cliente
        if (
            self._forma() != FormaPagamento.CREDIARIO
            or cliente is None
            or cliente.disponivel is None
        ):
            return ""
        excesso = bruto - cliente.disponivel
        if excesso <= 0:
            return ""
        return f"⚠ Passa do disponível do cliente em {formatar_brl(excesso)}."

    def _atualizar_totais(self) -> None:
        try:
            previa = self._calcular()
        except ValorInvalido as erro:
            self.totais.setText(f"Total a cobrar: — ({erro})")
            self.troco.clear()
            return
        partes = [
            f"Subtotal {formatar_brl(previa.subtotal)}",
            f"Desconto {formatar_brl(previa.desconto)}",
        ]
        if previa.pagamento.repasse and previa.pagamento.taxa > 0:
            partes.append(f"Taxa {formatar_brl(previa.pagamento.taxa)}")
        partes.append(f"Total a cobrar {formatar_brl(previa.pagamento.cobrado)}")
        texto = " · ".join(partes)
        aviso = self._aviso_limite(previa.bruto)
        self.totais.setText(f"{texto}\n{aviso}" if aviso else texto)
        self._atualizar_troco(previa.pagamento.cobrado)

    def _atualizar_troco(self, cobrado: Decimal) -> None:
        texto = self.recebido.text().strip()
        if self._forma() != FormaPagamento.DINHEIRO or not texto:
            self.troco.clear()
            return
        try:
            recebido = ler_decimal(texto, "Recebido")
        except ValorInvalido:
            self.troco.setText("Troco: —")
            return
        diferenca = recebido - cobrado
        if diferenca >= 0:
            self.troco.setText(f"Troco {formatar_brl(diferenca)}")
        else:
            self.troco.setText(f"Falta {formatar_brl(-diferenca)}")

    def _ler_recebido(self) -> Decimal | None:
        if self._forma() != FormaPagamento.DINHEIRO:
            return None
        return ler_decimal_opcional(self.recebido.text(), "Recebido")

    def _nova_venda(self) -> NovaVenda:
        return NovaVenda(
            itens=tuple(
                ItemVenda(qtd=item.qtd, produto_id=item.id)
                if item.produto
                else ItemVenda(qtd=item.qtd, servico_id=item.id)
                for item in self._itens
            ),
            forma=self._forma(),
            desconto=self._desconto_informado(),
            cliente_id=None if self._cliente is None else self._cliente.id,
        )

    # --- finalização ----------------------------------------------------------------

    def finalizar(self) -> None:
        if not self._itens:
            self.mensagem.setText("Carrinho vazio.")
            return
        try:
            previa = self._calcular()
            recebido = self._ler_recebido()
            if recebido is not None:
                troco(previa.pagamento.cobrado, recebido)
            dados = self._nova_venda()
        except ValorInvalido as erro:
            mostrar_erro(self, erro)
            return
        # Cada confirmação liga uma flag; as flags acumulam entre os reenvios
        # (ex.: estoque confirmado e, no reenvio, limite excedido → reenvia com as duas).
        autorizador: Ator | None = None
        confirmar_estoque = False
        confirmar_limite = False
        venda_id: int | None = None
        while venda_id is None:
            try:
                with transacao(self._fabrica) as s:
                    venda_id = registrar_venda(
                        s,
                        self._ator,
                        dados,
                        autorizador=autorizador,
                        confirmar_limite=confirmar_limite,
                        confirmar_estoque=confirmar_estoque,
                    )
            except EstoqueInsuficiente as erro:
                if confirmar_estoque:
                    mostrar_erro(self, erro)
                    return
                faltas = "\n".join(erro.faltas) if erro.faltas else str(erro)
                if self._ator.admin:
                    if not self._perguntar(
                        f"Estoque insuficiente:\n{faltas}\n\nVender mesmo assim?"
                    ):
                        return
                else:
                    autorizador = self._autorizar(
                        f"Estoque insuficiente:\n{faltas}\n\n"
                        "Para vender sem estoque, o administrador precisa autorizar."
                    )
                    if autorizador is None:
                        return
                confirmar_estoque = True
            except LimiteExcedido as erro:
                if confirmar_limite:
                    mostrar_erro(self, erro)
                    return
                pergunta = f"{erro}\n\nConfirmar a venda no crediário mesmo assim?"
                if not self._perguntar(pergunta):
                    return
                confirmar_limite = True
            except SessaoFechada as erro:
                mostrar_erro(self, erro)
                self.sessao_encerrada.emit()
                return
            except ErroDominio as erro:
                mostrar_erro(self, erro)
                return
        total = self._total_gravado(venda_id)
        self.limpar()
        sufixo = "" if total is None else f" Total {formatar_brl(total)}."
        self.mensagem.setText(f"Venda nº {venda_id} registrada.{sufixo}")
        self.recarregar()

    def _total_gravado(self, venda_id: int) -> Decimal | None:
        """Total a cobrar como o serviço gravou (`registrar_venda` devolve só o número)."""
        with transacao(self._fabrica) as s:
            linhas = vendas_da_sessao(s, self._ator)
        return next((linha.cobrado for linha in linhas if linha.id == venda_id), None)

    def limpar(self) -> None:
        self._itens.clear()
        self._mostrar_resultados([])
        self.busca.clear()
        self._busca_cliente.limpar()
        self.desconto.clear()
        self.tipo_desconto.setCurrentIndex(0)
        self.recebido.clear()
        self.forma.setCurrentIndex(0)
        self.definir_cliente(None)
        self.mensagem.clear()
        self._preencher_carrinho()
        self._ao_trocar_forma()
        self.busca.setFocus()

    # --- diálogos do caixa ----------------------------------------------------------

    def _receber(self) -> None:
        if DialogoRecebimento(self._fabrica, self._ator, self, perguntar=self._perguntar).exec():
            self.mensagem.setText("Recebimento registrado.")
            self.recarregar()

    def _abrir_vendas(self) -> None:
        DialogoVendasSessao(self._fabrica, self._ator, self, autorizar=self._autorizar).exec()
        self.recarregar()

    def _fechar_caixa(self) -> None:
        try:
            dialogo = DialogoFechamento(self._fabrica, self._ator, self, perguntar=self._perguntar)
        except ErroDominio as erro:  # caixa já fechado por outro login
            mostrar_erro(self, erro)
            self.sessao_encerrada.emit()
            return
        if dialogo.exec():
            self.limpar()
            self.sessao_encerrada.emit()

    # --- diálogos padrão ------------------------------------------------------------

    def _autorizar_padrao(self, texto: str) -> Ator | None:
        return pedir_autorizacao(self._fabrica, self, texto)
