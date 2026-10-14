"""
Palette claire (celle de Pecule) + generation du QSS Qt + style matplotlib
associe + style Fusion et palette Qt qui resistent au mode sombre de Windows.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QLibraryInfo, QRectF, Qt, QTranslator
from PySide6.QtGui import QColor, QPalette, QPen
from PySide6.QtWidgets import QProxyStyle, QStyle, QStyleFactory, QToolTip


def installer_traduction_qt(app) -> bool:
    """Passe en francais les boutons et menus fournis par Qt lui-meme
    (« Yes / No » des questions, clic droit « Undo, Cut, Copy... »).

    Repris de Pecule et de Recharges VE, qui le faisaient deja ; ici, il
    manquait jusqu'a la 1.50.0 (diagnostic du 26/09/2026). Qt livre ses
    traductions (`qtbase_fr.qm`) : on les charge plutot que de renommer les
    boutons un par un. Le traducteur est range sur `app`, sinon il serait
    ramasse par Python et cesserait de traduire. Un second appel ne fait
    rien. Rend False si le fichier est introuvable : l'application demarre
    quand meme, en anglais pour ces quelques mots."""
    if getattr(app, "_traducteur_qt", None) is not None:
        return True
    chemins = [QLibraryInfo.path(QLibraryInfo.TranslationsPath)]
    # Second recours : le dossier livre avec PySide6, que PyInstaller recopie
    # dans `_internal/PySide6/translations/`.
    try:
        import PySide6
        chemins.append(os.path.join(os.path.dirname(PySide6.__file__),
                                    "translations"))
    except Exception:
        pass
    for dossier in chemins:
        if not dossier or not os.path.isdir(dossier):
            continue
        traducteur = QTranslator(app)
        if traducteur.load("qtbase_fr", dossier):
            app.installTranslator(traducteur)
            app._traducteur_qt = traducteur   # garde une reference vivante
            return True
    return False

# Les couleurs de Pecule (decision de l'auteur du 25/09/2026 : ses trois
# applications suivent Pecule — comptesbudget/app.py, ui/main_window.py,
# ui/views/bilan.py). Fond gris clair sous des cartes blanches a liseré
# gris-bleu, texte noir, bleu nuit et bleu de selection pour les accents,
# bandeau creme. Trois exceptions assumees, pour rester lisible : voir
# « fonce » ci-dessous (tests/test_contraste.py).
LIGHT = {
    "name":           "light",
    # Fond des pages : le creme du menu de gauche, et cartes en ivoire. Le
    # gris-bleu et le blanc pur d'avant juraient avec le reste de
    # l'application (demande de l'auteur, 25/09/2026 ; memes couleurs dans
    # Pecule et Recharges VE).
    "bg_app":         "#ECE9D8",   # fond des pages
    "bg_carte":       "#FAF8F1",   # cartes, tuiles, graphiques
    "bg_panel":       "#FFFFFF",   # tableaux, champs, listes
    "bg_panel_alt":   "#F5F5F0",   # une ligne sur deux, boutons secondaires
    # Grilles des graphiques et fond des jauges : doivent rester discrets.
    "border":         "#E2E8F0",
    "border_strong":  "#C8D0DC",
    # Contour des cartes et des tableaux : le liseré des cartes de Pecule,
    # fonce d'un cran (#C8D0DC -> #BEC7D4) le 25/09/2026 pour rester visible
    # sur le fond creme (1,40 pour 1 au lieu de 1,27).
    "cadre":          "#BEC7D4",
    # Contour de ce qu'on clique (boutons, menus de periode) : 3 pour 1
    # au moins sur son fond, le minimum conseille pour un element actif
    # (regle du 15/09/2026, gardee : Pecule n'a pas d'equivalent). Fonce d'un
    # cran le 25/09/2026 : le fond gris de Pecule est plus soutenu que l'ancien.
    "cadre_controle": "#6F7885",
    "text_primary":   "#000000",   # le texte courant de Pecule
    "text_secondary": "#555555",   # lignes secondaires des tuiles de Pecule
    "text_muted":     "#666666",   # intitules des tuiles de Pecule
    # Vert et rouge des montants (ceux de Pecule). Le vert est fonce d'un cran :
    # le #229954 de Pecule ne fait que 3,5 pour 1 sur blanc.
    "credit":         "#18733A",
    "credit_bg":      "#E6F4EA",
    "debit":          "#BC3729",
    "debit_bg":       "#FDEDEB",
    # Accent : le bleu de selection de Pecule.
    "primary":        "#316AC5",
    "primary_bg":     "#E8EEF7",   # haut du degrade des en-tetes de Pecule
    # Orange des alertes de Pecule : vif pour les bordures, « encre » pour
    # ECRIRE en orange (bandeaux, pastilles).
    "warm":           "#E67E22",
    "warm_bg":        "#FEF5E7",
    "warm_ink":       "#7E5109",
    # Bleu d'information : celui des en-tetes de carte de Pecule.
    "info":           "#316AC5",
    "info_bg":        "#E8EEF7",
    "info_ink":       "#1F3A6B",
    "table_row_alt":  "#F5F5F0",
    # En-tete des cartes (29/09/2026) : le bandeau degrade de Pecule, titre
    # bleu nuit, filet dessous (comptesbudget/ui/views/bilan.py).
    "entete_haut":    "#E8EEF7",
    "entete_bas":     "#C9D6E8",
    "entete_texte":   "#1F3A6B",
    "entete_filet":   "#B0BFD3",
    "shadow":         "rgba(15, 23, 42, 0.06)",
    # Bandeau de gauche : celui de Pecule.
    "sb_bg":               "#ECE9D8",
    "sb_btn":              "#FCFCFC",
    # Contours du menu : ceux de Pecule (#DCDCDC) ne font que 1,3 pour 1.
    # Fonces le 15/09/2026 pour atteindre 3 pour 1, et garde ainsi (un cran
    # de plus le 25/09/2026 : le creme de Pecule est plus soutenu).
    "sb_btn_border":       "#808080",
    "sb_btn_text":         "#222222",
    "sb_btn_hover":        "#EAF2FB",
    # Survol et page affichee : le bleu de selection de Pecule, plus marque
    # que son bleu pale #9CC0E8 (1,6 pour 1 seulement).
    "sb_btn_hover_border": "#316AC5",
    "sb_btn_pressed":      "#D8E7F7",
    "sb_actif":            "#D8E7F7",
    "sb_actif_border":     "#316AC5",
    "sb_actif_text":       "#1F3A6B",
    # Titres de section : #6E6E6E dans Pecule, qui ne fait que 4,2 pour 1
    # sur le creme — fonce d'un cran.
    "sb_titre":            "#5A5A5A",
    "sb_titre_filet":      "#A9A9A9",
    "sb_brand":            "#1F3A6B",   # le bleu nuit de Pecule
    "sb_sub":              "#5A5A5A",
    "sb_version":          "#5A5A5A",
    # Ajoutees le 12/10/2026 avec le mode sombre : des couleurs jusque-la
    # ecrites en dur dans la feuille de style, la palette Qt et les vues.
    "text_disabled":       "#666666",   # ce qui est desactive
    "bg_saisie":           "#FFFFFF",   # cases de saisie (on voit ou taper)
    "selection":           "#316AC5",   # fond de selection, bouton Enregistrer
    "selection_survol":    "#1F3A6B",   # survol du bouton Enregistrer
    "texte_selection":     "#FFFFFF",   # texte sur le fond de selection
    "bulle_bg":            "#FFFFDC",   # infobulles
    "bulle_texte":         "#000000",
    "lien":                "#0B5AA8",
    "lien_vu":             "#6A3FA0",
    "jaune_bg":            "#FFFBE6",   # ligne du jour de la Saisie
    "barre_neutre":        "#94a3b8",   # l'annee de comparaison, en gris
    # Ligne choisie d'une liste deroulante ouverte : le creme de la page,
    # comme Fusion le peignait deja (audit du 12/10/2026 : on l'ecrit).
    "liste_choix_bg":      "#ECE9D8",
    "liste_choix_texte":   "#000000",
}


# Le mode sombre (decision de l'auteur du 12/10/2026, qui remplace « un seul
# theme, le clair » du 14/09/2026). Palette commune aux trois applications,
# validee sur maquette le 12/10/2026 : voir la charte d'interface. Chaque cle
# est la jumelle de la meme cle de LIGHT. Un sombre CHAUD (brun tres fonce),
# transposition du creme et de l'ivoire. Contrastes aux memes seuils que le
# clair : tests/test_contraste.py les verifie pour les deux palettes.
DARK = {
    "name":           "dark",
    "bg_app":         "#1C1B18",
    "bg_carte":       "#262521",
    # Tableaux et cases un cran plus clairs que la carte : on voit ou taper.
    "bg_panel":       "#302F2B",
    "bg_panel_alt":   "#2A2925",
    "border":         "#4A4944",
    "border_strong":  "#5E5C56",
    "cadre":          "#55565B",
    "cadre_controle": "#8A919C",
    # Blanc casse, jamais blanc pur : moins fatigant le soir.
    "text_primary":   "#EDEAE2",
    "text_secondary": "#C9C6BD",
    "text_muted":     "#ADAAA1",
    "credit":         "#5CC281",
    "credit_bg":      "#1B3324",
    "debit":          "#F2806F",
    "debit_bg":       "#3E201D",
    # Le bleu d'accent ecrit aussi (periode choisie, survol) : eclairci.
    "primary":        "#6FA0E8",
    "primary_bg":     "#24334A",
    "warm":           "#E67E22",
    "warm_bg":        "#3A2D16",
    "warm_ink":       "#F3C783",
    "info":           "#6FA0E8",
    "info_bg":        "#24334A",
    "info_ink":       "#A9C2EC",
    "table_row_alt":  "#2A2925",
    "entete_haut":    "#2E3B52",
    "entete_bas":     "#27344A",
    "entete_texte":   "#CFDCF3",
    "entete_filet":   "#41557A",
    "shadow":         "rgba(0, 0, 0, 0.30)",
    "sb_bg":               "#1C1B18",
    "sb_btn":              "#2B2A26",
    "sb_btn_border":       "#8A8780",
    "sb_btn_text":         "#E6E3DA",
    "sb_btn_hover":        "#24334A",
    "sb_btn_hover_border": "#6FA0E8",
    "sb_btn_pressed":      "#2A3F5F",
    "sb_actif":            "#2A3F5F",
    "sb_actif_border":     "#6FA0E8",
    "sb_actif_text":       "#CFDCF3",
    "sb_titre":            "#ADAAA1",
    "sb_titre_filet":      "#5E5C56",
    # Le bleu nuit de la marque devient un bleu clair.
    "sb_brand":            "#A9C2EC",
    "sb_sub":              "#ADAAA1",
    "sb_version":          "#ADAAA1",
    "text_disabled":       "#ADAAA1",
    "bg_saisie":           "#302F2B",
    "selection":           "#316AC5",
    "selection_survol":    "#25509A",
    "texte_selection":     "#FFFFFF",
    "bulle_bg":            "#3B3826",
    "bulle_texte":         "#F2EFE6",
    "lien":                "#82B6F5",
    "lien_vu":             "#BBA2EA",
    "jaune_bg":            "#35321C",
    "barre_neutre":        "#94a3b8",
    # Le fond de la page en faisait un « trou » a peine visible (1,29 pour
    # 1) : le bleu de selection, texte blanc (audit du 12/10/2026).
    "liste_choix_bg":      "#316AC5",
    "liste_choix_texte":   "#FFFFFF",
}

# Le reglage, garde dans les preferences de l'application (QSettings, comme
# la taille de la fenetre) : jamais dans les donnees. Il s'applique au
# prochain demarrage : changer de theme a chaud obligerait chaque page
# ouverte a se redessiner, et c'est la que se cachent les oublis.
CLE_THEME = "ui/theme"
THEMES = {"clair": LIGHT, "sombre": DARK}


# Le theme choisi pour cette session (voir choisir_theme, plus bas).
_THEME_ACTIF = LIGHT


def theme_actif() -> dict:
    """La palette de la session : LIGHT ou DARK."""
    return _THEME_ACTIF


def nom_du_theme(settings) -> str:
    """« clair » ou « sombre », lu dans les preferences. Une valeur
    inconnue ou absente donne le clair, le theme de reference."""
    valeur = settings.value(CLE_THEME) if settings is not None else None
    # Un fichier de preferences abime peut rendre une liste
    # (« clair, sombre ») : « in THEMES » levait alors une erreur et
    # l'application ne demarrait plus (audit du 13/10/2026).
    if not isinstance(valeur, str):
        return "clair"
    return valeur if valeur in THEMES else "clair"


def qss_for(t: dict) -> str:
    """Genere une feuille QSS complete a partir d'une palette."""
    # Les couleurs des series qui vont avec cette palette (traits des
    # tuiles), et non celles du theme de la session.
    cc = CHART_COLORS_SOMBRE if t is DARK else CHART_COLORS_CLAIR
    return f"""
QWidget {{
    background: {t["bg_app"]};
    color: {t["text_primary"]};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}}
/* Ce qui est desactive s'ecrit en gris, comme dans la palette (voir
   palette_claire). Sans cette regle, la couleur imposee ci-dessus gardait en
   noir « Ce mois-ci » et les fleches grisees : on les croyait cliquables
   (29/09/2026). */
QWidget:disabled {{
    color: {t["text_disabled"]};
}}
/* Les cases de saisie sont blanches : on voit ou taper (charte). Sans cette
   regle, la regle universelle QWidget leur donnait le fond beige de la page
   et, sur une carte ivoire, elles semblaient grisees (30/09/2026). Les menus
   deroulants ne sont pas concernes : ils gardent l'allure standard. */
QLineEdit, QAbstractSpinBox {{
    background: {t["bg_saisie"]};
}}
/* Les textes poses dans une carte prennent le fond de la carte. Sans cette
   regle, la regle universelle QWidget ci-dessus leur donnait le fond gris
   de la page : un bandeau gris derriere les titres de graphiques, les
   hypotheses, les Parametres... (audit du 14/09/2026). */
QFrame#Card QLabel, QFrame#Card QRadioButton, QFrame#Card QCheckBox {{
    background: transparent;
}}

/* Sidebar : sur le modele du bandeau de Pecule (14/09/2026) - boutons
   rectangulaires, emoji devant le libelle, titres de section soulignes.
   Les couleurs de Pecule (theme clair seul depuis le 14/09/2026).
   La page affichee est le bouton surligne (Pecule n'en a pas besoin : ses
   boutons lancent des actions). */
QFrame#Sidebar {{
    background: {t["sb_bg"]};
    border: none;
    border-right: 1px solid {t["sb_titre_filet"]};
}}
/* Selecteur descendant pour garantir que la couleur n'est pas ecrasee
   par la regle universelle QWidget plus haut. */
QFrame#Sidebar QLabel#Brand {{
    color: {t["sb_brand"]};
    font-size: 16px;
    font-weight: 800;
    padding: 2px 2px 0;
    background: transparent;
}}
QFrame#Sidebar QLabel#BrandSub {{
    color: {t["sb_sub"]};
    font-size: 11px;
    padding: 0 2px 2px;
    background: transparent;
}}
QFrame#Sidebar QLabel#BrandVersion {{
    color: {t["sb_version"]};
    font-size: 11px;
    padding: 4px 3px 0;
    background: transparent;
}}
/* Le trait de separation est porte par le titre lui-meme, comme dans
   Pecule : une bordure de QLabel s'affiche toujours. */
QLabel#NavSection {{
    color: {t["sb_titre"]};
    font-size: 8pt;
    font-weight: 700;
    letter-spacing: 1px;
    padding: 0 0 3px 3px;
    border: none;
    border-bottom: 1px solid {t["sb_titre_filet"]};
    background: transparent;
}}
QPushButton#NavItem {{
    text-align: left;
    padding-left: 8px;
    border: 1px solid {t["sb_btn_border"]};
    border-radius: 4px;
    background: {t["sb_btn"]};
    color: {t["sb_btn_text"]};
    font-size: 13px;
}}
QPushButton#NavItem:hover {{
    background: {t["sb_btn_hover"]};
    border-color: {t["sb_btn_hover_border"]};
}}
QPushButton#NavItem:pressed {{
    background: {t["sb_btn_pressed"]};
}}
QPushButton#NavItem:checked {{
    background: {t["sb_actif"]};
    border-color: {t["sb_actif_border"]};
    color: {t["sb_actif_text"]};
    font-weight: 600;
}}
/* Le curseur clavier se voit (audit du 12/10/2026, WCAG 2.4.7) : arrive
   avec Tab sur un bouton, rien ne changeait. Bord bleu de 2 px ; le retrait
   perd 1 px pour que le bouton garde sa taille. */
QPushButton#NavItem:focus {{
    border: 2px solid {t["primary"]};
    padding-left: 7px;
}}

/* Toolbar */
QFrame#Toolbar {{
    background: {t["bg_app"]};
    border-bottom: 1px solid {t["cadre"]};
}}
QLabel#ViewTitle {{
    color: {t["text_primary"]};
    font-size: 19px;
    font-weight: 700;
    background: transparent;
}}
QLabel#ViewSub {{
    color: {t["text_muted"]};
    font-size: 12px;
    background: transparent;
}}
QPushButton#ActionBtn {{
    background: {t["bg_panel_alt"]};
    border: 1px solid {t["cadre_controle"]};
    border-radius: 4px;
    padding: 8px 14px;
    color: {t["text_primary"]};
    font-weight: 600;
}}
QPushButton#ActionBtn:hover {{
    border-color: {t["primary"]};
    color: {t["primary"]};
}}
/* Desactive : bord et texte pales, il n'a plus l'air cliquable (audit du
   12/10/2026 ; il gardait le cadre d'un bouton actif). */
QPushButton#ActionBtn:disabled {{
    border-color: {t["border_strong"]};
    color: {t["text_disabled"]};
}}
QPushButton#ActionBtn:focus {{
    border: 2px solid {t["primary"]};
    padding: 7px 13px;
}}
QPushButton#SaveBtn {{
    background: {t["selection"]};
    border: 1px solid {t["selection"]};
    border-radius: 4px;
    padding: 8px 18px;
    color: {t["texte_selection"]};
    font-weight: 700;
}}
QPushButton#SaveBtn:hover {{
    /* Au survol, le bleu nuit de Pecule (29/09/2026 : c'etait un indigo
       #4338ca, etranger a la palette commune). */
    background: {t["selection_survol"]};
    border-color: {t["selection_survol"]};
}}
/* Deja bleu : son curseur clavier est un bord de la couleur du texte. */
QPushButton#SaveBtn:focus {{
    border: 2px solid {t["text_primary"]};
    padding: 7px 17px;
}}

/* Selecteur de periode : deux menus encadres par deux fleches, puis « Ce
   mois-ci ». Allure standard de Qt (Fusion), comme Pecule et Recharges VE
   (29/09/2026) : les regles arrondies d'avant faisaient disparaitre la
   fleche des menus (toute regle de style sur un menu deroulant l'efface) et
   donnaient a « Ce mois-ci » l'air d'un simple texte. Seules les fleches
   ‹ › ont leur taille, celle de Recharges VE. La largeur des menus est
   fixee dans app_desktop.py. Le calendrier de la vue Comparaison
   (QDateEdit#PeriodSelector) garde lui aussi l'allure standard. */
QPushButton#PeriodArrow {{
    font-size: 13pt;
    font-weight: bold;
    min-width: 26px;
    max-width: 26px;
    padding: 0px;
}}
QComboBox QAbstractItemView {{
    background: {t["bg_panel"]};
    color: {t["text_primary"]};
    border: 1px solid {t["cadre"]};
    selection-background-color: {t["primary_bg"]};
    selection-color: {t["primary"]};
    outline: none;
}}
/* La ligne choisie (ou survolee) d'une liste ouverte : sans cette regle,
   Fusion la peignait du fond de la page, a peine visible en sombre. Fusion
   dessine ses listes comme des menus : seul QComboBox::item les atteint
   (QAbstractItemView::item restait sans effet). */
QComboBox::item:selected {{
    background: {t["liste_choix_bg"]};
    color: {t["liste_choix_texte"]};
}}
/* Menus (« Bilans et comparaisons… ») : un liseré, celui des cartes, et
   l'entree survolee en bleu de selection. Sans ces regles, le menu avait la
   couleur de la page, sans bord, et la regle universelle QWidget effacait
   la mise en valeur de l'entree survolee (audit du 12/10/2026). */
QMenu {{
    border: 1px solid {t["cadre"]};
}}
QMenu::item:selected {{
    background: {t["selection"]};
    color: {t["texte_selection"]};
}}
/* Cette regle fait dessiner a Qt une coche devant la ligne choisie, qui
   decalait ce seul mot vers la droite : la couleur suffit. Toucher aux
   marges des lignes, lui, les etirait sur toute la hauteur. */
QComboBox::indicator {{
    width: 0px;
    height: 0px;
    image: none;
}}

/* Content area */
QScrollArea {{
    background: {t["bg_app"]};
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background: {t["bg_app"]};
}}

/* Cards : coins de 12 px dans les trois applis (choix de l'auteur du
   07/10/2026 ; 4 px du 29/09 au 07/10). Les tableaux gardent 4 px. */
QFrame#Card, QFrame.Card {{
    background: {t["bg_carte"]};
    border-radius: 12px;
    border: 1px solid {t["cadre"]};
}}
/* En-tete d'une carte titree (Card(titre=...)) : le bandeau degrade des
   cartes de Pecule, bord a bord en haut de la carte (29/09/2026). Plus
   precis que « QFrame#Card QLabel », qui le rendrait transparent. */
QFrame#Card QLabel#CardHeader {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {t["entete_haut"]}, stop:1 {t["entete_bas"]});
    color: {t["entete_texte"]};
    font-size: 9pt;
    font-weight: 600;
    letter-spacing: 0.5px;
    padding: 4px 10px;
    border: none;
    border-bottom: 1px solid {t["entete_filet"]};
    /* 11 px : le rayon de la carte moins son liseré, sinon le bandeau
       depasse dans les deux coins du haut. */
    border-top-left-radius: 11px;
    border-top-right-radius: 11px;
}}
QLabel#SectionTitle {{
    color: {t["text_secondary"]};
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 1px;
    background: transparent;
}}
QLabel#SectionSub {{
    color: {t["text_muted"]};
    font-size: 12px;
    background: transparent;
}}

/* KPI cards : trait de couleur de 3 px en HAUT, comme les tuiles de Pecule
   et de Recharges VE (29/09/2026 ; c'etait un trait de 4 px a gauche).
   Coins de 12 px, comme les cartes (07/10/2026). */
QFrame[role="kpi"] {{
    background: {t["bg_carte"]};
    border: 1px solid {t["cadre"]};
    border-radius: 12px;
    border-top-width: 3px;
}}
QFrame[role="kpi"][variant="credit"]   {{ border-top-color: {t["credit"]}; }}
QFrame[role="kpi"][variant="debit"]    {{ border-top-color: {t["debit"]}; }}
QFrame[role="kpi"][variant="primary"]  {{ border-top-color: {t["primary"]}; }}
QFrame[role="kpi"][variant="warm"]     {{ border-top-color: {t["warm"]}; }}
QFrame[role="kpi"][variant="info"]     {{ border-top-color: {t["info"]}; }}
QFrame[role="kpi"][variant="neutral"]  {{ border-top-color: {t["text_muted"]}; }}
QFrame[role="kpi"][variant="prod"]     {{ border-top-color: {cc["production"]}; }}
QFrame[role="kpi"][variant="solaire"]  {{ border-top-color: {cc["autoconso"]}; }}
QFrame[role="kpi"][variant="vente"]    {{ border-top-color: {cc["injection"]}; }}
QFrame[role="kpi"][variant="reseau"]   {{ border-top-color: {cc["soutirage"]}; }}
QFrame[role="kpi"][variant="total"]    {{ border-top-color: {cc["primary"]}; }}

QLabel#KpiLabel {{
    color: {t["text_muted"]};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
    background: transparent;
}}
QLabel#KpiValue {{
    color: {t["text_primary"]};
    font-size: 24px;
    font-weight: 700;
    background: transparent;
}}
QLabel#KpiSub {{
    color: {t["text_muted"]};
    font-size: 11px;
    background: transparent;
}}

/* Tuiles KPI (rangee du haut de "Repartition energie") : meme carte que
   KpiCard mais chiffre nettement plus gros, car c'est le seul contenu. */
/* Tuiles de la rangee du haut (Repartition energie) : trait de 3 px en
   haut, comme toute tuile chiffree (charte, 30/09/2026). */
QFrame[role="tile"] {{
    background: {t["bg_carte"]};
    border: 1px solid {t["cadre"]};
    border-radius: 12px;
    border-top-width: 3px;
}}
QFrame[role="tile"][variant="solaire"] {{ border-top-color: {cc["autoconso"]}; }}
QFrame[role="tile"][variant="prod"]    {{ border-top-color: {cc["production"]}; }}
QFrame[role="tile"][variant="credit"]  {{ border-top-color: {t["credit"]}; }}
QFrame[role="tile"][variant="debit"]   {{ border-top-color: {t["debit"]}; }}
QFrame[role="tile"][variant="neutral"] {{ border-top-color: {t["text_muted"]}; }}
QLabel#TileLabel {{
    color: {t["text_muted"]};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
    background: transparent;
}}
QLabel#TileValue {{
    color: {t["text_primary"]};
    font-size: 34px;
    font-weight: 700;
    background: transparent;
}}
QLabel#TileSub {{
    color: {t["text_secondary"]};
    font-size: 12px;
    background: transparent;
}}

/* En-tetes et lignes du tableau "Detail par poste" (grille maison, et non
   un QTableWidget : il faut indenter des sous-lignes au pixel pres). */
QLabel#GridHeader {{
    color: {t["text_secondary"]};
    font-size: 11px;
    font-weight: 700;
    background: transparent;
}}
QLabel#GridCell {{
    background: transparent;
}}
QWidget#PosteCell {{
    background: transparent;
}}

/* Cartes des postes financiers (Synthese) : l'allure des tuiles chiffrees,
   trait de 3 px en haut et titre en petites capitales (29/09/2026). */
QFrame[role="account"] {{
    background: {t["bg_carte"]};
    border: 1px solid {t["cadre"]};
    border-radius: 12px;
    border-top-width: 3px;
}}
QFrame[role="account"][variant="credit"]  {{ border-top-color: {t["credit"]}; }}
QFrame[role="account"][variant="debit"]   {{ border-top-color: {t["debit"]}; }}
QFrame[role="account"][variant="neutral"] {{ border-top-color: {t["text_muted"]}; }}
QLabel#AccountName {{ font-size: 11px; font-weight: 700; letter-spacing: 1px;
                      background: transparent; color: {t["text_muted"]}; }}
QLabel#AccountType {{ font-size: 11px; color: {t["text_muted"]}; background: transparent; }}
QLabel#AccountBalance {{ font-size: 22px; font-weight: 700; background: transparent; }}
QLabel#AccountTrend   {{ font-size: 11px; color: {t["text_muted"]}; background: transparent; }}

/* Tags */
QLabel[role="tag"] {{
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel[role="tag"][variant="credit"] {{ background: {t["credit_bg"]}; color: {t["credit"]}; }}
QLabel[role="tag"][variant="debit"]  {{ background: {t["debit_bg"]};  color: {t["debit"]}; }}
QLabel[role="tag"][variant="info"]   {{ background: {t["info_bg"]};   color: {t["info_ink"]}; }}
QLabel[role="tag"][variant="warm"]   {{ background: {t["warm_bg"]};   color: {t["warm_ink"]}; }}

/* Table - mouvements */
QTableWidget, QTableView {{
    background: {t["bg_panel"]};
    alternate-background-color: {t["table_row_alt"]};
    gridline-color: {t["border"]};
    border: 1px solid {t["cadre"]};
    border-radius: 4px;
    selection-background-color: {t["primary_bg"]};
    selection-color: {t["primary"]};
    color: {t["text_primary"]};
}}
/* Le meme retrait que les en-tetes : sans lui, un nombre aligne a droite
   touchait le bord de sa colonne, et celui de la carte dans la derniere
   (30/09/2026). */
QTableWidget::item {{
    padding-left: 10px;
    padding-right: 10px;
}}
QHeaderView::section {{
    background: {t["bg_panel_alt"]};
    color: {t["text_secondary"]};
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid {t["border_strong"]};
    font-weight: 600;
    font-size: 11px;
}}
QTableCornerButton::section {{
    background: {t["bg_panel_alt"]};
    border: none;
}}

/* Scrollbars */
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {t["border_strong"]};
    min-height: 30px; border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{ background: {t["text_muted"]}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent; height: 10px; margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {t["border_strong"]};
    min-width: 30px; border-radius: 5px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ height: 0; }}

/* Status bar */
QStatusBar {{
    background: {t["bg_app"]};
    color: {t["text_muted"]};
    border-top: 1px solid {t["cadre"]};
}}
"""


