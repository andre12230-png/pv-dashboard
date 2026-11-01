"""Des relevés tout en nombres entiers, avec un recalage sur facture.

Trouve le 01/11/2026 : une colonne sans aucune decimale etait lue en entiers,
et pandas 3 refuse d'y ecrire les valeurs recalees. L'application affichait
« Impossible de démarrer ». Un debutant qui saisit des kWh ronds et ajoute une
facture tombait dessus. Valeurs inventees.

    py -m pytest tests/test_releves_entiers.py
"""
from __future__ import annotations

import pandas as pd
import pytest
import yaml

import app_desktop
import data_loaders as dl

JOURS = pd.date_range("2025-01-01", "2025-03-31")
LIGNES = "".join(f"{j:%d/%m/%Y};20;10;8;3;5\n" for j in JOURS)


def _ecrire(tmp_path, monkeypatch, sources: dict | None = None) -> None:
    cfg = yaml.safe_load(app_desktop.CONFIG_PATH.read_text(encoding="utf-8"))
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(app_desktop, "BASE_DIR", tmp_path)
    monkeypatch.setattr(app_desktop, "CONFIG_PATH", tmp_path / "config.yaml")
    monkeypatch.setattr(app_desktop, "CONFIG_LOCAL_PATH",
                        tmp_path / "config-local.yaml")
    (tmp_path / "Releves-pv.csv").write_text(
        ";".join(dl.RELEVES_HEADER) + "\n" + LIGNES, encoding="utf-8")
    if sources:
        (tmp_path / "config-local.yaml").write_text(
            yaml.safe_dump({"sources": sources}), encoding="utf-8")


def test_les_releves_sont_lus_en_nombres_a_virgule(tmp_path, monkeypatch):
    _ecrire(tmp_path, monkeypatch)
    production, reseau = dl.load_releves_pv(str(tmp_path / "Releves-pv.csv"))
    assert production["production_kwh"].dtype == float
    for colonne in ("injection_kwh", "soutirage_kwh",
                    "soutirage_hc_kwh", "soutirage_hp_kwh"):
        assert reseau[colonne].dtype == float, colonne


@pytest.mark.parametrize("section, colonne, total", [
    ("injection_facturee", "injection_kwh", 500.0),
    ("conso_reseau_recalee", "soutirage_kwh", 500.0),
])
def test_un_recalage_sur_des_entiers_ne_bloque_pas_le_demarrage(
        tmp_path, monkeypatch, section, colonne, total):
    _ecrire(tmp_path, monkeypatch, {section: [
        {"debut": "2025-01-01", "fin": "2025-03-31", "total_kwh": total,
         "source": "facture inventée"}]})
    data = app_desktop.build_dataset(app_desktop.load_config())
    assert data.df[colonne].sum() == pytest.approx(total)
