"""Rappel de sauvegarde externe (28/09/2026), commun aux trois applications.

La date de la derniere sauvegarde externe reussie est retenue dans les
preferences (cle « sauvegarde/derniere ») ; le tableau de bord rappelle
doucement de recommencer au-dela de 30 jours. Sans sauvegarde jamais faite,
on compte depuis la premiere utilisation (cle de avis.py). Le texte vient de
sauvegarde_externe.rappel_sauvegarde_externe.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

import app_desktop  # noqa: E402
import avis  # noqa: E402
from gui_theme import LIGHT  # noqa: E402
from views.dashboard import DashboardView  # noqa: E402


@pytest.fixture
def prefs(tmp_path):
    return QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)


def _il_y_a(jours: int) -> str:
    return (date.today() - timedelta(days=jours)).isoformat()


def test_rappel_d_apres_les_preferences(prefs):
    fenetre = SimpleNamespace(
        settings=prefs,
        CLE_DERNIERE_SAUVEGARDE=app_desktop.MainWindow.CLE_DERNIERE_SAUVEGARDE)
    rappel = app_desktop.MainWindow._rappel_sauvegarde
    assert rappel(fenetre) is None                 # rien ne permet de compter
    prefs.setValue(avis.CLE_PREMIERE_UTILISATION, _il_y_a(45))
    assert "jamais" in rappel(fenetre)
    prefs.setValue(app_desktop.MainWindow.CLE_DERNIERE_SAUVEGARDE, _il_y_a(3))
    assert rappel(fenetre) is None
    prefs.setValue(app_desktop.MainWindow.CLE_DERNIERE_SAUVEGARDE, _il_y_a(40))
    assert "depuis 40 jours" in rappel(fenetre)


def test_le_bouton_retient_la_date(prefs, monkeypatch, tmp_path):
    monkeypatch.setattr(app_desktop.QFileDialog, "getExistingDirectory",
                        lambda *a: str(tmp_path))
    monkeypatch.setattr(app_desktop.sauvegarde_externe, "sauvegarder",
                        lambda *a, **k: (Path(tmp_path) / "copie", ["a.csv"]))
    monkeypatch.setattr(app_desktop.QMessageBox, "information",
                        lambda *a: None)
    fenetre = SimpleNamespace(
        settings=prefs, data=SimpleNamespace(releves_path=tmp_path / "a.csv"),
        CLE_DESTINATION_SAUVEGARDE=app_desktop.MainWindow
        .CLE_DESTINATION_SAUVEGARDE,
        CLE_DERNIERE_SAUVEGARDE=app_desktop.MainWindow.CLE_DERNIERE_SAUVEGARDE)
    app_desktop.MainWindow._sauvegarder_externe(fenetre)
    assert prefs.value(app_desktop.MainWindow.CLE_DERNIERE_SAUVEGARDE) == \
        date.today().isoformat()


def test_le_bandeau_du_tableau_de_bord():
    QApplication.instance() or QApplication([])
    vue = SimpleNamespace(theme=LIGHT, rappel_sauvegarde=lambda: "À refaire.")
    bandeau = DashboardView._bandeau_sauvegarde(vue)
    assert isinstance(bandeau, QLabel) and "À refaire." in bandeau.text()
    assert DashboardView._bandeau_sauvegarde(
        SimpleNamespace(theme=LIGHT, rappel_sauvegarde=lambda: None)) is None
    assert DashboardView._bandeau_sauvegarde(
        SimpleNamespace(theme=LIGHT, rappel_sauvegarde=None)) is None


def test_les_bandeaux_du_tableau_de_bord_ont_des_coins_de_4_px():
    """Charte (07/10/2026) : un bandeau a des coins de 4 px, comme dans
    Pecule et Recharges VE ; ces deux-la etaient a 6 px."""
    import re
    QApplication.instance() or QApplication([])
    sauvegarde = DashboardView._bandeau_sauvegarde(
        SimpleNamespace(theme=LIGHT, rappel_sauvegarde=lambda: "À refaire."))
    fraicheur = DashboardView._bandeau_fraicheur(
        SimpleNamespace(theme=LIGHT, data=SimpleNamespace(dernieres_saisies={})))
    for bandeau in (sauvegarde, fraicheur):
        assert re.findall(r"border-radius:\s*(\d+)px",
                          bandeau.styleSheet()) == ["4"]