def mpl_style(t: dict) -> dict:
    """Retourne un dict pour mettre a jour plt.rcParams selon le theme."""
    return {
        "figure.facecolor":    t["bg_carte"],
        "axes.facecolor":      t["bg_carte"],
        "axes.edgecolor":      t["border"],
        "axes.labelcolor":     t["text_secondary"],
        "axes.titlecolor":     t["text_primary"],
        "xtick.color":         t["text_muted"],
        "ytick.color":         t["text_muted"],
        "grid.color":          t["border"],
        "text.color":          t["text_primary"],
        "legend.facecolor":    t["bg_carte"],
        "legend.edgecolor":    t["border"],
        "savefig.facecolor":   t["bg_carte"],
        "font.family":         ["Segoe UI", "DejaVu Sans"],
        # Tailles de police harmonisees pour tous les graphiques.
        "font.size":           11,   # base (etiquettes de barres, etc.)
        "axes.labelsize":      12,   # titres d'axes (kWh, €)
        "axes.titlesize":      13,
        "xtick.labelsize":     11,
        "ytick.labelsize":     11,
        "legend.fontsize":     11,
        "axes.spines.top":     False,
        "axes.spines.right":   False,
        "axes.grid":           True,
        "grid.linestyle":      "--",
        "grid.linewidth":      0.5,
        "grid.alpha":          0.5,
        # Hachures des periodes incompletes : noires en clair (la valeur
        # par defaut de matplotlib), claires en sombre.
        "hatch.color":         t["text_primary"],
    }


