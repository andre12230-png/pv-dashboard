"""Diagramme de flux (Sankey) dessine au QPainter, sans dependance externe.

Pourquoi un widget maison plutot qu'une bibliotheque :
  - matplotlib.sankey dessine des fleches en zigzag, illisibles pour trois
    flux ;
  - plotly ferait un vrai Sankey mais s'affiche dans un navigateur, ce qui
    imposerait QWebEngineView (plusieurs centaines de Mo de dependance).
Un Sankey a deux colonnes, c'est quatre rectangles et trois rubans : Qt sait
faire ca nativement avec QPainterPath.

Ce que le dessin apporte ici : le ruban "autoconsommation" relie
physiquement la production a la consommation. Les kWh autoconsommes
n'apparaissent donc qu'une seule fois, au lieu d'etre comptes deux fois avec
deux pourcentages differents comme le faisaient les camemberts.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from gui_widgets import police_tabulaire

# Geometrie (en pixels)
LARGEUR_NOEUD = 18       # epaisseur des rectangles
LISERE_NOEUD = 2         # blanc autour d'un rectangle, voir paintEvent
ECART_NOEUDS = 34        # blanc vertical entre deux noeuds d'une colonne
ECART_RUBANS = 2         # blanc entre deux rubans voisins sur un meme noeud
HAUTEUR_MINI_NOEUD = 10  # voir _hauteurs_noeuds()
MARGE_HAUT = 18
MARGE_BAS = 18
OPACITE_RUBAN = 0.45
# Au-dela de cette largeur les rubans s'etirent au point de devenir des
# bandes horizontales : la pente qui relie la production a la consommation
# ne se voit plus, et le dessin ne raconte plus rien.
LARGEUR_MAXI = 940
RAYON_PASTILLE = 6  # coins arrondis de l'etiquette posee sur un ruban
# Ou poser l'etiquette le long de son ruban, en fraction de la longueur.
# Le milieu d'abord ; les autres servent quand deux etiquettes se marchent
# dessus, ce qui arrive en hiver ou la production se reduit a deux rubans
# colles l'un a l'autre.
POSITIONS_ESSAI = (0.5, 0.68, 0.32, 0.8, 0.2)


def _bezier(t: float, a: float, b: float, c: float, d: float) -> float:
    """Valeur d'une courbe de Bezier cubique au parametre t."""
    u = 1 - t
    return u * u * u * a + 3 * u * u * t * b + 3 * u * t * t * c + t * t * t * d


@dataclass(frozen=True)
class Noeud:
    """Un rectangle du diagramme."""
    cle: str
    libelle: str
    valeur: float
    couleur: str


@dataclass(frozen=True)
class Flux:
    """Un ruban entre un noeud de gauche et un noeud de droite.

    libelle et couleur sont facultatifs. Sans libelle le ruban reste muet ;
    sans couleur il prend celle de son noeud de depart.
    """
    source: str
    cible: str
    valeur: float
    libelle: str = ""
    couleur: str = ""


