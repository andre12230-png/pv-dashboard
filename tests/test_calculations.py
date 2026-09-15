"""Tests unitaires pour calculations.py (logique metier energetique)."""
from __future__ import annotations

from datetime import date, time, timedelta

import pandas as pd
import pytest

import calculations as calc

# -----------------------------------------------------------------------------
# Fixtures de configuration realistes
# -----------------------------------------------------------------------------

@pytest.fixture
def oa_surplus() -> calc.OAConfig:
    return calc.OAConfig(
        type="surplus",
        prix_kwh=0.13,
        prime_par_kwc=80.0,
        prime_duree=5,
        duree_contrat=20,
    )


@pytest.fixture
def bleu() -> calc.BleuBaseConfig:
    return calc.BleuBaseConfig(
        abonnement_tranches=[
            {"debut": "2023-01-01", "fin": "2024-12-31", "montant": 12.0},
            {"debut": "2025-01-01", "fin": "2025-12-31", "montant": 13.5},
        ],
        tranches=[
            {"debut": "2023-01-01", "fin": "2024-12-31", "prix": 0.25},
            {"debut": "2025-01-01", "fin": "2025-12-31", "prix": 0.27},
        ],
    )


@pytest.fixture
def octopus() -> calc.OctopusConfig:
    # 1 plage HC de 7h (00:30-07:30) -> ratio HC = 7/24
    return calc.OctopusConfig.periode_unique(
        abonnement_mensuel=15.0,
        prix_hp=0.30,
        prix_hc=0.18,
        plages_hc=calc.parse_plages_hc(["00:30-07:30"]),
    )


# -----------------------------------------------------------------------------
# Plages horaires HP/HC
# -----------------------------------------------------------------------------

def test_parse_plage():
    assert calc._parse_plage("00:30-07:30") == (time(0, 30), time(7, 30))


def test_parse_plages_hc():
    plages = calc.parse_plages_hc(["00:30-07:30", "22:00-23:00"])
    assert len(plages) == 2
    assert plages[1] == (time(22, 0), time(23, 0))


def test_is_in_plage_normale():
    plage = (time(0, 30), time(7, 30))
    assert calc._is_in_plage(time(3, 0), plage)
    assert calc._is_in_plage(time(0, 30), plage)         # debut inclusif
    assert not calc._is_in_plage(time(7, 30), plage)     # fin exclusive
    assert not calc._is_in_plage(time(8, 0), plage)


def test_is_in_plage_traverse_minuit():
    plage = (time(22, 0), time(6, 0))
    assert calc._is_in_plage(time(23, 0), plage)
    assert calc._is_in_plage(time(0, 0), plage)
    assert calc._is_in_plage(time(5, 59), plage)
    assert not calc._is_in_plage(time(6, 0), plage)
    assert not calc._is_in_plage(time(10, 0), plage)


def test_is_hc():
    plages = calc.parse_plages_hc(["00:30-07:30"])
    assert calc.is_hc(pd.Timestamp("2026-01-15 03:00"), plages)
    assert not calc.is_hc(pd.Timestamp("2026-01-15 10:00"), plages)


def test_duree_plage_h_normale():
    assert calc._duree_plage_h((time(0, 30), time(7, 30))) == 7.0


def test_duree_plage_h_traverse_minuit():
    assert calc._duree_plage_h((time(22, 0), time(6, 0))) == 8.0


# -----------------------------------------------------------------------------
# Annees OA (28/06 -> 27/06)
# -----------------------------------------------------------------------------

def test_oa_year_bounds():
    start = date(2023, 6, 28)
    debut, fin = calc.oa_year_bounds(start, 1)
    assert (debut, fin) == (date(2023, 6, 28), date(2024, 6, 27))

    debut, fin = calc.oa_year_bounds(start, 3)
    assert (debut, fin) == (date(2025, 6, 28), date(2026, 6, 27))


def test_oa_year_bounds_invalide():
    with pytest.raises(ValueError):
        calc.oa_year_bounds(date(2023, 6, 28), 0)


def test_oa_year_bounds_29_fevrier():
    # Un contrat signe un 29 fevrier n'a pas d'anniversaire chaque annee :
    # date(2025, 2, 29) levait une ValueError et faisait planter la vue.
    start = date(2024, 2, 29)
    assert calc.oa_year_bounds(start, 1) == (date(2024, 2, 29), date(2025, 2, 27))
    assert calc.oa_year_bounds(start, 2) == (date(2025, 2, 28), date(2026, 2, 27))
    assert calc.oa_year_bounds(start, 3) == (date(2026, 2, 28), date(2027, 2, 27))
    # 2028 est bissextile : l'anniversaire retrouve son 29.
    assert calc.oa_year_bounds(start, 4) == (date(2027, 2, 28), date(2028, 2, 28))
    assert calc.oa_year_bounds(start, 5) == (date(2028, 2, 29), date(2029, 2, 27))


def test_oa_year_bounds_29_fevrier_sans_trou_ni_recouvrement():
    # Chaque annee doit reprendre exactement le lendemain de la precedente.
    start = date(2024, 2, 29)
    for n in range(1, 9):
        _, fin = calc.oa_year_bounds(start, n)
        debut_suivant, _ = calc.oa_year_bounds(start, n + 1)
        assert debut_suivant == fin + timedelta(days=1)


def test_oa_year_bounds_31_du_mois():
    # Meme mecanique pour un 31 : fevrier et les mois de 30 jours.
    start = date(2024, 1, 31)
    assert calc.oa_year_bounds(start, 1) == (date(2024, 1, 31), date(2025, 1, 30))
    assert calc.oa_year_bounds(start, 2) == (date(2025, 1, 31), date(2026, 1, 30))


def test_assign_oa_year_29_fevrier():
    start = date(2024, 2, 29)
    idx = pd.DatetimeIndex([
        "2024-02-28",  # avant le debut -> 0
        "2024-02-29",  # debut -> annee 1
        "2025-02-27",  # dernier jour de l'annee 1
        "2025-02-28",  # anniversaire ramene au 28 -> annee 2
        "2026-03-01",  # annee 3
    ])
    assert list(calc.assign_oa_year(idx, start)) == [0, 1, 1, 2, 3]


def test_29_fevrier_ne_change_rien_au_contrat_reel():
    # Le contrat de l'utilisateur demarre un 28/06 : bornes inchangees.
    start = date(2022, 6, 28)
    assert calc.oa_year_bounds(start, 1) == (date(2022, 6, 28), date(2023, 6, 27))
    assert calc.oa_year_bounds(start, 5) == (date(2026, 6, 28), date(2027, 6, 27))


