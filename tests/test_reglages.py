"""La fenetre « Mes reglages » et l'ecriture prudente de config.yaml.

Deux fichiers servent de terrain : le modele livre (ce que remplit un nouvel
utilisateur) et ANCIEN, un config.yaml de la forme de celui de l'auteur --
ancien nom de section, plusieurs periodes de prix sur deux lignes,
commentaires partout -- aux valeurs inventees.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

import reglages as rg

MODELE = (Path(__file__).resolve().parents[1] / "config.yaml").read_text(
    encoding="utf-8")

ANCIEN = """\
# Configuration de test
installation:
  puissance_kwc: 6.0
  cout_total_eur: 15000.0
  date_mise_en_service: "2022-05-02"
  date_debut_contrat_oa: "2022-07-01"  # debut annee OA 1
oa:
  type: "surplus"
  prix_kwh_eur: 0.10
  prime_autoconsommation:
    montant_par_kwc: 300.0       # EUR / kWc
    duree_annees: 5
  duree_contrat_annees: 20
tarifs_reseau:
  bascule_hphc: "2026-01-01"
  octopus_hphc:
    # commentaire du contrat
    nom: "Fournisseur A"
    offre: "Offre A"
    periodes:
      - { debut: "2026-01-01", fin: "2026-01-31",
          abonnement: 20.00, prix_hp: 0.2100, prix_hc: 0.1200 }
      - { debut: "2026-02-01", fin: null,
          abonnement: 21.00, prix_hp: 0.2200, prix_hc: 0.1300 }
    plages_hc:
      # plages au format HH:MM-HH:MM
      - "23:00-05:00"
      - "14:00-16:00"
    part_hc_autoconso: 0.20
  comparaison_edf:
    nom: "EDF"
    periodes:
      - { debut: "2026-01-01", fin: null, abonnement: 19.0,
          prix_base: 0.19, prix_hp: 0.20, prix_hc: 0.15 }
sources:
  releves_csv: "Releves-pv.csv"
