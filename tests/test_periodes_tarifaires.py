"""Le prix d'un jour dans une grille tarifaire, quelle que soit la grille.

Audit du 13/10/2026 : un jour tombe dans un trou entre deux periodes (fin le
31/07, debut suivant le 02/08) valait NaN dans les calculs vectorises, et
sortait des sommes sans un mot : cout d'achat, et base de TVA trop basse. La
version jour par jour, elle, prenait la DERNIERE periode de la liste. Et deux
periodes qui se chevauchent donnaient deux prix differents selon la fonction.

Regle unique desormais : la periode qui contient le jour (la plus recente si
plusieurs) ; dans un trou, le tarif precedent reste en vigueur ; avant la
premiere periode, la premiere. Prix inventes.
"""
from __future__ import annotations

import pandas as pd
import pytest

import calculations as calc

TROU = [
    {"debut": "2026-01-01", "fin": "2026-07-31", "prix": 1.0},
    {"debut": "2026-08-02", "fin": "2026-12-31", "prix": 2.0},
    {"debut": "2027-01-01", "fin": None, "prix": 3.0},
]
CHEVAUCHEMENT = [
    {"debut": "2026-01-01", "fin": "2026-08-31", "prix": 1.0},
    {"debut": "2026-08-01", "fin": None, "prix": 2.0},
]
IMBRIQUEE = [
    {"debut": "2026-01-01", "fin": "2026-12-31", "prix": 1.0},
    {"debut": "2026-06-01", "fin": "2026-06-30", "prix": 2.0},
]
# Ecrite dans le desordre : la regle ne depend pas de l'ordre du fichier.
DESORDRE = [
    {"debut": "2026-08-02", "fin": None, "prix": 2.0},
    {"debut": "2026-01-01", "fin": "2026-07-31", "prix": 1.0},
]

ATTENDUS = [
    (TROU, "2026-08-01", 1.0),          # le tarif precedent reste en vigueur
    (TROU, "2026-08-02", 2.0),
    (TROU, "2025-12-31", 1.0),          # avant la premiere : la premiere
    (TROU, "2030-05-01", 3.0),
    (CHEVAUCHEMENT, "2026-08-15", 2.0),  # la plus recente l'emporte
    (CHEVAUCHEMENT, "2026-07-31", 1.0),
    (IMBRIQUEE, "2026-06-15", 2.0),
    (IMBRIQUEE, "2026-07-15", 1.0),     # la grande periode reprend
    (DESORDRE, "2026-08-01", 1.0),
]


@pytest.mark.parametrize("periodes, jour, prix", ATTENDUS)
def test_prix_du_jour(periodes, jour, prix):
    assert calc._valeur_periode(pd.Timestamp(jour), periodes, "prix") == prix
    serie = calc._valeur_periode_series(
        pd.DatetimeIndex([jour]), periodes, "prix")
    assert serie.iloc[0] == prix


@pytest.mark.parametrize("periodes", [TROU, CHEVAUCHEMENT, IMBRIQUEE,
                                      DESORDRE])
def test_les_deux_calculs_donnent_le_meme_prix_chaque_jour(periodes):
    jours = pd.date_range("2025-12-01", "2027-02-28", freq="D")
    serie = calc._valeur_periode_series(jours, periodes, "prix")
    assert not serie.isna().any()
    un_par_un = [calc._valeur_periode(j, periodes, "prix") for j in jours]
    assert serie.tolist() == un_par_un


def test_base_de_tva_sans_jour_perdu_dans_un_trou():
    grille = [
        {"debut": "2026-01-01", "fin": "2026-07-31", "prix_ht": 0.20,
         "accise": 0.03},
        {"debut": "2026-08-02", "fin": None, "prix_ht": 0.22,
         "accise": 0.03},
    ]
    jours = pd.date_range("2026-07-30", "2026-08-03", freq="D")
    prix = calc.prix_lasm_serie(jours, grille)
    assert not prix.isna().any()
    assert prix.loc["2026-08-01"] == pytest.approx(0.23)


def test_tarif_bleu_sans_jour_perdu_dans_un_trou():
    tranches = [
        {"debut": "2023-01-01", "fin": "2023-06-30", "prix": 0.20},
        {"debut": "2023-07-02", "fin": "2023-12-31", "prix": 0.25},
    ]
    jours = pd.date_range("2023-06-29", "2023-07-03", freq="D")
    serie = calc._prix_bleu_series(jours, tranches)
    assert not serie.isna().any()
    assert serie.loc["2023-07-01"] == pytest.approx(0.20)
    assert calc._prix_bleu_for_date(pd.Timestamp("2023-07-01"),
                                    tranches) == pytest.approx(0.20)


def test_abonnement_bleu_dans_un_trou_garde_le_precedent():
    bleu = calc.BleuBaseConfig.__new__(calc.BleuBaseConfig)
    bleu.abonnement_tranches = [
        {"debut": "2023-01-01", "fin": "2023-06-30", "montant": 10.0},
        {"debut": "2023-07-02", "fin": "2023-12-31", "montant": 12.0},
        {"debut": "2024-01-01", "fin": "2024-12-31", "montant": 14.0},
    ]
    jour = pd.Timestamp("2023-07-01")
    assert jour < calc.CUTOFF_OCTOPUS
    assert calc.abonnement_mensuel_eur(jour, bleu, None) == 10.0
