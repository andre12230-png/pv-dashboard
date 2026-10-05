"""Colonnes de tableau : jamais un en-tete coupe (audit du 04/10/2026).

Reparties a parts egales, les neuf colonnes des Releves (avec le vehicule)
laissaient 113 px a « Autoconsommation », qui en demande 133 : l'en-tete
s'affichait « utoconsommation ». Chaque colonne recoit d'abord sa largeur
minimale, puis le reste de la place est partage.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QFontMetrics  # noqa: E402
from PySide6.QtWidgets import QApplication, QTableWidget  # noqa: E402

from gui_widgets import largeurs_colonnes, repartir_colonnes  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def test_le_reste_est_partage_a_parts_egales():
    assert largeurs_colonnes([100, 50, 50], 260) == [120, 70, 70]


def test_sans_place_chacune_garde_son_minimum():
    assert largeurs_colonnes([100, 50, 50], 150) == [100, 50, 50]


def test_aucun_entete_n_est_coupe_dans_un_tableau_etroit(qapp):
    entetes = ["Date", "Production\n(kWh)", "Autoconsommation\n(kWh)",
               "Injection\n(kWh)", "Achat au réseau\n(kWh)"]
    table = QTableWidget(3, len(entetes))
    table.setHorizontalHeaderLabels(entetes)
    total = QTableWidget(1, len(entetes))
    repartir_colonnes(table, suiveuses=[total])
    table.resize(500, 300)
    table.show()
    QApplication.processEvents()
    h = table.horizontalHeader()
    fm = QFontMetrics(h.font())
    for c, texte in enumerate(entetes):
        ligne = max(texte.split("\n"), key=fm.horizontalAdvance)
        assert h.sectionSize(c) >= fm.horizontalAdvance(ligne), texte
        assert total.horizontalHeader().sectionSize(c) == h.sectionSize(c)
    table.close()
