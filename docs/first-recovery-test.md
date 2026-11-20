# Préparer le premier essai du recovery A3-A40

Le collecteur est utilisable dès maintenant sur Android d'origine pour établir
un état de référence. Un essai du recovery nécessite encore une image construite
et contrôlée, ainsi qu'une méthode de démarrage compatible avec le bootloader.
Ce document ne prétend pas que ces conditions sont déjà remplies.

## Un seul fichier PowerShell sur le PC Windows

Télécharger [`Collect-AcerDiagnostics.ps1`](../tools/Collect-AcerDiagnostics.ps1)
et le placer dans le dossier `platform-tools` qui contient déjà `adb.exe`.
Depuis PowerShell dans ce dossier, tablette démarrée et reconnue par ADB :

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Collect-AcerDiagnostics.ps1 -AdbPath .\adb.exe
```

L'option d'exécution ne concerne que ce processus PowerShell ; elle ne modifie
pas la stratégie Windows enregistrée. Le script écrit un dossier horodaté et
un ZIP à côté, puis son SHA-256. Il ne demande pas les droits administrateur.
Si plusieurs appareils sont branchés, ajouter `-Serial NUMERO_DE_LA_TABLETTE`.
La syntaxe cible Windows PowerShell 5.1. Les tests automatisés ont exécuté le
collecteur avec PowerShell 7.4.6 sous Linux et un faux ADB ; aucun essai Windows
5.1 ni aucune collecte réelle sur tablette n'a été effectué ici.

Le rapport contient identité logicielle, mémoire, montages déjà présents,
partitions, périphériques input, capacités tactiles, framebuffer, SELinux,
processus, dmesg, logcat et, s'il existe, `/tmp/recovery.log`. Le script n'effectue
aucun montage, reboot, déverrouillage, flash, demande de root ou changement de
politique SELinux. Les commandes indisponibles ou refusées restent consignées.
Un délai par commande empêche une lecture bloquée de retenir tout le script.

Sous Android d'origine, le rapport est marqué comme état de référence, pas
comme validation de TWRP. Il ne sauvegarde pas les applications ni les fichiers
personnels. Les journaux peuvent contenir des identifiants : examiner le ZIP
avant de le publier ; aucun envoi vers GitHub n'est automatique.

## Avant de démarrer une image modifiée

1. Vérifier l'image finale `TWRP-A3-A40-PROBE-UNTESTED.img` et son rapport JSON.
   Le hash doit correspondre au champ `image_sha256`, la taille doit être au plus
   16 Mio et `stock_kernel_kept_unchanged` doit être vrai pour ce profil.
   `recovery.img` et `boot.img` intermédiaires ne sont pas les fichiers à utiliser.
2. Le dernier relevé fourni indiquait `unlocked: no`, `secure: yes`. Si la
   tablette est déjà en fastboot, on peut relire l'état sans le modifier :

   ```powershell
   .\fastboot.exe devices
   .\fastboot.exe getvar unlocked 2>&1
   .\fastboot.exe getvar secure 2>&1
   ```

3. La présence du réglage OEM n'est pas un déverrouillage effectif. L'image de
   développement n'a plus de signature Acer valide. Le déverrouillage, avec
   effacement des données, reste une opération séparée ; le collecteur ne le fait pas.
4. Le support du démarrage temporaire `fastboot boot` n'est pas établi. L'aide
   du programme fastboot sur le PC n'indique pas les commandes implémentées par
   la tablette. Ne pas déduire ce support de la présence de `download:`.
5. Le `lk.bin` du paquet ancien contient les chaînes `getvar:`, `download:`,
   `flash:`, `erase:`, `continue`, `reboot`, `oem reboot-recovery` et les commandes
   de déverrouillage, ainsi que `not support on security`. Cet inventaire de
   chaînes n'est pas une analyse des handlers et ne prouve pas les capacités du
   bootloader actuellement installé. Voir le
   [relevé JSON](../evidence/stock-lk-string-inventory.json).

La méthode de lancement devra être choisie une fois ces points vérifiés. Si le
démarrage temporaire n'est pas pris en charge, écrire la partition recovery est
une opération différente, avec une procédure de restauration à établir. Le
paquet `0.013.00` ne doit pas être présenté comme une sauvegarde exacte de
l'installation `9.001.00`. Aucune commande de flash de remplacement n'est
proposée automatiquement.

## Quand le recovery aura effectivement démarré

- Conserver le système en lecture seule si TWRP le propose. Ne pas lancer
  d'installation, de réparation, de formatage ou de déchiffrement pour cet essai.
- Vérifier lisibilité, couleurs et orientation de l'écran ; vérifier que les
  touches et menus répondent à la position réelle du doigt. Les capacités input
  seules ne vérifient pas les coordonnées tactiles.
- Exécuter le même collecteur PowerShell et conserver le nouveau ZIP. Vérifier
  ADB, framebuffer, périphériques input, partitions attendues et messages d'erreur.
- L'absence de `/data` et `/cache` dans le fstab du profil probe est volontaire :
  un stockage interne indisponible n'est pas une invitation à formater.

Le premier résultat attendu est un recovery de diagnostic avec écran, tactile,
ADB et accès aux blocs cohérents. L'installation d'un ZIP LineageOS appartient
à une étape ultérieure.
