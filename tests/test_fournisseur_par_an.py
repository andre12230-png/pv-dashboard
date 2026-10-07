"""Page fournisseur : « soit environ X € par an » (audit du 04/10/2026).

Le gain de la periode etait multiplie jusqu'a faire un an : trois mois
d'ete donnaient +1 €/an, trois mois d'hiver +6 €/an, l'annee entiere +7 €.
Desormais : rien avant un an de releves, puis le gain reel des 365 derniers
jours, sans extrapolation."""
from __future__ import annotations

import pandas as pd

from views.octopus_edf import texte_par_an


def _gains(debut: str, jours: int, valeur: float = 0.1) -> pd.Series:
    return pd.Series(valeur, index=pd.date_range(debut, periods=jours))


def test_moins_d_un_an_rien_n_est_extrapole():
    texte = texte_par_an(_gains("2026-06-01", 90))
    assert "€" not in texte
    assert "après un an de relevés" in texte
    assert "275 jours" in texte


def test_au_dela_d_un_an_le_gain_des_365_derniers_jours():
    gains = pd.concat([_gains("2024-01-01", 400, 1.0),
                       _gains("2025-02-04", 365, 0.1)])
    assert texte_par_an(gains) == "soit +36,50\xa0€ sur les 365 derniers jours"