def test_assign_oa_year():
    start = date(2023, 6, 28)
    idx = pd.DatetimeIndex([
        "2023-06-27",  # avant -> 0
        "2023-06-28",  # debut -> 1
        "2024-06-27",  # dernier jour annee 1
        "2024-06-28",  # anniv -> annee 2
        "2025-12-31",  # annee 3
    ])
    years = calc.assign_oa_year(idx, start)
    assert list(years) == [0, 1, 1, 2, 3]


def test_prime_annuelle():
    oa = calc.OAConfig(
        type="surplus", prix_kwh=0.13,
        prime_par_kwc=80.0, prime_duree=5, duree_contrat=20,
    )
    # 6 kWc * 80 / 5 ans
    assert calc.prime_annuelle(6.0, oa) == pytest.approx(96.0)


def test_ratio_hc_observe_utilise_les_jours_detailles(octopus):
    # 2 jours detailles : HC 8 + 8, HP 2 + 2 -> ratio HC = 16/20 = 0,8.
    idx = pd.DatetimeIndex(["2026-01-01", "2026-01-02"])
    df = pd.DataFrame({
        "soutirage_kwh": [10.0, 10.0],
        "soutirage_hc_kwh": [8.0, 8.0],
        "soutirage_hp_kwh": [2.0, 2.0],
    }, index=idx)
    assert calc._ratio_hc_observe(df, octopus) == pytest.approx(0.8)


def test_ratio_hc_observe_defaut_sans_detail(octopus):
    # Sans jour detaille : repli sur la duree des plages HC / 24 h.
    idx = pd.DatetimeIndex(["2026-01-01"])
    df = pd.DataFrame({"soutirage_kwh": [10.0]}, index=idx)
    attendu = sum(calc._duree_plage_h(p) for p in octopus.plages_hc) / 24.0
    assert calc._ratio_hc_observe(df, octopus) == pytest.approx(attendu)


def test_cout_repli_suit_le_ratio_observe(octopus, bleu):
    # 1er jour detaille (tout en HC), 2e sans detail : le 2e doit etre
    # facture au prix du ratio observe (100 % HC), pas a celui des plages.
    idx = pd.DatetimeIndex(["2026-01-01", "2026-01-02"])
    df = pd.DataFrame({
        "soutirage_kwh": [10.0, 10.0],
        "soutirage_hc_kwh": [10.0, float("nan")],
        "soutirage_hp_kwh": [0.0, float("nan")],
    }, index=idx)
    out = calc.cout_reseau_journalier(df, None, bleu, octopus)
    energie = out.loc[idx[1], "cout_reseau_eur"] - out.loc[idx[1], "abonnement_eur"]
    assert energie == pytest.approx(10.0 * octopus.prix_hc(idx[1]))


def test_prime_est_versee_annee_terminee(oa_surplus):
    debut = date(2022, 6, 28)  # annee OA 1 : 28/06/2022 -> 27/06/2023
    auj = date(2026, 8, 1)
    assert calc.prime_est_versee(debut, 1, oa_surplus, auj) is True
    assert calc.prime_est_versee(debut, 4, oa_surplus, auj) is True


def test_prime_est_versee_annee_en_cours(oa_surplus):
    # Annee OA 5 : 28/06/2026 -> 27/06/2027, pas encore terminee au 01/08/2026.
    # C'est ce cas qui faisait diverger la vue Annees OA de la Synthese.
    debut = date(2022, 6, 28)
    assert calc.prime_est_versee(debut, 5, oa_surplus, date(2026, 8, 1)) is False
    # Une fois l'annee echue, elle compte.
    assert calc.prime_est_versee(debut, 5, oa_surplus, date(2027, 7, 1)) is True


def test_prime_est_versee_hors_duree(oa_surplus):
    debut = date(2022, 6, 28)
    auj = date(2035, 1, 1)  # toutes les annees sont echues
    assert calc.prime_est_versee(debut, oa_surplus.prime_duree, oa_surplus, auj) is True
    # Au dela de la duree de la prime, plus rien n'est verse.
    assert calc.prime_est_versee(debut, oa_surplus.prime_duree + 1,
                                 oa_surplus, auj) is False
    assert calc.prime_est_versee(debut, 0, oa_surplus, auj) is False


def test_prime_annuelle_duree_zero():
    oa = calc.OAConfig(
        type="surplus", prix_kwh=0.13,
        prime_par_kwc=80.0, prime_duree=0, duree_contrat=20,
    )
    assert calc.prime_annuelle(6.0, oa) == 0.0


# -----------------------------------------------------------------------------
# Bleu Base : prix et abonnement par date
# -----------------------------------------------------------------------------

def test_prix_bleu_dans_tranche(bleu):
    assert calc._prix_bleu_for_date(pd.Timestamp("2025-06-01"), bleu.tranches) == 0.27


def test_prix_bleu_avant_premiere(bleu):
    assert calc._prix_bleu_for_date(pd.Timestamp("2022-01-01"), bleu.tranches) == 0.25


def test_prix_bleu_apres_derniere(bleu):
    assert calc._prix_bleu_for_date(pd.Timestamp("2026-06-01"), bleu.tranches) == 0.27


def test_abonnement_avant_cutoff(bleu, octopus):
    assert calc.abonnement_mensuel_eur(
        pd.Timestamp("2025-06-15"), bleu, octopus,
    ) == 13.5


def test_abonnement_apres_cutoff(bleu, octopus):
    # A partir de 2026-01-01 -> Octopus, peu importe les tranches Bleu.
    assert calc.abonnement_mensuel_eur(
        pd.Timestamp("2026-01-01"), bleu, octopus,
    ) == 15.0


# -----------------------------------------------------------------------------
# Octopus : plusieurs periodes de prix (revalorisation du 01/08/2026)
# -----------------------------------------------------------------------------

@pytest.fixture
def octopus_deux_periodes() -> calc.OctopusConfig:
    """Grille a deux periodes, calquee sur le vrai changement du 01/08/2026."""
    return calc.OctopusConfig(
        periodes=[
            {"debut": "2026-01-01", "fin": "2026-07-31",
             "abonnement": 19.83, "prix_hp": 0.2132, "prix_hc": 0.1251},
            {"debut": "2026-08-01", "fin": None,
             "abonnement": 20.16, "prix_hp": 0.2213, "prix_hc": 0.1290},
        ],
        plages_hc=calc.parse_plages_hc(["23:56-05:26", "14:26-16:56"]),
    )


