"""Les erreurs techniques dites en francais dans les messages a l'ecran.

Diagnostic du 26/09/2026 : sept messages recopiaient tel quel le texte
d'erreur de Python, en anglais (« File is not a zip file », « [Errno 13]
Permission denied », « KeyError : 'Date' »). erreurs.py les traduit ; il est
commun aux trois applications (meme fichier dans Pecule et Recharges VE).

Deux parties : la traduction elle-meme, puis un controle du code — aucune
erreur attrapee ne doit plus etre recopiee brute dans un message (seuls les
print() vers le journal technique le peuvent).

    py -m pytest tests/test_erreurs_en_clair.py
"""
from __future__ import annotations

import ast
import errno
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from erreurs import erreur_en_clair

RACINE = Path(__file__).resolve().parent.parent
ANGLAIS = ("Expecting", "Permission denied", "No such file", "codec",
           "No space", "zip file", "database is locked", "malformed")


def sans_anglais(texte: str) -> bool:
    return not any(mot in texte for mot in ANGLAIS)


def _leve(fonction):
    try:
        fonction()
    except Exception as e:      # noqa: BLE001
        return e
    raise AssertionError("aucune erreur levee")


# ---------- la traduction ----------

def test_json_abime_dit_ou():
    texte = erreur_en_clair(_leve(lambda: json.loads('{"a": [,]}')))
    assert "ligne 1, colonne" in texte and sans_anglais(texte)


def test_caracteres_mal_codes():
    texte = erreur_en_clair(_leve(lambda: "Prés".encode("cp1252").decode()))
    assert "mal codés" in texte and sans_anglais(texte)


def test_acces_refuse_nomme_le_fichier():
    texte = erreur_en_clair(PermissionError(
        errno.EACCES, "Permission denied", r"C:\Donnees\Releves-pv.csv"))
    assert "« Releves-pv.csv »" in texte and "autre programme" in texte
    assert sans_anglais(texte)


def test_fichier_introuvable():
    texte = erreur_en_clair(FileNotFoundError(
        errno.ENOENT, "No such file or directory", r"C:\x\export.xlsx"))
    assert "« export.xlsx » introuvable" in texte and sans_anglais(texte)


def test_disque_plein():
    texte = erreur_en_clair(OSError(errno.ENOSPC, "No space left on device"))
    assert "disque est plein" in texte and sans_anglais(texte)


def test_classeur_excel_abime(tmp_path):
    faux = tmp_path / "faux.xlsx"
    faux.write_text("pas un classeur", encoding="utf-8")
    texte = erreur_en_clair(_leve(lambda: zipfile.ZipFile(faux)))
    assert "classeur Excel" in texte and sans_anglais(texte)


def test_colonne_manquante():
    texte = erreur_en_clair(_leve(lambda: {}["Date"]))
    assert "« Date »" in texte and texte.startswith("Une information")


def test_base_occupee():
    texte = erreur_en_clair(sqlite3.OperationalError("database is locked"))
    assert "occupée" in texte and sans_anglais(texte)


def test_base_abimee():
    texte = erreur_en_clair(
        sqlite3.DatabaseError("database disk image is malformed"))
    assert "abîmée" in texte and sans_anglais(texte)


def test_erreur_de_programme_signalee_comme_inattendue():
    texte = erreur_en_clair(_leve(lambda: None.upper()))
    assert texte.startswith("Erreur inattendue")
    assert "AttributeError" in texte      # garde de quoi l'identifier


def test_message_deja_en_francais_inchange():
    assert erreur_en_clair(ValueError("Date invalide.")) == "Date invalide."
    assert erreur_en_clair(RuntimeError("config.yaml est mal écrit.")) \
        == "config.yaml est mal écrit."


def test_erreur_de_fichier_propre_a_l_application_inchangee():
    """Une classe d'erreur de l'application, meme derivee d'OSError, porte
    deja son message en francais : il ne faut pas le reecrire."""
    class DossierInutilisable(OSError):
        pass
    assert erreur_en_clair(DossierInutilisable("Dossier inutilisable.")) \
        == "Dossier inutilisable."


def test_erreur_sans_message():
    assert erreur_en_clair(ValueError()) == \
        "Erreur inattendue de l'application (ValueError)."


# ---------- le code ne recopie plus l'erreur brute ----------

def _recopies_brutes(fichier: Path) -> list[int]:
    """Lignes ou une erreur est recopiee telle quelle — f"{exc}",
    f"{exc or ...}" ou str(exc) — ailleurs que dans un print().

    « Une erreur » : le nom d'un « except ... as x », ou une variable
    nommee comme on nomme les erreurs (e, exc, err) — une fonction qui
    recoit l'erreur en parametre, par exemple."""
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    noms = {"e", "exc", "err"}
    noms.update(n.name for n in ast.walk(arbre)
                if isinstance(n, ast.ExceptHandler) and n.name)
    dans_print = set()
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
                and noeud.func.id == "print"):
            dans_print.update(id(n) for n in ast.walk(noeud))

    def nomme_une_erreur(noeud) -> bool:
        return isinstance(noeud, ast.Name) and noeud.id in noms

    lignes = []
    for noeud in ast.walk(arbre):
        if id(noeud) in dans_print:
            continue
        if isinstance(noeud, ast.FormattedValue):
            # {exc}, mais aussi {exc or type(exc).__name__}
            valeur = noeud.value
            if nomme_une_erreur(valeur) or (
                    isinstance(valeur, ast.BoolOp)
                    and any(nomme_une_erreur(v) for v in valeur.values)):
                lignes.append(noeud.lineno)
        elif (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
              and noeud.func.id == "str" and len(noeud.args) == 1
              and nomme_une_erreur(noeud.args[0])):
            lignes.append(noeud.lineno)
    return sorted(lignes)


FICHIERS_A_L_ECRAN = sorted(
    [RACINE / "app_desktop.py", RACINE / "run.py",
     RACINE / "fenetre_reglages.py", *(RACINE / "views").glob("*.py")])


@pytest.mark.parametrize("fichier", FICHIERS_A_L_ECRAN,
                         ids=lambda f: f.name)
def test_aucune_erreur_recopiee_brute(fichier):
    assert _recopies_brutes(fichier) == []
