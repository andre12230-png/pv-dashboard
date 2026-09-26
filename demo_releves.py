"""Releves journaliers INVENTES, pour les captures du site et le smoke test.

Aucune donnee reelle : une installation de 3 kWc (celle du config.yaml livre)
et une maison d'environ 4 000 kWh par an, tirees au hasard avec une graine
fixe -- memes chiffres a chaque fois. Un seul generateur pour les deux usages :
deux copies finiraient par diverger.
"""
from __future__ import annotations

import math
import random
from datetime import date, timedelta
from pathlib import Path

# Production moyenne d'un jour, en kWh par kWc, mois par mois : environ
# 980 kWh/kWc sur l'annee, dans la moyenne francaise.
PROD_PAR_KWC = [1.1, 1.7, 2.6, 3.4, 3.9, 4.2, 4.3, 3.8, 3.0, 2.0, 1.2, 0.9]
KWC = 3.0
ENTETE = "Date;Prod_Jour;Inj_Jour;Conso_réseau_Jour;Conso_HC;Conso_HP"


def _nombre(x: float) -> str:
    """3,142 : la virgule decimale du CSV."""
    return f"{x:.3f}".replace(".", ",")


def lignes_demo(debut: date = date(2024, 1, 1), fin: date | None = None,
                graine: int = 2026) -> list[str]:
    """Les lignes du CSV (en-tete compris), du `debut` a `fin` (hier par
    defaut)."""
    hasard = random.Random(graine)
    fin = fin or date.today() - timedelta(days=1)
    lignes = [ENTETE]
    jour = debut
    while jour <= fin:
        # Meteo du jour : de tres couvert a grand soleil.
        meteo = min(1.35, max(0.15, hasard.gauss(0.95, 0.3)))
        prod = PROD_PAR_KWC[jour.month - 1] * KWC * meteo
        # Maison d'environ 4 000 kWh par an, davantage l'hiver.
        saison = math.cos(2 * math.pi * (jour.timetuple().tm_yday - 15) / 365)
        conso = max(5.0, 11 + 4 * saison + hasard.gauss(0, 1.5))
        autoconso = min(prod * hasard.uniform(0.32, 0.48), conso * 0.6)
        soutirage = conso - autoconso
        hc = soutirage * hasard.uniform(0.40, 0.55)
        lignes.append(";".join([
            jour.strftime("%d/%m/%Y"), _nombre(prod), _nombre(prod - autoconso),
            _nombre(soutirage), _nombre(hc), _nombre(soutirage - hc)]))
        jour += timedelta(days=1)
    return lignes


def ecrire_releves_demo(chemin: Path, **kwargs) -> int:
    """Ecrit le jeu invente dans `chemin` ; rend le nombre de jours."""
    lignes = lignes_demo(**kwargs)
    Path(chemin).write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return len(lignes) - 1
