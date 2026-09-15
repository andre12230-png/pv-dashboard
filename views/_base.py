"""Classe de base : chaque vue concrete implemente populate(period)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from app_data import AppData
from gui_widgets import Card


class BaseView(QWidget):
    """Classe de base : chaque vue implemente `populate(df, period)`."""

    # False dans les vues qui ignorent le selecteur de periode global :
    # MainWindow grise alors le menu deroulant quand la vue est affichee.
    utilise_periode: bool = True

    def __init__(self, data: AppData, theme: dict, parent=None):
        super().__init__(parent)
        self.data = data
        self.theme = theme
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        # Scroll area pour les vues longues
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.container = QWidget()
        self.layout_inner = QVBoxLayout(self.container)
        self.layout_inner.setContentsMargins(20, 18, 20, 20)
        self.layout_inner.setSpacing(16)
        self.scroll.setWidget(self.container)
        outer.addWidget(self.scroll)

    def _clear(self) -> None:
        while self.layout_inner.count():
            item = self.layout_inner.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _empty_card(self, message: str = "Aucune donnée sur cette période.") -> QFrame:
        """Carte 'rien a afficher', commune a toutes les vues."""
        card = Card()
        v = QVBoxLayout(card)
        v.setContentsMargins(20, 30, 20, 30)
        lbl = QLabel(message)
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"color: {self.theme['text_muted']}; padding: 20px;")
        v.addWidget(lbl)
        return card

    def set_theme(self, theme: dict) -> None:
        self.theme = theme

    def refresh(self, period: str) -> None:
        self._clear()
        self.populate(period)

    def populate(self, period: str) -> None:  # a override
        raise NotImplementedError
