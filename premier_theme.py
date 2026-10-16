"""Choix Clair / Sombre au tout premier lancement (16/10/2026).

Demande de l'auteur, la meme dans les trois applications : le mode sombre ne
se trouvait que dans Parametres › Apparence, ou un nouvel utilisateur ne le
cherchait pas. Au premier lancement, avant le chargement, l'application
demande donc « Clair ou Sombre ? ».

La question vient AVANT d'importer app_desktop parce que les vues prennent
leurs couleurs a l'import (voir gui_theme.choisir_theme) : posee apres, elle
obligerait a redemarrer pour voir le choix.

Elle n'est posee qu'une fois, et seulement a un vrai nouvel utilisateur :
- aucun theme encore choisi dans les preferences ;
- pas de config.yaml dans le dossier des donnees. Quelqu'un qui met a jour
  une ancienne version a deja le sien : on ne le derange pas, il garde le
  clair et peut changer dans Parametres.

Ce module n'importe que PySide6 et gui_theme : il tourne avant les vues.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from gui_theme import CLE_THEME, appliquer_style

THEMES = ("clair", "sombre")


def est_premier_lancement(reglages, dossier: Path) -> bool:
    """Vrai si aucun theme n'a encore ete choisi ET si le dossier des
    donnees n'a pas de config.yaml. Une preference abimee (revenue en
    liste, audit du 13/10/2026) compte comme absente."""
    valeur = reglages.value(CLE_THEME)
    if isinstance(valeur, str) and valeur in THEMES:
        return False
    return not (Path(dossier) / "config.yaml").exists()


def boite_du_choix(parent=None):
    """La petite fenetre de la question, et ses deux boutons.
    Rend (boite, bouton_clair, bouton_sombre)."""
    boite = QMessageBox(parent)
    boite.setWindowTitle("Gestion Photovoltaïque — Apparence")
    boite.setIcon(QMessageBox.Icon.Question)
    boite.setText(
        "Comment préférez-vous voir l'application ?\n\n"
        "• Clair : fond crème, texte noir.\n"
        "• Sombre : fond brun très foncé, texte clair, plus reposant le "
        "soir.\n\n"
        "Vous pourrez changer d'avis à tout moment dans "
        # Espaces insecables autour de « › » : le chemin ne se coupe pas.
        "Paramètres › Apparence.")
    clair = boite.addButton("Clair", QMessageBox.ButtonRole.AcceptRole)
    sombre = boite.addButton("Sombre", QMessageBox.ButtonRole.AcceptRole)
    # Entree ou la croix de fermeture : le clair, theme de reference.
    boite.setDefaultButton(clair)
    boite.setEscapeButton(clair)
    return boite, clair, sombre


def demander_a_l_ecran() -> str:
    """Montre la question et rend « clair » ou « sombre ». L'application
    Qt existe deja (run.main) ; elle porte le style clair, celui de la
    session tant que rien n'est choisi."""
    appliquer_style(QApplication.instance())
    boite, _clair, sombre = boite_du_choix()
    boite.exec()
    return "sombre" if boite.clickedButton() is sombre else "clair"


def demander_au_premier_lancement(reglages, dossier: Path,
                                  demander=demander_a_l_ecran) -> str | None:
    """Pose la question si c'est le premier lancement, et retient la
    reponse dans les preferences pour ne plus la reposer. Rend le theme
    choisi, ou None si rien n'a ete demande.

    `demander` : remplaçable par les tests."""
    if not est_premier_lancement(reglages, dossier):
        return None
    nom = demander()
    reglages.setValue(CLE_THEME, nom)
    reglages.sync()
    return nom
