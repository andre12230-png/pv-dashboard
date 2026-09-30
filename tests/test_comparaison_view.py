"""Tests de l'onglet Comparaison N vs N-1.

L'onglet avait ses propres boutons Mois / Annee et une liste de 54 mois,
pendant que le selecteur du haut restait grise : on croyait ne pas pouvoir
choisir de periode. Il obeit desormais au selecteur commun, comme les autres
onglets ; seul le mode « une journee precise » garde son calendrier.
"""
from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest
from PySide6.QtCore import QCoreApplication, QDate, QEvent
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QTableWidget

from gui_theme import LIGHT
from views._helpers import METRIQUES, PERIOD_ALL, filter_period
from views.comparaison import ComparaisonView, date_limite_n1

DEBUT_OA = pd.Timestamp("2024-05-12").date()


@pytest.fixture(scope="session")
def qapp():
    """Une seule QApplication pour toute la session (Qt l'exige)."""
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def vue(qapp):
    """Un releve par jour du 12/05/2024 au 28/02/2026 : deux annees OA
    completes et le debut de la troisieme."""
    jours = pd.date_range("2024-05-12", "2026-02-28", freq="D")
    df = pd.DataFrame({cle: 1.0 for cle, *_ in METRIQUES}, index=jours)
    df["annee_oa"] = [1 if j < pd.Timestamp("2025-05-12")
                      else 2 if j < pd.Timestamp("2026-05-12") else 3
                      for j in jours]
    data = SimpleNamespace(df=df, start_oa=DEBUT_OA)
    v = ComparaisonView(data, LIGHT)
    yield v
    # Detruit la vue et ses graphiques maintenant, pendant que Qt tourne
    # encore : laisses a la sortie de Python, ils faisaient planter la
    # fermeture de pytest (code 0xC0000374) une fois tous les tests reussis.
    v.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def textes(vue) -> list[str]:
    """Tous les textes affiches par l'onglet."""
    return [lab.text() for lab in vue.container.findChildren(QLabel)]


def test_l_onglet_obeit_au_selecteur_du_haut():
    """Sinon MainWindow grise le selecteur, et on croit qu'il est en panne."""
    assert ComparaisonView.utilise_periode is True


def test_un_mois_est_compare_au_meme_mois_de_l_an_passe(vue):
    vue.refresh("month-2026-02")
    assert any("Février 2026 face à Février 2025" in t for t in textes(vue))


def test_une_annee_est_comparee_a_la_precedente(vue):
    vue.refresh("year-2025")
    assert any("Année 2025 face à Année 2024" in t for t in textes(vue))


def test_une_annee_oa_est_comparee_a_la_precedente(vue):
    # L'annee OA #2 court jusqu'au 11/05/2026 et le fichier s'arrete au
    # 28/02/2026 : elle est en cours, donc coupee a la meme date.
    vue.refresh("oa-2")
    assert any("Année OA #2 (au 28/02) face à Année OA #1 (au 28/02)" in t
               for t in textes(vue))


# ---------------------------------------------------------------------------
# Periode en cours : l'an passe est coupe a la meme date.
# Sans cela, septembre 2026 (9 jours releves) etait compare a septembre 2025
# entier, et la production affichait -62 % alors que le mois n'etait pas fini.
# ---------------------------------------------------------------------------

def test_une_periode_terminee_n_est_pas_coupee(vue):
    df_n = filter_period(vue.data.df, "month-2026-01", DEBUT_OA)
    assert date_limite_n1(df_n, "month-2026-01", DEBUT_OA) is None


def test_un_mois_en_cours_coupe_l_an_passe_a_la_meme_date(vue):
    df = vue.data.df[vue.data.df.index <= "2026-02-10"]
    df_n = filter_period(df, "month-2026-02", DEBUT_OA)
    assert date_limite_n1(df_n, "month-2026-02", DEBUT_OA) == pd.Timestamp("2025-02-10")


def test_le_mois_en_cours_est_compare_aux_memes_jours(vue):
    """Un releve de 1 kWh par jour : 10 jours de chaque cote, pas 10 contre 28."""
    vue.data.df = vue.data.df[vue.data.df.index <= "2026-02-10"]
    vue.refresh("month-2026-02")
    assert any("Février 2026 (au 10/02) face à Février 2025 (au 10/02)" in t
               for t in textes(vue))
    table = vue.container.findChildren(QTableWidget)[-1]
    assert table.item(0, 0).text().strip() == "Production"
    assert table.item(0, 1).text() == "10,0 kWh"      # N-1
    assert table.item(0, 2).text() == "10,0 kWh"      # N


