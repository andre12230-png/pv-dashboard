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

# --- releves inventes (graine fixe, du 01/01/2024 a hier) ---
from demo_releves import ecrire_releves_demo  # noqa: E402

hier = date.today() - timedelta(days=1)
print("jeu :", ecrire_releves_demo(DEMO / "Releves-pv.csv", fin=hier), "jours, dans", DEMO)

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
