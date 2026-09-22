"""Tests de la vue Saisie : c'est elle qui declenche l'ecriture du CSV.

Les vues ne sont pas testees ailleurs, mais _enregistrer est le seul chemin
par lequel un clic de l'utilisateur peut effacer des annees de releves : il
merite ses propres garde-fous.
"""
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

import data_loaders as dl

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QLabel,
    QMessageBox,
)

import gui_theme  # noqa: E402
import views.saisie as saisie_module  # noqa: E402
from views.saisie import SaisieView  # noqa: E402

CSV_DEPART = (
    "Date;Prod_Jour;Inj_Jour;Conso_réseau_Jour;Conso_HC;Conso_HP\n"
    "01/05/2026;20,5;15,2;3,1;1,0;2,1\n"
    "02/05/2026;18;12;2;1,5;1,6\n"
    "03/05/2026;19;13;2,5;1,2;1,3\n"
)


@pytest.fixture(scope="session")
def qapp():
    """Une seule QApplication pour toute la session (Qt l'exige)."""
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def vue(qapp, tmp_path):
    """Vue Saisie branchee sur un CSV jetable."""
    csv = tmp_path / "Releves-pv.csv"
    csv.write_text(CSV_DEPART, encoding="utf-8")
    # La vue ne lit que releves_path et current_period dans son conteneur de
    # donnees : inutile de reconstruire tout le pipeline de calcul.
    # puissance_kwc : le plafond de saisie s'y adapte (10 kWh par kWc).
    # 6 kWc reproduit le plafond historique de 60 kWh.
    data = SimpleNamespace(releves_path=str(csv), current_period="all",
                           puissance_kwc=6.0)
    v = SaisieView(data, gui_theme.LIGHT)
    v.populate("all")
    return v


def _cellule(vue, ligne: int, colonne: str, texte: str) -> None:
    """Ecrit dans une cellule du tableau comme le ferait l'utilisateur."""
    vue.table.item(ligne, vue.COLS.index(colonne)).setText(texte)


def _dates_du_fichier(vue) -> list[str]:
    return [r["Date"] for r in dl.read_releves_raw(vue.data.releves_path)]


# ---------------------------------------------------------------------------
# A2 : la ligne neuve est pre-remplie avec le lendemain du dernier releve.
# Cette date est souvent dans le futur ; refuser les dates futures ne doit
# pas rendre l'enregistrement impossible pour autant.
# ---------------------------------------------------------------------------

def test_ligne_neuve_datee_dans_le_futur_ne_bloque_pas(vue):
    # La ligne 0 est la ligne neuve, pre-remplie au 04/05/2026 et vide.
    _cellule(vue, 0, "Date", "31/12/2099")
    # L'utilisateur corrige une journee existante plus bas dans le tableau.
    _cellule(vue, 1, "Prod_Jour", "21,5")

    vue._enregistrer()

    lignes = {r["Date"]: r for r in dl.read_releves_raw(vue.data.releves_path)}
    assert "31/12/2099" not in lignes          # la ligne vide est ignoree
    assert lignes["03/05/2026"]["Prod_Jour"] == "21,5"   # la correction passe


def test_ligne_neuve_datee_dans_le_futur_avec_valeur_est_refusee(vue):
    # Meme ligne, mais cette fois l'utilisateur y tape une production :
    # c'est la faute de frappe sur l'annee, elle doit etre refusee.
    _cellule(vue, 0, "Date", "31/12/2099")
    _cellule(vue, 0, "Prod_Jour", "22,1")

    vue._enregistrer()

    assert _dates_du_fichier(vue) == ["01/05/2026", "02/05/2026", "03/05/2026"]
    assert "futur" in vue.status_label.text()


