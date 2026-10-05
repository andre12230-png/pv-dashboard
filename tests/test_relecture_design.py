"""Relecture de design de la 1.52.16 (05/10/2026), charte des applis.

Donnees inventees : modele livre (3 kWc, contrat depuis le 01/01/2024),
releves du 26/04/2024 au 30/06/2025 (annee OA #1 partielle), 20 kWh
produits, 12 injectes, 5 achetes par jour.

    py -m pytest tests/test_relecture_design.py
"""
from __future__ import annotations

import pandas as pd
import pytest
import yaml

pytest.importorskip("PySide6")

from conftest import detruire  # noqa: E402
from PySide6.QtCore import QCoreApplication, QEvent, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QTableWidget  # noqa: E402

import app_desktop  # noqa: E402
import data_loaders as dl  # noqa: E402
from gui_theme import LIGHT  # noqa: E402
from gui_widgets import KpiCard, MplCanvas  # noqa: E402

JOURS = pd.date_range("2024-04-26", "2025-06-30", freq="D")
JOURNEES = "".join(f"{j:%d/%m/%Y};20;12;5;2;3\n" for j in JOURS)
VERT, ROUGE = LIGHT["credit"].lower(), LIGHT["debit"].lower()


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def fenetre(qapp, tmp_path, monkeypatch):
    ouvertes = []

    def ouvrir(modif=lambda cfg: None):
        cfg = yaml.safe_load(app_desktop.CONFIG_PATH.read_text(encoding="utf-8"))
        modif(cfg)
        (tmp_path / "config.yaml").write_text(
            yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
        monkeypatch.setattr(app_desktop, "BASE_DIR", tmp_path)
        monkeypatch.setattr(app_desktop, "CONFIG_PATH", tmp_path / "config.yaml")
        monkeypatch.setattr(app_desktop, "CONFIG_LOCAL_PATH",
                            tmp_path / "config-local.yaml")
        (tmp_path / "Releves-pv.csv").write_text(
            ";".join(dl.RELEVES_HEADER) + "\n" + JOURNEES, encoding="utf-8")
        data = app_desktop.build_dataset(app_desktop.load_config())
        prefs = QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)
        w = app_desktop.MainWindow(data, prefs)
        ouvertes.append(w)
        return w

    yield ouvrir
    for w in ouvertes:
        detruire(w)
    from views._helpers import definir_acheteur
    definir_acheteur("EDF OA")


def _vue(win, cle, periode):
    win._switch_view(cle)
    win._appliquer_periode(periode)
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    return win.views[cle]


def _textes(vue) -> str:
    return " | ".join(lbl.text() for lbl in vue.findChildren(QLabel))


def test_la_legende_des_annees_oa_n_est_jamais_hachuree(fenetre):
    """🔴 La legende prenait l'allure des premieres barres, celles de
    l'annee #1 partielle : tout paraissait incomplet."""
    vue = _vue(fenetre(), "oa", "all")
    ax = vue.findChildren(MplCanvas)[0].fig.axes[0]
    assert ax.patches[0].get_hatch()                  # l'annee #1, hachuree
    for carre in ax.get_legend().get_patches():
        assert not carre.get_hatch()


def test_impact_et_variations_aux_couleurs_de_la_charte():
    """🟡 #137B57 et #B44A20 a cote du #18733A / #C0392B des bilans."""
    from gui_theme import COULEUR_DEFAVORABLE, COULEUR_FAVORABLE
    assert COULEUR_FAVORABLE.lower() == VERT
    assert COULEUR_DEFAVORABLE.lower() == ROUGE


def test_les_quatre_montants_du_tableau_de_bord_suivent_leur_signe(fenetre):
    """🟡 Seul le bilan etait colore ; dans la Synthese, tout l'est."""
    vue = _vue(fenetre(), "dashboard", "year-2024")
    couleurs = {}
    for carte in vue.findChildren(KpiCard):
        titre = carte.label.text()
        for nom in ("VENTE", "ÉCONOMIES", "ACHAT AU RÉSEAU", "BILAN"):
            if nom in titre:
                couleurs[nom] = carte.value.styleSheet().lower()
    assert VERT in couleurs["VENTE"] and VERT in couleurs["ÉCONOMIES"]
    assert ROUGE in couleurs["ACHAT AU RÉSEAU"]


def test_comparer_distingue_les_kwh_et_les_euros(fenetre):
    """🟡 « Achat au réseau » deux fois, en kWh et en €."""
    vue = _vue(fenetre(), "comparaison", "month-2024-12")
    vue.refresh("year-2025")
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    from views._helpers import METRIQUES
    libelles = [label for _c, label, *_ in METRIQUES]
    assert len(libelles) == len(set(libelles))
    assert "Achat au réseau (€)" in libelles


def test_la_page_fournisseur_part_du_premier_releve(fenetre):
    """🟡 « Depuis la mise en service du 01/01/2024 » pour des releves qui
    commencent le 26/04/2024."""
    textes = _textes(_vue(fenetre(), "octopus_edf", "all"))
    assert "Depuis la mise en service" not in textes
    assert "26/04/2024" in textes


def test_le_sous_titre_du_remboursement_reste_court(fenetre):
    """🟡 Une ligne de ~170 signes ; la charte en veut ~110 au plus."""
    vue = _vue(fenetre(), "dashboard", "all")
    textes = [lbl.text() for lbl in vue.findChildren(QLabel)]
    sous_titre = next(t for t in textes if t.startswith("Depuis le premier relevé"))
    assert len(sous_titre) <= 110
    assert any("avant n'est pas compté" in t for t in textes)


def test_sans_vente_le_bilan_ne_parle_pas_de_vente(fenetre):
    """🟡 « +225 € de vente et d'économies » chez qui ne vend pas."""
    win = fenetre(lambda cfg: cfg["oa"].update(type="aucune"))
    textes = _textes(_vue(win, "categories", "year-2024"))
    assert "de vente et d'économies" not in textes
    assert "d'économies" in textes


def test_les_petits_mots_alignes(fenetre):
    """🟢 « Durée contrat », « #3 » face a « Année n° 3 », « Ventes »
    au pluriel, signe « − » du badge face au « - » des montants, trait
    orange de la tuile de comparaison du bilan."""
    win = fenetre(lambda cfg: cfg["oa"].update(acheteur="Solaire Coop"))
    assert "Durée contrat" not in _textes(_vue(win, "settings", "all"))
    oa = _vue(win, "oa", "all")
    table = oa.findChildren(QTableWidget)[-1]
    assert table.item(0, 0).text().startswith("n° ")
    synthese = _textes(_vue(win, "accounts", "all"))
    assert "Ventes" not in synthese and "ventes +" not in synthese
    tableau = _textes(_vue(win, "dashboard", "month-2024-12"))
    assert "−" not in tableau.split("par rapport")[0][-8:]
    rep = _vue(win, "categories", "month-2025-05")
    bilan = next(c for c in rep.findChildren(KpiCard)
                 if "BILAN" in c.label.text() and c.minimumHeight() == 118)
    assert bilan.property("variant") in ("credit", "debit")
