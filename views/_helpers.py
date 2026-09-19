"""Helpers partages par toutes les vues : formattage et selection de periode."""
from __future__ import annotations

from datetime import date as _date

import pandas as pd

import calculations as calc
from gui_theme import COULEUR_DEFAVORABLE, COULEUR_FAVORABLE

PERIOD_ALL = "all"

# Noms de mois en francais, independants de la locale du systeme. Accentues :
# ils ne servent qu'a l'affichage, jamais a fabriquer une valeur interne (une
# periode s'ecrit toujours "month-2026-09").
MOIS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


# -----------------------------------------------------------------------------
# Formatage
# -----------------------------------------------------------------------------

def fmt_kwh(x: float) -> str:
    if x is None or pd.isna(x):
        return "—"
    if abs(x) >= 1000:
        return f"{x/1000:.2f} MWh".replace(".", ",")
    return f"{x:.1f} kWh".replace(".", ",")


def fmt_kwc(x: float) -> str:
    """Puissance crete : '6 kWc', '9,5 kWc'. Vide si elle n'est pas connue.

    Le nombre de config.yaml est un decimal (6.0) : affiche tel quel il
    donnerait "6.0 kWc", avec un point et un zero inutile.
    """
    if not x:
        return ""
    texte = f"{float(x):.1f}".rstrip("0").rstrip(".")
    return f"{texte.replace('.', ',')} kWc"


def fmt_eur(x: float, signed: bool = False) -> str:
    if x is None or pd.isna(x):
        return "—"
    s = f"{abs(x):,.2f}".replace(",", " ").replace(".", ",")
    if signed and x > 0:
        return f"+{s} €"
    if x < 0:
        return f"-{s} €"
    return f"{s} €"


def fmt_pct(x: float) -> str:
    if x is None or pd.isna(x):
        return "—"
    return f"{x:.1f} %".replace(".", ",")


def fmt_prix_kwh(x) -> str:
    """Prix au kWh a la francaise, quatre decimales : '0,1985 €/kWh'.

    Plusieurs ecrans l'ecrivaient a l'anglaise (0.1985) : Parametres, tableau
    de bord, hypotheses de la comparaison avec EDF (audit du 14/09/2026).
    """
    return f"{float(x):.4f} €/kWh".replace(".", ",")


def nombre_barre(x, decimales: int = 0) -> str:
    """Chiffre pose sur une barre, a la francaise : '7 812', '25,1'.
    Vide pour zero ou une valeur absente : rien a lire sur une barre nulle."""
    if x is None or pd.isna(x) or round(float(x), decimales) == 0:
        return ""
    return f"{float(x):,.{decimales}f}".replace(",", " ").replace(".", ",")


def chiffres_sur_barres(ax, groupes, decimales: int = 0) -> list[list]:
    """Ecrit la valeur au-dessus de chaque barre d'un graphique matplotlib.

    `groupes` : les series de barres (ce que renvoie chaque ax.bar). Meme
    regle que "Mon fournisseur vs EDF", validee par l'auteur : les chiffres
    a l'horizontale tant qu'ils tiennent entre deux barres voisines, sinon
    debout et un peu plus petits. Demande de l'auteur du 15/09/2026 : les
    chiffres au-dessus de chaque barre, sur tous les graphiques en barres.

    Renvoie les textes poses, groupe par groupe (pour en mettre un en gras).
    """
    barres = [b for groupe in groupes for b in groupe]
    if not barres:
        return []
    etiquettes = [[nombre_barre(b.get_height(), decimales) for b in groupe]
                  for groupe in groupes]
    plus_long = max(len(t) for groupe in etiquettes for t in groupe)

    # Place disponible : l'ecart entre les centres de deux barres voisines,
    # converti en pixels d'apres la largeur du trace.
    centres = sorted(b.get_x() + b.get_width() / 2 for b in barres)
    ecarts = [b - a for a, b in zip(centres, centres[1:], strict=False) if b > a]
    xmin, xmax = ax.get_xlim()
    fig = ax.figure
    px_par_unite = (fig.get_figwidth() * fig.dpi * ax.get_position().width
                    / max(xmax - xmin, 1e-9))
    place_px = min(ecarts) * px_par_unite if ecarts else float("inf")
    # Largeur d'un chiffre ~ 0,6 fois la taille de la police (en pixels).
    largeur_px = plus_long * 9 * 0.6 * fig.dpi / 72
    debout = largeur_px > place_px

    textes = []
    for groupe, libelles in zip(groupes, etiquettes, strict=True):
        textes.append(ax.bar_label(groupe, labels=libelles, padding=2,
                                   rotation=90 if debout else 0,
                                   fontsize=8 if debout else 9))
    # Marge en haut : les chiffres des plus hautes barres ne sont pas coupes.
    ax.margins(y=0.20 if debout else 0.12)
    return textes


