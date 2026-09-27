"""Produto: cadastro, ajuste de estoque, busca e movimentações."""

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from cfauto.auth.models import Usuario
from cfauto.core import clock
from cfauto.core.audit import registrar
from cfauto.core.errors import EanDuplicado, RegistroNaoEncontrado, ValorInvalido
from cfauto.core.money import arredondar, arredondar_custo, arredondar_qtd
from cfauto.core.permissoes import Ator, Modulo, exigir_modulo
from cfauto.core.sequencias import proximo_codigo
from cfauto.core.texto import normalizar_texto
from cfauto.estoque.models import (
    MotivoAjuste,
    MovimentoEstoque,
    NotaEntrada,
    NotaEntradaItem,
    Produto,
    TipoMovimento,
)
from cfauto.estoque.movimentos import movimentar
from cfauto.estoque.schemas import DadosProduto, LinhaMovimento

TAMANHO_MAXIMO_EAN = 14


def snapshot_produto(p: Produto) -> dict[str, Any]:
    return {
        "codigo": p.codigo,
        "ean": p.ean,
        "descricao": p.descricao,
        "categoria": p.categoria,
        "embalagem": p.embalagem,
        "fator": p.fator,
        "preco_entrada": p.preco_entrada,
        "preco_venda": p.preco_venda,
        "preco_promocional": p.preco_promocional,
        "estoque": p.estoque,
        "estoque_minimo": p.estoque_minimo,
        "estoque_minimo_manual": p.estoque_minimo_manual,
        "data_ult_entrada": p.data_ult_entrada,
        "destino": p.destino,
        "ativo": p.ativo,
    }


def normalizar_ean(ean: str | None) -> str | None:
    """'' ou None → None; senão só dígitos ASCII, no máximo 14 (sem validar dígito verificador:
    códigos internos da loja são comuns)."""
    if ean is None:
        return None
    texto = ean.strip()
    if not texto:
        return None
    if not (texto.isascii() and texto.isdigit()) or len(texto) > TAMANHO_MAXIMO_EAN:
        raise ValorInvalido("O EAN deve ter só dígitos (no máximo 14).")
    return texto


def ean_em_uso(s: Session, ean: str) -> Produto | None:
    return s.scalar(select(Produto).where(Produto.ean == ean))


def novo_codigo_produto(s: Session) -> str:
    return proximo_codigo(s, "produto", digitos=4)


def _obter(s: Session, produto_id: int) -> Produto:
    produto = s.get(Produto, produto_id)
    if produto is None:
        raise RegistroNaoEncontrado("Produto não encontrado.")
    return produto


def _validar(dados: DadosProduto) -> str:
    descricao = dados.descricao.strip()
    if not descricao:
        raise ValorInvalido("Descrição obrigatória.")
    if arredondar_qtd(dados.fator) <= 0:
        raise ValorInvalido("O fator deve ser maior que zero.")
    if dados.preco_entrada < 0 or dados.preco_venda < 0:
        raise ValorInvalido("Preços não podem ser negativos.")
    if dados.preco_promocional is not None and dados.preco_promocional <= 0:
        raise ValorInvalido("O preço promocional deve ser maior que zero.")
    if dados.estoque_minimo < 0:
        raise ValorInvalido("O estoque mínimo não pode ser negativo.")
    return descricao


def _checar_ean(s: Session, ean: str | None, produto_id: int | None) -> None:
    if ean is None:
        return
    dono = ean_em_uso(s, ean)
    if dono is not None and dono.id != produto_id:
        raise EanDuplicado(f"O EAN {ean} já pertence ao produto {dono.codigo} — {dono.descricao}.")


def _aplicar(p: Produto, dados: DadosProduto, descricao: str, ean: str | None) -> None:
    p.ean = ean
    p.descricao = descricao
    p.categoria = dados.categoria.strip()
    p.embalagem = dados.embalagem.strip() or "Unidade"
    p.fator = arredondar_qtd(dados.fator)
    p.preco_entrada = arredondar_custo(dados.preco_entrada)
    p.preco_venda = arredondar(dados.preco_venda)
    p.preco_promocional = (
        None if dados.preco_promocional is None else arredondar(dados.preco_promocional)
    )
    p.destino = dados.destino


