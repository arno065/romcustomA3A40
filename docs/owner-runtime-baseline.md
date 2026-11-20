# État de référence de la tablette du propriétaire

Le ZIP transmis le 20 novembre 2026 a été contrôlé par CRC et lu hors ligne.
Il contient 14 fichiers. Les 12 commandes consignées ne présentent aucun délai
dépassé. La collecte a été exécutée avec Windows PowerShell 5.1.19041.7802.
Il s'agit d'**Android d'origine, pas d'un démarrage TWRP** : build
`Acer_AV0M0_A3-A40_9.001.00_WW_GEN1`, Android 6.0, correctif 2017-05-05, noyau
ARM64 3.18.22 compilé le 25 mai 2017, UID shell 2000 et SELinux Enforcing.

Les faits utiles au portage, sans les journaux bruts, sont conservés dans
[`evidence/owner-runtime-baseline.json`](../evidence/owner-runtime-baseline.json).
Le ZIP et les journaux contenant potentiellement des identifiants restent en
dehors du dépôt public.

## Confirmations pour le recovery

| Élément | Mesure sur la tablette | Conséquence |
|---|---|---|
| Framebuffer | `mtkfb`, 1920 × 1200, 32 bits, stride 7680 octets | Dimensions et stride cohérents avec la configuration TWRP actuelle |
| Taille virtuelle du framebuffer | 1920 × 2400 | Géométrie pour deux hauteurs de 1200 ; ce n'est pas un écran 1920 × 2400 |
| Partitions boot/recovery | 16 777 216 octets chacune | Limite de 16 Mio confirmée |
| System/cache/userdata | Identiques à la géométrie déjà enregistrée | Aucune correction de taille nécessaire |
| Mémoire visible par Linux | 1 987 660 Kio | Cohérent avec la capacité nominale de 2 Go |
| Données | `ro.crypto.state=encrypted`, `/data` via dm-1 | Le profil probe sans `/data` reste approprié |

L'ordre des canaux de couleur RGBX/BGRA n'a pas été mesuré par ce collecteur :
32 bits par pixel ne suffit pas à le confirmer. Aucun essai d'affichage du
recovery n'a encore été fourni.

## Tactile : faits nouveaux, pas encore de calibration

La propriété du firmware Android déclare `ID:FCC VER:1015`. Le paquet ancien
analysé déclarait `ID:FCC VER:1014`. Cette propriété est une indication publiée
par Android, pas une lecture indépendante de la mémoire du contrôleur.

Deux périphériques input sont présents :

| Nom | ABS_MT_POSITION_X | ABS_MT_POSITION_Y |
|---|---|---|
| `elan-touchscreen` | 0 à 2048 | 0 à 3264 |
| `mtk-tpd` | 0 à 1200 | 0 à 1920 |

Les numéros `event4` et `event5` observés sont susceptibles de changer selon le
noyau et l'ordre de détection. Ces plages ne sont pas la résolution physique de
l'écran. Elles ne disent pas à elles seules quel périphérique produit les
événements réels, ni si une rotation ou permutation d'axes sera nécessaire dans
TWRP. Aucun blacklist, swap ou flip n'est ajouté sur cette seule base.

Le dmesg fourni contient une reprise du pilote Elan et de l'affichage, mais pas
la décision initiale concernant le firmware tactile. Il ne complète donc pas
la preuve concernant tous les chemins de programmation au démarrage.

## Interprétation des erreurs de collecte

La liste par noms des partitions renvoie `Permission denied`, bien que le
client ADB ait rapporté le code 0 pour la commande composée. Les sorties des
commandes doivent donc aussi être lues ; un code 0 ne signifie pas que toutes
les lectures ont été autorisées sur cet ancien shell. `/proc/partitions` a
cependant bien fourni les tailles nécessaires. Aucun `/tmp/recovery.log`+n'est présent, ce qui est attendu sous Android d'origine.

Le diagnostic ne renseigne pas l'état actuel du déverrouillage du bootloader.
Il fournit désormais une référence concrète à comparer au premier rapport
du recovery personnalisé. Aucune modification supplémentaire sur la tablette
n'est nécessaire pour exploiter ce ZIP.
