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
    assert any("Février 2026 face à février 2025" in t for t in textes(vue))


def test_une_annee_est_comparee_a_la_precedente(vue):
    vue.refresh("year-2025")
    assert any("Année 2025" in t and "face à année 2024" in t
               for t in textes(vue))


def test_une_annee_oa_est_comparee_a_la_precedente(vue):
    # L'annee OA #2 court jusqu'au 11/05/2026 et le fichier s'arrete au
    # 28/02/2026 : elle est en cours, donc coupee a la meme date.
    vue.refresh("oa-2")
    assert any("Année OA #2 (au 28/02) face à année OA #1 (au 28/02)" in t
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
    assert any("Février 2026 (au 10/02) face à février 2025 (au 10/02)" in t
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
    assert any("Janvier 2026 face à janvier 2025" in t for t in textes(vue))


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
    assert "Économies" in noms and "Achat au réseau" in noms
    assert not any("autoconso" in n.lower().split() or "Soutirage" in n
                   for n in noms)


def test_graphique_sans_n_moins_1_et_chiffres_francais(vue_annuelle):
    from gui_widgets import MplCanvas
    ax = vue_annuelle.container.findChildren(MplCanvas)[0].fig.axes[0]
    legende = [t.get_text() for t in ax.get_legend().get_texts()]
    assert legende == ["Année 2024", "Année 2025"]
    assert "3 650" in [t.get_text() for t in ax.texts]


def test_pas_de_pourcentage_nul():
    """« +0,18 € (+0,0 %) » : un pourcentage arrondi a zero n'apprend rien."""
    from views._helpers import fmt_eur, variation
    texte, _ = variation(0.18, -419.95, fmt_eur, +1, LIGHT)
    assert texte == "+0,18 €"
    texte, _ = variation(-55.0, 2765.0, str, +1, LIGHT)
    assert "%" in texte                      # -2,0 % : garde son pourcentage


def test_l_explication_n_est_pas_repetee(vue_annuelle):
    """Le titre et le sous-titre de la page disent deja ce que la page
    compare : le titre de section qui le redisait est retire."""
    tous = " | ".join(textes(vue_annuelle))
    assert "COMPARAISON AVEC L'ANNÉE PRÉCÉDENTE" not in tous.upper()
    assert "Compare la période choisie" not in tous


def test_le_tableau_a_la_hauteur_de_ses_lignes(vue_annuelle):
    """Une bande vide d'une soixantaine de pixels restait sous la derniere
    ligne (hauteur calculee a 38 px par ligne)."""
    table = vue_annuelle.container.findChildren(QTableWidget)[0]
    contenu = (table.horizontalHeader().sizeHint().height()
               + sum(table.rowHeight(r) for r in range(table.rowCount())))
    assert table.height() - contenu <= 2 * table.frameWidth() + 2


def test_le_mode_journee_montre_toutes_ses_colonnes(vue):
    """30/09/2026 : en mode « Une journée précise », les deux tableaux
    n'affichaient que la colonne « Indicateur » : un ressort a droite des
    deux cartes gardait la place, les tableaux restaient a 256 px et leurs
    colonnes de valeurs etaient coupees (pas de defilement horizontal)."""
    vue.refresh("month-2026-02")
    vue._activer_mode_jour(True)
    vue.resize(1000, 900)
    vue.show()
    for _ in range(5):
        # Les tableaux du mode « mois » sont effaces (deleteLater) avant
        # qu'on compte ceux du mode journee.
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        QCoreApplication.processEvents()
    tableaux = vue.container.findChildren(QTableWidget)
    assert len(tableaux) == 2
    for table in tableaux:
        entete = table.horizontalHeader()
        largeur = sum(entete.sectionSize(j) for j in range(table.columnCount()))
        assert largeur <= table.viewport().width() + 1, (
            largeur, table.viewport().width())
    vue.hide()


# ---------------------------------------------------------------------------
# L'an passe commence en cours de periode (mise en service) : on compare a
# partir de la meme date. Mai 2024 n'avait que 20 jours de releves, et le
# badge du tableau de bord affichait « +429 % » face a mai 2025 entier
# (audit du 04/10/2026).
# ---------------------------------------------------------------------------

def test_l_annee_est_comparee_depuis_la_mise_en_service(vue):
    vue.refresh("year-2025")
    assert any("Année 2025 (depuis le 12/05) face à année 2024 "
               "(depuis le 12/05)" in t for t in textes(vue))
    table = vue.container.findChildren(QTableWidget)[-1]
    assert table.item(0, 0).text().strip() == "Production"
    assert table.item(0, 1).text() == table.item(0, 2).text()   # 234 j / 234 j


def test_le_mois_de_mise_en_service_est_compare_aux_memes_jours(vue):
    vue.refresh("month-2025-05")
    table = vue.container.findChildren(QTableWidget)[-1]
    assert table.item(0, 1).text() == "20,0 kWh"      # N-1 : 12 au 31/05
    assert table.item(0, 2).text() == "20,0 kWh"      # N : memes jours


def test_une_annee_oa_entiere_n_est_pas_coupee_au_debut(vue):
    """L'annee OA #1 commence le jour de la mise en service : rien a couper."""
    vue.refresh("oa-2")
    assert not any("depuis le" in t for t in textes(vue))


def test_le_badge_du_tableau_de_bord_compare_les_memes_jours(qapp, vue):
    from views.dashboard import DashboardView
    df = vue.data.df
    data = SimpleNamespace(df=df, start_oa=DEBUT_OA)
    tableau = DashboardView.__new__(DashboardView)
    tableau.data, tableau.theme = data, LIGHT
    df_n = filter_period(df, "month-2025-05", DEBUT_OA)
    badge = tableau._badge_n1(df_n, "month-2025-05",
                              float(df_n["production_kwh"].sum()))
    assert badge is not None
    assert badge.text().startswith("stable")     # memes jours, meme production


def test_sans_releve_l_an_passe_une_carte_le_dit(vue):
    """Audit du 04/10/2026 : un tableau de « — » (« pas de donnée l'an
    passé » huit fois) et un graphique sans barres, la ou la Repartition
    dit clairement que la comparaison n'est pas possible. Le fichier
    commence le 12/05/2024 : mai 2024 n'a pas d'an passe."""
    vue.refresh("month-2024-05")
    tout = " ".join(textes(vue))
    assert "la comparaison n'est pas possible" in tout
    assert not vue.container.findChildren(QTableWidget)