# ----------------------------------------------------------------------
# Couleurs metier
# ----------------------------------------------------------------------
# Source unique de verite : toute la couleur d'un flux d'energie (barres,
# courbes, rubans du Sankey, tuiles) part d'ici, jamais d'un code ecrit en
# dur dans une vue.
#
# Pourquoi cette palette et pas une autre : l'ancienne opposait un vert et un
# rouge, or ces deux teintes sont indistinguables pour environ 8 % des hommes
# (deuteranopie / protanopie) - et c'etait justement le contraste principal du
# graphique de consommation. L'orange remplace donc le rouge : il reste
# "chaud" (donc lisible comme une depense) mais se distingue du vert quel que
# soit le type de daltonisme. Chaque couleur garde un contraste d'au moins
# 3:1 sur le fond sombre, et toutes les paires restent separees a l'oeil.
#
# En sombre, le vert, le bleu et l'orange sont eclaircis d'un cran pour
# ressortir sur le fond des cartes, et le bleu nuit des totaux devient bleu
# clair (palette validee le 12/10/2026). Le jaune ne change pas.
# CHART_COLORS est le dictionnaire du theme de la session : choisir_theme()
# le remplit avec l'un ou l'autre jeu.
CHART_COLORS_CLAIR = {
    # Jaune franc : la production brute. Ecarte de l'orange du soutirage pour
    # que les deux ne se confondent pas dans les graphiques a quatre barres.
    "production":    "#e8b21f",
    # Vert : l'energie solaire consommee sur place (et, par extension, les
    # economies qu'elle represente).
    "autoconso":     "#199e70",
    # Bleu : ce qui part vers le reseau (injection) et l'argent qu'on en tire.
    "injection":     "#3987e5",
    # Orange : ce qu'on achete au reseau (soutirage) et ce que ca coute.
    "soutirage":     "#d95926",
    # Indigo : les totaux et les cumuls, qui ne sont pas un flux d'energie.
    "primary":       "#1F3A6B",
}
CHART_COLORS_SOMBRE = {
    "production":    "#e8b21f",
    "autoconso":     "#22b07f",
    "injection":     "#4a95ec",
    "soutirage":     "#e3693a",
    "primary":       "#A9C2EC",
}
CHART_COLORS = dict(CHART_COLORS_CLAIR)

