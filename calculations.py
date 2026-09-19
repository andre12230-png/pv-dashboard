"""
Calculs energetiques et financiers a partir des series Enphase et Enedis.

Modele :
  - Production       : Enphase (kWh)
  - Injection        : Enedis  (kWh) -> reseau
  - Soutirage        : Enedis  (kWh) -> achete au reseau
  - Autoconsommation : Production - Injection  (>= 0)
  - Consommation     : Autoconsommation + Soutirage

Tarifs :
  - Vente OA surplus : prix unique * injection
  - Prime autoconso : montant_par_kwc * Pcrete reparti sur 5 ans
  - Achat reseau    : Bleu Base par tranches historiques jusqu'au 31/12/2025,
                      puis Octopus HP/HC depuis le 01/01/2026.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

import pandas as pd

# ----------------------------------------------------------------------
# Series unifiees
# ----------------------------------------------------------------------

def merge_series(production: pd.DataFrame, reseau: pd.DataFrame) -> pd.DataFrame:
    """Joint production (Enphase) et reseau (Enedis) sur un index commun."""
    if production.empty and reseau.empty:
        return pd.DataFrame(
            columns=["production_kwh", "injection_kwh", "soutirage_kwh"]
        )

    # On agrege chaque source au jour pour eviter les desalignements de pas
    prod_d = production.resample("D").sum(min_count=1)
    res_d = reseau.resample("D").sum(min_count=1)
    df = prod_d.join(res_d, how="outer").fillna(0.0)

    for col in ("production_kwh", "injection_kwh", "soutirage_kwh"):
        if col not in df.columns:
            df[col] = 0.0

    df["autoconsommation_kwh"] = (df["production_kwh"] - df["injection_kwh"]).clip(lower=0)
    df["consommation_kwh"] = df["autoconsommation_kwh"] + df["soutirage_kwh"]
    return df


def jours_en_attente(df_daily: pd.DataFrame,
                     aujourd_hui: date | None = None) -> pd.DatetimeIndex:
    """Les journees de fin de serie qui ne sont pas encore completes.

    Deux raisons, signalees le 19/09/2026 par le meme utilisateur :

    - **le jour en cours n'est pas fini.** « On ne connait la production du
      jour que des l'instant ou il n'y a plus du tout de soleil. » Meme
      saisie, elle est partielle : on borne donc a la veille, quel que soit
      le contenu de la ligne ;
    - **Enedis publie avec un jour de retard.** L'onduleur donne la
      production du jour meme, la consommation et l'injection arrivent le
      lendemain. Une journee qui n'a AUCUN releve reseau n'est pas une
      journee a trou : la compter ferait 0 kWh au reseau, donc 100 %
      d'autoproduction et une facture amputee d'un jour.

    On ne regarde que la FIN de la serie : un jour sans releve suivi de jours
    releves est un vrai trou, qui reste signale et comble par les factures.
    Le CSV n'est jamais touche -- la journee revient d'elle-meme au prochain
    import.
    """
    vide = pd.DatetimeIndex([])
    if df_daily.empty:
        return vide

    limite = pd.Timestamp(aujourd_hui or date.today())
    # Le jour en cours, et tout ce qui le suit (une date saisie de travers).
    attente = (df_daily.index >= limite)

    colonnes = ("conso_absente", "releve_incomplet")
    if all(c in df_daily.columns for c in colonnes):
        # Ni consommation ni injection : rien du reseau pour cette journee.
        attente = attente | ((df_daily["conso_absente"] > 0)
                             & (df_daily["releve_incomplet"] > 0)).values

    n = 0
    for valeur in attente[::-1]:
        if not valeur:
            break
        n += 1
    return df_daily.index[len(df_daily) - n:] if n else vide


def jours_injection_estimee(df: pd.DataFrame) -> pd.Series:
    """Les journees dont l'injection est reellement estimee.

    C'est la meme condition que dans estime_injection_manquante : un releve
    manquant ET une production connue. Une journee a production nulle n'a rien
    a estimer -- l'annoncer comme estimee gonfle le compte pour rien. Un
    utilisateur a recompte a la main et trouve 23 jours la ou l'application en
    annoncait 27 (19/09/2026).
    """
    if df.empty or "releve_incomplet" not in df.columns:
        return pd.Series(False, index=df.index)
    estimes = df["releve_incomplet"].fillna(0) > 0
    if "production_kwh" in df.columns:
        estimes = estimes & (df["production_kwh"].fillna(0) > 0)
    return estimes


def estime_injection_manquante(df_daily: pd.DataFrame) -> pd.DataFrame:
    """
    Estime l'injection des jours 'releve_incomplet' (production connue mais
    injection jamais relevee : avant-contrat OA du 29/04 au 27/06/2022,
    pannes Linky), puis recale autoconso et consommation.

    Methode : ratio injection/production du meme mois calendaire, observe
    sur les jours complets de toutes les annees (fallback : ratio global).
    Le CSV n'est pas touche, l'estimation est refaite a chaque chargement ;
    ces jours restent marques releve_incomplet pour etre signales.
    """
    if df_daily.empty or "releve_incomplet" not in df_daily.columns:
        return df_daily
    out = df_daily.copy()
    manquants = (out["releve_incomplet"] > 0) & (out["production_kwh"] > 0)
    complets = (out["releve_incomplet"] == 0) & (out["production_kwh"] > 0)
    if not manquants.any() or not complets.any():
        return out

    ref = out[complets]
    ratio_global = ref["injection_kwh"].sum() / ref["production_kwh"].sum()
    ratios = (
        ref["injection_kwh"].groupby(ref.index.month).sum()
        / ref["production_kwh"].groupby(ref.index.month).sum()
    )
    ratio_jour = pd.Series(
        [float(ratios.get(m, ratio_global)) for m in out.index.month],
        index=out.index,
    ).clip(0.0, 1.0)

    inj_est = out.loc[manquants, "production_kwh"] * ratio_jour[manquants]
    out.loc[manquants, "injection_kwh"] = inj_est
    out.loc[manquants, "autoconsommation_kwh"] = (
        out.loc[manquants, "production_kwh"] - inj_est
    ).clip(lower=0)
    out.loc[manquants, "consommation_kwh"] = (
        out.loc[manquants, "autoconsommation_kwh"]
        + out.loc[manquants, "soutirage_kwh"]
    )
    return out


def recale_injection_sur_facture(df_daily: pd.DataFrame,
                                 tranches: Iterable[dict] | None) -> pd.DataFrame:
    """
    Recale l'injection sur les totaux des factures EDF OA.

    A quoi ca sert : les releves quotidiens d'injection viennent d'Enedis,
    mais EDF OA paie sur l'index du compteur de production, releve une seule
    fois par an. Les deux ne tombent pas exactement pareil -- heure du releve
    d'index, jours de panne jamais mesures -- avec un ecart de -0,8 % a
    +0,8 % sur les quatre premieres annees OA. La facture fait foi : c'est
    ce qui a reellement ete paye.

    Methode : tous les jours de la tranche sont multiplies par un meme
    facteur, choisi pour que le total tombe sur le montant facture. Un jour
    a 20 kWh est donc corrige dix fois plus qu'un jour a 2 kWh, ce qui est
    le bon sens : l'ecart d'un releve suit la quantite injectee, il ne se
    partage pas a parts egales entre un jour d'ete et un jour d'hiver. Un
    jour sans injection (tout autoconsomme) reste a zero.

    Garde-fou : l'injection d'un jour ne peut jamais depasser sa production,
    on ne vend pas ce qu'on n'a pas produit. Les jours qui butent sur ce
    plafond sont figes, et ce qu'ils ne peuvent pas absorber est redistribue
    sur les autres -- d'ou la boucle. Si le total facture reste hors
    d'atteinte, l'app garde la valeur physiquement possible.

    **Le total de chaque tranche devient exact ; le detail quotidien reste
    approche.** L'autoconso, qui est la production moins l'injection, suit
    automatiquement. Les jours concernes portent injection_recalee = 1.
    Le CSV n'est pas modifie : le calcul est refait a chaque chargement.
    """
    if df_daily.empty or not tranches or "injection_kwh" not in df_daily.columns:
        return df_daily
    out = df_daily.copy()
    if "injection_recalee" not in out.columns:
        out["injection_recalee"] = 0.0

    for tranche in tranches:
        debut = pd.Timestamp(tranche["debut"])
        fin = pd.Timestamp(tranche["fin"])
        total = float(tranche["total_kwh"])
        dans = (out.index >= debut) & (out.index <= fin)
        if not dans.any():
            continue

        valeurs = out.loc[dans, "injection_kwh"].astype(float)
        plafond = out.loc[dans, "production_kwh"].astype(float)
        for _ in range(10):
            reste = total - float(valeurs.sum())
            if abs(reste) < 1e-6:
                break
            # Seuls les jours qui ont encore de la marge peuvent absorber
            # l'ecart : ceux deja au plafond de leur production sont figes,
            # comme ceux a zero quand il faut retrancher.
            ajustables = (valeurs < plafond) if reste > 0 else (valeurs > 0)
            somme = float(valeurs[ajustables].sum())
            if somme <= 0:
                break
            valeurs.loc[ajustables] = (
                valeurs.loc[ajustables] * (1.0 + reste / somme))
            valeurs = valeurs.clip(lower=0.0, upper=plafond)

        out.loc[dans, "injection_kwh"] = valeurs
        out.loc[dans, "injection_recalee"] = 1.0

    # L'autoconso est le complement de l'injection : elle suit, et la
    # consommation avec elle.
    out["autoconsommation_kwh"] = (
        out["production_kwh"] - out["injection_kwh"]).clip(lower=0)
    out["consommation_kwh"] = out["autoconsommation_kwh"] + out["soutirage_kwh"]
    return out


def repartit_conso_facturee(df_daily: pd.DataFrame,
                            periodes: Iterable[dict] | None) -> pd.DataFrame:
    """
    Comble les jours sans releve de consommation reseau a partir des totaux
    lus sur les factures EDF (config.yaml, sources.conso_reseau_facturee).

    Sans cela ces jours comptent 0 kWh soutire : la facture est sous-evaluee
    et le taux d'autoproduction monte a 100 %. Le detail quotidien n'existe
    plus chez Enedis (36 mois glissants), mais la facture donne le total
    exact de la periode via les index du compteur.

    Methode : chaque total est reparti a parts egales sur les jours de sa
    periode qui n'ont pas de releve. Le total de la periode est donc exact ;
    seul le decoupage jour par jour est lisse. Si des jours de la periode
    sont deja releves, leur consommation est deduite du total avant partage.

    Les jours ainsi combles gardent conso_absente = 1 pour rester signales.
    Le CSV n'est pas modifie : le calcul est refait a chaque chargement.
    """
    if df_daily.empty or not periodes or "conso_absente" not in df_daily.columns:
        return df_daily
    out = df_daily.copy()

    for periode in periodes:
        debut = pd.Timestamp(periode["debut"])
        fin = pd.Timestamp(periode["fin"])
        total = float(periode["total_kwh"])
        dans_periode = (out.index >= debut) & (out.index <= fin)
        a_combler = dans_periode & (out["conso_absente"] > 0)
        nb = int(a_combler.sum())
        if nb == 0:
            continue
        # Jours de la periode deja releves : leur conso est deja comptee,
        # on ne partage que ce qui reste du total facture.
        deja_releve = float(out.loc[dans_periode & ~a_combler, "soutirage_kwh"].sum())
        reste = max(total - deja_releve, 0.0)
        out.loc[a_combler, "soutirage_kwh"] = reste / nb

    # La consommation totale depend du soutirage : on la recalcule.
    out["consommation_kwh"] = out["autoconsommation_kwh"] + out["soutirage_kwh"]
    return out


# Une consommation saisie arrondie a l'entier a perdu sa partie decimale.
# Cette perte suit une loi uniforme sur [0, 1[ : elle vaut donc 0,5 kWh en
# moyenne. Mesure sur janvier 2026, la seule periode dont on connaisse a la
# fois les valeurs arrondies et les index Enedis exacts : +0,53 kWh/jour.
TRONCATURE_MOYENNE_KWH = 0.5


def marque_conso_douteuse(df_daily: pd.DataFrame,
                          periodes: Iterable[dict] | None) -> pd.DataFrame:
    """
    Declare non fiable la consommation de certaines journees.

    Cas reel : la panne Linky de fevrier 2024, dont les valeurs du CSV ont
    ete obtenues par interpolation (progression parfaitement lineaire de
    +0,69 kWh/jour, et 3x superieures aux jours voisins). Mieux vaut les
    reconstituer a partir de la facture que les garder telles quelles.

    Ces jours portent `conso_douteuse = 1` (a reconstituer par le recalage)
    et `conso_absente = 1` (pour que les vues les signalent comme estimes).
    Les deux marqueurs sont distincts a dessein : un jour simplement
    `conso_absente` a deja recu sa valeur d'une autre source et ne doit pas
    etre retouche, alors qu'un jour douteux attend encore la sienne.
    """
    if df_daily.empty or not periodes:
        return df_daily
    out = df_daily.copy()
    for colonne in ("conso_absente", "conso_douteuse"):
        if colonne not in out.columns:
            out[colonne] = 0.0
    for periode in periodes:
        debut = pd.Timestamp(periode["debut"])
        fin = pd.Timestamp(periode["fin"])
        vise = (out.index >= debut) & (out.index <= fin)
        out.loc[vise, "conso_absente"] = 1.0
        out.loc[vise, "conso_douteuse"] = 1.0
    return out


def recale_sur_facture(df_daily: pd.DataFrame,
                       tranches: Iterable[dict] | None) -> pd.DataFrame:
    """
    Recale les consommations deja relevees sur le total facture par EDF.

    A quoi ca sert : de 2023 a 2025, les consommations du CSV sont arrondies
    a l'entier (la partie decimale a ete perdue a la saisie), et la periode
    de la panne Linky de fevrier 2024 a ete estimee. Les factures EDF, elles,
    portent les index reels du compteur : leur total est exact.

    Methode : l'ecart entre le total facture et la somme des jours releves
    est reparti selon son sens, parce que les deux cas n'ont pas la meme
    cause.

    - **Ecart positif** (le CSV manque des kWh) : c'est la decimale perdue a
      la saisie, entre 0 et 1 kWh par jour quelle que soit la valeur ->
      repartition **a parts egales**.
    - **Ecart negatif** (le CSV en annonce trop) : ce sont des jours estimes
      qui surevaluent, et l'exces est porte par les grosses valeurs, pas par
      les petites -> repartition **au prorata**. Une correction uniforme
      ecrasait sinon a zero des jours a 1 kWh (fin mars 2024) tout en
      laissant intacts des jours interpoles a 47 kWh.

    **Le total de chaque tranche devient exact ; le detail quotidien reste
    approche** (a moins d'environ 1 kWh pres). Les jours concernes portent
    conso_recalee = 1 pour que les vues puissent le dire.

    Une correction n'est jamais appliquee au point de rendre un jour negatif.
    Le CSV n'est pas modifie : le calcul est refait a chaque chargement.
    """
    if df_daily.empty or not tranches:
        return df_daily
    out = df_daily.copy()
    if "conso_recalee" not in out.columns:
        out["conso_recalee"] = 0.0

    for tranche in tranches:
        debut = pd.Timestamp(tranche["debut"])
        fin = pd.Timestamp(tranche["fin"])
        total = float(tranche["total_kwh"])
        periode = (out.index >= debut) & (out.index <= fin)
        # Jours a reconstituer : valeur du CSV declaree non fiable.
        a_reconstituer = (periode & (out["conso_douteuse"] > 0)
                          if "conso_douteuse" in out.columns
                          else periode & False)
        # Jours deja servis par une autre source : on n'y touche pas.
        deja_servis = (periode & (out["conso_absente"] > 0) & ~a_reconstituer
                       if "conso_absente" in out.columns
                       else periode & False)
        dans = periode & ~a_reconstituer & ~deja_servis
        nb = int(dans.sum())
        if nb == 0:
            continue

        if a_reconstituer.any():
            # Les jours releves sont d'abord corriges de leur troncature,
            # puis les jours a reconstituer recoivent le SOLDE de la facture.
            # C'est la seule facon de leur donner une valeur : le CSV ne
            # contient qu'une interpolation. L'incertitude porte sur la
            # troncature moyenne, pas sur le total, qui reste exact.
            releves = out.loc[dans, "soutirage_kwh"].astype(float) \
                + TRONCATURE_MOYENNE_KWH
            out.loc[dans, "soutirage_kwh"] = releves
            deja = float(out.loc[deja_servis, "soutirage_kwh"].sum())
            solde = max(total - float(releves.sum()) - deja, 0.0)
            out.loc[a_reconstituer, "soutirage_kwh"] = (
                solde / int(a_reconstituer.sum()))
            out.loc[periode & ~deja_servis, "conso_recalee"] = 1.0
            continue

        valeurs = out.loc[dans, "soutirage_kwh"].astype(float)
        for _ in range(10):
            reste = total - float(valeurs.sum())
            if abs(reste) < 1e-6:
                break
            if reste > 0:
                # Decimales perdues : meme quantite pour chaque jour.
                valeurs = valeurs + reste / len(valeurs)
                continue
            # Surevaluation : au prorata, donc proportionnelle a la valeur.
            # Un jour a 1 kWh perd 1 % la ou un jour a 50 kWh perd 1 %, au
            # lieu de perdre tous les deux le meme nombre de kWh.
            somme_actuelle = float(valeurs.sum())
            if somme_actuelle <= 0:
                break
            valeurs = (valeurs * (total / somme_actuelle)).clip(lower=0.0)
        out.loc[dans, "soutirage_kwh"] = valeurs
        out.loc[dans, "conso_recalee"] = 1.0

    out["consommation_kwh"] = out["autoconsommation_kwh"] + out["soutirage_kwh"]
    return out


def aggregate(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Aggrege une serie journaliere a la frequence demandee ('MS', 'YS', etc.)."""
    if df.empty:
        return df
    cols = [c for c in df.columns if c.endswith("_kwh") or c.endswith("_eur")]
    return df[cols].resample(freq).sum(min_count=1)


# ----------------------------------------------------------------------
# Annees OA (28/06 -> 27/06)
# ----------------------------------------------------------------------

def _anniversaire(annee: int, mois: int, jour: int) -> date:
    """Le meme jour/mois dans une autre annee.

    Ramene au dernier jour du mois quand la date n'existe pas : un contrat
    signe un 29 fevrier n'a pas d'anniversaire les annees non bissextiles,
    et `date(2025, 2, 29)` leverait une ValueError.
    """
    dernier_du_mois = calendar.monthrange(annee, mois)[1]
    return date(annee, mois, min(jour, dernier_du_mois))


def oa_year_bounds(start_date: date, year_index: int) -> tuple[date, date]:
    """Retourne (debut, fin) inclusifs de la N-ieme annee OA (1-indexe)."""
    if year_index < 1:
        raise ValueError("year_index doit etre >= 1")
    # On repart toujours du jour d'origine, jamais du debut calcule : sinon
    # un 29 fevrier ramene au 28 le resterait pour toutes les annees suivantes.
    debut = _anniversaire(
        start_date.year + (year_index - 1), start_date.month, start_date.day)
    fin = _anniversaire(
        start_date.year + year_index, start_date.month, start_date.day
    ) - timedelta(days=1)
    return debut, fin


def assign_oa_year(idx: pd.DatetimeIndex, start_date: date) -> pd.Series:
    """Pour chaque date, donne l'index d'annee OA (1, 2, 3, ...)."""
    anchor = pd.Timestamp(start_date)

    def _year_of(ts: pd.Timestamp) -> int:
        if ts < anchor:
            return 0
        years = ts.year - anchor.year
        # _anniversaire, et non pd.Timestamp(...) directement : un contrat
        # demarre un 29 fevrier n'a pas d'anniversaire chaque annee.
        anniversary = pd.Timestamp(
            _anniversaire(ts.year, anchor.month, anchor.day))
        if ts < anniversary:
            years -= 1
        return years + 1

    return pd.Series([_year_of(ts) for ts in idx], index=idx, name="annee_oa")


# ----------------------------------------------------------------------
# OA - revenu vente + prime
# ----------------------------------------------------------------------

@dataclass
class OAConfig:
    type: str
    prix_kwh: float
    prime_par_kwc: float
    prime_duree: int
    duree_contrat: int


def revenu_oa(df_daily: pd.DataFrame, oa: OAConfig,
              debut_contrat: date | None = None) -> pd.DataFrame:
    """Ajoute colonnes revenu_vente_eur (et prime calculee par an separement).

    Si debut_contrat est fourni, le revenu est nul avant cette date :
    l'injection d'avant-contrat n'etait pas payee par EDF OA."""
    out = df_daily.copy()
    if oa.type == "surplus":
        out["revenu_vente_eur"] = out["injection_kwh"] * oa.prix_kwh
    elif oa.type == "totale":
        out["revenu_vente_eur"] = out["production_kwh"] * oa.prix_kwh
    else:
        out["revenu_vente_eur"] = 0.0
    if debut_contrat is not None and not out.empty:
        out.loc[out.index < pd.Timestamp(debut_contrat), "revenu_vente_eur"] = 0.0
    return out


def prime_annuelle(p_crete_kwc: float, oa: OAConfig) -> float:
    """Montant de la prime a l'autoconsommation versee chaque annee (5 ans)."""
    total = oa.prime_par_kwc * p_crete_kwc
    if oa.prime_duree <= 0:
        return 0.0
    return total / oa.prime_duree


def prime_est_versee(start_oa: date, n_oa: int, oa: OAConfig,
                     aujourdhui: date | None = None) -> bool:
    """La prime de l'annee OA n est-elle deja encaissee ?

    EDF OA facture la prime a la date anniversaire, donc APRES la fin de
    l'annee OA concernee : une annee encore en cours ne compte pas, et au
    dela de oa.prime_duree il n'y a plus de prime du tout.

    Regle commune a la Synthese financiere et a la vue Annees OA : les deux
    la calculaient separement et se contredisaient d'un versement.
    """
    if not 1 <= n_oa <= oa.prime_duree:
        return False
    if aujourdhui is None:
        aujourdhui = date.today()
    return oa_year_bounds(start_oa, n_oa)[1] < aujourdhui


# ----------------------------------------------------------------------
# Tarifs reseau : Bleu Base (historique) puis Octopus HP/HC
# ----------------------------------------------------------------------

@dataclass
class BleuBaseConfig:
    abonnement_tranches: list[dict]  # {debut, fin, montant}
    tranches: list[dict]             # {debut, fin, prix}


@dataclass
class OctopusConfig:
    """Grille Octopus HP/HC, decoupee en periodes de prix.

    Octopus revalorise ses prix en cours de contrat (1re fois au 01/08/2026) :
    chaque periode garde donc ses propres montants, comme les tranches du
    Tarif Bleu. Une periode est un dict {debut, fin, abonnement, prix_hp,
    prix_hc} ; "fin" vide signifie "periode en cours".
    """
    periodes: list[dict]
    plages_hc: list[tuple[time, time]]
    # Part des kWh autoconsommes qui seraient factures en HC s'ils etaient
    # achetes au reseau. L'autoconso est diurne (production solaire) : la
    # plage HC de nuit ne la concerne jamais, seule celle de l'apres-midi
    # compte (~20 % de la production d'une journee).
    part_hc_autoconso: float = 0.20

    @classmethod
    def periode_unique(cls, abonnement_mensuel: float, prix_hp: float,
                       prix_hc: float, plages_hc: list[tuple[time, time]],
                       part_hc_autoconso: float = 0.20) -> "OctopusConfig":
        """Grille a prix constants, sans changement de tarif (tests, cas simple)."""
        return cls(
            periodes=[{"debut": "1970-01-01", "fin": None,
                       "abonnement": abonnement_mensuel,
                       "prix_hp": prix_hp, "prix_hc": prix_hc}],
            plages_hc=plages_hc,
            part_hc_autoconso=part_hc_autoconso,
        )

    def abonnement(self, jour: pd.Timestamp) -> float:
        """Abonnement mensuel TTC applicable a une date."""
        return _valeur_periode(jour, self.periodes, "abonnement")

    def prix_hp(self, jour: pd.Timestamp) -> float:
        """Prix du kWh en heures pleines applicable a une date."""
        return _valeur_periode(jour, self.periodes, "prix_hp")

    def prix_hc(self, jour: pd.Timestamp) -> float:
        """Prix du kWh en heures creuses applicable a une date."""
        return _valeur_periode(jour, self.periodes, "prix_hc")


def _parse_plage(plage: str) -> tuple[time, time]:
    a, b = plage.split("-")
    return (
        datetime.strptime(a.strip(), "%H:%M").time(),
        datetime.strptime(b.strip(), "%H:%M").time(),
    )


def parse_plages_hc(plages: Iterable[str]) -> list[tuple[time, time]]:
    return [_parse_plage(p) for p in plages]


def _is_in_plage(t: time, plage: tuple[time, time]) -> bool:
    start, end = plage
    if start <= end:
        return start <= t < end
    # Plage qui traverse minuit
    return t >= start or t < end


def is_hc(ts: pd.Timestamp, plages: list[tuple[time, time]]) -> bool:
    t = ts.time()
    return any(_is_in_plage(t, p) for p in plages)


def _prix_bleu_for_date(d: pd.Timestamp, tranches: list[dict]) -> float:
    # Aucune tranche declaree : l'utilisateur n'a jamais eu ce contrat-la
    # (section bleu_base absente de config.yaml). Prix nul plutot qu'une
    # erreur : les jours concernes n'ont simplement pas de tarif Bleu.
    if not tranches:
        return 0.0
    for tranche in tranches:
        debut = pd.Timestamp(tranche["debut"])
        fin = pd.Timestamp(tranche["fin"])
        if debut <= d <= fin:
            return float(tranche["prix"])
    # Hors plage definie : on prend le plus proche
    if d < pd.Timestamp(tranches[0]["debut"]):
        return float(tranches[0]["prix"])
    return float(tranches[-1]["prix"])


def _prix_bleu_series(idx: pd.DatetimeIndex,
                      tranches: list[dict]) -> pd.Series:
    """Version vectorisee de _prix_bleu_for_date sur un index complet."""
    if not tranches:
        return pd.Series(0.0, index=idx, dtype=float)
    prix = pd.Series(float("nan"), index=idx, dtype=float)
    for tranche in tranches:
        debut = pd.Timestamp(tranche["debut"])
        fin = pd.Timestamp(tranche["fin"])
        mask = (idx >= debut) & (idx <= fin)
        prix[mask] = float(tranche["prix"])
    # Fallback : dates hors tranches -> tranche la plus proche
    avant = idx < pd.Timestamp(tranches[0]["debut"])
    apres = idx > pd.Timestamp(tranches[-1]["fin"])
    prix[avant] = float(tranches[0]["prix"])
    prix[apres] = float(tranches[-1]["prix"])
    return prix


# Date a laquelle on change de facon de facturer : prix unique (Tarif Bleu
# Base) avant, heures pleines / heures creuses apres. Chez l'auteur c'est le
# passage chez Octopus, le 01/01/2026 ; ailleurs ce sera une autre date, ou
# la mise en service si le contrat a toujours ete en HP/HC.
#
# Cette date etait ecrite en dur : qui etait reste en prix unique en 2026 se
# voyait facturer en HP/HC sans pouvoir rien y faire. Elle se regle
# desormais dans config.yaml (tarifs_reseau.bascule_hphc) ; la valeur
# ci-dessous n'est plus qu'un defaut, applique tant que rien n'est declare.
CUTOFF_OCTOPUS = pd.Timestamp("2026-01-01")


def definir_bascule_hphc(valeur) -> None:
    """Regle la date de passage en heures pleines / heures creuses.

    Appelee une fois au demarrage, a partir de config.yaml. Une valeur vide
    laisse la date par defaut.
    """
    global CUTOFF_OCTOPUS
    if valeur in (None, ""):
        return
    try:
        CUTOFF_OCTOPUS = pd.Timestamp(valeur)
    except (ValueError, TypeError) as exc:
        raise RuntimeError(
            f"config.yaml : tarifs_reseau.bascule_hphc ne ressemble pas a "
            f"une date ('{valeur}'). Attendu : AAAA-MM-JJ, "
            "par exemple 2026-01-01."
        ) from exc

# Periode tarifaire encore en cours (Octopus ou grille EDF de reference) :
# "fin" vide dans config.yaml. On la borne tres loin dans le futur pour
# pouvoir comparer des dates sans cas particulier.
_FIN_OUVERTE = pd.Timestamp("2100-01-01")


def _fin_periode(periode: dict) -> pd.Timestamp:
    fin = periode.get("fin")
    if fin in (None, ""):
        return _FIN_OUVERTE
    return pd.Timestamp(fin)


def _valeur_periode(jour: pd.Timestamp, periodes: list[dict], cle: str) -> float:
    """Valeur d'une grille tarifaire (abonnement, prix_hp...) a une date donnee.

    Les bornes "debut" et "fin" designent des journees entieres : on compare
    donc a la date, pas a l'heure (une charge de 23h56 reste dans sa journee).
    """
    d = pd.Timestamp(jour).normalize()
    for p in periodes:
        if pd.Timestamp(p["debut"]) <= d <= _fin_periode(p):
            return float(p[cle])
    # Hors des periodes decrites : on prend la plus proche.
    if d < pd.Timestamp(periodes[0]["debut"]):
        return float(periodes[0][cle])
    return float(periodes[-1][cle])


def periodes_octopus(cfg_octopus: dict) -> list[dict]:
    """Periodes de prix Octopus lues dans config.yaml, triees par date.

    Accepte aussi l'ancienne forme du fichier (un seul jeu de prix dans
    abonnement_mensuel_eur / prix_hp_eur_kwh / prix_hc_eur_kwh) : un
    config.yaml d'avant le decoupage en periodes reste donc valable, ses prix
    s'appliquant a toute la periode Octopus.
    """
    periodes = cfg_octopus.get("periodes")
    if not periodes:
        return [{
            "debut": CUTOFF_OCTOPUS.date().isoformat(),
            "fin": None,
            "abonnement": float(cfg_octopus["abonnement_mensuel_eur"]),
            "prix_hp": float(cfg_octopus["prix_hp_eur_kwh"]),
            "prix_hc": float(cfg_octopus["prix_hc_eur_kwh"]),
        }]
    return sorted(periodes, key=lambda p: str(p["debut"]))


def periodes_edf(cfg_comparaison: dict) -> list[dict]:
    """Periodes de la grille EDF de reference (vue Octopus vs EDF).

    Meme principe que periodes_octopus : EDF revise ses tarifs reglementes en
    cours d'annee (1er fevrier, 1er aout), il faut donc comparer chaque mois
    a la grille EDF qui etait reellement en vigueur ce mois-la.

    Accepte aussi l'ancienne forme (un seul jeu de valeurs dans
    abonnement_mensuel_eur / prix_kwh_eur / prix_hp_eur_kwh / prix_hc_eur_kwh).
    """
    periodes = cfg_comparaison.get("periodes")
    if not periodes:
        return [{
            "debut": CUTOFF_OCTOPUS.date().isoformat(),
            "fin": None,
            "abonnement": float(cfg_comparaison.get("abonnement_mensuel_eur", 19.56)),
            "prix_base": float(cfg_comparaison.get("prix_kwh_eur", 0.1927)),
            "prix_hp": float(cfg_comparaison.get("prix_hp_eur_kwh", 0.2065)),
            "prix_hc": float(cfg_comparaison.get("prix_hc_eur_kwh", 0.1579)),
        }]
    return sorted(periodes, key=lambda p: str(p["debut"]))


def _valeur_periode_series(idx: pd.DatetimeIndex, periodes: list[dict],
                           cle: str) -> pd.Series:
    """Version vectorisee de _valeur_periode sur un index complet."""
    jours = pd.DatetimeIndex(idx).normalize()
    val = pd.Series(float("nan"), index=idx, dtype=float)
    for p in periodes:
        mask = ((jours >= pd.Timestamp(p["debut"]))
                & (jours <= _fin_periode(p)))
        val[mask] = float(p[cle])
    avant = jours < pd.Timestamp(periodes[0]["debut"])
    apres = jours > _fin_periode(periodes[-1])
    val[avant] = float(periodes[0][cle])
    val[apres] = float(periodes[-1][cle])
    return val


def _ratio_hc_observe(df: pd.DataFrame, octopus: OctopusConfig) -> float:
    """
    Part de la consommation tombant en heures creuses, mesuree sur les jours
    dont le detail HC/HP est connu (a partir de 2026).

    Sert a estimer le cout des jours ou ce detail manque encore (Enedis le
    publie avec du retard). A defaut de jour detaille, on retombe sur la
    duree des plages HC rapportee a 24 h.
    """
    defaut = sum(_duree_plage_h(p) for p in octopus.plages_hc) / 24.0
    if "soutirage_hp_kwh" not in df.columns or "soutirage_hc_kwh" not in df.columns:
        return defaut
    apres = df[df.index >= CUTOFF_OCTOPUS]
    if apres.empty:
        return defaut
    hp = apres["soutirage_hp_kwh"].fillna(0.0)
    hc = apres["soutirage_hc_kwh"].fillna(0.0)
    sout = apres["soutirage_kwh"].fillna(0.0)
    detaille = (hp + hc) >= 0.9 * sout
    total = float((hp[detaille] + hc[detaille]).sum())
    if total <= 0:
        return defaut
    return float(hc[detaille].sum()) / total


def cout_reseau_journalier(
    df_daily: pd.DataFrame,
    soutirage_par_heure: pd.DataFrame | None,
    bleu: BleuBaseConfig,
    octopus: OctopusConfig,
) -> pd.DataFrame:
    """
    Calcule le cout d'achat reseau journalier en EUR.

    - Avant 2026 : prix unique Bleu Base * soutirage_kwh journalier
    - Depuis 2026 : si soutirage_par_heure dispo -> split HP/HC reel ;
                    sinon estimation via ratio HP/HC moyen.
    """
    out = df_daily.copy()
    out["cout_reseau_eur"] = 0.0
    if out.empty:
        return out

    # Avant cutoff : Bleu Base (vectorise via _prix_bleu_series)
    mask_avant = out.index < CUTOFF_OCTOPUS
    if mask_avant.any():
        prix_bleu = _prix_bleu_series(out.index, bleu.tranches)
        out.loc[mask_avant, "cout_reseau_eur"] = (
            out.loc[mask_avant, "soutirage_kwh"] * prix_bleu.loc[mask_avant]
        )

    # Apres cutoff : Octopus HP/HC
    mask_apres = out.index >= CUTOFF_OCTOPUS
    if mask_apres.any():
        has_daily_hphc = (
            "soutirage_hp_kwh" in out.columns
            and "soutirage_hc_kwh" in out.columns
        )
        # Prix moyen servant de repli les jours ou le detail HC/HP manque.
        # On prend le ratio HC REELLEMENT observe sur les jours detailles :
        # la duree des plages sur 24 h (33 %) supposerait une consommation
        # uniforme jour et nuit, ce qui est faux ici (recharge du vehicule la
        # nuit -> pres de 58 % en heures creuses) et surfacturait ces jours.
        ratio_hc_moyen = _ratio_hc_observe(out, octopus)
        # Prix du jour : ils changent au fil des periodes (revalorisation
        # Octopus du 01/08/2026), d'ou une serie de prix et non un nombre.
        prix_hp_jour = _valeur_periode_series(out.index, octopus.periodes, "prix_hp")
        prix_hc_jour = _valeur_periode_series(out.index, octopus.periodes, "prix_hc")
        prix_moyen = (
            prix_hc_jour * ratio_hc_moyen
            + prix_hp_jour * (1 - ratio_hc_moyen)
        )

        if has_daily_hphc:
            # Cas Linky / releve manuel : HP et HC deja repartis au jour.
            # Si HP+HC est nul (ou < 90% du soutirage) sur une journee,
            # on retombe sur l'estimation par ratio plages HC pour cette journee
            # afin de ne pas sous-facturer.
            hp = out["soutirage_hp_kwh"].fillna(0.0)
            hc = out["soutirage_hc_kwh"].fillna(0.0)
            sout = out["soutirage_kwh"].fillna(0.0)
            cout_hphc = hp * prix_hp_jour + hc * prix_hc_jour
            cout_ratio = sout * prix_moyen
            seuil = sout * 0.9  # HP+HC doit couvrir au moins 90% du soutirage
            utilise_hphc = (hp + hc) >= seuil
            cout_apres = cout_hphc.where(utilise_hphc, cout_ratio)
            out.loc[mask_apres, "cout_reseau_eur"] = cout_apres.loc[mask_apres]
        elif soutirage_par_heure is not None and not soutirage_par_heure.empty:
            hourly = soutirage_par_heure[soutirage_par_heure.index >= CUTOFF_OCTOPUS].copy()
            if not hourly.empty:
                hourly["is_hc"] = [is_hc(ts, octopus.plages_hc) for ts in hourly.index]
                # Prix heure par heure : HC ou HP, au tarif de la periode.
                prix_hp_h = _valeur_periode_series(
                    hourly.index, octopus.periodes, "prix_hp")
                prix_hc_h = _valeur_periode_series(
                    hourly.index, octopus.periodes, "prix_hc")
                hourly["prix"] = prix_hp_h.where(~hourly["is_hc"], prix_hc_h)
                hourly["cout"] = hourly["soutirage_kwh"] * hourly["prix"]
                cout_daily = hourly["cout"].resample("D").sum()
                # Vectorise : assignation alignee sur l'index commun
                inter = cout_daily.index.intersection(out.index)
                if len(inter) > 0:
                    out.loc[inter, "cout_reseau_eur"] = cout_daily.loc[inter].astype(float)
        else:
            # Estimation : prix moyen pondere par duree des plages HC.
            out.loc[mask_apres, "cout_reseau_eur"] = (
                out.loc[mask_apres, "soutirage_kwh"] * prix_moyen[mask_apres]
            )

    # Abonnement fixe : la part journaliere est l'abonnement mensuel divise
    # par le nombre de jours du mois. Avant 2026 -> abonnement Bleu Base,
    # a partir de 2026 -> abonnement Octopus. Ajoute au cout reseau pour que
    # le bilan net reflete la facture reelle (consommation + abonnement).
    abo_mensuel = pd.Series(
        [abonnement_mensuel_eur(d, bleu, octopus) for d in out.index],
        index=out.index, dtype=float,
    )
    jours_mois = pd.Series(out.index.days_in_month, index=out.index, dtype=float)
    out["abonnement_eur"] = abo_mensuel / jours_mois
    out["cout_reseau_eur"] = out["cout_reseau_eur"] + out["abonnement_eur"]

    return out


def _duree_plage_h(plage: tuple[time, time]) -> float:
    start, end = plage
    s = start.hour + start.minute / 60.0
    e = end.hour + end.minute / 60.0
    if e >= s:
        return e - s
    return 24 - s + e


def economies_autoconsommation(
    df_daily: pd.DataFrame,
    bleu: BleuBaseConfig,
    octopus: OctopusConfig,
) -> pd.DataFrame:
    """
    Estimation de l'economie liee a l'autoconsommation : autoconso_kwh valorisee
    au prix d'achat reseau du moment.

    - Avant 2026 : prix Bleu Base de la date.
    - Depuis 2026 (Octopus) : l'autoconso remplace des achats en journee
      (heures solaires), donc surtout en HP. On pondere HP/HC par
      part_hc_autoconso (config), et non par la duree des plages sur 24 h
      qui inclurait a tort la plage HC de nuit.
    """
    out = df_daily.copy()
    if out.empty:
        out["economie_eur"] = 0.0
        return out

    # Serie de prix (et non un nombre) : les tarifs Octopus changent d'une
    # periode a l'autre (revalorisation du 01/08/2026).
    prix_moyen_octopus = (
        _valeur_periode_series(out.index, octopus.periodes, "prix_hc")
        * octopus.part_hc_autoconso
        + _valeur_periode_series(out.index, octopus.periodes, "prix_hp")
        * (1 - octopus.part_hc_autoconso)
    )

    # Vectorisation : prix Bleu pour avant cutoff, prix_moyen_octopus pour apres
    prix = _prix_bleu_series(out.index, bleu.tranches)
    prix = prix.where(out.index < CUTOFF_OCTOPUS, prix_moyen_octopus)
    out["economie_eur"] = out["autoconsommation_kwh"] * prix
    return out


# ----------------------------------------------------------------------
# Abonnements (cout fixe mensuel)
# ----------------------------------------------------------------------

def abonnement_mensuel_eur(jour: pd.Timestamp, bleu: BleuBaseConfig,
                           octopus: OctopusConfig) -> float:
    """Abonnement mensuel applicable a une date donnee.

    - A partir du 01/01/2026 : abonnement Octopus de la periode en cours
      (19,83 EUR jusqu'au 31/07/2026, 20,16 EUR depuis le 01/08/2026).
    - Avant : Tarif Bleu, recherche dans les tranches par date.
    """
    if jour >= CUTOFF_OCTOPUS:
        return octopus.abonnement(jour)
    if not bleu.abonnement_tranches:
        return 0.0
    for t in bleu.abonnement_tranches:
        if pd.Timestamp(t["debut"]) <= jour <= pd.Timestamp(t["fin"]):
            return float(t["montant"])
    # Hors plage definie : on prend la tranche la plus proche.
    if jour < pd.Timestamp(bleu.abonnement_tranches[0]["debut"]):
        return float(bleu.abonnement_tranches[0]["montant"])
    return float(bleu.abonnement_tranches[-1]["montant"])


# ----------------------------------------------------------------------
# Comparaison Octopus vs EDF Tarif Bleu
# ----------------------------------------------------------------------

def comparaison_octopus_edf(df_daily: pd.DataFrame,
                            edf_ref: list[dict]) -> pd.DataFrame:
    """
    Sur la periode Octopus (a partir du 01/01/2026), compare le cout reel
    paye chez Octopus a ce qu'auraient coute deux offres EDF Tarif Bleu :
    l'option Base (prix unique) et l'option Heures Pleines / Heures Creuses.

    edf_ref : liste de periodes {debut, fin, abonnement, prix_base, prix_hp,
    prix_hc}, telle que la renvoie periodes_edf(). Chaque journee est comparee
    a la grille EDF en vigueur ce jour-la (EDF revise au 1er fevrier et au
    1er aout).

    Colonnes retournees :
    - cout_octopus_eur   : cout reel = conso HP/HC + abonnement Octopus.
    - cout_edf_base_eur  : EDF option Base = soutirage x prix Base + abonnement.
    - cout_edf_hphc_eur  : EDF option HP/HC = conso HP/HC aux prix EDF + abonn.
    - gain_vs_base_eur   : cout_edf_base - cout_octopus  (positif = economie).
    - gain_vs_hphc_eur   : cout_edf_hphc - cout_octopus  (positif = economie).
    """
    cols = ["cout_octopus_eur", "cout_edf_base_eur", "cout_edf_hphc_eur",
            "gain_vs_base_eur", "gain_vs_hphc_eur", "soutirage_kwh",
            "abonnement_eur"]
    # Fichier de releves encore vide (premier lancement) : l'index n'est pas
    # un index de dates, et le comparer a une date levait une erreur qui
    # empechait la vue de s'afficher.
    if df_daily.empty:
        return pd.DataFrame(columns=cols)
    out = df_daily[df_daily.index >= CUTOFF_OCTOPUS].copy()
    if out.empty:
        return pd.DataFrame(columns=cols)

    # Grille EDF du jour : abonnement et prix suivent les revisions du tarif
    # reglementaire, comme les prix Octopus suivent les leurs.
    abo = _valeur_periode_series(out.index, edf_ref, "abonnement")
    edf_base = _valeur_periode_series(out.index, edf_ref, "prix_base")
    edf_hp = _valeur_periode_series(out.index, edf_ref, "prix_hp")
    edf_hc = _valeur_periode_series(out.index, edf_ref, "prix_hc")
    jours_mois = pd.Series(out.index.days_in_month, index=out.index, dtype=float)
    abo_jour = abo / jours_mois

    out["cout_octopus_eur"] = out["cout_reseau_eur"]
    out["cout_edf_base_eur"] = out["soutirage_kwh"] * edf_base + abo_jour

    # EDF HP/HC : pour les jours ou le detail HC/HP est renseigne, on applique
    # les prix EDF reels ; sinon on estime via le ratio HC observe.
    sout = out["soutirage_kwh"].fillna(0.0)
    hp = out["soutirage_hp_kwh"].fillna(0.0) if "soutirage_hp_kwh" in out.columns else sout * 0
    hc = out["soutirage_hc_kwh"].fillna(0.0) if "soutirage_hc_kwh" in out.columns else sout * 0
    detail_ok = (hp + hc) >= 0.9 * sout
    total_ok = float((hp[detail_ok] + hc[detail_ok]).sum())
    ratio_hc = (float(hc[detail_ok].sum()) / total_ok) if total_ok > 0 else 1 / 3
    cout_hphc_reel = hc * edf_hc + hp * edf_hp
    cout_hphc_estime = sout * (
        ratio_hc * edf_hc + (1 - ratio_hc) * edf_hp
    )
    out["cout_edf_hphc_eur"] = cout_hphc_reel.where(detail_ok, cout_hphc_estime) + abo_jour

    out["gain_vs_base_eur"] = out["cout_edf_base_eur"] - out["cout_octopus_eur"]
    out["gain_vs_hphc_eur"] = out["cout_edf_hphc_eur"] - out["cout_octopus_eur"]
    return out[cols]


# ----------------------------------------------------------------------
# TVA sur l'autoconsommation : livraison a soi-meme (LASM)
# ----------------------------------------------------------------------
#
# Rappel de la regle, pour que ce code reste lisible dans deux ans.
#
# Producteur en obligation d'achat, contrat S21 vente de surplus, entreprise
# individuelle assujettie a la TVA au reel simplifie :
#
#   - les ventes a EDF OA sont AUTOLIQUIDEES (art. 283-2 quinquies du CGI) :
#     EDF declare la TVA a la place du producteur, qui n'en collecte aucune.
#     La prime a l'autoconsommation, elle, est hors champ ;
#   - seule l'electricite produite ET consommee par soi-meme est taxable.
#     C'est une "livraison a soi-meme" (art. 257-II-1-1°), a porter LIGNE 5A
#     de la declaration annuelle CA12 / 3517-S ;
#   - la base = kWh autoconsommes x prix d'achat HT d'une electricite
#     similaire (art. 266-1-c), c'est-a-dire le propre tarif du producteur :
#     energie + acheminement HT, plus l'accise. Hors TVA, hors abonnement ;
#   - la periode declaree est l'annee CIVILE.
#
# Methode confirmee par ecrit par le SIE de l'auteur en septembre 2026, qui renvoie
# aux releves du producteur pour les quantites.
#
# Deux points de methode qui ne vont pas de soi :
#
#   1. La valorisation se fait JOUR PAR JOUR, au tarif en vigueur ce jour-la.
#      Une moyenne annuelle donnerait un chiffre different, et faux : les
#      tarifs changent en cours d'annee (1er fevrier, 1er aout) alors que
#      l'autoconsommation, elle, est concentree sur l'ete.
#
#   2. Les calculs partent des releves BRUTS du CSV, sans le recalage sur les
#      factures EDF OA applique ailleurs dans l'application. La declaration
#      doit reposer sur les quantites reellement relevees, pas sur des
#      valeurs reconstituees. Consequence assumee : un jour sans releve
#      d'injection compte toute sa production en autoconsommation, ce qui
#      tire la base VERS LE HAUT. Leur nombre est retourne avec le resultat.

@dataclass
class LasmConfig:
    """Grille servant a valoriser l'autoconsommation, lue dans config.yaml.

    periodes : liste de {debut, fin, prix_ht, accise}, "fin" vide = en cours.
    taux     : taux de TVA applicable (0,20).
    """
    periodes: list[dict]
    taux: float = 0.20


def periodes_lasm(cfg_lasm: dict | None) -> list[dict]:
    """Periodes de la grille LASM, triees par date de debut.

    Renvoie une liste vide si la section tva_lasm est absente : cette partie
    ne concerne que les producteurs assujettis a la TVA, elle doit pouvoir
    rester eteinte sans empecher l'application de demarrer.
    """
    if not cfg_lasm:
        return []
    periodes = cfg_lasm.get("periodes") or []
    return sorted(periodes, key=lambda p: str(p["debut"]))


def prix_lasm_serie(idx: pd.DatetimeIndex, periodes: list[dict]) -> pd.Series:
    """Prix unitaire de valorisation (EUR/kWh) pour chaque jour de l'index.

    C'est la somme des deux composantes de la grille : le prix HT de
    l'energie et de son acheminement, et l'accise sur l'electricite.
    """
    if not periodes:
        return pd.Series(0.0, index=idx, dtype=float)
    return (_valeur_periode_series(idx, periodes, "prix_ht")
            + _valeur_periode_series(idx, periodes, "accise"))


def arrondi_euro(montant: float) -> int:
    """Arrondit a l'euro entier, les demis vers le haut, comme le 3517-S.

    round() de Python arrondit "au pair le plus proche" : round(0.5) vaut 0
    et non 1. L'administration, elle, tranche toujours les demis vers le
    haut -- d'ou le passage par Decimal.
    """
    if montant is None or pd.isna(montant):
        return 0
    return int(Decimal(str(float(montant))).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP))


