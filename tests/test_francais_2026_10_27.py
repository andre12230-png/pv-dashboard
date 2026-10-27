"""Controle du francais du 26/10/2026 : le lot du Photovoltaique corrige le
27/10/2026 (rapport : F:\\Projets\\livrables\\controle-francais-applis-26-10-2026.md).

Dans les textes montres a l'utilisateur :
- « … » et non « ... » ; « — » et non « -- » entre deux mots ;
- des guillemets « » et non des apostrophes droites autour d'un terme
  ('injection', 'date;valeur') ;
- « n° 2 » et non « #2 » (« Année OA n° 2 », comme « Année de contrat n° 2 ») ;
- « Consommation » et non « Conso » ; « €/kWh » et non « EUR/kWh » ;
- « e-mail » ; « Heures pleines / heures creuses » sans majuscules au
  milieu du glossaire.
Les docstrings, les journaux techniques et la feuille de style sont laisses
de cote. Les styles de ligne de matplotlib (ls="--") ne sont pas du texte.

    py -m pytest tests/test_francais_2026_10_27.py
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

PROJET = Path(__file__).resolve().parent.parent
IGNORES = {"tests", "build", "dist", ".venv", "distribution", "installeur",
           "docs", "__pycache__", "backups", "factures"}
HORS_ECRAN = {"gui_theme.py", "gui_widgets.py", "smoke_desktop.py",
              "captures_site.py", "faire_archive.py", "faire_installeur.py"}

FAUTES = [
    ("trois points", re.compile(r"\.\.\.")),
    ("tiret double", re.compile(r"(^|\s)--(\s|$)")),
    ("apostrophes en guise de guillemets",
     re.compile(r"(^|[\s(/])'[^'\s][^']{1,40}'(?=[\s,.;:)/]|$)")),
    # « #2 », « #{n} » ; pas une couleur (#94a3b8, #1F3A6B).
    ("dièse pour un numéro", re.compile(r"#\{|#\d+(?![0-9A-Fa-f])")),
    ("Conso", re.compile(r"\bConso (recalée|connue)")),
    ("EUR/kWh", re.compile(r"EUR/kWh")),
    ("email", re.compile(r"reçu par email")),
    ("majuscules du glossaire", re.compile(r"Heures Pleines / Heures Creuses")),
]


def _fichiers() -> list[Path]:
    return [p for p in sorted(PROJET.rglob("*.py"))
            if not (set(p.relative_to(PROJET).parts) & IGNORES)
            and p.name not in HORS_ECRAN]


def _textes(fichier: Path) -> list[tuple[int, str]]:
    """Les chaines du fichier, sans les docstrings ni les print()."""
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    exclus = set()
    for n in ast.walk(arbre):
        corps = getattr(n, "body", None)
        if (isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))
                and corps and isinstance(corps[0], ast.Expr)
                and isinstance(corps[0].value, ast.Constant)):
            exclus.add(id(corps[0].value))
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "print"):
            exclus.update(id(x) for x in ast.walk(n))
    return [(n.lineno, n.value) for n in ast.walk(arbre)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in exclus]


@pytest.mark.parametrize("fichier", _fichiers(),
                         ids=lambda p: str(p.relative_to(PROJET)))
def test_textes_affiches_en_bon_francais(fichier):
    fautes = [(ligne, nom, texte[:70])
              for ligne, texte in _textes(fichier)
              if texte != "--"          # ls="--" : style de ligne
              for nom, motif in FAUTES if motif.search(texte)]
    assert fautes == []


def test_annee_oa_numerotee_en_francais():
    from views import _helpers
    assert _helpers._MOTS_EDF_OA["long"].format(n=2) == "Année OA n° 2"
    assert _helpers._MOTS_EDF_OA["court"].format(n=2) == "OA n° 2"
    assert _helpers._MOTS_EDF_OA["numero"].format(n=2) == "n° 2"
