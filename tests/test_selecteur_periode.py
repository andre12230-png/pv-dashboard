"""Tests du selecteur de periode en deux menus.

Ces fonctions decident de ce qu'on peut choisir et de ce que font les deux
fleches. Elles sont pures : elles recoivent un tableau de releves et
renvoient des listes, sans toucher a l'interface — c'est ce qui les rend
testables sans ouvrir de fenetre.
"""
from __future__ import annotations

import pandas as pd
import pytest

from views._helpers import (
    MOIS_TOUS,
    PERIOD_ALL,
    annee_de_periode,
    options_annees,
    options_mois,
    periode_voisine,
)

DEBUT_OA = pd.Timestamp("2024-05-12").date()


@pytest.fixture
def df():
    """Trois mois de 2025, deux de 2026, et deux annees OA."""
    jours = pd.to_datetime([
        "2025-04-10", "2025-05-10", "2025-06-10",
        "2026-01-10", "2026-02-10",
    ])
    return pd.DataFrame({"annee_oa": [1, 1, 1, 2, 2]}, index=jours)


def valeurs(options):
    return [v for _, v in options]


def libelles(options):
    return [lab for lab, _ in options]


def test_le_menu_des_annees_reste_court(df):
    """Une entree par annee civile, plus les annees OA : la liste ne grandit
    que d'un cran par an, la ou l'ancienne en gagnait un par mois."""
    opts = options_annees(df, DEBUT_OA)

    assert valeurs(opts) == [PERIOD_ALL, "year-2026", "year-2025", "oa-2", "oa-1"]
    assert libelles(opts)[:3] == ["Toute la période", "2026", "2025"]


def test_le_menu_des_mois_ne_montre_que_l_annee_choisie(df):
    """Choisir 2025 ne doit pas proposer les mois de 2026 : sinon on croit
    avoir change de mois alors qu'on a change d'annee."""
    opts = options_mois(df, 2025)

    assert valeurs(opts) == [MOIS_TOUS, "month-2025-06", "month-2025-05",
                             "month-2025-04"]
    assert libelles(opts) == ["Toute l'année", "Juin", "Mai", "Avril"]


def test_les_mois_sans_releve_ne_sont_pas_proposes(df):
    """Mars 2025 n'a aucun releve : le proposer ouvrirait un ecran vide sans
    dire pourquoi."""
    assert "month-2025-03" not in valeurs(options_mois(df, 2025))


def test_les_mois_accentues(df):
    """Les libelles s'ecrivent en francais correct : « Février », pas
    « Fevrier »."""
    assert libelles(options_mois(df, 2026)) == ["Toute l'année", "Février", "Janvier"]


def test_la_fleche_recule_d_un_mois(df):
    assert periode_voisine(df, DEBUT_OA, "month-2025-06", -1) == "month-2025-05"


def test_la_fleche_franchit_le_changement_d_annee(df):
    """De janvier 2026 on doit tomber sur juin 2025, le mois precedent qui
    porte des releves — et non buter sur le 1er janvier."""
    assert periode_voisine(df, DEBUT_OA, "month-2026-01", -1) == "month-2025-06"


def test_la_fleche_s_arrete_au_bout(df):
    """Rien avant le premier mois ni apres le dernier : c'est ce None qui
    grise la fleche au lieu de la laisser cliquable sans effet."""
    assert periode_voisine(df, DEBUT_OA, "month-2025-04", -1) is None
    assert periode_voisine(df, DEBUT_OA, "month-2026-02", +1) is None


def test_la_fleche_garde_l_echelle(df):
    """Sur une annee, la fleche change d'annee ; sur une annee OA, d'annee OA.
    Elle ne saute jamais d'une echelle a l'autre."""
    assert periode_voisine(df, DEBUT_OA, "year-2026", -1) == "year-2025"
    assert periode_voisine(df, DEBUT_OA, "oa-2", -1) == "oa-1"


def test_toute_la_periode_n_a_pas_de_voisine(df):
    """« Toute la periode » couvre deja tout : les deux fleches sont grisees."""
    assert periode_voisine(df, DEBUT_OA, PERIOD_ALL, -1) is None
    assert periode_voisine(df, DEBUT_OA, PERIOD_ALL, +1) is None


def test_annee_d_une_periode():
    assert annee_de_periode("month-2026-09") == 2026
    assert annee_de_periode("year-2024") == 2024
    # « Toute la periode » et les annees OA sont a cheval sur les annees
    # civiles : aucun mois ne peut leur etre rattache.
    assert annee_de_periode(PERIOD_ALL) is None
    assert annee_de_periode("oa-3") is None


def test_fichier_vide_ne_casse_rien():
    """Au tout premier lancement, avant le moindre releve, les menus doivent
    quand meme se construire."""
    vide = pd.DataFrame({"annee_oa": []}, index=pd.to_datetime([]))

    assert valeurs(options_annees(vide, DEBUT_OA)) == [PERIOD_ALL]
    assert valeurs(options_mois(vide, 2026)) == [MOIS_TOUS]
    assert periode_voisine(vide, DEBUT_OA, "month-2026-09", -1) is None
