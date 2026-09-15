"""
Application desktop PySide6 - Dashboard photovoltaique style "appli comptes".

Lancer :
    py app_desktop.py
"""

from __future__ import annotations

import os
import shutil
import sys
import traceback
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("QtAgg")
import pandas as pd
import yaml
from PySide6.QtCore import QDir, QLockFile, QSettings, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

import avis
import calculations as calc
import data_loaders as dl
import mise_a_jour
import reglages
import sauvegarde_externe
from app_data import AppData
from fenetre_reglages import FenetreReglages
from gui_theme import LIGHT, mpl_style, qss_for
from views import (
    MOIS_TOUS,
    PERIOD_ALL,
    AccountsView,
    AideView,
    BaseView,
    CategoriesView,
    ComparaisonView,
    DashboardView,
    OAView,
    OctopusEdfView,
    SaisieView,
    SettingsView,
    StatsView,
    TransactionsView,
    TvaView,
    annee_de_periode,
    bornes_annee_oa,
    fmt_kwc,
    fmt_kwh,
    options_annees,
    options_mois,
    period_options,
    periode_voisine,
)

# ----------------------------------------------------------------------
# Resolution des chemins
# ----------------------------------------------------------------------
# Le dossier de base est celui qui contient config.yaml, Releves-pv.csv et,
# a cote du CSV, le dossier backups/. C'est le dossier du projet, et il est
# le meme dans les deux modes de lancement : un seul jeu de donnees, jamais
# deux copies qui divergent.
#
# En .exe, trois cas, dans cet ordre :
#
# - Le dossier d'usage, separe du projet (F:\Gestion photovoltaique) : les
#   donnees, et dedans le programme, dans pv-dashboard\. Les donnees sont
#   donc un cran au-dessus de l'exe - la meme disposition que Recharges VE.
# - L'exe construit dans le projet : PyInstaller (--onedir) le place dans
#   dist/pv-dashboard/, un dossier qu'il EFFACE et recree a chaque
#   construction. Les donnees ne peuvent donc pas y vivre : on remonte de
#   deux crans (dist/pv-dashboard -> dist -> projet) pour les retrouver la ou
#   elles sont deja. On reconnait ce cas au config.yaml qui s'y trouve.
# - L'exe installe par le Setup, dans %LOCALAPPDATA%\Programs\pv-dashboard :
#   il n'a pas de projet autour de lui. Remonter de deux crans tomberait sur
#   %LOCALAPPDATA% lui-meme, ou tout s'ecrirait en vrac. Ses donnees vont
#   donc dans un dossier personnel, %LOCALAPPDATA%\pv-dashboard, toujours
#   accessible en ecriture. Le programme et les donnees sont alors separes :
#   une mise a jour ou une desinstallation ne touche jamais aux secondes.

DOSSIER_PERSONNEL = "pv-dashboard"


def resolve_base_dir() -> Path:
    if not getattr(sys, "frozen", False):
        return Path(__file__).parent
    programme = Path(sys.executable).parent
    # Un cran (dossier d'usage), puis deux (projet) : on s'arrete au premier
    # dossier qui porte un config.yaml.
    for dossier in (programme.parent, programme.parent.parent):
        if (dossier / "config.yaml").exists():
            return dossier
    racine = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    return (Path(racine) if racine else Path.home()) / DOSSIER_PERSONNEL


BASE_DIR = resolve_base_dir()
# Premier lancement d'une installation : le dossier personnel n'existe pas
# encore, alors que le journal doit pouvoir s'y ecrire des l'import.
try:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass  # l'erreur ressortira, lisible, a la lecture de config.yaml
CONFIG_PATH = BASE_DIR / "config.yaml"
# Configuration PERSONNELLE, a cote de la precedente et jamais versionnee :
# elle porte les totaux lus sur vos factures (recalages) et les chemins
# propres a votre machine. Voir load_config().
CONFIG_LOCAL_PATH = BASE_DIR / "config-local.yaml"
LOG_PATH = BASE_DIR / "pv-dashboard.log"

# Nom du logiciel, sans la taille de l'installation : celle-ci est lue dans
# config.yaml et ajoutee au titre de la fenetre. Ecrite en dur, elle
# affichait "6 kWc" a tout le monde, quelle que soit l'installation suivie.
APP_NAME = "Gestion Photovoltaique"
APP_VERSION = "1.35.0"


TAILLE_MAX_LOG = 1_000_000  # 1 Mo


def _tourner_le_log() -> None:
    """Repart d'un log neuf quand il depasse 1 Mo, en gardant le precedent.

    Sans cela pv-dashboard.log grossissait indefiniment : chaque demarrage
    sous pythonw y ajoute des lignes et rien ne le purgeait jamais.
    """
    try:
        if LOG_PATH.exists() and LOG_PATH.stat().st_size > TAILLE_MAX_LOG:
            precedent = LOG_PATH.with_suffix(".log.1")
            precedent.unlink(missing_ok=True)
            LOG_PATH.rename(precedent)
    except OSError:
        pass  # un log verrouille ne doit pas empecher l'app de demarrer


def _redirect_logs_if_no_console() -> None:
    """
    Redirige stdout/stderr vers pv-dashboard.log quand il n'y a pas de
    console disponible : sous PyInstaller --noconsole, sous pythonw.exe
    (Lancer.bat ou Lancer.vbs), ou tout autre contexte ou sys.stdout est None.
    Sinon, ne touche a rien (mode debug en console).
    """
    frozen = getattr(sys, "frozen", False)
    is_pythonw = "pythonw" in (sys.executable or "").lower()
    no_stdout = sys.stdout is None or sys.stderr is None
    if not (frozen or is_pythonw or no_stdout):
        return
    _tourner_le_log()
    try:
        fh = open(LOG_PATH, "a", encoding="utf-8", buffering=1)
        sys.stdout = fh
        sys.stderr = fh
    except OSError:
        try:
            sys.stdout = open(os.devnull, "w")
            sys.stderr = sys.stdout
        except OSError:
            # Ni fichier log ni devnull accessibles : aucun fallback possible.
            pass


_redirect_logs_if_no_console()


# ----------------------------------------------------------------------
# Donnees
# ----------------------------------------------------------------------

