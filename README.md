# Acer Iconia A3-A40 — base de portage vers Android 13 ARM64

État : **analyse du firmware et premier correctif matériel, sans ROM Android 13
compilée, sans recovery personnalisé fonctionnel et sans essai sur tablette**.

La cible reste LineageOS 20 / Android 13 allégé, ARM64 avec compatibilité ARM32.
Ce dépôt n'est pas une ROM Amazon renommée. Il n'enregistre pas encore de cible
`lunch` : le noyau Android 13 et l'intégration des HAL restent à réaliser.

## Ce qui a réellement été fait

- ZIP Acer `0.013.00_WW_GEN1` téléchargé et contrôlé par CRC ZIP.
- Image système sparse décodée directement depuis le ZIP, sans montage.
- 2 557 entrées de fichiers inventoriées. Bibliothèques et configurations
  nécessaires à l'analyse extraites séparément ; aucun programme OEM exécuté.
- Bibliothèques Mali, gralloc, hwcomposer, audio, capteurs et caméra trouvées
  dans les variantes ARM32 et ARM64.
- Dépendances et symboles importés de 12 HAL/bibliothèques critiques relevés.
- Noyau 3.18.22 et DTB d'origine extraits, ainsi que les ramdisks de boot/recovery.
- Reconstruction du corps du recovery d'origine vérifiée octet pour octet.
- DTB décompilé et recompilé : propriétés, nœuds et réservations conservés.
- Premier correctif source 3.18.22 préparé contre un dépôt Acer épinglé.

## Sources et portée

Archive analysée :
`Acer_Iconia_Tab_10_A3-A40_MT8163_0.013.00_WW_GEN1_010516_6.0_(by_firmwarefile.com).zip`.
SHA-256 : `e3acc6e203d038159c438968fd94c6e4261d8b67d81597f1fccc37c25b367830`.
Il s'agit d'un paquet tiers contenant un firmware Acer ancien, pas d'une preuve
de correspondance avec le firmware `9.001.00` de la tablette de l'utilisateur.

Références :

- Firmware : https://firmwarefile.com/acer-iconia-tab-10-a3-a40/
- Noyau Acer candidat : https://github.com/acer-b1-790/android_kernel_acer_b1-790
  révision `d65e8c4b0f64f36603a16a3a3c386b17a5240d01`.
- Référence MT8163 Android 13 :
  https://github.com/mt8163/android_device_amazon_karnak_old/tree/lineage-20.0
  révision `54ba05fed9e936ad125b2a1cbcddf4c0260e9b6c`.
- Noyau 4.9 de référence, pas adapté à l'Acer :
  https://github.com/mt8163/android_kernel_amazon_karnak_4.9/tree/lineage-20.0

Le dépôt Acer candidat contient le même projet générique `neostra8163_tb_m`,
Linux 3.18.22 et les noms exacts des pilotes présents dans le binaire Acer :
`NT71397_WUXGA_DSI_VDO_NT65902` et les fonctions `eKTH3260`/`elan-ktf` dans le
répertoire `EKTH3386`. Le nom de ce répertoire ne prouve pas la référence exacte
du contrôleur actif. Ce dépôt contient plusieurs matériels et **n'est pas une
source A3-A40 exacte validée** : sa configuration générique sélectionne un écran
720×1280, un autre tactile et des capteurs/caméras non validés.

## Organisation

- `tools/boot_image.py` : inspection Android v0 / MediaTek, contrôle du SHA-1
  d'en-tête, aller-retour stock et empaquetage d'un ramdisk recovery de développement.
- `tools/inspect_system.py` : conversion sparse et extraction ext4 en lecture seule.
- `tools/audit_hal.py` : analyse ELF avec `readelf`, sans chargement des bibliothèques.
- `tools/check_hal_abi.py` : vérification des imports et dépendances transitives
  contre les bibliothèques d'un système cible réellement construit. Une référence
  Mali ARM64 a été vérifiée contre Android 6 : 29 fournisseurs, aucun symbole
  manquant. Cela ne valide pas la compatibilité avec Android 13.
- `tools/fetch_stock.py` et `sources/firmware.json` : récupération du paquet
  d'origine documenté avec contrôle strict de taille et de SHA-256.
- `tools/inspect_dtb.py` : extraction typée des propriétés DTB.
- `tools/prepare_kernel_candidate.py` : génération du correctif source partiel.
- `device/acer/acer_jetfirefhd/` : premiers fragments BoardConfig/produit/fstab Acer.
- `kernel/reference/acer_jetfirefhd.stock.dts` : description matérielle issue du DTB
  Acer, non convertie aux interfaces d'un noyau 4.9.
- `kernel/patches/` : correctif reproductible contre la source Acer épinglée.
- `evidence/` : faits observés, inventaires et limites ; aucune donnée utilisateur.

## Correctif noyau initial

Le correctif introduit un DTS reproduisant l'arbre du firmware Acer, un
defconfig de travail sélectionnant cet arbre, le panneau 1920×1200 observé et
le pilote tactile Elan. Il désactive le choix Goodix de la configuration donneuse.
Il ajoute une option qui bloque les points d'entrée internes de programmation
du firmware tactile pendant les essais. Les interfaces de debug/I2C n'ont pas
été entièrement auditées : ce mécanisme n'est pas une protection complète.