def test_octopus_prix_de_chaque_periode(octopus_deux_periodes):
    o = octopus_deux_periodes
    # Dernier jour de l'ancienne grille, puis premier jour de la nouvelle.
    assert o.prix_hc(pd.Timestamp("2026-07-31")) == 0.1251
    assert o.prix_hp(pd.Timestamp("2026-07-31")) == 0.2132
    assert o.abonnement(pd.Timestamp("2026-07-31")) == 19.83
    assert o.prix_hc(pd.Timestamp("2026-08-01")) == 0.1290
    assert o.prix_hp(pd.Timestamp("2026-08-01")) == 0.2213
    assert o.abonnement(pd.Timestamp("2026-08-01")) == 20.16
    # La periode en cours ("fin" vide) continue de s'appliquer plus tard.
    assert o.prix_hc(pd.Timestamp("2027-03-15")) == 0.1290
    # Une charge de nuit reste dans SA journee : 23h56 le 31/07 est encore
    # a l'ancien prix, meme si elle finit le 1er aout.
    assert o.prix_hc(pd.Timestamp("2026-07-31 23:56")) == 0.1251


def test_cout_reseau_change_de_prix_au_01_08_2026(bleu, octopus_deux_periodes):
    # Deux journees identiques (10 kWh en HC) de part et d'autre du changement.
    idx = pd.DatetimeIndex(["2026-07-31", "2026-08-01"])
    df = pd.DataFrame({
        "soutirage_kwh": [10.0, 10.0],
        "soutirage_hc_kwh": [10.0, 10.0],
        "soutirage_hp_kwh": [0.0, 0.0],
    }, index=idx)
    out = calc.cout_reseau_journalier(df, None, bleu, octopus_deux_periodes)
    energie = out["cout_reseau_eur"] - out["abonnement_eur"]
    assert energie.iloc[0] == pytest.approx(10.0 * 0.1251)
    assert energie.iloc[1] == pytest.approx(10.0 * 0.1290)
    # L'abonnement journalier suit aussi la periode (juillet 31 j, aout 31 j).
    assert out["abonnement_eur"].iloc[0] == pytest.approx(19.83 / 31)
    assert out["abonnement_eur"].iloc[1] == pytest.approx(20.16 / 31)


def test_economies_autoconso_change_de_prix_au_01_08_2026(bleu,
                                                          octopus_deux_periodes):
    idx = pd.DatetimeIndex(["2026-07-31", "2026-08-01"])
    df = pd.DataFrame({"autoconsommation_kwh": [10.0, 10.0]}, index=idx)
    out = calc.economies_autoconsommation(df, bleu, octopus_deux_periodes)
    part_hc = octopus_deux_periodes.part_hc_autoconso  # 20 % par defaut
    avant = 0.1251 * part_hc + 0.2132 * (1 - part_hc)
    apres = 0.1290 * part_hc + 0.2213 * (1 - part_hc)
    assert out["economie_eur"].iloc[0] == pytest.approx(10.0 * avant)
    assert out["economie_eur"].iloc[1] == pytest.approx(10.0 * apres)


def test_periodes_octopus_accepte_ancien_config():
    """Un config.yaml d'avant le decoupage en periodes reste utilisable."""
    ancien = {"abonnement_mensuel_eur": 19.83,
              "prix_hp_eur_kwh": 0.2132, "prix_hc_eur_kwh": 0.1251}
    periodes = calc.periodes_octopus(ancien)
    assert len(periodes) == 1
    assert periodes[0]["prix_hc"] == 0.1251
    assert periodes[0]["fin"] is None


def test_periodes_octopus_triees_par_date():
    cfg = {"periodes": [
        {"debut": "2026-08-01", "fin": None,
         "abonnement": 20.16, "prix_hp": 0.2213, "prix_hc": 0.1290},
        {"debut": "2026-01-01", "fin": "2026-07-31",
         "abonnement": 19.83, "prix_hp": 0.2132, "prix_hc": 0.1251},
    ]}
    assert [p["debut"] for p in calc.periodes_octopus(cfg)] == [
        "2026-01-01", "2026-08-01"]


# -----------------------------------------------------------------------------
# Series unifiees (production / reseau)
# -----------------------------------------------------------------------------

def test_merge_series_empty():
    df = calc.merge_series(pd.DataFrame(), pd.DataFrame())
    assert df.empty
    assert list(df.columns) == ["production_kwh", "injection_kwh", "soutirage_kwh"]


def test_merge_series_nominal():
    idx = pd.DatetimeIndex(["2025-06-01", "2025-06-02"])
    prod = pd.DataFrame({"production_kwh": [20.0, 25.0]}, index=idx)
    res = pd.DataFrame(
        {"injection_kwh": [5.0, 10.0], "soutirage_kwh": [2.0, 3.0]}, index=idx,
    )
    df = calc.merge_series(prod, res)
    assert df["autoconsommation_kwh"].tolist() == [15.0, 15.0]
    assert df["consommation_kwh"].tolist() == [17.0, 18.0]


def test_merge_series_autoconso_clip_negative():
    # Si injection > production (mesure erronee), autoconso doit etre clippee a 0.
    idx = pd.DatetimeIndex(["2025-06-01"])
    prod = pd.DataFrame({"production_kwh": [5.0]}, index=idx)
    res = pd.DataFrame({"injection_kwh": [10.0], "soutirage_kwh": [0.0]}, index=idx)
    df = calc.merge_series(prod, res)
    assert df["autoconsommation_kwh"].iloc[0] == 0.0


# -----------------------------------------------------------------------------
# Estimation de l'injection manquante (jours releve_incomplet)
# -----------------------------------------------------------------------------

def _df_avec_incomplet() -> pd.DataFrame:
    # 2 jours complets de juin (ratio injection/prod = 0,5) + 1 jour de
    # juin 2022 sans releve d'injection.
    idx = pd.DatetimeIndex(["2023-06-01", "2023-06-02", "2022-06-15"])
    df = pd.DataFrame({
        "production_kwh": [20.0, 10.0, 30.0],
        "injection_kwh": [10.0, 5.0, 0.0],
        "soutirage_kwh": [2.0, 2.0, 0.0],
        "releve_incomplet": [0.0, 0.0, 1.0],
    }, index=idx)
    df["autoconsommation_kwh"] = (
        df["production_kwh"] - df["injection_kwh"]).clip(lower=0)
    df["consommation_kwh"] = df["autoconsommation_kwh"] + df["soutirage_kwh"]
    return df


def test_estime_injection_manquante_ratio_mensuel():
    out = calc.estime_injection_manquante(_df_avec_incomplet())
    jour = pd.Timestamp("2022-06-15")
    # ratio juin = (10+5)/(20+10) = 0,5 -> injection 15, autoconso 15
    assert out.loc[jour, "injection_kwh"] == pytest.approx(15.0)
    assert out.loc[jour, "autoconsommation_kwh"] == pytest.approx(15.0)
    assert out.loc[jour, "consommation_kwh"] == pytest.approx(15.0)
    # Les jours complets ne bougent pas
    assert out.loc[pd.Timestamp("2023-06-01"), "injection_kwh"] == 10.0