def amortissement(data) -> dict | None:
    """Ou en est le remboursement de l'installation, depuis la mise en service.

    Un seul calcul, partage par la Synthese financiere et par la barre
    « Installation remboursee » du tableau de bord : deux copies finiraient
    par diverger. Rend None quand il n'y a aucun releve.

    - recupere : ventes EDF OA + economies + primes deja versees ;
    - gains_an : rythme des gains RECURRENTS (vente OA + economies), les seuls
      qui se repetent chaque annee. La prime, apport unique limite a quelques
      annees, gonflerait ce rythme et raccourcirait l'amortissement (~4 ans
      de moins) ;
    - roi_an : annees necessaires depuis la mise en service, la prime totale
      (versee ou non) venant en deduction du capital a rembourser.
    """
    df = data.df
    if df is None or df.empty:
        return None
    oa = data.oa
    installation = data.cfg["installation"]
    prime_an = calc.prime_annuelle(installation["puissance_kwc"], oa)
    # EDF OA facture la prime APRES la fin de chaque annee OA (facture
    # anniversaire) : regle commune avec la vue Annees OA.
    nb_primes = sum(1 for a in df["annee_oa"].unique()
                    if calc.prime_est_versee(data.start_oa, int(a), oa))
    revenu = float(df["revenu_vente_eur"].sum())
    eco = float(df["economie_eur"].sum())
    invest = float(installation["cout_total_eur"])
    annees = max((df.index.max() - df.index.min()).days / 365.25, 0.01)
    gains_an = (revenu + eco) / annees
    prime_versee = prime_an * nb_primes
    prime_totale = prime_an * oa.prime_duree
    reste = invest - prime_totale
    return {
        "prime_an": prime_an,
        "nb_primes_versees": nb_primes,
        "prime_versee": prime_versee,
        "prime_totale": prime_totale,
        "invest": invest,
        "annees": annees,
        "gains_an": gains_an,
        "reste_a_amortir": reste,
        "roi_an": reste / gains_an if gains_an > 0 else None,
        "recupere": revenu + eco + prime_versee,
    }