"""


def _appliquer(texte: str, **changements) -> tuple[str, dict]:
    cfg = yaml.safe_load(texte)
    v = {**rg.lire_reglages(cfg), **changements}
    nouveau = rg.appliquer_reglages(texte, cfg, v)
    relu = yaml.safe_load(nouveau)
    # La preuve que fait enregistrer_reglages : rien d'autre n'a bouge.
    assert relu == rg.reglages_attendus(cfg, v)
    return nouveau, relu


def _commentaires(texte: str) -> list[str]:
    """Les commentaires seuls : lignes entieres, et fins de ligne « # ... »
    (sans la valeur qui les precede, qui peut legitimement changer)."""
    trouves = []
    for ligne in texte.splitlines():
        s = ligne.strip()
        if s.startswith("#"):
            trouves.append(s)
        elif "  #" in ligne:
            trouves.append(ligne[ligne.index("  #"):].strip())
    return trouves


# -----------------------------------------------------------------------------
# Rien de change : rien d'ecrit
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("texte", [MODELE, ANCIEN])
def test_sans_changement_le_texte_est_identique(texte):
    cfg = yaml.safe_load(texte)
    assert rg.appliquer_reglages(texte, cfg, rg.lire_reglages(cfg)) == texte


# -----------------------------------------------------------------------------
# Un nouvel utilisateur remplit le modele
# -----------------------------------------------------------------------------


def test_le_modele_rempli_par_une_nouvelle_utilisatrice():
    nouveau, relu = _appliquer(
        MODELE, puissance_kwc=4.5, cout_total_eur=11500.0,
        date_mise_en_service=date(2025, 4, 15),
        date_debut_contrat_oa=date(2025, 5, 20), prix_oa=0.04,
        prime_par_kwc=80.0, prime_duree=1, nom="TotalEnergies",
        offre="Heures Eco", abonnement=21.5, prix_hp=0.225, prix_hc=0.165,
        plages_hc=["22:00-06:00"])
    assert relu["installation"]["puissance_kwc"] == 4.5
    assert relu["installation"]["date_debut_contrat_oa"] == "2025-05-20"
    assert relu["oa"]["prime_autoconsommation"] == {"montant_par_kwc": 80.0,
                                                    "duree_annees": 1}
    contrat = relu["tarifs_reseau"]["contrat_hphc"]
    assert contrat["nom"] == "TotalEnergies"
    # Meme date que la periode du modele : elle est corrigee, pas doublee.
    assert len(contrat["periodes"]) == 1
    assert contrat["periodes"][0]["prix_hp"] == 0.225
    # Tous les commentaires du modele sont toujours la.
    assert _commentaires(nouveau) == _commentaires(MODELE)


# -----------------------------------------------------------------------------
# Un fichier comme celui de l'auteur
# -----------------------------------------------------------------------------


def test_nouveaux_prix_ajoutent_une_periode():
    nouveau, relu = _appliquer(ANCIEN, abonnement=22.0, prix_hp=0.23,
                               prix_hc=0.14, prix_depuis=date(2026, 8, 1))
    periodes = relu["tarifs_reseau"]["octopus_hphc"]["periodes"]
    assert [p["debut"] for p in periodes] == ["2026-01-01", "2026-02-01",
                                              "2026-08-01"]
    # L'ancienne periode se ferme la veille, ses prix restent.
    assert periodes[1]["fin"] == "2026-07-31"
    assert periodes[1]["prix_hp"] == 0.22
    assert periodes[2] == {"debut": "2026-08-01", "fin": None,
                           "abonnement": 22.0, "prix_hp": 0.23, "prix_hc": 0.14}
    # La periode fermee garde son ecriture : seule sa fin a change.
    assert ('      - { debut: "2026-02-01", fin: "2026-07-31",\n'
            "          abonnement: 21.00, prix_hp: 0.2200, prix_hc: 0.1300 }"
            ) in nouveau
    # L'ancien nom de section est garde tel quel.
    assert "octopus_hphc:" in nouveau
    assert _commentaires(nouveau) == _commentaires(ANCIEN)


def test_meme_date_corrige_la_periode_en_cours():
    _, relu = _appliquer(ANCIEN, prix_hp=0.2250,
                         prix_depuis=date(2026, 2, 1))
    periodes = relu["tarifs_reseau"]["octopus_hphc"]["periodes"]
    assert len(periodes) == 2
    assert periodes[1]["prix_hp"] == 0.225
    assert periodes[1]["fin"] is None


def test_des_prix_avant_la_periode_en_cours_sont_refuses():
    with pytest.raises(rg.ReglagesRefuses) as erreur:
        _appliquer(ANCIEN, prix_hp=0.30, prix_depuis=date(2026, 1, 15))
    assert "01/02/2026" in str(erreur.value)


def test_la_grille_edf_n_est_jamais_touchee():
    _, relu = _appliquer(ANCIEN, prix_hp=0.30, prix_depuis=date(2026, 9, 1))
    assert relu["tarifs_reseau"]["comparaison_edf"] == \
        yaml.safe_load(ANCIEN)["tarifs_reseau"]["comparaison_edf"]


def test_les_plages_changent_et_leur_commentaire_reste():
    nouveau, relu = _appliquer(ANCIEN, plages_hc=["22:00-06:00"])
    assert relu["tarifs_reseau"]["octopus_hphc"]["plages_hc"] == ["22:00-06:00"]
    assert "# plages au format HH:MM-HH:MM" in nouveau


def test_le_commentaire_en_bout_de_ligne_reste():
    nouveau, _ = _appliquer(ANCIEN, date_debut_contrat_oa=date(2022, 7, 15))
    assert 'date_debut_contrat_oa: "2022-07-15"  # debut annee OA 1' in nouveau


def test_un_nom_absent_est_ajoute():
    sans_nom = ANCIEN.replace('    nom: "Fournisseur A"\n', "")
    _, relu = _appliquer(sans_nom, nom="Engie")
    assert relu["tarifs_reseau"]["octopus_hphc"]["nom"] == "Engie"


def test_les_fins_de_ligne_windows_sont_gardees():
    crlf = ANCIEN.replace("\n", "\r\n")
    nouveau, _ = _appliquer(crlf, puissance_kwc=9.0)
    assert "\r\n" in nouveau
    assert "\n" not in nouveau.replace("\r\n", "")


# -----------------------------------------------------------------------------
# Enregistrement : sauvegarde, et rien d'ecrit au moindre doute
# -----------------------------------------------------------------------------


def _fichier(tmp_path, texte=ANCIEN) -> Path:
    chemin = tmp_path / "config.yaml"
    chemin.write_text(texte, encoding="utf-8")
    return chemin


def test_enregistrer_garde_une_copie(tmp_path):
    chemin = _fichier(tmp_path)
    v = {**rg.lire_reglages(yaml.safe_load(ANCIEN)), "puissance_kwc": 9.0}
    assert rg.enregistrer_reglages(chemin, v, tmp_path / "backups")
    assert yaml.safe_load(chemin.read_text(encoding="utf-8"))[
        "installation"]["puissance_kwc"] == 9.0
    copies = list((tmp_path / "backups").glob("config_avant-reglages_*.yaml"))
    assert len(copies) == 1
    assert copies[0].read_text(encoding="utf-8") == ANCIEN


def test_sans_changement_rien_n_est_ecrit(tmp_path):
    chemin = _fichier(tmp_path)
    v = rg.lire_reglages(yaml.safe_load(ANCIEN))
    assert rg.enregistrer_reglages(chemin, v, tmp_path / "backups") is False
    assert not (tmp_path / "backups").exists()


def test_une_config_refusee_par_le_controle_n_est_pas_ecrite(tmp_path):
    chemin = _fichier(tmp_path)
    v = {**rg.lire_reglages(yaml.safe_load(ANCIEN)), "puissance_kwc": 9.0}

    def verifier(_cfg):
        raise RuntimeError("il manque quelque chose")

    with pytest.raises(rg.ReglagesRefuses):
        rg.enregistrer_reglages(chemin, v, tmp_path / "backups", verifier)
    assert chemin.read_text(encoding="utf-8") == ANCIEN


def test_un_texte_qui_ne_se_relit_pas_juste_n_est_pas_ecrit(tmp_path, monkeypatch):
    """Si la modification du texte touchait autre chose que prevu, la
    relecture le voit et rien n'est ecrit."""
    chemin = _fichier(tmp_path)
    v = {**rg.lire_reglages(yaml.safe_load(ANCIEN)), "puissance_kwc": 9.0}
    monkeypatch.setattr(rg, "appliquer_reglages",
                        lambda t, c, val: t.replace("6.0", "9.0").replace(
                            "15000.0", "1.0"))
    with pytest.raises(rg.ReglagesRefuses):
        rg.enregistrer_reglages(chemin, v, tmp_path / "backups")
    assert chemin.read_text(encoding="utf-8") == ANCIEN


