# Portage TWRP pour Acer A3-A40

État : arbre appareil préparé, extraction du noyau stock et empaquetage contrôlés
hors ligne. **TWRP n'a pas encore été compilé et aucune nouvelle image recovery
n'a été testée sur tablette.** Le noyau expérimental publié précédemment n'est
pas TWRP.

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
ici. Le comportement du noyau stock et la correspondance du firmware tactile
restent à établir avant un essai matériel. Aucune commande de flash/démarrage
n'est donc incluse dans cette recette.

## Construction locale

Prévoir une machine Linux x86_64 avec Python 3 pour nos outils, Python 2.7 comme
`python` pour l'ancien système Android 9, les dépendances de compilation Android
et le lanceur `repo`. Utiliser un environnement dédié à ces outils anciens.
Le script exige au moins 40 Gio libres ; prévoir plutôt 60 Gio ou davantage.
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
Le build vise `ramdisk-recovery.img`. Il n'utilise pas le résultat standard
`recovery.img` d'Android make : ce dernier ne gère pas nos en-têtes spécifiques.
Des fichiers intermédiaires, dont `boot.img`, peuvent être produits comme
dépendances ; ils ne doivent pas être utilisés sur l'Acer.

L'empaquetage final vérifie le CPIO, les en-têtes ELF AArch64 des trois exécutables
principaux, les fichiers XML TWRP, le fstab probe, les scripts Acer et les
propriétés ADB. Il ajoute les en-têtes MediaTek, conserve les adresses et le
noyau du modèle, recalcule le SHA-1 Android, retire l'ancienne signature OEM et
refuse une image dépassant 16 Mio. Les dépendances ELF et la politique SELinux
restent à vérifier après compilation. Une validation de structure n'est pas une
validation de démarrage.

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

## Consommation GitHub Actions

Tous les workflows du dépôt sont maintenant **manuels** (`workflow_dispatch`).
Un push ou une pull request ne déclenche aucune compilation ni aucun test.
Ce portage ne crée aucun workflow TWRP. Les contrôles sont exécutés localement.
Les plafonds existants sont de 10 minutes pour les tests et 45 pour le noyau,
uniquement si quelqu'un les déclenche explicitement. Cela ne suit ni ne plafonne
la consommation éventuelle des autres dépôts du compte.
