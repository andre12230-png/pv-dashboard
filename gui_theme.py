"""
Palettes Light / Dark + generation du QSS Qt + style matplotlib associe.
"""

from __future__ import annotations

LIGHT = {
    "name":           "light",
    "bg_app":         "#f8fafc",
    "bg_panel":       "#ffffff",
    "bg_panel_alt":   "#f9fafb",
    "bg_sidebar":     "#0f172a",
    "bg_sidebar_2":   "#1e293b",
    "border":         "#e2e8f0",
    "border_strong":  "#cbd5e1",
    # Cadres (15/09/2026) : "border" ci-dessus reste pour les grilles des
    # graphiques et le fond des jauges, qui doivent rester discrets.
    # Contour des cartes et des tableaux : un cran plus marque.
    "cadre":          "#cbd5e1",
    # Contour de ce qu'on clique (boutons, menus de periode) : 3 pour 1
    # au moins sur son fond, le minimum conseille pour un element actif.
    "cadre_controle": "#8492a6",
    "text_primary":   "#0f172a",
    "text_secondary": "#475569",
    # Gris des petits textes : fonce le 15/09/2026 (#94a3b8 etait trop pale,
    # contraste 2,6:1 sur blanc) ; #64748b atteint 4,8:1, le minimum conseille.
    "text_muted":     "#64748b",
    "text_on_dark":   "#cbd5e1",
    # Vert et rouge des montants : un cran plus fonces le 15/09/2026 pour se
    # lire dans les tableaux (contraste d'au moins 4,5:1 sur blanc).
    "credit":         "#15803d",
    "credit_bg":      "#dcfce7",
    "debit":          "#b91c1c",
    "debit_bg":       "#fee2e2",
    "primary":        "#4f46e5",
    "primary_bg":     "#eef2ff",
    "warm":           "#f59e0b",
    "warm_bg":        "#fef3c7",
    # Orange "encre" : pour ECRIRE en orange (bandeaux, pastilles). L'orange
    # vif ci-dessus reste pour les bordures, il est illisible en texte.
    "warm_ink":       "#92400e",
    "info":           "#0ea5e9",
    "info_bg":        "#dbeafe",
    # Bleu "encre" : meme principe que warm_ink, pour le texte.
    "info_ink":       "#0369a1",
    "table_row_alt":  "#fafbfc",
    "shadow":         "rgba(15, 23, 42, 0.06)",
    # Bandeau de gauche : les couleurs de celui de Pecule.
    "sb_bg":               "#efece5",
    "sb_btn":              "#fcfcfc",
    # Contours du menu fonces le 15/09/2026 (3 pour 1 sur le fond beige).
    "sb_btn_border":       "#878787",
    "sb_btn_text":         "#222222",
    "sb_btn_hover":        "#eaf2fb",
    "sb_btn_hover_border": "#2f74b5",
    "sb_btn_pressed":      "#d8e7f7",
    "sb_actif":            "#d8e7f7",
    "sb_actif_border":     "#2f74b5",
    "sb_actif_text":       "#0f3b6e",
    "sb_titre":            "#5c5c5c",
    "sb_titre_filet":      "#a9a9a9",
    "sb_brand":            "#b45309",
    "sb_sub":              "#5c5c5c",
    "sb_version":          "#5c5c5c",
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
    background: {t["bg_panel"]};
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
    background: #4338ca;
    border-color: #4338ca;
}}

/* Selecteur de periode : deux menus encadres par deux fleches. Leur largeur
   est fixee dans app_desktop.py — elle differe d'un menu a l'autre, alors que
   tout le reste du look est commun. */
QPushButton#PeriodArrow {{
    background: {t["bg_panel_alt"]};
    border: 1px solid {t["cadre_controle"]};
    border-radius: 8px;
    padding: 4px 0;
    min-width: 30px;
    max-width: 30px;
    color: {t["text_primary"]};
    font-size: 17px;
    font-weight: 600;
}}
QPushButton#PeriodArrow:hover {{
    border-color: {t["primary"]};
    color: {t["primary"]};
}}
QPushButton#PeriodArrow:disabled {{
    color: {t["text_muted"]};
    background: {t["bg_app"]};
    border-color: {t["border"]};
}}
QComboBox#PeriodSelector {{
    background: {t["bg_panel"]};
    border: 1px solid {t["cadre_controle"]};
    border-radius: 8px;
    padding: 7px 12px;
    color: {t["text_primary"]};
}}
QComboBox#PeriodSelector:hover {{
    border-color: {t["primary"]};
}}
QComboBox#PeriodSelector:disabled {{
    color: {t["text_muted"]};
    background: {t["bg_app"]};
    border-color: {t["border"]};
}}
QComboBox#PeriodSelector::drop-down {{
    border: none;
    width: 20px;
}}
/* Selecteur de jour (calendrier) de la vue Comparaison : meme look que
   le combo de periode. */
