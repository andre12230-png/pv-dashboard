"""« Mes reglages » : lire et ecrire les reglages de config.yaml sans Bloc-notes.

Pourquoi ce module ?
    Le seul moyen de decrire son installation etait d'ouvrir config.yaml avec
    le Bloc-notes : un long chemin de fichier, puis un texte technique a
    modifier sans casser son alignement. De quoi decourager un debutant.
    La fenetre « Mes reglages » (fenetre_reglages.py) s'appuie sur ce module.

Deux promesses, tenues ici :
    1. Le fichier garde sa forme ET ses commentaires. On ne reecrit pas le
       fichier entier : on remplace, a leur place, les seules valeurs qui ont
       change. Les config.yaml existants restent donc valables tels quels.
    2. Rien n'est ecrit sans preuve. Le texte modifie est relu, et doit
       donner exactement la configuration attendue -- les valeurs voulues,
       et rien d'autre de change. Au moindre ecart, on n'ecrit rien. Avant
       d'ecrire, une copie datee part dans backups/.

Changer de prix suit la regle de toujours : on n'ecrase pas une periode de
prix, on en ajoute une (sinon les nouveaux prix refactureraient tout
l'historique). Si la date des nouveaux prix est posterieure au debut de la
periode en cours, celle-ci est fermee la veille et une nouvelle commence.
Meme date : on corrige la periode en cours.

Ce module ne depend pas de Qt : il se teste seul.
"""
from __future__ import annotations

import copy
import os
import re
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

import calculations as calc

# La section du contrat porte l'un de ces deux noms (voir normaliser_config
# dans app_desktop.py) : le nouveau d'abord, l'ancien pour les vieux fichiers.
SECTIONS_CONTRAT = ("contrat_hphc", "octopus_hphc")


class ReglagesRefuses(RuntimeError):
    """Les reglages n'ont pas ete enregistres ; le message dit pourquoi."""


# ----------------------------------------------------------------------
# Lecture : les valeurs a proposer dans la fenetre
# ----------------------------------------------------------------------

def _date(valeur) -> date:
    """Une date de config.yaml ('2025-04-15' ou date YAML) en objet date."""
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    return date.fromisoformat(str(valeur))


def _section_contrat(cfg: dict) -> str | None:
    """Nom de la section du contrat presente dans ce fichier."""
    tarifs = cfg.get("tarifs_reseau") or {}
    for nom in SECTIONS_CONTRAT:
        if isinstance(tarifs.get(nom), dict):
            return nom
    return None


def _contrat(cfg: dict) -> dict:
    section = _section_contrat(cfg)
    return cfg["tarifs_reseau"][section] if section else {}


def lire_reglages(cfg: dict) -> dict:
    """Les reglages modifiables, tels qu'ils sont aujourd'hui.

    Pour les prix du fournisseur : ceux de la derniere periode, la seule
    qu'on modifie depuis la fenetre.
    """
    inst = cfg.get("installation") or {}
    oa = cfg.get("oa") or {}
    prime = oa.get("prime_autoconsommation") or {}
    contrat = _contrat(cfg)
    periodes = contrat.get("periodes") or []
    derniere = periodes[-1] if periodes else {}
    aujourdhui = date.today()
    return {
        "puissance_kwc": float(inst.get("puissance_kwc") or 0),
        "cout_total_eur": float(inst.get("cout_total_eur") or 0),
        "date_mise_en_service": _date(
            inst.get("date_mise_en_service") or aujourdhui),
        "date_debut_contrat_oa": _date(
            inst.get("date_debut_contrat_oa") or aujourdhui),
        "prix_oa": float(oa.get("prix_kwh_eur") or 0),
        "prime_par_kwc": float(prime.get("montant_par_kwc") or 0),
        "prime_duree": int(prime.get("duree_annees") or 1),
        "nom": str(contrat.get("nom") or ""),
        "offre": str(contrat.get("offre") or ""),
        "abonnement": float(derniere.get("abonnement") or 0),
        "prix_hp": float(derniere.get("prix_hp") or 0),
        "prix_hc": float(derniere.get("prix_hc") or 0),
        "prix_depuis": _date(derniere.get("debut") or aujourdhui),
        "plages_hc": [str(p) for p in (contrat.get("plages_hc") or [])],
    }


