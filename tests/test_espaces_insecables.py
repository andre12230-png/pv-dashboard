"""Montants et nombres à espaces insécables (charte, section 4).

Avec une espace ordinaire, « 1 494,74 € » pouvait se couper en fin de
ligne : « 1 » d'un côté, « 494,74 € » de l'autre. Les milliers et l'unité
sont séparés par une espace insécable (\\xa0), comme dans Pécule
(07/10/2026).
"""
from __future__ import annotations

import pytest

pytest.importorskip("pandas")

from accords import nombre  # noqa: E402
from views._helpers import (fmt_eur, fmt_kwh, fmt_kwh_seul,  # noqa: E402
                            fmt_pct, fmt_prix_kwh, nombre_barre)

NBSP = "\xa0"


def test_les_montants_ne_se_coupent_pas():
    assert fmt_eur(1494.74) == f"1{NBSP}494,74{NBSP}€"
    assert fmt_eur(1494.74, signed=True) == f"+1{NBSP}494,74{NBSP}€"
    assert fmt_eur(-9000) == f"-9{NBSP}000,00{NBSP}€"


def test_les_nombres_ne_se_coupent_pas():
    assert fmt_kwh_seul(3650) == f"3{NBSP}650,0{NBSP}kWh"
    assert nombre_barre(7812) == f"7{NBSP}812"
    assert nombre(1614) == f"1{NBSP}614"


def test_l_unite_reste_collee_au_nombre():
    assert fmt_kwh(27.3) == f"27,3{NBSP}kWh"
    assert fmt_kwh(2760) == f"2,76{NBSP}MWh"
    assert fmt_pct(41.1) == f"41,1{NBSP}%"
    assert fmt_prix_kwh(0.1985) == f"0,1985{NBSP}€/kWh"


def test_aucune_espace_ordinaire_dans_un_montant():
    for texte in (fmt_eur(1234567.89), fmt_kwh_seul(1234567), nombre(1234567)):
        assert " " not in texte, repr(texte)


# --- Les textes ecrits directement dans le code (08/10/2026) ---------------
# Les fonctions de mise en forme ne suffisent pas : beaucoup de phrases
# ecrivent elles-memes « {x} kWh » ou « 100 km ». Ce test lit tout le code
# de l'application et refuse une espace ordinaire entre un nombre et son
# unite, ou entre les milliers.

import ast  # noqa: E402
import re  # noqa: E402
from pathlib import Path  # noqa: E402

HORS_ECRAN: set[str] = set()
RACINE = Path(__file__).resolve().parent.parent
IGNORES = {"tests", "build", "dist", ".venv", "distribution", "installeur",
           "migration", "docs", "__pycache__", "outils"}
UNITES = r"(?:€|kWh|MWh|kWc|kW|km|%|L\b|Wc|W\b)"
APRES_CHIFFRE = re.compile(r"\d " + UNITES)
EN_TETE = re.compile(r"^ " + UNITES)


def _fichiers_affiches():
    for fichier in sorted(RACINE.rglob("*.py")):
        rel = fichier.relative_to(RACINE)
        if IGNORES.intersection(rel.parts) or rel.as_posix() in HORS_ECRAN:
            continue
        if fichier.name.startswith(("captures", "faire_", "preparer_",
                                    "generer_")):
            continue
        yield rel, fichier


def _fautes_d_espace():
    fautes = []
    for rel, fichier in _fichiers_affiches():
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        ignores = set()
        for n in ast.walk(arbre):
            # Docstrings, et messages d'assert : jamais montres a l'ecran
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef,
                              ast.AsyncFunctionDef)):
                c = n.body
                if (c and isinstance(c[0], ast.Expr)
                        and isinstance(c[0].value, ast.Constant)):
                    ignores.add(id(c[0].value))
            if isinstance(n, ast.Assert) and n.msg is not None:
                ignores.update(id(m) for m in ast.walk(n.msg))
        for n in ast.walk(arbre):
            if id(n) in ignores:
                continue
            if isinstance(n, ast.JoinedStr):
                for a, b in zip(n.values, n.values[1:]):
                    if (isinstance(a, ast.FormattedValue)
                            and isinstance(b, ast.Constant)
                            and EN_TETE.search(b.value)):
                        fautes.append(f"{rel}:{b.lineno} {b.value[:30]!r}")
            if (isinstance(n, ast.Constant) and isinstance(n.value, str)
                    and APRES_CHIFFRE.search(n.value)):
                fautes.append(f"{rel}:{n.lineno} "
                              f"{APRES_CHIFFRE.search(n.value).group()!r}")
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "replace" and len(n.args) == 2
                    and all(isinstance(x, ast.Constant) for x in n.args)
                    and n.args[0].value == "," and n.args[1].value == " "):
                fautes.append(f"{rel}:{n.lineno} milliers a l'espace ordinaire")
    return fautes


def test_les_textes_du_code_n_ont_pas_d_espace_secable_avant_une_unite():
    fautes = _fautes_d_espace()
    assert not fautes, (f"{len(fautes)} fautes : espace ordinaire avant une "
                        "unite (ecrire \\xa0) :\n" + "\n".join(fautes))
