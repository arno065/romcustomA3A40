# Passage des composants Acer Android 6 vers Android 13

Ce document décrit des travaux à réaliser, pas des composants déjà fonctionnels.
La source Acer 3.18.22 et les bibliothèques du paquet 0.013.00 sont des bases
d'investigation. Les essais sur l'exemplaire en 9.001.00 restent nécessaires.

## Affichage et accélération graphique

Les binaires ARM64 présents dans le paquet Acer sont :

| Composant | Dépendances directes | Symboles globaux importés |
| --- | ---: | ---: |
| Mali EGL/GLES | 14 | 273 |
| gralloc MT8163 | 12 | 46 |
| hwcomposer MT8163 | 18 | 192 |

Les noms de panneau et de tactile ont été retrouvés dans le binaire du noyau,
et le dépôt noyau Acer contient ces pilotes. Le correctif matériel sélectionne
ces pilotes avec l'arbre extrait du firmware. La correspondance des variantes
de panneau/tactile présentes sur chaque tablette n'a pas encore été testée.

Le pilote Mali dépend notamment de `libui`, `libbinder`, `libutils`, `libcutils`
et de bibliothèques MediaTek. Le fait qu'une bibliothèque Android 13 porte le
même nom ne garantit pas qu'elle expose les mêmes symboles ou la même ABI C++.

Le contrôle statique du Mali ARM64 contre les fournisseurs Android 6 réussit :
29 bibliothèques fournissent les dépendances et symboles requis. Ce résultat
constitue une référence pour l'analyseur, pas une validation contre Android 13.
L'outil `check_hal_abi.py` doit être exécuté avec les bibliothèques du système
cible réellement construit avant d'écrire des shims ciblés. Il ne simule pas
les namespaces du linker, les protocoles HAL ou les ioctl du noyau.

Un premier [adaptateur de l'appel `GraphicBufferMapper::lock`](graphics-lock-bridge.md)
est écrit et vérifié en objet AArch64 et par des tests de transfert d'appel.
Il n'est pas encore intégré au système Android ou testé contre le vrai `libui`.

Travaux suivants : construire/sélectionner les interfaces graphics compatibles,
adapter le chemin legacy gralloc/HWC, vérifier les imports exacts puis valider
le rendu et les tampons sur matériel. Ne pas copier les bibliothèques centrales
Android 6 par-dessus celles d'Android 13 pour masquer les différences.

## Audio

`audio.primary.mt8163.so` ARM64 importe 246 symboles globaux et 28 bibliothèques,
dont `libmedia`, `libbinder` et les bibliothèques de paramètres audio MediaTek.
Il faudra examiner les interfaces legacy utilisables et les routes propres à
l'Acer. La présence d'un service audio pour karnak ne valide ni les amplificateurs,
ni le casque, ni les haut-parleurs de l'Acer.

## Wi-Fi et Bluetooth

La source candidate comprend les pilotes de connectivité MT8163 et WLAN gen2.
Il reste à vérifier le couplage avec les programmes WMT, les firmwares et les
configurations du paquet Acer, ainsi que les services Android 13. Une compilation
du pilote ne prouve pas le chargement du firmware ou la connexion réseau.

## Caméra, capteurs, alimentation

La configuration donneuse sélectionne des caméras et capteurs non vérifiés pour
l'A3-A40. Les sections observées du DTB sont conservées, mais elles ne suffisent
pas à reconstituer tout le defconfig. Les réglages de batterie, de charge et de
régulation doivent être comparés avant tout essai d'un noyau recompilé.

La première étape de validation reste un recovery avec écran, tactile, USB et
stockage corrects. La caméra peut rester hors du premier démarrage Android de
développement ; elle n'est pas déclarée supprimée du projet.

## Noyau et stockage

Le premier noyau candidat reste en 3.18.22 afin d'étudier une base proche du
firmware Acer. La prise en charge des fonctions attendues par Android 13 n'est
pas implémentée par ce correctif. Une migration 4.9 exigerait une adaptation
des pilotes, des interfaces et de l'arbre matériel ; elle ne consiste pas à
remplacer le numéro de version ou à réutiliser directement un noyau Amazon.

Les partitions Acer restent inchangées. Aucun `super`, slot A/B ou espace vendor
séparé n'est inventé. La politique de chiffrement d'une future installation
Android 13 n'est pas définie par l'ancien fstab FDE.

## Critères pour annoncer une version Android 13

Avant de déclarer une alpha utilisable : démarrage Android et ADB, affichage,
tactile, stockage, Wi-Fi, rendu graphique, audio, veille/reprise et installation
d'applications doivent avoir des résultats d'essais documentés. Le niveau de
correctif de sécurité annoncé ne doit pas être artificiellement relevé.