def test_valeur_hors_plafond_refusee_avec_le_bon_plafond_par_colonne(vue):
    # 251 au lieu de 25,1 en production : refuse.
    _cellule(vue, 1, "Prod_Jour", "251")
    vue._enregistrer()
    assert dl.read_releves_raw(vue.data.releves_path)[2]["Prod_Jour"] == "19"
    assert "depasse" in vue.status_label.text()


def test_conso_hivernale_elevee_reste_acceptee(vue):
    # 80 kWh soutires : impossible en production, banal en consommation.
    _cellule(vue, 1, "Conso_réseau_Jour", "80")
    vue._enregistrer()
    assert dl.read_releves_raw(vue.data.releves_path)[2]["Conso_réseau_Jour"] == "80"


# ---------------------------------------------------------------------------
# A4 : une lecture partielle ne doit pas devenir une suppression definitive.
# ---------------------------------------------------------------------------

class _FauxQMessageBox:
    """Remplace la vraie boite de dialogue : repond sans attendre de clic.

    On garde les constantes de PySide6 pour que le code teste continue de
    faire ses comparaisons habituelles.
    """

    Yes = QMessageBox.Yes
    No = QMessageBox.No

    reponse = QMessageBox.No
    messages: list[str] = []        # les question() : demandes de confirmation
    defauts: list[object] = []      # leur bouton par defaut
    avertissements: list[str] = []  # les warning()
    critiques: list[str] = []       # les critical()

    @staticmethod
    def question(parent, titre, message, boutons=None, defaut=None):
        _FauxQMessageBox.messages.append(message)
        _FauxQMessageBox.defauts.append(defaut)
        return _FauxQMessageBox.reponse

    @staticmethod
    def warning(parent, titre, message):
        _FauxQMessageBox.avertissements.append(message)

    @staticmethod
    def critical(parent, titre, message):
        _FauxQMessageBox.critiques.append(message)


@pytest.fixture
def dialogue(monkeypatch):
    """Intercepte les boites de dialogue de la vue Saisie."""
    _FauxQMessageBox.messages = []
    _FauxQMessageBox.defauts = []
    _FauxQMessageBox.avertissements = []
    _FauxQMessageBox.critiques = []
    _FauxQMessageBox.reponse = QMessageBox.No
    monkeypatch.setattr(saisie_module, "QMessageBox", _FauxQMessageBox)
    return _FauxQMessageBox


def _cache_partiel(vue) -> None:
    """La vue n'a lu qu'une journee sur trois, le disque en a bien trois."""
    vue.toutes_lignes = vue.toutes_lignes[:1]
    vue._remplir_tableau()


def test_enregistrer_demande_avant_de_perdre_un_cache_partiel(vue, dialogue):
    avant = open(vue.data.releves_path, encoding="utf-8").read()
    _cache_partiel(vue)

    dialogue.reponse = dialogue.No
    vue._enregistrer()

    assert dialogue.messages, "aucune confirmation demandee"
    assert open(vue.data.releves_path, encoding="utf-8").read() == avant


def test_le_dialogue_nomme_precisement_ce_qui_disparait(vue, dialogue):
    _cache_partiel(vue)
    vue._enregistrer()

    message = dialogue.messages[0]
    assert "2 ligne(s)" in message
    assert "Conso_réseau_Jour" in message
    # Le bouton par defaut doit etre Non : un Entree machinal ne detruit rien.
    assert dialogue.defauts[0] == QMessageBox.No


def test_cache_partiel_confirme_explicitement_est_ecrit(vue, dialogue):
    # Si l'utilisateur confirme malgre tout, l'ecriture doit aboutir : c'est
    # le meme chemin que l'effacement volontaire.
    _cache_partiel(vue)
    dialogue.reponse = dialogue.Yes
    vue._enregistrer()

    assert [r["Date"] for r in dl.read_releves_raw(vue.data.releves_path)] == [
        "01/05/2026"]


# ---------------------------------------------------------------------------
# L'effacement volontaire d'une journee est le cas d'usage legitime de la
# reduction : il doit continuer de fonctionner exactement comme avant.
# ---------------------------------------------------------------------------

