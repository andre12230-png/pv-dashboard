"""Graphique « Production mensuelle » des Statistiques (16/10/2026).

Cinq courbes de couleurs superposees faisaient brouillon (avis de l'auteur
du 16/10/2026). Proposition A retenue : l'annee la plus recente en jaune,
chaque mois avec son chiffre ; les autres annees resumees par leur moyenne
(trait gris en tirets) et une zone grise de la plus basse a la plus haute.
Le graphique reste lisible quel que soit le nombre d'annees.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402

from tests.test_contraste import contraste  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


def _axes(carte):
    from gui_widgets import MplCanvas
    return [ax for c in carte.findChildren(MplCanvas) for ax in c.fig.axes]


def _vue(theme):
    from views.stats import StatsView
    vue = StatsView.__new__(StatsView)
    vue.theme = theme
    return vue


def _releves(debut: str, fin: str, valeurs: dict[int, float]) -> pd.DataFrame:
    """Une production quotidienne constante par annee (valeurs inventees)."""
    jours = pd.date_range(debut, fin, freq="D")
    prod = [valeurs[j.year] for j in jours]
    return pd.DataFrame({"production_kwh": prod}, index=jours)


@pytest.fixture
def trois_annees():
    # 2024 et 2025 completes, 2026 jusqu'au 15 octobre : octobre incomplet.
    return _releves("2024-01-01", "2026-10-15",
                    {2024: 10.0, 2025: 20.0, 2026: 30.0})


def _ligne(ax, etiquette):
    return next(ligne for ligne in ax.get_lines() if ligne.get_label() == etiquette)


def test_l_annee_la_plus_recente_est_en_jaune(qapp, trois_annees):
    from gui_theme import CHART_COLORS_CLAIR, LIGHT
    ax = _axes(_vue(LIGHT)._monthly_lines(trois_annees))[0]
    annee = _ligne(ax, "2026")
    assert annee.get_color() == CHART_COLORS_CLAIR["production"]
    assert annee.get_linewidth() >= 2.5
    # Plus que deux courbes : l'annee et la moyenne des autres.
    assert len(ax.get_lines()) == 2


def test_chaque_mois_complet_de_l_annee_a_son_chiffre(qapp, trois_annees):
    from gui_theme import LIGHT
    ax = _axes(_vue(LIGHT)._monthly_lines(trois_annees))[0]
    textes = [t.get_text() for t in ax.texts]
    # Neuf mois complets (janvier a septembre) ; octobre n'est pas trace.
    assert len(textes) == 9
    # Janvier 2026 : 31 jours a 30 kWh, milliers separes.
    assert textes[0] == "930"
    assert "900" in textes  # avril, 30 jours


def test_les_autres_annees_sont_resumees(qapp, trois_annees):
    from gui_theme import LIGHT
    ax = _axes(_vue(LIGHT)._monthly_lines(trois_annees))[0]
    moyenne = _ligne(ax, "Moyenne des autres années")
    assert moyenne.get_linestyle() == "--"
    # Janvier : 310 kWh en 2024, 620 en 2025 -> moyenne 465.
    assert moyenne.get_ydata()[0] == pytest.approx(465.0)
    zones = [c for c in ax.collections if isinstance(c, PolyCollection)]
    assert len(zones) == 1
    etendue = zones[0].get_paths()[0].vertices[:, 1]
    assert etendue.min() == pytest.approx(290.0)  # fevrier 2024 : 29 x 10
    assert etendue.max() == pytest.approx(620.0)  # 31 jours x 20


def test_une_seule_annee_ni_moyenne_ni_zone(qapp):
    from gui_theme import LIGHT
    df = _releves("2026-01-01", "2026-06-30", {2026: 12.0})
    ax = _axes(_vue(LIGHT)._monthly_lines(df))[0]
    assert [ligne.get_label() for ligne in ax.get_lines()] == ["2026"]
    assert not [c for c in ax.collections if isinstance(c, PolyCollection)]


def test_janvier_sans_mois_complet_montre_l_annee_d_avant(qapp):
    """Le 5 janvier, l'annee nouvelle n'a aucun mois complet : la courbe
    jaune serait vide. On montre alors la derniere annee qui en a un."""
    from gui_theme import LIGHT
    df = _releves("2025-01-01", "2027-01-05",
                  {2025: 10.0, 2026: 20.0, 2027: 30.0})
    ax = _axes(_vue(LIGHT)._monthly_lines(df))[0]
    labels = [ligne.get_label() for ligne in ax.get_lines()]
    assert "2026" in labels and "2027" not in labels
    assert "Moyenne des autres années" in labels


def test_les_mois_s_ecrivent_comme_ailleurs(qapp, trois_annees):
    from gui_theme import LIGHT
    ax = _axes(_vue(LIGHT)._monthly_lines(trois_annees))[0]
    assert [t.get_text() for t in ax.get_xticklabels()] == [
        "janv.", "févr.", "mars", "avr.", "mai", "juin",
        "juil.", "août", "sept.", "oct.", "nov.", "déc."]


@pytest.mark.parametrize("nom", ["LIGHT", "DARK"])
def test_moyenne_et_chiffres_se_lisent(qapp, trois_annees, nom):
    """La moyenne (trait sans chiffre) tient 3 pour 1, les chiffres 4,5."""
    import gui_theme
    theme = getattr(gui_theme, nom)
    ax = _axes(_vue(theme)._monthly_lines(trois_annees))[0]
    fond = theme["bg_carte"]
    moyenne = _ligne(ax, "Moyenne des autres années")
    assert contraste(matplotlib.colors.to_hex(moyenne.get_color()), fond) >= 3.0
    for t in ax.texts:
        assert contraste(matplotlib.colors.to_hex(t.get_color()), fond) >= 4.5


def test_mois_sans_autre_annee_pas_de_moyenne(qapp):
    """Mise en service en mai 2025 : de janvier a avril, rien a comparer."""
    from gui_theme import LIGHT
    df = _releves("2025-05-01", "2026-08-31", {2025: 10.0, 2026: 20.0})
    ax = _axes(_vue(LIGHT)._monthly_lines(df))[0]
    moyenne = _ligne(ax, "Moyenne des autres années")
    assert np.isnan(moyenne.get_ydata()[:4]).all()
    assert not np.isnan(moyenne.get_ydata()[4])


def test_l_annee_choisie_passe_en_jaune(qapp, trois_annees):
    """Le selecteur « Période » choisit l'annee mise en avant (16/10/2026)."""
    from gui_theme import LIGHT
    ax = _axes(_vue(LIGHT)._monthly_lines(trois_annees, annee=2024))[0]
    assert {ligne.get_label() for ligne in ax.get_lines()} == {
        "2024", "Moyenne des autres années"}


