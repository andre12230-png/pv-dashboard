"""Accorder un mot avec un nombre : « 1 jour », « 1 614 jours ».

Plutot que « jour(s) » : l'application connait le nombre, elle accorde
(relecture du 29/09/2026, charte des trois applis). Comme en francais, 0 et
1 restent au singulier (« 0 ajout », « 1 ajout », « 2 ajouts »).
"""
from __future__ import annotations


def nombre(n: int) -> str:
    """« 1 614 » : milliers separes par une espace, comme les montants."""
    return f"{n:,}".replace(",", " ")


def accorde(n: int, singulier: str, forme_plurielle: str | None = None) -> str:
    """Le mot seul, accorde : accorde(2, "nouveau", "nouveaux") -> « nouveaux ».

    Sans forme plurielle donnee, on ajoute un « s ».
    """
    if n > 1:
        return forme_plurielle or singulier + "s"
    return singulier


def pluriel(n: int, singulier: str, forme_plurielle: str | None = None) -> str:
    """Le nombre et le mot accorde : pluriel(1614, "jour") -> « 1 614 jours »."""
    return f"{nombre(n)} {accorde(n, singulier, forme_plurielle)}"
