"""Le nom de l'application, accentue partout ou il s'affiche.

29/09/2026 : les titres des boites de message, l'ecran de chargement et le
titre de la fenetre disaient « Gestion Photovoltaique », sans trema, alors
que le bandeau dit « Photovoltaïque ». Le nom interne APP_NAME garde sa
forme d'origine (nom de l'application pour Qt, a ne pas changer) ; ce qui
s'affiche passe par NOM_AFFICHE.

    py -m pytest tests/test_nom_accentue.py
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent


def _textes_sans_accent(fichier: Path) -> list[int]:
    """Lignes des textes du code (hors docstrings et hors la definition
    d'APP_NAME) qui ecrivent « Photovoltaique » sans trema."""
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    a_ignorer = set()
    for noeud in ast.walk(arbre):
        # Les docstrings : une chaine seule sur sa ligne.
        if isinstance(noeud, ast.Expr) and isinstance(noeud.value, ast.Constant):
            a_ignorer.add(id(noeud.value))
        # APP_NAME = "Gestion Photovoltaique" : le nom interne, voulu.
        if (isinstance(noeud, ast.Assign)
                and any(isinstance(c, ast.Name) and c.id == "APP_NAME"
                        for c in noeud.targets)):
            a_ignorer.add(id(noeud.value))
    return sorted(
        n.lineno for n in ast.walk(arbre)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
        and "Photovoltaique" in n.value and id(n) not in a_ignorer)


@pytest.mark.parametrize("nom", ["run.py", "app_desktop.py"])
def test_textes_affiches_accentues(nom):
    assert _textes_sans_accent(RACINE / nom) == []


def test_titre_de_la_fenetre_accentue():
    import app_desktop
    assert app_desktop.NOM_AFFICHE == "Gestion Photovoltaïque"
    assert app_desktop.APP_NAME == "Gestion Photovoltaique"   # inchange
