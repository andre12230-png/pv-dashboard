"""Les listes datees montrent la date la plus recente en haut (10/10/2026).

Demande de l'auteur, pour ses deux applis de la maison : les releves, la
saisie, les annees OA et la TVA le faisaient deja ; les tuiles de rendement,
les periodes de prix des Parametres, les grilles de la Comparaison avec EDF
et les recalages de « Mes réglages » allaient du plus ancien au plus
recent. Seul l'ecran change : les fichiers gardent l'ordre chronologique.
Donnees inventees.

    py -m pytest tests/test_ordre_recentes_en_haut.py
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest
import yaml

pytest.importorskip("PySide6")

from conftest import detruire  # noqa: E402
from PySide6.QtWidgets import QApplication, QTableWidget  # noqa: E402
from test_reglages import ANCIEN  # noqa: E402
from test_tva_lasm import _lasm_plat, _releves  # noqa: E402

import reglages as rg  # noqa: E402
from gui_theme import LIGHT  # noqa: E402
from gui_widgets import KpiCard  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def test_tuiles_de_rendement_l_annee_la_plus_recente_en_premier(qapp):
    from views.stats import StatsView
    jours = pd.date_range("2023-03-01", "2025-06-30", freq="D")
    df = pd.DataFrame({"production_kwh": 10.0, "autoconsommation_kwh": 4.0,
                       "injection_kwh": 6.0, "soutirage_kwh": 5.0},
                      index=jours)
    v = StatsView(SimpleNamespace(df=df, cfg={"installation": {
        "puissance_kwc": 5.0}}), LIGHT)
    v.populate("all")
    try:
        # Titres en petites capitales : « ANNÉE 2025 — PARTIELLE ».
        titres = [c.label.text() for c in v.findChildren(KpiCard)]
        annees = [t.split()[1] for t in titres if t.upper().startswith("ANNÉE")]
        assert annees == ["2025", "2024", "2023"]
    finally:
        detruire(v)


def test_periodes_de_prix_des_parametres_la_plus_recente_en_haut():
    from views.settings import _recentes_d_abord
    periodes = [{"debut": "2023-02-01", "prix": 0.2},
                {"debut": "2024-02-01", "prix": 0.25},
                {"debut": "2022-08-01", "prix": 0.18}]
    assert [p["debut"] for p in _recentes_d_abord(periodes)] == [
        "2024-02-01", "2023-02-01", "2022-08-01"]
    assert _recentes_d_abord(None) == []


def test_controle_tva_trie_meme_si_le_fichier_est_dans_le_desordre(qapp):
    from views.tva import TvaView
    df = _releves([
        ("2023-01-15", 100.0, 50.0), ("2023-12-31", 0.0, 0.0),
        ("2024-01-15", 100.0, 50.0), ("2024-12-31", 0.0, 0.0),
    ])
    factures = [   # le plus recent d'abord, dans le fichier
        {"debut": "2024-01-01", "fin": "2024-12-31", "total_kwh": 50},
        {"debut": "2023-01-01", "fin": "2023-12-31", "total_kwh": 50},
    ]
    v = TvaView(SimpleNamespace(
        df_brut=df, lasm=_lasm_plat(),
        cfg={"sources": {"injection_facturee": factures}},
        cycle_oa="du 01/01 au 31/12"), LIGHT)
    v.populate("")
    try:
        controle = v.findChildren(QTableWidget)[-1]
        assert controle.item(0, 0).text().startswith("du 01/01/2024")
        assert controle.item(1, 0).text().startswith("du 01/01/2023")
    finally:
        detruire(v)


def test_mes_reglages_recalages_recents_en_haut_fichier_chronologique(qapp):
    from fenetre_reglages import FenetreReglages
    recalages = rg.recalages_vides()
    recalages["injection_facturee"] = [
        {"debut": date(2023, 1, 1), "fin": date(2023, 12, 31),
         "total_kwh": 100.0, "source": "facture A"},
        {"debut": date(2024, 1, 1), "fin": date(2024, 12, 31),
         "total_kwh": 200.0, "source": "facture B"},
    ]
    f = FenetreReglages(rg.lire_reglages(yaml.safe_load(ANCIEN)),
                        lambda _v: None, recalages=recalages,
                        enregistrer_recalages=lambda _r: None)
    try:
        lignes = [f._lignes.itemAt(i).widget()
                  for i in range(f._lignes.count())]
        assert [ligne.valeurs()[1]["debut"] for ligne in lignes] == [
            date(2024, 1, 1), date(2023, 1, 1)]
        # Une ligne neuve arrive en haut.
        f._ajouter_ligne()
        assert f._lignes.itemAt(0).widget() not in lignes
        # Ce qui s'enregistre reste dans l'ordre chronologique.
        lus = f.recalages()["injection_facturee"]
        debuts = [p["debut"] for p in lus]
        assert debuts == sorted(debuts)
    finally:
        detruire(f)
