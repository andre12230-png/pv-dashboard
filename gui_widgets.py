"""
Composants PySide6 reutilisables pour l'appli desktop PV.
"""

from __future__ import annotations

from typing import Iterable

import matplotlib
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _apply_props(widget: QWidget, **props) -> None:
    for k, v in props.items():
        widget.setProperty(k, v)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def police_tabulaire(taille_pt: int = 10, gras: bool = False) -> QFont:
    """Police dont tous les chiffres ont la meme largeur.

    Sans ca, un "1" est plus etroit qu'un "8" : dans une colonne de nombres
    alignes a droite, les virgules ne tombent pas les unes sous les autres et
    la colonne parait de travers. "tnum" est la fonctionnalite OpenType qui
    force cette largeur fixe (l'equivalent du font-feature-settings du web).
    """
    f = QFont("Segoe UI")
    f.setStyleHint(QFont.SansSerif)
    f.setPointSize(taille_pt)
    f.setBold(gras)
    # setFeature n'existe qu'a partir de Qt 6.7 et attend un QFont.Tag ; sans
    # lui l'affichage reste correct, seulement un peu moins bien aligne.
    if hasattr(f, "setFeature") and hasattr(QFont, "Tag"):
        f.setFeature(QFont.Tag.fromString("tnum"), 1)
    return f


def colored_label(text: str, color: str, weight: int = 700, size: int = 13) -> QLabel:
    lbl = QLabel(text)
    f = QFont()
    f.setPointSize(size - 3)
    f.setWeight(QFont.Weight(weight))
    lbl.setFont(f)
    lbl.setStyleSheet(f"color: {color}; background: transparent;")
    return lbl


# ----------------------------------------------------------------------
# Cartes
# ----------------------------------------------------------------------

