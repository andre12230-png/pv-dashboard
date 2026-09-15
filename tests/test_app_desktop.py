"""Tests du demarrage de l'application.

Le verrou d'instance unique est ici et pas dans les tests de vue : il se
prend avant toute fenetre, au tout debut de main().
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

import app_desktop  # noqa: E402


def test_une_seule_instance_a_la_fois(tmp_path):
    # Deux fenetres ouvertes sur le meme CSV se relisent et se reecrivent
    # mutuellement : la derniere a enregistrer gagne, et les saisies de
    # l'autre disparaissent sans un mot.
    chemin = str(tmp_path / "pv-dashboard.lock")

    premier = app_desktop.prendre_le_verrou(chemin)
    assert premier is not None, "la premiere instance doit obtenir le verrou"

    second = app_desktop.prendre_le_verrou(chemin)
    assert second is None, "la seconde instance doit etre refusee"

    # Une fois la premiere fermee, une nouvelle instance redevient possible.
    premier.unlock()
    troisieme = app_desktop.prendre_le_verrou(chemin)
    assert troisieme is not None
    troisieme.unlock()


def test_le_lanceur_prend_aussi_le_verrou(tmp_path):
    """L'exe, Lancer.vbs et Lancer.bat demarrent par run.py : c'est la que le
    verrou doit etre pris. Jusqu'en 1.30.0 il ne l'etait que par
    app_desktop.main(), que personne n'utilise, et deux fenetres pouvaient
    s'ouvrir. Les deux fonctions partagent le meme fichier de verrou."""
    import run

    chemin = str(tmp_path / "pv-dashboard.lock")
    premier = run.prendre_le_verrou(chemin)
    assert premier is not None
    # Une fenetre ouverte par l'autre voie est refusee elle aussi.
    assert app_desktop.prendre_le_verrou(chemin) is None
    premier.unlock()


def test_le_lanceur_s_arrete_si_le_verrou_est_pris():
    """main() doit demander le verrou avant de construire la fenetre."""
    import inspect

    import run

    source = inspect.getsource(run.main)
    assert source.index("prendre_le_verrou()") < source.index("create_window()")


def test_resolve_base_dir_remonte_de_deux_dossiers_en_exe(tmp_path, monkeypatch):
    """En .exe construit dans le projet, les donnees sont deux crans au-dessus.

    PyInstaller pose l'executable dans dist/pv-dashboard/, un dossier qu'il
    efface et recree entierement a chaque construction. config.yaml,
    Releves-pv.csv et backups/ vivent donc a la racine du projet, et l'exe
    remonte les chercher. Si cette arborescence changeait sans que la regle
    suive, l'exe livre ne trouverait plus rien : ce test tombe avant.
    """
    projet = tmp_path / "mon-projet"
    exe = projet / "dist" / "pv-dashboard" / "pv-dashboard.exe"
    exe.parent.mkdir(parents=True)
    (projet / "config.yaml").write_text("installation: {}\n", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))

    assert app_desktop.resolve_base_dir() == projet


def test_resolve_base_dir_dossier_d_usage(tmp_path, monkeypatch):
    """Le dossier d'usage, separe du projet : les donnees, et dedans le
    programme, comme F:\\Gestion photovoltaique\\pv-dashboard\\.

    Meme disposition que Recharges VE : les donnees un cran au-dessus de
    l'exe. Elle passe AVANT la regle des deux crans, sinon un dossier d'usage
    range dans un dossier qui porterait lui aussi un config.yaml se
    tromperait de donnees.
    """
    usage = tmp_path / "Gestion photovoltaique"
    exe = usage / "pv-dashboard" / "pv-dashboard.exe"
    exe.parent.mkdir(parents=True)
    (usage / "config.yaml").write_text("installation: {}\n", encoding="utf-8")
    (tmp_path / "config.yaml").write_text("autre: 1\n", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))

    assert app_desktop.resolve_base_dir() == usage


