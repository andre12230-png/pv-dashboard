"""Les chiffres au-dessus des barres (demande de l'auteur du 15/09/2026).

Chaque graphique en barres doit ecrire la valeur de chaque barre, a la
francaise, et les poser debout quand ils ne tiennent pas a l'horizontale.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from views._helpers import chiffres_sur_barres, nombre_barre  # noqa: E402


def test_nombre_a_la_francaise():
    assert nombre_barre(7812.4) == "7 812"
    assert nombre_barre(25.14, 1) == "25,1"
    assert nombre_barre(0) == ""
    assert nombre_barre(0.04, 1) == ""
    assert nombre_barre(None) == ""
    assert nombre_barre(float("nan")) == ""


def _textes(ax) -> list[str]:
    return [t.get_text() for t in ax.texts]


def test_une_barre_un_chiffre():
    fig, ax = plt.subplots(figsize=(8, 3), dpi=100)
    b = ax.bar([0, 1, 2], [120.0, 0.0, 95.6], 0.6)
    chiffres_sur_barres(ax, [b])
    assert _textes(ax) == ["120", "", "96"]
    assert all(t.get_rotation() == 0 for t in ax.texts)
    plt.close(fig)


def test_barres_serrees_chiffres_debout():
    """Soixante jours sur un graphique : a l'horizontale ils se
    chevaucheraient."""
    fig, ax = plt.subplots(figsize=(8, 3), dpi=100)
    b = ax.bar(range(60), [2150.0] * 60, 0.7)
    chiffres_sur_barres(ax, [b])
    assert {t.get_rotation() for t in ax.texts} == {90}
    plt.close(fig)


# -----------------------------------------------------------------------------
# Les graphiques des feuilles
# -----------------------------------------------------------------------------

pytest.importorskip("PySide6")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


def _axes(carte):
    from gui_widgets import MplCanvas
    return [ax for c in carte.findChildren(MplCanvas) for ax in c.fig.axes]


def test_production_jour_par_jour_chaque_jour_chiffre(qapp):
    from types import SimpleNamespace

    from gui_theme import LIGHT
    from views.dashboard import DashboardView

    jours = pd.date_range("2026-09-01", "2026-09-05", freq="D")
    df = pd.DataFrame({"production_kwh": [20.0, 25.8, 18.2, 0.0, 22.4]},
                      index=jours)
    vue = DashboardView.__new__(DashboardView)
    vue.data = SimpleNamespace(df=df, start_oa=pd.Timestamp("2022-06-28").date())
    vue.theme = LIGHT
    ax = _axes(vue._carte_production_jours(df))[0]
    assert _textes(ax) == ["20,0", "25,8", "18,2", "", "22,4"]
    # Le meilleur jour reste mis en valeur : son chiffre est en gras.
    gras = [t.get_text() for t in ax.texts if t.get_fontweight() == "bold"]
    assert gras == ["25,8"]


def test_statistiques_annuelles_chiffrees(qapp):
    from gui_theme import LIGHT
    from views.stats import StatsView

    annees = pd.DataFrame({
        "production_kwh": [7812.0, 7650.0],
        "autoconsommation_kwh": [3100.0, 3000.0],
        "injection_kwh": [4712.0, 4650.0],
        "soutirage_kwh": [5200.0, 5300.0],
    }, index=[2024, 2025])
    vue = StatsView.__new__(StatsView)
    vue.theme = LIGHT
    ax = _axes(vue._yearly_bars(annees, set()))[0]
    assert "7 812" in _textes(ax) and "5 300" in _textes(ax)
    assert len(ax.texts) == 8
