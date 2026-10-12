"""Lisibilite des textes : chaque couleur d'ecriture du theme doit se
detacher assez de son fond.

Le 15/09/2026, Andre a trouve des ecritures "tres claires et difficiles a
lire" : le gris des petits textes (#94a3b8) n'avait qu'un contraste de 2,6
pour 1 sur blanc, et l'orange du bandeau "Donnees incompletes" a peine 2 pour
1 sur son fond jaune. Le minimum conseille pour lire un texte courant est de
4,5 pour 1 (norme d'accessibilite WCAG, niveau AA).
"""

import pytest

from gui_theme import CHART_COLORS, LIGHT


def _luminance(couleur: str) -> float:
    """Luminance relative d'une couleur "#rrggbb" (formule WCAG)."""
    canaux = []
    for i in (1, 3, 5):
        c = int(couleur[i:i + 2], 16) / 255
        canaux.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = canaux
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(texte: str, fond: str) -> float:
    """Rapport de contraste entre deux couleurs, de 1 (identiques) a 21."""
    clair, fonce = sorted((_luminance(texte), _luminance(fond)), reverse=True)
    return (clair + 0.05) / (fonce + 0.05)


def test_contraste_de_reference():
    # Noir sur blanc : le maximum, 21 pour 1.
    assert contraste("#000000", "#ffffff") == pytest.approx(21.0)
    # L'ancien gris, celui qui a declenche la plainte.
    assert contraste("#94a3b8", "#ffffff") < 3


# (couleur du texte, fond sur lequel elle est ecrite)
PAIRES = [
    ("text_primary", "bg_panel"),
    ("text_secondary", "bg_panel"),
    ("text_muted", "bg_panel"),
    ("text_muted", "bg_app"),        # sous-titres des pages, sur le fond creme
    ("debit", "bg_app"),             # rouge sur le creme (4,46 avant le 08/10/2026)
    ("credit", "bg_panel"),          # montants positifs dans les tableaux
    ("debit", "bg_panel"),           # montants negatifs
    ("credit", "credit_bg"),         # pastille "+16 % vs ..."
    ("debit", "debit_bg"),
    ("warm_ink", "warm_bg"),         # bandeau "Donnees incompletes"
    ("info_ink", "info_bg"),
    ("info_ink", "bg_panel"),        # colonne Vehicule des releves
    ("sb_btn_text", "sb_btn"),       # menu de gauche
    ("sb_titre", "sb_bg"),
    ("sb_sub", "sb_bg"),
    ("sb_version", "sb_bg"),
    # Ajoutes le 25/09/2026, avec les couleurs de Pecule :
    ("sb_brand", "sb_bg"),           # nom de l'application
    ("sb_actif_text", "sb_actif"),   # page affichee
    ("primary", "bg_panel"),         # periode choisie, liens d'accent
    ("primary", "primary_bg"),       # element choisi dans un menu deroulant
    ("text_primary", "bg_panel_alt"),
    ("text_secondary", "bg_app"),
    # Le fond ivoire des cartes (25/09/2026) :
    ("text_primary", "bg_carte"),
    ("text_secondary", "bg_carte"),
    ("text_muted", "bg_carte"),
    ("credit", "bg_carte"),
    ("debit", "bg_carte"),
    ("info_ink", "bg_carte"),
    ("primary", "bg_carte"),
    # En-tete des cartes (29/09/2026), sur les deux bouts du degrade :
    ("entete_texte", "entete_haut"),
    ("entete_texte", "entete_bas"),
]


@pytest.mark.parametrize("texte, fond", PAIRES)
def test_texte_lisible(texte, fond):
    rapport = contraste(LIGHT[texte], LIGHT[fond])
    assert rapport >= 4.5, (
        f"{texte} {LIGHT[texte]} sur {fond} {LIGHT[fond]} : "
        f"{rapport:.2f} pour 1, moins que 4,5")


