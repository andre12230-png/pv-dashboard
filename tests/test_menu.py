"""Tests du menu de gauche.

Le menu est decrit une seule fois, dans NAV_ITEMS, et trois choses en
dependent : la barre laterale, le titre affiche en haut de la page, et le
smoke test qui ouvre chaque vue. Ces tests verifient qu'aucune des trois ne
peut se desynchroniser des autres.

Ils lisent la constante sans ouvrir de fenetre.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from conftest import detruire  # noqa: E402

import app_desktop  # noqa: E402

SOURCE = Path(app_desktop.__file__).read_text(encoding="utf-8")


def test_chaque_entree_a_un_titre_de_page():
    """Sans titre, _switch_view leve une KeyError et l'onglet ne s'ouvre
    pas du tout."""
    for key, label, _, _ in app_desktop.NAV_ITEMS:
        assert f'"{key}":' in SOURCE, f"l'entree « {label} » n'a pas de titre"


def test_chaque_entree_a_une_vue():
    """Une entree sans vue construite laisserait un onglet vide."""
    for key, label, _, _ in app_desktop.NAV_ITEMS:
        assert f'"{key}"' in SOURCE, f"l'entree « {label} » n'a pas de vue"


def test_les_cles_sont_uniques():
    """Deux entrees de meme cle se partageraient un seul bouton : la seconde
    ecraserait la premiere dans nav_buttons."""
    cles = [key for key, _, _, _ in app_desktop.NAV_ITEMS]

    assert len(cles) == len(set(cles))


def test_chaque_entree_a_un_pictogramme():
    """Un pictogramme absent laisserait l'entree sans icone, decalee par
    rapport aux autres. Ce sont des emojis, comme dans Pecule : Windows les
    dessine en couleur. Un caractere de la zone privee d'Unicode (Segoe MDL2
    Assets), place dans le texte d'un bouton, sortirait en carre vide."""
    for key, _, _, picto in app_desktop.NAV_ITEMS:
        assert picto.strip(), key
        assert not 0xE000 <= ord(picto[0]) <= 0xF8FF, key


def test_la_premiere_entree_ouvre_une_section():
    """Les entrees sans section heritent de la precedente : la premiere doit
    donc en declarer une."""
    assert app_desktop.NAV_ITEMS[0][2]


def test_les_libelles_du_menu_sont_accentues():
    """Le menu se lit en permanence : « Relevés », pas « Releves ». Ce test
    reperait les libelles ou un accent manque a l'evidence."""
    fautes = {
        "Releves": "Relevés", "Repartition": "Répartition",
        "energie": "énergie", "Synthese": "Synthèse",
        "financiere": "financière", "Annees": "Années",
        "Parametres": "Paramètres",
    }
    for _, label, _, _ in app_desktop.NAV_ITEMS:
        for faute, correction in fautes.items():
            assert not re.search(rf"\b{faute}\b", label), \
                f"« {label} » : écrire {correction}"


# ---------- le bandeau construit (29/09/2026) ----------

@pytest.fixture
def fenetre(tmp_path, monkeypatch):
    import yaml
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    import data_loaders as dl
    QApplication.instance() or QApplication([])
    cfg = yaml.safe_load(app_desktop.CONFIG_PATH.read_text(encoding="utf-8"))
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(app_desktop, "BASE_DIR", tmp_path)
    monkeypatch.setattr(app_desktop, "CONFIG_PATH", tmp_path / "config.yaml")
    monkeypatch.setattr(app_desktop, "CONFIG_LOCAL_PATH",
                        tmp_path / "config-local.yaml")
    (tmp_path / "Releves-pv.csv").write_text(
        ";".join(dl.RELEVES_HEADER) + "\n"
        "01/06/2025;20;12;5;2;3\n02/06/2025;18;10;6;3;3\n", encoding="utf-8")
    data = app_desktop.build_dataset(app_desktop.load_config())
    prefs = QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)
    w = app_desktop.MainWindow(data, prefs)
    yield w
    detruire(w)


def _bandeau_lu(fenetre) -> list[str]:
    """Titres de section et libelles des boutons, dans l'ordre du bandeau."""
    from PySide6.QtWidgets import QFrame
    bandeau = fenetre.findChild(QFrame, "Sidebar")
    disposition = bandeau.layout()
    lus = []
    for i in range(disposition.count()):
        w = disposition.itemAt(i).widget()
        if w is None:
            continue
        if w.objectName() == "NavSection":
            lus.append(w.text())
        elif w.objectName() == "NavItem":
            lus.append(w.text().split(" ", 1)[1])      # sans l'emoji
    return lus


def test_fin_du_menu_comme_pecule(fenetre):
    """29/09/2026 : la section « AUTRES » melangeait Notice, Parametres,
    Sauvegarde externe, Mise a jour et Votre avis. La fin du menu suit
    maintenant Pecule : MES DONNÉES, RÉGLAGES, AIDE (Notice, Votre avis,
    Mise a jour)."""
    lus = _bandeau_lu(fenetre)
    fin = lus[lus.index("MES DONNÉES"):]
    assert fin == ["MES DONNÉES", "Sauvegarde externe",
                   "RÉGLAGES", "Paramètres",
                   "AIDE", "Notice", "Votre avis", "Mise à jour"]
    assert "AUTRES" not in lus