QDateEdit#PeriodSelector {{
    background: {t["bg_panel"]};
    border: 1px solid {t["cadre_controle"]};
    border-radius: 8px;
    padding: 7px 12px;
    color: {t["text_primary"]};
}}
QDateEdit#PeriodSelector:hover {{
    border-color: {t["primary"]};
}}
QDateEdit#PeriodSelector::drop-down {{
    border: none;
    width: 20px;
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

/* Cards */
QFrame#Card, QFrame.Card {{
    background: {t["bg_panel"]};
    border-radius: 12px;
    border: 1px solid {t["cadre"]};
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

/* KPI cards */
QFrame[role="kpi"] {{
    background: {t["bg_panel"]};
    border: 1px solid {t["cadre"]};
    border-radius: 12px;
    border-left-width: 4px;
}}
QFrame[role="kpi"][variant="credit"]   {{ border-left-color: {t["credit"]}; }}
QFrame[role="kpi"][variant="debit"]    {{ border-left-color: {t["debit"]}; }}
QFrame[role="kpi"][variant="primary"]  {{ border-left-color: {t["primary"]}; }}
QFrame[role="kpi"][variant="warm"]     {{ border-left-color: {t["warm"]}; }}
QFrame[role="kpi"][variant="info"]     {{ border-left-color: {t["info"]}; }}
QFrame[role="kpi"][variant="neutral"]  {{ border-left-color: {t["text_muted"]}; }}
QFrame[role="kpi"][variant="prod"]     {{ border-left-color: {CHART_COLORS["production"]}; }}
QFrame[role="kpi"][variant="solaire"]  {{ border-left-color: {CHART_COLORS["autoconso"]}; }}
QFrame[role="kpi"][variant="vente"]    {{ border-left-color: {CHART_COLORS["injection"]}; }}
QFrame[role="kpi"][variant="reseau"]   {{ border-left-color: {CHART_COLORS["soutirage"]}; }}
QFrame[role="kpi"][variant="total"]    {{ border-left-color: {CHART_COLORS["primary"]}; }}

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
    background: {t["bg_panel"]};
    border: 1px solid {t["cadre"]};
    border-radius: 12px;
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
    background: {t["bg_panel"]};
    border: 1px solid {t["cadre"]};
    border-radius: 12px;
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
    border-radius: 8px;
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
    background: {t["bg_panel"]};
    color: {t["text_muted"]};
    border-top: 1px solid {t["cadre"]};
}}
"""


def mpl_style(t: dict) -> dict:
    """Retourne un dict pour mettre a jour plt.rcParams selon le theme."""
    return {
        "figure.facecolor":    t["bg_panel"],
        "axes.facecolor":      t["bg_panel"],
        "axes.edgecolor":      t["border"],
        "axes.labelcolor":     t["text_secondary"],
        "axes.titlecolor":     t["text_primary"],
        "xtick.color":         t["text_muted"],
        "ytick.color":         t["text_muted"],
        "grid.color":          t["border"],
        "text.color":          t["text_primary"],
        "legend.facecolor":    t["bg_panel"],
        "legend.edgecolor":    t["border"],
        "savefig.facecolor":   t["bg_panel"],
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
    "primary":       "#4f46e5",
}

# Couleurs de signe pour les montants et les variations (+ favorable /
# - defavorable). On reutilise le vert et l'orange de la palette plutot que le
# couple vert/rouge, pour ne pas reintroduire ailleurs le probleme qu'on vient
# de corriger dans les graphiques.
COULEUR_FAVORABLE = CHART_COLORS["autoconso"]
COULEUR_DEFAVORABLE = CHART_COLORS["soutirage"]
