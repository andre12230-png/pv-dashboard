"""Cartes a en-tete bleute, comme celles du Bilan de Pecule (29/09/2026).

Avant : le titre d'une carte etait un petit texte gris pose AU-DESSUS d'elle
(ou dans son coin). Pecule et Recharges VE ouvrent chaque carte par un
bandeau degrade bleu, titre en capitales bleu nuit. Card(titre=...) le
construit ; les titres de page et ceux qui coiffent un GROUPE de tuiles
restent au-dessus, comme dans Pecule. Releves inventes (demo_releves).

    py -m pytest tests/test_cartes_titrees.py
"""
from __future__ import annotations

import re
from datetime import date, timedelta

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

import app_desktop  # noqa: E402
from gui_theme import LIGHT, qss_for  # noqa: E402
from gui_widgets import Card  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_une_carte_titree_ouvre_par_son_bandeau(qapp):
    carte = Card(titre="Détail par poste", sous_titre="une précision")
    entete = carte.findChild(QLabel, "CardHeader")
    assert entete is not None and entete.text() == "DÉTAIL PAR POSTE"
    # Le bandeau est le premier element, bord a bord.
    assert carte.layout().itemAt(0).widget() is entete
    assert carte.layout().contentsMargins().top() == 0
    # Le contenu va dans le corps ; le sous-titre y est deja.
    assert carte.corps is not None
    sous = carte.findChild(QLabel, "SectionSub")
    assert sous is not None and sous.text() == "une précision"


def test_une_carte_sans_titre_reste_vide(qapp):
    """Les cartes existantes posent elles-memes leur disposition."""
    carte = Card()
    assert carte.layout() is None
    assert carte.corps is None


def test_le_bandeau_a_les_couleurs_de_pecule():
    qss = qss_for(LIGHT)
    bloc = re.search(r"QLabel#CardHeader\s*\{([^}]*)\}", qss)
    assert bloc, "le style du bandeau de carte manque"
    texte = bloc.group(1)
    for couleur in ("#E8EEF7", "#C9D6E8", "#1F3A6B", "#B0BFD3"):
        assert couleur in texte.upper(), couleur
    assert "qlineargradient" in texte


@pytest.fixture(scope="module")
def fenetre(qapp, tmp_path_factory):
    """La fenetre, sur des releves inventes de 2024 a hier."""
    import shutil

    from demo_releves import ecrire_releves_demo
    dossier = tmp_path_factory.mktemp("cartes")
    shutil.copy2(app_desktop.CONFIG_PATH, dossier / "config.yaml")
    ecrire_releves_demo(dossier / "Releves-pv.csv",
                        fin=date.today() - timedelta(days=1))
    anciens = (app_desktop.BASE_DIR, app_desktop.CONFIG_PATH,
               app_desktop.CONFIG_LOCAL_PATH)
    # build_dataset change un reglage global du module calculations (date de
    # bascule HP/HC). Le filet de conftest ne le remet qu'apres chaque TEST :
    # cette preparation, commune au fichier, doit le remettre elle-meme, sans
    # quoi il deborde sur les fichiers suivants (vu le 29/09/2026 :
    # test_nouvel_utilisateur echouait apres celui-ci).
    import calculations
    bascule = calculations.CUTOFF_OCTOPUS
    app_desktop.BASE_DIR = dossier
    app_desktop.CONFIG_PATH = dossier / "config.yaml"
    app_desktop.CONFIG_LOCAL_PATH = dossier / "config-local.yaml"
    try:
        data = app_desktop.build_dataset(app_desktop.load_config())
        prefs = QSettings(str(dossier / "prefs.ini"), QSettings.Format.IniFormat)
        w = app_desktop.MainWindow(data, prefs)
        yield w
        w.close()
    finally:
        (app_desktop.BASE_DIR, app_desktop.CONFIG_PATH,
         app_desktop.CONFIG_LOCAL_PATH) = anciens
        calculations.CUTOFF_OCTOPUS = bascule


def _entetes(fenetre, vue: str, periode: str | None = None) -> list[str]:
    fenetre._switch_view(vue)
    if periode:
        fenetre._appliquer_periode(periode)
    return [e.text() for e in fenetre.views[vue].findChildren(QLabel, "CardHeader")]