@pytest.mark.parametrize("plages", [[], ["22h-6h"]])
def test_des_heures_creuses_mal_ecrites_sont_refusees(tmp_path, plages):
    chemin = _fichier(tmp_path)
    v = {**rg.lire_reglages(yaml.safe_load(ANCIEN)), "plages_hc": plages}
    with pytest.raises(rg.ReglagesRefuses):
        rg.enregistrer_reglages(chemin, v, tmp_path / "backups")
    assert chemin.read_text(encoding="utf-8") == ANCIEN


# -----------------------------------------------------------------------------
# La fenetre
# -----------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


def test_la_fenetre_rend_ce_qu_on_lui_donne(qapp):
    from fenetre_reglages import FenetreReglages
    v = rg.lire_reglages(yaml.safe_load(ANCIEN))
    fenetre = FenetreReglages(v, lambda _v: None)
    assert fenetre.valeurs() == v


def test_la_fenetre_reste_ouverte_si_l_enregistrement_est_refuse(qapp, monkeypatch):
    from fenetre_reglages import FenetreReglages, QMessageBox
    messages = []
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda *a: messages.append(a[2]))

    def refuser(_v):
        raise rg.ReglagesRefuses("non")

    fenetre = FenetreReglages(rg.lire_reglages(yaml.safe_load(ANCIEN)), refuser)
    fenetre._on_enregistrer()
    assert messages == ["non"]
    assert fenetre.result() == 0