def test_estime_injection_sans_colonne_flag():
    idx = pd.DatetimeIndex(["2023-06-01"])
    df = pd.DataFrame({"production_kwh": [20.0], "injection_kwh": [10.0]},
                      index=idx)
    out = calc.estime_injection_manquante(df)
    assert out.loc[idx[0], "injection_kwh"] == 10.0  # inchange


def test_estime_injection_sans_jour_de_reference():
    # Tous les jours sont incomplets : aucun ratio calculable -> inchange.
    idx = pd.DatetimeIndex(["2022-06-15"])
    df = pd.DataFrame({
        "production_kwh": [30.0], "injection_kwh": [0.0],
        "soutirage_kwh": [0.0], "releve_incomplet": [1.0],
        "autoconsommation_kwh": [30.0], "consommation_kwh": [30.0],
    }, index=idx)
    out = calc.estime_injection_manquante(df)
    assert out.loc[idx[0], "injection_kwh"] == 0.0


# -----------------------------------------------------------------------------
# Repartition de la conso facturee (jours conso_absente)
# -----------------------------------------------------------------------------

def _df_sans_conso() -> pd.DataFrame:
    """4 jours : 3 sans releve de conso, 1 releve a 10 kWh."""
    idx = pd.DatetimeIndex(["2022-05-01", "2022-05-02", "2022-05-03", "2022-05-04"])
    df = pd.DataFrame({
        "production_kwh": [20.0, 20.0, 20.0, 20.0],
        "injection_kwh": [8.0, 8.0, 8.0, 8.0],
        "soutirage_kwh": [0.0, 0.0, 0.0, 10.0],
        "conso_absente": [1.0, 1.0, 1.0, 0.0],
    }, index=idx)
    df["autoconsommation_kwh"] = df["production_kwh"] - df["injection_kwh"]
    df["consommation_kwh"] = df["autoconsommation_kwh"] + df["soutirage_kwh"]
    return df


PERIODES_TEST = [{"debut": "2022-05-01", "fin": "2022-05-04", "total_kwh": 100.0}]


def test_repartit_conso_facturee_deduit_les_jours_releves():
    out = calc.repartit_conso_facturee(_df_sans_conso(), PERIODES_TEST)
    # 100 kWh factures - 10 deja releves = 90 a partager sur 3 jours
    for jour in ("2022-05-01", "2022-05-02", "2022-05-03"):
        assert out.loc[pd.Timestamp(jour), "soutirage_kwh"] == pytest.approx(30.0)
    # Le jour releve n'est pas touche
    assert out.loc[pd.Timestamp("2022-05-04"), "soutirage_kwh"] == 10.0
    # Le total de la periode retombe exactement sur la facture
    assert out["soutirage_kwh"].sum() == pytest.approx(100.0)


def test_repartit_conso_facturee_recalcule_la_consommation():
    out = calc.repartit_conso_facturee(_df_sans_conso(), PERIODES_TEST)
    jour = pd.Timestamp("2022-05-01")
    # consommation = autoconso (12) + soutirage reparti (30)
    assert out.loc[jour, "consommation_kwh"] == pytest.approx(42.0)


def test_repartit_conso_facturee_hors_periode_intacte():
    df = _df_sans_conso()
    periodes = [{"debut": "2021-01-01", "fin": "2021-12-31", "total_kwh": 500.0}]
    out = calc.repartit_conso_facturee(df, periodes)
    assert out["soutirage_kwh"].sum() == 10.0  # rien n'a bouge


def test_repartit_conso_facturee_sans_periodes():
    df = _df_sans_conso()
    assert calc.repartit_conso_facturee(df, None).equals(df)
    assert calc.repartit_conso_facturee(df, []).equals(df)


def test_repartit_conso_facturee_sans_colonne_flag():
    idx = pd.DatetimeIndex(["2022-05-01"])
    df = pd.DataFrame({"soutirage_kwh": [0.0]}, index=idx)
    assert calc.repartit_conso_facturee(df, PERIODES_TEST).equals(df)


def test_repartit_conso_facturee_total_deja_couvert():
    # Les jours releves depassent deja le total facture : pas de conso negative.
    df = _df_sans_conso()
    periodes = [{"debut": "2022-05-01", "fin": "2022-05-04", "total_kwh": 5.0}]
    out = calc.repartit_conso_facturee(df, periodes)
    assert (out["soutirage_kwh"] >= 0).all()
    assert out.loc[pd.Timestamp("2022-05-01"), "soutirage_kwh"] == 0.0


# -----------------------------------------------------------------------------
# Fraicheur des donnees (views/_helpers.py, teste sans Qt)
# -----------------------------------------------------------------------------

AUJOURDHUI = date(2026, 8, 1)


def test_fraicheur_a_jour():
    from views._helpers import fraicheur_donnees
    texte, en_retard = fraicheur_donnees({
        "Prod_Jour": date(2026, 7, 31),
        "Inj_Jour": date(2026, 7, 30),
    }, AUJOURDHUI)
    assert en_retard is False
    assert "à jour" in texte
    assert "Production hier" in texte
    assert "Injection il y a 2 jours" in texte


def test_fraicheur_en_retard():
    # Au-dela de 3 jours sur une grandeur : c'est un import oublie.
    from views._helpers import fraicheur_donnees
    texte, en_retard = fraicheur_donnees({
        "Prod_Jour": date(2026, 7, 31),
        "Conso_HC": date(2026, 7, 20),
    }, AUJOURDHUI)
    assert en_retard is True
    assert "incomplètes" in texte
    assert "Heures creuses il y a 12 jours" in texte
    assert "Importer" in texte  # dit quoi faire


def test_fraicheur_du_jour_meme():
    from views._helpers import fraicheur_donnees
    texte, en_retard = fraicheur_donnees(
        {"Prod_Jour": AUJOURDHUI}, AUJOURDHUI)
    assert en_retard is False
    assert "aujourd'hui" in texte


def test_fraicheur_sans_donnees():
    from views._helpers import fraicheur_donnees
    texte, en_retard = fraicheur_donnees({}, AUJOURDHUI)
    assert en_retard is True
    assert "Aucun relevé" in texte


def test_fraicheur_ignore_les_colonnes_absentes():
    # Une grandeur jamais renseignee ne doit pas apparaitre dans le resume.
    from views._helpers import fraicheur_donnees
    texte, _ = fraicheur_donnees({"Prod_Jour": date(2026, 7, 31)}, AUJOURDHUI)
    assert "Heures creuses" not in texte


