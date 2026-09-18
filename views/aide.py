"""La Notice : mode d'emploi et glossaire.

Le fichier garde le nom aide.py, et la vue la cle « aide » : ce sont des
identifiants internes, que renommer obligerait a toucher l'import, la table
des vues et le smoke test sans rien changer a l'ecran. Seul le libelle
affiche est passe de « Aide » a « Notice », le 07/09/2026, pour dire la meme
chose que dans Recharges VE.
"""
from __future__ import annotations

import html
import re

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

import calculations as calc
from gui_widgets import Card, SectionTitle
from views._base import BaseView
from views._helpers import fmt_date_fr, fmt_kwc

NOTICE_HTML = """
<h3 style="color:#b45309">À quoi sert l'application</h3>
<p>Cette application suit votre installation photovoltaïque de {puissance},
mise en service le {mise_en_service}. Elle réunit la production solaire,
l'électricité vendue au réseau et celle achetée, puis calcule le bilan
financier et l'amortissement des {invest} investis.</p>

<h3 style="color:#b45309">La première fois</h3>
<p>Trois choses à faire, dans cet ordre, avant que les chiffres aient un
sens :</p>
<p><b>1. Décrire votre installation.</b> Onglet <b>Paramètres</b>, bouton
<b>Modifier mes réglages</b> : puissance, coût, dates de votre contrat, prix
de rachat, fournisseur et prix de votre électricité. L'application se
recharge seule à l'enregistrement. L'onglet <b>Paramètres</b> montre ensuite
à tout moment ce qui est pris en compte : c'est là qu'on vérifie qu'on ne
s'est pas trompé.<br>
Les réglages plus rares (TVA, grille EDF de comparaison, prix d'un ancien
contrat à prix unique) se font dans le fichier <code>config.yaml</code>,
avec le Bloc-notes, dans le dossier de vos données : <code>{dossier}</code>
(menu Démarrer, raccourci « Dossier des données », si l'application a été
installée). Relancez alors l'application pour appliquer.</p>
<p><b>2. Faire entrer vos relevés.</b> Onglet <b>Saisie quotidienne</b> :
les boutons <b>Importer…</b> chargent d'un coup un fichier téléchargé chez
votre gestionnaire de réseau, votre fournisseur ou votre onduleur. À défaut,
la saisie à la main marche aussi bien.</p>
<p><b>3. Vos factures, si vous les avez.</b> Les totaux d'une facture sont
plus justes que la somme des relevés quotidiens. Ils se déclarent dans
<b>Modifier mes réglages</b>, section <b>Recalages sur mes factures</b> :
choisissez ce que vous recalez, la période, le total en kWh, et d'où il
vient. L'écart est réparti sur les jours de la période.</p>
<p>Le cas le plus utile pour un producteur : <b>Injection payée par EDF OA</b>.
EDF OA paie sur l'index du compteur, qui diffère un peu de ce qu'annonce
l'onduleur — donner le total en kWh de votre autofacturation (pas le montant
en euros) met l'application d'accord avec ce que vous avez réellement touché.</p>
<p>Ces totaux s'écrivent dans <code>config-local.yaml</code>, à côté de
<code>config.yaml</code> — un modèle commenté
(<code>config-local.exemple.yaml</code>) est fourni si vous préférez
l'écrire vous-même. Ce fichier est facultatif, et il ne quitte jamais votre
ordinateur : ce sont vos factures. <b>N'y recopiez jamais celles de quelqu'un
d'autre</b>, vos relevés seraient réécrits pour retomber sur des totaux qui ne
sont pas les vôtres.</p>

<h3 style="color:#b45309">Les vues (menu de gauche)</h3>
<p><b>Tableau de bord</b> — vue d'ensemble de la période choisie : la part de
soleil dans votre consommation (jauge), la production comparée à l'an passé,
où va votre soleil et d'où vient votre électricité, le bilan financier, où
en est le remboursement de l'installation, et la production jour par jour
avec votre meilleur jour.</p>
<p><b>Saisie quotidienne</b> — pour entrer ou corriger les relevés d'un jour.</p>
<p><b>Relevés journaliers</b> — le journal détaillé, une ligne par jour, et
les totaux de la période en bas du tableau.</p>
<p><b>Répartition énergie</b> — diagramme de flux montrant d'où vient et où va
chaque kWh, avec le détail poste par poste et la comparaison avec l'an
dernier.</p>
<p><b>Synthèse financière</b> — ventes, primes, économies et facture réseau
depuis le début, et le graphique du remboursement de l'installation : ce
qu'elle vous a rapporté face à ce qu'elle a coûté, avec l'année où elle sera
remboursée au rythme actuel. Le bilan net compte les ventes, les économies
et les primes, moins le coût de l'installation ; la facture d'électricité
n'y entre pas, puisque vous la paieriez même sans panneaux.</p>
<p><b>Années OA</b> — récapitulatif par cycle de contrat (du {debut_oa} au
{fin_oa} de l'année suivante).</p>
<p><b>TVA autoconsommation</b> — pour qui est assujetti à la TVA : la base à
déclarer sur l'électricité autoconsommée, année civile par année civile. Sans
intérêt pour les autres : cet onglet n'apparaît dans le menu que si la
section <code>tva_lasm</code> de <code>config.yaml</code> est remplie.</p>
<p><b>Statistiques</b> — comparaison des années civiles et rendement.</p>
<p><b>Comparaison N vs N-1</b> — compare la période choisie en haut à droite
à la même période un an plus tôt : un mois au même mois de l'année d'avant,
une année à la précédente, une année OA à l'année OA précédente. Sur « Toute la
période », rien à comparer : l'onglet invite à choisir un mois ou une année.
Une période <b>en cours</b> est comparée aux <b>mêmes dates</b> de l'an passé :
septembre relevé jusqu'au 9 face au 1<sup>er</sup>–9 septembre de l'année
d'avant, et non au mois entier — les libellés l'indiquent, « (au 09/09) ».
Le bouton <b>Une journée précise</b> ouvre un calendrier pour comparer un jour
donné au même jour de l'an passé ; changer de période en haut le referme.</p>
<p><b>{comparaison}</b> — ce que le changement d'opérateur a réellement fait
gagner, mois par mois. Cet onglet n'apparaît que si votre fournisseur n'est
pas EDF : il compare votre contrat au Tarif Bleu d'EDF.</p>
<p><b>Paramètres</b> — récapitulatif de la configuration (tarifs, contrat), et
bouton <b>Modifier mes réglages</b> pour la changer.</p>
<p><b>Votre avis</b> — signaler un problème ou proposer une idée : ouvre un
court questionnaire dans votre navigateur. L'application, elle, n'envoie
rien.</p>

<h3 style="color:#b45309">Vos données sont-elles à jour ?</h3>
<p>Un bandeau en haut du <b>Tableau de bord</b> indique l'âge de chaque
grandeur : <i>Production il y a 2 jours · Injection il y a 2 jours…</i>. Elles
n'avancent pas ensemble — la production vient de l'onduleur (disponible le
jour même), l'injection et la consommation du gestionnaire de réseau (deux
jours de retard environ), le détail heures creuses / pleines du fournisseur,
plus tard encore.</p>
<p>Si une grandeur dépasse <b>3 jours</b>, le bandeau devient orange : c'est
qu'un import a probablement été oublié. La barre d'état, en bas, rappelle la
date du dernier relevé quel que soit l'onglet affiché.</p>

<h3 style="color:#b45309">Choisir une période</h3>
<p>La barre en haut à droite porte <b>‹ année mois ›</b> et filtre toutes les
vues. Les deux flèches reculent ou avancent d'un cran : d'un mois quand un
mois est affiché, d'une année quand c'est une année, d'une année OA quand
c'est une année OA. Elles se grisent quand il n'y a plus rien de ce côté.</p>
<p>Le menu des mois ne propose que les mois qui portent des relevés. Il se
grise sur <b>Toute la période</b> et sur une <b>année OA</b>, qui sont à
cheval sur les mois ; les dates exactes d'une année OA se lisent en survolant
son entrée dans le menu des années.</p>
<p>L'application s'ouvre <b>toujours sur le mois en cours</b> : la période
n'est pas mémorisée d'une fois sur l'autre, pour ne pas retrouver au
lancement suivant les chiffres d'un mois passé consulté la veille.</p>

<h3 style="color:#b45309">Saisir les relevés du jour</h3>
<p>1. Ouvrez <b>Saisie quotidienne</b>.<br>
2. La première ligne, surlignée, est prête avec la date attendue.<br>
3. Saisissez les valeurs (touche Tab pour changer de case).<br>
4. Cliquez sur <b>Enregistrer</b> : les autres vues se mettent à jour.</p>
<p>Les décimales s'écrivent avec une virgule (ex. 24,8). Les cases sans donnée
peuvent rester vides. Le bouton <b>+ Ajouter une ligne</b> permet de saisir
plusieurs jours d'un coup.</p>
<p>La <b>date s'écrit en entier</b> : 05/08/2026. Une date incomplète (« 2026 »,
« 08/2026 ») est refusée avec un message — auparavant elle était comprise comme
le 1<sup>er</sup> janvier et écrasait le relevé de ce jour-là. Les valeurs
négatives sont refusées elles aussi.</p>
<p>Pour <b>effacer une journée</b>, videz toutes ses cases et enregistrez :
l'application demande confirmation, puis retire la ligne du fichier. L'ancienne
version reste dans le <code>.bak</code>.</p>

<h3 style="color:#b45309">Importer conso et injection</h3>
<p>Le bouton <b>Importer conso / injection…</b> (onglet Saisie quotidienne)
charge d'un coup ce que votre compteur a échangé avec le réseau. Deux fichiers
sont utiles, et se complètent :</p>
<ul>
<li>chez votre <b>gestionnaire de réseau</b> (Enedis en France, quel que soit
le fournisseur), le <b>classeur Excel</b>
« Export_energie_Consommation-Production… » : consommation <b>et</b>
production/injection importées ensemble ;</li>
<li>chez votre <b>fournisseur</b>, le relevé de suivi de consommation (CSV
« suivi_conso… » chez Octopus, par exemple) : la consommation avec le <b>détail heures
creuses / heures pleines</b>, que le classeur Excel ne contient pas. Malgré
son nom de fichier, ce relevé vient bien du fournisseur — c'est d'ailleurs le
seul à porter des euros, que le gestionnaire de réseau ne connaît pas.
L'application les ignore.</li>
</ul>
<p><b>Vous n'êtes pas obligé d'être chez les mêmes que l'auteur.</b> Le format
est reconnu automatiquement, et tout export <b>« date + valeur »</b> passe :
dates françaises ou internationales, valeurs en Wh ou en kWh, point-virgule,
virgule ou tabulation. La seule exigence est que l'en-tête dise de quelle
grandeur il s'agit — un mot comme « consommation », « injection » ou
« production » — car l'application refuse de deviner dans quelle colonne
ranger vos chiffres.</p>
<p><b>Le détail heures creuses / heures pleines sans passer par votre
fournisseur.</b> Dans votre espace client <b>Enedis</b>, l'export des
<b>index quotidiens</b> (un fichier <code>Export_…_Index_….xlsx</code>)
contient ce détail pour tout le monde, quel que soit le fournisseur. Attention,
ce fichier ne donne pas des consommations mais des <b>index</b> : l'état du
compteur, qui ne fait que monter. L'application s'en charge — elle soustrait
chaque jour du précédent et range le résultat. Les colonnes utilisées sont
celles du <b>calendrier fournisseur</b> (« Heures Pleines (en kWh) »,
« Heures Creuses (en kWh) ») ; celles du calendrier distributeur, en saison
basse ou haute, découpent la même énergie autrement et sont ignorées. Un jour
sans relevé laisse un trou plutôt qu'une valeur double.</p>
<p>Si vous produisez, ce même fichier contient <b>en plus</b> une feuille
d'index de production : l'application y lit votre <b>injection</b>. Un seul
téléchargement remplit alors quatre colonnes — consommation réseau, heures
creuses, heures pleines et injection. Pour l'obtenir : espace client Enedis,
<b>Ma consommation ▸ Suivre ma consommation</b>, choisir <b>Index (kWh)</b>
dans le menu de droite, puis <b>Télécharger le .xlsx</b>.</p>
<p><b>Le détail heures creuses / heures pleines</b> demande deux colonnes
nommées, l'une pour les heures creuses, l'autre pour les heures pleines.
Plusieurs libellés sont acceptés : <code>Consommation HC (kWh)</code> et
<code>Consommation HP (kWh)</code> (ceux d'Octopus), <code>Heures creuses</code>
et <code>Heures pleines</code>, ou simplement <code>HC</code> et
<code>HP</code>. La date reste en <b>première colonne</b>, le séparateur est le
point-virgule, et une colonne de consommation totale est facultative :</p>
<pre>Date;Consommation (kWh);Consommation HC (kWh);Consommation HP (kWh)
01/09/2026;12,3;5,1;7,2
02/09/2026;11,8;4,9;6,9</pre>
<p>Si le fichier ne porte <b>qu'une</b> des deux colonnes, l'application le dit
et n'importe rien, plutôt que de laisser ces kWh grossir la consommation réseau
sans prévenir. Et pour quelques jours seulement, les colonnes <b>Conso HC</b> et
<b>Conso HP</b> se remplissent aussi à la main dans le tableau de l'onglet
Saisie quotidienne.</p>
<p>L'import ne crée <b>jamais de doublon</b> : les jours nouveaux sont ajoutés,
les dates déjà présentes sont mises à jour (seule la colonne concernée est
remplacée — votre production n'est jamais touchée). Un récapitulatif
s'affiche avant d'appliquer, et l'état précédent est sauvegardé.</p>
<p>Si le fichier ne dit pas clairement s'il contient de l'injection ou de la
consommation, l'application <b>refuse de deviner</b> plutôt que de risquer de
ranger vos chiffres dans la mauvaise colonne. Elle vérifie aussi que
l'injection ne dépasse pas la production du jour — impossible, puisqu'on
n'injecte que le surplus — et vous prévient avant d'appliquer.</p>

<h3 style="color:#b45309">Importer la production</h3>
<p>Le bouton <b>Importer la production…</b> remplit la colonne Production sans
recopie à la main, à partir de l'export de votre onduleur. Avec un
<b>Enphase</b>, sur le site Enlighten : <b>Menu ▸ Système ▸ Rapports</b>,
choisissez <b>Énergie mensuelle</b> et le mois, puis <b>Rapport par email</b> ;
enregistrez la pièce jointe reçue et ouvrez-la avec ce bouton.</p>
<p>Une <b>autre marque d'onduleur</b> convient tout aussi bien : le lecteur ne
demande qu'un fichier « date + valeur », en Wh ou en kWh, quel que soit le
séparateur. Les relevés plus fins qu'une journée — toutes les 15 minutes chez
Enphase — sont <b>totalisés par jour</b>. La <b>journée en cours est
ignorée</b>, car l'export s'arrête à l'heure où vous l'avez demandé : elle
serait sous-évaluée. Mêmes garanties que l'autre import : aucun doublon,
récapitulatif avant d'appliquer, sauvegarde <code>.bak</code>.</p>

<h3 style="color:#b45309">D'où viennent les données</h3>
<p>Ci-dessous les sources de l'installation suivie ici ; les vôtres peuvent
être différentes, les imports s'en accommodent.</p>
<p><b>Production</b> : l'application ou le site de votre onduleur.<br>
<b>Injection et soutirage</b> : le gestionnaire de réseau, ici Enedis
(mon-compte-particulier.enedis.fr), grâce au compteur Linky — c'est la source
commune à tous les foyers français, quel que soit le fournisseur.<br>
<b>Heures creuses et heures pleines</b> : l'espace client du <b>fournisseur</b>
d'électricité. Tous ne publient pas ce détail jour par jour ; sans lui,
l'application estime la répartition et le dit.<br>
<b>Recharges du véhicule</b> : l'application <i>Recharges VE</i>, dont le
fichier est simplement lu (jamais modifié).</p>

<h3 style="color:#b45309">La part de la voiture</h3>
<p>Le soutirage réseau mélange deux choses très différentes : ce que consomme
la maison et ce que prend la voiture. L'application les sépare — sous la
barre <b>D'où vient votre électricité</b> du Tableau de bord, colonne
<b>dont véhicule</b> dans les Relevés journaliers, et deux sous-lignes dans
<b>Répartition énergie</b>.</p>
<p>Seules les recharges <b>faites à la maison</b> sont comptées : celles des
bornes extérieures ne passent pas par votre compteur. Une charge de nuit,
à cheval sur deux journées, est répartie entre les deux au prorata du temps.</p>

<h3 style="color:#b45309">Si vous êtes assujetti à la TVA</h3>
<p>Cette partie ne concerne que les producteurs qui déclarent la TVA
(entreprise individuelle au régime réel simplifié). Si ce n'est pas votre
cas, l'onglet <b>TVA autoconsommation</b> ne vous servira à rien : laissez la
section <code>tva_lasm</code> de <code>config.yaml</code> en commentaire, et
il n'apparaîtra pas dans le menu.</p>
<p><b>Ce qui est taxable, et ce qui ne l'est pas.</b> L'électricité vendue à
EDF OA ne vous fait rien collecter : c'est EDF qui en déclare la TVA à votre
place — on dit qu'elle est <i>autoliquidée</i> — et la prime à
l'autoconsommation est hors champ. En revanche, l'électricité que vous
produisez <b>et</b> consommez vous-même est taxable : c'est une <b>livraison à
soi-même</b>, à porter <b>ligne 5A</b> de la déclaration annuelle
<b>CA12 / 3517-S</b>.</p>
<p><b>Comment la base est calculée.</b> Chaque kWh autoconsommé est valorisé
au prix auquel vous auriez acheté la même électricité : votre part fourniture
et acheminement hors taxes, plus l'accise. Sans la TVA, et <b>sans
l'abonnement</b>, qui n'est pas un prix au kWh. Le calcul se fait <b>jour par
jour</b>, au tarif en vigueur ce jour-là — une moyenne annuelle donnerait un
chiffre faux, les tarifs changeant en cours d'année alors que
l'autoconsommation se concentre sur l'été. Ces tarifs se relèvent sur vos
factures et se déclarent dans <code>config.yaml</code>, section
<code>tva_lasm</code> : <b>à compléter à chaque révision</b>, en général le
1<sup>er</sup> février et le 1<sup>er</sup> août.</p>
<p><b>Le recoupement avec vos factures.</b> Sous le tableau, l'application
compare la somme de vos injections relevées aux kWh réellement facturés par
EDF OA, année de contrat par année de contrat. C'est lui qui rend vos chiffres
défendables : ils se retrouvent sur un document que vous n'écrivez pas
vous-même. Il suppose que les totaux de vos autofacturations soient déclarés
dans <code>config-local.yaml</code>.</p>
<p><b>Deux réserves, affichées en clair.</b> Les journées <b>sans relevé
d'injection</b> comptent toute leur production en autoconsommation, ce qui
majore la base : leur nombre est indiqué année par année. Et l'<b>année en
cours est une estimation</b>, prolongée jusqu'au 31 décembre d'après les
années passées — elle n'est pas à déclarer, elle se fige une fois l'année
terminée.</p>
<p>Les chiffres de cet onglet, et eux seuls, sont calculés sur vos relevés
<b>bruts</b>, sans le recalage sur factures appliqué ailleurs : une
déclaration doit reposer sur ce qui a réellement été relevé.</p>

<h3 style="color:#b45309">Vos sauvegardes</h3>
<p>À chaque enregistrement, l'application met de côté la version précédente
de vos relevés, à trois endroits :</p>
<ul>
<li><code>Relevés-pv.csv.bak</code> — juste avant le dernier enregistrement ;</li>
<li><code>backups/</code> — les <b>15 dernières versions</b>, horodatées ;</li>
<li><code>backups/</code> — la première de <b>chaque journée</b>, gardée 30 jours.</li>
</ul>
<p>Les copies quotidiennes échappent à la rotation des 15 : vous pouvez donc
revenir plusieurs semaines en arrière. Pour restaurer, fermez l'application et
recopiez le fichier voulu sur <code>Relevés-pv.csv</code>.</p>
<p><b>Sur une clé USB ou un disque externe.</b> Toutes ces copies restent sur
le même disque que vos données : si ce disque lâche, elles partent avec lui.
Le bouton <b>💾 Sauvegarde externe</b>, en bas du menu de gauche, copie vos
relevés et vos réglages sur le support de votre choix, dans un dossier daté,
et vérifie chaque copie. Un fichier <code>LISEZMOI.txt</code>, déposé à côté,
explique comment la remettre en service. Faites-le de temps en temps, par
exemple après chaque import mensuel.</p>

<h3 style="color:#b45309">Bon à savoir</h3>
<p>Toutes les données restent sur votre ordinateur. Après chaque enregistrement, les
calculs et graphiques sont recalculés automatiquement.</p>
<p>L'application ne se connecte jamais à Internet. Pour savoir si une version
plus récente existe, cliquez sur <b>🔄 Mise à jour</b> : la page de la dernière
version s'ouvre dans votre navigateur.</p>
"""

