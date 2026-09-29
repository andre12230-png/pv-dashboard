"""Pas de pluriel entre parentheses dans les textes de l'application.

Relecture du 29/09/2026 (charte des trois applis) : « 1614 jour(s) »,
« 2 ligne(s) datée(s) », « 0 nouveau(x) »... L'application connait le nombre :
elle accorde (« 1 jour », « 2 lignes »). Un utilisateur avait deja mal lu
« 0 nouveau(x) » (18/09/2026).

Le test lit le code de l'application : chaque chaine de caracteres (textes
des f-strings compris), hors commentaires et descriptions de fonctions
(docstrings), que l'utilisateur ne voit jamais.

    py -m pytest tests/test_pluriels.py
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

PROJET = Path(__file__).resolve().parent.parent
# « jour(s) », « nouveau(x) », « datée(s) », « relevée(s) »... ; pas « f(x) ».
PLURIEL_ENTRE_PARENTHESES = re.compile(r"[a-zà-ÿ]{2,}\((s|x|e|es)\)")


def _fichiers_de_l_application() -> list[Path]:
    ignores = {"tests", "build", "dist", ".venv", "outils"}
    return [p for p in PROJET.rglob("*.py")
            if not ignores.intersection(p.relative_to(PROJET).parts)]


def _docstrings(arbre: ast.AST) -> set[int]:
    """Identifiants des noeuds qui sont des docstrings."""
    ids = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.Module, ast.ClassDef, ast.FunctionDef,
                              ast.AsyncFunctionDef)):
            corps = noeud.body
            if (corps and isinstance(corps[0], ast.Expr)
                    and isinstance(corps[0].value, ast.Constant)
                    and isinstance(corps[0].value.value, str)):
                ids.add(id(corps[0].value))
    return ids


def test_aucun_pluriel_entre_parentheses():
    trouves = []
    for fichier in _fichiers_de_l_application():
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        docs = _docstrings(arbre)
        for noeud in ast.walk(arbre):
            if (isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)
                    and id(noeud) not in docs
                    and PLURIEL_ENTRE_PARENTHESES.search(noeud.value)):
                trouves.append(f"{fichier.relative_to(PROJET)}:{noeud.lineno} "
                               f"{noeud.value.strip()[:60]!r}")
    assert not trouves, "\n".join(trouves)


def test_le_test_voit_bien_un_pluriel_entre_parentheses():
    """Garde-fou : le motif reconnait les formes relevees le 29/09/2026."""
    for texte in ("1614 jour(s)", "0 nouveau(x)", "2 ligne(s) datée(s)",
                  "déjà relevée(s)"):
        assert PLURIEL_ENTRE_PARENTHESES.search(texte), texte
    # Une formule a une lettre n'est pas un pluriel.
    assert not PLURIEL_ENTRE_PARENTHESES.search("f(x) et g(e)")
