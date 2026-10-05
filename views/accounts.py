"""Vue Synthese financiere : postes financiers + evolution patrimoniale."""
from __future__ import annotations

import pandas as pd
from matplotlib.dates import DateFormatter, MonthLocator
from matplotlib.ticker import FuncFormatter
from PySide6.QtWidgets import QFrame, QLabel

import calculations as calc
from accords import accorde
from gui_theme import CHART_COLORS as CC
from gui_theme import mpl_style
from gui_widgets import AccountCard, Card, KpiCard, MplCanvas, SectionTitle, grid_row
from views._base import BaseView
from views._helpers import (
    PERIOD_ALL,
    amortissement,
    filter_period,
    fmt_date_fr,
    fmt_eur,
    libelle_periode,
    phrase_apres_contrat,
    poser_texte_court,
)


class AccountsView(BaseView):
    def populate(self, period: str) -> None:
        df = filter_period(self.data.df, period, self.data.start_oa)
        df_total = self.data.df
        if df_total.empty:
            self.layout_inner.addWidget(self._empty_card("Aucune donnée."))
            return

        revenu_cum = df_total["revenu_vente_eur"].sum()
        eco_cum = df_total["economie_eur"].sum()
        cout_cum = df_total["cout_reseau_eur"].sum()
        revenu_p = df["revenu_vente_eur"].sum() if not df.empty else 0
        eco_p = df["economie_eur"].sum() if not df.empty else 0
        cout_p = df["cout_reseau_eur"].sum() if not df.empty else 0

        cfg = self.data.cfg
        oa = self.data.oa
        # Primes, rythme des gains et remboursement : un seul calcul, partage
        # avec la barre « Installation remboursee » du tableau de bord.
        am = amortissement(self.data)
        prime_an = am["prime_an"]
        nb_oa = am["nb_primes_versees"]
        prime_versee = am["prime_versee"]
        prime_total = am["prime_totale"]

        invest = am["invest"]
        # Ce que l'installation a rapporte, moins ce qu'elle a coute. La
        # facture reseau n'y entre plus (decision de l'auteur, 14/09/2026) :
        # on la paierait meme sans panneaux, et plus cher ; ce que les
        # panneaux y changent est deja compte dans les economies. La
        # soustraire faisait afficher un bilan tres negatif sur la page meme qui
        # annoncait l'installation remboursee a 25 %.
        bilan_global = am["recupere"] - invest

        # La vraie date de depart des sommes : le premier releve. Le titre
        # disait la date du contrat, alors que les economies d'avant-contrat
        # y sont, et que rien d'avant les releves n'y est (audit du
        # 04/10/2026).
        self.layout_inner.addWidget(SectionTitle(
            "Postes financiers",
            f"Cumul depuis le premier relevé, le "
            f"{df_total.index.min():%d/%m/%Y}",
        ))

        date_mes = fmt_date_fr(cfg["installation"]["date_mise_en_service"])
        # Les montants sont des cumuls ; la ligne du dessous donne la part de
        # la periode choisie en haut, et la nomme (relecture du 29/09/2026 :
        # « sur période » ne disait pas laquelle, et sur toute la periode elle
        # repetait le montant). Sur toute la periode, elle se tait.
        quand = self._quand(period)

        def part(valeur: float, vide: str) -> str:
            if not quand:
                return ""
            if abs(valeur) < 0.005:
                return f"{vide} {quand}"
            return f"dont {fmt_eur(valeur, signed=True)} {quand}"

        # Vente et prime n'apparaissent que si le contrat les prevoit.
        vente = [AccountCard(
            "Vente",
            f"À {self.data.acheteur} — " + ("surplus injecté"
                                            if oa.type == "surplus"
                                            else "production vendue"),
            fmt_eur(revenu_cum, signed=True),
            part(revenu_p, "Aucune vente"),
            self.theme["credit"], "💶", "credit")] if self.data.vend else []
        prime = [AccountCard("Prime à l'autoconsommation",
                        f"Versée sur {oa.prime_duree} "
                        f"an{'s' if oa.prime_duree > 1 else ''}, à chaque "
                        "anniversaire du contrat",
                        fmt_eur(prime_versee, signed=True),
                        f"{nb_oa}/{oa.prime_duree} "
                        f"{accorde(oa.prime_duree, 'versement')} — "
                        f"total prévu {fmt_eur(prime_total)}",
                        self.theme["credit"], "🎁", "credit")] if oa.prime_duree else []
        accounts = vente + prime + [
            AccountCard("Économies", "Coût évité — kWh non achetés",
                        fmt_eur(eco_cum, signed=True),
                        part(eco_p, "Aucune économie"),
                        self.theme["credit"], "🐷", "credit"),
            AccountCard("Achat au réseau", "Électricité + abonnement",
                        fmt_eur(-cout_cum, signed=True),
                        part(-cout_p, "Aucun achat"),
                        self.theme["debit"], "🔌", "debit"),
            AccountCard("Investissement", f"Achat de l'installation — {date_mes}",
                        fmt_eur(-invest, signed=True),
                        "Amorti progressivement",
                        self.theme["debit"], "🏡", "debit"),
            AccountCard("Bilan de l'installation",
                        self._recettes().capitalize() + " − installation",
                        fmt_eur(bilan_global, signed=True),
                        "Amortissement atteint" if bilan_global >= 0 else "Amortissement en cours",
                        self.theme["credit"] if bilan_global >= 0 else self.theme["debit"],
                        "⚖️", "credit" if bilan_global >= 0 else "debit"),
        ]
        # 2 lignes de 3 cartes
        for i in range(0, 6, 3):
            self.layout_inner.addLayout(grid_row(accounts[i:i+3]))

        self.layout_inner.addWidget(
            self._remboursement_card(df_total, prime_an, oa, invest, am))

        # KPI synthese : calcul detaille et justifie dans amortissement()
        # (views/_helpers.py), partage avec le tableau de bord.
        annees = am["annees"]
        gains_an = am["gains_an"]
        prime_totale = am["prime_totale"]
        reste_a_amortir = am["reste_a_amortir"]
        roi_an = am["roi_an"]
        # Decimales a la francaise, comme partout ailleurs dans l'app.
        def _ans(x: float) -> str:
            return f"{x:.1f}".replace(".", ",")

        # Le bilan net n'est plus repete ici : il est deja dans la carte
        # « Bilan net global » du haut, meme calcul (relecture du 29/09/2026).
        gains = "vente + économies" if self.data.vend else "économies"
        manque = am["jours_avant_estimation"]
        if manque:
            # Moins d'un an de releves : rien a extrapoler (voir
            # amortissement()). On dit quand l'estimation viendra.
            s = "s" if manque > 1 else ""
            sous_titre_gains = (f"{gains} : estimés après un an de relevés "
                                f"(encore {manque} jour{s})")
        else:
            sous_titre_gains = (f"{gains}, moyenne sur {_ans(annees)} "
                                + ("an" if annees < 2 else "ans"))
        self.layout_inner.addLayout(grid_row([
            KpiCard("Gains récurrents par an",
                    fmt_eur(gains_an) if gains_an is not None else "—",
                    sous_titre_gains, "credit"),
            # « Temps de retour » et non « ROI » (sigle anglais, relecture du
            # 29/09/2026).
            KpiCard("Temps de retour", f"{_ans(roi_an)} ans" if roi_an else "—",
                    f"{fmt_eur(reste_a_amortir)} à amortir"
                    + (f" (prime de {fmt_eur(prime_totale)} déduite)"
                       if prime_totale else ""), "primary"),
        ]))
        note = QLabel(
            "Le temps de retour suppose que vos gains annuels restent au "
            "rythme observé jusqu'ici."
            + (" Il ne compte que les gains qui se répètent : la prime "
               "à l'autoconsommation, versée sur "
               f"{oa.prime_duree} an{'s' if oa.prime_duree > 1 else ''} "
               "seulement, est déduite du capital à amortir "
               "au lieu d'être comptée comme un revenu perpétuel."
               if oa.prime_duree else "")
            + (phrase_apres_contrat(
                self.data, pd.Timestamp(df_total.index.min())
                + pd.Timedelta(days=round(roi_an * 365.25)))
               if roi_an else "")
        )
        note.setStyleSheet(
            f"color: {self.theme['text_muted']}; font-size: 11px; padding-top: 4px;")
        poser_texte_court(self.layout_inner, note)
        self.layout_inner.addStretch(1)

    @staticmethod
    def _quand(period: str) -> str:
        """La periode choisie, a glisser dans une phrase : « en septembre
        2026 », « en 2025 », « sur l'année OA #2 » ; rien pour toute la
        periode."""
        if not period or period == PERIOD_ALL:
            return ""
        if period.startswith("month-"):
            return "en " + libelle_periode(period).lower()
        if period.startswith("year-"):
            return "en " + period.split("-")[1]
        if period.startswith("oa-"):
            return "sur l'année OA #" + period.split("-")[1]
        return ""

    def _recettes(self) -> str:
        """« ventes + économies + primes », selon ce que le contrat prévoit."""
        parts = (["ventes"] if self.data.vend else []) + ["économies"]
        if self.data.oa.prime_duree:
            parts.append("primes")
        return " + ".join(parts)

    def _remboursement_card(self, df_total: pd.DataFrame, prime_an: float,
                            oa, invest: float, am: dict) -> QFrame:
        """Ce que l'installation a rapporte (ventes + economies + primes),
        face a son cout, avec la projection au rythme actuel.

        Remplace « Evolution patrimoniale » (audit du 14/09/2026) : cinq
        courbes sur une echelle allant de moins le cout de l'installation a
        quelques milliers,
        ou l'investissement ecrasait tout le reste. La facture reseau n'y
        figure plus : ce n'est pas un cout de l'installation (on la paierait
        sans panneaux), et les economies en tiennent deja compte.
        """
        # Titre dans le bandeau de la carte, comme dans Pecule (29/09/2026).
        card = Card(titre="Remboursement de l'installation",
                    sous_titre="Ce qu'elle vous a rapporté, face à ce "
                               "qu'elle a coûté")
        v = card.corps
        v.setContentsMargins(16, 10, 16, 14)

        monthly_rev = df_total["revenu_vente_eur"].resample("MS").sum().cumsum()
        monthly_eco = df_total["economie_eur"].resample("MS").sum().cumsum()

        # La prime de l'annee OA n est versee a la FIN de cette annee
        # (facture anniversaire EDF OA), pas a son debut.
        prime_dates = []
        for n in range(1, oa.prime_duree + 1):
            _, fin = calc.oa_year_bounds(self.data.start_oa, n)
            if fin <= df_total.index.max().date():
                prime_dates.append(pd.Timestamp(fin))
        if prime_dates:
            prime_series = pd.Series([prime_an] * len(prime_dates), index=prime_dates)
            prime_monthly = (
                prime_series.resample("MS").sum()
                .reindex(monthly_rev.index, fill_value=0).cumsum()
            )
        else:
            prime_monthly = pd.Series(0.0, index=monthly_rev.index)

        recupere = monthly_rev + monthly_eco + prime_monthly

        canvas = MplCanvas(width=8, height=3.6, dpi=100)
        canvas.setMinimumHeight(320)
        canvas.apply_theme(mpl_style(self.theme))
        ax = canvas.fig.add_subplot(111)
        x = recupere.index
        ax.fill_between(x, 0, recupere.values, color=CC["autoconso"], alpha=0.18)
        ax.plot(x, recupere.values, color=CC["autoconso"], lw=2.5,
                marker="o" if len(x) == 1 else None,
                label=f"Récupéré : {self._recettes()}")
        if len(x) == 1:
            # Un seul mois de releves : face a un point seul, matplotlib
            # etalait l'axe sur quatre ans et la courbe disparaissait. On
            # resserre l'axe autour de ce mois.
            ax.set_xlim(x[0] - pd.DateOffset(months=1),
                        x[0] + pd.DateOffset(months=1))
            # Un repere par mois, ecrit « 09/2026 » et non « 2026-09-01 ».
            ax.xaxis.set_major_locator(MonthLocator())
            ax.xaxis.set_major_formatter(DateFormatter("%m/%Y"))
        # Chaque versement de la prime fait une marche dans la courbe, qui
        # passait pour une anomalie. La marche reste a sa vraie date (avant le
        # versement, l'argent n'etait pas la) mais elle est signalee : un point
        # sur chaque versement, et UNE etiquette sur le dernier - versee sur
        # 5 ans, la prime ferait sinon cinq etiquettes qui se chevauchent.
        mois_primes = [d.to_period("M").to_timestamp() for d in prime_dates]
        mois_primes = [m for m in mois_primes if m in recupere.index]
        if mois_primes:
            y_primes = [recupere.loc[m] for m in mois_primes]
            ax.plot(mois_primes, y_primes, ls="none", marker="o", ms=5,
                    color=CC["autoconso"], gid="versements_prime")
            n = len(mois_primes)
            detail = (fmt_eur(prime_an, signed=True) if n == 1
                      else f"{n} versements de {fmt_eur(prime_an)}")
            ax.annotate(f"Prime à l'autoconsommation\n{detail}",
                        xy=(mois_primes[-1], y_primes[-1]), xytext=(0, 14),
                        textcoords="offset points", ha="center", va="bottom",
                        fontsize=8, color=self.theme["text_secondary"],
                        arrowprops={"arrowstyle": "-", "lw": 0.8,
                                    "color": self.theme["text_secondary"]})
        ax.axhline(invest, color=CC["soutirage"], lw=1.5, ls="--",
                   label=f"Coût de l'installation ({fmt_eur(invest)})")
        # Projection au rythme actuel : la meme echeance que la barre du
        # tableau de bord et le ROI ci-dessous (amortissement()).
        roi_an = am["roi_an"] if am else None
        if roi_an and len(x) and recupere.iloc[-1] < invest:
            fin = (pd.Timestamp(df_total.index.min())
                   + pd.Timedelta(days=round(roi_an * 365.25)))
            if fin > x[-1]:
                ax.plot([x[-1], fin], [recupere.iloc[-1], invest],
                        color=CC["autoconso"], lw=1.5, ls=":",
                        label="Projection au rythme actuel")
                ax.annotate(f"≈ {fin.year}", xy=(fin, invest), xytext=(0, 8),
                            textcoords="offset points", ha="center",
                            fontsize=9, color=self.theme["text_secondary"])
        ax.set_ylim(0, invest * 1.15)
        # « 10 000 € » : les milliers separes comme dans les montants
        # (relecture du 29/09/2026), et l'unite sur chaque graduation plutot
        # qu'un « € » couche le long de l'axe (30/09/2026).
        ax.yaxis.set_major_formatter(FuncFormatter(
            lambda valeur, _pos: f"{valeur:,.0f} €".replace(",", " ")))
        # Au milieu a gauche, la zone vide du graphique : en haut, la legende
        # chevauchait la ligne du cout de l'installation.
        ax.legend(loc="center left", frameon=False, fontsize=9)
        canvas.fig.tight_layout()
        v.addWidget(canvas)
        return card
