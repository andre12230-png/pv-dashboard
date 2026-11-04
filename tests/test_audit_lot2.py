"""Tests du lot 2 de l'audit indépendant du 04-11-2026 (D5, D10, D11,
U02, S01). Valeurs inventées et rondes, aucune donnée réelle."""
from __future__ import annotations

import json

import pytest

import data_loaders as dl

# ── D11 : une date de recharge avec fuseau horaire ────────────────────
#
# Le lecteur acceptait « 2026-01-10T22:00:00+01:00 », puis le comparait à un
# minuit sans fuseau : TypeError, et le chargement s'arrêtait.

def _recharges(tmp_path, debut, fin, kwh=8.0):
    chemin = tmp_path / "recharges.json"
    chemin.write_text(json.dumps({"recharges": [
        {"lieu": "maison", "kwh": kwh, "cout_eur": 2.0,
         "date": debut, "fin": fin}]}), encoding="utf-8")
    return str(chemin)


@pytest.mark.parametrize("debut, fin", [
    ("2026-01-10T22:00:00+01:00", "2026-01-11T02:00:00+01:00"),
    ("2026-01-10T21:00:00Z", "2026-01-11T01:00:00Z"),
    ("2026-01-10T22:00:00+01:00", "2026-01-11T02:00:00"),   # mélange
])
def test_date_avec_fuseau_ne_bloque_pas_la_lecture(tmp_path, debut, fin):
    out = dl.charger_recharges_ve(_recharges(tmp_path, debut, fin))
    # Toute l'énergie est comptée, répartie sur les jours de la charge.
    assert out["recharge_ve_kwh"].sum() == pytest.approx(8.0)
    assert out["recharge_ve_eur"].sum() == pytest.approx(2.0)
    assert {d.day for d in out.index} <= {10, 11}


def test_date_sans_fuseau_inchangee(tmp_path):
    out = dl.charger_recharges_ve(_recharges(
        tmp_path, "2026-01-10T22:00:00", "2026-01-11T02:00:00"))
    assert list(out["recharge_ve_kwh"]) == pytest.approx([4.0, 4.0])


def test_source_recharges_illisible_n_empeche_pas_l_ouverture(tmp_path, monkeypatch):
    """Une source facultative qui échoue est signalée, puis ignorée."""
    import app_desktop
    chemin = _recharges(tmp_path, "2026-01-10T22:00:00", "2026-01-11T02:00:00")

    def panne(_chemin):
        raise TypeError("erreur imprévue de lecture")
    monkeypatch.setattr(app_desktop.dl, "charger_recharges_ve", panne)
    cfg = {"sources": {"recharges_ve_json": chemin}}
    assert app_desktop._charger_recharges_ve(cfg) is None


# ── D10 : le nom de la feuille d'index dit la grandeur ────────────────
#
# Seul « prod » faisait reconnaître l'injection : une feuille « Injection »
# devenait de la consommation réseau, comme toute feuille au nom inconnu.

def _index_une_feuille(tmp_path, nom_feuille):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = nom_feuille
    ws["B17"] = "Date du tele-releve"
    ws["C17"] = "Index totalisateur (en kWh)"
    ws["B18"], ws["C18"] = "01/01/2026", 100.0
    ws["B19"], ws["C19"] = "02/01/2026", 110.0
    chemin = str(tmp_path / "Export_Index.xlsx")
    wb.save(chemin)
    return chemin


@pytest.mark.parametrize("nom", ["Injection", "Index_Injection", "Index_Prod"])
def test_feuille_d_injection_reconnue(tmp_path, nom):
    chemin = _index_une_feuille(tmp_path, nom)
    assert dl.parse_enedis_fichier(chemin) == {"Inj_Jour": {"01/01/2026": "10"}}


@pytest.mark.parametrize("nom", ["Consommation", "Soutirage",
                                 "Index_Cons_Calendriers_1"])
def test_feuille_de_consommation_reconnue(tmp_path, nom):
    chemin = _index_une_feuille(tmp_path, nom)
    assert dl.parse_enedis_fichier(chemin) == {
        "Conso_réseau_Jour": {"01/01/2026": "10"}}


@pytest.mark.parametrize("nom", ["Feuil1", "Production et consommation"])
def test_feuille_d_index_au_nom_inconnu_ou_ambigu_refusee(tmp_path, nom):
    chemin = _index_une_feuille(tmp_path, nom)
    with pytest.raises(ValueError, match="renommez"):
        dl.parse_enedis_fichier(chemin)


