"""Les valeurs tapees dans la Saisie, pas encore enregistrees, ne se perdent
plus sans un mot.

Defaut d'origine (verifie le 28/09/2026) : chaque arrivee sur un onglet le
redessinait depuis le fichier. Quitter la Saisie puis y revenir, ou recliquer
sur son onglet, effacait ce qui etait tape ; la fermeture ne demandait rien.
Releves inventes.
"""
from __future__ import annotations

import pytest
import yaml

pytest.importorskip("PySide6")

from conftest import detruire  # noqa: E402
from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

import app_desktop  # noqa: E402
import data_loaders as dl  # noqa: E402


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
        ";".join(dl.RELEVES_HEADER) + "\n"
        "01/06/2025;20;12;5;2;3\n02/06/2025;18;10;6;3;3\n", encoding="utf-8")
    data = app_desktop.build_dataset(app_desktop.load_config())
    prefs = QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)
    w = app_desktop.MainWindow(data, prefs)
    w._switch_view("saisie")
    yield w
    # Fermeture de fin de test : plus de saisie en cours, pas de question.
    w.views["saisie"]._cache_mtime = None
    w.views["saisie"].refresh(w.current_period)
    detruire(w)


def _taper(win, texte: str) -> None:
    vue = win.views["saisie"]
    vue.table.item(0, vue.COLS.index("Prod_Jour")).setText(texte)


def _case(win) -> str:
    vue = win.views["saisie"]
    return vue.table.item(0, vue.COLS.index("Prod_Jour")).text()


def _releves(win) -> dict[str, dict[str, str]]:
    return {r["Date"]: r for r in dl.read_releves_raw(win.data.releves_path)}


# --- Changer d'onglet -------------------------------------------------------

def test_quitter_la_saisie_puis_revenir_garde_les_valeurs(win):
    _taper(win, "17")
    win._switch_view("dashboard")
    win._switch_view("saisie")
    assert _case(win) == "17"


def test_recliquer_sur_l_onglet_saisie_garde_les_valeurs(win):
    _taper(win, "17")
    win._switch_view("saisie")
    assert _case(win) == "17"


def test_sans_saisie_en_cours_le_tableau_suit_le_fichier(win):
    # Rien de tape : le retour sur l'onglet relit le fichier comme avant.
    with open(win.data.releves_path, "a", encoding="utf-8") as f:
        f.write("03/06/2025;19;11;4;2;2\n")
    win._switch_view("dashboard")
    win._switch_view("saisie")
    vue = win.views["saisie"]
    dates = [vue.table.item(r, 0).text() for r in range(vue.table.rowCount())]
    assert "03/06/2025" in dates


# --- Fermer l'application ---------------------------------------------------

class _FauxQMessageBox:
    Save = QMessageBox.Save
    Discard = QMessageBox.Discard
    Cancel = QMessageBox.Cancel
    reponse = QMessageBox.Cancel
    questions: list[str] = []

    @staticmethod
    def question(parent, titre, message, boutons=None, defaut=None):
        _FauxQMessageBox.questions.append(message)
        return _FauxQMessageBox.reponse


@pytest.fixture
def dialogue(monkeypatch):
    _FauxQMessageBox.questions = []
    monkeypatch.setattr(app_desktop, "QMessageBox", _FauxQMessageBox)
    # L'alerte passe par demander_enregistrement (30/09/2026).
    monkeypatch.setattr(
        app_desktop, "demander_enregistrement",
        lambda parent, titre, message: _FauxQMessageBox.question(
            parent, titre, message))
    return _FauxQMessageBox


def test_fermer_sans_saisie_ne_demande_rien(win, dialogue):
    assert win.close()
    assert dialogue.questions == []


def test_fermer_avec_saisie_en_cours_annuler_garde_la_fenetre(win, dialogue):
    _taper(win, "17")
    win._switch_view("dashboard")      # la saisie est ailleurs : on la trouve
    dialogue.reponse = QMessageBox.Cancel
    assert not win.close()
    assert len(dialogue.questions) == 1
    assert "pas encore enregistr" in dialogue.questions[0]
    assert _case(win) == "17"


