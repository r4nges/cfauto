from decimal import Decimal

from cfauto.auth.service import NovoUsuario, criar_usuario
from cfauto.core.db import transacao
from cfauto.core.permissoes import Modulo
from cfauto.estoque.entrada import confirmar_entrada, preparar_entrada
from cfauto.estoque.models import MotivoAjuste
from cfauto.estoque.produtos import ajustar_estoque, criar_produto, obter_produto
from cfauto.estoque.schemas import AcaoItem, DadosProduto, DecisaoItem
from cfauto.ui.estoque import entradas as tela_entradas
from cfauto.ui.estoque.entradas import DialogoConferencia, DialogoItensNota, TelaEntradas
from cfauto.ui.estoque.pagina import PaginaEstoque
from tests.estoque.xml_nfe import ItemXml, montar_nfe

EAN_REFRI = "7891000100103"


def _admin(fabrica):
    with transacao(fabrica) as s:
        return criar_usuario(
            s, None, NovoUsuario(nome="Dono", login="dono", senha="segredo1", admin=True)
        )


def _criar(fabrica, ator, descricao, **campos):
    with transacao(fabrica) as s:
        return criar_produto(s, ator, DadosProduto(descricao=descricao, **campos))


def _conferencia(fabrica, ator, xml):
    with transacao(fabrica) as s:
        return preparar_entrada(s, ator, xml)


def test_pagina_estoque_tem_as_tres_abas(qtbot, fabrica, relogio):
    pagina = PaginaEstoque(fabrica, _admin(fabrica))
    qtbot.addWidget(pagina)
    assert pagina.titulos() == ["Produtos", "Serviços", "Entradas de NF-e"]


def test_conferencia_sugere_e_confirma(qtbot, fabrica, relogio):
    ator = _admin(fabrica)
    refri = _criar(fabrica, ator, "Refrigerante Cola 2L", ean=EAN_REFRI)
    xml = montar_nfe(
        1,
        [
            ItemXml("A-100", "REFRI COLA 2L", "10", "75.00", ean=EAN_REFRI),
            ItemXml(
                "B-200", "PARAFUSO", "2", "30.00", unidade="CX", unidade_trib="UN", qtd_trib="200"
            ),
        ],
    )
    dlg = DialogoConferencia(fabrica, ator, xml, _conferencia(fabrica, ator, xml))
    qtbot.addWidget(dlg)
    assert dlg.acao_da_linha(0) is AcaoItem.VINCULAR
    assert dlg.acao_da_linha(1) is AcaoItem.CRIAR
    assert dlg.tabela.item(1, 10).text() == "200"
    assert dlg.botao_confirmar.isEnabled()
    dlg.confirmar()
    assert dlg.result() == 1
    tela = TelaEntradas(fabrica, ator)
    qtbot.addWidget(tela)
    assert tela.ids_na_tabela() == [dlg.nota_id]
    assert tela.tabela.item(0, 5).text() == "Lançada"
    with transacao(fabrica) as s:
        assert obter_produto(s, ator, refri.id).estoque == Decimal("10")
    itens = DialogoItensNota(fabrica, ator, dlg.nota_id)
    qtbot.addWidget(itens)
    assert itens.tabela.item(0, 4).text() == "0001 — Refrigerante Cola 2L"


def test_vincular_sem_produto_bloqueia_confirmar(qtbot, fabrica, relogio):
    ator = _admin(fabrica)
    parafuso = _criar(fabrica, ator, "Parafuso", fator=Decimal("100"))
    xml = montar_nfe(1, [ItemXml("B-200", "PARAFUSO", "2", "30.00", unidade="CX")])
    dlg = DialogoConferencia(fabrica, ator, xml, _conferencia(fabrica, ator, xml))
    qtbot.addWidget(dlg)
    dlg.definir_acao(0, AcaoItem.VINCULAR)
    assert not dlg.botao_confirmar.isEnabled()
    dlg.definir_produto(0, parafuso)
    assert dlg.botao_confirmar.isEnabled()
    assert dlg.campo_fator(0).text() == "100"
    assert dlg.tabela.item(0, 10).text() == "200"
    dlg.campo_fator(0).setText("50")
    assert dlg.tabela.item(0, 10).text() == "100"
    dlg.definir_acao(0, AcaoItem.IGNORAR)
    assert dlg.tabela.item(0, 10).text() == "—"