def fmt_date_fr(value) -> str:
    """Convertit une date (str ISO, datetime, Timestamp...) en DD/MM/YYYY."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    try:
        ts = pd.Timestamp(value)
    except (ValueError, TypeError):
        return str(value)
    if pd.isna(ts):
        return "—"
    return ts.strftime("%d/%m/%Y")


# -----------------------------------------------------------------------------
# Periodes
# -----------------------------------------------------------------------------

def label_mois_fr(periode_mensuelle) -> str:
    """Ex: 2026-04 -> 'Avril 2026'."""
    return f"{MOIS_FR[periode_mensuelle.month - 1].capitalize()} {periode_mensuelle.year}"


# Libelles courts des colonnes du CSV, pour parler de fraicheur.
LIBELLES_GRANDEURS = {
    "Prod_Jour": "Production",
    "Inj_Jour": "Injection",
    "Conso_réseau_Jour": "Conso réseau",
    "Conso_HC": "Heures creuses",
    "Conso_HP": "Heures pleines",
}


def _age_en_clair(jours: int) -> str:
    if jours <= 0:
        return "aujourd'hui"
    if jours == 1:
        return "hier"
    return f"il y a {jours} jours"


def fraicheur_donnees(dernieres: dict, aujourdhui=None,
                      illisibles: list[str] | None = None,
                      ) -> tuple[str, bool]:
    """
    Resume l'age des donnees, grandeur par grandeur.

    Les sources n'avancent pas au meme rythme : la production vient d'Enphase
    (disponible le jour meme), l'injection et la consommation d'Enedis (deux
    jours de retard environ), le detail HC/HP plus tard encore. Une seule date
    pour tout le fichier ne dirait donc pas ce qu'il reste a importer.

    `illisibles` : dates que pandas n'a pas su lire. Ces journees sont
    absentes de tous les calculs alors qu'elles restent visibles dans
    l'onglet Saisie ; le bandeau est l'endroit ou le dire.

    Retourne (texte a afficher, en_retard) ; en_retard vaut True des qu'une
    grandeur depasse 3 jours — au-dela, c'est qu'un import a ete oublie.
    """
    alerte = _alerte_dates_illisibles(illisibles)

    if not dernieres:
        return ("Aucun relevé dans le fichier." + alerte), True
    if aujourdhui is None:
        aujourdhui = _date.today()

    ages = []
    retard_max = 0
    for colonne, libelle in LIBELLES_GRANDEURS.items():
        quand = dernieres.get(colonne)
        if quand is None:
            continue
        jours = (aujourdhui - quand).days
        retard_max = max(retard_max, jours)
        ages.append(f"{libelle} {_age_en_clair(jours)}")

    if not ages:
        return ("Aucun relevé dans le fichier." + alerte), True
    if retard_max <= 3:
        return ("Données à jour — " + " · ".join(ages) + alerte), bool(alerte)
    return (
        "Données incomplètes — " + " · ".join(ages)
        + ". Pensez a importer vos derniers relevés (boutons « Importer » "
        "dans Saisie quotidienne)." + alerte
    ), True


def _alerte_dates_illisibles(illisibles: list[str] | None) -> str:
    """Phrase a accoler au bandeau quand des journees sont hors des calculs."""
    if not illisibles:
        return ""
    apercu = ", ".join(illisibles[:3]) + (" ..." if len(illisibles) > 3 else "")
    accord = "s" if len(illisibles) > 1 else ""
    return (
        f" ⚠ {len(illisibles)} date{accord} illisible{accord} dans le "
        f"fichier ({apercu}) : ce{'s' if len(illisibles) > 1 else 'tte'} "
        f"journée{accord} n'entre{'nt' if len(illisibles) > 1 else ''} dans "
        "aucun calcul, alors qu'elle" + accord + " reste" +
        ("nt" if len(illisibles) > 1 else "") +
        " visible" + accord + " dans Saisie quotidienne."
    )


def pas_graphique(df: pd.DataFrame) -> tuple[str, str, str]:
    """
    Choisit le pas de temps d'un graphique en fonction de l'etendue affichee.

    Le pas etait fige au mois : sur « Toute la periode » cela faisait 52 mois
    x 4 series = 208 barres sur 12 cm (illisible), et sur un seul mois une
    unique barre par serie (sans interet).

    Retourne (frequence pandas, format de date des etiquettes, adjectif au
    SINGULIER — a accorder par l'appelant : « Bilan mensuel », « Flux
    mensuels ») :
      - jusqu'a ~2 mois   -> semaines  (4 a 9 groupes)
      - jusqu'a ~18 mois  -> mois      (jusqu'a 18 groupes)
      - au-dela           -> annees    (5 groupes sur 4 ans d'historique)
    """
    if df.empty:
        return "MS", "%m/%y", "mensuel"
    jours = (df.index.max() - df.index.min()).days + 1
    if jours <= 70:
        # Tranches de 7 jours calees sur le debut de la periode, plutot que
        # des semaines calendaires : pandas les nommerait par leur date de
        # FIN, qui deborde du mois affiche ("03/08" sur un graphique de
        # juillet). Ici chaque etiquette est le premier jour de sa tranche.
        return "7D", "%d/%m", "hebdomadaire"
    if jours <= 550:
        return "MS", "%m/%y", "mensuel"
    return "YS", "%Y", "annuel"


def period_options(df: pd.DataFrame, start_oa) -> list[tuple[str, str]]:
    """Toutes les periodes valides, a plat : [(label, value), ...].

    Ne remplit plus aucun menu depuis que le selecteur est coupe en deux
    (voir options_annees et options_mois), mais reste la liste de reference
    de ce qui est selectionnable — c'est elle qui dit si une periode existe.
    """
    opts = [("Toute la période", PERIOD_ALL)]
    if df.empty:
        return opts
    for y in sorted(df.index.year.unique().tolist(), reverse=True):
        opts.append((f"Année {y}", f"year-{y}"))
    for m in sorted(df.index.to_period("M").unique().tolist(), reverse=True):
        opts.append((label_mois_fr(m), f"month-{m.strftime('%Y-%m')}"))
    for n in sorted([int(a) for a in df["annee_oa"].unique() if a > 0], reverse=True):
        opts.append((label_annee_oa(start_oa, n), f"oa-{n}"))
    return opts


# -----------------------------------------------------------------------------
# Selecteur de periode en deux menus (annee, puis mois)
# -----------------------------------------------------------------------------
# Une seule liste deroulante finissait par compter 65 lignes, et une de plus
# chaque mois. Coupee en deux, elle tient en 6 et 13 entrees qui ne
# s'allongeront plus. Les valeurs internes ("all", "year-2026",
# "month-2026-09", "oa-3") sont inchangees : seule la facon de les choisir
# change, les vues ne voient aucune difference.

MOIS_TOUS = "*"       # entree « Toute l'annee » du menu des mois


def label_annee_oa(start_oa, n: int) -> str:
    """Ex: 'Année OA #3'.

    Volontairement court : les dates de debut et de fin obligeraient le menu
    a rester deux fois plus large pour un libelle qu'on lit rarement. Elles
    sont dans l'infobulle (voir bornes_annee_oa) et dans l'onglet OA.
    """
    return f"Année OA #{n}"


def bornes_annee_oa(start_oa, n: int) -> str:
    """Ex: 'du 12/05/2024 au 11/05/2025' — pour l'infobulle du menu."""
    d, f = calc.oa_year_bounds(start_oa, n)
    return f"du {d.strftime('%d/%m/%Y')} au {f.strftime('%d/%m/%Y')}"


def options_annees(df: pd.DataFrame, start_oa) -> list[tuple[str, str]]:
    """Contenu du menu de gauche : « Toute la période », les annees civiles
    de la plus recente a la plus ancienne, puis les annees OA."""
    opts = [("Toute la période", PERIOD_ALL)]
    if df.empty:
        return opts
    for y in sorted(df.index.year.unique().tolist(), reverse=True):
        opts.append((str(y), f"year-{y}"))
    for n in sorted([int(a) for a in df["annee_oa"].unique() if a > 0], reverse=True):
        opts.append((label_annee_oa(start_oa, n), f"oa-{n}"))
    return opts


def options_mois(df: pd.DataFrame, annee: int) -> list[tuple[str, str]]:
    """Contenu du menu de droite pour une annee civile donnee.

    Seuls les mois qui portent des releves y figurent : proposer un mois vide
    ouvrirait un ecran sans rien, sans dire pourquoi.
    """
    opts = [("Toute l'année", MOIS_TOUS)]
    if df.empty:
        return opts
    mois = sorted({m for m in df.index.to_period("M").unique().tolist()
                   if m.year == annee}, reverse=True)
    for m in mois:
        opts.append((MOIS_FR[m.month - 1].capitalize(), f"month-{m.strftime('%Y-%m')}"))
    return opts


def annee_de_periode(period: str) -> int | None:
    """Annee civile portee par une periode, ou None (« toute la periode »,
    annee OA — qui est a cheval sur deux annees civiles)."""
    if period.startswith("year-"):
        return int(period.split("-")[1])
    if period.startswith("month-"):
        return int(period.split("-")[1])
    return None


def _echelle_de_navigation(df: pd.DataFrame, start_oa, period: str) -> list[str]:
    """Suite ordonnee, du plus ancien au plus recent, dans laquelle les deux
    fleches se deplacent — mois entre mois, annees entre annees."""
    if df.empty:
        return []
    if period.startswith("month-"):
        return [f"month-{m.strftime('%Y-%m')}"
                for m in sorted(df.index.to_period("M").unique().tolist())]
    if period.startswith("year-"):
        return [f"year-{y}" for y in sorted(df.index.year.unique().tolist())]
    if period.startswith("oa-"):
        return [f"oa-{n}"
                for n in sorted([int(a) for a in df["annee_oa"].unique() if a > 0])]
    return []   # « toute la periode » n'a ni precedent ni suivant


def periode_voisine(df: pd.DataFrame, start_oa, period: str, sens: int) -> str | None:
    """Periode d'un cran plus ancienne (sens=-1) ou plus recente (sens=+1).

    None quand il n'y a plus rien de ce cote : c'est ce qui grise la fleche,
    plutot que de la laisser cliquable sans effet.
    """
    echelle = _echelle_de_navigation(df, start_oa, period)
    if period not in echelle:
        return None
    i = echelle.index(period) + sens
    return echelle[i] if 0 <= i < len(echelle) else None


def filter_period(df: pd.DataFrame, period: str, start_oa) -> pd.DataFrame:
    if df.empty or period == PERIOD_ALL or not period:
        return df
    if period.startswith("year-"):
        y = int(period.split("-")[1])
        return df[df.index.year == y]
    if period.startswith("month-"):
        ym = period.split("-", 1)[1]
        start = pd.Timestamp(ym + "-01")
        end = start + pd.offsets.MonthEnd(0)
        return df[(df.index >= start) & (df.index <= end)]
    if period.startswith("oa-"):
        n = int(period.split("-")[1])
        d, f = calc.oa_year_bounds(start_oa, n)
        return df[(df.index.date >= d) & (df.index.date <= f)]
    return df


# -----------------------------------------------------------------------------
# Comparaison avec la periode precedente
# -----------------------------------------------------------------------------
# Ces trois fonctions etaient des methodes privees de ComparaisonView. Elles
# sont remontees ici parce que la vue "Repartition energie" affiche desormais
# le meme genre de comparaison : deux copies du meme calcul finiraient tot ou
# tard par diverger.

# (cle de colonne, libelle, unite, sens) - sens=+1 si une hausse est une
# bonne nouvelle (produire plus), -1 sinon (soutirer plus).
METRIQUES = [
    ("production_kwh",       "Production",          "kwh", +1),
    ("autoconsommation_kwh", "Autoconsommation",    "kwh", +1),
    ("injection_kwh",        "Injection vendue",    "kwh", +1),
    ("soutirage_kwh",        "Soutirage réseau",    "kwh", -1),
    ("revenu_vente_eur",     "Revenus vente OA",    "eur", +1),
    ("economie_eur",         "Économies autoconso", "eur", +1),
    ("cout_reseau_eur",      "Dépenses réseau",     "eur", -1),
    ("bilan_jour_eur",       "Bilan net",           "eur", +1),
]
METRIQUES_ENERGIE = {"production_kwh", "autoconsommation_kwh",
                     "injection_kwh", "soutirage_kwh"}


def agreger(df_sub: pd.DataFrame, cles=None) -> dict | None:
    """Somme les colonnes demandees. None si la periode n'a aucun releve."""
    if df_sub is None or df_sub.empty:
        return None
    if cles is None:
        cles = [cle for cle, *_ in METRIQUES]
    return {cle: float(df_sub[cle].sum()) for cle in cles
            if cle in df_sub.columns}


def variation(delta: float, base: float | None, fmt, sens: int,
              theme: dict) -> tuple[str, str]:
    """Retourne (texte de la variation, couleur) pour un ecart N - N-1.

    Le texte donne l'ecart en valeur ET en pourcentage, parce que l'un sans
    l'autre trompe : "+50 %" sur une base minuscule n'est rien, "+40 kWh" sans
    reference ne dit pas si c'est beaucoup.
    """
    if abs(delta) < 1e-9:
        return "stable", theme["text_muted"]
    favorable = (delta > 0) == (sens > 0)
    couleur = COULEUR_FAVORABLE if favorable else COULEUR_DEFAVORABLE
    signe = "+" if delta > 0 else "-"
    abs_str = fmt(abs(delta))
    if base is not None and abs(base) > 1e-9:
        pct = abs(delta) / abs(base) * 100
        pct_str = f"{pct:.1f}".replace(".", ",")
        return f"{signe}{abs_str}  ({signe}{pct_str} %)", couleur
    return f"{signe}{abs_str}", couleur


def periode_precedente(period: str) -> str | None:
    """Cle de la meme periode un cran plus tot (meme mois l'an dernier...).

    Retourne None quand la comparaison n'a pas de sens : "Toute la periode"
    n'a pas d'annee precedente, et l'annee OA #1 n'a pas de #0.
    """
    if not period or period == PERIOD_ALL:
        return None
    if period.startswith("year-"):
        return f"year-{int(period.split('-')[1]) - 1}"
    if period.startswith("month-"):
        p = pd.Period(period.split("-", 1)[1], freq="M") - 12
        return f"month-{p.strftime('%Y-%m')}"
    if period.startswith("oa-"):
        n = int(period.split("-")[1])
        return f"oa-{n - 1}" if n > 1 else None
    return None


def libelle_periode(period: str) -> str:
    """Nom lisible d'une cle de periode : 'Fevrier 2026', 'Annee 2025'..."""
    if not period or period == PERIOD_ALL:
        return "Toute la période"
    if period.startswith("year-"):
        return f"Année {period.split('-')[1]}"
    if period.startswith("month-"):
        return label_mois_fr(pd.Period(period.split("-", 1)[1], freq="M"))
    if period.startswith("oa-"):
        return f"Année OA #{period.split('-')[1]}"
    return period

def _pluriel(n: int, mot: str) -> str:
    """« 1 journée », « 1 062 valeurs » -- milliers separes comme fmt_eur."""
    nombre = f"{n:,}".replace(",", " ")
    return f"{nombre} {mot}" + ("s" if n > 1 else "")


def phrase_en_attente(jours) -> str:
    """Ce que deviennent les journees mises de cote faute de releves reseau.

    L'onduleur donne la production du jour meme, Enedis publie conso et
    injection le lendemain : la derniere journee d'un fichier n'a souvent que
    sa production. Elle sort des calculs (voir calculations.jours_en_attente),
    donc il faut dire ou elle est passee -- sinon on la croit perdue, ce qui
    a ete la premiere reaction d'un utilisateur (19/09/2026).
    """
    jours = list(jours or [])
    if not jours:
        return ""
    dates = ", ".join(d.strftime("%d/%m/%Y") for d in jours)
    if len(jours) == 1:
        debut = f"La journée du {dates} n'est pas encore comptée"
        possessif, suite = "sa", "Elle s'ajoutera d'elle-même"
    else:
        debut = f"Les journées du {dates} ne sont pas encore comptées"
        possessif, suite = "leur", "Elles s'ajouteront d'elles-mêmes"
    return (f"{debut} : {possessif} production est connue, mais Enedis publie "
            f"la consommation et l'injection le lendemain. {suite} au prochain "
            "import — rien n'est perdu.")


def phrase_import(nouveaux: int, remplaces: int, jours: int) -> str:
    """Ce que l'import va changer, en une phrase, avant le detail chiffre.

    Un utilisateur a lu « 0 nouveau(x) » dans le detail et conclu que son
    import ne faisait rien, alors qu'il corrigeait plus de mille valeurs
    (18/09/2026). Le detail par colonne reste ; cette phrase le precede et
    dit lequel des quatre nombres compte.
    """
    if not nouveaux and not remplaces:
        return (f"Rien à changer : les {jours} jours de ce fichier sont "
                "déjà dans vos relevés, avec les mêmes valeurs.")
    if not remplaces:
        return f"{_pluriel(nouveaux, 'journée')} va être ajoutée." if nouveaux == 1 \
            else f"{_pluriel(nouveaux, 'journée')} vont être ajoutées."
    if not nouveaux:
        debut = (f"{_pluriel(remplaces, 'valeur')} va être corrigée."
                 if remplaces == 1
                 else f"{_pluriel(remplaces, 'valeur')} vont être corrigées.")
        return (debut + " Aucune journée nouvelle : ces dates sont déjà dans "
                "vos relevés.")
    return (f"{_pluriel(nouveaux, 'journée')} vont être ajoutées, et "
            f"{_pluriel(remplaces, 'valeur')} corrigées.")

