"""Releves journaliers : en-tetes en clair et ligne de totaux (audit du
14/09/2026, groupe B)."""
from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QTableWidget  # noqa: E402

from gui_theme import LIGHT  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def vue(qapp):
    from views.transactions import TransactionsView
    jours = pd.date_range("2026-09-01", "2026-09-03", freq="D")
    df = pd.DataFrame({
        "production_kwh": [10.0, 12.5, 7.5],
        "autoconsommation_kwh": 4.0, "injection_kwh": 6.0,
        "soutirage_kwh": 8.0, "revenu_vente_eur": 0.6,
        "economie_eur": 0.9, "cout_reseau_eur": 2.0,
        "bilan_jour_eur": -0.5,
    }, index=jours)
    donnees = SimpleNamespace(df=df, start_oa=pd.Timestamp("2022-06-28").date())
    v = TransactionsView(donnees, LIGHT)
    v.refresh("all")
    return v


def _tables(vue):
    tables = vue.findChildren(QTableWidget)
    principal = next(t for t in tables if t.rowCount() == 3)
    totaux = next(t for t in tables if t.rowCount() == 1)
    return principal, totaux


def test_la_ligne_de_totaux_additionne_la_periode(vue):
    _, totaux = _tables(vue)
    assert totaux.item(0, 0).text() == "Total"
    assert totaux.item(0, 1).text() == "30,0"     # production
    assert totaux.item(0, 4).text() == "24,0"     # achetee au reseau
    assert totaux.item(0, 7).text() == "-1,50"    # bilan du jour cumule


def test_la_ligne_de_totaux_a_les_colonnes_du_tableau(vue):
    principal, totaux = _tables(vue)
    assert totaux.columnCount() == principal.columnCount()


def test_les_entetes_sont_en_clair(vue):
    principal, _ = _tables(vue)
    entetes = [principal.horizontalHeaderItem(i).text()
               for i in range(principal.columnCount())]
    assert "Production\n(kWh)" in entetes
    assert not any(e.startswith(("Prod\n", "Sout\n")) for e in entetes)
