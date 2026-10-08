"""Un emoji, puis UNE espace, puis le texte (charte, section 2).

Modele de Recharges VE (08/10/2026). Le test lit les chaines du code de
l'interface.

    py -m pytest tests/test_emoji_une_espace.py
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

PROJET = Path(__file__).resolve().parent.parent
EMOJI_PUIS_DEUX_ESPACES = re.compile(
    "[\U0001F300-\U0001FAFF☀-➿][️]?  ")


def _fichiers() -> list[Path]:
    ignores = {"tests", "build", "dist", ".venv", "distribution",
               "installeur", "docs", "__pycache__", "backups"}
    return [p for p in PROJET.rglob("*.py")
            if not ignores.intersection(p.relative_to(PROJET).parts)]


def test_une_seule_espace_apres_un_emoji():
    fautes = []
    for p in _fichiers():
        arbre = ast.parse(p.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if (isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)
                    and EMOJI_PUIS_DEUX_ESPACES.search(noeud.value)):
                fautes.append(f"{p.name}:{noeud.lineno}")
    assert not fautes, fautes
