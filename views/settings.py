"""Vue Parametres : recapitulatif de la configuration courante."""
from __future__ import annotations

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
)

import calculations as calc
from accords import pluriel
from gui_widgets import Card, SectionTitle, grid_row
from views._base import BaseView
from views._helpers import du_au, fmt_date_fr, fmt_eur, fmt_kwc, fmt_pct, fmt_prix_kwh


def _recentes_d_abord(periodes) -> list:
    """Les periodes de prix, la plus recente en premier (10/10/2026)."""
    return sorted(periodes or [], key=lambda t: str(t.get("debut") or ""),
                  reverse=True)


def _duree_ans(n) -> str:
    """'1 an', '5 ans' : l'ecran affichait « 1 ans »."""
    return f"{n} an" if float(n) <= 1 else f"{n} ans"


class SettingsView(BaseView):
    utilise_periode = False  # simple lecture de config.yaml
    # Ouvre la fenetre « Mes reglages » ; branche par MainWindow.
    ouvrir_reglages = None
    # Theme Clair / Sombre (12/10/2026) ; branches par MainWindow :
    # apparence_choisie() rend « clair » ou « sombre », choisir_apparence(nom)
    # l'enregistre dans les preferences.
    apparence_choisie = None
    choisir_apparence = None

    def populate(self, period: str) -> None:
        cfg = self.data.cfg
        inst = cfg["installation"]
        oa = self.data.oa
        # Facultative : qui n'a jamais eu de contrat a prix unique n'a pas
        # cette section dans son config.yaml.
        bleu = cfg["tarifs_reseau"].get("bleu_base") or {}
        octopus = cfg["tarifs_reseau"]["contrat_hphc"]

        # Le chemin exact : une fois l'application installee, le dossier des
        # donnees est cache dans %LOCALAPPDATA%, loin du programme.
        dossier = self.data.dossier_donnees or "le dossier de l'application"
        # Sans titre : il redisait celui de la page (30/09/2026).
        self.layout_inner.addWidget(SectionTitle(
            "",
            "Pour changer ces valeurs, cliquez sur « Modifier mes "
            "réglages ». Les réglages plus rares se changent dans le fichier "
            f"config.yaml, avec le Bloc-notes (dossier {dossier}).",
        ))
        if callable(self.ouvrir_reglages):
            bouton = QPushButton("Modifier mes réglages")
            # La meme allure que les boutons de la Saisie (30/09/2026).
            bouton.setObjectName("ActionBtn")
            bouton.setCursor(Qt.PointingHandCursor)
            bouton.clicked.connect(self.ouvrir_reglages)
            self.layout_inner.addWidget(bouton, alignment=Qt.AlignLeft)

        # Vente du surplus, vente totale, ou pas de vente : les lignes suivent
        # le contrat declare (voir build_dataset), sans rien supposer.
        installation = [
            ("Puissance crête", fmt_kwc(inst["puissance_kwc"])),
            ("Coût total", fmt_eur(inst["cout_total_eur"])),
            ("Mise en service", fmt_date_fr(inst["date_mise_en_service"])),
        ]
        if self.data.start_oa is not None:
            installation.append(("Début du contrat de vente",
                                 fmt_date_fr(self.data.start_oa)))
        if oa.type == "aucune":
            contrat = [("Type", "Pas de vente : l'injection n'est pas payée")]
        else:
            contrat = [
                ("Type", "Vente du surplus" if oa.type == "surplus"
                 else "Vente de toute la production"),
                ("Acheteur", self.data.acheteur),
                # « rachat », comme dans Mes reglages : « achat » designe
                # l'electricite achetee au reseau (30/09/2026).
                ("Prix de rachat du kWh", fmt_prix_kwh(oa.prix_kwh)),
            ]
            if oa.type == "surplus":
                contrat += [
                    ("Prime par kWc", fmt_eur(oa.prime_par_kwc) + "/kWc"),
                    ("Durée de la prime", _duree_ans(oa.prime_duree)),
                ]
            contrat.append(("Durée du contrat", _duree_ans(oa.duree_contrat)))
        cards = [
            self._kv_card("Installation", installation),
            self._kv_card("Vente" if oa.type == "aucune"
                          else "Contrat OA" if self.data.acheteur == "EDF OA"
                          else "Contrat de vente", contrat),
        ]
        self.layout_inner.addLayout(grid_row(cards))

        # Libelles entiers, sans « Abonn. » ni « HC » (journal du 01/10/2026).
        # La periode la plus recente en haut (10/10/2026), quel que soit
        # l'ordre du fichier.
        bleu_abo_rows = [(f"Abonnement {du_au(t['debut'], t['fin'])}",
                          f"{fmt_eur(t['montant'])} / mois")
                         for t in _recentes_d_abord(
                             bleu.get("abonnement_par_periode"))]
        bleu_rows = [(f"Prix du kWh {du_au(t['debut'], t['fin'])}",
                      fmt_prix_kwh(t["prix"]))
                     for t in _recentes_d_abord(
                         bleu.get("prix_kwh_par_periode"))]
        # Une ligne par periode de prix Octopus : les tarifs changent en cours
        # de contrat (revalorisation du 01/08/2026), l'ecran les montre tous.
        octopus_rows = []
        for p in reversed(calc.periodes_octopus(octopus)):
            libelle = (du_au(p["debut"], p["fin"]).capitalize() if p.get("fin")
                       else f"Depuis le {fmt_date_fr(p['debut'])}, en cours")
            octopus_rows.append((libelle, (
                f"abonnement {fmt_eur(p['abonnement'])}/mois · "
                f"HP {fmt_prix_kwh(p['prix_hp'])} · "
                f"HC {fmt_prix_kwh(p['prix_hc'])}")))
        octopus_rows += [
            ("Plages d'heures creuses", " / ".join(octopus["plages_hc"])),
            ("Part de l'autoconsommation en heures creuses",
             fmt_pct(self.data.octopus.part_hc_autoconso * 100)
             + ("" if octopus.get("part_hc_autoconso") is not None
                else " — estimée d'après vos heures creuses")),
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
        if callable(self.apparence_choisie) and callable(self.choisir_apparence):
            self.layout_inner.addWidget(self._carte_apparence())
        self.layout_inner.addStretch(1)

    def _carte_apparence(self) -> QFrame:
        """Le choix du theme, Clair ou Sombre (12/10/2026).

        Il s'applique au prochain demarrage : changer a chaud obligerait
        chaque page ouverte a se redessiner (voir gui_theme.py). Le reglage
        de Windows n'est jamais suivi : c'est l'application qui decide.
        """
        card = Card(titre="Apparence",
                    sous_titre="S'applique au prochain démarrage de l'application")
        v = card.corps
        v.setContentsMargins(20, 10, 20, 14)
        self._groupe_apparence = QButtonGroup(card)
        ligne = QHBoxLayout()
        ligne.setSpacing(24)
        choisi = self.apparence_choisie()
        for nom, libelle in (("clair", "Clair"), ("sombre", "Sombre")):
            bouton = QRadioButton(libelle)
            bouton.setChecked(nom == choisi)
            bouton.setCursor(Qt.PointingHandCursor)
            # nom=nom : chaque bouton garde son propre nom.
            bouton.toggled.connect(
                lambda coche, nom=nom: coche and self.choisir_apparence(nom))
            self._groupe_apparence.addButton(bouton)
            ligne.addWidget(bouton)
        ligne.addStretch(1)
        v.addLayout(ligne)
        return card

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
                lignes.append((libelle, pluriel(len(tranches), "période")))
        if not lignes:
            lignes = [("Aucun recalage déclaré",
                       "les relevés sont affichés tels que saisis")]
        return self._kv_card(
            "Recalages sur factures", lignes,
            sous_titre="Déclarés dans le fichier config-local.yaml")

    def _kv_card(self, title: str, kvs, sous_titre: str = "") -> QFrame:
        """Une carte « libelle : valeur », en liste simple.

        Chaque ligne etait enfermee dans de petits cadres gris (un QWidget
        par ligne, qui prenait le fond de la page) : l'ecran faisait
        brouillon (audit du 14/09/2026). Desormais, des lignes separees par
        un simple filet.
        """
        # Titre dans le bandeau de la carte, comme les autres (30/09/2026).
        card = Card(titre=title, sous_titre=sous_titre)
        v = card.corps
        v.setContentsMargins(20, 10, 20, 14)
        v.setSpacing(0)
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
