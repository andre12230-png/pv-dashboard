"""L'archive portable (.zip) ne doit jamais emporter de donnees personnelles.

Ajoutee le 15/09/2026 : jusque-la, seul l'installeur etait propose au
telechargement.
"""
from __future__ import annotations

import zipfile

import faire_archive as fa


def _archive(tmp_path, noms):
    chemin = tmp_path / "essai.zip"
    with zipfile.ZipFile(chemin, "w") as z:
        for nom in noms:
            z.writestr(nom, "x")
    return chemin


def test_une_archive_propre_passe(tmp_path):
    archive = _archive(tmp_path, [
        "pv-dashboard/pv-dashboard.exe",
        "pv-dashboard/config.yaml",               # le modele vierge
        "pv-dashboard/config-local.exemple.yaml",
        "pv-dashboard/_internal/matplotlib/exemple.csv",  # bibliotheque
        "README.md",
        "LICENSE",
    ])
    assert fa.verifier_archive(archive) == []


def test_les_donnees_personnelles_sont_denoncees(tmp_path):
    archive = _archive(tmp_path, [
        "pv-dashboard/pv-dashboard.exe",
        "pv-dashboard/config-local.yaml",
        "pv-dashboard/Releves-pv.csv",
        "pv-dashboard/backups/Releves-pv_jour_20260915.csv",
        "pv-dashboard/pv-dashboard.log",
    ])
    assert sorted(fa.verifier_archive(archive)) == [
        "pv-dashboard/Releves-pv.csv",
        "pv-dashboard/backups/Releves-pv_jour_20260915.csv",
        "pv-dashboard/config-local.yaml",
        "pv-dashboard/pv-dashboard.log",
    ]


def test_l_archive_contient_ce_que_livre_l_installeur():
    """Memes modeles que installeur/pv-dashboard.iss : sans eux, la version
    portable ne saurait pas preparer son dossier de donnees."""
    recette = (fa.RACINE / "installeur" / "pv-dashboard.iss").read_text(
        encoding="utf-8")
    for nom in fa.MODELES:
        assert nom in recette
