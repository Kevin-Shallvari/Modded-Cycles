# 72 — Mod Settings : une page de réglages des mods, et l'audio USB en 2CH ou 6CH

Demande de Maxime (19/10/2026), avant la fusion de l'OS unique (notes/71) : pouvoir activer et désactiver l'audio USB
6 canaux depuis les réglages, sur une nouvelle page *Mod Settings* qui accueillera ensuite d'autres réglages de mods ;
désactivé, le mode 6 canaux doit l'être vraiment et ne rien consommer. C'est l'issue #82 (« Switch Between Stereo Mix
and 6-Channel USB Audio », sans reflasher). Tweak `tweaks/model-cycles_OS1.13/12-mod-settings.json`, générateur
`tools/gen_mod_settings.py`, sources `tools/machines/mod_settings/`, preuve `tools/emu/test_mod_settings.py`.
Adresses : VA de l'OS 1.13.

## En bref

- **SETTINGS** ouvre le Config Menu de l'OS ; il gagne une 9ᵉ ligne, **Mods** (icône de pièce de puzzle), après
  Device. Elle ouvre la page **Mod Settings**, une `MenuView` de l'OS sans classe nouvelle, avec une ligne
  **USB Audio** : **2CH** (le mix stéréo, comme d'origine, par défaut) ou **6CH** (les six pistes, comme
  `6ch-usbup`). LEVEL/DATA pressé bascule, comme Device › USB mode.
- **Réglage gardé** : un enregistrement de 16 o en `0x404e9b80`, dans le bloc de réglages que l'OS sauvegarde en
  entier (272 o, flash `0x78000`), hors de sa somme de contrôle. Sans enregistrement valide : 2CH.
- **6CH** : les 15 modifications de `6ch-usbup` au pilote USB et aux descripteurs (100 o) sont faites **en
  mémoire**, au démarrage juste avant la mise en place du mode USB, ou à la bascule, USB arrêté. Les octets
  remplacés sont gardés et remis en 2CH. **En 2CH, le pilote est celui de l'OS, octet pour octet** : rien du mode
  6 canaux ne tourne (au démarrage, 22 à 88 instructions lisent le réglage, puis plus rien).
- **Bascule à chaud** : réglage enregistré, USB arrêté par la fonction de l'OS qui sert au changement de USB mode,
  modifications faites ou défaites, indices des rings remis à zéro, caches poussés, USB relancé : l'ordinateur voit
  le Model:Cycles partir et revenir environ une seconde plus tard, avec 2 ou 6 entrées.
- `[FAIT en émulation]` tout ce qui précède (§5). **Testé sur la machine le 19/10/2026** (§7).

## 1. Ce que fait l'OS

### 1.1 Le Config Menu et ses pages

| Adresse | Rôle |
|---|---|
| `0x4003c134` | constructeur de `ModelSettingsMenu` (« Config Menu », objet de 0x298 o créé en `0x4001b9e8`) : 8 lignes, Pattern, Project, MIDI, Audio, Backup, Upgrade, Battery, Device `[FAIT]` |
| `0x4003c99a` | son épilogue : `movem.l -104(fp),d2-d7/a2-a5 ; unlk fp ; rts`, `a2` = le menu ; aucun tweak n'y touche `[FAIT]` |
| `0x400406d8` | constructeur d'une `MenuView` (this, nom, réserve de lignes, &titre `std::string`, `Bitmap` d'icône) ; vtable `0x401087ec` ; objet de 0x23c o ; le titre est coupé à l'espace en deux lignes (+148, +556) `[FAIT]` |
| `0x4004082c` | dessin d'une `MenuView` (vt +120) : à gauche le titre et l'icône (+152), à droite la ligne choisie : son nom, son affichage, « n/total », flèches `[FAIT]` |
| `0x400734b0` | ligne (0x54 o) : (ligne, &libellé, &appui, &affichage, &changement, -1, 8), quatre `std::function` ; `0x40072ce6` l'ajoute à la vue `[FAIT]` (notes/32) |
| `0x4003b19e` | affichage d'une ligne du Config Menu : son icône 31 × 22 par `0x40071da4(écran, bitmap, x, y, 1)` `[FAIT]` |
| `0x4003bd42` | appui sur une ligne du Config Menu : copie du pointeur partagé de la page (`0x400d807e`), `0x40075754(menu, &copie)` l'ouvre, `0x400cf23c` libère la copie `[FAIT]` |
| `0x4007536a` | pointeur partagé d'une page fille (rendu en `a0`), comme le menu range les siennes en +600..+656 `[FAIT]` |
| `0x4007649e(vue + 56, 3)` | fait par Device Config (`0x40032726`) et Battery (`0x40031be4`) après le constructeur ; repris tel quel `[FAIT]` (sens exact `[HYP]` : une liste de groupes de touches) |
| `0x40031f8a`, `0x40031fd8` | Device › USB mode : l'appui bascule A+M / MID (`0x40004e04`) puis enregistre ; l'affichage écrit la valeur en grand par `0x40071c10(écran, 0x401429ec, x, y - 12, 1, 0, "XXX", valeur)` `[FAIT]` |