# ----------------------------------------------------------------------
# Ecriture des valeurs, en YAML
# ----------------------------------------------------------------------

def _chaine(texte) -> str:
    """Une chaine YAML entre guillemets doubles."""
    return '"' + str(texte).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _nombre(x) -> str:
    """Un nombre YAML qui se relit a l'identique : 4.5, 11500.0, 0.225."""
    return repr(float(x))


def _nombre_kwh(x) -> str:
    """Un total en kWh : 1497 reste 1497, 641.07 garde ses decimales.

    _nombre() rendrait « 1497.0 » -- juste, mais il salirait un fichier ou
    l'utilisateur a tout ecrit en entiers.
    """
    valeur = float(x)
    return str(int(valeur)) if valeur == int(valeur) else repr(valeur)


def _texte_date(d) -> str:
    return _chaine(_date(d).isoformat())


# ----------------------------------------------------------------------
# Reperage dans le texte : on suit l'indentation, comme YAML
# ----------------------------------------------------------------------

def _indent(ligne: str) -> int:
    return len(ligne) - len(ligne.lstrip(" "))


def _utile(ligne: str) -> bool:
    """Ni vide, ni commentaire."""
    s = ligne.strip()
    return bool(s) and not s.startswith("#")


def _fin_bloc(lignes: list[str], i: int) -> int:
    """Indice (exclu) de la fin du bloc de la cle ecrite a la ligne i."""
    ind = _indent(lignes[i])
    j = i + 1
    while j < len(lignes):
        if _utile(lignes[j]) and _indent(lignes[j]) <= ind:
            break
        j += 1
    return j


def _cle(lignes: list[str], chemin: list[str], debut: int = 0,
         fin: int | None = None) -> int | None:
    """Ligne ou s'ecrit la cle 'a.b.c' (chemin ['a', 'b', 'c']), ou None.

    Seules les cles du niveau courant comptent : celles d'un bloc plus
    indente, ou la suite d'une accolade sur la ligne d'apres, sont ignorees.
    """
    fin = len(lignes) if fin is None else fin
    motif = re.compile(rf"^\s*{re.escape(chemin[0])}:(\s|$)")
    niveau = None
    for k in range(debut, fin):
        if not _utile(lignes[k]):
            continue
        ind = _indent(lignes[k])
        if niveau is None:
            niveau = ind
        if ind != niveau or not motif.match(lignes[k]):
            continue
        if len(chemin) == 1:
            return k
        return _cle(lignes, chemin[1:], k + 1, _fin_bloc(lignes, k))
    return None


# « cle: valeur   # commentaire » : le commentaire est garde tel quel.
_SCALAIRE = re.compile(r"^(\s*[\w.-]+:[ \t]*)(.*?)([ \t]+#.*)?$")


def _remplacer_valeur(lignes: list[str], k: int, valeur: str) -> None:
    m = _SCALAIRE.match(lignes[k])
    lignes[k] = f"{m.group(1)}{valeur}{m.group(3) or ''}"


def _poser(lignes: list[str], chemin: list[str], valeur: str) -> None:
    k = _cle(lignes, chemin)
    if k is None:
        raise ReglagesRefuses(
            f"Réglage introuvable dans config.yaml : {'.'.join(chemin)}. "
            "Ajoutez-le avec le Bloc-notes (le modèle livré montre où).")
    _remplacer_valeur(lignes, k, valeur)


def _poser_ou_ajouter(lignes: list[str], chemin_section: list[str],
                      cle: str, valeur: str) -> None:
    """Remplace la cle, ou l'ajoute en tete de sa section si elle manque."""
    k = _cle(lignes, chemin_section + [cle])
    if k is not None:
        _remplacer_valeur(lignes, k, valeur)
        return
    ks = _cle(lignes, chemin_section)
    fin = _fin_bloc(lignes, ks)
    enfants = [j for j in range(ks + 1, fin) if _utile(lignes[j])]
    ind = _indent(lignes[enfants[0]]) if enfants else _indent(lignes[ks]) + 2
    lignes.insert(ks + 1, f"{' ' * ind}{cle}: {valeur}")