def test_une_annee_sans_mois_complet_le_dit(qapp):
    """Le 5 janvier, 2027 choisie : pas de courbe jaune vide sans un mot, ni
    une autre annee en jaune a sa place. Les autres restent tracees."""
    from PySide6.QtWidgets import QLabel

    from gui_theme import LIGHT
    df = _releves("2025-01-01", "2027-01-05",
                  {2025: 10.0, 2026: 20.0, 2027: 30.0})
    carte = _vue(LIGHT)._monthly_lines(df, annee=2027)
    ax = _axes(carte)[0]
    assert [ligne.get_label() for ligne in ax.get_lines()] == [
        "Moyenne des autres années"]
    textes = " ".join(lbl.text() for lbl in carte.findChildren(QLabel))
    assert "2027 n'a pas encore de mois complet" in textes


def test_la_legende_de_la_moyenne_ne_cite_pas_l_annee_choisie(qapp, trois_annees):
    """Revue du 16/10/2026 : 2024 choisie, la legende disait « Moyenne 2022
    à 2026 », comme si 2024 y etait comptee alors qu'elle en est exclue."""
    from gui_theme import LIGHT
    ax = _axes(_vue(LIGHT)._monthly_lines(trois_annees, annee=2025))[0]
    libelles = [t.get_text() for t in ax.get_legend().get_texts()]
    assert libelles == ["2025", "Moyenne des autres années",
                        "Écart des autres années"]
