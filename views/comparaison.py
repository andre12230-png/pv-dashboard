"""Vue Comparaison N vs N-1 : compare la periode choisie en haut (mois, annee,
annee OA) a la meme periode un an plus tot, ou bien une journee precise."""
from __future__ import annotations

import numpy as np
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

import calculations as calc
from app_data import AppData
from gui_theme import CHART_COLORS as CC
from gui_theme import mpl_style
from gui_widgets import Card, MplCanvas, SectionTitle
from views._base import BaseView
from views._helpers import (
    METRIQUES,
    METRIQUES_ENERGIE,
    PERIOD_ALL,
    agreger,
    filter_period,
    fmt_date_fr,
    fmt_eur,
    fmt_kwh,
    libelle_periode,
    periode_precedente,
    variation,
)


def fin_de_periode(period: str, start_oa) -> pd.Timestamp:
    """Dernier jour d'un mois, d'une annee civile ou d'une annee OA."""
    if period.startswith("month-"):
        return pd.Period(period.split("-", 1)[1], freq="M").end_time.normalize()
    if period.startswith("oa-"):
        _, fin = calc.oa_year_bounds(start_oa, int(period.split("-")[1]))
        return pd.Timestamp(fin)
    return pd.Timestamp(int(period.split("-")[1]), 12, 31)


def date_limite_n1(df_n: pd.DataFrame, period: str, start_oa) -> pd.Timestamp | None:
    """Date a laquelle couper l'an passe quand la periode N n'est pas finie.

    Septembre 2026 releve jusqu'au 09/09 ne se compare pas a septembre 2025
    entier : la production affichait -62 % alors que le mois n'etait qu'au
    tiers. On compare donc aux memes dates, du debut de la periode N-1
    jusqu'au 09/09/2025. Retourne None quand la periode N est complete (rien
    a couper) ou vide.
    """
    if df_n.empty:
        return None
    dernier = df_n.index.max().normalize()
    if dernier >= fin_de_periode(period, start_oa):
        return None
    return dernier - pd.DateOffset(years=1)


