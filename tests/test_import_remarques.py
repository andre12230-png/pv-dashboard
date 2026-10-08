"""Imports : ce que l'application a devine ou ecarte, elle le dit.

Revue du 28/09/2026 : les lignes illisibles etaient ignorees sans un mot,
l'unite (Wh ou kWh) devinee sans le dire -- une erreur multiplie tout par
mille --, et seul le premier fichier d'une archive .zip etait lu. Ces
remarques s'affichent dans le recapitulatif, avant la confirmation.
Valeurs inventees.
"""
from __future__ import annotations

import zipfile

import pytest

import data_loaders as dl


def _fichier(tmp_path, contenu: str, nom: str = "releve.csv") -> str:
    p = tmp_path / nom
    p.write_text(contenu, encoding="utf-8")
    return str(p)


# --- Unite devinee -----------------------------------------------------------

def test_unite_absente_valeurs_en_kwh_le_dit(tmp_path):
    notes: list[str] = []
    resultat = dl.parse_enedis_fichier(_fichier(
        tmp_path, "Date;Consommation\n01/09/2026;5,5\n02/09/2026;6\n"), notes)
    assert resultat == {"Conso_réseau_Jour": {"01/09/2026": "5,5",
                                              "02/09/2026": "6"}}
    assert any("kWh" in n and "grandeur" in n for n in notes)


def test_unite_absente_valeurs_en_wh_converties_et_le_dit(tmp_path):
    notes: list[str] = []
    resultat = dl.parse_enedis_fichier(_fichier(
        tmp_path, "Date;Consommation\n01/09/2026;5500\n02/09/2026;6000\n"),
        notes)
    assert resultat == {"Conso_réseau_Jour": {"01/09/2026": "5,5",
                                              "02/09/2026": "6"}}
    assert any("Wh" in n and "grandeur" in n for n in notes)


def test_unite_dans_l_en_tete_rien_a_dire(tmp_path):
    notes: list[str] = []
    dl.parse_enedis_fichier(_fichier(
        tmp_path, "Date;Consommation (kWh)\n01/09/2026;5,5\n"), notes)
    assert not any("grandeur" in n for n in notes)


def test_production_unite_devinee_le_dit(tmp_path):
    notes: list[str] = []
    resultat = dl.parse_enphase_fichier(_fichier(
        tmp_path, "Date;Production\n01/09/2026;20500\n02/09/2026;18000\n"),
        notes)
    assert resultat == {"Prod_Jour": {"01/09/2026": "20,5",
                                      "02/09/2026": "18"}}
    assert any("Wh" in n and "grandeur" in n for n in notes)


# --- Lignes ecartees ---------------------------------------------------------

def test_ligne_datee_illisible_comptee(tmp_path):
    notes: list[str] = []
    resultat = dl.parse_enedis_fichier(_fichier(
        tmp_path,
        "Date;Consommation (kWh)\n01/09/2026;5,5\n02/09/2026;abc\n"
        "03/09/2026;\n"), notes)
    assert resultat == {"Conso_réseau_Jour": {"01/09/2026": "5,5"}}
    assert any("2 ligne" in n and "02/09/2026" in n for n in notes)


def test_detail_hc_hp_ligne_illisible_comptee(tmp_path):
    notes: list[str] = []
    dl.parse_enedis_fichier(_fichier(
        tmp_path, "Date;HC;HP\n01/09/2026;5,1;2,4\n02/09/2026;x;y\n"), notes)
    assert any("1 ligne" in n and "02/09/2026" in n for n in notes)


def test_production_ligne_illisible_comptee(tmp_path):
    notes: list[str] = []
    dl.parse_enphase_fichier(_fichier(
        tmp_path,
        "Date;Production (kWh)\n01/09/2026;20,5\n02/09/2026;--\n"), notes)
    assert any("1 ligne" in n and "02/09/2026" in n for n in notes)