def test_fermer_sans_enregistrer_laisse_le_fichier_intact(win, dialogue):
    _taper(win, "17")
    dialogue.reponse = QMessageBox.Discard
    avant = _releves(win)
    assert win.close()
    assert _releves(win) == avant


def test_fermer_en_enregistrant_ecrit_la_saisie(win, dialogue):
    vue = win.views["saisie"]
    jour = vue.table.item(0, 0).text()      # la ligne neuve, pre-datee
    _taper(win, "17")
    win._switch_view("dashboard")
    dialogue.reponse = QMessageBox.Save
    assert win.close()
    assert _releves(win)[jour]["Prod_Jour"] == "17"


def test_fermer_en_enregistrant_une_saisie_refusee_garde_la_fenetre(
        win, dialogue):
    # Valeur refusee par la validation : rien n'est ecrit, on ne ferme pas.
    _taper(win, "abc")
    dialogue.reponse = QMessageBox.Save
    avant = _releves(win)
    assert not win.close()
    assert _releves(win) == avant
    assert _case(win) == "abc"


# --- Ouvrir « Mes reglages » (la fenetre est reconstruite apres) ------------

class _FausseFenetreReglages:
    ouvertures = 0

    def __init__(self, *_a, **_k):
        _FausseFenetreReglages.ouvertures += 1

    def exec(self):
        return 0                            # l'utilisateur ferme sans rien


@pytest.fixture
def reglages(monkeypatch):
    _FausseFenetreReglages.ouvertures = 0
    monkeypatch.setattr(app_desktop, "FenetreReglages", _FausseFenetreReglages)
    return _FausseFenetreReglages


def test_reglages_avec_saisie_en_cours_annuler_n_ouvre_rien(
        win, dialogue, reglages):
    _taper(win, "17")
    dialogue.reponse = QMessageBox.Cancel
    win._ouvrir_reglages()
    assert reglages.ouvertures == 0
    assert "pas encore enregistr" in dialogue.questions[0]
    assert _case(win) == "17"


def test_reglages_avec_saisie_en_cours_enregistrer_puis_ouvrir(
        win, dialogue, reglages):
    jour = win.views["saisie"].table.item(0, 0).text()
    _taper(win, "17")
    win._switch_view("settings")
    dialogue.reponse = QMessageBox.Save
    win._ouvrir_reglages()
    assert reglages.ouvertures == 1
    assert _releves(win)[jour]["Prod_Jour"] == "17"
    # Plus rien en attente : la fermeture ne redemande pas.
    dialogue.questions.clear()
    assert win.close()
    assert dialogue.questions == []


def test_reglages_sans_saisie_ne_demande_rien(win, dialogue, reglages):
    win._ouvrir_reglages()
    assert reglages.ouvertures == 1
    assert dialogue.questions == []


def test_l_alerte_dit_ne_pas_enregistrer(qapp, monkeypatch):
    """30/09/2026 : la traduction de Qt ecrivait « Ne pas tenir compte ». La
    charte veut « Enregistrer / Ne pas enregistrer / Annuler », Annuler par
    defaut."""
    from gui_widgets import demander_enregistrement
    vu = {}

    def regarder(self):
        vu["boutons"] = [b.text().replace("&", "") for b in self.buttons()]
        vu["defaut_est_annuler"] = (self.defaultButton()
                                    is self.button(QMessageBox.Cancel))
        return QMessageBox.Cancel
    monkeypatch.setattr(QMessageBox, "exec", regarder)
    reponse = demander_enregistrement(None, "Titre", "Des valeurs tapées…")
    assert reponse == QMessageBox.Cancel
    assert "Ne pas enregistrer" in vu["boutons"]
    assert not any("tenir compte" in b for b in vu["boutons"])
    assert vu["defaut_est_annuler"]      # « Annuler » une fois traduit