Les icônes du Config Menu sont des `Bitmap` 31 × 22 (un mot de 32 bits par colonne, **la ligne du bas dans le
bit 31**) ; leurs masques sont tous le même rectangle plein, celui de la copie gardée `0x4016e980` (notes/52).

### 1.2 Les réglages de l'OS

| Adresse | Rôle |
|---|---|
| `0x404e9b10` | bloc « COKI » (magique, CRC en +4, version, longueur en +0xc) ; la CRC couvre `0x404e9b18..0x404e9b62` (`0x40044b4e`, longueur 0x43 + 8) `[FAIT]` |
| `0x404e9b04` | l'objet de stockage (`0x400ddef2`, initialisation statique) : données `0x404e9b10`, **272 o**, offset flash `0x78000` `[FAIT]` |
| `0x400449a8` / `0x400449b8` | lecture / écriture des 272 o (`0x4008bd8a`, `0x4008cf3a`) ; l'OS écrit après chaque réglage changé (par ex. `0x40044e74`) `[FAIT]` |
| `0x4000567a` | lecture au démarrage, avant l'USB ; `0x40044b40` valide, sinon défauts `0x400449ce` `[FAIT]` |
| `0x404e9b63..0x404e9c0f` | dans le bloc sauvegardé, hors CRC ; ni lu ni écrit par l'OS ni par un tweak (relevé du 19/10/2026) `[FAIT]` |

### 1.3 L'USB : mode, arrêt, relance

