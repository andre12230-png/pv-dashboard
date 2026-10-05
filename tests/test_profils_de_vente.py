"""Ce que voient ceux qui ne vendent pas, ou plus (audit du 04/10/2026).

Sans vente : Comparer affichait « Vente 0,00 € · stable », la Repartition un
ruban « Vendu au réseau » et une injection a « +0,00 € », Parametres une
carte « Contrat OA », la page TVA des « ventes autoliquidées ». Contrat
termine : la carte de vente gardait « à 0,1000 €/kWh ».

Donnees inventees : modele livre (3 kWc, contrat depuis le 01/01/2024),
20 kWh produits, 12 injectes, 5 achetes par jour.

    py -m pytest tests/test_profils_de_vente.py
"""
from __future__ import annotations

import pandas as pd
import pytest
import yaml

pytest.importorskip("PySide6")

from conftest import detruire  # noqa: E402
from PySide6.QtCore import QCoreApplication, QEvent, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QTableWidget  # noqa: E402

import app_desktop  # noqa: E402
import data_loaders as dl  # noqa: E402
from gui_widgets import MplCanvas  # noqa: E402

JOURS = pd.date_range("2024-01-01", "2025-01-10", freq="D")
JOURNEES = "".join(f"{j:%d/%m/%Y};20;12;5;2;3\n" for j in JOURS)


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def fenetre(qapp, tmp_path, monkeypatch):
    """Fabrique : fenetre(modif) ouvre l'appli avec config.yaml modifie."""
    ouvertes = []

    def ouvrir(modif):
        cfg = yaml.safe_load(app_desktop.CONFIG_PATH.read_text(encoding="utf-8"))
        modif(cfg)
        (tmp_path / "config.yaml").write_text(
            yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
        monkeypatch.setattr(app_desktop, "BASE_DIR", tmp_path)
        monkeypatch.setattr(app_desktop, "CONFIG_PATH", tmp_path / "config.yaml")
        monkeypatch.setattr(app_desktop, "CONFIG_LOCAL_PATH",
                            tmp_path / "config-local.yaml")
        (tmp_path / "Releves-pv.csv").write_text(
            ";".join(dl.RELEVES_HEADER) + "\n" + JOURNEES, encoding="utf-8")
        data = app_desktop.build_dataset(app_desktop.load_config())
        prefs = QSettings(str(tmp_path / "prefs.ini"),
                          QSettings.Format.IniFormat)
        w = app_desktop.MainWindow(data, prefs)
        ouvertes.append(w)
        return w

    yield ouvrir
    for w in ouvertes:
        detruire(w)


def _sans_vente(cfg):
    cfg["oa"]["type"] = "aucune"
    cfg["tva_lasm"] = {"taux": 0.20, "periodes": [
        {"debut": "2024-01-01", "fin": None, "prix_ht": 0.15, "accise": 0.03}]}


def _textes(win, cle, periode):
    win._switch_view(cle)
    win._appliquer_periode(periode)
    # Les widgets de l'affichage precedent ne sont detruits qu'au prochain
    # tour de Qt : sans cela, on lirait aussi leurs textes.
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    vue = win.views[cle]
    morceaux = [lbl.text() for lbl in vue.findChildren(QLabel)]
    for table in vue.findChildren(QTableWidget):
        for r in range(table.rowCount()):
            item = table.item(r, 0)
            if item is not None:
                morceaux.append(item.text())
    for canvas in vue.findChildren(MplCanvas):
        for ax in canvas.fig.axes:
            morceaux += [t.get_text() for t in ax.texts]
    return " | ".join(morceaux)


def test_sans_vente_comparer_n_a_pas_de_ligne_vente(fenetre):
    win = fenetre(_sans_vente)
    textes = _textes(win, "comparaison", "year-2025")
    assert "  Vente" not in textes


def test_sans_vente_la_repartition_ne_parle_pas_de_vente(fenetre):
    win = fenetre(_sans_vente)
    textes = _textes(win, "categories", "year-2024")
    assert "Vendu au réseau" not in textes
    assert "Injecté, non payé" in textes


def test_sans_vente_les_parametres_n_ont_pas_de_contrat_oa(fenetre):
    win = fenetre(_sans_vente)
    textes = _textes(win, "settings", "all")
    assert "CONTRAT OA" not in textes.upper()


def test_sans_vente_la_tva_ne_parle_pas_de_ventes(fenetre):
    win = fenetre(_sans_vente)
    textes = _textes(win, "tva", "all")
    assert "autoliquidées" not in textes
    assert "autofacturations" not in textes


def test_contrat_termine_la_carte_ne_donne_plus_de_prix(fenetre):
    def court(cfg):
        cfg["oa"]["duree_contrat_annees"] = 1     # fin le 01/01/2025
    win = fenetre(court)
    textes = _textes(win, "dashboard", "month-2025-01")
    assert "0,1000 €/kWh" not in textes
    assert "contrat terminé le 01/01/2025" in textes


def test_une_projection_au_dela_du_contrat_le_dit(fenetre):
    """La date de remboursement suppose que la vente continue au meme prix ;
    au-dela de la fin du contrat, il faut le dire."""
    def court(cfg):
        cfg["oa"]["duree_contrat_annees"] = 1     # fin le 01/01/2025
    win = fenetre(court)
    for cle in ("dashboard", "accounts"):
        textes = _textes(win, cle, "all")
        assert "après la fin du contrat, le 01/01/2025" in textes, cle


@pytest.fixture
def remet_le_nom_d_annee():
    """Le nom de l'annee de contrat est un reglage du module : on le remet
    a « OA » apres le test, pour ne pas deteindre sur les suivants."""
    yield
    from views._helpers import definir_acheteur
    definir_acheteur("EDF OA")


def test_un_autre_acheteur_n_a_plus_d_annees_oa(fenetre, remet_le_nom_d_annee):
    """Audit du 04/10/2026 : avec un autre acheteur, le menu, les titres,
    les barres et le selecteur gardaient « Années OA », « OA #1 »."""
    from views._helpers import libelle_periode

    def autre(cfg):
        cfg["oa"]["acheteur"] = "Solaire Coop"
    win = fenetre(autre)
    boutons = " ".join(b.text() for b in win.nav_buttons.values())
    assert "Années de contrat" in boutons and "Années OA" not in boutons
    textes = _textes(win, "oa", "all")
    assert "OA #" not in textes and "année OA" not in textes.lower()
    assert libelle_periode("oa-2") == "Année de contrat n° 2"
    entetes = [win.views["oa"].findChildren(QTableWidget)[-1]
               .horizontalHeaderItem(0).text()]
    assert entetes == ["Année"]


def test_edf_oa_garde_ses_annees_oa(fenetre):
    from views._helpers import libelle_periode
    fenetre(lambda cfg: None)
    assert libelle_periode("oa-2") == "Année OA #2"


def test_des_libelles_entiers_et_un_seul_nom_par_mesure(fenetre):
    """Journal du 01/10/2026 : « Abonn. » dix fois, « Plages HC », « Durée
    prime » dans Parametres ; « Couverture solaire » en Repartition pour la
    meme mesure que l'« Autoproduction » du tableau de bord."""
    win = fenetre(lambda cfg: None)
    parametres = _textes(win, "settings", "all")
    for abrege in ("ABONN.", "PLAGES HC", "DURÉE PRIME"):
        assert abrege not in parametres.upper(), abrege
    repartition = _textes(win, "categories", "year-2024").upper()
    assert "COUVERTURE SOLAIRE" not in repartition
    assert "AUTOPRODUCTION" in repartition
