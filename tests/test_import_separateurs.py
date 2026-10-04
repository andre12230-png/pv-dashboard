"""
Imports de consommation / injection : les separateurs promis par la Notice.

La Notice annonce « point-virgule, virgule ou tabulation ». Ces tests gardent
la promesse pour les deux lecteurs du bouton conso / injection : le fichier
simple « date + valeur » et le fichier avec le detail heures creuses / pleines.
Valeurs inventees.
"""
from __future__ import annotations

import data_loaders as dl


def _importer(tmp_path, contenu: str) -> dict[str, dict[str, str]]:
    p = tmp_path / "releve.csv"
    p.write_text(contenu, encoding="utf-8")
    return dl.parse_enedis_fichier(str(p))


# --- Fichier simple « date + valeur » --------------------------------------

def test_conso_separee_par_des_virgules(tmp_path):
    # Separateur virgule : le point est alors le seul separateur decimal.
    resultat = _importer(
        tmp_path,
        "Date,Consommation (kWh)\n"
        "2026-09-01,5.5\n"
        "2026-09-02,4\n",
    )
    assert resultat == {
        "Conso_réseau_Jour": {"01/09/2026": "5,5", "02/09/2026": "4"},
    }


def test_injection_separee_par_des_virgules(tmp_path):
    resultat = _importer(
        tmp_path,
        "Date,Injection (kWh)\n"
        "01/09/2026,10.25\n",
    )
    assert resultat == {"Inj_Jour": {"01/09/2026": "10,25"}}


def test_point_virgule_garde_la_virgule_decimale(tmp_path):
    # Le cas courant ne doit pas changer : « 5,5 » reste cinq et demi.
    resultat = _importer(
        tmp_path,
        "Date;Consommation (kWh)\n"
        "01/09/2026;5,5\n",
    )
    assert resultat == {"Conso_réseau_Jour": {"01/09/2026": "5,5"}}


# --- Fichier avec le detail heures creuses / heures pleines ----------------

def test_detail_hc_hp_separe_par_des_tabulations(tmp_path):
    # Defaut d'origine : la colonne HC etait rangee comme consommation
    # TOTALE, et les heures pleines perdues, sans aucun avertissement.
    resultat = _importer(
        tmp_path,
        "Date\tConsommation HC (kWh)\tConsommation HP (kWh)\n"
        "01/09/2026\t5,1\t2,4\n",
    )
    assert resultat == {
        "Conso_HC": {"01/09/2026": "5,1"},
        "Conso_HP": {"01/09/2026": "2,4"},
    }


def test_detail_hc_hp_separe_par_des_virgules(tmp_path):
    resultat = _importer(
        tmp_path,
        "Date,HC,HP\n"
        "2026-09-01,5.1,2.4\n",
    )
    assert resultat == {
        "Conso_HC": {"01/09/2026": "5,1"},
        "Conso_HP": {"01/09/2026": "2,4"},
    }


# --- Releves heure par heure (audit du 04/10/2026) -------------------------

def test_une_courbe_heure_par_heure_est_refusee(tmp_path):
    """Plusieurs lignes horodatees pour un meme jour : la derniere ecrasait
    les autres en silence. Additionner serait faux aussi (une courbe de
    charge Enedis donne souvent une puissance en W, pas une energie) : on
    refuse, en disant quoi exporter."""
    import pytest
    with pytest.raises(ValueError, match="quotidien"):
        _importer(tmp_path,
                  "Date;Consommation (Wh)\n"
                  "2026-09-01T00:00:00+02:00;300\n"
                  "2026-09-01T00:30:00+02:00;250\n"
                  "2026-09-01T01:00:00+02:00;200\n")


def test_une_date_avec_minuit_une_fois_par_jour_passe(tmp_path):
    """Un export quotidien peut ecrire « 2026-09-01 00:00:00 » : une seule
    ligne par jour, c'est bien un releve quotidien."""
    resultat = _importer(tmp_path,
                         "Date;Consommation (kWh)\n"
                         "2026-09-01 00:00:00;5,5\n"
                         "2026-09-02 00:00:00;4\n")
    assert resultat == {
        "Conso_réseau_Jour": {"01/09/2026": "5,5", "02/09/2026": "4"}}
