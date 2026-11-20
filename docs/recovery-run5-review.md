# Revue de l'artefact TWRP, run 5

**Les contrôles hors ligne passent sur l'image finale transmise par le
propriétaire. Aucun démarrage sur tablette n'a encore été validé.**

Le ZIP `Acer-TWRP-PROBE-UNTESTED-5.zip` est une archive d'artefacts GitHub : il
contient l'image à examiner et ses journaux. Ce n'est pas un ZIP d'installation
LineageOS. Le fichier final est `TWRP-A3-A40-PROBE-UNTESTED.img`.

## Résultats

| Contrôle | Résultat |
|---|---|
| CRC du ZIP | Valide |
| Taille de l'image | 16 238 592 octets |
| Limite de la partition recovery | 16 777 216 octets |
| Marge | 538 624 octets, soit 526 Kio |
| Format | Android v0, pages de 2048 octets, en-têtes MediaTek cohérents |
| SHA-1 d'en-tête | Valide, recalculé sur les sections de l'image finale |
| SHA-256 | `fb49b04725692e80d82c4dc7edeab4a1366d4f20dc797cf6b79333a396fe0e6c` |
| Adresses kernel/ramdisk/tags | `0x40080000`, `0x44000000`, `0x4e000000` |
| Noyau | Section entière identique au recovery Acer 0.013.00 de référence |
| Ramdisk | 416 entrées CPIO, 9 877 492 octets compressés |
| Langues | Anglais et français uniquement |
| Exécutables principaux | Init, recovery, adbd et shell AArch64 |
| Dépendances statiques | 95 objets ELF ; 33 programmes examinés, tous passent |
| Politique SELinux | Format version 30, comme le recovery stock ; chargement non testé |

Le contrôle des dépendances suit les `DT_NEEDED` et vérifie les imports forts
contre les exports de leur fermeture transitive. Le loader `/sbin/linker64`
publie le SONAME `ld-android.so` : ce nom est résolu par l'interpréteur déjà
chargé, sans inventer un fichier manquant dans l'image. Init et adbd sont liés
statiquement. La recherche de bibliothèques à l'exécution, les chargements
dynamiques par nom, les interfaces noyau et le matériel restent à tester.

Les scripts Acer d'initialisation USB, la configuration ADB et le fstab probe
correspondent au dépôt. Le profil conserve `/system` en lecture seule avec
`noload`, et omet `/data`, `/cache` et les partitions de firmware. Les lectures
et effacements que pourrait effectuer un programme root ne sont pas bloqués
par ce seul fstab. Ce recovery reste destiné au diagnostic initial.

Le manifeste résolu des 226 projets a été conservé, ce qui permet désormais
d'identifier les révisions exactes utilisées pour cette image.

## Ce qu'il reste à établir avant l'essai

L'image est **non signée par Acer** : la signature du paquet d'origine a été
retirée puisqu'elle ne correspond plus au ramdisk modifié. Le dernier état
fastboot transmis indiquait un bootloader verrouillé ; son état actuel n'est
pas déduit de la réussite du build. Le support d'un démarrage temporaire par
`fastboot boot` n'a pas été établi non plus.

Le noyau vient du paquet 0.013.00 de 2016, tandis que la tablette fonctionne
actuellement avec le firmware 9.001.00 de 2017. Son identité au modèle de
référence ne prouve donc pas son identité au noyau installé sur la tablette.

La prochaine étape est de relire l'état du bootloader et de choisir la méthode
de démarrage réellement prise en charge, puis de vérifier écran, tactile et
ADB dans le recovery. Le déchiffrement et l'installation d'une ROM ne font pas
partie de cette validation initiale. Aucune commande de flash ou de
déverrouillage n'a été exécutée pendant cette revue.

## Relevés conservés

- [Synthèse avec empreintes et limites](../evidence/recovery-run5-review.json)
- [Fermeture statique ELF par programme](../evidence/recovery-run5-elf-audit.json)
- [Manifeste résolu de la construction](../evidence/recovery-run5-sources-resolved.xml)

Les exécutables ARM n'ont pas été lancés sur la machine d'analyse. Aucun
workflow GitHub Actions n'a été lancé ni surveillé pour examiner cette archive.
