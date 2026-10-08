"""
Lecture du fichier recharges.json de l'application Recharges VE : l'energie
rechargee a la maison, jour par jour. Lecture seule.

Detache de data_loaders.py le 28/09/2026 ; data_loaders le reimporte.
"""

from __future__ import annotations

import json
import sys
from datetime import date as _date

import pandas as pd

# ----------------------------------------------------------------------
# Recharges du vehicule electrique (application "recharges-ve")
# ----------------------------------------------------------------------

def charger_recharges_ve(path: str) -> pd.DataFrame:
    """
    Lit le fichier `recharges.json` de l'application recharges-ve et rend,
    par journee civile, l'energie rechargee A LA MAISON et son cout.

    Seules les recharges `lieu == "maison"` comptent : elles seules passent
    par le compteur de la maison. Les recharges exterieures sont payees
    ailleurs et n'ont rien a voir avec le releve Enedis.

    Une charge de nuit va typiquement de 23:30 a 05:00 : elle est donc
    **repartie entre les deux journees** au prorata du temps passe dans
    chacune, pour rester comparable aux releves quotidiens.

    Le cout vient du fichier (`cout_eur`), calcule par l'autre application
    sur les vraies plages horaires : le repartir au prorata du cout reseau
    total le surestimerait beaucoup, ces charges tombant presque toutes en
    heures creuses.

    Colonnes : recharge_ve_kwh, recharge_ve_eur. Le fichier appartient a
    l'autre application : il est seulement lu, jamais modifie. Un DataFrame
    vide est rendu si le fichier est absent ou illisible (l'app doit demarrer
    meme sans, par exemple sur un autre PC).
    """
    from datetime import datetime, time, timedelta

    vide = pd.DataFrame(columns=["recharge_ve_kwh", "recharge_ve_eur"])
    try:
        with open(path, "r", encoding="utf-8") as fh:
            contenu = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"[warn] recharges VE illisibles ({path}) : {exc}", file=sys.stderr)
        return vide

    recharges = contenu.get("recharges", []) if isinstance(contenu, dict) else contenu
    # Une forme inattendue (« recharges » vide, un texte, une liste melee)
    # faisait planter le demarrage (audit du 08/10/2026) : ce qu'on ne
    # comprend pas est ignore, comme une ligne incomplete.
    if not isinstance(recharges, list):
        recharges = []
    recharges = [r for r in recharges if isinstance(r, dict)]
    kwh_jour: dict[_date, float] = {}
    eur_jour: dict[_date, float] = {}

    def _ajouter(jour: _date, kwh: float, eur: float) -> None:
        kwh_jour[jour] = kwh_jour.get(jour, 0.0) + kwh
        eur_jour[jour] = eur_jour.get(jour, 0.0) + eur

    for r in recharges:
        # « Maison » ou « maison  » comptent aussi (audit du 08/10/2026).
        if str(r.get("lieu", "")).strip().lower() != "maison":
            continue
        try:
            kwh = float(r["kwh"])
            debut = datetime.fromisoformat(r["date"])
            fin = datetime.fromisoformat(r["fin"])
        except (KeyError, TypeError, ValueError):
            continue  # ligne incomplete : on l'ignore plutot que de tout perdre
        try:
            eur = float(r.get("cout_eur") or 0.0)
        except (TypeError, ValueError):
            eur = 0.0
        duree = (fin - debut).total_seconds()
        if duree <= 0:
            # Duree nulle ou incoherente : tout sur le jour de debut.
            _ajouter(debut.date(), kwh, eur)
            continue
        jour = debut.date()
        while jour <= fin.date():
            minuit = datetime.combine(jour, time.min)
            deb_j = max(debut, minuit)
            fin_j = min(fin, minuit + timedelta(days=1))
            secondes = (fin_j - deb_j).total_seconds()
            if secondes > 0:
                part = secondes / duree
                _ajouter(jour, kwh * part, eur * part)
            jour += timedelta(days=1)

    if not kwh_jour:
        return vide
    out = pd.DataFrame({
        "recharge_ve_kwh": pd.Series(kwh_jour),
        "recharge_ve_eur": pd.Series(eur_jour),
    }).sort_index()
    out.index = pd.to_datetime(out.index)
    return out
