"""Entrada de mercadoria por XML de NF-e: conferência, confirmação, estorno e consultas."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from cfauto.core import clock, config
from cfauto.core.audit import registrar
from cfauto.core.errors import (
    EstoqueInsuficiente,
    NotaJaImportada,
    RegistroNaoEncontrado,
    ValorInvalido,
)
from cfauto.core.money import arredondar, arredondar_custo, arredondar_qtd, formatar_qtd
from cfauto.core.permissoes import Ator, Modulo, exigir_admin, exigir_modulo
from cfauto.estoque.models import (
    Destino,
    NotaEntrada,
    NotaEntradaItem,
    Produto,
    TipoMovimento,
    VinculoFornecedorProduto,
)
from cfauto.estoque.movimentos import movimentar
from cfauto.estoque.nfe import ItemNotaLido, NotaFiscalLida, ler_nfe, sugerir_fator
from cfauto.estoque.produtos import ean_em_uso, novo_codigo_produto, snapshot_produto
from cfauto.estoque.schemas import (
    AcaoItem,
    ConferenciaNota,
    DecisaoItem,
    ItemConferencia,
    OrigemCasamento,
)


def preparar_entrada(s: Session, ator: Ator, conteudo: bytes) -> ConferenciaNota:
    """Lê o XML e sugere o produto de cada item. Não grava nada."""
    exigir_modulo(ator, Modulo.ESTOQUE)
    nota = ler_nfe(conteudo)
    _checar_duplicada(s, nota.chave)
    itens = tuple(_sugerir(s, nota.emitente_documento, item) for item in nota.itens)
    return ConferenciaNota(nota=nota, itens=itens, avisos=_avisos(s, nota))


def _avisos(s: Session, nota: NotaFiscalLida) -> tuple[str, ...]:
    configurado = str(config.obter(s, "empresa.cnpj", "") or "")
    cnpj_empresa = "".join(c for c in configurado if c.isdigit())
    destino = nota.destinatario_documento
    if cnpj_empresa and destino is not None and destino != cnpj_empresa:
        return (f"O destinatário da nota ({destino}) não é o CNPJ da empresa ({cnpj_empresa}).",)
    return ()


def _checar_duplicada(s: Session, chave: str) -> None:
    existente = s.scalar(
        select(NotaEntrada).where(NotaEntrada.chave == chave, NotaEntrada.estornada.is_(False))
    )
    if existente is not None:
        raise NotaJaImportada(
            f"A nota {existente.numero}/{existente.serie} de {existente.emitente_nome} "
            f"já foi lançada em {existente.data_entrada:%d/%m/%Y %H:%M}."
        )


def _vinculo(s: Session, cnpj: str, codigo: str) -> VinculoFornecedorProduto | None:
    return s.scalar(
        select(VinculoFornecedorProduto).where(
            VinculoFornecedorProduto.emitente_cnpj == cnpj,
            VinculoFornecedorProduto.codigo_fornecedor == codigo[:60],
        )
    )


def _produto_ativo_por_ean(s: Session, ean: str) -> Produto | None:
    produto = ean_em_uso(s, ean)
    return produto if produto is not None and produto.ativo else None


def _sugestao(
    item: ItemNotaLido,
    origem: OrigemCasamento,
    fator: Decimal,
    produto: Produto | None = None,
) -> ItemConferencia:
    return ItemConferencia(
        item=item,
        origem=origem,
        fator_sugerido=fator,
        produto_id=None if produto is None else produto.id,
        produto_codigo=None if produto is None else produto.codigo,
        produto_descricao=None if produto is None else produto.descricao,
    )


def _sugerir(s: Session, cnpj: str, item: ItemNotaLido) -> ItemConferencia:
    """Ordem: vínculo do fornecedor > EAN comercial > EAN tributável. Nunca por descrição."""
    vinculo = _vinculo(s, cnpj, item.codigo)
    if vinculo is not None:
        produto = s.get(Produto, vinculo.produto_id)
        if produto is not None and produto.ativo:
            return _sugestao(item, OrigemCasamento.VINCULO, vinculo.fator, produto)
    if item.ean is not None:
        produto = _produto_ativo_por_ean(s, item.ean)
        if produto is not None:
            # O EAN do produto identifica a embalagem dele: a unidade da nota é essa embalagem.
            return _sugestao(item, OrigemCasamento.EAN, produto.fator, produto)
    if item.ean_trib is not None and item.ean_trib != item.ean:
        produto = _produto_ativo_por_ean(s, item.ean_trib)
        if produto is not None:
            fator = arredondar_qtd(item.qtd_trib / item.qtd * produto.fator)
            return _sugestao(
                item, OrigemCasamento.EAN_TRIB, fator if fator > 0 else produto.fator, produto
            )
    fator = sugerir_fator(item.descricao, item.unidade, item.qtd, item.unidade_trib, item.qtd_trib)
    return _sugestao(item, OrigemCasamento.NENHUMA, fator)


@dataclass(frozen=True)
class _Plano:
    """Decisão de um item já validada contra o banco."""

    item: ItemNotaLido
    acao: AcaoItem
    fator: Decimal
    produto: Produto | None
    descricao_nova: str


def confirmar_entrada(
    s: Session, ator: Ator, conteudo: bytes, decisoes: Sequence[DecisaoItem]
) -> NotaEntrada:
    """Lança a nota: estoque, custo, data da última entrada, movimentos e vínculos."""
    exigir_modulo(ator, Modulo.ESTOQUE)
    lida = ler_nfe(conteudo)
    _checar_duplicada(s, lida.chave)
    planos = _validar_decisoes(s, lida, decisoes)  # tudo validado antes de gravar
    nota = NotaEntrada(
        chave=lida.chave,
        numero=lida.numero,
        serie=lida.serie,
        modelo=lida.modelo,
        emitente_cnpj=lida.emitente_documento,
        emitente_nome=lida.emitente_nome[:120],
        data_emissao=lida.data_emissao,
        data_entrada=clock.agora(),
        valor_total=arredondar(lida.valor_total),
        usuario_id=ator.id,
        xml_original=conteudo,
        estornada=False,
    )
    s.add(nota)
    s.flush()
    for plano in planos:
        registro = _registro_do_item(plano.item)
        nota.itens.append(registro)
        s.flush()
        if plano.acao is AcaoItem.IGNORAR:
            continue
        produto = plano.produto if plano.produto is not None else _criar_produto(s, ator, plano)
        _lancar(s, ator, lida.emitente_documento, registro, produto, plano)
    lancados = sum(1 for plano in planos if plano.acao is not AcaoItem.IGNORAR)
    registrar(
        s,
        ator.id,
        "entrada",
        "nota_entrada",
        nota.id,
        None,
        {
            "chave": nota.chave,
            "numero": nota.numero,
            "serie": nota.serie,
            "emitente": nota.emitente_nome,
            "emitente_cnpj": nota.emitente_cnpj,
            "valor_total": nota.valor_total,
            "itens_lancados": lancados,
            "itens_ignorados": len(planos) - lancados,
        },
    )
    return nota


def _validar_decisoes(
    s: Session, lida: NotaFiscalLida, decisoes: Sequence[DecisaoItem]
) -> list[_Plano]:
    por_item: dict[int, DecisaoItem] = {}
    for decisao in decisoes:
        if decisao.n_item in por_item:
            raise ValorInvalido(f"Item {decisao.n_item} decidido mais de uma vez.")
        por_item[decisao.n_item] = decisao
    numeros = {item.n_item for item in lida.itens}
    faltando = sorted(numeros - por_item.keys())
    if faltando:
        raise ValorInvalido("Itens sem decisão: " + ", ".join(map(str, faltando)) + ".")
    sobrando = sorted(por_item.keys() - numeros)
    if sobrando:
        raise ValorInvalido("Itens que não existem na nota: " + ", ".join(map(str, sobrando)) + ".")
    return [_plano(s, item, por_item[item.n_item]) for item in lida.itens]


def _plano(s: Session, item: ItemNotaLido, decisao: DecisaoItem) -> _Plano:
    if decisao.acao is AcaoItem.IGNORAR:
        return _Plano(item, AcaoItem.IGNORAR, Decimal(0), None, "")
    fator = arredondar_qtd(decisao.fator) if decisao.fator is not None else Decimal(0)
    if fator <= 0:
        raise ValorInvalido(f"Item {item.n_item}: o fator deve ser maior que zero.")
    if arredondar_qtd(item.qtd * fator) <= 0:
        raise ValorInvalido(f"Item {item.n_item}: a quantidade no estoque ficaria zero.")
    if decisao.acao is AcaoItem.VINCULAR:
        produto = None if decisao.produto_id is None else s.get(Produto, decisao.produto_id)
        if produto is None or not produto.ativo:
            raise ValorInvalido(f"Item {item.n_item}: escolha um produto ativo.")
        return _Plano(item, AcaoItem.VINCULAR, fator, produto, "")
    descricao = (item.descricao if decisao.descricao is None else decisao.descricao).strip()
    if not descricao:
        raise ValorInvalido(f"Item {item.n_item}: informe a descrição do produto novo.")
    return _Plano(item, AcaoItem.CRIAR, fator, None, descricao)


def _registro_do_item(item: ItemNotaLido) -> NotaEntradaItem:
    return NotaEntradaItem(
        n_item=item.n_item,
        codigo_fornecedor=item.codigo[:60],
        ean=item.ean,
        descricao_nota=item.descricao[:200],
        unidade=item.unidade[:10],
        qtd_nota=item.qtd,
        valor_produto=arredondar(item.valor_produto),
        desconto=arredondar(item.desconto),
        frete=arredondar(item.frete),
        seguro=arredondar(item.seguro),
        outros=arredondar(item.outros),
        ipi=arredondar(item.ipi),
        icms_st=arredondar(item.icms_st),
        custo_total=item.custo_total,
    )


def _criar_produto(s: Session, ator: Ator, plano: _Plano) -> Produto:
    item = plano.item
    # EAN da nota só se ainda estiver livre (outro item da mesma nota pode tê-lo usado).
    ean = item.ean if item.ean is not None and ean_em_uso(s, item.ean) is None else None
    produto = Produto(
        codigo=novo_codigo_produto(s),
        ean=ean,
        descricao=plano.descricao_nova[:200],
        categoria="",
        embalagem=item.unidade[:30] or "Unidade",
        fator=plano.fator,
        preco_entrada=Decimal("0.0000"),
        preco_venda=Decimal("0.00"),
        estoque=Decimal("0.000"),
        estoque_minimo=Decimal("0.000"),
        estoque_minimo_manual=False,
        destino=Destino.REVENDA,
        markup_manual=False,
        ativo=True,
    )
    s.add(produto)
    s.flush()
    registrar(s, ator.id, "criar", "produto", produto.id, None, snapshot_produto(produto))
    return produto


def _lancar(
    s: Session,
    ator: Ator,
    cnpj: str,
    registro: NotaEntradaItem,
    produto: Produto,
    plano: _Plano,
) -> None:
    item = plano.item
    qtd_estoque = arredondar_qtd(item.qtd * plano.fator)
    registro.produto = produto
    registro.fator = plano.fator
    registro.qtd_estoque = qtd_estoque
    registro.preco_entrada_anterior = produto.preco_entrada
    registro.data_ult_entrada_anterior = produto.data_ult_entrada
    if item.custo_total > 0:
        # Custo por unidade de estoque, expresso na embalagem do produto (que a nota não muda).
        produto.preco_entrada = arredondar_custo(item.custo_total / qtd_estoque * produto.fator)
    # Bonificação (custo zero) soma estoque, mas não zera o custo do produto.
    registro.preco_entrada_aplicado = produto.preco_entrada
    produto.data_ult_entrada = clock.hoje()
    s.flush()
    movimentar(s, ator, produto, qtd_estoque, TipoMovimento.ENTRADA_NF, nota_item=registro)
    _gravar_vinculo(s, cnpj, item.codigo, produto, plano.fator)


def _gravar_vinculo(s: Session, cnpj: str, codigo: str, produto: Produto, fator: Decimal) -> None:
    vinculo = _vinculo(s, cnpj, codigo)
    if vinculo is None:
        s.add(
            VinculoFornecedorProduto(
                emitente_cnpj=cnpj,
                codigo_fornecedor=codigo[:60],
                produto_id=produto.id,
                fator=fator,
            )
        )
    else:
        vinculo.produto_id = produto.id
        vinculo.fator = fator
    s.flush()


def listar_notas(s: Session, ator: Ator) -> list[NotaEntrada]:
    exigir_modulo(ator, Modulo.ESTOQUE)
    consulta = select(NotaEntrada).order_by(NotaEntrada.data_entrada.desc(), NotaEntrada.id.desc())
    return list(s.scalars(consulta))


def obter_nota(s: Session, ator: Ator, nota_id: int) -> NotaEntrada:
    exigir_modulo(ator, Modulo.ESTOQUE)
    return _obter_nota(s, nota_id)


def _obter_nota(s: Session, nota_id: int) -> NotaEntrada:
    nota = s.get(NotaEntrada, nota_id)
    if nota is None:
        raise RegistroNaoEncontrado("Nota de entrada não encontrada.")
    return nota


@dataclass(frozen=True)
class _Lancado:
    item: NotaEntradaItem
    produto: Produto
    qtd: Decimal


def _lancados_em_ordem_inversa(nota: NotaEntrada) -> list[_Lancado]:
    """Itens com produto, do último para o primeiro: vários itens do mesmo produto
    restauram o preço na ordem certa."""
    resultado = []
    for item in sorted(nota.itens, key=lambda i: i.n_item, reverse=True):
        if item.produto_id is None:
            continue
        if item.produto is None or item.qtd_estoque is None:
            raise ValorInvalido(f"Item {item.n_item} da nota está inconsistente.")
        resultado.append(_Lancado(item, item.produto, item.qtd_estoque))
    return resultado


def _checar_saldos(lancados: list[_Lancado], confirmar_negativo: bool) -> None:
    a_estornar: dict[int, Decimal] = {}
    produtos: dict[int, Produto] = {}
    for lancado in lancados:
        pid = lancado.produto.id
        a_estornar[pid] = a_estornar.get(pid, Decimal(0)) + lancado.qtd
        produtos[pid] = lancado.produto
    negativos = [
        (produtos[pid], qtd) for pid, qtd in a_estornar.items() if produtos[pid].estoque - qtd < 0
    ]
    if negativos and not confirmar_negativo:
        detalhes = "; ".join(
            f"{p.codigo} — {p.descricao}: estoque {formatar_qtd(p.estoque)}, "
            f"estorno {formatar_qtd(qtd)}"
            for p, qtd in negativos
        )
        raise EstoqueInsuficiente(f"O estorno deixará o estoque negativo: {detalhes}.")


def _pode_restaurar(s: Session, nota: NotaEntrada, lancado: _Lancado) -> bool:
    """Só volta o preço/data se esta nota ainda é a última palavra sobre o custo do produto."""
    if lancado.produto.preco_entrada != lancado.item.preco_entrada_aplicado:
        return False  # entrada posterior ou edição manual mudou o custo
    posterior = s.scalar(
        select(NotaEntradaItem.id)
        .join(NotaEntrada, NotaEntradaItem.nota_id == NotaEntrada.id)
        .where(
            NotaEntradaItem.produto_id == lancado.produto.id,
            NotaEntrada.estornada.is_(False),
            NotaEntrada.id > nota.id,
        )
        .limit(1)
    )
    return posterior is None


def estornar_entrada(
    s: Session, ator: Ator, nota_id: int, *, confirmar_negativo: bool = False
) -> NotaEntrada:
    """Desfaz a nota (só admin). Nunca apaga produto; vínculos permanecem."""
    exigir_admin(ator)
    nota = _obter_nota(s, nota_id)
    if nota.estornada:
        raise ValorInvalido("Esta nota já foi estornada.")
    lancados = _lancados_em_ordem_inversa(nota)
    _checar_saldos(lancados, confirmar_negativo)
    for lancado in lancados:
        movimentar(
            s,
            ator,
            lancado.produto,
            -lancado.qtd,
            TipoMovimento.ESTORNO_NF,
            nota_item=lancado.item,
        )
        anterior = lancado.item.preco_entrada_anterior
        if anterior is not None and _pode_restaurar(s, nota, lancado):
            lancado.produto.preco_entrada = anterior
            lancado.produto.data_ult_entrada = lancado.item.data_ult_entrada_anterior
    nota.estornada = True
    nota.estornada_em = clock.agora()
    nota.estornada_por = ator.id
    s.flush()
    registrar(
        s,
        ator.id,
        "estornar",
        "nota_entrada",
        nota.id,
        {"estornada": False},
        {"estornada": True, "chave": nota.chave, "itens_estornados": len(lancados)},
    )
    return nota
