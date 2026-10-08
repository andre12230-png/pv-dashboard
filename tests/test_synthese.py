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


def test_l_achat_au_reseau_reste_affiche(qapp, donnees):
    textes = _textes_de_la_synthese(donnees)
    assert "ACHAT AU RÉSEAU" in textes   # titre en petites capitales
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
                       if "Prime à l'autoconsommation" in t.get_text()]
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
    assert etiquettes == ["Prime à l'autoconsommation\n"
                          + fmt_eur(1440.0, signed=True)]


def test_pas_de_prime_avant_le_premier_versement(qapp, donnees):
    # Moins d'un an de donnees : aucune prime encore versee, aucune marche.
    donnees.df = donnees.df.loc[:"2023-03-31"]
    assert _prime_sur_le_graphique(donnees) == ([], 0)


def test_le_bilan_net_ne_s_affiche_qu_une_fois(qapp, donnees):
    """Relecture du 29/09/2026 : le bilan net figurait deux fois (carte
    « Bilan net global » en haut, tuile « Bilan net actuel » en bas), meme
    calcul, meme explication. On garde la carte du haut."""
    from views.accounts import AccountsView
    am = amortissement(donnees)
    montant = fmt_eur(am["recupere"] - 20000.0, signed=True)
    vue = AccountsView(donnees, LIGHT)
    vue.refresh("all")
    textes = [lbl.text() for lbl in vue.findChildren(QLabel)]
    assert textes.count(montant) == 1
    assert any("BILAN DE L'INSTALLATION" in t for t in textes)
    assert not any("BILAN NET ACTUEL" in t.upper() for t in textes)


def test_les_cartes_du_haut_ont_l_allure_des_tuiles(qapp, donnees):
    """Relecture du 29/09/2026 : les six cartes du haut n'avaient ni le trait
    de 3 px des tuiles chiffrees, ni leur titre en petites capitales, et
    leurs pastilles d'icone etaient de tons pastel absents de la palette."""
    import re

    from gui_theme import qss_for
    from gui_widgets import AccountCard
    from views.accounts import AccountsView
    vue = AccountsView(donnees, LIGHT)
    vue.refresh("all")
    cartes = vue.findChildren(AccountCard)
    assert len(cartes) == 6
    for carte in cartes:
        assert carte.property("variant") in ("credit", "debit")
        nom = carte.findChild(QLabel, "AccountName").text()
        assert nom == nom.upper()
        assert carte.findChild(QLabel, "AccountIcon") is None
    qss = qss_for(LIGHT)
    bloc = re.search(r'QFrame\[role="account"\]\s*\{([^}]*)\}', qss).group(1)
    assert "border-top-width: 3px" in bloc
    assert 'QFrame[role="account"][variant="credit"]' in qss
    assert 'QFrame[role="account"][variant="debit"]' in qss


def _labels(donnees, periode: str) -> list[str]:
    from views.accounts import AccountsView
    vue = AccountsView(donnees, LIGHT)
    vue.refresh(periode)
    return [lbl.text() for lbl in vue.findChildren(QLabel)]


def test_la_part_de_la_periode_dit_laquelle(qapp, donnees):
    """Relecture du 29/09/2026 : « +13,74 € sur période » ne disait pas
    quelle periode, et sur « toute la periode » la ligne repetait le montant
    juste au-dessus."""
    mois = _labels(donnees, "month-2024-01")
    assert "dont +31,00\xa0€ en janvier 2024" in mois          # 1 €/jour
    assert "dont +62,00\xa0€ en janvier 2024" in mois          # 2 €/jour
    assert "dont -155,00\xa0€ en janvier 2024" in mois         # 5 €/jour
    tout = _labels(donnees, "all")
    assert not any("sur période" in t or t.startswith("dont ") for t in tout)


def test_ni_jargon_ni_abreviation(qapp, donnees):
    import re
    textes = _labels(donnees, "all")
    joint = " | ".join(textes)
    assert not re.search(r"\bROI\b", joint)
    assert not re.search(r"\bautoconso\b", joint, re.IGNORECASE)
    assert "anniv." not in joint
    assert any("TEMPS DE RETOUR" in t.upper() for t in textes)
    assert any("PRIME À L'AUTOCONSOMMATION" in t for t in textes)


def test_un_seul_tiret_dans_les_sous_titres(qapp, donnees):
    """« Recettes — surplus injecté » mais « Coût évité - kWh non achetés » :
    un seul tiret, le long."""
    from gui_widgets import AccountCard
    from views.accounts import AccountsView
    vue = AccountsView(donnees, LIGHT)
    vue.refresh("all")
    for carte in vue.findChildren(AccountCard):
        for nom in ("AccountType", "AccountTrend"):
            assert " - " not in carte.findChild(QLabel, nom).text()


