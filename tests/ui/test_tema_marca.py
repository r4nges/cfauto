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
