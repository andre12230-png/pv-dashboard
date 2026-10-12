"""Corrections de l'audit de design du mode sombre (12/10/2026).

Six ecarts releves sur la v1.53.0, corriges un par un ; chacun a d'abord
eu son test, qui echouait.
"""
import time

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget

import gui_theme
from gui_theme import appliquer_style, choisir_theme, qss_for


@pytest.fixture(params=["clair", "sombre"])
def theme(request):
    """Le theme demande, palette et feuille de style posees, puis retour
    au clair."""
    app = QApplication.instance() or QApplication([])
    ancienne = app.palette()
    ancienne_feuille = app.styleSheet()
    t = choisir_theme(request.param)
    appliquer_style(app)
    app.setStyleSheet(qss_for(t))
    yield t
    choisir_theme("clair")
    appliquer_style(app)
    app.setPalette(ancienne)
    app.setStyleSheet(ancienne_feuille)


def _attendre(app):
    for _ in range(8):
        app.processEvents()
        time.sleep(0.01)


def _bord(widget) -> set:
    """Les couleurs des deux premieres colonnes de pixels, a mi-hauteur."""
    image = widget.grab().toImage()
    milieu = image.height() // 2
    return {image.pixelColor(x, y).name().upper()
            for x in (0, 1) for y in (milieu - 2, milieu, milieu + 2)}


def _deux(fabrique):
    """Deux exemplaires dans une fenetre invisible : le premier a le focus."""
    app = QApplication.instance()
    # Les tests tournent sur la plateforme « offscreen » (conftest.py) : rien
    # ne s'affiche. WA_DontShowOnScreen empecherait d'activer la fenetre.
    fenetre = QWidget()
    couche = QVBoxLayout(fenetre)
    a, b = fabrique(), fabrique()
    couche.addWidget(a)
    couche.addWidget(b)
    fenetre.resize(240, 120)
    fenetre.show()
    # Une fenetre qui n'est pas active ne donne le curseur a personne.
    fenetre.activateWindow()
    _attendre(app)
    a.setFocus(Qt.TabFocusReason)
    _attendre(app)
    assert a.hasFocus(), "le premier exemplaire n'a pas recu le curseur"
    return fenetre, a, b


def _bouton(nom):
    def fabrique():
        bouton = QPushButton("Recharger")
        bouton.setObjectName(nom)
        return bouton
    return fabrique


# ── 1. Le curseur clavier se voit ───────────────────────────────────────────

@pytest.mark.parametrize("fabrique", [
    _bouton("ActionBtn"), _bouton("NavItem"), QLineEdit, QSpinBox],
    ids=["ActionBtn", "NavItem", "QLineEdit", "QSpinBox"])
def test_le_curseur_clavier_se_voit(theme, fabrique):
    """Audit du 12/10/2026, point 1 : arrive avec Tab sur un bouton d'action,
    un bouton du bandeau ou une case de saisie, rien ne changeait. Le bord
    passe au bleu d'accent du theme (WCAG 2.4.7)."""
    fenetre, avec, sans = _deux(fabrique)
    try:
        assert theme["primary"].upper() in _bord(avec), _bord(avec)
        assert theme["primary"].upper() not in _bord(sans)
    finally:
        fenetre.close()


def test_le_curseur_clavier_se_voit_sur_enregistrer(theme):
    """Le bouton Enregistrer est deja bleu : son focus est un bord de la
    couleur du texte (noir en clair, blanc casse en sombre)."""
    fenetre, avec, sans = _deux(_bouton("SaveBtn"))
    try:
        assert theme["text_primary"].upper() in _bord(avec), _bord(avec)
        assert theme["text_primary"].upper() not in _bord(sans)
    finally:
        fenetre.close()


# ── 2. Les barres pales ne virent plus au brun olive ───────────────────────

def test_barre_pale_lisible_en_sombre():
    """Audit du 12/10/2026, point 2 : le jaune de la production estompe sur
    le fond sombre donnait un brun olive (#7D6420, 2,71 pour 1). La teinte
    pale du sombre se voit a 3 pour 1 au moins sur la carte et reste
    distincte du jaune plein de la barre mise en valeur."""
    from gui_theme import CHART_COLORS_SOMBRE, DARK, _contraste, adoucir
    choisir_theme("sombre")
    try:
        pale = adoucir(CHART_COLORS_SOMBRE["production"])
        assert _contraste(pale, DARK["bg_carte"]) >= 3.0, pale
        assert _contraste(pale, CHART_COLORS_SOMBRE["production"]) >= 1.4, pale
    finally:
        choisir_theme("clair")


def test_barre_pale_inchangee_en_clair():
    """En clair, le meme pastel qu'avant : le jaune a 45 % sur l'ivoire."""
    from gui_theme import CHART_COLORS_CLAIR, adoucir
    assert adoucir(CHART_COLORS_CLAIR["production"]).upper() == "#F2D892"