def _remplacer_liste(lignes: list[str], k: int, elements: list[str]) -> None:
    """Remplace les elements d'une liste ; ses commentaires restent."""
    m = _SCALAIRE.match(lignes[k])
    if m.group(2).strip():
        # Forme en ligne : plages_hc: ["22:00-06:00"]
        liste = ", ".join(_chaine(e) for e in elements)
        lignes[k] = f"{m.group(1)}[{liste}]{m.group(3) or ''}"
        return
    fin = _fin_bloc(lignes, k)
    items = [j for j in range(k + 1, fin) if lignes[j].lstrip().startswith("- ")]
    if items:
        ind, position = _indent(lignes[items[0]]), items[0]
    else:
        ind, position = _indent(lignes[k]) + 2, fin
    for j in reversed(items):
        del lignes[j]
    for n, e in enumerate(elements):
        lignes.insert(position + n, f"{' ' * ind}- {_chaine(e)}")


def _texte_periode(ind: int, p: dict) -> list[str]:
    """Une periode de prix, sur deux lignes, comme dans le modele livre."""
    fin = "null" if p.get("fin") in (None, "") else _texte_date(p["fin"])
    return [
        f"{' ' * ind}- {{ debut: {_texte_date(p['debut'])}, fin: {fin},",
        f"{' ' * (ind + 4)}abonnement: {_nombre(p['abonnement'])}, "
        f"prix_hp: {_nombre(p['prix_hp'])}, prix_hc: {_nombre(p['prix_hc'])} }}",
    ]


# ----------------------------------------------------------------------
# Ce qui change : une seule fonction, appliquee au dict ET au texte
# ----------------------------------------------------------------------

def _periodes_apres(periodes: list[dict], v: dict) -> list[dict] | None:
    """Nouvelle liste de periodes, ou None si les prix n'ont pas change."""
    if not periodes:
        raise ReglagesRefuses(
            "config.yaml ne contient aucune période de prix : complétez-le "
            "avec le Bloc-notes.")
    derniere = periodes[-1]
    prix = {"abonnement": float(v["abonnement"]),
            "prix_hp": float(v["prix_hp"]),
            "prix_hc": float(v["prix_hc"])}
    if all(float(derniere.get(c) or 0) == prix[c] for c in prix):
        return None
    debut = _date(derniere["debut"])
    if any(_date(p["debut"]) > debut for p in periodes):
        raise ReglagesRefuses(
            "Les périodes de prix de config.yaml ne sont pas rangées dans "
            "l'ordre des dates : modifiez-les avec le Bloc-notes.")
    depuis = _date(v["prix_depuis"])
    if depuis < debut:
        raise ReglagesRefuses(
            f"Les nouveaux prix ne peuvent pas commencer avant la période en "
            f"cours (le {debut:%d/%m/%Y}). Pour corriger une ancienne "
            "période, passez par le Bloc-notes.")
    avant = periodes[:-1]
    if depuis == debut:
        # Meme date : on corrige la periode en cours.
        return avant + [{**derniere, "debut": debut.isoformat(),
                         "fin": _fin_texte(derniere), **prix}]
    # Nouvelle periode : l'ancienne se ferme la veille (sauf si elle etait
    # deja close plus tot), et ses prix restent ceux des mois passes.
    fin_ancienne = derniere.get("fin")
    if fin_ancienne in (None, "") or _date(fin_ancienne) >= depuis:
        fin_ancienne = depuis - timedelta(days=1)
    fermee = {**derniere, "debut": debut.isoformat(),
              "fin": _date(fin_ancienne).isoformat()}
    neuve = {"debut": depuis.isoformat(), "fin": None, **prix}
    return avant + [fermee, neuve]


def _fin_texte(p: dict):
    fin = p.get("fin")
    return None if fin in (None, "") else _date(fin).isoformat()


