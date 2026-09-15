"""Ce qu'un nouvel utilisateur rencontre : premier lancement, config a lui.

Ces tests decrivent le parcours de quelqu'un qui recupere l'application sans
les donnees ni les factures de son auteur. Chacun correspond a un blocage
constate le 09/09/2026 en rejouant ce parcours a blanc.
"""
from __future__ import annotations

import pandas as pd
import pytest
import yaml

import app_desktop
import calculations as calc
import data_loaders as dl

# -----------------------------------------------------------------------------
# Premier lancement : aucun fichier de releves
# -----------------------------------------------------------------------------


def test_creer_csv_vide_pose_le_bon_entete(tmp_path):
    """L'en-tete doit etre celui qu'attend la lecture, accent compris."""
    chemin = tmp_path / "Releves-pv.csv"
    dl.creer_csv_vide(str(chemin))
    assert chemin.read_text(encoding="utf-8").strip() == ";".join(dl.RELEVES_HEADER)
    # Et il se relit sans erreur : l'application peut demarrer dessus.
    assert dl.read_releves_raw(str(chemin)) == []


def test_creer_csv_vide_n_ecrase_jamais_des_donnees(tmp_path):
    chemin = tmp_path / "Releves-pv.csv"
    chemin.write_text("Date;Prod_Jour\n01/05/2026;20,5\n", encoding="utf-8")
    dl.creer_csv_vide(str(chemin))
    assert "01/05/2026" in chemin.read_text(encoding="utf-8")


# -----------------------------------------------------------------------------
# Plafond de saisie : il suit la taille de l'installation
# -----------------------------------------------------------------------------


def test_plafond_par_defaut_inchange_sur_6_kwc():
    assert dl.plafond_colonne("Prod_Jour") == 60.0
    assert dl.plafond_colonne("Prod_Jour", 6.0) == 60.0


def test_plafond_suit_la_puissance_installee():
    """Une journee d'ete de 9 kWc etait refusee par le plafond fige a 60."""
    assert dl.plafond_colonne("Prod_Jour", 9.0) == 90.0
    assert dl.plafond_colonne("Inj_Jour", 9.0) == 90.0
    dl.normalise_nombre_saisie(
        "72,4", "Production", dl.plafond_colonne("Prod_Jour", 9.0))
    with pytest.raises(ValueError):
        dl.normalise_nombre_saisie(
            "72,4", "Production", dl.plafond_colonne("Prod_Jour", 6.0))


def test_plafond_de_conso_ne_depend_pas_de_l_installation():
    """La conso vient du chauffage et de la voiture, pas des panneaux."""
    assert dl.plafond_colonne("Conso_réseau_Jour", 9.0) == 150.0


# -----------------------------------------------------------------------------
# Configuration : deux fichiers, et des messages en francais
# -----------------------------------------------------------------------------


def test_config_locale_remplace_section_par_section():
    base = {"sources": {"releves_csv": "Releves-pv.csv"},
            "installation": {"puissance_kwc": 6.0}}
    local = {"sources": {"injection_facturee": [{"total_kwh": 10}]}}
    fusion = app_desktop._fusionne(base, local)
    # Ce qui n'est pas redit reste en place...
    assert fusion["sources"]["releves_csv"] == "Releves-pv.csv"
    assert fusion["installation"]["puissance_kwc"] == 6.0
    # ... et ce qui est ajoute vient completer.
    assert fusion["sources"]["injection_facturee"] == [{"total_kwh": 10}]


def test_config_locale_ne_modifie_pas_l_original():
    base = {"sources": {"releves_csv": "a.csv"}}
    app_desktop._fusionne(base, {"sources": {"releves_csv": "b.csv"}})
    assert base["sources"]["releves_csv"] == "a.csv"


def test_yaml_mal_ecrit_donne_un_message_en_francais(tmp_path):
    chemin = tmp_path / "config.yaml"
    chemin.write_text("installation:\n  puissance_kwc 6.0: 3\n mauvais\n",
                      encoding="utf-8")
    with pytest.raises(RuntimeError) as erreur:
        app_desktop._lire_yaml(chemin)
    message = str(erreur.value)
    assert "mal ecrit" in message
    assert "ligne" in message
    # Le message technique de PyYAML ne doit pas ressortir tel quel.
    assert "mapping values" not in message


def _config_minimale() -> dict:
    """Ce qu'un utilisateur neuf doit ecrire, et rien de plus."""
    return {
        "installation": {"puissance_kwc": 9.0, "cout_total_eur": 18000.0,
                         "date_mise_en_service": "2026-05-15",
                         "date_debut_contrat_oa": "2026-05-15"},
        "oa": {"type": "surplus", "prix_kwh_eur": 0.04,
               "prime_autoconsommation": {"montant_par_kwc": 80.0,
                                          "duree_annees": 1},
               "duree_contrat_annees": 20},
        "tarifs_reseau": {"contrat_hphc": {
            "periodes": [{"debut": "2026-01-01", "fin": None,
                          "abonnement": 20.16, "prix_hp": 0.2213,
                          "prix_hc": 0.1290}],
            "plages_hc": ["22:00-06:00"]}},
        "sources": {"releves_csv": "Releves-pv.csv"},
    }


