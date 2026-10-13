"""Le mode sombre (decision de l'auteur du 12/10/2026).

La palette sombre est commune aux trois applications (charte d'interface,
validee sur maquette le 12/10/2026). Ces tests verifient qu'elle tient les
memes seuils de lisibilite que la claire, qu'elle remplace bien toutes les
couleurs, et que le reglage choisit le bon theme sans jamais suivre Windows.
"""
import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import gui_theme  # noqa: E402
from gui_theme import (  # noqa: E402
    CHART_COLORS,
    DARK,
    LIGHT,
    choisir_theme,
    encre,
    mpl_style,
    nom_du_theme,
    qss_for,
)
from tests.test_contraste import (  # noqa: E402
    CADRES_CLIQUABLES,
    CADRES_DECORATIFS,
    PAIRES,
    contraste,
)


@pytest.fixture
def sombre():
    """Le theme sombre le temps d'un test, puis retour au clair."""
    choisir_theme("sombre")
    yield DARK
    choisir_theme("clair")


def test_chaque_couleur_claire_a_sa_jumelle_sombre():
    assert set(DARK) == set(LIGHT)


@pytest.mark.parametrize("texte, fond", PAIRES)
def test_texte_lisible_en_sombre(texte, fond):
    rapport = contraste(DARK[texte], DARK[fond])
    assert rapport >= 4.5, (
        f"{texte} {DARK[texte]} sur {fond} {DARK[fond]} : {rapport:.2f}")


@pytest.mark.parametrize("texte, fond", [
    ("text_disabled", "bg_app"), ("bulle_texte", "bulle_bg"),
    ("lien", "bg_carte"), ("lien_vu", "bg_carte"),
    ("texte_selection", "selection"), ("texte_selection", "selection_survol"),
    ("text_primary", "jaune_bg"), ("text_primary", "bg_saisie"),
])
def test_textes_ajoutes_lisibles_dans_les_deux_themes(texte, fond):
    """Les couleurs qui etaient ecrites en dur avant le 12/10/2026."""
    for t in (LIGHT, DARK):
        assert contraste(t[texte], t[fond]) >= 4.5, (t["name"], texte, fond)


@pytest.mark.parametrize("cadre, fond", CADRES_CLIQUABLES)
def test_cadre_cliquable_visible_en_sombre(cadre, fond):
    assert contraste(DARK[cadre], DARK[fond]) >= 3.0, (cadre, fond)


@pytest.mark.parametrize("cadre, fond", CADRES_DECORATIFS)
def test_cadre_de_carte_visible_en_sombre(cadre, fond):
    assert contraste(DARK[cadre], DARK[fond]) >= 1.3, (cadre, fond)


def test_le_cadre_des_cases_a_saisir_se_voit_en_sombre():
    """Le bleu qui encadre les cases a remplir de la Saisie : 3 pour 1."""
    for fond in ("bg_saisie", "jaune_bg"):
        assert contraste(DARK["primary"], DARK[fond]) >= 3.0, fond


def test_la_regle_universelle_ecrit_clair_sur_sombre():
    qss = qss_for(DARK)
    bloc = re.search(r"QWidget\s*\{([^}]*)\}", qss).group(1)
    assert DARK["bg_app"] in bloc and DARK["text_primary"] in bloc


def test_la_feuille_sombre_ne_garde_aucune_couleur_claire():
    """Toute couleur propre au clair qui resterait dans la feuille sombre
    serait une tache claire (ou un texte noir) sur l'ecran sombre."""
    qss = qss_for(DARK).upper()
    communes = {v.upper() for k, v in LIGHT.items() if DARK.get(k) == v}
    propres_au_clair = {v.upper() for v in LIGHT.values()
                        if v.startswith("#")} - communes
    restees = sorted(c for c in propres_au_clair if c in qss)
    assert not restees, f"couleurs du clair dans la feuille sombre : {restees}"
    # Ni blanc ni noir ecrits en dur.
    assert "WHITE" not in qss and "#000000" not in qss


def test_les_graphiques_prennent_le_fond_sombre():
    rc = mpl_style(DARK)
    assert rc["figure.facecolor"] == DARK["bg_carte"]
    assert rc["text.color"] == DARK["text_primary"]
    assert rc["hatch.color"] == DARK["text_primary"]


