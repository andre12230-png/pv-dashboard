"""Le premier lancement d'un nouvel utilisateur, rejoue de bout en bout.

Dossier de donnees vide, config.yaml modele, aucun releve : chaque ecran doit
s'ouvrir. Le smoke test tourne sur les vraies donnees de l'auteur et ne voit
donc jamais cet etat-la : le 14/09/2026, la carte « Pour commencer » du
tableau de bord y plantait sans qu'aucun test ne le remarque.
"""
from __future__ import annotations

import shutil

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

import app_desktop  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def fenetre_neuve(qapp, tmp_path, monkeypatch):
    """La fenetre telle que la voit un nouvel utilisateur."""
    shutil.copy(app_desktop.CONFIG_PATH, tmp_path / "config.yaml")
    monkeypatch.setattr(app_desktop, "BASE_DIR", tmp_path)
    monkeypatch.setattr(app_desktop, "CONFIG_PATH", tmp_path / "config.yaml")
    monkeypatch.setattr(app_desktop, "CONFIG_LOCAL_PATH",
                        tmp_path / "config-local.yaml")
    cfg = app_desktop.normaliser_config(
        app_desktop._lire_yaml(tmp_path / "config.yaml"))
    data = app_desktop.build_dataset(cfg)
    assert data.df.empty
    prefs = QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)
    win = app_desktop.MainWindow(data, prefs)
    yield win
    win.close()


def test_chaque_ecran_s_ouvre_sans_releve(fenetre_neuve):
    for key, _, _, _ in app_desktop.NAV_ITEMS:
        fenetre_neuve._switch_view(key)


def test_le_tableau_de_bord_dit_quoi_faire(fenetre_neuve):
    fenetre_neuve._switch_view("dashboard")
    textes = " ".join(lbl.text() for lbl in
                      fenetre_neuve.views["dashboard"].findChildren(QLabel))
    assert "Pour commencer" in textes
    assert "Importer" in textes


def test_le_tableau_de_bord_ouvre_mes_reglages(fenetre_neuve):
    from PySide6.QtWidgets import QPushButton
    fenetre_neuve._switch_view("dashboard")
    boutons = [b.text() for b in
               fenetre_neuve.views["dashboard"].findChildren(QPushButton)]
    assert "Remplir mes réglages" in boutons


def test_les_parametres_ouvrent_mes_reglages(fenetre_neuve):
    from PySide6.QtWidgets import QPushButton
    fenetre_neuve._switch_view("settings")
    boutons = [b.text() for b in
               fenetre_neuve.views["settings"].findChildren(QPushButton)]
    assert "Modifier mes réglages" in boutons


def test_mes_reglages_de_bout_en_bout(fenetre_neuve, tmp_path):
    """Enregistrer ses reglages ecrit config.yaml, et la fenetre rechargee
    les montre aussitot : plus besoin de relancer l'application."""
    import reglages

    valeurs = {**reglages.lire_reglages(fenetre_neuve.data.cfg),
               "puissance_kwc": 4.5, "nom": "Engie"}
    fenetre_neuve._enregistrer_reglages(valeurs)
    assert list((tmp_path / "backups").glob("config_avant-reglages_*.yaml"))

    fenetre_neuve._recharger_fenetre()
    suivante = fenetre_neuve._fenetre_suivante
    assert suivante.data.puissance_kwc == 4.5
    # Le libelle suit l'emoji du bouton, comme dans Pecule.
    assert suivante.nav_buttons["octopus_edf"].text().endswith("Engie vs EDF")
    assert "4,5 kWc" in suivante.findChild(QLabel, "BrandSub").text()
    suivante.close()


def test_le_titre_du_menu_ne_porte_plus_la_puissance(fenetre_neuve):
    """« Photovoltaique 4,5 kWc » depassait la largeur du menu : la
    puissance est passee sur la ligne du dessous."""
    marque = fenetre_neuve.findChild(QLabel, "Brand")
    assert marque.text() == "Photovoltaïque"
    sous_titre = fenetre_neuve.findChild(QLabel, "BrandSub")
    assert "kWc" in sous_titre.text()
