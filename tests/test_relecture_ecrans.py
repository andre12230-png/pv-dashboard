"""Relecture de tous les ecrans (30/09/2026) : ce que chaque page doit tenir.

Trois journees inventees, modele livre (3 kWc, contrat depuis le 01/01/2024).

    py -m pytest tests/test_relecture_ecrans.py
"""
from __future__ import annotations

import pytest
import yaml

pytest.importorskip("PySide6")

from conftest import detruire  # noqa: E402
from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QLabel,
    QPushButton,
    QTableWidget,
)

import app_desktop  # noqa: E402
import data_loaders as dl  # noqa: E402
from gui_theme import LIGHT  # noqa: E402
from gui_widgets import MplCanvas  # noqa: E402

JOURNEES = ("01/09/2026;20;12;5;2;3\n"
            "02/09/2026;18;10;6;3;3\n"
            "03/09/2026;19;11;4;2;2\n")


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
    detruire(w)


def _textes(win, cle: str) -> str:
    win._switch_view(cle)
    return " | ".join(lbl.text() for lbl in win.views[cle].findChildren(QLabel))


def _bandeaux(win, cle: str) -> list[str]:
    win._switch_view(cle)
    return [e.text() for e in win.views[cle].findChildren(QLabel, "CardHeader")]


# --- Saisie quotidienne -------------------------------------------------------

def test_saisie_le_bouton_d_import_dit_achat_au_reseau(win):
    """« Importer conso / injection… » : une abreviation, et le nom choisi
    pour ce flux est « Achat au réseau »."""
    win._switch_view("saisie")
    boutons = [b.text() for b in win.views["saisie"].findChildren(QPushButton)]
    assert "Importer achat au réseau / injection..." in boutons
    assert not [b for b in boutons if "conso" in b.lower()]


def test_saisie_la_ligne_orangee_est_expliquee(win):
    """La couleur ne porte jamais seule le sens : la phrase d'en-tete dit ce
    qu'est la ligne sur fond orange. Et « Modifiez », pas « Éditez »."""
    textes = _textes(win, "saisie")
    assert "fond orangé" in textes
    assert "Éditez" not in textes and "Modifiez" in textes


# --- Releves journaliers ------------------------------------------------------

def test_releves_le_bandeau_ne_redit_pas_la_page(win):
    assert "RELEVÉS JOURNALIERS" not in _bandeaux(win, "transactions")


def test_releves_les_nombres_sont_alignes_a_droite(win):
    """La charte : montants et chiffres alignes a droite. Ils etaient
    centres, en-tetes compris."""
    win._switch_view("transactions")
    tableau, totaux = win.views["transactions"].findChildren(QTableWidget)[:2]
    for table in (tableau, totaux):
        for col in range(1, table.columnCount()):
            assert table.item(0, col).textAlignment() & Qt.AlignRight, col
    for col in range(1, tableau.columnCount()):
        assert tableau.horizontalHeaderItem(col).textAlignment() & Qt.AlignRight


# --- Page du fournisseur ------------------------------------------------------

def test_fournisseur_la_page_porte_le_nom_du_menu(win):
    """Le menu disait « Mon fournisseur ou EDF », la page « Mon offre HP/HC
    ou EDF Tarif Bleu » : on doit arriver la ou l'on a clique."""
    win._switch_view("octopus_edf")
    assert win.title_lbl.text() in win.nav_buttons["octopus_edf"].text()
    # Les noms complets des deux offres restent dits, en sous-titre.
    assert "face à" in win.sub_lbl.text()
    assert win.data.fournisseur_reference[1] in win.sub_lbl.text()


def test_fournisseur_la_tuile_du_contrat_n_accorde_pas_au_hasard(win):
    """« Mon offre HP/HC (actuel) » : l'accord dependait du nom de l'offre."""
    textes = _textes(win, "octopus_edf")
    assert "(ACTUEL)" not in textes.upper()
    assert "VOTRE CONTRAT" in textes.upper()


# --- Statistiques --------------------------------------------------------------

def test_statistiques_les_titres_disent_ce_que_montrent_les_graphiques(win):
    bandeaux = _bandeaux(win, "stats")
    assert "ÉNERGIE PAR ANNÉE CIVILE" in bandeaux        # quatre series
    assert "PRODUCTION MENSUELLE, ANNÉE PAR ANNÉE" in bandeaux
    assert not [b for b in bandeaux if "MULTI" in b]


def test_statistiques_l_annee_partielle_garde_son_unite(win):
    textes = _textes(win, "stats")
    assert "kWh/kWc — du " in textes


# --- Graphiques en euros ---------------------------------------------------------

@pytest.mark.parametrize("cle", ["accounts", "octopus_edf"])
def test_pas_de_symbole_euro_couche_le_long_de_l_axe(win, cle):
    win._switch_view(cle)
    axes = [ax for canvas in win.views[cle].findChildren(MplCanvas)
            for ax in canvas.fig.axes]
    assert axes
    assert all(ax.get_ylabel() != "€" for ax in axes)


