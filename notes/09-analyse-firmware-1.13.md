# 09 · Analyse de l'image firmware officielle 1.13 (vérifié)

Fait le 25/09/2026 sur l'OS officiel `model-cycles_OS1.13.syx` téléchargé depuis elektron.se, avec `elektron-firmware-tool` (commit figé `a5bce9a`),
un désassembleur ColdFire (capstone) et le manuel utilisateur OS 1.13. Tout ce qui suit est **vérifié sur l'image ou le manuel**, sauf mention `[HYP]`.

Fichiers de travail (non versionnés, dans `build/re/` et `firmware/`) : section 3 extraite, module `mcfw.py`, listing du pilote USB.

> **Limite de méthode** : capstone (mode M68K_040) désassemble bien le pilote USB, mais **ne décode pas les instructions EMAC** (`mac.l`, `msac.l`, `mvs`, `mvz`…) que le mixeur et le DSP utilisent abondamment — elles ressortent en `dc.w`/`.short`. Pour ces zones, passer à **Ghidra** (`68000:BE:32:Coldfire`). Les grandes lignes du mixeur ci-dessous restent lisibles malgré ces trous.

---

## 1. Version, provenance, empreintes

- **`[FAIT]`** **1.13 est la dernière version.** Les notes de version officielles s'arrêtent à « 1.12 → 1.13 », et la page de support ne propose que `model-cycles_OS1.13.zip` (septembre 2024).
  Donc « la dernière » = **1.13**, et le patch de ms-multi-output s'applique tel quel. C'est confirmé : le build reproduit l'image octet pour octet.