def _vider_la_ligne(vue, ligne: int) -> None:
    for col in vue.COLS[1:]:
        _cellule(vue, ligne, col, "")


def test_effacement_volontaire_confirme(vue, dialogue):
    _vider_la_ligne(vue, 1)          # ligne 1 = 03/05/2026 (plus recent en haut)
    dialogue.reponse = dialogue.Yes
    vue._enregistrer()

    assert _dates_du_fichier(vue) == ["01/05/2026", "02/05/2026"]
    assert "03/05/2026" in dialogue.messages[0]   # la date effacee est nommee


def test_effacement_volontaire_refuse_ne_touche_a_rien(vue, dialogue):
    avant = open(vue.data.releves_path, encoding="utf-8").read()
    _vider_la_ligne(vue, 1)
    dialogue.reponse = dialogue.No
    vue._enregistrer()

    assert open(vue.data.releves_path, encoding="utf-8").read() == avant
    assert "annule" in vue.status_label.text().lower()


def test_ajout_normal_ne_demande_rien(vue, dialogue):
    # Une saisie ordinaire ne doit jamais faire apparaitre de dialogue.
    _cellule(vue, 0, "Date", "04/05/2026")
    _cellule(vue, 0, "Prod_Jour", "21,5")
    vue._enregistrer()

    assert dialogue.messages == []
    assert _dates_du_fichier(vue) == [
        "01/05/2026", "02/05/2026", "03/05/2026", "04/05/2026"]


# ---------------------------------------------------------------------------
# A5 : un echec d'ecriture doit se voir. Le message partait dans le petit
# libelle a cote du bouton, ou il pouvait passer inapercu -- alors que la
# saisie n'etait PAS enregistree.
# ---------------------------------------------------------------------------

def test_echec_d_ecriture_affiche_une_boite_de_dialogue(vue, dialogue,
                                                        monkeypatch):
    def _verrou(*args, **kwargs):
        raise OSError("le fichier est utilise par un autre programme")
    monkeypatch.setattr(dl.os, "replace", _verrou)

    _cellule(vue, 0, "Date", "04/05/2026")
    _cellule(vue, 0, "Prod_Jour", "21,5")
    vue._enregistrer()

    assert dialogue.critiques, "l'echec doit etre signale par une boite"
    assert "utilise par un autre programme" in dialogue.critiques[0]
    assert "PAS été enregistrés" in dialogue.critiques[0]


def test_echec_d_ecriture_conserve_la_saisie_dans_le_tableau(vue, dialogue,
                                                             monkeypatch):
    # La saisie doit rester a l'ecran pour pouvoir reessayer apres avoir
    # ferme Excel.
    def _verrou(*args, **kwargs):
        raise OSError("verrou")
    monkeypatch.setattr(dl.os, "replace", _verrou)

    _cellule(vue, 0, "Date", "04/05/2026")
    _cellule(vue, 0, "Prod_Jour", "21,5")
    vue._enregistrer()

    assert vue.table.item(0, vue.COLS.index("Prod_Jour")).text() == "21,5"
    assert _dates_du_fichier(vue) == ["01/05/2026", "02/05/2026", "03/05/2026"]


# ---------------------------------------------------------------------------
# B2 : concurrence. Appli ouverte + correction dans Excel = correction
# ecrasee, en silence des deux cotes.
# ---------------------------------------------------------------------------