# ======================================================================
# Les recalages sur factures (config-local.yaml)
# ======================================================================
#
# Demande d'un utilisateur (18/09/2026) : pouvoir dire a l'application ce
# qu'EDF OA a REELLEMENT paye, sans ouvrir le Bloc-notes. Ces sections
# reecrivent les releves journaliers : l'ecriture doit etre aussi prudente
# que celle de config.yaml.

LOCAL = """# Mon fichier local
sources:

  # Injection reellement payee par EDF OA
  injection_facturee:
    - { debut: "2024-01-01", fin: "2024-12-31", total_kwh: 3000,
        source: "autofacturation EDF OA" }

  recharges_ve_json: "F:/Recharge VE/recharges.json"
"""


def test_lire_les_recalages_d_une_config():
    cfg = yaml.safe_load(LOCAL)
    lus = rg.lire_recalages(cfg)
    assert lus["injection_facturee"] == [
        {"debut": date(2024, 1, 1), "fin": date(2024, 12, 31),
         "total_kwh": 3000.0, "source": "autofacturation EDF OA"},
    ]
    # Les autres sortes existent, vides.
    assert lus["conso_reseau_facturee"] == []
    assert lus["conso_reseau_douteuse"] == []


def test_ajouter_une_periode_facturee():
    cfg = yaml.safe_load(LOCAL)
    recalages = rg.lire_recalages(cfg)
    recalages["injection_facturee"].append(
        {"debut": date(2025, 1, 1), "fin": date(2025, 12, 31),
         "total_kwh": 3210.5, "source": "autofacturation 2025"})
    neuf = rg.appliquer_recalages(LOCAL, recalages)
    relu = yaml.safe_load(neuf)
    assert len(relu["sources"]["injection_facturee"]) == 2
    assert relu["sources"]["injection_facturee"][1]["total_kwh"] == 3210.5
    # Ce qui n'est pas un recalage n'est pas touche.
    assert relu["sources"]["recharges_ve_json"] == "F:/Recharge VE/recharges.json"
    assert "# Mon fichier local" in neuf
    assert "# Injection reellement payee par EDF OA" in neuf


# Le fichier d'un utilisateur de longue date : des totaux en entiers, et une
# source trop longue pour tenir sur une ligne. Ajouter une periode ne doit
# rien y changer -- ces lignes representent des heures de relevé de factures.
LOCAL_SOIGNE = """\
sources:

  injection_facturee:
    - { debut: "2022-04-29", fin: "2022-06-27", total_kwh: 1497,
        source: "avant contrat OA : index du compteur au
                 28/06/2022 (facture AF232803078110)" }
    - { debut: "2022-06-28", fin: "2023-06-27", total_kwh: 4731,
        source: "autofacturation" }
"""


def test_ajouter_ne_reecrit_pas_les_periodes_existantes():
    recalages = rg.lire_recalages(yaml.safe_load(LOCAL_SOIGNE))
    recalages["injection_facturee"].append(
        {"debut": date(2023, 6, 28), "fin": date(2024, 6, 27),
         "total_kwh": 4306, "source": "autofacturation"})
    neuf = rg.appliquer_recalages(LOCAL_SOIGNE, recalages)
    # Tout l'ancien texte est encore la, mot pour mot.
    assert LOCAL_SOIGNE.rstrip() in neuf
    assert "total_kwh: 1497," in neuf and "total_kwh: 1497.0" not in neuf
    assert rg.lire_recalages(yaml.safe_load(neuf)) == recalages


def test_un_total_entier_reste_entier():
    recalages = rg.recalages_vides()
    recalages["injection_facturee"].append(
        {"debut": date(2025, 1, 1), "fin": date(2025, 12, 31),
         "total_kwh": 3000, "source": ""})
    neuf = rg.appliquer_recalages("sources:\n", recalages)
    assert "total_kwh: 3000," in neuf
    # Une decimale, elle, est gardee.
    recalages["injection_facturee"][0]["total_kwh"] = 641.07
    assert "total_kwh: 641.07," in rg.appliquer_recalages("sources:\n", recalages)


