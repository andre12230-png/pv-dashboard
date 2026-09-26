"""Synthese financiere : le bilan net global.

Decision de l'auteur du 14/09/2026 : le bilan est ce que l'installation a
rapporte (ventes EDF OA + economies + primes deja versees) moins ce qu'elle a
coute. La facture reseau n'y entre plus : on la paierait meme sans panneaux,
et ce que les panneaux y changent est deja compte dans les economies. Avant,
la page affichait un bilan tres negatif a cote d'une installation
remboursee a 25 %.
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
        vend=True, acheteur="EDF OA", d_acheteur="d'EDF OA",
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


# --- La marche de la prime sur le graphique « Récupéré » -------------------
# La prime a l'autoconsommation arrive d'un coup, a la facture anniversaire
# EDF OA : la courbe fait une marche. Un utilisateur l'a prise pour une
# anomalie (23/09/2026). La marche est juste - avant ce versement, l'argent
# n'etait pas la - mais elle doit se lire sans explication : un point sur
# chaque versement, et une seule etiquette (plusieurs se chevaucheraient
# quand la prime est versee sur 5 ans).

def _prime_sur_le_graphique(donnees) -> tuple[list[str], int]:
    """(etiquettes de la prime, nombre de points de versement)."""
    from gui_widgets import MplCanvas
    from views.accounts import AccountsView
    vue = AccountsView(donnees, LIGHT)
    vue.refresh("all")
    textes, points = [], 0
    for canvas in vue.findChildren(MplCanvas):
        for ax in canvas.fig.axes:
            textes += [t.get_text() for t in ax.texts
                       if "Prime autoconso" in t.get_text()]
            points += sum(len(ligne.get_xdata()) for ligne in ax.lines
                          if ligne.get_gid() == "versements_prime")
    return textes, points


def test_chaque_versement_de_prime_est_marque(qapp, donnees):
    # Deux annees OA closes dans la fixture : deux versements de 360 EUR
    # (300 EUR/kWc x 6 kWc / 5 ans), deux points, une seule etiquette.
    etiquettes, points = _prime_sur_le_graphique(donnees)
    assert points == 2
    assert len(etiquettes) == 1
    assert "2 versements de " + fmt_eur(360.0) in etiquettes[0]


def test_prime_versee_en_une_fois(qapp, donnees):
    # Contrat recent : toute la prime d'un coup, la premiere annee.
    donnees.oa = calc.OAConfig(type="surplus", prix_kwh=0.1, prime_par_kwc=240.0,
                               prime_duree=1, duree_contrat=20)
    etiquettes, points = _prime_sur_le_graphique(donnees)
    assert points == 1
    assert etiquettes == ["Prime autoconso\n" + fmt_eur(1440.0, signed=True)]


def test_pas_de_prime_avant_le_premier_versement(qapp, donnees):
    # Moins d'un an de donnees : aucune prime encore versee, aucune marche.
    donnees.df = donnees.df.loc[:"2023-03-31"]
    assert _prime_sur_le_graphique(donnees) == ([], 0)