def _corriger_le_fichier_dans_le_dos(vue) -> None:
    """Quelqu'un d'autre (Excel, une synchro) a corrige une valeur du CSV.

    On corrige une valeur EXISTANTE, sans ajouter ni retirer de ligne : la
    volumetrie est donc identique et le controle de A4 ne peut rien voir.
    Seule la date de modification du fichier trahit le changement.
    """
    path = vue.data.releves_path
    contenu = open(path, encoding="utf-8").read()
    contenu = contenu.replace("01/05/2026;20,5;", "01/05/2026;21,9;")
    open(path, "w", encoding="utf-8").write(contenu)
    # mtime force : sur un disque rapide, deux ecritures rapprochees peuvent
    # porter la meme date et le test ne prouverait plus rien.
    stat = os.stat(path)
    os.utime(path, (stat.st_atime, stat.st_mtime + 10))


def test_enregistrer_refuse_si_le_fichier_a_change_entre_temps(vue, dialogue):
    _cellule(vue, 0, "Date", "05/05/2026")
    _cellule(vue, 0, "Prod_Jour", "21,5")
    _corriger_le_fichier_dans_le_dos(vue)

    vue._enregistrer()

    lignes = {r["Date"]: r for r in dl.read_releves_raw(vue.data.releves_path)}
    # La correction faite en dehors de l'appli est toujours la...
    assert lignes["01/05/2026"]["Prod_Jour"] == "21,9"
    # ...et la saisie de la vue n'a pas ete ecrite par-dessus.
    assert "05/05/2026" not in lignes
    # C'est bien le controle de concurrence qui a parle, et pas celui de A4 :
    # la volumetrie etait identique, aucune confirmation n'a ete demandee.
    assert dialogue.messages == []
    assert dialogue.avertissements, "l'utilisateur doit etre prevenu"
    assert "Recharger" in dialogue.avertissements[0]


def test_enregistrer_normal_apres_relecture(vue, dialogue):
    # Apres un Recharger, l'enregistrement doit repartir normalement.
    _corriger_le_fichier_dans_le_dos(vue)
    vue._cache_mtime = None
    vue.refresh("all")

    _cellule(vue, 0, "Date", "05/05/2026")
    _cellule(vue, 0, "Prod_Jour", "21,5")
    vue._enregistrer()

    assert "05/05/2026" in _dates_du_fichier(vue)


# ---------------------------------------------------------------------------
# B3 : deux lignes de meme date dans le tableau. La boucle de collecte
# ecrasait sans controle, et comme la ligne neuve est en position 0, c'est
# l'ANCIENNE valeur qui gagnait -- avec un "OK : 0 ajout(s), 0 modif(s)"
# rassurant.
# ---------------------------------------------------------------------------

def test_deux_lignes_de_meme_date_sont_refusees(vue, dialogue):
    _cellule(vue, 0, "Date", "03/05/2026")   # date deja presente plus bas
    _cellule(vue, 0, "Prod_Jour", "21,5")

    vue._enregistrer()

    # Rien n'a ete enregistre...
    assert dl.read_releves_raw(vue.data.releves_path)[2]["Prod_Jour"] == "19"
    # ...et la date fautive est nommee, pas un vague "0 modif".
    assert "03/05/2026" in vue.status_label.text()


def test_le_message_de_doublon_ne_ment_pas_sur_le_resultat(vue, dialogue):
    _cellule(vue, 0, "Date", "03/05/2026")
    _cellule(vue, 0, "Prod_Jour", "21,5")
    vue._enregistrer()
    assert "OK" not in vue.status_label.text()


def test_ligne_ajoutee_a_la_main_avec_une_date_libre_passe(vue, dialogue):
    # Le cas normal du bouton "+ Ajouter une ligne" ne doit pas etre gene.
    vue._ajouter_ligne_vide()
    _cellule(vue, 0, "Date", "06/05/2026")
    _cellule(vue, 0, "Prod_Jour", "21,5")
    vue._enregistrer()

    assert "06/05/2026" in _dates_du_fichier(vue)


# ---------------------------------------------------------------------------
# B5 : la vue Saisie est le seul endroit ou une date illisible reste visible,
# donc le seul endroit ou on peut la corriger. C'est la qu'il faut le dire.
# ---------------------------------------------------------------------------