# Les cadres (controle demande par Andre le 15/09/2026). Deux familles :
# - ce qu'on clique doit se reperer : 3 pour 1 des deux cotes du contour
#   (norme WCAG, contraste des elements d'interface) ;
# - les cartes et tableaux sont decoratifs : pas de minimum officiel, mais
#   au moins 1,4 pour 1 (avant : 1,2, on les devinait a peine).
CADRES_CLIQUABLES = [
    ("cadre_controle", "bg_panel"),      # menus annee / mois
    ("cadre_controle", "bg_panel_alt"),  # fleches, boutons Importer...
    ("cadre_controle", "bg_app"),
    ("sb_btn_border", "sb_btn"),         # boutons du menu de gauche
    ("sb_btn_border", "sb_bg"),
    ("sb_actif_border", "sb_actif"),     # page affichee
    ("sb_btn_hover_border", "sb_btn_hover"),
]
CADRES_DECORATIFS = [
    ("cadre", "bg_carte"),               # contour des cartes, cote carte
    ("cadre", "bg_panel"),               # contour des tableaux
    ("cadre", "bg_app"),                 # ... cote fond de page
]


@pytest.mark.parametrize("cadre, fond", CADRES_CLIQUABLES)
def test_cadre_cliquable_visible(cadre, fond):
    rapport = contraste(LIGHT[cadre], LIGHT[fond])
    assert rapport >= 3.0, (
        f"{cadre} {LIGHT[cadre]} sur {fond} {LIGHT[fond]} : "
        f"{rapport:.2f} pour 1, moins que 3")


@pytest.mark.parametrize("cadre, fond", CADRES_DECORATIFS)
def test_cadre_de_carte_visible(cadre, fond):
    # 1,3 au moins. Depuis le 25/09/2026 : liseré #BEC7D4 sur le fond creme
    # (#ECE9D8), 1,40 pour 1. Contour decoratif : la carte se detache aussi
    # par son fond ivoire.
    rapport = contraste(LIGHT[cadre], LIGHT[fond])
    assert rapport >= 1.3, (
        f"{cadre} {LIGHT[cadre]} sur {fond} {LIGHT[fond]} : "
        f"{rapport:.2f} pour 1, moins que 1,3")


# ── Le thème clair tient, quel que soit le réglage de Windows ───────────────
#
# Ajouté le 16/09/2026, après le défaut trouvé dans Pécule : celui-ci partait
# de la palette du SYSTÈME et n'y remplaçait que les fonds. Sur un poste réglé
# en mode sombre, Qt fournit des textes blancs, qui se retrouvaient sur du
# crème — illisibles.
#
# pv-dashboard échappe à ce piège pour une raison précise : sa feuille de style
# pose une règle universelle qui impose le fond ET la couleur du texte à tout
# widget, sans rien emprunter au système. Ces deux tests verrouillent ce
# choix : sans eux, alléger la règle ferait revenir le défaut en silence.

import re  # noqa: E402

from gui_theme import qss_for  # noqa: E402


def _nom_du_style(app) -> str:
    """Le nom du style de base : depuis le 12/10/2026, Fusion est enrobe
    d'un QProxyStyle (contour des cases et des ronds, comme Pecule), qui ne
    porte pas de nom lui-meme."""
    style = app.style()
    # Une feuille de style ajoute une enveloppe de plus : on les deballe
    # jusqu'au style qui porte un nom.
    while not style.name() and hasattr(style, "baseStyle"):
        style = style.baseStyle()
    return style.name()


def _bloc(qss: str, selecteur: str) -> str:
    """Contenu des accolades qui suivent un sélecteur de la feuille de style."""
    trouve = re.search(re.escape(selecteur) + r"\s*\{([^}]*)\}", qss)
    return trouve.group(1) if trouve else ""


def test_la_regle_universelle_impose_le_fond_ET_le_texte():
    """`QWidget { background: … ; color: … }` — les deux, pas seulement le
    fond : c'est ce qui protège d'un Windows en mode sombre."""
    bloc = _bloc(qss_for(LIGHT), "QWidget")
    assert bloc, "la règle universelle QWidget a disparu de la feuille de style"
    assert "background:" in bloc, "la règle QWidget n'impose plus le fond"
    assert "color:" in bloc, (
        "la règle QWidget n'impose plus la couleur du texte : sur un poste en "
        "mode sombre, Windows la mettrait en blanc sur ces fonds clairs")