class SankeyWidget(QWidget):
    """Deux colonnes de noeuds relies par des rubans proportionnels."""

    def __init__(self, gauche: list[Noeud], droite: list[Noeud],
                 flux: list[Flux], theme: dict, hauteur: int = 300,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.gauche = gauche
        self.droite = droite
        self.flux = flux
        self.theme = theme
        self.setFixedHeight(hauteur)
        self.setMaximumWidth(LARGEUR_MAXI)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Un Sankey n'a de sens que si tout ce qui entre ressort : on le
        # verifie plutot que de dessiner un diagramme faux en silence.
        total_g = sum(n.valeur for n in gauche)
        total_d = sum(n.valeur for n in droite)
        total_f = sum(f.valeur for f in flux)
        tolerance = max(0.01, total_g * 1e-6)
        assert abs(total_g - total_d) < tolerance, (
            f"Sankey desequilibre : {total_g:.3f} kWh a gauche contre "
            f"{total_d:.3f} kWh a droite")
        assert abs(total_g - total_f) < tolerance, (
            f"Sankey incomplet : {total_f:.3f} kWh de rubans pour "
            f"{total_g:.3f} kWh de noeuds")
        self.total = total_g

    def sizeHint(self) -> QSize:  # noqa: N802 (nom impose par Qt)
        """Taille visee : la largeur maxi, que le parent reduira au besoin."""
        return QSize(LARGEUR_MAXI, self.height())

    # ------------------------------------------------------------------
    # Geometrie
    # ------------------------------------------------------------------
    def _hauteurs_noeuds(self, noeuds: list[Noeud], hauteur_utile: float,
                         echelle: float) -> list[float]:
        """Hauteur de chaque rectangle, proportionnelle a sa valeur.

        Avec une stricte proportionnalite, un noeud presque nul (l'injection
        d'un mois d'hiver) se reduit a un trait de 2 px et son etiquette vient
        se coller a celle du voisin. On lui impose donc une hauteur plancher,
        reprise sur les autres noeuds pour que la colonne garde sa hauteur
        totale.

        Ce plancher fait mentir le dessin, il faut donc le garder bas. A 24 px
        l'injection de janvier 2026 (40 kWh, 4 % du total) etait dessinee trois
        fois trop grande, et la consommation perdait 14 px au profit d'un poste
        vingt fois plus petit. A 10 px, mesure sur les 59 periodes du CSV :
        l'ecart est nul des qu'un poste depasse 4,4 % du total (10 px sur les
        230 disponibles), et il plafonne a 4 px en dessous -- le pire cas etant
        decembre 2025, ou l'injection ne pese que 2,6 %. La barre reste visible
        et son etiquette lisible meme pour un poste nul.
        """
        hauteurs = [max(n.valeur * echelle, HAUTEUR_MINI_NOEUD) for n in noeuds]
        surplus = sum(hauteurs) - hauteur_utile
        if surplus > 0:
            # On reprend le surplus sur les noeuds qui ont de la marge.
            ajustables = [i for i, h in enumerate(hauteurs)
                          if h > HAUTEUR_MINI_NOEUD]
            marge_totale = sum(hauteurs[i] - HAUTEUR_MINI_NOEUD
                               for i in ajustables)
            if marge_totale > 0:
                for i in ajustables:
                    part = (hauteurs[i] - HAUTEUR_MINI_NOEUD) / marge_totale
                    hauteurs[i] -= surplus * part
        return hauteurs

    def _placer_colonne(self, noeuds: list[Noeud], hauteurs: list[float],
                        y_depart: float) -> dict[str, tuple[float, float]]:
        """{cle: (y_haut, hauteur)} en empilant les noeuds de haut en bas."""
        pos: dict[str, tuple[float, float]] = {}
        y = y_depart
        for n, h in zip(noeuds, hauteurs, strict=True):
            pos[n.cle] = (y, h)
            y += h + ECART_NOEUDS
        return pos

    def _tranches(self, noeuds: list[Noeud], pos: dict[str, tuple[float, float]],
                  cle_noeud, cle_tri, ordre_autre: list[str]
                  ) -> dict[int, tuple[float, float]]:
        """Repartit les rubans sur la hauteur de chaque noeud.

        Les rubans d'un meme noeud sont ranges dans l'ordre du noeud d'en
        face : c'est ce qui evite qu'ils se croisent au milieu du dessin.
        Retourne {index du flux: (y_haut, epaisseur)}.
        """
        rang = {cle: i for i, cle in enumerate(ordre_autre)}
        tranches: dict[int, tuple[float, float]] = {}
        for n in noeuds:
            indices = [i for i, f in enumerate(self.flux)
                       if cle_noeud(f) == n.cle]
            indices.sort(key=lambda i: rang.get(cle_tri(self.flux[i]), 0))
            if not indices:
                continue
            y_haut, hauteur = pos[n.cle]
            # Les ecarts entre rubans sont pris SUR la hauteur du noeud, sinon
            # la pile de rubans deborderait du rectangle.
            dispo = max(hauteur - ECART_RUBANS * (len(indices) - 1), 1.0)
            total = sum(self.flux[i].valeur for i in indices) or 1.0
            y = y_haut
            for i in indices:
                ep = self.flux[i].valeur / total * dispo
                tranches[i] = (y, ep)
                y += ep + ECART_RUBANS
        return tranches

    # ------------------------------------------------------------------
    # Dessin
    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802 (nom impose par Qt)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        police_nom = self.font()
        police_nom.setPointSize(9)
        police_val = police_tabulaire(10, gras=True)
        fm_nom = QFontMetrics(police_nom)
        fm_val = QFontMetrics(police_val)

        # Largeur reservee aux etiquettes, mesuree sur le texte reel : c'est
        # ce qui garantit qu'aucun libelle n'est tronque.
        def largeur_etiquette(noeuds: list[Noeud]) -> float:
            largeurs = [max(fm_nom.horizontalAdvance(n.libelle),
                            fm_val.horizontalAdvance(self._valeur_txt(n.valeur)))
                        for n in noeuds]
            return (max(largeurs) if largeurs else 0.0) + 14

        marge_g = largeur_etiquette(self.gauche)
        marge_d = largeur_etiquette(self.droite)

        x_gauche = marge_g
        x_droite = max(self.width() - marge_d - LARGEUR_NOEUD, x_gauche + 80)

        hauteur_utile = self.height() - MARGE_HAUT - MARGE_BAS
        # Meme echelle des deux cotes : c'est ce qui rend les deux colonnes
        # comparables d'un coup d'oeil (elles totalisent les memes kWh).
        n_max = max(len(self.gauche), len(self.droite))
        libre = hauteur_utile - ECART_NOEUDS * (n_max - 1)
        echelle = libre / self.total if self.total > 0 else 0.0

        h_g = self._hauteurs_noeuds(self.gauche, libre, echelle)
        h_d = self._hauteurs_noeuds(self.droite, libre, echelle)
        # Colonnes centrees verticalement l'une par rapport a l'autre.
        haut_g = sum(h_g) + ECART_NOEUDS * (len(self.gauche) - 1)
        haut_d = sum(h_d) + ECART_NOEUDS * (len(self.droite) - 1)
        pos_g = self._placer_colonne(
            self.gauche, h_g, MARGE_HAUT + (hauteur_utile - haut_g) / 2)
        pos_d = self._placer_colonne(
            self.droite, h_d, MARGE_HAUT + (hauteur_utile - haut_d) / 2)

        tr_src = self._tranches(self.gauche, pos_g, lambda f: f.source,
                                lambda f: f.cible, [n.cle for n in self.droite])
        tr_cib = self._tranches(self.droite, pos_d, lambda f: f.cible,
                                lambda f: f.source, [n.cle for n in self.gauche])

        couleurs = {n.cle: n.couleur for n in self.gauche + self.droite}

        # 1) Les rubans d'abord : les rectangles passent par-dessus.
        p.setPen(Qt.NoPen)
        etiquettes: list[tuple[Flux, QColor, tuple]] = []
        for i, f in enumerate(self.flux):
            if i not in tr_src or i not in tr_cib:
                continue
            y0, e0 = tr_src[i]
            y1, e1 = tr_cib[i]
            x0 = x_gauche + LARGEUR_NOEUD
            x1 = x_droite
            ctrl = (x1 - x0) * 0.5  # points de controle a mi-distance

            chemin = QPainterPath()
            chemin.moveTo(QPointF(x0, y0))
            chemin.cubicTo(QPointF(x0 + ctrl, y0), QPointF(x1 - ctrl, y1),
                           QPointF(x1, y1))
            chemin.lineTo(QPointF(x1, y1 + e1))
            chemin.cubicTo(QPointF(x1 - ctrl, y1 + e1),
                           QPointF(x0 + ctrl, y0 + e0), QPointF(x0, y0 + e0))
            chemin.closeSubpath()

            # Un ruban peut porter sa propre couleur : l'autoconsommation
            # est verte partout dans l'appli, pas jaune comme le soleil
            # dont elle sort. A defaut il garde celle de son noeud de
            # depart.
            teinte = QColor(f.couleur or couleurs[f.source])
            couleur = QColor(teinte)
            couleur.setAlphaF(OPACITE_RUBAN)
            p.fillPath(chemin, couleur)

            # On garde la geometrie du ruban : l'etiquette pourra glisser
            # le long de la courbe si elle en gene une autre.
            etiquettes.append((f, teinte, (x0, x1, y0, e0, y1, e1)))

        # 2) Les rectangles pleins, chacun cerne d'un liseré de la couleur
        # du fond. Sans ce liseré, un noeud et le ruban de meme couleur qui
        # en part se touchent et se lisent comme un seul bloc : le noeud
        # parait alors bien plus grand que sa valeur.
        fond = QColor(self.theme["bg_panel"])
        for noeuds, pos, x in ((self.gauche, pos_g, x_gauche),
                               (self.droite, pos_d, x_droite)):
            for n in noeuds:
                y, h = pos[n.cle]
                p.fillRect(QRectF(x - LISERE_NOEUD, y - LISERE_NOEUD,
                                  LARGEUR_NOEUD + 2 * LISERE_NOEUD,
                                  h + 2 * LISERE_NOEUD), fond)
                p.fillRect(QRectF(x, y, LARGEUR_NOEUD, h), QColor(n.couleur))

        # 3) Les etiquettes, a l'exterieur des rectangles.
        for n in self.gauche:
            y, h = pos_g[n.cle]
            self._etiquette(p, n, QRectF(0, y, x_gauche - 12, h),
                            Qt.AlignRight, police_nom, police_val, fm_nom)
        for n in self.droite:
            y, h = pos_d[n.cle]
            x = x_droite + LARGEUR_NOEUD + 12
            self._etiquette(p, n, QRectF(x, y, self.width() - x, h),
                            Qt.AlignLeft, police_nom, police_val, fm_nom)

        # 4) Les etiquettes des rubans, en dernier pour qu'elles passent
        # au-dessus de tout. Sans elles les trois flux du centre sont
        # muets : leurs valeurs ne se lisaient que par soustraction entre
        # les quatre rectangles des bords.
        posees: list[QRectF] = []
        for f, teinte, geo in etiquettes:
            if not f.libelle:
                continue
            for t in POSITIONS_ESSAI:
                zone = self._zone_etiquette(f, geo, t, fm_nom, fm_val)
                # Marge de 6 px : deux pastilles qui se frolent se lisent
                # deja mal.
                if not any(zone.intersects(z.adjusted(-6, -6, 6, 6))
                           for z in posees):
                    break
            posees.append(zone)
            self._etiquette_ruban(p, f, teinte, zone, police_nom,
                                  police_val, fm_nom, fm_val)
        p.end()

    def _zone_etiquette(self, f: Flux, geo: tuple, t: float,
                        fm_nom, fm_val) -> QRectF:
        """Rectangle de l'etiquette posee a la fraction t du ruban.

        Le ruban etant courbe, on evalue ses deux bords en t plutot que de
        les interpoler : l'etiquette reste centree sur l'epaisseur reelle.
        """
        x0, x1, y0, e0, y1, e1 = geo
        ctrl = (x1 - x0) * 0.5
        x = _bezier(t, x0, x0 + ctrl, x1 - ctrl, x1)
        haut = _bezier(t, y0, y0, y1, y1)
        bas = _bezier(t, y0 + e0, y0 + e0, y1 + e1, y1 + e1)

        largeur = max(fm_nom.horizontalAdvance(f.libelle),
                      fm_val.horizontalAdvance(self._valeur_txt(f.valeur))) + 18
        hauteur = fm_nom.height() + fm_val.height() + 8
        return QRectF(x - largeur / 2, (haut + bas) / 2 - hauteur / 2,
                      largeur, hauteur)

    def _etiquette_ruban(self, p: QPainter, f: Flux, teinte: QColor,
                         zone: QRectF, police_nom, police_val,
                         fm_nom, fm_val) -> None:
        """Nom et valeur du flux, sur une pastille posee sur le ruban.

        La pastille est opaque : les rubans etant translucides et parfois
        superposes, un texte pose directement dessus serait illisible.
        """
        txt_val = self._valeur_txt(f.valeur)
        h_nom, h_val = fm_nom.height(), fm_val.height()

        bord = QColor(teinte)
        bord.setAlphaF(0.55)
        p.setPen(QPen(bord, 1))
        p.setBrush(QColor(self.theme["bg_panel"]))
        p.drawRoundedRect(zone, RAYON_PASTILLE, RAYON_PASTILLE)
        p.setBrush(Qt.NoBrush)

        p.setFont(police_nom)
        p.setPen(QColor(self.theme["text_secondary"]))
        p.drawText(QRectF(zone.x(), zone.y() + 4, zone.width(), h_nom),
                   Qt.AlignHCenter | Qt.AlignVCenter, f.libelle)

        p.setFont(police_val)
        p.setPen(teinte)
        p.drawText(QRectF(zone.x(), zone.y() + 4 + h_nom, zone.width(), h_val),
                   Qt.AlignHCenter | Qt.AlignVCenter, txt_val)

    def _valeur_txt(self, valeur: float) -> str:
        return f"{valeur:,.1f} kWh".replace(",", " ").replace(".", ",")

    def _etiquette(self, p: QPainter, n: Noeud, zone: QRectF, alignement,
                   police_nom, police_val, fm_nom) -> None:
        """Nom au-dessus, valeur en dessous, le tout centre sur le noeud."""
        h_nom = fm_nom.height()
        h_totale = h_nom * 2
        y = zone.y() + (zone.height() - h_totale) / 2

        p.setFont(police_nom)
        p.setPen(QColor(self.theme["text_secondary"]))
        p.drawText(QRectF(zone.x(), y, zone.width(), h_nom),
                   alignement | Qt.AlignVCenter, n.libelle)

        p.setFont(police_val)
        p.setPen(QColor(n.couleur))
        p.drawText(QRectF(zone.x(), y + h_nom, zone.width(), h_nom),
                   alignement | Qt.AlignVCenter, self._valeur_txt(n.valeur))
