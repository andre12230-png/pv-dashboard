"""Formats d'export que l'import refusait ou lisait mal (audit du 08/10/2026).

Fichiers fabriques, valeurs inventees.

    py -m pytest tests/test_imports_audit_formats.py
"""

from __future__ import annotations

import imports_releves as ir


def test_date_francaise_suivie_d_une_heure():
    """« 01/06/2026 00:00 » : un releve quotidien horodate a minuit etait
    refuse (« Aucune ligne reconnue »), alors que la date ISO avec heure
    passait."""
    texte = ("Date;Injection (kWh)\n"
             "01/06/2026 00:00;12,5\n"
             "02/06/2026 00:00;10\n")
    colonne, valeurs = ir.parse_enedis_csv_texte(texte)
    assert colonne == "Inj_Jour"
    assert valeurs == {"01/06/2026": "12,5", "02/06/2026": "10"}


def test_annee_sur_deux_chiffres():
    """« 01/06/26 » : la ligne etait ignoree sans un mot, et l'import
    « reussissait » avec une partie des jours seulement."""
    texte = ("Date;Injection (kWh)\n"
             "01/06/26;12,5\n"
             "02/06/2026;10\n")
    _colonne, valeurs = ir.parse_enedis_csv_texte(texte)
    assert set(valeurs) == {"01/06/2026", "02/06/2026"}


def test_texte_unicode_de_windows():
    """Enregistre en « Texte Unicode » (UTF-16) par Windows : le fichier
    etait annonce « type de données introuvable »."""
    brut = "Date;Injection (kWh)\n01/06/2026;12,5\n".encode("utf-16")
    assert "Injection" in ir._decode_texte(brut)
    sans_marque = "Date;Injection (kWh)\n01/06/2026;12,5\n".encode("utf-16-le")
    assert "Injection" in ir._decode_texte(sans_marque)


def test_production_rangee_en_injection_est_annoncee():
    """Un export d'onduleur (« Production ») passe par le bouton « achat au
    réseau / injection » etait range en Injection sans un mot. Chez Enedis,
    « production » peut designer l'injection : on ne refuse pas, on le dit
    dans le recapitulatif, qui s'affiche avant d'appliquer."""
    notes: list[str] = []
    colonne, _ = ir.parse_enedis_csv_texte(
        "Date;Production (kWh)\n01/06/2026;12,5\n", notes)
    assert colonne == "Inj_Jour"
    assert any("Importer la production" in n for n in notes)
    # Un export qui dit « injection » ne recoit pas cette remarque.
    notes = []
    ir.parse_enedis_csv_texte("Date;Injection (kWh)\n01/06/2026;12,5\n", notes)
    assert not any("Importer la production" in n for n in notes)
