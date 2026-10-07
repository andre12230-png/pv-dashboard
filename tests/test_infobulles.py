"""Infobulles claires, quel que soit le réglage de Windows (charte, section 6).

Qt dessine les infobulles avec une palette à part (QToolTip.palette()),
prise au système : sur le PC de l'auteur, fond #3C3C3C et texte #D4D4D4.
app.setPalette() ne la touche pas : appliquer_style() doit la poser aussi,
comme Pécule et Recharges VE (07/10/2026).
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QColor, QPalette  # noqa: E402
from PySide6.QtWidgets import QApplication, QToolTip  # noqa: E402

from gui_theme import appliquer_style  # noqa: E402


def test_les_infobulles_restent_claires_sur_un_windows_sombre():
    app = QApplication.instance() or QApplication([])
    avant = QToolTip.palette()
    # Ce que donne un Windows réglé en mode sombre.
    sombre = QPalette(avant)
    sombre.setColor(QPalette.ToolTipBase, QColor("#3C3C3C"))
    sombre.setColor(QPalette.ToolTipText, QColor("#D4D4D4"))
    QToolTip.setPalette(sombre)
    try:
        appliquer_style(app)
        bulle = QToolTip.palette()
        assert bulle.color(QPalette.ToolTipBase).name().upper() == "#FFFFDC"
        assert bulle.color(QPalette.ToolTipText).name().upper() == "#000000"
    finally:
        QToolTip.setPalette(avant)