def test_le_reglage_choisit_le_theme():
    class Prefs:
        def __init__(self, valeur):
            self.valeur = valeur

        def value(self, cle):
            assert cle == gui_theme.CLE_THEME
            return self.valeur
    assert nom_du_theme(Prefs("sombre")) == "sombre"
    assert nom_du_theme(Prefs("clair")) == "clair"
    # Une valeur absente ou inconnue : le clair, theme de reference.
    assert nom_du_theme(Prefs(None)) == "clair"
    assert nom_du_theme(Prefs("bleu")) == "clair"


def test_choisir_le_sombre_change_toutes_les_couleurs(sombre):
    assert gui_theme.theme_actif() is DARK
    assert CHART_COLORS == gui_theme.CHART_COLORS_SOMBRE
    assert gui_theme.COULEUR_FAVORABLE == DARK["credit"]
    assert gui_theme.COULEUR_DEFAVORABLE == DARK["debit"]


def test_revenir_au_clair_remet_tout():
    choisir_theme("sombre")
    choisir_theme("clair")
    assert gui_theme.theme_actif() is LIGHT
    assert CHART_COLORS == gui_theme.CHART_COLORS_CLAIR
    assert gui_theme.COULEUR_FAVORABLE == LIGHT["credit"]


@pytest.mark.parametrize("serie", sorted(gui_theme.CHART_COLORS_SOMBRE))
def test_les_series_se_voient_sur_la_carte_sombre(serie):
    """Une barre porte une information : 3 pour 1 sur son fond (charte)."""
    couleur = gui_theme.CHART_COLORS_SOMBRE[serie]
    assert contraste(couleur, DARK["bg_carte"]) >= 3.0, (serie, couleur)


@pytest.mark.parametrize("serie", sorted(gui_theme.CHART_COLORS_SOMBRE))
def test_l_encre_sombre_eclaircit_et_se_lit(sombre, serie):
    couleur = gui_theme.CHART_COLORS_SOMBRE[serie]
    trace = encre(couleur)
    for fond in ("bg_panel", "table_row_alt", "bg_carte"):
        assert contraste(trace, DARK[fond]) >= 4.5, (serie, trace, fond)


def test_les_annees_des_statistiques_se_voient_en_sombre():
    from views.stats import COULEURS_ANNEES_SOMBRE
    for couleur in COULEURS_ANNEES_SOMBRE:
        assert contraste(couleur, DARK["bg_carte"]) >= 3.0, couleur


def test_la_palette_qt_sombre_ignore_windows(sombre):
    """Comme pour le clair : tout est remplace, fonds ET textes, quel que
    soit le reglage de Windows."""
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QApplication

    from gui_theme import appliquer_style
    app = QApplication.instance() or QApplication([])
    ancienne = app.palette()
    claire = QPalette()
    for role in (QPalette.WindowText, QPalette.Text):
        claire.setColor(role, QColor("#000000"))
    app.setPalette(claire)
    try:
        appliquer_style(app)
        pal = app.palette()
        assert pal.color(QPalette.Window).name().upper() == DARK["bg_app"]
        assert pal.color(QPalette.WindowText).name().upper() == DARK["text_primary"]
        assert pal.color(QPalette.Base).name().upper() == DARK["bg_saisie"]
        assert pal.color(QPalette.ToolTipBase).name().upper() == DARK["bulle_bg"]
    finally:
        choisir_theme("clair")
        appliquer_style(app)
        app.setPalette(ancienne)


def _couleurs_du_rond(app):
    """Les couleurs peintes dans le rond d'un bouton radio decoche."""
    from PySide6.QtWidgets import QRadioButton
    bouton = QRadioButton("Sombre")
    bouton.resize(120, 24)
    image = bouton.grab().toImage()
    return {image.pixelColor(x, y).name().upper()
            for x in range(0, 22) for y in range(0, 24)}