def test_dernieres_saisies_par_colonne(tmp_path):
    import data_loaders as dl
    p = tmp_path / "r.csv"
    p.write_text(
        "Date;Prod_Jour;Inj_Jour;Conso_réseau_Jour;Conso_HC;Conso_HP\n"
        "28/07/2026;20,0;15,0;10,0;4,0;6,0\n"
        "29/07/2026;21,0;16,0;11,0;;\n"      # HC/HP pas encore publies
        "30/07/2026;22,0;;;;\n",             # seule la production est saisie
        encoding="utf-8",
    )
    d = dl.dernieres_saisies(str(p))
    assert d["Prod_Jour"] == date(2026, 7, 30)
    assert d["Inj_Jour"] == date(2026, 7, 29)
    assert d["Conso_HC"] == date(2026, 7, 28)


# -----------------------------------------------------------------------------
# Pas de temps des graphiques (views/_helpers.py, teste sans Qt)
# -----------------------------------------------------------------------------

def _df_de(jours: int) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=jours, freq="D")
    return pd.DataFrame({"production_kwh": [1.0] * jours}, index=idx)


@pytest.mark.parametrize("jours, freq, adjectif", [
    (7, "7D", "hebdomadaire"),      # une semaine
    (31, "7D", "hebdomadaire"),     # un mois -> 5 tranches, pas 1 barre
    (70, "7D", "hebdomadaire"),     # limite basse
    (71, "MS", "mensuel"),
    (365, "MS", "mensuel"),         # une annee -> 12 barres
    (550, "MS", "mensuel"),         # limite haute
    (551, "YS", "annuel"),
    (1554, "YS", "annuel"),         # tout l'historique -> 5 barres, pas 208
])
def test_pas_graphique(jours, freq, adjectif):
    from views._helpers import pas_graphique
    f, _, adj = pas_graphique(_df_de(jours))
    assert (f, adj) == (freq, adjectif)


def test_pas_graphique_df_vide():
    from views._helpers import pas_graphique
    freq, _, adj = pas_graphique(pd.DataFrame())
    assert (freq, adj) == ("MS", "mensuel")


def test_pas_graphique_etiquettes_restent_dans_la_periode():
    # Le pas 7D est cale sur le debut : la derniere etiquette ne peut pas
    # deborder du mois affiche (ce que faisait W-MON, nomme par sa fin).
    from views._helpers import pas_graphique
    df = _df_de(31)
    freq, _, _ = pas_graphique(df)
    agrege = df.resample(freq).sum()
    assert agrege.index.max() <= df.index.max()


# -----------------------------------------------------------------------------
# Recalage sur les totaux factures (jours releves mais arrondis)
# -----------------------------------------------------------------------------

def _df_arrondi() -> pd.DataFrame:
    """4 jours releves a l'entier : 10 + 20 + 30 + 40 = 100 kWh."""
    idx = pd.DatetimeIndex(["2024-03-01", "2024-03-02", "2024-03-03", "2024-03-04"])
    df = pd.DataFrame({
        "soutirage_kwh": [10.0, 20.0, 30.0, 40.0],
        "autoconsommation_kwh": [5.0, 5.0, 5.0, 5.0],
    }, index=idx)
    df["consommation_kwh"] = df["autoconsommation_kwh"] + df["soutirage_kwh"]
    return df


def test_recale_repartit_l_ecart_a_parts_egales():
    # Facture 104 pour 100 releves -> +1 kWh sur chacun des 4 jours.
    out = calc.recale_sur_facture(_df_arrondi(), [
        {"debut": "2024-03-01", "fin": "2024-03-04", "total_kwh": 104.0}])
    assert list(out["soutirage_kwh"]) == pytest.approx([11.0, 21.0, 31.0, 41.0])
    assert out["soutirage_kwh"].sum() == pytest.approx(104.0)
    assert out["conso_recalee"].sum() == 4


def test_recale_recalcule_la_consommation():
    out = calc.recale_sur_facture(_df_arrondi(), [
        {"debut": "2024-03-01", "fin": "2024-03-04", "total_kwh": 104.0}])
    assert out.loc[pd.Timestamp("2024-03-01"), "consommation_kwh"] == pytest.approx(16.0)


def test_recale_ecart_negatif_au_prorata():
    # Facture 50 pour 100 releves : chaque jour perd la MEME PROPORTION.
    # Une correction uniforme (-12,5) mettrait le jour a 10 kWh a zero tout
    # en laissant celui a 40 quasi intact -- c'est l'inverse qu'il faut.
    out = calc.recale_sur_facture(_df_arrondi(), [
        {"debut": "2024-03-01", "fin": "2024-03-04", "total_kwh": 50.0}])
    assert list(out["soutirage_kwh"]) == pytest.approx([5.0, 10.0, 15.0, 20.0])
    assert out["soutirage_kwh"].sum() == pytest.approx(50.0)


def test_recale_jamais_de_soutirage_negatif_ni_nul():
    # Facture bien plus basse que le releve : aucun jour ne doit tomber a 0
    # (c'etait le cas des 25, 27 et 28/03/2024 avec l'ancienne repartition).
    out = calc.recale_sur_facture(_df_arrondi(), [
        {"debut": "2024-03-01", "fin": "2024-03-04", "total_kwh": 40.0}])
    assert (out["soutirage_kwh"] > 0).all()
    assert out["soutirage_kwh"].sum() == pytest.approx(40.0)


def test_recale_ecart_positif_reste_uniforme():
    # Decimales perdues : meme quantite pour chacun, pas un prorata.
    out = calc.recale_sur_facture(_df_arrondi(), [
        {"debut": "2024-03-01", "fin": "2024-03-04", "total_kwh": 102.0}])
    assert list(out["soutirage_kwh"]) == pytest.approx([10.5, 20.5, 30.5, 40.5])


def test_recale_ignore_les_jours_sans_releve():
    # Un jour comble par ailleurs (conso_absente) garde sa propre valeur.
    df = _df_arrondi()
    df["conso_absente"] = [1.0, 0.0, 0.0, 0.0]
    out = calc.recale_sur_facture(df, [
        {"debut": "2024-03-01", "fin": "2024-03-04", "total_kwh": 93.0}])
    assert out.loc[pd.Timestamp("2024-03-01"), "soutirage_kwh"] == 10.0  # intact
    releves = out.loc[out["conso_absente"] == 0, "soutirage_kwh"]
    assert releves.sum() == pytest.approx(93.0)


def test_marque_conso_douteuse_pose_les_deux_marqueurs():
    df = _df_arrondi()
    out = calc.marque_conso_douteuse(df, [
        {"debut": "2024-03-02", "fin": "2024-03-03"}])
    assert list(out["conso_douteuse"]) == [0.0, 1.0, 1.0, 0.0]
    assert list(out["conso_absente"]) == [0.0, 1.0, 1.0, 0.0]


