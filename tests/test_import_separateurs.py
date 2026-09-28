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
