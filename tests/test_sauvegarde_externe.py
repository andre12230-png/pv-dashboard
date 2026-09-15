"""Sauvegarde sur un support externe, et bouton « Mise à jour ».

Deux ajouts du 15/09/2026, pour qu'un utilisateur ne perde pas tout avec son
disque, et sache qu'une nouvelle version existe sans que l'application se
connecte a Internet.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

import sauvegarde_externe as se

QUAND = datetime(2026, 9, 15, 14, 30)


@pytest.fixture
def donnees(tmp_path):
    """Un dossier de donnees et une « cle USB », tous deux jetables."""
    dossier = tmp_path / "donnees"
    dossier.mkdir()
    (dossier / "config.yaml").write_text("a: 1\n", encoding="utf-8")
    (dossier / "releves.csv").write_text("Date;Prod\n2026-09-01;12,5\n",
                                         encoding="utf-8")
    cle = tmp_path / "cle"
    cle.mkdir()
    return dossier, cle


def _sauver(dossier, cle, fichiers=None):
    fichiers = fichiers or [dossier / "config.yaml", dossier / "releves.csv"]
    return se.sauvegarder(fichiers, cle, dossier, "Mon Appli", "1.0.0", QUAND)


def test_copie_dans_un_dossier_date(donnees):
    dossier, cle = donnees
    cible, copies = _sauver(dossier, cle)
    assert cible == cle / "Sauvegarde Mon Appli 2026-09-15 14h30"
    assert copies == ["config.yaml", "releves.csv"]
    for nom in copies:
        assert (cible / nom).read_bytes() == (dossier / nom).read_bytes()


def test_un_mode_d_emploi_accompagne_la_copie(donnees):
    dossier, cle = donnees
    cible, _ = _sauver(dossier, cle)
    texte = (cible / "LISEZMOI.txt").read_text(encoding="utf-8")
    assert "Mon Appli 1.0.0" in texte
    assert "releves.csv" in texte
    assert str(dossier) in texte


def test_deux_sauvegardes_dans_la_meme_minute(donnees):
    """La seconde ne doit jamais ecraser la premiere."""
    dossier, cle = donnees
    premiere, _ = _sauver(dossier, cle)
    seconde, _ = _sauver(dossier, cle)
    assert premiere != seconde
    assert seconde.name.endswith("(2)")


def test_un_fichier_absent_est_simplement_saute(donnees):
    """config-local.yaml n'existe pas chez tout le monde."""
    dossier, cle = donnees
    _, copies = _sauver(dossier, cle, [dossier / "config.yaml",
                                       dossier / "absent.yaml", None])
    assert copies == ["config.yaml"]


def test_rien_a_sauvegarder(donnees):
    dossier, cle = donnees
    with pytest.raises(se.SauvegardeImpossible, match="aucune donnée"):
        _sauver(dossier, cle, [dossier / "absent.yaml"])


def test_cle_retiree(donnees, tmp_path):
    dossier, _ = donnees
    with pytest.raises(se.SauvegardeImpossible, match="retirée"):
        _sauver(dossier, tmp_path / "cle-debranchee")


def test_refuse_le_dossier_des_donnees(donnees):
    """Une copie au meme endroit disparaitrait avec les originaux."""
    dossier, _ = donnees
    with pytest.raises(se.SauvegardeImpossible, match="clé USB"):
        _sauver(dossier, dossier)
    sous_dossier = dossier / "backups"
    sous_dossier.mkdir()
    with pytest.raises(se.SauvegardeImpossible):
        _sauver(dossier, sous_dossier)


def test_une_copie_differente_est_denoncee(donnees, monkeypatch):
    """Une cle defectueuse qui abime la copie ne doit pas passer pour une
    sauvegarde reussie."""
    dossier, cle = donnees

    def copie_abimee(source, dest):
        Path(dest).write_bytes(b"abime")
    monkeypatch.setattr(se.shutil, "copy2", copie_abimee)
    with pytest.raises(se.SauvegardeImpossible, match="ne correspond pas"):
        _sauver(dossier, cle)


def test_la_sauvegarde_ne_touche_pas_aux_originaux(donnees):
    dossier, cle = donnees
    avant = {p.name: p.read_bytes() for p in dossier.iterdir()}
    _sauver(dossier, cle)
    assert {p.name: p.read_bytes() for p in dossier.iterdir()} == avant


# -----------------------------------------------------------------------------
# « Mise à jour » : deux liens vers la derniere version, rien d'autre
# -----------------------------------------------------------------------------


def test_les_liens_de_mise_a_jour_visent_la_derniere_version():
    pytest.importorskip("PySide6")
    import mise_a_jour
    racine = "https://github.com/andre12230-png/pv-dashboard/releases/latest"
    assert mise_a_jour.PAGE_VERSIONS_URL == racine
    # Le nom fixe de l'installeur, celui que produit faire_installeur.py
    assert mise_a_jour.INSTALLEUR_URL == racine + "/download/pv-dashboard-Setup.exe"


@pytest.mark.parametrize("module", ["mise_a_jour.py", "sauvegarde_externe.py"])
def test_aucun_acces_reseau(module):
    """L'application ne se connecte jamais a Internet : ces deux modules
    confient une adresse au navigateur, ou copient des fichiers, sans plus."""
    source = (Path(__file__).resolve().parent.parent / module).read_text(
        encoding="utf-8")
    for interdit in ("import urllib", "import http", "import socket",
                     "import requests", "QtNetwork", "import ssl"):
        assert interdit not in source, f"{module} : {interdit}"
