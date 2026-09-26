"""Les erreurs techniques dites en français, pour les messages à l'écran.

Module COMMUN aux trois applications (Pécule, Photovoltaïque, Recharges VE) :
le même fichier dans chacune. Une évolution se reporte dans les trois.

Les boîtes de message recopiaient tel quel le texte d'erreur de Python, en
anglais et en jargon : « Expecting value: line 1 column 1 (char 0) »,
« [Errno 13] Permission denied: ... », « database is locked ». Ce module le
remplace par une phrase simple, qui dit ce qui se passe et, si possible,
quoi faire (diagnostic du 26/09/2026).

Les erreurs rédigées par l'application elle-même passent sans changement,
même quand leur classe dérive d'OSError : seules les erreurs d'origine de
Python sont traduites.

Sans Qt ni autre dépendance, pour se tester sans fenêtre.
"""

import errno
import json
from pathlib import Path

# Codes d'erreur de Windows qui veulent dire « disque plein ».
_DISQUE_PLEIN_WINDOWS = (39, 112)

# Erreurs qui trahissent un défaut du programme, pas un problème de fichier :
# on le dit, et on garde leur nom technique pour pouvoir les identifier.
_ERREURS_DE_PROGRAMME = (AttributeError, IndexError, NameError, TypeError,
                         ZeroDivisionError, AssertionError)


def erreur_en_clair(e: BaseException) -> str:
    """Une phrase en français qui explique l'erreur `e`."""
    nom = type(e).__name__
    # JSONDecodeError et UnicodeDecodeError sont aussi des ValueError :
    # elles doivent être reconnues avant le cas général.
    if isinstance(e, json.JSONDecodeError):
        return (f"Le contenu est abîmé à la ligne {e.lineno}, colonne "
                f"{e.colno}.")
    if isinstance(e, UnicodeDecodeError):
        return ("Le fichier contient des caractères mal codés : il a sans "
                "doute été réenregistré par un autre programme, dans un "
                "autre encodage.")
    # Reconnues par leur nom : inutile de charger zipfile, sqlite3 ou pandas
    # dans une application qui ne s'en sert pas.
    if nom == "BadZipFile":
        return ("Ce fichier n'est pas un classeur Excel valide (.xlsx) : il "
                "est peut-être abîmé, ou c'est un fichier d'un autre format "
                "renommé.")
    if type(e).__module__ == "sqlite3":
        return _erreur_de_base(e)
    if nom == "EmptyDataError":
        return "Le fichier est vide : il ne contient aucune colonne à lire."
    if nom == "ParserError":
        return ("Le fichier n'a pas pu être découpé en colonnes : il est "
                "peut-être abîmé, ou d'un autre format que celui attendu.")
    if isinstance(e, OSError) and type(e).__module__ == "builtins":
        return _erreur_de_fichier(e)
    if isinstance(e, KeyError):
        cle = e.args[0] if e.args else "?"
        return (f"Une information attendue manque : « {cle} » (une colonne "
                "d'un fichier importé, ou un réglage).")
    if isinstance(e, _ERREURS_DE_PROGRAMME):
        return (f"Erreur inattendue de l'application (détail technique : "
                f"{nom} : {e}).")
    return str(e) or f"Erreur inattendue de l'application ({nom})."


def _erreur_de_fichier(e: OSError) -> str:
    """Fichier introuvable, verrouillé, disque plein... en clair."""
    nom = f" « {Path(e.filename).name} »" if e.filename else ""
    if isinstance(e, FileNotFoundError):
        return f"Fichier{nom} introuvable."
    if isinstance(e, PermissionError):
        # Sous Windows, c'est aussi l'erreur d'un fichier ouvert ailleurs.
        return (f"Accès refusé au fichier{nom} : il est peut-être ouvert dans "
                "un autre programme (Excel, Bloc-notes…), ou le dossier est "
                "protégé en écriture.")
    if (e.errno == errno.ENOSPC
            or getattr(e, "winerror", None) in _DISQUE_PLEIN_WINDOWS):
        return "Le disque est plein : libérez de la place, puis réessayez."
    # Cas rare : on garde le détail d'origine, utile pour un dépannage,
    # mais derrière une phrase en français.
    detail = e.strerror or str(e)
    return (f"Le fichier{nom} n'a pas pu être lu ou écrit (détail technique : "
            f"{detail}).")


def _erreur_de_base(e: BaseException) -> str:
    """Les erreurs de la base de données SQLite, en clair."""
    texte = str(e).lower()
    if "locked" in texte or "busy" in texte:
        return ("La base de données est occupée par un autre programme (une "
                "autre fenêtre de l'application, une synchronisation "
                "OneDrive…) : réessayez dans un instant.")
    if "malformed" in texte or "not a database" in texte:
        return ("La base de données est abîmée, ou ce fichier n'en est pas "
                "une : restaurez une sauvegarde.")
    if "readonly" in texte or "read-only" in texte:
        return ("La base de données est en lecture seule : vérifiez que le "
                "dossier des données est accessible en écriture.")
    if "disk" in texte or "i/o" in texte or "full" in texte:
        return ("Le disque n'a pas pu être lu ou écrit (disque plein, clé "
                "retirée ?).")
    return f"Erreur de la base de données (détail technique : {e})."
