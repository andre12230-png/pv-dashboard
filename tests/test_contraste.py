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
