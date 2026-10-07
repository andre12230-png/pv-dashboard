"""Plus de zero negatif a l'ecran (audit du 04/10/2026).

Un ecart de -0,004 EUR s'ecrivait « -0,00 € » en rouge, -0,03 kWh
« -0,0 kWh », -0,4 % « −0 % par rapport à… », la page TVA « -0,0 » et
« -0,00 % ». Un nombre qui s'affiche zero s'ecrit zero, sans signe.
"""
from __future__ import annotations

import pytest

from gui_theme import LIGHT
from views._helpers import fmt_eur, fmt_kwh, fmt_kwh_seul, fmt_pct, variation


@pytest.fixture(scope="module")
def qapp_module():
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


def test_les_montants_minuscules_s_ecrivent_zero():
    assert fmt_eur(-0.004) == "0,00\xa0€"
    assert fmt_eur(-0.004, signed=True) == "0,00\xa0€"
    assert fmt_eur(-0.006) == "-0,01\xa0€"          # un vrai centime reste


def test_les_kwh_et_pourcentages_minuscules_s_ecrivent_zero():
    assert fmt_kwh(-0.03) == "0,0\xa0kWh"
    assert fmt_kwh_seul(-0.03) == "0,0\xa0kWh"
    assert fmt_pct(-0.04) == "0,0\xa0%"


def test_un_ecart_invisible_est_stable():
    texte, _couleur = variation(-0.004, 10.0, fmt_eur, +1, LIGHT)
    assert texte == "stable"
    texte, _couleur = variation(-0.03, 10.0, fmt_kwh_seul, +1, LIGHT)
    assert texte == "stable"


def test_les_nombres_de_la_page_tva():
    from views.tva import _nombre
    assert _nombre(-0.04, 1) == "0,0"
    assert _nombre(-0.004, 2) == "0,00"


def test_le_badge_du_tableau_de_bord_ne_dit_pas_moins_zero(qapp_module):
    from types import SimpleNamespace

    import pandas as pd

    from views.dashboard import DashboardView
    jours = (list(pd.date_range("2025-06-01", "2025-06-10"))
             + list(pd.date_range("2026-06-01", "2026-06-10")))
    prod = [10.0] * 10 + [9.996] * 10          # -0,04 %
    df = pd.DataFrame({"production_kwh": prod}, index=pd.DatetimeIndex(jours))
    tableau = DashboardView.__new__(DashboardView)
    tableau.data = SimpleNamespace(df=df, start_oa=None)
    tableau.theme = LIGHT
    df_n = df[df.index >= "2026-06-01"]
    badge = tableau._badge_n1(df_n, "month-2026-06",
                              float(df_n["production_kwh"].sum()))
    assert "−0 %" not in badge.text() and "-0 %" not in badge.text()
    assert badge.text().startswith("stable")


def test_le_total_des_releves_ne_dit_pas_moins_zero(qapp_module):
    from types import SimpleNamespace

    import pandas as pd
    from PySide6.QtWidgets import QTableWidget

    from views.transactions import TransactionsView
    jours = pd.date_range("2026-09-01", "2026-09-02", freq="D")
    df = pd.DataFrame({
        "production_kwh": 10.0, "autoconsommation_kwh": 4.0,
        "injection_kwh": 6.0, "soutirage_kwh": 8.0,
        "revenu_vente_eur": 0.6, "economie_eur": 0.9,
        "cout_reseau_eur": 1.5, "bilan_jour_eur": [0.001, -0.003],
    }, index=jours)
    v = TransactionsView(SimpleNamespace(df=df, start_oa=None), LIGHT)
    v.refresh("all")
    totaux = next(t for t in v.findChildren(QTableWidget) if t.rowCount() == 1)
    assert totaux.item(0, totaux.columnCount() - 1).text() == "0,00"
