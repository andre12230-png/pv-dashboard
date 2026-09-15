"""Vue Parametres : recapitulatif de la configuration courante."""
from __future__ import annotations

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

import calculations as calc
from gui_widgets import Card, SectionTitle, grid_row
from views._base import BaseView
from views._helpers import fmt_date_fr, fmt_eur, fmt_kwc, fmt_pct, fmt_prix_kwh


def _duree_ans(n) -> str:
    """'1 an', '5 ans' : l'ecran affichait « 1 ans »."""
    return f"{n} an" if float(n) <= 1 else f"{n} ans"


class SettingsView(BaseView):
    utilise_periode = False  # simple lecture de config.yaml
    # Ouvre la fenetre « Mes reglages » ; branche par MainWindow.
    ouvrir_reglages = None

    def populate(self, period: str) -> None:
        cfg = self.data.cfg
        inst = cfg["installation"]
        oa = cfg["oa"]
        # Facultative : qui n'a jamais eu de contrat a prix unique n'a pas
        # cette section dans son config.yaml.
        bleu = cfg["tarifs_reseau"].get("bleu_base") or {}
        octopus = cfg["tarifs_reseau"]["contrat_hphc"]

        # Le chemin exact : une fois l'application installee, le dossier des
        # donnees est cache dans %LOCALAPPDATA%, loin du programme.
        dossier = self.data.dossier_donnees or "le dossier de l'application"
        self.layout_inner.addWidget(SectionTitle(
            "Paramètres",
            "Bouton « Modifier mes réglages », ou, pour tout le reste, "
            f"config.yaml avec le Bloc-notes (dans {dossier}).",
        ))
        if callable(self.ouvrir_reglages):
            bouton = QPushButton("Modifier mes réglages")
            bouton.setCursor(Qt.PointingHandCursor)
            bouton.clicked.connect(self.ouvrir_reglages)
            self.layout_inner.addWidget(bouton, alignment=Qt.AlignLeft)

        cards = [
            self._kv_card("Installation", [
                ("Puissance crête", fmt_kwc(inst["puissance_kwc"])),
                ("Coût total", fmt_eur(inst["cout_total_eur"])),
                ("Mise en service", fmt_date_fr(inst["date_mise_en_service"])),
                ("Début du contrat OA", fmt_date_fr(inst["date_debut_contrat_oa"])),
            ]),
            self._kv_card("Contrat OA", [
                ("Type", "Vente du surplus" if oa["type"] == "surplus"
                 else "Vente totale"),
                ("Prix d'achat du surplus", fmt_prix_kwh(oa["prix_kwh_eur"])),
                ("Prime par kWc", fmt_eur(
                    oa["prime_autoconsommation"]["montant_par_kwc"]) + "/kWc"),
                ("Durée prime",
                 _duree_ans(oa['prime_autoconsommation']['duree_annees'])),
                ("Durée contrat", _duree_ans(oa['duree_contrat_annees'])),
            ]),
        ]
        self.layout_inner.addLayout(grid_row(cards))

        bleu_abo_rows = [(f"Abonn. {fmt_date_fr(t['debut'])} → {fmt_date_fr(t['fin'])}",
                          f"{fmt_eur(t['montant'])} / mois")
                         for t in (bleu.get("abonnement_par_periode") or [])]
        bleu_rows = [(f"kWh {fmt_date_fr(t['debut'])} → {fmt_date_fr(t['fin'])}",
                      fmt_prix_kwh(t["prix"]))
                     for t in (bleu.get("prix_kwh_par_periode") or [])]
        # Une ligne par periode de prix Octopus : les tarifs changent en cours
        # de contrat (revalorisation du 01/08/2026), l'ecran les montre tous.
        octopus_rows = []
        for p in calc.periodes_octopus(octopus):
            fin = fmt_date_fr(p["fin"]) if p.get("fin") else "en cours"
            libelle = f"{fmt_date_fr(p['debut'])} → {fin}"
            octopus_rows.append((libelle, (
                f"abonnement {fmt_eur(p['abonnement'])}/mois · "
                f"HP {fmt_prix_kwh(p['prix_hp'])} · "
                f"HC {fmt_prix_kwh(p['prix_hc'])}")))
        octopus_rows += [
            ("Plages HC", " / ".join(octopus["plages_hc"])),
            ("Part HC de l'autoconso (estimation)",
             fmt_pct(octopus.get("part_hc_autoconso", 0.20) * 100)),
        ]
        # Les deux titres portaient les dates du contrat de l'auteur. Elles
        # viennent maintenant de la date de bascule declaree en config.
        bascule = calc.CUTOFF_OCTOPUS
        veille = bascule - pd.Timedelta(days=1)
        cards2 = []
        if bleu_abo_rows or bleu_rows:
            cards2.append(self._kv_card(
                f"Prix unique (jusqu'au {veille:%d/%m/%Y})",
                bleu_abo_rows + bleu_rows))
        cards2.append(self._kv_card(
            f"Heures pleines / creuses (depuis le {bascule:%d/%m/%Y})",
            octopus_rows))
        self.layout_inner.addLayout(grid_row(cards2))

        self.layout_inner.addWidget(self._carte_recalages())
        self.layout_inner.addStretch(1)

    # Sections de config-local.yaml qui REECRIVENT les releves journaliers,
    # et ce qu'elles font, en clair.
    RECALAGES = [
        ("injection_facturee",
         "Injection recalée sur les factures de vente"),
        ("conso_reseau_facturee",
         "Consommation reconstituée à partir des factures"),
        ("conso_reseau_recalee",
         "Consommation recalée sur le total des factures"),
        ("conso_reseau_douteuse",
         "Journées déclarées non fiables, reconstituées"),
    ]

    def _carte_recalages(self) -> QFrame:
        """Dit si des totaux de factures reecrivent les releves, et lesquels.

        Ces recalages sont utiles -- une facture est plus juste qu'une somme
        de releves quotidiens -- mais ils modifient les chiffres affiches
        sans que rien ne le dise a l'ecran. Cette carte est l'endroit ou on
        peut le verifier.
        """
        sources = self.data.cfg.get("sources") or {}
        lignes = []
        for cle, libelle in self.RECALAGES:
            tranches = sources.get(cle) or []
            if tranches:
                lignes.append((libelle, f"{len(tranches)} période(s)"))
        if not lignes:
            lignes = [("Aucun recalage déclaré",
                       "les relevés sont affichés tels que saisis")]
        return self._kv_card(
            "Recalages sur factures (config-local.yaml)", lignes)

    def _kv_card(self, title: str, kvs) -> QFrame:
        """Une carte « libelle : valeur », en liste simple.

        Chaque ligne etait enfermee dans de petits cadres gris (un QWidget
        par ligne, qui prenait le fond de la page) : l'ecran faisait
        brouillon (audit du 14/09/2026). Desormais, des lignes separees par
        un simple filet.
        """
        card = Card()
        v = QVBoxLayout(card)
        v.setContentsMargins(20, 16, 20, 14)
        v.setSpacing(0)
        t = QLabel(title)
        t.setStyleSheet("font-weight: 700; font-size: 14px; padding-bottom: 8px;")
        v.addWidget(t)
        for i, (k, val) in enumerate(kvs):
            if i:
                filet = QFrame()
                filet.setFixedHeight(1)
                filet.setStyleSheet(
                    f"background: {self.theme['border']}; border: none;")
                v.addWidget(filet)
            row = QHBoxLayout()
            row.setContentsMargins(0, 7, 0, 7)
            row.setSpacing(12)
            k_l = QLabel(k)
            k_l.setStyleSheet(
                f"color: {self.theme['text_secondary']}; font-size: 12px;")
            v_l = QLabel(val)
            v_l.setStyleSheet(
                f"color: {self.theme['text_primary']}; font-weight: 600; "
                "font-size: 12px;")
            v_l.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(k_l, stretch=1)
            row.addWidget(v_l)
            v.addLayout(row)
        v.addStretch(1)
        return card
