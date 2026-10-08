"""Les boites de message disent l'action, et Mes reglages a l'allure des
ecrans (relecture des fenetres, 30/09/2026).

- La charte prefere des boutons qui disent l'action a « Oui / Non » : les
  trois confirmations de la Saisie quotidienne passent par `confirmer`.
- L'invitation a donner son avis porte une icone, comme les autres boites.
- Mes reglages range ses cases dans des cartes a bandeau, plus dans des
  cadres gris.

    py -m pytest tests/test_boites_action.py
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from conftest import detruire  # noqa: E402
from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QGroupBox,
    QLabel,
    QMessageBox,
)

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def boite_vue(monkeypatch):
    """Remplace l'attente du clic : note ce que la boite montre."""
    vu = {}

    def regarder(self):
        vu["boutons"] = [b.text().replace("&", "") for b in self.buttons()]
        defaut = self.defaultButton()
        vu["defaut"] = defaut.text().replace("&", "") if defaut else ""
        vu["icone"] = self.icon()
        return 0
    monkeypatch.setattr(QMessageBox, "exec", regarder)
    return vu


def test_confirmer_nomme_l_action(qapp, boite_vue):
    from gui_widgets import confirmer
    reponse = confirmer(None, "Titre", "Message", "Appliquer l'import",
                        annuler_par_defaut=False)
    assert reponse is False                      # personne n'a clique
    assert boite_vue["boutons"] == ["Appliquer l'import", "Annuler"]
    assert boite_vue["defaut"] == "Appliquer l'import"
    assert boite_vue["icone"] == QMessageBox.Question


def test_confirmer_garde_annuler_par_defaut_et_avertit(qapp, boite_vue):
    from gui_widgets import confirmer
    confirmer(None, "Titre", "Message", "Enregistrer quand même",
              avertissement=True)
    assert boite_vue["defaut"] == "Annuler"
    assert boite_vue["icone"] == QMessageBox.Warning


def test_la_saisie_ne_pose_plus_de_question_oui_non():
    source = (RACINE / "views" / "saisie.py").read_text(encoding="utf-8")
    assert "QMessageBox.question" not in source
    assert "QMessageBox.Yes" not in source
    # Les messages ne renvoient plus a un bouton « Non » qui n'existe plus.
    assert "pondez Non" not in source


def test_l_invitation_porte_une_icone(qapp, boite_vue, tmp_path):
    import avis
    reglages = QSettings(str(tmp_path / "p.ini"), QSettings.Format.IniFormat)
    avis.inviter(None, reglages, date(2026, 9, 30), "1.0.0")
    assert boite_vue["icone"] == QMessageBox.Question


def test_mes_reglages_range_ses_cases_dans_des_cartes(qapp):
    from test_reglages import VALEURS_FENETRE

    import reglages as rg
    from fenetre_reglages import FenetreReglages
    fenetre = FenetreReglages(dict(VALEURS_FENETRE), lambda v: None, None,
                              recalages=rg.recalages_vides(),
                              enregistrer_recalages=lambda r: None)
    try:
        assert fenetre.findChildren(QGroupBox) == []
        bandeaux = [lbl.text() for lbl in fenetre.findChildren(QLabel)
                    if lbl.objectName() == "CardHeader"]
        assert bandeaux == ["MON INSTALLATION", "MA VENTE D'ÉLECTRICITÉ",
                            "MON FOURNISSEUR D'ÉLECTRICITÉ",
                            "RECALAGES SUR MES FACTURES"]
    finally:
        detruire(fenetre)


def test_mes_reglages_enregistrer_a_l_allure_de_la_saisie(qapp):
    """Choix de l'auteur du 08/10/2026 : « Enregistrer » est bleu partout,
    comme dans la Saisie (il etait gris dans Mes réglages)."""
    from test_reglages import VALEURS_FENETRE

    import reglages as rg
    from fenetre_reglages import FenetreReglages
    fenetre = FenetreReglages(dict(VALEURS_FENETRE), lambda v: None, None,
                              recalages=rg.recalages_vides(),
                              enregistrer_recalages=lambda r: None)
    try:
        assert fenetre.btn_enregistrer.objectName() == "SaveBtn"
    finally:
        fenetre.deleteLater()
