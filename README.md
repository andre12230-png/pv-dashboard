# Gestion Photovoltaïque

[![Version](https://badgen.net/github/release/andre12230-png/pv-dashboard/stable?label=version&color=blue)](https://github.com/andre12230-png/pv-dashboard/releases/latest)
[![Licence MIT](https://badgen.net/github/license/andre12230-png/pv-dashboard)](LICENSE)

Application de bureau gratuite (Windows 10/11) pour suivre une installation
photovoltaïque : production, autoconsommation, injection, économies, vente
(surplus ou totale, à EDF OA ou à un autre acheteur, ou pas de vente du tout)
et remboursement de l'installation. Données 100 % locales, open source (licence MIT).

Page de présentation : **[andre12230-png.github.io/pv-dashboard](https://andre12230-png.github.io/pv-dashboard/)**

[![Vidéo de présentation de Gestion Photovoltaïque (1 min 10) — cliquez pour la lancer](docs/media/video-apercu.jpg)](https://andre12230-png.github.io/pv-dashboard/#video)
*▶ Vidéo de présentation (1 min 10), sur la page de présentation. Réalisée avec des données d'exemple.*

## Installer l'application

Pas besoin d'être informaticien, ni d'installer Python :

1. Téléchargez l'installeur
   **[pv-dashboard-Setup.exe](https://github.com/andre12230-png/pv-dashboard/releases/latest/download/pv-dashboard-Setup.exe)**
   (il est aussi sur la [page des versions](https://github.com/andre12230-png/pv-dashboard/releases/latest),
   rubrique *Assets*).
2. Lancez-le. Aucun mot de passe administrateur n'est demandé.
3. Windows peut afficher « Windows a protégé votre ordinateur » : le
   programme est encore peu téléchargé et n'est pas signe, ce qui ne veut
   pas dire qu'il est dangereux. Cliquez sur **Informations complémentaires**, puis
   **Exécuter quand même**.
4. Lancez **Gestion Photovoltaïque** depuis le menu Démarrer. Le tableau de
   bord indique les premiers pas : décrire votre installation, puis importer
   vos relevés.

Vous préférez une version **portable**, sans installation ? Prenez le fichier
`.zip` sur la [page des versions](https://github.com/andre12230-png/pv-dashboard/releases/latest)
(rubrique *Assets*) : decompressez-le où vous voulez (gardez tout le dossier
ensemble), puis double-cliquez `pv-dashboard\pv-dashboard.exe`. Vos données
vont, là aussi, dans votre dossier personnel (`%LOCALAPPDATA%\pv-dashboard`).

Vos données restent sur votre ordinateur : l'application ne contacte aucun
serveur. Pour la désinstaller : Paramètres Windows > Applications. Vos données
sont conservees.

La suite de ce document s'adresse à qui veut comprendre les calculs ou
modifier le programme.

Ce que l'application suppose de votre installation :

- une installation en **autoconsommation avec vente du surplus**, en
  **vente totale**, ou **sans vente** ; l'acheteur est EDF OA par défaut, ou
  celui que vous nommez (l'année de contrat suit la date de début de VOTRE
  contrat) ;
- un compteur **Linky** : c'est lui qui mesure l'injection (sans relevé
  d'injection, toute la production est comptée comme consommée chez vous,
  et l'application le signale) ;
- n'importe quel onduleur et n'importe quel fournisseur : les imports
  acceptent les exports de toutes les marques, voir « Une autre marque
  d'onduleur, un autre fournisseur ».

Rien n'est figé dans le programme : puissance, coût, dates et tarifs se
déclarent dans la fenêtre **Mes réglages** ou dans `config.yaml` (voir
**Premier démarrage** et **Configuration**), et la fenêtre, la Notice et les
plafonds de saisie s'y adaptent.

La **version** de l'application s'affiche dans le titre de sa fenêtre et en
bas du menu de gauche. Elle n'est écrite qu'à un seul endroit du code,
`APP_VERSION` dans `app_desktop.py` ; seul le site (`softwareVersion` de
`docs/index.html`) la recopie, à remettre à jour à chaque sortie. Le détail
de chaque version figure dans l'historique du dépôt.

## Premier démarrage

Rien n'est demandé avant le premier lancement : sans fichier de relevés,
l'application **le crée vide** et s'ouvre dessus. Trois étapes ensuite :

1. **Décrire l'installation** dans la fenêtre **Mes réglages** : puissance,
   coût, dates du contrat, prix de rachat, fournisseur et ses prix, et la
   part de l'autoconsommation qui tomberait en heures creuses. Elle
   s'ouvre depuis le message d'accueil, la carte « Pour commencer » du
   tableau de bord ou le bouton **Modifier mes réglages** de l'onglet
   **Paramètres**. L'application se recharge seule à l'enregistrement.
   La fenêtre ne remplace dans `config.yaml` que les valeurs changées, à
   leur place : les commentaires restent, une copie datée part dans
   `backups\` (`config_avant-reglages_...`, les 30 plus récentes sont
   gardées), et rien n'est écrit si le
   fichier relu ne donne pas exactement ce qui était voulu. Changer de prix
   ajoute une période (l'ancienne est fermée la veille) au lieu d'écraser
   l'historique. Le reste (TVA, grille EDF, prix unique d'avant) se règle
   toujours dans `config.yaml` avec le Bloc-notes.
2. **Faire entrer les relevés** : onglet **Saisie quotidienne**, boutons
   **Importer...**, ou saisie à la main.
3. **Déclarer ses factures**, facultatif : fenêtre **Mes réglages**, section
   **Recalages sur mes factures** (ou directement `config-local.yaml`)
   ci-dessous.

Si la configuration est incomplète, l'application affiche la liste, en
français, de ce qu'il reste à renseigner.

## Lancement

Double-cliquez sur **`Lancer.vbs`** : aucune fenêtre de terminal, l'app
s'ouvre directement.

Mode debug : **`Lancer.bat`** ouvre une console qui affiche les messages
et erreurs Python en direct.

Les deux lanceurs trouvent Python automatiquement via le Python Launcher
Windows (`py.exe` / `pyw.exe`, installe avec Python) — aucun chemin à
configurer.

**Une seule fenêtre à la fois.** Un deuxième lancement s'arrête sur un
avertissement au lieu d'ouvrir une seconde fenêtre. Les deux liraient le même
CSV au démarrage puis le réécriraient **en entier** à chaque enregistrement :
la dernière à enregistrer gagnerait, et les saisies faites dans l'autre
fenêtre disparaîtraient sans un mot. Le verrou est un petit fichier pose dans
le dossier temporaire de Windows ; il ne peut pas rester coincé après un
plantage, car il porte le numéro du processus qui l'à pris.

### Version compilée (.exe)

**`Construire-Exe.bat`** fabrique `dist\pv-dashboard\pv-dashboard.exe`
(environ 280 Mo, deux minutes de construction). Il démarre en ~6 s contre
~11 s pour `Lancer.vbs`, et ne dépend plus de l'installation Python.

L'exécutable lit les mêmes fichiers que les sources — `config.yaml`,
`config-local.yaml`, `Releves-pv.csv`, `backups\`, `pv-dashboard.ico` — en
remontant de deux dossiers depuis sa position. Il y a donc **un seul jeu de données**,
jamais deux copies qui divergent.

Conséquence : **ne déplacez pas** `dist\pv-dashboard\` ailleurs sur le
disque, il ne retrouverait plus rien. Pour un accès commode, faites un
raccourci vers l'exe. Le dossier est entièrement efface et reconstruit à
chaque appel du script : n'y rangez aucun fichier personnel.

**Dossier d'usage, séparé du projet.** On peut aussi se servir de
l'application hors du projet : un dossier qui contient les données
(`config.yaml`, `config-local.yaml`, `Releves-pv.csv`, `backups\`) et, dedans,
le dossier `pv-dashboard\` du programme. L'exe trouve alors ses données un cran
au-dessus de lui (règle essayée avant celle des deux crans). C'est ainsi que
l'auteur s'en sert, dans un dossier à part ; pour passer à une
nouvelle version, on remplace seulement le sous-dossier `pv-dashboard\`.

En cas d'erreur au démarrage (config invalide, CSV introuvable), une
boîte de dialogue affiche le problème et le chemin complet de la trace,
**`pv-dashboard.log`**, écrite dans le dossier des données
(`%LOCALAPPDATA%\pv-dashboard` pour la version installée).

### Installeur Windows (pour donner l'application)

Après la construction de l'exe, **`py faire_installeur.py`** fabrique
`distribution\pv-dashboard-Setup-X.Y.Z.exe` (Inno Setup 6 requis ; recette :
`installeur\pv-dashboard.iss`). Il installe l'application sans mot de passe
administrateur dans `%LOCALAPPDATA%\Programs\pv-dashboard`, avec ses
raccourcis au menu Démarrer, et se désinstalle par Paramètres > Applications.

Une fois installée, l'application range ses données **à part**, dans
`%LOCALAPPDATA%\pv-dashboard` : au premier lancement, elle y copie le
`config.yaml` modèle (et `config-local.exemple.yaml`), crée le fichier de
relevés vide et propose de remplir la fenêtre « Mes réglages » (ou plus tard). Le raccourci **Dossier des données** du menu
Démarrer y mene. Une mise à jour ne remplace jamais une configuration déjà
remplie, et une désinstallation laisse ce dossier en place.

L'exe construit dans le projet, lui, continue de lire les données du projet :
il les reconnaît au `config.yaml` présent deux dossiers au-dessus de lui.

L'app s'affiche en **thème clair** par défaut, comme Pécule. Un **thème
sombre** se choisit dans **Paramètres › Apparence** (Clair / Sombre) et
s'applique au prochain démarrage ; l'app ne suit jamais le thème de Windows.
Elle s'ouvre **toujours sur le mois en cours** : la période n'est
volontairement pas mémorisée, pour ne pas retrouver au lancement suivant
les chiffres d'un mois passé consulté la veille. À défaut de relevé pour
le mois en cours, elle s'ouvre sur toute la période.

### Choisir la période

La barre du haut porte **‹ année mois ›**. Les deux flèches reculent ou
avancent d'un cran — d'un mois quand un mois est affiché, d'une année quand
c'est une année, d'une année OA quand c'est une année OA — et se grisent
quand il n'y a plus rien de ce côté. Le menu des mois ne propose que les
mois qui portent des relevés.

Le bouton **Ce mois-ci** ramène au mois en cours (ou au dernier mois
relevé, tant que le mois en cours n'à rien) ; il est grise quand on y est
déjà. Au clavier : **Ctrl+←** et **Ctrl+→** pour la période précédente ou
suivante, **Ctrl+Origine** pour revenir au mois en cours. Sur les pages qui
ne dépendent pas de la période, le sélecteur entier est grise. Sur les
**Statistiques**, qui comparent toujours toutes les années, le menu des
mois disparaît et le bouton devient **Cette année**.

Le menu des années porte aussi **Toute la période** et les **années OA**
(du 12 mai au 11 mai, par exemple) ; dans ces deux cas le menu des mois ne
propose que **Toute l'année**, puisque ces périodes-là sont à cheval sur les mois. Les dates exactes
d'une année OA se lisent en survolant son entrée dans le menu. Avec un
autre acheteur qu'EDF OA (`oa.acheteur`), l'application parle partout
d'**années de contrat** (« Année de contrat n° 3 ») au lieu d'années OA.

## Le menu de gauche

Les pages sont rangées en cinq sections — Principal, Analyse, Mes données
(sauvegarde externe), Réglages, Aide (notice, votre avis, mise à jour), dans
l'ordre de Pécule — chacune avec un pictogramme, séparées par un filet. Les
pages qui servent de temps en temps (années de contrat, TVA, comparaison avec
l'an passé et avec un autre fournisseur) sont réunies sous un seul bouton,
**🗂️ Bilans et comparaisons…**, qui les propose dans un petit menu : le menu
tient ainsi sans défiler sur un portable 1366 × 768. Il défile si la fenêtre
est plus basse encore. Trois pages n'apparaissent que si elles vous
concernent : **Années OA** (si vous vendez votre électricité
et que la date de début du contrat est renseignée : masquée avec
`oa.type: aucune` ; « Années de contrat » avec un autre acheteur qu'EDF OA),
**TVA autoconsommation** (section `tva_lasm`
remplie) et la **comparaison avec EDF** (fournisseur autre qu'EDF).

Le bandeau reprend celui de Pécule : boutons rectangulaires, un emoji devant
chaque libellé, titres de section soulignés ; la page affichée est le bouton
surligné en bleu. En haut du
menu, le nom de l'application et ce qu'elle apporte (« Ce que rapportent vos
panneaux »), comme dans les deux autres applications ; en pied, le numéro de
version. La puissance de l'installation se lit dans le titre de la fenêtre.

## Vues disponibles

| Section | Contenu |
|---|---|
| Tableau de bord | Fraîcheur des données ; tuiles « Autoproduction » (jauge) et « Production » (période avec badge d'évolution sur l'an passé (mêmes dates) et mini-courbe) ; carte « Circulation de l'énergie » : barres « où va votre soleil » / « d'où vient votre électricité » (part du véhicule en légende) ; bilan financier avec icônes ; carte « Remboursement de l'installation » (même calcul que la Synthèse) ; production jour par jour (semaine par semaine sur un an, mois par mois au-delà) avec le meilleur jour en valeur ; le mois de mise en service et la période en cours, incomplets, sont **hachures** et ne comptent jamais comme meilleur mois |
| Saisie quotidienne | Tableau éditable pour ajouter / corriger les relevés du jour. Ce qui est tapé et pas encore enregistré survit à un changement d'onglet ; avant de fermer l'application, d'ouvrir « Mes réglages » ou d'importer un fichier, une question évite de le perdre sans un mot |
| Relevés journaliers | Journal jour par jour : production, autoconsommée, injectée, achetée au réseau (et part du véhicule), vente + économies, achat au réseau, bilan électricité ; ligne de totaux de la période sous le tableau (à part, pour que le tri ne la déplace pas) |
| Répartition énergie | Taux d'autoconsommation, couverture solaire et bilan ; diagramme de flux (Sankey) production/reseau -> injection/consommation ; détail par poste avec prix au kWh ; comparaison avec l'année précédente |
| Synthèse financière | Jusqu'à 6 postes selon le contrat (Vente, Prime, Économies, Achat au réseau, Investissement, Bilan de l'installation) + graphique « Remboursement de l'installation » (ce qu'elle a rapporté face à son coût, projection au rythme actuel ; chaque versement de la prime, qui fait une marche dans la courbe, est marqué d'un point et le dernier porte l'étiquette « Prime à l'autoconsommation » avec son montant, ou « N versements de X € » s'il y en a eu plusieurs).
Avant un an de relevés, ni rythme annuel ni temps de retour : quelques mois
d'été ou d'hiver, prolongés sur un an, les fausseraient de plusieurs années). Le **bilan de l'installation** = vente + économies + primes versées − coût de l'installation : l'achat au réseau n'y entre pas (on la paierait sans panneaux ; ce que les panneaux y changent est déjà dans les économies). Même calcul que la carte « Remboursement de l'installation » du tableau de bord (`amortissement()`) |
| Années OA | Récap par année de contrat OA (de sa date de début à la veille de son anniversaire). L'année en cours et la première si elle est incomplète sont nommées « (en cours) » et « (partielle) », leurs barres hachurees. Devient **Années de contrat** avec un autre acheteur qu'EDF OA. **Masquée sans revente** (`oa.type: aucune`) |
| TVA autoconsommation | Base de la livraison à soi-même par année civile (ligne 5A du 3517-S), TVA due, et recoupement des injections relevées avec les factures EDF OA. **N'apparaît que si la section `tva_lasm` est remplie** : elle ne concerne que les producteurs assujettis à la TVA |
| Statistiques | Comparaisons annuelles, rendement kWh/kWc |
| Comparer à l'an passé | La période choisie en haut (mois, année, année OA) face à la même période un an plus tôt (période en cours : mêmes dates de N-1) ; bouton « Une journée précise » pour comparer un jour donne |
| *Fournisseur* ou *référence* | Coût réel du contrat en cours face à la simulation de l'offre de référence, options Base et HP/HC (depuis la bascule) ; mois incomplets hachures. Le libellé porte les noms déclarés en config : "Mon fournisseur ou EDF" avec le modèle livré. **Masqué quand le fournisseur déclaré est EDF** (`nom: "EDF"`) : comparer EDF à EDF n'à pas de sens |
| Notice | Mode d'emploi et glossaire des termes |
| Paramètres | Vue lecture seule de la configuration, et la liste des recalages actifs ; bouton « Modifier mes réglages » |

Trois boutons du menu ouvrent une fenêtre plutôt qu'une page :

- **💾 Sauvegarde externe** : copie les données sur une clé USB ou un disque
  choisi, vérifiée fichier par fichier. Un rappel s'affiche sur le tableau de
  bord au-delà de 30 jours sans sauvegarde.
- **🔄 Mise à jour** : affiche la version installée et ouvre, à la demande,
  la page de la dernière version dans le navigateur. L'application ne se
  connecte jamais à Internet, c'est vous qui comparez les numeros.
- **💬 Votre avis** : ouvre un court questionnaire en ligne dans le
  navigateur (problème, idée), après avoir copié la version. L'application
  n'envoie rien elle-même. Une seule invitation, deux semaines après le
  premier lancement.

## Données

Toutes les données journalières sont dans un seul fichier, créé
automatiquement au premier lancement s'il n'existe pas :
**`Releves-pv.csv`** (format FR : séparateur `;`, décimales `,`, dates
DD/MM/YYYY, UTF-8).

Colonnes :

| Colonne | Source | Remarque |
|---|---|---|
| Date | — | Clé primaire, format DD/MM/YYYY |
| Prod_Jour | Onduleur (son application de suivi) | kWh produits dans la journée |
| Inj_Jour | Gestionnaire de réseau (Enedis) | kWh injectés au réseau |
| Conso_réseau_Jour | Gestionnaire de réseau (Enedis) | kWh soutirés du réseau |
| Conso_HC | Fournisseur | Part heures creuses |
| Conso_HP | Fournisseur | Part heures pleines |

L'en-tête du fichier écrit `Conso_réseau_Jour` **avec l'accent**. L'app
accepte aussi la forme sans accent, ainsi que `Conso_Jour`, `Soutirage` et
`Conso` : un CSV venu d'ailleurs n'à pas besoin d'être renomme.

Cases vides autorisees. L'app gère le passage d'un prix unique (Base) aux
heures pleines / creuses en utilisant les colonnes HC/HP quand elles sont
remplies et concordent avec le total du jour (entre 90 % et 120 % de
`Conso_réseau_Jour`) ; sinon le jour est estimé comme s'il n'avait pas de
détail.

À chaque enregistrement depuis l'app, l'écriture est atomique (une
interruption ne peut pas laisser un CSV à moitié écrit) et **trois
filets** conservent l'état précédent :

| Où | Quoi |
|---|---|
| `Releves-pv.csv.bak` | la version juste avant le dernier enregistrement |
| `backups/Releves-pv_<date>_<heure>.csv` | les **15** dernières versions |
| `backups/Releves-pv_jour_<date>.csv` | la première de chaque journée, pour les **30** dernières journées d'utilisation |

Les copies du jour échappent à la rotation des 15 : on peut donc revenir
plusieurs semaines en arrière, même après de nombreux enregistrements.
Pour restaurer, il suffit de copier le fichier voulu sur
`Releves-pv.csv` (l'app fermée). Le dossier `backups/` n'est pas
versionné : il contient les mêmes données personnelles que le CSV.

### Ajouter les données du jour

Ouvrez l'app → onglet **Saisie quotidienne**. Une ligne vide est
pre-remplie avec la date du jour suivant le dernier relevé. Saisissez
vos valeurs (Tab pour passer de cellule en cellule), cliquez sur
**Enregistrer**. Les autres vues se rafraîchissent automatiquement.
La ligne neuve laissée telle quelle n'est pas enregistree. Le bouton
**+ Ajouter une ligne** ajoute la journée suivante, pour rattraper
plusieurs jours d'un coup, jusqu'à aujourd'hui.

Ce qui est refusé à l'enregistrement, avec un message explicite :

- une **date incomplète** (`2026`, `08/2026`) ou inexistante (`31/02/2026`) :
  format attendu : `JJ/MM/AAAA` ;
- une **date dans le futur** (une faute de frappe sur l'année) ;
- une valeur **négative**, ou `inf` / `nan` (qui contaminaient les totaux) ;
- une valeur **au-delà du plausible** : 150 kWh pour la consommation,
  et **10 kWh par kWc** pour la production et l'injection (60 kWh sur une
  installation de 6 kWc, 90 sur 9 kWc).

Pour **effacer une journée**, videz toutes ses cases et enregistrez :
l'app demande confirmation, puis retire la ligne du fichier (une ligne
vide ferait un jour fantôme à 0 kWh dans les statistiques).

### Importer achat au réseau et injection

Le bouton **Importer achat au réseau / injection...** (onglet Saisie quotidienne)
charge un relevé quotidien de ce que le compteur a échangé avec le réseau.
**Aucune obligation d'être chez les mêmes fournisseurs que l'auteur** : tout
export "date + valeur" passe (voir plus bas). Les trois sources habituelles :

- **chez Enedis** (mon-compte-particulier.enedis.fr), l'**export d'index
  quotidiens** (`Export_<PRM>_Index_<periode>.xlsx`) : c'est le plus complet,
  et il est disponible **quel que soit votre fournisseur**. Il ne contient pas
  des consommations mais les **index du compteur** — l'application fait les
  soustractions elle-même et en tire la conso réseau **et le détail heures
  creuses / heures pleines**. Si vous injectez, sa feuille d'index de
  production donne en plus votre **injection** : un seul fichier remplit
  quatre colonnes. Pour l'obtenir : *Ma consommation > Suivre ma
  consommation*, choisir **Mixte** dans le menu du milieu (sans quoi la
  production manque) et **Index (kWh)** dans celui de droite, puis
  *Télécharger le .xlsx* ;
- **chez Enedis** toujours, le **classeur Excel** officiel
  (`..._Export_energie_Consommation-Production_....xlsx`) : les feuilles
  Consommation et Production sont importées d'un coup (la "production" Enedis
  = l'injection au réseau), mais **sans** le détail HC/HP ;
- **chez votre fournisseur**, le **CSV "suivi de consommation"**
  (`suivi_conso_....csv` chez Octopus) : conso réseau **et détail heures
  creuses / heures pleines**. Malgré le numéro de PRM dans son nom, ce fichier
  vient du fournisseur et non d'Enedis : il est d'ailleurs le seul à porter
  des colonnes en euros, qu'Enedis ne connaît pas. L'app les ignore ;
- ou un **export CSV** d'une seule grandeur.

Vous pouvez aussi **fabriquer vous-même** un CSV avec le détail HC/HP : une
colonne date en premier, puis deux colonnes nommées `Consommation HC (kWh)`
et `Consommation HP (kWh)` -- ou simplement `HC` et `HP`, ou encore
`Heures creuses` et `Heures pleines`. Les deux doivent être présentes ; avec
une seule, l'application refuse et dit laquelle manque.

Le format est détecté automatiquement (lignes d'en-tête ignorées, dates
ISO ou FR, valeurs en Wh ou kWh, jours "NA" ignorés). Fusion **sans
doublon** : les jours nouveaux sont ajoutes, les dates déjà présentes
voient leur valeur remplacée par celle du fichier (seule la colonne
importée change — la production saisie à la main n'est jamais
touchée). Un récapitulatif est affiché avant d'appliquer, et les
sauvegardes décrites plus haut conservent l'état précédent. Les valeurs
négatives et les dates futures du fichier sont écartées, et le
récapitulatif les cite ; une valeur négative déjà présente dans le CSV
(écrite par une version plus ancienne) est signalée dans le bandeau du
tableau de bord, sans que le fichier soit modifié.

Trois garde-fous évitent qu'une grandeur atterrisse dans la mauvaise
colonne ou avec la mauvaise unité :

- le type (injection ou consommation) est cherché **d'abord dans
  l'en-tête** du fichier, puis dans le reste du fichier si l'en-tête n'en dit
  rien ; s'il mentionne les deux
  (le classeur s'appelle "Consommation-Production"...), l'app **refuse
  de deviner** et le dit ;
- après lecture, elle vérifie que **l'injection ne dépasse pas la
  production** du même jour — c'est physiquement impossible, on
  n'injecte que le surplus. Au-delà de 10 % de jours douteux, un
  avertissement s'affiche avant le récapitulatif et le bouton par
  défaut devient « Annuler » ;
- les **valeurs invraisemblables** (au-delà des plafonds de la saisie à la
  main : 10 kWh par kWc, 150 kWh de consommation), signe typique de Wh lus
  comme des kWh, sont signalées en tête du récapitulatif, avec « Annuler »
  par défaut. L'import reste possible si les valeurs sont justes.

### Importer la production

Le bouton **Importer la production...** (onglet Saisie quotidienne) remplit la
colonne Production à partir de l'export de l'onduleur. Avec un **Enphase**,
depuis le rapport officiel Enlighten :

1. sur enlighten.enphaseenergy.com : **Menu > Système > Rapports** ;
2. choisir **Énergie mensuelle** et le mois voulu, puis **Rapport par
   email** ;
3. enregistrer la pièce jointe reçue (`.csv` ou `.zip`, peu importe) ;
4. dans l'app : **Importer la production...** et choisir ce fichier.

Le rapport donne la production toutes les 15 minutes : l'app **totalise
par jour** et arrondit au dixième, comme l'affichage Enlighten. La
**journée en cours est ignorée** (le rapport s'arrête à l'heure de sa
génération, elle serait sous-evaluee).

Mêmes garanties que l'autre import : fusion sans doublon, seule la
colonne Prod_Jour est modifiée, récapitulatif avant d'appliquer et
ancienne version conservée dans `Releves-pv.csv.bak`.

#### Le rapport mensuel d'un portail d'onduleur

Le même bouton accepte le **classeur Excel** que publient les portails
d'onduleurs (« rapport de centrale » chez Huawei FusionSolar, formes
voisines ailleurs) : une ligne par jour, une vingtaine de colonnes.

Il apporte **plus que la production**. Avant la mise en service du
compteur, le gestionnaire de réseau n'à aucun relevé : l'application doit
alors **estimer** l'autoconsommation de ces journées. Or l'onduleur, lui,
mesurait déjà. Le rapport donne ses colonnes **Production PV**,
**Exportation** et **Importation**, et ces journées cessent d'être
estimées. Quelques semaines chez la plupart, une saison entière chez qui
attend longtemps son raccordement.

Une règle protège les données du réseau : l'injection et la consommation
du rapport **ne remplissent que les cases vides**. Là où Enedis a relevé
quelque chose, c'est lui qui fait foi et rien n'est remplacé — ces
valeurs servent de base à la TVA sur l'autoconsommation. La production,
elle, n'à pas d'autre source que l'onduleur : elle est reprise
normalement. Le récapitulatif dit combien de journées ont été laissées
telles quelles.

Deux vérifications au passage : la colonne **Production totale** est un
cumul qui ne repart jamais à zéro, elle n'est **jamais** lue (c'est
Production PV qui donne le jour) ; et l'**autoconsommation** annoncée par
le rapport doit valoir production moins exportation, sans quoi
l'application prévient que les colonnes lues ne sont peut-etre pas les
bonnes.

### Une autre marque d'onduleur, un autre fournisseur

Les deux lecteurs ne connaissent pas de marque : ils acceptent **tout export
"date + valeur"**, vérifie sur des exports type SolarEdge, Huawei et un
fournisseur autre qu'Octopus.

- dates **françaises** (`01/08/2026`) ou **ISO** (`2026-08-01`) ;
- valeurs en **Wh** ou en **kWh**, unité lue dans l'en-tête ou devinée ;
- séparateur **`;`**, **`,`** ou **tabulation** ; lignes d'en-tête ignorées ;
- **production** : pas infrajournalier (15 minutes chez Enphase, avec
  l'heure) totalise par jour, ou relevé déjà quotidien ;
- **consommation et injection** : **une valeur par jour** (export quotidien
  d'Enedis ou du fournisseur). Une courbe à l'heure ou à la demi-heure est
  refusée avec un message (l'additionner serait faux : une courbe de charge
  donne souvent une puissance, pas une énergie) : exportez le relevé
  quotidien.

Seule exigence pour la conso et l'injection : **l'en-tête doit dire de quelle
grandeur il s'agit** — un mot comme `consommation`, `soutirage`, `injection`
ou `production`. Sans cela l'application refuse d'importer plutôt que de
ranger les valeurs dans la mauvaise colonne.

Ce qui n'à pas d'équivalent ailleurs : le **détail heures creuses / pleines**
au jour le jour, que tous les fournisseurs ne publient pas. Sans lui (ou
quand il ne concorde pas avec le total du jour),
l'application estime la répartition à partir du ratio observé sur les jours
qui ont ce détail, ou à défaut de la durée des plages d'heures creuses.

En France, l'**injection et la consommation** se récupèrent de toute façon
chez le gestionnaire de réseau (Enedis), commun à tous les fournisseurs, des
lors que le compteur est un **Linky**.

## Installation

Prérequis : Python 3.10+ installe depuis [python.org](https://www.python.org)
(garder l'option **"Install launcher"** cochée — c'est lui que les
lanceurs utilisent).

```bash
py -m pip install -r requirements.txt
```

Lancement : double-clic sur `Lancer.vbs`, ou en ligne de commande :

```bash
py run.py
```

`run.py` et non `app_desktop.py` : c'est lui qui affiche l'écran d'attente
pendant le chargement de pandas et de matplotlib, puis construit la fenêtre
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
exceptions déclarées pour les fichiers qui doivent importer après du code.

## Configuration

**Deux fichiers**, l'un à côté de l'autre, relus à chaque lancement :

| Fichier | Contenu | Versionné |
|---|---|---|
| `config.yaml` | l'installation et les tarifs | oui |
| `config-local.yaml` | les totaux lus sur **vos factures** et les chemins propres à votre machine | **non** |

Le second est facultatif et **remplace le premier section par section** : on
n'y écrit que ce qui lui est propre. Un modèle commente est fourni,
`config-local.exemple.yaml` : recopiez-le sous le nom `config-local.yaml`
pour l'activer.

Pourquoi séparer ? Les sections de recalage **réécrivent les relevés
journaliers** pour retomber sur le total d'une facture. Livrées avec le
programme, elles s'appliquaient aux relevés de qui récupérait
l'application : ses chiffres étaient faux, sans un mot. **Ne recopiez jamais les recalages de quelqu'un d'autre.**

Ce fichier n'étant plus protège par l'historique du dépôt, l'application en
garde une copie quotidienne dans `backups/` (les 30 dernières).

### config.yaml

- `installation` : puissance, coût, dates. La **puissance** sert aussi au
  titre de la fenêtre, à la Notice et au plafond de saisie (10 kWh par kWc :
  60 kWh sur 6 kWc, 90 sur 9 kWc)
- `oa` : type de vente (`surplus`, `totale` ou `aucune`), acheteur
  (facultatif, `EDF OA` par défaut), prix de rachat (€/kWh), prime autoconso
  (€/kWc, durée — vente du surplus seulement), durée du contrat
  (`duree_contrat_annees`, 20 ans pour l'OA : après, plus aucune vente
  n'est comptée ; 0 = pas de fin connue)
- `tarifs_reseau.bascule_hphc` : date du passage du prix unique aux heures
  pleines / creuses (chez l'auteur, un changement de fournisseur). Qui a
  toujours été en heures creuses met sa date de mise en service ; qui est
  encore en prix unique met une date future. Absente : 01/01/2026
- `tarifs_reseau.bleu_base` : abonnement et historique des prix Bleu
  Base par période. **Facultative** : sans elle, les journées d'avant la
  bascule sont comptées au tarif heures pleines / creuses (la bascule est
  ramenée au premier relevé)
- `tarifs_reseau.contrat_hphc.nom` / `.offre` : nom de VOTRE fournisseur tel
  qu'il s'affiche — le court pour le menu de gauche, le long pour les titres
  (chez l'auteur : "Octopus" / "Octopus Go"). Idem pour `comparaison_edf`.
  Sans eux : "Mon contrat" et "Tarif de référence". Le bouton de
  comparaison du menu porte ces noms : "Mon fournisseur ou EDF" avec le
  modèle livré
- `tarifs_reseau.contrat_hphc` : plages horaires HC, et `periodes` =
  abonnement + prix HP + prix HC pour chaque période de prix (les
  fournisseurs révisent leur grille en cours de contrat : laissez
  `fin: null` sur la période en cours et ajoutez-en une nouvelle à chaque
  changement). Cette section s'appelait autrefois `octopus_hphc` : un
  config.yaml qui porte encore l'ancien nom est lu sans changement
- `tarifs_reseau.comparaison_edf` : grille EDF Tarif Bleu de référence
  (le tarif réglementé, valable pour tous) utilisée par la vue de
  comparaison, en `periodes` elle aussi (abonnement, prix Base,
  prix HP, prix HC). EDF révise ses tarifs réglementés au 1er février et
  au 1er août : ajoutez une période à chaque révision. Les prix se
  relèvent sur particulier.edf.fr, guide "prix du kWh d'électricité",
  ligne 9 kVA -- attention, EDF les publie en **centimes**
- `tva_lasm` : grille servant à valoriser l'autoconsommation pour la TVA
  (voir « TVA sur l'autoconsommation » plus bas). `taux` = taux de TVA,
  `periodes` = une entrée par période tarifaire avec `prix_ht` (énergie +
  acheminement, hors taxes) et `accise`, en €/kWh, relevés sur les factures
  EDF. **Facultative** : sans elle, la vue TVA est masquée. À compléter à
  chaque évolution tarifaire, en général le 1er février et le 1er août
- `sources.releves_csv` : chemin du CSV de relevés

### config-local.yaml (personnel, non versionné)

- `sources.conso_reseau_facturee` : totaux de consommation lus sur les
  factures EDF, pour les périodes ou le détail quotidien n'existe plus
  chez Enedis (optionnel)
- `sources.conso_reseau_recalee` : totaux factures servant à recaler
  des consommations saisies arrondies au kWh entier (optionnel)
- `sources.conso_reseau_douteuse` : périodes dont la valeur saisie n'est
  pas fiable et doit être reconstituée (optionnel)
- `sources.injection_facturee` : totaux d'injection lus sur les
  autofacturations annuelles EDF OA, servant à recaler l'injection
  quotidienne, année OA par année OA (optionnel)
- `sources.recharges_ve_json` : chemin du `recharges.json` de
  l'application **recharges-ve**, pour afficher la part du soutirage qui
  part dans la voiture (optionnel, lu seulement)

## Année OA

Le cycle OA commence à la **date de début de votre contrat** et dure un an.
Par exemple, pour un contrat qui débute le 1er juillet 2024 :

- Année OA #1 : du 01/07/2024 au 30/06/2025
- Année OA #2 : du 01/07/2025 au 30/06/2026
- etc.

EDF OA verse une fois par an la somme correspondant à la production
injectée pendant ce cycle × tarif OA fixe. Le contrat dure
`oa.duree_contrat_annees` (20 ans pour l'OA) : passé cette date, plus
aucune vente n'est comptée.

Avec un autre acheteur qu'EDF OA, le même découpage s'appelle **année de
contrat** dans toute l'application.

## TVA sur l'autoconsommation

Cette partie ne concerne que les producteurs **assujettis à la TVA**
(entreprise individuelle, régime réel simplifié). Elle est facultative :
sans la section `tva_lasm` dans `config.yaml`, la vue est masquée.

### La règle

Contrat S21 en obligation d'achat, vente de surplus :

- les **ventes à EDF OA sont autoliquidées** (art. 283-2 quinquies du CGI).
  C'est EDF qui déclare leur TVA ; le producteur n'en collecte aucune. La
  **prime à l'autoconsommation est hors champ** ;
- seule l'électricité **produite ET consommée sur place** est taxable. C'est
  une **livraison à soi-même** (LASM, art. 257-II-1-1° du CGI), à porter
  **ligne 5A** de la déclaration annuelle **CA12 / 3517-S** ;
- la **base** = kWh autoconsommés × prix d'achat HT d'une électricité
  similaire (art. 266-1-c), c'est-à-dire **son propre tarif** : part
  fourniture + acheminement HT, plus l'**accise** sur l'électricité.
  **Hors TVA et hors abonnement** — l'abonnement n'est pas un prix au kWh ;
- la période déclarée est l'**année civile**.

Méthode confirmée par écrit par un service des impôts des entreprises (SIE)
en septembre 2026, qui renvoie aux relevés du producteur pour les
quantités.

### D'ou viennent les chiffres

Des **relevés quotidiens de `Releves-pv.csv`, pris tels quels** : ni
estimation des jours manquants, ni recalage sur les factures EDF OA. Ces
corrections améliorent les chiffres affichés partout ailleurs dans
l'application, mais une déclaration fiscale doit reposer sur les quantités
réellement relevées, pas sur des valeurs reconstituees.

Conséquence assumée : un jour sans relevé d'injection compte **toute** sa
production en autoconsommation, ce qui **majore** la base. Leur nombre est
affiché, et la vue le signale.

### Jour par jour, pas en moyenne

Chaque kWh autoconsommé est valorisé au tarif en vigueur **le jour même**.
Une moyenne annuelle donnerait un chiffre différent, et faux : les tarifs
changent en cours d'année (1er février, 1er août) alors que
l'autoconsommation, elle, se concentre sur l'été. Le « prix moyen pondéré »
affiché n'est donc pas un tarif : c'est la moyenne qui **ressort** de ce
calcul.

### Le contrôle avec les factures EDF OA

C'est lui qui rend les chiffres opposables. La somme des injections relevées
est comparée, **année de contrat par année de contrat**, aux kWh réellement
factures par EDF OA — un document que le producteur n'écrit pas lui-même,
établi sur l'index du compteur de production. Chez l'auteur, l'écart tient
**sous 1 %**.

Ce contrôle-là, et lui seul, complete d'abord les jours sans relevé par leur
estimation mensuelle : sans quoi une semaine de panne Linky ferait crier au
loup. Le nombre de jours ainsi estimés est affiché à côté de l'écart.

Les totaux factures se déclarent dans `sources.injection_facturee`
(`config-local.yaml`). Sans eux, la colonne de contrôle reste vide.

### L'année en cours

Elle est **projetée** jusqu'au 31/12 et marquée « estimé » partout : dans le
tableau, sur le graphique (barre hachurée) et en note. La projection part de
la part d'autoconsommation que les années passées avaient déjà atteinte **à
la même date**, et applique cette part moyenne au realise. Ce n'est pas un
montant à déclarer ; il se fige une fois l'année terminée.

Une année est considérée comme close quand les relevés vont jusqu'à son
31 décembre — année terminée n'est pas année complete.

### Les montants déjà déposés

Une fois une année déclarée, ses chiffres ne doivent plus bouger. Chez
l'auteur, un test non publie (`tests/test_tva_deposee.py`, exclu du dépôt
par `.gitignore`) les recalcule sur ses vrais relevés : si un changement de
code les fait bouger un jour, le test tombe. Faites de même avec les votres.

## Hypothèses de calcul

- **Autoconso** = Production − Injection (>= 0)
- **Conso totale** = Autoconso + Soutirage réseau
- **Économie d'autoconso** = kWh autoconsommés × prix achat réseau du
  moment. Avant la bascule en heures pleines / creuses : prix Base de la
  date. Après : prix HP/HC pondéré par `part_hc_autoconso` (config, ou la
  case « Autoconsommation en heures creuses » de **Mes réglages**, en %), la
  part d'autoconso qui tomberait en heures creuses — l'autoconso étant
  diurne, elle est faible, sauf plage creuse l'apres-midi. Absente du
  fichier, elle est **estimée d'après les plages HC** : la part d'une journée
  de soleil type qui tombe dedans (0 si elles sont toutes la nuit) ; « Mes
  réglages » montre l'estimation à côté de la case
- **Bilan électricité** (tableau de bord, Répartition, Comparer, Relevés,
  Années OA) = Vente + Économies − Achat au réseau, le même partout. La
  prime est comptée à part : sa colonne dans les Années OA, et le **bilan de
  l'installation** de la Synthèse financière. Un bilan s'écrit en vert s'il
  est positif, en rouge s'il est négatif
- **Prime à l'autoconsommation** : comptée seulement quand l'année OA
  concernée est **terminée** (EDF OA facture à la date anniversaire, donc
  après coup). L'année en cours est affichée « à venir » dans les Années OA
  sans entrer dans son bilan
- **Temps de retour** (ex-« ROI ») = (investissement − prime totale) ÷ gains **récurrents** annuels
  (vente OA + économies). La prime n'étant versée qu'un temps (en une fois
  pour les contrats récents, sur 5 ans pour les plus anciens), elle est
  déduite du capital à amortir au lieu d'être comptée comme un revenu qui
  se repete. Le calcul suppose des gains maintenus au rythme observé,
  et n'est fait qu'après un an de relevés (toutes les saisons comprises)
- **Avant le début du contrat OA** : pas de vente (contrat pas encore
  actif), même pour l'injection estimée de cette période
- **Après la fin du contrat** (début + `duree_contrat_annees`) : plus de
  vente non plus ; l'injection reste comptée en kWh
- **Jours sans relevé d'injection** (avant le contrat, ou panne du Linky
  dont les données ne sont plus disponibles chez Enedis) : injection
  estimée via le ratio injection/production du même mois observé sur les
  jours complets ; autoconso et conso recalees. Le CSV n'est pas modifié,
  ces jours restent signalés dans l'app
- **Injection recalée sur les factures EDF OA** (facultatif,
  `sources.injection_facturee`) : le détail quotidien vient d'Enedis, mais
  EDF OA paie sur l'index du compteur de production, relevé une seule fois
  par an. Les deux différent de quelques dixièmes de pour-cent selon
  l'année. L'app multiplie tous les jours d'une année OA facturée par un
  même facteur pour retomber sur le total payé, sans jamais faire dépasser
  l'injection d'un jour au-dessus de sa production. **Le total de chaque
  année OA est celui de la facture, le détail quotidien reste approche.**
  L'année en cours, pas encore facturée, n'est pas recalée. CSV intact
- **Injection d'avant-contrat** : entre la mise en service et le début du
  contrat, personne n'achète l'injection, mais le compteur de production la
  compte déjà. Son index au premier jour du contrat peut servir de tranche
  de recalage comme les autres. Aucun euro en jeu : c'est l'autoconso
  affichée de cette période qui en devient juste
- **Consommations arrondies** (facultatif, `sources.conso_reseau_recalee`) :
  des consommations saisies au kWh entier perdent leur partie décimale. L'app
  recale chaque tranche sur le total de la facture correspondante. L'écart
  est reparti **à parts égales** s'il est positif (la décimale perdue vaut 0
  à 1 kWh quel que soit le jour) et **au prorata** s'il est négatif (l'excès
  vient des grosses valeurs). **Le total de la tranche est exact, le détail
  quotidien approche à ~1 kWh pres.** CSV intact
- **Jours à la valeur non fiable** (`sources.conso_reseau_douteuse`) : par
  exemple une panne du Linky dont les valeurs ont été interpolees. Traités
  comme n'ayant pas de relevé : les autres jours de la tranche sont corrigés
  de leur troncature, puis ceux-ci reçoivent le **solde** de la facture
- **Jours sans relevé de consommation** : Enedis ne garde que **36 mois
  glissants**, le détail quotidien des débuts d'une installation ancienne
  n'existe plus. Les totaux se reprennent des **factures** et se déclarent
  dans `config-local.yaml`, section `sources.conso_reseau_facturee` ; l'app
  les repartit sur les jours non relevés. **Le total de chaque période est
  exact, pas le détail quotidien.** Sans cela ces jours compteraient 0 kWh
  soutiré : facture sous-evaluee et autoproduction affichée à 100 %. Le CSV
  n'est pas modifié, ces jours sont signalés par un astérisque
- **Avant la bascule** (`bascule_hphc`) : prix unique (Base), pas de HP/HC
- **Après la bascule** : heures pleines / creuses. Si les colonnes
  Conso_HC et Conso_HP sont renseignées pour un jour, le coût est calculé
  exactement ; sinon il est estimé au prix moyen correspondant au **ratio
  HC réellement observé** sur les jours détaillés ; la durée des plages
  sur 24 h (consommation supposée uniforme jour et nuit) ne sert qu'en
  repli, quand aucun jour n'à ce détail
- **Changement de grille du fournisseur** : chaque période de prix est
  gardée dans `config.yaml`, et chaque journée est facturée au prix de
  **sa** période. Un nouveau tarif ne s'applique donc pas rétroactivement
  aux mois précédents

## Fraîcheur des données

Un bandeau en tête du Tableau de bord donne l'âge de **chaque grandeur**
(production, injection, conso, HC/HP) : elles n'avancent pas ensemble,
Enphase publie le jour même et Enedis avec environ deux jours de retard.
Au-delà de **3 jours** sur l'une d'elles, le bandeau passe en orange et
rappelle d'importer. La barre d'état affiche la date du dernier relevé
depuis n'importe quel onglet.

## Part du véhicule électrique

Si `sources.recharges_ve_json` pointe vers le `recharges.json` de
l'application **recharges-ve**, l'app affiche quelle part du soutirage
réseau part dans la voiture : légende de la barre « D'où vient votre
électricité » au Tableau de bord, colonne « dont véhicule » dans les Relevés
journaliers, sous-lignes « dont recharge
véhicule » / « dont reste du foyer » dans Répartition énergie.

- Seules les recharges **à la maison** comptent : les recharges
  extérieures ne passent pas par votre compteur.
- Une charge de nuit (23:30 → 05:00) est **repartie entre les deux
  journées** au prorata du temps, pour rester comparable aux relevés
  quotidiens Enedis.
- Le **coût** est celui calculé par recharges-ve (vraies plages horaires),
  pas une part du coût réseau moyen : la recharge se fait presque
  entièrement en heures creuses, un prorata la surestimerait fortement.
- Le fichier de l'autre application est **seulement lu, jamais modifié**.
  Clé optionnelle : sans elle, ou si le fichier est absent, l'app
  fonctionne normalement sans afficher ces informations.

## Données 100 % locales

Tout tourne sur votre machine. Aucun fichier n'est envoyé sur internet.

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
├── faire_archive.py      # Fabrique l'archive portable (.zip), sans installeur
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
├── imports_releves.py    #   ... lecture des fichiers a importer (Enedis,
│                         #   fournisseur, onduleur, Enphase)
├── lecture_recharges_ve.py #  ... le recharges.json de Recharges VE
├── gui_theme.py          # Themes clair et sombre + QSS + style matplotlib
├── gui_widgets.py        # Widgets reutilisables (cards, KPI, pill...)
├── reglages.py           # « Mes reglages » : lire et ecrire config.yaml
├── fenetre_reglages.py   #   ... et la fenetre qui les presente
├── accords.py           # Accorder un mot avec un nombre (« 1 jour », « 2 jours »)
├── erreurs.py            # Erreurs techniques dites en francais (commun
│                         #   aux trois applications de l'auteur)
├── sauvegarde_externe.py # Copie verifiee sur cle USB ou disque (commun)
├── mise_a_jour.py        # Existe-t-il une version plus recente ?
├── avis.py               # « Votre avis » : le questionnaire en ligne
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
│   ├── comparaison.py    #   Comparer a l'an passe
│   ├── octopus_edf.py    #   Mon fournisseur ou EDF
│   ├── aide.py           #   Notice (mode d'emploi et glossaire)
│   └── settings.py       #   Parametres
│
│   -- les donnees (aucune n'est versionnee, sauf le modele) --
├── config.yaml           # Parametres editables (le modele est versionne)
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
├── demo_releves.py       # Releves INVENTES (smoke test, captures)
├── captures_site.py      # Captures de la page de presentation
├── pytest.ini
├── ruff.toml             # Regles d'analyse statique
├── requirements.txt      # Dependances d'execution
├── requirements-dev.txt  # Developpement : pytest, ruff, pyinstaller
├── LICENSE               # Licence MIT
├── docs/                 # Page de presentation (GitHub Pages)
├── pv-dashboard.ico      # Icone de l'application
└── README.md
```

Trois fichiers de vues portent un nom hérité d'un ancien projet de comptes,
qui ne dit pas leur contenu : `transactions.py` est la vue **Relevés
journaliers**, `categories.py` la **Répartition énergie** et `accounts.py`
la **Synthèse financière**. La liste ci-dessus fait foi.
