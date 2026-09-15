"""Tests unitaires pour data_loaders.py (lecture/ecriture du CSV releves)."""
from __future__ import annotations

import os
from datetime import date as _date

import pandas as pd
import pytest

import data_loaders as dl

# Deux jours volontairement dans le desordre : 02/05 avant 01/05.
# Le 02/05 n'a pas de soutirage direct mais a le detail HC/HP.
CSV_NOMINAL = (
    "Date;Prod_Jour;Inj_Jour;Conso_réseau_Jour;Conso_HC;Conso_HP\n"
    "02/05/2026;18,0;12,0;;1,5;1,6\n"
    "01/05/2026;20,5;15,2;3,1;1,0;2,1\n"
)


@pytest.fixture
def csv_path(tmp_path) -> str:
    p = tmp_path / "Releves-pv.csv"
    p.write_text(CSV_NOMINAL, encoding="utf-8")
    return str(p)


# -----------------------------------------------------------------------------
# read_releves_raw (editeur de saisie)
# -----------------------------------------------------------------------------

def test_read_raw_trie_par_date(csv_path):
    rows = dl.read_releves_raw(csv_path)
    assert [r["Date"] for r in rows] == ["01/05/2026", "02/05/2026"]


def test_read_raw_preserve_les_chaines(csv_path):
    rows = dl.read_releves_raw(csv_path)
    assert rows[0]["Prod_Jour"] == "20,5"     # virgule FR preservee
    assert rows[1]["Conso_réseau_Jour"] == ""  # case vide preservee


def test_read_raw_fichier_absent(tmp_path):
    assert dl.read_releves_raw(str(tmp_path / "absent.csv")) == []


def test_read_raw_colonne_sans_accent(tmp_path):
    # Variante d'en-tete sans accent -> mappee sur le nom officiel accentue.
    p = tmp_path / "r.csv"
    p.write_text(
        "Date;Prod_Jour;Inj_Jour;Conso_reseau_Jour;Conso_HC;Conso_HP\n"
        "01/05/2026;10,0;5,0;2,0;;\n",
        encoding="utf-8",
    )
    rows = dl.read_releves_raw(str(p))
    assert rows[0]["Conso_réseau_Jour"] == "2,0"


