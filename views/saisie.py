"""Vue Saisie quotidienne : tableau editable pour ajouter / corriger les releves."""
from __future__ import annotations

import os
import sys

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
)

import data_loaders as dl
from app_data import AppData
from gui_widgets import SectionTitle
from views._base import BaseView


class SaisieView(BaseView):
    """Tableau editable pour ajouter / modifier les releves journaliers."""

    utilise_periode = False  # editeur : montre toujours les derniers releves

    COLS = ["Date", "Prod_Jour", "Inj_Jour",
            "Conso_réseau_Jour", "Conso_HC", "Conso_HP"]
    HEADERS_AFFICHE = ["Date", "Production\n(kWh)", "Injection\n(kWh)",
                       "Conso réseau\n(kWh)", "Conso HC\n(kWh)", "Conso HP\n(kWh)"]
    NB_LIGNES_AFFICHEES = 30

    def __init__(self, data: AppData, theme: dict, parent=None):
        super().__init__(data, theme, parent)
        self.toutes_lignes: list[dict[str, str]] = []
        self.status_label: QLabel | None = None
        self.table: QTableWidget | None = None
        self.reload_callback = None  # set by MainWindow
        self._cache_mtime: float | None = None
        self._dates_illisibles: list[str] = []

    def populate(self, period: str) -> None:
        path = self.data.releves_path
        if not path:
            self.layout_inner.addWidget(self._empty_card(
                "Le CSV de relevés n'est pas configuré. "
                "Ajoutez sources.releves_csv dans config.yaml."
            ))
            return

        # Cache : on relit le CSV seulement si le fichier a change sur disque
        # (mtime different) ou si le cache est invalide (None apres _recharger).
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = None
        if (
            not self.toutes_lignes
            or self._cache_mtime is None
            or mtime != self._cache_mtime
        ):
            self.toutes_lignes = dl.read_releves_raw(path)
            # Releve en meme temps que la lecture : recompter a chaque
            # affichage de la vue relirait le fichier pour rien.
            self._dates_illisibles = dl.dates_illisibles(path)
            self._cache_mtime = mtime

        self.layout_inner.addWidget(SectionTitle(
            "Saisie quotidienne",
            "Éditez les valeurs puis cliquez sur Enregistrer. "
            "Décimales avec virgule. Cases vides autorisées.",
        ))

        # Bandeau d'actions
        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)
        btn_ajouter = QPushButton("+ Ajouter une ligne")
        btn_ajouter.setObjectName("ActionBtn")
        btn_ajouter.setCursor(Qt.PointingHandCursor)
        btn_ajouter.clicked.connect(self._ajouter_ligne_vide)

        btn_recharger = QPushButton("Recharger")
        btn_recharger.setObjectName("ActionBtn")
        btn_recharger.setCursor(Qt.PointingHandCursor)
        btn_recharger.clicked.connect(self._recharger)

        # Les boutons portaient le nom des fournisseurs de l'auteur
        # (« Importer Enedis / Octopus », « Importer Enphase ») : qui est
        # ailleurs croyait que cela ne le concernait pas, alors que les
        # deux lecteurs acceptent tout export « date + valeur ». Ils
        # disent maintenant CE QU'ILS IMPORTENT, les marques restant en
        # exemple dans l'infobulle.
        btn_importer = QPushButton("Importer conso / injection...")
        btn_importer.setObjectName("ActionBtn")
        btn_importer.setCursor(Qt.PointingHandCursor)
        btn_importer.setToolTip(
            "Ce que votre compteur a échangé avec le réseau.\n\n"
            "Classeur Excel Enedis (conso réseau + injection),\n"
            "export d'index quotidiens Enedis (conso, détail\n"
            "heures creuses / pleines ET injection), CSV\n"
            "'suivi_conso' de votre fournisseur, ou tout export\n"
            "CSV « date + valeur » d'une seule grandeur.")
        btn_importer.clicked.connect(self._importer_enedis)

        btn_enphase = QPushButton("Importer la production...")
        btn_enphase.setObjectName("ActionBtn")
        btn_enphase.setCursor(Qt.PointingHandCursor)
        btn_enphase.setToolTip(
            "Ce que vos panneaux ont produit.\n\n"
            "Rapport Enphase 'Énergie mensuelle' reçu par email\n"
            "(Enlighten > Menu > Système > Rapports), ou l'export\n"
            "de production de votre onduleur : tout fichier\n"
            "« date + valeur » convient, les pas infrajournaliers\n"
            "étant totalisés par jour.")
        btn_enphase.clicked.connect(self._importer_enphase)

        btn_enregistrer = QPushButton("Enregistrer")
        btn_enregistrer.setObjectName("SaveBtn")
        btn_enregistrer.setCursor(Qt.PointingHandCursor)
        btn_enregistrer.clicked.connect(self._enregistrer)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(
            f"color: {self.theme['text_muted']}; font-size: 12px;"
        )

        actions_row.addWidget(btn_ajouter)
        actions_row.addWidget(btn_recharger)
        actions_row.addWidget(btn_importer)
        actions_row.addWidget(btn_enphase)
        actions_row.addStretch(1)
        actions_row.addWidget(self.status_label)
        actions_row.addWidget(btn_enregistrer)
        self.layout_inner.addLayout(actions_row)

        # Tableau
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.HEADERS_AFFICHE)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectItems)
        self.table.setMinimumHeight(520)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for i in range(1, len(self.COLS)):
            header.setSectionResizeMode(i, QHeaderView.Stretch)

        self._remplir_tableau()
        self.layout_inner.addWidget(self.table)

        texte_info = (
            f"{len(self.toutes_lignes)} relevé(s) au total dans le fichier. "
            f"Les {self.NB_LIGNES_AFFICHEES} derniers jours sont affichés "
            "(les autres sont préservés à la sauvegarde)."
        )
        # Une date que pandas ne sait pas lire reste visible ICI, dans le
        # tableau, mais disparait de tous les calculs. C'est donc le seul
        # endroit ou le signaler serve a quelque chose : c'est aussi le seul
        # ou l'on puisse la corriger.
        if self._dates_illisibles:
            apercu = ", ".join(self._dates_illisibles[:3])
            if len(self._dates_illisibles) > 3:
                apercu += " ..."
            texte_info += (
                f"\n⚠  {len(self._dates_illisibles)} date(s) illisible(s) : "
                f"{apercu}. Ces journees n'entrent dans AUCUN calcul tant "
                "que leur date n'est pas corrigée dans le tableau ci-dessus."
            )

        info = QLabel(texte_info)
        info.setWordWrap(True)
        couleur = (self.theme["warm_ink"] if self._dates_illisibles
                   else self.theme["text_muted"])
        info.setStyleSheet(
            f"color: {couleur}; font-size: 11px; padding-top: 4px;"
        )
        self.layout_inner.addWidget(info)
        self.layout_inner.addStretch(1)

    def _prochaine_date(self) -> str:
        """Date du jour suivant le dernier releve, au format DD/MM/YYYY."""
        if self.toutes_lignes:
            derniere = self.toutes_lignes[-1]["Date"]
            try:
                d = pd.to_datetime(derniere, dayfirst=True, errors="raise")
                return (d + pd.Timedelta(days=1)).strftime("%d/%m/%Y")
            except (ValueError, TypeError) as exc:
                print(
                    f"[warn] _prochaine_date: date '{derniere}' invalide "
                    f"({exc}), fallback sur today",
                    file=sys.stderr,
                )
        return pd.Timestamp.today().strftime("%d/%m/%Y")

    def _remplir_tableau(self) -> None:
        assert self.table is not None
        recents = self.toutes_lignes[-self.NB_LIGNES_AFFICHEES:]
        # Ligne vide pre-remplie en haut
        nouvelle = {col: "" for col in self.COLS}
        nouvelle["Date"] = self._prochaine_date()

        lignes = [nouvelle] + list(reversed(recents))  # plus recent en haut
        self.table.setRowCount(len(lignes))
        for r, row_data in enumerate(lignes):
            for c, col in enumerate(self.COLS):
                item = QTableWidgetItem(row_data.get(col, ""))
                if r == 0:
                    # Met en evidence la nouvelle ligne
                    item.setBackground(self._couleur_nouvelle_ligne())
                self.table.setItem(r, c, item)
        self.table.setCurrentCell(0, 1)  # focus sur Prod_Jour de la nouvelle ligne

    def _couleur_nouvelle_ligne(self):
        # Jaune solaire tres pale, contraste OK clair et sombre
        return QColor(245, 158, 11, 38)

    def _ajouter_ligne_vide(self) -> None:
        assert self.table is not None
        self.table.insertRow(0)
        prochaine = self._prochaine_date_apres_table()
        valeurs = [prochaine, "", "", "", "", ""]
        for c, val in enumerate(valeurs):
            item = QTableWidgetItem(val)
            item.setBackground(self._couleur_nouvelle_ligne())
            self.table.setItem(0, c, item)
        self.table.setCurrentCell(0, 1)

    def _prochaine_date_apres_table(self) -> str:
        """Cherche la date la plus haute dans le tableau et renvoie j+1."""
        assert self.table is not None
        dates = []
        for r in range(self.table.rowCount()):
            cell = self.table.item(r, 0)
            if cell and cell.text().strip():
                try:
                    dates.append(pd.to_datetime(cell.text(), dayfirst=True))
                except (ValueError, TypeError):
                    # Cellule en cours d'edition par l'utilisateur, on ignore.
                    pass
        if dates:
            return (max(dates) + pd.Timedelta(days=1)).strftime("%d/%m/%Y")
        return pd.Timestamp.today().strftime("%d/%m/%Y")

    def _recharger(self) -> None:
        self._cache_mtime = None  # force la relecture disque dans populate
        self.refresh(self.data.current_period)
        self._set_status("Données rechargees depuis le disque.", ok=True)

    def _importer_enedis(self) -> None:
        """Importe un releve du reseau dans le CSV. Quatre fichiers passent :
        le classeur Excel Enedis (feuilles conso + production importees d'un
        coup), son export d'index quotidiens (les index du compteur, avec le
        detail heures creuses / pleines, convertis en consommations), le CSV
        "suivi de consommation" telecharge chez Octopus (conso + meme detail)
        ou un export CSV d'une seule grandeur.

        Le "suivi_conso" ne vient pas d'Enedis malgre son nom de fichier :
        c'est l'espace client Octopus qui le fournit, avec les euros.
        Enedis ne connait pas les prix."""
        self._importer_fichier(
            source="conso / injection",
            libelle_dialogue="Importer un relevé de consommation ou d'injection",
            filtre="Relevés réseau (*.xlsx *.csv);;Tous les fichiers (*)",
            parser=dl.parse_enedis_fichier,
        )

    def _importer_enphase(self) -> None:
        """Importe le rapport Enphase "Energie mensuelle" (Enlighten >
        Menu > Systeme > Rapports, recu par email) : la production des
        pas de 15 minutes est totalisee par jour.

        La journee en cours est ignoree : le rapport s'arrete a l'heure de
        sa generation, elle serait donc sous-evaluee."""
        self._importer_fichier(
            source="production",
            libelle_dialogue="Importer un relevé de production",
            filtre="Relevés de production (*.csv *.zip *.txt);;"
                   "Tous les fichiers (*)",
            parser=dl.parse_enphase_fichier,
            ignorer_jour_en_cours=True,
        )

    # Libelle affiche dans le recapitulatif pour chaque colonne importee.
    LIBELLES_IMPORT = {
        "Prod_Jour": "Production",
        "Inj_Jour": "Injection",
        "Conso_réseau_Jour": "Conso réseau",
        "Conso_HC": "Conso heures creuses",
        "Conso_HP": "Conso heures pleines",
    }

    def _importer_fichier(self, source: str, libelle_dialogue: str,
                          filtre: str, parser,
                          ignorer_jour_en_cours: bool = False) -> None:
        """Rouage commun aux imports Enedis et Enphase.

        Fusion par date, donc jamais de doublon : les jours nouveaux sont
        ajoutes, les dates deja presentes voient la valeur de la colonne
        importee remplacee (les autres colonnes ne bougent pas)."""
        titre = f"Import {source}"
        path = self.data.releves_path
        if not path:
            self._set_status("Pas de chemin CSV configuré.", ok=False)
            return

        fichier, _ = QFileDialog.getOpenFileName(
            self, libelle_dialogue, "", filtre)
        if not fichier:
            return

        try:
            imports = parser(fichier)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, titre, f"Import impossible :\n\n{exc}")
            return

        # Fusionne chaque grandeur (production, conso, injection) dans les
        # memes lignes.
        lignes = dl.read_releves_raw(path)
        recap = []
        alertes = []
        total_nouveaux = total_remplaces = 0
        jour_ignore = None
        for colonne, valeurs in imports.items():
            if ignorer_jour_en_cours:
                jour_ignore = dl.retirer_jour_en_cours(valeurs) or jour_ignore
            if not valeurs:
                continue
            # Garde-fou : une grandeur rangee dans la mauvaise colonne se
            # trahit par une injection superieure a la production.
            alerte = dl.controle_apres_import(lignes, colonne, valeurs)
            if alerte:
                alertes.append(alerte)
            lignes, nb_n, nb_r, nb_i = dl.merge_import(lignes, colonne, valeurs)
            libelle = self.LIBELLES_IMPORT.get(colonne, colonne)
            recap.append(
                f"  - {libelle} : {len(valeurs)} jour(s) lus, {nb_n} "
                f"nouveau(x), {nb_r} remplacé(s), {nb_i} identique(s)")
            total_nouveaux += nb_n
            total_remplaces += nb_r

        if jour_ignore:
            recap.append(
                f"\n  (journée en cours du {jour_ignore} ignorée : incomplète)")
        if not recap:
            QMessageBox.warning(
                self, titre,
                "Ce fichier ne contient aucun jour à importer.")
            return

        # Une anomalie physique passe devant le recapitulatif, et le bouton
        # par defaut devient Non : mieux vaut renoncer que corrompre le CSV.
        message = "Contenu du fichier :\n\n" + "\n".join(recap)
        if alertes:
            message = "\n\n".join(alertes) + "\n\n" + ("-" * 40) + "\n\n" + message
        message += ("\n\nAppliquer ? Une sauvegarde de l'ancienne version est "
                    "conservée.")
        reponse = QMessageBox.question(
            self, titre, message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No if alertes else QMessageBox.Yes)
        if reponse != QMessageBox.Yes:
            self._set_status("Import annulé.", ok=False)
            return

        try:
            dl.write_releves_raw(path, lignes)
        except (OSError, dl.ReductionRefusee) as exc:
            # Un import n'enleve jamais rien : s'il reduit le fichier, c'est
            # que la lecture du CSV etait incomplete. On ne l'ecrit pas.
            self._signaler_echec_ecriture(exc)
            return
        if callable(self.reload_callback):
            self.reload_callback()
        self._set_status(
            f"{titre} OK : {total_nouveaux} ajout(s), "
            f"{total_remplaces} remplacement(s).", ok=True)

    def _set_status(self, msg: str, ok: bool = True) -> None:
        if self.status_label is None:
            return
        couleur = "#16a34a" if ok else "#dc2626"
        self.status_label.setStyleSheet(
            f"color: {couleur}; font-size: 12px; font-weight: 600;"
        )
        self.status_label.setText(msg)

    def _fichier_modifie_depuis_la_lecture(self) -> bool:
        """Le CSV a-t-il change sur le disque depuis que la vue l'a lu ?

        Rien n'empeche de corriger le CSV dans Excel pendant que l'appli est
        ouverte. Le tableau, lui, montre encore l'etat d'avant : enregistrer
        ecraserait la correction, en silence des deux cotes.
        """
        if self._cache_mtime is None:
            return False
        try:
            return os.path.getmtime(self.data.releves_path) != self._cache_mtime
        except OSError:
            # Fichier disparu ou illisible : ce n'est pas a ce controle-ci
            # de s'en plaindre, l'ecriture le signalera.
            return False

    def _signaler_echec_ecriture(self, exc: Exception) -> None:
        """Un enregistrement rate se voit : boite de dialogue, pas petit label.

        Le message partait dans le libelle discret a cote du bouton, ou il
        pouvait parfaitement passer inapercu -- alors que rien n'a ete
        enregistre et que l'utilisateur s'apprete a fermer l'application.
        """
        QMessageBox.critical(
            self, "Enregistrement impossible",
            f"Les relevés n'ont PAS été enregistrés.\n\n{exc}\n\n"
            "Le fichier est peut-être ouvert dans un autre programme "
            "(Excel), ou en cours de synchronisation. Fermez-le puis "
            "réessayez : vos saisies sont toujours dans le tableau.")
        self._set_status("Enregistrement impossible (voir le message).",
                         ok=False)

    def _confirmer_suppression(self, pertes: str, videes: list[str]) -> bool:
        """Demande confirmation avant toute perte de donnees. Non par defaut.

        Deux situations tres differentes aboutissent ici, d'ou deux messages :
        l'effacement volontaire de journees (cas normal), et la reduction que
        personne n'a demandee (cas dangereux : le fichier a mal ete lu).
        """
        message = f"{pertes}.\n\n"
        if videes:
            apercu = ", ".join(videes[:5]) + (" ..." if len(videes) > 5 else "")
            message += (
                f"{len(videes)} journée(s) vidée(s) dans le tableau : "
                f"{apercu}\n\n")
        else:
            message += (
                "Or aucune journée n'a été vidée dans le tableau. Le fichier "
                "a donc probablement été lu incompletement (synchronisation "
                "interrompue, fichier verrouille) : enregistrer maintenant "
                "effacerait pour de bon ce qui n'a pas été lu.\n\n"
                "Dans le doute, repondez Non, puis cliquez sur Recharger.\n\n")
        message += "L'ancienne version restera dans le .bak.\n\nContinuer ?"

        reponse = QMessageBox.question(
            self, "Suppression de données", message,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return reponse == QMessageBox.Yes

    def _enregistrer(self) -> None:
        assert self.table is not None
        path = self.data.releves_path
        if not path:
            self._set_status("Pas de chemin CSV configuré.", ok=False)
            return

        if self._fichier_modifie_depuis_la_lecture():
            QMessageBox.warning(
                self, "Le fichier a change",
                "Le fichier de relevés a été modifié sur le disque depuis "
                "que cette vue l'a lu (Excel ? une synchronisation ?).\n\n"
                "Enregistrer maintenant ecraserait cette modification sans "
                "la voir.\n\n"
                "Cliquez sur Recharger pour repartir de la version du "
                "disque. Notez d'abord vos saisies en cours : le rechargement "
                "les remplacera.")
            self._set_status(
                "Fichier modifié sur le disque : cliquez sur Recharger.",
                ok=False)
            return

        # Collecte des lignes du tableau (validees)
        lignes_avant = {r["Date"]: r for r in self.toutes_lignes}
        lignes_table: dict[str, dict[str, str]] = {}
        videes: list[str] = []
        erreurs: list[str] = []
        doublons: list[str] = []
        for r in range(self.table.rowCount()):
            row = {}
            for c, col in enumerate(self.COLS):
                cell = self.table.item(r, c)
                row[col] = cell.text().strip() if cell else ""

            if not row["Date"]:
                # Ligne vide -> ignoree silencieusement
                if any(row[c] for c in self.COLS):
                    erreurs.append(f"Ligne {r + 1} : date manquante.")
                continue

            a_des_valeurs = any(row[col] for col in self.COLS[1:])

            # Validation de la date d'abord : il faut sa forme normalisee pour
            # savoir si ce jour existe deja dans le fichier.
            try:
                row["Date"] = dl.normalise_date_saisie(row["Date"])
            except ValueError as exc:
                # Une ligne sans aucune valeur n'a rien a enregistrer : on ne
                # se plaint pas de sa date. La ligne neuve est pre-remplie au
                # lendemain du dernier releve, donc souvent dans le futur --
                # refuser ici bloquerait tout l'enregistrement pour une ligne
                # qu'on allait de toute facon ignorer.
                if not a_des_valeurs:
                    continue
                erreurs.append(f"Ligne {r + 1} : {exc}.")
                continue

            if not a_des_valeurs:
                # Aucune valeur sur la ligne. Deux cas bien differents :
                avait_des_valeurs = any(
                    lignes_avant.get(row["Date"], {}).get(col, "")
                    for col in self.COLS[1:]
                )
                if avait_des_valeurs:
                    # Jour existant que l'on vient de vider : c'est un
                    # effacement volontaire (avant, il etait ignore et les
                    # anciennes valeurs revenaient au rafraichissement).
                    # La ligne sera retiree du fichier, pas laissee vide :
                    # une ligne sans valeurs ferait un jour fantome a 0 kWh
                    # de production dans toutes les statistiques.
                    videes.append(row["Date"])
                # sinon : ligne neuve pre-remplie, laissee telle quelle -> rien
                continue

            # Validation numerique (vide autorise)
            ok_row = True
            for col in self.COLS[1:]:
                try:
                    row[col] = dl.normalise_nombre_saisie(
                        row[col], self.LIBELLES_IMPORT.get(col, col),
                        dl.plafond_colonne(col, self.data.puissance_kwc))
                except ValueError as exc:
                    erreurs.append(f"Ligne {r + 1} : {exc}.")
                    ok_row = False
                    break
            if not ok_row:
                continue

            # Deux lignes de meme date : la seconde ecrasait la premiere sans
            # rien dire. Comme la ligne neuve est en position 0 et les lignes
            # existantes en dessous, c'est l'ANCIENNE valeur qui l'emportait,
            # et le message annoncait quand meme un enregistrement reussi.
            if row["Date"] in lignes_table:
                doublons.append(row["Date"])
                continue

            lignes_table[row["Date"]] = row

        if doublons:
            # dict.fromkeys : dedoublonne en gardant l'ordre d'apparition.
            dates = ", ".join(dict.fromkeys(doublons))
            erreurs.append(
                f"date(s) en double dans le tableau : {dates} "
                "(une seule ligne par journée)")

        if erreurs:
            self._set_status(" ".join(erreurs[:2]), ok=False)
            return

        # Merge : on part de toutes les lignes existantes du CSV, et on
        # remplace / ajoute celles editees dans le tableau.
        toutes = {row["Date"]: dict(row) for row in self.toutes_lignes}
        toutes.update(lignes_table)
        # Journees videes : la ligne disparait. (Sauf si la meme date a aussi
        # ete saisie ailleurs dans le tableau : la version remplie l'emporte.)
        for jour in videes:
            if jour not in lignes_table:
                toutes.pop(jour, None)
        lignes_finales = list(toutes.values())

        # Perdre des donnees ne se fait pas par megarde. Le controle porte sur
        # le FICHIER TEL QU'IL EST SUR LE DISQUE, et non sur ce que la vue
        # croit avoir lu : une lecture partielle se voit donc ici, alors que
        # l'ancien dialogue ne comptait que les lignes videes a la main.
        autoriser_reduction = False
        pertes = dl.pertes_a_l_ecriture(path, lignes_finales)
        if pertes:
            if not self._confirmer_suppression(pertes, videes):
                self._set_status("Enregistrement annule.", ok=False)
                return
            autoriser_reduction = True

        try:
            dl.write_releves_raw(path, lignes_finales, autoriser_reduction)
        except (OSError, dl.ReductionRefusee) as exc:
            self._signaler_echec_ecriture(exc)
            return

        # Le fichier vient d'etre reecrit : le cache en memoire est perime, il
        # ne contient pas ce qu'on vient d'ecrire. On l'invalide pour que le
        # rechargement qui suit relise vraiment le disque.
        #
        # Y mettre la nouvelle date de modification, comme on serait tente de
        # le faire pour calmer le controle de concurrence, produit exactement
        # l'inverse : populate ne voit plus aucun changement, reaffiche l'etat
        # d'avant -- la ligne du jour revient vide alors qu'elle est bien
        # enregistree -- et l'enregistrement SUIVANT repart de ce cache
        # perime, effacant la journee qu'on vient d'ajouter.
        # None ne desarme rien : _fichier_modifie_depuis_la_lecture ne peut
        # rien comparer tant que le fichier n'a pas ete relu, et populate
        # repose une date fraiche juste apres.
        self._cache_mtime = None

        # Compte reel : un ajout = date absente du CSV ; une modif = ligne
        # existante dont au moins une valeur a change (les lignes affichees
        # mais intactes ne comptent pas). Les effacements sont comptes a part.
        nb_ajout = sum(1 for d in lignes_table if d not in lignes_avant)
        nb_modif = sum(
            1 for d, row in lignes_table.items()
            if d in lignes_avant and row != lignes_avant[d]
        )

        # Recharge d'abord toutes les vues (ce qui reconstruit celle-ci et son
        # label de statut), PUIS affiche la confirmation : dans l'autre ordre,
        # le message serait efface aussitot par la reconstruction.
        if callable(self.reload_callback):
            self.reload_callback()
        message = f"OK : {nb_ajout} ajout(s), {nb_modif} modif(s)"
        if videes:
            message += f", {len(videes)} effacement(s)"
        self._set_status(message + " enregistre(s).", ok=True)
