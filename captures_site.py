"""Captures de la page de presentation, sur un jeu de demonstration INVENTE.

Aucune donnee reelle : un dossier temporaire, l'installation d'exemple du
config.yaml du depot (3 kWc, 9 000 EUR, OA depuis le 01/01/2024) et des
releves journaliers tires au hasard (graine fixe : memes chiffres a chaque
fois), du 01/01/2024 a hier. Les captures (1360 x 858, barre d'etat retiree :
elle affiche le chemin du dossier) sont ecrites dans le dossier donne en
argument ; on les regarde, puis on les copie dans docs/media.

    py captures_site.py dossier_de_sortie

La fenetre s'affiche quelques secondes a l'ecran pendant les captures (hors
ecran, Qt efface une partie du texte). Les preferences de la fenetre vont
dans un fichier jetable : celles de l'utilisateur ne sont pas touchees.
"""

import math
import random
import shutil
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

PROJET = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJET))
SORTIE = Path(sys.argv[1])
SORTIE.mkdir(parents=True, exist_ok=True)
DEMO = Path(tempfile.mkdtemp(prefix="captures_pv_"))

# --- installation d'exemple : le modele livre avec l'application ---
shutil.copy2(PROJET / "config.yaml", DEMO / "config.yaml")

# --- releves inventes ---
# Production moyenne d'un jour, en kWh par kWc, mois par mois : environ
# 980 kWh/kWc sur l'annee, dans la moyenne francaise.
PROD_PAR_KWC = [1.1, 1.7, 2.6, 3.4, 3.9, 4.2, 4.3, 3.8, 3.0, 2.0, 1.2, 0.9]
KWC = 3.0
hasard = random.Random(2026)


def nombre(x: float) -> str:
    """3,142 : la virgule decimale du CSV."""
    return f"{x:.3f}".replace(".", ",")


lignes = ["Date;Prod_Jour;Inj_Jour;Conso_réseau_Jour;Conso_HC;Conso_HP"]
jour, hier = date(2024, 1, 1), date.today() - timedelta(days=1)
while jour <= hier:
    # Meteo du jour : de tres couvert a grand soleil.
    meteo = min(1.35, max(0.15, hasard.gauss(0.95, 0.3)))
    prod = PROD_PAR_KWC[jour.month - 1] * KWC * meteo
    # Maison d'environ 4 000 kWh par an, davantage l'hiver.
    saison = math.cos(2 * math.pi * (jour.timetuple().tm_yday - 15) / 365)
    conso = max(5.0, 11 + 4 * saison + hasard.gauss(0, 1.5))
    autoconso = min(prod * hasard.uniform(0.32, 0.48), conso * 0.6)
    soutirage = conso - autoconso
    hc = soutirage * hasard.uniform(0.40, 0.55)
    lignes.append(";".join([
        jour.strftime("%d/%m/%Y"), nombre(prod), nombre(prod - autoconso),
        nombre(soutirage), nombre(hc), nombre(soutirage - hc)]))
    jour += timedelta(days=1)
(DEMO / "Releves-pv.csv").write_text("\n".join(lignes) + "\n", encoding="utf-8")
print("jeu :", len(lignes) - 1, "jours, dans", DEMO)

# --- l'application, tournee vers le dossier de demonstration ---
import app_desktop  # noqa: E402

app_desktop.BASE_DIR = DEMO
app_desktop.CONFIG_PATH = DEMO / "config.yaml"
app_desktop.CONFIG_LOCAL_PATH = DEMO / "config-local.yaml"   # absent : c'est voulu

from PySide6.QtCore import QEvent, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

application = QApplication(sys.argv)
app_desktop.configure_application(application)
donnees = app_desktop.build_dataset(app_desktop.load_config())
reglages = QSettings(str(DEMO / "preferences.ini"), QSettings.Format.IniFormat)
w = app_desktop.MainWindow(donnees, settings=reglages)
w.statusBar().hide()
w.resize(1360, 858)
w.show()


def attendre(secondes: float = 1.5):
    """Laisse la page finir de se dessiner.

    Une page qui se redessine marque ses anciennes cartes « a effacer »
    (deleteLater). Dans l'application, la boucle de Qt les efface aussitot ;
    ici, sans cette boucle, il faut le demander (DeferredDelete), sinon elles
    restent en surimpression sur la capture.
    """
    fin = time.monotonic() + secondes
    while time.monotonic() < fin:
        application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        application.processEvents()
        time.sleep(0.02)


attendre()
annee_passee = f"year-{hier.year - 1}"
for nom, vue, periode in (
        ("capture_1_tableau_de_bord", "dashboard", None),    # le mois en cours
        ("capture_2_synthese", "accounts", "all"),
        ("capture_3_repartition", "categories", annee_passee),
        ("capture_4_statistiques", "stats", "all")):
    w._switch_view(vue)
    if periode:
        w._appliquer_periode(periode)
    attendre()
    w.grab().save(str(SORTIE / f"{nom}.png"))
    print(nom, "OK")
w.close()
reglages.sync()      # la fermeture ecrit la taille de la fenetre : avant le menage
shutil.rmtree(DEMO, ignore_errors=True)
