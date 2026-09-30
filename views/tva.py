"""Vue TVA autoconsommation : base de la livraison a soi-meme (LASM).

De quoi il s'agit, en clair : l'electricite vendue a EDF OA ne donne lieu a
aucune TVA a collecter (EDF la declare a la place du producteur), mais celle
qu'on produit et qu'on consomme soi-meme est taxable. Cette vue calcule, pour
chaque annee civile, le montant a reporter ligne 5A de la declaration
annuelle CA12 / 3517-S, et la TVA qui en decoule.

Le detail de la regle et de la methode est en tete de la section LASM de
calculations.py.
"""
from __future__ import annotations

from datetime import date

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
from accords import accorde, pluriel
from gui_theme import CHART_COLORS as CC
from gui_theme import mpl_style
from gui_widgets import Card, KpiCard, MplCanvas, SectionTitle, grid_row
from views._base import BaseView
from views._helpers import chiffres_sur_barres, fmt_date_fr, fmt_pct


def _nombre(x: float, decimales: int = 1) -> str:
    """Un nombre a la francaise, virgule decimale."""
    return f"{x:,.{decimales}f}".replace(",", " ").replace(".", ",")


def textes_tuiles(ligne: dict, en_cours: bool, taux: float
                  ) -> list[tuple[str, str, str]]:
    """Libellé, valeur et sous-titre des quatre tuiles du haut de la page.

    Année à déclarer : les montants qui se reportent sur le formulaire.
    Année en cours : le RÉALISÉ au dernier relevé, jamais présenté comme un
    montant à déclarer ; l'estimation au 31/12 en sous-titre."""
    # En kWh entiers, et non en MWh comme ailleurs dans l'app : c'est la
    # quantite qui justifie la base declaree, elle se lit dans la meme unite
    # que les releves.
    if not en_cours:
        return [
            (f"Autoconsommation {ligne['annee']}",
             _nombre(ligne["autoconsommation_kwh"], 0) + " kWh",
             f"{fmt_pct(ligne['part_autoconso'] * 100)} de la production"),
            ("Prix moyen pondéré",
             _nombre(ligne["prix_moyen_eur_kwh"], 4) + " €/kWh",
             "énergie + acheminement HT + accise"),
            ("Base ligne 5A",
             _nombre(ligne["base_5a_eur"], 0) + " €",
             "montant à porter sur le 3517-S"),
            ("TVA à déclarer",
             _nombre(ligne["tva_due_eur"], 0) + " €",
             f"soit {_nombre(taux * 100, 0)} % de la base"),
        ]
    reel = ligne["a_date"]
    jusquau = reel["jusquau"].strftime("%d/%m/%Y")
    return [
        (f"Autoconsommation {ligne['annee']}",
         _nombre(reel["autoconsommation_kwh"], 0) + " kWh",
         f"au {jusquau} : {fmt_pct(reel['part_autoconso'] * 100)} "
         "de la production"),
        ("Prix moyen pondéré",
         _nombre(reel["prix_moyen_eur_kwh"], 4) + " €/kWh",
         "énergie + acheminement HT + accise"),
        ("Base à ce jour",
         _nombre(reel["base_5a_eur"], 0) + " €",
         f"estimée au 31/12 : {_nombre(ligne['base_5a_eur'], 0)} €"),
        ("TVA à ce jour",
         _nombre(reel["tva_due_eur"], 0) + " €",
         f"estimée au 31/12 : {_nombre(ligne['tva_due_eur'], 0)} €"),
    ]


