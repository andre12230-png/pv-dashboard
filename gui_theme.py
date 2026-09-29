"""
Palette claire (celle de Pecule) + generation du QSS Qt + style matplotlib
associe + style Fusion et palette Qt qui resistent au mode sombre de Windows.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QLibraryInfo, QTranslator
from PySide6.QtGui import QColor, QPalette


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
    "debit":          "#C0392B",
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
}


# Un seul theme, le clair, comme Pecule : decision de l'auteur du 14/09/2026,
# valable pour toutes ses applications. La palette sombre a ete retiree.


def qss_for(t: dict) -> str:
    """Genere une feuille QSS complete a partir d'une palette."""
    return f"""
QWidget {{
    background: {t["bg_app"]};
    color: {t["text_primary"]};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}}
/* Les textes poses dans une carte prennent le fond de la carte. Sans cette
   regle, la regle universelle QWidget ci-dessus leur donnait le fond gris
   de la page : un bandeau gris derriere les titres de graphiques, les
   hypotheses, les Parametres... (audit du 14/09/2026). */
QFrame#Card QLabel {{
    background: transparent;
}}

/* Sidebar : sur le modele du bandeau de Pecule (14/09/2026) - boutons
   rectangulaires, emoji devant le libelle, titres de section soulignes.
   En theme clair, les couleurs de Pecule ; en sombre, leur transposition.
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
QPushButton#NavItem:checked, QPushButton#NavItem[active="true"] {{
    background: {t["sb_actif"]};
    border-color: {t["sb_actif_border"]};
    color: {t["sb_actif_text"]};
    font-weight: 600;
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
    border-radius: 8px;
    padding: 8px 14px;
    color: {t["text_primary"]};
    font-weight: 600;
}}
QPushButton#ActionBtn:hover {{
    border-color: {t["primary"]};
    color: {t["primary"]};
}}
QPushButton#SaveBtn {{
    background: {t["primary"]};
    border: 1px solid {t["primary"]};
    border-radius: 8px;
    padding: 8px 18px;
    color: white;
    font-weight: 700;
}}
QPushButton#SaveBtn:hover {{
    /* Au survol, le bleu nuit de Pecule (29/09/2026 : c'etait un indigo
       #4338ca, etranger a la palette commune). */
    background: {t["sb_brand"]};
    border-color: {t["sb_brand"]};
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

/* Content area */
QScrollArea {{
    background: {t["bg_app"]};
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background: {t["bg_app"]};
}}

/* Cards : coins de 4 px, comme Pecule et Recharges VE (29/09/2026 ;
   c'etait 12 px). */
QFrame#Card, QFrame.Card {{
    background: {t["bg_carte"]};
    border-radius: 4px;
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
    border-top-left-radius: 3px;
    border-top-right-radius: 3px;
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

/* KPI cards : trait de couleur de 3 px en HAUT, coins de 4 px, comme les
   tuiles de Pecule et de Recharges VE (29/09/2026 ; c'etait un trait de
   4 px a gauche et des coins de 12 px). */
QFrame[role="kpi"] {{
    background: {t["bg_carte"]};
    border: 1px solid {t["cadre"]};
    border-radius: 4px;
    border-top-width: 3px;
}}
QFrame[role="kpi"][variant="credit"]   {{ border-top-color: {t["credit"]}; }}
QFrame[role="kpi"][variant="debit"]    {{ border-top-color: {t["debit"]}; }}
QFrame[role="kpi"][variant="primary"]  {{ border-top-color: {t["primary"]}; }}
QFrame[role="kpi"][variant="warm"]     {{ border-top-color: {t["warm"]}; }}
QFrame[role="kpi"][variant="info"]     {{ border-top-color: {t["info"]}; }}
QFrame[role="kpi"][variant="neutral"]  {{ border-top-color: {t["text_muted"]}; }}
QFrame[role="kpi"][variant="prod"]     {{ border-top-color: {CHART_COLORS["production"]}; }}
QFrame[role="kpi"][variant="solaire"]  {{ border-top-color: {CHART_COLORS["autoconso"]}; }}
QFrame[role="kpi"][variant="vente"]    {{ border-top-color: {CHART_COLORS["injection"]}; }}
QFrame[role="kpi"][variant="reseau"]   {{ border-top-color: {CHART_COLORS["soutirage"]}; }}
QFrame[role="kpi"][variant="total"]    {{ border-top-color: {CHART_COLORS["primary"]}; }}

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
QFrame[role="tile"] {{
    background: {t["bg_carte"]};
    border: 1px solid {t["cadre"]};
    border-radius: 4px;
}}
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
    text-transform: uppercase;
    background: transparent;
}}
QLabel#GridCell {{
    background: transparent;
}}
QWidget#PosteCell {{
    background: transparent;
}}

/* Account card */
QFrame[role="account"] {{
    background: {t["bg_carte"]};
    border: 1px solid {t["cadre"]};
    border-radius: 4px;
}}
QLabel#AccountName {{ font-size: 13px; font-weight: 600; background: transparent;
                      color: {t["text_primary"]}; }}
QLabel#AccountType {{ font-size: 11px; color: {t["text_muted"]}; background: transparent; }}
QLabel#AccountBalance {{ font-size: 22px; font-weight: 700; background: transparent; }}
QLabel#AccountTrend   {{ font-size: 11px; color: {t["text_muted"]}; background: transparent; }}
QLabel#AccountIcon {{
    color: white; font-weight: 700; font-size: 12px;
    border-radius: 8px; padding: 6px;
    qproperty-alignment: AlignCenter;
    min-width: 36px; min-height: 36px; max-width: 36px; max-height: 36px;
}}

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
QHeaderView::section {{
    background: {t["bg_panel_alt"]};
    color: {t["text_secondary"]};
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid {t["border_strong"]};
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
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
# Ces couleurs sont volontairement independantes du theme clair/sombre :
# ce sont des couleurs d'accent, elles fonctionnent sur les deux fonds.
CHART_COLORS = {
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

# Couleurs de signe pour les montants et les variations (+ favorable /
# - defavorable). On reutilise le vert et l'orange de la palette plutot que le
# couple vert/rouge, pour ne pas reintroduire ailleurs le probleme qu'on vient
# de corriger dans les graphiques.
COULEUR_FAVORABLE = CHART_COLORS["autoconso"]
COULEUR_DEFAVORABLE = CHART_COLORS["soutirage"]


def palette_claire() -> QPalette:
    """La palette de Pecule, construite de zero — fonds ET textes
    (comptesbudget/app.py). Reprise le 25/09/2026.

    La feuille de style impose deja fond et texte a chaque widget ; la
    palette couvre ce qu'elle ne touche pas (boites de message, menus
    deroulants, fenetres de choix de fichier). Rien n'est pris a la palette
    du systeme : un Windows regle en mode sombre ne change plus rien (defaut
    vu dans Pecule le 16/09/2026 : texte blanc sur fond clair)."""
    pal = QPalette()
    for role, couleur in (
            (QPalette.Window, "#ECE9D8"), (QPalette.WindowText, "#000000"),
            (QPalette.Base, "#FFFFFF"), (QPalette.Text, "#000000"),
            (QPalette.AlternateBase, "#F5F5F0"),
            (QPalette.Button, "#ECE9D8"), (QPalette.ButtonText, "#000000"),
            (QPalette.ToolTipBase, "#FFFFDC"), (QPalette.ToolTipText, "#000000"),
            (QPalette.Highlight, "#316AC5"), (QPalette.HighlightedText, "#FFFFFF"),
            (QPalette.PlaceholderText, "#6B6B6B"), (QPalette.BrightText, "#FFFFFF"),
            (QPalette.Link, "#0B5AA8"), (QPalette.LinkVisited, "#6A3FA0")):
        pal.setColor(role, QColor(couleur))
    # Ce qui est desactive s'efface, sans disparaitre pour autant.
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor("#6B6B6B"))
    return pal


def appliquer_style(app) -> None:
    """Style « Fusion » et palette claire, comme Pecule. Fusion est
    indispensable : les styles natifs de Windows peignent certains textes
    eux-memes, sans consulter la palette."""
    app.setStyle("Fusion")
    app.setPalette(palette_claire())
