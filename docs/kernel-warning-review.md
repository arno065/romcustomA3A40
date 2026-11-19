# Première analyse des avertissements de sections

Les 42 avertissements de la compilation initiale restent présents. Aucun n'a
été masqué, et aucun `__init` n'a été ajouté uniquement pour faire taire modpost.
Le noyau publié reste inchangé.

Dans la révision Acer `d65e8c4b0f64f36603a16a3a3c386b17a5240d01` :

- `drivers/misc/mediatek/mem/mtk_meminfo.c` expose `get_max_DRAM_size()` et
  appelle conditionnellement `init_get_max_DRAM_size()` marqué `__init` lorsque
  les tailles en cache sont nulles. L'initialisation est aussi un early_initcall.
  Il faut prouver que la branche ne peut pas être prise après libération de
  `.init.text`, y compris sur les chemins d'erreur, avant de la considérer bénigne.
- `drivers/misc/mediatek/boot/mt_boot_common.c` expose des accesseurs qui passent
  par `init_boot_common()`. Celui-ci utilise une machine d'état et appelle un
  scanner DT marqué `__init`. Le cache rend certains chemins conditionnels,
  sans démontrer à lui seul que tout appel tardif est impossible.
- `drivers/misc/mediatek/base/power/mt8163/mt_idle.c` exporte
  `mt_cpuidle_framework_init()`, qui appelle des auxiliaires d'initialisation.
  Son export ne permet pas de supposer que tous ses appelants sont précoces.

Les autres groupes touchent notamment USB, scan mémoire, boot reason,
videolfb, systracker et ATF. Le relevé brut et le décompte sont dans
`evidence/kernel-section-mismatches.log` et
`evidence/kernel-section-mismatch-summary.json`.

Ce diagnostic motive la séparation entre le noyau expérimental et la première
préparation TWRP qui conserve un noyau stock. Il ne certifie pas le noyau stock,
dont la version diffère de celle de la tablette actuelle et dont les chemins
de mise à jour tactile restent à examiner.
