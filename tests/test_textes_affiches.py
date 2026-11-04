"""Les textes affichés suivent la charte des applis.

Contrôle des textes du 04-11-2026 (rapport
F:\\Projets\\livrables\\controle-textes-photovoltaique-04-11-2026.md), écarts
X1 à X8. On lit le code source : ces textes sont dans des boîtes ou des
pages difficiles à ouvrir une à une dans un test.

    py -m pytest tests/test_textes_affiches.py
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent

# Les fichiers du programme (sans les tests ni les outils de fabrication).
FICHIERS_PROGRAMME = sorted(
    p for p in RACINE.rglob("*.py")
    if p.relative_to(RACINE).parts[0] not in {"tests", "build", "dist"}
    and p.name not in {"captures_site.py", "faire_archive.py",
                       "faire_installeur.py", "smoke_desktop.py"})


def _source(nom: str) -> str:
    return (RACINE / nom).read_text(encoding="utf-8")


def _textes(nom: str) -> list[str]:
    """Les chaînes d'un fichier, morceaux de f-strings compris."""
    arbre = ast.parse(_source(nom))
    textes = []
    for n in ast.walk(arbre):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            textes.append(n.value)
    return textes


def _titres_de_boites(nom: str) -> list[tuple[int, str]]:
    """Le titre (2e argument) de chaque QMessageBox.warning / critical /
    information et de chaque demander_enregistrement, tel qu'écrit dans le
    code : le texte, ou le nom de la constante."""
    arbre = ast.parse(_source(nom))
    titres = []
    for n in ast.walk(arbre):
        if not isinstance(n, ast.Call) or len(n.args) < 2:
            continue
        f = n.func
        nom_appel = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
        if nom_appel not in {"warning", "critical", "information",
                             "demander_enregistrement"}:
            continue
        titre = n.args[1]
        if isinstance(titre, ast.Constant):
            titres.append((n.lineno, titre.value))
        elif isinstance(titre, ast.Name):
            titres.append((n.lineno, titre.id))
    return titres


# --- X1 : le titre d'une boîte dit de quoi il s'agit ---------------------

@pytest.mark.parametrize("fichier", ["app_desktop.py", "run.py",
                                     "fenetre_reglages.py"])
def test_aucune_boite_n_a_pour_titre_le_nom_de_l_appli(fichier):
    vagues = {"NOM_AFFICHE", "Gestion Photovoltaïque", "TITRE"}
    fautifs = [(ligne, t) for ligne, t in _titres_de_boites(fichier)
               if t in vagues]
    assert not fautifs, f"{fichier} : titres trop vagues {fautifs}"


def test_un_theme_non_enregistre_ne_s_intitule_pas_apparence():
    # « Apparence » reste pour la boîte qui annonce le changement ; un
    # échec dit ce qui n'a pas marché.
    titres = [t for _, t in _titres_de_boites("app_desktop.py")]
    assert "Thème non enregistré" in titres


@pytest.mark.parametrize("titre", [
    "Saisie non enregistrée", "Réglages non relus", "Relevés non relus",
    "Thème non enregistré"])
def test_titres_de_la_fenetre_principale(titre):
    assert titre in [t for _, t in _titres_de_boites("app_desktop.py")]


@pytest.mark.parametrize("titre", ["Application déjà ouverte",
                                   "Démarrage impossible"])
def test_titres_du_lanceur(titre):
    assert titre in [t for _, t in _titres_de_boites("run.py")]


def test_titre_du_refus_de_mes_reglages():
    assert "Réglages non enregistrés" in [
        t for _, t in _titres_de_boites("fenetre_reglages.py")]


# --- X2 : pas de « OK » dans les comptes rendus --------------------------

def test_pas_de_ok_dans_les_comptes_rendus_de_la_saisie():
    fautifs = [t for t in _textes("views/saisie.py")
               if re.search(r"(^|\s)OK\b", t)]
    assert not fautifs, fautifs


# --- X3 : guillemets français autour d'une valeur citée -------------------

def test_valeurs_citees_entre_guillemets_francais():
    # « date '2026' incomplète » devient « date « 2026 » incomplète ».
    source = _source("data_loaders.py")
    assert not re.search(r"'\{[^}]+\}'", source), \
        "une valeur citée entre ' ' dans data_loaders.py"


# --- X4 : apostrophe droite partout ---------------------------------------

def test_aucune_apostrophe_courbe_dans_le_programme():
    fautifs = [p.relative_to(RACINE).as_posix() for p in FICHIERS_PROGRAMME
               if "’" in p.read_text(encoding="utf-8")]
    assert not fautifs, fautifs


# --- X5 : milliers séparés dans le glossaire ------------------------------

def test_milliers_separes_dans_le_glossaire():
    from views.aide import GLOSSAIRE_HTML
    # Un nombre de quatre chiffres collés, sauf le formulaire 3517-S.
    motif = r"\b\d{4}\b(?!-S)"
    assert not re.search(motif, GLOSSAIRE_HTML), \
        re.findall(motif, GLOSSAIRE_HTML)


# --- X6 : pas de « j » pour « jours » dans une phrase ---------------------

def test_pas_de_j_abrege_sur_la_page_tva():
    fautifs = [t for t in _textes("views/tva.py") if re.search(r"\sj\)", t)]
    assert not fautifs, fautifs


# --- X7 : pas de point après des points de suspension ---------------------

def test_pas_de_point_apres_les_points_de_suspension_dans_la_notice():
    from views.aide import NOTICE_HTML
    texte = re.sub(r"<[^>]+>", "", NOTICE_HTML)
    # « jours…. » en fin de phrase ; pas « Export_…_Index_….xlsx ».
    assert not re.search(r"…\.(\s|$)", texte)


# --- X8 : « €/mois », comme dans Mes réglages ------------------------------

def test_abonnement_ecrit_euros_par_mois_sans_espaces():
    assert not [t for t in _textes("views/settings.py") if " / mois" in t]
