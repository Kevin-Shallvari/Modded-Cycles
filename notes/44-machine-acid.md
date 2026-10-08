# 44 — Machine Acid : une basse façon 303 sur le Model:Cycles

Demande de Kevin (contributeur, 07/10/2026) : « une basse 303 carré-scie », en 7e machine, à côté des 6 d'origine,
sans en remplacer aucune ; conçue avec lui, choix par choix, en écoutant des prototypes. Tweak `26-acid.json`,
générateur `tools/gen_acid.py`, moteur `tools/machines/acid/acid.c`, preuve `tools/emu/test_acid.py` (référence
`tools/emu/acid_ref.c`). Adresses : VA de l'OS 1.13.

## Réponse courte

- **Une machine ajoutée, Acid**, avec la mécanique de MACRO ([43](43-machine-macro.md)) et des moteurs du Syntakt
  ([20](20-moteurs-syntakt-a-cocher.md)) : 7e machine, son nom, ses potards et leurs défauts. Notre code, en entiers,
  sans rien emprunter à personne.
- **Le son** : une dent de scie qui se fond en carré (SHAPE), un filtre en échelle à 4 pôles résonant, passe-bas ou
  passe-haut sur un seul potard façon DJ (COLOR), une enveloppe de filtre dans les deux sens (CONTOUR), l'accent sur
  PUNCH ; DECAY, GATE et PUNCH passent par la chaîne d'ampli d'origine, réglée comme TONE.
- **L'écrasement de la résonance** (ce qui fait « couiner » une 303 sans qu'elle s'emballe) est un **coude à 3
  segments** dans la boucle du filtre : linéaire par morceaux, donc l'équation sans retard (ZDF) se résout
  **exactement**, sans itération ni division par échantillon. En prototype, il sonne comme une vraie tangente
  hyperbolique résolue par Newton (3 à 4 fois plus chère), sans suréchantillonnage (§4).
- **Charge** : une voix Acid coûte **0,45 à 0,97 voix TONE** en instructions, réglage par réglage (0,85 au défaut,
  filtre passe-bas), jusqu'à 1,06 en cumulant passe-haut, carré, accent et résonance 127 ; environ deux fois moins
  qu'une voix MACRO ; voix muette : 572 instructions par bloc (§8).
- **Avec Model-TG** : version combinée `33-acid-tg.json`, Acid en 8e machine après le Sampler (§6).
- **Incompatible** avec MACRO et les moteurs du Syntakt (même place, même mécanique).

## 1. Ce que l'OS impose `[FAIT]`

Le même contrat que MACRO ([43 §2](43-machine-macro.md), [14 §2](14-machine-sd-vintage.md)) :

| Où | Quoi |
|---|---|
| `0x400a7d4a` | boucle des voix : pour chaque piste, `update[m](pmod, voix, params)` puis `render[m](out, voix)`, par blocs de 32 trames à 48 kHz (1 500 par seconde) |
| `voix + 0x34` / `+0x38` | trig de ce bloc / du bloc précédent ; remise à zéro de la voix `0x400a7ab8` au changement de machine |
| `pmod` | note du trig en demi-tons `<< 16` ; note = PITCH − 64 + note du trig + FINE, bornée à 0..127, 440 Hz à 69 |
| `params + 0x14..0x24` | PITCH, COLOR, SHAPE, SWEEP, CONTOUR, PUNCH, GATE, FINE, DECAY (mots 8.8) |
| `0x400a9252` / `0x400a9430` / `0x400a967a` | enveloppe d'ampli, VCA, PUNCH : appelées par le `render` de TONE, et par le nôtre |
| `MACSR = 0xa0` | EMAC fractionnaire signée, saturée, pendant la boucle des voix : notre multiplication |

FINE est le 2e rôle du potard PITCH sur la machine (Kevin) : il reste l'accord fin, comme sur toutes les machines.

## 2. Les potards (choix de Kevin, 08/10/2026)

