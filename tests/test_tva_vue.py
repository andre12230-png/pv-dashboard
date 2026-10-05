"""Page TVA : l'ordre des tableaux.

Demande du 27/09/2026 : l'annee la plus recente EN HAUT des deux tableaux
(recapitulatif par annee et controle avec les factures EDF OA), comme on lit
un releve. Le graphique, lui, reste chronologique de gauche a droite.

Donnees inventees.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QTableWidget
from test_tva_lasm import _lasm_plat, _releves

import calculations as calc
from gui_theme import LIGHT
from views.tva import TvaView


@pytest.fixture(scope="module")
def qapp():
    """Une seule QApplication pour toute la session (Qt l'exige)."""
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def vue(qapp):
    df = _releves([
        ("2023-01-15", 100.0, 50.0), ("2023-12-31", 0.0, 0.0),
        ("2024-01-15", 100.0, 50.0), ("2024-12-31", 0.0, 0.0),
        ("2025-01-15", 60.0, 30.0), ("2025-06-30", 0.0, 0.0),
    ])
    factures = [
        {"debut": "2023-01-01", "fin": "2023-12-31", "total_kwh": 50},
        {"debut": "2024-01-01", "fin": "2024-12-31", "total_kwh": 50},
    ]
    data = SimpleNamespace(
        df_brut=df,
        lasm=_lasm_plat(),
        cfg={"sources": {"injection_facturee": factures}},
        cycle_oa="du 01/01 au 31/12",
    )
    v = TvaView(data, LIGHT)
    v.populate("")
    return v


def _premiere_colonne(table: QTableWidget) -> list[str]:
    return [table.item(i, 0).text() for i in range(table.rowCount())]


def test_les_deux_tableaux_commencent_par_l_annee_la_plus_recente(vue):
    annees, controle = vue.findChildren(QTableWidget)
    assert _premiere_colonne(annees) == ["2025 (estimé)", "2024", "2023"]
    periodes = _premiere_colonne(controle)
    assert periodes[0].startswith("du 01/01/2024")
    assert periodes[-1].startswith("du 01/01/2023")


# --- Relecture du 30/09/2026 ----------------------------------------------

def _labels(vue) -> list:
    from PySide6.QtWidgets import QLabel
    return vue.findChildren(QLabel)


def test_la_page_ne_redit_pas_son_sous_titre(vue):
    """« … ligne 5A de la déclaration CA12 / 3517-S » figurait sous le titre
    de la page ET en tete du contenu."""
    assert not [lbl.text() for lbl in _labels(vue)
                if "ligne 5A de la déclaration" in lbl.text()]


def test_les_notes_se_lisent_en_lignes_courtes(vue):
    """Des lignes de ~200 signes a 1280 px : pas plus de 780 px de large,
    comme la Notice. Et plus de mots en capitales pour insister."""
    notes = [lbl for lbl in _labels(vue) if "Ce qui est taxable" in lbl.text()]
    assert len(notes) == 1
    assert notes[0].maximumWidth() <= 780
    assert "ESTIMATION" not in notes[0].text()
    assert " ET " not in notes[0].text()


def test_l_avertissement_d_estimation_est_pres_du_tableau(vue):
    """Il etait la derniere des notes de bas de page : il passe en sous-titre
    du tableau des annees, la ou se lit le chiffre estime."""
    avertissements = [lbl for lbl in _labels(vue)
                      if "pas un montant à déclarer" in lbl.text()]
    assert len(avertissements) == 1
    assert avertissements[0].objectName() == "SectionSub"


def test_le_tableau_des_annees_a_son_bandeau(vue):
    bandeaux = [lbl.text() for lbl in _labels(vue)
                if lbl.objectName() == "CardHeader"]
    assert "DÉTAIL PAR ANNÉE CIVILE" in bandeaux


def test_les_tableaux_n_ont_pas_de_bande_vide(vue):
    for table in vue.findChildren(QTableWidget):
        attendu = (table.horizontalHeader().sizeHint().height()
                   + sum(table.rowHeight(r) for r in range(table.rowCount()))
                   + 2 * table.frameWidth())
        assert table.height() == attendu


def test_le_seuil_du_controle_est_ecrit(vue):
    """Vert sous 1 %, rouge au-dela : la couleur portait seule le verdict."""
    assert [lbl for lbl in _labels(vue)
            if lbl.objectName() == "SectionSub" and "1 %" in lbl.text()]


def test_l_ecart_avec_les_factures_se_lit_pareil_dans_les_deux_tableaux(vue):
    """La colonne s'appelait « Contrôle EDF » (acheteur ecrit en dur) et son
    pourcentage restait noir, quand le tableau du dessous le colore."""
    annees, controle = vue.findChildren(QTableWidget)
    entetes = [annees.horizontalHeaderItem(j).text()
               for j in range(annees.columnCount())]
    assert "Contrôle EDF" not in entetes
    assert " ".join(entetes[-1].split()) == "Écart avec les factures"
    # 2024 : 50 kWh releves pour 50 factures, ecart nul, donc vert.
    ligne_2024 = _premiere_colonne(annees).index("2024")
    ecart = annees.item(ligne_2024, annees.columnCount() - 1)
    assert ecart.foreground().color().name() == LIGHT["credit"].lower()


def test_le_graphique_ecrit_des_euros_a_plat(vue):
    """Le « € » etait couche le long de l'axe, et les chiffres des barres
    n'avaient pas d'unite."""
    from matplotlib.colors import to_hex

    from gui_theme import CHART_COLORS
    from gui_widgets import MplCanvas
    ax = vue.findChildren(MplCanvas)[0].fig.axes[0]
    assert ax.get_ylabel() == ""
    chiffres = [t.get_text() for t in ax.texts if t.get_text()]
    assert chiffres and all(c.endswith(" €") for c in chiffres)
    # La TVA due n'est pas de l'autoconsommation : pas son vert.
    couleurs = {to_hex(b.get_facecolor()) for b in ax.patches}
    assert to_hex(CHART_COLORS["autoconso"]) not in couleurs


def test_les_annees_ne_ressemblent_pas_a_des_liens(vue):
    """Les annees closes s'ecrivaient en bleu gras, comme un lien cliquable."""
    annees = vue.findChildren(QTableWidget)[0]
    for i in range(annees.rowCount()):
        couleur = annees.item(i, 0).foreground().color().name()
        assert couleur != LIGHT["primary"].lower()


def test_les_periodes_s_ecrivent_du_au(vue):
    controle = vue.findChildren(QTableWidget)[1]
    assert _premiere_colonne(controle)[0] == "du 01/01/2024 au 31/12/2024"


def test_le_calcul_reste_chronologique():
    """Seul l'affichage s'inverse : le calcul rend toujours les annees dans
    l'ordre, le graphique et les tuiles en dependent."""
    df = _releves([("2023-01-15", 100.0, 50.0), ("2024-01-15", 100.0, 50.0)])
    lignes = calc.lasm_par_annee(df, _lasm_plat())
    assert [ligne["annee"] for ligne in lignes] == [2023, 2024]


def test_un_autre_acheteur_est_nomme_partout(qapp):
    # La page disait « EDF OA » a qui vend a un autre acheteur (28/09/2026).
    from PySide6.QtWidgets import QLabel
    df = _releves([("2024-01-15", 100.0, 50.0), ("2024-12-31", 0.0, 0.0)])
    data = SimpleNamespace(
        df_brut=df, lasm=_lasm_plat(),
        cfg={"sources": {"injection_facturee": [
            {"debut": "2024-01-01", "fin": "2024-12-31", "total_kwh": 50}]}},
        cycle_oa="du 01/01 au 31/12", acheteur="Solaire Coop",
        d_acheteur="de Solaire Coop")
    v = TvaView(data, LIGHT)
    v.populate("")
    textes = [lbl.text() for lbl in v.findChildren(QLabel)]
    for table in v.findChildren(QTableWidget):
        for i in range(table.rowCount()):
            for j in range(table.columnCount()):
                it = table.item(i, j)
                if it is not None:
                    textes += [it.text(), it.toolTip()]
    tout = " ".join(textes)
    assert "EDF OA" not in tout
    assert "Solaire Coop" in tout
