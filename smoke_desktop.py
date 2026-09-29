"""Smoke test offscreen : ouvre la fenetre, force chaque vue, chaque periode
et le selecteur. Aucun affichage visible. (Un seul theme depuis 1.32.0 : le
clair, comme Pecule.)

Il tourne sur un jeu INVENTE (demo_releves.py : l'installation du config.yaml
livre, releves du 01/01/2024 a hier), dans un dossier temporaire. Il lisait
auparavant les releves du dossier du projet ; depuis qu'ils n'y sont plus, il
n'avait rien a montrer et trois controles echouaient (26/09/2026)."""

import os
import shutil
import sys
import tempfile
from pathlib import Path

# Force le mode offscreen AVANT d'importer Qt
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

import app_desktop
from accords import pluriel
from demo_releves import ecrire_releves_demo


def main():
    # Dossier de donnees jetable : le modele livre et le jeu invente. Rien
    # n'est ecrit dans le dossier du projet (ni releves, ni sauvegardes).
    demo = Path(tempfile.mkdtemp(prefix="smoke_pv_"))
    shutil.copy2(app_desktop.CONFIG_PATH, demo / "config.yaml")
    nb_jours = ecrire_releves_demo(demo / "Releves-pv.csv")
    print(f"jeu : {pluriel(nb_jours, 'jour inventé', 'jours inventés')}")
    app_desktop.BASE_DIR = demo
    app_desktop.CONFIG_PATH = demo / "config.yaml"
    app_desktop.CONFIG_LOCAL_PATH = demo / "config-local.yaml"   # absent : voulu
    cfg = app_desktop.load_config()
    data = app_desktop.build_dataset(cfg)
    # Reference gardee : QApplication doit rester vivante pendant le test.
    _app = QApplication(sys.argv)
    # QSettings sur fichier jetable : le test change de periode, il ne doit
    # pas ecraser les preferences reelles de l'utilisateur.
    settings_tmp = tempfile.NamedTemporaryFile(suffix=".ini", delete=False)
    settings_tmp.close()
    settings = QSettings(settings_tmp.name, QSettings.Format.IniFormat)
    win = app_desktop.MainWindow(data, settings=settings)

    errors = []
    for view_key in [n[0] for n in app_desktop.NAV_ITEMS]:
        try:
            win._switch_view(view_key)
            print(f"  vue {view_key:14s} OK")
        except Exception as e:
            errors.append((view_key, str(e)))
            print(f"  vue {view_key:14s} ERREUR : {e}")

    print("--- filtrage par periode ---")
    for value in ["all", "year-2024", "month-2026-04", "oa-1", "oa-3"]:
        try:
            win._appliquer_periode(value)
            if win.current_period != value:
                raise AssertionError(f"affiche {win.current_period}")
            print(f"  periode {value:14s} OK")
        except Exception as e:
            errors.append((f"period {value}", str(e)))
            print(f"  periode {value:14s} ERREUR : {e}")

    print("--- fleches precedent / suivant ---")
    # Depuis un mois du milieu de l'historique, les deux fleches doivent
    # repondre et changer la periode : c'est le geste le plus frequent.
    try:
        win._appliquer_periode("month-2025-06")
        win._decaler_periode(-1)
        recule = win.current_period
        win._decaler_periode(+1)
        avance = win.current_period
        if recule != "month-2025-05" or avance != "month-2025-06":
            raise AssertionError(f"recule={recule} puis avance={avance}")
        print(f"  mois precedent puis suivant OK ({recule} -> {avance})")
    except Exception as e:
        errors.append(("fleches", str(e)))
        print(f"  fleches ERREUR : {e}")

    print("--- bouton « Ce mois-ci » et raccourcis ---")
    # Depuis un mois passe, le bouton et Ctrl+Origine ramenent au mois de
    # reference ; Ctrl+Gauche recule d'un mois. Grise une fois arrive.
    try:
        from views import mois_de_reference
        cible = mois_de_reference(win.data.df)
        win._switch_view("dashboard")
        win._appliquer_periode("month-2025-06")
        if not win.btn_ce_mois.isEnabled():
            raise AssertionError("bouton grise sur un mois passe")
        win.btn_ce_mois.click()
        if win.current_period != cible or win.btn_ce_mois.isEnabled():
            raise AssertionError(f"bouton -> {win.current_period}, attendu {cible}")
        touches = {sc.key().toString(): sc for sc in win.raccourcis_periode}
        win._appliquer_periode("month-2025-06")
        touches["Ctrl+Left"].activated.emit()
        if win.current_period != "month-2025-05":
            raise AssertionError(f"Ctrl+Gauche -> {win.current_period}")
        touches["Ctrl+Home"].activated.emit()
        if win.current_period != cible:
            raise AssertionError(f"Ctrl+Origine -> {win.current_period}")
        # Onglet sans periode : les raccourcis ne font rien.
        win._switch_view("saisie")
        touches["Ctrl+Left"].activated.emit()
        if win.current_period != cible:
            raise AssertionError("raccourci actif sur un onglet sans periode")
        win._switch_view("dashboard")
        print(f"  Ce mois-ci et raccourcis OK (-> {cible})")
    except Exception as e:
        errors.append(("ce mois-ci", str(e)))
        print(f"  Ce mois-ci ERREUR : {e}")

    print("--- page Statistiques : l'annee seulement ---")
    try:
        win._switch_view("stats")
        if not win.month_combo.isHidden():
            raise AssertionError("menu des mois visible sur Statistiques")
        if win.btn_ce_mois.text() != "Cette année":
            raise AssertionError(f"bouton : {win.btn_ce_mois.text()}")
        win._switch_view("dashboard")
        if win.month_combo.isHidden() or win.btn_ce_mois.text() != "Ce mois-ci":
            raise AssertionError("selecteur complet non retabli")
        print("  Statistiques sans menu des mois, retour au complet OK")
    except Exception as e:
        errors.append(("stats annuel", str(e)))
        print(f"  Statistiques ERREUR : {e}")

    print("--- les deux menus ---")
    try:
        win._appliquer_periode("month-2026-04")
        annees = [win.year_combo.itemText(i) for i in range(win.year_combo.count())]
        mois = [win.month_combo.itemText(i) for i in range(win.month_combo.count())]
        print(f"  annees ({len(annees)}) : {' | '.join(annees[:4])} ...")
        print(f"  mois   ({len(mois)}) : {' | '.join(mois[:5])} ...")
        print(f"  affiche : {win.year_combo.currentText()} / "
              f"{win.month_combo.currentText()}")
        if win.year_combo.currentText() != "2026" or win.month_combo.currentText() != "Avril":
            raise AssertionError("les menus n'affichent pas avril 2026")
    except Exception as e:
        errors.append(("menus", str(e)))
        print(f"  menus ERREUR : {e}")

    print()
    if errors:
        print(f"FAILED : {pluriel(len(errors), 'erreur')}")
        for k, e in errors:
            print(f"  - {k} : {e}")
        return 1
    print("PASSED : toutes les vues + 5 periodes + le selecteur")
    return 0


if __name__ == "__main__":
    sys.exit(main())
