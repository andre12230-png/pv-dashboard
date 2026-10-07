"""Montants et nombres à espaces insécables (charte, section 4).

Avec une espace ordinaire, « 1 494,74 € » pouvait se couper en fin de
ligne : « 1 » d'un côté, « 494,74 € » de l'autre. Les milliers et l'unité
sont séparés par une espace insécable (\\xa0), comme dans Pécule
(07/10/2026).
"""
from __future__ import annotations

import pytest

pytest.importorskip("pandas")

from accords import nombre  # noqa: E402
from views._helpers import (fmt_eur, fmt_kwh, fmt_kwh_seul,  # noqa: E402
                            fmt_pct, fmt_prix_kwh, nombre_barre)

NBSP = "\xa0"


def test_les_montants_ne_se_coupent_pas():
    assert fmt_eur(1494.74) == f"1{NBSP}494,74{NBSP}€"
    assert fmt_eur(1494.74, signed=True) == f"+1{NBSP}494,74{NBSP}€"
    assert fmt_eur(-9000) == f"-9{NBSP}000,00{NBSP}€"


def test_les_nombres_ne_se_coupent_pas():
    assert fmt_kwh_seul(3650) == f"3{NBSP}650,0{NBSP}kWh"
    assert nombre_barre(7812) == f"7{NBSP}812"
    assert nombre(1614) == f"1{NBSP}614"


def test_l_unite_reste_collee_au_nombre():
    assert fmt_kwh(27.3) == f"27,3{NBSP}kWh"
    assert fmt_kwh(2760) == f"2,76{NBSP}MWh"
    assert fmt_pct(41.1) == f"41,1{NBSP}%"
    assert fmt_prix_kwh(0.1985) == f"0,1985{NBSP}€/kWh"


def test_aucune_espace_ordinaire_dans_un_montant():
    for texte in (fmt_eur(1234567.89), fmt_kwh_seul(1234567), nombre(1234567)):
        assert " " not in texte, repr(texte)