def _bornes_annee(annee: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    return pd.Timestamp(annee, 1, 1), pd.Timestamp(annee, 12, 31)


def _autoconso_brute(df_brut: pd.DataFrame) -> pd.Series:
    """Autoconsommation journaliere = production - injection, jamais negative.

    merge_series a deja pose la colonne ; on sait la refaire ici pour que la
    fonction accepte aussi un tableau ne portant que les deux series
    d'origine.
    """
    if "autoconsommation_kwh" in df_brut.columns:
        return df_brut["autoconsommation_kwh"].fillna(0.0).clip(lower=0)
    prod = df_brut["production_kwh"].fillna(0.0)
    inj = df_brut["injection_kwh"].fillna(0.0)
    return (prod - inj).clip(lower=0)


def base_lasm_periode(df_brut: pd.DataFrame, lasm: LasmConfig,
                      debut: pd.Timestamp,
                      fin: pd.Timestamp) -> tuple[float, float]:
    """(kWh autoconsommes, base LASM en EUR) entre deux dates incluses.

    La base est cumulee jour par jour : chaque kWh est valorise au tarif en
    vigueur le jour ou il a ete consomme.
    """
    if df_brut.empty:
        return 0.0, 0.0
    tranche = df_brut.loc[(df_brut.index >= debut) & (df_brut.index <= fin)]
    if tranche.empty:
        return 0.0, 0.0
    auto = _autoconso_brute(tranche)
    prix = prix_lasm_serie(tranche.index, lasm.periodes)
    return float(auto.sum()), float((auto * prix).sum())


def controle_injection_facturee(
        df_brut: pd.DataFrame,
        injection_facturee: Iterable[dict] | None) -> list[dict]:
    """
    Recoupe les injections relevees avec les kWh reellement factures par EDF.

    C'est ce controle qui rend les chiffres opposables : les quantites
    declarees ne sortent pas d'un tableur tenu tout seul dans son coin, elles
    se recoupent avec un document que le producteur n'ecrit pas lui-meme --
    l'autofacturation annuelle d'EDF OA, etablie sur l'index du compteur de
    production, du 28/06 au 27/06.

    Les jours sans releve d'injection (pannes, avant-contrat) sont d'abord
    completes par estime_injection_manquante : sans cela le controle crierait
    au loup pour une semaine de panne Linky. Leur nombre est retourne, pour
    qu'une periode largement estimee ne passe pas pour une periode verifiee.

    Retourne une liste de dicts : debut, fin, releve_kwh, facture_kwh,
    ecart_kwh, ecart_pct, jours_estimes, source.
    """
    if df_brut.empty or not injection_facturee:
        return []
    # Le controle porte sur la serie completee, et non sur la serie brute :
    # un jour non releve n'est pas un jour a zero injection.
    df = estime_injection_manquante(df_brut)
    lignes = []
    for tranche in injection_facturee:
        debut = pd.Timestamp(tranche["debut"])
        fin = pd.Timestamp(tranche["fin"])
        dans = (df.index >= debut) & (df.index <= fin)
        if not dans.any():
            continue
        releve = float(df.loc[dans, "injection_kwh"].fillna(0.0).sum())
        facture = float(tranche["total_kwh"])
        estimes = int(jours_injection_estimee(df_brut.loc[dans]).sum())
        lignes.append({
            "debut": debut.date(),
            "fin": fin.date(),
            "releve_kwh": releve,
            "facture_kwh": facture,
            "ecart_kwh": releve - facture,
            "ecart_pct": ((releve - facture) / facture * 100.0
                          if facture else None),
            "jours_estimes": estimes,
            "source": str(tranche.get("source", "")),
        })
    return lignes


def _part_annee_ecoulee(df_brut: pd.DataFrame, annees: list[int],
                        mois: int, jour: int) -> float | None:
    """Part de l'autoconso annuelle deja acquise au (mois, jour) donne.

    Moyenne observee sur les annees civiles completes : c'est elle qui sert a
    extrapoler l'annee en cours. Comparaison sur (mois, jour) et non sur le
    quantieme, pour que le 1er mars d'une annee bissextile se compare bien au
    1er mars des autres.
    """
    parts = []
    for an in annees:
        debut, fin = _bornes_annee(an)
        tranche = df_brut.loc[(df_brut.index >= debut) & (df_brut.index <= fin)]
        if tranche.empty:
            continue
        auto = _autoconso_brute(tranche)
        total = float(auto.sum())
        if total <= 0:
            continue
        jusque = (tranche.index.month < mois) | (
            (tranche.index.month == mois) & (tranche.index.day <= jour))
        parts.append(float(auto[jusque].sum()) / total)
    if not parts:
        return None
    return sum(parts) / len(parts)


def _projette_fin_annee(df_brut: pd.DataFrame, lasm: LasmConfig, annee: int,
                        arret: date, completes: list[int], kwh_acquis: float,
                        base_acquise: float) -> tuple[float, float]:
    """Prolonge l'annee en cours jusqu'au 31/12. Voir lasm_par_annee."""
    part = _part_annee_ecoulee(df_brut, completes, arret.month, arret.day)
    if not part or part <= 0 or kwh_acquis <= 0:
        return kwh_acquis, base_acquise
    reste_kwh = max(kwh_acquis / part - kwh_acquis, 0.0)
    jours_restants = pd.date_range(
        pd.Timestamp(arret) + pd.Timedelta(days=1),
        pd.Timestamp(annee, 12, 31), freq="D")
    if len(jours_restants) == 0 or reste_kwh <= 0:
        return kwh_acquis, base_acquise
    # Les kWh a venir sont etales a parts egales sur les jours restants, puis
    # valorises au tarif de chaque jour. L'etalement est grossier -- octobre
    # produit moins que septembre -- mais il ne sert qu'a repartir le reste
    # entre deux grilles de prix si une revision tombe d'ici le 31/12. Sur
    # une fin d'annee sans revision a venir, il n'a aucun effet.
    prix = prix_lasm_serie(jours_restants, lasm.periodes)
    reste_base = float((reste_kwh / len(jours_restants) * prix).sum())
    return kwh_acquis + reste_kwh, base_acquise + reste_base


def lasm_par_annee(df_brut: pd.DataFrame, lasm: LasmConfig,
                   injection_facturee: Iterable[dict] | None = None,
                   aujourdhui: date | None = None) -> list[dict]:
    """
    Recapitulatif de la LASM, une ligne par annee civile.

    df_brut : les releves tels qu'ils sortent du CSV (merge_series), SANS le
    recalage sur les factures -- voir la note en tete de section.

    Chaque ligne porte :
      annee, production_kwh, injection_kwh, autoconsommation_kwh,
      part_autoconso (0 a 1), base_eur (exacte), base_5a_eur (arrondie :
      c'est elle qui se reporte ligne 5A), prix_moyen_eur_kwh, tva_eur
      (exacte), tva_due_eur (arrondie), jours_sans_injection, jours_releves,
      estimation (vrai pour l'annee en cours, projetee), controle (la ligne
      de controle EDF qui se cloture dans l'annee, ou None).

    L'annee en cours est PROJETEE jusqu'au 31/12 : on regarde quelle part de
    son autoconsommation annuelle chaque annee passee avait deja acquise a la
    meme date, et on applique cette part moyenne. C'est une estimation, et
    elle est marquee comme telle.
    """
    if df_brut.empty:
        return []
    if aujourdhui is None:
        aujourdhui = date.today()

    controles = {
        c["fin"].year: c
        for c in controle_injection_facturee(df_brut, injection_facturee)
    }

    # On ne projette jamais au-dela de ce qui est renseigne : si le CSV
    # s'arrete il y a trois semaines, la projection part de cette date-la.
    arret = min(df_brut.index.max().date(), aujourdhui)

    annees = sorted({int(an) for an in df_brut.index.year})
    # Une annee est CLOSE quand les releves vont jusqu'a son 31 decembre.
    # Ce n'est pas la meme chose que "annee passee" : si le CSV s'arrete en
    # septembre et qu'on est en janvier suivant, l'annee ecoulee est bien
    # terminee, mais il lui manque un trimestre. La projeter, et le dire, vaut
    # mieux que d'afficher un montant ampute comme s'il etait definitif.
    completes = [an for an in annees
                 if arret >= _bornes_annee(an)[1].date()]

    lignes = []
    for an in annees:
        debut, fin = _bornes_annee(an)
        tranche = df_brut.loc[(df_brut.index >= debut) & (df_brut.index <= fin)]
        auto = _autoconso_brute(tranche)
        prod = float(tranche["production_kwh"].fillna(0.0).sum())
        inj = float(tranche["injection_kwh"].fillna(0.0).sum())
        kwh = float(auto.sum())
        base = float((auto * prix_lasm_serie(tranche.index, lasm.periodes)).sum())
        sans_inj = int(jours_injection_estimee(tranche).sum())

        estimation = an not in completes
        if estimation:
            # Point de depart de la projection : le dernier jour renseigne DE
            # CETTE ANNEE-LA. Sans cette borne, une annee laissee en plan il y
            # a deux ans se verrait projeter depuis aujourd'hui, c'est-a-dire
            # pas du tout.
            arret_an = min(arret, tranche.index.max().date())
            kwh, base = _projette_fin_annee(
                df_brut, lasm, an, arret_an, completes, kwh, base)

        lignes.append({
            "annee": an,
            "production_kwh": prod,
            "injection_kwh": inj,
            "autoconsommation_kwh": kwh,
            "part_autoconso": (kwh / prod) if prod > 0 else 0.0,
            "base_eur": base,
            "base_5a_eur": arrondi_euro(base),
            "prix_moyen_eur_kwh": (base / kwh) if kwh > 0 else 0.0,
            "tva_eur": base * lasm.taux,
            "tva_due_eur": arrondi_euro(base * lasm.taux),
            "jours_sans_injection": sans_inj,
            "jours_releves": int(len(tranche)),
            "estimation": estimation,
            "controle": controles.get(an),
        })
    return lignes
