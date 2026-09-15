"""Tests de la TVA sur l'autoconsommation (livraison a soi-meme, LASM).

Deux familles de tests :

1. la MECANIQUE, sur des donnees fabriquees ici : arrondi du formulaire,
   grille tarifaire, valorisation jour par jour, jours sans releve,
   controle avec les factures, projection de l'annee en cours ;

2. les VALEURS DEJA DEPOSEES aupres du SIE, verifiees sur le vrai fichier de
   releves. Ces chiffres personnels ne sont pas publies : ils vivent dans
   tests/test_tva_deposee.py, present sur la seule machine de l'auteur et
   exclu du depot par .gitignore.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

import calculations as calc

RACINE = Path(calc.__file__).resolve().parent


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def lasm() -> calc.LasmConfig:
    """Deux periodes bien separees, pour que le jour par jour se voie.

    Premier semestre 2024 a 0,12 EUR/kWh, second a 0,25 : un ecart enorme,
    volontairement, pour qu'aucune erreur d'affectation ne passe inapercue.
    """
    return calc.LasmConfig(
        periodes=[
            {"debut": "2024-01-01", "fin": "2024-06-30",
             "prix_ht": 0.10, "accise": 0.02},
            {"debut": "2024-07-01", "fin": None,
             "prix_ht": 0.20, "accise": 0.05},
        ],
        taux=0.20,
    )


def _releves(jours: list[tuple[str, float, float | None]]) -> pd.DataFrame:
    """Fabrique une serie journaliere comme le fait merge_series.

    Chaque jour est un triplet (date, production, injection). Une injection a
    None represente un jour sans releve : injection a zero et drapeau
    releve_incomplet leve, exactement ce que produit le chargement du CSV
    quand la colonne Inj_Jour est vide.
    """
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d, _, _ in jours])
    prod = [p for _, p, _ in jours]
    inj = [0.0 if i is None else i for _, _, i in jours]
    incomplet = [1.0 if i is None else 0.0 for _, _, i in jours]
    df = pd.DataFrame(
        {"production_kwh": prod, "injection_kwh": inj,
         "releve_incomplet": incomplet},
        index=idx,
    )
    df["autoconsommation_kwh"] = (
        df["production_kwh"] - df["injection_kwh"]).clip(lower=0)
    df["soutirage_kwh"] = 0.0
    df["consommation_kwh"] = df["autoconsommation_kwh"]
    return df


# -----------------------------------------------------------------------------
# Arrondi du formulaire
# -----------------------------------------------------------------------------

def test_arrondi_euro_tranche_les_demis_vers_le_haut():
    """round() de Python arrondit au pair : round(0.5) vaut 0. Pas le fisc."""
    assert calc.arrondi_euro(0.5) == 1
    assert calc.arrondi_euro(1.5) == 2
    assert calc.arrondi_euro(84.5) == 85


def test_arrondi_euro_cas_courants():
    assert calc.arrondi_euro(85.23) == 85
    assert calc.arrondi_euro(88.74) == 89
    assert calc.arrondi_euro(102.32) == 102


# -----------------------------------------------------------------------------
# Grille tarifaire
# -----------------------------------------------------------------------------

def test_periodes_lasm_absentes_ne_font_pas_planter():
    """La section tva_lasm est facultative : elle ne concerne que les
    producteurs assujettis a la TVA."""
    assert calc.periodes_lasm(None) == []
    assert calc.periodes_lasm({}) == []


def test_periodes_lasm_sont_triees():
    periodes = calc.periodes_lasm({"periodes": [
        {"debut": "2025-01-01", "prix_ht": 0.2, "accise": 0.0},
        {"debut": "2023-01-01", "prix_ht": 0.1, "accise": 0.0},
    ]})
    assert [p["debut"] for p in periodes] == ["2023-01-01", "2025-01-01"]


def test_prix_lasm_additionne_energie_et_accise(lasm):
    idx = pd.DatetimeIndex(["2024-03-01", "2024-09-01"])
    prix = calc.prix_lasm_serie(idx, lasm.periodes)

    assert prix.iloc[0] == pytest.approx(0.12)
    assert prix.iloc[1] == pytest.approx(0.25)


def test_prix_lasm_derniere_periode_reste_en_cours(lasm):
    """Une periode a 'fin' vide court jusqu'a nouvel ordre : sans cela,
    l'annee en cours serait valorisee a zero."""
    prix = calc.prix_lasm_serie(pd.DatetimeIndex(["2027-05-05"]), lasm.periodes)

    assert prix.iloc[0] == pytest.approx(0.25)


# -----------------------------------------------------------------------------
# Base LASM : la valorisation se fait jour par jour
# -----------------------------------------------------------------------------