def test_une_sorte_absente_est_ajoutee():
    cfg = yaml.safe_load(LOCAL)
    recalages = rg.lire_recalages(cfg)
    recalages["conso_reseau_douteuse"].append(
        {"debut": date(2025, 3, 10), "fin": date(2025, 3, 14),
         "motif": "panne Linky"})
    relu = yaml.safe_load(rg.appliquer_recalages(LOCAL, recalages))
    # Les dates s'ecrivent entre guillemets, comme dans le modele livre :
    # YAML les rend donc en chaines, que lire_recalages renormalise.
    assert rg.lire_recalages(relu)["conso_reseau_douteuse"] == [
        {"debut": date(2025, 3, 10), "fin": date(2025, 3, 14),
         "motif": "panne Linky"},
    ]


def test_tout_retirer_laisse_une_liste_vide():
    cfg = yaml.safe_load(LOCAL)
    recalages = rg.lire_recalages(cfg)
    recalages["injection_facturee"].clear()
    relu = yaml.safe_load(rg.appliquer_recalages(LOCAL, recalages))
    assert relu["sources"]["injection_facturee"] == []


def test_sans_changement_le_fichier_local_est_identique():
    cfg = yaml.safe_load(LOCAL)
    assert rg.appliquer_recalages(LOCAL, rg.lire_recalages(cfg)) == LOCAL


def test_enregistrer_cree_le_fichier_s_il_manque(tmp_path):
    chemin = tmp_path / "config-local.yaml"
    recalages = rg.recalages_vides()
    recalages["injection_facturee"].append(
        {"debut": date(2025, 1, 1), "fin": date(2025, 12, 31),
         "total_kwh": 3000, "source": "autofacturation EDF OA"})
    assert rg.enregistrer_recalages(chemin, recalages, tmp_path / "backups")
    relu = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    assert relu["sources"]["injection_facturee"][0]["total_kwh"] == 3000


def test_enregistrer_sauvegarde_avant_d_ecrire(tmp_path):
    chemin = tmp_path / "config-local.yaml"
    chemin.write_text(LOCAL, encoding="utf-8")
    sauvegardes = tmp_path / "backups"
    recalages = rg.lire_recalages(yaml.safe_load(LOCAL))
    recalages["injection_facturee"][0]["total_kwh"] = 3100
    assert rg.enregistrer_recalages(chemin, recalages, sauvegardes)
    copies = list(sauvegardes.glob("config-local_avant-reglages_*.yaml"))
    assert len(copies) == 1
    assert copies[0].read_text(encoding="utf-8") == LOCAL


def test_enregistrer_ne_fait_rien_si_rien_ne_change(tmp_path):
    chemin = tmp_path / "config-local.yaml"
    chemin.write_text(LOCAL, encoding="utf-8")
    recalages = rg.lire_recalages(yaml.safe_load(LOCAL))
    assert rg.enregistrer_recalages(chemin, recalages, tmp_path / "b") is False
    assert chemin.read_text(encoding="utf-8") == LOCAL


def test_une_periode_a_l_envers_est_refusee(tmp_path):
    recalages = rg.recalages_vides()
    recalages["injection_facturee"].append(
        {"debut": date(2025, 12, 31), "fin": date(2025, 1, 1),
         "total_kwh": 3000, "source": ""})
    with pytest.raises(rg.ReglagesRefuses, match="après"):
        rg.enregistrer_recalages(tmp_path / "c.yaml", recalages, tmp_path / "b")


def test_un_total_negatif_est_refuse(tmp_path):
    recalages = rg.recalages_vides()
    recalages["conso_reseau_facturee"].append(
        {"debut": date(2025, 1, 1), "fin": date(2025, 12, 31),
         "total_kwh": -5, "source": ""})
    with pytest.raises(rg.ReglagesRefuses):
        rg.enregistrer_recalages(tmp_path / "c.yaml", recalages, tmp_path / "b")

# ======================================================================
# La fenetre : les recalages saisis ressortent tels quels
# ======================================================================

