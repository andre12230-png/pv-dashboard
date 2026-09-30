"""Conteneur type des donnees partagees entre MainWindow et les vues.

Remplace le dict anonyme construit par build_dataset : les acces se font
par attribut (data.df, data.oa...), avec autocompletion et detection des
fautes de frappe a l'analyse statique au lieu d'un KeyError au runtime.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

import calculations as calc


@dataclass
class AppData:
    df: pd.DataFrame                 # series journalieres enrichies (kWh + €)
    cfg: dict                        # config.yaml brute
    oa: calc.OAConfig
    bleu: calc.BleuBaseConfig
    octopus: calc.OctopusConfig
    start_oa: date | None            # debut du contrat OA (None : pas de vente)
    releves_path: str | None         # chemin absolu du CSV de releves
    edf_ref: list[dict]              # grille EDF de reference, par periodes
    # Les memes releves, mais BRUTS : ni injection estimee, ni recalage sur
    # les factures. Seule la vue TVA s'en sert : une declaration fiscale doit
    # reposer sur les quantites reellement relevees, pas sur des valeurs
    # reconstituees (voir la section LASM de calculations.py).
    df_brut: pd.DataFrame = field(default_factory=pd.DataFrame)
    # Grille de valorisation de l'autoconsommation (config.yaml, tva_lasm).
    # None quand la section est absente : la vue TVA se met alors en veille.
    lasm: calc.LasmConfig | None = None
    current_period: str = "all"      # periode active, tenue a jour par MainWindow
    # Date du dernier jour renseigne, par colonne du CSV : dit ce qui est a
    # jour et ce qui reste a importer (les sources n'avancent pas ensemble).
    dernieres_saisies: dict = field(default_factory=dict)
    # Dates du CSV que pandas n'a pas su lire : ces journees sont absentes de
    # tous les calculs alors qu'elles restent visibles dans l'onglet Saisie.
    dates_illisibles: list = field(default_factory=list)
    # Journees de fin de serie dont seule la production est connue : Enedis
    # publie conso et injection le lendemain. Mises de cote jusqu'a leur
    # import, et nommees par le tableau de bord pour qu'on ne les croie pas
    # perdues (voir calculations.jours_en_attente).
    jours_en_attente: list = field(default_factory=list)
    # Dossier ou vivent config.yaml et les releves. Les vues Parametres et
    # Notice l'affichent : une fois l'application installee, il est cache
    # dans %LOCALAPPDATA% et l'utilisateur ne le trouverait pas seul.
    dossier_donnees: str = ""

    @property
    def puissance_kwc(self) -> float:
        """Puissance de l'installation, en kWc (config.yaml).

        Sert au titre de la fenetre, a la notice et au plafond de saisie :
        tout cela etait ecrit pour une installation de 6 kWc.
        """
        return float(self.cfg.get("installation", {}).get("puissance_kwc", 0) or 0)

    def _nom_offre(self, section: str, defaut: str) -> tuple[str, str]:
        """(nom court, libelle complet) d'une offre declaree en config."""
        bloc = (self.cfg.get("tarifs_reseau") or {}).get(section) or {}
        nom = str(bloc.get("nom") or defaut)
        return nom, str(bloc.get("offre") or nom)

    @property
    def fournisseur(self) -> tuple[str, str]:
        """Le contrat en cours : ('Octopus', 'Octopus Go') chez l'auteur.

        Ces noms etaient ecrits en dur dans la vue de comparaison, qui
        annoncait donc "Octopus vs EDF" a qui est chez un autre fournisseur.
        """
        return self._nom_offre("contrat_hphc", "Mon contrat")

    @property
    def fournisseur_reference(self) -> tuple[str, str]:
        """L'offre servant de point de comparaison : ('EDF', 'EDF Tarif Bleu')."""
        return self._nom_offre("comparaison_edf", "Tarif de référence")

    # Au-dela de cette longueur, deux noms de fournisseurs ne tiennent plus
    # dans le menu (largeur fixe de 212 px) : on retombe sur un libelle
    # generique plutot que sur un texte coupe au milieu.
    LARGEUR_MAX_NAV = 22

    @property
    def libelle_comparaison(self) -> str:
        """Le nom de la page qui compare le contrat a l'offre de reference :
        « Octopus ou EDF » chez l'auteur. Le meme dans le menu, en titre de la
        page et dans la Notice (30/09/2026 : le menu disait « Mon fournisseur
        ou EDF » et la page « Mon offre HP/HC ou EDF Tarif Bleu »).

        « ou » et non « vs » (anglicisme, relecture du 29/09/2026)."""
        libelle = f"{self.fournisseur[0]} ou {self.fournisseur_reference[0]}"
        return (libelle if len(libelle) <= self.LARGEUR_MAX_NAV
                else "Comparaison tarifs")

    @property
    def meme_fournisseur_que_la_reference(self) -> bool:
        """Vrai quand le contrat en cours est chez le fournisseur de reference
        (EDF, le fournisseur historique).

        Comparer EDF a EDF n'a pas de sens : l'onglet de comparaison est alors
        masque. On cherche le nom de la reference ("EDF") comme mot entier
        dans le nom ou l'offre du contrat : "EDF", "edf" ou "EDF Tarif Bleu"
        le masquent, "Octopus" ou "Mon fournisseur" non.
        """
        ref = self.fournisseur_reference[0].strip()
        if not ref:
            return False
        texte = " ".join(self.fournisseur)
        return re.search(rf"\b{re.escape(ref)}\b", texte, re.IGNORECASE) is not None

    @property
    def vend(self) -> bool:
        """L'electricite injectee est-elle vendue ? (oa.type « aucune » : non)"""
        return self.oa is None or self.oa.type != "aucune"

    @property
    def acheteur(self) -> str:
        """Qui achete l'electricite vendue : oa.acheteur, « EDF OA » sinon."""
        return str((self.cfg.get("oa") or {}).get("acheteur") or "EDF OA")

    @property
    def d_acheteur(self) -> str:
        """« d'EDF OA », « de Solaire Coop » : l'elision suit le nom."""
        nom = self.acheteur
        return (f"d'{nom}" if nom[:1].upper() in "AEIOUYÉÈÊH"
                else f"de {nom}")

    @property
    def cycle_oa(self) -> str:
        """Bornes de l'annee OA, jour et mois : 'du 20/05 au 19/05'.

        Elle commence a la date de debut du contrat et finit la veille, un an
        plus tard. Les ecrans affichaient en dur '28/06 -> 27/06', le cycle du
        contrat de l'auteur, a tous les utilisateurs.
        """
        if self.start_oa is None:
            return ""
        veille = self.start_oa - timedelta(days=1)
        return f"du {self.start_oa:%d/%m} au {veille:%d/%m}"

    @property
    def date_mise_en_service(self) -> str:
        """Date de mise en service telle qu'ecrite dans config.yaml."""
        return str(self.cfg.get("installation", {}).get("date_mise_en_service", ""))