def test_seule_la_page_affichee_est_surlignee(fenetre):
    """La page affichée se reconnaît à son bouton coché, et à lui seul
    (11/10/2026 : la propriété « active » qui doublait ce marquage est
    retirée, la feuille de style ne connaît plus que « :checked »)."""
    from gui_theme import LIGHT, qss_for
    fenetre._switch_view("stats")
    coches = [k for k, b in fenetre.nav_buttons.items() if b.isChecked()]
    assert coches == ["stats"]
    fenetre._switch_view("dashboard")
    coches = [k for k, b in fenetre.nav_buttons.items() if b.isChecked()]
    assert coches == ["dashboard"]
    assert "[active" not in qss_for(LIGHT)


def test_les_pages_occasionnelles_sous_un_seul_bouton(fenetre):
    """11/10/2026 (choix de l'auteur) : le bandeau defilait sur un portable
    1366 x 768. Les pages qui servent une fois l'an ou de temps en temps
    passent sous « 🗂️ Bilans et comparaisons… », comme « Mettre au
    propre… » dans Pecule ; la section CONTRATS disparait."""
    lus = _bandeau_lu(fenetre)
    assert "CONTRATS" not in lus
    debut = lus[:lus.index("MES DONNÉES")]
    assert debut == ["PRINCIPAL", "Tableau de bord", "Saisie quotidienne",
                     "Relevés journaliers", "Répartition énergie",
                     "Synthèse financière",
                     "ANALYSE", "Statistiques", "Bilans et comparaisons…"]
    bouton = fenetre.bouton_bilans
    textes = [a.text() for a in bouton.menu().actions()]
    # Le modele livre a un contrat de vente et pas de TVA : la ligne TVA,
    # masquee, n'apparait pas dans le petit menu non plus.
    assert textes[0].startswith("📅 ")
    assert textes[1] == "🔁 Comparer à l'an passé"
    assert textes[2].startswith("⚖️ ")
    assert len(textes) == 3
    assert "tva" not in fenetre.nav_buttons


def test_une_page_du_petit_menu_surligne_son_bouton(fenetre):
    """La page choisie dans le petit menu s'affiche ; son bouton est
    surligne et la ligne cochee. Revenir a une autre page les libere."""
    action = fenetre.nav_buttons["comparaison"]
    action.trigger()
    assert fenetre.current_view == "comparaison"
    assert fenetre.bouton_bilans.isChecked()
    assert action.isChecked()
    fenetre.nav_buttons["stats"].click()
    assert fenetre.current_view == "stats"
    assert not fenetre.bouton_bilans.isChecked()
    assert not action.isChecked()
    assert fenetre.nav_buttons["stats"].isChecked()


def test_air_avant_les_titres_comme_les_deux_autres_applis(fenetre):
    """6 px d'air avant chaque titre de section, 4 sous le nom de l'appli,
    comme Pecule et Recharges VE (11/10/2026 ; c'etait 11 px)."""
    from PySide6.QtWidgets import QFrame
    disposition = fenetre.findChild(QFrame, "Sidebar").layout()
    airs = []
    for i in range(1, disposition.count()):
        w = disposition.itemAt(i).widget()
        if w is not None and w.objectName() == "NavSection":
            espace = disposition.itemAt(i - 1).spacerItem()
            airs.append(espace.sizeHint().height() if espace else None)
    assert airs[0] == 4
    assert set(airs[1:]) == {6}


def test_le_bandeau_defile_sur_un_petit_ecran(fenetre):
    """Comme Pecule et Recharges VE : le bandeau est dans une zone qui
    defile. Sans elle, la fenetre ne pouvait pas descendre sous la hauteur
    du menu (731 px mesures le 29/09/2026), trop pour un portable 1366 x 768."""
    from PySide6.QtWidgets import QFrame, QScrollArea
    bandeau = fenetre.findChild(QFrame, "Sidebar")
    zones = [z for z in fenetre.findChildren(QScrollArea)
             if z.widget() is bandeau]
    assert len(zones) == 1
    assert fenetre.minimumSizeHint().height() < 690


# ---------- le selecteur de periode (08/10/2026) ----------

def test_le_selecteur_porte_le_libelle_periode(fenetre):
    """« Période : » devant le selecteur, comme Pecule et Recharges VE
    (choix de l'auteur du 08/10/2026). Grise avec le selecteur, comme dans
    Pecule, sur un onglet ou la periode n'a pas de sens."""
    from PySide6.QtWidgets import QLabel
    libelle = fenetre.findChild(QLabel, "LibellePeriode")
    assert libelle is not None and libelle.text() == "Période :"
    rangee = fenetre.prev_btn.parentWidget().layout()
    assert rangee.indexOf(libelle) == rangee.indexOf(fenetre.prev_btn) - 1
    fenetre._selecteur_actif = False
    fenetre._maj_etat_selecteur()
    assert not libelle.isEnabled()
    fenetre._selecteur_actif = True
    fenetre._maj_etat_selecteur()
    assert libelle.isEnabled()
