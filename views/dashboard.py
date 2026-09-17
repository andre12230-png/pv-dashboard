"""Vue Tableau de bord : jauge d'autoproduction, production de la periode,
repartition de l'energie, bilan financier, remboursement de l'installation
et production jour par jour (refonte graphique du 14/09/2026)."""
from __future__ import annotations

import matplotlib.colors as mcolors
import numpy as np
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from gui_theme import CHART_COLORS as CC
from gui_theme import mpl_style
from gui_widgets import (
    BarMeter,
    BarreRepartition,
    Card,
    Jauge,
    KpiCard,
    MiniBarres,
    MplCanvas,
    SectionTitle,
    grid_row,
    police_tabulaire,
)
from views._base import BaseView
from views._helpers import (
    amortissement,
    chiffres_sur_barres,
    filter_period,
    fmt_eur,
    fmt_kwh,
    fmt_pct,
    fmt_prix_kwh,
    fraicheur_donnees,
    libelle_periode,
    periode_precedente,
)
from views.comparaison import date_limite_n1


class DashboardView(BaseView):
    # Ouvre la fenetre « Mes reglages » ; branche par MainWindow.
    ouvrir_reglages = None

    def populate(self, period: str) -> None:
        # Aucun releve du tout : premier lancement. Au lieu d'un bandeau
        # « Aucun releve » qui ne dit pas quoi faire, les premiers pas.
        if self.data.df.empty:
            self.layout_inner.addWidget(self._carte_premiers_pas())
            self.layout_inner.addStretch(1)
            return
        df = filter_period(self.data.df, period, self.data.start_oa)
        # Fraicheur en premier : on doit savoir si l'on regarde des chiffres
        # complets AVANT de les lire, pas apres.
        self.layout_inner.addWidget(self._bandeau_fraicheur())
        if df.empty:
            self.layout_inner.addWidget(self._empty_card("Aucune donnée sur cette période."))
            return

        prod = df["production_kwh"].sum()
        inj = df["injection_kwh"].sum()
        auto = df["autoconsommation_kwh"].sum()
        sout = df["soutirage_kwh"].sum()
        conso = df["consommation_kwh"].sum()
        revenu = df["revenu_vente_eur"].sum()
        eco = df["economie_eur"].sum()
        cout = df["cout_reseau_eur"].sum()
        bilan = revenu + eco - cout

        ratio_ac = (auto / prod * 100) if prod else 0
        ratio_ap = (auto / conso * 100) if conso else 0
        ratio_inj = (inj / prod * 100) if prod else 0

        # 1) En tete, en images : la part de soleil dans la consommation, et
        # la production de la periode avec son allure. Remplace une rangee de
        # cinq cartes de chiffres, jugee trop austere par l'auteur.
        haut = QHBoxLayout()
        haut.setSpacing(14)
        haut.addWidget(self._carte_jauge(ratio_ap), stretch=2)
        haut.addWidget(self._carte_production(df, period, prod), stretch=3)
        self.layout_inner.addLayout(haut)

        # 2) Ou va le soleil, d'ou vient l'electricite : deux barres qui se
        # lisent sans calcul. La part du soutirage qui part dans la voiture
        # reste dite : sans elle, on compare une consommation « maison +
        # voiture » a une consommation domestique.
        ve = df["recharge_ve_kwh"].sum() if "recharge_ve_kwh" in df.columns else 0.0
        ve_eur = (df["recharge_ve_eur"].sum()
                  if "recharge_ve_eur" in df.columns else 0.0)
        self.layout_inner.addWidget(self._carte_repartition(
            auto, inj, sout, conso, ratio_ac, ratio_inj, ratio_ap, ve, ve_eur))

        self.layout_inner.addWidget(SectionTitle("Bilan financier de la période"))
        # Une icone par montant, comme les emojis du bandeau de gauche.
        self.layout_inner.addLayout(grid_row([
            KpiCard("💶 Vente à EDF OA", fmt_eur(revenu, signed=True),
                    f"à {fmt_prix_kwh(self.data.oa.prix_kwh)}", "credit"),
            KpiCard("🐷 Économies", fmt_eur(eco, signed=True),
                    "kWh du soleil, non achetés", "credit"),
            KpiCard("🔌 Achat au réseau", fmt_eur(-cout, signed=True),
                    "électricité + abonnement", "debit"),
            KpiCard("⚖️ Bilan net", fmt_eur(bilan, signed=True),
                    "vente + économies − achat",
                    "credit" if bilan >= 0 else "debit"),
        ]))

        # Jours dont une grandeur n'a jamais ete relevee : l'app la reconstitue,
        # et le dit ici pour qu'on ne prenne pas ces chiffres pour des mesures.
        notes = []
        if "releve_incomplet" in df.columns:
            n_inc = int((df["releve_incomplet"] > 0).sum())
            if n_inc:
                notes.append(
                    f"ℹ {n_inc} jour(s) sans relevé d'injection Enedis sur la "
                    "période : injection et autoconso y sont estimées d'après "
                    "vos ratios mensuels observés."
                )
        if "injection_recalee" in df.columns:
            n_inj = int((df["injection_recalee"] > 0).sum())
            if n_inj:
                notes.append(
                    f"ℹ {n_inj} jour(s) de la période sont recalés sur les "
                    "factures EDF OA : le total vendu de chaque année OA est "
                    "celui qui a été payé, au kWh près. Le détail quotidien, "
                    "lui, reste approché."
                )
        if "conso_recalee" in df.columns:
            n_recale = int((df["conso_recalee"] > 0).sum())
            if n_recale:
                notes.append(
                    f"ℹ {n_recale} jour(s) de la période ont été saisis arrondis "
                    "au kWh entier : ils sont recalés sur le total des factures "
                    "EDF, exact. Le total est donc juste, le détail quotidien "
                    "approché à environ 1 kWh près."
                )
        if "conso_absente" in df.columns:
            n_conso = int((df["conso_absente"] > 0).sum())
            if n_conso:
                kwh = df.loc[df["conso_absente"] > 0, "soutirage_kwh"].sum()
                notes.append(
                    f"ℹ {n_conso} jour(s) sans relevé de consommation "
                    f"exploitable sur la période ({fmt_kwh(kwh)}) : données "
                    "absentes chez Enedis (36 mois glissants), ou valeurs "
                    "interpolées pendant une panne du compteur. Le "
                    "total de la facture EDF correspondante est réparti sur "
                    "ces jours — le total de la période est juste, pas le "
                    "détail quotidien."
                )
        for texte in notes:
            note = QLabel(texte)
            note.setWordWrap(True)
            note.setStyleSheet(
                f"color: {self.theme['text_muted']}; font-size: 11px;")
            self.layout_inner.addWidget(note)

        # Etape 2 (groupe B de l'audit) : ou en est le remboursement de
        # l'installation, puis la production au fil des jours, a la place de
        # deux graphiques hebdomadaires peu parlants (flux et bilan).
        remboursement = self._carte_remboursement()
        if remboursement is not None:
            self.layout_inner.addWidget(remboursement)
        self.layout_inner.addWidget(self._carte_production_jours(df))
        self.layout_inner.addStretch(1)

    # ------------------------------------------------------------------
    # En-tete graphique
    # ------------------------------------------------------------------
    def _carte_jauge(self, ratio_ap: float) -> QFrame:
        """La jauge d'autoproduction et sa phrase."""
        card = Card()
        h = QHBoxLayout(card)
        h.setContentsMargins(20, 16, 20, 16)
        h.setSpacing(18)
        h.addWidget(Jauge(ratio_ap / 100, CC["production"], self.theme["border"],
                          self.theme["text_primary"], "de soleil"))
        col = QVBoxLayout()
        col.setSpacing(4)
        titre = QLabel("AUTOPRODUCTION")
        titre.setObjectName("KpiLabel")
        phrase = QLabel(f"{fmt_pct(ratio_ap)} de ce que la maison consomme "
                        "vient de vos panneaux")
        phrase.setWordWrap(True)
        phrase.setStyleSheet(
            f"color: {self.theme['text_secondary']}; font-size: 13px; "
            "background: transparent;")
        col.addStretch(1)
        col.addWidget(titre)
        col.addWidget(phrase)
        col.addStretch(1)
        h.addLayout(col, stretch=1)
        return card

    def _carte_production(self, df: pd.DataFrame, period: str,
                          prod: float) -> QFrame:
        """La production de la periode, sa comparaison a l'an dernier et
        l'allure de ses jours (ou semaines, ou mois selon la duree)."""
        card = Card()
        v = QVBoxLayout(card)
        v.setContentsMargins(20, 16, 20, 14)
        v.setSpacing(6)
        tete = QHBoxLayout()
        titre = QLabel(f"PRODUCTION — {libelle_periode(period).upper()}")
        titre.setObjectName("KpiLabel")
        tete.addWidget(titre)
        tete.addStretch(1)
        badge = self._badge_n1(df, period, prod)
        if badge is not None:
            tete.addWidget(badge)
        v.addLayout(tete)
        valeur = QLabel(fmt_kwh(prod))
        valeur.setFont(police_tabulaire(gras=True))
        # Taille dans la feuille de style du label : posee par setFont, elle
        # etait ecrasee par celle de l'application (le chiffre sortait petit).
        valeur.setStyleSheet(
            f"color: {self.theme['text_primary']}; background: transparent; "
            "font-size: 32px; font-weight: 700;")
        v.addWidget(valeur)
        v.addWidget(MiniBarres(self._allure_production(df), CC["production"]))
        return card

    @staticmethod
    def _allure_production(df: pd.DataFrame) -> list[float]:
        """Les batons de la mini-courbe : un par jour sur un mois, un par
        semaine sur une annee, un par mois au-dela. Assez pour voir l'allure,
        jamais au point de ne plus distinguer les batons."""
        jours = len(df)
        freq = "D" if jours <= 62 else ("W" if jours <= 400 else "MS")
        return df["production_kwh"].resample(freq).sum().tolist()

    def _badge_n1(self, df: pd.DataFrame, period: str,
                  prod: float) -> QLabel | None:
        """« +24 % vs septembre 2025 », calcule comme l'onglet Comparaison N
        vs N-1 : une periode en cours est comparee aux MEMES dates de l'an
        passe. None quand il n'y a rien a comparer."""
        precedente = periode_precedente(period)
        if precedente is None:
            return None
        df_n1 = filter_period(self.data.df, precedente, self.data.start_oa)
        limite = date_limite_n1(df, period, self.data.start_oa)
        if limite is not None and not df_n1.empty:
            df_n1 = df_n1[df_n1.index.normalize() <= limite]
        base = float(df_n1["production_kwh"].sum()) if not df_n1.empty else 0.0
        if base <= 0:
            return None
        ecart = (prod - base) / base * 100
        signe = "+" if ecart >= 0 else "−"
        badge = QLabel(f"{signe}{abs(ecart):.0f} % vs "
                       f"{libelle_periode(precedente).lower()}")
        encre, fond = (("credit", "credit_bg") if ecart >= 0
                       else ("debit", "debit_bg"))
        badge.setStyleSheet(
            f"color: {self.theme[encre]}; background: {self.theme[fond]}; "
            "font-size: 11px; font-weight: 600; padding: 3px 8px; "
            "border-radius: 6px;")
        return badge

    def _carte_repartition(self, auto, inj, sout, conso, ratio_ac, ratio_inj,
                           ratio_ap, ve, ve_eur: float = 0.0) -> QFrame:
        """Deux barres : ou va la production, d'ou vient la consommation.

        Avec des recharges de vehicule (application Recharges VE), la part du
        reseau qui part dans la voiture a son propre morceau de barre et sa
        propre ligne : reduite a une mention en petit texte gris, elle ne se
        voyait plus (remarque de l'auteur, 14/09/2026).
        """
        card = Card()
        v = QVBoxLayout(card)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(6)

        def titre(texte: str) -> QLabel:
            lbl = QLabel(texte)
            lbl.setStyleSheet(
                f"color: {self.theme['text_secondary']}; font-size: 13px; "
                "background: transparent;")
            return lbl

        def legende(texte: str) -> QLabel:
            lbl = QLabel(texte)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                f"color: {self.theme['text_muted']}; font-size: 11px; "
                "background: transparent;")
            return lbl

        v.addWidget(titre("Où va votre soleil"))
        # Chaque morceau de barre a des libelles de secours, du plus long au
        # plus court : la barre ecrit le plus long qui tient (moitie d'ecran)
        v.addWidget(BarreRepartition([
            ([f"Consommé {fmt_kwh(auto)}", fmt_kwh(auto)],
             auto, CC["autoconso"]),
            ([f"Vendu à EDF OA {fmt_kwh(inj)}", f"Vendu {fmt_kwh(inj)}",
              fmt_kwh(inj)], inj, CC["injection"]),
        ]))
        v.addWidget(legende(f"{fmt_pct(ratio_ac)} consommé sur place · "
                            f"{fmt_pct(ratio_inj)} vendu"))
        v.addSpacing(8)
        v.addWidget(titre("D'où vient votre électricité"))
        avec_ve = ve > 0 and sout > 0
        if avec_ve:
            maison = max(sout - ve, 0.0)
            segments = [
                ([f"☀️ Soleil {fmt_kwh(auto)}", f"☀️ {fmt_kwh(auto)}", "☀️"],
                 auto, CC["production"]),
                ([f"🏠 Réseau, maison {fmt_kwh(maison)}",
                  f"🏠 Maison {fmt_kwh(maison)}", f"🏠 {fmt_kwh(maison)}",
                  "🏠"], maison, CC["soutirage"]),
                ([f"🚗 Réseau, véhicule {fmt_kwh(ve)}",
                  f"🚗 Véhicule {fmt_kwh(ve)}", f"🚗 {fmt_kwh(ve)}",
                  f"🚗 {fmt_kwh(ve).removesuffix(' kWh')}", "🚗"],
                 ve, self.theme["info"]),
            ]
        else:
            segments = [
                ([f"Soleil {fmt_kwh(auto)}", fmt_kwh(auto)],
                 auto, CC["production"]),
                ([f"Réseau {fmt_kwh(sout)}", fmt_kwh(sout)],
                 sout, CC["soutirage"]),
            ]
        v.addWidget(BarreRepartition(segments))
        v.addWidget(legende(
            f"{fmt_pct(ratio_ap)} de soleil · {fmt_pct(100 - ratio_ap)} du "
            f"réseau, sur {fmt_kwh(conso)} consommés"))
        if avec_ve:
            ligne_ve = (f"🚗 Recharge du véhicule : {fmt_kwh(ve)}, soit "
                        f"{fmt_pct(ve / sout * 100)} de l'électricité achetée "
                        "au réseau")
            if ve_eur > 0:
                ligne_ve += f", pour {fmt_eur(ve_eur)}"
            vehicule = QLabel(ligne_ve)
            vehicule.setWordWrap(True)
            vehicule.setStyleSheet(
                f"color: {self.theme['text_primary']}; font-size: 13px; "
                "font-weight: 600; background: transparent; padding-top: 4px;")
            v.addWidget(vehicule)
        return card

    def _carte_premiers_pas(self) -> QFrame:
        """Ce qu'un nouvel utilisateur doit faire, dans l'ordre."""
        card = Card()
        v = QVBoxLayout(card)
        v.setContentsMargins(28, 22, 28, 24)
        v.setSpacing(10)
        titre = QLabel("Pour commencer")
        titre.setStyleSheet(
            f"color: {self.theme['text_primary']}; font-size: 18px; "
            "font-weight: 700;")
        v.addWidget(titre)
        texte = QLabel(
            "<p><b>1. Décrivez votre installation</b> avec le bouton "
            "<b>Remplir mes réglages</b> ci-dessous : puissance, coût, dates "
            "du contrat, prix de votre fournisseur. Les valeurs affichées pour "
            "l'instant sont celles d'un exemple.</p>"
            "<p><b>2. Faites entrer vos relevés.</b> Onglet <b>Saisie "
            "quotidienne</b>, boutons <b>Importer…</b> : un fichier téléchargé "
            "sur le site d'Enedis (consommation, injection) ou de votre "
            "onduleur (production). La saisie à la main marche aussi.</p>"
            "<p><b>3. Revenez ici.</b> Le tableau de bord se remplit tout "
            "seul. La <b>Notice</b> explique chaque écran.</p>")
        texte.setTextFormat(Qt.RichText)
        texte.setWordWrap(True)
        texte.setStyleSheet(
            f"color: {self.theme['text_secondary']}; font-size: 13px;")
        v.addWidget(texte)
        if callable(self.ouvrir_reglages):
            bouton = QPushButton("Remplir mes réglages")
            bouton.setCursor(Qt.PointingHandCursor)
            bouton.clicked.connect(self.ouvrir_reglages)
            v.addWidget(bouton, alignment=Qt.AlignLeft)
        return card

    def _bandeau_fraicheur(self) -> QLabel:
        """Age des donnees, grandeur par grandeur, en tete du tableau de bord."""
        texte, en_retard = fraicheur_donnees(
            self.data.dernieres_saisies,
            illisibles=getattr(self.data, "dates_illisibles", None))
        lbl = QLabel(("⚠  " if en_retard else "✓  ") + texte)
        lbl.setWordWrap(True)
        couleur = self.theme["warm_ink"] if en_retard else self.theme["text_muted"]
        fond = self.theme["warm_bg"] if en_retard else "transparent"
        lbl.setStyleSheet(
            f"color: {couleur}; background: {fond}; font-size: 11px; "
            f"padding: 6px 10px; border-radius: 6px;")
        return lbl

    def _carte_remboursement(self) -> QFrame | None:
        """Ou en est le remboursement de l'installation. Depuis la mise en
        service, quelle que soit la periode choisie en haut : c'est un cumul.
        Meme calcul que la Synthese financiere (amortissement())."""
        am = amortissement(self.data)
        if am is None or am["invest"] <= 0:
            return None
        ratio = am["recupere"] / am["invest"]
        card = Card()
        v = QVBoxLayout(card)
        v.setContentsMargins(20, 14, 20, 16)
        v.setSpacing(8)
        tete = QHBoxLayout()
        titre = QLabel("🏡 INSTALLATION REMBOURSÉE — DEPUIS LA MISE EN SERVICE")
        titre.setObjectName("KpiLabel")
        tete.addWidget(titre)
        tete.addStretch(1)
        pourcentage = QLabel(f"{min(ratio, 1.0) * 100:.0f} %")
        pourcentage.setStyleSheet(
            f"color: {self.theme['text_primary']}; font-size: 18px; "
            "font-weight: 700; background: transparent;")
        tete.addWidget(pourcentage)
        v.addLayout(tete)
        v.addWidget(BarMeter(min(ratio, 1.0), CC["autoconso"],
                             self.theme["border"], hauteur=12))
        detail = (f"{fmt_eur(am['recupere'])} récupérés sur "
                  f"{fmt_eur(am['invest'])} : ventes à EDF OA, économies et "
                  "primes déjà perçues.")
        if ratio >= 1:
            detail += " L'installation est remboursée."
        elif am["roi_an"]:
            fin = (pd.Timestamp(self.data.df.index.min())
                   + pd.Timedelta(days=round(am["roi_an"] * 365.25)))
            detail += (f" Au rythme actuel, remboursement complet vers "
                       f"{fin.year} (voir la Synthèse financière).")
        note = QLabel(detail)
        note.setWordWrap(True)
        note.setStyleSheet(
            f"color: {self.theme['text_muted']}; font-size: 11px; "
            "background: transparent;")
        v.addWidget(note)
        return card

    # (frequence, titre, nom du record, format des dates) selon la duree.
    PAS_PRODUCTION = {
        "D": ("jour par jour", "Meilleur jour", "%d/%m"),
        "W": ("semaine par semaine", "Meilleure semaine, celle du", "%d/%m"),
        "MS": ("mois par mois", "Meilleur mois", "%m/%Y"),
    }

    def _carte_production_jours(self, df: pd.DataFrame) -> QFrame:
        """La production au fil de la periode, le meilleur jour (ou semaine,
        ou mois) en couleur pleine et chiffre, les autres adoucis."""
        jours = len(df)
        freq = "D" if jours <= 62 else ("W" if jours <= 400 else "MS")
        titre, nom_record, fmt_date = self.PAS_PRODUCTION[freq]
        serie = df["production_kwh"].resample(freq).sum()
        if freq == "W":
            # pandas date une semaine de son dimanche : on la date du lundi.
            serie.index = serie.index - pd.Timedelta(days=6)

        card = Card()
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 14, 16, 14)
        tete = QHBoxLayout()
        tete.addWidget(SectionTitle(f"Production {titre}"))
        tete.addStretch(1)
        valeurs = serie.values
        meilleur = int(valeurs.argmax()) if len(valeurs) and valeurs.max() > 0 else None
        if meilleur is not None:
            record = QLabel(
                f"🏆 {nom_record} {serie.index[meilleur].strftime(fmt_date)} : "
                f"{fmt_kwh(valeurs[meilleur])}")
            record.setStyleSheet(
                f"color: {self.theme['text_secondary']}; font-size: 12px; "
                "background: transparent;")
            tete.addWidget(record, alignment=Qt.AlignTop)
        v.addLayout(tete)

        canvas = MplCanvas(width=8, height=3.0, dpi=100)
        canvas.setMinimumHeight(270)
        canvas.apply_theme(mpl_style(self.theme))
        ax = canvas.fig.add_subplot(111)
        x = np.arange(len(serie.index))
        adoucie = mcolors.to_rgba(CC["production"], 0.45)
        couleurs = [CC["production"] if i == meilleur else adoucie
                    for i in range(len(x))]
        barres = ax.bar(x, valeurs, 0.7, color=couleurs)
        # Chaque barre porte son chiffre (demande du 15/09/2026) ; celui du
        # meilleur jour reste mis en valeur, en gras.
        textes = chiffres_sur_barres(ax, [barres],
                                     decimales=1 if freq == "D" else 0)
        if meilleur is not None:
            textes[0][meilleur].set_fontweight("bold")
        self._etiquettes_x(ax, serie.index, fmt_date)
        ax.set_ylabel("kWh")
        canvas.fig.tight_layout()
        v.addWidget(canvas)
        return card

    @staticmethod
    def _etiquettes_x(ax, index, fmt_date: str) -> None:
        """Etiquettes de l'axe des x, espacees pour rester lisibles."""
        x = np.arange(len(index))
        # Au-dela de 18 graduations les libelles se chevauchent : on n'en
        # garde qu'une sur deux (ou trois), les barres restent toutes la.
        pas = 1 if len(index) <= 18 else (2 if len(index) <= 36 else 3)
        ax.set_xticks(x[::pas])
        ax.set_xticklabels([d.strftime(fmt_date) for d in index[::pas]],
                           rotation=45, ha="right")

