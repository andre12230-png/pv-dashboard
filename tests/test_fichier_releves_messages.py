"""Messages du fichier des releves mal forme (audit du 08/10/2026).

Releves inventes.

    py -m pytest tests/test_fichier_releves_messages.py
"""

from __future__ import annotations

import pytest

import data_loaders as dl


def test_separateur_virgule_dit_ce_qui_est_attendu(tmp_path):
    """Un fichier separe par des virgules (Excel en anglais) etait annonce
    « non reconnu », sans dire pourquoi."""
    chemin = tmp_path / "Releves-pv.csv"
    chemin.write_text("Date,Prod_Jour,Inj_Jour\n01/06/2026,12,4\n",
                      encoding="utf-8")
    with pytest.raises(ValueError) as e:
        dl.read_releves_raw(str(chemin))
    assert "point-virgule" in str(e.value)


def test_colonnes_manquantes_dit_comment_les_ajouter(tmp_path):
    """Le refus reste (une colonne lue vide serait effacee a
    l'enregistrement), mais le message dit quoi faire."""
    chemin = tmp_path / "Releves-pv.csv"
    chemin.write_text("Date;Prod_Jour;Inj_Jour\n01/06/2026;12;4\n",
                      encoding="utf-8")
    with pytest.raises(ValueError) as e:
        dl.read_releves_raw(str(chemin))
    texte = str(e.value)
    assert "Conso_HC" in texte
    assert "ajoutez" in texte.lower()