def obter_produto(s: Session, ator: Ator, produto_id: int) -> Produto:
    exigir_modulo(ator, Modulo.ESTOQUE)
    return _obter(s, produto_id)


def criar_produto(s: Session, ator: Ator, dados: DadosProduto) -> Produto:
    exigir_modulo(ator, Modulo.ESTOQUE)
    descricao = _validar(dados)
    estoque_inicial = arredondar_qtd(dados.estoque_inicial)
    if estoque_inicial < 0:
        raise ValorInvalido("O estoque inicial não pode ser negativo.")
    ean = normalizar_ean(dados.ean)
    _checar_ean(s, ean, None)
    minimo = arredondar_qtd(dados.estoque_minimo)
    p = Produto(
        codigo=novo_codigo_produto(s),
        estoque=Decimal("0.000"),
        estoque_minimo=minimo,
        estoque_minimo_manual=dados.estoque_minimo_manual or minimo > 0,
        # Carimbada no cadastro mesmo com estoque 0 (como no original); nunca na edição.
        data_ult_entrada=clock.hoje(),
        markup_manual=False,
        ativo=True,
    )
    _aplicar(p, dados, descricao, ean)
    s.add(p)
    s.flush()
    if estoque_inicial > 0:
        movimentar(s, ator, p, estoque_inicial, TipoMovimento.CADASTRO)
    registrar(s, ator.id, "criar", "produto", p.id, None, snapshot_produto(p))
    return p


def atualizar_produto(s: Session, ator: Ator, produto_id: int, dados: DadosProduto) -> Produto:
    """Altera o cadastro. Nunca mexe no estoque nem na data da última entrada."""
    exigir_modulo(ator, Modulo.ESTOQUE)
    p = _obter(s, produto_id)
    descricao = _validar(dados)
    ean = normalizar_ean(dados.ean)
    _checar_ean(s, ean, p.id)
    antes = snapshot_produto(p)
    _aplicar(p, dados, descricao, ean)
    minimo = arredondar_qtd(dados.estoque_minimo)
    # Mudar o mínimo à mão o protege do cálculo automático (sub-projeto 7).
    p.estoque_minimo_manual = minimo != p.estoque_minimo or dados.estoque_minimo_manual
    p.estoque_minimo = minimo
    s.flush()
    registrar(s, ator.id, "alterar", "produto", p.id, antes, snapshot_produto(p))
    return p


def _definir_ativo(s: Session, ator: Ator, produto_id: int, ativo: bool, acao: str) -> Produto:
    exigir_modulo(ator, Modulo.ESTOQUE)
    p = _obter(s, produto_id)
    if p.ativo == ativo:
        raise ValorInvalido("O produto já está ativo." if ativo else "O produto já está inativo.")
    p.ativo = ativo
    s.flush()
    registrar(s, ator.id, acao, "produto", p.id, {"ativo": not ativo}, {"ativo": ativo})
    return p


def desativar_produto(s: Session, ator: Ator, produto_id: int) -> Produto:
    return _definir_ativo(s, ator, produto_id, False, "desativar")


def reativar_produto(s: Session, ator: Ator, produto_id: int) -> Produto:
    return _definir_ativo(s, ator, produto_id, True, "reativar")