def test_l_annee_en_cours_est_coupee_aussi(vue):
    df = vue.data.df
    df_n = filter_period(df, "year-2026", DEBUT_OA)
    assert date_limite_n1(df_n, "year-2026", DEBUT_OA) == pd.Timestamp("2025-02-28")


def test_toute_la_periode_invite_a_choisir(vue):
    """Comparer « tout » a « tout moins un an » n'a pas de sens."""
    vue.refresh(PERIOD_ALL)
    assert any("Choisissez un mois ou une année" in t for t in textes(vue))


def test_le_mode_journee_survit_a_son_propre_rafraichissement(vue):
    """Choisir une date redessine l'onglet avec la meme periode : le mode
    journee doit rester actif, sinon le calendrier disparaitrait aussitot."""
    vue.refresh("month-2026-02")
    vue._activer_mode_jour(True)
    vue._changer_date(QDate(2026, 2, 14))
    assert vue.mode_jour
    assert any("14/02/2026 face à 14/02/2025" in t for t in textes(vue))


def test_changer_de_periode_en_haut_quitte_le_mode_journee(vue):
    """Choisir un autre mois en haut, c'est vouloir voir ce mois-la."""
    vue.refresh("month-2026-02")
    vue._activer_mode_jour(True)
    vue.refresh("month-2026-01")
    assert not vue.mode_jour
    assert any("Janvier 2026 face à Janvier 2025" in t for t in textes(vue))


def test_le_calendrier_part_de_la_periode_choisie(vue):
    """Sous janvier 2025, le calendrier s'ouvre sur le dernier jour de
    janvier 2025 — pas sur le dernier releve du fichier."""
    vue.refresh("month-2025-01")
    vue._activer_mode_jour(True)
    assert vue.selection == "2025-01-31"


def test_le_bouton_journee_existe(vue):
    vue.refresh("month-2026-02")
    assert any(b.text() == "Une journée précise"
               for b in vue.container.findChildren(QPushButton))


# --- Relecture du 30/09/2026 -------------------------------------------------

@pytest.fixture
def vue_annuelle(qapp):
    """10 unites par jour en 2024 et 2025 : des totaux annuels au-dela de
    1 000 kWh (3 660 en 2024, annee bissextile, et 3 650 en 2025)."""
    jours = pd.date_range("2024-01-01", "2025-12-31", freq="D")
    df = pd.DataFrame({cle: 10.0 for cle, *_ in METRIQUES}, index=jours)
    df["annee_oa"] = 1
    v = ComparaisonView(SimpleNamespace(df=df, start_oa=DEBUT_OA), LIGHT)
    v.refresh("year-2025")
    yield v
    v.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def _cellules(vue) -> list[list[str]]:
    table = vue.container.findChildren(QTableWidget)[0]
    return [[table.item(r, c).text().strip() if table.item(r, c) else ""
             for c in range(table.columnCount())]
            for r in range(table.rowCount())]


def test_une_seule_unite_dans_le_tableau(vue_annuelle):
    """« 2,76 MWh », « 2,71 MWh » puis « -55,0 kWh » sur la meme ligne :
    tout en kWh, milliers separes."""
    lignes = _cellules(vue_annuelle)
    assert not any("MWh" in t for ligne in lignes for t in ligne)
    production = next(ligne for ligne in lignes if ligne[0] == "Production")
    assert production[1:3] == ["3 660,0 kWh", "3 650,0 kWh"]


def test_libelles_sans_jargon(vue_annuelle):
    noms = [ligne[0] for ligne in _cellules(vue_annuelle)]
    assert "Économies" in noms and "Consommation du réseau" in noms
    assert not any("autoconso" in n.lower().split() or "Soutirage" in n
                   for n in noms)


def test_graphique_sans_n_moins_1_et_chiffres_francais(vue_annuelle):
    from gui_widgets import MplCanvas
    ax = vue_annuelle.container.findChildren(MplCanvas)[0].fig.axes[0]
    legende = [t.get_text() for t in ax.get_legend().get_texts()]
    assert legende == ["Année 2024", "Année 2025"]
    assert "3 650" in [t.get_text() for t in ax.texts]
