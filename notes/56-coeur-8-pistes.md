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

### 3.1 Premier dessin, **dépassé** (11/10) : évacuer le voisin des états de voix

- Le premier dessin gardait les pistes 7-8 « sur place » (pour ne pas toucher aux pas de la boucle)
  et évacuait le bloc voisin `0x42309ad0..0x4230bb28`. Décode de ce bloc : la zone du **scanner du
  panneau** — minuteur 12 kHz / 12 phases (`0x40059cd0`), **tampon de balayage des touches**
  `0x42309b08` (24 o = 12 phases × 2), et un **anneau de 8 Ko** `0x42309b28..0x4230bb28`
  (1024 × 8 o, accesseur `0x4007f104`, index `0x40f0bf20` borné à `0x3ff`).
- **Dépassé** : le census (§3.4) a montré qu'**aucun** tableau par piste n'est atteint par un
  pointeur — tous le sont par *littéral de base + pas*. Chaque **ligne entière** peut donc être
  relogée, et **la zone du panneau n'est plus touchée du tout** : le chemin d'entrée (touches,
  maintien, anti-rebond) reste intact. Le dessin « déplacer le voisin » ne sert plus.

### 3.2 Le « jumper » (idée de Kevin) : rejeté `[FAIT]`

- Idée : un « saut » dans le dernier logement d'une ligne, pointant vers une seconde ligne.
- Rejeté : **la boucle ne lit jamais un pointeur**. Elle fait `lea $31c(aX),aX` (elle additionne).
  Un pointeur écrit dans un logement serait lu comme un paramètre de son (fausse hauteur), pas suivi.
  Le faire suivre = lire un pointeur à chaque pas dans la boucle chaude : plus lourd et plus risqué
  que réécrire ~50 constantes. **Mais l'idée a servi** : elle a forcé la vérification qu'aucune ligne
  n'est atteinte par une table de pointeurs — vérifié pour toutes (census §3.4).

### 3.4 Census des tableaux par piste `[FAIT]`

Chaque ligne = *base littérale + pas fixe* ; pour 8 pistes elle devient `8 × pas`. Littéraux comptés
par balayage de l'image (toutes les valeurs de la plage, pas seulement la base).

| # | Ligne | Base | Pas | Fin (6 logements) | Classe | Littéraux | Traitement |
|---|---|---|---|---|---|---|---|
| 1 | états des voix | `0x42308828` | `0x31c` | `0x42309ad0` | DDR | 5 : base, +4, +0x34, +0x38, +0x318 (init) | reloger la ligne |
| 2 | params (copie audio) | `0x8000100c` | `0x42` | `0x80001198` | SRAM | 2 : base, +0x16 | reloger |
| 3 | tampons de sortie | `0x80001858` | `0x80` | `0x80001b58` | SRAM | 9 | reloger |
| 4 | tampons de travail | `0x8000bd98` | `0x30` | `0x8000beb8` | SRAM | 1 (init) | reloger |
| 5 | note du trig (pmod) | `0x80001830` | `4` | `0x80001848` | SRAM | 4 | reloger |
| 6 | retrig / note directe | `0x40a78d58` | `0x1c` | `0x40a78e00` | DDR (BSS) | 4 adresses / 11 sites : base ×8, +4, +0x10, +0x14 | reloger |
| 7 | note courante | `0x40fe4cb4` | `4` | `0x40fe4ccc` | DDR (BSS) | 4 | reloger |
| 8 | gains du mixeur | `0x40a78b80…8c08` | littéraux par piste | — | DDR (BSS) | 1 par piste | 2 littéraux neufs |
| 9 | zone « événements » | `0x800015a0…0x8000182c` | 4 | — | SRAM | ~25 (voir §3.5) | reloger **+ retouches de code** |
| 10 | cluster BSS | `0x40fe4c90…0x40fe4cf8` | 4 | — | DDR (BSS) | ~8 (voir §3.5) | reloger **+ retouches de code** |

