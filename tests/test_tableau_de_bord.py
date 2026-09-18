"""Le tableau de bord graphique (v1.30.0) : jauge, barres, badge N-1.

Demande de l'auteur le 14/09/2026 : un tableau de bord « plus graphique,
moins austere ». Ces tests gardent les trois elements dessines a la main et
le badge de comparaison, qui doit compter comme l'onglet Comparaison N vs N-1.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from gui_theme import LIGHT  # noqa: E402
from gui_widgets import BarreRepartition, Jauge, MiniBarres  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


# -----------------------------------------------------------------------------
# Les elements dessines
# -----------------------------------------------------------------------------


def test_la_jauge_reste_entre_0_et_100(qapp):
    assert Jauge(1.7, "#e8b21f", "#333", "#fff").ratio == 1.0
    assert Jauge(-0.2, "#e8b21f", "#333", "#fff").ratio == 0.0


@pytest.mark.parametrize("fabrique", [
    lambda: Jauge(0.39, "#e8b21f", "#333", "#fff", "de soleil"),
    lambda: Jauge(0.0, "#e8b21f", "#333", "#fff"),
    lambda: BarreRepartition([("Consommé 121 kWh", 121, "#199e70"),
                              ("Vendu 179 kWh", 179, "#3987e5")]),
    lambda: BarreRepartition([("Rien", 0, "#199e70"), ("Rien", 0, "#3987e5")]),
    lambda: BarreRepartition([("Tout", 10, "#199e70"), ("Rien", 0, "#3987e5")]),
    lambda: MiniBarres([25.8, 13.0, 24.1], "#e8b21f"),
    lambda: MiniBarres([], "#e8b21f"),
    lambda: MiniBarres([0.0, 0.0], "#e8b21f"),
])
def test_chaque_element_se_dessine_sans_erreur(qapp, fabrique):
    """Y compris a vide : un mois sans soleil ne doit rien faire planter."""
    element = fabrique()
    element.resize(300, element.height())
    assert not element.grab().isNull()


# -----------------------------------------------------------------------------
# Le badge « +24 % vs septembre 2025 »
# -----------------------------------------------------------------------------


def _vue(df: pd.DataFrame):
    from types import SimpleNamespace

    from views.dashboard import DashboardView
    donnees = SimpleNamespace(df=df, start_oa=pd.Timestamp("2022-06-28").date())
    vue = DashboardView.__new__(DashboardView)
    vue.data, vue.theme = donnees, LIGHT
    return vue


def _serie(debut: str, fin: str, kwh: float) -> pd.DataFrame:
    jours = pd.date_range(debut, fin, freq="D")
    return pd.DataFrame({"production_kwh": kwh}, index=jours)


def test_un_mois_en_cours_est_compare_aux_memes_dates(qapp):
    """Septembre releve jusqu'au 13 : on le compare au 1er-13 septembre de
    l'an passe, pas au mois entier (qui donnerait une baisse trompeuse)."""
    df = pd.concat([_serie("2025-09-01", "2025-09-30", 10.0),
                    _serie("2026-09-01", "2026-09-13", 12.0)])
    vue = _vue(df)
    mois = df[df.index >= "2026-09-01"]
    badge = vue._badge_n1(mois, "month-2026-09", mois["production_kwh"].sum())
    assert isinstance(badge, QLabel)
    assert badge.text() == "+20 % vs septembre 2025"


def test_le_meilleur_jour_est_signale(qapp):
    """Etape 2 : la production jour par jour met en valeur le meilleur jour."""
    df = _serie("2026-09-01", "2026-09-13", 20.0)
    df.loc["2026-09-03", "production_kwh"] = 25.8
    carte = _vue(df)._carte_production_jours(df)
    textes = " ".join(lbl.text() for lbl in carte.findChildren(QLabel))
    assert "Meilleur jour 03/09" in textes
    assert "25,8 kWh" in textes


def test_une_annee_se_lit_semaine_par_semaine(qapp):
    df = _serie("2025-01-01", "2025-12-31", 10.0)
    carte = _vue(df)._carte_production_jours(df)
    textes = " ".join(lbl.text() for lbl in carte.findChildren(QLabel))
    assert "SEMAINE PAR SEMAINE" in textes.upper()


def test_amortissement_additionne_ventes_economies_et_primes_versees():
    """Un seul calcul pour la Synthese financiere et le tableau de bord."""
    from types import SimpleNamespace

    import calculations as calc
    from views._helpers import amortissement

    debut = pd.Timestamp("2022-06-28").date()
    jours = pd.date_range("2022-06-28", "2024-06-27", freq="D")
    df = pd.DataFrame({"revenu_vente_eur": 1.0, "economie_eur": 2.0},
                      index=jours)
    df["annee_oa"] = calc.assign_oa_year(df.index, debut).values
    oa = calc.OAConfig(type="surplus", prix_kwh=0.1, prime_par_kwc=300.0,
                       prime_duree=5, duree_contrat=20)
    donnees = SimpleNamespace(
        df=df, oa=oa, start_oa=debut,
        cfg={"installation": {"puissance_kwc": 6.0, "cout_total_eur": 20000.0}})
    am = amortissement(donnees)
    assert am["recupere"] == pytest.approx(
        3.0 * len(df) + am["prime_versee"])
    assert am["prime_totale"] == pytest.approx(
        calc.prime_annuelle(6.0, oa) * 5)
    assert am["roi_an"] == pytest.approx(
        (20000.0 - am["prime_totale"]) / am["gains_an"])


def test_pas_d_amortissement_sans_releve():
    from types import SimpleNamespace

    from views._helpers import amortissement
    assert amortissement(SimpleNamespace(df=pd.DataFrame())) is None