def test_config_minimale_est_acceptee():
    """Sans tarif a prix unique ni recalage : l'application doit demarrer."""
    app_desktop.verifier_config(_config_minimale())


def test_config_incomplete_dit_ce_qui_manque_en_francais():
    cfg = _config_minimale()
    del cfg["installation"]["cout_total_eur"]
    del cfg["tarifs_reseau"]["contrat_hphc"]["plages_hc"]
    with pytest.raises(RuntimeError) as erreur:
        app_desktop.verifier_config(cfg)
    message = str(erreur.value)
    assert "le coût total de l'installation" in message
    assert "les plages d'heures creuses" in message
    assert "config.yaml" in message


def test_tarif_a_prix_unique_facultatif():
    """Section bleu_base absente : plus de KeyError, un prix nul."""
    vide = calc.BleuBaseConfig(abonnement_tranches=[], tranches=[])
    octopus = calc.OctopusConfig(
        periodes=[{"debut": "2026-01-01", "fin": None, "abonnement": 20.16,
                   "prix_hp": 0.2213, "prix_hc": 0.1290}],
        plages_hc=calc.parse_plages_hc(["22:00-06:00"]))
    idx = pd.DatetimeIndex(["2025-06-01", "2026-06-01"])
    assert list(calc._prix_bleu_series(idx, vide.tranches)) == [0.0, 0.0]
    # Apres bascule, l'abonnement reste celui du fournisseur en cours.
    assert calc.abonnement_mensuel_eur(
        pd.Timestamp("2026-06-01"), vide, octopus) == 20.16
    assert calc.abonnement_mensuel_eur(
        pd.Timestamp("2025-06-01"), vide, octopus) == 0.0


def test_comparaison_tarifs_sur_un_fichier_vide():
    """Premier lancement : la vue de comparaison ne doit pas tomber en panne.

    Sur un fichier sans releve, l'index n'est pas un index de dates ; le
    comparer a la date de bascule levait une TypeError et la vue restait
    inaccessible.
    """
    vide = calc.comparaison_octopus_edf(pd.DataFrame(), [])
    assert vide.empty


# -----------------------------------------------------------------------------
# Date de bascule vers les heures creuses
# -----------------------------------------------------------------------------


@pytest.fixture
def bascule_restauree():
    """Rend sa date d'origine au module : c'est un reglage global."""
    origine = calc.CUTOFF_OCTOPUS
    yield
    calc.CUTOFF_OCTOPUS = origine


def test_bascule_hphc_se_regle_par_la_config(bascule_restauree):
    calc.definir_bascule_hphc("2024-03-01")
    assert calc.CUTOFF_OCTOPUS == pd.Timestamp("2024-03-01")


def test_bascule_hphc_absente_garde_la_valeur_en_cours(bascule_restauree):
    avant = calc.CUTOFF_OCTOPUS
    calc.definir_bascule_hphc(None)
    assert calc.CUTOFF_OCTOPUS == avant


def test_bascule_hphc_illisible_est_signalee(bascule_restauree):
    with pytest.raises(RuntimeError) as erreur:
        calc.definir_bascule_hphc("le 1er janvier")
    assert "bascule_hphc" in str(erreur.value)


# -----------------------------------------------------------------------------
# Le fichier livre avec l'application ne doit porter aucune facture
# -----------------------------------------------------------------------------