GLOSSAIRE_HTML = """
<p><b>kWh (kilowattheure)</b> — unité d'énergie. 1 kWh correspond à 1000 watts
utilisés pendant une heure.</p>
<p><b>MWh (mégawattheure)</b> — 1000 kWh.</p>
<p><b>kWc (kilowatt-crête)</b> — puissance maximale des panneaux dans des
conditions idéales. Votre installation fait {puissance}.</p>
<p><b>Production</b> — énergie produite par les panneaux solaires.</p>
<p><b>Autoconsommation</b> — part de la production consommée directement chez
vous, sans passer par le réseau.</p>
<p><b>Injection</b> — part de la production envoyée (et vendue) au réseau
électrique.</p>
<p><b>Soutirage réseau</b> — électricité achetée au réseau quand les panneaux
ne suffisent pas (nuit, mauvais temps).</p>
<p><b>Consommation totale</b> — tout ce que vous consommez : autoconsommation
+ soutirage réseau.</p>
<p><b>Taux d'autoconsommation</b> — part de la production que vous consommez
vous-même (autoconsommation ÷ production).</p>
<p><b>Taux d'autoproduction</b> — part de vos besoins couverte par le solaire
(autoconsommation ÷ consommation totale).</p>
<p><b>EDF OA (Obligation d'Achat)</b> — contrat par lequel EDF achète votre
surplus d'électricité à un prix fixe garanti.</p>
<p><b>Année OA</b> — cycle annuel du contrat. Le vôtre va du {debut_oa} au
{fin_oa} de l'année suivante.</p>
<p><b>Vente du surplus</b> — revenu tiré de l'électricité injectée et vendue à
EDF OA.</p>
<p><b>Prime à l'autoconsommation</b> — aide de l'État versée les premières
années du contrat, calculée selon la puissance (€/kWc).</p>
<p><b>Autoliquidation</b> — mécanisme par lequel c'est l'acheteur, ici EDF OA,
qui déclare la TVA à votre place. Vous n'en collectez donc aucune sur vos
ventes de surplus.</p>
<p><b>Livraison à soi-même (LASM)</b> — le fait de consommer ce qu'on a
produit soi-même. Pour un producteur assujetti à la TVA, c'est la seule part
de sa production qui soit taxable.</p>
<p><b>Ligne 5A (CA12 / 3517-S)</b> — la case de la déclaration annuelle de TVA
où se reporte la base de la livraison à soi-même. C'est le montant que calcule
l'onglet TVA autoconsommation.</p>
<p><b>Accise sur l'électricité</b> — taxe au kWh (autrefois CSPE, puis TICFE)
comprise dans le prix payé au fournisseur. Elle entre dans la base de la
livraison à soi-même ; la TVA, elle, n'y entre pas.</p>
<p><b>Prix unique (type Tarif Bleu Base)</b> — le kWh est facturé au même
prix à toute heure. C'est ce qui s'applique à vos achats jusqu'au
{veille_bascule}.</p>
<p><b>Heures Pleines / Heures Creuses (HP/HC)</b> — l'électricité est facturée
moins cher pendant les heures creuses. C'est ainsi que vos achats sont
comptés depuis le {bascule}.</p>
<p><b>Compteur Linky</b> — compteur communicant qui mesure l'énergie injectée
et soutirée.</p>
<p><b>Rendement spécifique</b> — production annuelle rapportée à la puissance
installée (kWh/kWc/an). Référence en France : 900 à 1200.</p>
<p><b>Économie d'autoconsommation</b> — argent économisé en consommant sa
propre production au lieu de l'acheter au réseau.</p>
<p><b>Bilan net</b> — recettes + économies − dépenses réseau (électricité
consommée + abonnement). Autrement dit : <b>ce que l'électricité vous coûte
encore</b>, une fois compté tout ce que le solaire vous rapporte ou vous
évite. Il passe au vert le jour où elle ne vous coûte plus rien.<br>
Attention à ne pas le confondre avec ce qui sort réellement de votre poche :
les économies ne sont pas encaissées. L'argent déboursé sur la période, c'est
l'achat au réseau moins la vente à EDF OA. Les infobulles des quatre cartes du
tableau de bord donnent le détail, vos chiffres à l'appui.</p>
<p><b>Abonnement</b> — part fixe de la facture d'électricité, payée chaque
mois quelle que soit la consommation. Comptée dans les dépenses réseau.</p>
<p><b>Amortissement</b> — moment où les gains cumulés égalent le coût de
l'installation ({invest}).</p>
<p><b>Retour sur investissement (ROI)</b> — durée estimée pour rembourser
l'investissement initial.</p>
"""


