"""Sans grille EDF de comparaison, plus de prix inventes (audit du 08/10/2026).

Quand la section comparaison_edf manquait, calculations.periodes_edf prenait
des prix EDF de 2026 ecrits dans le code : la comparaison se faisait en
silence a des tarifs qui vieillissent. Desormais : aucune grille, et la page
dit quoi renseigner. Donnees inventees.

    py -m pytest tests/test_grille_edf_absente.py
"""

from __future__ import annotations

import pandas as pd

import calculations as calc


def test_sans_section_aucune_grille():
    assert calc.periodes_edf({}) == []


def test_l_ancienne_forme_complete_reste_lue():
    ancien = {"abonnement_mensuel_eur": 20.0, "prix_kwh_eur": 0.2,
              "prix_hp_eur_kwh": 0.22, "prix_hc_eur_kwh": 0.16}
    (p,) = calc.periodes_edf(ancien)
    assert (p["abonnement"], p["prix_base"], p["prix_hp"], p["prix_hc"]) == (
        20.0, 0.2, 0.22, 0.16)


def test_comparaison_vide_sans_grille():
    jours = pd.date_range("2026-03-01", periods=3, freq="D")
    df = pd.DataFrame({"soutirage_kwh": 10.0, "cout_reseau_eur": 2.0,
                       "abonnement_eur": 0.6}, index=jours)
    assert calc.comparaison_octopus_edf(df, []).empty


def test_la_page_dit_quoi_renseigner():
    from views.octopus_edf import message_sans_grille
    texte = message_sans_grille("EDF")
    assert "comparaison_edf" in texte and "config.yaml" in texte
    assert "EDF" in texte
