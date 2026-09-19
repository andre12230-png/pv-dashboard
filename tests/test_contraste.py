"""Lisibilite des textes : chaque couleur d'ecriture du theme doit se
detacher assez de son fond.

Le 15/09/2026, Andre a trouve des ecritures "tres claires et difficiles a
lire" : le gris des petits textes (#94a3b8) n'avait qu'un contraste de 2,6
pour 1 sur blanc, et l'orange du bandeau "Donnees incompletes" a peine 2 pour
1 sur son fond jaune. Le minimum conseille pour lire un texte courant est de
4,5 pour 1 (norme d'accessibilite WCAG, niveau AA).
"""

import pytest

from gui_theme import LIGHT


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
    ("text_muted", "bg_app"),        # sous-titres des pages, sur le fond gris
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
    ("cadre", "bg_panel"),               # contour des cartes, cote carte
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
    rapport = contraste(LIGHT[cadre], LIGHT[fond])
    assert rapport >= 1.4, (
        f"{cadre} {LIGHT[cadre]} sur {fond} {LIGHT[fond]} : "
        f"{rapport:.2f} pour 1, moins que 1,4")


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


def test_pas_de_theme_sombre():
    """Un seul thème, le clair (décision du 14/09/2026)."""
    import gui_theme
    assert not hasattr(gui_theme, "DARK"), (
        "un thème sombre est réapparu dans gui_theme.py")
