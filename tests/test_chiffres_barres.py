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
    assert nombre_barre(7812.4) == "7\xa0812"
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


def _redimensionner(fig, largeur_pouces: float) -> None:
    """Ce que fait Qt quand la fenetre change de taille : la figure prend la
    taille du composant, puis matplotlib previent par un « resize_event »."""
    from matplotlib.backend_bases import ResizeEvent
    fig.set_size_inches(largeur_pouces, fig.get_figheight())
    fig.canvas.callbacks.process("resize_event",
                                 ResizeEvent("resize_event", fig.canvas))


def test_le_choix_suit_la_taille_reelle_du_graphique():
    """29/09/2026 : le choix a plat / debout se faisait une seule fois, sur
    la taille theorique du graphique (8 pouces). A l'ecran, le graphique est
    plus large et les chiffres restaient debout alors qu'ils tenaient. Le
    choix se refait a chaque changement de taille, sur la vraie largeur des
    chiffres et le vrai ecart entre deux barres."""
    fig, ax = plt.subplots(figsize=(6, 3), dpi=100)
    b = ax.bar(range(31), [10.7] * 31, 0.7)
    chiffres_sur_barres(ax, [b], decimales=1)
    assert {t.get_rotation() for t in ax.texts} == {90}     # trop serre
    _redimensionner(fig, 20)
    assert {t.get_rotation() for t in ax.texts} == {0}      # ca tient
    _redimensionner(fig, 6)
    assert {t.get_rotation() for t in ax.texts} == {90}     # et retour
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
    assert "7\xa0812" in _textes(ax) and "5\xa0300" in _textes(ax)
    assert len(ax.texts) == 8


def test_les_courbes_des_annees_se_distinguent_sans_la_couleur(qapp):
    """30/09/2026 : les courbes 2024, 2025, 2026 ne differaient que par leur
    couleur (meme trait, memes points ronds). Chaque annee a maintenant son
    trait et sa forme de point ; les mois s'ecrivent comme ailleurs."""
    from gui_theme import LIGHT
    from views.stats import StatsView
    jours = pd.date_range("2024-01-01", "2026-09-28", freq="D")
    df = pd.DataFrame({"production_kwh": 10.0}, index=jours)
    vue = StatsView.__new__(StatsView)
    vue.theme = LIGHT
    ax = _axes(vue._monthly_lines(df))[0]
    courbes = ax.get_lines()
    assert len(courbes) == 3
    assert len({c.get_marker() for c in courbes}) == 3
    assert len({c.get_linestyle() for c in courbes}) == 3
    assert [t.get_text() for t in ax.get_xticklabels()] == [
        "janv.", "févr.", "mars", "avr.", "mai", "juin",
        "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def test_les_tuiles_de_la_repartition_ont_leur_trait(qapp):
    """30/09/2026 : les trois tuiles du haut de la Repartition energie
    n'avaient pas le trait de 3 px des tuiles chiffrees (charte)."""
    import re as _re

    from gui_theme import LIGHT, qss_for
    qss = qss_for(LIGHT)
    bloc = _re.search(r'QFrame\[role="tile"\]\s*\{([^}]*)\}', qss).group(1)
    assert "border-top-width: 3px" in bloc
    for variante in ("solaire", "prod", "credit", "debit"):
        assert f'QFrame[role="tile"][variant="{variante}"]' in qss


def test_statistiques_l_annee_partielle_est_hachuree(qapp):
    """Charte : une periode incomplete reste tracee mais hachuree, et la
    legende garde des carres pleins (audit du 08/10/2026 : seule la mention
    « (partielle) » le disait)."""
    from matplotlib.patches import Patch

    from gui_theme import LIGHT
    from views.stats import StatsView

    annees = pd.DataFrame({
        "production_kwh": [7812.0, 4000.0],
        "autoconsommation_kwh": [3100.0, 1500.0],
        "injection_kwh": [4712.0, 2500.0],
        "soutirage_kwh": [5200.0, 2600.0],
    }, index=[2025, 2026])
    vue = StatsView.__new__(StatsView)
    vue.theme = LIGHT
    ax = _axes(vue._yearly_bars(annees, {2026}))[0]
    barres = ax.patches
    hachurees = [b for b in barres if b.get_hatch()]
    assert len(hachurees) == 4                   # les quatre de 2026
    poignees = ax.get_legend().legend_handles
    assert all(isinstance(p, Patch) and not p.get_hatch() for p in poignees)