def reglages_attendus(cfg: dict, v: dict) -> dict:
    """La configuration telle qu'elle doit etre apres enregistrement."""
    c = copy.deepcopy(cfg)
    inst = c.setdefault("installation", {})
    oa = c.setdefault("oa", {})
    prime = oa.setdefault("prime_autoconsommation", {})
    for cle_v, (bloc, cle) in _CHAMPS_SIMPLES.items():
        cible = {"installation": inst, "oa": oa, "prime": prime}[bloc]
        if _change(cible.get(cle), v[cle_v], cle_v):
            cible[cle] = _valeur_attendue(v[cle_v], cle_v)
    section = _section_contrat(c)
    contrat = c["tarifs_reseau"][section]
    for cle in ("nom", "offre"):
        if str(contrat.get(cle) or "") != v[cle]:
            contrat[cle] = v[cle]
    if [str(p) for p in contrat.get("plages_hc") or []] != list(v["plages_hc"]):
        contrat["plages_hc"] = list(v["plages_hc"])
    nouvelles = _periodes_apres(contrat.get("periodes") or [], v)
    if nouvelles is not None:
        contrat["periodes"] = nouvelles
    return c


# (cle dans la fenetre) -> (bloc, cle dans config.yaml)
_CHAMPS_SIMPLES = {
    "puissance_kwc": ("installation", "puissance_kwc"),
    "cout_total_eur": ("installation", "cout_total_eur"),
    "date_mise_en_service": ("installation", "date_mise_en_service"),
    "date_debut_contrat_oa": ("installation", "date_debut_contrat_oa"),
    "prix_oa": ("oa", "prix_kwh_eur"),
    "prime_par_kwc": ("prime", "montant_par_kwc"),
    "prime_duree": ("prime", "duree_annees"),
}
_CHEMINS = {
    "installation": ["installation"],
    "oa": ["oa"],
    "prime": ["oa", "prime_autoconsommation"],
}
_DATES = ("date_mise_en_service", "date_debut_contrat_oa")


def _change(ancienne, nouvelle, cle_v: str) -> bool:
    if ancienne is None:
        return True
    try:
        if cle_v in _DATES:
            return _date(ancienne) != _date(nouvelle)
        return float(ancienne) != float(nouvelle)
    except (TypeError, ValueError):
        return True


def _valeur_attendue(valeur, cle_v: str):
    if cle_v in _DATES:
        return _date(valeur).isoformat()
    if cle_v == "prime_duree":
        return int(valeur)
    return float(valeur)


def _valeur_texte(valeur, cle_v: str) -> str:
    if cle_v in _DATES:
        return _texte_date(valeur)
    if cle_v == "prime_duree":
        return str(int(valeur))
    return _nombre(valeur)


def appliquer_reglages(texte: str, cfg: dict, v: dict) -> str:
    """Le texte de config.yaml, avec les seules valeurs changees remplacees."""
    nl = "\r\n" if "\r\n" in texte else "\n"
    fin_de_ligne = texte.endswith(("\n", "\r"))
    lignes = texte.splitlines()

    inst = cfg.get("installation") or {}
    oa = cfg.get("oa") or {}
    prime = oa.get("prime_autoconsommation") or {}
    blocs = {"installation": inst, "oa": oa, "prime": prime}
    for cle_v, (bloc, cle) in _CHAMPS_SIMPLES.items():
        if _change(blocs[bloc].get(cle), v[cle_v], cle_v):
            _poser(lignes, _CHEMINS[bloc] + [cle], _valeur_texte(v[cle_v], cle_v))

    section = _section_contrat(cfg)
    if section is None:
        raise ReglagesRefuses(
            "config.yaml ne contient pas la section du contrat "
            "(tarifs_reseau > contrat_hphc) : partez du modèle livré.")
    chemin_contrat = ["tarifs_reseau", section]
    contrat = cfg["tarifs_reseau"][section]
    for cle in ("nom", "offre"):
        if str(contrat.get(cle) or "") != v[cle]:
            _poser_ou_ajouter(lignes, chemin_contrat, cle, _chaine(v[cle]))

    if [str(p) for p in contrat.get("plages_hc") or []] != list(v["plages_hc"]):
        k = _cle(lignes, chemin_contrat + ["plages_hc"])
        if k is None:
            raise ReglagesRefuses("Réglage introuvable : plages_hc.")
        _remplacer_liste(lignes, k, list(v["plages_hc"]))

    nouvelles = _periodes_apres(contrat.get("periodes") or [], v)
    if nouvelles is not None:
        _reecrire_periodes(lignes, chemin_contrat, contrat["periodes"], nouvelles)

    return nl.join(lignes) + (nl if fin_de_ligne else "")


