"""Sauvegarde des donnees sur un support externe (cle USB, disque).

Les sauvegardes automatiques (backups/) restent sur le meme disque que les
donnees : si ce disque lache, ou si le PC est vole, tout part ensemble. Ce
module copie les fichiers de donnees vers un dossier choisi par
l'utilisateur, dans un sous-dossier date, puis VERIFIE chaque copie octet
pour octet avant d'annoncer que c'est fait.

Il ne depend pas de l'interface : la fenetre choisit le dossier, ce module
fait la copie. Il se teste donc sans ouvrir de fenetre, et peut etre repris
tel quel par une autre application.
"""
from __future__ import annotations

import hashlib
import shutil
from datetime import datetime
from pathlib import Path


class SauvegardeImpossible(Exception):
    """Echec explique en francais, a montrer tel quel a l'utilisateur."""


def _empreinte(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def texte_lisezmoi(nom_appli: str, version: str, quand: datetime,
                   fichiers: list[str], dossier_donnees: Path) -> str:
    """Le mode d'emploi depose a cote des copies : sans lui, une sauvegarde
    retrouvee dans deux ans sur une cle ne dit pas quoi en faire. C'est un
    texte a lire, pas du code : il est accentue."""
    liste = "\n".join(f"  - {nom}" for nom in fichiers)
    return (
        f"Sauvegarde faite par {nom_appli} {version}\n"
        f"le {quand:%d/%m/%Y à %H:%M}.\n"
        "\n"
        "Fichiers sauvegardés :\n"
        f"{liste}\n"
        "\n"
        "POUR LA REMETTRE EN SERVICE\n"
        "\n"
        f"1. Fermez {nom_appli}.\n"
        "2. Ouvrez le dossier de vos données. Sur l'ordinateur où cette\n"
        "   sauvegarde a été faite, c'était :\n"
        f"   {dossier_donnees}\n"
        "3. Recopiez-y les fichiers ci-dessus, en acceptant de remplacer\n"
        "   ceux qui s'y trouvent.\n"
        f"4. Relancez {nom_appli}.\n"
    )


def sauvegarder(fichiers: list[Path | None], destination: Path,
                dossier_donnees: Path, nom_appli: str, version: str,
                maintenant: datetime | None = None) -> tuple[Path, list[str]]:
    """Copie les fichiers existants dans un sous-dossier date de
    `destination`, et verifie chaque copie.

    Renvoie le dossier cree et la liste des fichiers copies. Leve
    SauvegardeImpossible, avec un message comprehensible, si la sauvegarde
    ne peut pas etre faite ou ne peut pas etre garantie.
    """
    quand = maintenant or datetime.now()
    destination = Path(destination)
    if not destination.is_dir():
        raise SauvegardeImpossible(
            "Le dossier choisi est introuvable. La clé USB a-t-elle été "
            "retirée ?")
    # Sauvegarder dans le dossier des donnees lui-meme ne protege de rien.
    if destination.resolve().is_relative_to(Path(dossier_donnees).resolve()):
        raise SauvegardeImpossible(
            "Ce dossier est celui de vos données : une copie à cet endroit "
            "disparaîtrait avec elles. Choisissez une clé USB ou un disque "
            "externe.")

    presents = [Path(f) for f in fichiers if f and Path(f).is_file()]
    if not presents:
        raise SauvegardeImpossible(
            "Il n'y a encore aucune donnée à sauvegarder.")

    base = f"Sauvegarde {nom_appli} {quand:%Y-%m-%d %Hh%M}"
    cible = destination / base
    n = 2
    while cible.exists():            # deux sauvegardes dans la meme minute
        cible = destination / f"{base} ({n})"
        n += 1

    noms = [f.name for f in presents]
    try:
        cible.mkdir(parents=True)
        for f in presents:
            shutil.copy2(f, cible / f.name)
        (cible / "LISEZMOI.txt").write_text(
            texte_lisezmoi(nom_appli, version, quand, noms, dossier_donnees),
            encoding="utf-8")
    except OSError as e:
        raise SauvegardeImpossible(
            f"La copie a échoué ({e.strerror or e}). La clé est-elle pleine, "
            "retirée ou protégée en écriture ?") from e

    # Une copie n'est une sauvegarde que si elle est identique a l'original.
    for f in presents:
        if _empreinte(f) != _empreinte(cible / f.name):
            raise SauvegardeImpossible(
                f"La copie de {f.name} ne correspond pas à l'original : ne "
                "comptez pas sur cette sauvegarde, et réessayez sur un autre "
                "support.")
    return cible, noms