class ComparaisonView(BaseView):
    """Compare la periode du selecteur du haut a la meme periode N-1.

    L'onglet avait autrefois ses propres boutons Mois / Annee et une liste de
    tous les mois, pendant que le selecteur du haut restait grise : on
    croyait ne pas pouvoir choisir de periode. Il obeit desormais au
    selecteur commun, comme les autres onglets. Seul le mode « une journee
    precise » garde son calendrier, le selecteur du haut ne descendant pas
    jusqu'au jour.
    """

    def __init__(self, data: AppData, theme: dict, parent=None):
        super().__init__(data, theme, parent)
        self.mode_jour = False             # True : on compare une journee
        self.selection: str | None = None  # la journee comparee, "AAAA-MM-JJ"
        self._periode = PERIOD_ALL         # derniere periode recue du haut

    # ---------- construction de la vue ----------
    def populate(self, period: str) -> None:
        # Choisir une autre periode en haut, c'est vouloir voir cette
        # periode-la : on quitte le mode journee. Choisir une date dans le
        # calendrier redessine l'onglet avec la MEME periode, ce qui le laisse
        # en mode journee.
        if period != self._periode:
            self.mode_jour = False
            self.selection = None
        self._periode = period

        df = self.data.df
        if df.empty:
            self.layout_inner.addWidget(self._empty_card("Aucune donnée disponible."))
            return

        self.layout_inner.addWidget(SectionTitle(
            "Comparaison avec l'année précédente",
            "Compare la période choisie en haut à droite (mois, année ou "
            "année OA) à la même période un an plus tôt.",
        ))

        # Bandeau : le bouton « Une journee precise », et son calendrier
        # quand il est enfonce.
        barre = QHBoxLayout()
        barre.setSpacing(8)
        btn_jour = QPushButton("Une journée précise")
        btn_jour.setObjectName("ActionBtn")
        btn_jour.setCheckable(True)
        btn_jour.setChecked(self.mode_jour)
        btn_jour.setCursor(Qt.PointingHandCursor)
        btn_jour.setToolTip("Comparer un jour donné au même jour de l'année "
                            "précédente, au lieu de la période choisie en haut.")
        btn_jour.clicked.connect(self._activer_mode_jour)
        barre.addWidget(btn_jour)
        if self.mode_jour:
            barre.addSpacing(6)
            barre.addWidget(self._creer_calendrier(df))
        barre.addStretch(1)
        self.layout_inner.addLayout(barre)

        if self.mode_jour:
            self._rendre_jour(df)
        elif period == PERIOD_ALL or not period:
            self.layout_inner.addWidget(self._empty_card(
                "Choisissez un mois ou une année dans le sélecteur en haut à "
                "droite : l'onglet le compare à la même période un an plus "
                "tôt. Comparer « toute la période » n'aurait pas de sens."))
        elif periode_precedente(period) is None:
            # Seule l'annee OA #1 tombe ici : il n'y a pas d'annee OA #0.
            self.layout_inner.addWidget(self._empty_card(
                f"{libelle_periode(period)} est la première du contrat : il "
                "n'y a pas d'année précédente à lui comparer."))
        else:
            self._rendre_periode(df, period)
        self.layout_inner.addStretch(1)

    # ---------- mode journee ----------
    def _activer_mode_jour(self, actif: bool) -> None:
        self.mode_jour = bool(actif)
        if self.mode_jour and self.selection is None:
            self.selection = self._jour_par_defaut(self.data.df)
        self.refresh(self._periode)

    def _jour_par_defaut(self, df: pd.DataFrame) -> str:
        """Dernier jour releve DANS la periode choisie en haut : sous janvier
        2025, le calendrier s'ouvre en janvier 2025, pas au dernier releve du
        fichier. Repli sur ce dernier releve si la periode est vide."""
        dans_periode = filter_period(df, self._periode, self.data.start_oa)
        source = dans_periode if not dans_periode.empty else df
        return source.index.max().strftime("%Y-%m-%d")

    def _creer_calendrier(self, df: pd.DataFrame) -> QDateEdit:
        """Selecteur de jour avec calendrier, borne aux dates du dataset."""
        if self.selection is None:
            self.selection = self._jour_par_defaut(df)
        cal = QDateEdit()
        cal.setObjectName("PeriodSelector")
        cal.setCalendarPopup(True)
        cal.setDisplayFormat("dd/MM/yyyy")
        # Sans largeur minimale, le dernier chiffre de l'annee etait rogne.
        cal.setMinimumWidth(130)
        cal.setMinimumDate(df.index.min().date())
        cal.setMaximumDate(df.index.max().date())
        # setDate declencherait dateChanged -> refresh en pleine construction
        cal.blockSignals(True)
        cal.setDate(pd.Timestamp(self.selection).date())
        cal.blockSignals(False)
        cal.dateChanged.connect(self._changer_date)
        return cal

    def _changer_date(self, qdate) -> None:
        self.selection = qdate.toPython().strftime("%Y-%m-%d")
        self.refresh(self._periode)

    # ---------- rendu des comparaisons ----------
    def _rendre_jour(self, df: pd.DataFrame) -> None:
        d = pd.Timestamp(self.selection)
        d_prev = d - pd.DateOffset(years=1)

        agg_n = agreger(df[df.index.normalize() == d])
        agg_n1 = agreger(df[df.index.normalize() == d_prev])
        cumul_n = agreger(df[(df.index >= pd.Timestamp(d.year, 1, 1))
                             & (df.index <= d)])
        cumul_n1 = agreger(df[(df.index >= pd.Timestamp(d_prev.year, 1, 1))
                              & (df.index <= d_prev)])

        blocs = QHBoxLayout()
        blocs.setSpacing(14)
        blocs.addWidget(self._bloc(
            "Journée",
            fmt_date_fr(d), fmt_date_fr(d_prev), agg_n, agg_n1))
        blocs.addWidget(self._bloc(
            "Cumul depuis le 1er janvier",
            f"01/01 au {fmt_date_fr(d)}", f"01/01 au {fmt_date_fr(d_prev)}",
            cumul_n, cumul_n1,
            entete_n=str(d.year), entete_n1=str(d_prev.year)))
        blocs.addStretch(1)
        self.layout_inner.addLayout(blocs)
        self.layout_inner.addWidget(self._chart(
            "Cumul annuel - énergie", cumul_n, cumul_n1,
            str(d.year), str(d_prev.year)))

    def _rendre_periode(self, df: pd.DataFrame, period: str) -> None:
        """Un mois, une annee civile ou une annee OA, face a la precedente."""
        prev = periode_precedente(period)
        label_n, label_n1 = libelle_periode(period), libelle_periode(prev)
        df_n = filter_period(df, period, self.data.start_oa)
        df_n1 = filter_period(df, prev, self.data.start_oa)

        # Periode en cours : l'an passe s'arrete a la meme date, et les
        # libelles le disent (« Septembre 2026 (au 09/09) »).
        limite = date_limite_n1(df_n, period, self.data.start_oa)
        if limite is not None:
            df_n1 = df_n1[df_n1.index.normalize() <= limite]
            label_n += f" (au {df_n.index.max().strftime('%d/%m')})"
            label_n1 += f" (au {limite.strftime('%d/%m')})"

        agg_n = agreger(df_n)
        agg_n1 = agreger(df_n1)

        if period.startswith("month-"):
            titre, titre_chart = "Mois", "Énergie du mois"
        elif period.startswith("oa-"):
            titre, titre_chart = "Année OA", "Énergie de l'année OA"
        else:
            titre, titre_chart = "Année civile", "Énergie de l'année"

        # Pleine largeur : a 560 px, le tableau tronquait ses libelles
        # (« P… », « A… ») et montrait une barre de defilement (audit du
        # 14/09/2026).
        self.layout_inner.addWidget(
            self._bloc(titre, label_n, label_n1, agg_n, agg_n1))
        self.layout_inner.addWidget(self._chart(
            titre_chart, agg_n, agg_n1, label_n, label_n1))

    # ---------- widgets ----------
    def _bloc(self, titre: str, label_n: str, label_n1: str,
              agg_n: dict | None, agg_n1: dict | None,
              entete_n: str | None = None,
              entete_n1: str | None = None) -> QFrame:
        # entete_n/entete_n1 : en-tetes de colonnes courts (sinon = labels).
        entete_n = entete_n or label_n
        entete_n1 = entete_n1 or label_n1
        card = Card()
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 14, 16, 14)
        v.addWidget(SectionTitle(titre, f"{label_n}   vs   {label_n1}"))

        table = QTableWidget(len(METRIQUES), 4)
        table.setHorizontalHeaderLabels(
            ["Indicateur", entete_n1, entete_n, "Variation"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.setFocusPolicy(Qt.NoFocus)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        hh = table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 4):
            hh.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        for r, (cle, label, unite, sens) in enumerate(METRIQUES):
            fmt = fmt_kwh if unite == "kwh" else fmt_eur
            val_n = agg_n[cle] if agg_n else None
            val_n1 = agg_n1[cle] if agg_n1 else None

            it_label = QTableWidgetItem("  " + label)
            it_n1 = QTableWidgetItem(fmt(val_n1) if val_n1 is not None else "—")
            it_n = QTableWidgetItem(fmt(val_n) if val_n is not None else "—")
            it_n1.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_n.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            if val_n is not None and val_n1 is not None:
                txt, couleur = variation(val_n - val_n1, val_n1, fmt, sens,
                                         self.theme)
            else:
                txt, couleur = "donnée N-1 absente", self.theme["text_muted"]
            it_var = QTableWidgetItem(txt)
            it_var.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_var.setForeground(QColor(couleur))
            font = it_var.font()
            font.setBold(True)
            it_var.setFont(font)

            for c, it in enumerate([it_label, it_n1, it_n, it_var]):
                table.setItem(r, c, it)

        table.setFixedHeight(36 + len(METRIQUES) * 38)
        v.addWidget(table)
        return card

    def _chart(self, titre: str, agg_n: dict | None, agg_n1: dict | None,
               label_n: str, label_n1: str) -> QFrame:
        card = Card()
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 14, 16, 14)
        v.addWidget(SectionTitle(titre))

        metriques = [(c, label) for c, label, u, s in METRIQUES
                     if c in METRIQUES_ENERGIE]
        labels = [label for _, label in metriques]
        vals_n = [agg_n[c] if agg_n else 0.0 for c, _ in metriques]
        vals_n1 = [agg_n1[c] if agg_n1 else 0.0 for c, _ in metriques]

        # Assez haut pour ses libelles : a 3 pouces, la carte l'ecrasait, la
        # legende tombait sur les barres et les noms etaient coupes en bas.
        canvas = MplCanvas(width=8, height=3.6, dpi=100)
        canvas.setMinimumHeight(340)
        canvas.apply_theme(mpl_style(self.theme))
        ax = canvas.fig.add_subplot(111)
        x = np.arange(len(metriques))
        w = 0.36
        b1 = ax.bar(x - w / 2, vals_n1, w, label=f"{label_n1} (N-1)", color="#94a3b8")
        b2 = ax.bar(x + w / 2, vals_n, w, label=f"{label_n} (N)", color=CC["production"])
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.set_ylabel("kWh")
        # Legende au-dessus du trace, comme sur les autres graphiques.
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0),
                  frameon=False, ncol=2)
        ax.bar_label(b1, fmt="%.0f", padding=2)
        ax.bar_label(b2, fmt="%.0f", padding=2)
        ax.margins(y=0.15)
        canvas.fig.tight_layout()
        v.addWidget(canvas)
        return card
