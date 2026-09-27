"""Page TVA : l'ordre des tableaux.

Demande du 27/09/2026 : l'annee la plus recente EN HAUT des deux tableaux
(recapitulatif par annee et controle avec les factures EDF OA), comme on lit
un releve. Le graphique, lui, reste chronologique de gauche a droite.

Donnees inventees.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QTableWidget
from test_tva_lasm import _lasm_plat, _releves

import calculations as calc
from gui_theme import LIGHT
from views.tva import TvaView


@pytest.fixture(scope="module")
def qapp():
    """Une seule QApplication pour toute la session (Qt l'exige)."""
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def vue(qapp):
    df = _releves([
        ("2023-01-15", 100.0, 50.0), ("2023-12-31", 0.0, 0.0),
        ("2024-01-15", 100.0, 50.0), ("2024-12-31", 0.0, 0.0),
        ("2025-01-15", 60.0, 30.0), ("2025-06-30", 0.0, 0.0),
    ])
    factures = [
        {"debut": "2023-01-01", "fin": "2023-12-31", "total_kwh": 50},
        {"debut": "2024-01-01", "fin": "2024-12-31", "total_kwh": 50},
    ]
    data = SimpleNamespace(
        df_brut=df,
        lasm=_lasm_plat(),
        cfg={"sources": {"injection_facturee": factures}},
        cycle_oa="01/01 → 31/12",
    )
    v = TvaView(data, LIGHT)
    v.populate("")
    return v


def _premiere_colonne(table: QTableWidget) -> list[str]:
    return [table.item(i, 0).text() for i in range(table.rowCount())]


def test_les_deux_tableaux_commencent_par_l_annee_la_plus_recente(vue):
    annees, controle = vue.findChildren(QTableWidget)
    assert _premiere_colonne(annees) == ["2025 (estimé)", "2024", "2023"]
    periodes = _premiere_colonne(controle)
    assert periodes[0].startswith("01/01/2024")
    assert periodes[-1].startswith("01/01/2023")


def test_le_calcul_reste_chronologique():
    """Seul l'affichage s'inverse : le calcul rend toujours les annees dans
    l'ordre, le graphique et les tuiles en dependent."""
    df = _releves([("2023-01-15", 100.0, 50.0), ("2024-01-15", 100.0, 50.0)])
    lignes = calc.lasm_par_annee(df, _lasm_plat())
    assert [ligne["annee"] for ligne in lignes] == [2023, 2024]
