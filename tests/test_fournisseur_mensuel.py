"""Graphique « Coût mensuel comparé » de la page fournisseur (29/09/2026).

Sur 33 mois dans un seul graphique, les trois montants de chaque mois se
chevauchaient et les mois etaient ecrits debout. L'auteur tient aux montants
au-dessus des barres : on leur donne de la place, un graphique par annee
civile, la plus recente en haut, les douze mois toujours la et la meme
echelle d'une annee a l'autre. Donnees inventees.

    py -m pytest tests/test_fournisseur_mensuel.py
"""
from __future__ import annotations

import pandas as pd
import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from gui_theme import LIGHT  # noqa: E402
from gui_widgets import MplCanvas  # noqa: E402

MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
        "juil.", "août", "sept.", "oct.", "nov.", "déc."]


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def _carte(debut: str, fin: str):
    from views.octopus_edf import OctopusEdfView
    jours = pd.date_range(debut, fin, freq="D")
    comp = pd.DataFrame({"cout_octopus_eur": 3.0, "cout_edf_hphc_eur": 2.9,
                         "cout_edf_base_eur": 3.1}, index=jours)
    vue = OctopusEdfView.__new__(OctopusEdfView)
    vue.theme = LIGHT
    return vue._chart_mensuel(comp, "Mon fournisseur", "EDF")


def _axes(carte):
    return [c.fig.axes[0] for c in carte.findChildren(MplCanvas)]


def test_un_graphique_par_annee_la_plus_recente_en_haut(qapp):
    axes = _axes(_carte("2024-06-15", "2026-09-28"))
    assert [ax.get_title(loc="left") for ax in axes] == ["2026", "2025", "2024"]


def test_les_douze_mois_a_plat(qapp):
    for ax in _axes(_carte("2024-06-15", "2026-09-28")):
        etiquettes = ax.get_xticklabels()
        assert [t.get_text() for t in etiquettes] == MOIS
        assert all(t.get_rotation() == 0 for t in etiquettes)


def test_chaque_barre_a_son_montant(qapp):
    """2026 : janvier a septembre ; 2024 : juin a decembre. Trois montants
    par mois present, pas un de plus ni de moins."""
    ax_2026, _ax_2025, ax_2024 = _axes(_carte("2024-06-15", "2026-09-28"))
    assert len([t for t in ax_2026.texts if t.get_text()]) == 3 * 9
    assert len([t for t in ax_2024.texts if t.get_text()]) == 3 * 7


def test_meme_echelle_et_une_seule_legende(qapp):
    axes = _axes(_carte("2024-06-15", "2026-09-28"))
    assert len({ax.get_ylim() for ax in axes}) == 1
    assert axes[0].get_legend() is not None
    assert all(ax.get_legend() is None for ax in axes[1:])


def test_les_mois_incomplets_sont_hachures(qapp):
    """Audit du 04/10/2026 : le premier et le dernier mois, incomplets,
    passaient pour des mois entiers. Ils restent la, hachures, et la carte
    le dit."""
    from PySide6.QtWidgets import QLabel
    carte = _carte("2025-03-20", "2025-06-10")
    ax = carte.findChildren(MplCanvas)[0].fig.axes[0]
    # Les barres arrivent par serie (mon offre, puis les deux autres), chacune
    # dans l'ordre des mois : mars, avril, mai, juin.
    hachures = [bool(p.get_hatch()) for p in ax.patches][:4]
    assert hachures == [True, False, False, True]
    textes = " ".join(lbl.text() for lbl in carte.findChildren(QLabel))
    assert "incomplets" in textes


def _hypotheses(comp, debut_grille="2026-01-01"):
    from PySide6.QtWidgets import QLabel

    from views.octopus_edf import OctopusEdfView
    vue = OctopusEdfView.__new__(OctopusEdfView)
    vue.theme = LIGHT
    ref = [{"debut": debut_grille, "fin": None, "abonnement": 20.0,
            "prix_base": 0.2, "prix_hp": 0.22, "prix_hc": 0.16}]
    carte = vue._carte_hypotheses(ref, "Mon offre", "EDF Tarif Bleu", comp)
    return " ".join(lbl.text() for lbl in carte.findChildren(QLabel))


def test_les_hypotheses_ne_disent_reels_que_s_ils_le_sont(qapp):
    """Audit du 04/10/2026 : « calculé sur vos relevés HP/HC réels » meme
    sans aucun detail HC / HP, et « grille en vigueur à chaque date » pour
    des releves anterieurs a la seule grille du modele."""
    jours = pd.date_range("2025-06-01", "2026-03-31", freq="D")
    sans_detail = pd.DataFrame({"soutirage_kwh": 10.0, "soutirage_hc_kwh": 0.0,
                                "soutirage_hp_kwh": 0.0}, index=jours)
    texte = _hypotheses(sans_detail)
    assert "relevés HP/HC réels" not in texte
    assert "estimée" in texte
    assert "Avant le 01/01/2026" in texte
    avec = sans_detail.assign(soutirage_hc_kwh=4.0, soutirage_hp_kwh=6.0)
    texte = _hypotheses(avec, debut_grille="2025-01-01")
    assert "relevés HP/HC réels" in texte
    assert "Avant le" not in texte
