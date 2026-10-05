"""Vue Statistiques : comparaison annuelle, rendement specifique."""
from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy

from gui_theme import CHART_COLORS as CC
from gui_theme import mpl_style
from gui_widgets import Card, KpiCard, MplCanvas, SectionTitle, grid_row
from views._base import BaseView
from views._helpers import chiffres_sur_barres


def milliers(valeur: float) -> str:
    """« 1 181 » et non « 1181 » : les milliers separes, comme partout
    ailleurs (relecture du 01/10/2026)."""
    return f"{valeur:,.0f}".replace(",", " ")


# Graduations des axes en kWh : « 8 000 » et non « 8000 ».
AXE_MILLIERS = FuncFormatter(lambda valeur, _pos: milliers(valeur))

# Une couleur par annee, foncee : sans chiffre a cote, une courbe tient au
# moins 3 pour 1 sur l'ivoire des cartes (charte). L'orange et le bleu clair
# d'avant ne faisaient que 2,0 et 2,6 (01/10/2026).
COULEURS_ANNEES = ["#b45309", "#0369a1", "#15803d", "#7c3aed", "#dc2626",
                   "#0e7490"]


class StatsView(BaseView):
    utilise_periode = False  # comparaisons multi-annees : toujours tout l'historique
    selecteur_annuel = True  # un mois n'a aucun sens ici : menu des mois masque

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
            texte_moyenne = (f"moyenne des années complètes : "
                             f"{milliers(int(moyenne))} kWh/kWc/an")
        else:
            texte_moyenne = "aucune année complète pour calculer une moyenne"

        self.layout_inner.addWidget(SectionTitle(
            # Une seule ecriture de l'unite sur la page (01/10/2026).
            "Rendement spécifique (kWh/kWc/an)",
            f"Référence France : 900 à 1 200 kWh/kWc/an — {texte_moyenne}",
        ))
        cards = []
        for y, v in rendement.items():
            if int(y) in partielles:
                g = df[df.index.year == int(y)]
                cards.append(KpiCard(
                    f"Année {int(y)} — partielle", milliers(int(v)),
                    f"kWh/kWc — du {g.index.min().strftime('%d/%m')} "
                    f"au {g.index.max().strftime('%d/%m')} — hors moyenne",
                    "neutral"))
            else:
                cards.append(KpiCard(
                    f"Année {int(y)}", milliers(int(v)), "kWh/kWc/an",
                    "primary"))
        # Toutes les tuiles de la meme largeur : les annees partielles, au
        # sous-titre plus long, prenaient plus de place et attiraient l'oeil
        # (01/10/2026). Leur sous-titre passe a la ligne.
        for carte in cards:
            carte.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            carte.sub.setWordWrap(True)
        # Jusqu'a six annees par ligne : par quatre, la cinquieme restait
        # seule, etiree sur toute la largeur (audit du 14/09/2026).
        for i in range(0, len(cards), 6):
            self.layout_inner.addLayout(grid_row(cards[i:i+6]))
        self.layout_inner.addStretch(1)

    def _yearly_bars(self, yearly: pd.DataFrame, partielles: set[int]) -> QFrame:
        # Titre dans le bandeau de la carte, comme dans Pecule (29/09/2026).
        # « Énergie » : le graphique montre quatre grandeurs, pas la seule
        # production (30/09/2026).
        card = Card(titre="Énergie par année civile")
        v = card.corps
        v.setContentsMargins(16, 10, 16, 14)
        canvas = MplCanvas(width=5, height=3.2, dpi=100)
        canvas.apply_theme(mpl_style(self.theme))
        ax = canvas.fig.add_subplot(111)
        xs = np.arange(len(yearly.index))
        w = 0.2
        # Libelles en clair, comme les en-tetes des Releves journaliers.
        b1 = ax.bar(xs - 1.5*w, yearly["production_kwh"], w,
                    label="Production", color=CC["production"])
        b2 = ax.bar(xs - 0.5*w, yearly["autoconsommation_kwh"], w,
                    label="Autoconsommation", color=CC["autoconso"])
        b3 = ax.bar(xs + 0.5*w, yearly["injection_kwh"], w,
                    label="Injection", color=CC["injection"])
        b4 = ax.bar(xs + 1.5*w, yearly["soutirage_kwh"], w,
                    label="Achat au réseau", color=CC["soutirage"])
        # Le chiffre de chaque barre (demande du 15/09/2026).
        chiffres_sur_barres(ax, [b1, b2, b3, b4])
        ax.set_xticks(xs)
        ax.set_xticklabels([f"{y}\n(partielle)" if int(y) in partielles else str(y)
                            for y in yearly.index])
        ax.set_ylabel("kWh")
        ax.yaxis.set_major_formatter(AXE_MILLIERS)
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
        # Titre dans le bandeau de la carte, comme dans Pecule (29/09/2026).
        card = Card(titre="Production mensuelle, année par année")
        v = card.corps
        v.setContentsMargins(16, 10, 16, 14)
        df_m = df.copy()
        df_m["mois"] = df_m.index.month
        df_m["annee"] = df_m.index.year
        pivot = df_m.pivot_table(values="production_kwh", index="mois",
                                  columns="annee", aggfunc="sum")
        # Un mois incomplet (mise en service, mois en cours) n'est pas trace :
        # avril 2022, deux jours de releves, tirait la courbe vers zero
        # (01/10/2026). Un mois compte s'il a un releve chaque jour.
        jours = df_m.groupby(["annee", "mois"]).size()
        incomplets = False
        for (annee, mois), nombre in jours.items():
            if nombre < pd.Period(year=int(annee), month=int(mois),
                                  freq="M").days_in_month:
                pivot.loc[mois, annee] = np.nan
                incomplets = True
        if pivot.isna().all().all():
            # Aucun mois complet : un graphique vide, sa legende et un axe
            # « 0, 0, −0 » n'apprenaient rien (audit du 04/10/2026).
            note = QLabel("La production mensuelle s'affichera ici dès votre "
                          "premier mois complet de relevés.")
            note.setObjectName("SectionSub")
            note.setWordWrap(True)
            v.addWidget(note)
            return card
        canvas = MplCanvas(width=5, height=3.2, dpi=100)
        canvas.apply_theme(mpl_style(self.theme))
        ax = canvas.fig.add_subplot(111)
        palette = COULEURS_ANNEES
        # La couleur ne porte jamais seule le sens (charte, 30/09/2026) :
        # chaque annee a aussi son trait et sa forme de point.
        traits = ["-", "--", "-.", ":"]
        points = ["o", "s", "^", "D", "v", "P"]
        for i, col in enumerate(pivot.columns):
            ax.plot(pivot.index, pivot[col], lw=2,
                    ls=traits[i % len(traits)], marker=points[i % len(points)],
                    color=palette[i % len(palette)], label=str(col))
        ax.set_xticks(range(1, 13))
        # Les mois comme sur les autres pages (« janv. », « sept. »).
        ax.set_xticklabels(["janv.", "févr.", "mars", "avr.", "mai", "juin",
                            "juil.", "août", "sept.", "oct.", "nov.", "déc."],
                           fontsize=8)
        # « kWh », comme l'axe du graphique voisin ; le titre de la carte dit
        # deja qu'il s'agit de production.
        ax.set_ylabel("kWh")
        ax.yaxis.set_major_formatter(AXE_MILLIERS)
        # Legende au-dessus du trace : en haut a droite, elle recouvrait les
        # points d'aout et de septembre (audit du 14/09/2026).
        # Trois annees par ligne au plus : cinq sur une seule ne tenaient pas,
        # la derniere s'affichait « 20. » (01/10/2026).
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0),
                  frameon=False, ncol=min(len(pivot.columns), 3))
        canvas.fig.tight_layout()
        v.addWidget(canvas)
        if incomplets:
            note = QLabel("Les mois incomplets (mise en service, mois en "
                          "cours) ne sont pas tracés.")
            note.setObjectName("SectionSub")
            note.setWordWrap(True)
            v.addWidget(note)
        return card