VALEURS_FENETRE = {
    "puissance_kwc": 6.0, "cout_total_eur": 15000,
    "date_mise_en_service": date(2022, 5, 2),
    "date_debut_contrat_oa": date(2022, 7, 1),
    "prix_oa": 0.1003, "prime_par_kwc": 380.0, "prime_duree": 5,
    "nom": "Octopus", "offre": "Octopus Go", "abonnement": 20.16,
    "prix_hp": 0.2213, "prix_hc": 0.129, "prix_depuis": date(2026, 8, 1),
    "plages_hc": ["22:00-06:00"], "part_hc_autoconso": 0.20,
}


@pytest.fixture
def fenetre():
    """Une fenetre Mes reglages, sans jamais l'afficher a l'ecran."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from fenetre_reglages import FenetreReglages

    app = QApplication.instance() or QApplication([])

    def construire(recalages):
        return FenetreReglages(dict(VALEURS_FENETRE), lambda v: None, None,
                               recalages=recalages,
                               enregistrer_recalages=lambda r: None)

    yield construire
    app.processEvents()


def test_la_fenetre_rend_les_recalages_qu_on_lui_donne(fenetre):
    donnes = rg.recalages_vides()
    donnes["injection_facturee"].append(
        {"debut": date(2024, 7, 1), "fin": date(2025, 6, 30),
         "total_kwh": 3210.5, "source": "autofacturation EDF OA"})
    donnes["conso_reseau_douteuse"].append(
        {"debut": date(2025, 3, 10), "fin": date(2025, 3, 14),
         "motif": "panne Linky"})
    assert fenetre(donnes).recalages() == donnes


def test_sans_recalage_la_fenetre_n_en_invente_pas(fenetre):
    assert fenetre(rg.recalages_vides()) .recalages() == rg.recalages_vides()


def test_les_jours_douteux_n_ont_pas_de_total(fenetre):
    """Leur case kWh est grisee : un jour ecarte n'a pas de total."""
    donnes = rg.recalages_vides()
    donnes["conso_reseau_douteuse"].append(
        {"debut": date(2025, 3, 10), "fin": date(2025, 3, 14), "motif": "x"})
    f = fenetre(donnes)
    ligne = f._lignes.itemAt(0).widget()
    assert not ligne.total.isEnabled()
    assert "total_kwh" not in f.recalages()["conso_reseau_douteuse"][0]


def test_une_ligne_retiree_disparait_des_recalages(fenetre):
    donnes = rg.recalages_vides()
    donnes["injection_facturee"].append(
        {"debut": date(2024, 7, 1), "fin": date(2025, 6, 30),
         "total_kwh": 3210.5, "source": ""})
    f = fenetre(donnes)
    f._retirer_ligne(f._lignes.itemAt(0).widget())
    assert f.recalages() == rg.recalages_vides()

# ======================================================================
# La prime a l'autoconsommation se lit en euros, pas en euros par kWc
# ======================================================================
#
# Un utilisateur, 18/09/2026 : « j'ai donc mis mes 1440 euros et du coup au bout
# d'un an mon installation etait amortie ». Le champ attend un montant PAR
# kWc ; il a saisi son total, et rien ne l'a averti. Il a fini par trouver
# 120 par tatonnement, en croyant que c'etait un montant mensuel.


def test_la_prime_dit_son_total():
    assert rg.phrase_prime(par_kwc=120, kwc=12, duree=1) == (
        "120 €/kWc × 12 kWc = 1 440 € au total, versés en une seule fois."
    )


def test_la_prime_etalee_dit_le_versement_annuel():
    assert rg.phrase_prime(par_kwc=380, kwc=6, duree=5) == (
        "380 €/kWc × 6 kWc = 2 280 € au total, soit 456 € par an pendant 5 ans."
    )


def test_une_prime_nulle_se_tait():
    assert rg.phrase_prime(par_kwc=0, kwc=6, duree=1) == "Pas de prime."


def test_les_decimales_de_puissance_sont_gardees():
    assert rg.phrase_prime(par_kwc=100, kwc=3.5, duree=1) == (
        "100 €/kWc × 3,5 kWc = 350 € au total, versés en une seule fois."
    )

# ======================================================================
# La prime se saisit au choix : en tout, ou par kWc
# ======================================================================
#
# Suite du retour du 18/09/2026. L'utilisateur a fait remarquer (19/09) que ce
# qu'il a sous les yeux, c'est le montant touche avec sa premiere facture --
# pas un montant par kWc. La saisie propose donc les deux, le fichier de
# configuration continuant de stocker le montant PAR kWc : rien a convertir
# dans les reglages existants.