Points relevés au passage :
- La ligne 1 est bien privée au moteur (boucle + init seuls) ; son littéral `+0x318` est l'init des
  tampons de travail (`0x40059762`).
- Les littéraux **intérieurs** existent (ligne 6 : `+4`, `+0x10`, `+0x14`) : le census les compte tous.
- Les valeurs voisines trouvées dans la plage d'une ligne (ex. `0x80001848/4c/50` après pmod,
  `0x8000beb8` après les tampons de travail) sont **d'autres objets**, pas des logements de la ligne :
  ils restent où ils sont, la ligne part.

### 3.5 Les deux mini-zones : reloger **et** retoucher du code `[FAIT]`

Ces deux groupes ne sont pas des lignes simples : leurs tableaux par piste sont **entrelacés** avec
de petits champs, et certaines boucles sont **déroulées** ou portent des **décalages figés**.

- **Zone « événements » SRAM** (`0x800015a0..0x8000182c`, ~0x290 o) : base `0x800015a0` (12 sites),
  plus les tableaux par piste `0x800017b4`, `0x800017cc` (minuteurs), `0x800017ec`, `0x80001800/04`,
  `0x8000181c` (drapeaux/événements), `0x800017e4/e8` (pointeurs), et la copie de 0x42 o à
  `0x8000173a`. Contraintes de code relevées :
  - boucle à **6 pas** bornée par `moveq #$6,d1` en `0x40059240` (à porter à 8) ;
  - **groupe déroulé** `0x40058de4..0x40058e02` : six instructions, une par logement
    (`+0`, `+4`, … `+0x14`) — il en faudra deux de plus (ou le transformer en boucle) ;
  - **décalages figés** dans le code : `clr.l -$18(a0)` et `clr.l 0x14(a0)` en `0x40059218/0x40059228`
    (distances entre deux tableaux) ; la boucle de remise à zéro compare à la **fin absolue**
    `cmpa.l #$80001804` (`0x40059526`).
- **Cluster BSS** (`0x40fe4c90..0x40fe4cf8`, ~0x68 o) : tableaux par piste `0x40fe4c9c` (8 sites),
  `0x40fe4cb4` (note courante, ligne 7), `0x40fe4cd0`, `0x40fe4cdc`, `0x40fe4cf0/cf4`, plus des
  tampons de 12 o (`0x40fe4c90` → `0x40fe4cd0`, recopie `0x40059836`). Même nature : reloger le bloc
  en conservant les écarts, et porter les bornes/boucles à 8.
- **Conséquence** : ces deux groupes demandent une **liste d'édition de code** (bornes, groupes
  déroulés, décalages figés) en plus des réécritures de littéraux. C'est le point le plus délicat de
  la phase 2 ; il est borné (les sites sont énumérés ci-dessus) et sera traité en premier à
  l'implémentation, avec la preuve `0xFF` (§3.6).

### 3.6 Les contrôles de risque adoptés `[FAIT]`

1. **Census durci** (§3.4/3.5) : par ligne, la base **et** les littéraux intérieurs **et** les bornes
   qui portent le compte (`cmpi #0x18c`, `cmpi #0x120`, `moveq #6`…), plus la vérification « aucun
   autre chemin ne peut calculer dans la plage » (pas de table de pointeurs) et « l'adresse n'est
   donnée à aucun matériel » (pas de DMA/registre).