def _lire_yaml(chemin: Path) -> dict:
    """Lit un fichier YAML en transformant ses erreurs en messages lisibles.

    yaml.safe_load leve des messages techniques en anglais ("mapping values
    are not allowed here"), affiches tels quels dans la boite d'erreur au
    demarrage. On les reecrit en francais, en gardant le numero de ligne :
    c'est la seule information vraiment utile pour retrouver sa faute de
    frappe.
    """
    try:
        with open(chemin, "r", encoding="utf-8") as fh:
            contenu = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        ligne = ""
        marque = getattr(exc, "problem_mark", None)
        if marque is not None:
            ligne = f" (ligne {marque.line + 1})"
        raise RuntimeError(
            f"{chemin.name} est mal ecrit{ligne}. Verifiez les deux-points, "
            "les tirets et l'alignement des lignes autour de cet endroit, "
            "puis relancez l'application."
        ) from exc
    if contenu is None:
        return {}
    if not isinstance(contenu, dict):
        raise RuntimeError(
            f"{chemin.name} ne contient pas une configuration valide "
            "(il devrait commencer par des sections comme 'installation:')."
        )
    return contenu


def _fusionne(base: dict, ajout: dict) -> dict:
    """Recopie 'ajout' par-dessus 'base', section par section.

    Une valeur simple ou une liste remplace celle de 'base' ; deux
    dictionnaires sont fusionnes en profondeur. C'est ce qui permet a
    config-local.yaml de n'ecrire QUE ce qui lui est propre, sans recopier
    tout le reste.
    """
    resultat = dict(base)
    for cle, valeur in ajout.items():
        if isinstance(valeur, dict) and isinstance(resultat.get(cle), dict):
            resultat[cle] = _fusionne(resultat[cle], valeur)
        else:
            resultat[cle] = valeur
    return resultat


def load_config() -> dict:
    """La configuration = config.yaml, complete par config-local.yaml.

    Pourquoi deux fichiers ?
        config.yaml est versionne : il decrit VOTRE installation et vos
        tarifs, et sert de modele a qui recupere l'application.
        config-local.yaml, lui, n'est jamais versionne. Il porte les totaux
        releves sur vos factures (les sections de recalage) et les chemins
        propres a votre machine. Sans cette separation, celui qui recupere
        l'application heritait des factures de quelqu'un d'autre : ses
        propres releves etaient alors reecrits en silence.
        Le second fichier est facultatif : sans lui, l'application marche.
    """
    cfg = _lire_yaml(CONFIG_PATH)
    if CONFIG_LOCAL_PATH.exists():
        cfg = _fusionne(cfg, _lire_yaml(CONFIG_LOCAL_PATH))
    return normaliser_config(cfg)


def normaliser_config(cfg: dict) -> dict:
    """Range l'ancien nom de section du contrat sous le nouveau.

    La section du contrat en heures pleines / creuses s'appelait
    "octopus_hphc", du nom du fournisseur de l'auteur : un autre utilisateur
    pouvait croire qu'elle ne concernait qu'Octopus. Elle s'appelle
    desormais "contrat_hphc". Les config.yaml ecrits avec l'ancien nom
    restent valables : on les traduit ici, une fois pour toutes, et le reste
    du programme ne connait plus que le nouveau nom.

    Si les deux noms sont presents, le nouveau l'emporte.
    """
    tarifs = cfg.get("tarifs_reseau")
    if isinstance(tarifs, dict) and "octopus_hphc" in tarifs:
        ancien = tarifs.pop("octopus_hphc")
        tarifs.setdefault("contrat_hphc", ancien)
    return cfg


def _sauvegarder_config_local() -> None:
    """Garde une copie quotidienne de config-local.yaml dans backups/.

    Ce fichier n'est plus versionne : il contient des donnees personnelles
    (les totaux des factures) qui ne doivent pas partir avec le programme.
    Mais il n'est du coup plus protege par l'historique du depot, alors qu'il
    represente des heures de releve de factures. On le sauvegarde donc comme
    le CSV : une copie par journee, les 30 dernieres.

    Silencieux en cas d'echec : une sauvegarde ratee ne doit jamais empecher
    l'application de demarrer.
    """
    if not CONFIG_LOCAL_PATH.exists():
        return
    try:
        dossier = BASE_DIR / "backups"
        dossier.mkdir(exist_ok=True)
        copie = dossier / f"config-local_jour_{date.today():%Y%m%d}.yaml"
        if not copie.exists():
            shutil.copy2(CONFIG_LOCAL_PATH, copie)
        anciennes = sorted(dossier.glob("config-local_jour_*.yaml"),
                           key=lambda f: f.stat().st_mtime, reverse=True)
        for vieille in anciennes[30:]:
            vieille.unlink(missing_ok=True)
    except OSError as exc:
        print(f"[warn] sauvegarde de config-local.yaml impossible : {exc}",
              file=sys.stderr)


# Modeles livres a cote du programme par l'installeur. Au premier lancement,
# ils sont recopies dans le dossier des donnees : c'est la que l'utilisateur
# les remplit, pas dans le dossier du programme qu'une mise a jour remplace.
MODELES_CONFIG = ("config.yaml", "config-local.exemple.yaml")
# Les modeles poses a CE lancement-ci (rempli par create_window) : sert a
# accueillir le nouvel utilisateur une seule fois, pas a chaque demarrage.
MODELES_POSES: list[str] = []


def installer_modeles_config(dossier_donnees: Path,
                             dossier_programme: Path) -> list[str]:
    """Recopie les modeles absents du dossier des donnees. Rend leurs noms.

    Ne remplace JAMAIS un fichier deja present : apres une mise a jour, le
    config.yaml de l'utilisateur, rempli a la main, doit rester le sien.
    """
    poses = []
    for nom in MODELES_CONFIG:
        modele = dossier_programme / nom
        cible = dossier_donnees / nom
        if cible.exists() or not modele.exists():
            continue
        shutil.copy2(modele, cible)
        poses.append(nom)
    return poses


def _charger_recharges_ve(cfg: dict):
    """Recharges du vehicule (app recharges-ve), si la source est configuree.

    Contrairement au CSV de releves, ce fichier vit volontairement HORS du
    dossier de l'application : c'est celui de l'autre projet, et on ne fait
    que le lire. Toute absence est silencieuse (l'app doit demarrer sans).
    """
    chemin = (cfg.get("sources") or {}).get("recharges_ve_json")
    if not chemin:
        return None
    p = Path(chemin)
    if not p.is_absolute():
        p = BASE_DIR / p
    if not p.exists():
        print(f"[warn] recharges VE introuvables : {p}", file=sys.stderr)
        return None
    return dl.charger_recharges_ve(str(p))


