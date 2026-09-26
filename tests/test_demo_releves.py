"""Le jeu de releves INVENTES des captures du site et du smoke test.

Il doit etre lisible par l'application, identique a chaque tirage (graine
fixe), et couvrir les periodes que le smoke test parcourt.
"""
from __future__ import annotations

from datetime import date

import data_loaders as dl
from demo_releves import ecrire_releves_demo, lignes_demo


def test_meme_jeu_a_chaque_fois():
    fin = date(2026, 6, 30)
    assert lignes_demo(fin=fin) == lignes_demo(fin=fin)


def test_lisible_par_l_application(tmp_path):
    chemin = tmp_path / "Releves-pv.csv"
    n = ecrire_releves_demo(chemin, fin=date(2026, 6, 30))
    production, reseau = dl.load_releves_pv(str(chemin))
    assert n == (date(2026, 6, 30) - date(2024, 1, 1)).days + 1
    assert len(production) == n and len(reseau) == n
    # Les periodes du smoke test : 2024, juin 2025, avril 2026.
    jours = {d.strftime("%Y-%m") for d in production.index}
    assert {"2024-01", "2025-06", "2026-04"} <= jours