def _luminance(couleur: str) -> float:
    """Luminance relative d'une couleur « #rrggbb » (formule WCAG)."""
    canaux = []
    for i in (1, 3, 5):
        c = int(couleur[i:i + 2], 16) / 255
        canaux.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = canaux
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contraste(a: str, b: str) -> float:
    clair, fonce = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (clair + 0.05) / (fonce + 0.05)


def _fonds_d_ecriture(t: dict) -> tuple:
    """Les fonds sur lesquels on ecrit : cases et tableaux, lignes
    alternees, cartes."""
    return (t["bg_panel"], t["table_row_alt"], t["bg_carte"])


def encre(couleur: str, seuil: float = 4.8) -> str:
    """La meme teinte, assombrie juste assez pour ECRIRE (30/09/2026).

    Charte : couleur vive pour une barre, variante foncee pour ecrire. Les
    couleurs des series (jaune 1,83 pour 1, vert, bleu, orange 3,2 a 3,9)
    ecrivaient des chiffres presque illisibles. On multiplie les trois
    composantes par un meme facteur, ce qui garde la teinte, jusqu'a
    atteindre le seuil sur les trois fonds. Une couleur deja assez foncee
    ne bouge pas.

    En sombre (12/10/2026), c'est l'inverse : on ECLAIRCIT la teinte, en la
    rapprochant du blanc, jusqu'au meme seuil sur les fonds sombres.
    """
    t = theme_actif()
    fonds = _fonds_d_ecriture(t)
    r, g, b = (int(couleur[i:i + 2], 16) for i in (1, 3, 5))
    sombre = t is DARK
    pas = 0.0
    while pas <= 1.0:
        if sombre:
            # Melange avec le blanc : pas = 0 la couleur, pas = 1 le blanc.
            trace = "#%02x%02x%02x" % tuple(
                round(c + (255 - c) * pas) for c in (r, g, b))
        else:
            facteur = 1.0 - pas
            trace = "#%02x%02x%02x" % tuple(
                round(c * facteur) for c in (r, g, b))
        if min(_contraste(trace, f) for f in fonds) >= seuil:
            return couleur if pas == 0.0 else trace
        pas = round(pas + 0.01, 2)
    return "#FFFFFF" if sombre else "#000000"


