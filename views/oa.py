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
)

import calculations as calc
from gui_theme import CHART_COLORS as CC
from gui_theme import mpl_style
from gui_widgets import Card, MplCanvas, SectionTitle
from views._base import BaseView
from views._helpers import chiffres_sur_barres, du_au, hauteur_exacte, poser_texte_court
from views.transactions import texte_bilan


def nombre_fr(valeur: float) -> str:
    """« 2 354,4 » : une decimale, milliers separes par une espace, comme
    partout ailleurs (c'etait « 2354,4 », 30/09/2026)."""
    return f"{valeur:,.1f}".replace(",", " ").replace(".", ",")


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
                # Jours anterieurs au contrat OA (entre la mise en service et
                # le debut du contrat) : ils etaient purement ignores ici, si
                # bien que le tableau ne totalisait pas toute la production.
                avant_contrat = {
                    "n": 0,
                    "periode": du_au(g.index.min(), g.index.max()),
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
                "periode": du_au(d, f),
                "prod": g["production_kwh"].sum(),
                "auto": g["autoconsommation_kwh"].sum(),
                "inj":  g["injection_kwh"].sum(),
                "revenu": g["revenu_vente_eur"].sum(),
                "prime": prime,
                "prime_a_venir": eligible and not versee,
                "eco": g["economie_eur"].sum(),
                # Sans la prime, qui a sa colonne : le meme « Bilan
                # électricité » que le Tableau de bord sur la meme annee
                # (choix de l'auteur, 05/10/2026).
                "bilan": g["bilan_jour_eur"].sum(),
            })

        # Sans titre : il redisait celui de la page (30/09/2026).
        self.layout_inner.addWidget(SectionTitle(
            "",
            f"Découpage {self.data.cycle_oa} — contrat sur {oa.duree_contrat} ans",
        ))

        if not rows and not avant_contrat:
            self.layout_inner.addWidget(self._empty_card("Aucune donnée."))
            return

        # Bar chart
        # Titre dans le bandeau de la carte, comme dans Pecule (29/09/2026).
        chart_card = Card(titre="Production, autoconsommation et injection par année OA")
        cv = chart_card.corps
        cv.setContentsMargins(16, 10, 16, 14)
        canvas = MplCanvas(width=8, height=3.2, dpi=100)
        canvas.apply_theme(mpl_style(self.theme))
        ax = canvas.fig.add_subplot(111)
        xs = np.arange(len(rows))
        w = 0.27
        b1 = ax.bar(xs - w, [r["prod"] for r in rows], w,
                    label="Production", color=CC["production"])
        b2 = ax.bar(xs, [r["auto"] for r in rows], w,
                    label="Autoconsommation", color=CC["autoconso"])
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
        # Titre dans le bandeau, comme les autres cartes (30/09/2026).
        table_card = Card(titre="Détail par année OA")
        tv = table_card.corps
        tv.setContentsMargins(0, 0, 0, 0)
        cols = ["Année OA", "Période", "Production\n(kWh)",
                "Autoconsommation\n(kWh)", "Injection\n(kWh)", "Vente\n(€)",
                "Prime\n(€)", "Économies\n(€)", "Bilan\nélectricité (€)"]
        # L'annee la plus recente en haut, comme la page TVA (27/09/2026) :
        # c'est elle qu'on vient voir. La periode d'avant-contrat, la plus
        # ancienne, ferme donc le tableau (elle reste hors du graphique, qui
        # compare des annees OA entre elles et garde l'ordre du temps).
        lignes = list(reversed(rows)) + ([avant_contrat] if avant_contrat else [])
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
                QTableWidgetItem(nombre_fr(r["prod"])),
                QTableWidgetItem(nombre_fr(r["auto"])),
                QTableWidgetItem(nombre_fr(r["inj"])),
                QTableWidgetItem(f"{r['revenu']:.2f}".replace(".", ",")),
                QTableWidgetItem(prime_txt),
                QTableWidgetItem(f"{r['eco']:.2f}".replace(".", ",")),
                # Meme ecriture que les Releves : jamais « -0,00 ».
                QTableWidgetItem(texte_bilan(r["bilan"])[0]),
            ]
            # En noir : en bleu gras, le numero passait pour un lien
            # cliquable (30/09/2026).
            couleur_n = (self.theme["text_muted"] if r["n"] == 0
                         else self.theme["text_primary"])
            items[0].setForeground(QColor(couleur_n))
            f = QFont()
            f.setBold(True)
            items[0].setFont(f)
            if r["n"] == 0:
                items[1].setToolTip(
                    "Du raccordement au début du contrat de vente : "
                    "l'injection de cette période n'était pas rémunérée.")
            items[-1].setForeground(
                QColor(self.theme[texte_bilan(r["bilan"])[1]]))
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
        # « Autoconsommation » en toutes lettres (30/09/2026) : a part egale,
        # sa colonne etait trop etroite et l'en-tete coupe.
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        # La prime aussi : « (180,00 à venir) » est plus long qu'un montant
        # et sortait coupe (« (180,00 à v… »).
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        # Une ligne par annee, toutes de la meme hauteur : sans cela,
        # « (180,00 à venir) » etait mesure comme s'il passait a la ligne.
        table.setWordWrap(False)
        hauteur_exacte(table)
        tv.addWidget(table)
        self.layout_inner.addWidget(table_card)

        legendes = []
        if avant_contrat:
            legendes.append(
                "La ligne « avant OA » couvre du raccordement au début du "
                "contrat : l'électricité injectée pendant cette période "
                f"n'était pas achetée par {self.data.acheteur}, d'où un "
                "revenu nul."
            )
        if any(r.get("prime_a_venir") for r in rows):
            legendes.append(
                "Une prime « à venir » n'est pas encore encaissée : "
                f"{self.data.acheteur} la facture après la fin de l'année OA "
                "concernée."
            )
        if legendes:
            note = QLabel("\n".join(legendes))
            # Lignes courtes, comme la Notice et la page TVA.
            note.setStyleSheet(
                f"color: {self.theme['text_muted']}; font-size: 11px; padding-top: 6px;")
            poser_texte_court(self.layout_inner, note)
        self.layout_inner.addStretch(1)

