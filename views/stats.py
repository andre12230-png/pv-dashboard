"""Vue Statistiques : comparaison annuelle, rendement specifique."""
from __future__ import annotations

import numpy as np
import pandas as pd
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from gui_theme import CHART_COLORS as CC
from gui_theme import mpl_style
from gui_widgets import Card, KpiCard, MplCanvas, SectionTitle, grid_row
from views._base import BaseView
from views._helpers import chiffres_sur_barres


class StatsView(BaseView):
    utilise_periode = False  # comparaisons multi-annees : toujours tout l'historique

    def populate(self, period: str) -> None:
        df = self.data.df
        if df.empty:
            self.layout_inner.addWidget(self._empty_card("Aucune donnée."))
            return

        yearly = df.groupby(df.index.year).agg({
            "production_kwh": "sum",
            "autoconsommation_kwh": "sum",
            "injection_kwh": "sum",
            "soutirage_kwh": "sum",
        })

        # Annees partielles (installation en cours d'annee, annee en cours) :
        # signalees partout et exclues de la moyenne de rendement, sinon
        # elles tirent les comparaisons vers le bas.
        debut, fin = df.index.min(), df.index.max()
        partielles = {
            int(y) for y in yearly.index
            if debut > pd.Timestamp(int(y), 1, 1) or fin < pd.Timestamp(int(y), 12, 31)
        }

        self.layout_inner.addWidget(SectionTitle("Comparaison annuelle"))

        graphs = QHBoxLayout()
        graphs.setSpacing(14)
        graphs.addWidget(self._yearly_bars(yearly, partielles))
        graphs.addWidget(self._monthly_lines(df))
        self.layout_inner.addLayout(graphs)

        p_crete = self.data.cfg["installation"]["puissance_kwc"]
        rendement = (yearly["production_kwh"] / p_crete)
        completes = [y for y in rendement.index if int(y) not in partielles]
        if completes:
            moyenne = rendement.loc[completes].mean()
            texte_moyenne = f"moyenne des années complètes : {int(moyenne)}"
        else:
            texte_moyenne = "aucune année complète pour calculer une moyenne"

        self.layout_inner.addWidget(SectionTitle(
            "Rendement spécifique (kWh / kWc / an)",
            f"Référence France : 900-1200 kWh/kWc/an - {texte_moyenne}",
        ))
        cards = []
        for y, v in rendement.items():
            if int(y) in partielles:
                g = df[df.index.year == int(y)]
                cards.append(KpiCard(
                    f"Année {int(y)} - partielle", f"{int(v)}",
                    f"du {g.index.min().strftime('%d/%m')} "
                    f"au {g.index.max().strftime('%d/%m')} - hors moyenne",
                    "neutral"))
            else:
                cards.append(KpiCard(
                    f"Année {int(y)}", f"{int(v)}", "kWh/kWc", "primary"))
        # Jusqu'a six annees par ligne : par quatre, la cinquieme restait
        # seule, etiree sur toute la largeur (audit du 14/09/2026).
        for i in range(0, len(cards), 6):
            self.layout_inner.addLayout(grid_row(cards[i:i+6]))
        self.layout_inner.addStretch(1)

    def _yearly_bars(self, yearly: pd.DataFrame, partielles: set[int]) -> QFrame:
        card = Card()
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 14, 16, 14)
        v.addWidget(QLabel("Production par année civile"))
        canvas = MplCanvas(width=5, height=3.2, dpi=100)
        canvas.apply_theme(mpl_style(self.theme))
        ax = canvas.fig.add_subplot(111)
        xs = np.arange(len(yearly.index))
        w = 0.2
        # Libelles en clair, comme les en-tetes des Releves journaliers.
        b1 = ax.bar(xs - 1.5*w, yearly["production_kwh"], w,
                    label="Production", color=CC["production"])
        b2 = ax.bar(xs - 0.5*w, yearly["autoconsommation_kwh"], w,
                    label="Autoconsommée", color=CC["autoconso"])
        b3 = ax.bar(xs + 0.5*w, yearly["injection_kwh"], w,
                    label="Injectée", color=CC["injection"])
        b4 = ax.bar(xs + 1.5*w, yearly["soutirage_kwh"], w,
                    label="Achetée", color=CC["soutirage"])
        # Le chiffre de chaque barre (demande du 15/09/2026).
        chiffres_sur_barres(ax, [b1, b2, b3, b4])
        ax.set_xticks(xs)
        ax.set_xticklabels([f"{y}\n(partielle)" if int(y) in partielles else str(y)
                            for y in yearly.index])
        ax.set_ylabel("kWh")
        # Legende au-dessus du trace : dedans, elle recouvrait le haut des
        # barres de production, les plus hautes.
        # Deux par ligne : en clair, les quatre libelles ne tiennent pas sur
        # une seule (« Achetee » sortait coupe).
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0),
                  frameon=False, ncol=2)
        canvas.fig.tight_layout()
        v.addWidget(canvas)
        return card

    def _monthly_lines(self, df: pd.DataFrame) -> QFrame:
        card = Card()
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 14, 16, 14)
        v.addWidget(QLabel("Production mensuelle multi-années"))
        df_m = df.copy()
        df_m["mois"] = df_m.index.month
        df_m["annee"] = df_m.index.year
        pivot = df_m.pivot_table(values="production_kwh", index="mois",
                                  columns="annee", aggfunc="sum")
        canvas = MplCanvas(width=5, height=3.2, dpi=100)
        canvas.apply_theme(mpl_style(self.theme))
        ax = canvas.fig.add_subplot(111)
        palette = ["#f59e0b", "#0ea5e9", "#16a34a", "#7c3aed", "#ef4444", "#06b6d4"]
        for i, col in enumerate(pivot.columns):
            ax.plot(pivot.index, pivot[col], marker="o", lw=2,
                    color=palette[i % len(palette)], label=str(col))
        ax.set_xticks(range(1, 13))
        ax.set_xticklabels(["Jan", "Fév", "Mar", "Avr", "Mai", "Juin",
                            "Juil", "Août", "Sep", "Oct", "Nov", "Déc"])
        ax.set_ylabel("Production (kWh)")
        # Legende au-dessus du trace : en haut a droite, elle recouvrait les
        # points d'aout et de septembre (audit du 14/09/2026).
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0),
                  frameon=False, ncol=min(len(pivot.columns), 6))
        canvas.fig.tight_layout()
        v.addWidget(canvas)
        return card
