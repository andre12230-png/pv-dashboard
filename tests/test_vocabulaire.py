"""Un nom par flux d'energie, sur tous les ecrans (choix de l'auteur, 30/09/2026).

Avant, l'electricite achetee s'appelait « Soutirage réseau », « Acheté au
réseau », « Achetée », « Conso réseau » ou « Consommation du réseau » selon
l'ecran ; l'envoyee « Injectée », « Injection vendue », « Injection réseau » ;
l'autoconsommee « Autoconso », « Autoconsommée ». Desormais :

- « Achat au réseau » ;
- « Injection » ;
- « Autoconsommation ».

Les phrases qui expliquent une barre ou un ruban restent (« Vendu à EDF OA
370 kWh », « Acheté au réseau »). Les noms internes (cles de programme et de
configuration, colonnes reconnues a l'import) ne sont pas des textes
affiches : ils ne changent pas.

Le test lit le code de l'application : chaque chaine affichee (textes des
f-strings compris), hors docstrings et hors identifiants.

    py -m pytest tests/test_vocabulaire.py
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

PROJET = Path(__file__).resolve().parent.parent

ANCIENS_NOMS = re.compile(
    r"Soutirage réseau|Achetée|Conso réseau|Consommation du réseau"
    r"|Conso H[CP]|Autoconsommée|Injectée|Injection vendue|Injection réseau"
    r"|(?<![\w_])[Aa]utoconso(?![\w_])")


def _fichiers_de_l_application() -> list[Path]:
    ignores = {"tests", "build", "dist", ".venv", "outils"}
    return [p for p in PROJET.rglob("*.py")
            if not ignores.intersection(p.relative_to(PROJET).parts)]


def _docstrings(arbre: ast.AST) -> set[int]:
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


def test_un_nom_par_flux():
    trouves = []
    for fichier in _fichiers_de_l_application():
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        docs = _docstrings(arbre)
        for noeud in ast.walk(arbre):
            if not (isinstance(noeud, ast.Constant)
                    and isinstance(noeud.value, str)) or id(noeud) in docs:
                continue
            texte = noeud.value
            # Cle de programme en minuscules (« autoconso », « part_hc_autoconso ») ;
            # un libelle d'un mot (« Autoconso ») porte une majuscule.
            if texte.isidentifier() and texte == texte.lower():
                continue
            if ANCIENS_NOMS.search(texte):
                trouves.append(f"{fichier.relative_to(PROJET)}:{noeud.lineno} "
                               f"{texte.strip()[:60]!r}")
    assert not trouves, "\n".join(trouves)


def test_le_motif_reconnait_les_anciens_noms():
    for texte in ("Soutirage réseau", "Achetée au réseau", "Part autoconso",
                  "Autoconso", "Injectée", "Conso HC"):
        assert ANCIENS_NOMS.search(texte), texte
    for texte in ("part_hc_autoconso", "Autoconsommation", "Achat au réseau",
                  "Acheté au réseau", "Injection", "Vendu à EDF OA"):
        assert not ANCIENS_NOMS.search(texte), texte
