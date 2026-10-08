"""Une case de chiffres illisible dans Releves-pv.csv (audit du 08/10/2026).

« 12,5 kWh » ou « 1O » (lettre O) dans une case de production devenait
0 kWh dans tous les calculs, sans un mot. Comme les dates illisibles, ces
cases sont desormais relevees et annoncees dans le bandeau du tableau de
bord. Releves inventes.

    py -m pytest tests/test_valeurs_illisibles.py
"""

from __future__ import annotations

from datetime import date

import data_loaders as dl
from views._helpers import fraicheur_donnees


def test_cases_illisibles_relevees(tmp_path):
    chemin = tmp_path / "Releves-pv.csv"
    chemin.write_text(
        ";".join(dl.RELEVES_HEADER) + "\n"
        "01/06/2026;12,5 kWh;4;5;2;3\n"
        "02/06/2026;10;;6;3;3\n"          # case vide : pas une faute
        "03/06/2026;9;1O;6;3;3\n", encoding="utf-8")
    assert dl.valeurs_illisibles(str(chemin)) == [
        "01/06/2026 (Prod_Jour : « 12,5 kWh »)",
        "03/06/2026 (Inj_Jour : « 1O »)"]


def test_le_bandeau_le_dit():
    texte, en_retard = fraicheur_donnees(
        {"Prod_Jour": date(2026, 6, 3)}, aujourdhui=date(2026, 6, 4),
        valeurs_illisibles=["01/06/2026 (Prod_Jour : « 12,5 kWh »)"])
    assert en_retard
    assert "12,5 kWh" in texte and "0\xa0kWh" in texte
    assert "Saisie quotidienne" in texte
