"""« Votre avis » et menu adapte a l'utilisateur.

Deux demandes du 14/09/2026, en vue de la publication :
- un bouton « Votre avis », comme dans Pecule, avec une seule invitation
  deux semaines apres le premier lancement ;
- l'onglet TVA autoconsommation masque a qui n'a pas rempli la section
  tva_lasm : il ne concerne que les producteurs assujettis a la TVA.
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402

import app_desktop  # noqa: E402
import avis  # noqa: E402


@pytest.fixture
def settings(tmp_path):
    """Preferences sur fichier jetable : jamais celles de l'utilisateur."""
    return QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)


@pytest.fixture
def lien_renseigne(monkeypatch):
    monkeypatch.setattr(avis, "FORMULAIRE_AVIS_URL", "https://exemple.invalid/f")


# -----------------------------------------------------------------------------
# L'invitation : une seule fois, apres deux semaines, s'il y a des releves
# -----------------------------------------------------------------------------


def test_premiere_utilisation_jamais_ecrasee(settings):
    avis.noter_premiere_utilisation(settings, date(2026, 9, 1))
    avis.noter_premiere_utilisation(settings, date(2026, 9, 20))
    assert settings.value(avis.CLE_PREMIERE_UTILISATION) == "2026-09-01"


def test_pas_d_invitation_avant_deux_semaines(settings, lien_renseigne):
    avis.noter_premiere_utilisation(settings, date(2026, 9, 1))
    assert not avis.doit_inviter(settings, date(2026, 9, 14), True)
    assert avis.doit_inviter(settings, date(2026, 9, 15), True)


def test_pas_d_invitation_sans_releves(settings, lien_renseigne):
    avis.noter_premiere_utilisation(settings, date(2026, 1, 1))
    assert not avis.doit_inviter(settings, date(2026, 9, 1), False)


def test_une_seule_invitation(settings, lien_renseigne):
    avis.noter_premiere_utilisation(settings, date(2026, 1, 1))
    settings.setValue(avis.CLE_INVITATION_FAITE, "2026-02-01")
    assert not avis.doit_inviter(settings, date(2026, 9, 1), True)


def test_pas_d_invitation_sans_lien(settings, monkeypatch):
    """Tant que le questionnaire n'existe pas, on n'invite personne."""
    monkeypatch.setattr(avis, "FORMULAIRE_AVIS_URL", "")
    avis.noter_premiere_utilisation(settings, date(2026, 1, 1))
    assert not avis.doit_inviter(settings, date(2026, 9, 1), True)


def test_le_questionnaire_a_un_lien():
    """Le questionnaire existe depuis le 15/09/2026 : sans lien, le bouton
    « Ouvrir le questionnaire » serait grise et l'invitation muette."""
    assert avis.FORMULAIRE_AVIS_URL.startswith("https://forms.cloud.microsoft/")


def test_la_version_copiee_nomme_l_application():
    texte = avis.description_systeme("1.2.3")
    assert texte.startswith("Gestion Photovoltaïque 1.2.3")


# -----------------------------------------------------------------------------
# L'onglet TVA n'apparait que si la section tva_lasm est remplie
# -----------------------------------------------------------------------------


def _fenetre(lasm=None, chez_edf=False):
    return SimpleNamespace(data=SimpleNamespace(
        lasm=lasm, meme_fournisseur_que_la_reference=chez_edf))


def test_onglet_tva_masque_sans_grille():
    faux_self = _fenetre(lasm=None)
    assert not app_desktop.MainWindow._entree_visible(faux_self, "tva")


def test_onglet_tva_visible_avec_grille():
    faux_self = _fenetre(lasm=object())
    assert app_desktop.MainWindow._entree_visible(faux_self, "tva")


def test_les_autres_onglets_toujours_visibles():
    faux_self = _fenetre(lasm=None, chez_edf=True)
    for key, _, _, _ in app_desktop.NAV_ITEMS:
        if key not in ("tva", "octopus_edf"):
            assert app_desktop.MainWindow._entree_visible(faux_self, key)


# -----------------------------------------------------------------------------
# L'onglet de comparaison n'apparait que chez un autre fournisseur qu'EDF
# -----------------------------------------------------------------------------


def test_onglet_comparaison_masque_chez_edf():
    faux_self = _fenetre(chez_edf=True)
    assert not app_desktop.MainWindow._entree_visible(faux_self, "octopus_edf")


def test_onglet_comparaison_visible_ailleurs():
    faux_self = _fenetre(chez_edf=False)
    assert app_desktop.MainWindow._entree_visible(faux_self, "octopus_edf")


def _donnees(contrat: dict):
    """Un AppData minimal, juste de quoi lire les noms d'offres."""
    import pandas as pd

    from app_data import AppData
    tarifs = {"contrat_hphc": contrat,
              "comparaison_edf": {"nom": "EDF", "offre": "EDF Tarif Bleu"}}
    return AppData(df=pd.DataFrame(), cfg={"tarifs_reseau": tarifs},
                   oa=None, bleu=None, octopus=None,
                   start_oa=date(2026, 1, 1), releves_path=None, edf_ref=[])


@pytest.mark.parametrize("contrat", [
    {"nom": "EDF"},
    {"nom": "edf"},
    {"nom": "EDF", "offre": "Tarif Bleu HP/HC"},
    {"nom": "Mon fournisseur", "offre": "EDF Tarif Bleu"},
])
def test_chez_edf_reconnu(contrat):
    assert _donnees(contrat).meme_fournisseur_que_la_reference


@pytest.mark.parametrize("contrat", [
    {"nom": "Octopus", "offre": "Octopus Go"},
    {"nom": "Mon fournisseur", "offre": "Mon offre HP/HC"},
    {},                                   # rien de declare : "Mon contrat"
    {"nom": "Fedfer"},                    # "edf" au milieu d'un mot : non
])
def test_autre_fournisseur_reconnu(contrat):
    assert not _donnees(contrat).meme_fournisseur_que_la_reference