# Encre des variations et des montants ecrits (+ favorable / - defavorable) :
# le vert et le rouge des montants de la charte, les memes que les bilans.
# Un vert et un orange a part (#137b57, #b44a20, choisis le 30/09/2026 pour
# les daltoniens) faisaient deux verts et deux rouges sur la meme page
# (relecture du 05/10/2026). Les daltoniens n'y perdent rien : chaque
# variation porte aussi son signe, la couleur n'est jamais seule.
def _melange(a: str, b: str, part_a: float) -> str:
    """La couleur a melangee a la couleur b (part_a de a, le reste de b)."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(
        round(x * part_a + y * (1 - part_a)) for x, y in zip(ca, cb, strict=True))


# Le gris neutre qui adoucit une couleur en sombre (voir adoucir).
_GRIS_ADOUCI_SOMBRE = "#77736A"


def adoucir(couleur: str) -> str:
    """La teinte pale d'une couleur de serie, pour les barres qui ne sont
    pas mises en valeur (production jour par jour, tuile Production).

    En clair : la couleur a 45 % sur l'ivoire des cartes, le pastel d'avant.
    En sombre (audit du 12/10/2026) : la meme recette donnait un brun olive
    terne (#7D6420, 2,71 pour 1 sur la carte). La couleur est melangee a
    parts egales a un gris neutre : un « sable » lisible (5,1 pour 1),
    distinct du jaune plein.
    """
    t = theme_actif()
    if t is DARK:
        return _melange(couleur, _GRIS_ADOUCI_SOMBRE, 0.5)
    return _melange(couleur, t["bg_carte"], 0.45)


# Remplacees par celles du theme sombre si c'est lui qui est choisi.
COULEUR_FAVORABLE = LIGHT["credit"]       # #18733A, 5,6 pour 1 sur l'ivoire
COULEUR_DEFAVORABLE = LIGHT["debit"]      # #BC3729 : 5,3 pour 1 sur l'ivoire, 4,6 sur le creme


def choisir_theme(nom: str) -> dict:
    """Fixe le theme de la session, « clair » ou « sombre », et le rend.

    A appeler au demarrage, AVANT d'importer les vues : certaines prennent
    CHART_COLORS ou COULEUR_FAVORABLE au moment ou elles sont importees.
    Le dictionnaire CHART_COLORS est rempli sur place, pour que ceux qui
    l'ont deja importe voient aussi les bonnes couleurs.
    """
    global _THEME_ACTIF, COULEUR_FAVORABLE, COULEUR_DEFAVORABLE
    _THEME_ACTIF = THEMES.get(nom, LIGHT)
    sombre = _THEME_ACTIF is DARK
    CHART_COLORS.clear()
    CHART_COLORS.update(CHART_COLORS_SOMBRE if sombre else CHART_COLORS_CLAIR)
    COULEUR_FAVORABLE = _THEME_ACTIF["credit"]
    COULEUR_DEFAVORABLE = _THEME_ACTIF["debit"]
    return _THEME_ACTIF


def palette_pour(t: dict) -> QPalette:
    """La palette Qt d'un theme, construite de zero — fonds ET textes.
    Voir palette_claire() pour la raison."""
    pal = QPalette()
    for role, cle in (
            (QPalette.Window, "bg_app"), (QPalette.WindowText, "text_primary"),
            (QPalette.Base, "bg_saisie"), (QPalette.Text, "text_primary"),
            (QPalette.AlternateBase, "table_row_alt"),
            (QPalette.Button, "bg_app"), (QPalette.ButtonText, "text_primary"),
            (QPalette.ToolTipBase, "bulle_bg"),
            (QPalette.ToolTipText, "bulle_texte"),
            (QPalette.Highlight, "selection"),
            (QPalette.HighlightedText, "texte_selection"),
            (QPalette.PlaceholderText, "text_muted"),
            (QPalette.BrightText, "texte_selection"),
            (QPalette.Link, "lien"), (QPalette.LinkVisited, "lien_vu")):
        pal.setColor(role, QColor(t[cle]))
    # Ce qui est desactive s'efface, sans disparaitre pour autant.
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor(t["text_disabled"]))
    return pal


def palette_claire() -> QPalette:
    """La palette de Pecule, construite de zero — fonds ET textes
    (comptesbudget/app.py). Reprise le 25/09/2026.

    La feuille de style impose deja fond et texte a chaque widget ; la
    palette couvre ce qu'elle ne touche pas (boites de message, menus
    deroulants, fenetres de choix de fichier). Rien n'est pris a la palette
    du systeme : un Windows regle en mode sombre ne change plus rien (defaut
    vu dans Pecule le 16/09/2026 : texte blanc sur fond clair)."""
    return palette_pour(LIGHT)


class StyleContoure(QProxyStyle):
    """Le style « Fusion », plus un contour lisible aux cases a cocher et aux
    boutons radio : celui de Pecule (comptesbudget/app.py, StyleClair).

    Fusion cerne ces controles d'une teinte tiree du fond de la page : a
    peine visible sur le creme, presque invisible en sombre (choix Clair /
    Sombre des Parametres, 12/10/2026). La charte veut 3 pour 1 pour ce
    qu'on clique : le contour des controles du theme.
    """

    def __init__(self, contour: str, cadrer_les_cases: bool = False,
                 focus: str = "#316AC5", eteint: str = "#C8D0DC"):
        super().__init__(QStyleFactory.create("Fusion"))
        self.contour = QColor(contour)
        # Bord d'un bouton ou d'un menu deroulant desactive : pale, pour
        # qu'il n'ait plus l'air cliquable (audit du 12/10/2026).
        self.eteint = QColor(eteint)
        # Bord d'une case de saisie qui a le curseur clavier, dans les deux
        # themes (audit du 12/10/2026) : la feuille de style, qui donne leur
        # fond aux cases, effacait celui de Fusion.
        self.focus = QColor(focus)
        # En sombre seulement (12/10/2026) : les cases de saisie recoivent
        # elles aussi ce contour. Fusion le tire du fond de la page, presque
        # noir en sombre : on voyait mal ou taper. Le clair garde son allure.
        self.cadrer_les_cases = cadrer_les_cases

    def _cadrer(self, painter, rect, couleur, epaisseur=1) -> None:
        """Le contour d'une case de saisie, aux coins arrondis de Fusion."""
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(couleur, 1))
        painter.setBrush(Qt.NoBrush)
        # Le demi-pixel cale le trait sur une seule rangee de pixels : sans
        # lui, il se partage entre deux et sort pale. Un trait par pixel
        # d'epaisseur, de l'exterieur vers l'interieur.
        for i in range(epaisseur):
            marge = 0.5 + i
            painter.drawRoundedRect(
                QRectF(rect).adjusted(marge, marge, -marge, -marge), 2, 2)
        painter.restore()

    def _case(self, painter, option) -> None:
        """Bord d'une case de saisie : bleu de 2 px si elle a le curseur,
        sinon le contour des controles (en sombre seulement)."""
        if option.state & QStyle.State_HasFocus:
            self._cadrer(painter, option.rect, self.focus, 2)
        elif self.cadrer_les_cases:
            self._cadrer(painter, option.rect, self.contour)

    def _bouton(self, painter, option) -> None:
        """Bord d'un bouton ou d'un menu deroulant standard (fleches de
        periode, « Ce mois-ci », choix de l'annee...) : le contour des
        controles, 3 pour 1 sur la page comme le veut la charte, ou un bord
        pale s'il est desactive. Fusion ne leur donnait que 2 pour 1 en
        clair et 1,6 en sombre, desactives ou non (audit du 12/10/2026)."""
        if not option.state & QStyle.State_Enabled:
            self._cadrer(painter, option.rect, self.eteint)
        elif option.state & QStyle.State_HasFocus:
            self._cadrer(painter, option.rect, self.focus, 2)
        else:
            self._cadrer(painter, option.rect, self.contour)

    def drawComplexControl(self, control, option, painter, widget=None):
        super().drawComplexControl(control, option, painter, widget)
        if control == QStyle.CC_SpinBox and option.frame:
            self._case(painter, option)
        elif control == QStyle.CC_ComboBox and option.frame:
            self._bouton(painter, option)

    def drawPrimitive(self, element, option, painter, widget=None):
        super().drawPrimitive(element, option, painter, widget)
        if element == QStyle.PE_FrameLineEdit:
            self._case(painter, option)
        elif element == QStyle.PE_PanelButtonCommand:
            self._bouton(painter, option)
        if element in (QStyle.PE_IndicatorCheckBox,
                       QStyle.PE_IndicatorItemViewItemCheck,
                       QStyle.PE_IndicatorRadioButton):
            painter.save()
            rond = element == QStyle.PE_IndicatorRadioButton
            painter.setRenderHint(painter.RenderHint.Antialiasing, rond)
            painter.setPen(QPen(self.contour, 1))
            painter.setBrush(Qt.NoBrush)
            cadre = option.rect.adjusted(0, 0, -1, -1)
            if rond:
                painter.drawEllipse(cadre)
            else:
                painter.drawRect(cadre)
            painter.restore()