def _textes_affiches(vue) -> str:
    return " ".join(w.text() for w in vue.findChildren(QLabel))


def test_la_vue_saisie_signale_une_date_illisible(qapp, tmp_path):
    csv = tmp_path / "Releves-pv.csv"
    csv.write_text(CSV_DEPART.replace("02/05/2026", "32/13/2026"),
                   encoding="utf-8")
    # puissance_kwc : le plafond de saisie s'y adapte (10 kWh par kWc).
    # 6 kWc reproduit le plafond historique de 60 kWh.
    data = SimpleNamespace(releves_path=str(csv), current_period="all",
                           puissance_kwc=6.0)
    v = SaisieView(data, gui_theme.LIGHT)
    v.populate("all")

    affiche = _textes_affiches(v)
    assert "32/13/2026" in affiche
    assert "illisible" in affiche.lower()


def test_la_vue_saisie_ne_dit_rien_quand_tout_va_bien(vue):
    affiche = _textes_affiches(vue)
    assert "illisible" not in affiche.lower()


# ---------------------------------------------------------------------------
# Regression : apres un enregistrement, la vue doit montrer ce qui vient
# d'etre ecrit. Les tests precedents ne branchaient pas reload_callback,
# c'est pourquoi ils n'ont rien vu.
# ---------------------------------------------------------------------------

def test_apres_enregistrement_la_vue_montre_la_nouvelle_journee(vue, dialogue):
    # Le cache etait reaccorde a la date du fichier JUSTE AVANT le
    # rechargement : populate ne voyait donc plus aucun changement et
    # reaffichait l'etat d'avant. La saisie etait bien dans le fichier, mais
    # la ligne du jour revenait vide a l'ecran, ce qui donne l'impression
    # que rien n'a ete enregistre.
    vue.reload_callback = lambda: vue.refresh(vue.data.current_period)

    _cellule(vue, 0, "Date", "04/05/2026")
    _cellule(vue, 0, "Prod_Jour", "21,5")
    vue._enregistrer()

    # Le fichier a bien la journee...
    assert "04/05/2026" in _dates_du_fichier(vue)
    # ...et la vue aussi : le cache a ete relu.
    assert vue.toutes_lignes[-1]["Date"] == "04/05/2026"
    assert len(vue.toutes_lignes) == 4
    # La ligne neuve est passee au lendemain, preuve que le tableau a suivi.
    assert vue.table.item(0, 0).text() == "05/05/2026"


def test_apres_enregistrement_les_valeurs_normalisees_sont_affichees(vue,
                                                                     dialogue):
    # Meme cause : le tableau montrait la chaine d'avant normalisation.
    vue.reload_callback = lambda: vue.refresh(vue.data.current_period)

    _cellule(vue, 1, "Prod_Jour", "19,50")   # se normalise en 19,5
    vue._enregistrer()

    assert dl.read_releves_raw(vue.data.releves_path)[2]["Prod_Jour"] == "19,5"
    ligne_affichee = [vue.table.item(1, c).text() for c in range(len(vue.COLS))]
    assert ligne_affichee[1] == "19,5"


def test_deux_enregistrements_de_suite_fonctionnent(vue, dialogue):
    # Le controle de concurrence ne doit pas se declencher sur sa propre
    # ecriture au passage suivant.
    vue.reload_callback = lambda: vue.refresh(vue.data.current_period)

    _cellule(vue, 0, "Date", "04/05/2026")
    _cellule(vue, 0, "Prod_Jour", "21,5")
    vue._enregistrer()

    _cellule(vue, 0, "Date", "05/05/2026")
    _cellule(vue, 0, "Prod_Jour", "22,5")
    vue._enregistrer()

    assert _dates_du_fichier(vue) == [
        "01/05/2026", "02/05/2026", "03/05/2026", "04/05/2026", "05/05/2026"]
    assert dialogue.avertissements == []   # aucune fausse alerte de concurrence

