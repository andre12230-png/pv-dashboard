"""Page Statistiques : pistes de la relecture du 16/10/2026.

La page dit quelle annee est en avant, ce que compte la moyenne, et la zone
grise se lit au survol (charte : une zone pale porte son chiffre ou une
infobulle).

Jeu invente : 2023 a 2025 entieres, 2026 jusqu'au 29/09, trois niveaux de
production pour que plus basse, moyenne et plus haute different.

    py -m pytest tests/test_statistiques_lisibilite.py
"""
from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

pytest.importorskip("PySide6")

from conftest import detruire  # noqa: E402
from matplotlib.backend_bases import MouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from gui_theme import LIGHT  # noqa: E402
from gui_widgets import KpiCard, MplCanvas  # noqa: E402
from views.stats import StatsView  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _vue(debut="2023-01-01", fin="2026-09-29"):
    jours = pd.date_range(debut, fin, freq="D")
    niveaux = {2023: 10.0, 2024: 20.0, 2025: 30.0, 2026: 15.0}
    df = pd.DataFrame({"production_kwh": [niveaux[j.year] for j in jours],
                       "autoconsommation_kwh": 7.0, "injection_kwh": 3.0,
                       "soutirage_kwh": 9.0}, index=jours)
    data = SimpleNamespace(df=df, cfg={"installation": {"puissance_kwc": 6.0}})
    return StatsView(data, LIGHT)


@pytest.fixture
def vue(qapp):
    v = _vue()
    yield v
    detruire(v)


def _tuile(vue, annee: int) -> KpiCard:
    return next(c for c in vue.findChildren(KpiCard)
                if str(annee) in c.label.text())


def _textes(vue) -> str:
    return " ".join(lbl.text() for lbl in vue.findChildren(QLabel))


def _survoler(vue, mois: float, kwh: float) -> str:
    """Passe la souris sur le graphique des courbes ; rend son infobulle."""
    canvas = vue.findChildren(MplCanvas)[1]
    ax = canvas.fig.axes[0]
    canvas.draw()
    x, y = ax.transData.transform((mois, kwh))
    canvas.callbacks.process(
        "motion_notify_event",
        MouseEvent("motion_notify_event", canvas, x, y))
    return canvas.toolTip()


@pytest.mark.parametrize("annee, autre", [(2024, 2025), (2025, 2024)])
def test_la_tuile_de_l_annee_choisie_ressort(vue, annee, autre):
    """Par son trait de couleur, et par ses mots : la couleur ne porte jamais
    seule le sens."""
    vue.populate(f"year-{annee}")
    choisie, voisine = _tuile(vue, annee), _tuile(vue, autre)
    assert choisie.property("variant") == "warm"
    assert "année choisie" in choisie.sub.text()
    assert voisine.property("variant") == "primary"
    assert "année choisie" not in voisine.sub.text()


def test_l_annee_partielle_choisie_garde_sa_mention(vue):
    vue.populate("year-2026")
    sous_titre = _tuile(vue, 2026).sub.text()
    assert "hors moyenne" in sous_titre and "année choisie" in sous_titre


def test_la_page_dit_quelle_annee_est_en_jaune(vue):
    vue.populate("year-2024")
    assert "En jaune : 2024, l'année choisie en haut de la page." in _textes(vue)


@pytest.mark.parametrize("periode", ["all", "oa-1", "month-2026-05"])
def test_la_page_suit_l_annee_que_montre_le_menu(vue, periode):
    """Capture de l'auteur du 01/11/2026 : l'appli s'ouvre sur toute la
    periode, le menu de Statistiques montrait 2026, mais la tuile 2026 n'etait
    pas signalee et la phrase parlait de « l'année la plus récente »."""
    vue.populate(periode)
    assert "En jaune : 2026, l'année choisie en haut de la page." in _textes(vue)
    tuile = _tuile(vue, 2026)
    assert tuile.property("variant") == "warm"
    assert "année choisie" in tuile.sub.text()


def test_le_5_janvier_la_page_suit_aussi_le_menu(qapp):
    """Le menu montre l'annee nouvelle, encore sans mois complet : la phrase
    le dit, et le jaune ne passe pas en douce a l'annee d'avant."""
    v = _vue("2025-01-01", "2026-01-05")
    v.populate("all")
    assert "2026 n'a pas encore de mois complet" in _textes(v)
    assert "En jaune" not in _textes(v)
    assert _tuile(v, 2026).property("variant") == "warm"
    detruire(v)


def test_la_page_dit_ce_que_compte_la_moyenne(vue):
    vue.populate("year-2024")
    assert ("Moyenne et zone grise : les autres années, mois complets "
            "seulement.") in _textes(vue)


def test_avec_une_seule_annee_pas_de_phrase_sur_la_moyenne(qapp):
    v = _vue("2025-01-01", "2025-12-31")
    v.populate("year-2025")
    assert "Moyenne et zone grise" not in _textes(v)
    assert "En jaune : 2025" in _textes(v)
    detruire(v)


def test_le_survol_donne_les_chiffres_de_la_zone_grise(vue):
    """Mai sans 2024 : 2023 (310 kWh), 2025 (930), 2026 (465)."""
    vue.populate("year-2024")
    texte = _survoler(vue, 5, 500)
    assert texte == ("Mai, autres années : plus basse 310\xa0kWh — "
                     "moyenne 568\xa0kWh — plus haute 930\xa0kWh")


def test_le_survol_suit_le_mois_le_plus_proche(vue):
    vue.populate("year-2024")
    assert _survoler(vue, 2.2, 300).startswith("Février, autres années")


def test_hors_du_graphique_l_infobulle_disparait(vue):
    vue.populate("year-2024")
    _survoler(vue, 5, 500)
    canvas = vue.findChildren(MplCanvas)[1]
    canvas.callbacks.process(
        "motion_notify_event",
        MouseEvent("motion_notify_event", canvas, 0, 0))
    assert canvas.toolTip() == ""


def test_un_mois_d_une_seule_autre_annee_donne_son_chiffre(qapp):
    """Plus basse et plus haute seraient le meme nombre."""
    v = _vue("2025-01-01", "2026-09-29")
    v.populate("year-2026")
    assert _survoler(v, 5, 500) == "Mai, autre année : 930\xa0kWh"
    detruire(v)
