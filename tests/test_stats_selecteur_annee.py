"""Page Statistiques : le selecteur « Période » choisit l'annee mise en
avant (16/10/2026, demande de l'auteur).

Le selecteur etait grise sur cette page : l'annee en jaune du graphique
« Production mensuelle » etait toujours la plus recente. Il propose
maintenant les seules annees civiles, ses fleches avancent d'une annee et
« Cette année » ramene a l'annee en cours. Jeu invente (demo_releves).
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

pytest.importorskip("PySide6")

from conftest import detruire  # noqa: E402

import app_desktop  # noqa: E402
from views._helpers import (  # noqa: E402
    annee_de_reference,
    options_annees_seules,
    periode_annuelle,
    periode_pour_annee,
)


@pytest.fixture
def df():
    jours = pd.to_datetime(["2024-03-10", "2025-06-10", "2026-02-10"])
    return pd.DataFrame({"annee_oa": [1, 2, 2]}, index=jours)


# ---------- Fonctions sans fenetre ----------

def test_le_menu_ne_propose_que_les_annees(df):
    """Ni « Toute la période » ni les annees OA : le graphique compare des
    annees civiles."""
    assert options_annees_seules(df) == [
        ("2026", "year-2026"), ("2025", "year-2025"), ("2024", "year-2024")]


def test_l_annee_visee_par_une_periode(df):
    assert periode_annuelle(df, "year-2025") == "year-2025"
    assert periode_annuelle(df, "month-2024-03") == "year-2024"
    # Toute la periode, annee OA, annee sans releve : la plus recente.
    assert periode_annuelle(df, "all") == "year-2026"
    assert periode_annuelle(df, "oa-1") == "year-2026"
    assert periode_annuelle(df, "year-2019") == "year-2026"


def test_sans_releve_aucune_annee():
    vide = pd.DataFrame({"annee_oa": []}, index=pd.to_datetime([]))
    assert options_annees_seules(vide) == []
    assert periode_annuelle(vide, "all") is None
    assert annee_de_reference(vide) is None


def test_cette_annee_vise_l_annee_en_cours_ou_la_derniere(df):
    assert annee_de_reference(df, pd.Timestamp("2026-10-16")) == "year-2026"
    # Avant tout releve de l'annee nouvelle : la derniere annee relevee.
    assert annee_de_reference(df, pd.Timestamp("2027-01-03")) == "year-2026"


def test_changer_d_annee_garde_le_mois(df):
    """Revue du 16/10/2026 : choisir 2024 sur Statistiques faisait passer
    les autres pages a l'annee 2024 entiere. Le mois affiche est garde quand
    il a des releves la-bas, sinon c'est l'annee entiere."""
    assert periode_pour_annee(df, "month-2026-02", "year-2024") == "year-2024"
    assert periode_pour_annee(df, "month-2025-06", "year-2024") == "year-2024"
    assert periode_pour_annee(df, "month-2024-03", "year-2024") == "month-2024-03"
    jours = pd.to_datetime(["2024-03-10", "2025-03-10", "2025-06-10"])
    df2 = pd.DataFrame({"annee_oa": [1, 1, 2]}, index=jours)
    assert periode_pour_annee(df2, "month-2025-03", "year-2024") == "month-2024-03"
    # Pas un mois : l'annee entiere.
    assert periode_pour_annee(df2, "all", "year-2024") == "year-2024"
    assert periode_pour_annee(df2, "year-2025", "year-2024") == "year-2024"


# ---------- Dans la fenetre ----------

@pytest.fixture
def fenetre(tmp_path, monkeypatch):
    import yaml
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from demo_releves import ecrire_releves_demo
    QApplication.instance() or QApplication([])
    cfg = yaml.safe_load(app_desktop.CONFIG_PATH.read_text(encoding="utf-8"))
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(app_desktop, "BASE_DIR", tmp_path)
    monkeypatch.setattr(app_desktop, "CONFIG_PATH", tmp_path / "config.yaml")
    monkeypatch.setattr(app_desktop, "CONFIG_LOCAL_PATH",
                        tmp_path / "config-local.yaml")
    ecrire_releves_demo(tmp_path / "Releves-pv.csv",
                        debut=date(2024, 1, 1), fin=date(2026, 3, 15))
    data = app_desktop.build_dataset(app_desktop.load_config())
    prefs = QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)
    w = app_desktop.MainWindow(data, prefs)
    w._appliquer_periode("month-2026-02")
    w._switch_view("stats")
    yield w
    detruire(w)


def _annee_en_jaune(fenetre) -> str:
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    from gui_theme import CHART_COLORS_CLAIR
    from gui_widgets import MplCanvas
    # Les graphiques du dessin precedent ne disparaissent qu'au tour suivant
    # de la boucle d'evenements (deleteLater).
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    _barres, courbes = (c.fig.axes[0] for c in
                        fenetre.views["stats"].findChildren(MplCanvas))
    jaune = [ligne for ligne in courbes.get_lines()
             if ligne.get_color() == CHART_COLORS_CLAIR["production"]]
    assert len(jaune) == 1
    return jaune[0].get_label()


def _valeurs_du_menu(fenetre) -> list[str]:
    combo = fenetre.year_combo
    return [combo.itemData(i) for i in range(combo.count())]


def test_le_selecteur_est_actif_et_ne_montre_que_les_annees(fenetre):
    assert fenetre.year_combo.isEnabled()
    assert not fenetre.month_combo.isVisibleTo(fenetre)
    assert _valeurs_du_menu(fenetre) == ["year-2026", "year-2025", "year-2024"]
    assert fenetre.year_combo.currentData() == "year-2026"
    assert _annee_en_jaune(fenetre) == "2026"


def test_choisir_une_annee_la_met_en_jaune_et_garde_le_mois(fenetre):
    fenetre.year_combo.setCurrentIndex(2)
    # Fevrier 2026 affiche avant : fevrier 2024, pas l'annee entiere.
    assert fenetre.current_period == "month-2024-02"
    assert fenetre.year_combo.currentData() == "year-2024"
    assert _annee_en_jaune(fenetre) == "2024"


def test_les_fleches_avancent_d_une_annee_en_gardant_le_mois(fenetre):
    assert not fenetre.next_btn.isEnabled()      # 2026 : la plus recente
    fenetre.prev_btn.click()
    assert fenetre.current_period == "month-2025-02"
    assert _annee_en_jaune(fenetre) == "2025"
    fenetre.prev_btn.click()
    assert fenetre.current_period == "month-2024-02"
    assert not fenetre.prev_btn.isEnabled()      # 2024 : la plus ancienne
    fenetre._raccourci_periode(+1)               # Ctrl+Droite
    assert fenetre.current_period == "month-2025-02"


def test_un_mois_absent_de_l_annee_donne_l_annee_entiere(fenetre):
    """Decembre 2025 vers 2026 : decembre 2026 n'a pas de releve (le jeu
    s'arrete en mars), on montre donc l'annee 2026 entiere."""
    fenetre._appliquer_periode("month-2025-12")
    fenetre.next_btn.click()
    assert fenetre.current_period == "year-2026"
    assert _annee_en_jaune(fenetre) == "2026"


def test_cette_annee_ramene_au_mois_en_cours(fenetre):
    """« Cette année » ramene au mois de reference (le mois en cours, ou
    le dernier releve) : les autres pages retrouvent le mois en cours, et
    Statistiques montre son annee."""
    assert fenetre.btn_ce_mois.text() == "Cette année"
    # Fevrier 2026 est dans l'annee de reference (la derniere relevee).
    assert not fenetre.btn_ce_mois.isEnabled()
    fenetre.year_combo.setCurrentIndex(2)
    assert fenetre.btn_ce_mois.isEnabled()
    fenetre.btn_ce_mois.click()
    assert fenetre.current_period == "month-2026-03"   # dernier mois releve
    assert fenetre.year_combo.currentData() == "year-2026"
    assert not fenetre.btn_ce_mois.isEnabled()


def test_les_autres_pages_gardent_leur_mois(fenetre):
    fenetre.prev_btn.click()
    fenetre._switch_view("dashboard")
    valeurs = _valeurs_du_menu(fenetre)
    assert valeurs[0] == "all"
    assert fenetre.year_combo.currentData() == "year-2025"
    assert fenetre.month_combo.isVisibleTo(fenetre)
    assert fenetre.month_combo.currentData() == "month-2025-02"


def test_venir_de_toute_la_periode_montre_la_plus_recente(fenetre):
    fenetre._switch_view("dashboard")
    fenetre._appliquer_periode("all")
    fenetre._switch_view("stats")
    assert fenetre.year_combo.currentData() == "year-2026"
    assert _annee_en_jaune(fenetre) == "2026"
    fenetre.prev_btn.click()
    assert fenetre.current_period == "year-2025"