class TvaView(BaseView):
    # Recapitulatif de TOUTES les annees civiles : la declaration est
    # annuelle, le selecteur de periode n'a rien a y faire.
    utilise_periode = False

    def populate(self, period: str) -> None:
        # Sans titre : il redisait celui de la page (30/09/2026).
        self.layout_inner.addWidget(SectionTitle(
            "",
            "Livraison à soi-même — ligne 5A de la déclaration CA12 / 3517-S",
        ))

        if self.data.lasm is None:
            self.layout_inner.addWidget(self._empty_card(
                "Aucune grille tarifaire n'est déclarée pour la TVA.\n\n"
                "Cette page ne concerne que les producteurs assujettis à la "
                "TVA. Pour l'activer, renseignez la section « tva_lasm » de "
                "config.yaml : une ligne par période tarifaire, avec le prix "
                "hors taxes du kWh et l'accise, relevés sur vos factures."))
            return

        lignes = calc.lasm_par_annee(
            self.data.df_brut,
            self.data.lasm,
            (self.data.cfg.get("sources") or {}).get("injection_facturee"),
        )
        if not lignes:
            self.layout_inner.addWidget(self._empty_card(
                "Aucun relevé : rien à déclarer pour l'instant."))
            return

        self._cartes_annee_a_declarer(lignes)
        self._graphique(lignes)
        self._tableau_annees(lignes)
        self._tableau_controle()
        self._notes(lignes)
        self.layout_inner.addStretch(1)

    # ------------------------------------------------------------------
    # Rangee du haut : la derniere annee CLOSE, celle qui se declare
    # ------------------------------------------------------------------
    def _cartes_annee_a_declarer(self, lignes: list[dict]) -> None:
        # Janvier-mai : l'annee a declarer ; a partir de juin : l'annee en
        # cours, en realise (voir calc.ligne_des_tuiles_lasm).
        choix = calc.ligne_des_tuiles_lasm(lignes, self.aujourdhui())
        if choix is None:
            return
        ligne, en_cours = choix
        variantes = ("warm", "info", "primary", "debit")
        cartes = [KpiCard(label, valeur, sous_titre, variant=variante)
                  for (label, valeur, sous_titre), variante in zip(
                      textes_tuiles(ligne, en_cours, self.data.lasm.taux),
                      variantes, strict=True)]
        self.layout_inner.addLayout(grid_row(cartes))

    @staticmethod
    def aujourdhui() -> date:
        """La date du jour (isolee pour que les tests puissent la fixer)."""
        return date.today()

    # ------------------------------------------------------------------
    # Graphique : TVA due par annee
    # ------------------------------------------------------------------
    def _graphique(self, lignes: list[dict]) -> None:
        # Titre dans le bandeau de la carte, comme dans Pecule (29/09/2026).
        card = Card(titre="TVA due par année civile")
        v = card.corps
        v.setContentsMargins(16, 10, 16, 14)
        canvas = MplCanvas(width=8, height=2.8, dpi=100)
        canvas.apply_theme(mpl_style(self.theme))
        ax = canvas.fig.add_subplot(111)
        xs = np.arange(len(lignes))
        hauteurs = [ligne["tva_due_eur"] for ligne in lignes]
        # L'annee en cours est projetee : hachures et transparence pour qu'on
        # ne la lise pas comme un montant acquis.
        couleurs = [CC["autoconso"] for _ in lignes]
        barres = ax.bar(xs, hauteurs, 0.55, color=couleurs)
        for barre, ligne in zip(barres, lignes, strict=True):
            if ligne["estimation"]:
                barre.set_alpha(0.45)
                barre.set_hatch("//")
        # Le montant de chaque annee au-dessus de sa barre (demande du
        # 15/09/2026).
        chiffres_sur_barres(ax, [barres])
        ax.set_xticks(xs)
        ax.set_xticklabels([
            f"{ligne['annee']}\n(estimé)" if ligne["estimation"]
            else str(ligne["annee"]) for ligne in lignes])
        ax.set_ylabel("€")
        canvas.fig.tight_layout()
        v.addWidget(canvas)
        self.layout_inner.addWidget(card)

    # ------------------------------------------------------------------
    # Tableau principal : une ligne par annee civile
    # ------------------------------------------------------------------
    def _tableau_annees(self, lignes: list[dict]) -> None:
        card = Card()
        v = QVBoxLayout(card)
        v.setContentsMargins(0, 0, 0, 0)
        cols = ["Année", "Autoconsommation (kWh)", "Part d'autoconsommation",
                "Prix moyen (€/kWh)", "Base ligne 5A (€)", "TVA due (€)",
                "Contrôle EDF"]
        table = QTableWidget(len(lignes), len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setShowGrid(False)

        gras = QFont()
        gras.setBold(True)
        # L'annee la plus recente en haut (demande du 27/09/2026) ; le
        # graphique, lui, reste chronologique de gauche a droite.
        for i, ligne in enumerate(reversed(lignes)):
            controle = ligne["controle"]
            if controle is None or controle["ecart_pct"] is None:
                ecart_txt = "—"
            else:
                ecart_txt = f"{controle['ecart_pct']:+.2f} %".replace(".", ",")
            items = [
                QTableWidgetItem(f"{ligne['annee']} (estimé)"
                                 if ligne["estimation"] else str(ligne["annee"])),
                QTableWidgetItem(_nombre(ligne["autoconsommation_kwh"], 0)),
                QTableWidgetItem(fmt_pct(ligne["part_autoconso"] * 100)),
                QTableWidgetItem(_nombre(ligne["prix_moyen_eur_kwh"], 4)),
                QTableWidgetItem(_nombre(ligne["base_5a_eur"], 0)),
                QTableWidgetItem(_nombre(ligne["tva_due_eur"], 0)),
                QTableWidgetItem(ecart_txt),
            ]
            items[0].setFont(gras)
            items[0].setForeground(QColor(
                self.theme["text_muted"] if ligne["estimation"]
                else self.theme["primary"]))
            items[4].setFont(gras)
            items[5].setFont(gras)
            if ligne["estimation"]:
                items[0].setToolTip(
                    "Année non terminée : les chiffres sont une projection au "
                    "31/12, obtenue à partir de la part d'autoconsommation "
                    "déjà atteinte à la même date les années précédentes.")
            if ligne["jours_sans_injection"]:
                n = ligne["jours_sans_injection"]
                items[1].setToolTip(
                    f"{pluriel(n, 'jour')} sans relevé d'injection : toute "
                    f"{accorde(n, 'sa', 'leur')} production compte en "
                    "autoconsommation, ce qui tire ce chiffre vers le haut.")
                items[1].setForeground(QColor(self.theme["text_muted"]))
            if controle is not None:
                items[6].setToolTip(
                    f"Année de contrat du {fmt_date_fr(controle['debut'])} au "
                    f"{fmt_date_fr(controle['fin'])} : "
                    f"{_nombre(controle['releve_kwh'])} kWh relevés contre "
                    f"{_nombre(controle['facture_kwh'], 0)} kWh facturés.")
            for j in range(1, len(cols)):
                items[j].setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            for j, item in enumerate(items):
                table.setItem(i, j, item)

        # Colonnes reparties sur toute la largeur : avec la derniere seule
        # etiree, un grand vide la separait des autres (audit du 14/09/2026).
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.setFixedHeight(40 + len(lignes) * 36)
        v.addWidget(table)
        self.layout_inner.addWidget(card)

    # ------------------------------------------------------------------
    # Controle de coherence avec les factures EDF OA
    # ------------------------------------------------------------------
    def _tableau_controle(self) -> None:
        controles = calc.controle_injection_facturee(
            self.data.df_brut,
            (self.data.cfg.get("sources") or {}).get("injection_facturee"),
        )
        if not controles:
            return
        # Titre dans le bandeau de la carte, comme dans Pecule (29/09/2026).
        card = Card(
            titre=f"Contrôle avec les factures {self._d_acheteur()}",
            sous_titre="Injection relevée face aux kWh réellement facturés, "
                       "année de contrat par année de contrat "
                       f"({self.data.cycle_oa})")
        v = card.corps
        v.setContentsMargins(0, 8, 0, 0)
        # Le sous-titre garde un peu d'air a gauche ; le tableau, bord a bord.
        v.itemAt(0).widget().setContentsMargins(12, 0, 12, 6)
        cols = ["Période", "Relevé (kWh)", "Facturé (kWh)", "Écart (kWh)",
                "Écart", "Jours estimés"]
        table = QTableWidget(len(controles), len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setShowGrid(False)

        gras = QFont()
        gras.setBold(True)
        # La periode la plus recente en haut, comme le tableau des annees.
        for i, ligne in enumerate(reversed(controles)):
            pct = ligne["ecart_pct"]
            items = [
                QTableWidgetItem(f"{fmt_date_fr(ligne['debut'])} → "
                                 f"{fmt_date_fr(ligne['fin'])}"),
                QTableWidgetItem(_nombre(ligne["releve_kwh"])),
                QTableWidgetItem(_nombre(ligne["facture_kwh"], 0)),
                QTableWidgetItem(f"{ligne['ecart_kwh']:+.1f}".replace(".", ",")),
                QTableWidgetItem("—" if pct is None
                                 else f"{pct:+.2f} %".replace(".", ",")),
                QTableWidgetItem(str(ligne["jours_estimes"] or "—")),
            ]
            # Vert tant que le recoupement tient sous 1 %, l'ordre de grandeur
            # d'un decalage d'heure de relevé d'index. Au-dela, il y a une
            # vraie difference a comprendre avant de s'appuyer sur ces chiffres.
            if pct is not None:
                couleur = (self.theme["credit"] if abs(pct) < 1.0
                           else self.theme["debit"])
                items[4].setForeground(QColor(couleur))
                items[4].setFont(gras)
            if ligne["source"]:
                items[0].setToolTip(ligne["source"])
            for j in range(1, len(cols)):
                items[j].setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            for j, item in enumerate(items):
                table.setItem(i, j, item)

        # Colonnes reparties sur toute la largeur : avec la derniere seule
        # etiree, un grand vide la separait des autres (audit du 14/09/2026).
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.setFixedHeight(40 + len(controles) * 36)
        v.addWidget(table)
        self.layout_inner.addWidget(card)

    # ------------------------------------------------------------------
    # Notes de bas de page
    # ------------------------------------------------------------------
    def _acheteur(self) -> str:
        """A qui l'electricite est vendue (« EDF OA » si rien n'est dit)."""
        return getattr(self.data, "acheteur", None) or "EDF OA"

    def _d_acheteur(self) -> str:
        """« d'EDF OA », « de Solaire Coop »."""
        return getattr(self.data, "d_acheteur", None) or "d'EDF OA"

    def _notes(self, lignes: list[dict]) -> None:
        textes = [
            "Ce qui est taxable : seule l'électricité produite ET consommée "
            "sur place l'est, au titre de la livraison à soi-même "
            f"(art. 257-II-1-1° du CGI). Les ventes à {self._acheteur()} "
            "sont autoliquidées — l'acheteur déclare leur TVA — et la prime à "
            "l'autoconsommation est hors champ.",
            "Comment la base est calculée : chaque kWh autoconsommé est "
            "valorisé au tarif d'achat en vigueur le jour même — part "
            "fourniture et acheminement HT, plus l'accise, hors TVA et hors "
            "abonnement (art. 266-1-c). Le prix moyen affiché n'est pas un "
            "tarif : c'est la moyenne qui ressort de ce calcul jour par jour.",
            "D'où viennent les chiffres : des relevés quotidiens du fichier "
            "Releves-pv.csv, pris tels quels, sans le recalage sur factures "
            "appliqué dans les autres onglets. Le contrôle ci-dessus les "
            "recoupe avec les autofacturations annuelles "
            f"{self._d_acheteur()}.",
        ]
        incompletes = [ligne for ligne in lignes
                       if ligne["jours_sans_injection"]]
        if incompletes:
            detail = ", ".join(
                f"{ligne['annee']} ({ligne['jours_sans_injection']} j)"
                for ligne in incompletes)
            textes.append(
                "Attention : certaines années comptent des jours sans relevé "
                f"d'injection — {detail}. Toute la production de ces jours-là "
                "est comptée en autoconsommation, ce qui majore la base.")
        if any(ligne["estimation"] for ligne in lignes):
            textes.append(
                "L'année en cours est une ESTIMATION, pas un montant à "
                "déclarer : elle prolonge l'autoconsommation déjà relevée "
                "jusqu'au 31/12, d'après la part atteinte à la même date les "
                "années précédentes. Elle se fige une fois l'année terminée.")
        note = QLabel("\n\n".join("• " + t for t in textes))
        note.setWordWrap(True)
        note.setStyleSheet(
            f"color: {self.theme['text_muted']}; font-size: 11px; "
            "padding-top: 6px;")
        self.layout_inner.addWidget(note)
