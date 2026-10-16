"""Choix Clair / Sombre au tout premier lancement (demande de l'auteur,
16/10/2026, comme dans Recharges VE).

Le mode sombre ne se trouvait que dans Parametres › Apparence : un nouvel
utilisateur ne savait pas qu'il existait. Au premier lancement, avant le
chargement, l'application demande maintenant « Clair ou Sombre ? ». Jamais a
quelqu'un qui a deja son config.yaml (mise a jour) ni qui a deja choisi.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

import premier_theme  # noqa: E402
from gui_theme import CLE_THEME, nom_du_theme  # noqa: E402


def _reglages(tmp_path):
    """Des preferences jetables, jamais le registre de l'utilisateur."""
    return QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)


def _dossier(tmp_path):
    dossier = tmp_path / "donnees"
    dossier.mkdir()
    return dossier


def test_dossier_sans_config_et_aucun_choix_c_est_un_premier_lancement(tmp_path):
    assert premier_theme.est_premier_lancement(_reglages(tmp_path),
                                               _dossier(tmp_path))


def test_dossier_absent_c_est_aussi_un_premier_lancement(tmp_path):
    assert premier_theme.est_premier_lancement(_reglages(tmp_path),
                                               tmp_path / "pas_encore_cree")


def test_deja_un_config_yaml_on_ne_demande_rien(tmp_path):
    """Une mise a jour : l'utilisateur a deja ses reglages."""
    dossier = _dossier(tmp_path)
    (dossier / "config.yaml").write_text("site: {}\n", encoding="utf-8")
    assert not premier_theme.est_premier_lancement(_reglages(tmp_path),
                                                   dossier)


def test_theme_deja_choisi_on_ne_demande_rien(tmp_path):
    reglages = _reglages(tmp_path)
    reglages.setValue(CLE_THEME, "clair")
    assert not premier_theme.est_premier_lancement(reglages,
                                                   _dossier(tmp_path))


def test_preference_abimee_traitee_comme_absente(tmp_path):
    """Une valeur revenue en liste (audit du 13/10/2026) ne fait pas
    planter le demarrage : on repose la question."""
    reglages = _reglages(tmp_path)
    reglages.setValue(CLE_THEME, ["clair", "sombre"])
    assert premier_theme.est_premier_lancement(reglages, _dossier(tmp_path))


def test_le_choix_sombre_est_retenu(tmp_path):
    reglages = _reglages(tmp_path)
    nom = premier_theme.demander_au_premier_lancement(
        reglages, _dossier(tmp_path), demander=lambda: "sombre")
    assert nom == "sombre"
    assert nom_du_theme(reglages) == "sombre"


def test_le_choix_est_retenu_pour_ne_plus_redemander(tmp_path):
    reglages, dossier = _reglages(tmp_path), _dossier(tmp_path)
    premier_theme.demander_au_premier_lancement(
        reglages, dossier, demander=lambda: "clair")
    assert not premier_theme.est_premier_lancement(reglages, dossier)


def test_pas_de_question_hors_premier_lancement(tmp_path):
    dossier = _dossier(tmp_path)
    (dossier / "config.yaml").write_text("site: {}\n", encoding="utf-8")

    def demander():
        raise AssertionError("la question n'aurait pas du etre posee")
    assert premier_theme.demander_au_premier_lancement(
        _reglages(tmp_path), dossier, demander=demander) is None


def test_la_boite_propose_clair_et_sombre_clair_par_defaut():
    QApplication.instance() or QApplication([])
    boite, clair, sombre = premier_theme.boite_du_choix()
    assert isinstance(boite, QMessageBox)
    assert clair.text() == "Clair"
    assert sombre.text() == "Sombre"
    assert boite.defaultButton() is clair
    assert boite.escapeButton() is clair
    assert "Paramètres › Apparence" in boite.text()


def test_le_lanceur_demande_apres_le_verrou_et_avant_le_chargement():
    """Pas de question si l'application est deja ouverte ; et la reponse
    doit etre connue avant d'importer les vues, qui prennent leurs
    couleurs a l'import."""
    import inspect

    import run
    source = inspect.getsource(run.main)
    position = source.index("demander_au_premier_lancement")
    assert source.index("prendre_le_verrou()") < position
    assert position < source.index("import app_desktop")
