"""« Votre avis » : le questionnaire en ligne, et l'unique invitation a le
remplir.

Repris de Pecule. Les utilisateurs ne remontent pas d'eux-memes ce qui
coince : sans compte GitHub, ils n'avaient aucun moyen de le faire. Le
questionnaire n'en demande aucun. L'application ne fait que l'ouvrir dans le
navigateur ; ce qui est envoye, c'est l'utilisateur qui l'ecrit et qui
l'envoie. Elle-meme ne contacte aucun serveur.

Les deux dates de l'invitation sont gardees dans les preferences de
l'application (QSettings, comme le theme), pas dans les donnees.
"""
from __future__ import annotations

import platform
import sys
from datetime import date

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

# Questionnaire en ligne (Microsoft Forms « Gestion Photovoltaique — votre
# avis », cree le 15/09/2026 dans le compte de l'auteur). Changer le lien =
# changer cette constante et republier.
FORMULAIRE_AVIS_URL = "https://forms.cloud.microsoft/r/2B6NBcZUhe"
TICKETS_GITHUB_URL = "https://github.com/andre12230-png/pv-dashboard/issues"

# Jours d'utilisation avant l'unique invitation a donner son avis.
DELAI_INVITATION_AVIS = 14

CLE_PREMIERE_UTILISATION = "avis/premiere_utilisation"
CLE_INVITATION_FAITE = "avis/invitation"

TITRE = "Votre avis sur Gestion Photovoltaïque"


def description_systeme(version: str) -> str:
    """Version de l'application et de Windows, a coller dans le
    questionnaire : c'est la premiere chose a savoir pour comprendre un
    probleme."""
    if sys.platform == "win32":
        systeme = f"Windows {platform.release()}"
    else:
        systeme = f"{platform.system()} {platform.release()}"
    return f"Gestion Photovoltaïque {version} — {systeme}"


def noter_premiere_utilisation(settings: QSettings, aujourdhui: date) -> None:
    """Retient le jour du premier lancement (sans l'ecraser ensuite). Pour
    qui utilisait deja l'application, c'est le jour de la mise a jour :
    l'invitation viendra donc deux semaines apres, pas le jour meme."""
    if not settings.value(CLE_PREMIERE_UTILISATION):
        settings.setValue(CLE_PREMIERE_UTILISATION, aujourdhui.isoformat())


def doit_inviter(settings: QSettings, aujourdhui: date,
                 a_des_releves: bool) -> bool:
    """Vrai une seule fois : apres deux semaines d'usage, si l'invitation n'a
    jamais ete faite et s'il y a des releves -- sans eux, l'utilisateur n'a
    pas encore d'avis a donner."""
    if not FORMULAIRE_AVIS_URL:
        return False
    if settings.value(CLE_INVITATION_FAITE):
        return False
    if not a_des_releves:
        return False
    try:
        debut = date.fromisoformat(str(settings.value(CLE_PREMIERE_UTILISATION)))
    except ValueError:
        return False
    return (aujourdhui - debut).days >= DELAI_INVITATION_AVIS


def ouvrir_questionnaire(version: str) -> str:
    """Copie la version dans le presse-papiers, puis ouvre le questionnaire
    dans le navigateur. Renvoie le texte copie."""
    texte = description_systeme(version)
    QGuiApplication.clipboard().setText(texte)
    QDesktopServices.openUrl(QUrl(FORMULAIRE_AVIS_URL))
    return texte


class AvisDialog(QDialog):
    """Fenetre ouverte par le bouton « Votre avis » du menu de gauche."""

    def __init__(self, version: str, parent=None):
        super().__init__(parent)
        self.version = version
        self.setWindowTitle(TITRE)
        self.setMinimumWidth(460)
        v = QVBoxLayout(self)
        v.setSpacing(12)

        intro = QLabel(
            "Un problème à l'installation, un relevé qui ne s'importe pas, "
            "une idée pour faire mieux ? Dites-le : c'est ainsi que "
            "l'application s'améliore.<br><br>"
            "Le questionnaire s'ouvre dans votre navigateur. Il prend deux "
            "minutes et aucune réponse n'est obligatoire. "
            "<b>N'y indiquez ni adresse ni numéro de compteur.</b>")
        intro.setTextFormat(Qt.RichText)
        intro.setWordWrap(True)
        v.addWidget(intro)

        version_lbl = QLabel(
            f"Votre version : <b>{description_systeme(version)}</b><br>"
            "<span style='color:#666'>Elle sera copiée pour vous : collez-la "
            "(Ctrl+V) dans la question « Votre version ».</span>")
        version_lbl.setTextFormat(Qt.RichText)
        version_lbl.setWordWrap(True)
        v.addWidget(version_lbl)

        # Confirmation affichee une fois le questionnaire ouvert.
        self.confirmation = QLabel("")
        self.confirmation.setStyleSheet("color:#2E7D32")
        self.confirmation.setWordWrap(True)
        self.confirmation.hide()
        v.addWidget(self.confirmation)

        github = QLabel(
            "Vous avez un compte GitHub ? Vous pouvez aussi "
            f"<a href='{TICKETS_GITHUB_URL}'>ouvrir un ticket</a>.")
        github.setTextFormat(Qt.RichText)
        github.setOpenExternalLinks(True)
        github.setStyleSheet("color:#666")
        v.addWidget(github)

        boutons = QHBoxLayout()
        boutons.addStretch()
        self.btn_ouvrir = QPushButton("Ouvrir le questionnaire")
        self.btn_ouvrir.setDefault(True)
        self.btn_ouvrir.clicked.connect(self.on_ouvrir)
        # Tant que le lien n'est pas renseigne, le bouton ne ferait rien.
        self.btn_ouvrir.setEnabled(bool(FORMULAIRE_AVIS_URL))
        boutons.addWidget(self.btn_ouvrir)
        fermer = QPushButton("Fermer")
        fermer.clicked.connect(self.accept)
        boutons.addWidget(fermer)
        v.addLayout(boutons)

    def on_ouvrir(self) -> None:
        ouvrir_questionnaire(self.version)
        self.confirmation.setText(
            "✓ Questionnaire ouvert dans votre navigateur, version copiée. "
            "Merci !")
        self.confirmation.show()


def inviter(parent, settings: QSettings, aujourdhui: date, version: str) -> None:
    """L'unique invitation. Elle est notee comme faite quelle que soit la
    reponse : un « Non merci » ne doit jamais revenir. Le bouton du menu
    reste la pour qui changerait d'avis."""
    settings.setValue(CLE_INVITATION_FAITE, aujourdhui.isoformat())
    boite = QMessageBox(parent)
    boite.setWindowTitle(TITRE)
    boite.setTextFormat(Qt.RichText)
    boite.setText(
        "Vous utilisez l'application depuis deux semaines.<br><br>"
        "Qu'est-ce qui marche, qu'est-ce qui coince ? Deux minutes de "
        "questionnaire aident à l'améliorer.<br><br>"
        "<span style='color:#666'>Cette question ne vous sera plus posée. "
        "Le bouton « Votre avis » du menu de gauche reste à votre "
        "disposition.</span>")
    oui = boite.addButton("Donner mon avis…", QMessageBox.AcceptRole)
    boite.addButton("Non merci", QMessageBox.RejectRole)
    boite.exec()
    if boite.clickedButton() is oui:
        AvisDialog(version, parent).exec()
