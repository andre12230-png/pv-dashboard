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

from conftest import detruire  # noqa: E402
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
    detruire(w)


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
    inj = table.item(ligne, entetes.index("Injection\n(kWh)")).text()
    revenu = table.item(ligne, entetes.index("Revenu\n(€)")).text()
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
    actuel = next(v for k, v in valeurs.items() if "votre contrat" in k.lower())
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


def test_la_repartition_ecrit_lisiblement(win):
    """30/09/2026 : la colonne « Impact » et le « Bilan » s'ecrivaient dans
    les couleurs vives des graphiques (3,2 a 3,9 pour 1). Tout texte colore
    de la page doit tenir 4,5 sur l'ivoire des cartes."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from test_contraste import contraste

    from gui_theme import LIGHT
    win._switch_view("categories")
    trouves = []
    for lbl in win.views["categories"].findChildren(QLabel):
        couleur = re.search(r"(?<![-\w])color:\s*(#[0-9A-Fa-f]{6})",
                            lbl.styleSheet())
        if lbl.text() and couleur:
            rapport = contraste(couleur.group(1), LIGHT["bg_carte"])
            if rapport < 4.5:
                trouves.append(f"{lbl.text()!r} {couleur.group(1)} {rapport:.2f}")
    assert not trouves, trouves


def test_annees_oa_les_en_tetes_ne_sont_pas_coupes(win):
    """30/09/2026 : en toutes lettres, « Autoconsommation » etait coupe
    (« utoconsommatio ») : les colonnes se partageaient la largeur a parts
    egales. Elles la partagent toujours (sinon un grand vide, audit du
    14/09/2026), sauf celle-la, qui prend la largeur de son en-tete."""
    from PySide6.QtWidgets import QHeaderView
    win._switch_view("oa")
    table = win.views["oa"].findChildren(QTableWidget)[0]
    entete = table.horizontalHeader()
    noms = [table.horizontalHeaderItem(j).text() for j in range(table.columnCount())]
    colonne = next(j for j, nom in enumerate(noms) if nom.startswith("Autoconsommation"))
    assert entete.sectionResizeMode(colonne) == QHeaderView.ResizeToContents
    assert entete.sectionResizeMode(colonne + 1) == QHeaderView.Stretch
    # La prime « (180,00 à venir) » prend elle aussi la largeur de son texte.
    prime = next(j for j, nom in enumerate(noms) if nom.startswith("Prime"))
    assert entete.sectionResizeMode(prime) == QHeaderView.ResizeToContents


def test_annees_oa_les_numeros_ne_ressemblent_pas_a_des_liens(win):
    """30/09/2026 : « #1 » s'ecrivait en bleu gras, comme un lien cliquable
    (meme defaut que les annees de la page TVA)."""
    from gui_theme import LIGHT
    win._switch_view("oa")
    table = win.views["oa"].findChildren(QTableWidget)[0]
    for i in range(table.rowCount()):
        couleur = table.item(i, 0).foreground().color().name()
        assert couleur != LIGHT["primary"].lower()


def test_annees_oa_pas_de_bande_vide_sous_le_tableau(win):
    win._switch_view("oa")
    table = win.views["oa"].findChildren(QTableWidget)[0]
    attendu = (table.horizontalHeader().sizeHint().height()
               + sum(table.rowHeight(r) for r in range(table.rowCount()))
               + 2 * table.frameWidth())
    assert table.height() == attendu
    # Toutes les lignes ont la meme hauteur (« à venir » ne passe pas a la ligne).
    assert len({table.rowHeight(r) for r in range(table.rowCount())}) == 1


def test_milliers_separes_dans_les_annees_oa():
    """« 2354,4 » : les milliers se separent, comme partout ailleurs."""
    from views.oa import nombre_fr
    assert nombre_fr(2354.4) == "2 354,4"
    assert nombre_fr(856.25) == "856,2" or nombre_fr(856.25) == "856,3"


def test_un_bilan_nul_ne_prend_ni_signe_ni_couleur():
    """Relevés : « +0,00 » en vert pour une journée à l'équilibre."""
    from views.transactions import texte_bilan
    assert texte_bilan(0.004) == ("0,00", "text_primary")
    assert texte_bilan(1.27) == ("+1,27", "credit")
    assert texte_bilan(-1.27) == ("-1,27", "debit")


def test_la_notice_se_lit_en_lignes_courtes(win):
    """Des lignes de ~170 signes a 1280 px : le texte de chaque rubrique ne
    depasse plus 780 px de large (~110 signes)."""
    win._switch_view("aide")
    textes = [lbl for lbl in win.views["aide"].findChildren(QLabel)
              if lbl.wordWrap() and len(lbl.text()) > 300]
    assert textes
    assert all(lbl.maximumWidth() <= 780 for lbl in textes)


def test_la_notice_ne_coupe_pas_son_texte(win, qapp):
    """30/09/2026 : la largeur limitee a 780 px coupait la fin de presque
    toutes les rubriques — la hauteur etait calculee pour la largeur de la
    carte, plus grande, donc pour moins de lignes. Chaque texte doit recevoir
    la hauteur que sa largeur reelle demande."""
    from PySide6.QtCore import Qt
    win.setAttribute(Qt.WA_DontShowOnScreen, True)
    for largeur, hauteur in ((1280, 900), (1366, 728), (1920, 1040)):
        win.resize(largeur, hauteur)
        win.show()
        win._switch_view("aide")
        for _ in range(20):
            qapp.processEvents()
        coupes = []
        for lbl in win.views["aide"].findChildren(QLabel):
            if lbl.wordWrap() and lbl.isVisible():
                besoin = lbl.heightForWidth(lbl.width())
                if lbl.height() < besoin - 2:
                    coupes.append((lbl.text()[:30], lbl.height(), besoin))
        assert not coupes, (largeur, coupes)


def test_la_notice_ne_dit_pas_annee_suivante_a_tort(win):
    """Un contrat qui commence un 1er janvier court du 01/01 au 31/12 de la
    MEME annee : la notice ajoutait « de l'année suivante » a tous."""
    textes = _textes(win, "aide")
    assert "du 01/01 au 31/12" in textes
    assert "31/12 de l'année suivante" not in textes


def test_parametres_prix_de_rachat(win):
    """30/09/2026 : Mes reglages disait « Prix de rachat du kWh », Parametres
    « Prix d'achat du kWh ». Un nom par chose ; « achat » designe l'electricite
    achetee au reseau."""
    textes = _textes(win, "settings")
    assert "Prix de rachat du kWh" in textes
    assert "Prix d'achat du kWh" not in textes
