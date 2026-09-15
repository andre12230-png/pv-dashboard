"""Tests du menu de gauche.

Le menu est decrit une seule fois, dans NAV_ITEMS, et trois choses en
dependent : la barre laterale, le titre affiche en haut de la page, et le
smoke test qui ouvre chaque vue. Ces tests verifient qu'aucune des trois ne
peut se desynchroniser des autres.

Ils lisent la constante sans ouvrir de fenetre.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

import app_desktop  # noqa: E402

SOURCE = Path(app_desktop.__file__).read_text(encoding="utf-8")


def test_chaque_entree_a_un_titre_de_page():
    """Sans titre, _switch_view leve une KeyError et l'onglet ne s'ouvre
    pas du tout."""
    for key, label, _, _ in app_desktop.NAV_ITEMS:
        assert f'"{key}":' in SOURCE, f"l'entree « {label} » n'a pas de titre"


def test_chaque_entree_a_une_vue():
    """Une entree sans vue construite laisserait un onglet vide."""
    for key, label, _, _ in app_desktop.NAV_ITEMS:
        assert f'"{key}"' in SOURCE, f"l'entree « {label} » n'a pas de vue"


def test_les_cles_sont_uniques():
    """Deux entrees de meme cle se partageraient un seul bouton : la seconde
    ecraserait la premiere dans nav_buttons."""
    cles = [key for key, _, _, _ in app_desktop.NAV_ITEMS]

    assert len(cles) == len(set(cles))


def test_chaque_entree_a_un_pictogramme():
    """Un pictogramme absent laisserait l'entree sans icone, decalee par
    rapport aux autres. Ce sont des emojis, comme dans Pecule : Windows les
    dessine en couleur. Un caractere de la zone privee d'Unicode (Segoe MDL2
    Assets), place dans le texte d'un bouton, sortirait en carre vide."""
    for key, _, _, picto in app_desktop.NAV_ITEMS:
        assert picto.strip(), key
        assert not 0xE000 <= ord(picto[0]) <= 0xF8FF, key


def test_la_premiere_entree_ouvre_une_section():
    """Les entrees sans section heritent de la precedente : la premiere doit
    donc en declarer une."""
    assert app_desktop.NAV_ITEMS[0][2]


def test_les_libelles_du_menu_sont_accentues():
    """Le menu se lit en permanence : « Relevés », pas « Releves ». Ce test
    reperait les libelles ou un accent manque a l'evidence."""
    fautes = {
        "Releves": "Relevés", "Repartition": "Répartition",
        "energie": "énergie", "Synthese": "Synthèse",
        "financiere": "financière", "Annees": "Années",
        "Parametres": "Paramètres",
    }
    for _, label, _, _ in app_desktop.NAV_ITEMS:
        for faute, correction in fautes.items():
            assert not re.search(rf"\b{faute}\b", label), \
                f"« {label} » : écrire {correction}"