| Adresse | Rôle |
|---|---|
| `0x40004e04(mode)` | changement de USB mode : rien si c'est le mode actuel ; sinon `0x40004d9a`, nouveau mode, `0x40004db4` `[FAIT]` |
| `0x40004d9a` | arrêt : `0x400042d4` (USBCMD.RS = 0, interruptions USB coupées, rappel d'arrêt du mode, pour A+M `0x40002c56` qui arrête les flux : `0x404a0644` = 0), état 0, compte à rebours 30 `[FAIT]` |
| `0x40004db4` | compte à rebours en cours : état 1 ; à zéro (appel suivant par la tâche périodique), rebranche si VBUS (`0x400041e6`) `[FAIT]` |
| `0x4000576c`, `0x400057c6` | démarrage : `lea 0x40004e40,a2` puis, après d'autres initialisations qui gardent `a2`, `jsr (a2)` avec le mode `[FAIT]` |
| `0x40002778` | début d'un flux (choix de l'interface par l'ordinateur) : amorce le ring **à partir de l'indice courant** `0x8000bc94`, jamais remis à zéro `[FAIT]` |
| `0x40002912` | envoi d'un bloc : sort tout de suite si `0x404a0644` = 0 (aucun flux) `[FAIT]` |

Ring de sortie : 16 cases de 56 o en stéréo, 9 cases de 168 o en 6 canaux, à partir de `0x80009800` ; ring d'entrée
16 cases (`0x80009b80`) ou 5 (`0x80009de8`), indice `0x8000bc90` (notes/04, 13, 35). Un indice resté de l'autre mode
déborde : 12 (possible en stéréo) donne en 6 canaux la case `0x80009fe0`, hors du ring (§5).

### 1.4 Les caches

`ACR0 = 0x4007e020` : `0x40000000..0x47ffffff` en copyback. L'OS écrit `CACR = 0xa50ce100` une seule fois
(`0x40000548`) ; aucun tweak de l'OS ne le change ensuite (ACR1 seulement pour Model-TG) `[FAIT]`. Sur le cœur V4,
`CPUSHL (An)` désigne un ensemble et une voie (bits 11..4 et 1..0 de `An`), comme Linux l'emploie sur cette famille
`[HYP fort]` ; l'OS l'emploie avec l'adresse des octets qu'il change (descripteurs, `0x400049dc`).

## 2. Conception

- **Page** : `mods_menu_add` (`cfg_tail`, à la place de l'épilogue `0x4003c99a`) construit une fois une
  `MenuView` « Mod Settings » (nom « ModSettingsMenu »), son `0x4007649e(vue + 56, 3)`, sa ligne USB Audio, et son
  pointeur partagé (`0x4007536a`) gardé dans nos variables ; puis ajoute la ligne Mods au menu. Lignes faites comme
  l'arpégiateur (notes/32) : closures de 4 o, gestionnaire générique `0x4002cf00`, pas de fonction de changement
  (comme les lignes du Config Menu et USB mode). L'icône est un `Bitmap` 31 × 22 (notre image, masque gardé
  `0x4016e980`), la même pour la ligne et pour la page.
- **Enregistrement** : `0x404e9b80` : « MODS », version 1, 10 octets de réglages (0 = défaut), octet de contrôle
  `0x5a + somme`. Valide si magique et contrôle bons ; sinon tous les réglages valent 0. Écrit, puis `0x400449b8`.
  Un futur réglage prend l'octet suivant (version inchangée : 0 reste son défaut).
- **6CH en mémoire** : table générée depuis `11-6ch-usbup.json` (adresse, longueur, octets nouveaux). Activer : pour
  chaque site, garder les octets en place puis écrire les nouveaux, interruptions masquées (`SR = 0x2700`) ;
  désactiver : remettre les octets gardés. Le tweak ne porte donc aucun octet d'origine de ces sites. Les 4 stubs de
  `6ch-usbup` (cave `0x4015c044`, jamais appelés en 2CH) et sa correction du flux stéréo (heure fixe, boucle des
  voix, partagée avec Model-TG) sont écrits tels quels : mêmes écritures entières que `6ch-usbup` et `model-tg-st`.
- **Caches** : après les écritures, `cpushl %bc` sur la première et la dernière ligne de chaque site (lecture par
  adresse), puis sur les 256 ensembles × 4 voies (lecture ensemble/voie : 16 Ko, le cache de données en fait 8),
  puis `CACR = 0xa40ce100` (celui de l'OS sans DCINVA, qui jetterait les lignes modifiées) : caches d'instructions
  et de branchements invalidés. Pousser une ligne est sans danger dans les deux lectures.
- **Démarrage** (`usb_boot`, `lea` en `0x4000576c`) : si le réglage est 6CH, indices des rings à zéro et 6CH en place,
  puis `jmp 0x40004e40` avec le même mode. Sinon, rien.
- **Bascule** (`usb_press`) : enregistrement, `0x40004d9a` (USB arrêté, flux arrêtés : plus rien n'exécute les sites,
  l'envoi sort au test de `0x404a0644`), indices des rings à zéro, 6CH mis ou ôté, `0x40004db4` (relance après le
  compte à rebours : l'ordinateur relit les descripteurs), redessin (`0x40076082`). Le chemin d'arrêt et de relance
  est celui de Device › USB mode.

## 3. Place libre et conflits

- Code et données dans **huit masques de sprites libérés** (`tools/sprites.py`) : cinq 47 × 47 rendus libres par le
  retrait de Chord Keys (`0x4016b6f8`, `0x4016b9e8`, `0x40171f30`, `0x40172608`, `0x40179730` : 348, 304, 348, 268,
  176 o sur 376), trois 48 × 22 libres sur toutes les branches (`0x40187528` : la table et les octets 6CH, 190/192 ;
  `0x401876a8` : l'icône et l'état, 161/192 ; `0x40188f98` : les octets gardés, 104/192). Chaque masque est
  redirigé vers sa copie gardée. La PR #75 (à fermer) utilisait aussi des 47 × 47.
- Crochets : `0x4003c99a` (jmp) et `0x4000576c` (lea) ; personne d'autre n'y touche.
- `conflicts` : `6ch-usbup` et `6ch-multiout`, qui écrivent les 15 sites pour de bon.
- Nouveau champ de tweak **`runtime`** (off, len, why) : les octets de l'OS qu'un tweak réécrit pendant que l'OS
  tourne. `tools/check_overlaps.py` refuse qu'un tweak installable avec lui y écrive (même un tweak qu'il demanderait),
  sauf conflit déclaré ; `tools/registry.py` les liste au §6 avec l'enregistrement « MODS ». Les builders n'en ont
  pas besoin.

## 4. Le tweak

28 écritures : les 10 de `6ch-usbup` hors des 15 sites (identiques), 8 zones de code et données, 8 redirections de
masques, 2 crochets. 1 899 o dans les masques. En 2CH le seul code exécuté est `usb_boot` au démarrage, la
construction de la page avec le Config Menu, et les fonctions de ligne quand on ouvre le menu ; rien dans
l'interruption audio ni dans le pilote USB.

## 5. Preuve en émulation

`tools/emu/test_mod_settings.py --cycles … --syntakt …` sur l'OS entier (`os.json`, charges utiles comprises), code
même de l'OS :

| Cas | Résultat |
|---|---|
| Les 15 sites dans l'OS | octets d'origine (aucun tweak de l'OS n'y écrit) |
| OS + mod-settings avec les octets 6CH | = OS + `6ch-usbup`, hors des écritures propres du mod |
| Démarrage sans enregistrement, enregistrement abîmé, 2CH, valeur inconnue | mise en place USB appelée une fois avec le mode, image et indices inchangés (22 à 88 instructions avant) |
| Démarrage en 6CH | les 15 sites modifiés avant la mise en place USB, indices à zéro, rien d'autre |
| Config Menu (vrai constructeur, vrai dessin) | 9 lignes, les 8 premières identiques à l'OS sans le mod, la 9ᵉ « Mods » et son icône |
| Page | « Mod Settings », une ligne « USB Audio », valeur « 2CH » |
| Appui sur Mods | le menu ouvre la vue de la page ; la copie du pointeur partagé est libérée |
| Appui sur USB Audio | enregistrement, arrêt USB (pilote encore d'origine), 6CH en place, relance ; image = avant + octets 6CH ; indices à zéro ; SR rendu ; 1 024 poussées de cache, `CACR = 0xa40ce100` ; valeur « 6CH » |
| Second appui, puis six de plus | retour à l'image d'avant octet pour octet ; alternance toujours sur les deux mêmes images |
| Réglages | l'enregistrement est dans les 272 o que l'OS écrit en flash ; ses réglages restent valides ; un réglage de l'OS changé ensuite laisse l'enregistrement intact |
| Flux USB (modèle de `test_usb_in.py`) après bascule | 6CH et retour en 2CH : aucune trame manquante, en double ou sautée, trois charges, deux départs, ±100 ppm |
| Flux 6CH démarré avec l'indice 12 laissé par la stéréo | case `0x80009fe0`, hors du ring : la remise à zéro est nécessaire ; avec 0, les 8 cases amorcées sont dans le ring |

Images de l'écran : `--png dossier` (Config Menu ligne 9, page en 2CH et en 6CH).

Non couvert par l'émulation : les caches (Unicorn n'en a pas ; le code les pousse dans les deux lectures de
`CPUSHL`), le contrôleur USB réel et l'ordinateur qui réénumère, la touche LEVEL/DATA elle-même (l'appui est appelé
directement), l'écriture en flash.

## 6. Plan de test sur la machine (PR #100)

1. SETTINGS : la ligne Mods après Device, son icône ; LEVEL/DATA l'ouvre ; retour au menu comme pour Device.
2. USB Audio en 2CH : l'ordinateur voit 2 entrées, son normal ; puis LEVEL/DATA : déconnexion, retour vers une
   seconde plus tard avec 6 entrées ; enregistrer six pistes, comme avec `6ch-usbup`.
3. Repasser en 2CH : retour à 2 entrées, mix stéréo, sans éteindre.
4. Éteindre en 6CH, rallumer : 6 entrées dès le démarrage, la page affiche 6CH.
5. Plusieurs bascules de suite, avec un enregistrement en cours dans le logiciel (après l'avoir arrêté) ; Model-TG
   et les moteurs en marche.
6. USB mode sur MID puis A+M en 6CH ; CONFIG › UPGRADE par USB en 2CH et en 6CH.
7. Les autres réglages (MIDI, Audio, Device) gardés après extinction, avant et après une bascule.

## 7. Testé sur la machine (19/10/2026)

Maxime a essayé la branche `claude/mod-settings-usb` (PR #100) sur son Model:Cycles après le plan de test du §6, et
répondu : « ça marche nickel ». Le détail point par point du §6 n'a pas été rapporté ; le réglage passe en
`tested` (`os.json`). L'OS 2.0 entier reste `experimental` tant que Maxime n'a pas confirmé avoir flashé ce firmware
précis (MAIN OS `1ee74aa2…76fa`).
