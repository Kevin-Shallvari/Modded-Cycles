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

### 3.1 Les états des voix : déplacer le bloc « autre utilisateur » `[HYP → le décodage avance (§3.3)]`

- La zone à libérer : `0x42309ad0 .. 0x4230a100` (les deux logements des pistes 7-8 ; les références
  `0x400598ea`, `0x40059be8`, `0x40059bf6` coincident avec ce que la borne-8 écrase) ;
- **[À FAIRE]** Aucune réference littérale **à l'intérieur** de la plage : les sites-litteraux
  ne visent que `0x42309ad0` (3 fois), `+4`, `0x42309b08` (2) et `0x42309b28` (1) — tout l'intérieur
  est adressé par **décalage**, l'étendue exacte n'est donc visible qu'à l'exécution.

### 3.3 (séance du 11/10) Ce que le bloc « autre utilisateur » est réellement — Demi-décode `[FAIT]`

Désassemblant les 5 sites de références littérales, les deux premières fonctions sont l'état
**d'un module annexe (des latches de temps)**, null doute un minuteur de phase horloge :

- Peut-être une seule entité — la fonction `0x400598b8` lit et écrit :
  - une table de **2 mots longs par côté** (index `d2 = lsl #3` : lité `0x42309ad0`, `0x42309ad4`),
    avec une protection entrée-musique par table à 15 entrées (`0x4010da18/da30/da70`),
    `moveq #f, d1` et un `and.l d1,d0` (clamps sur 15), l'écriture marquant un **délai infini**
    (`0x7fffffff`) et un *span* mis à zéro ;
  - **la table des index** `0x40a79134` et `0x40a7916c` (temps relatif par entrée et par mode) ;
  - les deux autres références `0x42309b08` et `0x42309b28` sont les miens (les index + et le
    travail applicatif de l'usage dans les autres fonctions du même module).
- **Confusion claire** : un suivi d'événements géolocalisé aux **`« voice »` (côté audio)** à des
  heures voulues. Le bloc est *offset-addressed* et borné **par ses tables d'index** ; son étendue
  **réelle** dépend de ce que les indices portent ; l'étendue mécanique bornée par l'OS (un lapin :
  index 0..15 × 8 o = 120 o) **est bien en deçà** de ce que le banc born-8 a écrit (0x4230a100).
  **[À FAIRE]** faire le banc *de toute écriture détériorée*, pas juste l'empreinte, pour mesurer
  l'extension réelle du bloc. Notons que l'étendue mécanique trackée a montré **0x4230a100**
  — c'est peut-être **bien plus** avec les 8 pistes bornées : le banc d'extension à mesurer va
  déterminer s'il faut reloger le bloc autant d'octets.
- **L'alternative propre** qui reste ouverte : **conservé la continuité** (pistes 7-8 sur place →
  il faut quand même un « déplacement du bloc externe »), ou **compiler un détour** pour
  `_pistes 7-8 dans une seconde base` (« le débat propre est l'aide de la seconde zone »).

### 3.2 Les tampons de sortie : déplacer le tampon « post-mix » `[FAIT sur 6 refs]`

- Le vrai bloc : **2 tampons de 0x80 chaque** : L à `0x80001b58` et R à `0x80001bd8` —
  tout le bloc `0x80001b58..0x80001c58` compris (0x100 = **256 o**), avec **6 références**,
  toutes dans le noyau du mixeur :
  - L : `0x400569d4`, `0x400569fe`, `0x40056ad0`, `0x40056b0a` (2 appels `pea` + le chemin de
    l'envoi delay) ;
  - R : `0x40056ade`, `0x40056b18` (le chemin delay/reverb en R) ;
  - appels vers `0x400567a4` (recopier aux chaines) et `0x40056698/0x40056716` (multiplié par la
    « table des coefficients ») : la même paire est écrite ensuite (le cheminement du post-mix
    vers delay et vers reverb).
- **Les 6 « xrefs » restantes sont des fausses positives** : `0x80001c00/0x1c40/0x1c48` tombent
  dans des instructions (les seuls octets coïncidant avec un pointeur), vérifié octet par octet
  (les fragments `02eb 8806 8000 1c40` des sites `0x400794xx`, `0x4007e8xx`, `0x4014baxx` — des
  opérandes d'instructions, pas des pointeurs ; voir `build/re8/probe_postmix2.py`).
- **[FAIT en émulation, 11/10]** La fenêtre `0x800074b4..0x80008000` (2 892 o) est validée comme
  accueil, quatre garde-fous (`build/re8/probe_window.py`) :
  1. la copie de démarrage (ROM `0x4019b590` → SRAM `0x80000000`) y dépose **723 mots, tous nuls**
     — c'est du padding de BSS, pas des données ;
  2. la table des pointeurs de machines `0x40118590` (32 entrées) vise des adresses éparses
     (`0x80002464`, `0x80002060`, `0x8000e2d8`…, plus haut `0x8000e6dc`) : **aucune entrée dans la
     fenêtre** ;
  3. le balayage de toute l'image ne donne que 12 valeurs distinctes de la fenêtre, 59 occurrences,
     toutes dans des zones de données (masques de sprites/constantes : le plus bas, `0x800076da` ;
     le plus fréquent, `0x80007fff` × 46 = un masque) ; **les 565 premiers octets
     `0x800074b4..0x800076d9` n'apparaissent nulle part**, pas même comme coïncidence ;
  4. exécution réelle (boot + 24 blocs, les 6 machines d'origine trigées, CHORD compris) :
     **0 accès** à la fenêtre.
- **Accueil retenu** (dans les 565 o vierges) : staging L/R (256 o) à `0x800074b4..0x800075b4`,
  **+ les tampons de travail des pistes 7-8** (2 × 0x30 = 96 o) à `0x800075b4..0x80007644`.
  En 0x80001c58 il y a en effet un **compteur de temps de 4 o** (outil de mesure `0x4008ec4c`,
  lu comme valeur) — et juste après, la banque d'ondes de CHORD : le tampon de staging n'a donc
  pas le droit d'y rester, et les iniciarateurs (l'init voix `0x4005974c` avance `0x8000bd98 +
  t·0x30`, bornée par le `cmpi #0x120` de son boucle 6 pistes) écriraient le tampon de KICK
  (0x8000beB8, notes/26) si on les laissait avancer — d'où les 96 o dans la fenêtre.
- **Limites de la preuve** : l'ISR complet et les IRQ UI/MIDI/séquenceur ne sont pas émulés ;
  les 12 constantes restent éventuellement lues par du code non couvert. Audite plus profond
  possible : un relevé d'écriture depuis la machine (firmware de diagnostic).

## 4. Le chemin menant au premier firmware Groove

1. Décoder l'étendue réelle du bloc « autres utilisateurs » (§3.3) et choisir sa recopie.
2. Trouver l'accueil SRAM du tampon post-mix (§3.2), par le banc du mixeur (§4).
3. Écrire `tools/gen_groove_8.py` (un seul `tweak` dérivé, en ligne de commande seulement,
   pas dans le flasher ; SHA-256 du MAIN OS obligatoire par build) : bornes + relocations + les littéraux
   cités, sorties dans `tweaks/model-cycles_OS1.13/NN-groove-8tracks.json`.
4. Prouver en émulation avec `tools/re/test_load8.py` (pistes 0-5 octet-identiques stock ;
   7-8 jouent avec machine TONE ; pile impeccable) — plus la vérification MIDI/note-par-piste que le
   full ISR (qui ne se débusque pas).
5. Sans modification : chaque jalon publie son SHA-256 du MAIN OS (notes/55 §2bis).

## 5. Ce qui compte pour la suite

- Les emplacements à libérer totalisent ~0x100 o de SRAM tu coût à trouver (§3.2) et la zone d'états du
  bloc de temps (§3.3, étendue à corroborer) — les pistes elles-mêmes restent en place, continuité
  gardée.
- La nécessité de connaître exactement « où » : le banc empirique a montré que chaque « assez de
  pistes » est une hypothèse à vérifier — les zones de SRAM sont denses, et l'étendue du bloc de temps
  de temps n'apparaît pas dans les références littérales.
- Le §3 s'applique sans conflit avec les mods du dépôt (la ligne Groove n'en porte aucun) : les
  toutes écritures liées au mek des sites des mods du dépôt ne s'y chevauchent pas.
