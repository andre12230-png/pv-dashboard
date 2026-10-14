"""Les week-ends des calendriers se lisent (relecture du 14/10/2026).

Qt ecrit samedis et dimanches dans un rouge vif et pur : 4,0 pour 1 sur le
blanc des cases, 3,35 sur le fond sombre, sous les 4,5 de la charte. Les deux
calendriers de l'appli (« Mes reglages », vue Comparaison) les ecrivent dans
le rouge des depenses du theme. Meme defaut, meme correction que Pecule.
"""
from __future__ import annotations

import os
from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import gui_theme  # noqa: E402
from tests.test_contraste import contraste  # noqa: E402
from views._helpers import METRIQUES  # noqa: E402


@pytest.fixture(params=["clair", "sombre"])
def theme(request):
    QApplication.instance() or QApplication([])
    t = gui_theme.choisir_theme(request.param)
    yield t
    gui_theme.choisir_theme("clair")


def _verifier(case, t):
    calendrier = case.calendarWidget()
    for jour in (Qt.Saturday, Qt.Sunday):
        couleur = calendrier.weekdayTextFormat(jour).foreground().color()
        assert couleur.name().upper() == t["debit"].upper()
        assert contraste(couleur.name(), t["bg_saisie"]) >= 4.5


def test_calendrier_de_mes_reglages(theme):
    import fenetre_reglages
    _verifier(fenetre_reglages._date(date(2026, 10, 14)), theme)


def test_calendrier_de_la_comparaison(theme):
    from views.comparaison import ComparaisonView
    jours = pd.date_range("2025-01-01", "2026-02-28", freq="D")
    df = pd.DataFrame({cle: 1.0 for cle, *_ in METRIQUES}, index=jours)
    df["annee_oa"] = 1
    vue = ComparaisonView(SimpleNamespace(df=df, start_oa=date(2025, 1, 1)),
                          theme)
    try:
        _verifier(vue._creer_calendrier(df), theme)
    finally:
        vue.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