def _titres_au_dessus(fenetre, vue: str) -> list[str]:
    return [e.text() for e in fenetre.views[vue].findChildren(QLabel, "SectionTitle")]


@pytest.mark.parametrize("vue, periode, attendus", [
    ("dashboard", None, ["CIRCULATION DE L'ÉNERGIE",
                         "REMBOURSEMENT DE L'INSTALLATION",
                         "PRODUCTION JOUR PAR JOUR"]),
    ("categories", f"year-{date.today().year - 1}",
     ["CIRCULATION DE L'ÉNERGIE", "DÉTAIL PAR POSTE"]),
    ("accounts", "all", ["REMBOURSEMENT DE L'INSTALLATION"]),
    ("transactions", "all", ["RELEVÉS JOURNALIERS"]),
    ("aide", None, ["SOMMAIRE", "À QUOI SERT L'APPLICATION", "GLOSSAIRE"]),
    ("settings", None, ["INSTALLATION", "RECALAGES SUR FACTURES"]),
    ("stats", None, ["PRODUCTION PAR ANNÉE CIVILE",
                     "PRODUCTION MENSUELLE MULTI-ANNÉES"]),
    ("oa", None, ["PRODUCTION, AUTOCONSOMMATION ET INJECTION PAR ANNÉE OA",
                  "DÉTAIL PAR ANNÉE OA"]),
    ("octopus_edf", None, ["COÛT MENSUEL COMPARÉ (€)", "HYPOTHÈSES DU CALCUL"]),
])
def test_les_titres_de_carte_sont_dans_leur_bandeau(fenetre, vue, periode,
                                                     attendus):
    entetes = _entetes(fenetre, vue, periode)
    for titre in attendus:
        assert titre in entetes, f"{vue} : « {titre} » absent de {entetes}"
        # ... et plus au-dessus de la carte.
        assert titre not in _titres_au_dessus(fenetre, vue), (vue, titre)


def test_les_deux_chiffres_du_haut_sont_des_tuiles(fenetre):
    """29/09/2026 (option B de l'auteur) : Autoproduction et Production sont
    des chiffres cles, comme les tuiles du bilan : titre en petites
    capitales dans la tuile, trait jaune (le soleil) de 3 px en haut."""
    from PySide6.QtWidgets import QFrame
    fenetre._switch_view("dashboard")
    vue = fenetre.views["dashboard"]
    trouves = {}
    for tuile in vue.findChildren(QFrame):
        if tuile.property("role") != "kpi":
            continue
        for libelle in tuile.findChildren(QLabel, "KpiLabel"):
            if libelle.text() == "AUTOPRODUCTION":
                trouves["autoproduction"] = tuile
            elif libelle.text().startswith("PRODUCTION —"):
                trouves["production"] = tuile
    assert set(trouves) == {"autoproduction", "production"}, trouves
    for tuile in trouves.values():
        assert tuile.property("variant") == "prod"


def test_un_titre_de_groupe_de_tuiles_reste_au_dessus(fenetre):
    """« Bilan financier de la période » coiffe quatre tuiles : il reste
    un titre de section, comme dans Pecule."""
    fenetre._switch_view("dashboard")
    assert "BILAN FINANCIER DE LA PÉRIODE" in _titres_au_dessus(
        fenetre, "dashboard")


# Relecture du 30/09/2026 : un titre de section qui redit celui de la page.
TITRES_REPETES = {
    "saisie": "SAISIE QUOTIDIENNE",
    "oa": "ANNÉES OA",
    "settings": "PARAMÈTRES",
    "aide": "NOTICE D'UTILISATION",
    "octopus_edf": "MON OFFRE HP/HC OU EDF TARIF BLEU",
}


@pytest.mark.parametrize("vue, titre", sorted(TITRES_REPETES.items()))
def test_pas_de_titre_de_section_qui_redit_la_page(fenetre, vue, titre):
    assert titre not in _titres_au_dessus(fenetre, vue) + _entetes(fenetre, vue)


def test_la_notice_n_a_plus_de_titre_dans_le_texte(fenetre):
    """Le titre de chaque rubrique est dans son bandeau, plus dans le texte."""
    fenetre._switch_view("aide")
    assert not any("<h3" in lbl.text()
                   for lbl in fenetre.views["aide"].findChildren(QLabel))