def _nota_lancada(fabrica, ator):
    produto = _criar(fabrica, ator, "Refri", ean=EAN_REFRI)
    xml = montar_nfe(1, [ItemXml("A-100", "REFRI", "10", "75.00", ean=EAN_REFRI)])
    decisao = DecisaoItem(1, AcaoItem.VINCULAR, produto_id=produto.id, fator=Decimal("1"))
    with transacao(fabrica) as s:
        nota = confirmar_entrada(s, ator, xml, [decisao])
    return nota, produto


def test_estorno_com_segunda_confirmacao_quando_fica_negativo(qtbot, fabrica, relogio):
    ator = _admin(fabrica)
    nota, produto = _nota_lancada(fabrica, ator)
    with transacao(fabrica) as s:
        ajustar_estoque(s, ator, produto.id, Decimal("3"), MotivoAjuste.PERDA_AVARIA)
    tela = TelaEntradas(fabrica, ator)
    qtbot.addWidget(tela)
    perguntas = []

    def responder(texto):
        perguntas.append(texto)
        return True

    assert tela.estornar_nota(nota.id, responder)
    assert len(perguntas) == 2
    assert "negativo" in perguntas[1]
    assert tela.tabela.item(0, 5).text() == "Estornada"


def test_estorno_cancelado_nao_muda_nada(qtbot, fabrica, relogio):
    ator = _admin(fabrica)
    nota, _produto = _nota_lancada(fabrica, ator)
    tela = TelaEntradas(fabrica, ator)
    qtbot.addWidget(tela)
    assert not tela.estornar_nota(nota.id, lambda _texto: False)
    assert tela.tabela.item(0, 5).text() == "Lançada"


def test_botao_estornar_desabilita_para_nota_ja_estornada(qtbot, fabrica, relogio):
    ator = _admin(fabrica)
    nota, _produto = _nota_lancada(fabrica, ator)
    tela = TelaEntradas(fabrica, ator)
    qtbot.addWidget(tela)
    assert not tela.botao_estornar.isEnabled()  # nada selecionado ainda
    tela.selecionar(0)
    assert tela.botao_estornar.isEnabled()
    assert tela.estornar_nota(nota.id, lambda _texto: True)
    tela.selecionar(0)
    assert not tela.botao_estornar.isEnabled()


def test_operador_de_estoque_nao_ve_estornar(qtbot, fabrica, relogio):
    admin = _admin(fabrica)
    with transacao(fabrica) as s:
        estoquista = criar_usuario(
            s,
            admin,
            NovoUsuario(
                nome="João", login="joao", senha="segredo3", modulos=frozenset({Modulo.ESTOQUE})
            ),
        )
    tela = TelaEntradas(fabrica, estoquista)
    qtbot.addWidget(tela)
    assert tela.botao_estornar.isHidden()


def test_importar_arquivo_invalido_mostra_erro(qtbot, fabrica, relogio, tmp_path, monkeypatch):
    erros = []
    monkeypatch.setattr(tela_entradas, "mostrar_erro", lambda _pai, erro: erros.append(str(erro)))
    arquivo = tmp_path / "nota.xml"
    arquivo.write_bytes(b"<html><body>oi</body></html>")
    tela = TelaEntradas(fabrica, _admin(fabrica))
    qtbot.addWidget(tela)
    tela.importar_arquivo(arquivo)
    assert "NF-e" in erros[0]