def test_les_petites_barres_de_la_tuile_prennent_la_teinte_pale(theme):
    from gui_theme import adoucir
    from gui_widgets import MiniBarres
    jaune = gui_theme.CHART_COLORS["production"]
    barres = MiniBarres([2.0, 4.0], jaune, hauteur=40)
    barres.resize(80, 40)
    image = barres.grab().toImage()
    # Milieu de la premiere barre (la plus basse, donc pale).
    couleur = image.pixelColor(20, 36).name().upper()
    assert couleur == adoucir(jaune).upper(), couleur


def test_le_jour_par_jour_n_estompe_plus_par_transparence():
    """Le graphique jour par jour prend la teinte pale du theme au lieu
    d'un jaune transparent pose sur le fond (qui donnait l'olive)."""
    import inspect

    import views.dashboard as tableau
    source = inspect.getsource(tableau)
    assert 'to_rgba(CC["production"], 0.45)' not in source
    assert "adoucir(" in source


# ── 3. La ligne choisie d'une liste deroulante se voit ─────────────────────

def _lignes_de_la_liste(app, t):
    """Couleur de fond de la ligne choisie et d'une autre, liste ouverte."""
    from PySide6.QtWidgets import QComboBox
    liste = QComboBox()
    liste.addItems(["Toute l'année", "Octobre", "Septembre", "Août"])
    liste.resize(200, 26)
    liste.show()
    liste.setCurrentIndex(1)
    liste.showPopup()
    _attendre(app)
    vue = liste.view()
    fenetre = vue.window()
    image = fenetre.grab().toImage()

    def fond(rang):
        centre = vue.viewport().mapTo(
            fenetre, vue.visualRect(liste.model().index(rang, 0)).center())
        return image.pixelColor(image.width() - 12, centre.y()).name().upper()
    resultat = fond(1), fond(2)
    liste.hidePopup()
    liste.close()
    return resultat


def test_la_ligne_choisie_d_une_liste_se_voit_en_sombre():
    """Audit du 12/10/2026, point 3 : en sombre, la ligne choisie prenait le
    fond de la page, un « trou » a peine plus fonce que la liste (1,29 pour
    1). Elle prend le bleu de selection, texte blanc."""
    from gui_theme import DARK, _contraste
    app = QApplication.instance() or QApplication([])
    ancienne_feuille = app.styleSheet()
    t = choisir_theme("sombre")
    try:
        appliquer_style(app)
        app.setStyleSheet(qss_for(t))
        choisie, autre = _lignes_de_la_liste(app, t)
        assert choisie == DARK["selection"].upper(), choisie
        assert _contraste(choisie, autre) >= 2.0
        assert _contraste(DARK["texte_selection"], choisie) >= 4.5
    finally:
        choisir_theme("clair")
        appliquer_style(app)
        app.setStyleSheet(ancienne_feuille)


def test_la_ligne_choisie_ne_se_decale_pas(theme):
    """Pas de coche devant la ligne choisie : elle decalait ce seul mot."""
    from PySide6.QtWidgets import QComboBox
    app = QApplication.instance()
    liste = QComboBox()
    liste.addItems(["Toute l'année", "Octobre", "Septembre"])
    liste.resize(160, 26)
    liste.show()
    liste.setCurrentIndex(1)
    liste.showPopup()
    _attendre(app)
    vue = liste.view()
    fenetre = vue.window()
    image = fenetre.grab().toImage()

    def premier_pixel_de_texte(rang):
        """Premier pixel qui n'est pas le fond de la ligne, de gauche a
        droite (le fond est lu juste a l'interieur du cadre de la liste)."""
        y = vue.viewport().mapTo(
            fenetre, vue.visualRect(liste.model().index(rang, 0)).center()).y()
        from gui_theme import _contraste
        fond = image.pixelColor(4, y).name()
        for x in range(4, image.width()):
            for dy in range(-3, 4):
                # Une trame infime du fond (1,05 pour 1) n'est pas du texte.
                if _contraste(image.pixelColor(x, y + dy).name(), fond) > 1.5:
                    return x
        return None
    x_choisi = premier_pixel_de_texte(1)
    x_autre = premier_pixel_de_texte(2)
    liste.hidePopup()
    liste.close()
    assert abs(x_choisi - x_autre) <= 3, (x_choisi, x_autre)


# ── 4. Les menus ont un bord ───────────────────────────────────────────────

def _menu_ouvert(app):
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QMenu
    menu = QMenu()
    for libelle in ("Années OA", "Comparer à l'an passé", "Mon fournisseur"):
        menu.addAction(libelle)
    menu.popup(QPoint(0, 0))
    menu.setActiveAction(menu.actions()[1])
    _attendre(app)
    return menu


