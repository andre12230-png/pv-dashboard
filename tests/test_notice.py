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
