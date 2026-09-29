"""Les pages qui n'etaient verifiees que par « elles s'ouvrent » (smoke) :
Repartition energie, Annees OA, Fournisseur vs EDF, Parametres.

Revue du 28/09/2026. Ici, leurs chiffres sont controles sur trois journees
inventees dont on connait les bons resultats. Modele livre (3 kWc, vente du
surplus a 0,10 EUR/kWh, contrat depuis le 01/01/2024).

    py -m pytest tests/test_pages_chiffrees.py
"""
from __future__ import annotations

import re

import pytest
import yaml

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QTableWidget  # noqa: E402

import app_desktop  # noqa: E402
import data_loaders as dl  # noqa: E402
from views._helpers import fmt_pct  # noqa: E402

# Production, injection, conso reseau, HC, HP.
JOURNEES = ("01/09/2026;20;12;5;2;3\n"
            "02/09/2026;18;10;6;3;3\n"
            "03/09/2026;19;11;4;2;2\n")
PRODUCTION, INJECTION, SOUTIRAGE = 57.0, 33.0, 15.0
AUTOCONSO = PRODUCTION - INJECTION                # 24


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def win(qapp, tmp_path, monkeypatch):
    cfg = yaml.safe_load(app_desktop.CONFIG_PATH.read_text(encoding="utf-8"))
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(app_desktop, "BASE_DIR", tmp_path)
    monkeypatch.setattr(app_desktop, "CONFIG_PATH", tmp_path / "config.yaml")
    monkeypatch.setattr(app_desktop, "CONFIG_LOCAL_PATH",
                        tmp_path / "config-local.yaml")
    (tmp_path / "Releves-pv.csv").write_text(
        ";".join(dl.RELEVES_HEADER) + "\n" + JOURNEES, encoding="utf-8")
    data = app_desktop.build_dataset(app_desktop.load_config())
    prefs = QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)
    w = app_desktop.MainWindow(data, prefs)
    w._appliquer_periode("all")
    yield w
    w.close()


def _textes(win, cle: str) -> str:
    win._switch_view(cle)
    return " | ".join(lbl.text() for lbl in win.views[cle].findChildren(QLabel))


def _euros(texte: str) -> float:
    """« -1 234,56 € » ou « +12,00 € » -> nombre."""
    brut = texte.replace(" ", "").replace(" ", "").replace("€", "")
    return float(brut.replace(",", ".").replace("−", "-"))


# --- Repartition energie -------------------------------------------------------

def test_repartition_taux_d_autoconsommation_et_couverture(win):
    textes = _textes(win, "categories")
    assert fmt_pct(AUTOCONSO / PRODUCTION * 100) in textes          # 42,1 %
    assert fmt_pct(AUTOCONSO / (AUTOCONSO + SOUTIRAGE) * 100) in textes


# --- Annees OA ----------------------------------------------------------------

def test_annees_oa_revenu_egal_injection_fois_prix(win):
    win._switch_view("oa")
    table = win.views["oa"].findChildren(QTableWidget)[0]
    entetes = [table.horizontalHeaderItem(j).text()
               for j in range(table.columnCount())]
    ligne = 0                                      # une seule annee OA
    inj = table.item(ligne, entetes.index("Inj (kWh)")).text()
    revenu = table.item(ligne, entetes.index("Revenu (€)")).text()
    assert inj == "33,0"
    assert revenu == f"{INJECTION * 0.10:.2f}".replace(".", ",")    # 3,30


# --- Fournisseur vs EDF ---------------------------------------------------------

def test_fournisseur_vs_edf_ecarts_coherents(win):
    cle = "octopus_edf"
    win._switch_view(cle)
    cartes = {}
    for lbl in win.views[cle].findChildren(QLabel):
        cartes.setdefault(lbl.parent(), []).append(lbl.text())
    valeurs = {}
    for textes in cartes.values():
        euros = [t for t in textes if re.fullmatch(r"[+\-−]?[\d  ]+,\d\d €", t)]
        if euros:
            valeurs[textes[0]] = _euros(euros[0])
    actuel = next(v for k, v in valeurs.items() if "(actuel)" in k.lower())
    base = next(v for k, v in valeurs.items()
                if k.upper().endswith("BASE") and not k.upper().startswith("PAR RAPPORT À"))
    hphc = next(v for k, v in valeurs.items()
                if k.upper().endswith("HP/HC") and not k.upper().startswith("PAR RAPPORT À"))
    gain_base = next(v for k, v in valeurs.items()
                     if k.upper().startswith("PAR RAPPORT À") and k.upper().endswith("BASE"))
    gain_hphc = next(v for k, v in valeurs.items()
                     if k.upper().startswith("PAR RAPPORT À") and k.upper().endswith("HP/HC"))
    assert actuel > 0
    assert gain_base == pytest.approx(base - actuel, abs=0.01)
    assert gain_hphc == pytest.approx(hphc - actuel, abs=0.01)


# --- Parametres ---------------------------------------------------------------

def test_parametres_reprennent_la_configuration(win):
    textes = _textes(win, "settings")
    assert "3 kWc" in textes
    assert "9 000,00 €" in textes
    assert "EDF OA" in textes
    assert "0,1000 €/kWh" in textes
    assert "en cours" in textes                      # periode de prix ouverte


def test_plus_de_vs_sur_les_pages_chiffrees(win):
    """Relecture du 29/09/2026 : « vs » est un anglicisme. Sur des pages
    remplies de chiffres (les tuiles « VS EDF BASE » de la page fournisseur
    n'existent qu'avec des releves), aucun texte ne l'emploie."""
    vs = re.compile(r"\bvs\b", re.IGNORECASE)
    trouves = []
    for cle in win.views:
        win._switch_view(cle)
        trouves += [f"{cle} : {lbl.text()[:80]}"
                    for lbl in win.views[cle].findChildren(QLabel)
                    if vs.search(lbl.text())]
    assert not trouves, trouves


def test_l_estimation_annuelle_se_lit_en_toutes_lettres(win):
    """29/09/2026 : « ~-19,88 €/an » (tilde colle au signe, barre oblique)
    devient « soit environ -19,88 € par an »."""
    textes = _textes(win, "octopus_edf")
    assert "~" not in textes and "€/an" not in textes
    assert textes.count("soit environ ") == 2
    assert " € par an" in textes
