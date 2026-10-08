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


# --- Virgule decimale et ouverture de « Mes réglages » ----------------------
# Un prix tape « 0,22 » donnait au demarrage « could not convert string to
# float: '0,22' », en anglais ; et une erreur a l'ouverture de « Mes
# réglages » ne disait rien du tout (le clic semblait sans effet).

def test_virgule_decimale_lue(tmp_path):
    cfg = app_desktop._lire_yaml(_ecrire(tmp_path, (
        "tarifs_reseau:\n"
        "  contrat_hphc:\n"
        "    prix_hp_eur_kwh: 0,2200\n"
        '    prix_hc_eur_kwh: "0,16"\n'
        '    nom: "Offre 2,5"\n')))
    contrat = cfg["tarifs_reseau"]["contrat_hphc"]
    assert contrat["prix_hp_eur_kwh"] == 0.22
    assert contrat["prix_hc_eur_kwh"] == 0.16
    assert contrat["nom"] == "Offre 2,5"          # un nom reste un nom


def test_mes_reglages_qui_echoue_le_dit(monkeypatch):
    """Le clic sur « Modifier mes réglages » ne reste plus muet."""
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    vus = []

    class Faux:
        cfg = {}

    fenetre = type("F", (), {})()
    fenetre.data = Faux()
    fenetre._saisies_reglees = lambda avant: True
    monkeypatch.setattr(app_desktop.reglages, "lire_reglages",
                        lambda cfg: (_ for _ in ()).throw(
                            ValueError("Prix du kWh illisible : 0,2x")))
    monkeypatch.setattr(app_desktop.QMessageBox, "warning",
                        lambda parent, titre, texte: vus.append((titre, texte)))
    app_desktop.MainWindow._ouvrir_reglages(fenetre)
    assert vus and "0,2x" in vus[0][1]
    assert vus[0][0] != "Erreur"
