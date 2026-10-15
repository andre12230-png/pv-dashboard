"""Fabrique l'installeur Windows : distribution/pv-dashboard-Setup-X.Y.Z.exe.

A lancer APRES la construction de l'exe (commande PyInstaller de
Construire-Exe.bat), qui produit dist/pv-dashboard/. Necessite Inno Setup 6
(gratuit) : winget install JRSoftware.InnoSetup

Ce script :

  * verifie qu'aucune donnee personnelle ne traine dans le dossier construit,
    ni dans le config.yaml livre comme modele ;
  * lance le compilateur d'Inno Setup sur installeur/pv-dashboard.iss en lui
    passant le numero de version (APP_VERSION de app_desktop.py) ;
  * affiche la taille et l'empreinte SHA-256 de l'installeur produit.

Une fois installee, l'application range ses donnees dans
%LOCALAPPDATA%\\pv-dashboard, pas a cote du programme : voir
resolve_base_dir() dans app_desktop.py.

    py faire_installeur.py
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

RACINE = Path(__file__).parent
CONSTRUIT = RACINE / "dist" / "pv-dashboard"
RECETTE = RACINE / "installeur" / "pv-dashboard.iss"
SORTIE = RACINE / "distribution"

# Donnees personnelles : si l'une d'elles se trouvait dans le dossier
# construit, a n'importe quelle profondeur, elle partirait chez un inconnu.
# La recette les exclut deja a la racine ; ce controle double la ceinture de
# bretelles et fouille aussi les sous-dossiers (_internal compris).
INTERDITS = ("config.yaml", "config-local.yaml", "Releves-pv.csv", "backups",
             "pv-dashboard.log")

# Cles de config.yaml qui portent des factures ou des chemins personnels :
# leur place est config-local.yaml, jamais le modele livre.
CLES_PERSONNELLES = ("injection_facturee", "conso_reseau_facturee",
                     "conso_reseau_recalee", "conso_reseau_douteuse",
                     "recharges_ve_json")


def lire_version() -> str:
    """APP_VERSION, lu dans le texte de app_desktop.py.

    Importer le module chargerait PySide6, pandas et matplotlib, et
    redirigerait la sortie vers le journal : bien trop pour un numero."""
    texte = (RACINE / "app_desktop.py").read_text(encoding="utf-8")
    trouve = re.search(r'^APP_VERSION = "([0-9.]+)"', texte, re.MULTILINE)
    if not trouve:
        raise SystemExit("ARRET : APP_VERSION introuvable dans app_desktop.py.")
    return trouve.group(1)


def chercher_donnees_personnelles(dossier: Path) -> list[str]:
    """Chemins (relatifs, avec des /) des fichiers ou dossiers interdits
    trouves dans `dossier`, a toutes les profondeurs, tries.

    La comparaison ignore majuscules et minuscules, comme Windows. Un dossier
    interdit (backups) est signale une seule fois, sans son contenu."""
    interdits = {nom.lower() for nom in INTERDITS}
    trouves = []
    for chemin in sorted(dossier.rglob("*")):
        relatif = chemin.relative_to(dossier).as_posix()
        # Deja couvert par un dossier interdit signale plus haut ?
        if any(relatif.startswith(t + "/") for t in trouves):
            continue
        if chemin.name.lower() in interdits:
            trouves.append(relatif)
    return sorted(trouves)


def verifier_dossier_construit() -> None:
    """Arrete tout si une donnee personnelle se trouve dans le dossier
    construit, a quelque profondeur que ce soit."""
    trouves = chercher_donnees_personnelles(CONSTRUIT)
    if trouves:
        raise SystemExit(
            "ARRET : donnees personnelles dans le dossier construit : "
            + ", ".join(trouves))


def verifier_modele() -> None:
    """Le config.yaml livre ne doit porter aucune facture."""
    with open(RACINE / "config.yaml", encoding="utf-8") as fh:
        sources = (yaml.safe_load(fh) or {}).get("sources") or {}
    presentes = [cle for cle in CLES_PERSONNELLES if cle in sources]
    if presentes:
        raise SystemExit(
            "ARRET : config.yaml porte des donnees personnelles "
            f"({', '.join(presentes)}). Leur place est config-local.yaml.")


def trouver_iscc() -> str:
    """Cherche le compilateur d'Inno Setup aux endroits habituels.

    La variable d'environnement ISCC permet d'en imposer un autre."""
    candidats = [os.environ.get("ISCC", "")]
    for base in (os.environ.get("LOCALAPPDATA", "") + r"\Programs",
                 os.environ.get("ProgramFiles(x86)", ""),
                 os.environ.get("ProgramFiles", "")):
        candidats.append(os.path.join(base, "Inno Setup 6", "ISCC.exe"))
    for chemin in candidats:
        if chemin and os.path.isfile(chemin):
            return chemin
    raise SystemExit(
        "ARRET : Inno Setup 6 est introuvable.\n"
        "Installez-le avec : winget install JRSoftware.InnoSetup")


def main() -> int:
    if not (CONSTRUIT / "pv-dashboard.exe").is_file():
        raise SystemExit(
            f"ARRET : {CONSTRUIT}\\pv-dashboard.exe n'existe pas.\n"
            "Construisez d'abord l'exe (commande de Construire-Exe.bat).")

    version = lire_version()
    print(f"Version : {version}")

    verifier_dossier_construit()
    verifier_modele()

    iscc = trouver_iscc()
    print(f"Inno Setup : {iscc}")
    # /Q : n'affiche que les erreurs. /D : definit AppVersion pour la recette.
    resultat = subprocess.run([iscc, "/Q", f"/DAppVersion={version}", str(RECETTE)])
    if resultat.returncode != 0:
        raise SystemExit("ARRET : la compilation de l'installeur a echoue.")

    cible = SORTIE / f"pv-dashboard-Setup-{version}.exe"
    if not cible.is_file():
        raise SystemExit(f"ARRET : {cible} n'a pas ete produit.")
    # Copie au nom FIXE, sans numero : c'est elle que vise le bouton
    # « Telecharger » de la page de presentation et du README
    # (.../releases/latest/download/pv-dashboard-Setup.exe). Un nom numerote
    # casserait ce lien a chaque version.
    fixe = SORTIE / "pv-dashboard-Setup.exe"
    shutil.copy2(cible, fixe)
    empreinte = hashlib.sha256(cible.read_bytes()).hexdigest()
    print()
    print(f"Installeur : {cible}")
    print(f"Nom fixe   : {fixe} (celui a joindre a la release)")
    print(f"Taille     : {cible.stat().st_size / (1024 * 1024):.1f} Mo")
    print(f"SHA-256    : {empreinte}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