def _reecrire_periodes(lignes: list[str], chemin_contrat: list[str],
                       anciennes: list[dict], nouvelles: list[dict]) -> None:
    """Reecrit la derniere periode du fichier, et ajoute la nouvelle."""
    kp = _cle(lignes, chemin_contrat + ["periodes"])
    if kp is None:
        raise ReglagesRefuses("Réglage introuvable : periodes.")
    fin = _fin_bloc(lignes, kp)
    items = [j for j in range(kp + 1, fin) if lignes[j].lstrip().startswith("- ")]
    if len(items) != len(anciennes) or "{" not in lignes[items[-1]]:
        raise ReglagesRefuses(
            "Les périodes de prix de config.yaml ont une forme inattendue : "
            "modifiez-les avec le Bloc-notes.")
    s = e = items[-1]
    while "}" not in lignes[e]:
        e += 1
        if e >= fin:
            raise ReglagesRefuses("Période de prix mal fermée dans config.yaml.")
    ind = _indent(lignes[s])
    derniere, modifiees = anciennes[-1], nouvelles[len(anciennes) - 1:]
    # La periode qu'on ferme garde son ecriture d'origine (0.1290 reste
    # 0.1290) : seule sa date de fin change. On ne la reecrit entierement que
    # si ce remplacement n'est pas possible.
    if len(modifiees) == 2 and all(
            modifiees[0].get(c) == derniere.get(c)
            for c in ("abonnement", "prix_hp", "prix_hc")):
        ancien = lignes[s:e + 1]
        if _fin_texte(derniere) == modifiees[0]["fin"]:
            fermee = ancien
        else:
            fermee = _poser_fin(ancien, modifiees[0]["fin"])
        if fermee is not None:
            lignes[s:e + 1] = fermee + _texte_periode(ind, modifiees[1])
            return
    remplacement = []
    for p in modifiees:
        remplacement += _texte_periode(ind, p)
    lignes[s:e + 1] = remplacement


_FIN_OUVERTE = re.compile(r"(\bfin:\s*)(null|~)?(?=\s*[,}])")


def _poser_fin(lignes_periode: list[str], fin: str) -> list[str] | None:
    """Les lignes d'une periode avec « fin: null » remplace par la date, ou
    None si ce « fin » ouvert n'y est pas ecrit tel quel."""
    for n, ligne in enumerate(lignes_periode):
        nouvelle, compte = _FIN_OUVERTE.subn(
            lambda m: m.group(1) + _texte_date(fin), ligne, count=1)
        if compte:
            return lignes_periode[:n] + [nouvelle] + lignes_periode[n + 1:]
    return None


# ----------------------------------------------------------------------
# La prime a l'autoconsommation, dite en euros
# ----------------------------------------------------------------------
#
# Le champ attend un montant PAR kWc. Un utilisateur y a saisi le total de sa
# prime (1440 EUR) : son installation s'est retrouvee amortie au bout d'un an,
# sans qu'aucun message ne l'avertisse (18/09/2026). Il a fini par trouver la
# bonne valeur par tatonnement, en croyant que c'etait un montant mensuel.
# D'ou cette phrase, affichee sous les cases et recalculee a chaque frappe.

def _euros(x: float) -> str:
    """1440 -> « 1 440 », 456.5 -> « 456,50 » (milliers comme fmt_eur)."""
    entier = abs(x - round(x)) < 0.005
    texte = f"{x:,.0f}" if entier else f"{x:,.2f}"
    return texte.replace(",", " ").replace(".", ",")


def _kwc(x: float) -> str:
    """6.0 -> « 6 », 3.5 -> « 3,5 » : on ne montre pas de zero inutile."""
    return f"{x:g}".replace(".", ",")