def ajustar_estoque(
    s: Session,
    ator: Ator,
    produto_id: int,
    nova_quantidade: Decimal,
    motivo: MotivoAjuste,
    observacao: str = "",
) -> MovimentoEstoque:
    """Leva o estoque à quantidade contada, registrando a diferença com motivo."""
    exigir_modulo(ator, Modulo.ESTOQUE)
    p = _obter(s, produto_id)
    nova = arredondar_qtd(nova_quantidade)
    if nova < 0:
        raise ValorInvalido("A quantidade não pode ser negativa.")
    obs = observacao.strip()
    if motivo is MotivoAjuste.OUTRO and not obs:
        raise ValorInvalido("Informe a observação quando o motivo for 'Outro'.")
    diferenca = nova - p.estoque
    if diferenca == 0:
        raise ValorInvalido("O estoque já está com essa quantidade.")
    antes = p.estoque
    movimento = movimentar(
        s, ator, p, diferenca, TipoMovimento.AJUSTE, motivo=motivo, observacao=obs or None
    )
    registrar(
        s,
        ator.id,
        "ajustar_estoque",
        "produto",
        p.id,
        {"estoque": antes},
        {"estoque": p.estoque, "motivo": motivo, "observacao": obs or None},
    )
    return movimento


def _casa_codigo(p: Produto, chave: str) -> bool:
    if p.ean is not None and p.ean == chave:
        return True
    if p.codigo == chave:
        return True
    return chave.isdigit() and p.codigo.isdigit() and int(p.codigo) == int(chave)


def buscar_produtos(
    s: Session, ator: Ator, termo: str = "", *, incluir_inativos: bool = False
) -> list[Produto]:
    """Código/EAN exatos primeiro; depois descrição começando pelo termo; depois descrição
    contendo todas as palavras. Sem acento e sem diferenciar maiúsculas."""
    exigir_modulo(ator, Modulo.ESTOQUE)
    consulta = select(Produto)
    if not incluir_inativos:
        consulta = consulta.where(Produto.ativo.is_(True))
    produtos = sorted(s.scalars(consulta), key=lambda p: (normalizar_texto(p.descricao), p.id))
    chave = normalizar_texto(termo)
    if not chave:
        return produtos
    palavras = chave.split()
    exatos: list[Produto] = []
    prefixos: list[Produto] = []
    contem: list[Produto] = []
    for p in produtos:
        if _casa_codigo(p, chave):
            exatos.append(p)
            continue
        descricao = normalizar_texto(p.descricao)
        if descricao.startswith(chave):
            prefixos.append(p)
        elif all(palavra in descricao for palavra in palavras):
            contem.append(p)
    return exatos + prefixos + contem


def listar_movimentos(s: Session, ator: Ator, produto_id: int) -> list[LinhaMovimento]:
    """Movimentos do produto, do mais recente para o mais antigo."""
    exigir_modulo(ator, Modulo.ESTOQUE)
    _obter(s, produto_id)
    consulta = (
        select(
            MovimentoEstoque,
            Usuario.nome.label("usuario_nome"),
            NotaEntrada.numero.label("nota_numero"),
            NotaEntrada.serie.label("nota_serie"),
            NotaEntrada.emitente_nome.label("nota_emitente"),
        )
        .join(Usuario, MovimentoEstoque.usuario_id == Usuario.id)
        .outerjoin(NotaEntradaItem, MovimentoEstoque.nota_entrada_item_id == NotaEntradaItem.id)
        .outerjoin(NotaEntrada, NotaEntradaItem.nota_id == NotaEntrada.id)
        .where(MovimentoEstoque.produto_id == produto_id)
        .order_by(MovimentoEstoque.data_hora.desc(), MovimentoEstoque.id.desc())
    )
    linhas = []
    for row in s.execute(consulta):
        m = row.MovimentoEstoque
        nota = (
            None
            if row.nota_numero is None
            else f"NF {row.nota_numero}/{row.nota_serie} — {row.nota_emitente}"
        )
        linhas.append(
            LinhaMovimento(
                data_hora=m.data_hora,
                tipo=m.tipo,
                quantidade=m.quantidade,
                saldo_apos=m.saldo_apos,
                usuario_nome=row.usuario_nome,
                motivo=m.motivo,
                observacao=m.observacao,
                nota=nota,
            )
        )
    return linhas


def categorias_usadas(s: Session, ator: Ator) -> list[str]:
    exigir_modulo(ator, Modulo.ESTOQUE)
    valores = s.scalars(select(Produto.categoria).where(Produto.categoria != "").distinct())
    return sorted(valores, key=normalizar_texto)
