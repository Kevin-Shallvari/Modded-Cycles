# 54 — Wave autonome : la machine lit elle-même sa table (sans Model-TG)

Feuille de route du 11/10/2026 (handoff `handoff-wave-standalone.md`, milestone 1) : la machine Wave de
[52](52-etude-tables-d-ondes.md) lisait un fichier déjà chargé par Model-TG ; pour jouer Wave avec un moteur du Syntakt
et Acid, il faut la défaire de Model-TG : elle ouvre et lit **elle-même** son fichier. C'est le premier jalon du but
« un firmware sans Model-TG contenant un moteur du Syntakt (ou quelques-uns) + Acid + Wave » ; model-tg libère ~88 Ko.
Tweak `36-wavetable.json` (remplace `36-wavetable-tg.json`, supprimé), générateur `tools/gen_wavetable.py`, moteur
`tools/machines/wavetable/wt.c` (désormais `WT_BASE[t]`/`WT_COUNT[t]`), preuve `tools/emu/test_wavetable.py` (+
`wt_host.c`). Adresses : VA de l'OS 1.13.

## Réponse courte

La machine **lit le fichier elle-même** : le navigateur (déjà bloqué dans `/Wavetables`, [52 §3quater](52-etude-tables-d-ondes.md))
note l'entrée du fichier choisi pour la piste active, et le **premier appui sur le pad** lit le fichier par l'API de
fichiers de l'OS dans un tampon SDRAM de la piste. Le moteur est inchangé dans son principe : il ne lit plus
`track_slot`/`slot_base` de Model-TG mais nos deux tableaux. Wave est la **7e machine** (index 6), la mécanique est
celle d'Acid seule. Ce jalon ne fait pas encore l'envoi du fichier sans le mode SMP de Model-TG (milestone 2), et ne
vise pas encore la fusion des générateurs (milestone 3).

## 1. La lecture d'un fichier par l'OS `[FAIT : désassemblage]`

Le chemin d'origine qui lit un preset (une lecture courte, 48..160 o) est `0x400a2a28` (appelé par `0x400a3052`, que
le navigateur appelle en `0x400a6426`). Il fixe les conventions de l'API de fichiers :

| Appel | Convention |
|---|---|
| `0x4007e4f4(entrée, sortie)` | ouvre : `entrée` = pointeur vers une entrée de navigateur de 16 o (inode +0, empreinte +4, taille +8, 4e mot +12) ; `sortie` = un flux de 16 o (+0 inode, +4 position, +8, +12 = 1) ; rend `d0 >= 0` |
| `0x4007eb16(inode)` | taille du fichier, ou −1 |
| `0x4007baaa(tampon, longueur, flux)` | lit jusqu'à `longueur` octets, avance le flux (+4), rend le nombre lu |
| `0x4007bc1c(flux)` | ferme |
| `0x4007de78(inode, sortie 16 o)` | ce que donne `getEntry` (`0x4007cdd4`) |

L'entrée de navigateur que le navigateur pousse (a0 = `fp-24`, argument = `fp-16`) suffit : sa taille est en +8 (le
conteneur entier). Pas besoin d'appeler `0x4007eb16`.

## 2. Le chargeur

Deux accroches, plus les 5 du navigateur bloqué ([52 §3quater](52-etude-tables-d-ondes.md)) :

- **`0x400a6426`** (`jsr 0x400a3052`, 6 o) → `jsr wt_parse` : la piste **active** (`0x40a700c4`) joue-t-elle Wave
  (kit d'origine : `*(u32*)0x40a78888 + 28 + 100 t`, octet +38 ; d'abord écrit +0x38 par erreur, voir §fin) ? Si oui, recopie l'entrée de 16 o dans `wt_h[t]`
  et remet `WT_COUNT[t]` à zéro (la table est à recharger), puis rejoue `jsr 0x400a3052` (le navigateur ne change pas) ;
