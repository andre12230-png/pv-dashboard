"""La fenetre « Mes reglages » : decrire son installation sans Bloc-notes.

Toute la logique (lecture, ecriture prudente de config.yaml) est dans
reglages.py ; ici, seulement les cases a remplir et leurs explications.
"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, QLocale, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import calculations as calc
from erreurs import erreur_en_clair
from gui_widgets import Card
from reglages import (
    SORTES_RECALAGE,
    ReglagesRefuses,
    libelle_recalage,
    phrase_prime,
    prime_par_kwc_depuis_total,
    prime_totale,
    recalages_vides,
)

TITRE = "Mes réglages"
FRANCAIS = QLocale(QLocale.French, QLocale.France)


def _nombre(valeur: float, decimales: int, suffixe: str,
            maximum: float) -> QDoubleSpinBox:
    """Une case a nombre, virgule decimale a la francaise."""
    case = QDoubleSpinBox()
    case.setLocale(FRANCAIS)
    case.setDecimals(decimales)
    case.setRange(0, maximum)
    case.setSuffix(suffixe)
    # « 15 000 € » et non « 15000 € » : les milliers separes, comme dans
    # le texte juste dessous et partout ailleurs (30/09/2026).
    case.setGroupSeparatorShown(True)
    case.setValue(valeur)
    case.setMinimumWidth(140)
    return case


def _date(valeur: date) -> QDateEdit:
    """Une case a date, avec un petit calendrier."""
    case = QDateEdit(QDate(valeur.year, valeur.month, valeur.day))
    case.setCalendarPopup(True)
    case.setDisplayFormat("dd/MM/yyyy")
    case.setMinimumWidth(140)
    return case


def _en_date(case: QDateEdit) -> date:
    d = case.date()
    return date(d.year(), d.month(), d.day())


class LigneRecalage(QWidget):
    """Une periode de recalage : sa sorte, ses dates, son total, sa source.

    Les jours douteux n'ont pas de total en kWh -- leur case se grise, et le
    texte devient un motif (« panne Linky ») plutot qu'une reference de
    facture.
    """

    def __init__(self, cle: str, periode: dict, retirer,
                 acheteur: str = "EDF OA"):
        super().__init__()
        ligne = QHBoxLayout(self)
        ligne.setContentsMargins(0, 0, 0, 0)
        ligne.setSpacing(6)

        self.sorte = QComboBox()
        for k in SORTES_RECALAGE:
            self.sorte.addItem(libelle_recalage(k, acheteur), k)
        self.sorte.setCurrentIndex(list(SORTES_RECALAGE).index(cle))
        self.sorte.setMinimumWidth(200)
        self.sorte.currentIndexChanged.connect(self._sorte_changee)

        self.debut = _date(periode.get("debut") or date.today())
        self.fin = _date(periode.get("fin") or date.today())
        for case in (self.debut, self.fin):
            case.setMinimumWidth(110)
        self.total = _nombre(float(periode.get("total_kwh") or 0), 1, " kWh",
                             1_000_000)
        # Assez large pour « 999999,9 kWh » : tronque, un total ne se relit
        # pas, et c'est justement le chiffre qu'on vient verifier.
        self.total.setMinimumWidth(130)
        self.source = QLineEdit(str(periode.get("source")
                                    or periode.get("motif") or ""))
        self.source.setMinimumWidth(130)
        # Sans cela, un texte plus long que la case s'affiche par sa fin :
        # on croit le debut perdu.
        self.source.setCursorPosition(0)

        bouton = QPushButton("✕")
        bouton.setFixedWidth(30)
        bouton.setToolTip("Retirer cette ligne")
        bouton.clicked.connect(lambda: retirer(self))

        for case in (self.sorte, self.debut, self.fin, self.total,
                     self.source, bouton):
            ligne.addWidget(case)
        self._sorte_changee()

    def _sorte_changee(self) -> None:
        champ = SORTES_RECALAGE[self.sorte.currentData()][1]
        self.total.setEnabled(champ is not None)
        self.source.setPlaceholderText(
            "d'où vient ce total (facture du…)" if champ
            else "pourquoi ces jours sont douteux")

    def valeurs(self) -> tuple:
        """(cle de la sorte, periode) au format de reglages.lire_recalages."""
        cle = self.sorte.currentData()
        periode = {"debut": _en_date(self.debut), "fin": _en_date(self.fin)}
        champ = SORTES_RECALAGE[cle][1]
        if champ:
            periode[champ] = round(self.total.value(), 1)
            periode["source"] = self.source.text().strip()
        else:
            periode["motif"] = self.source.text().strip()
        return cle, periode


class FenetreReglages(QDialog):
    """enregistrer(valeurs) ecrit les reglages ; s'il leve une erreur, la
    fenetre reste ouverte et l'affiche."""

    def __init__(self, valeurs: dict, enregistrer, parent=None,
                 recalages: dict | None = None, enregistrer_recalages=None):
        super().__init__(parent)
        self._enregistrer = enregistrer
        self._enregistrer_recalages = enregistrer_recalages
        # Nomme dans les recalages (« Injection payee par ... »).
        self._acheteur_nom = valeurs.get("acheteur") or "EDF OA"
        self.setWindowTitle(TITRE)
        self.setMinimumWidth(620)
        # Plus large quand les recalages sont la : leur rangee compte six
        # cases, et une fenetre trop etroite ferait apparaitre une barre de
        # defilement horizontale.
        self.resize(830, 820) if enregistrer_recalages else self.resize(660, 760)

        corps = QWidget()
        v = QVBoxLayout(corps)
        v.setSpacing(14)

        intro = QLabel(
            "Décrivez votre installation et vos contrats. Ces valeurs se "
            "lisent sur la facture de l'installateur, votre contrat de vente "
            "(EDF OA, le plus souvent) et la fiche tarifaire de votre "
            "fournisseur. Tout se change plus tard, ici même.")
        intro.setWordWrap(True)
        v.addWidget(intro)

        # --- Mon installation ------------------------------------------
        self.puissance = _nombre(valeurs["puissance_kwc"], 2, " kWc", 100)
        self.cout = _nombre(valeurs["cout_total_eur"], 0, " €", 1_000_000)
        self.mise_en_service = _date(valeurs["date_mise_en_service"])
        self.debut_oa = _date(valeurs["date_debut_contrat_oa"])
        v.addWidget(self._groupe("Mon installation", [
            ("Puissance des panneaux", self.puissance),
            ("Coût total, pose comprise", self.cout),
            ("Date de mise en service", self.mise_en_service),
            ("Début du contrat de vente", self.debut_oa),
        ], "L'année du contrat de vente commence à sa date de début et dure "
           "un an. Sans vente, cette date ne sert pas."))

        # --- Ma vente d'electricite ---------------------------------------
        # Vente du surplus (avec prime), de toute la production, ou pas de
        # vente : les cases qui ne servent pas sont grisees (_maj_type_vente)
        # et leur contenu n'est pas ecrit dans config.yaml.
        self.type_vente = QComboBox()
        for texte, code in (("Je vends mon surplus", "surplus"),
                            ("Je vends toute ma production", "totale"),
                            ("Je ne vends pas mon électricité", "aucune")):
            self.type_vente.addItem(texte, code)
        self.type_vente.setCurrentIndex(max(
            self.type_vente.findData(valeurs.get("type_vente", "surplus")), 0))
        self.acheteur = QLineEdit(valeurs.get("acheteur", "EDF OA"))
        self.acheteur.setPlaceholderText("EDF OA")
        self.prix_oa = _nombre(valeurs["prix_oa"], 4, " €/kWh", 5)
        # La prime se saisit au choix : en tout, ou par kWc. Le fichier de
        # configuration, lui, garde toujours le montant PAR kWc -- rien a
        # convertir dans les reglages existants. Le choix s'ouvre sur « en
        # tout » : c'est ce que l'utilisateur a sous les yeux, le montant
        # touche avec sa premiere facture (retour du 19/09/2026).
        self.mode_prime = QComboBox()
        self.mode_prime.addItems(["en tout", "par kWc"])
        self.prime = _nombre(
            prime_totale(valeurs["prime_par_kwc"], valeurs["puissance_kwc"]),
            2, " €", 1_000_000)
        self.prime_duree = QSpinBox()
        self.prime_duree.setRange(1, 20)
        # « 1 an », « 5 ans » : le suffixe suit la valeur (c'etait « an(s) »).
        self.prime_duree.valueChanged.connect(
            lambda n: self.prime_duree.setSuffix(" an" if n <= 1 else " ans"))
        self.prime_duree.setValue(valeurs["prime_duree"])
        self.prime_duree.setSuffix(
            " an" if self.prime_duree.value() <= 1 else " ans")
        # Cette ligne montre l'unite que l'utilisateur n'a PAS sous les yeux,
        # et se recalcule a chaque frappe. Sans elle, on saisit son total dans
        # une case qui attend des euros par kWc, et l'installation parait
        # amortie en un an.
        self.total_prime = QLabel()
        self.total_prime.setWordWrap(True)
        self.total_prime.setStyleSheet(
            "color: #000000; font-size: 12px; font-weight: 600;")
        for case in (self.puissance, self.prime):
            case.valueChanged.connect(self._montrer_total_prime)
        self.prime_duree.valueChanged.connect(self._montrer_total_prime)
        self.mode_prime.currentIndexChanged.connect(self._changer_mode_prime)
        self._montrer_total_prime()

        v.addWidget(self._groupe("Ma vente d'électricité", [
            ("Ce que je vends", self.type_vente),
            ("Acheteur", self.acheteur),
            ("Prix de rachat du kWh", self.prix_oa),
            ("Prime saisie", self.mode_prime),
            ("Prime à l'autoconsommation", self.prime),
            ("Prime versée sur", self.prime_duree),
            ("", self.total_prime),
        ], "Prix hors taxes, fixé par votre contrat pour toute sa durée.<br><br>"
           "<b>La prime se saisit comme vous l'avez reçue</b> : « en tout », "
           "le montant versé avec votre première facture, ou « par kWc », "
           "comme l'écrit l'arrêté tarifaire. La ligne au-dessous montre "
           "l'autre valeur — vérifiez qu'elle correspond à votre "
           "attestation.<br><br>"
           "Elle est versée <b>en une seule fois</b> pour les contrats récents "
           "(mettez 1 an), sur 5 ans pour les plus anciens. Elle ne concerne "
           "que la vente du surplus."))
        self.type_vente.currentIndexChanged.connect(self._maj_type_vente)
        self._maj_type_vente()

        # --- Mon fournisseur ---------------------------------------------
        self.nom = QLineEdit(valeurs["nom"])
        self.nom.setPlaceholderText("TotalEnergies, EDF, Engie…")
        self.offre = QLineEdit(valeurs["offre"])
        self.offre.setPlaceholderText("nom de l'offre (facultatif)")
        self.abonnement = _nombre(valeurs["abonnement"], 2, " €/mois", 1000)
        self.prix_hp = _nombre(valeurs["prix_hp"], 4, " €/kWh", 5)
        self.prix_hc = _nombre(valeurs["prix_hc"], 4, " €/kWh", 5)
        self.plages = QLineEdit(" ; ".join(valeurs["plages_hc"]))
        self.plages.setPlaceholderText("22:00-06:00 ; 14:00-16:00")
        self.prix_depuis = _date(valeurs["prix_depuis"])
        # Pourcentage a l'ecran, fraction dans config.yaml (0.20 = 20 %).
        # On retient ce que la case affichait a l'ouverture : tant qu'elle
        # n'a pas bouge, c'est la valeur lue, exacte, qui repart (voir
        # _part_hc).
        self._part_hc_lue = valeurs["part_hc_autoconso"]
        # Part non ecrite dans le fichier : la case montre l'estimation, et
        # tant qu'on n'y touche pas, rien n'est ecrit (voir _part_hc).
        self._part_hc_declaree = valeurs.get("part_hc_declaree", True)
        self.part_hc = _nombre(self._part_hc_lue * 100, 0, " %", 100)
        self._part_hc_affichee = self.part_hc.value()
        # L'estimation d'apres les plages, a cote de la case, et un bouton
        # pour la reprendre. Elle suit les plages tapees.
        self.estimation_hc = QLabel()
        self.estimation_hc.setStyleSheet("color: #555555;")
        self.bouton_estimation = QPushButton("Reprendre")
        self.bouton_estimation.setToolTip(
            "Mettre dans la case l'estimation d'après vos heures creuses.")
        self.bouton_estimation.clicked.connect(self._reprendre_estimation)
        self._estimation = 0.0
        self.plages.textChanged.connect(self._maj_estimation)
        self._maj_estimation()
        ligne_part = QWidget()
        rangee = QHBoxLayout(ligne_part)
        rangee.setContentsMargins(0, 0, 0, 0)
        rangee.addWidget(self.part_hc)
        rangee.addWidget(self.estimation_hc, 1)
        rangee.addWidget(self.bouton_estimation)
        v.addWidget(self._groupe("Mon fournisseur d'électricité", [
            ("Fournisseur", self.nom),
            ("Offre", self.offre),
            ("Abonnement", self.abonnement),
            ("Prix heures pleines", self.prix_hp),
            ("Prix heures creuses", self.prix_hc),
            ("Heures creuses", self.plages),
            ("Ces prix s'appliquent depuis le", self.prix_depuis),
            ("Autoconsommation en heures creuses", ligne_part),
        ], "Prix TTC, pour la puissance de votre compteur. En option Base "
           "(prix unique), mettez le même prix en heures pleines et en heures "
           "creuses. Vous êtes chez EDF ? Écrivez EDF : l'onglet de "
           "comparaison avec EDF disparaîtra.<br><br>"
           "<b>Heures creuses</b> : elles figurent sur votre facture. "
           "Écrivez-les sous la forme 22:00-06:00 ; s'il y en a plusieurs, "
           "séparez-les par un point-virgule : 23:00-05:00 ; 14:00-16:00."
           "<br><br>"
           "<b>Vos prix ont changé ?</b> Indiquez la date du changement : "
           "les anciens prix restent appliqués aux mois d'avant. (Les prix "
           "d'exemple de l'installation livrée, eux, sont remplacés : vos "
           "premiers prix s'appliquent aussi aux mois d'avant.)<br><br>"
           "<b>Autoconsommation en heures creuses</b> : la part du courant "
           "de vos panneaux que vous auriez payée au prix des heures creuses, "
           "s'il avait fallu l'acheter. Vos panneaux produisent le jour : si "
           "toutes vos heures creuses sont la nuit, c'est 0 %. Avec une plage "
           "l'après-midi, une partie de votre production tombe dedans. "
           "L'estimation à côté part de vos plages et d'une journée de soleil "
           "type ; « Reprendre » la met dans la case. Sans valeur de votre "
           "part, c'est elle qui sert. Ce réglage chiffre ce que votre "
           "autoconsommation vous fait économiser."))

        # --- Recalages sur factures -------------------------------------
        if enregistrer_recalages is not None:
            v.addWidget(self._groupe_recalages(recalages or recalages_vides()))
        v.addStretch(1)

        defilement = QScrollArea()
        defilement.setWidgetResizable(True)
        defilement.setFrameShape(QScrollArea.NoFrame)
        defilement.setWidget(corps)

        boutons = QHBoxLayout()
        boutons.addStretch(1)
        annuler = QPushButton("Annuler")
        annuler.clicked.connect(self.reject)
        self.btn_enregistrer = QPushButton("Enregistrer")
        self.btn_enregistrer.setDefault(True)
        self.btn_enregistrer.clicked.connect(self._on_enregistrer)
        boutons.addWidget(annuler)
        boutons.addWidget(self.btn_enregistrer)

        tout = QVBoxLayout(self)
        tout.addWidget(defilement, stretch=1)
        tout.addLayout(boutons)

    def _groupe_recalages(self, recalages: dict) -> Card:
        """Le tableau des recalages : une ligne par periode, plus un bouton."""
        groupe = Card(titre="Recalages sur mes factures")
        dehors = groupe.corps

        note = QLabel(
            "Facultatif, et à manier avec soin. Ces lignes <b>réécrivent vos "
            "relevés</b> pour retomber sur le total d'une facture : l'écart "
            "est réparti sur les jours de la période.<br><br>"
            f"<b>{libelle_recalage('injection_facturee', self._acheteur_nom)}"
            "</b> : le total en kWh de "
            "votre autofacturation — pas le montant en euros. C'est ce que le "
            "compteur a compté, qui diffère un peu de ce qu'annonce "
            "l'onduleur.<br>"
            "<b>Conso recalée sur facture</b> : quand vos relevés sont arrondis "
            "et que la facture donne le vrai total.<br>"
            "<b>Conso connue par la facture</b> : périodes dont "
            "le détail quotidien n'existe plus chez Enedis (36 mois).<br>"
            "<b>Jours douteux</b> : ils sont traités comme s'ils n'avaient "
            "pas de relevé.<br><br>"
            "Ces réglages n'appartiennent qu'à votre installation : ils "
            "s'écrivent dans <code>config-local.yaml</code>, qui ne part "
            "jamais avec le programme.")
        note.setTextFormat(Qt.RichText)
        note.setWordWrap(True)
        note.setStyleSheet("color: #666666; font-size: 11px;")
        dehors.addWidget(note)

        entetes = QHBoxLayout()
        entetes.setSpacing(6)
        for titre, largeur in (("Ce qu'on recale", 200), ("Du", 110),
                               ("Au", 110), ("Total", 130),
                               ("D'où ça vient", 130), ("", 30)):
            case = QLabel(titre)
            case.setMinimumWidth(largeur)
            case.setStyleSheet("color: #666666; font-size: 11px;")
            entetes.addWidget(case)
        dehors.addLayout(entetes)

        self._lignes = QVBoxLayout()
        self._lignes.setSpacing(4)
        dehors.addLayout(self._lignes)
        for cle in SORTES_RECALAGE:
            for periode in recalages.get(cle) or []:
                self._ajouter_ligne(cle, periode)

        ajouter = QPushButton("+ Ajouter une ligne")
        ajouter.clicked.connect(lambda: self._ajouter_ligne())
        barre = QHBoxLayout()
        barre.addWidget(ajouter)
        barre.addStretch(1)
        dehors.addLayout(barre)
        return groupe

    def _ajouter_ligne(self, cle: str = "injection_facturee",
                       periode: dict | None = None) -> None:
        ligne = LigneRecalage(cle, periode or {}, self._retirer_ligne,
                              self._acheteur_nom)
        self._lignes.addWidget(ligne)

    def _retirer_ligne(self, ligne: LigneRecalage) -> None:
        self._lignes.removeWidget(ligne)
        ligne.setParent(None)
        ligne.deleteLater()

    def recalages(self) -> dict:
        """Les recalages tels que saisis, au format de lire_recalages."""
        tous = recalages_vides()
        for i in range(self._lignes.count()):
            ligne = self._lignes.itemAt(i).widget()
            if ligne is None:
                continue
            cle, periode = ligne.valeurs()
            tous[cle].append(periode)
        return tous

    def _en_tout(self) -> bool:
        """Vrai quand la case de prime contient un montant total."""
        return self.mode_prime.currentIndex() == 0

    def _prime_par_kwc(self) -> float:
        """La valeur a enregistrer : le fichier garde toujours des €/kWc."""
        if self._en_tout():
            return prime_par_kwc_depuis_total(
                self.prime.value(), self.puissance.value())
        return self.prime.value()

    def _montrer_total_prime(self) -> None:
        """Recalcule la phrase de la prime a chaque changement de case."""
        self.total_prime.setText(phrase_prime(
            self._prime_par_kwc(), self.puissance.value(),
            self.prime_duree.value(),
            saisie="total" if self._en_tout() else "kwc"))

    def _changer_mode_prime(self) -> None:
        """Bascule entre montant total et montant par kWc : la somme saisie
        est convertie, pour que l'utilisateur retrouve la meme prime."""
        kwc = self.puissance.value()
        valeur = self.prime.value()
        if self._en_tout():
            # On vient de « par kWc » : la case contenait des €/kWc.
            self.prime.setSuffix(" €")
            self.prime.setMaximum(1_000_000)
            self.prime.setValue(prime_totale(valeur, kwc))
        else:
            self.prime.setSuffix(" €/kWc")
            self.prime.setValue(prime_par_kwc_depuis_total(valeur, kwc))
            self.prime.setMaximum(10_000)
        self._montrer_total_prime()

    def _groupe(self, titre: str, champs, aide: str) -> Card:
        # Une carte a bandeau, comme sur les ecrans, et non plus un cadre
        # gris titre au-dessus (relecture des fenetres, 30/09/2026).
        groupe = Card(titre=titre)
        form = QFormLayout()
        groupe.corps.addLayout(form)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setHorizontalSpacing(14)
        for libelle, case in champs:
            form.addRow(libelle, case)
        note = QLabel(aide)
        note.setTextFormat(Qt.RichText)
        note.setWordWrap(True)
        note.setStyleSheet("color: #666666; font-size: 11px;")
        form.addRow(note)
        return groupe

    def valeurs(self) -> dict:
        """Les reglages tels que saisis, au format de reglages.lire_reglages."""
        plages = [p.strip() for p in
                  self.plages.text().replace(",", ";").split(";") if p.strip()]
        return {
            "puissance_kwc": round(self.puissance.value(), 2),
            "cout_total_eur": round(self.cout.value(), 0),
            "date_mise_en_service": _en_date(self.mise_en_service),
            "date_debut_contrat_oa": _en_date(self.debut_oa),
            "prix_oa": round(self.prix_oa.value(), 4),
            "prime_par_kwc": round(self._prime_par_kwc(), 4),
            "prime_duree": self.prime_duree.value(),
            "type_vente": self.type_vente.currentData(),
            "acheteur": self.acheteur.text().strip() or "EDF OA",
            "nom": self.nom.text().strip(),
            "offre": self.offre.text().strip(),
            "abonnement": round(self.abonnement.value(), 2),
            "prix_hp": round(self.prix_hp.value(), 4),
            "prix_hc": round(self.prix_hc.value(), 4),
            "prix_depuis": _en_date(self.prix_depuis),
            "plages_hc": plages,
            "part_hc_autoconso": self._part_hc(),
        }

    def _maj_type_vente(self) -> None:
        """Grise ce qui ne sert pas : tout le contrat sans vente, la prime en
        vente totale (elle ne va qu'a la vente du surplus)."""
        vente = self.type_vente.currentData()
        for case in (self.debut_oa, self.acheteur, self.prix_oa):
            case.setEnabled(vente != "aucune")
        for case in (self.mode_prime, self.prime, self.prime_duree):
            case.setEnabled(vente == "surplus")
        # Sa couleur est fixee (noir) : grisee, elle se lirait encore comme
        # un montant a toucher. On la masque.
        self.total_prime.setVisible(vente == "surplus")

    def _part_hc(self) -> float | None:
        """La part saisie, en fraction ; None = ne rien ecrire.

        Case non touchee : la valeur lue, exacte. Un 0,225 du fichier
        s'affiche arrondi a 23 % ; enregistrer un autre reglage ne doit pas
        le changer en 0,23 sans que l'utilisateur l'ait voulu. Et si cette
        valeur n'etait que l'estimation (rien d'ecrit), None : l'estimation
        continue de suivre les plages au lieu d'etre figee."""
        if self.part_hc.value() == self._part_hc_affichee:
            return self._part_hc_lue if self._part_hc_declaree else None
        return round(self.part_hc.value() / 100, 4)

    def _maj_estimation(self) -> None:
        """Recalcule l'estimation d'apres les plages tapees."""
        plages = [p.strip() for p in
                  self.plages.text().replace(",", ";").split(";") if p.strip()]
        try:
            self._estimation = calc.estimer_part_hc_autoconso(
                calc.parse_plages_hc(plages))
        except (ValueError, TypeError):
            self.estimation_hc.setText("Estimation : plages illisibles")
            self.bouton_estimation.setEnabled(False)
            return
        self.estimation_hc.setText(
            "Estimation d'après vos heures creuses : "
            f"{round(self._estimation * 100)} %")
        self.bouton_estimation.setEnabled(True)

    def _reprendre_estimation(self) -> None:
        self.part_hc.setValue(round(self._estimation * 100))

    def _on_enregistrer(self) -> None:
        try:
            self._enregistrer(self.valeurs())
            # Les recalages vivent dans un autre fichier : on les ecrit
            # ensuite, et une erreur ici laisse la fenetre ouverte sans
            # annuler ce qui vient d'etre enregistre dans config.yaml.
            if self._enregistrer_recalages is not None:
                self._enregistrer_recalages(self.recalages())
        except (ReglagesRefuses, OSError) as exc:
            QMessageBox.warning(self, TITRE, erreur_en_clair(exc))
            return
        self.accept()