# ── D5 : un classeur heure par heure est refusé, comme le CSV ─────────

def _classeur_conso(tmp_path, lignes):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Export Consommation Quotidienne"
    ws.append(["Date", "Valeur (en kWh)"])
    for ligne in lignes:
        ws.append(list(ligne))
    chemin = str(tmp_path / "Export_energie_Consommation.xlsx")
    wb.save(chemin)
    return chemin


def test_classeur_horaire_refuse(tmp_path):
    from datetime import datetime
    chemin = _classeur_conso(tmp_path, [
        (datetime(2026, 1, 10, 12, 0), 2.0),
        (datetime(2026, 1, 10, 12, 30), 3.0)])
    with pytest.raises(ValueError, match="courbe de charge"):
        dl.parse_enedis_fichier(chemin)


def test_classeur_horaire_en_texte_refuse(tmp_path):
    chemin = _classeur_conso(tmp_path, [
        ("10/01/2026 12:00", 2.0), ("10/01/2026 12:30", 3.0)])
    with pytest.raises(ValueError, match="courbe de charge"):
        dl.parse_enedis_fichier(chemin)


def test_classeur_quotidien_toujours_accepte(tmp_path):
    from datetime import datetime
    chemin = _classeur_conso(tmp_path, [
        (datetime(2026, 1, 10), 2.0), (datetime(2026, 1, 11), 3.0)])
    assert dl.parse_enedis_fichier(chemin) == {
        "Conso_réseau_Jour": {"10/01/2026": "2", "11/01/2026": "3"}}


# ── S01 : une copie de secours ratée n'est plus passée sous silence ───

CSV_DEPART = (
    "Date;Prod_Jour;Inj_Jour;Conso_réseau_Jour;Conso_HC;Conso_HP\n"
    "01/05/2026;20;15;3;1;2\n"
    "02/05/2026;18;12;2;1;1\n"
)


def _lignes_plus_une(chemin):
    lignes = dl.read_releves_raw(chemin)
    lignes.append({"Date": "03/05/2026", "Prod_Jour": "19", "Inj_Jour": "13",
                   "Conso_réseau_Jour": "2", "Conso_HC": "1", "Conso_HP": "1"})
    return lignes


def test_ecriture_normale_ne_signale_rien(tmp_path):
    chemin = tmp_path / "Releves-pv.csv"
    chemin.write_text(CSV_DEPART, encoding="utf-8")
    manques = dl.write_releves_raw(str(chemin), _lignes_plus_une(str(chemin)))
    assert manques == []
    assert (tmp_path / "Releves-pv.csv.bak").exists()


def test_copie_de_secours_ratee_est_signalee(tmp_path, monkeypatch):
    chemin = tmp_path / "Releves-pv.csv"
    chemin.write_text(CSV_DEPART, encoding="utf-8")

    def copie_impossible(*_a, **_k):
        raise PermissionError(13, "Accès refusé")
    monkeypatch.setattr(dl.shutil, "copy2", copie_impossible)

    manques = dl.write_releves_raw(str(chemin), _lignes_plus_une(str(chemin)))
    # Les nouvelles données sont bien enregistrées…
    assert "03/05/2026" in chemin.read_text(encoding="utf-8")
    # … mais l'absence de copie de secours est dite.
    assert manques and "copie" in manques[0]


def test_saisie_previent_quand_la_copie_de_secours_manque(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from types import SimpleNamespace

    from PySide6.QtWidgets import QApplication, QMessageBox

    import gui_theme
    import views.saisie as saisie_module
    QApplication.instance() or QApplication([])
    chemin = tmp_path / "Releves-pv.csv"
    chemin.write_text(CSV_DEPART, encoding="utf-8")
    data = SimpleNamespace(releves_path=str(chemin), current_period="all",
                           puissance_kwc=6.0)
    vue = saisie_module.SaisieView(data, gui_theme.LIGHT)
    vue.populate("all")
    vrai = dl.write_releves_raw
    monkeypatch.setattr(saisie_module.dl, "write_releves_raw",
                        lambda *a, **k: (vrai(*a, **k),
                                         ["la copie datée dans backups"])[1])
    titres = []
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda _p, titre, texte, *a, **k: titres.append(texte)
                        or QMessageBox.Ok)
    vue.table.item(1, vue.COLS.index("Prod_Jour")).setText("21")

    assert vue._enregistrer() is True
    assert titres and "bien enregistrés" in titres[0]
    assert "backups" in titres[0]


