"""La Notice decoupee en rubriques, avec un sommaire (audit du 14/09/2026).

Le decoupage ne doit rien perdre du texte : chaque titre de rubrique devient
une entree du sommaire, dans l'ordre, et le texte recolle est identique.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from views.aide import NOTICE_HTML, AideView  # noqa: E402


def test_une_rubrique_par_titre_dans_l_ordre():
    rubriques = AideView._decouper(NOTICE_HTML)
    assert len(rubriques) == NOTICE_HTML.count("<h3")
    assert rubriques[0][0] == "À quoi sert l'application"
    assert rubriques[-1][0] == "Bon à savoir"


def test_le_decoupage_ne_perd_aucun_texte():
    rubriques = AideView._decouper(NOTICE_HTML)
    assert "".join(corps for _, corps in rubriques) == NOTICE_HTML.lstrip()


def test_chaque_rubrique_commence_par_son_titre():
    for titre, corps in AideView._decouper(NOTICE_HTML):
        assert corps.startswith("<h3")
        assert titre

def test_la_notice_donne_le_format_hphc():
    """Avis du 18/09/2026 : personne ne devinait les en-tetes a ecrire.

    La notice doit montrer les libelles acceptes ET un exemple de ligne.
    """
    assert "Consommation HC (kWh)" in NOTICE_HTML
    assert "Consommation HP (kWh)" in NOTICE_HTML
    assert "Date;Consommation (kWh);Consommation HC (kWh)" in NOTICE_HTML

def test_la_notice_parle_de_l_export_d_index_enedis():
    """L'index n'est pas une consommation : si la notice ne le dit pas,
    personne ne comprend pourquoi ce fichier-la marche."""
    assert "index quotidiens" in NOTICE_HTML
    assert "calendrier fournisseur" in NOTICE_HTML

def test_la_notice_renvoie_les_recalages_vers_la_fenetre():
    """Demande d'un utilisateur (18/09/2026) : ne plus imposer le Bloc-notes.
    Si la notice ne le dit pas, la fenetre ne sert a rien."""
    assert "Recalages sur mes factures" in NOTICE_HTML
    assert "Injection payée par EDF OA" in NOTICE_HTML

def test_la_notice_previent_pour_le_premier_jour_d_un_index():
    """Un utilisateur a perdu le jour de sa mise en service sans comprendre
    pourquoi (18/09/2026). La parade — partir de la veille — doit être écrite."""
    assert "partez de la veille" in NOTICE_HTML
    assert "sert de référence" in NOTICE_HTML
    # Et le menu qui manquait à son export.
    assert "Mixte" in NOTICE_HTML
