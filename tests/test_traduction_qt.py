"""Les boutons fournis par Qt lui-meme, en francais.

Diagnostic du 26/09/2026 : contrairement a Pecule et a Recharges VE, cette
application ne chargeait pas la traduction de Qt. Les deux questions de la
page Saisie affichaient donc « Yes / No », et le clic droit dans une case de
saisie « Undo, Cut, Copy, Paste... ».

La traduction doit etre posee des la creation de l'application, dans les
deux portes d'entree (run.py, celle de l'exe, et app_desktop.main) : le
message « deja ouvert » s'affiche avant tout le reste.

    py -m pytest tests/test_traduction_qt.py
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLineEdit, QMessageBox  # noqa: E402

from gui_theme import installer_traduction_qt  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_boutons_et_clic_droit_en_francais(qapp):
    assert installer_traduction_qt(qapp)
    boite = QMessageBox(QMessageBox.Question, "t", "x",
                        QMessageBox.Yes | QMessageBox.No)
    textes = {b.text().replace("&", "") for b in boite.buttons()}
    assert textes == {"Oui", "Non"}
    champ = QLineEdit()
    menu = champ.createStandardContextMenu()
    actions = [a.text().replace("&", "") for a in menu.actions()]
    assert any(t.startswith("Copier") for t in actions)


def test_une_seconde_installation_ne_double_pas_le_traducteur(qapp):
    assert installer_traduction_qt(qapp)
    assert installer_traduction_qt(qapp)
    assert qapp._traducteur_qt is not None


def _appels_dans_l_ordre(fichier: str, fonction: str) -> list[str]:
    """Les fonctions appelees dans `fonction`, dans l'ordre du texte."""
    arbre = ast.parse((RACINE / fichier).read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.FunctionDef) and noeud.name == fonction:
            appels = [n for n in ast.walk(noeud) if isinstance(n, ast.Call)]
            appels.sort(key=lambda n: (n.lineno, n.col_offset))
            return [ast.unparse(n.func) for n in appels]
    raise AssertionError(f"{fonction} introuvable dans {fichier}")


@pytest.mark.parametrize("fichier", ["run.py", "app_desktop.py"])
def test_traduction_posee_avant_le_message_deja_ouvert(fichier):
    appels = _appels_dans_l_ordre(fichier, "main")
    assert "installer_traduction_qt" in appels
    assert (appels.index("installer_traduction_qt")
            < appels.index("prendre_le_verrou"))
