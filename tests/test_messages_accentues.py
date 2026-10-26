"""Les messages montres a l'utilisateur sont accentues (controle du 26/10/2026).

Le controle du francais a trouve des messages ecrits sans accents : la
liste « Il manque : » d'une configuration incomplete (« la duree du contrat
de vente, en annees », « sert de modele »), « la fenetre ne sait pas
modifier », « Données rechargees », « Enregistrement annule. ». Ce test lit
tout le texte du code de l'application et refuse les formes non accentuees
les plus courantes. Les docstrings, les messages d'assert et les journaux
techniques (print) ne s'affichent pas a l'ecran : ils sont laisses de cote.

    py -m pytest tests/test_messages_accentues.py
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

PROJET = Path(__file__).resolve().parent.parent
IGNORES = {"tests", "build", "dist", ".venv", "distribution", "installeur",
           "docs", "__pycache__", "backups", "factures"}
# La feuille de style (ses commentaires sont dans une chaine) ne s'affiche
# pas, ni les outils de fabrication et le controle « smoke ».
HORS_ECRAN = {"gui_theme.py", "smoke_desktop.py", "captures_site.py",
              "faire_archive.py", "faire_installeur.py"}

# Mots qui ne s'ecrivent jamais ainsi en francais correct. « duree » et
# « annees » seuls sont aussi des noms de reglages : on ne les cherche que
# dans une tournure de phrase (« la duree du », « en annees »).
SANS_ACCENT = re.compile(
    r"\b(?:etre|negatifs?|negatives?|superieure?s?|inferieure?s?|comptees?|"
    r"fenetres?|rechargees|duree du|en annees|modeles?|a cote|a zero|"
    r"debut du|livre avec|annule\.)(?![\w'])",
    re.IGNORECASE)


def _fichiers() -> list[Path]:
    return [p for p in sorted(PROJET.rglob("*.py"))
            if not IGNORES.intersection(p.relative_to(PROJET).parts)
            and p.name not in HORS_ECRAN]


def _textes_affiches(fichier: Path):
    """Les chaines du code, sans docstrings, messages d'assert ni print."""
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    ignores = set()
    for n in ast.walk(arbre):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef,
                          ast.AsyncFunctionDef)):
            corps = n.body
            if (corps and isinstance(corps[0], ast.Expr)
                    and isinstance(corps[0].value, ast.Constant)):
                ignores.add(id(corps[0].value))
        if isinstance(n, ast.Assert) and n.msg is not None:
            ignores.update(id(m) for m in ast.walk(n.msg))
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "print"):
            for arg in n.args:
                ignores.update(id(m) for m in ast.walk(arg))
    for n in ast.walk(arbre):
        if (isinstance(n, ast.Constant) and isinstance(n.value, str)
                and id(n) not in ignores):
            yield n.lineno, n.value


def test_aucun_message_sans_accent():
    fautes = []
    for fichier in _fichiers():
        for ligne, texte in _textes_affiches(fichier):
            trouve = SANS_ACCENT.search(texte)
            if trouve:
                fautes.append(f"{fichier.relative_to(PROJET)}:{ligne} "
                              f"« {trouve.group(0)} »")
    assert not fautes, "Accents manquants :\n" + "\n".join(fautes)


def test_la_configuration_incomplete_est_dite_avec_ses_accents():
    """Le cas trouve par le controle, verifie sur le message lui-meme."""
    pytest.importorskip("pandas")
    import app_desktop

    cfg = {"installation": {"puissance_kwc": 9.0, "cout_total_eur": 18000.0,
                            "date_mise_en_service": "2026-05-15"},
           "oa": {"type": "surplus"},
           "tarifs_reseau": {"contrat_hphc": {
               "periodes": [{"debut": "2026-01-01", "fin": None,
                             "abonnement": 19.0, "prix_hp": 0.21,
                             "prix_hc": 0.16}],
               "plages_hc": ["22:00-06:00"]}},
           "sources": {"releves_csv": "Releves-pv.csv"}}
    with pytest.raises(RuntimeError) as erreur:
        app_desktop.verifier_config(cfg)
    message = str(erreur.value)
    assert "la date de début du contrat de vente" in message
    assert "la durée du contrat de vente, en années" in message
    assert "Le fichier livré avec l'application sert de modèle." in message