def test_le_menu_a_un_bord(theme):
    """Audit du 12/10/2026, point 4 : le petit menu « Bilans et
    comparaisons… » avait la couleur de la page et flottait sans limite. Il
    prend le liseré des cartes."""
    app = QApplication.instance()
    menu = _menu_ouvert(app)
    try:
        image = menu.grab().toImage()
        gauche = image.pixelColor(0, image.height() // 2).name().upper()
        assert gauche == theme["cadre"].upper(), gauche
    finally:
        menu.close()


def test_l_entree_survolee_du_menu_se_voit(theme):
    """Le bord ne doit pas effacer la mise en valeur de l'entree survolee."""
    from gui_theme import _contraste
    app = QApplication.instance()
    menu = _menu_ouvert(app)
    try:
        image = menu.grab().toImage()
        actions = menu.actions()
        y_active = menu.actionGeometry(actions[1]).center().y()
        y_autre = menu.actionGeometry(actions[2]).center().y()
        x = image.width() - 6
        active = image.pixelColor(x, y_active).name()
        autre = image.pixelColor(x, y_autre).name()
        assert _contraste(active, autre) >= 1.15, (active, autre)
    finally:
        menu.close()


# ── 5. Un bouton desactive n'a plus l'air cliquable ────────────────────────

def _bord_le_plus_net(widget, fond) -> float:
    """Le contraste le plus fort, sur le fond de la page, parmi les trois
    premieres colonnes de pixels a mi-hauteur : c'est la que passe le bord."""
    from gui_theme import _contraste
    image = widget.grab().toImage()
    y = image.height() // 2
    return max(_contraste(image.pixelColor(x, y).name(), fond)
               for x in range(3))


@pytest.mark.parametrize("nom", ["", "PeriodArrow", "ActionBtn", "combo"])
def test_bouton_actif_bien_cerne_desactive_efface(theme, nom):
    """Audit du 12/10/2026, point 5 : « Ce mois-ci » grise gardait le cadre
    d'un bouton actif. La mesure a montre pire : en sombre, le bord des
    boutons standard (fleches, « Ce mois-ci ») et des menus deroulants
    etait presque invisible (1,08 pour 1). Actif : 3 pour 1 au moins sur la
    page (charte) ; desactive : nettement plus pale."""
    from PySide6.QtWidgets import QComboBox
    app = QApplication.instance()
    fenetre = QWidget()
    couche = QVBoxLayout(fenetre)
    if nom == "combo":
        actif, eteint = QComboBox(), QComboBox()
        for liste in (actif, eteint):
            liste.addItems(["Octobre", "Septembre"])
    else:
        actif, eteint = QPushButton("Ce mois-ci"), QPushButton("Ce mois-ci")
        actif.setObjectName(nom)
        eteint.setObjectName(nom)
    for x in (actif, eteint):
        x.setFocusPolicy(Qt.NoFocus)   # le bord du focus fausserait la mesure
        couche.addWidget(x)
    eteint.setEnabled(False)
    fenetre.show()
    _attendre(app)
    try:
        net_actif = _bord_le_plus_net(actif, theme["bg_app"])
        net_eteint = _bord_le_plus_net(eteint, theme["bg_app"])
        assert net_actif >= 3.0, net_actif
        assert net_eteint <= net_actif * 0.6, (net_actif, net_eteint)
    finally:
        fenetre.close()


# ── 6. Les infobulles prennent les couleurs du theme ───────────────────────

def test_l_infobulle_prend_les_couleurs_du_theme(theme):
    """Audit du 12/10/2026, point 6 : les infobulles n'avaient pas ete vues
    en sombre. Verifie le jour meme : fond et texte de la charte dans les
    deux themes (jaune pale en clair). Ce test les garde."""
    from collections import Counter

    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QToolTip
    app = QApplication.instance()
    bouton = QPushButton("Paramètres")
    bouton.show()
    bouton.activateWindow()
    _attendre(app)
    QToolTip.showText(bouton.mapToGlobal(QPoint(5, 5)),
                      "Votre installation et vos tarifs", bouton)
    _attendre(app)
    try:
        bulles = [w for w in app.allWidgets()
                  if w.metaObject().className() == "QTipLabel"
                  and w.isVisible()]
        assert bulles, "aucune infobulle affichee"
        image = bulles[0].grab().toImage()
        couleurs = Counter(image.pixelColor(x, y).name().upper()
                           for x in range(image.width())
                           for y in range(image.height()))
        fond = couleurs.most_common(1)[0][0]
        assert fond == theme["bulle_bg"].upper(), fond
        assert theme["bulle_texte"].upper() in couleurs
    finally:
        QToolTip.hideText()
        bouton.close()
