"""Estoque: produto, serviço, livro de movimentos e notas de entrada."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import ForeignKey, Index, LargeBinary, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cfauto.core.db import Base, ComTimestamps
from cfauto.core.money import arredondar
from cfauto.core.tipos import Custo, DecimalEscalado, Dinheiro, EnumTexto, Quantidade


class Destino(StrEnum):
    REVENDA = "REVENDA"
    USO_CONSUMO = "USO_CONSUMO"
    MATERIA_PRIMA = "MATERIA_PRIMA"


TITULOS_DESTINO: dict[Destino, str] = {
    Destino.REVENDA: "Revenda",
    Destino.USO_CONSUMO: "Uso/Consumo",
    Destino.MATERIA_PRIMA: "Matéria-prima",
}


class TipoMovimento(StrEnum):
    CADASTRO = "CADASTRO"
    ENTRADA_NF = "ENTRADA_NF"
    ESTORNO_NF = "ESTORNO_NF"
    AJUSTE = "AJUSTE"
    VENDA = "VENDA"
    CANCELAMENTO_VENDA = "CANCELAMENTO_VENDA"


TITULOS_TIPO_MOVIMENTO: dict[TipoMovimento, str] = {
    TipoMovimento.CADASTRO: "Cadastro",
    TipoMovimento.ENTRADA_NF: "Entrada NF-e",
    TipoMovimento.ESTORNO_NF: "Estorno NF-e",
    TipoMovimento.AJUSTE: "Ajuste",
    TipoMovimento.VENDA: "Venda",
    TipoMovimento.CANCELAMENTO_VENDA: "Cancelamento de venda",
}


class MotivoAjuste(StrEnum):
    INVENTARIO = "INVENTARIO"
    PERDA_AVARIA = "PERDA_AVARIA"
    CONSUMO_INTERNO = "CONSUMO_INTERNO"
    OUTRO = "OUTRO"


TITULOS_MOTIVO: dict[MotivoAjuste, str] = {
    MotivoAjuste.INVENTARIO: "Inventário",
    MotivoAjuste.PERDA_AVARIA: "Perda/Avaria",
    MotivoAjuste.CONSUMO_INTERNO: "Consumo interno",
    MotivoAjuste.OUTRO: "Outro",
}


class Produto(ComTimestamps, Base):
    __tablename__ = "produto"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    ean: Mapped[str | None] = mapped_column(String(14), unique=True)
    descricao: Mapped[str] = mapped_column(String(200))
    categoria: Mapped[str] = mapped_column(String(60), default="")
    embalagem: Mapped[str] = mapped_column(String(30), default="Unidade")
    # Unidades de estoque por embalagem; preco_entrada é o custo da embalagem.
    fator: Mapped[Decimal] = mapped_column(Quantidade(), default=Decimal(1))
    data_ult_entrada: Mapped[date | None]
    preco_entrada: Mapped[Decimal] = mapped_column(Custo(), default=Decimal(0))
    preco_venda: Mapped[Decimal] = mapped_column(Dinheiro(), default=Decimal(0))
    preco_promocional: Mapped[Decimal | None] = mapped_column(Dinheiro())
    # Saldo; só muda por cfauto.estoque.movimentos.movimentar().
    estoque: Mapped[Decimal] = mapped_column(Quantidade(), default=Decimal(0))
    estoque_minimo: Mapped[Decimal] = mapped_column(Quantidade(), default=Decimal(0))
    estoque_minimo_manual: Mapped[bool] = mapped_column(default=False)
    destino: Mapped[Destino] = mapped_column(EnumTexto(Destino), default=Destino.REVENDA)
    markup_pct: Mapped[Decimal | None] = mapped_column(DecimalEscalado(2))
    markup_manual: Mapped[bool] = mapped_column(default=False)
    ativo: Mapped[bool] = mapped_column(default=True)

    @property
    def preco_fracionado(self) -> Decimal:
        """Custo por unidade de estoque."""
        return self.preco_entrada / self.fator

    @property
    def margem(self) -> Decimal | None:
        """(venda − custo unitário) ÷ venda; None sem preço de venda ou sem custo."""
        if self.preco_venda <= 0 or self.preco_entrada <= 0:
            return None
        return (self.preco_venda - self.preco_fracionado) / self.preco_venda


class Servico(ComTimestamps, Base):
    __tablename__ = "servico"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    nome: Mapped[str] = mapped_column(String(120))
    mao_obra_pct: Mapped[Decimal] = mapped_column(DecimalEscalado(2), default=Decimal(0))
    ativo: Mapped[bool] = mapped_column(default=True)
    materiais: Mapped[list["ServicoMaterial"]] = relationship(
        back_populates="servico",
        cascade="all, delete-orphan",
        order_by="ServicoMaterial.id",
        lazy="selectin",
    )

    @property
    def custo_materiais(self) -> Decimal:
        return sum((m.custo_unit * m.qtd for m in self.materiais), Decimal(0))

    @property
    def preco(self) -> Decimal:
        return arredondar(self.custo_materiais * (1 + self.mao_obra_pct / 100))


class ServicoMaterial(ComTimestamps, Base):
    __tablename__ = "servico_material"

    id: Mapped[int] = mapped_column(primary_key=True)
    servico_id: Mapped[int] = mapped_column(ForeignKey("servico.id"), index=True)
    descricao: Mapped[str] = mapped_column(String(120))
    custo_unit: Mapped[Decimal] = mapped_column(Custo())
    qtd: Mapped[Decimal] = mapped_column(Quantidade())
    servico: Mapped[Servico] = relationship(back_populates="materiais")


class NotaEntrada(ComTimestamps, Base):
    __tablename__ = "nota_entrada"
    __table_args__ = (
        # Impede lançar a mesma nota duas vezes, mas permite reimportar uma nota estornada.
        Index(
            "ix_nota_entrada_chave_ativa",
            "chave",
            unique=True,
            sqlite_where=text("estornada = 0"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    chave: Mapped[str] = mapped_column(String(44))
    numero: Mapped[int]
    serie: Mapped[int]
    modelo: Mapped[int]
    emitente_cnpj: Mapped[str] = mapped_column(String(14))
    emitente_nome: Mapped[str] = mapped_column(String(120))
    data_emissao: Mapped[date]
    data_entrada: Mapped[datetime]
    valor_total: Mapped[Decimal] = mapped_column(Dinheiro())
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    xml_original: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    estornada: Mapped[bool] = mapped_column(default=False)
    estornada_em: Mapped[datetime | None]
    estornada_por: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    itens: Mapped[list["NotaEntradaItem"]] = relationship(
        back_populates="nota",
        cascade="all, delete-orphan",
        order_by="NotaEntradaItem.n_item",
        lazy="selectin",
    )


class NotaEntradaItem(ComTimestamps, Base):
    __tablename__ = "nota_entrada_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    nota_id: Mapped[int] = mapped_column(ForeignKey("nota_entrada.id"), index=True)
    n_item: Mapped[int]
    codigo_fornecedor: Mapped[str] = mapped_column(String(60))
    ean: Mapped[str | None] = mapped_column(String(14))
    descricao_nota: Mapped[str] = mapped_column(String(200))
    unidade: Mapped[str] = mapped_column(String(10))
    qtd_nota: Mapped[Decimal] = mapped_column(DecimalEscalado(4))
    valor_produto: Mapped[Decimal] = mapped_column(Dinheiro(), default=Decimal(0))
    desconto: Mapped[Decimal] = mapped_column(Dinheiro(), default=Decimal(0))
    frete: Mapped[Decimal] = mapped_column(Dinheiro(), default=Decimal(0))
    seguro: Mapped[Decimal] = mapped_column(Dinheiro(), default=Decimal(0))
    outros: Mapped[Decimal] = mapped_column(Dinheiro(), default=Decimal(0))
    ipi: Mapped[Decimal] = mapped_column(Dinheiro(), default=Decimal(0))
    icms_st: Mapped[Decimal] = mapped_column(Dinheiro(), default=Decimal(0))
    custo_total: Mapped[Decimal] = mapped_column(Dinheiro())
    # Nulo = item ignorado na conferência.
    produto_id: Mapped[int | None] = mapped_column(ForeignKey("produto.id"), index=True)
    fator: Mapped[Decimal | None] = mapped_column(Quantidade())
    qtd_estoque: Mapped[Decimal | None] = mapped_column(Quantidade())
    preco_entrada_aplicado: Mapped[Decimal | None] = mapped_column(Custo())
    preco_entrada_anterior: Mapped[Decimal | None] = mapped_column(Custo())
    data_ult_entrada_anterior: Mapped[date | None]
    nota: Mapped[NotaEntrada] = relationship(back_populates="itens")
    produto: Mapped[Produto | None] = relationship(lazy="selectin")


class MovimentoEstoque(ComTimestamps, Base):
    __tablename__ = "movimento_estoque"

    id: Mapped[int] = mapped_column(primary_key=True)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produto.id"), index=True)
    data_hora: Mapped[datetime] = mapped_column(index=True)
    tipo: Mapped[TipoMovimento] = mapped_column(EnumTexto(TipoMovimento))
    quantidade: Mapped[Decimal] = mapped_column(Quantidade())
    saldo_apos: Mapped[Decimal] = mapped_column(Quantidade())
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    motivo: Mapped[MotivoAjuste | None] = mapped_column(EnumTexto(MotivoAjuste))
    observacao: Mapped[str | None] = mapped_column(String(200))
    nota_entrada_item_id: Mapped[int | None] = mapped_column(ForeignKey("nota_entrada_item.id"))
    venda_item_id: Mapped[int | None] = mapped_column(ForeignKey("venda_item.id"))


class VinculoFornecedorProduto(ComTimestamps, Base):
    """Código do item no fornecedor → produto, aprendido na conferência da NF-e."""

    __tablename__ = "vinculo_fornecedor_produto"
    __table_args__ = (UniqueConstraint("emitente_cnpj", "codigo_fornecedor"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    emitente_cnpj: Mapped[str] = mapped_column(String(14))
    codigo_fornecedor: Mapped[str] = mapped_column(String(60))
    produto_id: Mapped[int] = mapped_column(ForeignKey("produto.id"))
    fator: Mapped[Decimal] = mapped_column(Quantidade())