- **`[FAIT]`** Empreintes (à ajouter aux références de [README](README.md#chiffres-clés-os-113)) :

| Fichier | SHA-256 |
|---|---|
| `model-cycles_OS1.13.zip` | `bea11b4e3e996a92c0651d1d1039542e41df183da876208bed1cf4c4e9b7f6b2` |
| `model-cycles_OS1.13.syx` | `44fe586269631a0ca7da25a3383fc6733c314809505fc3cc52f1e0ed9800640c` |
| section 3 (MAIN OS) extraite | `cc99d4f0175d34d1e91d046e6ec85a5e8ab58ab9edbb3c24406acd48cb99ee98` |
| build patché `mc-multi-output.syx` | `9c631bc276baaae52270a8256a0213b3c1e9076f9b192137bd6e06d887fe22f6` ✅ reproductible |

## 2. Structure du conteneur ELE3 (vérifié)

L'OS Cycles a **4 sections** (et non les hypothèses de [02](02-format-os-syx.md)) :

| id | nom | taille décompressée | `dest` (table ELE3) | remarque |
|---|---|---|---|---|
| 5 | meta | 15 o (brut) | 0 | horodatage ASCII `210525 16:37:28` |
| 2 | bootstrap | 26 602 o | `0x04000000` | code ColdFire ; menu de démarrage. En-tête interne `[taille][0x80010000]`. Chaînes : `STARTUP MENU`, `OS UPGRADE`, `EMPTY RESET`, `FACTORY RESET`, `RECEIVING...`, `PLEASE RESTART ME` |
| 3 | **MAIN OS** | **1 744 192 o** | `0x40000400` | **la cible du mod** |
| 4 | updater | 31 752 o (brut) | `0x80000400` | |

- **`[FAIT]`** Trailer **HMAC-SHA256**, chaîne de dérivation de clé = **`"REVERB SEND"`**, clé retrouvée depuis l'image : `8c0e4553…9a0b98bd`. Le mécanisme de [02 §4](02-format-os-syx.md#4-conteneur-ele3) est donc confirmé sur le Cycles.
- Chaîne de build ELE3 = `0038`, version affichée `1.13`, checksum de contenu `0x26369ffc`.

## 3. Le menu de démarrage et l'upgrade (manuel, confirme [06](06-flash-et-recuperation.md))

- **`[FAIT]`** **Menu de démarrage** (manuel §13) : maintenir **[FUNC]** à l'allumage, puis **[TRIG 1]** EXIT, **[TRIG 2]** EMPTY RESET, **[TRIG 3]** FACTORY RESET, **[TRIG 4]** OS UPGRADE.
  Ma note [06 §2](06-flash-et-recuperation.md#2-flasher) (« TRIG 4 ») est donc **confirmée**.
- **`[FAIT]`** **« USB MIDI transfer is not possible when upgrading the OS from the STARTUP menu. »** (manuel §13.4) → la récupération n'est possible **que par l'entrée MIDI IN** (jack TRS du M:C, avec ou sans adaptateur DIN, cf. [12](12-flash-par-jack-trs.md)). C'est bien la raison d'exiger une interface MIDI.
- **`[FAIT]`** L'upgrade normal (`CONFIG → UPGRADE`, §12.6) passe par USB avec Transfer, **mais** le mod casse l'USB-audio ; l'upgrade par le menu de démarrage (MIDI IN) reste la voie sûre.

## 4. Réglages USB de la machine (manuel + image)

- **`[FAIT]`** **`CONFIG → DEVICE → USB MODE`** (§12.7.1) a deux valeurs : **`A+M`** (« carte son **et** interface MIDI ») et **`MID`** (MIDI seul).
  Confirmé dans l'image par les chaînes `USB mode`, `A+M`, `MID`, `USB+MIDI` et la fonction de sélection de mode.
- **`[FAIT]`** **`CONFIG → AUDIO → TRK OUT`** (§12.4.3) : « Sets if the separate tracks sends audio to the MAIN OUT, HEADPHONES OUT, **and USB** or not. »
  → Il existe **déjà** une notion de routage audio par piste ; en stock l'USB reste stéréo, mais ce réglage est un point d'entrée intéressant pour un mode configurable ([08 §D](08-feuille-de-route.md#d-mode-sélectionnable-dans-settings-stéréo--6--8-canaux)).
- **`[FAIT]`** `INT OUT` (§12.4.2) a un mode **`AUT`** : le M:C coupe l'audio interne vers MAIN/HEADPHONES **quand il envoie et reçoit de l'audio par USB**. À garder en tête pour les tests.
- **`[FAIT]`** `USB GAIN` (§12.4.6, 0 à +18 dB) n'affecte que l'audio **hôte → device**, pas les stems. `DEL OUT` / `REV OUT` routent les effets vers MAIN/HEADPHONES/USB.

### Correction de [04 §3](04-usb-audio.md#3-descripteurs)
La **table des modes USB à `0x4013e544` a 4 entrées de stride `0x28`**, ce qui correspond vraisemblablement à **{A+M, MID} × {2 vitesses USB}** `[HYP]`, et non à « CDC/MIDI » comme je l'avais supposé.
Le patch redirige **les 4 entrées** vers la config audio+MIDI HS de 328 o (`0x4019b2b6`). Les blobs libérés (75 o et 101 o) hébergent les stubs.
Mon décodage des blobs (interfaces Audio Control + MIDIStreaming pour les 101 o ; IAD classe 02/02/01 pour les 75 o) **reste exact en tant que données** ; c'est leur étiquette « mode » qui était à préciser.

## 4bis. Caves de code libres (0xff) — ressource pour toutes les extensions

> ⚠️ **Correction** ([14 §5](14-machine-sd-vintage.md#5-place-libre--les-caves-0xff-étaient-des-masques-de-sprites)).
> - Les 4 plus gros blocs ne sont **pas** libres : ce sont les **masques** (tout à `0xFF`) de 4 sprites, passés au constructeur `Bitmap` `0x40070172`.
> - On en libère 3 en faisant lire à leur sprite le masque identique `0x40154ae4` (même rendu, `tools/sprites.py`) : `0x4015c044` (720 o), `0x4016cae8` et `0x4018a788` (1024 o chacun).
> - Le « 1025ᵉ » octet de `0x4016cae8` est le 1er octet du plan image du sprite.

- **`[FAIT]`** Le MAIN OS contient ~**6 Ko de zones remplies de `0xff`**, réparties en 21 blocs. Les plus gros :

| VA | Taille | Nature |
|---|---|---|
| `0x40154ae4` | 1040 o | masque du sprite 32×260 — gardé intact, masque partagé |
| `0x4016cae8` | 1024 o (+1) | masque du sprite 64×128 — libérable |
| `0x4018a788` | 1024 o | masque du sprite 64×128 — libérable |
| `0x4015c044` | 720 o | masque du sprite 64×90 — libérable |
| `0x40148662`, `0x401489fa` | 396 o chacun | caves des tweaks de drumkilla |
| une dizaine d'autres | 120–182 o | |

- **`[FAIT]`** C'est **bien mieux que réutiliser les blobs de descripteurs** (§5) : ces zones ne sont pas réécrites à l'exécution (masques de sprites statiques), et les utiliser **ne casse pas l'upgrade USB**.
- **`[FAIT]`** Les 3 tweaks de `drumkilla/elektron-model-tweaks` (ci-dessous) écrivent justement dans les caves autour de `0x40147xxx`–`0x40148xxx` : usage confirmé.
- **`[À FAIRE]`** Avant d'utiliser une cave, confirmer qu'aucun pointeur (opérande ou table) ne la vise, et qu'elle n'est pas du BSS initialisé à l'exécution (méthode `scan_hole` / `mcfw.code_refs`).

## 4ter. Tweaks QoL prêts à l'emploi (drumkilla, testés sur vrai matériel)

`[FAIT]` Trois tweaks pour le M:C 1.13, **testés sur de vraies machines** par leur auteur, buildables avec notre chaîne :
- **latching-mute** : verrouiller le mode mute (maintenir TRK + tap FUNC), corrige la gêne signalée dans le [dossier §7.2](00-dossier-technique.md) ;
- **trig-preview** : séquenceur à l'arrêt, maintenir un pas + PAGE pour l'écouter (note, longueur, p-locks) ;
- **browser-scroll** : défilement des noms longs dans le navigateur.

Ils sont indépendants et combinables. Bon terrain d'essai à faible risque pour valider la procédure de flash le jour de la réception, avant de tenter le multipiste. À porter dans `tweaks/` si tu les veux.

## 5. ⚠️ Découverte importante : les descripteurs sont réécrits à l'exécution

- **`[FAIT]`** Une fonction du pilote (appelée à l'initialisation du mode USB) **réécrit les octets `bLength` de chaque descripteur** en RAM, à des offsets précis **dans les blobs** qui servent de code cave au mod.
- **Ces écritures tombent dans les 2 à 4 premiers octets de chaque blob**, c'est-à-dire **juste avant** le début de chaque stub (par exemple, elle écrit `0x4019b134`/`0x4019b135`, alors que le stub prime6 commence à `0x4019b136`).
  C'est très probablement **la raison du `nop` d'alignement** en tête de prime6 et token6 : garder le corps du stub hors de portée de ces écritures.
- **Conséquence pour toute extension `[FAIT]`** : ne jamais placer de code de stub dans les **4 premiers octets** d'un blob de descripteur réutilisé. Ces octets sont réécrits à chaque (ré)initialisation USB.
  Un `hookcheck` de la cave ne suffit pas à détecter ce piège : il faut connaître cette fonction de « fixup ». Elle vise aussi les descripteurs non patchés (device, etc.), sans impact.
- `[HYP]` À vérifier : le patch de ms-multi-output survit-il à un **changement de mode USB à chaud** (A+M ↔ MID dans CONFIG), qui rappellerait cette fonction et pourrait réénumérer ? À tester sur matériel (question ajoutée en [08](08-feuille-de-route.md#questions-ouvertes)).

## 6. Le mixeur : où sont le volume, le pan et les envois FX (vérifié)

- **`[FAIT]`** J'ai localisé la fonction de mixage (autour de `0x40056930`). Elle lit les **6 blocs de rendu par piste à `0x80001858`** (stride `0x80`, 32 trames) et accumule vers des **buffers stéréo L et R distincts**.
- **`[FAIT]`** Elle applique des **coefficients par piste** rangés dans des tableaux séparés (`0x40a78b80`, `…8b98`, `…8bb8`, `…8bd0`, `…8be8`, `…8c08`…). La présence de **deux coefficients (L et R) par piste** et de copies mises à l'échelle vers d'autres buffers correspond exactement au modèle du README :
  **volume/level de piste + pan (coefficient) + envois delay/reverb dérivés de la somme**.
- **`[FAIT]`** Confirme la nature des stems de [01 §2](01-ms-multi-output.md#2-nature-des-stems-à-connaître-avant-de-mixer) : le point de prélèvement (`0x80001858`) est **avant** le pan et les envois. Les stems sont donc mono, pré-pan, sans FX — cohérent avec ce que dit l'auteur.
- **`[FAIT]`, encourageant pour le mode 8 canaux** : la boucle d'accumulation itère sur **8 emplacements** (6 pistes + de la place). Cela conforte l'idée d'ajouter le **mix stéréo** en canaux 7-8 ([08 §A](08-feuille-de-route.md#a-8-canaux--6-pistes--mix-stéréo-recommandé-comme-jalon-2)).
- **`[À FAIRE]`** Confirmer lequel des buffers correspond au **mix final envoyé à l'USB** (celui que lit le feeder via `36(sp)`), s'il est **post-saturation** et **post-retours FX**. C'est la source à câbler pour les canaux 7-8.

## 7. Ce que cela change dans le plan

- ✅ **1.13 confirmée** : pas de portage de version à prévoir (question Q11 résolue).
- ✅ **Build reproductible confirmé** avec l'outil figé `a5bce9a` (question de [05 §3](05-methode-patch.md#3-build-reproductible-modèle-à-suivre) résolue : c'est bien ce commit).
- ✅ **Procédure de secours confirmée par le manuel** (MIDI IN obligatoire).
- ⚠️ **Nouveau garde-fou** pour les extensions : éviter les 4 premiers octets des blobs (§5).
- ▶️ **Prochaine étape RE utile** : finir de qualifier le buffer de mix (§6) avant de tenter le mode 8 canaux.

Les fichiers de désassemblage et le module `mcfw.py` sont dans `build/re/` (non versionnés). Voir [07 §2](07-snippets.md#2-mcfwpy--helpers-main-os-testé) pour le module.
