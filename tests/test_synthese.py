"""Synthese financiere : le bilan net global.

Decision de l'auteur du 14/09/2026 : le bilan est ce que l'installation a
rapporte (ventes EDF OA + economies + primes deja versees) moins ce qu'elle a
coute. La facture reseau n'y entre plus : on la paierait meme sans panneaux,
et ce que les panneaux y changent est deja compte dans les economies. Avant,
la page affichait -21 580 EUR a cote d'une installation remboursee a 25 %.
"""
from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

import calculations as calc  # noqa: E402
from gui_theme import LIGHT  # noqa: E402
from views._helpers import amortissement, fmt_eur  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def donnees():
    debut = pd.Timestamp("2022-06-28").date()
    jours = pd.date_range("2022-06-28", "2024-06-27", freq="D")
    df = pd.DataFrame({"revenu_vente_eur": 1.0, "economie_eur": 2.0,
                       "cout_reseau_eur": 5.0}, index=jours)
    df["annee_oa"] = calc.assign_oa_year(df.index, debut).values
    oa = calc.OAConfig(type="surplus", prix_kwh=0.1, prime_par_kwc=300.0,
                       prime_duree=5, duree_contrat=20)
    return SimpleNamespace(
        df=df, oa=oa, start_oa=debut, current_period="all",
        cfg={"installation": {"puissance_kwc": 6.0, "cout_total_eur": 20000.0,
                              "date_mise_en_service": "2022-06-28"}})


def _textes_de_la_synthese(donnees) -> str:
    from views.accounts import AccountsView
    vue = AccountsView(donnees, LIGHT)
    vue.refresh("all")
    return " ".join(lbl.text() for lbl in vue.findChildren(QLabel))


def test_le_bilan_ne_soustrait_plus_la_facture_reseau(qapp, donnees):
    am = amortissement(donnees)
    attendu = am["recupere"] - 20000.0
    textes = _textes_de_la_synthese(donnees)
    assert fmt_eur(attendu, signed=True) in textes
    # L'ancien calcul (facture deduite) ne doit plus apparaitre nulle part.
    ancien = attendu - donnees.df["cout_reseau_eur"].sum()
    assert fmt_eur(ancien, signed=True) not in textes


def test_la_facture_reseau_reste_affichee(qapp, donnees):
    textes = _textes_de_la_synthese(donnees)
    assert "Facture réseau" in textes
    assert fmt_eur(-donnees.df["cout_reseau_eur"].sum(), signed=True) in textes