def test_la_part_du_vehicule_se_voit(qapp):
    """Avec des recharges, le reseau se partage en « maison » et
    « vehicule » dans la barre, et une ligne dit la part de la voiture (elle
    ne se voyait plus, reduite a une mention en petit texte gris)."""
    vue = _vue(_serie("2026-09-01", "2026-09-13", 20.0))
    carte = vue._carte_repartition(121.3, 178.7, 186.7, 308.0, 40.4, 59.6,
                                   39.4, 67.8, 8.75)
    barre_origine = carte.findChildren(BarreRepartition)[1]
    assert [libs[0].split(" ")[0] for libs, _, _ in barre_origine.segments] == \
        ["☀️", "🏠", "🚗"]
    assert barre_origine.segments[1][1] == pytest.approx(186.7 - 67.8)
    textes = " ".join(lbl.text() for lbl in carte.findChildren(QLabel))
    assert "🚗 Recharge du véhicule : 67,8 kWh" in textes
    assert "8,75 €" in textes


# 985 px : la barre d'une fenetre de 1280 px (moitie de l'ecran de l'auteur)
@pytest.mark.parametrize("largeur", [985, 650, 450])
def test_le_vehicule_garde_un_libelle_en_moitie_d_ecran(qapp, largeur):
    """Fenetre en moitie d'ecran : le morceau « vehicule » (19 % de la barre)
    etait trop etroit pour « Reseau, vehicule 67,8 kWh » et restait muet
    (remarque de l'auteur, 17/09/2026). Il prend alors un libelle plus court."""
    vue = _vue(_serie("2026-09-01", "2026-09-16", 20.0))
    carte = vue._carte_repartition(147.0, 216.2, 214.9, 361.9, 40.5, 59.5,
                                   40.6, 67.8, 8.75)
    barre = carte.findChildren(BarreRepartition)[1]
    barre.resize(largeur, barre.height())
    affiches = barre.libelles_affiches()
    assert all(affiches), affiches
    # A 450 px, seule l'icone tient avec la police des tests (sans ecran)
    if largeur >= 650:
        assert "67,8" in affiches[2]


def test_sans_recharge_rien_ne_change(qapp):
    vue = _vue(_serie("2026-09-01", "2026-09-13", 20.0))
    carte = vue._carte_repartition(121.3, 178.7, 186.7, 308.0, 40.4, 59.6,
                                   39.4, 0.0)
    assert len(carte.findChildren(BarreRepartition)[1].segments) == 2
    textes = " ".join(lbl.text() for lbl in carte.findChildren(QLabel))
    assert "véhicule" not in textes


def test_pas_de_badge_sans_annee_precedente(qapp):
    df = _serie("2026-09-01", "2026-09-13", 12.0)
    vue = _vue(df)
    assert vue._badge_n1(df, "month-2026-09", 156.0) is None
    assert vue._badge_n1(df, "all", 156.0) is None

# -----------------------------------------------------------------------------
# Le bilan financier s'explique tout seul
# -----------------------------------------------------------------------------
#
# Question d'un utilisateur (18/09/2026) : « le dernier chiffre veut dire
# quoi ? Que l'on a depense en realite cette somme sur l'annee ? » Sa lecture
# etait juste, mais le sous-titre donnait la formule sans dire ce que le
# resultat signifie -- ni que les economies ne sont pas de l'argent recu.


def _cartes_du_bilan(revenu, eco, cout):
    """Refait les quatre cartes comme le tableau de bord, sans la vue."""
    from gui_widgets import KpiCard
    from views._helpers import fmt_eur
    bilan = revenu + eco - cout
    return KpiCard(
        "⚖️ Bilan net", fmt_eur(bilan, signed=True),
        ("ce que l'électricité vous coûte encore" if bilan < 0
         else "ce que le solaire vous rapporte, net"),
        "credit" if bilan >= 0 else "debit",
        aide=f"sorti de votre poche {fmt_eur(cout - revenu)}")


def test_la_carte_porte_une_infobulle(qapp):
    from gui_widgets import KpiCard
    carte = KpiCard("Essai", "12 €", "sous-titre", "credit", aide="explication")
    assert carte.toolTip() == "explication"


def test_une_carte_sans_infobulle_reste_muette(qapp):
    from gui_widgets import KpiCard
    assert KpiCard("Essai", "12 €").toolTip() == ""


def test_le_sous_titre_du_bilan_suit_le_signe(qapp):
    # Bilan negatif : l'electricite coute encore quelque chose.
    negatif = _cartes_du_bilan(revenu=932.08, eco=667.30, cout=1785.34)
    assert negatif.sub.text() == "ce que l'électricité vous coûte encore"
    # Bilan positif : le solaire rapporte plus qu'il n'en coute.
    positif = _cartes_du_bilan(revenu=2000.0, eco=700.0, cout=1500.0)
    assert positif.sub.text() == "ce que le solaire vous rapporte, net"


def test_le_tableau_de_bord_explique_ses_quatre_montants():
    """Les quatre cartes du bilan portent toutes une infobulle, et celle des
    economies dit qu'elles ne sont pas encaissees."""
    source = (Path(__file__).resolve().parents[1]
              / "views" / "dashboard.py").read_text(encoding="utf-8")
    debut = source.index("Bilan financier de la période")
    fin = source.index("]))", debut)
    bloc = source[debut:fin]
    assert bloc.count("aide=") == 4, "une carte du bilan n'explique rien"
    assert "pas de l'argent reçu" in bloc
    assert "sorti de votre poche" in bloc

