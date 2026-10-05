"""Page Statistiques : relecture du 01/10/2026 (capture de l'auteur).

Jeu invente : mise en service le 29/04/2022, releves jusqu'au 29/09/2026,
18 kWh produits chaque jour sur 6 kWc. Cinq annees, dont deux partielles.

    py -m pytest tests/test_statistiques.py
"""
from __future__ import annotations

import math
from types import SimpleNamespace

import pandas as pd
import pytest

pytest.importorskip("PySide6")

from conftest import detruire  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from gui_theme import LIGHT, _contraste  # noqa: E402
from gui_widgets import KpiCard, MplCanvas  # noqa: E402
from views.stats import StatsView  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def vue(qapp):
    jours = pd.date_range("2022-04-29", "2026-09-29", freq="D")
    df = pd.DataFrame({"production_kwh": 18.0, "autoconsommation_kwh": 7.0,
                       "injection_kwh": 11.0, "soutirage_kwh": 9.0}, index=jours)
    data = SimpleNamespace(df=df, cfg={"installation": {"puissance_kwc": 6.0}})
    v = StatsView(data, LIGHT)
    v.populate("all")
    yield v
    detruire(v)


def _axes(vue):
    barres, courbes = (c.fig.axes[0] for c in vue.findChildren(MplCanvas))
    return barres, courbes


def test_la_legende_des_courbes_tient_dans_le_graphique(vue):
    """Cinq annees sur une ligne : la derniere s'affichait « 20. »."""
    _barres, courbes = _axes(vue)
    canvas = courbes.figure.canvas
    canvas.figure.set_size_inches(5, 3.2)
    canvas.draw()
    legende = courbes.get_legend()
    assert [t.get_text() for t in legende.get_texts()] == [
        "2022", "2023", "2024", "2025", "2026"]
    cadre = legende.get_window_extent(canvas.get_renderer())
    assert cadre.x0 >= 0 and cadre.x1 <= canvas.figure.bbox.width


def test_un_mois_incomplet_n_est_pas_trace(vue):
    """Avril 2022 (2 jours, mise en service le 29) tire la courbe vers zero ;
    septembre 2026 n'a que 29 jours sur 30. Ni l'un ni l'autre n'est trace,
    et une phrase le dit."""
    _barres, courbes = _axes(vue)
    lignes = {ligne.get_label(): ligne for ligne in courbes.get_lines()}
    avril_2022 = dict(zip(lignes["2022"].get_xdata(), lignes["2022"].get_ydata(),
                          strict=True))
    assert math.isnan(avril_2022[4])
    assert avril_2022[5] == pytest.approx(31 * 18)          # mai entier, trace
    septembre_2026 = dict(zip(lignes["2026"].get_xdata(),
                              lignes["2026"].get_ydata(), strict=True))
    assert math.isnan(septembre_2026[9])
    textes = " ".join(lbl.text() for lbl in vue.findChildren(QLabel))
    assert "incomplets" in textes


def test_les_milliers_sont_separes(vue):
    """« 1181 », « 8000 » : les milliers se separent, comme « 1 200 » sur la
    meme ligne et partout ailleurs."""
    barres, courbes = _axes(vue)
    for ax in (barres, courbes):
        assert ax.yaxis.get_major_formatter()(8000, 0) == "8 000"
    valeurs = [c.value.text() for c in vue.findChildren(KpiCard)]
    assert "1 095" in valeurs                       # 365 x 18 / 6
    textes = " ".join(lbl.text() for lbl in vue.findChildren(QLabel))
    # 2023, 2024 (bissextile : 1 098) et 2025 : moyenne 1 096.
    assert "moyenne des années complètes : 1 096 kWh/kWc/an" in textes


def test_les_courbes_se_detachent_du_fond(vue):
    """Sans chiffre a cote, une courbe tient 3 pour 1 sur l'ivoire (charte) :
    l'orange de 2022 faisait 2,0 et le bleu clair de 2023, 2,6."""
    from matplotlib.colors import to_hex
    _barres, courbes = _axes(vue)
    for ligne in courbes.get_lines():
        couleur = to_hex(ligne.get_color())
        assert _contraste(couleur, LIGHT["bg_carte"]) >= 3, (ligne.get_label(),
                                                             couleur)


def test_l_unite_du_rendement_s_ecrit_d_une_seule_facon(vue):
    """« (kWh / kWc / AN) » : l'« an » passait en capitales, et l'unite
    s'ecrivait de trois facons sur la page."""
    titres = [lbl.text() for lbl in vue.findChildren(QLabel, "SectionTitle")]
    assert "RENDEMENT SPÉCIFIQUE (kWh/kWc/an)" in titres
    assert not [t for t in titres if "AN)" in t or "kWh / kWc" in t]


def test_les_tuiles_de_rendement_ont_la_meme_largeur(vue, qapp):
    """Les annees partielles, au sous-titre plus long, prenaient plus de
    place que les annees completes : on les voyait d'abord."""
    vue.setAttribute(Qt.WA_DontShowOnScreen, True)
    vue.resize(1100, 900)
    vue.show()
    for _ in range(10):
        qapp.processEvents()
    largeurs = {c.width() for c in vue.findChildren(KpiCard)}
    assert max(largeurs) - min(largeurs) <= 2, largeurs


def test_les_deux_axes_disent_kwh(vue):
    barres, courbes = _axes(vue)
    assert barres.get_ylabel() == courbes.get_ylabel() == "kWh"


def test_sans_mois_complet_la_carte_le_dit(qapp):
    """Audit du 04/10/2026 : une semaine de releves donnait un graphique
    vide, legende « 2026 » et axe « 0, 0, 0, −0 »."""
    jours = pd.date_range("2026-09-15", "2026-09-21", freq="D")
    df = pd.DataFrame({"production_kwh": 18.0, "autoconsommation_kwh": 7.0,
                       "injection_kwh": 11.0, "soutirage_kwh": 9.0}, index=jours)
    v = StatsView(SimpleNamespace(df=df, cfg={"installation": {"puissance_kwc": 6.0}}),
                  LIGHT)
    v.populate("all")
    textes = " ".join(lbl.text() for lbl in v.findChildren(QLabel))
    assert "premier mois complet" in textes
    assert len(v.findChildren(MplCanvas)) == 1     # plus de graphique vide
    detruire(v)
