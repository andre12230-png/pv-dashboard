"""Vue de comparaison : le contrat en cours face a une offre de reference.

Les noms des deux offres (« Octopus Go » et « EDF Tarif Bleu » chez l'auteur)
etaient ecrits en dur ici : la vue annoncait « Octopus vs EDF » a qui est chez
un tout autre fournisseur. Ils viennent maintenant de config.yaml, cles `nom`
et `offre` des sections contrat_hphc et comparaison_edf.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

import calculations as calc
from gui_theme import CHART_COLORS as CC
from gui_theme import mpl_style
from gui_widgets import Card, KpiCard, MplCanvas, SectionTitle, grid_row
from views._base import BaseView
from views._helpers import fmt_date_fr, fmt_eur, fmt_prix_kwh, label_mois_fr


class OctopusEdfView(BaseView):
    """Compare le cout reel du contrat en cours a une offre de reference."""

    utilise_periode = False  # couvre toujours la periode depuis la bascule

    def populate(self, period: str) -> None:
        df = self.data.df
        ref = self.data.edf_ref
        comp = calc.comparaison_octopus_edf(df, ref)
        # Noms d'affichage : le court pour les cartes, le long pour les titres.
        mien, mon_offre = self.data.fournisseur
        autre, autre_offre = self.data.fournisseur_reference
        bascule = calc.CUTOFF_OCTOPUS

        if comp.empty:
            self.layout_inner.addWidget(self._empty_card(
                f"Aucune donnée depuis le passage en heures pleines / creuses "
                f"({bascule:%d/%m/%Y})."))
            self.layout_inner.addStretch(1)
            return

        cout_octopus = comp["cout_octopus_eur"].sum()
        cout_base = comp["cout_edf_base_eur"].sum()
        cout_hphc = comp["cout_edf_hphc_eur"].sum()
        gain_base = comp["gain_vs_base_eur"].sum()
        gain_hphc = comp["gain_vs_hphc_eur"].sum()
        jours = len(comp)
        par_an = 365.25 / jours if jours else 0.0

        options = {mon_offre: cout_octopus,
                   f"{autre} Base": cout_base,
                   f"{autre} HP/HC": cout_hphc}
        gagnant = min(options, key=options.get)

        # Qui a toujours ete en heures creuses n'a « change » de rien : sa
        # periode commence a la mise en service.
        try:
            mise_en_service = pd.Timestamp(self.data.date_mise_en_service)
        except (TypeError, ValueError):
            mise_en_service = None
        if mise_en_service is not None and bascule <= mise_en_service:
            depuis = f"Depuis la mise en service du {mise_en_service:%d/%m/%Y}"
        else:
            depuis = (f"Depuis le passage en heures pleines / creuses du "
                      f"{bascule:%d/%m/%Y}")
        self.layout_inner.addWidget(SectionTitle(
            f"{mon_offre} vs {autre_offre}", f"{depuis} - {jours} jour(s)",
        ))

        self.layout_inner.addWidget(SectionTitle("Coût sur la période"))
        self.layout_inner.addLayout(grid_row([
            KpiCard(f"{mon_offre} (actuel)", fmt_eur(cout_octopus),
                    "votre contrat", "primary"),
            KpiCard(f"{autre} Base", fmt_eur(cout_base),
                    "option prix unique", "neutral"),
            KpiCard(f"{autre} HP/HC", fmt_eur(cout_hphc),
                    "option HP/HC", "neutral"),
        ]))

        self.layout_inner.addWidget(SectionTitle(f"Économie grâce à {mien}"))
        self.layout_inner.addLayout(grid_row([
            KpiCard(f"vs {autre} Base", fmt_eur(gain_base, signed=True),
                    f"~{fmt_eur(gain_base * par_an, signed=True)}/an",
                    "credit" if gain_base >= 0 else "debit"),
            KpiCard(f"vs {autre} HP/HC", fmt_eur(gain_hphc, signed=True),
                    f"~{fmt_eur(gain_hphc * par_an, signed=True)}/an",
                    "credit" if gain_hphc >= 0 else "debit"),
            KpiCard("Offre la moins chère", gagnant,
                    "sur la période analysée",
                    "credit" if gagnant == mon_offre else "warm"),
        ]))

        self.layout_inner.addWidget(self._chart_mensuel(comp, mien, autre))
        self.layout_inner.addWidget(
            self._carte_hypotheses(ref, mon_offre, autre_offre))
        self.layout_inner.addStretch(1)

    def _chart_mensuel(self, comp: pd.DataFrame, mien: str,
                       autre: str) -> QFrame:
        card = Card()
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 14, 16, 14)
        v.addWidget(SectionTitle("Coût mensuel comparé (€)"))
        m = comp[["cout_octopus_eur", "cout_edf_hphc_eur",
                  "cout_edf_base_eur"]].resample("MS").sum()

        canvas = MplCanvas(width=8, height=3.2, dpi=100)
        canvas.apply_theme(mpl_style(self.theme))
        ax = canvas.fig.add_subplot(111)
        x = np.arange(len(m.index))
        w = 0.27
        b1 = ax.bar(x - w, m["cout_octopus_eur"], w, label=mien,
                    color=CC["primary"])
        b2 = ax.bar(x, m["cout_edf_hphc_eur"], w, label=f"{autre} HP/HC",
                    color=CC["injection"])
        b3 = ax.bar(x + w, m["cout_edf_base_eur"], w, label=f"{autre} Base",
                    color="#94a3b8")
        ax.set_xticks(x)
        if len(m.index) > 12:
            # Au-dela d'un an, les noms complets (« Janvier 2024 ») se
            # chevauchaient sous l'axe : mois abrege et annee sur deux
            # chiffres, poses debout (vu sur des donnees de 33 mois,
            # 15/09/2026).
            courts = ("janv.", "févr.", "mars", "avr.", "mai", "juin",
                      "juil.", "août", "sept.", "oct.", "nov.", "déc.")
            ax.set_xticklabels([f"{courts[d.month - 1]} {d:%y}" for d in m.index],
                               rotation=90)
        else:
            ax.set_xticklabels([label_mois_fr(d.to_period("M")) for d in m.index],
                               rotation=20, ha="right")
        ax.set_ylabel("€")
        # Legende au-dessus du trace : dedans, elle recouvrait les barres.
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0),
                  frameon=False, ncol=3)
        # Les montants au-dessus des barres restent affiches (l'auteur y
        # tient) : a l'horizontale jusqu'a un an ; au-dela, les trois chiffres
        # d'un meme mois se chevaucheraient, on les pose debout, un peu plus
        # petits. La marge du haut evite de couper ceux des plus hautes barres.
        debout = len(m.index) > 12
        for b in (b1, b2, b3):
            ax.bar_label(b, fmt="%.0f", padding=2,
                         rotation=90 if debout else 0,
                         fontsize=8 if debout else 10)
        ax.margins(y=0.18 if debout else 0.10)
        canvas.fig.tight_layout()
        v.addWidget(canvas)
        return card

    def _carte_hypotheses(self, ref: list[dict], mon_offre: str,
                          autre_offre: str) -> QFrame:
        card = Card()
        v = QVBoxLayout(card)
        v.setContentsMargins(20, 14, 20, 16)
        titre = QLabel("Hypothèses du calcul")
        titre.setStyleSheet("font-weight: 700; font-size: 13px;")
        v.addWidget(titre)
        # Une phrase par grille de reference : elle change en cours d'annee
        # (revision du tarif reglemente au 1er fevrier et au 1er aout).
        grilles = " ".join(
            f"Du {fmt_date_fr(p['debut'])} "
            f"{('au ' + fmt_date_fr(p['fin'])) if p.get('fin') else '(en cours)'} : "
            f"abonnement {fmt_eur(p['abonnement'])}/mois, "
            f"Base {fmt_prix_kwh(p['prix_base'])}, "
            f"HP {fmt_prix_kwh(p['prix_hp'])} et HC {fmt_prix_kwh(p['prix_hc'])}."
            for p in ref
        )
        txt = QLabel(
            f"Le coût {mon_offre} est calculé sur vos relevés HP/HC réels. Les "
            f"coûts de comparaison sont estimés à partir de la grille "
            f"{autre_offre} en vigueur à chaque date. {grilles} "
            "Attention : le scénario heures pleines / creuses reprend votre "
            "répartition HC/HP actuelle, or les plages d'heures creuses de "
            f"{autre_offre} diffèrent de celles de {mon_offre} : ce scénario "
            "est donc indicatif. Valeurs modifiables dans config.yaml, section "
            "comparaison_edf."
        )
        txt.setWordWrap(True)
        txt.setStyleSheet(f"color: {self.theme['text_muted']}; font-size: 12px;")
        v.addWidget(txt)
        return card