def test_jours_douteux_recoivent_le_solde_de_la_facture():
    # 4 jours releves 10/20/30/40. Les deux du milieu sont declares douteux :
    # les deux autres sont corriges de leur troncature (+0,5), et le solde
    # de la facture revient aux douteux.
    df = calc.marque_conso_douteuse(_df_arrondi(), [
        {"debut": "2024-03-02", "fin": "2024-03-03"}])
    out = calc.recale_sur_facture(df, [
        {"debut": "2024-03-01", "fin": "2024-03-04", "total_kwh": 71.0}])
    # jours releves : 10,5 et 40,5 = 51 ; solde 71 - 51 = 20, soit 10 chacun
    assert out.loc[pd.Timestamp("2024-03-01"), "soutirage_kwh"] == pytest.approx(10.5)
    assert out.loc[pd.Timestamp("2024-03-04"), "soutirage_kwh"] == pytest.approx(40.5)
    assert out.loc[pd.Timestamp("2024-03-02"), "soutirage_kwh"] == pytest.approx(10.0)
    assert out.loc[pd.Timestamp("2024-03-03"), "soutirage_kwh"] == pytest.approx(10.0)
    assert out["soutirage_kwh"].sum() == pytest.approx(71.0)


def test_jours_douteux_jamais_negatifs():
    # Facture plus basse que les seuls jours releves : le solde est borne a 0
    # au lieu de rendre les jours douteux negatifs.
    df = calc.marque_conso_douteuse(_df_arrondi(), [
        {"debut": "2024-03-02", "fin": "2024-03-03"}])
    out = calc.recale_sur_facture(df, [
        {"debut": "2024-03-01", "fin": "2024-03-04", "total_kwh": 10.0}])
    assert (out["soutirage_kwh"] >= 0).all()


def test_jours_deja_combles_ne_sont_pas_ecrases_par_le_solde():
    # Un jour comble par conso_reseau_facturee (2022) garde sa valeur meme
    # si la tranche contient par ailleurs des jours douteux.
    df = _df_arrondi()
    df["conso_absente"] = [1.0, 0.0, 0.0, 0.0]   # jour 1 : deja servi
    df = calc.marque_conso_douteuse(df, [{"debut": "2024-03-04", "fin": "2024-03-04"}])
    out = calc.recale_sur_facture(df, [
        {"debut": "2024-03-01", "fin": "2024-03-04", "total_kwh": 71.0}])
    assert out.loc[pd.Timestamp("2024-03-01"), "soutirage_kwh"] == 10.0  # intact
    assert out["soutirage_kwh"].sum() == pytest.approx(71.0)


def test_recale_hors_periode_et_sans_tranches():
    df = _df_arrondi()
    assert calc.recale_sur_facture(df, None).equals(df)
    inchange = calc.recale_sur_facture(df, [
        {"debut": "2020-01-01", "fin": "2020-12-31", "total_kwh": 500.0}])
    assert inchange["soutirage_kwh"].sum() == pytest.approx(100.0)


# -----------------------------------------------------------------------------
# Recalage de l'injection sur les factures EDF OA
# -----------------------------------------------------------------------------

def _df_injection() -> pd.DataFrame:
    """4 jours : injection 10 + 20 + 30 + 40 = 100 kWh, production large."""
    idx = pd.DatetimeIndex(["2024-03-01", "2024-03-02", "2024-03-03", "2024-03-04"])
    df = pd.DataFrame({
        "production_kwh": [20.0, 40.0, 60.0, 80.0],
        "injection_kwh": [10.0, 20.0, 30.0, 40.0],
        "soutirage_kwh": [1.0, 1.0, 1.0, 1.0],
    }, index=idx)
    df["autoconsommation_kwh"] = (
        df["production_kwh"] - df["injection_kwh"]).clip(lower=0)
    df["consommation_kwh"] = df["autoconsommation_kwh"] + df["soutirage_kwh"]
    return df


def _tranche(total: float) -> list[dict]:
    return [{"debut": "2024-03-01", "fin": "2024-03-04", "total_kwh": total}]


def test_recale_injection_ecart_positif_au_prorata():
    # Facture 110 pour 100 releves : chaque jour prend 10 % de plus. L'ecart
    # d'un releve d'index suit la quantite injectee, il ne se partage pas a
    # parts egales entre un jour d'ete et un jour d'hiver.
    out = calc.recale_injection_sur_facture(_df_injection(), _tranche(110.0))
    assert list(out["injection_kwh"]) == pytest.approx([11.0, 22.0, 33.0, 44.0])
    assert out["injection_kwh"].sum() == pytest.approx(110.0)
    assert out["injection_recalee"].sum() == 4


def test_recale_injection_ecart_negatif_au_prorata():
    out = calc.recale_injection_sur_facture(_df_injection(), _tranche(50.0))
    assert list(out["injection_kwh"]) == pytest.approx([5.0, 10.0, 15.0, 20.0])


def test_recale_injection_recalcule_autoconso_et_conso():
    # L'autoconso est le complement de l'injection : elle doit suivre.
    out = calc.recale_injection_sur_facture(_df_injection(), _tranche(110.0))
    jour = pd.Timestamp("2024-03-01")
    assert out.loc[jour, "autoconsommation_kwh"] == pytest.approx(9.0)   # 20 - 11
    assert out.loc[jour, "consommation_kwh"] == pytest.approx(10.0)      # + 1 soutire


def test_recale_injection_jamais_au_dessus_de_la_production():
    # On ne vend pas ce qu'on n'a pas produit : le 1er jour ne peut pas
    # depasser 10,5 kWh, et ce qu'il n'absorbe pas revient aux autres jours.
    df = _df_injection()
    df.loc[pd.Timestamp("2024-03-01"), "production_kwh"] = 10.5
    out = calc.recale_injection_sur_facture(df, _tranche(110.0))
    assert out.loc[pd.Timestamp("2024-03-01"), "injection_kwh"] == pytest.approx(10.5)
    assert (out["injection_kwh"] <= out["production_kwh"] + 1e-9).all()
    assert out["injection_kwh"].sum() == pytest.approx(110.0)


def test_recale_injection_jour_sans_injection_reste_a_zero():
    # Une journee entierement autoconsommee n'a rien injecte : le recalage
    # ne doit pas lui inventer des kWh vendus.
    df = _df_injection()
    df.loc[pd.Timestamp("2024-03-01"), "injection_kwh"] = 0.0
    out = calc.recale_injection_sur_facture(df, _tranche(99.0))
    assert out.loc[pd.Timestamp("2024-03-01"), "injection_kwh"] == 0.0
    assert out["injection_kwh"].sum() == pytest.approx(99.0)


def test_recale_injection_total_hors_datteinte():
    # Facture superieure a toute la production de la periode (cas absurde) :
    # l'app s'arrete au maximum physique au lieu de boucler ou d'inventer.
    out = calc.recale_injection_sur_facture(_df_injection(), _tranche(9999.0))
    assert list(out["injection_kwh"]) == pytest.approx([20.0, 40.0, 60.0, 80.0])
    assert (out["autoconsommation_kwh"] == 0).all()


