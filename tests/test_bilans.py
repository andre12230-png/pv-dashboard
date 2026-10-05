"""Deux bilans nommes, les memes mots partout (choix de l'auteur, 05/10/2026).

- « Bilan électricité » = vente + economies − achat au reseau : Tableau de
  bord, Repartition, Comparer, Releves ET Annees OA (la prime y reste dans
  sa colonne). Sur une meme annee de contrat, la page Annees OA ajoutait la
  prime et s'ecartait du Tableau de bord.
- « Bilan de l'installation » = vente + economies + primes − cout : la
  Synthese seule.
- « Vente » et « Achat au réseau » au lieu de Recettes, Revenus vente OA,
  Facture reseau, Depenses reseau.
- Un bilan s'ecrit en vert s'il est positif, en rouge s'il est negatif.

Donnees inventees : modele livre (3 kWc, surplus a 0,10 EUR/kWh, contrat
depuis le 01/01/2024), 20 kWh produits, 12 injectes, 5 achetes par jour.

    py -m pytest tests/test_bilans.py
"""
from __future__ import annotations

import pandas as pd
import pytest
import yaml

pytest.importorskip("PySide6")

from conftest import detruire  # noqa: E402
from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QTableWidget  # noqa: E402

import app_desktop  # noqa: E402
import data_loaders as dl  # noqa: E402

JOURS = pd.date_range("2024-01-01", "2025-01-10", freq="D")
JOURNEES = "".join(f"{j:%d/%m/%Y};20;12;5;2;3\n" for j in JOURS)

# Ce que plus aucune page ne doit ecrire.
ANCIENS_NOMS = ("Bilan net", "Recettes", "Facture réseau", "FACTURE RÉSEAU",
                "Dépenses réseau", "Revenus vente", "BILAN NET")


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def win(qapp, tmp_path, monkeypatch):
    cfg = yaml.safe_load(app_desktop.CONFIG_PATH.read_text(encoding="utf-8"))
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
    w._appliquer_periode("all")
    yield w
    detruire(w)


def _labels(win, cle: str) -> list[QLabel]:
    win._switch_view(cle)
    return win.views[cle].findChildren(QLabel)


def _textes(win, cle: str) -> str:
    return " | ".join(lbl.text() for lbl in _labels(win, cle))


def _textes_tableaux(win, cle: str) -> str:
    morceaux = []
    for table in win.views[cle].findChildren(QTableWidget):
        for c in range(table.columnCount()):
            entete = table.horizontalHeaderItem(c)
            if entete is not None:
                morceaux.append(entete.text())
    return " | ".join(morceaux)


def test_annees_oa_et_tableau_de_bord_ont_le_meme_bilan(win):
    """Annee OA #1 : la prime est versee, mais elle reste dans sa colonne."""
    df = win.data.df
    attendu = df[df["annee_oa"] == 1]["bilan_jour_eur"].sum()
    win._switch_view("oa")
    table = win.views["oa"].findChildren(QTableWidget)[-1]
    entetes = [table.horizontalHeaderItem(c).text()
               for c in range(table.columnCount())]
    col = next(i for i, e in enumerate(entetes) if e.startswith("Bilan"))
    ligne = next(r for r in range(table.rowCount())
                 if table.item(r, 0).text().endswith("1"))
    lu = float(table.item(ligne, col).text().replace(",", ".")
               .replace(" ", "").replace(" ", ""))
    assert lu == pytest.approx(attendu, abs=0.01)


@pytest.mark.parametrize("cle", ["dashboard", "categories", "accounts",
                                 "oa", "comparaison", "transactions"])
def test_plus_aucun_ancien_nom(win, cle):
    textes = _textes(win, cle) + " | " + _textes_tableaux(win, cle)
    trouves = [n for n in ANCIENS_NOMS if n in textes]
    assert not trouves, trouves


def test_les_deux_bilans_sont_nommes(win):
    assert "BILAN ÉLECTRICITÉ" in _textes(win, "dashboard")
    synthese = _textes(win, "accounts")
    assert "BILAN DE L'INSTALLATION" in synthese
    assert "ACHAT AU RÉSEAU" in synthese
    assert "BILAN ÉLECTRICITÉ" in _textes(win, "categories")


def test_le_bilan_du_tableau_de_bord_suit_son_signe(win):
    """Il etait ecrit en noir ; vert ou rouge selon le signe, comme ailleurs."""
    labels = _labels(win, "dashboard")
    titre = next(lbl for lbl in labels if "BILAN ÉLECTRICITÉ" in lbl.text())
    valeur = titre.parent().findChild(QLabel, "KpiValue")
    from gui_theme import LIGHT
    negatif = win.data.df["bilan_jour_eur"].sum() < 0
    attendu = LIGHT["debit" if negatif else "credit"].lower()
    assert attendu in valeur.styleSheet().lower()


def test_l_annee_oa_en_cours_est_signalee(win):
    """Audit du 04/10/2026 : l'annee OA en cours (ici 10 jours) avait
    l'allure d'une mauvaise annee. Son nom le dit, ses barres sont
    hachurees."""
    from gui_widgets import MplCanvas
    win._switch_view("oa")
    vue = win.views["oa"]
    ax = vue.findChildren(MplCanvas)[0].fig.axes[0]
    noms = [t.get_text() for t in ax.get_xticklabels()]
    assert noms[-1].startswith("OA #2") and "en cours" in noms[-1]
    assert "en cours" not in noms[0]
    hachures = [bool(p.get_hatch()) for p in ax.patches]
    assert hachures[:2] == [False, True]          # production #1, #2
    table = vue.findChildren(QTableWidget)[-1]
    assert "en cours" in table.item(0, 1).text()  # #2, la plus recente en haut


def test_une_annee_oa_commencee_en_route_est_partielle(win):
    """Releves commences apres le debut du contrat : l'annee #1 est
    partielle, et le dit."""
    from gui_widgets import MplCanvas
    df = win.data.df
    win.data.df = df[df.index >= "2024-04-26"]
    win._switch_view("oa")
    win.views["oa"].refresh("all")
    ax = win.views["oa"].findChildren(MplCanvas)[-1].fig.axes[0]
    noms = [t.get_text() for t in ax.get_xticklabels()]
    assert noms[0] == "OA #1 (partielle)"