def test_synthese_l_axe_du_remboursement_est_en_euros(win):
    win._switch_view("accounts")
    canvas = win.views["accounts"].findChildren(MplCanvas)[0]
    canvas.draw()
    ax = canvas.fig.axes[0]
    graduations = [t.get_text() for t in ax.get_yticklabels() if t.get_text()]
    assert graduations and all(g.endswith("\xa0€") for g in graduations)


# --- Textes longs ----------------------------------------------------------------

def test_aucune_page_ne_coupe_un_texte(win, qapp):
    """Generalise le test de la Notice : tout texte qui passe a la ligne
    recoit la hauteur que sa largeur reelle demande, sur toutes les pages."""
    win.setAttribute(Qt.WA_DontShowOnScreen, True)
    for largeur, hauteur in ((1280, 900), (1366, 728)):
        win.resize(largeur, hauteur)
        win.show()
        for cle in win.views:
            win._switch_view(cle)
            for _ in range(10):
                qapp.processEvents()
            coupes = [(lbl.text()[:30], lbl.height(), lbl.heightForWidth(lbl.width()))
                      for lbl in win.views[cle].findChildren(QLabel)
                      if lbl.wordWrap() and lbl.isVisible()
                      and lbl.height() < lbl.heightForWidth(lbl.width()) - 2]
            assert not coupes, (largeur, cle, coupes)


def test_les_phrases_d_en_tete_passent_a_la_ligne(win):
    """Une phrase d'en-tete tenue sur une seule ligne poussait la page
    Parametres hors de la fenetre (barre de defilement horizontale, cartes
    coupees a droite) des qu'elle etait un peu longue. Toute phrase de plus
    de 60 signes doit pouvoir passer a la ligne.

    (On ne mesure pas ici la largeur des pages : les polices de remplacement
    de l'environnement de test sont presque deux fois plus larges que les
    vraies. La mesure se fait a l'image, vraies polices.)"""
    rigides = []
    for cle, vue in win.views.items():
        win._switch_view(cle)
        rigides += [(cle, lbl.text()[:40]) for lbl in vue.findChildren(QLabel)
                    if len(lbl.text()) > 60 and not lbl.wordWrap()
                    and lbl.objectName() in ("SectionSub", "")]
    assert not rigides, rigides


@pytest.mark.parametrize("cle, debut", [
    ("accounts", "Le temps de retour suppose"),
    ("octopus_edf", "Le coût "),
])
def test_les_notes_se_lisent_en_lignes_courtes(win, cle, debut):
    win._switch_view(cle)
    notes = [lbl for lbl in win.views[cle].findChildren(QLabel)
             if lbl.text().startswith(debut)]
    assert len(notes) == 1
    assert notes[0].maximumWidth() <= 780


# --- Comparer a l'an passe ---------------------------------------------------------

def test_pas_de_pourcentage_sur_un_bilan_negatif():
    """« -7,22 € (-73,3 %) » pour un bilan passe de -9,86 € a -17,08 € : un
    pourcentage calcule sur une perte ne se comprend pas. L'ecart en euros
    suffit."""
    from views._helpers import fmt_eur, variation
    texte, _couleur = variation(-7.22, -9.86, fmt_eur, +1, LIGHT)
    assert "%" not in texte and "7,22" in texte
    # Sur une base positive, le pourcentage reste.
    texte, _couleur = variation(-16.9, 254.0, fmt_eur, +1, LIGHT)
    assert "%" in texte


# --- Repartition energie -------------------------------------------------------------

def test_repartition_dit_l_an_passe(win):
    win._appliquer_periode("month-2026-09")
    textes = _textes(win, "categories").upper()
    assert "L'ANNÉE PRÉCÉDENTE" not in textes


# --- Parametres ------------------------------------------------------------------------

def test_parametres_la_phrase_d_en_tete_est_une_phrase(win):
    textes = _textes(win, "settings")
    assert "Bouton « Modifier mes réglages », ou" not in textes
    assert "Pour changer ces valeurs" in textes


def test_parametres_le_bouton_a_l_allure_des_autres(win):
    win._switch_view("settings")
    bouton = next(b for b in win.views["settings"].findChildren(QPushButton)
                  if b.text() == "Modifier mes réglages")
    assert bouton.objectName() == "ActionBtn"


def test_releves_les_euros_portent_leur_signe(win):
    """Charte : la couleur ne porte jamais seule le sens. « Vente +
    économies » s'ecrivait 0,95 en vert, « Achat au réseau » 2,40 en rouge,
    sans signe (audit du 08/10/2026)."""
    win._switch_view("transactions")
    tableau, totaux = win.views["transactions"].findChildren(QTableWidget)[:2]
    n = tableau.columnCount()
    credit, debit = n - 3, n - 2
    for r in range(tableau.rowCount()):
        texte_c = tableau.item(r, credit).text()
        texte_d = tableau.item(r, debit).text()
        assert texte_c == "0,00" or texte_c.startswith("+"), texte_c
        assert texte_d == "0,00" or texte_d.startswith("-"), texte_d
    assert totaux.item(0, debit).text().startswith("-")
