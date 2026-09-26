"""Vente totale, ou pas de revente du tout (lot « autres utilisateurs »,
26/09/2026).

L'application supposait le contrat de son auteur : vente du SURPLUS à EDF OA,
avec prime à l'autoconsommation et date de début de contrat. En vente totale,
la prime était comptée quand même ; sans revente (autoconsommation seule, un
kit prêt à brancher par exemple), la configuration était refusée faute de
date de contrat, et plusieurs écrans plantaient sans elle.
"""
from __future__ import annotations

import pytest
import yaml

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

import app_desktop  # noqa: E402
import calculations as calc  # noqa: E402
import data_loaders as dl  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _donnees(tmp_path, monkeypatch, retoucher):
    """Le modele livre, retouche, sur trois journees completes."""
    cfg = yaml.safe_load(app_desktop.CONFIG_PATH.read_text(encoding="utf-8"))
    retoucher(cfg)
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(app_desktop, "BASE_DIR", tmp_path)
    monkeypatch.setattr(app_desktop, "CONFIG_PATH", tmp_path / "config.yaml")
    monkeypatch.setattr(app_desktop, "CONFIG_LOCAL_PATH",
                        tmp_path / "config-local.yaml")
    (tmp_path / "Releves-pv.csv").write_text(
        ";".join(dl.RELEVES_HEADER) + "\n"
        "01/06/2025;20;12;5;2;3\n02/06/2025;18;10;6;3;3\n"
        "03/06/2026;19;11;4;2;2\n", encoding="utf-8")
    lu = app_desktop.normaliser_config(
        app_desktop._lire_yaml(tmp_path / "config.yaml"))
    app_desktop.verifier_config(lu)
    return app_desktop.build_dataset(lu)


def _vente_totale(cfg):
    cfg["oa"]["type"] = "totale"


def _sans_revente(cfg):
    cfg["oa"] = {"type": "aucune"}
    cfg["installation"].pop("date_debut_contrat_oa", None)


def test_vente_totale_sans_prime(tmp_path, monkeypatch):
    # La prime à l'autoconsommation ne va qu'à la vente du surplus.
    data = _donnees(tmp_path, monkeypatch, _vente_totale)
    assert calc.prime_annuelle(data.puissance_kwc, data.oa) == 0
    assert data.df["revenu_vente_eur"].sum() > 0


def test_sans_revente_rien_n_est_vendu(tmp_path, monkeypatch):
    data = _donnees(tmp_path, monkeypatch, _sans_revente)
    assert data.start_oa is None
    assert data.df["revenu_vente_eur"].sum() == 0
    assert calc.prime_annuelle(data.puissance_kwc, data.oa) == 0
    # Pas d'« Année OA » dans le sélecteur de période.
    from views._helpers import period_options
    assert not [v for _, v in period_options(data.df, data.start_oa)
                if str(v).startswith("oa-")]


def test_sans_revente_chaque_ecran_s_ouvre(qapp, tmp_path, monkeypatch):
    data = _donnees(tmp_path, monkeypatch, _sans_revente)
    prefs = QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)
    win = app_desktop.MainWindow(data, prefs)
    try:
        for key, _, _, _ in app_desktop.NAV_ITEMS:
            win._switch_view(key)
        # Pas d'onglet « Années OA » ni de « OA depuis » sous le titre.
        assert "oa" not in win.nav_buttons
        sous_titre = " ".join(lbl.text() for lbl in win.findChildren(QLabel)
                              if lbl.objectName() == "BrandSub")
        assert "OA" not in sous_titre
    finally:
        win.close()


def test_type_de_vente_inconnu_refuse_en_francais():
    cfg = yaml.safe_load(app_desktop.CONFIG_PATH.read_text(encoding="utf-8"))
    cfg["oa"]["type"] = "surplsu"
    with pytest.raises(RuntimeError) as erreur:
        app_desktop.verifier_config(cfg)
    assert "surplus, totale ou aucune" in str(erreur.value)


# ── Les libellés suivent le contrat (étape 2) ───────────────────────────────

def _textes(win, key) -> str:
    # En majuscules : les titres des cartes s'affichent ainsi.
    win._switch_view(key)
    return " ".join(lbl.text() for lbl in
                    win.views[key].findChildren(QLabel)).upper()


def _fenetre(qapp, tmp_path, monkeypatch, retoucher):
    data = _donnees(tmp_path, monkeypatch, retoucher)
    prefs = QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)
    return app_desktop.MainWindow(data, prefs)


def _autre_acheteur(cfg):
    cfg["oa"]["type"] = "totale"
    cfg["oa"]["acheteur"] = "Solaire Coop"


def test_un_autre_acheteur_est_nomme(qapp, tmp_path, monkeypatch):
    win = _fenetre(qapp, tmp_path, monkeypatch, _autre_acheteur)
    try:
        tableau = _textes(win, "dashboard")
        assert "VENTE À SOLAIRE COOP" in tableau
        assert "EDF OA" not in tableau
        synthese = _textes(win, "accounts")
        assert "SOLAIRE COOP" in synthese
        assert "PRIME AUTOCONSO" not in synthese      # vente totale : pas de prime
        assert "EDF OA" not in _textes(win, "settings")
    finally:
        win.close()


def test_sans_revente_pas_de_vente_affichee(qapp, tmp_path, monkeypatch):
    win = _fenetre(qapp, tmp_path, monkeypatch, _sans_revente)
    try:
        tableau = _textes(win, "dashboard")
        assert "VENTE À" not in tableau
        assert "INJECTÉ" in tableau
        synthese = _textes(win, "accounts")
        assert "VENTE" not in synthese and "PRIME AUTOCONSO" not in synthese
    finally:
        win.close()


def test_par_defaut_toujours_edf_oa(qapp, tmp_path, monkeypatch):
    # Sans acheteur déclaré (les fichiers existants) : rien ne change.
    win = _fenetre(qapp, tmp_path, monkeypatch, lambda cfg: None)
    try:
        assert "VENTE À EDF OA" in _textes(win, "dashboard")
    finally:
        win.close()
