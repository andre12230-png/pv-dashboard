"""Premier lancement : chaque page vide dit quoi faire (audit du 04/10/2026).

Seul le tableau de bord guidait le nouvel utilisateur ; ailleurs on lisait
« Aucune donnée. », « Aucun relevé sur cette période. », et la page du
fournisseur parlait de « passage en heures pleines / creuses ».
"""
from __future__ import annotations

import pytest
import yaml

pytest.importorskip("PySide6")

from conftest import detruire  # noqa: E402
from PySide6.QtCore import QCoreApplication, QEvent, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

import app_desktop  # noqa: E402
import data_loaders as dl  # noqa: E402


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
        ";".join(dl.RELEVES_HEADER) + "\n", encoding="utf-8")
    data = app_desktop.build_dataset(app_desktop.load_config())
    prefs = QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)
    w = app_desktop.MainWindow(data, prefs)
    yield w
    detruire(w)


@pytest.mark.parametrize("cle", ["transactions", "categories", "accounts",
                                 "stats", "comparaison", "octopus_edf"])
def test_chaque_page_vide_renvoie_a_la_saisie(win, cle):
    win._switch_view(cle)
    win._appliquer_periode("all")
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    textes = " ".join(lbl.text() for lbl in win.views[cle].findChildren(QLabel))
    assert "Saisie quotidienne" in textes, textes
    assert "passage en heures" not in textes


@pytest.mark.parametrize("cle", ["transactions", "categories", "accounts",
                                 "stats", "comparaison", "octopus_edf", "oa"])
def test_le_message_ne_s_affiche_qu_une_fois(win, cle):
    win._switch_view(cle)
    win._appliquer_periode("all")
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    textes = [lbl.text() for lbl in win.views[cle].findChildren(QLabel)]
    assert sum("Aucun relevé pour l'instant" in t for t in textes) <= 1


# --- Periode vide, alors que des releves existent (audit du 08/10/2026) -----
# « Aucune donnée. » ne disait ni pourquoi ni quoi faire.

@pytest.mark.parametrize("message", [
    "Aucune donnée.", "Aucune donnée disponible.",
    "Aucune donnée sur cette période.", "Aucun relevé sur cette période."])
def test_periode_vide_dit_de_changer_de_periode(qapp, message):
    import pandas as pd

    from gui_theme import LIGHT
    from views._base import CONSEIL_PERIODE, BaseView

    vue = BaseView.__new__(BaseView)
    vue.theme = LIGHT
    vue.data = type("D", (), {"df": pd.DataFrame(
        {"production_kwh": [1.0]}, index=[pd.Timestamp("2025-06-01")])})()
    carte = vue._empty_card(message)
    texte = " ".join(e.text() for e in carte.findChildren(QLabel))
    assert texte.startswith("Aucun relevé sur cette période.")
    assert CONSEIL_PERIODE in texte and "Toute la période" in texte


def test_un_message_precis_reste_tel_quel(qapp):
    import pandas as pd

    from gui_theme import LIGHT
    from views._base import BaseView

    vue = BaseView.__new__(BaseView)
    vue.theme = LIGHT
    vue.data = type("D", (), {"df": pd.DataFrame(
        {"production_kwh": [1.0]}, index=[pd.Timestamp("2025-06-01")])})()
    carte = vue._empty_card("Aucune grille de TVA déclarée.")
    texte = " ".join(e.text() for e in carte.findChildren(QLabel))
    assert texte == "Aucune grille de TVA déclarée."


def test_pas_de_conseil_de_periode_sur_une_page_qui_l_ignore(qapp):
    import pandas as pd

    from gui_theme import LIGHT
    from views.oa import OAView

    vue = OAView.__new__(OAView)
    vue.theme = LIGHT
    vue.data = type("D", (), {"df": pd.DataFrame(
        {"production_kwh": [1.0]}, index=[pd.Timestamp("2025-06-01")])})()
    carte = vue._empty_card("Aucune donnée.")
    texte = " ".join(e.text() for e in carte.findChildren(QLabel))
    assert "flèches" not in texte
