"""Le premier lancement d'un nouvel utilisateur, rejoue de bout en bout.

Dossier de donnees vide, config.yaml modele, aucun releve : chaque ecran doit
s'ouvrir. Le smoke test tourne sur les vraies donnees de l'auteur et ne voit
donc jamais cet etat-la : le 14/09/2026, la carte « Pour commencer » du
tableau de bord y plantait sans qu'aucun test ne le remarque.
"""
from __future__ import annotations

import re
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
    # « ou » et non « vs » (anglicisme, relecture du 29/09/2026)
    assert suivante.nav_buttons["octopus_edf"].text().endswith("Engie ou EDF")
    assert "4,5 kWc" in suivante.findChild(QLabel, "BrandSub").text()
    suivante.close()


def test_le_titre_du_menu_ne_porte_plus_la_puissance(fenetre_neuve):
    """« Photovoltaique 4,5 kWc » depassait la largeur du menu : la
    puissance est passee sur la ligne du dessous."""
    marque = fenetre_neuve.findChild(QLabel, "Brand")
    assert marque.text() == "Photovoltaïque"
    sous_titre = fenetre_neuve.findChild(QLabel, "BrandSub")
    assert "kWc" in sous_titre.text()


# -----------------------------------------------------------------------------
# Lot « autres utilisateurs » (26/09/2026) : production seule
# -----------------------------------------------------------------------------

def test_production_seule_le_tableau_de_bord_dit_ce_qui_manque(
        qapp, tmp_path, monkeypatch):
    # Qui n'a que sa production (onduleur, pas encore de compte Enedis)
    # retombait sur « Pour commencer », comme si rien n'avait ete importe.
    import data_loaders as dl
    shutil.copy(app_desktop.CONFIG_PATH, tmp_path / "config.yaml")
    monkeypatch.setattr(app_desktop, "BASE_DIR", tmp_path)
    monkeypatch.setattr(app_desktop, "CONFIG_PATH", tmp_path / "config.yaml")
    monkeypatch.setattr(app_desktop, "CONFIG_LOCAL_PATH",
                        tmp_path / "config-local.yaml")
    entete = ";".join(dl.RELEVES_HEADER)
    vides = ";" * (len(dl.RELEVES_HEADER) - 2)
    (tmp_path / "Releves-pv.csv").write_text(
        entete + "\n"
        + f"01/05/2026;20{vides}\n02/05/2026;18{vides}\n", encoding="utf-8")
    cfg = app_desktop.normaliser_config(
        app_desktop._lire_yaml(tmp_path / "config.yaml"))
    data = app_desktop.build_dataset(cfg)
    assert data.df.empty and len(data.jours_en_attente) == 2
    prefs = QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)
    win = app_desktop.MainWindow(data, prefs)
    try:
        win._switch_view("dashboard")
        textes = " ".join(lbl.text() for lbl in
                          win.views["dashboard"].findChildren(QLabel))
        assert "2 journées de production" in textes
        assert "Enedis" in textes
    finally:
        win.close()


def test_sans_ancien_tarif_les_journees_anciennes_ont_un_prix(
        qapp, tmp_path, monkeypatch):
    # Le modele livre ne declare aucun tarif a prix unique (bleu_base) : la
    # notice dit qu'on ne l'a alors jamais eu. Pourtant, les journees d'avant
    # la date de bascule du modele (2024) etaient comptees a 0 EUR, sans un
    # mot -- qui importait ses 36 mois Enedis avait des bilans faux.
    import data_loaders as dl
    shutil.copy(app_desktop.CONFIG_PATH, tmp_path / "config.yaml")
    monkeypatch.setattr(app_desktop, "BASE_DIR", tmp_path)
    monkeypatch.setattr(app_desktop, "CONFIG_PATH", tmp_path / "config.yaml")
    monkeypatch.setattr(app_desktop, "CONFIG_LOCAL_PATH",
                        tmp_path / "config-local.yaml")
    (tmp_path / "Releves-pv.csv").write_text(
        ";".join(dl.RELEVES_HEADER) + "\n"
        "01/06/2023;20;12;5;;\n02/06/2023;18;10;6;;\n", encoding="utf-8")
    cfg = app_desktop.normaliser_config(
        app_desktop._lire_yaml(tmp_path / "config.yaml"))
    data = app_desktop.build_dataset(cfg)
    jour = data.df.loc["2023-06-01"]
    assert jour["cout_reseau_eur"] > 0
    assert jour["economie_eur"] > 0


def test_sans_ancien_tarif_le_glossaire_n_en_invente_pas(fenetre_neuve):
    # Le glossaire disait a chacun « prix unique jusqu'au 31/12/2023 », date
    # du modele, meme sans aucun tarif a prix unique declare.
    fenetre_neuve._switch_view("aide")
    textes = " ".join(lbl.text() for lbl in
                      fenetre_neuve.views["aide"].findChildren(QLabel))
    assert "vos achats jusqu'au" not in textes
    assert "Vous n'en avez déclaré aucun" in textes


def test_sans_vehicule_la_notice_n_en_parle_pas(fenetre_neuve):
    # Lot « autres utilisateurs » (26/09/2026) : la rubrique « La part de la
    # voiture » et l'appli Recharges VE etaient presentees a tout le monde.
    fenetre_neuve._switch_view("aide")
    textes = " ".join(lbl.text() for lbl in
                      fenetre_neuve.views["aide"].findChildren(QLabel))
    assert "La part de la voiture" not in textes
    assert "Recharges VE" not in textes
    assert "changement d'opérateur" not in textes


def test_avec_vehicule_la_rubrique_voiture_reste(qapp):
    from types import SimpleNamespace

    import pandas as pd

    from views.aide import AideView
    vue = SimpleNamespace(data=SimpleNamespace(
        cfg={}, df=pd.DataFrame(columns=["recharge_ve_kwh"]),
        start_oa="2024-01-01", dossier_donnees="", puissance_kwc=6.0,
        date_mise_en_service="2024-01-01",
        fournisseur=("F", "Offre F"), fournisseur_reference=("EDF", "Tarif Bleu"),
        libelle_comparaison="F ou EDF"))
    vue.data.cfg = {"installation": {"cout_total_eur": 1000.0}}
    champs = AideView._champs_installation(vue)
    assert "La part de la voiture" in champs["rubrique_voiture"]
    assert "Recharges VE" in champs["source_vehicule"]


def test_plus_de_vs_dans_l_appli(fenetre_neuve):
    """Relecture du 29/09/2026 : « vs » est un anglicisme. Ni le menu, ni
    les titres de page, ni les textes des pages ne l'emploient."""
    boutons = [b.text() for b in fenetre_neuve.nav_buttons.values()]
    assert fenetre_neuve.nav_buttons["comparaison"].text().endswith(
        "Comparer à l'an passé")
    # Le mot seul, en minuscules comme en capitales (« VS EDF BASE »).
    vs = re.compile(r"\bvs\b", re.IGNORECASE)
    trouves = [t for t in boutons if vs.search(t)]
    for cle in fenetre_neuve.views:
        fenetre_neuve._switch_view(cle)
        trouves += [f"{cle} : {lbl.text()[:80]}"
                    for lbl in fenetre_neuve.findChildren(QLabel)
                    if vs.search(lbl.text())]
    assert not trouves, trouves
