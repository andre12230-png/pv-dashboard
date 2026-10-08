"""Dates ecrites a la main dans config.yaml / config-local.yaml (audit du
08/10/2026).

Une date tapee a la francaise, « 01/06/2024 », etait lue par pandas au format
americain : le 6 janvier 2024. Les annees OA et le passage en heures pleines /
creuses etaient alors faux sur toute la periode, sans un mot. Desormais :
JJ/MM/AAAA est lu comme un Francais l'ecrit, AAAA-MM-JJ reste valable, et une
date impossible est refusee avec un message clair. Donnees inventees.

    py -m pytest tests/test_dates_config.py
"""

from __future__ import annotations

from datetime import date

import pytest

import app_desktop
import reglages


def _ecrire(tmp_path, texte: str):
    chemin = tmp_path / "config.yaml"
    chemin.write_text(texte, encoding="utf-8")
    return chemin


def test_date_francaise_lue_jour_puis_mois(tmp_path):
    cfg = app_desktop._lire_yaml(_ecrire(tmp_path, (
        "installation:\n"
        '  date_debut_contrat_oa: "01/06/2024"\n'
        "contrat_hphc:\n"
        "  periodes:\n"
        '    - { debut: "15.03.2025", fin: "31-12-2025" }\n')))
    assert cfg["installation"]["date_debut_contrat_oa"] == "2024-06-01"
    periode = cfg["contrat_hphc"]["periodes"][0]
    assert (periode["debut"], periode["fin"]) == ("2025-03-15", "2025-12-31")


def test_dates_iso_et_yaml_inchangees(tmp_path):
    cfg = app_desktop._lire_yaml(_ecrire(tmp_path, (
        "installation:\n"
        "  date_mise_en_service: 2024-06-01\n"
        '  date_debut_contrat_oa: "2024-06-01"\n'
        '  nom: "Toit sud 12/06"\n')))
    assert cfg["installation"]["date_mise_en_service"] == date(2024, 6, 1)
    assert cfg["installation"]["date_debut_contrat_oa"] == "2024-06-01"
    assert cfg["installation"]["nom"] == "Toit sud 12/06"   # pas une date


def test_date_impossible_refusee_en_clair(tmp_path):
    with pytest.raises(RuntimeError) as e:
        app_desktop._lire_yaml(_ecrire(tmp_path, (
            "installation:\n"
            '  date_debut_contrat_oa: "31/02/2024"\n')))
    assert "31/02/2024" in str(e.value)
    assert "date" in str(e.value).lower()


def test_mes_reglages_lit_une_date_francaise():
    """« Mes réglages » relit le fichier brut a l'enregistrement : il lui
    faut la meme lecture (avant : « Invalid isoformat string »)."""
    assert reglages._date("01/06/2024") == date(2024, 6, 1)
    assert reglages._date("2024-06-01") == date(2024, 6, 1)