def phrase_prime(par_kwc: float, kwc: float, duree: int) -> str:
    """Ce que la prime represente vraiment, en euros et non en euros par kWc."""
    total = float(par_kwc) * float(kwc)
    if total <= 0:
        return "Pas de prime."
    debut = (f"{_euros(par_kwc)} €/kWc × {_kwc(kwc)} kWc = "
             f"{_euros(total)} € au total")
    if duree <= 1:
        return debut + ", versés en une seule fois."
    return (f"{debut}, soit {_euros(total / duree)} € par an pendant "
            f"{duree} ans.")


# ----------------------------------------------------------------------
# Controle des valeurs saisies
# ----------------------------------------------------------------------

def controler(v: dict) -> None:
    """Refuse ce qui ne peut pas etre juste, avec un message clair."""
    if float(v["puissance_kwc"]) <= 0:
        raise ReglagesRefuses("La puissance de l'installation doit être "
                              "supérieure à zéro.")
    if not v["plages_hc"]:
        raise ReglagesRefuses(
            "Indiquez au moins une plage d'heures creuses. En option Base "
            "(prix unique), gardez celle du modèle et mettez le même prix en "
            "heures pleines et en heures creuses.")
    try:
        calc.parse_plages_hc(list(v["plages_hc"]))
    except Exception as exc:
        raise ReglagesRefuses(
            "Heures creuses : écrivez chaque plage sous la forme "
            "22:00-06:00, et séparez-les par un point-virgule.") from exc


# ----------------------------------------------------------------------
# Recalages sur factures (config-local.yaml)
# ----------------------------------------------------------------------
#
# Ces quatre sections REECRIVENT les releves journaliers pour retomber sur le
# total d'une facture. Elles vivent dans config-local.yaml, qui n'est jamais
# livre avec le programme : les factures d'un foyer fausseraient les chiffres
# d'un autre, en silence. Un utilisateur a demande le 18/09/2026 de pouvoir
# les saisir sans ouvrir le Bloc-notes -- d'ou ce qui suit.
#
# Meme prudence que pour config.yaml : on remplace les seules lignes
# concernees, on relit le resultat avant d'ecrire, on garde une copie datee.

# cle YAML -> (libelle, champ chiffre). Le champ vaut None quand la section
# ne porte pas de total : les jours douteux n'ont qu'un motif.
SORTES_RECALAGE = {
    "conso_reseau_douteuse": ("Jours douteux", None),
    "conso_reseau_recalee": ("Conso recalée sur facture", "total_kwh"),
    "conso_reseau_facturee": ("Conso connue par la facture", "total_kwh"),
    "injection_facturee": ("Injection payée par EDF OA", "total_kwh"),
}


def recalages_vides() -> dict:
    """Le dictionnaire des quatre sortes, toutes vides."""
    return {cle: [] for cle in SORTES_RECALAGE}


def lire_recalages(cfg: dict) -> dict:
    """Les recalages de config-local.yaml, dates normalisees en date()."""
    sources = (cfg or {}).get("sources") or {}
    lus = recalages_vides()
    for cle, (_libelle, champ) in SORTES_RECALAGE.items():
        for p in sources.get(cle) or []:
            periode = {"debut": _date(p["debut"]), "fin": _date(p["fin"])}
            if champ:
                periode[champ] = float(p.get(champ) or 0)
                periode["source"] = str(p.get("source") or "")
            else:
                periode["motif"] = str(p.get("motif") or "")
            lus[cle].append(periode)
    return lus


def _texte_recalage(ind: int, cle: str, p: dict) -> list:
    """Une periode de recalage, a la forme du modele livre."""
    debut, fin = _texte_date(p["debut"]), _texte_date(p["fin"])
    champ = SORTES_RECALAGE[cle][1]
    if champ is None:
        return [f"{' ' * ind}- {{ debut: {debut}, fin: {fin}, "
                f"motif: {_chaine(p.get('motif', ''))} }}"]
    return [
        f"{' ' * ind}- {{ debut: {debut}, fin: {fin}, "
        f"{champ}: {_nombre_kwh(p[champ])},",
        f"{' ' * (ind + 4)}source: {_chaine(p.get('source', ''))} }}",
    ]