def test_graduations_avec_espace_des_milliers(qapp, donnees):
    """L'axe du remboursement affichait « 10000 » ; les montants s'ecrivent
    « 9 000,00 € »."""
    from gui_widgets import MplCanvas
    from views.accounts import AccountsView
    vue = AccountsView(donnees, LIGHT)
    vue.refresh("all")
    ax = vue.findChildren(MplCanvas)[0].fig.axes[0]
    # Avec l'unite sur chaque graduation (30/09/2026 : plus de « € » couche).
    assert ax.yaxis.get_major_formatter()(20000, 0) == "20\xa0000\xa0€"


# --- Pas d'extrapolation avant un an de relevés (audit du 04/10/2026) -------

def _quelques_jours(donnees, debut: str, fin: str):
    jours = pd.date_range(debut, fin, freq="D")
    df = pd.DataFrame({"revenu_vente_eur": 1.0, "economie_eur": 2.0,
                       "cout_reseau_eur": 5.0}, index=jours)
    df["annee_oa"] = calc.assign_oa_year(df.index, donnees.start_oa).values
    donnees.df = df
    return donnees


def test_une_semaine_ne_donne_ni_rythme_ni_temps_de_retour(qapp, donnees):
    """Une semaine de releves affichait « 632,75 € par an, moyenne sur
    0,0 an » et « remboursement vers 2039 » ; trois mois commences au
    printemps raccourcissaient le temps de retour de six ans, en octobre ils
    l'allongeaient de dix-huit. Avant un an de releves, on n'extrapole pas."""
    _quelques_jours(donnees, "2024-06-01", "2024-06-07")
    am = amortissement(donnees)
    assert am["gains_an"] is None
    assert am["roi_an"] is None
    assert am["jours_avant_estimation"] == 365 - 7
    textes = _textes_de_la_synthese(donnees)
    assert "0,0 an" not in textes
    assert "après un an de relevés" in textes


def test_un_an_de_releves_suffit_et_chaque_jour_compte(qapp, donnees):
    """365 jours de releves valent un an : le rythme est la somme des gains,
    sans le jour oublie de l'ancien calcul (dernier - premier)."""
    _quelques_jours(donnees, "2024-01-01", "2024-12-30")   # 365 jours
    am = amortissement(donnees)
    assert am["jours_avant_estimation"] == 0
    assert am["gains_an"] == pytest.approx(3.0 * 365 / (365 / 365.25))
    assert am["roi_an"] is not None


def test_une_semaine_reste_visible_sur_le_graphique(qapp, donnees):
    """Une semaine = un seul point mensuel : matplotlib etalait l'axe sur
    quatre ans et la courbe disparaissait (vu le 04/10/2026, une fois la
    projection retiree avant un an de releves)."""
    from gui_widgets import MplCanvas
    from views.accounts import AccountsView
    _quelques_jours(donnees, "2024-06-01", "2024-06-07")
    vue = AccountsView(donnees, LIGHT)
    vue.refresh("all")
    ax = vue.findChildren(MplCanvas)[0].fig.axes[0]
    gauche, droite = ax.get_xlim()
    assert droite - gauche < 100        # en jours


# --- La vraie date de depart des cumuls (audit du 04/10/2026) -------------

def test_le_cumul_part_du_premier_releve(qapp, donnees):
    """La Synthese disait « Cumul depuis <debut du contrat> » alors que ses
    sommes partent du premier releve (economies d'avant-contrat comprises,
    et rien d'avant les releves pour un contrat ancien)."""
    _quelques_jours(donnees, "2024-03-10", "2025-06-30")
    textes = _textes_de_la_synthese(donnees)
    assert "Cumul depuis le premier relevé, le 10/03/2024" in textes
    assert "Cumul depuis 28/06/2022" not in textes


def test_le_tableau_de_bord_dit_d_ou_part_le_remboursement(qapp, donnees):
    """Releves commences longtemps apres la mise en service : la carte
    disait « Depuis la mise en service » et comptait « 13 % remboursé »."""
    from views.dashboard import DashboardView
    _quelques_jours(donnees, "2024-03-10", "2025-06-30")
    tableau = DashboardView.__new__(DashboardView)
    tableau.data, tableau.theme = donnees, LIGHT
    carte = tableau._carte_remboursement()
    textes = " ".join(lbl.text() for lbl in carte.findChildren(QLabel))
    assert "Depuis le premier relevé, le 10/03/2024" in textes
    assert "avant n'est pas compté" in textes