# Ce que la configuration doit contenir, et le libelle a montrer quand il
# manque. Cle "a.b.c" = section a, sous-section b, reglage c.
REGLAGES_OBLIGATOIRES = [
    ("installation.puissance_kwc", "la puissance de l'installation, en kWc"),
    ("installation.cout_total_eur", "le coût total de l'installation"),
    ("installation.date_mise_en_service", "la date de mise en service"),
    ("installation.date_debut_contrat_oa", "la date de debut du contrat OA"),
    ("oa.prix_kwh_eur", "le prix d'achat du surplus, en EUR/kWh"),
    ("oa.duree_contrat_annees", "la duree du contrat OA, en annees"),
    ("tarifs_reseau.contrat_hphc.periodes",
     "au moins une période de prix de votre fournisseur (abonnement, HP, HC)"),
    ("tarifs_reseau.contrat_hphc.plages_hc", "les plages d'heures creuses"),
    ("sources.releves_csv", "le nom du fichier de relevés"),
]


def _valeur_config(cfg: dict, chemin: str):
    """Descend dans la configuration le long d'un chemin 'a.b.c'."""
    courant = cfg
    for morceau in chemin.split("."):
        if not isinstance(courant, dict) or morceau not in courant:
            return None
        courant = courant[morceau]
    return courant


def verifier_config(cfg: dict) -> None:
    """Signale en francais ce qui manque a la configuration.

    Sans ce controle, un reglage oublie ressortait en plein visage sous la
    forme d'un message de programmeur -- "KeyError : 'bleu_base'" -- qui ne
    disait ni quel fichier corriger, ni quoi y ecrire.

    Seul l'indispensable est exige. Les sections facultatives (tarif Bleu
    Base d'avant le changement de fournisseur, grille EDF de comparaison,
    recalages sur factures) peuvent etre absentes : l'application s'en
    passe.
    """
    # Une config ecrite avec l'ancien nom de section reste acceptee.
    normaliser_config(cfg)
    manquants = [libelle for chemin, libelle in REGLAGES_OBLIGATOIRES
                 if _valeur_config(cfg, chemin) in (None, "", [], {})]
    if not manquants:
        return
    details = "".join(f"  - {libelle}\n" for libelle in manquants)
    raise RuntimeError(
        "La configuration est incomplète. Il manque :\n\n"
        + details
        + f"\nCorrigez config.yaml (ou config-local.yaml), dans {BASE_DIR}, "
          "puis relancez. Le fichier livre avec l'application sert de "
          "modele."
    )


def build_dataset(cfg: dict) -> AppData:
    verifier_config(cfg)
    releves_csv = cfg["sources"].get("releves_csv")
    if not releves_csv:
        raise RuntimeError(
            "config.yaml : sources.releves_csv est obligatoire (chemin vers le CSV)."
        )
    releves_path = (BASE_DIR / releves_csv).resolve()
    # Garde-fou : le chemin (potentiellement relatif avec des ..) doit rester
    # dans le dossier de l'application, pas pointer ailleurs sur le disque.
    if not releves_path.is_relative_to(BASE_DIR.resolve()):
        raise RuntimeError(
            f"config.yaml : sources.releves_csv pointe hors du dossier de "
            f"l'application ({releves_path}). Placez le CSV a cote de l'app."
        )
    if not releves_path.exists():
        # Premier lancement : on cree le fichier vide au lieu de refuser de
        # demarrer. Refuser enfermait le nouvel utilisateur dans un cercle :
        # les boutons d'import sont DANS l'application, et l'application ne
        # s'ouvrait pas sans donnees. Il ne restait qu'a fabriquer le CSV a
        # la main, avec le bon en-tete, le bon separateur et le bon
        # encodage. Un fichier ne portant que sa ligne d'en-tete suffit :
        # l'application s'ouvre vide, prete a recevoir une saisie ou un
        # import.
        dl.creer_csv_vide(str(releves_path))
        print(f"[info] fichier de releves cree : {releves_path}", file=sys.stderr)

    production, reseau = dl.load_releves_pv(str(releves_path))
    df = calc.merge_series(production, reseau)
    # Copie de la serie AVANT toute correction : c'est elle, et elle seule,
    # que la vue TVA utilise. Les etapes qui suivent (estimation des jours
    # manquants, recalage sur les factures) ameliorent les chiffres affiches
    # partout ailleurs, mais une declaration fiscale doit reposer sur les
    # quantites reellement relevees.
    df_brut = df.copy()
    # Jours sans releve d'injection (avant-contrat OA, pannes Linky) :
    # injection estimee via les ratios mensuels observes, CSV intact.
    df = calc.estime_injection_manquante(df)
    # Puis le tout est recale sur les totaux des factures EDF OA :
    # l'index annuel du compteur de production fait foi, ce sont les
    # kWh reellement payes. CSV intact.
    df = calc.recale_injection_sur_facture(
        df, cfg["sources"].get("injection_facturee"))
    # Jours sans releve de consommation reseau (2022 - debut 2023, hors des
    # 36 mois conserves par Enedis) : totaux lus sur les factures EDF et
    # repartis sur la periode. CSV intact la aussi.
    df = calc.repartit_conso_facturee(df, cfg["sources"].get("conso_reseau_facturee"))
    # Jours dont la conso saisie n'est pas fiable (panne Linky interpolee) :
    # declares sans releve, ils seront reconstitues par le recalage.
    df = calc.marque_conso_douteuse(df, cfg["sources"].get("conso_reseau_douteuse"))
    # Consommations relevees mais arrondies a l'entier (2023-2025) : recalees
    # sur le total des factures EDF, CSV intact.
    df = calc.recale_sur_facture(df, cfg["sources"].get("conso_reseau_recalee"))
    # Part du soutirage qui part dans la voiture (fichier de l'app
    # recharges-ve, lu seulement). Colonne absente si la source n'est pas
    # configuree ou introuvable : les vues s'adaptent.
    ve = _charger_recharges_ve(cfg)
    if ve is not None and not ve.empty:
        for col in ("recharge_ve_kwh", "recharge_ve_eur"):
            df[col] = ve[col].reindex(df.index, fill_value=0.0)

    oa = calc.OAConfig(
        type=cfg["oa"]["type"],
        prix_kwh=cfg["oa"]["prix_kwh_eur"],
        prime_par_kwc=cfg["oa"]["prime_autoconsommation"]["montant_par_kwc"],
        prime_duree=cfg["oa"]["prime_autoconsommation"]["duree_annees"],
        duree_contrat=cfg["oa"]["duree_contrat_annees"],
    )
    # Tarif Bleu Base : facultatif. Il ne concerne que les journees anterieures
    # au passage en heures creuses / heures pleines. Qui n'a jamais eu ce
    # contrat peut supprimer la section : l'application n'en a plus besoin.
    cfg_bleu = cfg["tarifs_reseau"].get("bleu_base") or {}
    bleu = calc.BleuBaseConfig(
        abonnement_tranches=cfg_bleu.get("abonnement_par_periode") or [],
        tranches=cfg_bleu.get("prix_kwh_par_periode") or [],
    )
    # Date de passage en heures pleines / heures creuses : reglable, car elle
    # n'a aucune raison d'etre la meme pour tout le monde.
    calc.definir_bascule_hphc(cfg["tarifs_reseau"].get("bascule_hphc"))
    cfg_octopus = cfg["tarifs_reseau"]["contrat_hphc"]
    octopus = calc.OctopusConfig(
        periodes=calc.periodes_octopus(cfg_octopus),
        plages_hc=calc.parse_plages_hc(cfg_octopus["plages_hc"]),
        # .get : les anciens config.yaml sans cette cle restent valides.
        part_hc_autoconso=float(cfg_octopus.get("part_hc_autoconso", 0.20)),
    )

    start_oa = pd.Timestamp(cfg["installation"]["date_debut_contrat_oa"]).date()
    # debut_contrat : pas de vente OA avant le 28/06/2022 (injection gratuite).
    df = calc.revenu_oa(df, oa, debut_contrat=start_oa)
    df = calc.cout_reseau_journalier(df, None, bleu, octopus)
    df = calc.economies_autoconsommation(df, bleu, octopus)
    df["annee_oa"] = calc.assign_oa_year(df.index, start_oa).values
    df["bilan_jour_eur"] = (
        df["revenu_vente_eur"] + df["economie_eur"] - df["cout_reseau_eur"]
    )
    # Grille EDF de reference (vue Octopus vs EDF), par periodes elle aussi.
    edf_ref = calc.periodes_edf(cfg["tarifs_reseau"].get("comparaison_edf", {}))
    # Grille de valorisation de l'autoconsommation pour la TVA. Facultative :
    # elle ne concerne que les producteurs assujettis a la TVA.
    cfg_lasm = cfg.get("tva_lasm") or {}
    periodes_lasm = calc.periodes_lasm(cfg_lasm)
    lasm = (calc.LasmConfig(periodes=periodes_lasm,
                            taux=float(cfg_lasm.get("taux", 0.20)))
            if periodes_lasm else None)
    return AppData(df=df, cfg=cfg, oa=oa, bleu=bleu, octopus=octopus,
                   start_oa=start_oa, releves_path=str(releves_path),
                   edf_ref=edf_ref, df_brut=df_brut, lasm=lasm,
                   dernieres_saisies=dl.dernieres_saisies(str(releves_path)),
                   dates_illisibles=dl.dates_illisibles(str(releves_path)),
                   dossier_donnees=str(BASE_DIR))