def test_read_raw_entete_illisible_refuse(tmp_path):
    # Ce que produit Excel quand il a lu le CSV en ANSI puis l'a reenregistre
    # en "CSV UTF-8" : l'accent devient deux caracteres. Avant, la colonne
    # n'entrait pas dans colmap et TOUTES ses valeurs devenaient "" -- sans
    # exception ni avertissement. L'appli demarrait, les vues basculaient en
    # silence sur le repli HC+HP, et le premier Enregistrer detruisait des
    # annees de conso en reecrivant un en-tete correctement accentue.
    p = tmp_path / "r.csv"
    p.write_text(
        "Date;Prod_Jour;Inj_Jour;Conso_rÃ©seau_Jour;Conso_HC;Conso_HP\n"
        "01/05/2026;10,0;5,0;2,0;;\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError) as exc:
        dl.read_releves_raw(str(p))
    message = str(exc.value)
    assert "Conso_réseau_Jour" in message    # la colonne qu'on ne retrouve pas
    assert "Conso_rÃ©seau_Jour" in message   # les en-tetes reellement lus


def test_read_raw_colonne_absente_refuse(tmp_path):
    # Colonne carrement absente : meme traitement, pour la meme raison.
    p = tmp_path / "r.csv"
    p.write_text(
        "Date;Prod_Jour;Inj_Jour;Conso_HC;Conso_HP\n"
        "01/05/2026;10,0;5,0;;\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Conso_réseau_Jour"):
        dl.read_releves_raw(str(p))


def test_read_raw_alias_legitimes_toujours_acceptes(tmp_path):
    # La distinction est "aucun alias ne correspond" (erreur), et non "le nom
    # n'est pas exactement l'officiel" (tolere). Les variantes documentees
    # doivent continuer de passer.
    p = tmp_path / "r.csv"
    p.write_text(
        "Jour;Production;Injection;Conso_reseau_Jour;HC;HP\n"
        "01/05/2026;10,0;5,0;2,0;0,5;1,5\n",
        encoding="utf-8",
    )
    rows = dl.read_releves_raw(str(p))
    assert rows[0]["Conso_réseau_Jour"] == "2,0"
    assert rows[0]["Prod_Jour"] == "10,0"
    assert rows[0]["Conso_HC"] == "0,5"


def test_read_raw_ignore_lignes_sans_date(tmp_path):
    p = tmp_path / "r.csv"
    p.write_text(
        "Date;Prod_Jour;Inj_Jour;Conso_réseau_Jour;Conso_HC;Conso_HP\n"
        ";10,0;;;;\n"
        "01/05/2026;12,0;;;;\n",
        encoding="utf-8",
    )
    rows = dl.read_releves_raw(str(p))
    assert len(rows) == 1
    assert rows[0]["Date"] == "01/05/2026"


# -----------------------------------------------------------------------------
# write_releves_raw (ecriture atomique + backup)
# -----------------------------------------------------------------------------

def _ligne(date: str, prod: str = "1,0") -> dict[str, str]:
    return {"Date": date, "Prod_Jour": prod, "Inj_Jour": "",
            "Conso_réseau_Jour": "", "Conso_HC": "", "Conso_HP": ""}


def test_write_raw_roundtrip_et_tri(tmp_path):
    p = str(tmp_path / "out.csv")
    dl.write_releves_raw(p, [_ligne("02/05/2026", "18,0"),
                             _ligne("01/05/2026", "20,5")])
    relu = dl.read_releves_raw(p)
    assert [r["Date"] for r in relu] == ["01/05/2026", "02/05/2026"]
    assert relu[1]["Prod_Jour"] == "18,0"


def test_write_raw_cree_backup(csv_path):
    with open(csv_path, encoding="utf-8") as fh:
        original = fh.read()
    rows = dl.read_releves_raw(csv_path)
    rows.append(_ligne("03/05/2026", "9,9"))
    dl.write_releves_raw(csv_path, rows)

    bak = csv_path + ".bak"
    assert os.path.exists(bak)
    with open(bak, encoding="utf-8") as fh:
        assert fh.read() == original  # le .bak est la version d'AVANT


def test_write_raw_pas_de_tmp_residuel(csv_path):
    dl.write_releves_raw(csv_path, dl.read_releves_raw(csv_path))
    assert not os.path.exists(csv_path + ".tmp")


def test_write_raw_force_l_ecriture_sur_le_disque(csv_path, monkeypatch):
    # NTFS journalise le RENOMMAGE, pas les donnees : sans fsync, une coupure
    # de courant entre l'ecriture du .tmp et sa publication peut laisser un
    # CSV de 0 octet -- le renommage etant, lui, bel et bien enregistre.
    appels = []
    vrai_fsync, vrai_replace = os.fsync, os.replace

    def _fsync(fd):
        appels.append("fsync")
        return vrai_fsync(fd)

    def _replace(src, dst):
        appels.append("replace")
        return vrai_replace(src, dst)

    monkeypatch.setattr(dl.os, "fsync", _fsync)
    monkeypatch.setattr(dl.os, "replace", _replace)

    dl.write_releves_raw(csv_path, dl.read_releves_raw(csv_path))

    assert "fsync" in appels, "les donnees ne sont pas forcees sur le disque"
    assert appels.index("fsync") < appels.index("replace"), (
        "le fsync doit avoir lieu AVANT la publication")


def test_write_raw_echappe_le_separateur(tmp_path):
    # ";".join(cells) sans echappement : un ';' dans une valeur produisait
    # 7 champs au lieu de 6 et rendait le CSV illisible DEFINITIVEMENT
    # (ParserError au demarrage suivant). L'exposition est faible -- la
    # saisie refuse deja '1;5' -- mais le degat serait irreversible.
    p = str(tmp_path / "out.csv")
    ligne = {c: "" for c in dl.RELEVES_HEADER}
    ligne["Date"] = "01/05/2026"
    ligne["Prod_Jour"] = "1;5"
    dl.write_releves_raw(p, [ligne])

    relu = dl.read_releves_raw(p)
    assert len(relu) == 1
    assert relu[0]["Prod_Jour"] == "1;5"


def test_write_raw_conserve_le_format_exact_du_fichier(tmp_path):
    # Le fichier reel est en LF sans BOM et sans guillemets : l'echappement
    # ne doit rien changer a son apparence pour les valeurs normales.
    # csv.writer ecrit des CRLF par defaut, ce qui reecrirait 1572 lignes.
    p = str(tmp_path / "out.csv")
    dl.write_releves_raw(p, [_ligne("01/05/2026", "20,5")])

    brut = open(p, "rb").read()
    assert b"\r\n" not in brut                  # fins de ligne LF
    assert brut.startswith("Date;Prod_Jour".encode())
    assert b'"' not in brut                    # aucun guillemet superflu
    assert brut.endswith(b"01/05/2026;20,5;;;;\n")


def test_write_raw_ignore_lignes_sans_date(tmp_path):
    p = str(tmp_path / "out.csv")
    dl.write_releves_raw(p, [_ligne(""), _ligne("01/05/2026")])
    assert len(dl.read_releves_raw(p)) == 1


# ---------------------------------------------------------------------------
# Controle de volumetrie : ecrire moins que ce qui est sur le disque est
# une suppression. Elle doit etre demandee, jamais subie.
# ---------------------------------------------------------------------------

def _csv_trois_jours(tmp_path) -> str:
    p = str(tmp_path / "Releves-pv.csv")
    dl.write_releves_raw(p, [
        {"Date": "01/05/2026", "Prod_Jour": "20,5", "Inj_Jour": "15,2",
         "Conso_réseau_Jour": "3,1", "Conso_HC": "1", "Conso_HP": "2,1"},
        {"Date": "02/05/2026", "Prod_Jour": "18", "Inj_Jour": "12",
         "Conso_réseau_Jour": "2", "Conso_HC": "1,5", "Conso_HP": "1,6"},
        {"Date": "03/05/2026", "Prod_Jour": "19", "Inj_Jour": "13",
         "Conso_réseau_Jour": "2,5", "Conso_HC": "1,2", "Conso_HP": "1,3"},
    ])
    return p


def test_write_raw_refuse_de_perdre_des_lignes(tmp_path):
    # Le cas reel : une lecture partielle (synchro interrompue, fichier
    # verrouille) laisse un cache incomplet, et _enregistrer reconstruit tout
    # le fichier a partir de ce cache. Ce qui n'a pas ete lu n'est pas reecrit.
    p = _csv_trois_jours(tmp_path)
    avant = open(p, encoding="utf-8").read()

    partiel = dl.read_releves_raw(p)[:1]      # une seule des trois journees
    with pytest.raises(dl.ReductionRefusee):
        dl.write_releves_raw(p, partiel)

    # Le fichier sur le disque n'a pas bouge.
    assert open(p, encoding="utf-8").read() == avant


def test_write_raw_refuse_de_vider_une_colonne(tmp_path):
    # Meme nombre de lignes, mais une colonne entiere passee a vide : c'est
    # ce que produisait l'en-tete non reconnu de A3.
    p = _csv_trois_jours(tmp_path)
    rows = dl.read_releves_raw(p)
    for r in rows:
        r["Conso_réseau_Jour"] = ""

    with pytest.raises(dl.ReductionRefusee):
        dl.write_releves_raw(p, rows)


def test_write_raw_message_nomme_precisement_les_pertes(tmp_path):
    p = _csv_trois_jours(tmp_path)
    rows = dl.read_releves_raw(p)[:1]
    with pytest.raises(dl.ReductionRefusee) as exc:
        dl.write_releves_raw(p, rows)

    pertes = exc.value.pertes
    assert "2 ligne(s)" in pertes
    assert "Conso_réseau_Jour" in pertes    # la colonne est nommee
    assert "2 valeur(s)" in pertes          # et le compte aussi


def test_write_raw_reduction_acceptee_si_demandee(tmp_path):
    # L'effacement volontaire reste possible : il faut le dire explicitement.
    p = _csv_trois_jours(tmp_path)
    rows = dl.read_releves_raw(p)[:1]
    dl.write_releves_raw(p, rows, autoriser_reduction=True)
    assert [r["Date"] for r in dl.read_releves_raw(p)] == ["01/05/2026"]


def test_write_raw_laisse_passer_un_ajout(tmp_path):
    # Aucune baisse : l'ecriture normale ne doit rien demander.
    p = _csv_trois_jours(tmp_path)
    rows = dl.read_releves_raw(p)
    rows.append({"Date": "04/05/2026", "Prod_Jour": "21", "Inj_Jour": "",
                 "Conso_réseau_Jour": "", "Conso_HC": "", "Conso_HP": ""})
    dl.write_releves_raw(p, rows)
    assert len(dl.read_releves_raw(p)) == 4


def test_write_raw_laisse_passer_une_correction(tmp_path):
    # Corriger une valeur ne change aucun compte : rien ne doit s'y opposer.
    p = _csv_trois_jours(tmp_path)
    rows = dl.read_releves_raw(p)
    rows[0]["Prod_Jour"] = "21,5"
    dl.write_releves_raw(p, rows)
    assert dl.read_releves_raw(p)[0]["Prod_Jour"] == "21,5"


def test_write_raw_fichier_neuf_sans_controle(tmp_path):
    # Rien sur le disque : il n'y a rien a perdre.
    p = str(tmp_path / "neuf.csv")
    dl.write_releves_raw(p, [_ligne("01/05/2026")])
    assert len(dl.read_releves_raw(p)) == 1


def test_pertes_a_l_ecriture_rien_a_signaler(tmp_path):
    p = _csv_trois_jours(tmp_path)
    assert dl.pertes_a_l_ecriture(p, dl.read_releves_raw(p)) is None


# -----------------------------------------------------------------------------
# parse_enedis_csv + merge_import (import d'un export Enedis, sans doublon)
# -----------------------------------------------------------------------------

def test_parse_enedis_injection_wh_dates_iso(tmp_path):
    # Format courant : metadonnees puis 'Date;Valeur (en Wh)', dates ISO.
    p = tmp_path / "enedis.csv"
    p.write_text(
        "Identifiant PRM;Type de donnees;Date de debut;Date de fin\n"
        "12345678901234;Injection quotidienne;01/06/2026;03/06/2026\n"
        "\n"
        "Date;Valeur (en Wh)\n"
        "2026-06-01;12571\n"
        "2026-06-02;9800\n",
        encoding="utf-8",
    )
    colonne, valeurs = dl.parse_enedis_csv(str(p))
    assert colonne == "Inj_Jour"
    assert valeurs == {"01/06/2026": "12,571", "02/06/2026": "9,8"}


def test_parse_enedis_conso_kwh_dates_fr(tmp_path):
    p = tmp_path / "enedis.csv"
    p.write_text(
        "Date;Consommation (en kWh)\n"
        "01/06/2026;12,5\n"
        "02/06/2026;9\n",
        encoding="utf-8",
    )
    colonne, valeurs = dl.parse_enedis_csv(str(p))
    assert colonne == "Conso_réseau_Jour"
    assert valeurs == {"01/06/2026": "12,5", "02/06/2026": "9"}


def test_parse_enedis_unite_devinee(tmp_path):
    # Pas d'unite dans l'entete : mediane > 200 -> valeurs en Wh.
    p = tmp_path / "enedis.csv"
    p.write_text(
        "Type;Consommation quotidienne\n"
        "Date;Valeur\n"
        "2026-06-01;12571\n",
        encoding="utf-8",
    )
    _, valeurs = dl.parse_enedis_csv(str(p))
    assert valeurs == {"01/06/2026": "12,571"}


def test_parse_enedis_type_inconnu(tmp_path):
    p = tmp_path / "autre.csv"
    p.write_text("Date;Truc\n2026-06-01;5\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Type de donnees"):
        dl.parse_enedis_csv(str(p))


def test_parse_enedis_sans_lignes_donnees(tmp_path):
    p = tmp_path / "vide.csv"
    p.write_text("Injection quotidienne;periode\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Aucune ligne"):
        dl.parse_enedis_csv(str(p))


def test_parse_enedis_xlsx_deux_feuilles(tmp_path):
    # Reproduit la structure du classeur officiel Enedis : page d'accueil,
    # puis une feuille par grandeur avec metadonnees et tableau Date/Valeur.
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    accueil = wb.active
    accueil.title = "Page d'accueil"
    accueil["B6"] = "Les données de ce fichier..."
    for nom, valeur in (("Export Consommation Quotidienne", 1.361),
                        ("Export Production Quotidienne", 33.53)):
        ws = wb.create_sheet(nom)
        ws["B9"] = "Date de début : "
        ws["C9"] = "08/07/2023"
        ws["B14"] = "Date"
        ws["C14"] = "Valeur (en kWh)"
        ws["B15"] = "08/07/2023"
        ws["C15"] = valeur
        ws["B16"] = "09/07/2023"
        ws["C16"] = "NA"  # donnees indisponibles -> jour ignore
    p = tmp_path / "export_enedis.xlsx"
    wb.save(p)

    imports = dl.parse_enedis_fichier(str(p))
    assert imports == {
        "Conso_réseau_Jour": {"08/07/2023": "1,361"},
        "Inj_Jour": {"08/07/2023": "33,53"},
    }


# Extrait du "suivi de consommation" telecharge chez Octopus (et non chez
# Enedis, malgre le PRM dans le nom du fichier) : colonnes nommees, avec le
# detail heures creuses / heures pleines.
SUIVI_CONSO_OCTOPUS = (
    "Période de consommation;Consommation (kWh);Consommation (euros);"
    "Nature de la donnée (Réelle/estimée);Option tarifaire;"
    "Consommation HP (kWh);Consommation HC (kWh);"
    "Consommation HP (euros);Consommation HC (euros)\n"
    "01/07/2026;4,749;0,62;-;Heures pleines / heures creuses;"
    "1,005;3,744;0,22;0,4\n"
    "02/07/2026;2,459;0,35;-;Heures pleines / heures creuses;"
    "0,747;1,712;0,16;0,19\n"
)


def test_parse_octopus_suivi_conso_detail_hphc(tmp_path):
    p = tmp_path / "suivi_conso.csv"
    p.write_text(SUIVI_CONSO_OCTOPUS, encoding="utf-8")
    assert dl.parse_enedis_fichier(str(p)) == {
        "Conso_réseau_Jour": {"01/07/2026": "4,749", "02/07/2026": "2,459"},
        "Conso_HP": {"01/07/2026": "1,005", "02/07/2026": "0,747"},
        "Conso_HC": {"01/07/2026": "3,744", "02/07/2026": "1,712"},
    }


def test_parse_octopus_suivi_conso_ignore_les_euros(tmp_path):
    # La colonne "Consommation (euros)" ne doit pas etre prise pour des kWh.
    p = tmp_path / "suivi_conso.csv"
    p.write_text(SUIVI_CONSO_OCTOPUS, encoding="utf-8")
    imports = dl.parse_enedis_fichier(str(p))
    assert imports["Conso_réseau_Jour"]["01/07/2026"] != "0,62"


def test_parse_enedis_csv_simple_reste_gere(tmp_path):
    # Sans colonnes HC/HP nommees, le parseur generique reprend la main.
    p = tmp_path / "enedis.csv"
    p.write_text("Date;Consommation (en kWh)\n01/06/2026;12,5\n",
                 encoding="utf-8")
    assert dl.parse_enedis_fichier(str(p)) == {
        "Conso_réseau_Jour": {"01/06/2026": "12,5"},
    }


def test_parse_enedis_fichier_dispatch_csv(tmp_path):
    p = tmp_path / "enedis.csv"
    p.write_text("Date;Consommation (en kWh)\n01/06/2026;12,5\n",
                 encoding="utf-8")
    assert dl.parse_enedis_fichier(str(p)) == {
        "Conso_réseau_Jour": {"01/06/2026": "12,5"},
    }


# ---------------------------------------------------------------- Enphase

# Extrait du rapport "Energie mensuelle" : un pas de 15 minutes par ligne,
# separateur virgule, valeurs en Wh, date suivie de l'heure et du fuseau.
RAPPORT_ENPHASE_15MIN = (
    "Date/Time,Energy Produced (Wh)\n"
    "2026-07-14 06:00:00 +0200,120\n"
    "2026-07-14 06:15:00 +0200,380\n"
    "2026-07-14 06:30:00 +0200,500\n"
    "2026-07-15 06:00:00 +0200,1000\n"
)


def test_parse_enphase_totalise_les_pas_de_15_min(tmp_path):
    p = tmp_path / "rapport.csv"
    p.write_text(RAPPORT_ENPHASE_15MIN, encoding="utf-8")
    # 120 + 380 + 500 = 1000 Wh -> 1 kWh ; arrondi au dixieme.
    assert dl.parse_enphase_fichier(str(p)) == {
        "Prod_Jour": {"14/07/2026": "1", "15/07/2026": "1"},
    }


def test_parse_enphase_arrondi_au_dixieme(tmp_path):
    p = tmp_path / "rapport.csv"
    p.write_text("Date/Time,Energy Produced (Wh)\n"
                 "2026-07-14 06:00:00 +0200,24599\n", encoding="utf-8")
    assert dl.parse_enphase_fichier(str(p)) == {
        "Prod_Jour": {"14/07/2026": "24,6"},
    }


def test_parse_enphase_quotidien_kwh_dates_fr(tmp_path):
    p = tmp_path / "rapport.csv"
    p.write_text("Date;Energie produite (en kWh)\n"
                 "14/07/2026 00:00;30,1\n"
                 "15/07/2026 00:00;22,4\n", encoding="utf-8")
    assert dl.parse_enphase_fichier(str(p)) == {
        "Prod_Jour": {"14/07/2026": "30,1", "15/07/2026": "22,4"},
    }


def test_parse_enphase_unite_devinee_sans_entete(tmp_path):
    # Pas d'unite dans l'entete : un total journalier de 30000 est en Wh.
    p = tmp_path / "rapport.csv"
    p.write_text("Date/Time,Energie\n"
                 "2026-07-14 06:00:00,30000\n"
                 "2026-07-15 06:00:00,22000\n", encoding="utf-8")
    assert dl.parse_enphase_fichier(str(p)) == {
        "Prod_Jour": {"14/07/2026": "30", "15/07/2026": "22"},
    }


def test_parse_enphase_zip(tmp_path):
    import zipfile

    p = tmp_path / "rapport.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("lisezmoi.txt", "")
        zf.writestr("2829824_energie.csv", RAPPORT_ENPHASE_15MIN)
    # Le premier fichier texte utile de l'archive est lu.
    assert "14/07/2026" in dl.parse_enphase_fichier(str(p))["Prod_Jour"]


def test_parse_enphase_fichier_non_reconnu(tmp_path):
    p = tmp_path / "autre.csv"
    p.write_text("Bonjour;ceci n'est pas un rapport\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Aucune ligne"):
        dl.parse_enphase_fichier(str(p))


def test_retirer_jour_en_cours():
    from datetime import date

    valeurs = {"25/07/2026": "20,8", "26/07/2026": "22,3", "27/07/2026": "0,2"}
    retire = dl.retirer_jour_en_cours(valeurs, aujourdhui=date(2026, 7, 27))
    assert retire == "27/07/2026"
    assert valeurs == {"25/07/2026": "20,8", "26/07/2026": "22,3"}


def test_retirer_jour_en_cours_absent():
    from datetime import date

    valeurs = {"25/07/2026": "20,8"}
    assert dl.retirer_jour_en_cours(valeurs, aujourdhui=date(2026, 7, 27)) is None
    assert valeurs == {"25/07/2026": "20,8"}


def test_merge_import_sans_doublon():
    rows = [_ligne("01/05/2026", "10,0")]  # jour existant, Prod=10,0
    lignes, nb_n, nb_r, nb_i = dl.merge_import(
        rows, "Inj_Jour", {"01/05/2026": "5,5", "02/05/2026": "6"})
    par_date = {r["Date"]: r for r in lignes}
    assert len(lignes) == 2                              # fusion, pas de doublon
    assert par_date["01/05/2026"]["Prod_Jour"] == "10,0"  # autre colonne intacte
    assert par_date["01/05/2026"]["Inj_Jour"] == "5,5"    # valeur remplacee
    assert par_date["02/05/2026"]["Inj_Jour"] == "6"      # nouveau jour
    assert (nb_n, nb_r, nb_i) == (1, 1, 0)


def test_merge_import_valeur_identique_comptee_inchangee():
    ligne = _ligne("01/05/2026")
    ligne["Inj_Jour"] = "5,5"
    lignes, nb_n, nb_r, nb_i = dl.merge_import(
        [ligne], "Inj_Jour", {"01/05/2026": "5,5"})
    assert len(lignes) == 1
    assert (nb_n, nb_r, nb_i) == (0, 0, 1)


# -----------------------------------------------------------------------------
# Detection du type d'export et controle de coherence
# -----------------------------------------------------------------------------

def test_type_ambigu_refuse(tmp_path):
    # Le classeur officiel s'appelle "Consommation-Production" : avant, le mot
    # "production" gagnait et une conso partait dans la colonne Injection.
    p = tmp_path / "export.csv"
    p.write_text(
        "Export energie Consommation-Production quotidienne\n"
        "Date;Valeur (en kWh)\n"
        "01/06/2026;12,5\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="ambigu"):
        dl.parse_enedis_csv(str(p))


def test_type_lu_dans_l_entete_pas_dans_les_donnees(tmp_path):
    # Le mot parasite est APRES les donnees : l'en-tete doit trancher seul.
    p = tmp_path / "export.csv"
    p.write_text(
        "Type de donnees;Consommation quotidienne\n"
        "Date;Valeur (en kWh)\n"
        "01/06/2026;12,5\n"
        "Note de bas de page : production non incluse\n",
        encoding="utf-8",
    )
    colonne, valeurs = dl.parse_enedis_csv(str(p))
    assert colonne == "Conso_réseau_Jour"
    assert valeurs == {"01/06/2026": "12,5"}


def _lignes_prod(prod: dict[str, str]) -> list[dict[str, str]]:
    lignes = []
    for date, val in prod.items():
        ligne = {c: "" for c in dl.RELEVES_HEADER}
        ligne["Date"] = date
        ligne["Prod_Jour"] = val
        lignes.append(ligne)
    return lignes


def test_controle_import_detecte_injection_superieure(tmp_path):
    # Une conso rangee par erreur en injection : sans rapport avec la prod.
    rows = _lignes_prod({"01/06/2026": "20,0", "02/06/2026": "18,0",
                         "03/06/2026": "22,0"})
    alerte = dl.controle_apres_import(rows, "Inj_Jour", {
        "01/06/2026": "45,0", "02/06/2026": "38,0", "03/06/2026": "51,0"})
    assert alerte is not None
    assert "impossible" in alerte.lower()


def test_controle_import_accepte_une_injection_normale():
    rows = _lignes_prod({"01/06/2026": "20,0", "02/06/2026": "18,0"})
    assert dl.controle_apres_import(rows, "Inj_Jour", {
        "01/06/2026": "14,0", "02/06/2026": "12,5"}) is None


def test_controle_import_tolere_un_jour_isole():
    # 1 anomalie sur 12 jours (8 %) : sous le seuil, pas d'alerte.
    prod = {f"{j:02d}/06/2026": "20,0" for j in range(1, 13)}
    valeurs = {f"{j:02d}/06/2026": "15,0" for j in range(1, 13)}
    valeurs["05/06/2026"] = "40,0"
    assert dl.controle_apres_import(_lignes_prod(prod), "Inj_Jour", valeurs) is None


def test_controle_import_ignore_la_consommation():
    # La conso n'a aucune raison d'etre inferieure a la production.
    rows = _lignes_prod({"01/06/2026": "20,0"})
    assert dl.controle_apres_import(
        rows, "Conso_réseau_Jour", {"01/06/2026": "60,0"}) is None


# -----------------------------------------------------------------------------
# Rotation des sauvegardes
# -----------------------------------------------------------------------------

def test_sauvegardes_horodatee_et_du_jour(csv_path):
    dl.write_releves_raw(csv_path, dl.read_releves_raw(csv_path))
    dossier = dl.dossier_sauvegardes(csv_path)
    noms = os.listdir(dossier)
    assert any(n.startswith("Releves-pv_jour_") for n in noms)
    assert any(n.startswith("Releves-pv_2") for n in noms)


def test_sauvegardes_rotation(csv_path, monkeypatch):
    # Au dela de MAX_SAUVEGARDES, seules les plus recentes sont gardees.
    monkeypatch.setattr(dl, "MAX_SAUVEGARDES", 3)
    rows = dl.read_releves_raw(csv_path)
    for i in range(6):
        rows[0]["Prod_Jour"] = f"{10 + i},0"
        dl.write_releves_raw(csv_path, rows)
    dossier = dl.dossier_sauvegardes(csv_path)
    horodatees = [n for n in os.listdir(dossier) if n.startswith("Releves-pv_2")]
    assert len(horodatees) <= 3


def test_sauvegarde_du_jour_epargnee_par_la_rotation(csv_path, monkeypatch):
    monkeypatch.setattr(dl, "MAX_SAUVEGARDES", 1)
    rows = dl.read_releves_raw(csv_path)
    for i in range(4):
        rows[0]["Prod_Jour"] = f"{10 + i},0"
        dl.write_releves_raw(csv_path, rows)
    dossier = dl.dossier_sauvegardes(csv_path)
    du_jour = [n for n in os.listdir(dossier) if n.startswith("Releves-pv_jour_")]
    assert len(du_jour) == 1  # toujours la, malgre la rotation a 1


def _verrouille_os_replace(monkeypatch):
    """Simule le CSV ouvert dans Excel : os.replace echoue sur un verrou."""
    def _verrou(*args, **kwargs):
        raise OSError("le fichier est utilise par un autre programme")
    monkeypatch.setattr(dl.os, "replace", _verrou)


def _archives(csv_path) -> list[str]:
    dossier = dl.dossier_sauvegardes(csv_path)
    if not os.path.exists(dossier):
        return []
    return sorted(os.listdir(dossier))


def test_l_archive_contient_la_version_d_avant(csv_path):
    # LE piege de cette correction : deplacer betement l'archivage apres
    # os.replace archiverait le NOUVEAU contenu, puisque `path` a deja ete
    # remplace a ce moment-la. L'archive doit porter la version d'avant.
    avant = open(csv_path, encoding="utf-8").read()
    rows = dl.read_releves_raw(csv_path)
    rows[0]["Prod_Jour"] = "21,5"
    dl.write_releves_raw(csv_path, rows)

    dossier = dl.dossier_sauvegardes(csv_path)
    horodatees = [n for n in os.listdir(dossier) if n.startswith("Releves-pv_2")]
    assert len(horodatees) == 1
    contenu = open(os.path.join(dossier, horodatees[0]), encoding="utf-8").read()
    assert contenu == avant

    # La sauvegarde du jour aussi.
    du_jour = [n for n in os.listdir(dossier) if n.startswith("Releves-pv_jour_")]
    assert open(os.path.join(dossier, du_jour[0]), encoding="utf-8").read() == avant


def test_echec_d_ecriture_ne_consomme_aucune_sauvegarde(csv_path, monkeypatch):
    # shutil.copy2 vers .bak et archiver_sauvegarde etaient appeles AVANT
    # os.replace, sans condition : la copie avait deja eu lieu quand
    # l'ecriture echouait.
    _verrouille_os_replace(monkeypatch)
    rows = dl.read_releves_raw(csv_path)
    rows[0]["Prod_Jour"] = "21,5"

    with pytest.raises(OSError):
        dl.write_releves_raw(csv_path, rows)

    assert not os.path.exists(csv_path + ".bak")   # aucun .bak consomme
    assert _archives(csv_path) == []               # aucune archive creee


def test_echec_d_ecriture_ne_laisse_pas_de_fichier_temporaire(csv_path,
                                                              monkeypatch):
    _verrouille_os_replace(monkeypatch)
    rows = dl.read_releves_raw(csv_path)
    with pytest.raises(OSError):
        dl.write_releves_raw(csv_path, rows)

    restants = [n for n in os.listdir(os.path.dirname(csv_path))
                if n.endswith(".tmp")]
    assert restants == []


def test_echec_d_ecriture_laisse_le_csv_intact(csv_path, monkeypatch):
    avant = open(csv_path, encoding="utf-8").read()
    _verrouille_os_replace(monkeypatch)
    rows = dl.read_releves_raw(csv_path)
    rows[0]["Prod_Jour"] = "21,5"
    with pytest.raises(OSError):
        dl.write_releves_raw(csv_path, rows)
    assert open(csv_path, encoding="utf-8").read() == avant


def test_echecs_repetes_ne_purgent_pas_l_historique(csv_path, monkeypatch):
    # Quinze tentatives ratees remplacaient tout l'historique fin par quinze
    # copies identiques du fichier courant.
    monkeypatch.setattr(dl, "MAX_SAUVEGARDES", 3)
    rows = dl.read_releves_raw(csv_path)
    for i in range(3):
        rows[0]["Prod_Jour"] = f"{10 + i},0"
        dl.write_releves_raw(csv_path, rows)

    dossier = dl.dossier_sauvegardes(csv_path)
    avant = _archives(csv_path)
    contenus_avant = [
        open(os.path.join(dossier, n), encoding="utf-8").read() for n in avant
    ]

    _verrouille_os_replace(monkeypatch)
    for _ in range(10):
        with pytest.raises(OSError):
            dl.write_releves_raw(csv_path, rows)

    assert _archives(csv_path) == avant          # ni ajout ni rotation
    assert [
        open(os.path.join(dossier, n), encoding="utf-8").read() for n in avant
    ] == contenus_avant                          # contenus inchanges


def test_sauvegarde_n_empeche_pas_l_ecriture(csv_path, monkeypatch):
    # Un echec d'archivage ne doit jamais bloquer l'enregistrement.
    def _casse(*a, **k):
        raise OSError("disque plein")
    monkeypatch.setattr(dl.os, "makedirs", _casse)
    rows = dl.read_releves_raw(csv_path)
    rows[0]["Prod_Jour"] = "99,9"
    dl.write_releves_raw(csv_path, rows)
    assert dl.read_releves_raw(csv_path)[0]["Prod_Jour"] == "99,9"


# -----------------------------------------------------------------------------
# charger_recharges_ve (fichier de l'application recharges-ve)
# -----------------------------------------------------------------------------

def _ecrire_recharges(tmp_path, recharges) -> str:
    import json
    p = tmp_path / "recharges.json"
    p.write_text(json.dumps({"recharges": recharges}), encoding="utf-8")
    return str(p)


def test_recharges_ve_ignore_l_exterieur(tmp_path):
    # Seules les recharges "maison" passent par le compteur de la maison.
    chemin = _ecrire_recharges(tmp_path, [
        {"lieu": "maison", "kwh": 10.0,
         "date": "2026-05-01T10:00", "fin": "2026-05-01T12:00"},
        {"lieu": "exterieur", "kwh": 40.0,
         "date": "2026-05-01T14:00", "fin": "2026-05-01T15:00"},
    ])
    df_ve = dl.charger_recharges_ve(chemin)
    assert df_ve['recharge_ve_kwh'].loc[pd.Timestamp("2026-05-01")] == pytest.approx(10.0)
    assert df_ve['recharge_ve_kwh'].sum() == pytest.approx(10.0)


def test_recharges_ve_repartit_sur_deux_jours(tmp_path):
    # Charge de nuit 22:00 -> 02:00 : 4 h dont 2 h la veille -> 50 / 50.
    chemin = _ecrire_recharges(tmp_path, [
        {"lieu": "maison", "kwh": 20.0,
         "date": "2026-05-01T22:00", "fin": "2026-05-02T02:00"},
    ])
    df_ve = dl.charger_recharges_ve(chemin)
    assert df_ve['recharge_ve_kwh'].loc[pd.Timestamp("2026-05-01")] == pytest.approx(10.0)
    assert df_ve['recharge_ve_kwh'].loc[pd.Timestamp("2026-05-02")] == pytest.approx(10.0)
    assert df_ve['recharge_ve_kwh'].sum() == pytest.approx(20.0)  # rien ne se perd


def test_recharges_ve_duree_nulle(tmp_path):
    # Debut == fin : tout sur le jour de debut, pas de division par zero.
    chemin = _ecrire_recharges(tmp_path, [
        {"lieu": "maison", "kwh": 5.0,
         "date": "2026-05-01T10:00", "fin": "2026-05-01T10:00"},
    ])
    df_ve = dl.charger_recharges_ve(chemin)
    assert df_ve['recharge_ve_kwh'].loc[pd.Timestamp("2026-05-01")] == pytest.approx(5.0)


def test_recharges_ve_ligne_incomplete_ignoree(tmp_path):
    chemin = _ecrire_recharges(tmp_path, [
        {"lieu": "maison", "kwh": 8.0,
         "date": "2026-05-01T10:00", "fin": "2026-05-01T12:00"},
        {"lieu": "maison", "kwh": 3.0, "date": "2026-05-02T10:00"},  # pas de fin
    ])
    df_ve = dl.charger_recharges_ve(chemin)
    assert df_ve['recharge_ve_kwh'].sum() == pytest.approx(8.0)


def test_recharges_ve_cout_reparti_comme_l_energie(tmp_path):
    # Le cout vient du fichier (vraies plages horaires) : le calculer au
    # prorata du cout reseau moyen le surestimerait, ces charges tombant
    # presque toutes en heures creuses.
    chemin = _ecrire_recharges(tmp_path, [
        {"lieu": "maison", "kwh": 20.0, "cout_eur": 2.50,
         "date": "2026-05-01T22:00", "fin": "2026-05-02T02:00"},
    ])
    df_ve = dl.charger_recharges_ve(chemin)
    assert df_ve["recharge_ve_eur"].sum() == pytest.approx(2.50)
    assert df_ve["recharge_ve_eur"].loc[pd.Timestamp("2026-05-01")] == pytest.approx(1.25)


def test_recharges_ve_sans_cout(tmp_path):
    # Champ cout_eur absent : energie comptee quand meme, cout a zero.
    chemin = _ecrire_recharges(tmp_path, [
        {"lieu": "maison", "kwh": 10.0,
         "date": "2026-05-01T10:00", "fin": "2026-05-01T12:00"},
    ])
    df_ve = dl.charger_recharges_ve(chemin)
    assert df_ve["recharge_ve_kwh"].sum() == pytest.approx(10.0)
    assert df_ve["recharge_ve_eur"].sum() == pytest.approx(0.0)


def test_recharges_ve_fichier_absent(tmp_path):
    # L'app doit demarrer meme sans le fichier de l'autre projet.
    s = dl.charger_recharges_ve(str(tmp_path / "nexiste_pas.json"))
    assert s.empty


def test_recharges_ve_fichier_illisible(tmp_path):
    p = tmp_path / "casse.json"
    p.write_text("{ceci n'est pas du json", encoding="utf-8")
    assert dl.charger_recharges_ve(str(p)).empty


# -----------------------------------------------------------------------------
# Validation de la saisie (normalise_date_saisie / normalise_nombre_saisie)
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("texte, attendu", [
    ("30/07/2026", "30/07/2026"),
    ("1/1/2026", "01/01/2026"),      # tolerance sur les zeros
    ("2026-07-30", "30/07/2026"),    # forme ISO acceptee
    ("  30/07/2026  ", "30/07/2026"),
])
def test_normalise_date_saisie_valide(texte, attendu):
    assert dl.normalise_date_saisie(texte) == attendu


@pytest.mark.parametrize("texte", [
    "2026",        # annee seule : pandas en faisait le 01/01/2026
    "01/2026",     # mois/annee : idem
    "30/07/26",    # annee sur 2 chiffres : ambigu
    "31/02/2026",  # date inexistante
    "abc",
    "",
    "   ",
])
def test_normalise_date_saisie_refusee(texte):
    # Ces frappes ecrasaient silencieusement un releve existant.
    with pytest.raises(ValueError):
        dl.normalise_date_saisie(texte)


@pytest.mark.parametrize("texte, attendu", [
    ("24,8", "24,8"),
    ("24.8", "24,8"),   # point converti en virgule
    ("0", "0"),
    ("", ""),           # case vide autorisee
    ("   ", ""),
])
def test_normalise_nombre_saisie_valide(texte, attendu):
    assert dl.normalise_nombre_saisie(texte) == attendu


@pytest.mark.parametrize("texte", ["-5", "abc", "inf", "nan", "12,5,3"])
def test_normalise_nombre_saisie_refusee(texte):
    # float() acceptait -5, inf et nan : les NaN contaminaient tous les totaux.
    with pytest.raises(ValueError):
        dl.normalise_nombre_saisie(texte)


def test_normalise_nombre_saisie_message_nomme_la_colonne():
    with pytest.raises(ValueError, match="Production"):
        dl.normalise_nombre_saisie("abc", "Production")


# Une valeur tapee avec un espace passait la validation, puis etait ecrite
# telle quelle dans le CSV : plus rien ne savait la relire ensuite et la
# journee valait 0 kWh. Pire qu'une case vide, qui elle est signalee.
@pytest.mark.parametrize("texte, attendu", [
    ("22, 1", 22.1),               # espace apres la virgule
    ("2 5", 25.0),                 # espace au milieu des chiffres
    ("1 000,5", 1000.5),           # espace separateur de milliers
    ("1\u00a0000,5", 1000.5),      # idem avec un espace insecable
])
def test_normalise_nombre_saisie_espaces_relisibles(texte, attendu):
    # Plafond releve : ce test porte sur les espaces, pas sur la plausibilite.
    normalise = dl.normalise_nombre_saisie(texte, plafond=2000.0)
    # 1. le parseur interne doit retrouver le nombre...
    assert dl._parse_nombre(normalise) == attendu
    # 2. ...et pandas aussi, puisque c'est lui qui alimente les calculs.
    relu = pd.to_numeric(
        pd.Series([normalise]).str.strip().str.replace(",", ".", regex=False),
        errors="coerce",
    )
    assert relu.iloc[0] == attendu


# Bornes de plausibilite : une date dans le futur ou un ordre de grandeur
# impossible sont des fautes de frappe, pas des releves.

def test_normalise_date_saisie_refuse_le_futur():
    # 17/08/2062 tape au lieu de 17/08/2026 : le resample("D") comblait
    # ensuite le fichier jusqu'en 2062 et la production moyenne s'effondrait.
    with pytest.raises(ValueError) as exc:
        dl.normalise_date_saisie("17/08/2062", aujourdhui=_date(2026, 8, 18))
    message = str(exc.value)
    assert "17/08/2062" in message   # la date tapee
    assert "18/08/2026" in message   # la date du jour


def test_normalise_date_saisie_refuse_demain():
    with pytest.raises(ValueError):
        dl.normalise_date_saisie("19/08/2026", aujourdhui=_date(2026, 8, 18))


@pytest.mark.parametrize("texte", ["18/08/2026", "29/04/2022"])
def test_normalise_date_saisie_accepte_aujourdhui_et_le_passe(texte):
    assert dl.normalise_date_saisie(texte, aujourdhui=_date(2026, 8, 18)) == texte


def test_normalise_nombre_saisie_refuse_au_dela_du_plafond():
    # 251 tape au lieu de 25,1 : la virgule oubliee.
    with pytest.raises(ValueError) as exc:
        dl.normalise_nombre_saisie("251", "Production")
    assert "251" in str(exc.value)
    assert "Production" in str(exc.value)


# Les maxima reellement presents dans le fichier apres 4 ans de releves.
# Le plafond ne doit JAMAIS refuser une valeur deja enregistree, sinon la
# vue Saisie devient impossible a enregistrer des qu'elle en affiche une.
@pytest.mark.parametrize("colonne, valeur", [
    ("Prod_Jour", "40,204"),          # 01/07/2022
    ("Inj_Jour", "35,408"),           # 02/07/2022
    ("Conso_réseau_Jour", "80"),      # 22/01/2025, journee d'hiver
    ("Conso_HC", "50,22"),            # 09/01/2026
    ("Conso_HP", "19,74"),            # 02/01/2026
])
def test_plafonds_acceptent_les_maxima_reels(colonne, valeur):
    assert dl.normalise_nombre_saisie(
        valeur, colonne, dl.plafond_colonne(colonne)) == valeur


def test_plafond_production_plus_strict_que_la_consommation():
    # 6 kWc : 100 kWh produits dans la journee sont impossibles. 100 kWh
    # soutires un jour d'hiver avec recharge du vehicule ne le sont pas.
    with pytest.raises(ValueError):
        dl.normalise_nombre_saisie("100", "Production",
                                   dl.plafond_colonne("Prod_Jour"))
    assert dl.normalise_nombre_saisie(
        "100", "Conso reseau", dl.plafond_colonne("Conso_réseau_Jour")) == "100"


def test_plafond_colonne_couvre_toutes_les_colonnes():
    # Une colonne oubliee dans la table donnerait un plafond au hasard.
    for colonne in dl.RELEVES_HEADER[1:]:
        assert dl.plafond_colonne(colonne) > 0


def test_normalise_puis_ecriture_puis_relecture(tmp_path):
    """Aller-retour complet : ce qui est tape doit arriver intact aux calculs."""
    p = str(tmp_path / "Releves-pv.csv")
    ligne = {c: "" for c in dl.RELEVES_HEADER}
    ligne["Date"] = "01/05/2026"
    ligne["Prod_Jour"] = dl.normalise_nombre_saisie("22, 1")
    dl.write_releves_raw(p, [ligne])

    production, _ = dl.load_releves_pv(p)
    assert production["production_kwh"].iloc[0] == pytest.approx(22.1)


# ---------------------------------------------------------------------------
# B5 : une date illisible fait disparaitre la journee de tous les calculs
# (to_datetime errors="coerce" puis dropna), alors qu'elle reste visible
# dans l'onglet Saisie. L'ecart devient incomprehensible.
# ---------------------------------------------------------------------------

def test_dates_illisibles_sont_comptees(tmp_path):
    p = tmp_path / "r.csv"
    p.write_text(
        "Date;Prod_Jour;Inj_Jour;Conso_réseau_Jour;Conso_HC;Conso_HP\n"
        "01/05/2026;20,5;;;;\n"
        "32/13/2026;18,0;;;;\n"      # date inexistante
        "le 3 mai;19,0;;;;\n"        # texte
        "03/05/2026;21,0;;;;\n",
        encoding="utf-8",
    )
    assert dl.dates_illisibles(str(p)) == ["32/13/2026", "le 3 mai"]


def test_dates_illisibles_fichier_sain(csv_path):
    assert dl.dates_illisibles(csv_path) == []


def test_dates_illisibles_fichier_absent(tmp_path):
    assert dl.dates_illisibles(str(tmp_path / "absent.csv")) == []


def test_la_journee_illisible_disparait_bien_des_calculs(tmp_path):
    # On verifie que le comptage decrit une perte REELLE, et pas une
    # inquietude theorique.
    p = tmp_path / "r.csv"
    p.write_text(
        "Date;Prod_Jour;Inj_Jour;Conso_réseau_Jour;Conso_HC;Conso_HP\n"
        "01/05/2026;20,5;;;;\n"
        "32/13/2026;18,0;;;;\n",
        encoding="utf-8",
    )
    production, _ = dl.load_releves_pv(str(p))
    assert len(production) == 1                       # la journee a disparu
    assert len(dl.dates_illisibles(str(p))) == 1      # et on sait le dire


# -----------------------------------------------------------------------------
# load_releves_pv (pipeline de calcul)
# -----------------------------------------------------------------------------

def test_load_pv_conversion_numerique(csv_path):
    production, reseau = dl.load_releves_pv(csv_path)
    jour1 = pd.Timestamp("2026-05-01")
    assert production.loc[jour1, "production_kwh"] == pytest.approx(20.5)
    assert reseau.loc[jour1, "injection_kwh"] == pytest.approx(15.2)
    assert reseau.loc[jour1, "soutirage_kwh"] == pytest.approx(3.1)


def test_load_pv_soutirage_fallback_hphc(csv_path):
    # 02/05 : pas de soutirage direct -> somme HC + HP (1,5 + 1,6).
    _, reseau = dl.load_releves_pv(csv_path)
    assert reseau.loc[pd.Timestamp("2026-05-02"), "soutirage_kwh"] == pytest.approx(3.1)


def test_load_pv_expose_detail_hphc(csv_path):
    _, reseau = dl.load_releves_pv(csv_path)
    assert "soutirage_hp_kwh" in reseau.columns
    assert reseau.loc[pd.Timestamp("2026-05-02"), "soutirage_hc_kwh"] == pytest.approx(1.5)


def test_load_pv_marque_conso_absente(tmp_path):
    # Aucun releve de conso (ni total, ni HC/HP) -> conso_absente = 1.0.
    # Sans ce marqueur, le jour passerait pour une conso reelle de 0 kWh.
    p = tmp_path / "r.csv"
    p.write_text(
        "Date;Prod_Jour;Inj_Jour;Conso_réseau_Jour;Conso_HC;Conso_HP\n"
        "01/05/2026;10,0;5,0;;;\n"          # rien -> absente
        "02/05/2026;12,0;5,0;2,0;;\n"       # total direct -> presente
        "03/05/2026;12,0;5,0;;1,0;1,5\n",   # HC+HP seuls -> presente
        encoding="utf-8",
    )
    _, reseau = dl.load_releves_pv(str(p))
    assert reseau.loc[pd.Timestamp("2026-05-01"), "conso_absente"] == 1.0
    assert reseau.loc[pd.Timestamp("2026-05-02"), "conso_absente"] == 0.0
    assert reseau.loc[pd.Timestamp("2026-05-03"), "conso_absente"] == 0.0


def test_load_pv_marque_jours_incomplets(tmp_path):
    # Production saisie mais injection vide -> releve_incomplet = 1.0
    # (l'autoconso vaudra toute la production, a signaler comme estimation).
    p = tmp_path / "r.csv"
    p.write_text(
        "Date;Prod_Jour;Inj_Jour;Conso_réseau_Jour;Conso_HC;Conso_HP\n"
        "01/05/2026;10,0;;2,0;;\n"
        "02/05/2026;12,0;5,0;2,0;;\n",
        encoding="utf-8",
    )
    _, reseau = dl.load_releves_pv(str(p))
    assert reseau.loc[pd.Timestamp("2026-05-01"), "releve_incomplet"] == 1.0
    assert reseau.loc[pd.Timestamp("2026-05-02"), "releve_incomplet"] == 0.0


def test_load_pv_doublons_garde_le_dernier(tmp_path):
    p = tmp_path / "r.csv"
    p.write_text(
        "Date;Prod_Jour;Inj_Jour;Conso_réseau_Jour;Conso_HC;Conso_HP\n"
        "01/05/2026;10,0;;;;\n"
        "01/05/2026;11,0;;;;\n",
        encoding="utf-8",
    )
    production, _ = dl.load_releves_pv(str(p))
    assert len(production) == 1
    assert production["production_kwh"].iloc[0] == pytest.approx(11.0)


def test_load_pv_encodage_cp1252(tmp_path):
    # CSV sauve par Excel FR en ANSI : l'accent de Conso_réseau_Jour est
    # encode en cp1252 -> le fallback d'encodage doit le lire sans erreur.
    p = tmp_path / "r.csv"
    contenu = (
        "Date;Prod_Jour;Inj_Jour;Conso_réseau_Jour;Conso_HC;Conso_HP\n"
        "01/05/2026;10,0;5,0;2,0;;\n"
    )
    p.write_bytes(contenu.encode("cp1252"))
    production, reseau = dl.load_releves_pv(str(p))
    assert production["production_kwh"].iloc[0] == pytest.approx(10.0)
    assert reseau["soutirage_kwh"].iloc[0] == pytest.approx(2.0)


def test_load_pv_colonnes_manquantes(tmp_path):
    p = tmp_path / "r.csv"
    p.write_text("Foo;Bar\n1;2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="non reconnu"):
        dl.load_releves_pv(str(p))