- **`0x4008171e`** (prologue `link.w %fp,#-104 ; moveq #127,%d0`, 6 o) → `jmp wt_note` : à l'appui d'un pad, si la
  piste joue Wave, une entrée est notée et `WT_COUNT[t] == 0` (pas déjà chargée), ouvre le fichier, le lit en morceaux
  de 64 Ko dans `0x46800000 + 0x300000 t` (3 Mo par piste), ferme, puis pose `WT_BASE[t] = tampon + 64` et
  `WT_COUNT[t] = (taille - 80) / 2` ; enfin rejoue `link.w %fp,#-104 ; moveq #127,%d0 ; jmp 0x40081724`.

`wt_is_ours` (d0 = piste) lit le kit d'origine et compare l'octet de machine à 6 ; il garde `d1`, `d2` et `a0`. Les
deux accroches gardent exactement les registres et la pile attendus par l'OS.

## 3. Le moteur

`wt.c` ne connaît plus Model-TG : il lit `WT_BASE[t]` (début du PCM, en-tête de 64 o déjà sauté) et
`WT_COUNT[t]` (nombre d'échantillons). Le reste est inchangé : `F = WT_COUNT[t] / S_TOTAL` (copies adoucies gravées par
l'outil web, [52 §13](52-etude-tables-d-ondes.md)), oscillateur sur les copies (`LGC`, `OFF`), passe-bas d'Acid, chaîne
d'ampli d'origine. Un fichier non converti (`WT_COUNT[t]` non multiple de `S_TOTAL`) ne joue rien. Le banc HOST expose
`host_wt_base`/`host_wt_count`.

## 4. Le générateur

`tools/gen_wavetable.py` a perdu `find_tg`, les retouches de Model-TG (`preset_fail_hook`, `name_probe`), `wt_boot`,
`wt_or_any`, `wt_np`, `dispatch_tg_asm` et le crochet de la tâche des LED. Il suit **Acid seule** (`gen_acid.py`,
`26-acid.json`) : charge utile à `0x43000000`, crochet de démarrage seul (`0x400004b2`), aucun détour de la boucle des
voix (les tables update/render déplacées suffisent), plus l'envoi USB à heure fixe et la boucle des voix court-circuitée
(`tools/usb_steady.py`, `tools/voice_loop.py`). Le chargeur et les 5 accroches du navigateur vivent dans `glue_asm`.
**Aucun `requires`** ; conflits : MACRO, Acid, les moteurs du Syntakt et Model-TG (même place). `36-wavetable-tg.json`
est supprimé ; Wave n'est plus une carte du flasher tant que le milestone 2 ne lui donne pas sa route d'envoi.

## 5. Preuve `[FAIT en émulation]`

`tools/emu/test_wavetable.py` (`--cycles model-cycles_OS1.13.syx`, ~6 min) :

1. **Convertisseur** : table bien formée, copies courtes bornées en bande, le moteur HOST joue ;
2. **Firmware** : démarrage (le crochet seul range la charge utile, la remise à zéro du BSS de l'OS suit), puis **le
   vrai chemin navigateur → chargeur → tampon** : `wt_parse` note l'entrée, `wt_note` lit le conteneur par l'API de
   fichiers (simulée par un petit arbre en mémoire) et pose `WT_BASE`/`WT_COUNT` ; PCM copié à l'octet ;
3. **Lecture** : la table joue par la vraie boucle des voix (grave et aigu, lectures dans le fichier uniquement),
   fichier non converti muet ;
4. **6 pistes Wave** (6 tables) et une piste TONE mêlée, identique à l'OS d'origine.

`python3 tools/gen_wavetable.py --check`, `gen_flasher_tweaks.py --check`, `ref_mainos.py --check` verts. Le JSON
versionné vient de `m68k-elf-gcc` 16.2 (Homebrew) avec les binutils 2.38 d'Ubuntu 22.04 (`M68K_CROSS` vers un `gcc` qui
appelle cet assembleur par `-B`), comme les moteurs du Syntakt et SD VINTAGE v2 ; la chaîne a été validée en
reproduisant **à l'octet** `20-sdvintage-snare.json` et `22-sdvintage-7th.json` avant de régénérer Wave. Un autre GCC
donne d'autres octets, et `--check` le dit.

**Chaîne exacte** (sur un Linux sans ces paquets) : Linuxbrew (`brew install m68k-elf-gcc` → 16.2.0) ; le paquet
`binutils-m68k-linux-gnu` 2.38 d'Ubuntu 22.04 extrait à part ; un préfixe `M68K_CROSS` où `mc-gcc` =
`m68k-elf-gcc -B<dossier contenant as>/` (l'`as` est celui de 2.38) et `mc-as`/`mc-ld`/`mc-nm`/`mc-objcopy`/`mc-objdump`
sont ceux de 2.38 (`LD_LIBRARY_PATH` vers leur `libopcodes`/`libbfd`).

## 6. Reste à faire

- **Milestone 2** : la colle SMP (table d'opcodes de 35 octets, drapeau CYC/SMP, bascule depuis la page Convert) pour
  envoyer un fichier sans Model-TG ;
- **Milestone 3** : fusion des générateurs (moteurs du Syntakt + Acid + Wave, allocateur partagé) et sélecteur du
  flasher, puis retour de Wave dans le flasher ;
- **Matériel (Kevin)** : flasher `wavetable`, poser une table (mode SMP), la jouer — le son, la latence du premier
  chargement, la charge.

## Correction : l'octet de machine est en +38, pas en +0x38 (12/10/2026)

Premier essai de Kevin sur la machine (firmware Wave seule) : sur la piste Wave, le navigateur n'est pas bloqué dans
`/Wavetables`, YES sur une table affiche « Error loading preset » (aussi juste après un redémarrage), et le pad ne
joue rien. Cause `[FAIT]` : `wt_is_ours` lisait l'octet de machine du son en **+0x38** (56) au lieu de **+38**
(décimal, `0x26`) — celui que lit Model-TG (`mvzb %a0@(38)`, « Sampler (machine byte +38 = 6) », `KIT_SND` = 28,
`SND_SIZE` = 100) et que donnent les [notes 46](46-ecoute-des-samples.md) et [52](52-etude-tables-d-ondes.md). La
piste Wave n'était donc jamais reconnue : ni verrou, ni entrée notée, ni lecture ; YES tombait sur le chargement de
preset de l'OS. La preuve posait l'octet au même mauvais endroit, d'où « TOUT OK ». Corrigé (`MACH_OFF` = 38 dans
`tools/gen_wavetable.py`, même constante dans la preuve) ; preuve TOUT OK. Sur la machine (Kevin, 12/10/2026) : le
navigateur est de nouveau bloqué dans `/Wavetables` `[FAIT : sur la machine]` ; le pad ne jouait toujours rien et YES
affichait toujours l'erreur — sections suivantes.

## Longueur de la table : l'en-tête, pas « taille − 80 » (12/10/2026)

Liste du dossier par le protocole de Transfer `[FAIT : sur la machine]` : les tables du +Drive font **64 o d'en-tête
+ PCM, sans fin** (`ESW Analog - ARP Pulse-wt` : 17 216 o = 64 + 2 trames × 4 288 × 2 ; `… 303 Saw-wt` : 2 195 520 o =
64 + 256 trames). `WT_COUNT = (taille − 80) / 2` donnait 8 échantillons de moins : jamais un nombre entier de trames,
donc rien ne jouait. Le chargeur prend maintenant les octets de PCM de l'en-tête (+4, ce qu'écrit `uploadSample`),
bornés au fichier ; un fichier avec 16 o de fin marche aussi. La preuve construisait son fichier avec une fin et la
taille en +8 : elle suit maintenant l'en-tête de la page (octets de PCM en +4, 48 000 en +8, sans fin), plus un cas
avec fin.

## YES charge la table, comme le Sampler de Model-TG (12/10/2026)

Le YES du navigateur (`0x400a64fa`) lit le fichier comme un preset (`0x400a51fa`, 3e argument = piste visée) ;
l'échec affiche « Error loading\npreset » (`pea 0x401302b2` en `0x400a6752`). On reprend la méthode du
`preset_fail_hook` de Model-TG (MIT) :

| Site | Écriture | Rôle |
|---|---|---|
| `0x400a6732` (6 o) | `jsr 0x400a51fa` (relatif, 4 o) + `move.l %d3,-(%sp)` → `jsr wt_yes` | rejoue le chargement de preset ; s'il échoue et que la piste visée joue Wave : `wt_load`, puis le message ; rejoue le `move.l` recouvert |
| `0x400a6754` (4 o) | `0x401302b2` → `wt_msg` | l'OS affiche notre message (« Table loaded\nto track N », ou la raison) ; ailleurs, `wt_msg` reprend le texte d'origine |
| `0x400a6602` (6 o) | `jsr 0x400a3052` → `jsr wt_parse` | la lecture de preset du YES note aussi l'entrée choisie (même appel qu'au curseur) |

