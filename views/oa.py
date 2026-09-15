"""Vue Annees OA : recapitulatif par cycle de contrat (un an a partir de la
date de debut du contrat OA)."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

import calculations as calc
from gui_theme import CHART_COLORS as CC
from gui_theme import mpl_style
from gui_widgets import Card, MplCanvas, SectionTitle
from views._base import BaseView
from views._helpers import chiffres_sur_barres


class OAView(BaseView):
    utilise_periode = False  # recap de TOUS les cycles OA, quelle que soit la periode

    def populate(self, period: str) -> None:
        df_total = self.data.df
        oa = self.data.oa
        prime_an = calc.prime_annuelle(self.data.cfg["installation"]["puissance_kwc"], oa)
        rows = []
        avant_contrat = None
        for n_oa, g in df_total.groupby("annee_oa"):
            if n_oa == 0:
                # Jours anterieurs au contrat OA (mise en service 29/04/2022 ->
                # debut OA 28/06/2022) : ils etaient purement ignores ici, si
                # bien que le tableau ne totalisait pas toute la production.
                avant_contrat = {
                    "n": 0,
                    "periode": f"{g.index.min().strftime('%d/%m/%Y')} → "
                               f"{g.index.max().strftime('%d/%m/%Y')}",
                    "prod": g["production_kwh"].sum(),
                    "auto": g["autoconsommation_kwh"].sum(),
                    "inj":  g["injection_kwh"].sum(),
                    "revenu": g["revenu_vente_eur"].sum(),  # 0 : pas de contrat
                    "prime": 0.0,
                    "prime_a_venir": False,
                    "eco": g["economie_eur"].sum(),
                    "bilan": g["bilan_jour_eur"].sum(),
                }
                continue
            d, f = calc.oa_year_bounds(self.data.start_oa, int(n_oa))
            # La prime n'est encaissee qu'une fois l'annee OA terminee (facture
            # anniversaire EDF OA) : meme regle que la Synthese financiere.
            versee = calc.prime_est_versee(self.data.start_oa, int(n_oa), oa)
            eligible = 1 <= n_oa <= oa.prime_duree
            prime = prime_an if versee else 0.0
            rows.append({
                "n": int(n_oa),
                "periode": f"{d.strftime('%d/%m/%Y')} → {f.strftime('%d/%m/%Y')}",
                "prod": g["production_kwh"].sum(),
                "auto": g["autoconsommation_kwh"].sum(),
                "inj":  g["injection_kwh"].sum(),
                "revenu": g["revenu_vente_eur"].sum(),
                "prime": prime,
                "prime_a_venir": eligible and not versee,
                "eco": g["economie_eur"].sum(),
                "bilan": g["bilan_jour_eur"].sum() + prime,
            })

        self.layout_inner.addWidget(SectionTitle(
            "Années OA",
            f"Découpage {self.data.cycle_oa} - contrat sur {oa.duree_contrat} ans",
        ))

        if not rows and not avant_contrat:
            self.layout_inner.addWidget(self._empty_card("Aucune donnée."))
            return

        # Bar chart
        chart_card = Card()
        cv = QVBoxLayout(chart_card)
        cv.setContentsMargins(16, 14, 16, 14)
        cv.addWidget(QLabel("Production / Autoconso / Injection par année OA"))
        canvas = MplCanvas(width=8, height=3.2, dpi=100)
        canvas.apply_theme(mpl_style(self.theme))
        ax = canvas.fig.add_subplot(111)
        xs = np.arange(len(rows))
        w = 0.27
        b1 = ax.bar(xs - w, [r["prod"] for r in rows], w,
                    label="Production", color=CC["production"])
        b2 = ax.bar(xs, [r["auto"] for r in rows], w,
                    label="Autoconso", color=CC["autoconso"])
        b3 = ax.bar(xs + w, [r["inj"] for r in rows], w,
                    label="Injection", color=CC["injection"])
        ax.set_xticks(xs)
        ax.set_xticklabels([f"OA #{r['n']}" for r in rows])
        ax.set_ylabel("kWh")
        # Le chiffre de chaque barre (demande du 15/09/2026).
        chiffres_sur_barres(ax, [b1, b2, b3])
        # Legende au-dessus du trace : dedans, elle recouvrait les chiffres.
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0),
                  frameon=False, ncol=3)
        canvas.fig.tight_layout()
        cv.addWidget(canvas)
        self.layout_inner.addWidget(chart_card)

        # Tableau
        table_card = Card()
        tv = QVBoxLayout(table_card)
        tv.setContentsMargins(0, 0, 0, 0)
        cols = ["Année OA", "Période", "Prod (kWh)", "Auto (kWh)", "Inj (kWh)",
                "Revenu (€)", "Prime (€)", "Éco (€)", "Bilan (€)"]
        # La periode d'avant-contrat ouvre le tableau (mais pas le graphique,
        # qui compare des annees OA entre elles).
        lignes = ([avant_contrat] if avant_contrat else []) + rows
        table = QTableWidget(len(lignes), len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setShowGrid(False)
        for i, r in enumerate(lignes):
            # Prime pas encore encaissee : on l'affiche en clair sans la
            # compter dans le bilan, pour ne pas laisser croire a une recette.
            prime_txt = f"{r['prime']:.2f}".replace(".", ",")
            if r.get("prime_a_venir"):
                prime_txt = f"({prime_an:.2f} à venir)".replace(".", ",")
            items = [
                QTableWidgetItem("avant OA" if r["n"] == 0 else f"#{r['n']}"),
                QTableWidgetItem(r["periode"]),
                QTableWidgetItem(f"{r['prod']:.1f}".replace(".", ",")),
                QTableWidgetItem(f"{r['auto']:.1f}".replace(".", ",")),
                QTableWidgetItem(f"{r['inj']:.1f}".replace(".", ",")),
                QTableWidgetItem(f"{r['revenu']:.2f}".replace(".", ",")),
                QTableWidgetItem(prime_txt),
                QTableWidgetItem(f"{r['eco']:.2f}".replace(".", ",")),
                QTableWidgetItem(
                    f"{'+' if r['bilan'] >= 0 else '-'}{abs(r['bilan']):.2f}"
                    .replace(".", ",")),
            ]
            couleur_n = (self.theme["text_muted"] if r["n"] == 0
                         else self.theme["primary"])
            items[0].setForeground(self._color(couleur_n))
            f = QFont()
            f.setBold(True)
            items[0].setFont(f)
            if r["n"] == 0:
                items[1].setToolTip(
                    "Du raccordement au début du contrat EDF OA : l'injection "
                    "de cette période n'etait pas remuneree.")
            bilan_color = self.theme["credit"] if r["bilan"] >= 0 else self.theme["debit"]
            items[-1].setForeground(self._color(bilan_color))
            items[-1].setFont(f)
            for j in range(2, len(cols)):
                items[j].setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            for j, it in enumerate(items):
                table.setItem(i, j, it)
        # Colonnes reparties sur toute la largeur : avec la derniere seule
        # etiree, un grand vide la separait des autres (audit du 14/09/2026).
        # L'annee et la periode gardent la largeur de leur texte.
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.setFixedHeight(40 + len(lignes) * 36)
        tv.addWidget(table)
        self.layout_inner.addWidget(table_card)

        legendes = []
        if avant_contrat:
            legendes.append(
                "La ligne « avant OA » couvre du raccordement au début du "
                "contrat : l'électricité injectée pendant cette période "
                "n'était pas achetée par EDF OA, d'où un revenu nul."
            )
        if any(r.get("prime_a_venir") for r in rows):
            legendes.append(
                "Une prime « à venir » n'est pas encore encaissée : EDF OA la "
                "facture après la fin de l'année OA concernée. Elle n'entre "
                "donc pas dans le bilan de la ligne."
            )
        if legendes:
            note = QLabel("\n".join(legendes))
            note.setWordWrap(True)
            note.setStyleSheet(
                f"color: {self.theme['text_muted']}; font-size: 11px; padding-top: 6px;")
            self.layout_inner.addWidget(note)
        self.layout_inner.addStretch(1)

    def _color(self, hex_color: str):
        return QColor(hex_color)