def test_le_total_se_deduit_du_montant_par_kwc():
    assert rg.prime_totale(par_kwc=160, kwc=9) == 1440


def test_le_montant_par_kwc_se_deduit_du_total():
    assert rg.prime_par_kwc_depuis_total(total=1440, kwc=9) == 160


def test_une_puissance_nulle_ne_divise_rien():
    """Sans puissance saisie, la conversion n'a pas de sens : zero, pas un
    plantage."""
    assert rg.prime_par_kwc_depuis_total(total=1440, kwc=0) == 0


def test_les_deux_conversions_se_repondent():
    total = rg.prime_totale(par_kwc=380, kwc=6)
    assert rg.prime_par_kwc_depuis_total(total, 6) == 380


def test_la_phrase_en_mode_total_donne_le_montant_par_kwc():
    """En saisie « en tout », c'est l'autre valeur qui manque a l'utilisateur."""
    assert rg.phrase_prime(par_kwc=160, kwc=9, duree=1, saisie="total") == (
        "1 440 € au total pour 9 kWc, soit 160 €/kWc, "
        "versés en une seule fois."
    )


def test_la_phrase_en_mode_total_avec_etalement():
    assert rg.phrase_prime(par_kwc=380, kwc=6, duree=5, saisie="total") == (
        "2 280 € au total pour 6 kWc, soit 380 €/kWc, "
        "étalés sur 5 ans (456 € par an)."
    )


def test_le_mode_par_kwc_reste_la_phrase_d_origine():
    """Le defaut ne change pas : les appels existants gardent leur phrase."""
    assert rg.phrase_prime(par_kwc=120, kwc=12, duree=1) == (
        "120 €/kWc × 12 kWc = 1 440 € au total, versés en une seule fois."
    )


def test_une_prime_nulle_se_tait_aussi_en_mode_total():
    assert rg.phrase_prime(0, 9, 1, saisie="total") == "Pas de prime."

def test_la_fenetre_ouvre_la_prime_sur_le_montant_total(qapp):
    """Le choix s'ouvre sur « en tout » : ce que l'utilisateur a touche."""
    from fenetre_reglages import FenetreReglages
    f = FenetreReglages(dict(VALEURS_FENETRE), lambda _v: None)
    # 380 €/kWc pour 6 kWc, c'est 2 280 € recus.
    assert f.prime.value() == 2280
    assert f.prime.suffix() == " €"
    # Mais le fichier, lui, garde des euros par kWc : rien a convertir.
    assert f.valeurs()["prime_par_kwc"] == 380.0


def test_basculer_en_par_kwc_convertit_la_somme_affichee(qapp):
    from fenetre_reglages import FenetreReglages
    f = FenetreReglages(dict(VALEURS_FENETRE), lambda _v: None)
    f.mode_prime.setCurrentIndex(1)
    assert f.prime.value() == 380
    assert f.prime.suffix() == " €/kWc"
    assert f.valeurs()["prime_par_kwc"] == 380.0


def test_le_total_saisi_ne_se_multiplie_plus_par_la_puissance(qapp):
    """Le piege du 18/09/2026 : saisir 1440 (son total) dans une case qui
    attendait des €/kWc valorisait la prime a 8 640 € pour 6 kWc."""
    from fenetre_reglages import FenetreReglages
    f = FenetreReglages(dict(VALEURS_FENETRE), lambda _v: None)
    f.prime.setValue(1440)
    assert f.valeurs()["prime_par_kwc"] == 240.0
    assert "1 440 € au total" in f.total_prime.text()


def test_la_phrase_suit_le_mode_de_saisie(qapp):
    from fenetre_reglages import FenetreReglages
    f = FenetreReglages(dict(VALEURS_FENETRE), lambda _v: None)
    assert f.total_prime.text().startswith("2 280 € au total")
    f.mode_prime.setCurrentIndex(1)
    assert f.total_prime.text().startswith("380 €/kWc")