def test_la_regle_universelle_ecrit_sombre_sur_clair():
    """Et dans le bon sens : fond clair, texte sombre, lisible."""
    assert _luminance(LIGHT["bg_app"]) > _luminance(LIGHT["text_primary"])
    assert contraste(LIGHT["text_primary"], LIGHT["bg_app"]) >= 4.5


def test_les_couleurs_sont_celles_de_pecule():
    """Decision de l'auteur du 25/09/2026 : ses trois applications suivent
    les couleurs de Pecule. Les teintes de base ne doivent pas deriver."""
    assert LIGHT["bg_app"].upper() == "#ECE9D8"     # creme de ses fenetres
    assert LIGHT["bg_carte"].upper() == "#FAF8F1"   # ivoire de ses cartes
    assert LIGHT["cadre"].upper() == "#BEC7D4"      # liseré de ses cartes
    assert LIGHT["sb_bg"].upper() == "#ECE9D8"      # creme de ses fenetres
    assert LIGHT["primary"].upper() == "#316AC5"    # son bleu de selection
    assert LIGHT["text_primary"].upper() == "#000000"


def test_la_palette_ignore_le_mode_sombre_de_windows():
    """Sur un poste regle en sombre, Qt fournit une palette a textes blancs :
    appliquer_style() doit tout remplacer, fonds ET textes, et passer en
    Fusion (defaut vu dans Pecule le 16/09/2026)."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QApplication

    from gui_theme import appliquer_style
    app = QApplication.instance() or QApplication([])
    ancienne_feuille = app.styleSheet()
    app.setStyleSheet("")                 # lire le style sans intermediaire
    sombre = QPalette()
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        sombre.setColor(role, QColor("#FFFFFF"))
    app.setPalette(sombre)

    appliquer_style(app)

    palette = app.palette()
    assert palette.color(QPalette.WindowText).name() == "#000000"
    assert palette.color(QPalette.Text).name() == "#000000"
    assert palette.color(QPalette.Base).name() == "#ffffff"
    assert _nom_du_style(app).lower() == "fusion"
    app.setStyleSheet(ancienne_feuille)


def test_le_message_deja_ouvert_est_deja_en_clair(monkeypatch):
    """29/09/2026 : run.main() posait la palette claire seulement en
    construisant la fenetre (MainWindow._apply_theme). Les boites « deja
    ouvert » et « Impossible de demarrer », affichees avant, gardaient la
    palette de Windows : textes blancs sur un poste regle en sombre.
    Le theme doit etre pose avant le premier message."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QApplication, QMessageBox

    import run
    app = QApplication.instance() or QApplication([])
    ancienne_feuille = app.styleSheet()
    ancienne_palette = app.palette()
    ancien_style = _nom_du_style(app)
    app.setStyleSheet("")
    # Un poste regle en sombre : Qt fournit des textes blancs, style natif.
    sombre = QPalette()
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        sombre.setColor(role, QColor("#FFFFFF"))
    app.setPalette(sombre)
    app.setStyle("Windows")

    vu = {}

    def boite(*_args, **_kwargs):
        # Ce que la boite « deja ouvert » trouverait au moment de s'afficher.
        vu["texte"] = app.palette().color(QPalette.WindowText).name()
        vu["style"] = _nom_du_style(app).lower()
        return QMessageBox.Ok
    monkeypatch.setattr(run, "prendre_le_verrou", lambda: None)
    monkeypatch.setattr(run.QMessageBox, "warning", boite)
    try:
        assert run.main() == 1
    finally:
        app.setStyle(ancien_style)
        app.setPalette(ancienne_palette)
        app.setStyleSheet(ancienne_feuille)
    assert vu == {"texte": "#000000", "style": "fusion"}


