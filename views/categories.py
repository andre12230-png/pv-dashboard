"""Vue Repartition energie : tuiles KPI, diagramme de flux, detail par poste.

Les trois camemberts d'origine ont ete remplaces, pour deux raisons :
  - ils prenaient 60 % de la hauteur de la page pour afficher trois ratios ;
  - surtout, deux d'entre eux etiquetaient "Autoconso" la meme valeur avec
    deux pourcentages differents (52,5 % de la production, 16,7 % de la
    consommation), parce que les denominateurs n'etaient pas les memes.
Ce sont deux indicateurs distincts : ils portent desormais deux noms
distincts (taux d'autoconsommation / couverture solaire), et le diagramme de
flux ne montre les kWh autoconsommes qu'une seule fois, sous forme d'un ruban
qui relie la production a la consommation.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from gui_theme import CHART_COLORS as CC
from gui_widgets import Card, KpiCard, KpiTile, SectionTitle, police_tabulaire
from views._base import BaseView
from views._helpers import (
    agreger,
    filter_period,
    fmt_eur,
    fmt_kwh,
    fmt_pct,
    libelle_periode,
    periode_precedente,
    variation,
)
from views._sankey import Flux, Noeud, SankeyWidget
from views.comparaison import date_limite_n1

# Comparaison N vs N-1 du bas de page : (colonne, libelle, unite, sens).
# sens=+1 si une hausse est une bonne nouvelle.
METRIQUES_COMPARAISON = [
    ("production_kwh",       "Production",       "kwh", +1),
    ("consommation_kwh",     "Consommation",     "kwh", -1),
    ("autoconsommation_kwh", "Autoconsommation", "kwh", +1),
    ("bilan_jour_eur",       "Bilan",            "eur", +1),
]


class CategoriesView(BaseView):
    def populate(self, period: str) -> None:
        df = filter_period(self.data.df, period, self.data.start_oa)
        if df.empty:
            self.layout_inner.addWidget(self._empty_card())
            return

        auto = df["autoconsommation_kwh"].sum()
        inj = df["injection_kwh"].sum()
        sout = df["soutirage_kwh"].sum()
        prod = df["production_kwh"].sum()
        conso = df["consommation_kwh"].sum()
        revenu = df["revenu_vente_eur"].sum()
        eco = df["economie_eur"].sum()
        cout = df["cout_reseau_eur"].sum()

        # 1) Rangee de tuiles : les trois chiffres cles, sans graphique.
        self.layout_inner.addLayout(
            self._tuiles(period, prod, auto, conso, revenu, eco, cout))

        # 2) Diagramme de flux.
        self.layout_inner.addWidget(SectionTitle(
            "Circulation de l'énergie",
            "Largeur des rubans proportionnelle aux kWh.",
        ))
        self.layout_inner.addWidget(self._carte_sankey(prod, inj, sout, conso, auto))

        # 3) Detail chiffre.
        ve = df["recharge_ve_kwh"].sum() if "recharge_ve_kwh" in df.columns else 0.0
        ve_eur = df["recharge_ve_eur"].sum() if "recharge_ve_eur" in df.columns else 0.0
        self.layout_inner.addWidget(SectionTitle("Détail par poste"))
        self.layout_inner.addWidget(
            self._detail_table(prod, auto, inj, sout, revenu, eco, cout, ve, ve_eur))

        # 4) Comparaison avec la meme periode l'an dernier.
        self.layout_inner.addWidget(self._bloc_comparaison(period))
        self.layout_inner.addStretch(1)

    # ------------------------------------------------------------------
    # 1) Tuiles KPI
    # ------------------------------------------------------------------
    def _tuiles(self, period: str, prod, auto, conso, revenu, eco, cout) -> QHBoxLayout:
        h = QHBoxLayout()
        h.setSpacing(14)

        taux = auto / prod * 100 if prod > 0 else 0.0
        couverture = auto / conso * 100 if conso > 0 else 0.0
        credits = revenu + eco
        bilan = credits - cout

        h.addWidget(KpiTile(
            "Taux d'autoconsommation", fmt_pct(taux),
            self._paire_kwh(auto, prod, "produits"),
            ratio=taux / 100, bar_color=CC["autoconso"],
            track_color=self.theme["border"]))

        h.addWidget(KpiTile(
            "Couverture solaire", fmt_pct(couverture),
            self._paire_kwh(auto, conso, "consommés"),
            ratio=couverture / 100, bar_color=CC["autoconso"],
            track_color=self.theme["border"]))

        h.addWidget(KpiTile(
            self._titre_bilan(period), fmt_eur(bilan, signed=True),
            f"{fmt_eur(credits, signed=True)} de crédits "
            f"− {fmt_eur(cout)} d'achat",
            value_color=CC["autoconso"] if bilan >= 0 else CC["soutirage"],
            track_color=self.theme["border"]))
        return h

    def _titre_bilan(self, period: str) -> str:
        """'Bilan du mois' n'a de sens que sur un mois ; on adapte."""
        if period and period.startswith("month-"):
            return "Bilan du mois"
        if period and (period.startswith("year-") or period.startswith("oa-")):
            return "Bilan de l'année"
        return "Bilan total"

    def _paire_kwh(self, part: float, total: float, suffixe: str) -> str:
        """'126,7 des 241,1 kWh produits' — meme unite pour les deux nombres.

        fmt_kwh bascule tout seul en MWh au-dela de 1000 : applique aux deux
        nombres separement, la phrase pourrait melanger les unites.
        """
        if total >= 1000:
            return (f"{part/1000:.2f} des {total/1000:.2f} MWh {suffixe}"
                    .replace(".", ","))
        return f"{part:.1f} des {total:.1f} kWh {suffixe}".replace(".", ",")

    # ------------------------------------------------------------------
    # 2) Diagramme de flux
    # ------------------------------------------------------------------
    def _carte_sankey(self, prod, inj, sout, conso, auto) -> QFrame:
        card = Card()
        v = QVBoxLayout(card)
        v.setContentsMargins(20, 16, 20, 16)

        gauche = [
            Noeud("production", "Production solaire", prod, CC["production"]),
            Noeud("soutirage", "Soutirage réseau", sout, CC["soutirage"]),
        ]
        droite = [
            Noeud("injection", "Injection réseau", inj, CC["injection"]),
            Noeud("consommation", "Consommation foyer", conso, CC["primary"]),
        ]
        # Chaque ruban porte son nom et sa couleur. C'est la seule facon de
        # nommer l'autoconsommation, qui n'est ni un noeud de depart ni un
        # noeud d'arrivee mais le chemin entre les deux. Les couleurs sont
        # celles du tableau "Detail par poste" juste en dessous.
        flux = [
            Flux("production", "injection", inj,
                 "Vendu au réseau", CC["injection"]),
            Flux("production", "consommation", auto,
                 "Autoconsommation", CC["autoconso"]),
            Flux("soutirage", "consommation", sout,
                 "Acheté au réseau", CC["soutirage"]),
        ]
        # Le diagramme est borne en largeur (LARGEUR_MAXI) pour que les rubans
        # gardent une pente visible ; deux ressorts le centrent dans la carte.
        ligne = QHBoxLayout()
        ligne.setContentsMargins(0, 0, 0, 0)
        ligne.addStretch(1)
        ligne.addWidget(SankeyWidget(gauche, droite, flux, self.theme,
                                     hauteur=300))
        ligne.addStretch(1)
        v.addLayout(ligne)

        total = QLabel(f"Total qui entre = total qui sort = {fmt_kwh(prod + sout)}")
        total.setAlignment(Qt.AlignCenter)
        total.setStyleSheet(
            f"color: {self.theme['text_muted']}; font-size: 11px; "
            f"background: transparent;")
        v.addWidget(total)
        return card

    # ------------------------------------------------------------------
    # 3) Tableau detaille
    # ------------------------------------------------------------------
    def _detail_table(self, prod, auto, inj, sout, revenu, eco, cout,
                      ve: float = 0.0, ve_eur: float = 0.0) -> QFrame:
        card = Card()
        v = QVBoxLayout(card)
        v.setContentsMargins(20, 14, 20, 16)

        grille = QGridLayout()
        grille.setHorizontalSpacing(18)
        grille.setVerticalSpacing(0)
        grille.setColumnStretch(0, 1)   # le libelle prend la place restante
        grille.setColumnMinimumWidth(1, 110)
        grille.setColumnMinimumWidth(2, 90)
        grille.setColumnMinimumWidth(3, 110)

        for col, titre in enumerate(["Poste", "Énergie", "€/kWh", "Impact"]):
            lbl = QLabel(titre)
            lbl.setObjectName("GridHeader")
            lbl.setAlignment(Qt.AlignLeft if col == 0
                             else Qt.AlignRight | Qt.AlignVCenter)
            lbl.setContentsMargins(0, 0, 0, 8)
            grille.addWidget(lbl, 0, col)
        grille.addWidget(self._filet(), 1, 0, 1, 4)

        ligne = 2

        def poste(nom, couleur, kwh, montant=None, sous_ligne=False):
            nonlocal ligne
            grille.addWidget(self._cellule_poste(nom, couleur, sous_ligne),
                             ligne, 0)
            grille.addWidget(self._cellule_nombre(fmt_kwh(kwh)), ligne, 1)
            grille.addWidget(self._cellule_nombre(self._prix_kwh(montant, kwh)),
                             ligne, 2)
            if montant is None:
                grille.addWidget(self._cellule_nombre("—"), ligne, 3)
            else:
                couleur_montant = (CC["autoconso"] if montant >= 0
                                   else CC["soutirage"])
                grille.addWidget(
                    self._cellule_nombre(fmt_eur(montant, signed=True),
                                         couleur_montant, gras=True),
                    ligne, 3)
            ligne += 1

        # Bloc production : ce que les panneaux fabriquent, et ou ca va.
        poste("Production solaire", CC["production"], prod)
        poste("Autoconsommation", CC["autoconso"], auto, eco)
        poste("Injection réseau (vente OA)", CC["injection"], inj, revenu)

        # Filet de separation : sans lui, on additionne machinalement les six
        # lignes et on croit a une consommation de 1 262 kWh.
        grille.addWidget(self._filet(), ligne, 0, 1, 4)
        ligne += 1

        # Bloc consommation : ce qu'on achete au reseau, et a quoi ca sert.
        poste("Soutirage réseau (achat)", CC["soutirage"], sout, -cout)
        if ve > 0:
            # Le cout de la recharge vient de l'appli recharges-ve (vraies
            # plages horaires, presque tout en heures creuses) ; le reste du
            # soutirage porte donc le solde, dont l'abonnement.
            poste("dont recharge véhicule", CC["soutirage"], ve, -ve_eur,
                  sous_ligne=True)
            poste("dont reste du foyer", CC["soutirage"], sout - ve,
                  -(cout - ve_eur), sous_ligne=True)

        v.addLayout(grille)
        return card

    def _filet(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.HLine)
        f.setFixedHeight(1)
        f.setStyleSheet(f"background: {self.theme['border_strong']}; border: none;")
        return f

    def _cellule_poste(self, nom: str, couleur: str, sous_ligne: bool) -> QWidget:
        """Pastille de couleur + libelle, indente si c'est une sous-ligne."""
        w = QWidget()
        w.setObjectName("PosteCell")
        h = QHBoxLayout(w)
        # 24 px d'indentation : les sous-lignes decomposent le soutirage, elles
        # ne s'ajoutent pas a lui.
        h.setContentsMargins(24 if sous_ligne else 0, 9, 0, 9)
        h.setSpacing(10)

        pastille = QLabel()
        pastille.setFixedSize(10, 10)
        pastille.setStyleSheet(f"background: {couleur}; border-radius: 5px;")
        h.addWidget(pastille)

        lbl = QLabel(nom)
        couleur_texte = (self.theme["text_muted"] if sous_ligne
                         else self.theme["text_primary"])
        lbl.setStyleSheet(f"color: {couleur_texte}; font-size: 13px; "
                          f"background: transparent;")
        h.addWidget(lbl)
        h.addStretch(1)
        return w

    def _cellule_nombre(self, texte: str, couleur: str | None = None,
                        gras: bool = False) -> QLabel:
        lbl = QLabel(texte)
        lbl.setObjectName("GridCell")
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl.setFont(police_tabulaire(10, gras=gras))
        lbl.setStyleSheet(
            f"color: {couleur or self.theme['text_secondary']}; "
            f"background: transparent;")
        return lbl

    def _prix_kwh(self, montant: float | None, kwh: float) -> str:
        """Prix unitaire du poste, en euros par kWh.

        C'est la colonne qui explique d'un coup d'oeil pourquoi 114 kWh
        vendus rapportent moins que 127 kWh autoconsommes : le tarif de rachat
        est deux fois plus bas que le prix auquel on achete son electricite.
        """
        if montant is None or kwh <= 0:
            return "—"
        return f"{abs(montant) / kwh:.3f}".replace(".", ",")

    # ------------------------------------------------------------------
    # 4) Comparaison N vs N-1
    # ------------------------------------------------------------------
    def _bloc_comparaison(self, period: str) -> QWidget:
        precedente = periode_precedente(period)
        boite = QWidget()
        v = QVBoxLayout(boite)
        v.setContentsMargins(0, 8, 0, 0)
        v.setSpacing(0)

        if precedente is None:
            v.addWidget(SectionTitle("Comparaison avec l'année précédente"))
            v.addWidget(self._empty_card(
                "Choisissez un mois ou une année dans le menu déroulant "
                "en haut pour comparer avec la même période l'an dernier."))
            return boite

        cles = [cle for cle, *_ in METRIQUES_COMPARAISON]
        df_n = filter_period(self.data.df, period, self.data.start_oa)
        df_n1 = filter_period(self.data.df, precedente, self.data.start_oa)
        # Une periode en cours est comparee aux MEMES dates de l'an passe,
        # comme dans l'onglet Comparaison N vs N-1 et au tableau de bord.
        # Face au mois entier, 13 jours de septembre affichaient « -44,8 % »
        # de production quand le tableau de bord annoncait « +24 % ».
        limite = date_limite_n1(df_n, period, self.data.start_oa)
        suffixe_n = suffixe_n1 = ""
        if limite is not None and not df_n1.empty:
            df_n1 = df_n1[df_n1.index.normalize() <= limite]
            suffixe_n = f" (au {df_n.index.max():%d/%m})"
            suffixe_n1 = f" (au {limite:%d/%m})"
        agg_n = agreger(df_n, cles)
        agg_n1 = agreger(df_n1, cles)

        titre = (f"{libelle_periode(period)}{suffixe_n} vs "
                 f"{libelle_periode(precedente).lower()}{suffixe_n1}")
        v.addWidget(SectionTitle("Comparaison avec l'année précédente", titre))

        if agg_n1 is None:
            v.addWidget(self._empty_card(
                f"Aucun relevé sur {libelle_periode(precedente).lower()} : "
                "la comparaison n'est pas possible."))
            return boite

        ligne = QHBoxLayout()
        ligne.setSpacing(14)
        for cle, label, unite, sens in METRIQUES_COMPARAISON:
            fmt = fmt_kwh if unite == "kwh" else fmt_eur
            val_n = agg_n.get(cle, 0.0) if agg_n else 0.0
            val_n1 = agg_n1.get(cle, 0.0)
            txt, couleur = variation(val_n - val_n1, val_n1, fmt, sens,
                                     self.theme)
            carte = KpiCard(label, fmt(val_n),
                            f"{txt}\nN-1 : {fmt(val_n1)}",
                            variant=self._variant(cle, val_n))
            carte.sub.setStyleSheet(
                f"color: {couleur}; font-size: 11px; font-weight: 600; "
                f"background: transparent;")
            carte.setMinimumHeight(118)
            ligne.addWidget(carte)
        v.addLayout(ligne)
        return boite

    def _variant(self, cle: str, valeur: float) -> str:
        """Couleur du liseré gauche : la meme que dans le diagramme de flux."""
        if cle == "bilan_jour_eur":
            return "solaire" if valeur >= 0 else "reseau"
        return {"production_kwh": "prod",
                "consommation_kwh": "total",
                "autoconsommation_kwh": "solaire"}.get(cle, "neutral")