# -----------------------------------------------------------------------------
# Le recapitulatif d'import dit ce qui va changer
# -----------------------------------------------------------------------------
#
# Un utilisateur, 18/09/2026 : « quand je l'importe je n'ai aucune nouvelle
# ligne ». Son import avait pourtant corrige plus de 1000 valeurs -- il avait
# lu « 0 nouveau(x) » et conclu qu'il ne se passait rien. Quatre nombres par
# ligne, et aucun ne disait lequel comptait.
from views._helpers import phrase_import  # noqa: E402


def test_rien_ne_change_se_dit_en_toutes_lettres():
    assert phrase_import(nouveaux=0, remplaces=0, jours=591) == (
        "Rien à changer : les 591 jours de ce fichier sont déjà dans vos "
        "relevés, avec les mêmes valeurs."
    )


def test_des_valeurs_corrigees_sans_jour_nouveau():
    # Le cas d'un utilisateur : rien de nouveau, mais 1062 valeurs remplacees.
    assert phrase_import(nouveaux=0, remplaces=1062, jours=591) == (
        "1 062 valeurs vont être corrigées. Aucune journée nouvelle : "
        "ces dates sont déjà dans vos relevés."
    )


def test_des_journees_nouvelles_et_des_corrections():
    assert phrase_import(nouveaux=12, remplaces=30, jours=42) == (
        "12 journées vont être ajoutées, et 30 valeurs corrigées."
    )


def test_une_seule_journee_nouvelle_se_dit_au_singulier():
    assert phrase_import(nouveaux=1, remplaces=0, jours=1) == (
        "1 journée va être ajoutée."
    )


def test_une_seule_valeur_corrigee():
    assert phrase_import(nouveaux=0, remplaces=1, jours=5) == (
        "1 valeur va être corrigée. Aucune journée nouvelle : "
        "ces dates sont déjà dans vos relevés."
    )

# -----------------------------------------------------------------------------
# La journee en attente de ses releves reseau
# -----------------------------------------------------------------------------
#
# Elle sort des calculs (calculations.jours_en_attente) : il faut donc dire ou
# elle est passee. Un utilisateur a cru ses lignes perdues des qu'une journee
# a disparu d'une vue (19/09/2026) -- c'est la premiere conclusion qu'on tire.

from datetime import date  # noqa: E402

from views._helpers import phrase_en_attente  # noqa: E402


def test_sans_journee_en_attente_on_ne_dit_rien():
    assert phrase_en_attente([]) == ""
    assert phrase_en_attente(None) == ""


def test_une_journee_en_attente_est_nommee_et_rassure():
    texte = phrase_en_attente([date(2026, 9, 19)])
    assert texte == (
        "La journée du 19/09/2026 n'est pas encore comptée : une journée "
        "n'est complète que le lendemain — le soleil doit avoir fini la "
        "sienne, et Enedis publie la consommation et l'injection avec un jour "
        "de retard. Elle s'ajoutera d'elle-même au prochain import — rien "
        "n'est perdu."
    )


def test_deux_journees_en_attente_se_mettent_au_pluriel():
    texte = phrase_en_attente([date(2026, 9, 18), date(2026, 9, 19)])
    assert texte.startswith(
        "Les journées du 18/09/2026, 19/09/2026 ne sont pas encore comptées")
    assert "Elles s'ajouteront" in texte



# ---------------------------------------------------------------------------
# Rapport d'onduleur : il complete le gestionnaire de reseau, il ne le
# remplace pas. L'injection et la consommation ne remplissent que les cases
# vides -- elles servent de base a la TVA sur l'autoconsommation.
# ---------------------------------------------------------------------------