Ce correctif **reste en Linux 3.18.22**. Il sert à préparer un noyau/recovery
Acer reproductible. Les options héritées concernant la caméra, les capteurs,
l'alimentation et la batterie demandent une comparaison supplémentaire. Il ne
constitue ni un portage Linux 4.9 ni la prise en charge d'Android 13.

## Reproduire l'analyse

Python 3.10+ et GNU `readelf` sont nécessaires. Les chemins sont à remplacer
par ceux de votre environnement Linux ; aucune commande ne flashe la tablette.

```sh
python -m pip install -r requirements.txt
python tools/fetch_stock.py
python tools/inspect_system.py firmware.zip system.raw.img extraction
python tools/audit_hal.py extraction evidence/hal-audit.json
python tools/boot_image.py inspect boot.img
python tools/boot_image.py roundtrip boot.img
python tools/boot_image.py roundtrip recovery.img
python -m unittest discover -s tests -v
```

Sur un checkout propre de la source Acer exactement épinglée :

```sh
python tools/prepare_kernel_candidate.py /chemin/vers/noyau /chemin/vers/ce/projet
```

Un ramdisk recovery déjà construit peut ensuite être empaqueté hors ligne :

```sh
python tools/boot_image.py pack-recovery recovery-stock.img nouveau-ramdisk.cpio.gz recovery-dev.img --unsigned-development
```

Le script conserve le noyau Acer de l'image passée en entrée et les adresses de
chargement. Il ajoute l'en-tête MediaTek au nouveau ramdisk, recalcule le SHA-1
de l'en-tête et vérifie la limite de 16 Mio. Il retire la signature OEM devenue
invalide : l'image produite n'est donc pas utilisable comme image OEM signée.
Il ne compile pas TWRP, ne remplace pas le noyau par un noyau Android 13 et ne
garantit pas le démarrage. La signature OEM d'origine n'a pas été vérifiée
cryptographiquement.

## Travail nécessaire avant Android 13

1. Reconstituer et valider la configuration noyau propre à l'Acer. Choisir entre
   les rétroportages nécessaires sur 3.18 et une migration 4.9 avec pilotes Acer.
   Le DTB de 3.18 n'est pas une conversion automatique vers les interfaces 4.9.
2. Obtenir un démarrage recovery avec écran, tactile, USB et stockage corrects.
3. Adapter l'interface des HAL legacy aux services Android 13 et résoudre les
   imports ELF contre les bibliothèques réellement construites pour Android 13.
   Copier `libbinder`, `libui`, `libc` et tout Android 6 par-dessus Android 13
   n'est pas une solution à ces incompatibilités.
4. Choisir le stockage vendor sans inventer une partition séparée. La tablette
   dispose de `system`, `boot`, `recovery`, `cache`, `userdata`, sans `super` ni
   partition `vendor` observée. Aucun repartitionnement n'est inclus.
5. Définir la politique de chiffrement de la nouvelle installation. L'ancien
   firmware impose FDE et dm-verity ; le fstab recovery provisoire n'est pas la
   politique de chiffrement Android 13.
6. Construire LineageOS 20, puis valider boot, ADB, rendu, tactile, Wi-Fi,
   Bluetooth, audio, suspend/reprise et applications sur la tablette.

Le workspace utilisé pour cette analyse dispose d'un volume d'environ 8 Gio :
il suffit à cette extraction, pas à un arbre de sources et une compilation
complète d'Android 13. Aucun build complet n'a été lancé.

## Allègement visé

Conserver ARM64 et ARM32, WebView et les composants nécessaires aux applications.
Éviter les applications de démonstration et services superflus. Ne pas activer
automatiquement `ro.config.low_ram`, ni augmenter arbitrairement la zRAM, ni
changer le format de chiffrement sans validation. Les services Google seront un
choix d'intégration distinct, pas une condition du premier démarrage.

## Compilation expérimentale sur GitHub Actions

Le workflow `Source and binary-format tests` exécute les tests à chaque push.
`Experimental Acer kernel candidate` est un workflow manuel qui récupère la
source Acer épinglée, applique le correctif et tente une compilation avec le GCC
Android 4.9 de la branche Google `marshmallow-release`, épinglé à la révision
`4b341df712969ca2ac0c3cf6294260d406b9d9be`.

Les journaux et éventuels résultats de cette compilation sont conservés dans
un artefact nommé `NOT-FLASHABLE-kernel-investigation`. Un succès de compilation
ne validerait ni le matériel ni Android 13. Le script local équivalent est
`bash kernel/build-candidate.sh`; il ne demande pas de droits administrateur.

## État des validations

- Huit tests sur les formats boot/MTK/sparse réussis.
- Quatre tests supplémentaires du contrôle d'ABI avec de vrais fichiers ELF
  compilés pour les tests : fournisseur compatible, symbole supprimé,
  bibliothèque absente et architecture incorrecte.
- Corps du recovery Acer reconstruit à l'identique, hors signature retirée.
- Aller-retour du DTB vérifié sur les propriétés et les réservations.
- Correctif source contrôlé par `git diff --check` et vérification d'application.
- Noyau candidat : non compilé, non testé sur matériel.
- Android 13 : non compilé, non démarré ; aucune version flashable livrée.
