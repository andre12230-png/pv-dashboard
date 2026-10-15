"""Le dossier construit ne doit emporter aucune donnee personnelle, a
aucune profondeur.

Ajoute le 15/10/2026 : le controle d'avant l'installeur et l'archive ne
regardait que le premier niveau du dossier construit ; un config-local.yaml
glisse dans un sous-dossier (par exemple _internal) serait parti chez un
inconnu.
"""
from __future__ import annotations

import faire_installeur as fi


def _dossier(tmp_path, noms):
    """Cree un faux dossier construit avec les fichiers donnes."""
    racine = tmp_path / "pv-dashboard"
    for nom in noms:
        chemin = racine / nom
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text("x", encoding="utf-8")
    return racine


def test_un_dossier_propre_passe(tmp_path):
    racine = _dossier(tmp_path, [
        "pv-dashboard.exe",
        "_internal/python312.dll",
        "_internal/matplotlib/mpl-data/exemple.csv",  # bibliotheque
    ])
    assert fi.chercher_donnees_personnelles(racine) == []


def test_les_donnees_au_premier_niveau_sont_trouvees(tmp_path):
    racine = _dossier(tmp_path, ["pv-dashboard.exe", "config-local.yaml"])
    assert fi.chercher_donnees_personnelles(racine) == ["config-local.yaml"]


def test_les_donnees_dans_les_sous_dossiers_sont_trouvees(tmp_path):
    racine = _dossier(tmp_path, [
        "pv-dashboard.exe",
        "_internal/config-local.yaml",
        "_internal/donnees/Releves-pv.csv",
        "sous-dossier/config.yaml",
        "sous-dossier/pv-dashboard.log",
        "_internal/backups/Releves-pv_jour_20260101.csv",
    ])
    assert fi.chercher_donnees_personnelles(racine) == [
        "_internal/backups",
        "_internal/config-local.yaml",
        "_internal/donnees/Releves-pv.csv",
        "sous-dossier/config.yaml",
        "sous-dossier/pv-dashboard.log",
    ]


def test_la_casse_ne_trompe_pas_le_controle(tmp_path):
    """Windows ne distingue pas majuscules et minuscules : le controle non
    plus."""
    racine = _dossier(tmp_path, ["_internal/Config-Local.YAML"])
    assert fi.chercher_donnees_personnelles(racine) == [
        "_internal/Config-Local.YAML"]