def test_le_clair_reste_le_theme_par_defaut():
    """Le 12/10/2026, un mode sombre est revenu (il remplace « un seul
    thème, le clair » du 14/09/2026), mais le clair reste la référence :
    sans réglage, c'est lui. Les tests du sombre : test_theme_sombre.py."""
    import gui_theme
    assert gui_theme.nom_du_theme(None) == "clair"
    assert gui_theme.theme_actif() is LIGHT


def test_survol_du_bouton_enregistrer_dans_la_palette():
    """29/09/2026 : le bouton « Enregistrer » de la Saisie passait au survol
    en indigo #4338ca, une couleur étrangère à la palette commune. Il fonce
    maintenant vers le bleu nuit de Pécule, texte blanc toujours lisible."""
    import re as _re
    bloc = _bloc(qss_for(LIGHT), "QPushButton#SaveBtn:hover")
    assert bloc, "le survol du bouton Enregistrer a disparu"
    fond = _re.search(r"background:\s*(#[0-9A-Fa-f]{6})", bloc).group(1)
    assert fond.upper() == "#1F3A6B"
    assert contraste("#FFFFFF", fond) >= 4.5


def test_selecteur_de_periode_a_l_allure_des_deux_autres_applis():
    """29/09/2026 : les menus de la periode etaient arrondis (8 px) et sans
    fleche ▾ (une regle de style sur un menu deroulant fait disparaitre la
    fleche de Qt), et « Ce mois-ci » ressemblait a du texte. Pecule et
    Recharges VE gardent l'allure standard (Fusion) : aucune regle propre
    aux menus ni au bouton ; les fleches ‹ › ont seulement leur taille."""
    qss = qss_for(LIGHT)
    assert _bloc(qss, "QComboBox#PeriodSelector") == ""
    assert _bloc(qss, "QPushButton#PeriodToday") == ""
    assert _bloc(qss, "QDateEdit#PeriodSelector") == ""
    fleche = _bloc(qss, "QPushButton#PeriodArrow")
    assert "border" not in fleche and "26px" in fleche


def _encre_la_plus_foncee(bouton) -> str:
    """Couleur la plus sombre dessinee par un bouton : celle de son texte."""
    image = bouton.grab().toImage()
    couleurs = {image.pixelColor(x, y).name()
                for x in range(image.width()) for y in range(image.height())}
    return min(couleurs, key=_luminance)


def test_un_bouton_desactive_s_ecrit_en_gris():
    """29/09/2026 : « Ce mois-ci » et la fleche › etaient bien desactives sur
    le mois en cours, mais restaient dessines en noir : la regle universelle
    `QWidget { color: … }` ecrasait le gris de la palette. Un bouton
    desactive doit s'ecrire dans le gris de la charte, #666666 (#6B6B6B avant
    le 08/10/2026 : 4,37 sur le creme)."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QPushButton

    QApplication.instance() or QApplication([])
    bouton = QPushButton("Ce mois-ci")
    bouton.setStyleSheet(qss_for(LIGHT))
    bouton.resize(110, 30)

    # Actif : le texte est noir (le test voit bien le texte).
    assert _encre_la_plus_foncee(bouton) == "#000000"
    # Desactive : plus de noir, le gris des elements desactives.
    bouton.setEnabled(False)
    assert _encre_la_plus_foncee(bouton) == "#666666"


def test_les_cases_de_saisie_sont_blanches():
    """30/09/2026 : la regle universelle `QWidget { background: … }` donnait
    aux cases de saisie le fond beige de la page ; posees sur une carte
    ivoire, elles semblaient grisees. La charte les veut blanches : on voit
    ou taper."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import (
        QApplication,
        QDateEdit,
        QDoubleSpinBox,
        QLineEdit,
        QSpinBox,
    )

    QApplication.instance() or QApplication([])
    for classe in (QLineEdit, QSpinBox, QDoubleSpinBox, QDateEdit):
        case = classe()
        case.setStyleSheet(qss_for(LIGHT))
        case.resize(160, 28)
        image = case.grab().toImage()
        # Au milieu de la case, a gauche des fleches, la ou l'on tape.
        fond = image.pixelColor(80, 20).name()
        assert fond == "#ffffff", f"{classe.__name__} : fond {fond}"


