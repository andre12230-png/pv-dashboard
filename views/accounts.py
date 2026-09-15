"""Vue Synthese financiere : postes financiers + evolution patrimoniale."""
from __future__ import annotations

import pandas as pd
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

import calculations as calc
from gui_theme import CHART_COLORS as CC
from gui_theme import mpl_style
from gui_widgets import AccountCard, Card, KpiCard, MplCanvas, SectionTitle, grid_row
from views._base import BaseView
from views._helpers import amortissement, filter_period, fmt_date_fr, fmt_eur


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
        # soustraire faisait afficher -21 580 EUR sur la page meme qui
        # annoncait l'installation remboursee a 25 %.
        bilan_global = am["recupere"] - invest

        self.layout_inner.addWidget(SectionTitle(
            "Postes financiers",
            f"Cumul depuis {self.data.start_oa.strftime('%d/%m/%Y')}",
        ))

        date_mes = fmt_date_fr(cfg["installation"]["date_mise_en_service"])
        accounts = [
            AccountCard("Vente EDF OA", "Recettes — surplus injecté",
                        fmt_eur(revenu_cum, signed=True),
                        f"+{fmt_eur(revenu_p)} sur période" if revenu_p > 0 else "Aucune recette",
                        self.theme["credit"], "💶", "#dbeafe"),
            AccountCard("Prime autoconso",
                        f"Versée sur {oa.prime_duree} "
                        f"an{'s' if oa.prime_duree > 1 else ''} (anniv. OA)",
                        fmt_eur(prime_versee, signed=True),
                        f"{nb_oa}/{oa.prime_duree} versement(s) - "
                        f"total prévu {fmt_eur(prime_total)}",
                        self.theme["credit"], "🎁", "#dcfce7"),
            AccountCard("Économies autoconso", "Coût évité - kWh non achetés",
                        fmt_eur(eco_cum, signed=True),
                        f"+{fmt_eur(eco_p)} sur période" if eco_p > 0 else "Aucune économie",
                        self.theme["credit"], "🐷", "#d1fae5"),
            AccountCard("Facture réseau", "Dépenses - électricité + abonnement",
                        fmt_eur(-cout_cum, signed=True),
                        f"-{fmt_eur(cout_p)} sur période" if cout_p > 0 else "Aucune dépense",
                        self.theme["debit"], "🔌", "#fee2e2"),
            AccountCard("Investissement", f"Achat installation - {date_mes}",
                        fmt_eur(-invest, signed=True),
                        "Amorti progressivement",
                        self.theme["debit"], "🏡", "#e5e7eb"),
            AccountCard("Bilan net global",
                        "Ventes + économies + primes − installation",
                        fmt_eur(bilan_global, signed=True),
                        "Amortissement atteint" if bilan_global >= 0 else "Amortissement en cours",
                        self.theme["credit"] if bilan_global >= 0 else self.theme["debit"],
                        "⚖️", "#e0e7ff"),
        ]
        # 2 lignes de 3 cartes
        for i in range(0, 6, 3):
            self.layout_inner.addLayout(grid_row(accounts[i:i+3]))

        self.layout_inner.addWidget(SectionTitle(
            "Remboursement de l'installation",
            "Ce qu'elle vous a rapporté, face à ce qu'elle a coûté"))
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

        self.layout_inner.addLayout(grid_row([
            KpiCard("Gains récurrents par an", fmt_eur(gains_an),
                    f"vente OA + économies, moyenne sur {_ans(annees)} an(s)",
                    "credit"),
            KpiCard("ROI estimé", f"{_ans(roi_an)} ans" if roi_an else "—",
                    f"{fmt_eur(reste_a_amortir)} à amortir "
                    f"(prime de {fmt_eur(prime_totale)} déduite)", "primary"),
            KpiCard("Bilan net actuel", fmt_eur(bilan_global, signed=True),
                    "ventes + économies + primes − installation",
                    "credit" if bilan_global >= 0 else "debit"),
        ]))
        note = QLabel(
            "Le ROI suppose que vos gains annuels restent au rythme observé "
            "jusqu'ici. Il ne compte que les gains qui se répètent : la prime "
            "à l'autoconsommation, versée sur "
            f"{oa.prime_duree} an{'s' if oa.prime_duree > 1 else ''} "
            "seulement, est déduite du capital à amortir "
            "au lieu d'être comptée comme un revenu perpétuel."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            f"color: {self.theme['text_muted']}; font-size: 11px; padding-top: 4px;")
        self.layout_inner.addWidget(note)
        self.layout_inner.addStretch(1)

    def _remboursement_card(self, df_total: pd.DataFrame, prime_an: float,
                            oa, invest: float, am: dict) -> QFrame:
        """Ce que l'installation a rapporte (ventes + economies + primes),
        face a son cout, avec la projection au rythme actuel.

        Remplace « Evolution patrimoniale » (audit du 14/09/2026) : cinq
        courbes sur une echelle allant de -21 900 EUR a quelques milliers,
        ou l'investissement ecrasait tout le reste. La facture reseau n'y
        figure plus : ce n'est pas un cout de l'installation (on la paierait
        sans panneaux), et les economies en tiennent deja compte.
        """
        card = Card()
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 14, 16, 14)

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
                label="Récupéré : ventes + économies + primes")
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
        ax.set_ylabel("€")
        # Au milieu a gauche, la zone vide du graphique : en haut, la legende
        # chevauchait la ligne du cout de l'installation.
        ax.legend(loc="center left", frameon=False, fontsize=9)
        canvas.fig.tight_layout()
        v.addWidget(canvas)
        return card