# ----------------------------------------------------------------------
# MainWindow
# ----------------------------------------------------------------------

def _age_court(jours: int) -> str:
    """'aujourd'hui' / 'hier' / 'il y a N jours', pour la barre d'etat."""
    if jours <= 0:
        return "aujourd'hui"
    if jours == 1:
        return "hier"
    return f"il y a {jours} jours"


# Le menu de gauche : (cle, libelle, section ou None, pictogramme).
# Les pictogrammes sont des emojis, comme dans Pecule : Windows les dessine en
# couleur (police Segoe UI Emoji), sans image a fabriquer. Une entree sans
# section appartient a celle de l'entree precedente. Les libelles sont
# accentues — ils se lisent.
NAV_ITEMS = [
    ("dashboard",    "Tableau de bord",      "PRINCIPAL", "🏠"),
    ("saisie",       "Saisie quotidienne",   None,        "✏️"),
    ("transactions", "Relevés journaliers",  None,        "📋"),
    ("categories",   "Répartition énergie",  None,        "🔀"),
    ("accounts",     "Synthèse financière",  None,        "💶"),
    ("oa",           "Années OA",            "CONTRATS",  "📅"),
    ("tva",          "TVA autoconsommation", None,        "🧾"),
    ("stats",        "Statistiques",         "ANALYSE",   "📊"),
    ("comparaison",  "Comparaison N vs N-1", None,        "🔁"),
    # Libelle recalcule au demarrage a partir des noms de fournisseurs
    # declares en config (voir _libelle_comparaison).
    ("octopus_edf",  "Comparaison tarifs",   None,        "⚖️"),
    ("aide",         "Notice",               "AUTRES",    "📖"),
    ("settings",     "Paramètres",           None,        "⚙️"),
]


