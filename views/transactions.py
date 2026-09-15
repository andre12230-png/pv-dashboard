"""Vue Releves journaliers : tableau detaille jour par jour."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from gui_widgets import Card, SectionTitle
from views._base import BaseView
from views._helpers import filter_period


class _ItemTriable(QTableWidgetItem):
    """Cellule de tableau qui se trie sur une valeur (date ou nombre) plutot
    que sur le texte affiche : sans cela Qt trie alphabetiquement et
    "9,5" est classe apres "33,2"."""

    def __init__(self, texte: str, cle):
        super().__init__(texte)
        self._cle = cle

    def __lt__(self, autre):
        if isinstance(autre, _ItemTriable):
            return self._cle < autre._cle
        return super().__lt__(autre)


class TransactionsView(BaseView):
    def populate(self, period: str) -> None:
        df = filter_period(
            self.data.df, period, self.data.start_oa,
        ).sort_index(ascending=False)
        if df.empty:
            self.layout_inner.addWidget(self._empty_card("Aucun relevé sur cette période."))
            self.layout_inner.addStretch(1)
            return

        self.layout_inner.addWidget(SectionTitle(
            "Relevés journaliers",
            f"{len(df)} jour(s) - 1 ligne = 1 journée de production",
        ))

        card = Card()
        v = QVBoxLayout(card)
        v.setContentsMargins(0, 0, 0, 0)

        # Colonne vehicule seulement si la source est configuree et alimentee.
        avec_ve = ("recharge_ve_kwh" in df.columns
                   and float(df["recharge_ve_kwh"].sum()) > 0)
        # En-tetes en clair : « Prod / Auto / Inj / Sout » etait du jargon
        # (audit du 14/09/2026).
        colonnes = [
            "Date",
            "Production\n(kWh)", "Autoconsommée\n(kWh)", "Injectée\n(kWh)",
            "Achetée au réseau\n(kWh)",
        ]
        if avec_ve:
            colonnes.append("dont véhicule\n(kWh)")
        colonnes += ["Recettes\n(€)", "Dépenses\n(€)", "Bilan du jour\n(€)"]

        table = QTableWidget(len(df), len(colonnes))
        table.setHorizontalHeaderLabels(colonnes)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSortingEnabled(False)
        table.setShowGrid(False)
        header = table.horizontalHeader()
        for i in range(len(colonnes)):
            header.setSectionResizeMode(i, QHeaderView.Stretch)

        ALIGN_CENTER = Qt.AlignHCenter | Qt.AlignVCenter

        def _num_item(value: float, decimals: int = 1,
                      estime: bool = False) -> QTableWidgetItem:
            # L'asterisque est pose sur la valeur estimee elle-meme (et pas
            # sur la ligne) : on voit ainsi laquelle des colonnes est deduite
            # d'un calcul plutot que relevee.
            txt = f"{value:.{decimals}f}".replace(".", ",") + (" *" if estime else "")
            it = _ItemTriable(txt, float(value))
            it.setTextAlignment(ALIGN_CENTER)
            if estime:
                it.setToolTip("Valeur estimée : ce jour n'a pas de relevé.")
            return it

        for row, (d, r) in enumerate(df.iterrows()):
            credit = r["revenu_vente_eur"] + r["economie_eur"]
            debit = r["cout_reseau_eur"]
            bilan = r["bilan_jour_eur"]
            inj_estimee = float(r.get("releve_incomplet", 0) or 0) > 0
            sout_estime = float(r.get("conso_absente", 0) or 0) > 0

            date_item = _ItemTriable(d.strftime("%d/%m/%Y"), d)
            date_item.setTextAlignment(ALIGN_CENTER)

            prod_item = _num_item(r["production_kwh"])
            auto_item = _num_item(r["autoconsommation_kwh"], estime=inj_estimee)
            inj_item  = _num_item(r["injection_kwh"], estime=inj_estimee)
            sout_item = _num_item(r["soutirage_kwh"], estime=sout_estime)

            credit_item = _ItemTriable(
                f"{credit:,.2f}".replace(",", " ").replace(".", ","), float(credit))
            credit_item.setTextAlignment(ALIGN_CENTER)
            if credit > 0:
                credit_item.setForeground(self._color(self.theme["credit"]))

            debit_item = _ItemTriable(
                f"{debit:,.2f}".replace(",", " ").replace(".", ","), float(debit))
            debit_item.setTextAlignment(ALIGN_CENTER)
            if debit > 0:
                debit_item.setForeground(self._color(self.theme["debit"]))

            bilan_item = _ItemTriable(
                f"{'+' if bilan >= 0 else '-'}{abs(bilan):,.2f}"
                .replace(",", " ").replace(".", ","),
                float(bilan),
            )
            bilan_item.setTextAlignment(ALIGN_CENTER)
            color = self.theme["credit"] if bilan >= 0 else self.theme["debit"]
            bilan_item.setForeground(self._color(color))
            f = QFont()
            f.setBold(True)
            bilan_item.setFont(f)

            cellules = [date_item, prod_item, auto_item, inj_item, sout_item]
            if avec_ve:
                ve_item = _num_item(float(r.get("recharge_ve_kwh", 0.0) or 0.0))
                ve_item.setForeground(self._color(self.theme["info_ink"]))
                cellules.append(ve_item)
            cellules += [credit_item, debit_item, bilan_item]
            for col, item in enumerate(cellules):
                table.setItem(row, col, item)

        table.setSortingEnabled(True)
        v.addWidget(table)
        v.addWidget(self._ligne_totaux(df, colonnes, avec_ve))
        self.layout_inner.addWidget(card)

        legendes = []
        if "releve_incomplet" in df.columns and (df["releve_incomplet"] > 0).any():
            legendes.append(
                "* sur Injectée / Autoconsommée : pas de relevé d'injection "
                "Enedis ce jour-là "
                "— injection estimée d'après vos ratios mensuels observés."
            )
        if "conso_absente" in df.columns and (df["conso_absente"] > 0).any():
            legendes.append(
                "* sur Achetée au réseau : pas de relevé de consommation ce "
                "jour-là (données "
                "hors des 36 mois conservés par Enedis) — le total de la facture "
                "EDF de la période est réparti sur ses jours."
            )
        if legendes:
            note = QLabel("\n".join(legendes))
            note.setWordWrap(True)
            note.setStyleSheet(
                f"color: {self.theme['text_muted']}; font-size: 11px; padding-top: 4px;")
            self.layout_inner.addWidget(note)

    def _ligne_totaux(self, df, colonnes: list[str],
                      avec_ve: bool) -> QTableWidget:
        """Les totaux de la periode, sous le tableau, dans ses colonnes.

        A part du tableau lui-meme : quand on le trie en cliquant sur un
        en-tete, une ligne de totaux qui en ferait partie se retrouverait
        melee aux jours (audit du 14/09/2026).
        """
        def nombre(x: float, decimales: int) -> str:
            return (f"{x:,.{decimales}f}".replace(",", " ")
                    .replace(".", ","))

        credit = float(df["revenu_vente_eur"].sum() + df["economie_eur"].sum())
        debit = float(df["cout_reseau_eur"].sum())
        bilan = float(df["bilan_jour_eur"].sum())
        valeurs = ["Total",
                   nombre(df["production_kwh"].sum(), 1),
                   nombre(df["autoconsommation_kwh"].sum(), 1),
                   nombre(df["injection_kwh"].sum(), 1),
                   nombre(df["soutirage_kwh"].sum(), 1)]
        if avec_ve:
            valeurs.append(nombre(df["recharge_ve_kwh"].sum(), 1))
        valeurs += [nombre(credit, 2), nombre(debit, 2),
                    f"{'+' if bilan >= 0 else '-'}{nombre(abs(bilan), 2)}"]

        ligne = QTableWidget(1, len(colonnes))
        ligne.horizontalHeader().setVisible(False)
        ligne.verticalHeader().setVisible(False)
        ligne.setEditTriggers(QTableWidget.NoEditTriggers)
        ligne.setSelectionMode(QTableWidget.NoSelection)
        ligne.setFocusPolicy(Qt.NoFocus)
        ligne.setShowGrid(False)
        ligne.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        ligne.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for i in range(len(colonnes)):
            ligne.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)
        gras = QFont()
        gras.setBold(True)
        for c, texte in enumerate(valeurs):
            it = QTableWidgetItem(texte)
            it.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            it.setFont(gras)
            ligne.setItem(0, c, it)
        dernier = ligne.item(0, len(valeurs) - 1)
        dernier.setForeground(self._color(
            self.theme["credit"] if bilan >= 0 else self.theme["debit"]))
        ligne.setFixedHeight(36)
        ligne.setStyleSheet(
            f"QTableWidget {{ border: none; border-top: 1px solid "
            f"{self.theme['border_strong']}; background: "
            f"{self.theme['bg_panel_alt']}; }}")
        return ligne

    def _color(self, hex_color: str):
        return QColor(hex_color)
