"""Le titre d'une boite de message dit de quoi il s'agit (charte).

Modele de tests/test_titres_des_boites.py de Recharges VE (08/10/2026) : un
titre vague (« Erreur », « Attention ») ne dit ni ce qui a echoue ni quoi
faire. Le test lit le code de l'interface.

    py -m pytest tests/test_titres_des_boites.py
"""

from __future__ import annotations

import re
from pathlib import Path

PROJET = Path(__file__).resolve().parent.parent
TITRE_VAGUE = re.compile(
    r'''QMessageBox\.\w+\(\s*[\w.]+,\s*"(Erreur|Attention|Information|Saisie)"''')


def test_aucun_titre_vague():
    fautes = []
    for p in [PROJET / "app_desktop.py", *PROJET.glob("views/*.py"),
              PROJET / "fenetre_reglages.py", PROJET / "avis.py",
              PROJET / "mise_a_jour.py"]:
        texte = p.read_text(encoding="utf-8")
        for m in TITRE_VAGUE.finditer(texte):
            ligne = texte.count("\n", 0, m.start()) + 1
            fautes.append(f"{p.name}:{ligne} « {m.group(1)} »")
    assert not fautes, fautes