Le chargement de preset échoue toujours : la piste ne reçoit jamais la table comme un preset. `wt_load` (partagé avec
le repli au pad) rend un code : 0 chargée, 1 rien de noté, 2 lecture, 3 plus de 3 Mo, 4 pas un nombre entier de
trames (« Table not\nconverted »). Le curseur ne décharge plus la table jouée : il note seulement l'entrée.

## La table retenue : jeton dans le nom du son (12/10/2026)

Comme le jeton « SMP » de Model-TG (`name_store`) : le nom du son (16 o en +4 du son vivant, `wt_snd` = `sound_obj`
de Model-TG : projet `0x400cf866` + 212 + 68 t, vtable[40]) est enregistré tel quel avec le projet. Après un
chargement réussi (YES ou pad), `wt_stamp` y écrit **« W » + clé (8 chiffres hex) + empreinte (24 bits, 6 chiffres)**,
15 caractères. La clé est le premier mot de l'entrée du navigateur ; `0x4007de78(clé, &entrée)` `[FAIT :
désassemblage]` reconstruit l'entrée (+0 clé, +4 empreinte impaire, +8 taille) et rend 0, ou −1 si le fichier n'existe
plus ou que le système de fichiers n'est pas prêt.

Retour de la table : `wt_tick`, dans les 5 cases des LedHandler qui pointent sur une fonction vide (`0x400d7648`,
celles de Model-TG ; aucun autre tweak ne les touche), au niveau d'interruption 0 et une fois par bloc audio
(`0x8000184c`). Pour chaque piste Wave dont le nom porte un jeton différent de `wt_tok[t]` : il le note (une seule
tentative par jeton), reconstruit l'entrée, vérifie l'empreinte (un autre fichier sur la même clé ne charge rien) et
charge. Projet rechargé, mise sous tension, autre kit : la table revient sans appui. Limites : un fichier déplacé ou
renommé peut changer de clé (la table ne revient pas, YES la retrouve) ; le nom du son montre le jeton, pas le nom de
la table.

Preuve (`tools/emu/test_wavetable.py` §2bis, §2ter) : YES sur une piste Wave (table chargée, message, pile et `d3`
rendus, jeton écrit), vrai preset (rien), autre machine (message d'origine), fichier non converti, piste visée ≠ piste
active ; tâche : niveau non nul (rien), jetons valides chargés, autre machine / sans jeton / empreinte changée / jeton
abîmé (rien), une fois par bloc, pas de relecture, kit changé. TOUT OK.

**Sur la machine (Kevin, 12/10/2026)** `[FAIT : sur la machine]` : YES charge la table (« Table loaded »), le pad la
joue, et la table revient après extinction / rallumage et rechargement du projet (« it works »).
