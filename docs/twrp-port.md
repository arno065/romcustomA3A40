# Portage TWRP pour Acer A3-A40

État : arbre appareil préparé, extraction du noyau stock et empaquetage contrôlés
hors ligne. L'[image finale du run 5](recovery-run5-review.md), transmise par le
propriétaire, passe les contrôles de format, taille, hash et fermeture statique
ELF. **Aucune nouvelle image recovery n'a été testée sur tablette.**
Le noyau expérimental publié précédemment n'est pas TWRP. Le diagnostic reçu du
propriétaire est une [référence Android d'origine](owner-runtime-baseline.md).

## Base choisie

Le manifeste minimal Omni/TWRP `twrp-9.0` est destiné aux appareils livrés avec
Android 5.1 à 9. Il sert ici à construire le recovery, pas à remplacer Android 6
par Android 9. La cible de la future ROM reste Android 13. Un recovery basé sur
Android 9 ne garantit pas à lui seul l'installation d'une ROM Android 13 : le
format du ZIP, l'updater et l'organisation system/vendor devront être validés.

Le manifeste, le recovery TeamWin et les règles de construction TeamWin sont
épinglés dans `recovery/twrp/sources.json`. Les autres projets restent aux
révisions du manifeste ; le script exporte `repo manifest -r` après synchronisation
pour figer l'ensemble réellement utilisé. Aucun prétendu manifeste intégralement
verrouillé n'est fourni sans cette synchronisation.

## Profil du premier essai

- ARM64, comme l'exécutable recovery Acer d'origine ; compatibilité ARM32
  conservée dans la géométrie commune.
- Noyau et DTB conservés octet pour octet depuis le recovery Acer identifié.
  Le candidat recompilé avec paramètres matériels hérités n'est pas substitué.
- Écran 1920 × 1200, thème paysage, framebuffer `RGBX_8888` et stride du pilote.
  Ce choix suit le pilote Acer candidat ; couleurs, orientation et coordonnées
  tactiles nécessitent toujours un essai réel.
- Français et anglais conservés. Les langues supplémentaires et leurs grosses
  polices sont exclues pour respecter la partition recovery de 16 Mio.
- Initialisation USB TWRP legacy `android_usb`, avec le réglage MediaTek `cmode=1`
  observé dans le recovery Acer. Le script USB TWRP amont conserve son identifiant
  `18D1:D001` : le pilote Windows fastboot Acer ne prouve pas qu'ADB recovery sera
  déjà reconnu.
- ADB root sans authentification dans ce recovery de développement uniquement.
  Il donne un accès complet aux partitions, malgré les choix prudents du fstab.
- Pas de `/data`, `/cache`, `/misc`, NVRAM, bootloader, TEE ou métadonnées FDE dans
  le fstab du profil probe. `/system` utilise `ro,noload` pour éviter aussi la
  relecture du journal ext4. Boot/recovery sont proposés en sauvegarde, avec
  flash d'image et effacement désactivés dans ce profil.
- Pas de déchiffrement FDE, MTP, stockage USB de masse ou montage automatique de
  carte SD. Les fichiers d'essai passeront par ADB vers `/tmp`, en mémoire.

Ces paramètres ne constituent pas un verrou contre root ou un script ZIP : un
updater peut écrire directement sur les blocs. **Ce profil sert au diagnostic,
pas encore à installer une ROM.** Un profil d'installation viendra après les
essais matériels et la définition de la politique de chiffrement.

## Limite du noyau stock disponible

Le recovery disponible provient du firmware `0.013.00`, alors que la tablette
est en `9.001.00`. Conserver son noyau élimine les modifications du noyau donneur,
mais ne prouve pas sa correspondance avec la tablette actuelle.

Le pilote Elan du dépôt Acer candidat contient des chemins de mise à jour du
firmware tactile au démarrage. Le patch du noyau expérimental bloque plusieurs
de ces chemins ; **ces protections ne modifient pas le binaire stock** utilisé
ici. L'[analyse du binaire stock](stock-touch-audit.md) n'a trouvé aucun chemin
d'appels directs au programmeur depuis les deux routines de démarrage examinées.
Des limites subsistent sur les callbacks et les appels indirects ; la fonction
de programmation reste présente. Cela ne certifie pas la tablette actuelle.
Aucune commande de flash/démarrage
n'est donc incluse dans cette recette.

## Construction locale

Prévoir une machine Linux x86_64 avec Python 3 pour nos outils, Python 2.7 comme
`python` pour l'ancien système Android 9, les dépendances de compilation Android
et le lanceur `repo`. Utiliser un environnement dédié à ces outils anciens.
Le script exige au moins 40 Gio libres avant synchronisation et 20 Gio encore
libres avant compilation ; prévoir plutôt 60 Gio ou davantage au départ.
Ce seuil est une marge de préparation, pas une taille de build mesurée ici.
L'environnement actuel dispose d'environ 8 Gio au total et ne peut pas accueillir
cette compilation. Aucune synchronisation complète n'y a été lancée.

Depuis la racine de ce dépôt, sur la machine de compilation :

```sh
# Récupère les sources sur cette machine, sans utiliser GitHub Actions.
bash recovery/twrp/init-sources.sh /chemin/neuf/twrp-a3a40

# Utilise le recovery Acer dont le SHA-256 est documenté dans sources.json.
# Le répertoire appareil et celui de sortie ne doivent pas déjà exister.
bash recovery/twrp/build-local.sh /chemin/neuf/twrp-a3a40 /chemin/recovery-stock.img /chemin/neuf/resultat-twrp
```

La préparation copie la géométrie mesurée commune, extrait le noyau sans son
en-tête MediaTek et conserve le recovery stock comme modèle d'empaquetage.
Le build vise la cible standard `recoveryimage`. L'empaquetage récupère le ramdisk
du `recovery.img` généré après contrôle de son en-tête et de son SHA-1 ; à défaut,
il accepte `ramdisk-recovery.cpio` brut ou `ramdisk-recovery.img` compressé.
L'image finale est reconstruite avec les en-têtes MediaTek et le noyau stock
identifié. Le `recovery.img` standard n'est pas livré comme image pour l'Acer.
Des fichiers intermédiaires, dont `boot.img`, peuvent être produits comme
dépendances ; ils ne doivent pas être utilisés sur l'Acer.

L'empaquetage final vérifie le CPIO, les en-têtes ELF AArch64 des trois exécutables
principaux, les fichiers XML TWRP, le fstab probe, les scripts Acer et les
propriétés ADB. Il ajoute les en-têtes MediaTek, conserve les adresses et le
noyau du modèle, recalcule le SHA-1 Android, retire l'ancienne signature OEM et
refuse une image dépassant 16 Mio. Les dépendances ELF et la politique SELinux
restent à vérifier après compilation. Une validation de structure n'est pas une
validation de démarrage.

Le contrôle du SHA-1 de l'image intermédiaire reconnaît les deux conventions
du header v0 : trois sections pour l'ancien outil Acer, ou quatre tailles
(dont le DT absent de taille zéro) pour le mkbootimg Omni Android 9. Il vérifie
effectivement le hash dans les deux cas et refuse une image corrompue. Le packer
final Acer conserve sa convention stock. Un vecteur synthétique indépendant,
généré par l'outil Omni amont, est conservé dans
`tests/fixtures/omni-v0-no-dt.json` ; les détails du correctif sont dans
[`evidence/omni-boot-id-regression.json`](../evidence/omni-boot-id-regression.json).

## Taille du ramdisk

Le relevé fourni par le propriétaire montrait une image intermédiaire de
18 819 072 octets pour une limite de 16 777 216 : dépassement de 2 041 856 octets.
`TW_EXTRA_LANGUAGES=false` évite l'ajout des polices asiatiques. Le hook standard
`BOARD_RECOVERY_IMAGE_PREPARE` exécute ensuite `slim_twrp_resources.py` sur le
ramdisk du build, avant mkbootfs et compression : seuls `en.xml` et `fr.xml`
restent dans les langues. Le hook vérifie les polices référencées avant retrait,
conserve les ressources communes et actualise les index de fichiers du ramdisk.
Le noyau, ADB et les bibliothèques sont conservés.

Une mesure locale sur les seules polices/langues amont donne environ 2,56 Mo
de différence entre les agrégats gzip avant/après. Ce n'est pas une mesure de
l'image complète reconstruite. Le relevé est dans
[`evidence/twrp-resource-slimming.json`](../evidence/twrp-resource-slimming.json).

Après le prochain build, `ramdisk-size.json` indiquera la taille compressée,
le budget exact avec les en-têtes MediaTek et le noyau Acer, la marge restante
et les 30 plus gros fichiers décompressés. Ce diagnostic est aussi tenté en cas
d'échec de make sur la taille, sans masquer son code d'erreur. Le fichier est
conservé parmi les artefacts JSON du workflow. La limite finale reste 16 Mio et
l'empaquetage refuse toujours de la dépasser. La prochaine compilation complète
reste nécessaire pour confirmer le gain.

Si un contrôle échoue, le script s'arrête. Il n'y a ni téléchargement automatique
d'une image d'un autre appareil, ni flash, ni déverrouillage, ni wipe.

## Vérifications avant le premier essai matériel

1. Obtenir un ramdisk TWRP réellement compilé et contrôler sa fermeture de
   dépendances ELF, son poids et la compatibilité de sa politique SELinux.
2. Résoudre la question de la mise à jour tactile et choisir le noyau d'essai.
3. Vérifier l'état de déverrouillage et les commandes réellement acceptées par
   ce bootloader. La présence du réglage OEM ne prouve pas le déverrouillage ;
   le support de `fastboot boot` n'a pas été établi.
4. Vérifier ADB, framebuffer, tactile, stockage et journaux. Ne pas demander de
   formatage de `/data` pour faire disparaître un échec de déchiffrement.
5. Concevoir puis tester le profil d'installation séparé, avant un ZIP LineageOS.

## Construction GitHub Actions et consommation

Tous les workflows du dépôt sont **manuels** (`workflow_dispatch`). Un push ou
une pull request ne déclenche aucune compilation ni aucun test. Le propriétaire
a autorisé la construction TWRP sur Actions avec son plafond de dépenses à 0 €.
Le workflow `Build experimental Acer TWRP probe` utilise un runner Linux standard,
un seul job limité à 120 minutes, deux tâches de compilation et aucune matrice.
Les exécutions de ce workflow ne se chevauchent pas.

Le workflow libère de l'espace uniquement sur le runner jetable, installe les
outils Android anciens, vérifie le lanceur repo v2.54 par SHA-256, synchronise
les sources et récupère le firmware stock avec le contrôle de taille/SHA-256.
Seul le recovery nécessaire est extrait. Le ZIP de 1,5 Go est ensuite supprimé.
Le lanceur utilise `repo init --depth=1` et
`repo sync -c --force-sync --no-clone-bundle --no-tags -j$(nproc)`.
Un cache `.repo` utilise les actions `actions/cache/restore@v4` et
`actions/cache/save@v4`, avec une clé fondée sur le hash de `sources.json`, qui
contient la révision du manifeste. La restauration n'est activée que si au moins
60 Gio sont libres après nettoyage. La sauvegarde suit immédiatement une
synchronisation réussie, avant la compilation, et exige une marge libre d'au
moins la taille de `.repo` plus 25 Gio pour la compression et le build. Un échec
de cache, notamment faute de quota, n'arrête pas la compilation. Seuls les objets
et métadonnées `.repo` sont cachés ; les fichiers de travail sont recréés par
`repo sync`. Le script refuse toujours d'écraser un arbre de travail existant.

Les résultats et journaux sont conservés trois jours,
sans publication automatique de release ni envoi du firmware OEM complet.
Une image n'est jointe que si la construction puis les contrôles d'empaquetage
ont réussi. Elle reste marquée UNTESTED et ne constitue pas une validation matérielle.

Les autres limites restent de 10 minutes pour les tests et 45 pour le noyau.
Aucun réglage de facturation n'est modifié. Ces limites ne suivent ni ne plafonnent
la consommation des autres dépôts du compte. Un nouveau lancement reste explicite ;
il n'y a pas de boucle de relance automatique.