@pytest.mark.parametrize("nom", ["clair", "sombre"])
def test_le_rond_des_boutons_radio_a_un_contour_lisible(nom):
    """12/10/2026 : en sombre, le rond du choix Clair / Sombre se voyait a
    peine (Fusion le cerne d'un fond a peine plus fonce que la page). Comme
    dans Pecule, le contour des controles de la charte (3 pour 1)."""
    from PySide6.QtWidgets import QApplication

    from gui_theme import appliquer_style
    app = QApplication.instance() or QApplication([])
    ancienne = app.palette()
    ancienne_feuille = app.styleSheet()
    app.setStyleSheet("")          # lire le style sans intermediaire
    t = choisir_theme(nom)
    try:
        appliquer_style(app)
        assert t["cadre_controle"].upper() in _couleurs_du_rond(app)
        from tests.test_contraste import _nom_du_style
        assert _nom_du_style(app).lower() == "fusion"
    finally:
        choisir_theme("clair")
        appliquer_style(app)
        app.setPalette(ancienne)
        app.setStyleSheet(ancienne_feuille)


@pytest.mark.parametrize("classe", ["QSpinBox", "QDoubleSpinBox", "QLineEdit",
                                    "QDateEdit"])
def test_les_cases_de_saisie_ont_un_bord_en_sombre(classe):
    """12/10/2026 : dans « Mes réglages », en sombre, les cases de saisie
    n'avaient pas de bord visible (Fusion le tire du fond de la page,
    presque noir) : on voyait mal ou taper. Le contour des controles de la
    charte, 3 pour 1."""
    from PySide6 import QtWidgets
    from PySide6.QtWidgets import QApplication

    from gui_theme import appliquer_style
    app = QApplication.instance() or QApplication([])
    ancienne = app.palette()
    ancienne_feuille = app.styleSheet()
    t = choisir_theme("sombre")
    try:
        appliquer_style(app)
        app.setStyleSheet(qss_for(t))
        case = getattr(QtWidgets, classe)()
        case.resize(160, 28)
        image = case.grab().toImage()
        bord = {image.pixelColor(x, image.height() // 2).name().upper()
                for x in range(0, 3)}
        assert t["cadre_controle"].upper() in bord, bord
    finally:
        choisir_theme("clair")
        appliquer_style(app)
        app.setPalette(ancienne)
        app.setStyleSheet(ancienne_feuille)


# --- Reglage abime ou non enregistre (audit du 13/10/2026) -------------------

def test_un_reglage_abime_donne_le_clair_sans_planter(tmp_path):
    """« theme=clair, sombre » se lit comme une liste : le test « in THEMES »
    levait TypeError, avant le demarrage de la fenetre."""
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    ini = tmp_path / "prefs.ini"
    ini.write_text("[ui]\ntheme=clair, sombre\n", encoding="utf-8")
    prefs = QSettings(str(ini), QSettings.Format.IniFormat)
    assert nom_du_theme(prefs) == "clair"


class _PrefsEnLectureSeule:
    """Preferences dont l'ecriture echoue (fichier verrouille)."""

    def __init__(self, statut):
        self.statut = statut
        self.valeurs = {}

    def setValue(self, cle, valeur):
        self.valeurs[cle] = valeur

    def sync(self):
        pass

    def status(self):
        return self.statut

    def value(self, cle, defaut=None):
        return self.valeurs.get(cle, defaut)


def _choisir(monkeypatch, statut):
    from types import SimpleNamespace

    import app_desktop
    messages = []
    monkeypatch.setattr(
        app_desktop.QMessageBox, "information",
        staticmethod(lambda *a, **k: messages.append(("info", a[2]))))
    monkeypatch.setattr(
        app_desktop.QMessageBox, "warning",
        staticmethod(lambda *a, **k: messages.append(("alerte", a[2]))))
    fenetre = SimpleNamespace(settings=_PrefsEnLectureSeule(statut),
                              _apparence_choisie=lambda: "clair")
    app_desktop.MainWindow._choisir_apparence(fenetre, "sombre")
    return messages


def test_choix_du_theme_non_enregistre_est_dit(monkeypatch):
    from PySide6.QtCore import QSettings
    messages = _choisir(monkeypatch, QSettings.Status.AccessError)
    assert [genre for genre, _ in messages] == ["alerte"]
    assert "pas pu être enregistré" in messages[0][1]


def test_choix_du_theme_enregistre_est_annonce(monkeypatch):
    from PySide6.QtCore import QSettings
    messages = _choisir(monkeypatch, QSettings.Status.NoError)
    assert [genre for genre, _ in messages] == ["info"]
    assert "prochain démarrage" in messages[0][1]