def test_base_valorise_chaque_jour_a_son_tarif(lasm):
    """C'est le coeur de la methode : 6 kWh au premier tarif, 8 au second."""
    df = _releves([("2024-01-15", 10.0, 4.0), ("2024-07-15", 10.0, 2.0)])

    kwh, base = calc.base_lasm_periode(
        df, lasm, pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31"))

    assert kwh == pytest.approx(14.0)
    assert base == pytest.approx(6 * 0.12 + 8 * 0.25)


def test_une_moyenne_annuelle_donnerait_un_autre_resultat(lasm):
    """Preuve par l'absurde que le jour par jour n'est pas un detail.

    Le meme volume valorise a la moyenne des deux tarifs donne 2,59 EUR au
    lieu de 2,72 : l'autoconsommation n'est pas repartie egalement sur
    l'annee, elle se concentre l'ete, du cote du tarif le plus cher.
    """
    df = _releves([("2024-01-15", 10.0, 4.0), ("2024-07-15", 10.0, 2.0)])

    _, base = calc.base_lasm_periode(
        df, lasm, pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31"))
    moyenne_naive = 14.0 * (0.12 + 0.25) / 2

    assert base == pytest.approx(2.72)
    assert moyenne_naive == pytest.approx(2.59)
    assert base != pytest.approx(moyenne_naive)


def test_autoconsommation_jamais_negative(lasm):
    """Une injection relevee au-dessus de la production (arrondis, decalage
    d'horodatage) ne doit pas creer une base negative."""
    df = _releves([("2024-03-01", 5.0, 8.0)])

    kwh, base = calc.base_lasm_periode(
        df, lasm, pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31"))

    assert kwh == 0.0
    assert base == 0.0


# -----------------------------------------------------------------------------
# Recapitulatif par annee
# -----------------------------------------------------------------------------

def test_lasm_par_annee_calcule_base_et_tva(lasm):
    # Le 31/12 a zero ferme l'annee : les releves vont jusqu'au bout, la
    # ligne est definitive et non projetee.
    df = _releves([("2024-01-15", 10.0, 4.0), ("2024-07-15", 10.0, 2.0),
                   ("2024-12-31", 0.0, 0.0)])

    lignes = calc.lasm_par_annee(df, lasm, aujourdhui=date(2025, 3, 1))

    assert len(lignes) == 1
    ligne = lignes[0]
    assert ligne["annee"] == 2024
    assert ligne["autoconsommation_kwh"] == pytest.approx(14.0)
    assert ligne["part_autoconso"] == pytest.approx(14 / 20)
    assert ligne["base_eur"] == pytest.approx(2.72)
    assert ligne["base_5a_eur"] == 3
    assert ligne["tva_due_eur"] == 1
    assert ligne["prix_moyen_eur_kwh"] == pytest.approx(2.72 / 14)
    assert ligne["estimation"] is False


def test_les_jours_sans_injection_sont_comptes_et_signales(lasm):
    """Un jour sans releve compte toute sa production en autoconsommation :
    la base est majoree, et il faut que ca se voie."""
    df = _releves([("2024-03-01", 10.0, 4.0), ("2024-03-02", 10.0, None)])

    ligne = calc.lasm_par_annee(df, lasm, aujourdhui=date(2025, 1, 1))[0]

    assert ligne["jours_sans_injection"] == 1
    # 6 kWh le jour releve, 10 kWh le jour sans releve.
    assert ligne["autoconsommation_kwh"] == pytest.approx(16.0)


def test_annee_sans_production_ne_divise_pas_par_zero(lasm):
    df = _releves([("2024-03-01", 0.0, 0.0)])

    ligne = calc.lasm_par_annee(df, lasm, aujourdhui=date(2025, 1, 1))[0]

    assert ligne["part_autoconso"] == 0.0
    assert ligne["prix_moyen_eur_kwh"] == 0.0
    assert ligne["tva_due_eur"] == 0


def test_releves_vides_ne_donnent_aucune_ligne(lasm):
    assert calc.lasm_par_annee(pd.DataFrame(), lasm) == []


# -----------------------------------------------------------------------------
# Projection de l'annee en cours
# -----------------------------------------------------------------------------

def _lasm_plat() -> calc.LasmConfig:
    """Un tarif unique : la projection se lit alors directement en kWh."""
    return calc.LasmConfig(
        periodes=[{"debut": "2020-01-01", "fin": None,
                   "prix_ht": 0.10, "accise": 0.0}],
        taux=0.20,
    )


def test_annee_en_cours_est_projetee_et_marquee_estimee():
    """2023 et 2024 ont fait la moitie de leur autoconso au 30/06. 2025 en
    est a 60 kWh a cette date : on projette donc 120 kWh."""
    df = _releves([
        ("2023-01-15", 100.0, 0.0), ("2023-09-15", 100.0, 0.0),
        ("2024-01-15", 100.0, 0.0), ("2024-09-15", 100.0, 0.0),
        ("2025-01-15", 60.0, 0.0), ("2025-06-30", 0.0, 0.0),
    ])

    lignes = calc.lasm_par_annee(df, _lasm_plat(), aujourdhui=date(2025, 6, 30))
    par_annee = {ligne["annee"]: ligne for ligne in lignes}

    assert par_annee[2023]["estimation"] is False
    assert par_annee[2024]["estimation"] is False
    assert par_annee[2025]["estimation"] is True
    assert par_annee[2025]["autoconsommation_kwh"] == pytest.approx(120.0)
    assert par_annee[2025]["base_eur"] == pytest.approx(12.0)


def test_projection_ne_depasse_pas_le_dernier_releve():
    """Si le CSV s'arrete avant aujourd'hui, la projection part de la
    derniere journee renseignee, pas de la date du jour."""
    df = _releves([
        ("2023-01-15", 100.0, 0.0), ("2023-09-15", 100.0, 0.0),
        ("2024-01-15", 100.0, 0.0), ("2024-09-15", 100.0, 0.0),
        ("2025-01-15", 60.0, 0.0), ("2025-06-30", 0.0, 0.0),
    ])

    # Trois mois apres le dernier releve : le resultat doit etre le meme.
    tardif = calc.lasm_par_annee(df, _lasm_plat(), aujourdhui=date(2025, 9, 30))
    a_jour = calc.lasm_par_annee(df, _lasm_plat(), aujourdhui=date(2025, 6, 30))

    assert (tardif[-1]["autoconsommation_kwh"]
            == pytest.approx(a_jour[-1]["autoconsommation_kwh"]))


def test_annee_passee_aux_releves_tronques_reste_une_estimation():
    """Annee terminee n'est pas annee complete : s'il manque le dernier
    trimestre, le montant n'est pas definitif et ne doit pas s'annoncer
    comme tel."""
    df = _releves([
        ("2023-01-15", 100.0, 0.0), ("2023-09-15", 100.0, 0.0),
        ("2023-12-31", 0.0, 0.0),
        ("2024-01-15", 100.0, 0.0), ("2024-06-30", 0.0, 0.0),
    ])

    lignes = calc.lasm_par_annee(df, _lasm_plat(), aujourdhui=date(2025, 5, 1))
    par_annee = {ligne["annee"]: ligne for ligne in lignes}

    assert par_annee[2023]["estimation"] is False
    assert par_annee[2024]["estimation"] is True


def test_premiere_annee_ne_se_projette_pas():
    """Sans annee complete derriere elle, il n'y a rien pour extrapoler :
    on garde le realise plutot que d'inventer une part."""
    df = _releves([("2025-01-15", 60.0, 0.0), ("2025-06-30", 0.0, 0.0)])

    ligne = calc.lasm_par_annee(df, _lasm_plat(), aujourdhui=date(2025, 6, 30))[0]

    assert ligne["estimation"] is True
    assert ligne["autoconsommation_kwh"] == pytest.approx(60.0)


# -----------------------------------------------------------------------------
# Controle avec les factures EDF OA
# -----------------------------------------------------------------------------

def test_controle_compare_releve_et_facture():
    df = _releves([("2024-07-01", 100.0, 50.0), ("2024-07-02", 100.0, 50.0)])
    factures = [{"debut": "2024-07-01", "fin": "2024-07-02", "total_kwh": 99,
                 "source": "autofacturation EDF OA"}]

    ligne = calc.controle_injection_facturee(df, factures)[0]

    assert ligne["releve_kwh"] == pytest.approx(100.0)
    assert ligne["facture_kwh"] == pytest.approx(99.0)
    assert ligne["ecart_kwh"] == pytest.approx(1.0)
    assert ligne["ecart_pct"] == pytest.approx(100 / 99 * 100 - 100)
    assert ligne["source"] == "autofacturation EDF OA"


def test_controle_signale_les_jours_estimes():
    """Une periode largement reconstituee ne doit pas passer pour verifiee."""
    df = _releves([("2024-07-01", 100.0, 50.0), ("2024-07-02", 100.0, None)])
    factures = [{"debut": "2024-07-01", "fin": "2024-07-02", "total_kwh": 100}]

    ligne = calc.controle_injection_facturee(df, factures)[0]

    assert ligne["jours_estimes"] == 1


def test_controle_complete_les_jours_sans_releve():
    """Un jour non releve n'est pas un jour a zero injection : sans cette
    correction, une semaine de panne ferait crier au loup."""
    df = _releves([("2024-07-01", 100.0, 50.0), ("2024-07-02", 100.0, None)])
    factures = [{"debut": "2024-07-01", "fin": "2024-07-02", "total_kwh": 100}]

    ligne = calc.controle_injection_facturee(df, factures)[0]

    assert ligne["releve_kwh"] > 50.0


def test_controle_sans_factures_ne_retourne_rien():
    df = _releves([("2024-07-01", 100.0, 50.0)])

    assert calc.controle_injection_facturee(df, None) == []


def test_le_controle_est_rattache_a_l_annee_ou_il_se_cloture():
    """L'annee EDF OA court du 28/06 au 27/06 : celle qui se termine en 2025
    s'affiche sur la ligne 2025."""
    df = _releves([("2024-07-01", 100.0, 50.0), ("2025-01-15", 100.0, 50.0)])
    factures = [{"debut": "2024-06-28", "fin": "2025-06-27", "total_kwh": 100}]

    lignes = calc.lasm_par_annee(df, _lasm_plat(), factures,
                                 aujourdhui=date(2026, 1, 1))
    par_annee = {ligne["annee"]: ligne for ligne in lignes}

    assert par_annee[2024]["controle"] is None
    assert par_annee[2025]["controle"] is not None