def _remplacer_periodes(lignes: list, k: int, textes: list) -> None:
    """Remplace les elements d'une liste ecrite sur plusieurs lignes.

    Les commentaires du bloc restent ou ils sont ; seules les lignes de
    donnees sont refaites. Une liste videe s'ecrit « cle: [] ».
    """
    fin = _fin_bloc(lignes, k)
    utiles = [j for j in range(k + 1, fin) if _utile(lignes[j])]
    position = utiles[0] if utiles else fin
    for j in reversed(utiles):
        del lignes[j]
    m = _SCALAIRE.match(lignes[k])
    # m.group(1) va jusqu'aux espaces qui suivent le « : » -- il n'y en a
    # aucun quand la cle finit la ligne, d'ou l'espace remis a la main :
    # « injection_facturee:[] » ne serait pas du YAML.
    debut_ligne = m.group(1).rstrip()
    if not textes:
        lignes[k] = f"{debut_ligne} []{m.group(3) or ''}"
        return
    lignes[k] = f"{debut_ligne}{m.group(3) or ''}".rstrip()
    for n, ligne in enumerate(textes):
        lignes.insert(position + n, ligne)


def appliquer_recalages(texte: str, recalages: dict) -> str:
    """Le texte de config-local.yaml, avec les seuls recalages remplaces."""
    nl = "\r\n" if "\r\n" in texte else "\n"
    fin_de_ligne = texte.endswith(("\n", "\r"))
    lignes = texte.splitlines()

    anciens = lire_recalages(yaml.safe_load(texte) or {})

    if _cle(lignes, ["sources"]) is None:
        raise ReglagesRefuses(
            "config-local.yaml ne contient pas de section « sources » : "
            "partez du modèle livré, config-local.exemple.yaml.")

    for cle in SORTES_RECALAGE:
        if anciens[cle] == recalages[cle]:
            continue
        ks = _cle(lignes, ["sources"])   # les indices bougent a chaque passe
        ind = _indent(lignes[ks]) + 4
        textes = []
        for periode in recalages[cle]:
            textes.extend(_texte_recalage(ind, cle, periode))
        k = _cle(lignes, ["sources", cle])
        if k is None:
            # Cette sorte n'est pas encore dans le fichier : on l'ajoute a la
            # fin de la section, avec ses periodes.
            fin = _fin_bloc(lignes, ks)
            nouvelles = [f"{' ' * (ind - 2)}{cle}:"] + textes
            for n, ligne in enumerate(nouvelles):
                lignes.insert(fin + n, ligne)
        elif recalages[cle][:len(anciens[cle])] == anciens[cle]:
            # Cas courant : on ajoute une periode a la suite. Les anciennes ne
            # sont PAS reecrites -- elles portent la mise en forme de celui
            # qui les a saisies (source sur plusieurs lignes, commentaires),
            # et rien ne justifie d'y toucher.
            ajoutees = []
            for periode in recalages[cle][len(anciens[cle]):]:
                ajoutees.extend(_texte_recalage(ind, cle, periode))
            fin = _fin_bloc(lignes, k)
            for n, ligne in enumerate(ajoutees):
                lignes.insert(fin + n, ligne)
        else:
            _remplacer_periodes(lignes, k, textes)

    return nl.join(lignes) + (nl if fin_de_ligne else "")


def controler_recalages(recalages: dict) -> None:
    """Refuse une periode impossible, avec un message clair."""
    for cle, (libelle, champ) in SORTES_RECALAGE.items():
        for p in recalages.get(cle) or []:
            if _date(p["fin"]) < _date(p["debut"]):
                raise ReglagesRefuses(
                    f"{libelle} : la date de fin doit être après celle de "
                    "début.")
            if champ and float(p.get(champ) or 0) < 0:
                raise ReglagesRefuses(
                    f"{libelle} : un total en kWh ne peut pas être négatif.")


# Fichier cree quand il n'existe pas encore : le strict necessaire, le modele
# livre restant la reference commentee.
_LOCAL_NEUF = (
    "# Ce fichier complete config.yaml. Il n'appartient qu'a CETTE\n"
    "# installation : ne le recopiez jamais ailleurs, ses totaux de factures\n"
    "# reecrivent les releves journaliers.\n"
    "#\n"
    "# Ecrit par la fenetre « Mes reglages ». Le modele commente livre a cote,\n"
    "# config-local.exemple.yaml, montre tout ce qu'on peut y mettre.\n"
    "sources:\n"
)


