"""Alerte au demarrage sur les recalages de config-local.yaml.

Analyse critique du 16-10-2026 : un fichier modifie a la main avec deux
periodes qui se chevauchent etait lu sans un mot, et les jours communs etaient
recales deux fois. Seule la fenetre « Mes réglages » refusait de l'enregistrer.
Valeurs inventees.

    py -m pytest tests/test_alerte_recalages.py
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox, QWidget  # noqa: E402

import app_desktop  # noqa: E402
import reglages as rg  # noqa: E402

SAINES = [
    {"debut": "2025-01-01", "fin": "2025-06-30", "total_kwh": 1000},
    {"debut": "2025-07-01", "fin": "2025-12-31", "total_kwh": 1000},
]
CHEVAUCHANTES = [
    {"debut": "2025-01-01", "fin": "2025-06-30", "total_kwh": 1000},
    {"debut": "2025-06-01", "fin": "2025-12-31", "total_kwh": 1000},
]


def _cfg(periodes: list) -> dict:
    return {"sources": {"injection_facturee": periodes}}


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


class FenetreFactice(QWidget):
    """Ce que l'alerte demande a la fenetre principale."""

    def __init__(self, cfg: dict):
        super().__init__()
        self.data = SimpleNamespace(cfg=cfg)
        self.reglages_ouverts = 0

    def _ouvrir_reglages(self) -> None:
        self.reglages_ouverts += 1


@pytest.fixture
def boites(monkeypatch):
    """Remplace l'attente d'un clic : `boites.bouton` est le bouton choisi,
    `boites.vues` les boites montrees."""
    etat = SimpleNamespace(bouton="Plus tard", vues=[])

    def exec_(boite):
        etat.vues.append(boite)
        return 0

    def clique(boite):
        return next(b for b in boite.buttons() if b.text() == etat.bouton)

    monkeypatch.setattr(QMessageBox, "exec", exec_)
    monkeypatch.setattr(QMessageBox, "clickedButton", clique)
    return etat


def test_des_recalages_sains_ne_disent_rien():
    assert rg.defaut_des_recalages(_cfg(SAINES)) == ""
    assert rg.defaut_des_recalages({}) == ""


def test_un_chevauchement_est_nomme_avec_ses_dates():
    defaut = rg.defaut_des_recalages(_cfg(CHEVAUCHANTES))
    assert "chevauchent" in defaut
    assert "01/06/2025" in defaut and "30/06/2025" in defaut


def test_des_dates_a_l_envers_sont_signalees():
    defaut = rg.defaut_des_recalages(_cfg([
        {"debut": "2025-12-31", "fin": "2025-01-01", "total_kwh": 1000}]))
    assert "date de fin" in defaut


def test_une_periode_illisible_ne_fait_pas_planter_le_demarrage():
    defaut = rg.defaut_des_recalages(_cfg([
        {"debut": "pas une date", "fin": "2025-01-01", "total_kwh": 1000}]))
    assert "illisible" in defaut


def test_rien_a_signaler_aucune_boite(qapp, boites):
    fenetre = FenetreFactice(_cfg(SAINES))
    app_desktop.annoncer_recalages_a_verifier(fenetre)
    assert not boites.vues


def test_la_boite_dit_le_defaut_et_ce_qu_il_change(qapp, boites):
    fenetre = FenetreFactice(_cfg(CHEVAUCHANTES))
    app_desktop.annoncer_recalages_a_verifier(fenetre)
    boite = boites.vues[0]
    assert boite.windowTitle() == "Recalages à vérifier"
    assert boite.icon() == QMessageBox.Warning
    assert "chevauchent" in boite.text()
    assert "peuvent être faux" in boite.text()
    assert fenetre.reglages_ouverts == 0          # « Plus tard »


def test_corriger_ouvre_mes_reglages(qapp, boites):
    boites.bouton = "Corriger mes réglages"
    fenetre = FenetreFactice(_cfg(CHEVAUCHANTES))
    app_desktop.annoncer_recalages_a_verifier(fenetre)
    assert fenetre.reglages_ouverts == 1


def test_le_demarrage_appelle_l_alerte():
    """Apres win.show() : la boite a la fenetre pour parent."""
    source = Path(app_desktop.__file__).with_name("run.py").read_text(encoding="utf-8")
    assert (source.index("win.show()")
            < source.index("app_desktop.annoncer_recalages_a_verifier(win)")
            < source.index("app.exec()"))


# -----------------------------------------------------------------------------
# Audit du 04-11-2026, D1 et D8 : recalages suspendus par le calcul
# -----------------------------------------------------------------------------

SUSPENDU = ("Consommation recalée sur facture du 01/01/2025 au 10/01/2025 : "
            "8 jours n'ont pas de relevé, du 01/01/2025 au 08/01/2025. "
            "Ce recalage est suspendu jusqu'à leur import.")


def test_un_recalage_suspendu_est_annonce(qapp, boites):
    fenetre = FenetreFactice(_cfg(SAINES))
    fenetre.data.recalages_suspendus = [SUSPENDU]
    app_desktop.annoncer_recalages_a_verifier(fenetre)
    texte = boites.vues[0].text()
    assert "01/01/2025 au 08/01/2025" in texte
    assert "gardent les valeurs des relevés" in texte


def test_au_plus_cinq_recalages_suspendus_detailles(qapp, boites):
    fenetre = FenetreFactice(_cfg(SAINES))
    fenetre.data.recalages_suspendus = [SUSPENDU] * 7
    app_desktop.annoncer_recalages_a_verifier(fenetre)
    texte = boites.vues[0].text()
    assert texte.count("• Consommation") == 5
    assert "et 2 autres" in texte


def test_la_preparation_des_donnees_transmet_les_suspensions(tmp_path):
    # Bout a bout : une facture qui commence avant le premier releve
    # arrive jusqu'a AppData sans fausser les jours presents.
    import pandas as pd

    import calculations as calc
    idx = pd.DatetimeIndex(["2025-01-09", "2025-01-10"])
    df = pd.DataFrame({"soutirage_kwh": [10.0, 10.0],
                       "autoconsommation_kwh": [0.0, 0.0]}, index=idx)
    df["consommation_kwh"] = df["soutirage_kwh"]
    alertes: list = []
    calc.recale_sur_facture(df, [{"debut": "2025-01-01", "fin": "2025-01-10",
                                  "total_kwh": 100.0}], alertes)
    assert alertes == [SUSPENDU]