# ── U02 : fermer « Mes réglages » ne perd plus les modifications ──────

@pytest.fixture
def reglages(monkeypatch):
    """Fenêtre « Mes réglages » ; la question posée à la fermeture est
    remplacée par une réponse choisie dans le test."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QMessageBox

    import fenetre_reglages
    from tests.test_reglages import VALEURS_FENETRE
    QApplication.instance() or QApplication([])
    enregistrees = []
    questions = []
    reponse = {"bouton": QMessageBox.Cancel}

    def demander(_parent, titre, _message):
        questions.append(titre)
        return reponse["bouton"]
    monkeypatch.setattr(fenetre_reglages, "demander_enregistrement", demander)
    fenetre = fenetre_reglages.FenetreReglages(
        dict(VALEURS_FENETRE), enregistrees.append)
    return fenetre, enregistrees, questions, reponse


def test_fermer_sans_rien_changer_ne_demande_rien(reglages):
    fenetre, enregistrees, questions, _ = reglages
    fenetre.reject()                       # Échap, croix ou Annuler
    assert questions == [] and fenetre.result() == 0


def test_fermer_apres_un_changement_demande_et_annuler_garde_ouvert(reglages):
    from PySide6.QtWidgets import QMessageBox
    fenetre, enregistrees, questions, reponse = reglages
    fenetre.show()
    fenetre.nom.setText("Fournisseur fictif")
    reponse["bouton"] = QMessageBox.Cancel
    fenetre.reject()
    assert questions == ["Réglages non enregistrés"]
    assert fenetre.isVisible() and enregistrees == []     # rien de perdu
    assert fenetre.nom.text() == "Fournisseur fictif"
    fenetre.hide()


def test_fermer_et_enregistrer(reglages):
    from PySide6.QtWidgets import QDialog, QMessageBox
    fenetre, enregistrees, _questions, reponse = reglages
    fenetre.nom.setText("Fournisseur fictif")
    reponse["bouton"] = QMessageBox.Save
    fenetre.reject()
    assert [v["nom"] for v in enregistrees] == ["Fournisseur fictif"]
    assert fenetre.result() == QDialog.Accepted


def test_fermer_sans_enregistrer(reglages):
    from PySide6.QtWidgets import QMessageBox
    fenetre, enregistrees, _questions, reponse = reglages
    fenetre.nom.setText("Fournisseur fictif")
    reponse["bouton"] = QMessageBox.Discard
    fenetre.reject()
    assert enregistrees == [] and fenetre.result() == 0


def test_avec_recalages_fermer_sans_changer_ne_demande_rien(monkeypatch):
    pytest.importorskip("PySide6")
    from datetime import date

    from PySide6.QtWidgets import QApplication

    import fenetre_reglages
    import reglages as rg
    from tests.test_reglages import VALEURS_FENETRE
    QApplication.instance() or QApplication([])
    questions = []
    monkeypatch.setattr(fenetre_reglages, "demander_enregistrement",
                        lambda *a: questions.append(a[1]))
    donnes = rg.recalages_vides()
    donnes["injection_facturee"].append(
        {"debut": date(2024, 7, 1), "fin": date(2025, 6, 30),
         "total_kwh": 3000.0, "source": "facture fictive"})
    fenetre = fenetre_reglages.FenetreReglages(
        dict(VALEURS_FENETRE), lambda v: None, None, recalages=donnes,
        enregistrer_recalages=lambda r: None)
    fenetre.reject()
    assert questions == []
    # Retirer un recalage est un changement : la question vient.
    fenetre2 = fenetre_reglages.FenetreReglages(
        dict(VALEURS_FENETRE), lambda v: None, None, recalages=donnes,
        enregistrer_recalages=lambda r: None)
    ligne = fenetre2._lignes.itemAt(0).widget()
    fenetre2._retirer_ligne(ligne)
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(fenetre_reglages, "demander_enregistrement",
                        lambda *a: questions.append(a[1]) or QMessageBox.Cancel)
    fenetre2.reject()
    assert questions == ["Réglages non enregistrés"]
