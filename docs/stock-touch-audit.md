# Tactile Elan : vérification du noyau stock disponible

Résultat du 20 novembre 2026 : **aucun chemin d'appels directs vers le programmeur
de firmware n'a été trouvé depuis les deux routines de démarrage examinées**.
Cela affine l'inquiétude initiale fondée sur la source Acer candidate, sans
certifier l'ensemble du pilote ni le matériel de la tablette actuelle.

## Binaire effectivement étudié

Recovery Acer `0.013.00`, SHA-256
`4aa1ff4a7b824e57839f929730f9cd5798cb6bffa4ec0c978d86ff147f932aee`.
L'Image ARM64 décompressée a pour SHA-256
`3ac70724f3db3054a4696d54e5d07e76717607526d124d7c97494aae7862de21`.
Elle est différente, par sa provenance, du firmware `9.001.00` actuellement
installé sur la tablette. Aucune lecture de celle-ci n'a été effectuée ici.

`vmlinux-to-elf` 1.4.0 a récupéré 63 033 symboles kallsyms et reconstruit un ELF
avec base virtuelle inférée `0xffffffc000080000`. Notre contrôle compare ensuite
la section `.kernel` de cet ELF à l'Image d'origine **octet pour octet**.
Les bornes des fonctions sont déduites des symboles de texte suivants, pas
d'informations de débogage fournies par Acer.

## Ce qui est observé

- `elan_ktf_ts_probe` prépare une tâche différée dont le callback est
  `elan_ic_init_work` (`0xffffffc00066f7e8`, 928 octets).
- Ce callback reconnaît notamment les identifiants `0x0fcc` et `0x1b00`, extrait
  les identifiants/versions embarqués, puis compare l'identifiant et la version
  présents. On retrouve les branches correspondant à une version embarquée
  supérieure, une version non supérieure et un identifiant différent.
- Dans ce binaire, les branches observées passent par des messages de journal,
  déverrouillages, délais et lectures d'état. Aucun appel direct au programmeur
  n'y apparaît. La source candidate ne peut donc pas être assimilée à ce binaire
  sur la seule présence de noms de fonctions communs.
- L'exploration des appels directs depuis probe et le callback couvre sept
  fonctions de ce bloc de pilote, dont les helpers reset, hello, poll et lecture
  d'informations firmware. `Update_FW_in_Driver.isra.17` n'est pas atteinte par
  ces arêtes.
- **Le programmeur existe toujours**, à `0xffffffc0006701cc`. Il appelle
  `EnterISPMode`, `i2c_master_send` et les fonctions d'acquittement. Son absence
  du graphe de démarrage étudié ne le neutralise pas.
- Probe contient un appel indirect à `0xffffffc00066ece4`, cohérent avec une
  interrogation des fonctionnalités de l'adaptateur I2C. Sa cible n'est pas
  résolue par ce contrôle. Les callbacks de frameworks et autres threads ne
  sont pas couverts par une preuve d'absence de programmation.

Le détail des fonctions et appels décodés est dans
[`evidence/stock-touch-audit.json`](../evidence/stock-touch-audit.json).

## Une lecture sysfs n'est pas forcément sans effet

Dans le binaire, `show_reset` appelle directement `elan_ktf_ts_hw_reset`.
La source Acer candidate confirme son raccordement à l'attribut lisible `reset`.
Elle expose aussi des attributs de calibration et de modification des IRQ.
Le nom ou le mode en lecture d'un fichier ne garantit donc pas une lecture
purement informative.

Le collecteur PowerShell ne lit aucun de ces attributs, aucun nœud constructeur
I2C/tactile et aucun répertoire sysfs par recherche récursive. Il recueille les
propriétés Android déjà publiées, `/proc/bus/input/devices`, les capacités input
et une liste limitée d'attributs standard du framebuffer. La propriété
`ro.acer.touch_fw_version` est une information déclarée par le firmware Android,
pas une interrogation indépendante du contrôleur.

## Reproduire le contrôle

Les outils d'analyse restent séparés du runtime de la tablette. Avec une Image
extraite du recovery identifié et un environnement Python dédié contenant
`vmlinux-to-elf==1.4.0` :

```sh
vmlinux-to-elf kernel.Image stock-analysis.vmlinux
python tools/audit_stock_touch.py kernel.Image stock-analysis.vmlinux --nm /chemin/aarch64-linux-android-nm --output /chemin/audit.json
```

Le second outil vérifie le hash identifié et la correspondance de la section
avant de décoder les instructions `BL`, les branches terminales `B`, les branches
conditionnelles sortant de la fonction et les branches indirectes. Il ne modifie
ni le noyau ni la tablette. Ce contrôle
n'est pas une preuve formelle de tout le comportement du pilote et ne remplace
pas une validation matérielle du recovery.