def _rapport_onduleur(chemin, jours):
    """Faux rapport de centrale : (jour ISO, production, export, import)."""
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "Rapport de centrale"
    for col, nom in enumerate(
            ["Période statistique", "Production PV (kWh)",
             "Exportation (kWh)", "Importation (kWh)"], start=1):
        ws.cell(row=2, column=col, value=nom)
    for i, (jour, prod, export, imp) in enumerate(jours, start=3):
        ws.cell(row=i, column=1, value=jour)
        ws.cell(row=i, column=2, value=prod)
        ws.cell(row=i, column=3, value=export)
        ws.cell(row=i, column=4, value=imp)
    wb.save(chemin)
    return str(chemin)


@pytest.fixture
def fichier_choisi(monkeypatch):
    """Remplace le selecteur de fichier par un chemin impose."""
    choix = {}

    class _FauxQFileDialog:
        @staticmethod
        def getOpenFileName(*_a, **_k):
            return choix.get("path", ""), ""

    monkeypatch.setattr(saisie_module, "QFileDialog", _FauxQFileDialog)
    return choix


def test_rapport_onduleur_ne_recouvre_pas_une_injection_relevee(
        vue, dialogue, fichier_choisi, tmp_path):
    # Le 01/05 a deja une injection Enedis (15,2) : l'onduleur annonce 9,9,
    # sa valeur doit etre ignoree. Le 30/04 est inconnu du CSV : tout entre.
    fichier_choisi["path"] = _rapport_onduleur(
        tmp_path / "Rapport.xlsx",
        [("2026-04-30", 17.0, 11.0, 4.0), ("2026-05-01", 21.0, 9.9, 8.8)])
    dialogue.reponse = dialogue.Yes

    vue._importer_enphase()

    lignes = {r["Date"]: r for r in dl.read_releves_raw(vue.data.releves_path)}
    # Journee inconnue d'Enedis : les trois grandeurs sont ecrites.
    assert lignes["30/04/2026"]["Prod_Jour"] == "17"
    assert lignes["30/04/2026"]["Inj_Jour"] == "11"
    assert lignes["30/04/2026"]["Conso_réseau_Jour"] == "4"
    # Journee deja relevee : l'injection et la conso reseau ne bougent pas.
    assert lignes["01/05/2026"]["Inj_Jour"] == "15,2"
    assert lignes["01/05/2026"]["Conso_réseau_Jour"] == "3,1"
    # La production, elle, n'a pas d'autre source que l'onduleur.
    assert lignes["01/05/2026"]["Prod_Jour"] == "21"


def test_le_recapitulatif_annonce_les_journees_laissees_au_reseau(
        vue, dialogue, fichier_choisi, tmp_path):
    # L'utilisateur doit comprendre pourquoi toutes ses journees ne sont pas
    # reprises : sans cette phrase, il croirait a un import rate.
    fichier_choisi["path"] = _rapport_onduleur(
        tmp_path / "Rapport.xlsx",
        [("2026-04-30", 17.0, 11.0, 4.0), ("2026-05-01", 21.0, 9.9, 8.8)])
    dialogue.reponse = dialogue.No

    vue._importer_enphase()

    message = dialogue.messages[0]
    assert "1 journée(s) laissée(s) telle(s) quelle(s)" in message
    assert "gestionnaire de réseau" in message


def test_rapport_entierement_couvert_par_le_reseau_le_dit(
        vue, dialogue, fichier_choisi, tmp_path):
    # Toutes les journees du rapport sont deja relevees : la production est
    # reprise, mais il n'y a rien a completer cote reseau. Sans cette
    # phrase, l'utilisateur croirait l'import rate.
    fichier_choisi["path"] = _rapport_onduleur(
        tmp_path / "Rapport.xlsx",
        [("2026-05-01", 21.0, 9.9, 8.8), ("2026-05-02", 18.0, 11.0, 2.0)])
    dialogue.reponse = dialogue.No

    vue._importer_enphase()

    message = dialogue.messages[0]
    assert "rien à compléter" in message
    assert "2 journée(s) sont déjà relevées" in message