class KpiCard(QFrame):
    """Carte KPI : libelle, grande valeur, sous-texte.
    Variant : credit/debit/primary/warm/info/neutral."""

    def __init__(self, label: str, value: str, sub: str = "", variant: str = "neutral",
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("KpiCard")
        _apply_props(self, role="kpi", variant=variant)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(90)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(4)

        self.label = QLabel(label.upper())
        self.label.setObjectName("KpiLabel")
        self.value = QLabel(value)
        self.value.setObjectName("KpiValue")
        self.sub = QLabel(sub)
        self.sub.setObjectName("KpiSub")
        self.sub.setVisible(bool(sub))

        layout.addWidget(self.label)
        layout.addWidget(self.value)
        layout.addWidget(self.sub)
        layout.addStretch(1)


class AccountCard(QFrame):
    """Carte 'compte bancaire' : nom + type + solde + tendance + pastille."""

    def __init__(self, name: str, type_label: str, balance: str, trend: str,
                 trend_color: str, icon_text: str, icon_color: str,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("AccountCard")
        _apply_props(self, role="account")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(140)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(6)

        # Tete : nom/type a gauche, icone a droite
        head = QHBoxLayout()
        head.setSpacing(8)
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        name_l = QLabel(name)
        name_l.setObjectName("AccountName")
        type_l = QLabel(type_label)
        type_l.setObjectName("AccountType")
        text_col.addWidget(name_l)
        text_col.addWidget(type_l)
        head.addLayout(text_col, stretch=1)

        icon = QLabel(icon_text)
        icon.setObjectName("AccountIcon")
        icon.setAlignment(Qt.AlignCenter)
        # 20 px : la pastille porte un emoji (Synthese financiere, 14/09/2026),
        # plus deux lettres ; a la taille par defaut il sortait minuscule.
        icon.setStyleSheet(
            f"background: {icon_color}; color: white; "
            f"font-weight: 700; font-size: 20px; border-radius: 8px;"
        )
        icon.setFixedSize(38, 38)
        head.addWidget(icon, alignment=Qt.AlignTop)

        outer.addLayout(head)

        bal = QLabel(balance)
        bal.setObjectName("AccountBalance")
        bal.setStyleSheet(f"color: {trend_color}; background: transparent;")
        outer.addWidget(bal)

        trend_l = QLabel(trend)
        trend_l.setObjectName("AccountTrend")
        outer.addWidget(trend_l)
        outer.addStretch(1)


class Card(QFrame):
    """Carte conteneur generique. Posez un layout dedans."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setProperty("class", "Card")


class SectionTitle(QWidget):
    """Petit bandeau 'TITRE' + sous-texte optionnel."""

    def __init__(self, title: str, sub: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 4, 0, 8)
        v.setSpacing(2)
        t = QLabel(title.upper())
        t.setObjectName("SectionTitle")
        v.addWidget(t)
        if sub:
            s = QLabel(sub)
            s.setObjectName("SectionSub")
            v.addWidget(s)


class Tag(QLabel):
    """Petit badge texte coloré."""

    def __init__(self, text: str, variant: str = "info", parent: QWidget | None = None):
        super().__init__(text, parent)
        _apply_props(self, role="tag", variant=variant)
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)


class BarMeter(QWidget):
    """Barre horizontale fine, dessinee a la main.

    Pourquoi pas matplotlib : une barre de proportion n'est pas un graphique.
    Un QWidget qui se peint lui-meme tient en trente lignes, s'affiche
    instantanement et suit la largeur de sa carte, la ou une figure
    matplotlib apporterait des axes, des marges et un temps de rendu pour
    dessiner... un rectangle.

    `ratio` est borne a [0, 1] : un taux superieur a 100 % remplirait la barre
    au-dela de sa propre largeur.
    """

    def __init__(self, ratio: float, color: str, track_color: str,
                 hauteur: int = 8, parent: QWidget | None = None):
        super().__init__(parent)
        self.ratio = max(0.0, min(1.0, float(ratio)))
        self.color = QColor(color)
        self.track_color = QColor(track_color)
        self.setFixedHeight(hauteur)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, event) -> None:  # noqa: N802 (nom impose par Qt)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        h = float(self.height())
        rayon = h / 2.0  # coins entierement arrondis : 4 px si la barre fait 8 px

        # Rail de fond : rappelle l'echelle, donc ce qui reste a atteindre.
        p.setBrush(self.track_color)
        p.drawRoundedRect(QRectF(0, 0, float(self.width()), h), rayon, rayon)

        # Partie remplie. En dessous de la hauteur de la barre, un rectangle
        # arrondi devient une pastille illisible : on impose ce minimum.
        largeur = self.ratio * float(self.width())
        if largeur > 0:
            p.setBrush(self.color)
            p.drawRoundedRect(QRectF(0, 0, max(largeur, h), h), rayon, rayon)
        p.end()


def _texte_lisible_sur(fond: QColor) -> QColor:
    """Encre sombre sur une couleur claire, blanche sur une couleur foncee."""
    clarte = 0.299 * fond.red() + 0.587 * fond.green() + 0.114 * fond.blue()
    return QColor("#1c1917") if clarte > 150 else QColor("#ffffff")


class Jauge(QWidget):
    """Jauge ronde : un anneau rempli selon `ratio`, le pourcentage au centre.

    Dessinee a la main, comme BarMeter : un anneau n'est pas un graphique, et
    matplotlib apporterait axes et marges pour un simple arc de cercle.
    """

    def __init__(self, ratio: float, color: str, track_color: str,
                 text_color: str, legende: str = "", cote: int = 124,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.ratio = max(0.0, min(1.0, float(ratio)))
        self.color = QColor(color)
        self.track_color = QColor(track_color)
        self.text_color = QColor(text_color)
        self.legende = legende
        self.setFixedSize(cote, cote)

    def paintEvent(self, event) -> None:  # noqa: N802 (nom impose par Qt)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        epaisseur = 12.0
        marge = epaisseur / 2 + 1
        zone = QRectF(marge, marge, self.width() - 2 * marge,
                      self.height() - 2 * marge)
        stylo = QPen(self.track_color, epaisseur)
        p.setPen(stylo)
        p.drawArc(zone, 0, 360 * 16)
        if self.ratio > 0:
            stylo = QPen(self.color, epaisseur)
            stylo.setCapStyle(Qt.RoundCap)
            p.setPen(stylo)
            # Qt compte les angles en seiziemes de degre, depuis 3 h, dans le
            # sens inverse des aiguilles : on part de midi et on tourne a droite.
            p.drawArc(zone, 90 * 16, int(-self.ratio * 360 * 16))
        # Le pourcentage, puis sa legende juste dessous.
        p.setPen(self.text_color)
        f = police_tabulaire(gras=True)
        f.setPixelSize(26)
        p.setFont(f)
        haut = QRectF(0, self.height() / 2 - 22, self.width(), 30)
        p.drawText(haut, Qt.AlignCenter, f"{round(self.ratio * 100)} %")
        if self.legende:
            f = QFont()
            f.setPixelSize(11)
            p.setFont(f)
            bas = QRectF(0, self.height() / 2 + 8, self.width(), 18)
            p.drawText(bas, Qt.AlignCenter, self.legende)
        p.end()


class BarreRepartition(QWidget):
    """Barre horizontale en plusieurs segments proportionnels, chacun portant
    son libelle. `segments` : liste de (libelle, valeur, couleur).

    Un segment trop etroit pour son texte le tait : le libelle complet reste
    lisible dans la ligne de legende que la vue place dessous.
    """

    ECART = 2  # pixels entre deux segments, couleur du fond

    def __init__(self, segments: list[tuple[str, float, str]],
                 hauteur: int = 28, parent: QWidget | None = None):
        super().__init__(parent)
        self.segments = [(lib, max(0.0, float(v)), QColor(c))
                         for lib, v, c in segments]
        self.setFixedHeight(hauteur)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, event) -> None:  # noqa: N802 (nom impose par Qt)
        total = sum(v for _, v, _ in self.segments)
        if total <= 0:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        f = QFont()
        f.setPixelSize(12)
        f.setBold(True)
        p.setFont(f)
        visibles = [s for s in self.segments if s[1] > 0]
        utile = float(self.width()) - self.ECART * (len(visibles) - 1)
        h = float(self.height())
        x = 0.0
        for lib, v, couleur in visibles:
            largeur = utile * v / total
            p.setPen(Qt.NoPen)
            p.setBrush(couleur)
            p.drawRoundedRect(QRectF(x, 0, largeur, h), 5, 5)
            zone = QRectF(x + 10, 0, largeur - 20, h)
            if p.fontMetrics().horizontalAdvance(lib) <= zone.width():
                p.setPen(_texte_lisible_sur(couleur))
                p.drawText(zone, Qt.AlignVCenter | Qt.AlignLeft, lib)
            x += largeur + self.ECART
        p.end()


class MiniBarres(QWidget):
    """Petits batons, sans axes : l'allure de la production sur la periode.
    Le plus haut est en couleur pleine, les autres adoucis."""

    def __init__(self, valeurs: list[float], color: str, hauteur: int = 56,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.valeurs = [max(0.0, float(v)) for v in valeurs]
        self.color = QColor(color)
        self.setFixedHeight(hauteur)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, event) -> None:  # noqa: N802 (nom impose par Qt)
        if not self.valeurs or max(self.valeurs) <= 0:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        n = len(self.valeurs)
        pas = float(self.width()) / n
        largeur = max(1.0, pas * 0.7)
        maxi = max(self.valeurs)
        adouci = QColor(self.color)
        adouci.setAlphaF(0.45)
        for i, v in enumerate(self.valeurs):
            h = (float(self.height()) - 2) * v / maxi
            p.setBrush(self.color if v == maxi else adouci)
            p.drawRoundedRect(QRectF(i * pas + (pas - largeur) / 2,
                                     self.height() - h, largeur, h),
                              min(3.0, largeur / 2), min(3.0, largeur / 2))
        p.end()


class KpiTile(QFrame):
    """Tuile de la rangee du haut : libelle, grand chiffre, barre, sous-titre.

    Difference avec KpiCard : le chiffre est nettement plus gros (c'est le
    seul contenu de la tuile) et une barre de proportion peut se glisser
    juste dessous. Hauteur fixe pour que les trois tuiles d'une rangee
    s'alignent quelle que soit la longueur de leurs textes.
    """

    def __init__(self, label: str, value: str, sub: str = "",
                 value_color: str | None = None,
                 ratio: float | None = None,
                 bar_color: str | None = None,
                 track_color: str = "#1f2937",
                 hauteur: int = 140,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("KpiTile")
        _apply_props(self, role="tile")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(hauteur)

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(8)

        lab = QLabel(label.upper())
        lab.setObjectName("TileLabel")
        v.addWidget(lab)

        val = QLabel(value)
        val.setObjectName("TileValue")
        # Taille posee ici (et pas dans le QSS) en pixels : c'est la seule
        # facon de garantir les 32 px demandes quel que soit le zoom Windows.
        f = police_tabulaire(gras=True)
        f.setPixelSize(34)
        val.setFont(f)
        if value_color:
            val.setStyleSheet(f"color: {value_color}; background: transparent;")
        v.addWidget(val)

        if ratio is not None:
            v.addWidget(BarMeter(ratio, bar_color or "#199e70", track_color))
        else:
            # Sans barre, le sous-titre remonterait et les tuiles d'une meme
            # rangee ne s'aligneraient plus : on reserve la hauteur perdue.
            v.addSpacing(8)

        s = QLabel(sub)
        s.setObjectName("TileSub")
        s.setWordWrap(True)
        s.setVisible(bool(sub))
        v.addWidget(s)
        v.addStretch(1)


# ----------------------------------------------------------------------
# Canvas matplotlib
# ----------------------------------------------------------------------

class MplCanvas(FigureCanvas):
    """Canvas matplotlib avec methode `draw_plot(callback)` pour redessiner."""

    def __init__(self, width: float = 5, height: float = 3.2, dpi: int = 100,
                 parent: QWidget | None = None):
        self.fig = Figure(figsize=(width, height), dpi=dpi, tight_layout=True)
        super().__init__(self.fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def clear(self) -> None:
        self.fig.clf()

    def apply_theme(self, rc_params: dict) -> None:
        # On met a jour les rcParams globaux ET les couleurs de la figure
        for k, v in rc_params.items():
            matplotlib.rcParams[k] = v
        self.fig.set_facecolor(rc_params.get("figure.facecolor", "white"))


# ----------------------------------------------------------------------
# Layouts en grille
# ----------------------------------------------------------------------

def grid_row(widgets: Iterable[QWidget], spacing: int = 14) -> QHBoxLayout:
    """Layout horizontal a colonnes egales."""
    h = QHBoxLayout()
    h.setSpacing(spacing)
    for w in widgets:
        h.addWidget(w, stretch=1)
    return h
