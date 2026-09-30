"""Vue de comparaison : le contrat en cours face a une offre de reference.

Les noms des deux offres (« Octopus Go » et « EDF Tarif Bleu » chez l'auteur)
etaient ecrits en dur ici : la vue annoncait « Octopus vs EDF » a qui est chez
un tout autre fournisseur. Ils viennent maintenant de config.yaml, cles `nom`
et `offre` des sections contrat_hphc et comparaison_edf.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from PySide6.QtWidgets import QFrame, QLabel

import calculations as calc
from gui_theme import CHART_COLORS as CC
from gui_theme import mpl_style
from gui_widgets import Card, KpiCard, MplCanvas, SectionTitle, grid_row
from views._base import BaseView
from views._helpers import (
    chiffres_sur_barres,
    fmt_date_fr,
    fmt_eur,
    fmt_prix_kwh,
    nombre_de_jours,
    poser_texte_court,
)


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
        # Sans titre : il redisait celui de la page (30/09/2026).
        self.layout_inner.addWidget(SectionTitle(
            "", f"{depuis} — {nombre_de_jours(jours)}",
        ))

        self.layout_inner.addWidget(SectionTitle("Coût sur la période"))
        self.layout_inner.addLayout(grid_row([
            # « (actuel) » s'accordait au hasard avec le nom de l'offre.
            KpiCard(f"{mon_offre} — votre contrat", fmt_eur(cout_octopus),
                    "contrat en cours", "primary"),
            KpiCard(f"{autre} Base", fmt_eur(cout_base),
                    "option prix unique", "neutral"),
            KpiCard(f"{autre} HP/HC", fmt_eur(cout_hphc),
                    "option HP/HC", "neutral"),
        ]))

        self.layout_inner.addWidget(SectionTitle(f"Économie (ou surcoût) avec {mien}"))
        self.layout_inner.addLayout(grid_row([
            KpiCard(f"Par rapport à {autre} Base", fmt_eur(gain_base, signed=True),
                    f"soit environ {fmt_eur(gain_base * par_an, signed=True)} par an",
                    "credit" if gain_base >= 0 else "debit"),
            KpiCard(f"Par rapport à {autre} HP/HC", fmt_eur(gain_hphc, signed=True),
                    f"soit environ {fmt_eur(gain_hphc * par_an, signed=True)} par an",
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
        # Titre dans le bandeau de la carte, comme dans Pecule (29/09/2026).
        card = Card(titre="Coût mensuel comparé (€)")
        v = card.corps
        v.setContentsMargins(16, 10, 16, 14)
        m = comp[["cout_octopus_eur", "cout_edf_hphc_eur",
                  "cout_edf_base_eur"]].resample("MS").sum()
        # Un graphique par annee civile, la plus recente en haut, comme les
        # tableaux de la page TVA (29/09/2026). Sur 33 mois dans un seul
        # graphique, les trois montants de chaque mois se chevauchaient et
        # les mois etaient ecrits debout ; l'auteur tient aux montants : on
        # leur donne de la place. Meme echelle pour toutes les annees, pour
        # qu'elles se comparent d'un coup d'oeil.
        plafond = float(m.max().max()) if not m.empty else 0.0
        for rang, annee in enumerate(sorted(set(m.index.year), reverse=True)):
            v.addWidget(self._graphique_annee(
                m[m.index.year == annee], annee, mien, autre, plafond,
                avec_legende=(rang == 0)))
        return card

    MOIS_COURTS = ("janv.", "févr.", "mars", "avr.", "mai", "juin",
                   "juil.", "août", "sept.", "oct.", "nov.", "déc.")

    def _graphique_annee(self, mois: pd.DataFrame, annee: int, mien: str,
                         autre: str, plafond: float,
                         avec_legende: bool) -> MplCanvas:
        """Les douze mois d'une annee : un emplacement par mois, meme vide
        (une annee commencee en juin garde janvier a mai), les trois couts
        cote a cote, chacun avec son montant."""
        canvas = MplCanvas(width=8, height=2.8, dpi=100)
        canvas.setMinimumHeight(250)
        canvas.apply_theme(mpl_style(self.theme))
        ax = canvas.fig.add_subplot(111)
        x = np.array([d.month - 1 for d in mois.index])
        w = 0.3
        b1 = ax.bar(x - w, mois["cout_octopus_eur"], w, label=mien,
                    color=CC["primary"])
        b2 = ax.bar(x, mois["cout_edf_hphc_eur"], w, label=f"{autre} HP/HC",
                    color=CC["injection"])
        b3 = ax.bar(x + w, mois["cout_edf_base_eur"], w, label=f"{autre} Base",
                    color="#94a3b8")
        ax.set_xticks(range(12))
        ax.set_xticklabels(self.MOIS_COURTS, rotation=0)
        ax.set_xlim(-0.6, 11.6)
        # Pas de « € » couche le long de l'axe : le titre de la carte dit
        # deja l'unite (30/09/2026).
        ax.set_title(str(annee), loc="left", fontsize=10, fontweight="bold")
        if avec_legende:
            # Au-dessus du trace : dedans, elle recouvrait les barres.
            ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0),
                      frameon=False, ncol=3)
        # Les montants : a plat s'ils tiennent a l'ecran, debout sinon (regle
        # commune). Hauteur fixe, commune a toutes les annees, avec de quoi
        # loger les chiffres des plus hautes barres.
        chiffres_sur_barres(ax, [b1, b2, b3])
        ax.set_ylim(0, plafond * 1.25 if plafond > 0 else 1)
        canvas.fig.tight_layout()
        return canvas

    def _carte_hypotheses(self, ref: list[dict], mon_offre: str,
                          autre_offre: str) -> QFrame:
        # Titre dans le bandeau de la carte, comme les autres (29/09/2026 ;
        # c'etait un texte gras dans le corps).
        card = Card(titre="Hypothèses du calcul")
        v = card.corps
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
        txt.setStyleSheet(f"color: {self.theme['text_muted']}; font-size: 12px;")
        poser_texte_court(v, txt)
        return card
