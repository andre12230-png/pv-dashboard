"""
Chargement / ecriture du CSV consolide "Releves-pv.csv".

Format du CSV (locale FR) :
    Date;Prod_Jour;Inj_Jour;Conso_reseau_Jour;Conso_HC;Conso_HP
    01/01/2024;12,5;;;;
    ...

- separateur ";", decimales ","
- dates DD/MM/YYYY
- granularite journaliere
- cases vides autorisees (donnee non disponible)

API publique :
    load_releves_pv(path)   -> (production_df, reseau_df) au format pipeline
    read_releves_raw(path)  -> liste de dicts pour l'editeur de saisie
    write_releves_raw(path, rows) -> reecrit le CSV en preservant le format
    normalise_date_saisie(texte)   -> valide une date tapee ('DD/MM/YYYY')
    normalise_nombre_saisie(texte) -> valide un kWh tape (format FR)
    retirer_jour_en_cours(valeurs) -> enleve la journee en cours (incomplete)
    merge_import(rows, colonne, valeurs) -> fusion sans doublon par date

Reimportes d'autres fichiers depuis le 28/09/2026 (dl.xxx marche toujours) :
    imports_releves.py      -> parse_enedis_fichier, parse_enphase_fichier...
                               (lecture des fichiers a importer)
    lecture_recharges_ve.py -> charger_recharges_ve (recharges.json de
                               l'application Recharges VE, lecture seule)
"""

from __future__ import annotations

import csv
import os
import shutil
import sys
from datetime import date as _date
from typing import Iterable

import pandas as pd

from accords import accorde, pluriel

# Porte d'entree : tout ce qui a ete detache le 28/09/2026 reste
# accessible ici (dl.parse_enedis_fichier, dl._parse_nombre...).
from imports_releves import (  # noqa: F401
    _COLONNES_RAPPORT_ONDULEUR,
    _COLONNES_SUIVI_CONSO,
    _ENTETES_AUTOCONSO_RAPPORT,
    _ENTETES_CONSO,
    _ENTETES_DATE_RAPPORT,
    _ENTETES_HC,
    _ENTETES_HP,
    _ENTETES_INDEX_TOTAL,
    _FEUILLES_ENEDIS,
    _MOTS_CONSO,
    _MOTS_INJECTION,
    _RE_DATE_FR,
    _RE_DATE_HEURE_FR,
    _RE_DATE_ISO,
    _RE_NOMBRE,
    _cellule_date,
    _cellule_nombre,
    _charger_openpyxl,
    _decode_texte,
    _decoupe_ligne,
    _en_date,
    _entete_du_fichier,
    _fmt_kwh_fr,
    _index_d_une_feuille,
    _lire_archive,
    _lire_texte,
    _nombre_cellule,
    _normalise_entete,
    _noter_lignes_ecartees,
    _noter_unite_devinee,
    _parse_date_any,
    _parse_jour_any,
    _parse_nombre,
    _rapport_d_une_feuille,
    _type_de_donnees,
    _unite_annoncee,
    _valeur_ligne,
    consommation_depuis_index,
    parse_enedis_csv,
    parse_enedis_csv_texte,
    parse_enedis_fichier,
    parse_enedis_index_xlsx,
    parse_enedis_xlsx,
    parse_enphase_fichier,
    parse_enphase_texte,
    parse_octopus_suivi_conso,
    parse_rapport_onduleur_xlsx,
)
from lecture_recharges_ve import (  # noqa: F401
    charger_recharges_ve,
)


def _first_matching(cols: Iterable[str], candidates: Iterable[str]) -> str | None:
    cols_lower = {c.lower().strip(): c for c in cols}
    for cand in candidates:
        if cand.lower() in cols_lower:
            return cols_lower[cand.lower()]
    return None


# ----------------------------------------------------------------------
# CSV consolide "Releves-pv.csv"
# ----------------------------------------------------------------------

_RELEVES_DATE_CANDIDATES = ("Date", "Jour", "Date_jour")
_RELEVES_PROD_CANDIDATES = ("Prod_Jour", "Production", "Prod")
_RELEVES_INJ_CANDIDATES = ("Inj_Jour", "Injection", "Inj")
_RELEVES_SOUT_CANDIDATES = (
    "Conso_reseau_Jour", "Conso_réseau_Jour", "Conso_Jour", "Soutirage", "Conso",
)
_RELEVES_HC_CANDIDATES = ("Conso_HC", "HC", "Heures_creuses")
_RELEVES_HP_CANDIDATES = ("Conso_HP", "HP", "Heures_pleines")


def _read_releves_csv(path: str) -> pd.DataFrame:
    """Lit le CSV consolide en gerant l'encodage et le separateur FR."""
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            df = pd.read_csv(
                path, sep=";", decimal=",", encoding=encoding,
                dtype=str, keep_default_na=False,
            )
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"Encodage non reconnu pour {path}")

    df.columns = [c.strip() for c in df.columns]
    return df


