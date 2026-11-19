# Premier adaptateur graphique Acer

`hardware/acer/graphics-lock/mapper_lock.c` propose un adaptateur pour un seul
appel legacy. Il n'est pas encore installé dans une image, injecté dans un HAL
ou validé sur la tablette.

## Besoin observé

Les deux variantes du HAL Acer `hwcomposer.mt8163.so` importent :

```text
_ZN7android19GraphicBufferMapper4lockEPK13native_handlejRKNS_4RectEPPv
```

L'en-tête `GraphicBufferMapper.h` de LineageOS 20 déclare l'API avec deux
paramètres de sortie supplémentaires et des valeurs par défaut. Les valeurs
par défaut en C++ ne créent pas un ancien symbole binaire supplémentaire.
L'adaptateur fournit donc l'ancien symbole et appelle la signature longue :

```text
_ZN7android19GraphicBufferMapper4lockEPK13native_handlejRKNS_4RectEPPvPiS9_
```

Il transmet les pointeurs et le champ `usage` sur 32 bits, fournit deux pointeurs
nuls pour les sorties supplémentaires et conserve le code de retour signé
`status_t`. Les arguments nuls obligatoires sont refusés avec `BAD_VALUE`.
Aucun objet C++ n'est alloué ou lu, aucune disposition mémoire de classe n'est
définie dans cet adaptateur et aucune copie de `libui` Android 6 n'est incluse.

## Références

- En-tête cible :
  https://github.com/LineageOS/android_frameworks_native/blob/lineage-20.0/libs/ui/include/ui/GraphicBufferMapper.h
  — blob Git `507fa355a495caf2a1624567d91e6e9e5c75952d`.
- Même transformation d'appel présente dans la référence MT8163 :
  https://github.com/mt8163/android_device_amazon_karnak_old/blob/54ba05fed9e936ad125b2a1cbcddf4c0260e9b6c/libshims/libshim_gui.cpp
- Imports Acer : `evidence/hal-audit.json`.

L'implémentation de ce dépôt est limitée à l'appel effectivement observé dans
le compositeur Acer. Elle n'ajoute pas les autres fonctions du shim karnak,
et elle conserve explicitement un résultat de type entier signé.

## Validation et limites

Trois tests compilent et chargent une bibliothèque native avec un fournisseur
simulé. Ils vérifient la transmission des pointeurs et du champ usage, les
sorties supplémentaires nulles, la propagation de succès/erreur et le rejet
d'un pointeur de sortie invalide. Il s'agit de tests du transfert d'appel,
pas de tests du vrai `libui` Android 13.

Le fichier C a aussi été compilé en objet AArch64 avec GCC Android 4.9. La table
des symboles contient exactement l'ancienne entrée définie et la nouvelle
entrée externe attendue. Le module Soong, sa variante ARM32 et sa liaison avec
le véritable `libui` cible n'ont pas encore été construits.

Il reste à choisir l'intégration au linker/vendor, vérifier que le symbole
cible est réellement exporté dans la construction retenue, vérifier la validité
de l'objet mapper fourni par le client, puis tester la synchronisation et les
tampons sur matériel. Les autres différences d'ABI, les services HWC/gralloc et
les interfaces noyau ne sont pas corrigés par cette seule passerelle.