2. **Hooks de lecture** aux accueils : l'émulation ne comptait que les écritures ; les lectures aussi
   (la banque d'ondes de CHORD précède la couture SRAM — ses lectures ne doivent pas mordre dedans).
3. **Banc `0xFF`** : chaque relogement est rejoué deux fois, accueil rempli de `0xFF` puis de `0`,
   comportement identique exigé — preuve qu'aucune ligne n'est lue avant d'être écrite.
4. **Stub de démarrage** si 3 échoue : petit nettoyage (~20 o) après la remise à zéro du BSS et avant
   les interruptions (la couture SRAM et la queue haute ne sont **pas** nettoyées au démarrage).
5. **Liste machine** écrite d'avance pour Maxime : 6 pistes d'origine identiques, panneau/maintien,
   écrans, MIDI, chargement/sauvegarde de projet, audio USB et `CONFIG › UPGRADE`, puis les 2 pistes.


### 3.7 Annexe : le tampon de staging « post-mix » (dessin dépassé)

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
- **Dépassé aussi (11/10)** : avec le census §3.4, le tampon de staging n'a plus besoin de bouger —
  c'est la **ligne des tampons de sortie** qui se reloge en entier (§3.4, ligne 3), staging compris
  dans le voisinage laissé en place. Les 6 références et la validation de la fenêtre restent utiles
  comme accueil des lignes SRAM (§3.4).

## 4. Le chemin menant au premier firmware Groove

1. **Liste d'édition des mini-zones** (§3.5) : bornes (`moveq #6` en `0x40059240`, `cmpa #0x80001804`
   en `0x40059526`), le groupe déroulé `0x40058de4..0x40058e02` (six instructions → huit), les deux
   décalages figés (`-$18(a0)`, `0x14(a0)` en `0x40059218/0x40059228`), et les bornes des lignes
   simples (boucle des voix `6→8`, init `0x120→0x180`, lissage `0x18c→0x210`).
2. **Bancs de contrôle** (§3.6) : hooks de lecture aux accueils, puis banc `0xFF` vs `0` sur chaque
   relogement ; stub de démarrage si nécessaire.
3. Écrire `tools/gen_groove_8.py` (tweak en ligne de commande seulement, pas dans le flasher ;
   SHA-256 du MAIN OS publié par build) : bornes + ~50 littéraux des lignes 1–8 + les deux mini-zones
   + les 2 appels neufs du mixeur + 10 entrées de descripteurs + 3 bornes du quick-mute + le pas du
   pattern et la conversion des projets — sortie dans `tweaks/model-cycles_OS1.13/NN-groove-8tracks.json`.
4. Prouver en émulation avec `tools/re/test_load8.py` (pistes 0-5 octet-identiques stock ; 7-8 jouent
   avec machine TONE ; pile impeccable) — plus le banc `0xFF` ; la vérification MIDI/note par piste
   relève de la machine (l'ISR complet ne s'émule pas).
5. Chaque jalon publie son SHA-256 du MAIN OS (notes/55 §2bis) ; essai machine par Maxime avec la
   liste du §3.6.

## 5. Ce qui compte pour la suite

- **Dix lignes** (§3.4) : huit se relogent par réécriture de littéraux (5 + 2 + 9 + 1 + 4 + 4 + 4 +
  2 neufs), deux sont des **mini-zones entrelacées** qui demandent en plus des retouches de code
  (§3.5) : bornes à porter à 8, un groupe déroulé de six instructions à allonger, deux décalages
  figés et une comparaison de fin absolue.
- **Accueils** : SRAM — la couture `0x800074c0..0x80008000` (2 880 o, jamais copiée) pour les lignes
  2–5 (~2 Ko), la queue `0x8000f2e8..0x80010000` (3 352 o) en réserve ; DDR — la fenêtre
  `0x4230dc10..0x4232d1a8` (≈128 Ko, dans le BSS remis à zéro) pour la ligne 1 (6,4 Ko).
- **La zone du panneau n'est plus touchée** (§3.1) : entrées, maintien et anti-rebond restent
  intacts ; c'est la plus grosse réduction de risque de la séance.
- **Les contrôles** (§3.6) : census durci, hooks de lecture, banc `0xFF`, stub de démarrage si
  besoin, liste machine — la seule conséquence qu'aucun contrôle en atelier ne couvre est une ligne
  touchée par l'UI/le panneau/l'USB/le MIDI ; c'est l'objet de la liste machine.