def test_en_tetes_et_metadonnees_ne_comptent_pas(tmp_path):
    # Seules les lignes qui commencent par une date sont des journees.
    notes: list[str] = []
    dl.parse_enedis_fichier(_fichier(
        tmp_path,
        "Export du compteur;xyz\nDate;Consommation (kWh)\n01/09/2026;5,5\n"),
        notes)
    assert not any("ligne" in n for n in notes)


# --- Archive .zip ------------------------------------------------------------

def _zip(tmp_path, fichiers: dict[str, str]) -> str:
    p = tmp_path / "rapport.zip"
    with zipfile.ZipFile(p, "w") as z:
        for nom, contenu in fichiers.items():
            z.writestr(nom, contenu)
    return str(p)


def test_zip_tous_les_fichiers_sont_lus(tmp_path):
    notes: list[str] = []
    resultat = dl.parse_enphase_fichier(_zip(tmp_path, {
        "aout.csv": "Date;Production (kWh)\n31/08/2026;20\n",
        "septembre.csv": "Date;Production (kWh)\n01/09/2026;18\n",
        "lisez-moi.txt": "rien a lire\n",
    }), notes)
    assert resultat == {"Prod_Jour": {"31/08/2026": "20", "01/09/2026": "18"}}
    assert any("2 fichiers" in n for n in notes)


def test_zip_meme_jour_meme_valeur_accepte(tmp_path):
    resultat = dl.parse_enphase_fichier(_zip(tmp_path, {
        "a.csv": "Date;Production (kWh)\n01/09/2026;18\n",
        "b.csv": "Date;Production (kWh)\n01/09/2026;18\n02/09/2026;19\n",
    }))
    assert resultat == {"Prod_Jour": {"01/09/2026": "18", "02/09/2026": "19"}}


def test_zip_deux_fichiers_qui_se_contredisent_refuse(tmp_path):
    with pytest.raises(ValueError) as erreur:
        dl.parse_enphase_fichier(_zip(tmp_path, {
            "a.csv": "Date;Production (kWh)\n01/09/2026;18\n",
            "b.csv": "Date;Production (kWh)\n01/09/2026;25\n",
        }))
    texte = str(erreur.value)
    assert "01/09/2026" in texte and "a.csv" in texte and "b.csv" in texte


def test_zip_un_seul_fichier_rien_a_dire(tmp_path):
    notes: list[str] = []
    dl.parse_enphase_fichier(_zip(tmp_path, {
        "rapport.csv": "Date;Production (kWh)\n01/09/2026;18\n"}), notes)
    assert not any("fichiers" in n for n in notes)


# --- Valeurs invraisemblables (28/09/2026) -----------------------------------
# Le plafond de la saisie a la main ne s'appliquait pas aux imports : des Wh
# lus comme des kWh (mille fois trop) passaient sans alerte.

def test_vraisemblance_rien_a_dire_sur_des_valeurs_normales():
    assert dl.controle_vraisemblance(
        "Conso_réseau_Jour", {"01/09/2026": "12,5"}, "Consommation") is None


def test_vraisemblance_consommation_mille_fois_trop_grande():
    alerte = dl.controle_vraisemblance(
        "Conso_réseau_Jour",
        {"01/09/2026": "5500", "02/09/2026": "12", "03/09/2026": "6100"},
        "Consommation réseau")
    assert "2 valeurs de Consommation réseau dépassent" in alerte
    assert "01/09/2026" in alerte and "150\xa0kWh" in alerte
    assert "Consommation réseau" in alerte


def test_vraisemblance_production_suit_la_puissance():
    # 3 kWc -> 30 kWh par jour au plus ; 45 est suspect ici, pas sur 6 kWc.
    valeurs = {"01/07/2026": "45"}
    assert dl.controle_vraisemblance("Prod_Jour", valeurs, "Production",
                                     puissance_kwc=3.0) is not None
    assert dl.controle_vraisemblance("Prod_Jour", valeurs, "Production",
                                     puissance_kwc=6.0) is None