def test_resolve_base_dir_installe_range_les_donnees_chez_l_utilisateur(
        tmp_path, monkeypatch):
    """Installe par le Setup, l'exe n'a pas de projet autour de lui.

    Remonter de deux crans depuis %LOCALAPPDATA%\\Programs\\pv-dashboard
    tombait sur %LOCALAPPDATA% lui-meme : config.yaml, le CSV et le journal
    s'y seraient ecrits en vrac. Une installation neuve range donc ses
    donnees dans un dossier personnel qui porte le nom de l'application.
    """
    exe = tmp_path / "Programs" / "pv-dashboard" / "pv-dashboard.exe"
    exe.parent.mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))

    assert app_desktop.resolve_base_dir() == tmp_path / "local" / "pv-dashboard"


def test_premier_lancement_pose_les_modeles_de_configuration(tmp_path):
    """Sans config.yaml, une installation neuve ne demarrerait pas : on pose
    le modele livre a cote du programme, avec celui de config-local."""
    programme = tmp_path / "programme"
    donnees = tmp_path / "donnees"
    programme.mkdir()
    donnees.mkdir()
    (programme / "config.yaml").write_text("modele: 1\n", encoding="utf-8")
    (programme / "config-local.exemple.yaml").write_text("x: 1\n", encoding="utf-8")

    poses = app_desktop.installer_modeles_config(donnees, programme)

    assert poses == ["config.yaml", "config-local.exemple.yaml"]
    assert (donnees / "config.yaml").read_text(encoding="utf-8") == "modele: 1\n"
    assert (donnees / "config-local.exemple.yaml").exists()


def test_premier_lancement_n_ecrase_jamais_la_configuration(tmp_path):
    """Une mise a jour relance le programme sur une config deja remplie :
    elle ne doit en aucun cas etre remplacee par le modele."""
    programme = tmp_path / "programme"
    donnees = tmp_path / "donnees"
    programme.mkdir()
    donnees.mkdir()
    (programme / "config.yaml").write_text("modele: 1\n", encoding="utf-8")
    (donnees / "config.yaml").write_text("la mienne: 9\n", encoding="utf-8")

    assert app_desktop.installer_modeles_config(donnees, programme) == []
    assert (donnees / "config.yaml").read_text(encoding="utf-8") == "la mienne: 9\n"


def test_resolve_base_dir_depuis_les_sources(monkeypatch):
    """Lance en .py, le dossier de base est celui du code : le meme jeu de
    donnees que l'exe, jamais une seconde copie qui divergerait."""
    monkeypatch.delattr(sys, "frozen", raising=False)

    assert app_desktop.resolve_base_dir() == Path(app_desktop.__file__).parent


def test_ouverture_toujours_sur_le_mois_en_cours(tmp_path):
    """L'appli s'ouvre sur le mois en cours, meme apres avoir consulte un
    autre mois lors de la derniere utilisation.

    Sinon on rouvre le tableau de bord sur des chiffres anciens sans s'en
    apercevoir, et on les prend pour ceux du mois courant.
    """
    import pandas as pd
    from PySide6.QtCore import QSettings

    mois_en_cours = pd.Timestamp.now().strftime("%Y-%m")
    mois_ancien = (pd.Timestamp.now() - pd.offsets.MonthBegin(3)).strftime("%Y-%m")

    # Un jeu de donnees minimal contenant les deux mois, pour que les deux
    # figurent dans la liste deroulante des periodes.
    index = pd.to_datetime([f"{mois_ancien}-15", f"{mois_en_cours}-01"])
    df = pd.DataFrame({"annee_oa": [0, 0]}, index=index)

    fichier = tmp_path / "prefs.ini"
    settings = QSettings(str(fichier), QSettings.Format.IniFormat)
    # Derniere periode consultee : un mois passe.
    settings.setValue("ui/period", f"month-{mois_ancien}")

    faux_self = SimpleNamespace(
        settings=settings,
        data=SimpleNamespace(df=df, start_oa=None),
    )
    periode = app_desktop.MainWindow._startup_period(faux_self)

    assert periode == f"month-{mois_en_cours}"
