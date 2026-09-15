"""Configuration commune aux tests.

Qt doit tourner sans ecran : les tests de vue construisent de vrais widgets,
mais rien ne doit s'afficher ni attendre un clic. La variable doit etre posee
AVANT le premier import de PySide6, d'ou sa place ici (conftest est importe
avant les fichiers de test).
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def pytest_sessionfinish(session, exitstatus):
    """Detruit les fenetres Qt restantes AVANT que Python ne s'arrete.

    Les tests de vue laissent des onglets en vie. Laisses a la sortie de
    Python, ils sont detruits en vrac, parfois apres Qt lui-meme : la suite
    plantait alors a la fermeture (code 0xC0000374) alors que tous les tests
    avaient reussi. Ici, Qt tourne encore et chaque objet part dans l'ordre.
    """
    try:
        from PySide6.QtCore import QCoreApplication, QEvent
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return
    if QApplication.instance() is None:
        return
    for fenetre in QApplication.topLevelWidgets():
        fenetre.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