def test_recale_injection_hors_periode_et_sans_tranches():
    df = _df_injection()
    assert calc.recale_injection_sur_facture(df, None).equals(df)
    inchange = calc.recale_injection_sur_facture(df, [
        {"debut": "2020-01-01", "fin": "2020-12-31", "total_kwh": 500.0}])
    assert inchange["injection_kwh"].sum() == pytest.approx(100.0)


# -----------------------------------------------------------------------------
# Revenu OA
# -----------------------------------------------------------------------------

def test_revenu_oa_nul_avant_contrat(oa_surplus):
    from datetime import date as date_type
    idx = pd.DatetimeIndex(["2022-06-15", "2022-06-28"])
    df = pd.DataFrame({"production_kwh": [20.0, 20.0],
                       "injection_kwh": [10.0, 10.0]}, index=idx)
    out = calc.revenu_oa(df, oa_surplus, debut_contrat=date_type(2022, 6, 28))
    assert out["revenu_vente_eur"].iloc[0] == 0.0            # avant contrat
    assert out["revenu_vente_eur"].iloc[1] == pytest.approx(1.3)  # apres

def test_revenu_oa_surplus(oa_surplus):
    idx = pd.DatetimeIndex(["2025-06-01"])
    df = pd.DataFrame({"production_kwh": [20.0], "injection_kwh": [10.0]}, index=idx)
    out = calc.revenu_oa(df, oa_surplus)
    assert out["revenu_vente_eur"].iloc[0] == pytest.approx(10.0 * 0.13)


def test_revenu_oa_totale():
    oa = calc.OAConfig(
        type="totale", prix_kwh=0.18,
        prime_par_kwc=0.0, prime_duree=0, duree_contrat=20,
    )
    idx = pd.DatetimeIndex(["2025-06-01"])
    df = pd.DataFrame({"production_kwh": [20.0], "injection_kwh": [10.0]}, index=idx)
    out = calc.revenu_oa(df, oa)
    assert out["revenu_vente_eur"].iloc[0] == pytest.approx(20.0 * 0.18)


def test_revenu_oa_type_inconnu():
    oa = calc.OAConfig(
        type="autre", prix_kwh=0.13,
        prime_par_kwc=0.0, prime_duree=0, duree_contrat=20,
    )
    idx = pd.DatetimeIndex(["2025-06-01"])
    df = pd.DataFrame({"production_kwh": [20.0], "injection_kwh": [10.0]}, index=idx)
    out = calc.revenu_oa(df, oa)
    assert out["revenu_vente_eur"].iloc[0] == 0.0


# -----------------------------------------------------------------------------
# Cout reseau journalier (Bleu avant 2026, Octopus apres + abonnement)
# -----------------------------------------------------------------------------

def test_cout_reseau_avant_cutoff(bleu, octopus):
    # Juin 2025 (30 jours) : Bleu 0.27 EUR/kWh + abo 13.5/30 par jour
    idx = pd.DatetimeIndex(["2025-06-15"])
    df = pd.DataFrame({"soutirage_kwh": [10.0]}, index=idx)
    out = calc.cout_reseau_journalier(df, None, bleu, octopus)
    abo_jour = 13.5 / 30
    assert out["cout_reseau_eur"].iloc[0] == pytest.approx(10 * 0.27 + abo_jour)


def test_cout_reseau_apres_cutoff_sans_hphc(bleu, octopus):
    # Fev 2026 (28 jours) : prix moyen pondere par ratio HC + abo Octopus
    idx = pd.DatetimeIndex(["2026-02-15"])
    df = pd.DataFrame({"soutirage_kwh": [10.0]}, index=idx)
    out = calc.cout_reseau_journalier(df, None, bleu, octopus)
    ratio = 7 / 24
    prix_moyen = 0.18 * ratio + 0.30 * (1 - ratio)
    abo_jour = 15.0 / 28
    assert out["cout_reseau_eur"].iloc[0] == pytest.approx(10 * prix_moyen + abo_jour)


def test_cout_reseau_apres_cutoff_avec_hphc(bleu, octopus):
    # HP+HC couvrent >= 90% du soutirage : prix reels appliques
    idx = pd.DatetimeIndex(["2026-02-15"])
    df = pd.DataFrame({
        "soutirage_kwh": [10.0],
        "soutirage_hp_kwh": [7.0],
        "soutirage_hc_kwh": [3.0],
    }, index=idx)
    out = calc.cout_reseau_journalier(df, None, bleu, octopus)
    abo_jour = 15.0 / 28
    expected = 7 * 0.30 + 3 * 0.18 + abo_jour
    assert out["cout_reseau_eur"].iloc[0] == pytest.approx(expected)


def test_cout_reseau_hphc_insuffisant_fallback(bleu, octopus):
    # HP+HC ne couvrent que 50% du soutirage -> fallback ratio moyen
    idx = pd.DatetimeIndex(["2026-02-15"])
    df = pd.DataFrame({
        "soutirage_kwh": [10.0],
        "soutirage_hp_kwh": [3.0],
        "soutirage_hc_kwh": [2.0],
    }, index=idx)
    out = calc.cout_reseau_journalier(df, None, bleu, octopus)
    ratio = 7 / 24
    prix_moyen = 0.18 * ratio + 0.30 * (1 - ratio)
    abo_jour = 15.0 / 28
    expected = 10 * prix_moyen + abo_jour
    assert out["cout_reseau_eur"].iloc[0] == pytest.approx(expected)


def test_cout_reseau_empty(bleu, octopus):
    out = calc.cout_reseau_journalier(pd.DataFrame(), None, bleu, octopus)
    assert "cout_reseau_eur" in out.columns
    assert out.empty


# -----------------------------------------------------------------------------
# Economies autoconsommation
# -----------------------------------------------------------------------------

def test_economies_autoconso_avant_cutoff(bleu, octopus):
    idx = pd.DatetimeIndex(["2025-06-01"])
    df = pd.DataFrame({"autoconsommation_kwh": [15.0]}, index=idx)
    out = calc.economies_autoconsommation(df, bleu, octopus)
    assert out["economie_eur"].iloc[0] == pytest.approx(15.0 * 0.27)


def test_economies_autoconso_apres_cutoff(bleu, octopus):
    # Depuis Octopus : pondere par part_hc_autoconso (defaut 20 %), pas par
    # la duree des plages sur 24 h (l'autoconso est diurne).
    idx = pd.DatetimeIndex(["2026-06-01"])
    df = pd.DataFrame({"autoconsommation_kwh": [15.0]}, index=idx)
    out = calc.economies_autoconsommation(df, bleu, octopus)
    prix_moyen = 0.18 * 0.20 + 0.30 * 0.80
    assert out["economie_eur"].iloc[0] == pytest.approx(15.0 * prix_moyen)