class MainWindow(QMainWindow):
    def __init__(self, data: AppData, settings: QSettings | None = None):
        super().__init__()
        self.data = data
        # Preferences persistantes (registre Windows). Injectable pour que
        # les tests utilisent un fichier temporaire au lieu des vraies prefs.
        self.settings = settings if settings is not None else QSettings(
            "pv-dashboard", "pv-dashboard")
        # Un seul theme, le clair, comme Pecule : decision de l'auteur du
        # 14/09/2026, valable pour toutes ses applications. Le theme sombre
        # et son bouton de bascule ont ete retires.
        self.theme = LIGHT
        self.current_view = "dashboard"
        self.current_period = self._startup_period()
        self.data.current_period = self.current_period
        puissance = fmt_kwc(self.data.puissance_kwc)
        titre = f"{APP_NAME} {puissance}".strip()
        self.setWindowTitle(f"{titre} - v{APP_VERSION}")
        self.resize(1400, 900)

        self._build_ui()
        self._apply_theme()
        self._switch_view(self.current_view)

        geometrie = self.settings.value("ui/geometry")
        if geometrie is not None:
            self.restoreGeometry(geometrie)

    def _startup_period(self) -> str:
        """Periode affichee a l'ouverture : toujours le mois en cours.

        On ne rouvre volontairement PAS sur la derniere periode consultee :
        apres avoir regarde un mois passe, on retrouverait ces chiffres-la au
        lancement suivant en les prenant pour ceux du mois courant. Repli sur
        toute la periode tant qu'aucun releve n'existe pour le mois en cours
        (il ne figure alors pas dans la liste deroulante).
        """
        mois = f"month-{pd.Timestamp.now().strftime('%Y-%m')}"
        available = {v for _, v in period_options(self.data.df, self.data.start_oa)}
        return mois if mois in available else PERIOD_ALL

    def closeEvent(self, event) -> None:
        self.settings.setValue("ui/geometry", self.saveGeometry())
        super().closeEvent(event)

    # ---------- UI ----------
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        h.addWidget(self._build_sidebar())

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        right.addWidget(self._build_toolbar())

        self.stack = QStackedWidget()
        self.views: dict[str, BaseView] = {
            "dashboard":    DashboardView(self.data, self.theme),
            "saisie":       SaisieView(self.data, self.theme),
            "transactions": TransactionsView(self.data, self.theme),
            "categories":   CategoriesView(self.data, self.theme),
            "accounts":     AccountsView(self.data, self.theme),
            "oa":           OAView(self.data, self.theme),
            "tva":          TvaView(self.data, self.theme),
            "stats":        StatsView(self.data, self.theme),
            "comparaison":  ComparaisonView(self.data, self.theme),
            "octopus_edf":  OctopusEdfView(self.data, self.theme),
            "aide":         AideView(self.data, self.theme),
            "settings":     SettingsView(self.data, self.theme),
        }
        self.views["saisie"].reload_callback = self._on_data_changed
        # Les deux portes d'entree de la fenetre « Mes reglages ».
        self.views["dashboard"].ouvrir_reglages = self._ouvrir_reglages
        self.views["settings"].ouvrir_reglages = self._ouvrir_reglages
        for key in [n[0] for n in NAV_ITEMS]:
            self.stack.addWidget(self.views[key])
        right.addWidget(self.stack, stretch=1)

        right_wrap = QWidget()
        right_wrap.setLayout(right)
        h.addWidget(right_wrap, stretch=1)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status_bar()

    # Au-dela de cette longueur, deux noms de fournisseurs ne tiennent plus
    # dans le menu (largeur fixe de 230 px) : on retombe sur un libelle
    # generique plutot que sur un texte coupe au milieu.
    LARGEUR_MAX_NAV = 22

    def _libelle_comparaison(self, court: bool) -> str:
        """« Octopus vs EDF » chez l'auteur, autre chose ailleurs."""
        mien, mon_offre = self.data.fournisseur
        autre, autre_offre = self.data.fournisseur_reference
        if court:
            libelle = f"{mien} vs {autre}"
            return (libelle if len(libelle) <= self.LARGEUR_MAX_NAV
                    else "Comparaison tarifs")
        return f"{mon_offre} vs {autre_offre}"

    def _build_sidebar(self) -> QFrame:
        """Le bandeau de gauche, sur le modele de celui de Pecule (14/09/2026).

        Des boutons rectangulaires, un emoji devant chaque libelle, des
        sections annoncees par un petit titre souligne. Difference avec
        Pecule, dont les boutons lancent des actions : ici ils menent a des
        pages, et celle qui est affichee est le bouton surligne. Les couleurs
        suivent le theme (gui_theme.py) : en theme clair, ce sont celles de
        Pecule ; en sombre, leur transposition.
        """
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(212)
        v = QVBoxLayout(sidebar)
        v.setContentsMargins(10, 12, 10, 10)
        v.setSpacing(4)

        brand = QLabel("Photovoltaïque")
        brand.setObjectName("Brand")
        v.addWidget(brand)
        puissance = fmt_kwc(self.data.puissance_kwc)
        sub = QLabel(" · ".join(filter(None, [
            puissance, f"OA depuis {self.data.start_oa.strftime('%d/%m/%Y')}"])))
        sub.setObjectName("BrandSub")
        v.addWidget(sub)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: dict[str, QPushButton] = {}

        # La section d'une entree est celle de la derniere entree qui en
        # declarait une, masquee ou non : un onglet cache ne doit jamais
        # emporter avec lui le titre de sa section.
        section_courante = None
        section_affichee = None
        for key, label, section, picto in NAV_ITEMS:
            if section:
                section_courante = section
            if not self._entree_visible(key):
                continue
            if key == "octopus_edf":
                label = self._libelle_comparaison(court=True)
            if section_courante != section_affichee:
                # Comme dans Pecule : un peu d'air, le titre souligne.
                v.addSpacing(11)
                sec = QLabel(section_courante)
                sec.setObjectName("NavSection")
                v.addWidget(sec)
                v.addSpacing(2)
                section_affichee = section_courante
            btn = self._bouton_menu(f"{picto} {label}")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked=False, k=key: self._switch_view(k))
            self.nav_group.addButton(btn)
            self.nav_buttons[key] = btn
            v.addWidget(btn)

        # Trois actions, pas des pages : hors du groupe de navigation, elles
        # ne restent jamais « enfoncees ». Sauvegarde externe : les backups/
        # restent sur le meme disque que les donnees. Mise a jour : repris
        # de Pecule, sans aucun acces reseau.
        self.sauvegarde_btn = self._bouton_menu("💾 Sauvegarde externe")
        self.sauvegarde_btn.setToolTip(
            "Copier vos relevés et vos réglages sur une clé USB ou un disque")
        self.sauvegarde_btn.clicked.connect(self._sauvegarder_externe)
        v.addWidget(self.sauvegarde_btn)

        self.maj_btn = self._bouton_menu("🔄 Mise à jour")
        self.maj_btn.setToolTip(
            "Voir s'il existe une version plus récente (dans votre navigateur)")
        self.maj_btn.clicked.connect(self._ouvrir_mise_a_jour)
        v.addWidget(self.maj_btn)

        # « Votre avis » (repris de Pecule), comme dans Pecule : un bouton de
        # la derniere section.
        self.avis_btn = self._bouton_menu("💬 Votre avis")
        self.avis_btn.setToolTip(
            "Signaler un problème ou proposer une idée "
            "(questionnaire en ligne, dans votre navigateur)")
        self.avis_btn.clicked.connect(self._ouvrir_avis)
        v.addWidget(self.avis_btn)

        # La version va en pied : utile pour une capture d'ecran ou un rapport
        # de bug, mais on ne la lit pas tous les jours.
        v.addStretch(1)
        version = QLabel(f"v{APP_VERSION}")
        version.setObjectName("BrandVersion")
        v.addWidget(version)
        return sidebar

    @staticmethod
    def _bouton_menu(texte: str) -> QPushButton:
        """Un bouton du bandeau : meme hauteur minimale que dans Pecule."""
        btn = QPushButton(texte)
        btn.setObjectName("NavItem")
        btn.setMinimumHeight(30)
        btn.setCursor(Qt.PointingHandCursor)
        return btn

    def _entree_visible(self, key: str) -> bool:
        """Deux onglets ne concernent qu'une partie des utilisateurs :

        - TVA : les seuls producteurs assujettis a la TVA, une petite
          minorite. Visible si la section tva_lasm de config.yaml est remplie.
        - la comparaison avec EDF : sans objet pour qui est deja chez EDF.
          Visible si le fournisseur declare n'est pas celui de reference.

        Les autres onglets sont toujours la."""
        if key == "tva":
            return self.data.lasm is not None
        if key == "octopus_edf":
            return not self.data.meme_fournisseur_que_la_reference
        return True

    def _ouvrir_reglages(self) -> None:
        """Ouvre la fenetre « Mes reglages » ; si elle enregistre, recharge."""
        fenetre = FenetreReglages(reglages.lire_reglages(self.data.cfg),
                                  self._enregistrer_reglages, self)
        if fenetre.exec() == QDialog.Accepted:
            self._recharger_fenetre()

    @staticmethod
    def _enregistrer_reglages(valeurs: dict) -> None:
        reglages.enregistrer_reglages(CONFIG_PATH, valeurs, BASE_DIR / "backups",
                                      verifier=verifier_config)

    def _recharger_fenetre(self) -> None:
        """Les reglages touchent au menu, aux titres et a tous les calculs :
        on reconstruit la fenetre entiere, au meme endroit de l'ecran, au
        lieu de demander de relancer l'application."""
        try:
            data = build_dataset(load_config())
        except Exception as exc:  # frontiere : l'utilisateur doit le savoir
            QMessageBox.warning(
                self, APP_NAME,
                "Réglages enregistrés, mais l'application n'a pas pu les "
                f"relire :\n\n{exc}\n\nRelancez-la.")
            return
        nouvelle = MainWindow(data, self.settings)
        nouvelle.setWindowIcon(self.windowIcon())
        nouvelle.setGeometry(self.geometry())
        nouvelle._switch_view("settings")
        nouvelle.show()
        # Gardee en vie par l'ancienne, elle-meme gardee par le lanceur.
        self._fenetre_suivante = nouvelle
        self.close()

    def _ouvrir_avis(self) -> None:
        """Ouvre la fenetre « Votre avis » (questionnaire en ligne)."""
        avis.AvisDialog(APP_VERSION, self).exec()

    def _ouvrir_mise_a_jour(self) -> None:
        """Ouvre la fenetre « Mise à jour » (liens vers la derniere version)."""
        mise_a_jour.MiseAJourDialog(APP_VERSION, self).exec()

    # Dernier dossier choisi pour la sauvegarde externe, propose la fois
    # suivante (preferences de l'application, pas les donnees).
    CLE_DESTINATION_SAUVEGARDE = "sauvegarde/destination"

    def _sauvegarder_externe(self) -> None:
        """Copie les donnees sur une cle USB ou un disque choisi par
        l'utilisateur. La copie et sa verification : sauvegarde_externe.py."""
        depart = str(self.settings.value(self.CLE_DESTINATION_SAUVEGARDE, "")
                     or "")
        choisi = QFileDialog.getExistingDirectory(
            self, "Choisissez la clé USB ou le disque où sauvegarder", depart)
        if not choisi:
            return                      # l'utilisateur a renonce
        fichiers = [self.data.releves_path, CONFIG_PATH, CONFIG_LOCAL_PATH]
        try:
            cible, copies = sauvegarde_externe.sauvegarder(
                fichiers, Path(choisi), BASE_DIR, "Gestion Photovoltaïque",
                APP_VERSION)
        except sauvegarde_externe.SauvegardeImpossible as e:
            QMessageBox.warning(self, "Sauvegarde impossible", str(e))
            return
        self.settings.setValue(self.CLE_DESTINATION_SAUVEGARDE, choisi)
        liste = "\n".join(f"  • {nom}" for nom in copies)
        QMessageBox.information(
            self, "Sauvegarde terminée",
            f"{len(copies)} fichiers copiés et vérifiés dans :\n{cible}\n\n"
            f"{liste}\n\nPour la remettre en service un jour, suivez le "
            "fichier LISEZMOI.txt placé à côté.")

    def inviter_a_donner_son_avis(self) -> None:
        """L'unique invitation, deux semaines apres le premier lancement.
        Appelee une fois la fenetre affichee."""
        aujourdhui = date.today()
        avis.noter_premiere_utilisation(self.settings, aujourdhui)
        if avis.doit_inviter(self.settings, aujourdhui,
                             not self.data.df.empty):
            avis.inviter(self, self.settings, aujourdhui, APP_VERSION)

    def _build_toolbar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("Toolbar")
        bar.setFixedHeight(84)
        h = QHBoxLayout(bar)
        h.setContentsMargins(20, 10, 20, 10)
        h.setSpacing(14)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.title_lbl = QLabel("Tableau de bord")
        self.title_lbl.setObjectName("ViewTitle")
        self.sub_lbl = QLabel("Vue d'ensemble de l'installation")
        self.sub_lbl.setObjectName("ViewSub")
        title_col.addWidget(self.title_lbl)
        title_col.addWidget(self.sub_lbl)
        h.addLayout(title_col)
        h.addStretch(1)

        # Selecteur de periode : « precedent », annee, mois, « suivant ».
        # Les deux fleches font le geste le plus frequent (le mois d'avant)
        # en un clic, sans ouvrir de liste.
        self.prev_btn = QPushButton("‹")
        self.prev_btn.setObjectName("PeriodArrow")
        self.prev_btn.setCursor(Qt.PointingHandCursor)
        self.prev_btn.clicked.connect(lambda: self._decaler_periode(-1))
        h.addWidget(self.prev_btn)

        # Le menu des annees est le plus large des deux : il porte aussi les
        # annees OA, dont le libelle rappelle les dates de debut et de fin.
        self.year_combo = QComboBox()
        self.year_combo.setObjectName("PeriodSelector")
        self.year_combo.setMinimumWidth(150)
        self.year_combo.currentIndexChanged.connect(self._on_year_changed)
        h.addWidget(self.year_combo)

        self.month_combo = QComboBox()
        self.month_combo.setObjectName("PeriodSelector")
        self.month_combo.setMinimumWidth(130)
        self.month_combo.currentIndexChanged.connect(self._on_month_changed)
        h.addWidget(self.month_combo)

        self.next_btn = QPushButton("›")
        self.next_btn.setObjectName("PeriodArrow")
        self.next_btn.setCursor(Qt.PointingHandCursor)
        self.next_btn.clicked.connect(lambda: self._decaler_periode(+1))
        h.addWidget(self.next_btn)

        self._peupler_selecteur()

        # Plus de bouton Clair / Sombre : un seul theme, le clair (14/09/2026).
        return bar

    # ---------- Theme ----------
    def _apply_theme(self) -> None:
        QApplication.instance().setStyleSheet(qss_for(self.theme))
        matplotlib.rcParams.update(mpl_style(self.theme))
        for v in self.views.values():
            v.set_theme(self.theme)
        # Le rendu de la vue courante n'est volontairement PAS fait ici, pour
        # eviter un double rendu au demarrage : __init__ enchaine _apply_theme
        # puis _switch_view (qui rafraichit).

    # ---------- Navigation ----------
    def _switch_view(self, key: str) -> None:
        self.current_view = key
        idx = [n[0] for n in NAV_ITEMS].index(key)
        self.stack.setCurrentIndex(idx)
        for k, btn in self.nav_buttons.items():
            btn.setChecked(k == key)
            btn.setProperty("active", "true" if k == key else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        titles = {
            "dashboard":    ("Tableau de bord", "Vue d'ensemble de votre installation"),
            "saisie":       ("Saisie quotidienne", "Ajouter ou corriger les relevés d'un jour"),
            "transactions": ("Relevés journaliers", "Production, injection et conso jour par jour"),
            "categories":   ("Répartition énergie", "D'où vient et où va chaque kWh"),
            "accounts":     ("Synthèse financière", "Revenus, économies et dépenses électricité"),
            "oa":           ("Années OA", "Suivi du contrat EDF Obligation d'Achat"),
            "tva":          ("TVA autoconsommation",
                             "Base ligne 5A de la déclaration CA12 / 3517-S"),
            "stats":        ("Statistiques", "Comparaisons annuelles et rendement"),
            "comparaison":  ("Comparaison N vs N-1",
                             "La période choisie vs la même période un an plus tôt"),
            "octopus_edf":  (self._libelle_comparaison(court=False),
                             "Votre contrat face au Tarif Bleu d'EDF"),
            "aide":         ("Notice", "Mode d'emploi et glossaire des termes"),
            "settings":     ("Paramètres", "Configuration de l'application"),
        }
        title, sub = titles[key]
        self.title_lbl.setText(title)
        self.sub_lbl.setText(sub)

        # Grise le selecteur de periode sur les onglets qui ne l'utilisent pas
        # (sinon on croit qu'il est en panne). L'infobulle explique pourquoi.
        vue = self.views[key]
        self._selecteur_actif = vue.utilise_periode
        inutile = ("" if vue.utilise_periode
                   else "Sans effet sur cet onglet : il gère lui-même sa "
                        "période d'affichage.")
        for w in (self.prev_btn, self.year_combo, self.month_combo, self.next_btn):
            w.setToolTip(inutile)
        self._maj_etat_selecteur()

        vue.refresh(self.current_period)

    # ---------- Selecteur de periode ----------
    def _peupler_selecteur(self) -> None:
        """Remet les deux menus d'aplomb sur self.current_period.

        Appelee a la construction, apres chaque changement de periode et
        apres une saisie (de nouveaux mois peuvent etre apparus). Les signaux
        sont coupes pendant l'operation : sans cela, remplir un menu
        declencherait le changement de periode qu'on est en train d'appliquer.
        """
        for combo in (self.year_combo, self.month_combo):
            combo.blockSignals(True)

        self.year_combo.clear()
        for label, value in options_annees(self.data.df, self.data.start_oa):
            self.year_combo.addItem(label, value)
            # Les annees OA sont a cheval sur deux annees civiles : leurs
            # bornes exactes se lisent au survol, faute de tenir dans le menu.
            if value.startswith("oa-"):
                self.year_combo.setItemData(
                    self.year_combo.count() - 1,
                    bornes_annee_oa(self.data.start_oa, int(value.split("-")[1])),
                    Qt.ToolTipRole)
        annee = annee_de_periode(self.current_period)
        cible = f"year-{annee}" if annee is not None else self.current_period
        self.year_combo.setCurrentIndex(self._index_de(self.year_combo, cible))

        # Le menu des mois n'a de sens que sous une annee civile : « toute la
        # periode » et les annees OA sont a cheval sur les mois.
        self.month_combo.clear()
        if annee is None:
            self.month_combo.addItem("Toute l'année", MOIS_TOUS)
        else:
            for label, value in options_mois(self.data.df, annee):
                self.month_combo.addItem(label, value)
            cible = (self.current_period
                     if self.current_period.startswith("month-") else MOIS_TOUS)
            self.month_combo.setCurrentIndex(self._index_de(self.month_combo, cible))

        for combo in (self.year_combo, self.month_combo):
            combo.blockSignals(False)
        self._maj_etat_selecteur()

    @staticmethod
    def _index_de(combo: QComboBox, valeur: str) -> int:
        """Rang de `valeur` dans un menu, 0 si elle n'y est pas."""
        return next((i for i in range(combo.count())
                     if combo.itemData(i) == valeur), 0)

    def _maj_etat_selecteur(self) -> None:
        """Active ou grise les quatre elements du selecteur.

        Une fleche grisee dit qu'il n'y a plus rien de ce cote ; cliquable
        mais sans effet, elle ferait croire a une panne.
        """
        actif = getattr(self, "_selecteur_actif", True)
        annee = annee_de_periode(self.current_period)
        self.year_combo.setEnabled(actif)
        self.month_combo.setEnabled(actif and annee is not None)
        for bouton, sens in ((self.prev_btn, -1), (self.next_btn, +1)):
            voisine = periode_voisine(self.data.df, self.data.start_oa,
                                      self.current_period, sens)
            bouton.setEnabled(actif and voisine is not None)

    def _appliquer_periode(self, periode: str) -> None:
        """Change la periode affichee et remet toute la barre d'aplomb."""
        self.current_period = periode or PERIOD_ALL
        self.data.current_period = self.current_period
        self._peupler_selecteur()
        self.views[self.current_view].refresh(self.current_period)

    def _on_year_changed(self, idx: int) -> None:
        valeur = self.year_combo.itemData(idx)
        if valeur is None:
            return
        # En changeant d'annee on garde le mois affiche s'il existe la-bas :
        # c'est ce qu'on veut pour comparer un mois d'une annee sur l'autre.
        # Sinon on montre l'annee entiere plutot qu'un ecran vide.
        if self.current_period.startswith("month-") and valeur.startswith("year-"):
            annee = int(valeur.split("-")[1])
            candidat = f"month-{annee}-{self.current_period[-2:]}"
            if candidat in {v for _, v in options_mois(self.data.df, annee)}:
                valeur = candidat
        self._appliquer_periode(valeur)

    def _on_month_changed(self, idx: int) -> None:
        valeur = self.month_combo.itemData(idx)
        if valeur is None:
            return
        if valeur == MOIS_TOUS:
            valeur = self.year_combo.currentData() or PERIOD_ALL
        self._appliquer_periode(valeur)

    def _decaler_periode(self, sens: int) -> None:
        """Un cran en arriere (sens=-1) ou en avant (+1), a echelle constante :
        un mois reste un mois, une annee reste une annee."""
        voisine = periode_voisine(self.data.df, self.data.start_oa,
                                  self.current_period, sens)
        if voisine is not None:
            self._appliquer_periode(voisine)

    def _update_status_bar(self) -> None:
        """Barre d'etat : volume, production cumulee, fichier et fraicheur.

        Reconstruite apres chaque saisie : sinon elle continuerait d'annoncer
        l'ancien nombre de jours et l'ancien age des donnees.
        """
        dernier = self.data.dernieres_saisies.get("Prod_Jour")
        age = ""
        if dernier is not None:
            jours = (date.today() - dernier).days
            age = f" - Dernier relevé {_age_court(jours)}"
        self.status_bar.showMessage(
            f"  {len(self.data.df)} jour(s) - "
            f"Production cumulée {fmt_kwh(self.data.df['production_kwh'].sum())}"
            f"{age} - Données : {self.data.releves_path}"
        )

    def _on_data_changed(self) -> None:
        """Recharge le CSV apres une saisie et rafraichit toutes les vues."""
        cfg = load_config()
        self.data = build_dataset(cfg)
        for vue in self.views.values():
            vue.data = self.data
        # De nouveaux mois (voire une nouvelle annee) peuvent etre apparus.
        # Si la periode affichee a disparu du fichier, on retombe sur toute la
        # periode plutot que de rester sur un mois fantome.
        valides = {v for _, v in period_options(self.data.df, self.data.start_oa)}
        if self.current_period not in valides:
            self.current_period = PERIOD_ALL
        self.data.current_period = self.current_period
        self._peupler_selecteur()
        self.views[self.current_view].refresh(self.current_period)
        self._update_status_bar()


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

# L'icone : a cote des donnees dans le projet ; a cote du programme une fois
# installe (l'installeur la pose la, pas dans le dossier personnel).
ICON_PATH = BASE_DIR / "pv-dashboard.ico"
if not ICON_PATH.exists() and getattr(sys, "frozen", False):
    ICON_PATH = Path(sys.executable).parent / "pv-dashboard.ico"


WIN_APP_ID = "pvdashboard.gestion.6kwc"


def set_windows_app_id() -> None:
    """Windows : identite d'app distincte pour que la barre des taches affiche
    notre icone et non celle de Python/pythonw. A appeler AVANT la creation de
    QApplication. Sans effet hors Windows."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(WIN_APP_ID)
    except (OSError, AttributeError) as exc:
        # Cosmetique : si echec, la barre des taches affichera l'icone Python.
        print(f"[warn] SetCurrentProcessExplicitAppUserModelID: {exc}",
              file=sys.stderr)


def configure_application(app: QApplication) -> None:
    """Renseigne nom, version et icone sur la QApplication."""
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("PV Dashboard")
    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))


def create_window() -> MainWindow:
    """Charge la config + les donnees et construit la fenetre principale.
    Suppose qu'une QApplication existe deja. Leve une exception en cas d'erreur
    (config.yaml, CSV) : c'est a l'appelant de la signaler a l'utilisateur."""
    if getattr(sys, "frozen", False):
        # Premier lancement d'une installation neuve : sans config.yaml,
        # l'application ne pourrait pas demarrer.
        MODELES_POSES[:] = installer_modeles_config(
            BASE_DIR, Path(sys.executable).parent)
    cfg = load_config()
    _sauvegarder_config_local()
    data = build_dataset(cfg)
    win = MainWindow(data)
    if ICON_PATH.exists():
        win.setWindowIcon(QIcon(str(ICON_PATH)))
    return win


def annoncer_premier_lancement(parent: QWidget | None) -> None:
    """Invite le nouvel utilisateur a decrire SON installation. Ne dit rien
    aux lancements suivants.

    Le message donnait autrefois le chemin de config.yaml, a ouvrir avec le
    Bloc-notes : de quoi decourager un debutant. Il ouvre maintenant la
    fenetre « Mes reglages ».
    """
    if "config.yaml" not in MODELES_POSES:
        return
    boite = QMessageBox(parent)
    boite.setIcon(QMessageBox.Information)
    boite.setWindowTitle(APP_NAME)
    boite.setText(
        "Bienvenue !\n\n"
        "Les réglages affichés sont ceux d'une installation d'exemple. "
        "Commencez par décrire la vôtre : puissance, coût, dates du contrat, "
        "prix de votre fournisseur. Deux minutes suffisent.")
    remplir = boite.addButton("Remplir mes réglages", QMessageBox.AcceptRole)
    boite.addButton("Plus tard", QMessageBox.RejectRole)
    boite.exec()
    if boite.clickedButton() is remplir and hasattr(parent, "_ouvrir_reglages"):
        parent._ouvrir_reglages()


def prendre_le_verrou(chemin: str | None = None) -> QLockFile | None:
    """Verrou d'instance unique. Rend le QLockFile, ou None s'il est deja pris.

    Rien n'empechait de lancer deux fois l'application. Or les deux fenetres
    lisent le meme CSV au demarrage, puis le reecrivent INTEGRALEMENT a
    chaque enregistrement : la derniere a enregistrer gagne, et les saisies
    faites dans l'autre fenetre disparaissent sans un mot.

    Le verrou doit rester vivant tant que l'application tourne : main() le
    garde donc dans une variable jusqu'a la fin.
    """
    chemin = chemin or os.path.join(QDir.tempPath(), "pv-dashboard.lock")
    verrou = QLockFile(chemin)
    # 0 = pas de peremption par le temps. Un verrou laisse par une
    # application qui a plante est repris grace au PID qu'il contient, mais
    # une session longue n'est jamais consideree comme abandonnee.
    verrou.setStaleLockTime(0)
    return verrou if verrou.tryLock(100) else None


def main() -> int:
    set_windows_app_id()
    app = QApplication(sys.argv)
    configure_application(app)

    verrou = prendre_le_verrou()
    if verrou is None:
        QMessageBox.warning(
            None, APP_NAME,
            f"{APP_NAME} est déjà ouvert.\n\n"
            "Deux fenêtres ouvertes en même temps se réécrivent le même "
            "fichier de relevés : la dernière enregistrée effacerait les "
            "saisies de l'autre.\n\n"
            "Utilisez la fenetre déjà ouverte.")
        return 1

    # Chargement config + donnees APRES la creation de QApplication :
    # en cas d'erreur (config.yaml malforme, CSV introuvable...) on peut
    # afficher une boite de dialogue au lieu de mourir silencieusement
    # sous pythonw (ou seul le fichier log recevait la trace).
    try:
        win = create_window()
    except Exception as exc:  # frontiere applicative : tout doit etre signale
        traceback.print_exc()  # trace complete -> pv-dashboard.log sous pythonw
        QMessageBox.critical(
            None,
            APP_NAME,
            "Impossible de démarrer l'application.\n\n"
            f"{type(exc).__name__} : {exc}\n\n"
            "Vérifiez config.yaml et le fichier de relevés.\n"
            f"Trace complète dans {LOG_PATH.name}.",
        )
        return 1

    win.show()
    annoncer_premier_lancement(win)
    win.inviter_a_donner_son_avis()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
