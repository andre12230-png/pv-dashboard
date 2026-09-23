# Gestion Photovoltaique

[![Version](https://badgen.net/github/release/andre12230-png/pv-dashboard/stable?label=version&color=blue)](https://github.com/andre12230-png/pv-dashboard/releases/latest)
[![Licence MIT](https://badgen.net/github/license/andre12230-png/pv-dashboard)](LICENSE)

Application de bureau gratuite (Windows 10/11) pour suivre une installation
photovoltaique en autoconsommation avec vente du surplus : production,
autoconsommation, injection, economies, revente EDF OA et remboursement de
l'installation. Donnees 100 % locales, open source (licence MIT).

Page de presentation : **[andre12230-png.github.io/pv-dashboard](https://andre12230-png.github.io/pv-dashboard/)**

## Installer l'application

Pas besoin d'etre informaticien, ni d'installer Python :

1. Telechargez l'installeur
   **[pv-dashboard-Setup.exe](https://github.com/andre12230-png/pv-dashboard/releases/latest/download/pv-dashboard-Setup.exe)**
   (il est aussi sur la [page des versions](https://github.com/andre12230-png/pv-dashboard/releases/latest),
   rubrique *Assets*).
2. Lancez-le. Aucun mot de passe administrateur n'est demande.
3. Windows peut afficher « Windows a protege votre ordinateur » : le
   programme n'est pas signe (un certificat coute plusieurs centaines
   d'euros par an). Cliquez sur **Informations complementaires**, puis
   **Executer quand meme**.
4. Lancez **Gestion Photovoltaique** depuis le menu Demarrer. Le tableau de
   bord indique les premiers pas : decrire votre installation, puis importer
   vos releves.

Vous preferez une version **portable**, sans installation ? Prenez le fichier
`.zip` sur la [page des versions](https://github.com/andre12230-png/pv-dashboard/releases/latest)
(rubrique *Assets*) : decompressez-le ou vous voulez (gardez tout le dossier
ensemble), puis double-cliquez `pv-dashboard\pv-dashboard.exe`. Vos donnees
vont, la aussi, dans votre dossier personnel (`%LOCALAPPDATA%\pv-dashboard`).

Vos donnees restent sur votre ordinateur : l'application ne contacte aucun
serveur. Pour la desinstaller : Parametres Windows > Applications. Vos donnees
sont conservees.

La suite de ce document s'adresse a qui veut comprendre les calculs ou
modifier le programme.

Ce que l'application suppose de votre installation :

- une installation en **autoconsommation avec vente du surplus** a EDF OA
  (l'annee OA suit la date de debut de VOTRE contrat) ;
- un compteur **Linky** (necessaire : c'est lui qui mesure l'injection) ;
- n'importe quel onduleur et n'importe quel fournisseur : les imports
  acceptent les exports de toutes les marques, voir « Une autre marque
  d'onduleur, un autre fournisseur ».

Rien n'est fige dans le programme : puissance, cout, dates et tarifs se
declarent dans la fenetre **Mes reglages** ou dans `config.yaml` (voir
**Premier demarrage** et **Configuration**), et la fenetre, la Notice et les
plafonds de saisie s'y adaptent.

La **version** de l'application s'affiche dans le titre de sa fenetre et en
bas du menu de gauche. Elle n'est ecrite qu'a un seul endroit du code,
`APP_VERSION` dans `app_desktop.py` ; le detail de chaque version figure dans
l'historique du depot.

## Premier demarrage

Rien n'est demande avant le premier lancement : sans fichier de releves,
l'application **le cree vide** et s'ouvre dessus. Trois etapes ensuite :

1. **Decrire l'installation** dans la fenetre **Mes reglages** : puissance,
   cout, dates du contrat, prix de rachat, fournisseur et ses prix, et la
   part de l'autoconsommation qui tomberait en heures creuses. Elle
   s'ouvre depuis le message d'accueil, la carte « Pour commencer » du
   tableau de bord ou le bouton **Modifier mes reglages** de l'onglet
   **Parametres**. L'application se recharge seule a l'enregistrement.
   La fenetre ne remplace dans `config.yaml` que les valeurs changees, a
   leur place : les commentaires restent, une copie datee part dans
   `backups\` (`config_avant-reglages_...`), et rien n'est ecrit si le
   fichier relu ne donne pas exactement ce qui etait voulu. Changer de prix
   ajoute une periode (l'ancienne est fermee la veille) au lieu d'ecraser
   l'historique. Le reste (TVA, grille EDF, prix unique d'avant) se regle
   toujours dans `config.yaml` avec le Bloc-notes.
2. **Faire entrer les releves** : onglet **Saisie quotidienne**, boutons
   **Importer...**, ou saisie a la main.
3. **Declarer ses factures**, facultatif : fenetre **Mes reglages**, section
   **Recalages sur mes factures** (ou directement `config-local.yaml`)
   ci-dessous.

Une configuration incomplete n'affiche plus un message de programmeur mais
la liste, en francais, de ce qu'il reste a renseigner.

## Lancement

Double-cliquez sur **`Lancer.vbs`** : aucune fenetre de terminal, l'app
s'ouvre directement.

Mode debug : **`Lancer.bat`** ouvre une console qui affiche les messages
et erreurs Python en direct.

Les deux lanceurs trouvent Python automatiquement via le Python Launcher
Windows (`py.exe` / `pyw.exe`, installe avec Python) — aucun chemin a
configurer.

**Une seule fenetre a la fois.** Un deuxieme lancement s'arrete sur un
avertissement au lieu d'ouvrir une seconde fenetre. Les deux liraient le meme
CSV au demarrage puis le reecriraient **en entier** a chaque enregistrement :
la derniere a enregistrer gagnerait, et les saisies faites dans l'autre
fenetre disparaitraient sans un mot. Le verrou est un petit fichier pose dans
le dossier temporaire de Windows ; il ne peut pas rester coince apres un
plantage, car il porte le numero du processus qui l'a pris.

### Version compilee (.exe)

**`Construire-Exe.bat`** fabrique `dist\pv-dashboard\pv-dashboard.exe`
(environ 280 Mo, deux minutes de construction). Il demarre en ~6 s contre
~11 s pour `Lancer.vbs`, et ne depend plus de l'installation Python.

L'executable lit les memes fichiers que les sources — `config.yaml`,
`config-local.yaml`, `Releves-pv.csv`, `backups\`, `pv-dashboard.ico` — en
remontant de deux dossiers depuis sa position. Il y a donc **un seul jeu de donnees**,
jamais deux copies qui divergent.

Consequence : **ne deplacez pas** `dist\pv-dashboard\` ailleurs sur le
disque, il ne retrouverait plus rien. Pour un acces commode, faites un
raccourci vers l'exe. Le dossier est entierement efface et reconstruit a
chaque appel du script : n'y rangez aucun fichier personnel.

**Dossier d'usage, separe du projet.** On peut aussi se servir de
l'application hors du projet : un dossier qui contient les donnees
(`config.yaml`, `config-local.yaml`, `Releves-pv.csv`, `backups\`) et, dedans,
le dossier `pv-dashboard\` du programme. L'exe trouve alors ses donnees un cran
au-dessus de lui (regle essayee avant celle des deux crans). C'est ainsi que
l'auteur s'en sert, dans un dossier a part ; pour passer a une
nouvelle version, on remplace seulement le sous-dossier `pv-dashboard\`.

En cas d'erreur au demarrage (config invalide, CSV introuvable), une
boite de dialogue affiche le probleme ; la trace complete est ecrite
dans **`pv-dashboard.log`** a cote de l'app.

### Installeur Windows (pour donner l'application)

Apres la construction de l'exe, **`py faire_installeur.py`** fabrique
`distribution\pv-dashboard-Setup-X.Y.Z.exe` (Inno Setup 6 requis ; recette :
`installeur\pv-dashboard.iss`). Il installe l'application sans mot de passe
administrateur dans `%LOCALAPPDATA%\Programs\pv-dashboard`, avec ses
raccourcis au menu Demarrer, et se desinstalle par Parametres > Applications.

Une fois installee, l'application range ses donnees **a part**, dans
`%LOCALAPPDATA%\pv-dashboard` : au premier lancement, elle y copie le
`config.yaml` modele (et `config-local.exemple.yaml`), dit ou le trouver et
cree le fichier de releves vide. Le raccourci **Dossier des donnees** du menu
Demarrer y mene. Une mise a jour ne remplace jamais une configuration deja
remplie, et une desinstallation laisse ce dossier en place.

L'exe construit dans le projet, lui, continue de lire les donnees du projet :
il les reconnait au `config.yaml` present deux dossiers au-dessus de lui.

L'app s'affiche toujours en **theme clair**, comme Pecule (le theme sombre a
ete retire en 1.32.0), et s'ouvre **toujours sur le mois en cours** : la periode n'est
volontairement pas memorisee, pour ne pas retrouver au lancement suivant
les chiffres d'un mois passe consulte la veille. A defaut de releve pour
le mois en cours, elle s'ouvre sur toute la periode.

### Choisir la periode

La barre du haut porte **‹ annee mois ›**. Les deux fleches reculent ou
avancent d'un cran — d'un mois quand un mois est affiche, d'une annee quand
c'est une annee, d'une annee OA quand c'est une annee OA — et se grisent
quand il n'y a plus rien de ce cote. Le menu des mois ne propose que les
mois qui portent des releves.

Le menu des annees porte aussi **Toute la periode** et les **annees OA**
(du 12 mai au 11 mai, par exemple) ; dans ces deux cas le menu des mois est
grise, puisque ces periodes-la sont a cheval sur les mois. Les dates exactes
d'une annee OA se lisent en survolant son entree dans le menu.

## Le menu de gauche

Les pages sont rangees en quatre sections — Principal, Contrats, Analyse,
Autres — chacune avec un pictogramme, separees par un filet. Deux n'apparaissent
que si elles vous concernent : **TVA autoconsommation** (section `tva_lasm`
remplie) et la **comparaison avec EDF** (fournisseur autre qu'EDF). Le bandeau reprend celui de Pecule : boutons rectangulaires, un
emoji devant chaque libelle, titres de section soulignes ; la page
affichee est le bouton surligne en bleu. En haut du
menu, la puissance et la date de debut du contrat OA ; en pied, le numero de
version.

## Vues disponibles

| Section | Contenu |
|---|---|
| Tableau de bord | Fraicheur des donnees ; jauge d'autoproduction ; production de la periode avec badge d'evolution sur l'an passe (memes dates) et mini-courbe ; barres « ou va votre soleil » / « d'ou vient votre electricite » (part du vehicule en legende) ; bilan financier avec icones ; barre « Installation remboursee » (meme calcul que la Synthese) ; production jour par jour (semaine par semaine sur un an, mois par mois au-dela) avec le meilleur jour en valeur |
| Saisie quotidienne | Tableau editable pour ajouter / corriger les releves du jour |
| Releves journaliers | Journal jour par jour : production, autoconsommee, injectee, achetee au reseau (et part du vehicule), recettes, depenses, bilan du jour ; ligne de totaux de la periode sous le tableau (a part, pour que le tri ne la deplace pas) |
| Repartition energie | Taux d'autoconsommation, couverture solaire et bilan ; diagramme de flux (Sankey) production/reseau -> injection/consommation ; detail par poste avec prix au kWh ; comparaison N vs N-1 |
| Synthese financiere | 6 postes (Vente OA, Prime, Economies, Facture, Investissement, Bilan global) + graphique « Remboursement de l'installation » (ce qu'elle a rapporte face a son cout, projection au rythme actuel). Le **bilan global** = ventes + economies + primes versees − cout de l'installation : la facture reseau n'y entre pas (on la paierait sans panneaux ; ce que les panneaux y changent est deja dans les economies). Meme calcul que la barre « Installation remboursee » du tableau de bord (`amortissement()`) |
| Annees OA | Recap par annee de contrat OA (de sa date de debut a la veille de son anniversaire) |
| TVA autoconsommation | Base de la livraison a soi-meme par annee civile (ligne 5A du 3517-S), TVA due, et recoupement des injections relevees avec les factures EDF OA. **N'apparait que si la section `tva_lasm` est remplie** : elle ne concerne que les producteurs assujettis a la TVA |
| Statistiques | Comparaisons annuelles, rendement kWh/kWc |
| Comparaison N vs N-1 | La periode choisie en haut (mois, annee, annee OA) vs la meme periode un an plus tot (periode en cours : memes dates de N-1) ; bouton « Une journee precise » pour comparer un jour donne |
| *Fournisseur* vs *reference* | Cout reel du contrat en cours vs simulation de l'offre de reference, options Base et HP/HC (depuis la bascule). Le libelle porte les noms declares en config : "Mon fournisseur vs EDF" avec le modele livre. **Masque quand le fournisseur declare est EDF** (`nom: "EDF"`) : comparer EDF a EDF n'a pas de sens |
| Notice | Mode d'emploi et glossaire des termes |
| Votre avis | Ouvre un court questionnaire en ligne dans le navigateur (probleme, idee), apres avoir copie la version. L'application n'envoie rien elle-meme. Une seule invitation, deux semaines apres le premier lancement |
| Parametres | Vue lecture seule de la configuration, et la liste des recalages actifs |

## Donnees

Toutes les donnees journalieres sont dans un seul fichier, cree
automatiquement au premier lancement s'il n'existe pas :
**`Releves-pv.csv`** (format FR : separateur `;`, decimales `,`, dates
DD/MM/YYYY, UTF-8).

Colonnes :

| Colonne | Source | Remarque |
|---|---|---|
| Date | — | Cle primaire, format DD/MM/YYYY |
| Prod_Jour | Onduleur (son application de suivi) | kWh produits dans la journee |
| Inj_Jour | Gestionnaire de reseau (Enedis) | kWh injectes au reseau |
| Conso_réseau_Jour | Gestionnaire de reseau (Enedis) | kWh soutires du reseau |
| Conso_HC | Fournisseur | Part heures creuses |
| Conso_HP | Fournisseur | Part heures pleines |

L'en-tete du fichier ecrit `Conso_réseau_Jour` **avec l'accent**. L'app
accepte aussi la forme sans accent, ainsi que `Conso_Jour`, `Soutirage` et
`Conso` : un CSV venu d'ailleurs n'a pas besoin d'etre renomme.

Cases vides autorisees. L'app gere le passage d'un prix unique (Base) aux
heures pleines / creuses en utilisant les colonnes HC/HP quand elles sont
remplies.

A chaque enregistrement depuis l'app, l'ecriture est atomique (une
interruption ne peut pas laisser un CSV a moitie ecrit) et **trois
filets** conservent l'etat precedent :

| Ou | Quoi |
|---|---|
| `Releves-pv.csv.bak` | la version juste avant le dernier enregistrement |
| `backups/Releves-pv_<date>_<heure>.csv` | les **15** dernieres versions |
| `backups/Releves-pv_jour_<date>.csv` | la premiere de chaque journee, **30** jours |

Les copies du jour echappent a la rotation des 15 : on peut donc revenir
plusieurs semaines en arriere, meme apres de nombreux enregistrements.
Pour restaurer, il suffit de copier le fichier voulu sur
`Releves-pv.csv` (l'app fermee). Le dossier `backups/` n'est pas
versionne : il contient les memes donnees personnelles que le CSV.

### Ajouter les donnees du jour

Ouvrez l'app → onglet **Saisie quotidienne**. Une ligne vide est
pre-remplie avec la date du jour suivant le dernier releve. Saisissez
vos valeurs (Tab pour passer de cellule en cellule), cliquez sur
**Enregistrer**. Les autres vues se rafraichissent automatiquement.
La ligne neuve laissee telle quelle n'est pas enregistree.

Ce qui est refuse a l'enregistrement, avec un message explicite :

- une **date incomplete** (`2026`, `08/2026`) ou inexistante (`31/02/2026`) :
  elle etait auparavant comprise comme le 1er janvier et **ecrasait** le
  releve de ce jour. Format attendu : `JJ/MM/AAAA` ;
- une valeur **negative**, ou `inf` / `nan` (qui contaminaient les totaux) ;
- une valeur **au-dela du plausible** : 150 kWh pour la consommation,
  et **10 kWh par kWc** pour la production et l'injection (60 kWh sur une
  installation de 6 kWc, 90 sur 9 kWc). Le plafond etait fige a 60 : une
  journee d'ete d'une installation plus grande etait refusee a tort.

Pour **effacer une journee**, videz toutes ses cases et enregistrez :
l'app demande confirmation, puis retire la ligne du fichier (une ligne
vide ferait un jour fantome a 0 kWh dans les statistiques).

### Importer conso et injection

Le bouton **Importer conso / injection...** (onglet Saisie quotidienne)
charge un releve quotidien de ce que le compteur a echange avec le reseau.
**Aucune obligation d'etre chez les memes fournisseurs que l'auteur** : tout
export "date + valeur" passe (voir plus bas). Les trois sources habituelles :

- **chez Enedis** (mon-compte-particulier.enedis.fr), l'**export d'index
  quotidiens** (`Export_<PRM>_Index_<periode>.xlsx`) : c'est le plus complet,
  et il est disponible **quel que soit votre fournisseur**. Il ne contient pas
  des consommations mais les **index du compteur** — l'application fait les
  soustractions elle-meme et en tire la conso reseau **et le detail heures
  creuses / heures pleines**. Si vous injectez, sa feuille d'index de
  production donne en plus votre **injection** : un seul fichier remplit
  quatre colonnes. Pour l'obtenir : *Ma consommation > Suivre ma
  consommation*, choisir **Index (kWh)** dans le menu de droite, puis
  *Telecharger le .xlsx* ;
- **chez Enedis** toujours, le **classeur Excel** officiel
  (`..._Export_energie_Consommation-Production_....xlsx`) : les feuilles
  Consommation et Production sont importees d'un coup (la "production" Enedis
  = l'injection au reseau), mais **sans** le detail HC/HP ;
- **chez votre fournisseur**, le **CSV "suivi de consommation"**
  (`suivi_conso_....csv` chez Octopus) : conso reseau **et detail heures
  creuses / heures pleines**. Malgre le numero de PRM dans son nom, ce fichier
  vient du fournisseur et non d'Enedis : il est d'ailleurs le seul a porter
  des colonnes en euros, qu'Enedis ne connait pas. L'app les ignore ;
- ou un **export CSV** d'une seule grandeur.

Vous pouvez aussi **fabriquer vous-meme** un CSV avec le detail HC/HP : une
colonne date en premier, puis deux colonnes nommees `Consommation HC (kWh)`
et `Consommation HP (kWh)` -- ou simplement `HC` et `HP`, ou encore
`Heures creuses` et `Heures pleines`. Les deux doivent etre presentes ; avec
une seule, l'application refuse et dit laquelle manque.

Le format est detecte automatiquement (lignes d'en-tete ignorees, dates
ISO ou FR, valeurs en Wh ou kWh, jours "NA" ignores). Fusion **sans
doublon** : les jours nouveaux sont ajoutes, les dates deja presentes
voient leur valeur remplacee par celle du fichier (seule la colonne
importee change — la production saisie a la main n'est jamais
touchee). Un recapitulatif est affiche avant d'appliquer, et les
sauvegardes decrites plus haut conservent l'etat precedent.

Deux garde-fous evitent qu'une grandeur atterrisse dans la mauvaise
colonne :

- le type (injection ou consommation) est lu **dans l'en-tete** du
  fichier, pas n'importe ou dedans ; si l'en-tete mentionne les deux
  (le classeur s'appelle "Consommation-Production"...), l'app **refuse
  de deviner** et le dit ;
- apres lecture, elle verifie que **l'injection ne depasse pas la
  production** du meme jour — c'est physiquement impossible, on
  n'injecte que le surplus. Au-dela de 10 % de jours douteux, un
  avertissement s'affiche avant le recapitulatif et le bouton par
  defaut devient « Non ».

### Importer la production

Le bouton **Importer la production...** (onglet Saisie quotidienne) remplit la
colonne Production a partir de l'export de l'onduleur. Avec un **Enphase**,
depuis le rapport officiel Enlighten :

1. sur enlighten.enphaseenergy.com : **Menu > Systeme > Rapports** ;
2. choisir **Energie mensuelle** et le mois voulu, puis **Rapport par
   email** ;
3. enregistrer la piece jointe recue (`.csv` ou `.zip`, peu importe) ;
4. dans l'app : **Importer la production...** et choisir ce fichier.

Le rapport donne la production toutes les 15 minutes : l'app **totalise
par jour** et arrondit au dixieme, comme l'affichage Enlighten. La
**journee en cours est ignoree** (le rapport s'arrete a l'heure de sa
generation, elle serait sous-evaluee).

Memes garanties que l'autre import : fusion sans doublon, seule la
colonne Prod_Jour est modifiee, recapitulatif avant d'appliquer et
ancienne version conservee dans `Releves-pv.csv.bak`.

#### Le rapport mensuel d'un portail d'onduleur

Le meme bouton accepte le **classeur Excel** que publient les portails
d'onduleurs (« rapport de centrale » chez Huawei FusionSolar, formes
voisines ailleurs) : une ligne par jour, une vingtaine de colonnes.

Il apporte **plus que la production**. Avant la mise en service du
compteur, le gestionnaire de reseau n'a aucun releve : l'application doit
alors **estimer** l'autoconsommation de ces journees. Or l'onduleur, lui,
mesurait deja. Le rapport donne ses colonnes **Production PV**,
**Exportation** et **Importation**, et ces journees cessent d'etre
estimees. Quelques semaines chez la plupart, une saison entiere chez qui
attend longtemps son raccordement.

Une regle protege les donnees du reseau : l'injection et la consommation
du rapport **ne remplissent que les cases vides**. La ou Enedis a releve
quelque chose, c'est lui qui fait foi et rien n'est remplace — ces
valeurs servent de base a la TVA sur l'autoconsommation. La production,
elle, n'a pas d'autre source que l'onduleur : elle est reprise
normalement. Le recapitulatif dit combien de journees ont ete laissees
telles quelles.

Deux verifications au passage : la colonne **Production totale** est un
cumul qui ne repart jamais a zero, elle n'est **jamais** lue (c'est
Production PV qui donne le jour) ; et l'**autoconsommation** annoncee par
le rapport doit valoir production moins exportation, sans quoi
l'application previent que les colonnes lues ne sont peut-etre pas les
bonnes.

### Une autre marque d'onduleur, un autre fournisseur

Les deux lecteurs ne connaissent pas de marque : ils acceptent **tout export
"date + valeur"**, verifie sur des exports type SolarEdge, Huawei et un
fournisseur autre qu'Octopus.

- dates **francaises** (`01/08/2026`) ou **ISO** (`2026-08-01`), avec ou sans
  heure ;
- valeurs en **Wh** ou en **kWh**, unite lue dans l'en-tete ou devinee ;
- separateur **`;`**, **`,`** ou **tabulation** ; lignes d'en-tete ignorees ;
- pas **infrajournalier totalise par jour** (15 minutes chez Enphase), ou
  releve deja quotidien.

Seule exigence pour la conso et l'injection : **l'en-tete doit dire de quelle
grandeur il s'agit** — un mot comme `consommation`, `soutirage`, `injection`
ou `production`. Sans cela l'application refuse d'importer plutot que de
ranger les valeurs dans la mauvaise colonne.

Ce qui n'a pas d'equivalent ailleurs : le **detail heures creuses / pleines**
au jour le jour, que tous les fournisseurs ne publient pas. Sans lui,
l'application estime la repartition a partir du ratio observe et le signale.

En France, l'**injection et la consommation** se recuperent de toute facon
chez le gestionnaire de reseau (Enedis), commun a tous les fournisseurs, des
lors que le compteur est un **Linky**.

## Installation

Prerequis : Python 3.10+ installe depuis [python.org](https://www.python.org)
(garder l'option **"Install launcher"** cochee — c'est lui que les
lanceurs utilisent).

```bash
py -m pip install -r requirements.txt
```

Lancement : double-clic sur `Lancer.vbs`, ou en ligne de commande :

```bash
py run.py
```

`run.py` et non `app_desktop.py` : c'est lui qui affiche l'ecran d'attente
pendant le chargement de pandas et de matplotlib, puis construit la fenetre
derriere.

## Tests

```bash
py -m pip install -r requirements-dev.txt   # pytest et ruff (une seule fois)
py -m pytest                                # tests unitaires (calculs + CSV)
py smoke_desktop.py                         # demarrage complet offscreen
py -m ruff check .                          # analyse statique
```

Les trois doivent passer avant un commit. La configuration de `ruff` est dans
`ruff.toml` : pycodestyle (E/W), pyflakes (F, les imports morts et les
variables jamais lues), bugbear (B) et tri des imports (I), avec deux
exceptions declarees pour les fichiers qui doivent importer apres du code.

## Configuration

**Deux fichiers**, l'un a cote de l'autre, relus a chaque lancement :

| Fichier | Contenu | Versionne |
|---|---|---|
| `config.yaml` | l'installation et les tarifs | oui |
| `config-local.yaml` | les totaux lus sur **vos factures** et les chemins propres a votre machine | **non** |

Le second est facultatif et **remplace le premier section par section** : on
n'y ecrit que ce qui lui est propre. Un modele commente est fourni,
`config-local.exemple.yaml` : recopiez-le sous le nom `config-local.yaml`
pour l'activer.

Pourquoi separer ? Les sections de recalage **reecrivent les releves
journaliers** pour retomber sur le total d'une facture. Livrees avec le
programme, elles s'appliquaient aux releves de qui recuperait
l'application : ses chiffres etaient faux, sans un mot. Un essai a blanc du
09/09/2026 le montrait -- 5 kWh saisis affiches 7,66, un total de 305 kWh
reecrit a 467. **Ne recopiez jamais les recalages de quelqu'un d'autre.**

Ce fichier n'etant plus protege par l'historique du depot, l'application en
garde une copie quotidienne dans `backups/` (les 30 dernieres).

### config.yaml

- `installation` : puissance, cout, dates. La **puissance** sert aussi au
  titre de la fenetre, a la Notice et au plafond de saisie (10 kWh par kWc :
  60 kWh sur 6 kWc, 90 sur 9 kWc)
- `oa` : prix d'achat surplus (€/kWh), prime autoconso (€/kWc, duree)
- `tarifs_reseau.bascule_hphc` : date du passage du prix unique aux heures
  pleines / creuses (chez l'auteur, un changement de fournisseur). Qui a
  toujours ete en heures creuses met sa date de mise en service ; qui est
  encore en prix unique met une date future. Absente : 01/01/2026
- `tarifs_reseau.bleu_base` : abonnement et historique des prix Bleu
  Base par periode. **Facultative** : sans elle, l'application considere
  qu'il n'y a rien eu avant la bascule
- `tarifs_reseau.contrat_hphc.nom` / `.offre` : nom de VOTRE fournisseur tel
  qu'il s'affiche — le court pour le menu de gauche, le long pour les titres
  (chez l'auteur : "Octopus" / "Octopus Go"). Idem pour `comparaison_edf`.
  Sans eux : "Mon contrat" et "Tarif de reference". Le bouton de
  comparaison du menu porte ces noms : "Mon fournisseur vs EDF" avec le
  modele livre
- `tarifs_reseau.contrat_hphc` : plages horaires HC, et `periodes` =
  abonnement + prix HP + prix HC pour chaque periode de prix (les
  fournisseurs revisent leur grille en cours de contrat : laissez
  `fin: null` sur la periode en cours et ajoutez-en une nouvelle a chaque
  changement). Cette section s'appelait autrefois `octopus_hphc` : un
  config.yaml qui porte encore l'ancien nom est lu sans changement
- `tarifs_reseau.comparaison_edf` : grille EDF Tarif Bleu de reference
  (le tarif reglemente, valable pour tous) utilisee par la vue de
  comparaison, en `periodes` elle aussi (abonnement, prix Base,
  prix HP, prix HC). EDF revise ses tarifs reglementes au 1er fevrier et
  au 1er aout : ajoutez une periode a chaque revision. Les prix se
  relevent sur particulier.edf.fr, guide "prix du kWh d'electricite",
  ligne 9 kVA -- attention, EDF les publie en **centimes**
- `tva_lasm` : grille servant a valoriser l'autoconsommation pour la TVA
  (voir « TVA sur l'autoconsommation » plus bas). `taux` = taux de TVA,
  `periodes` = une entree par periode tarifaire avec `prix_ht` (energie +
  acheminement, hors taxes) et `accise`, en €/kWh, releves sur les factures
  EDF. **Facultative** : sans elle, la vue TVA reste en veille. A completer a
  chaque evolution tarifaire, en general le 1er fevrier et le 1er aout
- `sources.releves_csv` : chemin du CSV de releves

### config-local.yaml (personnel, non versionne)

- `sources.conso_reseau_facturee` : totaux de consommation lus sur les
  factures EDF, pour les periodes ou le detail quotidien n'existe plus
  chez Enedis (optionnel)
- `sources.conso_reseau_recalee` : totaux factures servant a recaler
  des consommations saisies arrondies au kWh entier (optionnel)
- `sources.conso_reseau_douteuse` : periodes dont la valeur saisie n'est
  pas fiable et doit etre reconstituee (optionnel)
- `sources.injection_facturee` : totaux d'injection lus sur les
  autofacturations annuelles EDF OA, servant a recaler l'injection
  quotidienne, annee OA par annee OA (optionnel)
- `sources.recharges_ve_json` : chemin du `recharges.json` de
  l'application **recharges-ve**, pour afficher la part du soutirage qui
  part dans la voiture (optionnel, lu seulement)

## Annee OA

Le cycle OA commence a la **date de debut de votre contrat** et dure un an.
Par exemple, pour un contrat qui debute le 1er juillet 2024 :

- Annee OA #1 : 01/07/2024 → 30/06/2025
- Annee OA #2 : 01/07/2025 → 30/06/2026
- etc.

EDF OA verse une fois par an la somme correspondant a la production
injectee pendant ce cycle × tarif OA fixe.

## TVA sur l'autoconsommation

Cette partie ne concerne que les producteurs **assujettis a la TVA**
(entreprise individuelle, regime reel simplifie). Elle est facultative :
sans la section `tva_lasm` dans `config.yaml`, la vue reste en veille.

### La regle

Contrat S21 en obligation d'achat, vente de surplus :

- les **ventes a EDF OA sont autoliquidees** (art. 283-2 quinquies du CGI).
  C'est EDF qui declare leur TVA ; le producteur n'en collecte aucune. La
  **prime a l'autoconsommation est hors champ** ;
- seule l'electricite **produite ET consommee sur place** est taxable. C'est
  une **livraison a soi-meme** (LASM, art. 257-II-1-1° du CGI), a porter
  **ligne 5A** de la declaration annuelle **CA12 / 3517-S** ;
- la **base** = kWh autoconsommes × prix d'achat HT d'une electricite
  similaire (art. 266-1-c), c'est-a-dire **son propre tarif** : part
  fourniture + acheminement HT, plus l'**accise** sur l'electricite.
  **Hors TVA et hors abonnement** — l'abonnement n'est pas un prix au kWh ;
- la periode declaree est l'**annee civile**.

Methode confirmee par ecrit par un service des impots des entreprises (SIE)
en septembre 2026, qui renvoie aux releves du producteur pour les
quantites.

### D'ou viennent les chiffres

Des **releves quotidiens de `Releves-pv.csv`, pris tels quels** : ni
estimation des jours manquants, ni recalage sur les factures EDF OA. Ces
corrections ameliorent les chiffres affiches partout ailleurs dans
l'application, mais une declaration fiscale doit reposer sur les quantites
reellement relevees, pas sur des valeurs reconstituees.

Consequence assumee : un jour sans releve d'injection compte **toute** sa
production en autoconsommation, ce qui **majore** la base. Leur nombre est
affiche, et la vue le signale.

### Jour par jour, pas en moyenne

Chaque kWh autoconsomme est valorise au tarif en vigueur **le jour meme**.
Une moyenne annuelle donnerait un chiffre different, et faux : les tarifs
changent en cours d'annee (1er fevrier, 1er aout) alors que
l'autoconsommation, elle, se concentre sur l'ete. Le « prix moyen pondere »
affiche n'est donc pas un tarif : c'est la moyenne qui **ressort** de ce
calcul.

### Le controle avec les factures EDF OA

C'est lui qui rend les chiffres opposables. La somme des injections relevees
est comparee, **annee de contrat par annee de contrat**, aux kWh reellement
factures par EDF OA — un document que le producteur n'ecrit pas lui-meme,
etabli sur l'index du compteur de production. Chez l'auteur, l'ecart tient
**sous 1 %**.

Ce controle-la, et lui seul, complete d'abord les jours sans releve par leur
estimation mensuelle : sans quoi une semaine de panne Linky ferait crier au
loup. Le nombre de jours ainsi estimes est affiche a cote de l'ecart.

Les totaux factures se declarent dans `sources.injection_facturee`
(`config-local.yaml`). Sans eux, la colonne de controle reste vide.

### L'annee en cours

Elle est **projetee** jusqu'au 31/12 et marquee « estime » partout : dans le
tableau, sur le graphique (barre hachuree) et en note. La projection part de
la part d'autoconsommation que les annees passees avaient deja atteinte **a
la meme date**, et applique cette part moyenne au realise. Ce n'est pas un
montant a declarer ; il se fige une fois l'annee terminee.

Une annee est consideree comme close quand les releves vont jusqu'a son
31 decembre — annee terminee n'est pas annee complete.

### Les montants deja deposes

Une fois une annee declaree, ses chiffres ne doivent plus bouger. Chez
l'auteur, un test non publie (`tests/test_tva_deposee.py`, exclu du depot
par `.gitignore`) les recalcule sur ses vrais releves : si un changement de
code les fait bouger un jour, le test tombe. Faites de meme avec les votres.

## Hypotheses de calcul

- **Autoconso** = Production − Injection (>= 0)
- **Conso totale** = Autoconso + Soutirage reseau
- **Economie d'autoconso** = kWh autoconsommes × prix achat reseau du
  moment. Avant la bascule en heures pleines / creuses : prix Base de la
  date. Apres : prix HP/HC pondere par `part_hc_autoconso` (config, ou la
  case « Autoconsommation en heures creuses » de **Mes reglages**, en %), la
  part d'autoconso qui tomberait en heures creuses — l'autoconso etant
  diurne, elle est faible, sauf plage creuse l'apres-midi. Absente du
  fichier, elle vaut 20 %
- **Bilan net** (tableau de bord, pastille) = Vente OA + Economies − Facture
  reseau. La prime, versee une fois par an a l'anniversaire OA, est comptee
  a part dans la Synthese financiere et les Annees OA
- **Prime a l'autoconsommation** : comptee seulement quand l'annee OA
  concernee est **terminee** (EDF OA facture a la date anniversaire, donc
  apres coup). L'annee en cours est affichee « a venir » dans les Annees OA
  sans entrer dans son bilan
- **ROI** = (investissement − prime totale) ÷ gains **recurrents** annuels
  (vente OA + economies). La prime n'etant versee que sur 5 ans, elle est
  deduite du capital a amortir au lieu d'etre comptee comme un revenu qui
  se repete. Le calcul suppose des gains maintenus au rythme observe
- **Avant le debut du contrat OA** : pas de vente (contrat pas encore
  actif), meme pour l'injection estimee de cette periode
- **Jours sans releve d'injection** (avant le contrat, ou panne du Linky
  dont les donnees ne sont plus disponibles chez Enedis) : injection
  estimee via le ratio injection/production du meme mois observe sur les
  jours complets ; autoconso et conso recalees. Le CSV n'est pas modifie,
  ces jours restent signales dans l'app
- **Injection recalee sur les factures EDF OA** (facultatif,
  `sources.injection_facturee`) : le detail quotidien vient d'Enedis, mais
  EDF OA paie sur l'index du compteur de production, releve une seule fois
  par an. Les deux different de quelques dixiemes de pour-cent selon
  l'annee. L'app multiplie tous les jours d'une annee OA facturee par un
  meme facteur pour retomber sur le total paye, sans jamais faire depasser
  l'injection d'un jour au-dessus de sa production. **Le total de chaque
  annee OA est celui de la facture, le detail quotidien reste approche.**
  L'annee en cours, pas encore facturee, n'est pas recalee. CSV intact
- **Injection d'avant-contrat** : entre la mise en service et le debut du
  contrat, personne n'achete l'injection, mais le compteur de production la
  compte deja. Son index au premier jour du contrat peut servir de tranche
  de recalage comme les autres. Aucun euro en jeu : c'est l'autoconso
  affichee de cette periode qui en devient juste
- **Consommations arrondies** (facultatif, `sources.conso_reseau_recalee`) :
  des consommations saisies au kWh entier perdent leur partie decimale. L'app
  recale chaque tranche sur le total de la facture correspondante. L'ecart
  est reparti **a parts egales** s'il est positif (la decimale perdue vaut 0
  a 1 kWh quel que soit le jour) et **au prorata** s'il est negatif (l'exces
  vient des grosses valeurs). **Le total de la tranche est exact, le detail
  quotidien approche a ~1 kWh pres.** CSV intact
- **Jours a la valeur non fiable** (`sources.conso_reseau_douteuse`) : par
  exemple une panne du Linky dont les valeurs ont ete interpolees. Traites
  comme n'ayant pas de releve : les autres jours de la tranche sont corriges
  de leur troncature, puis ceux-ci recoivent le **solde** de la facture
- **Jours sans releve de consommation** : Enedis ne garde que **36 mois
  glissants**, le detail quotidien des debuts d'une installation ancienne
  n'existe plus. Les totaux se reprennent des **factures** et se declarent
  dans `config-local.yaml`, section `sources.conso_reseau_facturee` ; l'app
  les repartit sur les jours non releves. **Le total de chaque periode est
  exact, pas le detail quotidien.** Sans cela ces jours compteraient 0 kWh
  soutire : facture sous-evaluee et autoproduction affichee a 100 %. Le CSV
  n'est pas modifie, ces jours sont signales par un asterisque
- **Avant la bascule** (`bascule_hphc`) : prix unique (Base), pas de HP/HC
- **Apres la bascule** : heures pleines / creuses. Si les colonnes
  Conso_HC et Conso_HP sont renseignees pour un jour, le cout est calcule
  exactement ; sinon il est estime au prix moyen correspondant au **ratio
  HC reellement observe** sur les jours detailles, et non a la duree des
  plages sur 24 h qui supposerait une consommation uniforme jour et nuit
- **Changement de grille du fournisseur** : chaque periode de prix est
  gardee dans `config.yaml`, et chaque journee est facturee au prix de
  **sa** periode. Un nouveau tarif ne s'applique donc pas retroactivement
  aux mois precedents

## Fraicheur des donnees

Un bandeau en tete du Tableau de bord donne l'age de **chaque grandeur**
(production, injection, conso, HC/HP) : elles n'avancent pas ensemble,
Enphase publie le jour meme et Enedis avec environ deux jours de retard.
Au-dela de **3 jours** sur l'une d'elles, le bandeau passe en orange et
rappelle d'importer. La barre d'etat affiche la date du dernier releve
depuis n'importe quel onglet.

## Part du vehicule electrique

Si `sources.recharges_ve_json` pointe vers le `recharges.json` de
l'application **recharges-ve**, l'app affiche quelle part du soutirage
reseau part dans la voiture : legende de la barre « D'ou vient votre
electricite » au Tableau de bord, colonne « dont vehicule » dans les Releves
journaliers, sous-lignes « dont recharge
vehicule » / « dont reste du foyer » dans Repartition energie.

- Seules les recharges **a la maison** comptent : les recharges
  exterieures ne passent pas par votre compteur.
- Une charge de nuit (23:56 → 05:26) est **repartie entre les deux
  journees** au prorata du temps, pour rester comparable aux releves
  quotidiens Enedis.
- Le **cout** est celui calcule par recharges-ve (vraies plages horaires),
  pas une part du cout reseau moyen : la recharge se fait presque
  entierement en heures creuses, un prorata la surestimerait fortement.
- Le fichier de l'autre application est **seulement lu, jamais modifie**.
  Clé optionnelle : sans elle, ou si le fichier est absent, l'app
  fonctionne normalement sans afficher ces informations.

## Donnees 100 % locales

Tout tourne sur votre machine. Aucun fichier n'est envoye sur internet.

## Structure du projet

```
pv-dashboard/
│
│   -- ce qu'on lance --
├── run.py                # LANCEUR : ecran d'attente, puis l'application.
│                         #   C'est lui que lancent Lancer.vbs, Lancer.bat
│                         #   et Construire-Exe.bat, PAS app_desktop.py.
├── Lancer.vbs            # Lanceur silencieux (recommande)
├── Lancer.bat            # Lanceur debug (console visible)
├── Construire-Exe.bat    # Fabrique le dossier dist
├── faire_installeur.py   # Fabrique distribution\pv-dashboard-Setup-X.Y.Z.exe
├── installeur/
│   └── pv-dashboard.iss  #   Recette Inno Setup. Son AppId ne doit JAMAIS
│                         #   changer (reconnaissance des mises a jour)
│
│   -- le programme --
├── app_desktop.py        # MainWindow : chargement des donnees, verrou
│                         #   d'instance unique, assemblage des vues
├── app_data.py           # AppData : le jeu de donnees partage par les vues
├── calculations.py       # Calculs energetiques et financiers (pur metier)
├── data_loaders.py       # Lecture/ecriture Releves-pv.csv (atomique + .bak)
├── gui_theme.py          # Theme clair + QSS + style matplotlib
├── gui_widgets.py        # Widgets reutilisables (cards, KPI, pill...)
├── views/                # Une vue par fichier, une par section de l'app
│   ├── _base.py          #   BaseView commune
│   ├── _helpers.py       #   formatage FR + filtrage de periode
│   ├── _sankey.py        #   diagramme de flux, dessine au QPainter
│   ├── dashboard.py      #   Tableau de bord
│   ├── saisie.py         #   Saisie quotidienne
│   ├── transactions.py   #   Releves journaliers
│   ├── categories.py     #   Repartition energie
│   ├── accounts.py       #   Synthese financiere
│   ├── oa.py             #   Annees OA
│   ├── tva.py            #   TVA autoconsommation (LASM, ligne 5A)
│   ├── stats.py          #   Statistiques
│   ├── comparaison.py    #   Comparaison N vs N-1
│   ├── octopus_edf.py    #   Mon fournisseur vs EDF
│   ├── aide.py           #   Notice (mode d'emploi et glossaire)
│   └── settings.py       #   Parametres
│
│   -- les donnees (aucune n'est versionnee) --
├── config.yaml           # Parametres editables (versionne)
├── config-local.exemple.yaml  # Modele du fichier personnel
│                         #   (config-local.yaml, jamais versionne)
├── Releves-pv.csv        # Donnees, une ligne par jour
├── Releves-pv.csv.bak    # Etat juste avant le dernier enregistrement
├── backups/              # 15 copies horodatees + 30 quotidiennes
├── factures/             # Vos PDF de factures, si vous voulez les ranger
│                         #   la. Jamais lus par le programme : leurs totaux
│                         #   se recopient a la main dans config-local.yaml
│
│   -- verification et outillage --
├── tests/                # Tests unitaires pytest
├── smoke_desktop.py      # Test de bon demarrage (offscreen)
├── pytest.ini
├── ruff.toml             # Regles d'analyse statique
├── requirements.txt      # Dependances d'execution
├── requirements-dev.txt  # Developpement : pytest, ruff, pyinstaller
├── LICENSE               # Licence MIT
├── docs/                 # Page de presentation (GitHub Pages)
├── pv-dashboard.ico      # Icone de l'application
├── pv-dashboard.log      # Erreurs de demarrage (ecrit par l'app)
├── pv-dashboard.spec     # Engendre par PyInstaller, non versionne
└── README.md
```

Trois fichiers de vues portent un nom herite d'un ancien projet de comptes,
qui ne dit pas leur contenu : `transactions.py` est la vue **Releves
journaliers**, `categories.py` la **Repartition energie** et `accounts.py`
la **Synthese financiere**. La liste ci-dessus fait foi.