def test_economies_autoconso_part_hc_personnalisee(bleu):
    # part_hc_autoconso configurable : 50 % HC -> prix moyen (HP+HC)/2
    octopus = calc.OctopusConfig.periode_unique(
        abonnement_mensuel=15.0,
        prix_hp=0.30,
        prix_hc=0.18,
        plages_hc=calc.parse_plages_hc(["00:30-07:30"]),
        part_hc_autoconso=0.5,
    )
    idx = pd.DatetimeIndex(["2026-06-01"])
    df = pd.DataFrame({"autoconsommation_kwh": [10.0]}, index=idx)
    out = calc.economies_autoconsommation(df, bleu, octopus)
    assert out["economie_eur"].iloc[0] == pytest.approx(10.0 * 0.24)


def test_economies_autoconso_empty(bleu, octopus):
    out = calc.economies_autoconsommation(pd.DataFrame(), bleu, octopus)
    assert "economie_eur" in out.columns


# -----------------------------------------------------------------------------
# Comparaison Octopus vs EDF Tarif Bleu
# -----------------------------------------------------------------------------

@pytest.fixture
def edf_ref() -> list[dict]:
    """Grille EDF de reference a une seule periode."""
    return [{"debut": "2026-01-01", "fin": None, "abonnement": 14.0,
             "prix_base": 0.25, "prix_hp": 0.30, "prix_hc": 0.18}]


def test_comparaison_vide_avant_cutoff(edf_ref):
    # Aucune ligne >= 2026-01-01 -> retourne un DataFrame vide
    idx = pd.DatetimeIndex(["2025-06-01"])
    df = pd.DataFrame({
        "soutirage_kwh": [10.0], "cout_reseau_eur": [3.0],
        "abonnement_eur": [0.5],
    }, index=idx)
    out = calc.comparaison_octopus_edf(df, edf_ref)
    assert out.empty


def test_comparaison_apres_cutoff(edf_ref):
    idx = pd.DatetimeIndex(["2026-02-15"])  # 28 jours
    df = pd.DataFrame({
        "soutirage_kwh": [10.0],
        "cout_reseau_eur": [3.5],
        "abonnement_eur": [0.5],
    }, index=idx)
    out = calc.comparaison_octopus_edf(df, edf_ref)
    abo_jour = 14.0 / 28
    assert out["cout_octopus_eur"].iloc[0] == pytest.approx(3.5)
    assert out["cout_edf_base_eur"].iloc[0] == pytest.approx(10 * 0.25 + abo_jour)
    assert out["gain_vs_base_eur"].iloc[0] == pytest.approx(
        out["cout_edf_base_eur"].iloc[0] - 3.5,
    )


def test_comparaison_suit_la_grille_edf_du_jour():
    """EDF revise aussi ses tarifs : chaque jour est compare a SA grille."""
    idx = pd.DatetimeIndex(["2026-07-15", "2026-08-15"])  # 31 jours chacun
    df = pd.DataFrame({
        "soutirage_kwh": [10.0, 10.0],
        "cout_reseau_eur": [3.5, 3.5],
        "abonnement_eur": [0.5, 0.5],
    }, index=idx)
    ref = [
        {"debut": "2026-01-01", "fin": "2026-07-31", "abonnement": 19.56,
         "prix_base": 0.1927, "prix_hp": 0.2065, "prix_hc": 0.1579},
        {"debut": "2026-08-01", "fin": None, "abonnement": 19.88,
         "prix_base": 0.1985, "prix_hp": 0.2142, "prix_hc": 0.1589},
    ]
    out = calc.comparaison_octopus_edf(df, ref)
    assert out["cout_edf_base_eur"].iloc[0] == pytest.approx(
        10 * 0.1927 + 19.56 / 31)
    assert out["cout_edf_base_eur"].iloc[1] == pytest.approx(
        10 * 0.1985 + 19.88 / 31)


def test_comparaison_grille_edf_de_janvier_2026():
    """Janvier 2026 relevait encore de la grille EDF du 01/08/2025.

    La revision EDF tombe le 1er fevrier : comparer janvier a la grille de
    fevrier sous-estimait le scenario EDF (fevrier etait une baisse).
    """
    idx = pd.DatetimeIndex(["2026-01-15", "2026-02-15"])
    df = pd.DataFrame({
        "soutirage_kwh": [100.0, 100.0],
        "cout_reseau_eur": [15.0, 15.0],
        "abonnement_eur": [0.6, 0.6],
    }, index=idx)
    ref = [
        {"debut": "2026-01-01", "fin": "2026-01-31", "abonnement": 19.56,
         "prix_base": 0.1952, "prix_hp": 0.2081, "prix_hc": 0.1635},
        {"debut": "2026-02-01", "fin": "2026-07-31", "abonnement": 19.56,
         "prix_base": 0.1927, "prix_hp": 0.2065, "prix_hc": 0.1579},
    ]
    out = calc.comparaison_octopus_edf(df, ref)
    assert out["cout_edf_base_eur"].iloc[0] == pytest.approx(
        100 * 0.1952 + 19.56 / 31)          # janvier : 31 jours
    assert out["cout_edf_base_eur"].iloc[1] == pytest.approx(
        100 * 0.1927 + 19.56 / 28)          # fevrier : 28 jours


def test_periodes_edf_accepte_ancien_config():
    """Un config.yaml d'avant le decoupage en periodes reste utilisable."""
    ancien = {"abonnement_mensuel_eur": 19.56, "prix_kwh_eur": 0.1927,
              "prix_hp_eur_kwh": 0.2065, "prix_hc_eur_kwh": 0.1579}
    periodes = calc.periodes_edf(ancien)
    assert len(periodes) == 1
    assert periodes[0]["prix_base"] == 0.1927
    assert periodes[0]["prix_hc"] == 0.1579
    assert periodes[0]["fin"] is None


def test_fraicheur_signale_les_dates_illisibles():
    # Une date que pandas ne sait pas lire retire la journee de tous les
    # calculs : le bandeau doit le dire, sinon l'ecart reste inexplicable.
    from views._helpers import fraicheur_donnees
    texte, en_retard = fraicheur_donnees(
        {"Prod_Jour": date(2026, 8, 17)}, AUJOURDHUI,
        illisibles=["32/13/2026", "le 3 mai"])
    assert "2" in texte
    assert "32/13/2026" in texte
    assert en_retard is True


def test_fraicheur_sans_date_illisible_ne_dit_rien():
    from views._helpers import fraicheur_donnees
    texte, _ = fraicheur_donnees({"Prod_Jour": date(2026, 8, 17)}, AUJOURDHUI,
                                 illisibles=[])
    assert "illisible" not in texte.lower()