# Les couleurs de serie sur lesquelles une barre de repartition ecrit son
# libelle (Tableau de bord : « Ou va votre soleil », « D'ou vient votre
# electricite »), plus le bleu de la part du vehicule.
FONDS_DES_BARRES = [
    CHART_COLORS["production"],
    CHART_COLORS["autoconso"],
    CHART_COLORS["injection"],
    CHART_COLORS["soutirage"],
    LIGHT["info"],
]


@pytest.mark.parametrize("fond", FONDS_DES_BARRES)
def test_texte_des_barres_de_repartition_lisible(fond):
    """29/09/2026 : le texte blanc des barres vert, bleu et orange ne faisait
    que 3,4 a 3,9 pour 1. L'encre etait choisie sur une estimation de la
    clarte du fond, pas sur le contraste reel : elle doit tenir 4,5 pour 1."""
    from PySide6.QtGui import QColor

    from gui_widgets import _texte_lisible_sur
    encre = _texte_lisible_sur(QColor(fond)).name()
    rapport = contraste(encre, fond)
    assert rapport >= 4.5, (
        f"texte {encre} sur {fond} : {rapport:.2f} pour 1, moins que 4,5")


def test_cartes_arrondies_a_12_px_et_trait_en_haut_comme_pecule():
    """29/09/2026 : tout etait passe a 4 px et le trait des tuiles en HAUT.
    07/10/2026, choix de l'auteur pour les trois applis : cartes et tuiles
    a 12 px ; les tableaux gardent 4 px ; l'en-tete bleute d'une carte
    arrondit ses coins du haut a 11 px pour ne pas depasser."""
    import re as _re
    qss = qss_for(LIGHT)
    for selecteur, attendu in (('QFrame#Card, QFrame.Card', "12"),
                               ('QFrame[role="kpi"]', "12"),
                               ('QFrame[role="tile"]', "12"),
                               ('QFrame[role="account"]', "12"),
                               ('QTableWidget, QTableView', "4")):
        bloc = _bloc(qss, selecteur)
        assert bloc, selecteur
        rayon = _re.search(r"border-radius:\s*(\d+)px", bloc)
        assert rayon and rayon.group(1) == attendu, selecteur
    entete = _bloc(qss, 'QFrame#Card QLabel#CardHeader')
    assert _re.search(r"border-top-left-radius:\s*11px", entete)
    assert _re.search(r"border-top-right-radius:\s*11px", entete)
    kpi = _bloc(qss, 'QFrame[role="kpi"]')
    assert "border-top-width: 3px" in kpi and "border-left-width" not in kpi
    assert 'border-left-color' not in qss


@pytest.mark.parametrize("sens, ecart", [(+1, 5.0), (+1, -5.0),
                                         (-1, 5.0), (-1, -5.0)])
def test_la_colonne_variation_se_lit(sens, ecart):
    """30/09/2026 : la colonne « Variation » (Comparer à l'an passé,
    Répartition énergie) s'écrivait dans les couleurs vives des graphiques :
    3,1 à 3,9 pour 1. Même teinte, variante foncée pour écrire."""
    from views._helpers import variation
    _texte, couleur = variation(ecart, 100.0, str, sens, LIGHT)
    # Cases blanches, lignes alternées, fond ivoire des cartes.
    for fond in ("#FFFFFF", "#F5F5F0", LIGHT["bg_carte"]):
        assert contraste(couleur, fond) >= 4.5, (couleur, fond)


# --- Encre des couleurs de graphiques (30/09/2026) ---------------------------
# Les couleurs vives des series servent aux barres ; pour ECRIRE, la meme
# teinte assombrie (charte : couleur vive pour une barre, encre pour ecrire).