| Potard | Nom affiché | Rôle | Défaut |
|---|---|---|---|
| PITCH, FINE, touches | — | la note, comme les machines d'origine | — |
| COLOR | Cutoff / CUT | filtre façon DJ : 0..63 passe-bas de 20 Hz à 20 kHz, 64 ouvert (pas de filtre), 64..127 passe-haut de 10 Hz à 20 kHz (§3.2) ; lu en 8.8 (10 à 11 octaves en 63 crans : 1/6 d'octave par cran, mais le LFO et les slides balaient sans marches) | 30 |
| SHAPE | Wave / WAVE | dent de scie (0) → carré (127), fondu continu | 0 |
| SWEEP | Reso / RES | résonance, auto-oscillation à partir d'environ 118 | 90 |
| CONTOUR | Env Mod / ENV | enveloppe du filtre, bipolaire : 64 rien, 127 +6 octaves, 0 −6 octaves | 100 |
| DECAY | (commun) | durée de l'enveloppe du filtre (30 ms à 2 s, exponentielle) et chaîne d'ampli d'origine, comme sur la 303 | 50 |
| PUNCH | (commun) | accent : attaque du filtre 0,5 → 0,9, enveloppe ×1,6, résonance +10 %, décroissance du filtre bornée à ~200 ms, +3,5 dB ; plus le PUNCH d'origine | — |
| GATE | (commun) | comme les machines d'origine | — |

« Resonance » (9 lettres) ne tient pas : la fenêtre des potards coupe le nom long aux espaces et n'affiche que des
mots de 8 lettres au plus ([18 §10](18-septieme-machine.md)) ; le générateur refuse un mot plus long. Images : les
siennes (§3.4).

Pas de potard de saturation (drive) : les quatre potards de la machine sont pris, PUNCH et GATE ne valent que 0 ou 1.
L'attaque du filtre est fixe, plus forte sur l'accent, comme sur la 303.

## 3. Le moteur

### 3.1 Oscillateur

- Dent de scie à polyBLEP (correction de 2 échantillons autour de chaque saut) : pas de repliement audible sur une
  basse, quelques résidus sur les notes très aiguës, comme les machines d'origine.
- Carré = scie − la même scie décalée d'une demi-période. Le fondu (1 − m)·scie + m·carré vaut donc
  **scie − m · scie décalée** : une multiplication.
- Phase sur 32 bits ; incrément par bloc depuis une table de 193 entrées (1/16 de demi-ton, interpolée), décalé de
  l'octave ; une division par bloc (`divu.l`) pour le polyBLEP.

### 3.2 Filtre

4 étages à un pôle (TPT : `v = (x − s)·G ; y = v + s ; s = y + v`), contre-réaction globale `k · f(y4)`, résolue sans
retard. Avec `y4 = G⁴·u + S` (S : la part des états) et `u = x − k·f(y4)` :

| Segment de f | f(y) | y4 |
|---|---|---|
| \|y\| < T1 = 0,12 | y | (G⁴·x + S) / (1 + k·G⁴) |
| T1 ≤ \|y\| < T2 = 0,40 | 0,35·y ± 0,078 | (G⁴·(x ∓ k·0,078) + S) / (1 + 0,35·k·G⁴) |
| \|y\| ≥ T2 | ± 0,218 (plat) | inutile : la contre-réaction est une constante |

f est monotone, donc la solution est unique : on essaie le 1er segment, puis le 2e, puis le plat. Les deux divisions
`1/(1 + a·k·G⁴)` ne dépendent que du bloc : calculées dans `update`, par 3 tours de Newton en entiers. Par
échantillon : 11 multiplications (4 pour S en une seule chaîne d'accumulation de l'EMAC, 2 pour y4, 1 pour u, 4 pour
les étages), 14 au-delà du coude, aucune pour le filtre ouvert (COLOR 64).

- Coupure : table de G = g/(1+g), g = tan(π·fc/fs), par 1/16 d'octave de 10 Hz à 0,45·fs (179 entrées), interpolée ;
  `1 − G` donne le 1/(1+g) des états. Calculée une fois par bloc (0,67 ms), comme l'enveloppe.
- k = 4,3 × SWEEP/127 (+10 % sur l'accent) : au-delà de 4, le filtre linéaire s'emballerait ; le coude le borne
  (auto-oscillation stable).
- Passe-bas : sortie y4 × (1 + k/2), puis jusqu'à (1 + k) sur la dernière octave de COLOR (ci-dessous). Passe-haut :
  u − 4·y1 + 6·y2 − 4·y3 + y4, par décalages et additions.
- **Pas de marche à COLOR 64** (revue du 08/10/2026, choix de Kevin). La contre-réaction est inversée : à la coupure,
  les 4 étages la retardent de 180° et elle s'ajoute (la résonance) ; en dessous, sans retard, elle se retranche. Le
  gain du passe-bas sous la coupure est donc 1/(1 + k) (exact en discret : chaque étage TPT vaut 1 au continu), soit
  −12 dB à la résonance par défaut (k = 3,05). La compensation 1 + k/2 en rend une partie (la basse s'amincit avec la
  résonance, comme sur la 303, sans que le pic ne sature). Grand ouvert, toute la note est sous la coupure : il restait
  (1 + k/2)/(1 + k) = 0,62, **−4,1 dB** contre le filtre ouvert (64) et le passe-haut à 20 Hz, qui valent 1 (à ces
  fréquences, la contre-réaction du passe-haut est nulle). En tournant COLOR de 63 à 64, le son montait d'un cran.
  Correction : sur la dernière octave de COLOR (de 56,7 à 63,99, la position du potard, pas l'enveloppe, pour que le
  niveau ne suive pas l'enveloppe), la compensation monte jusqu'à 1 + k. Avec l'accent, jusqu'à 1 + 3k/4 seulement :
  attaqué plus fort, le filtre entre davantage dans le coude, la contre-réaction réelle est plus faible que k et il
  perd moins ; la pleine compensation le rendait 0,8 à 3,4 dB trop fort. Écart à 63,99 contre 64 (bande audible,
  note 36, résonance 60 / 90 / 127) :

  | Son | avant | après |
  |---|---|---|
  | scie | −2,9 / −4,1 / −4,1 dB | +0,7 / 0,0 / +0,4 dB |
  | carré | −1,9 / −3,9 / −4,4 | +1,7 / +0,2 / +0,1 |
  | scie + accent | −1,2 / −2,4 / −3,8 | +0,8 / 0,0 / −1,2 |
  | carré + accent | −0,3 / −1,2 / −2,5 | +1,8 / +1,2 / +0,1 |

  Limite : la compensation suit k et l'accent, pas le niveau réel du signal (le coude) ; un carré sans accent à
  résonance 60 reste à +1,7 dB.
- **Passe-haut depuis 10 Hz** (même revue, choix de Kevin). Il partait de 20 Hz : même là, 4 pôles penchent les notes
  graves (les plats du carré s'affaissent, chaque front repart de plus haut) : la note perd un peu (−1 dB à la note 36,
  −2,7 dB à la note 24) et ses crêtes doublent ; le carré accentué touchait le plafond de la sortie (écrêté), −3,7 dB
  après la chaîne d'ampli de l'OS, entre COLOR 64 et 65. Il part maintenant du bas de la table, 10 Hz (11 octaves sur
  63 crans, 20 kHz en haut comme avant ; 1er cran, 65 : 11,3 Hz). Avant la chaîne d'ampli, à 64,01 : note 36, scie
  −0,3 dB, carré accentué −0,3 dB sans écrêtage (crête 0,88) ; note 24 : −1,0 / −1,4 dB, le carré accentué y touche
  encore le plafond. Partir de 1 Hz aurait effacé le reste, mais demandait d'allonger la table (3,3 octaves) et, à
  pas égal, laissait ~19 crans sans effet audible. À résonance 127, l'auto-oscillation du passe-bas grand ouvert
  (vers 21 kHz, inaudible) est amplifiée elle aussi : +4,5 dB d'énergie sur toute la bande, crête ~0,35.
- Formats : signaux Q27 (marge ±16), coefficients Q31 ; sortie ramenée en Q31, saturée.

### 3.3 État, voix muette

Un état de 92 o par piste (BSS de la charge utile, 552 o), remis à zéro à la première note sur la machine (repère
`'ACD1'` en `voix + 0x2c`, effacé par la remise à zéro de la voix). **Voix muette non calculée** : sans trig, avec
l'enveloppe d'ampli sous 2^14, comme MACRO.

### 3.4 Images `[FAIT en émulation]`

Demande de Kevin (08/10/2026) : un smiley « acid » plutôt que l'image de TONE. Chaque machine a 3 images (`Bitmap`,
constructeur `0x40070172` : vtable `0x401117c8`, largeur, hauteur, mots par colonne, image, masque ; 1 bit par pixel,
colonne par colonne, y = 0 en bas, [39 §2](39-animation-demarrage.md)), construites au démarrage dans 3 tableaux de 6 :

| Tableau | Taille | Dessin d'origine | Où | Acid |
|---|---|---|---|---|
| `0x40fe32cc` | 48 × 33 | fiche « CLASS / STYLE / STR / DEX / MAG » | écran MACHINES (`drum_icons`) | fiche de TONE recopiée au build depuis TON OS, retouchée par 17 relocalisations (18 avec celle du paramètre Algorithm) : « CLASS:SYNTH », « STYLE:ACID », STR 4, DEX 5, MAG 3 (choix de Kevin) |
| `0x40fe384c` | 34 × 34 | lettre K, S, M, P, T, C | écran MACHINES, `0x4001b6a6` | smiley : disque plein, yeux et sourire évidés |
| `0x40fe37f0` | 25 × 22 | petite lettre | `0x400a4de6` (`small_icon`), `0x400a40bc`, `0x400a4fc6` | smiley, en petit |

- La police de la fiche est celle de l'OS (3 × 5 pixels, pas de 4) ; A, C, I et D sont dessinés ici sur ce modèle,
  les losanges pleins et vides aussi. Masques : ceux de l'OS, entièrement opaques.
- Trois objets `Bitmap` statiques dans la charge utile (`+0x1800`), puis les images (fiche 384 o, smileys 272 et 100 o).
- Écran MACHINES et petite lettre : détours propres à Acid (`acid_drum_icons`, `acid_small_icon`), ceux de
  `gs.detours_asm` avec nos objets pour la machine 6. Les 3 autres sites : `add.l tableau, %d0` remplacé par un `jsr`
  (6 o) qui rend notre objet si d0 = 28 × 6, sinon fait la même addition ; leur repli des machines > 5 passe de 5 à 6
  (l'ancien tweak les ramenait à SNARE : Acid y montrait un « S », comme MACRO aujourd'hui).
- Preuve : les objets sont octet pour octet ceux du vrai constructeur de l'OS ; la fiche est celle de TONE hors
  « STYLE:ACID » et les notes ; aux 5 sites, le vrai code de l'OS passe nos objets pour Acid et les siens, inchangés,
  pour les machines 0..5.

## 4. Les choix, et pourquoi `[FAIT en prototype]`

Prototype en flottants (Python, hors dépôt), écouté par Kevin, puis le même calcul en entiers (C) : écart de la
solution sans retard aux étages du filtre de 9 LSB de Q27 au plus sur 350 000 échantillons.

| Écrasement de la résonance | Coût par échantillon | Énergie hors harmoniques, note 36 / 72 (48 kHz ; suréchantillonné ×8) |
|---|---|---|
| aucun (filtre linéaire) | ~8 à 10 multiplications | −60 / −58 dB ; s'emballe dès k = 4 |
| écrêtage dur | ~10 à 12 | −38 / −23 dB (−37 / −23) |
| **coude à 3 segments (retenu)** | **~11 à 14** | **−40 / −24 dB (−40 / −24)** |
| tangente hyperbolique, Newton | ~30 à 50 (2 tours et une division par échantillon) | −40 / −24 dB (−39 / −24) |

- À 48 kHz et suréchantillonné 8 fois, chaque variante donne la même énergie hors harmoniques à 0,5 dB près : ce
  n'est pas du repliement, c'est l'écrasement lui-même. **Pas besoin de suréchantillonner.**
- Le coude sonne comme la tangente hyperbolique, pour le prix du filtre linéaire. Choix de Kevin à l'écoute.
- Calculer les coefficients une fois par bloc de 32 (et non tous les 8 échantillons) : retenu, pour la charge.

## 5. Place

| | |
|---|---|
| Charge utile au démarrage | `0x43000000`, comme MACRO seule (`gs.LAYOUT`) |
| Code et tables | 5 078 o à `+0` (code 3 076 o, tables 2 002 o) |
| Images et leurs objets `Bitmap` | 840 o à `+0x1800` (§3.4) |
| Détours, données, descripteurs, rangées, enregistrements | `+0x33000..0x36000` (`gs.LAYOUT`), comme MACRO |
| États des 6 pistes | 552 o à `+0x36000` |
| Ajouté à l'image (morceaux tassés, stub `PACK`) | 11 452 o (MACRO : 103 552 o) |
| Crochet de démarrage | masque de sprite `0x4016cae8`, à `0x400004b2`, comme MACRO |

## 6. Incompatibilités

- **MACRO**, **moteurs du Syntakt**, **SD VINTAGE** : même mécanique de machines ajoutées, même place, même crochet.
  Une charge utile commune les réunirait [À FAIRE si on le demande].
- **Model-TG** : version combinée `33-acid-tg.json` (`requires` `model-tg-st`), comme `32-macro-tg.json` `[FAIT en
  émulation]` : charge utile à `0x46700000`, Acid en 8e machine, détour `0x400a7dfe` (machines 0..6 vers Model-TG, Acid
  vers nos `update`/`render`, puis son étage `ah_noenv` : Attack, filtre), crochet de démarrage chaîné à son
  `boot_extra_hook`. Images : aux 3 sites de la lettre, la borne passe de 5 à 7 (`0x4001b696`, `0x400a4096`,
  `0x400a4f9e`) ; notre détour rend le smiley pour 7 et l'image de CHORD pour le Sampler (6), comme Model-TG seul.
- Avec les autres mods (6 canaux, arpégiateur, trig-hold, tempo, animation, drumkilla) : voir §7.

## 7. Le tweak et la preuve

- `26-acid.json` : 125 écritures (celles de MACRO seule, plus les 3 sites d'images), plus l'envoi à l'USB à heure fixe
  ([35](35-glitches-usb-multipiste.md)) et la boucle des voix de [36](36-regulateur-sans-coupures-inutiles.md).
- Compilé par `m68k-linux-gnu-gcc` 13.3 (Ubuntu 24.04, le compilateur de MACRO) ; un autre GCC donne d'autres
  octets, `--check` le dit.

Preuve (`tools/emu/test_acid.py`, 08/10/2026) `[FAIT en émulation]`, **tout OK**, seule, avec Model-TG (`acid-tg`
sur `model-tg-st`, mêmes vérifications, plus celles de `test_model_tg_syntakt.py` : 8 machines sur 2 lignes, touche
Attack, potards, images comparées à Model-TG seul, Sampler mêlé), et avec
`6ch-usbup,model-tg-st,trig-hold,arp,tempo-max,boot-anim` :

| Vérification | Résultat |
|---|---|
| Décompresseur du bootstrap | OS agrandi relu à l'identique, fin `0x401acdfc` (limite `0x40200000`) |
| Crochet de démarrage | charge utile de 221 736 o reconstituée à `0x43000000` depuis 11 452 o tassés ; SRAM intacte ; reprise normale |
| Interface (vérifications de `test_syntakt_machines.py`) | MACHINES : « Acid » après Chord, sa fiche et son smiley (§3.4), 7 repères ; molette jusqu'à 6 ; changement de machine réel : Cutoff 30, Wave 0, Reso 90, Env Mod 100, Decay 50 ; noms Cutoff / Wave / Reso / Env Mod ; machines 0..5 identiques |
| **Son, avant la chaîne d'ampli** | **identique échantillon par échantillon** au même moteur compilé pour l'ordinateur, rejoué avec ce que le moteur reçoit dans l'OS, sur 23 cas (défaut, carré, fondu, passe-bas fermé et ouvert, filtre ouvert, passe-haut, résonance 0 et 127, accent, enveloppe dans les deux sens, DECAY, GATE, notes extrêmes, COLOR balayé en 8.8, tous les potards qui bougent, changements de note) |
| Voix muette | calculée exactement quand l'OS l'impose (3 044 blocs, dont 269 muets à sortie nulle) |
| Chaîne d'ampli | mêmes lectures de la voix que TONE (24 champs, DECAY, PUNCH, GATE) |
| Machines d'origine | identiques à l'OS d'origine, sans une instruction d'Acid |
| Machine locks, 6 pistes Acid, Acid mêlée aux machines d'origine | tout joue ; chaque piste identique à la même piste jouée seule |
| Niveau autour de COLOR 64 | 63 / 63,99 / 64,01 / 65 à 2 dB près du filtre ouvert, après la chaîne d'ampli (note 36, scie et carré + accent, résonance 0 / 90 / 127) : passe-bas 0 à +0,4 dB, passe-haut −0,3 dB (scie), −1,7 à −2,0 dB (carré + accent, PUNCH de l'OS compris) (§3.2) |
| Comportement | le centre du spectre suit COLOR (passe-bas 71 / 177 / 818 Hz, passe-haut 3 314 / 5 820 / 14 948 Hz) ; résonance 127 + accent : auto-oscillation bornée par le coude |

**Piège trouvé en chemin** `[FAIT]` : la référence pour l'ordinateur additionnait les produits exacts puis tronquait
une fois ; l'EMAC tronque **chaque produit** en entrant dans l'accumulateur (8 bits sous le LSB du résultat,
`tools/emu/emac.py`). Un LSB d'écart dans les chaînes de 2 et 4 produits du filtre, amplifié par la contre-réaction :
la référence reproduit maintenant l'EMAC (`prod` puis `rd` dans `acid.c`, côté HOST). Le code du Cycles n'a pas
changé.

## 8. Charge

Instructions par bloc de 32 trames d'une voix (la boucle des voix entière, moins la même boucle sans voix), mesurées
dans la vraie boucle des voix `[FAIT en émulation]` :

| Réglage | 1er bloc | moyenne | maximum | moyenne / TONE |
|---|---|---|---|---|
| passe-bas (défaut) | 5 481 | 4 471 | 4 481 | 0,85 |
| passe-haut | 5 870 | 4 860 | 4 870 | 0,92 |
| filtre ouvert (COLOR 64) | 3 090 | 2 402 | 2 412 | 0,45 |
| carré | 5 734 | 5 114 | 5 206 | 0,97 |
| résonance 127 + accent (au-delà du coude) | 5 875 | 4 560 | 5 051 | 0,86 |
| note 96 | 5 342 | 4 677 | 4 723 | 0,88 |
| passe-haut + carré + accent + résonance 127 (pire cas cumulé) | 5 924 | 5 497 | 5 604 | 1,04 |

TONE : 5 291 ; voix muette : 572 ; pile : 240 o sous la boucle des voix. Réglage par réglage, une voix Acid coûte
moins qu'une voix TONE ; tout cumulé, jusqu'à 6 % de plus (5 604 au pire bloc). Les autres machines d'origine coûtent
plus que TONE (CHORD ~8 300 au même réglage) : six pistes Acid restent sous la charge des six machines d'origine,
sans régulateur de charge, mais pas forcément sous celle de six pistes TONE. Ce sont des
instructions, pas des cycles (caches de 8 Ko, attentes de l'EMAC) : le compteur de charge sur la machine le dira
([23](23-optimisation-charge.md)).

Avec Model-TG (son étage `ah_noenv` compris) : TONE 5 669 ; Acid de 2 461 (ouvert) à 5 173 (carré) en moyenne, 0,43 à
0,91 TONE.

## 9. À vérifier sur la machine

1. Le Cycles démarre ; MACHINES montre « Acid » après Chord, avec sa fiche (« STYLE:ACID ») et son smiley, le smiley
   aussi sur les autres écrans qui montrent l'image de la machine ; la molette y va et en revient.
2. Les noms des potards (Cutoff, Wave, Reso, Env Mod) tiennent à l'écran ; leurs défauts au changement de machine.
3. COLOR : passe-bas de sombre à ouvert, rien à 64, passe-haut de plein à fin, sans saut de volume de 63 à 65 ; SWEEP qui couine puis siffle seul en
   haut de course ; CONTOUR dans les deux sens ; PUNCH sur quelques pas (accent).
4. Six pistes Acid ensemble, et Acid avec les machines d'origine : pas de craquement.
5. `CONFIG › UPGRADE` par USB revient toujours à l'OS officiel.

## 10. Slide façon 303 : étude `[EN COURS]`

Demande de Kevin (08/10/2026) : un slide comme sur la 303. Idée retenue avec lui : **un pas dont la note est tenue
jusqu'au trig suivant (GATE à 1, longueur du trig qui va jusqu'au trig suivant, « 100 % ») glisse vers la note
suivante**, comme le commutateur SLIDE de la 303 (note tenue et glissement ne font qu'un). Le slide trig de Model-TG
([31 §9](31-model-tg.md)) est autre chose : il fait glisser tous les paramètres qui diffèrent, sur tout l'intervalle
entre deux trigs, et les enveloppes repartent ; il demande Model-TG.

### 10.1 L'enveloppe d'ampli, GATE et la fin de note `[FAIT]`

Lecture de `0x400a9252` (enveloppe), `0x400a9430` (VCA), `0x400a7d4a` (boucle des voix), puis mesure en émulation
(Acid, DECAY 60) :

| Champ de la voix | Rôle |
|---|---|
| `+0x34` / `+0x38` | trig de ce bloc / du bloc précédent (masque `trig_mask` de la boucle des voix) |
| `+0x3c` | fin de note de ce bloc (2e masque de la boucle des voix, `release_mask`) |
| `+0x24c` | GATE, recopié de `params + 0x20` à chaque bloc par la boucle des voix (`0x400a7de0`) |
| `+0x230` / `+0x234` | niveau de l'enveloppe, ce bloc / le précédent (`0x80000000` = plein) |
| `+0x23c` | état : 0 attaque, 1 décroissance, 2 tenue |
| `+0x244` | fin de note en attente : posé si `+0x3c` sans trig dans le bloc |
| `+0x248` | pas d'attaque : `0x80000000` (attaque instantanée) pour Acid comme pour TONE |

- **GATE à 0** : attaque instantanée, puis décroissance (état 1), quoi qu'il arrive.
- **GATE à 1** : après l'attaque, l'enveloppe **reste pleine** (état 2) jusqu'à une fin de note (`+0x3c`), puis
  décroît. Mesuré : pleine 1 500 blocs (1 s) sans fin de note ; fin de note au bloc 300, décroissance dès le bloc 301.
- **Fin de note et trig dans le même bloc** : le trig gagne (`+0x244` n'est posé que sans trig), la note reste tenue.
- **Chaque trig fait un creux** : au bloc du trig, le VCA met le niveau à 0 et descend vers 0 sur les 32 trames
  (0,67 ms) ; au bloc suivant, l'attaque instantanée remet le plein d'un coup. Mesuré sur une note tenue (bloc 300 :
  niveau 0, bloc 301 : plein), sur une note qui décroît aussi. C'est le comportement de toutes les machines.
- Le PUNCH de l'OS (`0x400a967a`) repart lui aussi sur `+0x38`.

### 10.2 D'où vient la fin de note `[FAIT en partie]`

L'OS a une longueur de trig (chaînes « Trig Length », « LEN », « Len:%4s », « INF »). Le masque `release_mask` est
construit par l'appelant de la boucle des voix (`0x40059382` → `0x4005979e` → `0x4005981e`, champ `+0x14` de sa
structure), à partir d'événements en attente par piste, sans les pistes qui ont un trig dans le bloc ; à l'arrêt du
séquenceur, il vaut « toutes les pistes ». C'est bien la **longueur du trig** (§10.4) : le constructeur de trigs met la durée de la longueur dans l'événement
de la note (`+0x34`), recopiée par piste quand la note part (`0x400590aa`) ; INF a une durée nulle, aucune fin de note.
Reste `[HYP]` : le décompte lui-même (non suivi jusqu'au bit du masque), et le relâchement d'une touche ou un note-off
MIDI.

### 10.3 Ce que ferait Acid `[À FAIRE]`

- **Détection, dans `update`, au bloc du trig (`+0x34`)** : GATE à 1, enveloppe en tenue (`+0x23c` = 2) et pas de
  fin de note en attente (`+0x244` = 0) : la note précédente est encore tenue, c'est un slide. `update` passe avant
  le VCA : il voit l'état d'avant le creux.
- **Hauteur** : au lieu de prendre la note d'un coup, la hauteur courante (en demi-tons, 16.16) rejoint la nouvelle
  d'une fraction fixe par bloc (lissage exponentiel, ~60 ms comme la 303 ; une multiplication par bloc).
- **Pas de creux, pas de nouvelle attaque** : notre `render` appelle lui-même la chaîne d'ampli ; pour un slide, il
  l'appellerait avec `+0x34` / `+0x38` masqués (remis ensuite) : l'enveloppe reste en tenue, le PUNCH ne repart pas.
- **Enveloppe du filtre** : pas relancée sur une note glissée (comme la 303).
- Ouvert : l'accent sur la note glissée (la 303 l'applique), le temps de glissement (pas de potard libre : fixe).
- Ce que perd l'utilisateur : une note GATE à 1 tenue jusqu'au trig suivant glisse toujours ; pour une note tenue
  sans glissement, raccourcir sa longueur.
- Bonus probable : au clavier, jouer lié (une touche avant de lâcher la précédente) glisserait aussi, si `release_mask`
  est bien le relâchement des touches (§10.2).

### 10.4 Une valeur « SLD » après INF sur la longueur `[FAIT : lecture de l'OS ; À FAIRE : le code]`

Proposition de Kevin (08/10/2026) : sur le potard de longueur, après INF, une valeur **SLD** qui tient la note jusqu'au
trig suivant, met GATE à 1 d'elle-même et glisse vers la note suivante.

Ce que l'OS impose (lecture du code, et `docs/INTERNALS.md` de Model-TG v1.1.0, qui décrit les mêmes données) :

| Où | Quoi |
|---|---|
| descripteur n° 17, `0x4010e098` | « Trig Length » / LEN : paramètre de trig (type `0x12`, indice 2), 0..127 (`max 0x7f00`), défaut 14 |
| `0x40045a68` | affichage : 0..126 → « 1 » à « 127 » (`%d` de la valeur + 1), 127 et au-delà → « INF » |
| pas + `192` (octet signé) | longueur du pas ; −1 = celle de la piste (`+709`) ; lue par le constructeur de trigs (`0x400549f8`) |
| `0x4010d818` | durée par longueur, 128 mots : 1/8 de pas = 337 500, un pas = 2 700 000 (longueur 14), … ; **INF (127) = 0** : pas de fin de note. Le mot suivant (indice 128) vaut 1 |
| drapeaux du pas, bit 12 (`0x1000`) | inutilisé par l'OS, sauvé, chargé et copié avec le pas (Model-TG s'en sert pour ses slide trigs) ; le constructeur de trigs le recopie tel quel dans l'événement de la note (`+0x28`, `0x40054bca`) |

Conséquences :

- **SLD ne peut pas être la valeur 128** : la longueur du pas est un octet signé (128 y vaut −128) et, sur l'OS
  d'origine, l'indice 128 de la table donne une durée de 1, une note coupée aussitôt.
- **SLD = longueur 127 (INF) + bit 12 du pas.** Sur l'OS d'origine (retour par CONFIG › UPGRADE), un pattern fait
  avec SLD joue INF : rien ne casse. Avec Model-TG, ce même bit est un slide trig : les deux se
  marcheraient dessus avec `acid-tg` (d'où le choix du §10.5).
- **À écrire** (détours) :
  1. le potard : une valeur de plus après INF (max du descripteur 127 → 128), avec un détour du setter et du getter
     de la longueur du pas : 128 ↔ (127, bit 12) ;
  2. l'affichage : « SLD » pour 128 (détour de `0x40045a68`, ou de son appelant pour la longueur seule) ;
  3. le passage à Acid : là où la note part (`0x40059016`..`0x400590aa`, événement `a2` en main), recopier le bit 12
     de `+0x28` dans un mot par piste de la charge utile ;
  4. Acid : note SLD → GATE à 1 (écrit dans `voix + 0x24c` après la boucle des voix, avant la chaîne d'ampli) et
     glissement vers le trig suivant, comme au §10.3.
- À vérifier avant d'écrire : tous les endroits qui lisent ou bornent la longueur (écran NOTE/VEL/LEN `0x40029ac0`,
  trig-preview, copier/coller, p-locks de longueur s'il y en a), et les écritures des autres tweaks à ces adresses.

### 10.5 Choix retenu : le slide trig de Model-TG, joué en slide 303 par Acid `[À FAIRE]`

Kevin (08/10/2026) : avec Model-TG, garder son slide trig (SETTINGS + touche de pas) pour marquer les pas, mais
qu'Acid le joue en slide 303. SLD (§10.4) en attente : il prendrait le même bit 12 que Model-TG.

- **Ordre** : la PR d'Acid seule ; puis `acid-tg` (version combinée, comme `32-macro-tg.json`) ; puis ce slide.
- **Sur une piste Acid** : Acid lit le glissement que `sld_seq` arme (état à `SLD_BASE`, symbole exporté) et coupe le
  balayage de `sld_apply` pour sa piste : la note d'avant reste fixe. Au slide trig : hauteur qui rejoint la nouvelle
  note (prise du trig, `pmod`) en ~60 ms, enveloppe du filtre non relancée, chaîne d'ampli appelée trig masqué (pas
  de creux, §10.1). Les autres machines gardent le slide de Model-TG.
- **Volume (choix c)** : une note marquée pour glisser est **tenue au plein** jusqu'au slide trig (GATE forcé à 1 par
  Acid, `voix + 0x24c`), comme une note liée de la 303 ; repli si l'OS s'y prête mal : relancer au plein sans creux.
- À lire avant d'écrire : `src/model_tg.s` (v1.1.0, MIT) pour la disposition de l'état des glissements et la façon de
  couper `sld_apply` sur une piste.