def enregistrer_recalages(chemin, recalages: dict, dossier_sauvegardes) -> bool:
    """Ecrit les recalages dans config-local.yaml, qu'il existe ou non.

    Rend False s'il n'y avait rien a changer. Leve ReglagesRefuses sans avoir
    rien ecrit si le resultat ne se relit pas comme attendu.
    """
    controler_recalages(recalages)
    chemin = Path(chemin)
    existait = chemin.exists()
    texte = chemin.read_text(encoding="utf-8") if existait else _LOCAL_NEUF
    nouveau = appliquer_recalages(texte, recalages)
    if nouveau == texte:
        return False

    # La preuve : relu, le texte doit rendre exactement ce qu'on voulait.
    try:
        relu = yaml.safe_load(nouveau)
    except yaml.YAMLError:
        relu = None
    if relu is None or lire_recalages(relu) != recalages:
        raise ReglagesRefuses(
            "Les recalages n'ont pas été enregistrés : config-local.yaml a "
            "une forme que la fenetre ne sait pas modifier sans risque. Rien "
            "n'a été changé. Modifiez-le avec le Bloc-notes.")

    if existait:
        dossier_sauvegardes = Path(dossier_sauvegardes)
        dossier_sauvegardes.mkdir(parents=True, exist_ok=True)
        shutil.copy2(chemin, dossier_sauvegardes /
                     ("config-local_avant-reglages_"
                      f"{datetime.now():%Y%m%d-%H%M%S}.yaml"))
    temporaire = chemin.with_name(chemin.name + ".tmp")
    with open(temporaire, "w", encoding="utf-8", newline="") as fh:
        fh.write(nouveau)
    os.replace(temporaire, chemin)
    return True


# ----------------------------------------------------------------------
# Enregistrement
# ----------------------------------------------------------------------

def enregistrer_reglages(chemin: Path, v: dict, dossier_sauvegardes: Path,
                         verifier=None) -> bool:
    """Ecrit les reglages dans config.yaml. Rend False s'il n'y avait rien a
    changer. Leve ReglagesRefuses sans avoir rien ecrit si quelque chose ne
    va pas.

    verifier : controle de la configuration complete (verifier_config de
    app_desktop), appele sur le resultat avant toute ecriture.
    """
    controler(v)
    chemin = Path(chemin)
    with open(chemin, encoding="utf-8", newline="") as fh:
        texte = fh.read()
    cfg = yaml.safe_load(texte) or {}
    nouveau = appliquer_reglages(texte, cfg, v)
    if nouveau == texte:
        return False

    # La preuve : relu, le texte doit donner exactement ce qui est attendu.
    attendu = reglages_attendus(cfg, v)
    try:
        relu = yaml.safe_load(nouveau)
    except yaml.YAMLError:
        relu = None
    if relu != attendu:
        raise ReglagesRefuses(
            "Les réglages n'ont pas été enregistrés : config.yaml a une forme "
            "que la fenêtre ne sait pas modifier sans risque. Rien n'a été "
            "changé. Modifiez-le avec le Bloc-notes.")
    if verifier is not None:
        try:
            verifier(copy.deepcopy(relu))
        except RuntimeError as exc:
            raise ReglagesRefuses(str(exc)) from exc

    # Copie datee, puis ecriture par un fichier temporaire : une coupure en
    # plein enregistrement ne laisse jamais un config.yaml a moitie ecrit.
    dossier_sauvegardes = Path(dossier_sauvegardes)
    dossier_sauvegardes.mkdir(parents=True, exist_ok=True)
    shutil.copy2(chemin, dossier_sauvegardes /
                 f"config_avant-reglages_{datetime.now():%Y%m%d-%H%M%S}.yaml")
    temporaire = chemin.with_name(chemin.name + ".tmp")
    with open(temporaire, "w", encoding="utf-8", newline="") as fh:
        fh.write(nouveau)
    os.replace(temporaire, chemin)
    return True
