"""« Mise à jour » : savoir s'il existe une version plus récente, sans
aucun acces reseau.

Repris de Pecule. L'application ne se connecte jamais a Internet : elle ne
peut donc pas decouvrir seule qu'une nouvelle version est sortie. Ce bouton
affiche la version installee et ouvre, a la demande, la page de la derniere
version ou l'installeur dans le navigateur : c'est l'utilisateur qui compare
les numeros, et rien ne part de l'application.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

# La page de la derniere version publiee, et son installeur. Le nom de
# l'installeur est fixe (faire_installeur.py) : ce lien vise donc toujours
# la version la plus recente.
PAGE_VERSIONS_URL = "https://github.com/andre12230-png/pv-dashboard/releases/latest"
INSTALLEUR_URL = ("https://github.com/andre12230-png/pv-dashboard/releases/"
                  "latest/download/pv-dashboard-Setup.exe")


class MiseAJourDialog(QDialog):
    """Fenetre ouverte par le bouton « Mise à jour » du menu de gauche."""

    def __init__(self, version: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Rechercher une mise à jour")
        self.setMinimumWidth(460)
        v = QVBoxLayout(self)
        v.setSpacing(12)

        self.version = QLabel(
            f"Vous utilisez <b>Gestion Photovoltaïque {version}</b>.")
        self.version.setTextFormat(Qt.RichText)
        v.addWidget(self.version)

        explication = QLabel(
            "L'application ne se connecte jamais à Internet : elle ne peut "
            "donc pas savoir toute seule qu'une nouvelle version existe."
            "<br><br>"
            "<b>Voir les nouveautés</b> ouvre dans votre navigateur la page de "
            "la dernière version. Si son numéro est plus grand que le vôtre, "
            "une mise à jour vous attend.<br><br>"
            "<b>Télécharger l'installeur</b> récupère directement la dernière "
            "version. Fermez l'application avant de le lancer : vos données "
            "ne sont pas touchées.")
        explication.setTextFormat(Qt.RichText)
        explication.setWordWrap(True)
        v.addWidget(explication)

        # Confirmation affichee une fois le navigateur sollicite.
        self.confirmation = QLabel("")
        self.confirmation.setStyleSheet("color:#2E7D32")
        self.confirmation.setWordWrap(True)
        self.confirmation.hide()
        v.addWidget(self.confirmation)

        boutons = QHBoxLayout()
        boutons.addStretch()
        self.btn_nouveautes = QPushButton("🌐 Voir les nouveautés")
        self.btn_nouveautes.setDefault(True)
        self.btn_nouveautes.clicked.connect(
            lambda: self._ouvrir(PAGE_VERSIONS_URL,
                                 "✓ Page des nouveautés ouverte dans votre "
                                 "navigateur."))
        boutons.addWidget(self.btn_nouveautes)
        self.btn_installeur = QPushButton("⬇ Télécharger l'installeur")
        self.btn_installeur.clicked.connect(
            lambda: self._ouvrir(INSTALLEUR_URL,
                                 "✓ Téléchargement lancé dans votre "
                                 "navigateur. Fermez l'application avant de "
                                 "lancer l'installeur."))
        boutons.addWidget(self.btn_installeur)
        fermer = QPushButton("Fermer")
        fermer.clicked.connect(self.accept)
        boutons.addWidget(fermer)
        v.addLayout(boutons)

    def _ouvrir(self, adresse: str, message: str) -> None:
        """Confie l'adresse au navigateur : l'application, elle, ne
        telecharge rien."""
        QDesktopServices.openUrl(QUrl(adresse))
        self.confirmation.setText(message)
        self.confirmation.show()