def load_releves_pv(path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Charge le CSV consolide et retourne (production, reseau).

    - production : DataFrame indexe par timestamp (jour) avec 'production_kwh'.
    - reseau     : DataFrame indexe par timestamp (jour) avec 'injection_kwh',
                   'soutirage_kwh', 'releve_incomplet' (1.0 les jours avec
                   production saisie mais sans releve d'injection), et
                   eventuellement 'soutirage_hp_kwh' / 'soutirage_hc_kwh'
                   si les colonnes HP/HC sont renseignees.
    """
    df = _read_releves_csv(path)

    date_col = _first_matching(df.columns, _RELEVES_DATE_CANDIDATES)
    prod_col = _first_matching(df.columns, _RELEVES_PROD_CANDIDATES)
    inj_col = _first_matching(df.columns, _RELEVES_INJ_CANDIDATES)
    sout_col = _first_matching(df.columns, _RELEVES_SOUT_CANDIDATES)
    hc_col = _first_matching(df.columns, _RELEVES_HC_CANDIDATES)
    hp_col = _first_matching(df.columns, _RELEVES_HP_CANDIDATES)

    if date_col is None or prod_col is None:
        raise ValueError(
            f"Releves-pv.csv non reconnu ({path}). "
            f"Colonnes trouvées : {list(df.columns)}"
        )

    def _to_num(series: pd.Series) -> pd.Series:
        s = series.astype(str).str.strip().str.replace(",", ".", regex=False)
        s = s.replace({"": None, "nan": None, "NaN": None})
        return pd.to_numeric(s, errors="coerce")

    out = pd.DataFrame()
    out["timestamp"] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
    out["production_kwh"] = _to_num(df[prod_col])
    out["injection_kwh"] = _to_num(df[inj_col]) if inj_col else pd.NA
    out["soutirage_jour_kwh"] = _to_num(df[sout_col]) if sout_col else pd.NA
    out["soutirage_hc_kwh"] = _to_num(df[hc_col]) if hc_col else pd.NA
    out["soutirage_hp_kwh"] = _to_num(df[hp_col]) if hp_col else pd.NA

    out = out.dropna(subset=["timestamp"]).set_index("timestamp").sort_index()
    out = out[~out.index.duplicated(keep="last")]

    # Soutirage total : preference au champ direct ; sinon HC+HP.
    sout_direct = out["soutirage_jour_kwh"]
    sout_hphc = out[["soutirage_hc_kwh", "soutirage_hp_kwh"]].sum(
        axis=1, min_count=1,
    )
    soutirage = sout_direct.where(sout_direct.notna(), sout_hphc)

    production = pd.DataFrame(
        {"production_kwh": out["production_kwh"].fillna(0.0)},
        index=out.index,
    )
    reseau = pd.DataFrame(
        {
            "injection_kwh": out["injection_kwh"].fillna(0.0),
            "soutirage_kwh": soutirage.fillna(0.0),
            # 1.0 quand le jour a une production saisie mais pas de releve
            # d'injection Enedis : l'autoconso vaut alors toute la production
            # (estimation haute), les vues le signalent.
            "releve_incomplet": (
                out["injection_kwh"].isna() & out["production_kwh"].notna()
            ).astype(float),
            # 1.0 quand aucun releve de consommation reseau n'existe pour ce
            # jour (ni total, ni HC/HP). Sans marqueur, le fillna ci-dessus
            # ferait passer ces jours pour une consommation reelle de 0 kWh :
            # facture sous-evaluee et autoproduction affichee a 100 %.
            "conso_absente": soutirage.isna().astype(float),
        },
        index=out.index,
    )
    # On expose le detail HP/HC uniquement quand au moins une valeur est connue,
    # pour que le calcul de cout reseau puisse l'utiliser quand il existe.
    if out["soutirage_hp_kwh"].notna().any() or out["soutirage_hc_kwh"].notna().any():
        reseau["soutirage_hp_kwh"] = out["soutirage_hp_kwh"]
        reseau["soutirage_hc_kwh"] = out["soutirage_hc_kwh"]

    return production, reseau


# Colonnes du CSV consolide, en preservant l'orthographe avec accent.
RELEVES_HEADER = [
    "Date", "Prod_Jour", "Inj_Jour",
    "Conso_réseau_Jour", "Conso_HC", "Conso_HP",
]


def creer_csv_vide(path: str) -> None:
    """Cree un fichier de releves ne portant que sa ligne d'en-tete.

    Sert au tout premier lancement : sans fichier, l'application refusait de
    demarrer et il fallait le fabriquer a la main, avec le bon separateur, le
    bon encodage et l'accent de "Conso_réseau_Jour". Trois pieges pour qui
    n'a jamais ouvert un CSV.

    N'ecrase jamais un fichier existant : les donnees passent avant tout.
    """
    if os.path.exists(path):
        return
    dossier = os.path.dirname(os.path.abspath(path))
    os.makedirs(dossier, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(";".join(RELEVES_HEADER) + "\n")


def _date_key(row: dict[str, str]) -> tuple[int, int, int]:
    """Cle de tri chronologique pour une ligne avec date FR DD/MM/YYYY."""
    try:
        d, m, y = row["Date"].split("/")
        return (int(y), int(m), int(d))
    except (ValueError, KeyError):
        return (0, 0, 0)


def read_releves_raw(path: str) -> list[dict[str, str]]:
    """
    Lit le CSV consolide en preservant les valeurs sous forme de chaines
    (utile pour un editeur : on ne perd pas la representation virgule/point).

    Retourne une liste de dicts {colonne -> valeur_str}, triee par date
    croissante. Les valeurs manquantes sont des chaines vides.

    Leve ValueError si une colonne du format n'a AUCUN alias correspondant
    dans l'en-tete : mieux vaut refuser de lire que rendre une colonne vide
    qu'un enregistrement effacerait ensuite pour de bon. Les variantes de
    nom documentees (accent ou non, "Production" pour "Prod_Jour"...)
    restent acceptees.
    """
    if not os.path.exists(path):
        return []

    df = _read_releves_csv(path)  # deja en str grace au dtype=str

    # Mapping nom officiel -> nom trouve (pour gerer les variantes d'accent)
    aliases = {
        "Date": _RELEVES_DATE_CANDIDATES,
        "Prod_Jour": _RELEVES_PROD_CANDIDATES,
        "Inj_Jour": _RELEVES_INJ_CANDIDATES,
        "Conso_réseau_Jour": _RELEVES_SOUT_CANDIDATES,
        "Conso_HC": _RELEVES_HC_CANDIDATES,
        "Conso_HP": _RELEVES_HP_CANDIDATES,
    }
    colmap: dict[str, str] = {}
    manquantes: list[str] = []
    for officiel, candidats in aliases.items():
        trouve = _first_matching(df.columns, candidats)
        if trouve is None:
            manquantes.append(officiel)
        else:
            colmap[officiel] = trouve

    # Une colonne dont AUCUN alias ne correspond etait simplement absente de
    # colmap, et la comprehension ci-dessous donnait alors "" a toutes les
    # lignes -- sans exception ni avertissement. L'application demarrait
    # normalement (load_releves_pv n'exige que Date et Prod_Jour), les vues
    # affichaient des chiffres plausibles, puis le premier Enregistrer
    # reecrivait le fichier a partir de ces chaines vides : des annees de
    # releves detruites, et l'anomalie d'en-tete effacee du meme coup.
    if manquantes:
        raise ValueError(
            f"{os.path.basename(path)} : "
            f"{accorde(len(manquantes), 'colonne')} "
            f"{accorde(len(manquantes), 'introuvable')} dans "
            f"l'en-tête : {', '.join(manquantes)}.\n"
            f"En-têtes lus dans le fichier : {list(df.columns)}.\n"
            "Aucun des noms acceptés ne correspond. Le fichier n'est pas lu, "
            "car une colonne lue vide serait effacée au premier "
            "enregistrement.\n"
            "Cause la plus fréquente : le fichier a été ouvert puis "
            "réenregistré par Excel, qui a abîmé les accents de l'en-tête."
        )

    # Colonne par colonne, et non ligne par ligne : iterrows fabriquait un
    # objet par ligne et prenait a lui seul la moitie du temps du calcul
    # complet (0,3 s sur quatre ans de releves, 28/09/2026). Meme resultat,
    # garde par test_read_raw_meme_resultat_que_la_lecture_ligne_a_ligne.
    colonnes = {officiel: [str(v).strip() for v in df[colmap[officiel]]]
                for officiel in RELEVES_HEADER}
    rows: list[dict[str, str]] = []
    for i in range(len(df)):
        row = {officiel: colonnes[officiel][i] for officiel in RELEVES_HEADER}
        if not row["Date"]:
            continue
        rows.append(row)

    # Tri chronologique par date FR (DD/MM/YYYY).
    rows.sort(key=_date_key)
    return rows


def dates_illisibles(path: str) -> list[str]:
    """
    Dates du CSV que pandas n'arrive pas a lire, dans l'ordre du fichier.

    load_releves_pv fait to_datetime(errors="coerce") puis dropna : une date
    illisible fait donc disparaitre la journee de TOUS les calculs, en
    silence -- alors qu'elle reste parfaitement visible dans l'onglet Saisie.
    L'ecart entre les deux est incomprehensible tant que personne ne le dit.

    Le CSV n'est pas modifie : c'est un constat, la correction se fait a la
    main dans la vue Saisie.
    """
    if not os.path.exists(path):
        return []
    df = _read_releves_csv(path)
    date_col = _first_matching(df.columns, _RELEVES_DATE_CANDIDATES)
    if date_col is None:
        return []

    brutes = df[date_col].astype(str).str.strip()
    # Meme lecture que load_releves_pv, pour compter exactement ce qu'elle
    # ecarte -- ni plus, ni moins.
    lues = pd.to_datetime(brutes, errors="coerce", dayfirst=True)
    return [
        brut for brut, lisible in zip(brutes, lues.notna(), strict=True)
        if brut and not lisible
    ]


def dernieres_saisies(path: str) -> dict[str, _date]:
    """
    Pour chaque colonne du CSV, la date du dernier jour reellement renseigne.

    Sert a dire d'un coup d'oeil ce qui est a jour et ce qui ne l'est pas.
    Les grandeurs n'avancent pas au meme rythme : la production vient
    d'Enphase (disponible le jour meme), l'injection et la consommation
    d'Enedis (deux jours de retard environ), le detail HC/HP d'Octopus
    plus tard encore. Une date unique pour tout le fichier ne dirait pas
    grand-chose.

    Une case vide ne compte pas : seule une valeur saisie fait foi.
    """
    dernieres: dict[str, _date] = {}
    for row in read_releves_raw(path):
        jour = _parse_date_any(row.get("Date", ""))
        if jour is None:
            continue
        d, m, y = (int(x) for x in jour.split("/"))
        quand = _date(y, m, d)
        for colonne in RELEVES_HEADER[1:]:
            if (row.get(colonne) or "").strip():
                if colonne not in dernieres or quand > dernieres[colonne]:
                    dernieres[colonne] = quand
    return dernieres


# ----------------------------------------------------------------------
# Bornes de plausibilite a la saisie
# ----------------------------------------------------------------------
# La faute de frappe la plus courante est la virgule oubliee : 251 tape au
# lieu de 25,1. Sans borne haute la valeur passe, et elle fausse ensuite
# toutes les moyennes sans que rien ne le signale.
#
# Production et injection : le plafond DEPEND de la taille de l'installation.
# Un beau jour d'ete, une installation produit rarement plus de 7 kWh par
# kWc. Avec une marge de moitie : 10 kWh par kWc, soit 60 kWh sur 6 kWc.
#
# Ce plafond etait fige a 60 : une installation de 9 kWc voyait ses journees
# d'ete refusees a la saisie, avec un message parlant de valeur improbable
# alors qu'elle etait vraie.
KWH_MAX_PAR_KWC = 10.0
PUISSANCE_PAR_DEFAUT_KWC = 6.0
MAX_KWH_JOUR = KWH_MAX_PAR_KWC * PUISSANCE_PAR_DEFAUT_KWC
# Consommation reseau : elle ne depend pas de l'installation mais du
# chauffage et de la recharge du vehicule, elle monte donc bien plus haut.
# Un foyer chauffe a l'electricite qui recharge une voiture peut soutirer
# 80 kWh un jour d'hiver. Marge x1,9 environ -> 150 kWh.
#
# Un plafond unique a 60 refuserait de vraies journees d'hiver :
# la vue Saisie deviendrait impossible a enregistrer des qu'elle en affiche
# une. D'ou deux plafonds, et non un seul.
MAX_KWH_JOUR_CONSO = 150.0

PLAFONDS_COLONNES = {
    "Prod_Jour": MAX_KWH_JOUR,
    "Inj_Jour": MAX_KWH_JOUR,
    "Conso_réseau_Jour": MAX_KWH_JOUR_CONSO,
    "Conso_HC": MAX_KWH_JOUR_CONSO,
    "Conso_HP": MAX_KWH_JOUR_CONSO,
}


def plafond_colonne(colonne: str, puissance_kwc: float | None = None) -> float:
    """Plafond de plausibilite d'une colonne officielle du CSV.

    `puissance_kwc` adapte le plafond de production et d'injection a la
    taille de l'installation (10 kWh par kWc). Sans elle, on garde celui
    d'une installation de 6 kWc.

    Colonne inconnue : on prend le plafond le plus permissif, mieux vaut
    laisser passer que refuser une valeur legitime.
    """
    plafond = PLAFONDS_COLONNES.get(colonne, MAX_KWH_JOUR_CONSO)
    if puissance_kwc and colonne in ("Prod_Jour", "Inj_Jour"):
        return max(float(puissance_kwc) * KWH_MAX_PAR_KWC, 1.0)
    return plafond


def normalise_date_saisie(texte: str, aujourdhui: _date | None = None) -> str:
    """
    Valide une date tapee dans la vue Saisie et la rend au format 'DD/MM/YYYY'.

    Strict volontairement : pandas acceptait '2026' (-> 01/01/2026) et
    '01/2026' (-> 01/01/2026), si bien qu'une frappe incomplete ecrasait
    silencieusement le releve du 1er janvier. On exige donc jour, mois et
    annee sur 4 chiffres (la forme ISO 2026-07-30 passe aussi).

    Leve ValueError avec un message lisible si la date n'est pas valide.
    """
    texte = (texte or "").strip()
    if not texte:
        raise ValueError("date manquante")
    jour = _parse_date_any(texte)
    if jour is None:
        raise ValueError(
            f"date '{texte}' incomplète ou mal formée "
            "(attendu JJ/MM/AAAA, par exemple 30/07/2026)")

    # Une date dans le futur n'est pas un releve : c'est une faute de frappe
    # sur l'annee. 2062 au lieu de 2026 faisait passer le fichier de 1572 a
    # 14721 lignes (resample("D") comble les jours manquants) et divisait la
    # production moyenne par neuf, sans le moindre avertissement.
    d, m, y = (int(x) for x in jour.split("/"))
    reference = aujourdhui or _date.today()
    if _date(y, m, d) > reference:
        raise ValueError(
            f"date '{jour}' dans le futur : nous sommes le "
            f"{reference:%d/%m/%Y}, un relevé ne peut pas la porter")
    return jour


def normalise_nombre_saisie(texte: str, colonne: str = "",
                            plafond: float = MAX_KWH_JOUR) -> str:
    """
    Valide une valeur tapee dans la vue Saisie et la rend au format FR
    (virgule decimale), espaces retires. Une case vide reste vide : c'est
    autorise.

    La valeur rendue est celle qui sera ECRITE dans le CSV : elle doit donc
    etre relisible par _parse_nombre et par pandas.

    Refuse ce qui n'a pas de sens pour des kWh : texte, valeur negative,
    'inf' et 'nan' (que float() acceptait, ce qui contaminait ensuite tous
    les totaux avec des NaN), et valeur au-dessus du `plafond` de
    plausibilite de la colonne (voir plafond_colonne).

    Leve ValueError avec un message lisible.
    """
    texte = (texte or "").strip()
    if not texte:
        return ""
    ou = f" ({colonne})" if colonne else ""
    valeur = texte.replace(",", ".").replace(" ", "").replace(" ", "")
    try:
        nombre = float(valeur)
    except ValueError:
        raise ValueError(
            f"valeur '{texte}'{ou} : attendu un nombre, par exemple 24,8"
        ) from None
    if nombre != nombre or nombre in (float("inf"), float("-inf")):
        raise ValueError(f"valeur '{texte}'{ou} : nombre non exploitable")
    if nombre < 0:
        raise ValueError(
            f"valeur '{texte}'{ou} : un relevé en kWh ne peut pas être négatif")
    if nombre > plafond:
        raise ValueError(
            f"valeur '{texte}'{ou} : {_fmt_kwh_fr(nombre)}\xa0kWh dépasse le "
            f"maximum plausible de {_fmt_kwh_fr(plafond)}\xa0kWh pour une "
            "journée (virgule oubliée ?)")
    # On rend la valeur NORMALISEE, pas le texte tape. Avant, '22, 1' etait
    # accepte puis ecrit tel quel dans le CSV : a la relecture, plus rien ne
    # savait le lire et la journee valait 0 kWh -- pire qu'une case vide, qui
    # elle est reperee comme absente et comblee.
    return _fmt_kwh_fr(nombre)


def retirer_jour_en_cours(valeurs: dict[str, str],
                          aujourdhui: _date | None = None) -> str | None:
    """
    Retire du dictionnaire le jour en cours (journee forcement incomplete :
    le rapport s'arrete a l'heure de sa generation). Modifie le dictionnaire
    et retourne la date retiree, ou None s'il n'y en avait pas.
    """
    jour = aujourdhui or _date.today()
    cle = f"{jour.day:02d}/{jour.month:02d}/{jour.year:04d}"
    return cle if valeurs.pop(cle, None) is not None else None


def merge_import(rows: list[dict[str, str]], colonne: str,
                 valeurs: dict[str, str]) -> tuple[list[dict[str, str]], int, int, int]:
    """
    Fusionne des valeurs importees {date: kwh_str} dans les lignes du CSV,
    sans jamais creer de doublon (fusion par date).

    La valeur importee REMPLACE celle de la colonne pour les dates deja
    presentes ; les autres colonnes de la ligne ne sont pas touchees.

    Retourne (lignes, nb_nouveaux, nb_remplaces, nb_inchanges).
    """
    toutes = {r["Date"]: dict(r) for r in rows}
    nb_nouveaux = nb_remplaces = nb_inchanges = 0
    for date_fr, val in valeurs.items():
        if date_fr in toutes:
            if toutes[date_fr].get(colonne, "") == val:
                nb_inchanges += 1
            else:
                nb_remplaces += 1
            toutes[date_fr][colonne] = val
        else:
            ligne = {c: "" for c in RELEVES_HEADER}
            ligne["Date"] = date_fr
            ligne[colonne] = val
            toutes[date_fr] = ligne
            nb_nouveaux += 1
    return list(toutes.values()), nb_nouveaux, nb_remplaces, nb_inchanges


def garder_si_case_vide(rows: list[dict[str, str]], colonne: str,
                        valeurs: dict[str, str]) -> tuple[dict[str, str], int]:
    """
    Ne garde d'un import que les journees dont la case est encore vide.

    Sert aux grandeurs dont le gestionnaire de reseau est la source de
    verite : l'injection et la consommation reseau. Le rapport d'un onduleur
    les COMPLETE la ou Enedis n'a rien (avant la mise en service du
    compteur), mais ne doit jamais ecrire par-dessus un releve existant --
    ces valeurs servent de base a la TVA sur l'autoconsommation.

    Une journee absente du CSV n'a rien a proteger : elle est gardee.

    Retourne (valeurs_a_importer, nombre_de_journees_ecartees).
    """
    occupees = {
        r["Date"] for r in rows if (r.get(colonne) or "").strip()
    }
    gardees = {d: v for d, v in valeurs.items() if d not in occupees}
    return gardees, len(valeurs) - len(gardees)


def controle_apres_import(rows: list[dict[str, str]],
                          colonne: str,
                          valeurs: dict[str, str]) -> str | None:
    """
    Verifie qu'un import ne produit pas de valeurs physiquement impossibles.

    Seul controle vraiment discriminant : **l'injection ne peut jamais
    depasser la production du meme jour** (on n'injecte que du surplus).
    Un export de consommation range par erreur dans la colonne Injection
    se trahit ainsi immediatement, la conso etant sans rapport avec la
    production du jour.

    Retourne un message d'avertissement, ou None si tout est coherent.
    """
    if colonne != "Inj_Jour" or not valeurs:
        return None
    par_date = {r["Date"]: r for r in rows}

    def _num(v: str) -> float | None:
        v = (v or "").strip().replace(",", ".")
        try:
            return float(v) if v else None
        except ValueError:
            return None

    suspects, exemples = 0, []
    compares = 0
    for jour, val in valeurs.items():
        inj = _num(val)
        prod = _num(par_date.get(jour, {}).get("Prod_Jour", ""))
        if inj is None or prod is None or prod <= 0:
            continue
        compares += 1
        if inj > prod * 1.05:  # 5 % de tolerance (arrondis, pas de mesure)
            suspects += 1
            if len(exemples) < 3:
                exemples.append(f"{jour} : {val} injecté pour {prod:g} produit")
    if compares == 0 or suspects <= compares * 0.10:
        return None
    return (
        f"Attention : sur {pluriel(compares, 'jour')} "
        f"{accorde(compares, 'comparable')}, {suspects} "
        f"{accorde(suspects, 'aurait', 'auraient')} "
        f"une injection SUPÉRIEURE à la production.\n\n"
        + "\n".join("  - " + e for e in exemples)
        + "\n\nC'est impossible : on n'injecte que le surplus. Ce fichier "
        "contient probablement une autre grandeur (une consommation ?) "
        "que l'application a prise pour de l'injection."
    )


def controle_vraisemblance(colonne: str, valeurs: dict[str, str],
                           libelle: str,
                           puissance_kwc: float | None = None) -> str | None:
    """
    Des valeurs importees depassent-elles le maximum vraisemblable ?

    Meme plafond que la saisie a la main (plafond_colonne), qui ne
    s'appliquait pas aux imports : des Wh lus comme des kWh -- mille fois
    trop -- passaient sans un mot. Ce n'est qu'une alerte : une vraie journee
    exceptionnelle doit rester importable (decision du 26/09/2026, le
    plafond ne bloque que ce qui est tape).

    Retourne un message d'avertissement, ou None si tout est vraisemblable.
    """
    plafond = plafond_colonne(colonne, puissance_kwc)
    trop: list[tuple[str, str]] = []
    for jour, val in valeurs.items():
        v = _parse_nombre(val or "")
        if v is not None and v > plafond:
            trop.append((jour, val))
    if not trop:
        return None
    exemples = "\n".join(f"  - {jour} : {val}\xa0kWh" for jour, val in trop[:3])
    return (
        f"Attention : {pluriel(len(trop), 'valeur')} de {libelle} "
        f"{accorde(len(trop), 'dépasse', 'dépassent')} le maximum "
        f"vraisemblable ({plafond:g}\xa0kWh par jour).\n\n{exemples}\n\n"
        "Une unité mal lue (des Wh pris pour des kWh) ou une colonne qui "
        "n'est pas la bonne donne ce genre de chiffres. Vérifiez le fichier "
        "avant d'appliquer."
    )


class ReductionRefusee(ValueError):
    """L'ecriture demandee ferait disparaitre des donnees presentes sur le disque.

    Levee par write_releves_raw quand le nombre de lignes, ou le nombre de
    valeurs d'une colonne, baisserait par rapport au fichier existant.

    La vue Saisie l'attrape, decrit la perte a l'utilisateur, et ne recommence
    avec autoriser_reduction=True que s'il confirme. L'attribut `pertes` porte
    la description lisible, prete a etre affichee.
    """

    def __init__(self, pertes: str):
        self.pertes = pertes
        super().__init__(
            f"Enregistrement refusé : {pertes}. "
            "Si cet effacement est voulu, il doit être confirmé."
        )


def _volumetrie(rows: list[dict[str, str]]) -> tuple[int, dict[str, int]]:
    """(nombre de lignes datees, nombre de valeurs non vides par colonne)."""
    par_colonne = {col: 0 for col in RELEVES_HEADER[1:]}
    lignes = 0
    for row in rows:
        if not (row.get("Date") or "").strip():
            continue
        lignes += 1
        for col in RELEVES_HEADER[1:]:
            if (row.get(col) or "").strip():
                par_colonne[col] += 1
    return lignes, par_colonne


def _volumetrie_sur_disque(path: str) -> tuple[int, dict[str, int]]:
    """Volumetrie du fichier existant, (0, {}) s'il n'y en a pas.

    Si le fichier existe mais n'est plus lisible comme CSV structure (en-tete
    abime, encodage casse), on ne peut plus compter par colonne ; le nombre de
    lignes reste mesurable et suffit deja a reperer une troncature.
    """
    if not os.path.exists(path):
        return 0, {}
    try:
        return _volumetrie(read_releves_raw(path))
    except (OSError, ValueError):
        pass
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lignes = [ligne for ligne in fh.read().splitlines() if ligne.strip()]
        return max(len(lignes) - 1, 0), {}   # -1 pour la ligne d'en-tete
    except OSError:
        return 0, {}


def _enumere(morceaux: list[str]) -> str:
    """['a', 'b', 'c'] -> 'a, b et c'."""
    if len(morceaux) == 1:
        return morceaux[0]
    return ", ".join(morceaux[:-1]) + " et " + morceaux[-1]


def pertes_a_l_ecriture(path: str,
                        rows: list[dict[str, str]]) -> str | None:
    """
    Decrit ce qu'ecrire `rows` dans `path` ferait disparaitre, ou None.

    Compare au fichier existant sur le disque le nombre de lignes ET le
    nombre de valeurs non vides de chaque colonne. Les deux comptent : vider
    une colonne sur toutes les lignes ne change pas le nombre de lignes.

    Sert a decrire la perte a l'utilisateur AVANT de la lui faire subir ;
    write_releves_raw s'en sert pour refuser par defaut.
    """
    lignes_avant, cols_avant = _volumetrie_sur_disque(path)
    lignes_apres, cols_apres = _volumetrie(rows)

    pertes: list[str] = []
    total = 0
    if lignes_apres < lignes_avant:
        pertes.append(pluriel(lignes_avant - lignes_apres, "ligne"))
        total += lignes_avant - lignes_apres
    for col, avant in cols_avant.items():
        manque = avant - cols_apres.get(col, 0)
        if manque > 0:
            pertes.append(f"{pluriel(manque, 'valeur')} de {col}")
            total += manque
    if not pertes:
        return None
    # « 1 ligne va etre supprimee », « 2 lignes vont etre supprimees »
    return _enumere(pertes) + (" va être supprimée" if total == 1
                               else " vont être supprimées")


def write_releves_raw(path: str, rows: list[dict[str, str]],
                      autoriser_reduction: bool = False) -> None:
    """
    Reecrit le CSV consolide en preservant le format FR :
    - separateur ";"
    - dates DD/MM/YYYY
    - decimales avec virgule
    - encodage UTF-8 (sans BOM)
    - en-tete avec accent : 'Conso_réseau_Jour'
    Les valeurs sont passees telles quelles (deja en chaines avec virgule),
    a ceci pres qu'une valeur contenant un ';' est mise entre guillemets pour
    rester relisible.

    Ecriture atomique : le contenu est ecrit dans un fichier temporaire puis
    substitue d'un coup via os.replace. Si l'ecriture echoue en cours de
    route (verrou de synchro cloud, disque plein, coupure), le CSV existant reste
    intact. L'ancienne version est conservee dans <path>.bak.

    Le fichier est reconstruit INTEGRALEMENT a partir de `rows` : ce qui n'y
    figure pas disparait. Une lecture partielle deviendrait donc une
    suppression definitive. D'ou le controle de volumetrie : si le nombre de
    lignes ou le nombre de valeurs d'une colonne baisse, ReductionRefusee est
    levee. `autoriser_reduction=True` passe outre -- l'appelant doit alors
    avoir fait confirmer la perte, que pertes_a_l_ecriture sait decrire.
    """
    if not autoriser_reduction:
        pertes = pertes_a_l_ecriture(path, rows)
        if pertes is not None:
            raise ReductionRefusee(pertes)

    rows_sorted = [row for row in sorted(rows, key=_date_key)
                   if row.get("Date")]

    tmp_path = path + ".tmp"
    # Instantane de la version actuelle, pris AVANT d'ecrire quoi que ce soit.
    # C'est lui qui deviendra le .bak et l'archive horodatee -- mais seulement
    # si la publication reussit. Deux conditions a tenir ensemble :
    #   - les sauvegardes doivent contenir ce qui etait sur le disque AVANT
    #     cette ecriture, donc on ne peut pas les prendre apres os.replace
    #     (a ce moment-la `path` porte deja le nouveau contenu) ;
    #   - elles ne doivent pas exister si os.replace echoue, donc on ne peut
    #     pas les poser avant.
    # D'ou l'instantane intermediaire : capture tot, promu tard.
    prev_path = path + ".prev.tmp"
    instantane = None
    try:
        if os.path.exists(path):
            try:
                shutil.copy2(path, prev_path)
                instantane = prev_path
            except OSError as exc:
                # Best effort : ne pas pouvoir sauvegarder ne doit pas
                # empecher d'enregistrer les nouvelles donnees.
                print(f"[warn] instantane de {path} impossible : {exc}",
                      file=sys.stderr)

        with open(tmp_path, "w", encoding="utf-8", newline="") as fh:
            # csv.writer met d'office entre guillemets toute valeur contenant
            # le separateur. Avec ";".join(cells), un ';' dans une valeur
            # produisait 7 champs au lieu de 6 et rendait le fichier illisible
            # pour de bon : ParserError au demarrage suivant, sans retour
            # possible. lineterminator est impose, sans quoi csv.writer
            # ecrirait des CRLF et changerait les fins de ligne du fichier
            # entier (le CSV reel est en LF).
            graveur = csv.writer(fh, delimiter=";", lineterminator="\n")
            graveur.writerow(RELEVES_HEADER)
            for row in rows_sorted:
                graveur.writerow([row.get(col, "") for col in RELEVES_HEADER])
            # NTFS journalise le RENOMMAGE, pas les donnees : sans ces deux
            # lignes, une coupure de courant juste apres peut publier un CSV
            # de 0 octet, le renommage ayant ete enregistre mais pas son
            # contenu. flush() vide le tampon de Python, fsync() force le
            # disque a ecrire pour de bon.
            fh.flush()
            os.fsync(fh.fileno())

        # Publication atomique. Si elle echoue (CSV ouvert dans Excel, verrou
        # de partage Windows, disque plein), on ressort par le finally :
        # aucune sauvegarde n'aura ete consommee, aucun temporaire ne restera,
        # et le CSV existant sera intact. Quinze tentatives ratees purgeaient
        # auparavant tout l'historique fin, en le remplacant par quinze copies
        # identiques du fichier courant.
        os.replace(tmp_path, path)

        # A partir d'ici seulement, l'ancienne version est promue.
        if instantane is not None:
            archiver_sauvegarde(path, source=instantane)
            try:
                os.replace(instantane, path + ".bak")
                instantane = None   # devenu le .bak : plus rien a nettoyer
            except OSError as exc:
                print(f"[warn] sauvegarde {path}.bak impossible : {exc}",
                      file=sys.stderr)
    finally:
        for reste in (tmp_path, prev_path):
            if os.path.exists(reste):
                try:
                    os.remove(reste)
                except OSError:
                    pass  # un fichier verrouille sera repris au prochain passage


# Rotation des sauvegardes, sur le modele de l'application recharges-ve :
# des copies rapprochees pour rattraper une fausse manipulation immediate,
# et une par jour pour remonter plus loin sans garder des milliers de
# fichiers. Le .bak reste a cote du CSV, c'est le filet le plus visible.
MAX_SAUVEGARDES = 15          # copies horodatees les plus recentes
MAX_SAUVEGARDES_JOUR = 30     # une par journee


def dossier_sauvegardes(path: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(path)), "backups")


def archiver_sauvegarde(path: str, source: str | None = None) -> str | None:
    """
    Copie le CSV actuel dans backups/ avant qu'il ne soit remplace, et fait
    le menage. Deux familles de fichiers :

    - `<nom>_<AAAAMMJJ_HHMMSS>.csv` : les MAX_SAUVEGARDES plus recentes ;
    - `<nom>_jour_<AAAAMMJJ>.csv`   : la premiere de chaque journee, gardee
      MAX_SAUVEGARDES_JOUR jours. Elle echappe a la rotation ci-dessus.

    Sans elle, deux enregistrements successifs suffisaient a perdre la seule
    version d'avant : le .bak etait ecrase par le second.

    `path` sert a NOMMER les copies et a situer le dossier backups ; `source`
    est le fichier dont le CONTENU est archive. Les deux different au moment
    ou write_releves_raw archive : `path` porte deja la nouvelle version,
    l'instantane de l'ancienne est ailleurs. Par defaut, source = path.

    Retourne le chemin de la copie horodatee, ou None en cas d'echec (la
    sauvegarde ne doit jamais empecher l'enregistrement).
    """
    from datetime import datetime

    try:
        dossier = dossier_sauvegardes(path)
        os.makedirs(dossier, exist_ok=True)
        base = os.path.splitext(os.path.basename(path))[0]
        maintenant = datetime.now()

        # Deux enregistrements dans la meme seconde donneraient le meme nom :
        # la seconde copie ecraserait la premiere au lieu de s'ajouter.
        horodatage = f"{maintenant:%Y%m%d_%H%M%S}"
        copie = os.path.join(dossier, f"{base}_{horodatage}.csv")
        suffixe = 1
        while os.path.exists(copie):
            copie = os.path.join(dossier, f"{base}_{horodatage}_{suffixe}.csv")
            suffixe += 1
        a_archiver = source or path
        shutil.copy2(a_archiver, copie)

        # Une sauvegarde par journee, posee seulement si elle n'existe pas.
        du_jour = os.path.join(dossier, f"{base}_jour_{maintenant:%Y%m%d}.csv")
        if not os.path.exists(du_jour):
            shutil.copy2(a_archiver, du_jour)

        _faire_le_menage(dossier, f"{base}_2", MAX_SAUVEGARDES)
        _faire_le_menage(dossier, f"{base}_jour_", MAX_SAUVEGARDES_JOUR)
        return copie
    except OSError as exc:
        print(f"[warn] archivage de {path} impossible : {exc}", file=sys.stderr)
        return None


def _faire_le_menage(dossier: str, prefixe: str, combien: int) -> None:
    """Ne garde que les `combien` fichiers les plus recents du prefixe.

    Tri sur la date de modification et non sur le nom : `copy2` preserve la
    date du contenu, alors qu'un tri alphabetique melangerait les deux
    familles de noms.
    """
    fichiers = [
        os.path.join(dossier, n) for n in os.listdir(dossier)
        if n.startswith(prefixe) and n.endswith(".csv")
    ]
    fichiers.sort(key=os.path.getmtime, reverse=True)
    for vieux in fichiers[combien:]:
        try:
            os.remove(vieux)
        except OSError:
            pass  # un fichier verrouille sera repris au prochain passage
