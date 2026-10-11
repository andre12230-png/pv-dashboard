"""
Application desktop PySide6 - Dashboard photovoltaique style "appli comptes".

Se lance par run.py (Lancer.vbs, Lancer.bat, l'exe) : c'est lui qui montre
l'ecran d'attente puis ouvre cette fenetre.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("QtAgg")
import pandas as pd
import yaml
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
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
    QScrollArea,
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
from erreurs import erreur_en_clair
from fenetre_reglages import FenetreReglages
from gui_theme import LIGHT, appliquer_style, mpl_style, qss_for
from gui_widgets import demander_enregistrement
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
    mois_de_reference,
    nombre_de_jours,
    options_annees,
    options_mois,
    period_options,
    periode_voisine,
)
from views._helpers import definir_acheteur, mot_annee

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
# Le meme nom, tel qu'il s'affiche (titre de la fenetre, boites de message).
# APP_NAME garde sa forme d'origine : c'est le nom de l'application pour Qt,
# qu'il vaut mieux ne pas changer d'une version a l'autre (29/09/2026).
NOM_AFFICHE = "Gestion Photovoltaïque"
APP_VERSION = "1.52.22"


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
            f"{chemin} est mal écrit{ligne}. Vérifiez les deux-points, "
            "les tirets et l'alignement des lignes autour de cet endroit, "
            "puis relancez l'application."
        ) from exc
    if contenu is None:
        return {}
    if not isinstance(contenu, dict):
        raise RuntimeError(
            f"{chemin} ne contient pas une configuration valide "
            "(il devrait commencer par des sections comme 'installation:')."
        )
    try:
        return _valeurs_a_la_francaise(contenu)
    except ValueError as exc:
        raise RuntimeError(f"{chemin} : {erreur_en_clair(exc)}") from exc


# Un nombre ecrit a la francaise, seul dans sa case : « 0,22 », « -1,5 ».
_NOMBRE_A_VIRGULE = re.compile(r"^\s*-?\d+,\d+\s*$")


def _valeurs_a_la_francaise(valeur):
    """Recopie la configuration en lisant ce qu'un Francais tape a la main
    (audit du 08/10/2026) :
    - une date JJ/MM/AAAA devient AAAA-MM-JJ, le seul format que le reste du
      programme comprend sans ambiguite (« 01/06/2024 » etait lu le 6
      janvier) ;
    - un nombre a virgule (« 0,22 ») devient un nombre (il donnait
      « could not convert string to float », en anglais).
    Fait ici, a la lecture, une fois pour tout le fichier."""
    if isinstance(valeur, dict):
        return {cle: _valeurs_a_la_francaise(v) for cle, v in valeur.items()}
    if isinstance(valeur, list):
        return [_valeurs_a_la_francaise(v) for v in valeur]
    if isinstance(valeur, str):
        if _NOMBRE_A_VIRGULE.match(valeur):
            return float(valeur.strip().replace(",", "."))
        return reglages.date_francaise_en_iso(valeur) or valeur
    return valeur


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
    ("tarifs_reseau.contrat_hphc.periodes",
     "au moins une période de prix de votre fournisseur (abonnement, HP, HC)"),
    ("tarifs_reseau.contrat_hphc.plages_hc", "les plages d'heures creuses"),
    ("sources.releves_csv", "le nom du fichier de relevés"),
]
# Exiges seulement si l'on vend son electricite (oa.type « surplus » ou
# « totale ») : sans revente, il n'y a ni contrat, ni prix, ni date.
REGLAGES_VENTE = [
    ("installation.date_debut_contrat_oa", "la date de debut du contrat de vente"),
    ("oa.prix_kwh_eur", "le prix d'achat du kWh vendu, en EUR/kWh"),
    ("oa.duree_contrat_annees", "la duree du contrat de vente, en annees"),
]
# Les trois facons de vendre (ou non) son electricite.
TYPES_VENTE = ("surplus", "totale", "aucune")


def type_vente(cfg: dict) -> str:
    """oa.type, « surplus » s'il n'est pas dit (le cas des anciens fichiers)."""
    return str((cfg.get("oa") or {}).get("type") or "surplus")


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
    vente = type_vente(cfg)
    if vente not in TYPES_VENTE:
        raise RuntimeError(
            f"config.yaml : oa.type vaut « {vente} ». Il doit valoir "
            "surplus, totale ou aucune (vente du surplus, vente de toute la "
            f"production, ou pas de vente). Corrigez-le dans {BASE_DIR}, "
            "puis relancez.")
    exiges = REGLAGES_OBLIGATOIRES + (REGLAGES_VENTE if vente != "aucune" else [])
    manquants = [libelle for chemin, libelle in exiges
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
    # Journees dont seule la production est connue, en fin de serie : Enedis
    # publie conso et injection le lendemain. Elles sont mises de cote (le CSV
    # les garde) plutot que comptees a 0 kWh au reseau, ce qui afficherait
    # 100 % d'autoproduction. Le tableau de bord les nomme.
    attente = calc.jours_en_attente(df)
    if len(attente):
        df = df.drop(index=attente)
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
    # Jours sans releve de consommation reseau (plus anciens que les 36 mois
    # conserves par Enedis) : totaux lus sur les factures et repartis sur
    # la periode. CSV intact la aussi.
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

    # Vente du surplus (avec prime), vente totale, ou pas de vente du tout.
    # La prime a l'autoconsommation ne va qu'a la vente du SURPLUS : en vente
    # totale rien n'est autoconsomme, et sans vente il n'y a pas de contrat.
    # Elle etait pourtant comptee en vente totale.
    cfg_oa = cfg.get("oa") or {}
    vente = type_vente(cfg)
    cfg_prime = cfg_oa.get("prime_autoconsommation") or {}
    avec_prime = vente == "surplus"
    oa = calc.OAConfig(
        type=vente,
        prix_kwh=float(cfg_oa.get("prix_kwh_eur") or 0) if vente != "aucune" else 0.0,
        prime_par_kwc=float(cfg_prime.get("montant_par_kwc") or 0) if avec_prime else 0.0,
        prime_duree=int(cfg_prime.get("duree_annees") or 0) if avec_prime else 0,
        duree_contrat=int(cfg_oa.get("duree_contrat_annees") or 0),
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
    cfg_octopus = cfg["tarifs_reseau"]["contrat_hphc"]
    bascule = cfg["tarifs_reseau"].get("bascule_hphc")
    # Poser la date declaree AVANT de lire les periodes : une config a
    # l'ancien format date sa periode unique de la bascule, qui aurait ete
    # celle du calcul precedent (reglage global du module).
    calc.definir_bascule_hphc(bascule)
    if not bleu.tranches:
        # Aucun tarif a prix unique declare : l'utilisateur ne l'a jamais eu,
        # toutes ses journees relevent du contrat HP/HC (avant sa premiere
        # periode, c'est elle qui sert). Sans cela, les journees d'avant la
        # date de bascule etaient comptees a 0 EUR, sans un mot. La bascule
        # recule donc a la plus ancienne des dates connues.
        candidats = [pd.Timestamp(p["debut"])
                     for p in calc.periodes_octopus(cfg_octopus)]
        if not df.empty:
            candidats.append(pd.Timestamp(df.index.min()).normalize())
        bascule = min(candidats).date().isoformat()
    calc.definir_bascule_hphc(bascule)
    octopus = calc.OctopusConfig(
        periodes=calc.periodes_octopus(cfg_octopus),
        plages_hc=calc.parse_plages_hc(cfg_octopus["plages_hc"]),
        # Sans part ecrite : estimee d'apres les plages HC (28/09/2026), la
        # meme que montre « Mes reglages » (reglages._part_hc).
        part_hc_autoconso=(
            float(cfg_octopus["part_hc_autoconso"])
            if cfg_octopus.get("part_hc_autoconso") is not None
            else calc.estimer_part_hc_autoconso(
                calc.parse_plages_hc(cfg_octopus["plages_hc"]))),
    )

    # Pas de vente, pas de contrat : ni date de debut, ni « annees OA ».
    debut_contrat = cfg["installation"].get("date_debut_contrat_oa")
    start_oa = (pd.Timestamp(debut_contrat).date()
                if vente != "aucune" and debut_contrat else None)
    # Vente totale : rien n'est autoconsomme, toute la production est vendue.
    if vente == "totale":
        df = calc.applique_vente_totale(df)
        df_brut = calc.applique_vente_totale(df_brut)
    # debut_contrat : pas de vente OA avant le debut du contrat (injection gratuite).
    df = calc.revenu_oa(df, oa, debut_contrat=start_oa)
    df = calc.cout_reseau_journalier(df, None, bleu, octopus)
    df = calc.economies_autoconsommation(df, bleu, octopus)
    df["annee_oa"] = (calc.assign_oa_year(df.index, start_oa).values
                      if start_oa is not None else 0)
    df["bilan_jour_eur"] = (
        df["revenu_vente_eur"] + df["economie_eur"] - df["cout_reseau_eur"]
    )
    # Grille EDF de reference (vue Octopus ou EDF), par periodes elle aussi.
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
                   valeurs_illisibles=dl.valeurs_illisibles(str(releves_path)),
                   jours_en_attente=[d.date() for d in attente],
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
    ("comparaison",  "Comparer à l'an passé", None,       "🔁"),
    # Libelle recalcule au demarrage a partir des noms de fournisseurs
    # declares en config (voir AppData.libelle_comparaison).
    ("octopus_edf",  "Comparaison tarifs",   None,        "⚖️"),
    # Fin du menu comme dans Pecule (29/09/2026 ; c'etait une section
    # « AUTRES ») : « MES DONNÉES » (💾 Sauvegarde externe, une action, posee
    # par _build_sidebar juste avant RÉGLAGES), RÉGLAGES, puis AIDE, ou
    # suivent les actions 💬 Votre avis et 🔄 Mise à jour.
    ("settings",     "Paramètres",           "RÉGLAGES",  "⚙️"),
    ("aide",         "Notice",               "AIDE",      "📖"),
]


class MainWindow(QMainWindow):
    def __init__(self, data: AppData, settings: QSettings | None = None):
        # « Années OA » ou « Années de contrat », selon l'acheteur : a poser
        # avant de construire le menu et les pages.
        definir_acheteur(data.acheteur)
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
        titre = f"{NOM_AFFICHE} {puissance}".strip()
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

    def _saisies_reglees(self, avant: str) -> bool:
        """Avant de fermer la fenetre : que faire des valeurs tapees dans la
        Saisie et pas encore enregistrees ? Fermer les perdait sans un mot.

        Rend True si l'on peut continuer (rien en cours, enregistre, ou
        abandon choisi), False si l'utilisateur annule ou si l'enregistrement
        echoue. « Annuler » est le bouton par defaut."""
        saisie = self.views.get("saisie")
        if saisie is None or not saisie.a_des_saisies_en_cours():
            return True
        reponse = demander_enregistrement(
            self, NOM_AFFICHE,
            "Des valeurs tapées dans la Saisie quotidienne ne sont pas "
            f"encore enregistrées.\n\nLes enregistrer {avant} ?")
        if reponse == QMessageBox.Cancel:
            return False
        if reponse == QMessageBox.Save and not saisie._enregistrer():
            # Valeur refusee ou ecriture impossible : la raison s'affiche sous
            # le tableau. On y ramene l'utilisateur plutot que de continuer.
            self._switch_view("saisie")
            return False
        # Enregistre ou abandonne : le tableau repart du fichier, plus rien
        # n'est en attente.
        saisie._cache_mtime = None
        saisie.refresh(self.current_period)
        return True

    def closeEvent(self, event) -> None:
        if not self._saisies_reglees("avant de fermer"):
            event.ignore()
            return
        self.settings.setValue("ui/geometry", self.saveGeometry())
        super().closeEvent(event)

    # ---------- UI ----------
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # Le bandeau defile, comme dans Pecule et Recharges VE (29/09/2026) :
        # sans cela, la fenetre ne pouvait pas descendre sous la hauteur du
        # menu (731 px), trop pour un portable 1366 x 768.
        defilement = QScrollArea()
        defilement.setWidget(self._build_sidebar())
        defilement.setWidgetResizable(True)
        defilement.setFrameShape(QFrame.NoFrame)
        defilement.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        defilement.setFixedWidth(212)
        h.addWidget(defilement)

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
        self.views["dashboard"].rappel_sauvegarde = self._rappel_sauvegarde
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

    def _build_sidebar(self) -> QFrame:
        """Le bandeau de gauche, sur le modele de celui de Pecule (14/09/2026).

        Des boutons rectangulaires, un emoji devant chaque libelle, des
        sections annoncees par un petit titre souligne. Difference avec
        Pecule, dont les boutons lancent des actions : ici ils menent a des
        pages, et celle qui est affichee est le bouton surligne. Les couleurs
        suivent le theme (gui_theme.py), clair et seul : celles de Pecule.
        """
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        v = QVBoxLayout(sidebar)
        v.setContentsMargins(10, 12, 10, 10)
        v.setSpacing(4)

        brand = QLabel("Photovoltaïque")
        brand.setObjectName("Brand")
        v.addWidget(brand)
        puissance = fmt_kwc(self.data.puissance_kwc)
        debut = self.data.start_oa
        sub = QLabel(" · ".join(filter(None, [
            puissance,
            (f"{'OA' if self.data.acheteur == 'EDF OA' else 'Vente'} depuis "
             f"{debut.strftime('%d/%m/%Y')}") if debut else None])))
        sub.setObjectName("BrandSub")
        v.addWidget(sub)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: dict[str, QPushButton] = {}

        # Trois actions, pas des pages : hors du groupe de navigation, elles
        # ne restent jamais « enfoncees ». Sauvegarde externe : les backups/
        # restent sur le meme disque que les donnees. Mise a jour : repris
        # de Pecule, sans aucun acces reseau. Creees ici, placees plus bas.
        self.sauvegarde_btn = self._bouton_menu("💾 Sauvegarde externe")
        self.sauvegarde_btn.setToolTip(
            "Copier vos relevés et vos réglages sur une clé USB ou un disque")
        self.sauvegarde_btn.clicked.connect(self._sauvegarder_externe)

        self.maj_btn = self._bouton_menu("🔄 Mise à jour")
        self.maj_btn.setToolTip(
            "Voir s'il existe une version plus récente (dans votre navigateur)")
        self.maj_btn.clicked.connect(self._ouvrir_mise_a_jour)

        # « Votre avis » (repris de Pecule), comme dans Pecule : un bouton de
        # la derniere section.
        self.avis_btn = self._bouton_menu("💬 Votre avis")
        self.avis_btn.setToolTip(
            "Signaler un problème ou proposer une idée "
            "(questionnaire en ligne, dans votre navigateur)")
        self.avis_btn.clicked.connect(self._ouvrir_avis)

        def titre_de_section(nom: str) -> None:
            # Comme dans Pecule : un peu d'air, le titre souligne.
            v.addSpacing(11)
            sec = QLabel(nom)
            sec.setObjectName("NavSection")
            v.addWidget(sec)
            v.addSpacing(2)

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
                label = self.data.libelle_comparaison
            if key == "oa":
                label = mot_annee("pluriel")
            if section_courante != section_affichee:
                # Comme dans Pecule, « MES DONNÉES » precede « RÉGLAGES ».
                if section_courante == "RÉGLAGES":
                    titre_de_section("MES DONNÉES")
                    v.addWidget(self.sauvegarde_btn)
                titre_de_section(section_courante)
                section_affichee = section_courante
            btn = self._bouton_menu(f"{picto} {label}")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked=False, k=key: self._switch_view(k))
            self.nav_group.addButton(btn)
            self.nav_buttons[key] = btn
            v.addWidget(btn)

        # Fin de la section AIDE, dans l'ordre de Pecule : Notice (la page,
        # juste au-dessus), Votre avis, Mise a jour.
        v.addWidget(self.avis_btn)
        v.addWidget(self.maj_btn)

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
        """Trois onglets ne concernent qu'une partie des utilisateurs :

        - Années OA : qui revend son surplus sous contrat.
        - TVA : les seuls producteurs assujettis a la TVA, une petite
          minorite. Visible si la section tva_lasm de config.yaml est remplie.
        - la comparaison avec EDF : sans objet pour qui est deja chez EDF.
          Visible si le fournisseur declare n'est pas celui de reference.

        Les autres onglets sont toujours la."""
        if key == "tva":
            return self.data.lasm is not None
        if key == "octopus_edf":
            return not self.data.meme_fournisseur_que_la_reference
        if key == "oa":
            # Sans contrat de vente, pas d'annees de contrat a montrer.
            return self.data.start_oa is not None
        return True

    def _ouvrir_reglages(self) -> None:
        """Ouvre la fenetre « Mes reglages » ; si elle enregistre, recharge."""
        # Enregistrer des reglages reconstruit toute la fenetre : la question
        # sur la Saisie se pose donc AVANT, pas une fois la nouvelle ouverte.
        if not self._saisies_reglees("avant d'ouvrir vos réglages"):
            return
        # Un reglage illisible ne laisse plus le clic sans effet visible
        # (audit du 08/10/2026) : on dit lequel, en francais.
        try:
            valeurs = reglages.lire_reglages(self.data.cfg)
            recalages = reglages.lire_recalages(self.data.cfg)
        except (ValueError, TypeError, KeyError, OSError) as exc:
            QMessageBox.warning(
                self, "Réglages illisibles",
                "Vos réglages n'ont pas pu être lus : "
                f"{erreur_en_clair(exc)}\n\nCorrigez cette valeur dans "
                "config.yaml (Paramètres indique son dossier), puis relancez "
                "l'application.")
            return
        fenetre = FenetreReglages(
            valeurs, self._enregistrer_reglages, self,
            recalages=recalages,
            enregistrer_recalages=self._enregistrer_recalages)
        if fenetre.exec() == QDialog.Accepted:
            self._recharger_fenetre()

    @staticmethod
    def _enregistrer_recalages(recalages: dict) -> None:
        """Ecrit les recalages sur factures dans config-local.yaml."""
        reglages.enregistrer_recalages(CONFIG_LOCAL_PATH, recalages,
                                       BASE_DIR / "backups")

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
                self, NOM_AFFICHE,
                "Réglages enregistrés, mais l'application n'a pas pu les "
                f"relire :\n\n{erreur_en_clair(exc)}\n\nRelancez-la.")
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
    # Jour de la derniere sauvegarde externe reussie (AAAA-MM-JJ), pour le
    # rappel du tableau de bord (28/09/2026).
    CLE_DERNIERE_SAUVEGARDE = "sauvegarde/derniere"

    def _rappel_sauvegarde(self) -> str | None:
        """Le rappel de sauvegarde externe, commun aux trois applications.
        Sans sauvegarde jamais faite, on compte depuis la premiere
        utilisation (retenue par avis.py)."""
        return sauvegarde_externe.rappel_sauvegarde_externe(
            self.settings.value(self.CLE_DERNIERE_SAUVEGARDE) or None,
            self.settings.value(avis.CLE_PREMIERE_UTILISATION) or None)

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
            QMessageBox.warning(self, "Sauvegarde impossible",
                                erreur_en_clair(e))
            return
        self.settings.setValue(self.CLE_DESTINATION_SAUVEGARDE, choisi)
        self.settings.setValue(self.CLE_DERNIERE_SAUVEGARDE,
                               date.today().isoformat())
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
        # « Période : » devant, comme Pecule et Recharges VE (choix de
        # l'auteur du 08/10/2026) ; grise avec le selecteur.
        self.lbl_periode = QLabel("Période :")
        self.lbl_periode.setObjectName("LibellePeriode")
        h.addWidget(self.lbl_periode)
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

        # Retour au mois en cours en un clic, apres etre alle voir un mois
        # passe (meme bouton que Pecule et Recharges VE, 23/09/2026). Grise
        # quand on y est deja : il dit alors aussi qu'on regarde bien le mois
        # en cours, pas de vieux chiffres. Avant l'import du mois, il mene au
        # dernier mois qui a des releves (cf. mois_de_reference).
        self.btn_ce_mois = QPushButton("Ce mois-ci")
        self.btn_ce_mois.setObjectName("PeriodToday")
        self.btn_ce_mois.setCursor(Qt.PointingHandCursor)
        self.btn_ce_mois.clicked.connect(self._aller_au_mois_en_cours)
        h.addWidget(self.btn_ce_mois)

        # Raccourcis clavier, dans toute la fenetre : Ctrl+Gauche / Ctrl+Droite
        # (mois precedent / suivant), Ctrl+Origine (mois en cours). Une zone de
        # saisie garde ses propres Ctrl+Gauche / Ctrl+Droite (sauter un mot) :
        # Qt lui laisse la priorite quand elle a le curseur. Sans effet sur
        # les onglets qui n'utilisent pas la periode, comme le selecteur.
        self.raccourcis_periode = []
        for touches, action in (
                ("Ctrl+Left", lambda: self._raccourci_periode(-1)),
                ("Ctrl+Right", lambda: self._raccourci_periode(+1)),
                ("Ctrl+Home", lambda: self._raccourci_periode(0))):
            sc = QShortcut(QKeySequence(touches), self)
            sc.setContext(Qt.WindowShortcut)
            sc.activated.connect(action)
            self.raccourcis_periode.append(sc)

        self._peupler_selecteur()

        # Plus de bouton Clair / Sombre : un seul theme, le clair (14/09/2026).
        return bar

    # ---------- Theme ----------
    def _apply_theme(self) -> None:
        # Fusion et palette claire d'abord (resistent au mode sombre de
        # Windows), puis la feuille de style par-dessus.
        appliquer_style(QApplication.instance())
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
        # Le bouton coché est la page affichée : la feuille de style le
        # surligne par « :checked » (une propriété « active » doublait ce
        # marquage, retirée le 11/10/2026).
        for k, btn in self.nav_buttons.items():
            btn.setChecked(k == key)
        titles = {
            "dashboard":    ("Tableau de bord", "Vue d'ensemble de votre installation"),
            "saisie":       ("Saisie quotidienne", "Ajouter ou corriger les relevés d'un jour"),
            "transactions": ("Relevés journaliers",
                             "Production, injection et achat au réseau, jour par jour"),
            "categories":   ("Répartition énergie", "D'où vient et où va chaque kWh"),
            "accounts":     ("Synthèse financière",
                             "Vente, économies, achat au réseau et remboursement"),
            "oa":           (mot_annee("pluriel"),
                             "Suivi du contrat EDF Obligation d'Achat"
                             if self.data.acheteur == "EDF OA"
                             else f"Suivi de votre contrat avec "
                                  f"{self.data.acheteur}"),
            "tva":          ("TVA autoconsommation",
                             "Livraison à soi-même — ligne 5A de la "
                             "déclaration CA12 / 3517-S"),
            "stats":        ("Statistiques", "Comparaisons annuelles et rendement"),
            "comparaison":  ("Comparer à l'an passé",
                             f"Le mois, l'année ou l'{mot_annee('minuscule')} choisis en haut, "
                             "face à la même période un an plus tôt"),
            # Le nom du menu, pour arriver la ou l'on a clique ; les noms
            # complets des deux offres en sous-titre (30/09/2026).
            "octopus_edf":  (self.data.libelle_comparaison,
                             f"{self.data.fournisseur[1]} face à "
                             f"{self.data.fournisseur_reference[1]}"),
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
        self.btn_ce_mois.setToolTip(
            inutile or "Revenir au mois en cours (Ctrl+Origine)")
        # Pages ou seule l'annee a un sens (Statistiques) : pas de menu des
        # mois, et le bouton parle d'annee.
        self.month_combo.setVisible(not vue.selecteur_annuel)
        self.btn_ce_mois.setText(
            "Cette année" if vue.selecteur_annuel else "Ce mois-ci")
        if not inutile:
            self.prev_btn.setToolTip("Période précédente (Ctrl+←)")
            self.next_btn.setToolTip("Période suivante (Ctrl+→)")
        self._maj_etat_selecteur()

        # Une vue qui porte des valeurs tapees et pas encore enregistrees n'est
        # pas redessinee : le dessin repart du fichier et les effacait sans un
        # mot (quitter la Saisie puis y revenir, recliquer sur son onglet).
        if not vue.a_des_saisies_en_cours():
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
        self.lbl_periode.setEnabled(actif)
        self.year_combo.setEnabled(actif)
        self.month_combo.setEnabled(actif and annee is not None)
        for bouton, sens in ((self.prev_btn, -1), (self.next_btn, +1)):
            voisine = periode_voisine(self.data.df, self.data.start_oa,
                                      self.current_period, sens)
            bouton.setEnabled(actif and voisine is not None)
        cible = mois_de_reference(self.data.df)
        self.btn_ce_mois.setEnabled(
            actif and cible is not None and self.current_period != cible)

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

    def _aller_au_mois_en_cours(self) -> None:
        """Bouton « Ce mois-ci » : le mois en cours, ou le dernier mois
        releve tant que le mois en cours n'a rien."""
        cible = mois_de_reference(self.data.df)
        if cible is not None:
            self._appliquer_periode(cible)

    def _raccourci_periode(self, sens: int) -> None:
        """Ctrl+Gauche (-1), Ctrl+Droite (+1), Ctrl+Origine (0). Sans effet
        quand le selecteur est grise pour l'onglet affiche."""
        if not getattr(self, "_selecteur_actif", True):
            return
        if sens == 0:
            self._aller_au_mois_en_cours()
        else:
            self._decaler_periode(sens)

    def _update_status_bar(self) -> None:
        """Barre d'etat : volume, production cumulee, fichier et fraicheur.

        Reconstruite apres chaque saisie : sinon elle continuerait d'annoncer
        l'ancien nombre de jours et l'ancien age des donnees.
        """
        dernier = self.data.dernieres_saisies.get("Prod_Jour")
        age = ""
        if dernier is not None:
            jours = (date.today() - dernier).days
            age = f" · Dernier relevé {_age_court(jours)}"
        # Des « · » plutot que des « - » (relecture du 30/09/2026).
        self.status_bar.showMessage(
            f"  {nombre_de_jours(len(self.data.df))} · "
            f"Production cumulée {fmt_kwh(self.data.df['production_kwh'].sum())}"
            f"{age} · Données : {self.data.releves_path}"
        )

    def _on_data_changed(self) -> None:
        """Recharge le CSV apres une saisie et rafraichit toutes les vues."""
        try:
            data = build_dataset(load_config())
        except Exception as exc:  # frontiere : l'utilisateur doit le savoir
            # Les releves sont bien enregistres ; c'est la relecture qui
            # echoue (config.yaml retouche au Bloc-notes, appli ouverte...).
            # On garde l'affichage precedent plutot que d'echouer sans un mot.
            QMessageBox.warning(
                self, NOM_AFFICHE,
                "Vos relevés sont enregistrés, mais l'application n'a pas pu "
                f"les relire :\n\n{erreur_en_clair(exc)}\n\n"
                "Corrigez config.yaml si vous l'avez modifié, puis relancez "
                "l'application.")
            return
        self.data = data
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
    boite.setWindowTitle(NOM_AFFICHE)
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
