# 56 — Le cœur 8 pistes (phase 2 de Model:Groove) : où rangent les pistes et comment les placer

Travail du 11/10 (suite de [55](55-model-groove.md)). La phase 2 est le cœur : faire jouer 8 pistes
audio à l'OS 1.13. Cette note fixe le dessin de l'implantation avec les chiffres de la séance
(la vraie boucle en émulation, mesurée pas à pas — les empreintes sont **[FAIT]** ; les
choix d'adresse pas encore fixés restent **[À FAIRE]**/`[HYP]`).

Récapitulatif du mod voulu (phase 2) : borne de piste `moveq #6→#8` en `0x400a7e40`, mixeur 6 → 8 appels, +10 entrées de descripteurs (560 o en cave), 3 bornes du quick-mute `moveq #5 → #7` (`0x40013846, 0x40013928, 0x40013a90`), stride du pattern en 8 pistes et conversions, et les relocations de RAM ci-dessous.

## 1. Le plan des pointeurs de la boucle des voix `[FAIT]`

Banc `build/re8/probe_voice_emac.py` (capstone + EMAC, la boucle complète `0x400a7d4a..0x400a7e6a`).

- **L'entrée de la boucle** reçoit 4 arguments : le **base des 6 tampons de sortie**
  (`0x80001858`), une zone de paramètres avance de 0xe (`lea $e(a2)`), le **masque des trigs** et
  le **masque des releases** ; les EMAC réglèrent la table `movel #160,%macsr` (`0xa0` = le mode
  de l'audio du M:C, notes/14).
- Le compte des pistes est **`moveq #6,d0` en `0x400a7e40`**. Les pointeurs avancent ainsi à
  chaque piste :
  | Pointeur | Ce qu'il porte | Stride |
  |---|---|---|
  | `a5` (`0x4230885c`), `a6` (`0x42308828`), `a3` (`0x42308860`), `a4` (`0x4230882c`) | états des voix (+ 0x34/0x38 trigs) ; `voix+0x318` = tampon de travail | **+0x31c** (`lea $31c(aX)`, `0x400a7e42..0x400a7e52`) |
  | `a2` (les paramètres, l'arg 2) | slots 8.8 par piste | +0x42 (`lea $42(a2)`, `0x400a7e4e`) |
  | `d3` (arg 1 = le base des tampons) | **le tampon de sortie de la piste** | **+0x80** (`addi #0x80, d3`, `0x400a7e3a`) |
  | `a0` (arg 4 du dé dispatch, d'après le `sp@48` table) | tableau des pointeurs par piste | +4 par piste (`addql #4`, `0x400a7df6`) |
- La boucle ÷2 « pistes » s'arrête après le rendu appelé au tampon de la piste courante
  (`moveal %d3,%a1`, 32 mots ; la « division des pistes par 2 » sous Model-TG, notes/36 §4).

## 2. Les empreintes de RAM avec la borne 8, mesurées `[FAIT]`

`build/re8/probe_footprint.py` (hook d'écriture sur un bloc stable, stock vs borne 8, TONE
soutenues). Pour 8 voix TONE actives :

- **états de voix** : les écritures courent jusqu'à **`0x4230a100`** (le stock s'arrête à
  `0x42309ac8`) : les pistes 7-8 occupent alors **`0x42309ad0..0x4230a100`**, c'est-à-dire la zone
  des « prochaines utilisations » de l'OS (les références `0x400598ea/0x40059be8/0x40059bf6`).
- **tampons de sortie SRAM** : s'écrivent en fenêtres de 64 o jusqu'à **`0x80001c40`** (le stock
  jusqu'à `0x80001b40`) : les pistes 7-8 occupent alors `0x80001b58..` — sous le post-mix.

## 3. L'implantation proposée : seule la zone **étrangère** est relogée `[HYP → à valider]`

Conserver **la continuité** (les pointer-strides de § ne doivent pas se reecrire) : les pistes 7-8
sont *sur place*, exactement après les 6 ; ce qui doit partir, c'est l'autre utilisateur de la
zone.

### 3.1 Les états des voix : déplacer le bloc « autre utilisateur » (3 refs)

- La zone à libérer : `0x42309ad0 .. 0x4230a100` (0x330 = 816 o de fin de l'empreinte born-8
  à couvrir ; les 3 références `0x400598ea`, `0x40059be8`, `0x40059bf6` portent dessus).
- **[À FAIRE]** DÉCODER l'**exacte étendue** du bloc (pour choisir sa nouvelle adresse DDR
  libre, p.ex. au-dessus de la fin de BSS `0x423380b0`, sous la pile `0x48000000`, zone libre
  notes/27 §3) et ses lectures d'index. Déplacement de la constante le cas échéant : 3 littéraux.

### 3.2 Les tampons de sortie : déplacer le tampon « post-mix » (12 refs trouvées)

- Le bloc SRAM **vécu** : `0x80001b58..0x80001c58` (0x100 = 256 o) :
  - `0x80001b58` (4 refs : `0x400569d4`, `0x400569fe`, `0x40056ad0`, `0x40056b0a`) — le tampon
    dry/de staging du post-mix vers delay/reverb ;
  - `0x80001bd8` (2 refs : `0x40056ade`, `0x40056b18`) ;
  - sous-blocs internes désignés : `0x80001c00` (2), `0x80001c40` (3), `0x80001c48` (1).
- **[À FAIRE]** La place d'accueil en SRAM — *libre en stock* : les pages de xrefs relevées
  (`sram_xrefs.txt`) portent aussi les zones `0x800011e8..0x80001400` (un gap d'environ 540 o)
  et `0x80007500..0x80007e80`. À trancher par le banc — la sortie SDRAM est le plan de secours
  (latence, ~2 à 4 points du bloc `[HYP]`), l'accueil serait `0x4240....` avec les 12 littéraux
  retouchés.
- Le reste du mod (bornes, mixeur, descripteurs, quick-mute) ne dépend pas de ce choix.

## 4. Le chemin menant au premier firmware Groove

1. Étendre `mcfw` avec le décodage du bloc « autre utilisateur » des états de voix (§3.1) et
   trancher sa recopie (`0x4240...`).
2. Trouver l'accueil SRAM du tampon post-mix (§3.2), par émulation empirique (le banc qui n'empeche
   pas la fonction audio complète).
3. Écrire `tools/gen_groove_8.py` (un seul `tweak` dérivé, en ligne de commande seulement,
   pas dans le flasher ; SHV MAI obligatoire par build) : bornes + relocations + les littéraux
   cités, sorties dans `tweaks/model-cycles_OS1.13/NN-groove-8tracks.json`.
4. Prouver en émulation avec `tools/re/test_load8.py` (pistes 0-5 octet-identiques stock ;
   7-8 jouent avec machine TONE ; pile impeccable) — plus la horn MIDI/note-par-piste que le
   full ISR (qui ne se débusque pas).
5. Sans modification : chaque jalon publie son SHA-256 du MAIN OS (notes/55 §2bis).

## 5. Ce qui compte pour la suite

- Les emplacements à libérer totalisent ~0x330 o de SDRAM et 0x100 o de SRAM (§3), donc 8 pistes
  + 2 états + l'accueil de ces blocs relogés dans un DDR libre.
- La nécessité de connaître exactement « où » : le banc empirique a montré que chaque « assez
  de pistes » est une hypothèse à vérifier — les zones de SRAM sont denses.
- Le §3 s'applique sans conflit avec les mods du dépôt (la ligne Groove n'en porte aucun) : la
  disposition du RAM relogée ne touche pas les sites de leurs écritures.
