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

from conftest import detruire  # noqa: E402
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


def test_vente_totale_rien_n_est_autoconsomme(tmp_path, monkeypatch):
    # En vente totale, toute la production part au reseau par son propre
    # compteur : la maison ne consomme que du reseau. Defaut d'origine : la
    # production etait payee en entier ET la part non injectee comptee en
    # economie, soit deux fois (ici 20 kWh vendus, dont 8 comptes en plus).
    data = _donnees(tmp_path, monkeypatch, _vente_totale)
    df = data.df
    assert df["autoconsommation_kwh"].sum() == 0
    assert df["economie_eur"].sum() == 0
    assert (df["injection_kwh"] == df["production_kwh"]).all()
    assert (df["consommation_kwh"] == df["soutirage_kwh"]).all()
    assert df["bilan_jour_eur"].sum() == pytest.approx(
        df["revenu_vente_eur"].sum() - df["cout_reseau_eur"].sum())


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
        detruire(win)


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
        detruire(win)


def test_sans_revente_pas_de_vente_affichee(qapp, tmp_path, monkeypatch):
    win = _fenetre(qapp, tmp_path, monkeypatch, _sans_revente)
    try:
        tableau = _textes(win, "dashboard")
        assert "VENTE À" not in tableau
        assert "INJECTÉ" in tableau
        synthese = _textes(win, "accounts")
        assert "VENTE" not in synthese and "PRIME AUTOCONSO" not in synthese
    finally:
        detruire(win)


def test_par_defaut_toujours_edf_oa(qapp, tmp_path, monkeypatch):
    # Sans acheteur déclaré (les fichiers existants) : rien ne change.
    win = _fenetre(qapp, tmp_path, monkeypatch, lambda cfg: None)
    try:
        assert "VENTE À EDF OA" in _textes(win, "dashboard")
    finally:
        detruire(win)


def test_sous_titre_des_annees_de_contrat_nomme_l_acheteur(
        qapp, tmp_path, monkeypatch):
    win = _fenetre(qapp, tmp_path, monkeypatch, _autre_acheteur)
    try:
        win._switch_view("oa")
        assert "EDF" not in win.sub_lbl.text()
        assert "Solaire Coop" in win.sub_lbl.text()
    finally:
        detruire(win)


# ── Années OA : la plus récente en haut (28/09/2026) ────────────────────────

def _contrat_en_cours_de_releves(cfg):
    # Le 01/06/2025 precede le contrat : une ligne « avant OA ».
    cfg["installation"]["date_debut_contrat_oa"] = "2025-06-02"


def test_annees_oa_la_plus_recente_en_haut(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QTableWidget
    win = _fenetre(qapp, tmp_path, monkeypatch, _contrat_en_cours_de_releves)
    try:
        win._switch_view("oa")
        table = win.views["oa"].findChildren(QTableWidget)[0]
        premiere_colonne = [table.item(i, 0).text()
                            for i in range(table.rowCount())]
        # Comme la page TVA : l'annee la plus recente d'abord, et la periode
        # d'avant-contrat, la plus ancienne, en dernier.
        assert premiere_colonne == ["#2", "#1", "avant OA"]
    finally:
        detruire(win)


# ── La Notice nomme l'acheteur réel (28/09/2026) ────────────────────────────

def test_la_notice_nomme_l_acheteur_declare(qapp, tmp_path, monkeypatch):
    win = _fenetre(qapp, tmp_path, monkeypatch, _autre_acheteur)
    try:
        win._switch_view("aide")
        texte = " ".join(lbl.text() for lbl in
                         win.views["aide"].findChildren(QLabel))
        assert "Injection payée par Solaire Coop" in texte
        assert "la vente à Solaire Coop" in texte
        # EDF OA n'apparait plus que dans sa propre definition du glossaire.
        assert texte.count("EDF OA") == 1
        assert "EDF OA (Obligation d'Achat)" in texte
    finally:
        detruire(win)


def test_chez_edf_oa_la_notice_ne_change_pas(qapp, tmp_path, monkeypatch):
    win = _fenetre(qapp, tmp_path, monkeypatch, lambda cfg: None)
    try:
        win._switch_view("aide")
        texte = " ".join(lbl.text() for lbl in
                         win.views["aide"].findChildren(QLabel))
        assert "Injection payée par EDF OA" in texte
        assert "la vente à EDF OA" in texte
    finally:
        detruire(win)


# ── Part HC de l'autoconsommation : 0 % par defaut (28/09/2026) ─────────────

def _sans_part_hc(cfg):
    cfg["tarifs_reseau"]["contrat_hphc"].pop("part_hc_autoconso", None)


def test_sans_part_hc_declaree_les_calculs_prennent_zero(tmp_path, monkeypatch):
    # Decision d'Andre : 0 partout. Le code prenait 20 %, le modele ecrit 0.
    data = _donnees(tmp_path, monkeypatch, _sans_part_hc)
    assert data.octopus.part_hc_autoconso == 0.0


def test_sans_part_hc_declaree_les_parametres_affichent_zero(
        qapp, tmp_path, monkeypatch):
    win = _fenetre(qapp, tmp_path, monkeypatch, _sans_part_hc)
    try:
        textes = _textes(win, "settings")
        assert "0,0\xa0%" in textes
        assert "20,0\xa0%" not in textes
    finally:
        detruire(win)


def _apres_midi_sans_part(cfg):
    contrat = cfg["tarifs_reseau"]["contrat_hphc"]
    contrat.pop("part_hc_autoconso", None)
    contrat["plages_hc"] = ["23:56-05:26", "14:26-16:56"]


def test_sans_part_declaree_les_calculs_prennent_l_estimation(
        tmp_path, monkeypatch):
    data = _donnees(tmp_path, monkeypatch, _apres_midi_sans_part)
    assert data.octopus.part_hc_autoconso == 0.24


def test_parametres_disent_que_la_part_est_estimee(qapp, tmp_path, monkeypatch):
    win = _fenetre(qapp, tmp_path, monkeypatch, _apres_midi_sans_part)
    try:
        textes = _textes(win, "settings")
        assert "24,0\xa0%" in textes and "ESTIM" in textes
    finally:
        detruire(win)
