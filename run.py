"""
Lanceur de l'application avec ecran de chargement.

Pourquoi ce fichier ?
    pandas et matplotlib mettent ~1.5 s a se charger. Lance directement,
    app_desktop.py laisse donc un ecran vide pendant tout ce temps. Ce lanceur
    cree d'abord une petite fenetre "Chargement..." (instantanee : elle ne
    depend que de PySide6), PUIS importe le reste et construit la fenetre
    derriere cet ecran. Le temps total est identique, mais l'application
    parait immediate au lieu de ne rien afficher.

Lancer :
    py run.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QDir, QLockFile, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox, QSplashScreen

WIN_APP_ID = "pvdashboard.gestion.6kwc"


def _base_dir() -> Path:
    """Le dossier du projet, en .py comme en .exe.

    Meme regle que resolve_base_dir() dans app_desktop.py, recopiee ici a
    dessein : ce lanceur doit pouvoir ecrire le journal AVANT d'importer
    app_desktop, qui met une seconde et demie a se charger (pandas,
    matplotlib). L'importer des maintenant retarderait l'ecran d'attente,
    qui est toute la raison d'etre de ce fichier.
    """
    if not getattr(sys, "frozen", False):
        return Path(__file__).parent
    # Dossier d'usage : les donnees un cran au-dessus de l'exe.
    # Exe construit dans le projet : deux crans au-dessus.
    # Exe installe par le Setup : dossier personnel dans %LOCALAPPDATA%.
    programme = Path(sys.executable).parent
    for dossier in (programme.parent, programme.parent.parent):
        if (dossier / "config.yaml").exists():
            return dossier
    racine = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    return (Path(racine) if racine else Path.home()) / "pv-dashboard"


LOG_PATH = _base_dir() / "pv-dashboard.log"


def _set_windows_app_id() -> None:
    """Barre des taches : icone de l'app et non celle de Python. Avant QApplication."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(WIN_APP_ID)
    except (OSError, AttributeError):
        pass


def _make_splash() -> QSplashScreen:
    """Ecran de chargement simple : panneau sombre, barre d'accent et titre."""
    w, h = 460, 250
    pix = QPixmap(w, h)
    pix.fill(QColor("#0f172a"))

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    # Barre d'accent en haut (couleur "production" du tableau de bord).
    painter.fillRect(0, 0, w, 6, QColor("#f5a524"))

    painter.setPen(QColor("#f8fafc"))
    title_font = QFont()
    title_font.setPointSize(20)
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.drawText(0, 80, w, 40, Qt.AlignHCenter, "Gestion Photovoltaique")

    painter.setPen(QColor("#94a3b8"))
    sub_font = QFont()
    sub_font.setPointSize(11)
    painter.setFont(sub_font)
    painter.drawText(0, 124, w, 26, Qt.AlignHCenter, "Tableau de bord solaire")
    painter.end()

    splash = QSplashScreen(pix)
    splash.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    return splash


def _message(splash: QSplashScreen, app: QApplication, text: str) -> None:
    splash.showMessage(f"   {text}", Qt.AlignBottom | Qt.AlignLeft,
                       QColor("#cbd5e1"))
    app.processEvents()


def _log_traceback() -> None:
    """Ecrit la trace dans le fichier log (stdout peut etre absent sous pythonw)."""
    import traceback
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            traceback.print_exc(file=fh)
    except OSError:
        pass


def prendre_le_verrou(chemin: str | None = None) -> QLockFile | None:
    """Verrou d'instance unique : rend le QLockFile, ou None s'il est pris.

    Meme verrou (meme fichier) que prendre_le_verrou() dans app_desktop.py,
    recopie ici pour la meme raison que _base_dir() : il doit etre pris
    AVANT d'importer app_desktop, lent a charger.

    Il manquait ici jusqu'en 1.30.0 : seul le lancement direct de
    app_desktop.py le prenait, or l'exe, Lancer.vbs et Lancer.bat passent
    tous par ce fichier. Deux fenetres pouvaient donc s'ouvrir et la derniere
    a enregistrer effacait les saisies de l'autre.
    """
    chemin = chemin or os.path.join(QDir.tempPath(), "pv-dashboard.lock")
    verrou = QLockFile(chemin)
    # 0 = pas de peremption par le temps ; un verrou laisse par un plantage
    # est repris grace au numero de processus qu'il contient.
    verrou.setStaleLockTime(0)
    return verrou if verrou.tryLock(100) else None


def main() -> int:
    _set_windows_app_id()
    app = QApplication.instance() or QApplication(sys.argv)

    # Garde dans une variable jusqu'a la fin : relache, il ne protege plus.
    verrou = prendre_le_verrou()
    if verrou is None:
        QMessageBox.warning(
            None, "Gestion Photovoltaique",
            "Gestion Photovoltaique est déjà ouvert.\n\n"
            "Deux fenêtres ouvertes en même temps se réécrivent le même "
            "fichier de relevés : la dernière enregistrée effacerait les "
            "saisies de l'autre.\n\n"
            "Utilisez la fenêtre déjà ouverte.")
        return 1

    splash = _make_splash()
    splash.show()
    _message(splash, app, "Chargement des bibliotheques...")

    # Imports lourds (pandas, matplotlib, vues) APRES l'affichage du splash.
    try:
        import app_desktop
        app_desktop.configure_application(app)
        _message(splash, app, "Preparation des donnees...")
        win = app_desktop.create_window()
    except Exception as exc:  # frontiere applicative : tout doit etre signale
        _log_traceback()
        # Les erreurs que l'application leve elle-meme (configuration
        # incomplete, fichier mal ecrit) portent deja une phrase redigee pour
        # l'utilisateur : la faire preceder de "RuntimeError :" ne l'aide en
        # rien. Les autres, imprevues, gardent leur nom technique - c'est ce
        # qui permettra de les identifier.
        if isinstance(exc, RuntimeError):
            detail = str(exc)
        else:
            detail = f"{type(exc).__name__} : {exc}"
        QMessageBox.critical(
            None,
            "Gestion Photovoltaique",
            "Impossible de démarrer l'application.\n\n"
            f"{detail}\n\n"
            f"Trace complète dans {LOG_PATH.name}.",
        )
        return 1

    splash.finish(win)
    win.show()
    # Apres le splash : affiche avant, le message passerait sous lui.
    app_desktop.annoncer_premier_lancement(win)
    # L'unique invitation « Votre avis », deux semaines apres le premier
    # lancement (voir avis.py).
    win.inviter_a_donner_son_avis()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