# -----------------------------------------------------------------------------
# Part des heures creuses dans l'autoconsommation (promesse du 19/09/2026 a un
# utilisateur : ce reglage ne se changeait qu'au Bloc-notes)
# -----------------------------------------------------------------------------


def _sans_part_hc(texte: str) -> str:
    """Le meme fichier, sans la ligne part_hc_autoconso (vieux fichiers)."""
    return "".join(ligne for ligne in texte.splitlines(keepends=True)
                   if "part_hc_autoconso:" not in ligne)


def test_part_hc_est_lue_telle_qu_ecrite():
    assert rg.lire_reglages(yaml.safe_load(ANCIEN))["part_hc_autoconso"] == 0.20
    # Le modele livre ecrit 0 : ce zero est une vraie valeur, pas un vide.
    assert rg.lire_reglages(yaml.safe_load(MODELE))["part_hc_autoconso"] == 0.0


def test_part_hc_absente_vaut_ce_que_l_application_utilise():
    # Sans la ligne, les calculs prennent 20 % (app_desktop) : la fenetre
    # doit montrer ce qui est reellement applique, pas une case vide.
    cfg = yaml.safe_load(_sans_part_hc(ANCIEN))
    assert rg.lire_reglages(cfg)["part_hc_autoconso"] == 0.20


def test_changer_la_part_hc_ne_touche_que_sa_ligne():
    nouveau, relu = _appliquer(ANCIEN, part_hc_autoconso=0.35)
    assert relu["tarifs_reseau"]["octopus_hphc"]["part_hc_autoconso"] == 0.35
    avant, apres = ANCIEN.splitlines(), nouveau.splitlines()
    # strict : meme nombre de lignes, la valeur est remplacee, pas ajoutee.
    differentes = [a for a, b in zip(avant, apres, strict=True) if a != b]
    assert differentes == ["    part_hc_autoconso: 0.20"]
    assert _commentaires(nouveau) == _commentaires(ANCIEN)


def test_la_part_hc_du_modele_se_remplit():
    _nouveau, relu = _appliquer(MODELE, part_hc_autoconso=0.2)
    assert relu["tarifs_reseau"]["contrat_hphc"]["part_hc_autoconso"] == 0.2


def test_part_hc_absente_et_inchangee_n_ecrit_rien():
    texte = _sans_part_hc(ANCIEN)
    cfg = yaml.safe_load(texte)
    assert rg.appliquer_reglages(texte, cfg, rg.lire_reglages(cfg)) == texte


def test_part_hc_absente_puis_changee_est_ajoutee_au_contrat():
    _nouveau, relu = _appliquer(_sans_part_hc(ANCIEN), part_hc_autoconso=0.0)
    assert relu["tarifs_reseau"]["octopus_hphc"]["part_hc_autoconso"] == 0.0


@pytest.mark.parametrize("part", [-0.1, 1.5])
def test_une_part_hc_hors_de_0_a_100_pour_cent_est_refusee(part):
    v = {**rg.lire_reglages(yaml.safe_load(ANCIEN)), "part_hc_autoconso": part}
    with pytest.raises(rg.ReglagesRefuses, match="heures creuses"):
        rg.controler(v)


def test_la_fenetre_montre_la_part_hc_en_pour_cent(qapp):
    from fenetre_reglages import FenetreReglages
    f = FenetreReglages(dict(VALEURS_FENETRE), lambda _v: None)
    assert f.part_hc.value() == 20
    assert f.part_hc.suffix() == " %"
    f.part_hc.setValue(35)
    assert f.valeurs()["part_hc_autoconso"] == 0.35


def test_une_part_hc_fine_n_est_pas_arrondie_en_douce(qapp):
    # 0,225 s'affiche arrondi a 23 %. Tant qu'on ne touche pas a la case,
    # enregistrer d'autres reglages doit rendre 0,225, pas 0,23 : sinon le
    # fichier changerait sans que l'utilisateur l'ait voulu.
    from fenetre_reglages import FenetreReglages
    f = FenetreReglages({**VALEURS_FENETRE, "part_hc_autoconso": 0.225},
                        lambda _v: None)
    f.prix_hp.setValue(0.25)
    assert f.valeurs()["part_hc_autoconso"] == 0.225