def calendrier_lisible(case) -> None:
    """Samedis et dimanches du calendrier d'une case a date dans le rouge
    des depenses du theme. Qt les ecrit dans un rouge vif et pur : 4,0 pour
    1 sur le blanc, 3,35 sur le fond sombre, sous les 4,5 de la charte
    (relecture du 14/10/2026, meme correction que Pecule)."""
    calendrier = case.calendarWidget()
    for jour in (Qt.Saturday, Qt.Sunday):
        forme = calendrier.weekdayTextFormat(jour)
        forme.setForeground(QColor(theme_actif()["debit"]))
        calendrier.setWeekdayTextFormat(jour, forme)


def appliquer_style(app) -> None:
    """Style « Fusion » et palette du theme choisi (le clair par defaut),
    comme Pecule. Fusion est
    indispensable : les styles natifs de Windows peignent certains textes
    eux-memes, sans consulter la palette."""
    t = theme_actif()
    # Garde une reference vivante : Qt ne garde pas l'objet Python.
    app._style_contoure = StyleContoure(t["cadre_controle"],
                                        cadrer_les_cases=t is DARK,
                                        focus=t["primary"],
                                        eteint=t["border_strong"])
    app.setStyle(app._style_contoure)
    palette = palette_pour(t)
    app.setPalette(palette)
    # Les infobulles ont leur palette a elles, prise au systeme (fond
    # #3C3C3C sur un Windows sombre) : setPalette() ne la touche pas.
    QToolTip.setPalette(palette)
