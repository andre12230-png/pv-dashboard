"""Une case de chiffres illisible dans Releves-pv.csv (audit du 08/10/2026).

« 12,5 kWh » ou « 1O » (lettre O) dans une case de production devenait
0 kWh dans tous les calculs, sans un mot. Comme les dates illisibles, ces
cases sont desormais relevees et annoncees dans le bandeau du tableau de
bord. Releves inventes.

    py -m pytest tests/test_valeurs_illisibles.py
"""

from __future__ import annotations

from datetime import date

import data_loaders as dl
from views._helpers import fraicheur_donnees


def test_cases_illisibles_relevees(tmp_path):
    chemin = tmp_path / "Releves-pv.csv"
    chemin.write_text(
        ";".join(dl.RELEVES_HEADER) + "\n"
        "01/06/2026;12,5 kWh;4;5;2;3\n"
        "02/06/2026;10;;6;3;3\n"          # case vide : pas une faute
        "03/06/2026;9;1O;6;3;3\n", encoding="utf-8")
    assert dl.valeurs_illisibles(str(chemin)) == [
        "01/06/2026 (Prod_Jour : « 12,5 kWh »)",
        "03/06/2026 (Inj_Jour : « 1O »)"]


def test_le_bandeau_le_dit():
    texte, en_retard = fraicheur_donnees(
        {"Prod_Jour": date(2026, 6, 3)}, aujourdhui=date(2026, 6, 4),
        valeurs_illisibles=["01/06/2026 (Prod_Jour : « 12,5 kWh »)"])
    assert en_retard
    assert "12,5 kWh" in texte and "0\xa0kWh" in texte
    assert "Saisie quotidienne" in texte


# --- Valeurs negatives deja dans le fichier (contre-audit du 13/10/2026) -----
# L'import et la saisie les refusent desormais, mais un fichier plus ancien
# peut en contenir : 20 produits et -5 injectes donnaient 25 kWh
# d'autoconsommation. Elles sont signalees, le fichier n'est pas reecrit.

def test_cases_negatives_relevees(tmp_path):
    chemin = tmp_path / "Releves-pv.csv"
    chemin.write_text(
        ";".join(dl.RELEVES_HEADER) + "\n"
        "01/06/2026;20;-5;5;2;3\n"
        "02/06/2026;10;0;-0;3;3\n"         # « -0 » vaut zero : pas une faute
        "03/06/2026;9;1;6;-1,5;3\n", encoding="utf-8")
    assert dl.valeurs_negatives(str(chemin)) == [
        "01/06/2026 (Inj_Jour : « -5 »)",
        "03/06/2026 (Conso_HC : « -1,5 »)"]


def test_le_bandeau_dit_les_negatifs():
    texte, en_retard = fraicheur_donnees(
        {"Prod_Jour": date(2026, 6, 3)}, aujourdhui=date(2026, 6, 4),
        valeurs_negatives=["01/06/2026 (Inj_Jour : « -5 »)"])
    assert en_retard
    assert "-5" in texte and "négative" in texte
    assert "Saisie quotidienne" in texte


def test_les_negatifs_arrivent_jusqu_au_tableau_de_bord(tmp_path, monkeypatch):
    import yaml

    import app_desktop
    cfg = yaml.safe_load(app_desktop.CONFIG_PATH.read_text(encoding="utf-8"))
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(app_desktop, "BASE_DIR", tmp_path)
    monkeypatch.setattr(app_desktop, "CONFIG_PATH", tmp_path / "config.yaml")
    monkeypatch.setattr(app_desktop, "CONFIG_LOCAL_PATH",
                        tmp_path / "config-local.yaml")
    (tmp_path / "Releves-pv.csv").write_text(
        ";".join(dl.RELEVES_HEADER) + "\n"
        "01/06/2025;20;-5;5;2;3\n", encoding="utf-8")
    data = app_desktop.build_dataset(app_desktop.load_config())
    assert data.valeurs_negatives == ["01/06/2025 (Inj_Jour : « -5 »)"]
