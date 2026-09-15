"""Fabrique l'archive portable : distribution/pv-dashboard-X.Y.Z-win64.zip.

La version « portable » de l'application, pour qui ne veut pas d'installeur :
on decompresse l'archive ou l'on veut et on lance pv-dashboard.exe. Elle
contient exactement ce que livre l'installeur (installeur/pv-dashboard.iss) :
le programme construit, les modeles de configuration et l'icone, plus le
README et la licence. Une fois lancee, l'application range ses donnees dans
%LOCALAPPDATA%\\pv-dashboard, comme apres une installation : voir
resolve_base_dir() dans app_desktop.py.

A lancer APRES la construction de l'exe (commande de Construire-Exe.bat) :

    py faire_archive.py

Le script relit l'archive produite pour s'assurer qu'aucune donnee
personnelle n'y est entree, et la supprime si c'etait le cas.
"""
import hashlib
import sys
import zipfile
from pathlib import Path

from faire_installeur import (
    CONSTRUIT,
    INTERDITS,
    RACINE,
    SORTIE,
    lire_version,
    verifier_modele,
)

# Dossier de l'application dans l'archive : une fois decompresse, il donne
# pv-dashboard\pv-dashboard.exe, comme apres une installation.
DOSSIER = "pv-dashboard"

# Joints au programme, comme dans l'installeur : les modeles sont recopies
# dans le dossier des donnees au premier lancement.
MODELES = ("config.yaml", "config-local.exemple.yaml", "pv-dashboard.ico")

# A la racine de l'archive, a cote du dossier de l'application.
DOCUMENTS = ("README.md", "LICENSE")

# Ce qui ne doit JAMAIS partir. config.yaml, lui, est le modele vierge :
# verifier_modele() s'assure qu'il ne porte aucune facture.
NOMS_INTERDITS = ("config-local.yaml", "Releves-pv.csv", "pv-dashboard.log")


def verifier_archive(archive: Path) -> list[str]:
    """Relit l'archive et renvoie la liste des fichiers suspects.

    Les bibliotheques embarquees par PyInstaller (_internal) apportent leurs
    propres fichiers d'exemple, .csv compris : le controle ne regarde pas
    la-dedans."""
    suspects = []
    with zipfile.ZipFile(archive) as z:
        for nom in z.namelist():
            if nom.startswith(f"{DOSSIER}/_internal/"):
                continue
            court = nom.rsplit("/", 1)[-1]
            if (court in NOMS_INTERDITS or court.lower().endswith(".csv")
                    or "backups/" in nom):
                suspects.append(nom)
    return suspects


def main() -> int:
    if not (CONSTRUIT / "pv-dashboard.exe").is_file():
        raise SystemExit(
            f"ARRET : {CONSTRUIT}\\pv-dashboard.exe n'existe pas.\n"
            "Construisez d'abord l'exe (commande de Construire-Exe.bat).")
    trouves = [nom for nom in INTERDITS if (CONSTRUIT / nom).exists()]
    if trouves:
        raise SystemExit(
            "ARRET : donnees personnelles dans le dossier construit : "
            + ", ".join(trouves))
    verifier_modele()

    version = lire_version()
    SORTIE.mkdir(exist_ok=True)
    archive = SORTIE / f"pv-dashboard-{version}-win64.zip"
    archive.unlink(missing_ok=True)

    n = 0
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for fichier in sorted(CONSTRUIT.rglob("*")):
            if fichier.is_file():
                z.write(fichier, Path(DOSSIER) / fichier.relative_to(CONSTRUIT))
                n += 1
        for nom in MODELES:
            z.write(RACINE / nom, f"{DOSSIER}/{nom}")
            n += 1
        for nom in DOCUMENTS:
            if (RACINE / nom).exists():
                z.write(RACINE / nom, nom)
                n += 1

    suspects = verifier_archive(archive)
    if suspects:
        archive.unlink(missing_ok=True)
        print("ARRET : des donnees personnelles ont failli partir :")
        for s in suspects:
            print(f"  {s}")
        print("L'archive a ete supprimee.")
        return 1

    empreinte = hashlib.sha256(archive.read_bytes()).hexdigest()
    print(f"Archive    : {archive}")
    print(f"Contenu    : {n} fichiers, aucune donnee personnelle")
    print(f"Taille     : {archive.stat().st_size / (1024 * 1024):.1f} Mo")
    print(f"SHA-256    : {empreinte}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