class AideView(BaseView):
    """Notice d'utilisation et glossaire des termes."""

    utilise_periode = False  # contenu fixe

    def populate(self, period: str) -> None:
        # Tout ce qui decrit l'installation vient de config.yaml : une seule
        # source de verite, pas un chiffre fige dans le texte. La notice
        # decrivait sinon l'installation de son auteur a tous ses lecteurs.
        champs = self._champs_installation()
        self.layout_inner.addWidget(SectionTitle(
            "Notice d'utilisation", "Comment utiliser l'application"))
        # Une carte par rubrique, et un sommaire qui y mene : la notice etait
        # un seul long bloc de texte (audit du 14/09/2026).
        rubriques = self._decouper(NOTICE_HTML.format(**champs))
        self.layout_inner.addWidget(
            self._sommaire([titre for titre, _ in rubriques] + ["Glossaire"]))
        self._cibles = []
        for _, corps in rubriques:
            carte = self._carte(corps)
            self._cibles.append(carte)
            self.layout_inner.addWidget(carte)
        titre_glossaire = SectionTitle(
            "Glossaire", "Définitions des termes employés")
        self._cibles.append(titre_glossaire)
        self.layout_inner.addWidget(titre_glossaire)
        self.layout_inner.addWidget(self._carte(GLOSSAIRE_HTML.format(**champs)))
        self.layout_inner.addStretch(1)

    _TITRE_RUBRIQUE = re.compile(r"<h3[^>]*>(.*?)</h3>", re.S)

    @classmethod
    def _decouper(cls, notice_html: str) -> list[tuple[str, str]]:
        """(titre, html) de chaque rubrique : une rubrique commence a chaque
        titre <h3>. Le texte lui-meme n'est pas modifie."""
        rubriques = []
        for morceau in re.split(r"(?=<h3)", notice_html):
            if not morceau.strip():
                continue
            trouve = cls._TITRE_RUBRIQUE.search(morceau)
            titre = (html.unescape(re.sub(r"<[^>]+>", "", trouve.group(1)))
                     if trouve else "")
            rubriques.append((titre.strip(), morceau))
        return rubriques

    def _sommaire(self, titres: list[str]) -> QFrame:
        """Les titres des rubriques, en liens : un clic fait defiler la page
        jusqu'a la rubrique."""
        card = Card()
        v = QVBoxLayout(card)
        v.setContentsMargins(24, 14, 24, 16)
        v.setSpacing(6)
        entete = QLabel("Sommaire")
        entete.setStyleSheet(
            f"color: {self.theme['text_primary']}; font-size: 14px; "
            "font-weight: 700;")
        v.addWidget(entete)
        couleur = self.theme["primary"]
        liens = " &nbsp;·&nbsp; ".join(
            f'<a href="{i}" style="color: {couleur}; text-decoration: none;">'
            f"{html.escape(titre)}</a>"
            for i, titre in enumerate(titres))
        lbl = QLabel(liens)
        lbl.setTextFormat(Qt.RichText)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
        lbl.setStyleSheet("font-size: 13px; line-height: 160%;")
        lbl.linkActivated.connect(self._aller_a)
        v.addWidget(lbl)
        return card

    def _aller_a(self, lien: str) -> None:
        """Fait defiler la page jusqu'a la rubrique choisie au sommaire."""
        cible = self._cibles[int(lien)]
        self.scroll.verticalScrollBar().setValue(max(cible.y() - 8, 0))

    def _champs_installation(self) -> dict:
        """Les valeurs que la notice et le glossaire vont chercher en config.

        Le cycle OA se deduit de la date de debut du contrat : il court d'un
        anniversaire a la veille du suivant. La bascule vers les heures
        creuses vient de tarifs_reseau.bascule_hphc.
        """
        cout = self.data.cfg["installation"]["cout_total_eur"]
        debut_oa = pd.Timestamp(self.data.start_oa)
        veille_oa = debut_oa - pd.Timedelta(days=1)
        bascule = calc.CUTOFF_OCTOPUS
        return {
            # Echappe : un « & » dans un nom de dossier casserait le HTML.
            "dossier": html.escape(self.data.dossier_donnees
                                   or "le dossier de l'application"),
            "invest": f"{cout:,.0f} €".replace(",", " "),
            "puissance": fmt_kwc(self.data.puissance_kwc) or "puissance inconnue",
            "mise_en_service": fmt_date_fr(self.data.date_mise_en_service),
            "debut_oa": f"{debut_oa:%d/%m}",
            "fin_oa": f"{veille_oa:%d/%m}",
            "bascule": f"{bascule:%d/%m/%Y}",
            "veille_bascule": f"{bascule - pd.Timedelta(days=1):%d/%m/%Y}",
            # Nom de la vue de comparaison, qui porte celui des deux offres.
            "comparaison": f"{self.data.fournisseur[1]} vs "
                           f"{self.data.fournisseur_reference[1]}",
        }

    def _carte(self, html: str) -> QFrame:
        card = Card()
        v = QVBoxLayout(card)
        v.setContentsMargins(24, 18, 24, 22)
        lbl = QLabel(html)
        lbl.setTextFormat(Qt.RichText)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"color: {self.theme['text_secondary']}; font-size: 13px;")
        v.addWidget(lbl)
        return card