def test_config_livree_sans_donnees_personnelles():
    """Les recalages reecrivent les releves : livres avec l'application, ils
    fausseraient ceux d'un autre foyer en silence. Ils vivent desormais dans
    config-local.yaml, qui n'est pas versionne."""
    with open(app_desktop.CONFIG_PATH, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    sources = cfg.get("sources") or {}
    for cle in ("injection_facturee", "conso_reseau_facturee",
                "conso_reseau_recalee", "conso_reseau_douteuse",
                "recharges_ve_json"):
        assert cle not in sources, (
            f"{cle} est une donnee personnelle : elle va dans config-local.yaml")


# -----------------------------------------------------------------------------
# Un autre onduleur, un autre fournisseur
# -----------------------------------------------------------------------------
# Les boutons d'import nommaient les marques de l'auteur ("Importer Enphase",
# "Importer Enedis / Octopus"). Or les deux lecteurs acceptent tout export
# "date + valeur" : le blocage etait dans le vocabulaire, pas dans le code.
# Ces tests fixent cette tolerance, pour qu'un remaniement ne la reprenne pas.


def test_production_d_un_autre_onduleur_au_pas_infrajournalier():
    """Export type SolarEdge : dates ISO, virgule, valeurs en Wh."""
    texte = ("Time,Production (Wh)\n"
             "2026-08-01 06:00,120\n"
             "2026-08-01 12:00,4200\n"
             "2026-08-01 18:00,900\n"
             "2026-08-02 12:00,5100\n")
    assert dl.parse_enphase_texte(texte) == {"01/08/2026": "5,2",
                                             "02/08/2026": "5,1"}


def test_production_d_un_autre_onduleur_deja_quotidienne():
    """Export type Huawei : dates francaises, kWh, point-virgule."""
    texte = ("Date;Rendement energetique (kWh)\n"
             "01/08/2026;22,4\n"
             "02/08/2026;25,1\n")
    assert dl.parse_enphase_texte(texte) == {"01/08/2026": "22,4",
                                             "02/08/2026": "25,1"}


def test_conso_d_un_autre_fournisseur():
    texte = ("Suivi de consommation quotidienne\n"
             "Date;Consommation (en kWh)\n"
             "01/08/2026;8,4\n")
    colonne, valeurs = dl.parse_enedis_csv_texte(texte)
    assert colonne == "Conso_réseau_Jour"
    assert valeurs == {"01/08/2026": "8,4"}


def test_injection_d_un_autre_fournisseur():
    texte = "Date;Production injectee (en kWh)\n01/08/2026;14,2\n"
    colonne, valeurs = dl.parse_enedis_csv_texte(texte)
    assert colonne == "Inj_Jour"
    assert valeurs == {"01/08/2026": "14,2"}


def test_message_de_refus_ne_parle_plus_d_une_seule_marque():
    """Un en-tete muet doit orienter, pas renvoyer au seul cas de l'auteur."""
    with pytest.raises(ValueError) as erreur:
        dl.parse_enedis_csv_texte("Date;Valeur\n01/08/2026;8,4\n")
    message = str(erreur.value)
    assert "date + valeur" in message
    assert "Est-ce bien un export quotidien Enedis" not in message


def _donnees_avec(cfg_tarifs: dict):
    """Un AppData minimal, juste de quoi lire les noms d'offres."""
    from app_data import AppData
    return AppData(df=pd.DataFrame(), cfg={"tarifs_reseau": cfg_tarifs},
                   oa=None, bleu=None, octopus=None,
                   start_oa=pd.Timestamp("2026-01-01").date(),
                   releves_path=None, edf_ref=[])


def test_noms_d_offres_lus_dans_la_config():
    data = _donnees_avec({
        "contrat_hphc": {"nom": "TotalEnergies", "offre": "Heures Eco"},
        "comparaison_edf": {"nom": "EDF", "offre": "EDF Tarif Bleu"},
    })
    assert data.fournisseur == ("TotalEnergies", "Heures Eco")
    assert data.fournisseur_reference == ("EDF", "EDF Tarif Bleu")


def test_noms_d_offres_absents_donnent_des_libelles_neutres():
    """Une config qui ne les declare pas ne doit pas afficher 'Octopus'."""
    data = _donnees_avec({"contrat_hphc": {}, "comparaison_edf": {}})
    assert data.fournisseur == ("Mon contrat", "Mon contrat")
    assert data.fournisseur_reference == ("Tarif de référence",
                                          "Tarif de référence")


def test_offre_seule_suffit():
    """Sans 'offre', le nom court sert aussi de libelle long."""
    data = _donnees_avec({"contrat_hphc": {"nom": "Engie"},
                          "comparaison_edf": {}})
    assert data.fournisseur == ("Engie", "Engie")


# -----------------------------------------------------------------------------
# La section du contrat a change de nom : octopus_hphc -> contrat_hphc
# -----------------------------------------------------------------------------
# L'ancien nom faisait croire a un autre utilisateur que la section ne
# concernait qu'Octopus. Les config.yaml deja ecrits doivent rester valables.


def test_ancien_nom_de_section_toujours_lu():
    cfg = _config_minimale()
    cfg["tarifs_reseau"]["octopus_hphc"] = cfg["tarifs_reseau"].pop("contrat_hphc")
    app_desktop.verifier_config(cfg)
    assert "octopus_hphc" not in cfg["tarifs_reseau"]
    assert cfg["tarifs_reseau"]["contrat_hphc"]["plages_hc"] == ["22:00-06:00"]


def test_nouveau_nom_l_emporte_sur_l_ancien():
    cfg = {"tarifs_reseau": {"octopus_hphc": {"nom": "Ancien"},
                             "contrat_hphc": {"nom": "Nouveau"}}}
    app_desktop.normaliser_config(cfg)
    assert cfg["tarifs_reseau"] == {"contrat_hphc": {"nom": "Nouveau"}}


def test_config_sans_tarifs_ne_plante_pas():
    assert app_desktop.normaliser_config({}) == {}


def test_modele_livre_ne_parle_pas_d_octopus():
    """Le modele est copie chez chaque nouvel utilisateur : le bouton de
    comparaison ne doit pas lui annoncer le fournisseur de l'auteur."""
    with open(app_desktop.CONFIG_PATH, encoding="utf-8") as fh:
        cfg = app_desktop.normaliser_config(yaml.safe_load(fh))
    app_desktop.verifier_config(cfg)
    data = _donnees_avec(cfg["tarifs_reseau"])
    assert "octopus" not in " ".join(data.fournisseur).lower()