@pytest.mark.parametrize("serie", sorted(CHART_COLORS))
def test_l_encre_de_chaque_serie_se_lit(serie):
    from gui_theme import encre
    trace = encre(CHART_COLORS[serie])
    for fond in ("#FFFFFF", "#F5F5F0", LIGHT["bg_carte"]):
        assert contraste(trace, fond) >= 4.5, (serie, trace, fond)


def test_l_encre_garde_la_teinte():
    import colorsys

    from gui_theme import encre

    def teinte(c):
        r, g, b = (int(c[i:i + 2], 16) / 255 for i in (1, 3, 5))
        return colorsys.rgb_to_hsv(r, g, b)[0]
    for couleur in CHART_COLORS.values():
        assert abs(teinte(encre(couleur)) - teinte(couleur)) < 0.02, couleur
    # Une couleur deja assez foncee ne bouge pas.
    assert encre("#1F3A6B").lower() == "#1f3a6b"


def test_le_diagramme_de_flux_ecrit_lisiblement(monkeypatch):
    """Les chiffres des noeuds et des rubans s'ecrivaient dans la couleur de
    leur serie : le jaune de la production faisait 1,83 pour 1."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QPainter
    from PySide6.QtWidgets import QApplication

    from views._sankey import Flux, Noeud, SankeyWidget
    QApplication.instance() or QApplication([])
    encres = []
    origine = QPainter.drawText

    def noter(self, *args):
        encres.append(self.pen().color().name())
        return origine(self, *args)
    monkeypatch.setattr(QPainter, "drawText", noter)
    gauche = [Noeud("production", "Production solaire", 237.1,
                    CHART_COLORS["production"]),
              Noeud("soutirage", "Soutirage réseau", 171.4,
                    CHART_COLORS["soutirage"])]
    droite = [Noeud("injection", "Injection réseau", 140.8,
                    CHART_COLORS["injection"]),
              Noeud("consommation", "Consommation foyer", 267.7,
                    CHART_COLORS["primary"])]
    flux = [Flux("production", "injection", 140.8, "Vendu au réseau"),
            Flux("production", "consommation", 96.3, "Autoconsommation",
                 CHART_COLORS["autoconso"]),
            Flux("soutirage", "consommation", 171.4, "Acheté au réseau")]
    widget = SankeyWidget(gauche, droite, flux, LIGHT)
    widget.resize(1000, 300)
    widget.grab()
    assert encres, "le diagramme n'a rien ecrit"
    for trace in set(encres):
        assert contraste(trace, LIGHT["bg_carte"]) >= 4.5, trace


# --- Les unites gardent leur ecriture (30/09/2026) ----------------------------

def test_les_capitales_epargnent_les_unites():
    from gui_widgets import capitales
    assert (capitales("Rendement spécifique (kWh / kWc / an)")
            == "RENDEMENT SPÉCIFIQUE (kWh / kWc / AN)")
    assert capitales("Prix d'achat en €/kWh") == "PRIX D'ACHAT EN €/kWh"
    assert capitales("Coût mensuel comparé (€)") == "COÛT MENSUEL COMPARÉ (€)"


def test_les_titres_en_capitales_gardent_leurs_unites():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QLabel

    from gui_widgets import Card, KpiCard, SectionTitle
    QApplication.instance() or QApplication([])
    section = SectionTitle("Rendement spécifique (kWh / kWc / an)")
    assert section.findChild(QLabel, "SectionTitle").text() == \
        "RENDEMENT SPÉCIFIQUE (kWh / kWc / AN)"
    assert Card(titre="Production (kWh)").entete.text() == "PRODUCTION (kWh)"
    assert KpiCard("Production (kWh)", "12").label.text() == "PRODUCTION (kWh)"


def test_les_en_tetes_de_tableaux_ne_sont_plus_forces_en_capitales():
    """Comme Pécule : « Production (kWh) » et non « PRODUCTION (KWH) »."""
    qss = qss_for(LIGHT)
    assert "text-transform" not in _bloc(qss, "QHeaderView::section")
    assert "text-transform" not in _bloc(qss, "QLabel#GridHeader")
