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
4. **Stub de démarrage** — **retiré** (§3.10) : les accueils étant dans le BSS remis à zéro au
   démarrage, le contenu initial est nul et aucun nettoyage n'est nécessaire. Il ne reviendrait que
   si l'on déplaçait un jour une ligne vers une zone non remise à zéro.
5. **Liste machine** écrite d'avance pour Maxime : 6 pistes d'origine identiques, panneau/maintien,
   écrans, MIDI, chargement/sauvegarde de projet, audio USB et `CONFIG › UPGRADE`, puis les 2 pistes.
6. **Assertion de disposition** (ajoutée après le §3.8.e) : le générateur connaît le début et la
   taille de chaque tableau de la zone reconstruite ; il **vérifie qu'aucun ne recouvre un autre**
   (les tableaux de 6 sont adjacents, un dimensionnement faux les fait se chevaucher en silence).
   Contrôle statique, exact, sans machine.
7. **Test d'isolement des pistes neuves** (ajouté après le §3.8.e) : écrire un marqueur distinct dans
   un logement de la piste 7, puis vérifier que le logement correspondant de la piste 8 est
   **intact**. C'est le contrôle qui manquait au banc `0xFF` : celui-ci ne voit pas les collisions
   *écriture sur écriture* entre deux pistes neuves (§3.9.2).
8. **Contrôle d'appel par piste** (§3.8.f) : compter les appels `table[d4]` de la boucle des voix par
   piste, pour trancher le seul « ne pas toucher » à risque (index de machine vs de piste).


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

### 3.8 Liste d'édition (étape 1) — les mini-zones `[FAIT]`

Désassemblage octet par octet (`build/re8/probe_editlist.py`, `probe_editlist2.py`,
`probe_bounds.py`, `probe_bounds2.py`). Chaque ligne donne les **octets d'origine** : le générateur
n'aura qu'à les remplacer.

#### a) Groupe déroulé : l'option A ne tient pas, l'option B tient largement

```
0x40058ddc  23c0800017e4   move.l d0, $800017e4.l
0x40058de2  42b9800017ec   clr.l $800017ec.l     ┐
0x40058de8  42b9800017f0   clr.l $800017f0.l     │
0x40058dee  42b9800017f4   clr.l $800017f4.l     │ 36 octets (6 × 6)
0x40058df4  42b9800017f8   clr.l $800017f8.l     │
0x40058dfa  42b9800017fc   clr.l $800017fc.l     │
0x40058e00  42b980001800   clr.l $80001800.l     ┘
0x40058e06  6000039c       bra.w $400591a4       ← immédiatement après : aucune marge
```

- **A (ajouter deux `clr.l`) est impossible en place** : il faudrait insérer 12 octets au milieu de la
  fonction, donc décaler tout ce qui suit et corriger chaque saut de la région. Rejeté.
- **B (remplacer les six par une boucle) tient dans les 36 octets** : `lea.l $<A'>.l,a0` (6) +
  `moveq #$8,d1` (2) + `clr.l (a0)+` (2) + `subq.l #$1,d1` (2) + `bne.b` (2) = **14 octets**, 22 de
  reste (compléter par des `nop`). Seul contrôle avant d'écrire : que `d1`/`a0` soient morts au point
  de branchement `$400591a4`.
- **C (repli)** : recopier le groupe dans l'espace libre (huit `clr.l` + `jmp` de retour) et remplacer
  les six instructions par un `jmp` (6 octets) — plus gros, gardé en secours.

#### b) Mini-zone 1 — les trois autres constructions

| Construction | Site | Octets d'origine | Remplacement |
|---|---|---|---|
| base T2 | `0x400591f8` | `41f9800017cc` `lea.l $800017cc.l,a0` | nouvelle base T2 |
| distance T2→T1 | `0x40059218` | `42a8ffe8` `clr.l -$18(a0)` | `42a8ffe0` (−0x20) |
| zéro du logement | `0x40059228` | `4290` `clr.l (a0)` | inchangé (décalage 0) |
| **borne** de boucle | `0x40059240` | `7206` `moveq #$6,d1` | `7208` (8) |
| base A | `0x40059518` | `41f9800017ec` `lea.l $800017ec.l,a0` | nouvelle base A |
| distance A→B | `0x40059520` | `42a80014` `clr.l $14(a0)` | `42a8001c` (B = A + 8 logements) |
| **fin absolue** | `0x40059524` | `b1fc80001804` `cmpa.l #$80001804,a0` | `<A'> + 0x20` |

**Correction du census** : `0x8000181c` **n'est pas** un tableau par piste — c'est un **masque 32
bits**, un bit par piste (`or.l d0,$8000181c.l` / `and.l d0,$8000181c.l` avec `d0 = 1 << piste`).
Huit pistes tiennent dans 32 bits : **aucune modification**. Idem `0x80001820`. Le chevauchement
redouté avec pmod (`0x80001830`) n'existe donc pas.

**Et surtout : la zone compte SIX tableaux par piste, pas quatre** (§3.8.e). Deux d'entre eux
n'apparaissent dans **aucun littéral** : ils ne sont atteints que par *décalage calculé*
(`addi.l #$NN` puis `(a0, dN.l*4)`), donc invisibles au balayage du census. La famille d'immediats
`0x77…0x93` est la signature « piste + constante » :

| Tableau | Atteint par | Immediat | Sites |
|---|---|---|---|
| `0x8000177c` | `0x800015a0 + (piste + 0x77) × 4` | `addi.l #$77` | `0x40058c32` |
| `0x80001794` | `+ 0x7d` | `addi.l #$7d` | `0x40058c3e` |
| `0x800017b4` (T1) | `+ 0x85` | `addi.l #$85` | `0x40059018`, `0x40059716` |
| `0x800017cc` (T2) | `+ 0x8b` | `addi.l #$8b` | `0x40058f1a`, `0x400590a4`, `0x4005970a` |
| `0x800017ec` (A) | `+ 0x93` | `addi.l #$93` | 6 sites |
| `0x80001804` (B) | A + 0x18 (déplacement `$14(a0)`) | — | `0x40059520` |

Ces cinq immediats devront être **recalculés** dans la nouvelle disposition (ils encodent la
position de chaque tableau dans la zone).

#### c) Mini-zone 2 — le cluster BSS

Correction du census : le cluster contient aussi des **tableaux de mots** (pas 2) indexés par la
piste (`move.w d0,(a0,d2.l*2)`), et deux tampons de 12 octets recopiés l'un dans l'autre.

| Élément | Base | Pas | Logements | Sites |
|---|---|---|---|---|
| tampon source | `0x40fe4c90` | 2 | 6 mots (12 o) | `0x40056da6`, `0x4005983c` |
| tableau long | `0x40fe4c9c` | 4 | 6 | 8 sites |
| note courante | `0x40fe4cb4` | 4 | 6 | 4 sites |
| tableau mot | `0x40fe4cd0` | 2 | 6 mots (12 o) | 4 sites |
| tableau mot | `0x40fe4cdc` | 2 | 6 mots (12 o) | 4 sites |
| petits champs | `0x40fe4cf0/4` | — | — | 2 + 1 |

| Construction | Site | Origine | Remplacement |
|---|---|---|---|
| boucle bitmask | `0x4005929a` | `7206` `moveq #$6,d1` | `7208` |
| remise à zéro | `0x4005965c` | `7218` `moveq #$18,d1` | `7220` (8 longs) |
| garde « dernière piste » | `0x400596f2` | `7405` `moveq #$5,d2` | `7407` |
| taille de la copie | `0x40059830` | `4878000c` `pea.l #$c.w` | `48780010` (16 o) |

Les littéraux plus bas (`0x40fe4b84`, `0x40fe4b90`, `0x40fe4b94`) appartiennent à **d'autres objets**
(sites `0x400fabcc`, `0x40056d5c`, `0x4005938e`) : ils ne font pas partie du cluster.

#### d) Bornes candidates : vérifiées une par une

| Site | Valeur | Verdict |
|---|---|---|
| `0x40058d22` | `7406` #6 | **piste** (boucle T2, tête `0x40058cec`) → 8 |
| `0x40059240` | `7206` #6 | **piste** (boucle bitmask événements) → 8 |
| `0x4005929a` | `7206` #6 | **piste** (boucle bitmask cluster) → 8 |
| `0x4005973c` | `7006` #6 | **piste** (boucle qui appelle `(a2)` par piste) → 8 |
| `0x40059538` | `7406` #6 | **piste** : `cmp.l d0,d2` — `6` = « toutes les pistes » (joker) → 8 |
| `0x4005965c` | `7218` #0x18 | **piste** (6 longs) → `7220` |
| `0x400596f2` | `7405` #5 | **piste** (dernière piste) → 7 |
| `0x4005873a` | `7006` #6 | **non** : `cmp.l (a2),d0` — **étiquette de type** d'objet → inchangé |
| `0x4005856a` | `7006` #6 | **non** : valeur rangée dans un objet neuf (même étiquette) → inchangé |
| `0x40059668` | `7205` #5 | **non** : valeur écrite dans un **registre matériel** (`0xfc04c07f`) → inchangé |
| `0x400588f2` | `7205` #5 | **piste** : garde `si (piste > 5) sortir`, puis ligne retrig `0x40a78d58 + piste×0x1c` → 7 |
| `0x40058c2a` | `7205` #5 | **piste** : garde, puis zone événements via `+0x77` / `+0x7d` → 7 |
| `0x400595f2` | `7006` #6 | **piste** : boucle de 6 copies par piste (vers `0x800015a0`) → 8 |
| `0x40058ace`, `0x40058b0a` | `7205` #5 | **non** : valeurs de champ d'objets dans une **séquence d'auto-test** (magies `0x12345678`, `0x12345679`, `0x89000000`, `0x78000000`) → inchangé |
| `0x40058b22` | `7207` #7 | **non** : même séquence d'auto-test → inchangé |

Bilan des **16 bornes candidates** (13 lignes) : **10 sont des comptes de pistes** (à porter à 8, ou 7
pour les gardes « dernière piste ») et **6 sont des valeurs étrangères** (étiquette de type, champ
d'objet, registre matériel, valeurs d'auto-test) qu'il ne faut **pas** toucher.

#### e) Le trou du census : les tableaux atteints par décalage calculé

Le census des littéraux ne peut voir qu'un tableau **dont l'adresse de base est écrite en clair**. Or
le code atteint aussi des tableaux par `addi.l #$NN, dN` (NN = piste + constante) suivi de
`(aN, dN.l*4)` : l'adresse n'apparaît alors **nulle part**. Un balayage systématique des immediats
(`probe_offsets.py`, `probe_offsets2.py`) sur chaque base de ligne montre que **seule la zone
« événements » utilise ce motif** ; la famille `0x77…0x93` y désigne six tableaux par piste (§3.8.b).
La méthode naïve produit beaucoup de faux positifs (un même `addi` peut alimenter n'importe quelle
base) : le signal fiable est le **groupe d'immediats contigus** utilisés avec *cette* base.

Conséquence pour la suite : le générateur devra réécrire ces cinq immediats **et** vérifier, pour
chaque ligne, qu'aucun tableau n'est atteint par un motif de ce genre (les autres lignes n'en ont pas
d'après ce balayage).

#### f) Bornes des lignes simples — octets exacts

| Ligne | Site | Origine | Remplacement |
|---|---|---|---|
| boucle maîtresse des voix | `0x400a7e40` | `7006` `moveq #$6,d0` | `7008` (8) |
| parcours params (a) | `0x40056f92` | `0c810000018c` `cmpi.l #$18c,d1` | `0c8100000210` (8 × 0x42) |
| parcours params (b) | `0x400584ea` | `0c800000018c` `cmpi.l #$18c,d0` | `0c8000000210` |
| parcours tampons de travail | `0x4005978c` | `0c8200000120` `cmpi.l #$120,d2` | `0c8200000180` (8 × 0x30) |

- La boucle maîtresse (`0x400a7d4a`) est **le** point de commande : `moveq #$6,d0` en `0x400a7e40`,
  puis les pointeurs avancent (`a5/a6/a3/a4 += 0x31c` états, `a2 += 0x42` params, `d3 += 0x80`
  sorties) et `cmp.l d2,d0 / bne.w` referme. Une seule instruction porte les huit pistes.
- Les deux `cmpi #0x18c` (396 = 6 × 66) sont les deux parcours de la ligne **params** ; `cmpi #0x120`
  (288 = 6 × 48) est le parcours des **tampons de travail** (il range `0x8000bd98 + d2` dans
  `-$31c(a2)`, le champ pointeur de l'état de voix).

**Décoys de la boucle des voix** : les gardes `moveq #$5` en `0x400a7dba`, `0x400a7dc0` et
`0x400a7df4` ne comptent **pas** les pistes. L'index comparé (`d4`) est **lu dans l'état de voix**
(`move.l (a6),d4`), pas dans le compteur de piste (`d2`) : c'est l'indice de **machine**. Les tables
visées (`0x40118610`, `0x40118628`, `0x40118640`) ont **6 entrées** (trois blocs de 0x18 : deux
tables de pointeurs de fonction, une suite d'octets `00 01 02 03 04 05`) — six machines, pas six
pistes. Inchangées.
`[À VÉRIFIER au banc]` C'est le seul « ne pas toucher » à risque : si l'index était en fait la
piste, les pistes 7-8 ne recevraient **aucun** appel de machine (silencieuses). Contrôle simple :
compter les appels de `table[d4]` par piste dans le banc — un appel par piste avec `d4` = piste ⇒
c'est la piste ; `d4` variant indépendamment ⇒ c'est la machine.

### 3.9 Conséquences du trou du census (pourquoi cette trouvaille compte)

Le trou du §3.8.e n'est pas une curiosité : c'est un défaut de **méthode**, et il a trois
conséquences concrètes.

1. **Le plan aurait produit une machine subtilement fausse.** Construit sur quatre tableaux au lieu
   de six : les deux tableaux invisibles restent à 6 logements alors que le code en écrit 8 → la
   piste 7 écrit dans le **premier logement de la piste 8** (une piste écrase l'autre), et toute la
   nouvelle disposition est dimensionnée autour d'une forme incomplète, donc décalée. Aucun plantage :
   le symptôme est « la piste 7 fait parfois dérailler la piste 8 » — le genre de bug qui coûte des
   jours sur la machine.
2. **Les preuves prévues ne l'auraient pas attrapé.** Le banc `0xFF` teste *lecture avant écriture* ;
   la comparaison « pistes 0-5 identiques au stock » ne couvre pas les pistes neuves. Ce défaut est
   une **écriture sur écriture** entre deux pistes neuves : il passe les deux contrôles. D'où deux
   contrôles neufs (§3.6, points 6 et 7).
3. **Le travail et le budget changent un peu** : la zone se reconstruit sur **six** tableaux (≈ +0x30
   octets), cinq immediats de plus à recalculer, et un cas de plus pour le banc.

**Le gain** : la méthode a été refaite pour **toutes** les lignes avec un balayage capable de
détecter ce contre-exemple. « Aucun tableau n'est atteint autrement que par base + pas » est
maintenant **prouvé** pour chaque ligne, au lieu d'être supposé à partir de celles qu'on avait
regardées. C'est exactement ce que veut dire « census durci » — et c'est pourquoi cette étape vient
**avant** la première écriture.

### 3.10 Correction des accueils : **tout en DDR** `[FAIT]` (13/10)

Le census des accueils a été refait (`build/re8/probe_homes.py`, `probe_sramgaps.py`) et il
**invalide** le choix SRAM des §3.1/§5.

- La **couture SRAM** `0x800074c0..0x80008000` n'a que **~550 o** libres (`0x800074c0..0x800076da`) :
  à partir de `0x800076da` le stock y pointe déjà — 12 littéraux, dont un **tableau de trois
  pointeurs** en `0x4010b304` (`0x80007e53`, `0x80007a82`, `0x800076da`). Elle n'est de plus **pas
  recopiée** au démarrage : son contenu initial est indéfini. Elle ne peut donc recevoir que de
  petites choses, et seulement avec un nettoyage au démarrage.
- La **queue SRAM** `0x8000f2e8..0x80010000` est encore plus dense (99 littéraux).
- Le SRAM entier est plein : sur les 927 adresses SRAM référencées, le plus grand trou sans littéral
  fait **962 o** — et la seule ligne des **tampons de sortie** en demande **1024**. Aucune ligne ne
  peut donc rester en SRAM.
- **Conclusion** : toutes les lignes relogées vont dans la **fenêtre DDR** `0x4230dc10..0x4232d1a8`
  (128 Ko, **aucun** littéral, dans le BSS **remis à zéro** au démarrage). Bénéfice inattendu : le
  contenu initial est nul, donc **aucun stub de nettoyage n'est nécessaire** (§3.6 point 4 tombe —
  les cinq lignes SRAM sont d'ailleurs **toutes à zéro dans l'image**, vérifié).
- **Conséquence à mesurer** : les lignes chaudes (params, tampons de sortie, tampons de travail)
  quittent le SRAM rapide pour la DDR. Les états de voix, eux, y sont **déjà** dans le stock : l'accès
  DDR n'est donc pas anormal pour ce moteur, mais le coût des lignes chaudes doit être remesuré.
- **Méthode** : le générateur n'accepte un site de littéral que s'il est **l'opérande d'une
  instruction** (désassemblé) — les coïncidences d'octets des tables de données (dont le census en
  avait relevé plusieurs) sont rejetées et comptées.

### 3.11 Le banc du jalon 1 `[FAIT]` (13/10)

`tools/re/test_groove.py` : Unicorn, le **vrai code de l'OS**, image stock contre image groove.

| Contrôle | Résultat |
|---|---|
| A. littéraux relogés (179 écritures, 712 octets) | ok |
| B. pistes 0-5 **octet pour octet identiques** au stock (1 note trk 0 ; 6 notes) | ok |
| C. les pistes **6 et 7 jouent** | ok (704 valeurs non nulles chacune) |
| D. pistes 6-7 **muettes** sans trig | ok (0 valeur) |
| E. **isolement** : 6 seule vs 6+7 (idem 7) | ok — aucun recouvrement entre les pistes neuves |
| F. banc **`0xFF` vs `0`**, accueil par accueil | ok sur les 8 accueils |
| G. **appels de machine par piste** | 24 par piste (0-7) ; index comparé `d4` = 4 |
| H. **lignes de cache de 16 o** (6 blocs) | code +0, DDR data **+194**, SRAM **−70** (§3.11.H) |

- **F, subtilité qui a failli tromper** : la première version comparait **tous** les blocs de sortie,
  y compris ceux des pistes non rendues — qui gardent la valeur de remplissage (`0xFF` vs `0`) et
  font donc échouer le banc **à tort**. La comparaison juste porte sur les pistes **actives**. Le banc
  remplit maintenant **un accueil à la fois** et exige le même signal : chacun des huit accueils passe.
- **G tranche le §3.8.f** : l'index comparé aux tables de six est `d4` = 4, c'est-à-dire l'index de
  **machine**, pas la piste — les gardes `moveq #$5` de la boucle des voix sont bien des bornes de
  machine, inchangées.
- **Limite assumée** : l'ISR complet ne s'émule pas (notes/27 §3.4) ; les lignes que la boucle des
  voix ne touche pas (params, retrig, zone, cluster) ne sont donc **pas** couvertes par F — c'est
  l'objet de la liste machine (§3.6 point 5).

#### H. Le coût mémoire du relogement, mesuré `[FAIT]` (14/10)

L'émulateur **ne chronomètre pas** les défauts de cache (notes/23 §4) : la mesure du dépôt est le
nombre de **lignes de cache de 16 o distinctes** touchées pendant des blocs (notes/23 §4, notes/27 §3).

| Scénario (6 blocs, 1 note par piste) | code | données DDR | SRAM | autre |
|---|---|---|---|---|
| stock : 6 voix | 12 | 311 | 211 | 16 |
| groove : 8 voix | 12 | **505** | **141** | 16 |
| delta | **+0** | **+194** | **−70** | 0 |

Lecture : le code ne bouge pas (+0 — les patchs ne coûtent aucune ligne). Les **+194 lignes DDR**
se décomposent en **~106 lignes pour les deux voix de plus** (inévitables : c'est le but du mod) et
**~90 lignes déplacées de la SRAM vers la DDR** (tampons de sortie, tampons de travail, pmod) — les
−70 lignes SRAM. Ces ~90 lignes passent d'un accès SRAM à **un cycle** à un accès DDR **en cache
copyback**. À retenir : les **états de voix** (la ligne la plus lue du moteur) sont **déjà en DDR**
dans le stock — la DDR n'est donc pas un mode d'accès nouveau pour cette boucle. Le temps réel, lui,
se mesure sur la machine (notes/23 §4) : c'est le seul point que ce banc ne peut pas trancher.

### 3.12 Reconnaissance du mixeur `[FAIT — à poursuivre]` (14/10)

Le mixeur n'est pas « six appels écrits à la main » comme le disait la note 54 §2.4 : le chemin audio
appelle **deux fonctions** en leur passant la **ligne des tampons de sortie** comme argument, et le
compte des pistes est **à l'intérieur** d'elles.

- `0x40059818` : `pea.l $80001858.l` → `jsr 0x400a7d4a` — la **boucle des voix** (déjà portée à 8,
  §3.8.f) reçoit la ligne en argument ;
- `0x40059824` : `pea.l $80001858.l` → `jsr 0x40056d9c` — le **mixeur** reçoit la même ligne ;
- `0x40056d9c` : boucle interne de **8** tours (`d5 = 0x20`, pas de 4 → 8 × 4 = les 32 trames du bloc),
  boucle externe sur les entrées du cluster (`a2` de `0x40fe4c90` jusqu'à `0x40fe4c9c`, soit 3 tours —
  L / R / multi ?). Le mixeur semble donc **déjà générique** sur la ligne ; c'est le **masque/bornes**
  internes qui fixent le nombre de pistes, pas six appels.
- **Trouvaille au passage** : un **second groupe déroulé de six** (comme celui de la zone événements,
  §3.8.a) dans le chemin audio, `0x400597ea..0x40059806` : `move.w d0,$32(a2)` puis `+0x42` six fois
  (les **params** des 6 pistes), suivi de **deux champs isolés** (`$1b0(a2)`, `$1ae(a2)`). Huit pistes
  demandent **deux magasins de plus** (`$1be(a2)`, `$200(a2)`) — donc **du code neuf**, à loger.
- **Prochaine étape du mixeur** : désassembler `0x40056d9c` **avec les EMAC** (`mcfw.emac_disasm`, que
  capstone ne sait pas lire) pour trouver le masque/les bornes internes, et traiter le groupe déroulé
  des params comme celui de la zone événements.

### 3.13 Le mixeur est **déjà** à 8 : sa borne est le tableau de mots du cluster `[FAIT]` (14/10)

Le désassemblage **avec les EMAC** (`mcfw.emac_disasm`, objdump `m68k:isa-c:emac`) rend lisible
`0x40056d9c`, dont capstone ne montrait que des `dc.w`. Le résultat change la taille du jalon 2 :

```
40056da4  lea 0x40fe4c90,%a2              ; a2 = tableau de mots du cluster
40056db8  mvsw %a2@+,%d4                  ; un mot par piste, a2 += 2
40056dca  msacl %d4,%a1,%a0@+,%a1,%acc0   ; le mélange : 4 EMAC par tour
40056dce  msacl … %acc1
40056dd2  msacl … %acc2
40056dd6  msacl … %acc3
40056de2  moveml %d0-%d3,%a0@(-20)
40056de8  subql #4,%d5                    ; 32/4 = 8 tours internes (les 32 trames du bloc)
40056dea  bgts 0x40056dca
40056dec  cmpal #0x40fe4c9c,%a2           ; ← LA borne des pistes : fin du tableau de mots
40056df2  bnes 0x40056db8
```

- La boucle **externe** avance `a2` de 2 en 2 dans le tableau de mots du cluster (`0x40fe4c90`,
  6 mots) et s'arrête sur une **comparaison à une fin absolue** (`0x40fe4c9c`) — exactement le motif
  de la zone événements (§3.8.a).
- Or le générateur **réécrit déjà** ces deux littéraux (`0x40056da6` → nouveau cluster,
  `0x40056dee` → nouveau cluster + 0x10) et **élargit** le tableau de 12 à 16 o (6 → 8 mots).
  **La boucle du mixeur tourne donc déjà huit fois** : la part « mixeur » du jalon 2 est faite par le
  relogement du cluster, **pas** par des appels écrits à la main — correction de notes/54 §2.4.
- Idem pour la seconde fonction (`0x40056e24`, `lea 0x40fe4cdc,%a2`) : tableau de mots élargi et
  littéral réécrit.

#### Un trou de balayage, trouvé au passage

Le premier balayage des bornes allait de `0x40058300` à `0x40059a00` : **il excluait la région du
mixeur** (`0x40056000..0x40058300`). Refait (`build/re8/probe_bounds_audio.py`) et trié
(`probe_triage.py`, avec les EMAC) :

| Site | Valeur | Verdict |
|---|---|---|
| `0x40056e90` | `7206` #6 | **piste** : boucle du tableau de mots du cluster → 8 — **ajouté au générateur** |
| `0x400564cc` | `7606` #6 | **à trier** : boucle à pas de **12 o** (une structure par piste de 12 o ?) — probablement à porter à 8 |
| `0x4005617c` | `7205` #5 | **à trier** : garde `assert(d0 <= 5)` sur un octet (piste ou machine ?) |
| `0x400561ca` | `7e06` #6 | **non** : `d0` est un **octet de donnée** du pattern (clampé à 6, sinon 2) → valeur |
| `0x40056040` | `7005` #5 | **non** : valeur rangée dans un global (`0x40a78924`) |
| `0x400a7bfa` | `7205` #5 | **non** : valeur rangée dans l'état de voix (`+664`) |
| `0x4005649e`, `0x400581fc`, `0x40056dba`, `0x4005691a`, `0x40057204`, `0x40057248` | #0x18 / #0xc | **non** : décalages (`asr`/`lsl`/`lsr`), pas des comptes |

**Deux sites restent à trancher** (`0x400564cc`, `0x4005617c`), plus le reste de l'OS (interface,
séquenceur, format de pattern) qui n'est pas encore balayé.

### 3.14 Tri des deux bornes : la garde est une piste, et une **famille par piste inconnue** `[FAIT]` (14/10)

#### a) `0x4005617c` : c'est bien un index de **piste** → 7

```
40056182  movel %sp@(48),%d2        ; arg1
4005618a  mvzb %d2,%d0
4005618c  cmpl %d0,%d1              ; d1 = 5
4005618e  bccs 0x40056192
40056190  illegal                   ; assert(index <= 5) : sinon, plantage
...
400561b2  movel #722,%d0            ; 722 = le pas du pattern par piste (notes/54 §2.3)
400561b8  mulsl %d2,%d0             ; d0 = piste x 722
400561bc  lea %a0@(0,%d0:l),%a1     ; a1 = base + piste x 722
```

`d2` est multiplié par **722** : c'est l'**index de piste**, et la garde exige `≤ 5`. Elle est appelée
depuis le **chemin MIDI/note** (`0x40081598`, `0x400818b6`). Pour huit pistes, elle doit passer à
**7**, sinon la piste 7 ou 8 **plante** (`illegal`).

#### b) Une famille par piste que le census n'avait pas vue

La même fonction indexe des tableaux en `0x422ff1xx` (SDRAM, dans le BSS remis à zéro) :

| Adresse | Ce que le code en fait | Sites |
|---|---|---|
| `0x422ff174` | tableau d'**octets indexé par piste** (pas 1 : `mvsb %a1@(0,%d2:l)`) | `0x40054490`, `0x4005538e`, `0x400561de` |
| `0x422ff17c` | tableau de **pointeurs indexé par piste** (pas 4 : `%a3@(0,%d6:l:4)`, `d6 = piste + 5`) | `0x40054416`, `0x40055394` |
| `0x422ff168`, `0x422ff16c`, `0x422ff16e`, `0x422ff194` | champs voisins, mêmes appelants | 3, 1, 3, 3 |
| `0x422ff1ac` | un long (soustraction : `subl 0x422ff1ac,%d0`) | `0x4005463a`, `0x400553f2`, `0x400561fc` |

- Le tableau de pointeurs `0x422ff17c` (6 entrées) **finit exactement** sur `0x422ff194` (qui a 3
  sites) : l'élargir à 8 entrées **déborderait** sur le champ suivant — il faut donc **reloger la
  famille**, comme les autres lignes.
- **Conséquence sur le jalon 1** : le banc ne couvre que la boucle des voix, donc il ne voit pas ce
  chemin. Aujourd'hui, si une piste 7 ou 8 passe par le chemin MIDI/note, elle **plante** sur l'assert
  et, même au-delà, écrirait hors des tableaux. **La garde et le relogement de la famille doivent être
  faits ensemble** : le jalon 1 n'est donc **pas encore sûr pour le chemin MIDI/note**.
- Le census avait cherché des **lignes** déjà identifiées ; cette famille est dans une autre zone de
  la SDRAM (`0x422ff1xx`, sous les états de voix). Leçon : après les balayages systématiques, il faut
  encore **suivre les gardes** — c'est une garde qui a mené ici.

#### c) `0x400564cc` : toujours à trancher

Boucle de 6 tours (`%d6`), pas de **12 o** (`lea %a0@(12),%a0`) dans une grosse fonction de rendu de
voix (EMAC), atteinte par des adresses **calculées** (aucune référence littérale à `0x40056320`). Le
pas de 12 o ressemble à une structure par piste (12 o = 6 mots), mais la base n'est pas encore
identifiée. **À trancher au prochain passage.**

### 3.15 La famille `0x422ff1xx` cartographiée `[FAIT]` (14/10)

La garde du §3.14.a a mené à une famille par piste en SDRAM. Cartographie par désassemblage de
**chaque** site d'usage (`build/re8/probe_family_map.py`, avec les EMAC) :

| Adresse | Nature | Pas | Preuve |
|---|---|---|---|
| `0x422ff158` | **champ simple** (un pointeur sauvegardé puis relu) | — | `movel 0x422ff158,%d1` / `movel %a2,0x422ff158` |
| `0x422ff15c` | **masque 32 bits** | — | `orl %d1,0x422ff15c` avec `%d1 = 1 << n` |
| `0x422ff160` | **champ simple** (compteur lu d'un registre matériel `0xfc094014`) | — | `movel %d0,0x422ff160` |
| `0x422ff164` | **champ simple** (registre `0xfc094016`) | — | `movel %d0,0x422ff164` |
| `0x422ff168` | **tableau d'octets par piste** | 1 | `moveb %d3,%fp@(0,%d0:l)` |
| `0x422ff16e` | **tableau d'octets par piste** | 1 | `moveb %a0@+,%fp@(0,%d0:l)` (`0x422ff16c` n'est que `a1@(2,%d2:l)`) |
| `0x422ff174` | **tableau d'octets par piste** | 1 | `mvsb %a1@(0,%d2:l),%d3` |
| `0x422ff17c` | **table de pointeurs par piste** | 4 | `%a3@(0,%d6:l:4)` avec `d6 = piste + 5` : la table commence bien à `0x422ff17c` |
| `0x422ff194` | **structure suivante** (juste après la table) | ? | `lea 0x422ff194,%a4` — **pas encore décodée** |
| `0x422ff1ac` | **champ simple** | — | `movel %a0@,0x422ff1ac` |

Disposition déduite des bases :

```
0x422ff168  octets[6]  (6 o)   ┐
0x422ff16e  octets[6]  (6 o)   ├ trois tableaux d'octets PACKÉS (bases à 6 o d'écart)
0x422ff174  octets[6]  (6 o)   ┘ -> fin 0x422ff17a
0x422ff17a  2 o non référencés
0x422ff17c  pointeurs[6] (24 o)  -> fin 0x422ff194   <- finit EXACTEMENT sur la structure suivante
```

- **Les trois tableaux d'octets sont collés** : les élargir à 8 o ferait **déborder** l'un sur l'autre.
  La table de pointeurs **finit exactement** sur `0x422ff194`. → la famille doit être **relogée en
  bloc** `[0x422ff168, 0x422ff194)` (0x2C o), reconstruite à 8 logements (octets[8] ×3 puis
  pointeurs[8], alignés) et ses **quatre littéraux** réécrits — même méthode que le cluster (§3.8.c).
- **Bornes dans les fonctions de la famille** : `0x4005449e` `7206` #6 **confirmé** (la boucle qui
  écrit les trois tableaux d'octets : `cmpl %d0,%d1` en `0x400544b0`) ; `0x4005617c` `7205` #5
  **confirmé** (la garde, §3.14.a) ; `0x400561ca` `7e06` #6 **non** (valeur de donnée, §3.13).
  **À trier** : `0x4005478e` #5, `0x40055372` #6, `0x400553e2` #6, `0x4005544e` #6.
- **Pas encore décodée** : `0x422ff194` (la structure juste après la table de pointeurs, peut-être
  par piste elle aussi) — à décoder avant de figer le relogement.

**Donc** : la famille est cartographiée, mais son traitement demande encore **quatre bornes triées** et
`0x422ff194` décodée. Comme pour la garde, on ne fait pas la moitié : **le relogement, les bornes et la
garde partiront ensemble.**

### 3.16 Tri terminé : la famille est relogée `[FAIT]` (14/10)

| Site | Valeur | Verdict |
|---|---|---|
| `0x40055372` | `7006` #6 | **piste** : `%fp += 722` (pas du pattern) à chaque tour → 8 |
| `0x400553e2` | `7c06` #6 | **piste** : boucle qui écrit les tableaux d'octets (`%a1@(0,%d0:l)`) → 8 |
| `0x4005449e` | `7206` #6 | **piste** : boucle des trois tableaux d'octets → 8 |
| `0x4005617c` | `7205` #5 | **piste** : la garde `assert(index ≤ 5)`, index = piste (× 722) → 7 |
| `0x4005544e` | `7406` #6 | **non** : `d2` est une **valeur par défaut** posée dans une branche (table `0x4010afa4` indexée par la machine) |
| `0x422ff194` | — | **tableau de longs par piste** (`moveal %d7,%a1` / `addql #4,%d7` / `movel %d4,%a1@+`) : 24 o (6 × 4), **fin `0x422ff1ac`** |
| `0x400564cc` | `7606` #6 | base **`0x40fe4cd0`** (2ᵉ tableau de mots du cluster), pas de **12 o**, 6 tours — la structure de l'enregistrement n'est **pas identifiée** |
| `0x4005478e` | `7205` #5 | **accesseur** `index → octet` (tableau `0x40a7886c`, valeur par défaut au-delà de 5), appelé depuis `0x4006a9b4` — **piste ou machine ?** non tranché |

**Implémenté (jalon 1)** : les **quatre bornes** de la famille et le **relogement du bloc**
`[0x422ff168, 0x422ff1ac)` (0x44 o) — trois tableaux d'octets, une table de pointeurs et un tableau
de longs, reconstruits à 8 logements. `0x422ff194` a **étendu le bloc** : il est lui aussi par piste.
Le champ simple suivant (`0x422ff1ac`) ne bouge pas. Total : 179 écritures, 712 octets.

**Reste hors du jalon 1, et pourquoi** :

- `0x400564cc` : la structure de l'enregistrement de 12 o n'est pas identifiée — toucher la borne
  sans savoir ce qu'elle parcourt serait hasardeux ;
- `0x4005478e` : un accesseur **avec valeur par défaut** hors bornes — au pire une **valeur fausse**
  pour les pistes 7-8 (pas de corruption), mais il faut d'abord trancher piste/machine.

### 3.17 Les deux derniers points `[FAIT]` (14/10)

#### a) `0x4005478e` : l'index **est** la piste → seconde famille, relogée

L'appelant `0x4006a9a0` :

```
4006a9ae  clrl %d2
4006a9b2  lea 0x4005478e,%a3
4006a9b8  movel %d2,%sp@-          ; l'index passé à l'accesseur est d2
4006a9ba  jsr %a3@
4006a9be  cmpl %a2@(72),%d0        ; comparé au champ +72 de l'enregistrement
4006a9c6  movel %d0,%a2@(72)
4006a9ca  addql #1,%d2
4006a9cc  addql #4,%a2             ; a2 avance de 4 o par tour -> une piste par tour
4006a9ce  moveq #6,%d0             ; borne : 6 -> 8
```

Donc : la garde de l'accesseur (`0x4005478e` `7205` → `7207`), la boucle appelante
(`0x4006a9ce` `7006` → `7008`), et le tableau d'octets indexé par piste (`0x40a7886c`) à porter à
8 logements. Or il est **collé** à ses voisins, et l'accesseur voisin (`0x4005470e`) **efface**
`0x40a78848` jusqu'à `0x40a78860` par **comparaison absolue** : c'est un tableau de **longs par
piste**. La zone est donc une seconde famille par piste, `[0x40a78848, 0x40a78872)` (0x2A o) :

```
0x40a78848  longs[6]   (24 o)   <- effacé jusqu'à 0x40a78860 (comparaison absolue)
0x40a78860  octets[6]  (6 o)    ┐
0x40a78866  octets[6]  (6 o)    ├ trois tableaux d'octets PACKÉS
0x40a7886c  octets[6]  (6 o)    ┘ -> fin 0x40a78872
```

**Relogée en bloc** à 8 logements (0x38 o) — longs[8] puis octets[8] ×3 — avec ses **quatre
littéraux** (27 sites), la garde et la borne. Le champ simple suivant (`0x40a78872`) ne bouge pas.

#### b) `0x400564cc` : **non tranché — et on n'y touche pas**

La fonction (`0x400562fc`) n'a **aucune référence littérale** : elle est atteinte par une adresse
**calculée** (table de pointeurs), son appelant reste donc inconnu. Deux lectures **incompatibles** :

- le **rendu** (`0x400564cc`) : `a0` part de `0x40fe4cd0` et avance de **12 o** par tour, et `d6`
  indexe un tampon de **128 o** (`lsll #7`) — 128 = la taille d'un tampon de sortie, ce qui suggère
  que `d6` est la piste ;
- l'**ISR** (`0x40059130`) : `move.w %d0,(%a0,%d2:l*2)` avec `a0 = 0x40fe4cd0` / `0x40fe4cdc` et
  `d2` = **piste** (vérifié : `addi.l #$93,%d0` désigne la zone événements) → **deux tableaux de mots
  de 12 o indexés par piste** (pas 2).

Les deux ne peuvent pas décrire le même octet : soit la zone est réutilisée (union), soit l'un des
deux index n'est pas la piste. **Trancher demande une trace à l'exécution** (émuler la fonction de
rendu et comparer `d6` aux tampons de sortie) — hors de portée du banc actuel, qui ne couvre que la
boucle des voix. **Décision : on ne touche ni la borne `0x400564cc` ni la lecture « enregistrements
de 12 o » du cluster** — se tromper ici casserait le tableau de mots du mixeur, dont dépend le
mélange (déjà vérifié à 8). C'est le **seul point laissé ouvert**, et il est **sans risque
immédiat** : la borne reste à 6, le rendu traite donc 6 éléments, comme le stock.

### 3.18 La table des descripteurs est par **machine**, pas par piste `[FAIT]` (14/10)

`build/re8/probe_descs.py` (`--desc`) décode `0x4010dce0` : 76 entrées de `0x38` o, **14 mots
longs** chacune. Une entrée :

| Champ | Où | Exemple (entrée 46) |
|---|---|---|
| index (0..5) | mot long 0, moitié basse | `0` |
| identifiant d'encodeur (0x0b..0x0e) | mot long 1, moitié basse | `0x0b` |
| **index d'encodeur** (0x10..0x13) | mot long 6, moitié **haute** | `0x10` |
| **nom** du paramètre | mot long 11 | `0x4012999c` |
| **groupe** | mot long 12 | `0x4012996f` |
| **nom court** | mot long 13 | `0x401299a7` |

Et les chaînes visées le disent : `Drum`, `ALG`, `Pitch`, `PTCH`, `FTUN`, `Punch`, `PAW`, `Gate`,
`GATE`, **`Kick Color`**, `COLR`, **`Kick Shape`**, `SHPE`, **`Kick Sweep`**, `SWEP`,
**`Kick Contour`**, `CONT`, **`Snare Color`**, **`Snare Shape`**, **`Snare Sweep`**,
**`Snare Contour`**, **`Metal …`**, **`Perc …`**, **`Tone …`**, **`Chord …`**.

- L'index 0..5 est donc l'index de **machine** (KICK, SNARE, METAL, PERC, TONE, CHORD), pas de piste :
  les six groupes de 4 entrées (encodeurs `0x0b..0x0e`) portent les noms **propres à chaque
  machine**, suivis d'une entrée séparatrice (`idx 0x0007`, `+0x18 = 0x50`). C'est la **correction de
  notes/54 §2.5**, qui lisait « par piste » (l'index croît de la même façon dans les deux cas, d'où
  la confusion — ce sont les chaînes qui tranchent).
- **Conséquence : la table des descripteurs ne demande AUCUN changement pour huit pistes.** Les
  machines ne changent pas ; l'interface lit `(machine de la piste, encodeur)`. Le poste
  « + 10 entrées de descripteurs » du jalon 2 **tombe**.
- Note de méthode : c'est exactement le genre d'erreur que le projet redoute — un index qui croît
  mécaniquement ressemble à un compte de pistes. Ici, seule la **lecture des chaînes** a tranché.

Au passage, la plus longue plage de zéros de l'image (`0x40000400..0x4019b590`) fait **2 837 octets à
`0x4019a4ec`** — candidate pour loger de la donnée neuve (à vérifier par les mêmes balayages que les
autres accueils avant tout usage).

### 3.19 Le pattern : premiers relevés `[EN COURS]` (14/10)

**Les constantes** (`build/re8/probe_pattern.py`) :

- pas par piste **722** : en clair à `0x4000c5a8`, `0x4000c618`, `0x4000cfb8`, `0x4000d154`,
  `0x4000d1a2`, et dans la zone des **accesseurs de champ** `0x400173bb`, `0x4001829e`,
  `0x40018864`, `0x40018d02`, `0x40019136`, `0x400192ee`, `0x40019418` ;
- taille de pattern **30710** : `0x4000eaa6`, `0x4000ec92`, `0x4000feb0`, `0x4000ffd4`, `0x4002017e`,
  `0x400203ac`, `0x4005d2dc`, `0x4005d4f8`, `0x4008152c`, … ;
- base mémoire **0x406fa040** : `0x400083ca`, `0x4002018c`, `0x400203b6`, `0x40055e08`, `0x40081536`,
  `0x4008178a`.

**La copie A→B (`0x4005b4ec`) est une traduction champ à champ écrite à la main :**

```
4005b50e  moveb %a3@(128),%a2@(580)     ; A+128 -> B+580
4005b526  movew %a4@,%a0@(0,%d0:l)      ; une copie indexée par d0
4005b52a  addql #2,%d0
4005b52c  moveb %a3@(191),%a2@(128)
4005b53e  moveb %a3@(511),%a2@(320)
4005b552  cmpil #128,%d0                 ; 64 tours de 2 : les 64 pas du pattern
4005b558  bnes 0x4005b50e
```

Par tour : **1 mot** (le pas) + **8 octets** à décalages figés. Côté B, **six** de ces octets sont
consécutifs à pas de **64** (`128, 192, 256, 320, 384, 448`) — la signature des **6 pistes** ; côté A
ils sont à `191 + 64k`. Les deux formes (fichier et mémoire) ont donc des **décalages différents**, et
la traduction est manuelle : deux pistes de plus demandent **deux champs de plus dans la copie**, pas
seulement un compteur.

**Les bornes candidates** (`probe_pattern2.py`) : le séquenceur en contient **~24** (`#5`/`#6`) —
`0x4000cb2c`, `0x4000cb72`, `0x4000cb78`, `0x4000cd2e`, `0x4000cfd6`, `0x4000cfdc`, `0x4000d02c`,
`0x4000d032`, `0x4000d094`, `0x4000d09a`, `0x4000d5f0`, `0x4000d728`, `0x4000ef6e`, `0x4000f174`,
`0x4000f280`, `0x4000f286`, `0x4000f5a0`, `0x4000f5f2`, `0x4000fd7c`, `0x4000fe7c`, `0x4000ff66`,
`0x4001006c`, `0x40020a42`, `0x40020dce` (dont un `#7`).

**Échelle, honnêtement** : c'est le sous-chantier le plus lourd du projet — ~24 bornes à trier **une
par une** (la méthode a montré que ~40 % des candidates sont des valeurs étrangères), les champs de
copie A↔B à étendre, le format fichier, et la conversion des projets existants. À mener **par lots**,
comme le reste : triage → extensions → preuve. Le prochain lot utile est le triage de ces 24 bornes.

### 3.20 Le compte de pistes du pattern est **4332 = 6 × 722** `[FAIT]` (14/10)

Le pas de piste 722 est utilisé pour calculer les pointeurs par piste, et les boucles sont bornées
par une **constante**, pas par un « 6 » :

```
4000c5a6  addil #722,%d3
4000c5ac  lea %a3@(88),%a3
4000c5b4  cmpil #4332,%d3        ; 4332 = 6 x 722 : fin du bloc des six pistes
4000c5ba  bnes 0x4000c59a
```

Balayage (`probe_pattern5.py`) :

| Constante | Sens | Sites |
|---|---|---|
| **4332** | 6 × 722, fin du bloc des pistes | **21 longs** : `0x4000c5b6`, `0x4000c626`, `0x4000cfc0`, `0x4000d15a`, `0x4000d1a8`, `0x4005433a`, `0x400545f6`, `0x40054b56`, `0x40054da2`, `0x40054e5c`, `0x40054e98`, `0x40054fc8`, `0x40055062`, `0x4005b91e`, `0x4005b92c`, `0x4005ba66`, `0x4005bfb0`, `0x4005c2a2`, `0x4006160c`, `0x4006163e`, `0x40061646` (+ un mot à `0x4004af9c`) |
| **4336** | 4332 + 4 (bloc + un en-tête ?) | 2 longs (`0x4000c5be`, `0x40112945`) + mots |
| **30710** | taille d'un pattern | 12 longs (`0x4000eaa6`…`0x400819c4`) + mots |
| **5776** = 8 × 722 | — | **aucun** (le mod doit l'introduire) |

- **Le bloc des pistes d'un pattern fait donc 4332 o, écrit en clair à 21 endroits**, dont la zone
  **audio** (`0x40054xxx`) : le moteur lit aussi les pas du pattern courant. Pour huit pistes :
  **4332 → 5776**, `4336 → 5780`, et la taille de pattern **30710 → 32154** (30710 + 2 × 722).
- Le nombre de pistes du pattern **n'est donc pas dispersé en « 24 bornes »** : c'est **une classe de
  constantes**, comme les pas de ligne du moteur (§3.4). C'est une bien meilleure nouvelle que le
  premier relevé ne le laissait croire.
- **Ce qui reste à trancher** : chaque site est-il un pas, une comparaison ou une taille ? (les 21
  longs semblent être des comparaisons de fin de bloc) ; et surtout **la forme fichier** — la même
  constante 4332 y apparaît (`0x4005b91e`, `0x4005b92c`, `0x4005ba66`, `0x4005bfb0`, `0x4005c2a2`),
  donc la conversion et la compatibilité des projets se jouent là. Le **30710** est la taille du
  pattern en mémoire ; reste à voir si la forme fichier a la sienne.

### 3.21 Tri des 33 sites du pattern : tout est à changer, sauf une coïncidence `[FAIT]` (14/10)

`build/re8/probe_pattern6.py` donne, pour chaque site, **l'instruction qui le porte** :

| Constante | Instruction | Nb | Verdict |
|---|---|---|---|
| **4332** | `cmpil #4332,%dN` (fin de bloc) | 17 | **à changer** → 5776 |
| **4332** | `addil #4332,%dN` (pas) | 4 | **à changer** → 5776 |
| **4332** | `pea 0x40a710ec` | 1 | **coïncidence** : la valeur `0x10ec` = 4332 est la moitié basse d'un **pointeur** → **ne pas toucher** |
| **4336** | `addil #4336,%d2` | 1 | **à changer** → 5780 |
| **30710** | `movel #30710,%dN` / `pea 0x77f6` / `addil` / `lea %aN@(30710)` | ~22 | **à changer** → 32154 |

- **21 sites réels pour 4332** (17 comparaisons de fin de bloc + 4 pas) — et **une coïncidence** que
  seul le désassemblage révèle : `pea 0x40a710ec` n'est pas « 4332 » mais un pointeur dont la moitié
  basse vaut 4332. Un remplacement « à l'aveugle » de 4332 casserait ce pointeur — c'est exactement
  le genre de piège que le tri par instruction évite.
- **Le mécanisme de la queue de pattern est identifié** : juste après la boucle des pistes,
  `addil #4336,%d2` puis `movel %d2,%a2@(672)` : la base de la **queue** du pattern
  (`pattern + 4336`, soit le bloc des pistes + 4 o d'en-tête) est **calculée une fois et rangée dans
  un champ** (672). Les champs de la queue sont donc atteints **relativement à ce pointeur**, pas par
  des décalages figés depuis la base du pattern — **c'est ce qui rend l'extension bornée** : allonger
  le bloc des pistes déplace la queue toute seule, par le seul changement de `4336`.
- **Ensemble du changement** : `4332 → 5776` (21 sites), `4336 → 5780` (1 site), `30710 → 32154`
  (~22 sites) — et **rien d'autre** dans le code : les enregistrements de piste (708 o) sont
  autonomes, et la queue est relative à son pointeur.

**Reste à trancher** :
- la **forme fichier** : la même constante 4332 y apparaît (`0x4005b91e`, `0x4005b92c`, `0x4005ba66`,
  `0x4005bfb0`, `0x4005c2a2`) — donc le format de fichier a son propre bloc de pistes, et c'est là que
  se joue la **compatibilité des projets** ;
- les **conversions** (`0x4005c040`, `0x4005c1cc`, appelées indirectement) ;
- la **place** : combien de patterns, et la région mémoire a-t-elle de quoi grandir de 1444 o par
  pattern.

### 3.22 Forme fichier, conversions, et une **seconde sorte d'enregistrement** `[FAIT]` (14/10)

`build/re8/probe_file.py`, `probe_pcrel2.py`, `probe_file2.py`, `probe_7094.py`.

- **96 patterns** : `moveq #95,%d1` / `cmpl %d0,%d1` / `bcss` (`0x400083ba`) borne l'index à 95, et
  l'adresse est `0x406fa040 + index × 30710` ✓ (base confirmée à `0x400083c8`).
- **La boucle par piste appelle la copie par un pointeur de fonction** :
  ```
  4005ba42  lea %pc@(0x4005b642),%a4    ; la copie B->A, prise en adresse RELATIVE
  4005ba50  pea %a3@(0,%d2:l)           ; source : base + piste x 722
  4005ba54  pea %a5@(0,%d2:l)           ; destination : base + piste x 722
  4005ba58  addil #722,%d2
  4005ba5e  jsr %a4@
  4005ba64  cmpil #4332,%d2             ; 6 pistes
  4005ba6a  bnes 0x4005ba46
  ```
  D'où l'absence de référence littérale aux copies : elles sont prises en **adresse relative**
  (`lea %pc@`) — c'est aussi pourquoi les « conversions » semblaient ne pas exister.
- **La queue du pattern est traitée une fois**, après la boucle, via `%a3@(4336)` et `%a2@(4336)` :
  le bloc des pistes, puis **4 octets d'en-tête**, puis la queue ✓ — cohérent avec le §3.21 (la base de
  la queue rangée dans un champ).
- **Un champ à `30706`** (= fin du pattern − 4) : `movel %a0@(30706),%d0` / `andl %a0@(30706),%d0` —
  quatre octets de drapeaux en fin de pattern ✓.
- **Une seconde sorte d'enregistrement : `7094` o** (`movel #7094` / `addil #7094`, 8 sites longs :
  `0x400083d4`, `0x400100a0`, `0x40010790`, `0x40020196`, `0x400203c0`, `0x4005d360`, `0x400617ae`,
  `0x400d1bca`) — calculée **juste après** l'adresse du pattern, donc c'est un **second tableau**
  indexé de la même façon : selon toute vraisemblance le **kit** (les réglages de machine par piste).
  **Il porte lui aussi des données par piste** — donc il devra grandir pour huit pistes, et son
  découpage par piste reste à établir (ce n'est pas 722).

**Conséquence sur le plan** : le jalon « pattern » n'est pas seulement trois constantes. Il y a
**deux tableaux par pattern** — les pas (`30710`, bloc de pistes `4332`) et les réglages (`7094`) — et
c'est dans le second que vivent les machines des pistes 7-8. La bonne nouvelle du §3.21 tient (la
queue est relative à un pointeur), mais le second tableau demande son propre relevé.

**Ce qui reste** : le découpage par piste du tableau `7094` ; les conversions de version (appelées par
pointeur, à retrouver par les `lea %pc@`) ; et la place mémoire (96 × 1444 o de plus pour les pas,
plus ce que le tableau `7094` demandera).

### 3.23 Le kit, et l'ensemble du changement « pattern » enfin borné `[FAIT]` (14/10)

`build/re8/probe_kit.py`, `probe_kitstride.py`, `probe_kit600.py`.

- **La base du second tableau (le kit)** : `0x406fa040 + 96 × 30710` arrondi à `0x409c9a00` — les
  patterns puis les kits, **96 × 7094** (`addil #1084005504` en `0x400083dc` = `0x409c9a00`). Dans la
  **forme fichier**, le même calcul se fait en **décalage** : `addal #2948188` (= 96 × 30710 + 28)
  en `0x400100aa` — donc le fichier range lui aussi les patterns puis les kits.
- **Le pas par piste DANS le kit est 100 o** :
  ```
  4005b2f2  lea %a3@(28),%fp          ; le kit : bloc par piste à +28
  4005b2f6  lea %a2@(32),%a5
  4005b300  pea %fp@(0,%d2:l)
  4005b304  pea %a5@(0,%d2:l)
  4005b308  addil #100,%d2            ; <-- pas par piste du kit
  4005b30e  jsr %a4@
  4005b314  cmpil #600,%d2            ; <-- 600 = 6 x 100
  ```
- **Sa borne est `600` = 6 × 100**, à **7 `cmpil`** : `0x40009aa2`, `0x40009b5a`, `0x4000a546`,
  `0x4005b314`, `0x4005bea4`, `0x4005cd60`, `0x4005d132` (plus une coïncidence en `0x401081d2`,
  `btst %d0,%a4@(0)`). `800` (8 × 100) **n'existe pas** dans le code.

#### L'ensemble du changement « pattern » (patterns **et** kits)

| Constante | Sens | Sites | Nouvelle valeur |
|---|---|---|---|
| **4332** | bloc des pistes du pattern (6 × 722) | 21 | **5776** |
| **4336** | base de la queue (bloc + 4 o d'en-tête) | 1 | **5780** |
| **30710** | taille d'un pattern | ~22 | **32154** |
| **600** | bloc par piste du kit (6 × 100) | 7 | **800** |
| **7094** | taille d'un kit | 8 | **7294** |

**~59 sites, tous identifiés et classés** (chaque site vérifié par l'instruction qui le porte, une
coïncidence de pointeur écartée au §3.21, une autre ici). Le fichier grandit de
96 × (1444 + 200) = **157 824 o** (≈ 154 Ko) ; la mémoire, d'autant.

**Reste, pour finir le jalon « pattern »** :

1. le **marqueur de version** : le champ à `30706` (fin du pattern − 4) est le candidat — c'est lui
   qui dira à l'OS qu'un projet est « 6 pistes » (à convertir) ou « 8 pistes » ;
2. les **conversions** (appelées par `lea %pc@`, à retrouver — les cibles repérées sont
   `0x4005bfea`, `0x4005c0c6`, `0x4005c15a`, `0x4005c252`) ;
3. la **place mémoire** : 96 patterns + 96 kits, et la région a-t-elle de quoi grandir de
   (1444 + 200) o par paire.

### 3.24 Marqueur de version (négatif) et **place : la zone suivante est occupée** `[FAIT]` (14/10)

`build/re8/probe_version.py`, `probe_version2.py`.

#### a) Le champ `30706` n'est **pas** un marqueur de version

```
400541da  moveq #127,%d0
400541dc  andl %a0@(30706),%d0     ; (pattern@30706) & 127 : une valeur sur 7 bits
400541e4  cmpl %d1,%d0
400541e6  beqs 0x40054200
```
Masqué à `0x7f` puis comparé à un octet de table : c'est une **donnée** (7 bits — un canal MIDI, une
gamme…), pas un indicateur de format. **Le marqueur de version reste à trouver ailleurs** (peut-être
au niveau du *projet*, pas du pattern).

#### b) Les « conversions » de notes/54 §2.3 : lecture à réviser

- `0x4005bba0`, appelée par les fonctions repérées, est un **utilitaire de comparaison**
  (`cmpl %d1,%d0 ; sne ; negl` → renvoie −1/0/1) ;
- les corps (`0x4005c00e`…) sont des **boucles d'octets jusqu'à 128** qui **fusionnent/copient**,
  pas des conversions de version.

Donc `0x4005c040`/`0x4005c1cc` ne sont **pas** les conversions annoncées : le mécanisme de
compatibilité des projets reste **à établir**. C'est le point ouvert du jalon « pattern », et il
touche directement la question de Kevin (que devient un projet existant).

#### c) La place : la zone de croissance est **occupée**

Les tables vivent en SDRAM : patterns `0x406fa040` (96 × 30710), kits `0x409c9a00` (96 × 7094) — les
kits finissent à `0x40a6fe00`. Or **la zone juste après est utilisée** :

| Plage | Littéraux distincts | Ce qu'on y voit |
|---|---|---|
| `[0x40a6fe00, 0x40a96640)` (les 157 824 o dont on aurait besoin) | **2 208** | utilisé par le MIDI (`0x40080xxx`) et le séquenceur (`0x40054xxx`) |
| `[0x40a96640, 0x42308828)` | **3 399** | adresses impaires (`0x40ac4eb9`…) → des **chaînes** (noms de sons) |

**Conséquence** : allonger les tables sur place **écraserait** ce qui suit. Il faut donc, pour la
mémoire, soit **reloger les tables** (leurs bases ne sont citées que par 6 + 2 littéraux — c'est bon
marché) dans une zone réellement libre, soit déplacer l'occupant. **Trouver cette zone est un
sous-chantier neuf** : il faut une **carte du libre en SDRAM**, avec les mêmes balayages que pour les
accueils du moteur (littéraux **et** accès par décalage calculé).

**Bilan du jalon « pattern »** : le *code* est borné et classé (~59 sites) ; il reste **deux
inconnues** — le mécanisme de compatibilité des projets, et **où** loger les tables agrandies.

### 3.25 Carte du libre en SDRAM : dense et fragmentée — la croissance ne peut pas être **relogée** `[FAIT]` (14/10)

`build/re8/probe_sdram.py`, `probe_sdram2.py`. SDRAM = 64 Mo (`0x40000000..0x44000000`).

- **27 324 adresses** de la SDRAM sont citées par un littéral (24 131 sous la fin du BSS, 3 193
  au-dessus) : la mémoire est **dense**.
- Le découpage en blocs de 64 Ko le dit mieux que les « trous » (un seul littéral au milieu d'une
  grande zone libre coupe un trou en deux) : **166 blocs sur 1024 sont totalement vides**, soit
  ~10,6 Mo libres **mais éparpillés**.
- Plus grande plage **totalement** vide : **262 144 o** (`0x43a30000..0x43a70000`).
- Plus grandes plages **presque** vides (≤ 2 littéraux par bloc) : **720 896 o** (`0x43dd0000`),
  655 360 o (`0x43350000`), 589 824 o (`0x43b10000`), 524 288 o (`0x43a10000`), 524 288 o
  (`0x43d00000`) — toutes dans le **haut de la SDRAM** (`0x4335xxxx..0x43e8xxxx`).

**Conséquence — le point important** : les tables demandent, agrandies,
96 × 32154 + 96 × 7294 ≈ **3,8 Mo contigus**. Il n'existe **aucune** plage libre de cette taille
(la plus grande est 256 Ko). **Reloger les tables est donc exclu.**

**Ce que ça impose** : la croissance doit se faire **à l'intérieur** des enregistrements existants.
Or un enregistrement de pattern fait **30 710 o** dont les pistes n'occupent que **4 332** : les
**26 378 o restants** (la « queue ») sont l'endroit à regarder — si elle a de la marge, les deux
pistes de plus y tiennent **sans mémoire neuve**. C'est aussi ce que suggérait le §3.21 (la queue est
atteinte relativement à un pointeur rangé dans un champ) : sa disposition interne est la prochaine
chose à décoder, et elle décide si le jalon « pattern » tient en mémoire ou non.

**Ce qui est donc établi pour le jalon « pattern »** :
1. le **code** : ~59 sites, bornés et classés `[FAIT]` ;
2. la **mémoire** : pas de relogement possible ; il faut **loger les 1 644 o de plus par pattern
   dans la queue de l'enregistrement** — à confirmer en décodant cette queue ;
3. la **compatibilité des projets** : mécanisme encore à établir (§3.24.b).

### 3.26 La queue = les **verrous de paramètres**, et elle est par piste aussi `[FAIT]` (14/10)

`build/re8/probe_tail.py` — le gestionnaire `0x4005b766`, appelé au chargement avec `%a3@(4336)` :

```
4005b796  moveal %d0,%a1
4005b79e  lea %a1@(0,%d1:l),%a4
4005b7a4  moveq #66,%d5              ; 33 mots par pas
4005b7a6  movew %d3,%a4@(0,%a0:l)    ; écrit 0xFFFF (initialisation « pas de verrou »)
4005b7aa  addql #2,%a0
4005b7ae  bnes 0x4005b7a2
4005b7b0  addil #68,%d1              ; <-- pas de 68 o : un PAS
4005b7b6  cmpil #4352,%d1            ; <-- 4352 = 64 x 68
4005b7bc  bnes 0x4005b79c
4005b7be  addil #4385,%d0            ; <-- pas de 4385 o : une PISTE
4005b7c4  cmpil #26310,%d0           ; <-- 26310 = 6 x 4385
4005b7ca  bnes 0x4005b796
```

Trois niveaux imbriqués, sans ambiguïté :

| Niveau | Pas | Borne | Nombre |
|---|---|---|---|
| pas (à l'intérieur d'une piste) | 68 o | 4352 | **64** (= les 64 pas du pattern) |
| piste (à l'intérieur de la queue) | 4385 o | 26310 | **6** (= les 6 pistes) |

Et le contenu : l'innermost écrit `0xFFFF` en 33 mots (66 o) — l'**initialisation à « pas de
verrou »** ✓. Donc **la queue est la table des verrous de paramètres** : 6 pistes × 64 pas × 68 o,
chaque pas portant 66 o de verrous (+2 o de marge).

**Composition complète de l'enregistrement de pattern** :

```
0      .. 4332    les pas        6 pistes x 722
4332   .. 4336    un en-tête de 4 o
4336   .. 30646   les verrous    6 pistes x 64 pas x 68   (= 26310)
30646  .. 30710   reste (64 o)
```

**Conséquence — et c'est un vrai obstacle** : les **deux** moitiés sont **par piste**. Pour huit
pistes, l'enregistrement doit passer de 30 710 à **40 924 o** (+1444 pour les pas, +8770 pour les
verrous), soit **+10 214 o par pattern** — **~1 Mo de plus** au total. Or le §3.25 a montré qu'il
n'existe **aucune plage libre contiguë** de cette taille (la plus grande plage presque vide fait
704 Ko). **La mémoire est donc le vrai verrou du jalon « pattern ».**

**Les issues possibles** (à trancher avec Kevin) :

1. **consolider** : reloger quelques structures pour rassembler ~1 Mo libre — lourd, et il faudrait
   d'abord identifier ce qui occupe le haut de la SDRAM ;
2. **échanger des patterns contre des pistes** : `72 patterns × 40 924 = 2 946 528`, contre
   `96 × 30 710 = 2 948 160` — **72 patterns à 8 pistes tiennent exactement dans l'empreinte
   actuelle** ✓. C'est le compromis le plus simple, mais il change la structure des projets ;
3. **réduire la queue** : les verrous sont stockés sur 66 o par pas alors que le M:C n'en utilise
   peut-être pas autant — reste à mesurer (combien de verrous par pas l'OS écrit-il réellement ?).

### 3.27 Décision : **cinq banques à huit pistes** `[FAIT]` (14/10)

Kevin : « je suis prêt à perdre une banque, ça ne me dérange pas ». Le compromis mémoire est donc
tranché — **on échange la banque F contre les pistes 7-8** — et il faut le dire précisément :

- **96 = 6 banques (A–F) × 16 patterns**, pas 6 pistes × 16 (le nom de pattern est `%c%02d` en
  `0x40124aed`, et les lettres `ABCDEF` sont dans l'image ; et l'enregistrement contient **déjà** les
  6 pistes, donc l'index 0..95 énumère des patterns) ;
- **ce n'est pas « 16 emplacements jamais utilisés »** : c'est la **banque F** (`F01`..`F16`). Un
  projet qui a du contenu là-dedans le **perdrait** (ou devrait être remappé) — à traiter par la
  conversion, c'est le seul point de perte de données du mod.

**Chiffres du choix** (80 patterns = 5 banques) :

| | Aujourd'hui (96 × 6) | Après (80 × 8) | Delta |
|---|---|---|---|
| enregistrement de pattern | 30 710 | **40 924** | +10 214 |
| enregistrement de kit | 7 094 | **7 294** | +200 |
| **table des patterns** | 2 948 160 | **3 273 920** | **+325 760** |
| **table des kits** | 681 024 | **583 520** | **−97 504** |
| **total** | 3 629 184 | **3 857 440** | **+228 256** |

- Les **kits rétrécissent** (80 au lieu de 96) : leur table passe sous sa taille actuelle ✓.
- Donc : les **patterns grandissent sur place** (2,95 → 3,27 Mo, soit **+326 Ko** dans l'espace que
  les kits libèrent en partant) ✓, et les **kits déménagent** (583 520 o, plus petits qu'aujourd'hui)
  — candidate : la plage presque vide de **704 Ko** à `0x43dd0000` ✓.
- **La mémoire cesse d'être le verrou** ✓ : le total ne grandit que de **228 Ko**, et aucune plage de
  ~1 Mo n'est nécessaire.

**Ce que la décision change dans le code** (en plus des ~59 sites du §3.23) :

- le **nombre de patterns** : la garde `moveq #95` (`0x400083ba`) passe à **`moveq #79`** — et ses
  jumelles (les `#96` du code, à recenser) ;
- les **bases des deux tables** et la **nouvelle disposition** (patterns sur place, kits ailleurs) ;
- la **conversion** doit décider du sort de la banque F.

**Reste donc, pour finir le jalon « pattern »** :
1. la **compatibilité des projets** (mécanisme à établir, §3.24.b) — c'est elle qui traitera la
   banque F et les projets existants ;
2. le **déménagement des kits** (trouver leur accueil, y compris les 11 références de la plage
   `0x43dd0000`) ;
3. l'**implémentation** : ~59 sites + la garde du nombre de patterns + les bases des tables.

### 3.28 La compatibilité des projets : **un sceau magique et des conversions** `[FAIT]` (14/10)

`build/re8/probe_header.py`, `probe_header2.py`, `probe_header3.py`, `probe_transfer.py`.

#### a) L'en-tête de projet

**`0x406fa024`**, soit **28 octets juste avant la table des patterns** (`0x406fa040`) : cité par
**7 `pea`** (`0x40006cb0`, `0x4004489e`, `0x400448c4`, `0x40044922`, `0x40044946`, `0x40044974`,
`0x40044bb8`), toujours passé au **gestionnaire de chargement/sauvegarde** `0x4005deaa` (avec
`0x404e9c20` et un drapeau). C'est **l'en-tête du projet** — dans le BSS, donc rempli au chargement
(on ne peut pas le lire dans l'image, seulement son usage).

#### b) Le sceau magique : **`0xBEEFBACE`**

Le gestionnaire de chargement `0x4005d9f6` **teste le premier mot long** de la structure :

```
4005da28  movel #-1091585330,%d0        ; -1091585330 = 0xBEEFBACE
4005da2e  cmpl %a2@,%d0
4005da30  bnew 0x4005de9e               ; sceau absent -> on abandonne
```

`0xBEEFBACE` (« beef base ») apparaît à **24 sites**, tous dans le chemin de chargement/sauvegarde,
et le tri par instruction les classe :

| Forme | Nb | Sens |
|---|---|---|
| `movel #magic,%aN@` | 6 | **écriture du sceau** dans une structure (`0x4000ef7a`, `0x4000fd82`, `0x4005afbe`, `0x4005b072`, `0x4005d3b4`, `0x400a2f46`) |
| `movel #magic,%dN` | 12 | sceau chargé dans un registre (comparaison ou écriture différée), dont `0x4005da28` |
| `cmpil #magic,%d0` | 1 | **comparaison** (`0x400a2acc`) |
| `.short 0xbeef` | 2 | coïncidences dans des données (`0x40134e21`, `0x4013d3ed`) |

**Donc le format d'un projet est identifié par un sceau**, écrit au début de la structure et
**vérifié au chargement** ✓✓.

#### c) Et l'OS **a déjà** un mécanisme de conversion

Les sites `movel #magic,%dN` des **`0x4005c30c`, `0x4005c42e`, `0x4005c550`, `0x4005c770`,
`0x4005c9a8`, `0x4005ce3c`** sont dans la zone `0x4005c0xx..0x4005cexx` — celle des fonctions
« comparaison + fusion » du §3.24.b. Autrement dit : **ces fonctions construisent des structures
marquées du sceau**, c'est-à-dire qu'elles **produisent un format** — c'est le mécanisme de
migration que l'OS utilise déjà entre versions ✓.

**Conséquence pour le mod — et c'est la bonne nouvelle** : le mécanisme existe et il est repéré.
Un build 8 pistes devrait :

1. écrire un **sceau distinct** pour son format (par exemple `0xBEEFBACF`) ;
2. **accepter l'ancien sceau** au chargement et **convertir** (6 → 8 pistes), en traitant la
   **banque F** (perdue ou remappée, §3.27) ;
3. écrire le nouveau sceau à la sauvegarde, ce qui rend un projet 8 pistes **non lisible par l'OS
   d'origine** — à documenter pour l'utilisateur.

**Ce qui reste à préciser** : la **liste des sceaux acceptés** (y a-t-il plusieurs valeurs selon les
versions ? le tri des 24 sites le dira), et le **point d'aiguillage** de la conversion (où l'OS
choisit la fonction selon le sceau lu).

### 3.29 La compatibilité des projets : **le mécanisme complet, et il est rassurant** `[FAIT]` (14/10)

`build/re8/probe_magic.py`, `probe_conv.py`, `probe_dispatch.py`, `probe_load.py`, `probe_class.py`,
`probe_map.py`, `probe_magic2.py`.

#### a) La carte mémoire du projet — vérifiée par l'arithmétique

| Adresse | Quoi | Taille |
|---|---|---|
| `0x404e9c20` | **l'image du projet** (le format rangé) | **2 163 716** = `0x210404` |
| `+0` | sceau **`0xBEEFBACE`** | |
| `+4` | **le numéro de version** | |
| `+0x210400` | sceau de clôture **`0xBACEF00C`** (les 4 derniers octets) | |
| `0x406fa024` | **l'en-tête de projet** (28 o) | |
| `0x406fa040` | table des patterns (96 × 30 710) | 2 948 160 |
| `0x409c9a00` | table des kits (96 × 7 094) | 681 024 |

**`0x404e9c20 + 2 163 716 = 0x406fa024`** ✓✓ — l'image **finit exactement** là où commence
l'en-tête, lui-même juste avant les patterns. C'est **une seule plage contiguë** : image → en-tête →
patterns → kits. Le décalage des images des anciennes versions (v0 finit en `0x40660424`, v1/v2 en
`0x4065e024`, v3 en `0x4066a024`) est **du vide** : l'image est dimensionnée pour la version
courante, et c'est pourquoi la chaîne **recopie le résultat dans l'image** à la fin.

#### b) Le chemin de chargement : `0x4008d8e6`

```
4008d92e  movel #2163716,%sp@-      ; la taille de l'image
4008d934  jsr 0x400802e0            ; allocation
4008d948  pea 0x404e9c20            ; <- l'adresse FIXE de l'image
4008d950  lea 0x4008f1f0,%a4
4008d956  jsr %a4@                  ; memcpy(0x404e9c20, tampon, 2163716)
4008d972  jsr 0x4005d9f6            ; <- LA CHAINE DE CONVERSION
4008d986  jsr %a5@                  ; liberation du tampon
4008d98a  tstb %d7
4008d98c  beqs 0x4008d9f4           ; conversion ratee -> on abandonne
```

Le projet stocké est donc **copié à l'adresse fixe `0x404e9c20`** puis **mis à niveau sur place**
par la chaîne. Si la mise à niveau échoue, le chargement est abandonné ✓.

#### c) La chaîne de conversion : `0x4005d9f6`

Six blocs de **198 octets** (0xC6), un par version, chacun :

1. alloue le tampon de la version suivante (sa taille en littéral) ;
2. fabrique un objet de 16 octets : `[+0 descripteur de classe][+4 = 1][+8 = 1][+12 tampon]` ;
3. appelle **le convertisseur de la version** ;
4. recopie le résultat dans l'image (`memcpy` + `a3@ = 1`).

| Version | Convertisseur | Tampon alloué |
|---|---|---|
| 0 | `0x4005c748` | 1 524 740 |
| 1 | `0x4005c97e` | 1 524 740 |
| 2 | `0x4005c2e2` | 1 573 892 |
| 3 | `0x4005c404` | 2 163 716 |
| 4 | `0x4005ce12` | 2 163 716 |
| 5 | `0x4005c526` | 2 163 716 |

**Fin de chaîne, explicite** :

```
4005de74  movel %a2@(4),%d0          ; le champ version de l'objet
4005de78  moveal #-1091585330,%a0    ; 0xBEEFBACE
4005de7e  cmpal %a2@,%a0
4005de80  bnes 0x4005de9e
4005de82  movel #2163712,%d1         ; 0x210400
4005de88  moveal #-1160843252,%a0    ; 0xBACEF00C
4005de8e  cmpal %a2@(0,%d1:l),%a0
4005de92  bnes 0x4005de9e
4005de94  moveq #6,%d1               ; <<< LA VERSION COURANTE EST 6
4005de96  cmpl %d0,%d1
4005de98  seq %d0
```

Chaque convertisseur vérifie lui-même la **version de la source** (`cmpl %a2@(4),%d0` avec 0, 1, 2,
3, 4, 5), le sceau `0xBEEFBACE` **et** le sceau de clôture `0xBACEF00C` à la position de sa version.

**Conséquence directe et importante** : une image dont la version n'est pas 0..6 **échoue
proprement** (le contrôle final est `== 6`) → **l'OS d'origine refuse un projet Groove au lieu de le
mal lire** ✓✓. C'est exactement la garantie qu'on voulait : pas de corruption silencieuse.

#### d) Les descripteurs de classe

Table à **`0x4010eff4`**, **28 octets par entrée**, 5 pointeurs de méthodes + 0 + un pointeur vers
une sous-table. `0x4010f160 - 0x4010eff4 = 364 = 13 × 28` : **une seule table indexée**. La chaîne
utilise les entrées **13 à 18** (une par version : `0x4010f160`, `f17c`, `f198`, `f1b4`, `f1d0`,
`f1ec`) ; les fonctions d'emballage de `0x400e24xx` utilisent les entrées 0 à 7. C'est **la table à
étendre** pour une version 7.

#### e) Le sceau n'est pas propre à l'image

`0xBEEFBACE` marque aussi des enregistrements de **100 octets** (`0x4005afbe`) et de **112 octets**
(lecteur `0x400a2axx`, qui accepte en plus un sceau alternatif **`0xABCDEF12`**, 2 sites). Le format
est donc identifié par **sceau + version**, pas par le sceau seul.

#### f) Ce que ça donne pour le mod — **version 7**

Le mécanisme existe et il est fait exactement pour ça. Groove = **version 7** :

1. un **convertisseur v6 → v7** (6 pistes → 8) ;
2. **un bloc de 198 octets de plus** dans la chaîne `0x4005d9f6` ;
3. **une entrée de classe** (28 o) de plus dans la table `0x4010eff4`, avec la nouvelle taille ;
4. l'image grandit (elle contient les patterns rangés) → **l'en-tête et les tables se décalent**,
   donc les littéraux de base (`0x406fa040`, `0x409c9a00`) changent — ce qu'on savait déjà.

**Et la question de Kevin a maintenant une réponse précise** : un projet d'origine (version ≤ 6) est
**converti au chargement** par la chaîne ; un projet **sauvegardé** par Groove (version 7) est
**refusé** par l'OS d'origine, sans corruption. Reste à traiter la **banque F** dans le convertisseur
v6 → v7 (§3.27).

### 3.30 La sauvegarde et le +Drive : **verdict, et c'est un oui franc** `[FAIT]` (14/10)

`build/re8/probe_save.py` .. `probe_save5.py`, `probe_wrap.py`.

#### a) L'enregistrement stocké

| Adresse | Quoi | Taille |
|---|---|---|
| `0x404e9b10` | **l'enveloppe** du projet stocké | **272** o |
| `0x404e9c20` | **l'image** (§3.29) | 2 163 716 o |
| | **l'enregistrement complet** | **2 163 988** = `0x210514` |

`0x404e9c20 - 0x404e9b10 = 0x110 = 272` ✓ : l'image suit immédiatement l'enveloppe. L'enveloppe
porte **son propre sceau `0x434F4B49` (« COKI »)** en `+0` (3 sites : `0x40044ae4`, `0x40044af8`,
`0x40044b7c`), un nom, un index, des horodatages. La sauvegarde est `0x400449ce` → `0x4008ec1c`
(avec `0x53` = 83), et le chemin « projet » est la grappe `0x40042xxx..0x40044xxx`.

#### b) Le +Drive est un **système de fichiers**

Les chaînes de l'image (noms de types C++ laissés par le compilateur) le disent sans ambiguïté :

- `ProjectHandler::register_route` avec les routes **`/projects/`**, **`/projects/*`**,
  **`/projects/*/.metadata`** ;
- `Project::loadProjectFromMmc(int, std::function)` — « **Mmc** » : le +Drive est du stockage type
  carte, présenté par un système de fichiers ;
- `ProjectManager` : `interactiveLoad`, `interactiveSave`, `interactiveDelete`, `interactiveClear`,
  `rebuild`, `savePatternToProject` ;
- `Write project MRAM`, `SaveBackupProject`, `saveProjectToMmc(tempProject)` ;
- `MidiRpcStorageSpaceRequest` / `Response` — **l'espace libre est interrogeable par MIDI** ;
- `"Not enough space"`, `"No space left on device"`, `"Could not write to file (file system
  full?)"`, `"Lock mem full!"` — l'OS **sait** manquer de place et le dit.

**Conséquence majeure** : ce ne sont **pas des emplacements de taille fixe**. Un enregistrement plus
gros demande **plus de blocs libres**, pas un changement de géométrie → **rien de ce qui est déjà
stocké n'est bousculé** ✓✓.

#### c) Les formats ont des **noms de types**, et l'OS gère les versions explicitement

```
ModelSeries::projectStorage_v1_t … projectStorage_v6_t
ModelSeries::projectSettingsStorage_v1_t … _v3_t
ModelSeries::patternSettingsStorage_v0_t
Project::updateMirror(ModelSeries::projectStorage_v6_t&, …)
"Invalid project version"
"Project version is newer than what the device supports"
```

- La famille `projectStorage_v1_t..v6_t` **confirme nommément** la chaîne du §3.29 (versions 1..6 ;
  le cas « 0 » du `tstl` étant l'absence de version) ;
- **`projectStorage_v6_t` est le format courant** ✓ — c'est le type à décliner en **v7** ;
- il existe **d'autres familles versionnées** (réglages de projet v1..v3, réglages de pattern v0) :
  la chaîne étudiée est celle des **projets**, pas la seule ;
- et surtout : **« Project version is newer than what the device supports »** est le message
  exact que l'OS d'origine affichera pour un projet Groove (v7) — **un refus propre, explicite, déjà
  prévu par Elektron** ✓✓✓. C'est la meilleure réponse possible à la question de Kevin.

#### d) La capacité — et le verdict

- **+Drive : 1 Go**, **96 projets**, 96 patterns par projet (fiche constructeur).
- **96 × 2 163 988 = 207 742 848 o ≈ 198 Mo** → il reste **≈ 826 Mo**.
- Budget par projet à 96 projets : **≈ 10,7 Mo**, soit **~5× la taille actuelle** (2,16 Mo).

L'image doit grandir d'environ **0,4 Mo** (patterns rangés : 14 848 → ~19 800 pour 8 pistes) — soit
**0,05 %** de la marge. **La mémoire du +Drive n'est pas un problème du tout** ✓✓✓.

**Verdict de l'option A** :

| Question | Réponse |
|---|---|
| Le +Drive est-il à emplacements fixes ? | **Non** — système de fichiers à arborescence |
| Faut-il changer la géométrie ? | **Non** |
| Les projets déjà stockés risquent-ils d'être bousculés ? | **Non** |
| La place suffit-elle ? | **Oui, très largement** (~826 Mo de marge) |
| Que voit l'utilisateur avec un projet Groove sur l'OS d'origine ? | **« Project version is newer than what the device supports »** — un refus propre |
| Les projets stockés sont-ils mis à niveau ? | **Oui** — « UPGRADING ACTIVE PROJECT… », « UPGRADING FACTORY PROJECT… » |

**Le volet stockage est clos, et sans mauvaise surprise.** Reste au programme : la banque F dans le
convertisseur v6 → v7, le déménagement des kits, l'implémentation, et l'interface de sélection des
pistes.

#### e) Bonus pour la suite

Les **noms de types C++** sont restés dans l'image (`Project`, `ProjectManager`, `ProjectHandler`,
`ProjectCache`, `MemoryStreamReader/Writer`, `BackupFileHeader`, `DataChangeInfo`,
`ValueWithMirror<…>`, …). C'est une **carte de l'architecture** utilisable pour les prochaines
recherches : on peut nommer les objets au lieu de les décrire par leur adresse.

### 3.31 L'interface : ce qui est établi, et la vraie question qui reste `[FAIT]`/`[HYP]` (14/10)

`build/re8/probe_ui.py` .. `probe_ui10.py`.

#### a) Les classes, par leurs noms de types

`TrackSelectionView`, `TrackMenuView`, `PadsView`, `PatternGridView`
(`produceLedData(const std::bitset<54>&, std::bitset<54>&)`), `LedManager`, `LedHandler`,
`DrumSelect`, `TransportView`, `NoteSetupMenuView`, `QuickMuteMenuView`, `PatternAndBankSelectView`.
L'interface utilise **« TRK »** comme abréviation de piste (« Copy TRK %d Sound »,
« Paste TRK %d Sound », « Clear TRK %d Sound ») et affiche « **Track %d** ».

#### b) **Six pads, en dur** `[FAIT]`

`0x4001cf8c`, une méthode de `PadsView` :

```
4001cf98  moveal 0x404a8ba0,%a0       ; le tableau des pads
4001cfa2  movel  %a0@(0,%d2:l:4),%d0  ; pad[d2]
4001cfa6  btst   %d2,%d1              ; le pad d2 est-il enfonce ?
4001cfb6  moveq  #6,%d0               ; <<< 6 PADS
4001cfb8  cmpl   %d2,%d0
4001cfba  bnes   0x4001cf98
```

Le panneau a **six pads** et le code le suppose. C'est **la contrainte matérielle** de
l'interface.

#### c) **Onze bornes « 6 » dans l'interface** `[FAIT]`

Balayage de `0x40020000..0x40030000` (objdump, fiable — capstone désynchronise ici) :

| Adresse | Forme | Rôle probable |
|---|---|---|
| `0x40020a42` | boucle `moveq #6` | liste de 6 |
| `0x40022ec2` | comparaison `== 6` | test |
| `0x400231c2` | boucle `moveq #6` | liste de 6 |
| `0x4002399a` | garde « ≤ 5 » | action de piste (Copy/Paste/Clear TRK) |
| `0x40023ca2` | bornage ≤ 5 | indice de piste |
| `0x40023efa` | garde « ≤ 5 » | action de piste |
| `0x40024960` | garde ≤ 5 | |
| `0x40028ee2` | boucle `moveq #6` | **liste des 6 pistes** (avec « Track %d ») |
| `0x4002b9b4` | bornage ≤ 5 | |
| `0x4002fa10` | boucle `moveq #6` | |
| `0x4002fade` | boucle `moveq #6` | |

**Attention** : 6 est aussi le nombre de **machines** (Kick, Snare, Metal, Perc, Tone, Chord) —
certaines de ces bornes peuvent porter sur la machine, pas sur la piste. Celles de `0x4002399a`
et `0x40023efa` sont bien des pistes : leurs appelants (`0x4002415e`, `0x4002417e`) construisent
les entrées « Copy/Paste/Clear TRK %d Sound ».

#### d) Le panneau est assemblé de façon déclarative

`0x4001bxxx` alloue chaque vue et l'attache à un **emplacement fixe** (`%a2@(164)`, `%a2@(172)`,
…). `TrackSelectionView` est créée en `0x4001bb06` (constructeur `0x40023a7a`, **vtable
`0x40100edc`**, 7 méthodes) — donc **toujours présente**, pas une fenêtre déclenchée par un
bouton.

#### e) La vraie question — et c'est de la **conception**, pas de la RE `[HYP]`

**Le panneau n'a que six pads.** Comment l'utilisateur atteint-il les pistes 7 et 8 ?
Les candidats :

| Option | Principe | Remarque |
|---|---|---|
| **a** | `[FUNC]` + pad = pistes 7-8 | réutilise le matériel existant, aucun bouton neuf |
| **b** | une seconde « page » de pistes | suppose un geste de bascule |
| **c** | les 16 boutons de pas | 16 emplacements libres, mais change l'ergonomie |
| **d** | une entrée de menu | le plus sûr, le moins direct |

Le **geste actuel** de sélection de piste n'est **pas encore décodé** : il est dans le
`consumeKeyEvent` de la vue, atteignable par la vtable `0x40100edc` (7 pointeurs de méthodes).
C'est le dernier point de RE de l'interface.

#### f) Conséquence pour le plan

L'interface **n'est pas gratuite** : onze bornes à élargir, **un geste à concevoir**, et
l'affichage (nom « Track %d », LEDs — le plan de LEDs est un `bitset<54>`). C'est précisément
pourquoi il valait la peine de la regarder **avant** d'écrire les ~59 sites du moteur : le
geste de sélection est une décision de conception, et elle appartient à Maxime.

### 3.32 Décision de conception : **une seconde page de pistes** `[FAIT]` (14/10)

`build/re8/probe_ui11.py` .. `probe_ui14.py`.

#### a) La décision de Kevin

> « une combinaison **bouton TRACK + bouton PAGE** ne bascule que **T1 et T2** en pistes
> **7-8** ; la même combinaison **allume les 6 LEDs de piste**, ce qui montre la **page 1 et la
> page 2** »

Traduction en conception :

| | Page 1 | Page 2 |
|---|---|---|
| Pads actifs | **T1–T6** | **T1–T2** |
| Pistes atteintes | 1–6 | **7–8** |
| LEDs de piste | 1–6 allumées | **1–2 allumées** (donc on *voit* la page) |
| Bascule | **`[TRACK]` + `[PAGE]`** | idem |

C'est l'option **(b)** du §3.31.e : elle respecte le matériel (6 pads), ne crée aucun bouton, et
les **LEDs servent d'indicateur de page** — donc l'utilisateur sait toujours où il est.

#### b) Ce que la RE a établi sur le geste actuel `[FAIT]`

- **La sélection de piste est aujourd'hui un MENU**, pas un pad : `TrackSelectionView` est
  construite en `0x4001bb06` (constructeur `0x40023a7a`, vtable **`0x40100edc`**), et sa méthode
  `0x40023d94` fabrique **une entrée par piste**, gardée par `moveq #5` (`0x40023d98`), avec la
  chaîne `0x4012691c`.
- **La carte des LEDs est un `bitset<54>`** : la méthode `0x40023d18` fait exactement un
  `bitset::set` (`moveq #53,%d2` borne le bit, `orl %d1,%a2@(0,%d2:l:4)` pose le bit ; la chaîne
  « bitset::set » est en `0x40125ed9`). **C'est le point d'accroche de l'affichage de page** :
  allumer 1–2 au lieu de 1–6 sur la page 2.
- Le **tableau des pads** (`0x404a8ba0`) et la **table de recherche de LED** (`0x404a8c68`) sont
  en **BSS** (nuls dans l'image, remplis à l'exécution) — donc leur *contenu* ne se lit pas
  statiquement, seulement leur *usage*.
- **Le mot « Page » existe déjà dans l'interface** : la chaîne `0x4012691c` dit
  « Undo Paste / **Paste Page** / Paste %d Trig%s / Undo Clear », et `[PAGE]` seul fait déjà
  défiler les **64 pas** (4 pages de 16). La « page de pistes » est donc une **seconde notion de
  page**, à ne pas confondre avec celle des pas — à garder clair dans le code et dans le guide.
- La chaîne `0x40125ed9` contient aussi « **Erase all locks** » / « **Erase locks** » — les
  actions d'effacement des verrous de paramètres, utiles au volet « pattern » (§3.26).

#### c) Ce qui reste à décoder pour poser le geste `[HYP]`

1. **Les codes de touche** de `[TRACK]` et de `[PAGE]`, et donc **si `[TRACK]`+`[PAGE]` est
   libre** — c'est la vérification indispensable avant d'y accrocher la bascule de page ;
2. le **`consumeKeyEvent`** de la vue (dans la vtable `0x40100edc`) pour voir la forme exacte du
   traitement des combinaisons ;
3. la **correspondance pad → piste** (probablement une table en BSS) à rendre dépendante de la page.

**Aucun de ces trois points ne remet en cause la conception** : ils disent *où* écrire, pas *quoi*.

### 3.33 `[TRACK]`+`[PAGE]` : la combinaison semble **libre** `[FAIT]`/`[HYP]` (14/10)

`build/re8/probe_key.py` .. `probe_key7.py`.

#### a) Le panneau, d'après le manuel (source externe, à confirmer sur la machine)

| Combinaison | Fonction documentée |
|---|---|
| `[FUNC]` + **`[TRACK]`** | ouvre le menu **TRACK SETUP** |
| `[FUNC]` + **`[PAGE]`** | ouvre le menu **SCALE** (pattern / track) |
| `[FUNC]` + `[RETRIG]` | ouvre le menu RETRIG SETUP |
| **`[TRACK]` + `[T1]`..`[T6]`** | **sélectionne la piste** |
| `[PAGE]` seul | défile les 64 pas (4 pages de 16) |

Et — **correction utile au §3.31** : **les six pads SONT les boutons de piste `T1`–`T6`** ✓.
Le tableau de pads de `0x404a8ba0` et la boucle `moveq #6` de `0x4001cf8c` sont donc bien
**le tableau des pistes**, et la conception de Kevin (« T1 et T2 ») porte exactement sur eux.

**`[TRACK]` + `[PAGE]` n'apparaît dans aucune combinaison documentée** → la bascule de page de
Kevin ne devrait **rien écraser**. C'est une bonne nouvelle, mais ce n'est **pas encore prouvé
dans le code** (voir d).

#### b) Ce que le code confirme

- Le menu **Track Setup** est construit par **`0x4003e020`** (titre « Track Setup » en
  `0x4012774d`, vue `TrackMenuView`) ;
- il est appelé depuis **`0x4001c510`**, dans la **zone du panneau** (`0x4001cxxx`, celle de
  `PadsView`) — c'est donc le chemin `[FUNC]`+`[TRACK]` ;
- le menu **Scale Setup** est construit en **`0x4002f350`** (« Scale Setup » en `0x40126fc3`,
  `ScaleMenuView`) — le chemin `[FUNC]`+`[PAGE]` ;
- la **répartition des touches est pilotée par des prédicats** (`0x40072490`, `0x400724a0`)
  appelés avec l'événement : les **codes de touche ne sont donc pas des littéraux** dans le
  gestionnaire, ils sont lus dans la structure `KeyEvent`.

#### c) L'automate d'interface — utile pour la suite

L'image contient des commandes `#UI_AUTOMATOR_*`, dont **`#UI_AUTOMATOR_EVENT_STREAM_ON`** : le
flux d'événements du panneau peut être **diffusé**, ce qui donne un moyen d'**observer les codes
de touche en fonctionnement** plutôt que de les deviner. Autres commandes notables :
`#MMC_RECONFIGURE`, `#FORMAT_FILE_SYSTEM` (le +Drive est bien de l'**MMC**), `#CONTENT_UPLOAD`,
`#MRV_DUMP`/`#MRAM_DUMP`, `#READ_FIRMWARE_MODEL`.

#### d) Ce qui reste pour **prouver** que la combinaison est libre `[HYP]`

1. lire le champ « code de touche » de `KeyEvent` (et donc les codes de `[TRACK]` et `[PAGE]`) ;
2. suivre le chemin `[TRACK]` **maintenu** + pad (la sélection de piste actuelle) : c'est là que
   la **page** devra s'insérer ;
3. vérifier qu'aucun prédicat ne traite déjà `[TRACK]`+`[PAGE]`.

**La conception n'est pas menacée** : au pire, si la combinaison s'avérait prise, il suffirait de
lui en préférer une autre (par exemple `[FUNC]`+`[TRACK]`+pad), sans changer la page elle-même.

### 3.34 Le panneau : bornes, gestion des touches, et un piège à éviter `[FAIT]`/`[HYP]` (14/10)

`build/re8/probe_pad.py` .. `probe_pad4.py`.

#### a) Dix bornes de plus dans la zone du panneau (`0x4001b000..0x4001e000`)

| Adresse | Forme | Rôle |
|---|---|---|
| `0x4001b086`, `0x4001b092` | boucles `moveq #6` | listes de 6 |
| `0x4001b52a` | garde `moveq #6` | |
| **`0x4001b696`** | **bornage ≤ 5** | **PIÈGE : c'est la MACHINE, pas la piste** (voir b) |
| `0x4001cfb6` | boucle `moveq #6` | le tableau des pads/pistes (§3.31.b) |
| `0x4001d5d2`, `0x4001d74e` | boucles `moveq #6` | mises à jour par pad |

#### b) **Le piège** : `0x4001b696` n'est pas une borne de piste `[FAIT]`

```
4001b68c  asrl #8,%d0
4001b696  moveq #5,%d1
4001b698  cmpl %d0,%d1
4001b69a  bges 0x4001b69e
4001b69c  moveq #5,%d0            ; bornage a 5
4001b6a0  lsll #2,%d1             ; d1 = d0 * 4
4001b6a2  lsll #5,%d0             ; d0 = d0 * 32
4001b6a4  subl %d1,%d0            ; d0 = d0 * 28
4001b6a6  addl 0x40fe384c,%d0     ; base + index * 28
```

L'index est multiplié par **28** puis ajouté à une base : c'est le **descripteur de machine**
(28 octets, §3.29.d), pas une piste. **Il ne faut pas l'élargir** : ce serait une corruption
silencieuse. C'est exactement le genre de fausse borne qu'il fallait trier — et elle confirme que
le nombre **6 = machines** est partout mêlé au nombre **6 = pistes**.

#### c) La forme de la gestion des touches `[FAIT]`

- `PadsView` a trois méthodes propres : **`0x4001d506`**, `0x4001d180`, `0x4001d3de`
  (vtable `0x401001d8`, les autres entrées étant des stubs `0x40075fxx`) ;
- `0x4001d506` est le gestionnaire d'événements : il appelle `0x4007240c(événement)` et compare
  le résultat à **2** puis **4** (`0x4001d522`, `0x4001d53c`) — donc le **type d'événement**
  (appui / relâchement), puis un prédicat `0x400724a0`, et il mémorise un état de maintien en
  `a2@(112)` ;
- `0x4001d590` parcourt les **6 pads** et appelle une méthode virtuelle par pad — c'est la mise à
  jour **par pad** (l'endroit naturel pour l'affichage de page) ;
- juste avant la vtable, une petite table **`1, 2, 3, 4, 5, 0x1b`** en `0x401001d8`.

#### d) Le bilan du volet « interface » `[FAIT]`

| Élément | État |
|---|---|
| Bornes « 6 » recensées | **21** (11 en `0x4002xxxx` §3.31.c, 10 en `0x4001bxxx` §3.34.a) |
| Pièges identifiés | `0x4001b696` (machine) ; le nombre 6 = machines mêlé partout |
| Affichage de page | crochet trouvé : `bitset<54>` + `bitset::set` (`0x40023d18`) |
| Les 6 pads = T1–T6 | confirmé (manuel + tableau `0x404a8ba0`) |
| Combinaison `[TRACK]`+`[PAGE]` | non documentée → **libre a priori** |
| Chemin **pad → piste** | **pas encore épinglé** `[HYP]` |

Le chemin pad → piste reste le dernier point : il est **événementiel et réparti sur plusieurs
couches** (le gestionnaire principal `MainScreenView::consumeKeyEvent`, puis les vues), ce qui le
rend plus long à lire que le reste. **Il ne bloque pas la conception** : il dit où poser la page,
pas ce qu'est la page.

### 3.35 Le format **rangé** (packed) décodé — et il simplifie tout `[FAIT]` (14/10)

`build/re8/probe_pack.py`.

#### a) Les deux formes, côte à côte

Les copies par piste le disent :

- **`0x4005b4ec` : rangé → déployé** (A → B), appelée **par piste** ;
- **`0x4005b642` : déployé → rangé** (B → A) ;
- appelantes : `0x4005b8e2` (A→B, chargement d'un pattern) et `0x4005ba42` (B→A).

La boucle appelante (`0x4005b8a0`) est explicite :

```
4005b8de  lea   %a3@(4),%a4          ; les données rangees commencent a +4
4005b916  addil #722,%d2             ; <<< PAS PAR PISTE : 722
4005b91c  cmpil #4332,%d2            ; jusqu'a 4332 = 6 x 722
4005b924  pea   %a3@(4336)           ; la queue (les verrous) a +4336
4005b946  movel %sp@(44),%a2@(30706) ; le champ a +30706 (valeur 7 bits)
```

**Le pas par piste est 722 dans les DEUX formes** ✓ — et l'offset de la queue est **4336 dans les
deux** ✓. La copie A→B ne fait que **permuter les champs à l'intérieur du bloc de 722 octets** :

| rangé | → déployé |
|---|---|
| 0..128 (64 **mots**, un par pas) | 0..128 (copie telle quelle) |
| 128, 192, 256, 320, 384, 448, 512, 576, 640 | 580, 256, 516, 128, 192, 644, 320, 384, 448 |

puis la queue, avec des **bornages** (`min`/`max` sur `a1@(715)`, `a1@(718)`, …) et un tableau de
64 mots pour le champ de pas.

#### b) Les tailles — et l'arithmétique tombe juste

| | Formule | Valeur |
|---|---|---|
| **rangé** | `4 + N × (722 + 1752)` = `4 + N × 2474` | 6 pistes → **14848** |
| **déployé** | `4 + N×722 + N×4385 + 64` | 6 pistes → **30710** |

`14848 − 4336 = 10512` et **`10512 / 6 = 1752` exactement** ✓ ; **`4 + 6 × 2474 = 14848`** ✓ ;
`26310 / 6 = 4385` ✓ (`4385 = 64 × 68 + 33`). Les deux formes sont donc **par piste** de bout en
bout, et **les pas ne changent pas** : seuls les **compteurs** changent.

#### c) Le jeu de changements **révisé** — plus simple que prévu

| Constante | Avant | Après | Note |
|---|---|---|---|
| pas par piste | 722 | **722** | **inchangé** ✓ |
| queue déployée / piste | 4385 | **4385** | **inchangé** ✓ |
| queue rangée / piste | 1752 | **1752** | **inchangé** ✓ |
| `4332` (6×722) | 4332 | **5776** | 8×722 |
| `4336` (offset queue) | 4336 | **5780** | |
| **`14848`** (bloc rangé) | 14848 | **19796** | `4 + 8 × 2474` — **constante à ajouter au jeu** |
| `30710` (record déployé) | 30710 | **40924** | |
| `7094` (kit) | 7094 | **7294** | +2 × 100 |
| `600` (borne des kits) | 600 | **800** | 8 × 100 |
| nombre de patterns | 96 | **80** | garde `moveq #95` → `#79` |

#### d) L'image projet **grandit de 60 768 octets** — et c'est tout

L'image contient les patterns rangés **et** les kits :

- rangés : 80 × 19796 = 1 583 680 (au lieu de 96 × 14848 = 1 425 408) → **+158 272** ;
- kits : 80 × 7294 = 583 520 (au lieu de 96 × 7094 = 681 024) → **−97 504** ;
- **total : 2 224 484 au lieu de 2 163 716 → +60 768** ✓ (les 80 patterns compensent presque la
  croissance).

Conséquences sur la disposition (§3.29.a) :

- l'**image** passe à 2 224 484 → **l'en-tête et les patterns se décalent de 60 768** ;
- la table des patterns (80 × 40924 = 3 273 920) finit **au-delà** de l'ancienne zone des kits →
  les **kits déménagent** (583 520 o, vers la plage de 704 Ko à `0x43dd0000`) ;
- les **littéraux de base** changent : en-tête `0x406fa024` → `0x4070b1a4`, patterns `0x406fa040`
  → `0x4070b1c0` (à recompter précisément dans le générateur).

**La place au +Drive reste confortable** : l'image ne prend que +60 768 octets (§3.30 : ~826 Mo de
marge) ✓.

### 3.36 Triage des sites du « pattern » — l'inventaire avant d'écrire `[FAIT]` (14/10)

`build/re8/probe_triage.py`, `probe_triage2.py`. **Aucune écriture n'a encore été faite** :
cette étape établit *où* écrire, avec l'instruction de chaque site.

#### a) Les sites d'**immédiat 32 bits** (balayage par valeur, opérande vérifié)

| Constante | Avant → Après | Sites réels | Forme |
|---|---|---|---|
| `4332` | → 5776 | **21** | 17 `cmpi.l`, 4 `addi.l` |
| `14848` | → 19796 | **19** | 15 `addi.l`, 4 `move.l` |
| `30710` | → 40924 | **12** | 7 `move.l`, 5 `addi.l` |
| `7094` | → 7294 | **8** | 6 `move.l`, 2 `addi.l` |
| `600` | → 800 | **7** | 7 `cmpi.l` |
| taille d'image | 2163716 → 2224484 | **20** | `move.l #…,-(a7)` |
| base des patterns | `0x406fa040` → +60768 | **6** | 4 `addi.l`, 1 `lea.l` |
| **en-tête de projet** | `0x406fa024` → +60768 | **7** | 6 `pea.l`, 1 `cmpi.l` |
| base de l'image | `0x404e9c20` (inchangée) | **9** | 8 `pea.l`, 1 `move.l` |
| **offset des kits** | `2948188` → à recalculer | **6** | 2 `addi.l`, 3 `adda.l`, 1 `addi.l` |

#### b) Les sites de **déplacement 16 bits** (le balayage 32 bits les rate)

| Déplacement | Avant → Après | Sites | Forme |
|---|---|---|---|
| `4336` (queue) | → 5780 | **7** | `pea.l $10f0(aN)` |
| `30706` (champ 7 bits) | → 40920 | **4** | `move.l $77f2(aN)` |
| `30642` | → 40856 | **3** | `pea.l $77b2(aN)` |
| `14736` | → 19684 | **8** | `pea.l`/`lea.l $3990(aN)` |
| `7094` | → 7294 | **9** | `pea.l $1bb6.w` (dont le `lea` de 0x4005d55a) |
| `722`, `4385` | **inchangés** | 20 / 10 | pas de changement (par piste) |
| `2474`, `1752`, `19796` | — | **0** | valeurs *calculées*, jamais écrites ✓ |

#### c) Le triage a évité deux pièges

1. **`600` a 27 sites de déplacement** — mais ce sont des coïncidences (`clr.l $258(a2)`,
   `move.l $258(a0),d0`, …) : **seuls les 7 `cmpi.l`** sont la borne des kits ✓ ;
2. **`0x409c9a00` n'a AUCUN site** ✗ — la base des kits n'est pas un littéral. Le code la
   **calcule** : en `0x4000ea46`, `d2` est une base d'exécution, la boucle fait
   `addil #30710,%d3` jusqu'à `cmpil #2948160` (96 × 30710) et lit `a3@(0,%d3)` avec
   `a3 = d2 + 28` ; l'offset des kits est `2948188` **relatif à cette même base**. Comme
   `d2 + 28` = la table des patterns et `28` = l'en-tête, **la base est l'en-tête de projet**
   (`0x406fa024`), les patterns suivent à +28 et les kits à +2948188.

**Conséquence, et c'est important** : le déménagement des kits n'est **pas** une réécriture de
base (il n'y en a pas) mais **une seule valeur d'offset** (`2948188`), répétée 6 fois. Un offset
de 32 bits peut viser n'importe où ✓ — donc les kits peuvent bien partir vers la plage de 704 Ko
à `0x43dd0000` ✓, sans toucher aux patterns.

#### d) Ce qui reste à trier avant d'écrire

- le **nombre de patterns** : `moveq #95` (`0x400083ba`) et ses jumelles (`#96`) — non balayés ici,
  car `96` est une valeur trop commune pour un scan brut : il faut trier par instruction ;
- les sites de **`14848` en déplacement** (39 relevés, dont des coïncidences à écarter).

### 3.37 Le générateur du jalon « pattern » — et un arrêt net là où la preuve manque `[FAIT]`/`[HYP]` (14/10)

`tools/gen_groove_pattern.py` → `tweaks/model-cycles_OS1.13/57-groove-patterns.json`.
C'est un **fichier de jalon distinct** de `56-groove-8tracks.json`, pour que l'artefact prouvé du
jalon 1 reste intact ; les deux s'appliquent dans l'ordre (56 puis 57).

#### a) La disposition est **arrêtée** `[FAIT]`

| | Avant | Après |
|---|---|---|
| image projet | 2 163 716 | **2 224 484** (+60 768) |
| en-tête de projet | `0x406fa024` | **`0x40708d84`** |
| table des patterns | `0x406fa040` | **`0x40708da0`** |
| kits | en-tête + 2 948 188 | **`0x43dd0000`**, offset **57 438 844** |

Le générateur calcule ces valeurs ; elles remplacent mes estimations à la main du §3.35.d
(l'arithmétique de l'outil fait foi).

**Le logement des kits est justifié** : dans la plage de 720 896 o à `0x43dd0000`, **tous** les
littéraux sont regroupés à la toute fin (`0x43e80001..0x43e8ffff`) — donc
`0x43dd0000..0x43e80000` est **entièrement sans littéral**, et les kits (583 520 o) y tiennent
avec ~137 Ko de reste ✓.

#### b) Les familles de sites, et les compteurs contrôlés `[FAIT]`

13 familles d'**immédiats** (21, 1, 19, 12, 8, 7, 2, 1, 8, 20, 6, 7, 6 sites — conformes au
triage du §3.36) et 7 familles de **déplacements** : 4 en mode *registre* (4336 : 7, 30706 : 4,
30642 : 3, 14736 : 8) et 3 en mode *absolu* (7094 : 7, 600 : 6, 14848 : 30) → **184 écritures**.

#### c) **L'arrêt net** : le tri n'est pas une preuve `[HYP]`

Le partage « absolu / registre » est un **premier filtre**, pas une démonstration : il suppose
qu'une taille est toujours poussée en absolu et qu'un décalage d'enregistrement est toujours à
registre. Or :

- `lea.l $1bb6(a4),a4` (`0x4005d55a`) ressemble à un **pas de kit** (7 094) qui devrait changer ;
- `pea.l $3a00(a2)` (`0x4005e2be`) et `pea.l $3a00(a5)` (`0x4005ee5c`) poussent `a2 + 14848`,
  c'est-à-dire peut-être **le bloc suivant** — à changer aussi ;
- à l'inverse, les déplacements de `600` sont pour la plupart des **coïncidences**
  (`clr.l $258(a2)`) qu'il ne faut **pas** toucher.

Les compteurs « conformes » du §b sont donc **partiellement circulaires** : je les ai fixés à
partir du même filtre. Il reste **~11 sites en mode registre** à revoir un par un pour `7094`,
`600` et `14848`.

**En conséquence, l'outil refuse d'écrire** : `REVIEW_PENDING = True` fait échouer
`gen_groove_pattern.py` (code 1, aucun fichier écrit) tant que la revue n'est pas faite ; un
`--draft` explicite est nécessaire pour écrire malgré tout. **Aucun firmware incomplet ne peut
donc être construit à partir de ce JSON.** C'est le même principe que la règle du dépôt : une
preuve manquante arrête la ligne, elle ne la contourne pas.

#### d) La suite, dans l'ordre

1. **revoir les ~11 sites en mode registre** (§c), ajuster les compteurs, puis lever
   `REVIEW_PENDING` ;
2. écrire le JSON, `--check`, et **prouver en émulation** (`tools/re/test_groove_pattern.py` :
   pattern 8 pistes chargé, joué, sauvegardé, relu) ;
3. le **convertisseur v6 → v7** (§3.29.f) et le sort de la **banque F** (§3.27) ;
4. l'**interface** : la page de pistes (§3.32).

### 3.38 La revue des sites en mode registre — faite, et le JSON écrit `[FAIT]` (14/10)

`build/re8/probe_review.py`, `probe_review2.py`.

#### a) Le verdict, site par site (21 sites en mode registre)

| Valeur | Sites | Verdict |
|---|---|---|
| **7094** | 2 | **1 vrai** : `lea.l $1bb6(a4),a4` (`0x4005d55a`) — une **boucle qui avance de 7 094** (`moveq #$60`/`addq` autour) = **le pas des kits, à changer** ; 1 coïncidence de données |
| **600** | 13 | **aucun vrai** : tous des **champs d'objets** (`clr.l $250/254/258/25c(a2)` en série, `move.l $258(a0),d0`, …) → **à laisser** |
| **14848** | 9 | **4 vrais** : `cmp.l $3a00(a2),d0` (`0x4005e268`, compare le **pattern suivant**), `pea.l $3a00(a2)` (`0x4005e2be`) et `pea.l $3a00(a5)` (`0x4005ee5c`, poussent le **bloc suivant**), `lea.l $3a00(a4),a4` (`0x4008db14`, boucle bornée par `moveq #$60` = 96) ; 5 coïncidences |

Les **7 coïncidences** (1 pour 7094, 6 pour 14848) sont toutes dans la **zone de données** de
l'image, et vérifiées une par une : leurs octets voisins sont des `.short` (de la donnée que le
désassembleur décode comme du code). Elles sont écartées nommément dans le générateur
(`EXCLUDE`), avec leur raison.

**Compteurs finaux** : 7094 → **8** sites, 600 → **6**, 14848 → **33**. `REVIEW_PENDING` est levé.

#### b) Le JSON est écrit, et il est vérifié `[FAIT]`

```
python3 tools/gen_groove_pattern.py --cycles model-cycles_OS1.13.syx
python3 tools/gen_groove_pattern.py --cycles model-cycles_OS1.13.syx --check
```

**188 écritures**, `--check` vert. Chaque site est vérifié octet à octet contre l'image
d'origine, et le générateur **refuse** d'écrire si un compteur de famille ne correspond pas à la
revue (c'est ce qui a attrapé mes deux erreurs d'adresse pendant cette étape).

#### c) Les deux tweaks Groove ensemble `[FAIT]`

`build/re8/check_both.py` :

| | |
|---|---|
| `56-groove-8tracks.json` | 179 écritures |
| `57-groove-patterns.json` | 188 écritures |
| **intersection** | **0** ✓ |
| octets modifiés | 1 324 |
| **MAIN OS Groove (56 + 57)** | **`3dd3ddb7c7ea6073999d9ddaa2e5881909f3074219e6a2a58918ace6c60b861d`** |

**Ce hash n'est PAS publié comme jalon** : le jalon 2 est **construit**, pas encore **prouvé en
émulation** — et la règle du projet est qu'un jalon ne publie son hash qu'une fois prouvé. Il
n'entre donc pas encore dans `BUILD.md`.

#### d) La suite immédiate

**Prouver le jalon 2 en émulation** : `tools/re/test_groove_pattern.py` — charger un pattern à
huit pistes, le jouer, le **sauvegarder**, le **relire** et vérifier que les pistes 7-8
reviennent intactes, avec les pistes 1-6 identiques à l'origine (le même esprit que le banc du
jalon 1). Ensuite : le convertisseur v6 → v7 et la banque F, puis la page de pistes.

### 3.39 Le banc du jalon 2 — et ce qu'il a trouvé tout de suite `[FAIT]`/`[HYP]` (14/10)

`tools/re/test_groove_pattern.py`, `build/re8/diag_unpack.py`.

Le banc appelle le **vrai code de l'OS** : `0x4005b894(a2 = enregistrement déployé, a3 = enregistrement
rangé)` — la boucle de dépliage d'un pattern, celle dont le générateur change le **pas** (722,
inchangé) et la **borne** (4332 → 5776), plus le gestionnaire de queue `0x4005b766`. Trois images :
stock, jalon 1 seul, **les deux**.

#### a) Ce que le banc **établit déjà** `[FAIT]`

- les deux tweaks **ne se recouvrent pas** (intersection 0) et les constantes du format sont bien
  celles du tweak — relues dans l'image : `4332 → 5776` ✓, `4336 → 5780` ✓ ;
- **le bloc des pas (0..4332) se déplie à l'identique dans le stock et dans Groove** ✓✓ : les pas
  des pistes 0-5 sont **inchangés** par le jalon 2 — c'est le contrôle le plus important pour ne
  pas casser l'existant, et il passe.

#### b) Ce qu'il a **trouvé** — une vraie information `[FAIT]`

`0x4005b894` prend un **troisième argument**, qu'il range en `+30706` de l'enregistrement :

```
4005b946  movel %sp@(44),%a2@(30706)
```

Je l'ai passé en bouillie (le banc n'empile que deux arguments), donc **tout le volet « queue » du
banc n'est pas encore significatif**. Le diagnostic (`diag_unpack.py`) le montre crûment : les
écritures s'arrêtent à l'offset **4135**, c'est-à-dire dans le **bloc des pas**, et l'étendue de
la queue varie d'une image à l'autre sans logique lisible.

#### c) Une **suspicion** à lever, et elle compte `[HYP]`

Le **nombre de pistes du gestionnaire de queue** (`0x4005b766`) n'apparaît **pas** dans le jeu de
changements du §3.35.c : la queue est par piste (pas 4385, **inchangé**), mais **combien de pistes**
le gestionnaire parcourt-il ? Le banc, dans son état actuel, donne une queue Groove d'environ
**sept** pistes avec la piste 7 **vide** — ce qui est exactement le symptôme d'une **borne de
comptage non élargie**. Ce n'est pas une conclusion (le troisième argument manque), mais c'est une
piste sérieuse, et elle irait dans le sens d'un **trou** dans le jeu de changements.

#### d) L'état, sans embellissement

**Le jalon 2 est construit, pas prouvé** — et il pourrait être **incomplet**. Le JSON de
`57-groove-patterns.json` est donc versionné **avec sa mise en garde** (§3.38.c : hash non publié,
absent de `BUILD.md`), et le banc **échoue** tant que le troisième argument n'est pas fourni.

**La suite, dans l'ordre :**
1. trouver le **troisième argument** de `0x4005b894` (son appelant : `0x4005b924` appelle le
   gestionnaire de queue, mais qui appelle `0x4005b894` ?) et ce que `+30706` signifie ;
2. lever la suspicion du §c en lisant la **borne de comptage du gestionnaire de queue** ;
3. compléter le jeu de changements si elle manque, régénérer, et **re-prouver** ;
4. l'aller-retour complet (déplier puis **replier** = la sauvegarde), puis le convertisseur
   v6 → v7 (banque F), puis la page de pistes.

### 3.40 Le banc a trouvé **deux bornes oubliées** — dont une corrigée, une qui reste `[FAIT]`/`[HYP]` (14/10)

`build/re8/probe_arg3.py`, `probe_gap.py`, `probe_b5.py`.

#### a) Le troisième argument, et le premier trou `[FAIT]`

`0x4005b894` est appelé depuis `0x4000ffe2`, `0x4005d4d2` et `0x4005e2b6`, avec **trois**
arguments ; le troisième est rangé en `+30706` de l'enregistrement. **Il n'est lu ni par le
dépliage ni par le gestionnaire de queue** : le banc le fournit désormais explicitement (0), mais
il n'était pas la cause de l'échec.

La cause, elle, était nette : le **gestionnaire de queue** (`0x4005b766`) parcourt les pistes avec

```
4005b7be  addil #4385,%d0
4005b7c4  cmpil #26310,%d0        ; <<< 6 x 4385 = 26310
...
4005b802  cmpil #26310,%d3        ; <<< et de nouveau
```

**`26310` manquait au jeu de changements** ✓ — c'est le trou que le banc soupçonnait. Il a
**3 sites** (`0x4005b7c6`, `0x4005b804`, `0x40061594`) et devient **35 080 = 8 × 4385**. Vérifié :
`10512` (la queue **rangée**) n'a **aucun** site — pas de trou de ce côté ✓.

**Après la correction, le banc passe le contrôle B** ✓ : la queue déployée de la **piste 7** est
désormais remplie (2 076 / 2 176 mots `0xFFFF`), et **rien** en stock ✓✓.

#### b) Le second trou, trouvé en lisant le gestionnaire `[HYP]`

Le gestionnaire **décode aussi** les verrous rangés : il lit les deux premiers octets d'une entrée
et **valide l'index de piste** qu'elle contient :

```
4005b810  moveb %a2@,%d0          ; index de PAS (borne 32)
4005b812  moveb %a2@(1),%d4       ; index de PISTE
4005b820  moveb #5,%d5
4005b824  cmpl  %d1,%d5
4005b826  bcss  0x4005b87c        ; <<< l'index de piste doit etre < 5
```

**`moveb #5` doit devenir `moveb #7`** ✓ — sinon les verrous des pistes 6-7 sont **rejetés** ✗.
L'image contient **six** sites `moveb #5,%dN` : `0x400411ee`, `0x400596a0`, `0x4005cde0`,
`0x40061048`, `0x400aad6c` et celui-ci (`0x4005b820`). **Un seul est identifié** ; les cinq autres
doivent être revus (certains sont peut-être la même borne dans le chemin de **sauvegarde**).

#### c) Pourquoi C et D échouent encore — et ce n'est pas qu'un trou

Mes **données de test** sont aussi en cause : le gestionnaire lit la queue rangée comme des
**entrées de verrou** (index de pas < 32, index de piste ✓), et ma queue synthétique contient des
octets quelconques ✗ — d'où des écritures à des endroits arbitraires (`diag_unpack.py` : 27 octets
non nuls après la piste 5 **en stock**). Le banc doit donc fabriquer une queue rangée
**réaliste** (des entrées de verrou valides pour les pistes 0-7) avant que C et D aient un sens.

#### d) L'état — le JSON est **retiré**

`57-groove-patterns.json` **n'est pas versionné** : le jeu de changements est incomplet (borne
`#5`), donc un firmware construit à partir de lui serait **faux** (les verrous des pistes 6-7
perdus). Le générateur **refuse à nouveau d'écrire** (`REVIEW_PENDING = True`), avec le motif.
Ce qui est acquis reste acquis : le générateur reproduit **191 écritures vérifiées**, la disposition
est arrêtée, et **le banc a fait son travail** — il a trouvé, avant toute machine, deux bornes que
la lecture statique avait manquées.

#### e) La suite, précise

1. **revoir les six sites `moveb #5`** et appliquer `#5 → #7` là où c'est l'index de piste ;
2. **rendre la queue rangée du banc réaliste** (entrées de verrou valides, pistes 0-7) ;
3. régénérer, `--check`, **re-prouver** (B, C, D) ;
4. l'aller-retour complet (déplier puis **replier** = la sauvegarde) ;
5. le convertisseur v6 → v7 (banque F), puis la page de pistes.

### 3.41 Les six sites `moveb #5` revus — et le contrôle C qui reste inexpliqué `[FAIT]`/`[HYP]` (14/10)

`build/re8/probe_b5b.py`, `probe_g5.py`.

#### a) Revue des six sites `moveb #5,%dN` `[FAIT]`

| Site | Contexte | Verdict |
|---|---|---|
| **`0x4005b820`** | le gestionnaire de queue : index de piste **encodé** dans les verrous | **la borne de piste → `#7`** ✓ |
| `0x400596a0` | écrit 5 dans `0x40a78e10` | **un compteur à rebours** (`movel 0x40a78e10,%d0` / `bles` / `subql #1` / … → pose un drapeau à zéro), **pas une borne de piste** ✗ |
| `0x400411ee` | `movel %d0,%a2@(112)`, un objet de voix | sans rapport ✗ |
| `0x4005cde0` | compare une valeur de table (« genre ») | sans rapport ✗ |
| `0x40061048` | un cas de commutation (`beqw`/`bnew`) | sans rapport ✗ |
| `0x400aad6c` | contexte EMAC / note (`moveq #27`, `lsll`) | sans rapport ✗ |

**Une seule correction, donc** : `moveb #5,%d5` → `moveb #7,%d5` en `0x4005b820` (4 octets,
`1a3c0005` → `1a3c0007`). Le jeu de changements passe à **192 écritures**.

#### b) Ce que ça donne `[FAIT]`

- **contrôle A** : ok (les deux tweaks sans recouvrement, constantes patchées) ;
- **contrôle B : PASSE** ✓ — la queue déployée de la **piste 7** est remplie
  (2 076 / 2 176 mots `0xFFFF`) et **rien** en stock : le dépliage couvre bien **huit pistes** ;
- **contrôle D** : s'améliore (27 → **4** octets non nuls après la piste 5 en stock).

#### c) Le **contrôle C reste en échec**, et je ne l'explique pas encore `[HYP]`

Le **bloc des pas (0..4332) est identique** ✓ — mais les **queues des pistes 0-5 diffèrent**
entre le stock et Groove ✗. Deux lectures possibles, et je ne tranche pas :

1. **mes données de test sont encore en cause** : la queue rangée est mise à zéro, et le
   gestionnaire la lit comme des **entrées de verrou** ; une entrée nulle peut être interprétée
   et écrire un verrou — différemment selon la borne `#5`/`#7` et les bornes de piste ;
2. **il reste un effet réel** du patch sur les queues 0-5, que la lecture statique n'a pas vu.

**Le contrôle C est le plus important du banc** (les pistes 0-5 ne doivent pas bouger) : tant
qu'il échoue, le jalon 2 **n'est pas prouvé**.

#### d) L'état

`57-groove-patterns.json` est **de nouveau retiré** (non versionné) et le générateur **refuse
d'écrire** (`REVIEW_PENDING = True`, motif : contrôle C). Acquis : **192 écritures vérifiées**,
la disposition arrêtée, le contrôle B qui passe, et **deux bornes trouvées par le banc** dont une
corrigée.

#### e) La suite, précise

1. **trancher le contrôle C** : écrire dans le banc une queue rangée **au vrai format** (entrées
   de verrou valides, pistes 0-7) — ou partir d'un pattern **réel** — pour que C mesure le patch
   et non mes données ;
2. si C passe : régénérer, `--check`, publier le hash du jalon 2, puis l'aller-retour complet
   (déplier → **replier** = la sauvegarde) ;
3. le convertisseur v6 → v7 (banque F), puis la page de pistes.

### 3.42 Le format **rangé** de la queue : une liste d'entrées de 130 o — et une **correction** `[FAIT]` (14/10)

`0x4005b766` (le gestionnaire de queue), seconde moitié : c'est **le format rangé des verrous**.

```
4005b80a  moveq #80,%d3             ; <<< 80 ENTREES
4005b810  moveb %a2@,%d0            ; +0 : index de PAS (borne 32)
4005b812  moveb %a2@(1),%d4         ; +1 : index de PISTE
4005b84e  movew %a2@(2,%a0:l),%d4   ; +2.. : 64 MOTS (128 o) de valeurs
4005b86a  cmpal #128,%a0
4005b878  moveb %d5,%a1@(4352)      ; un drapeau
4005b87c  subql #1,%d3              ; l'entree suivante
4005b87e  lea %a2@(130),%a2         ; <<< PAS D'UNE ENTREE : 130 OCTETS
```

#### a) La structure réelle

| | |
|---|---|
| une entrée rangée | **130 o** = 1 o de pas + 1 o de piste + **64 mots** |
| nombre d'entrées | **80** (`moveq #80`) |
| donc la queue rangée | `112 + 80 × 130` = **10 512** ✓ (le 112 est un en-tête) |
| la queue déployée | **26 310** = 6 × 4 385 ✓ — celle-là **est** par piste |

#### b) **La correction** : `1752` par piste était une **coïncidence** `[FAIT]`

Le §3.35.b concluait « queue rangée = 1 752 o par piste » parce que `10512 / 6 = 1752`
**exactement**. C'est vrai **arithmétiquement** et **faux structurellement** : la queue rangée
n'est **pas** découpée par piste — c'est une **liste plate d'entrées de 130 o**, chacune portant
son numéro de piste. Les 1 752 o par piste sont un artefact de la division.

**Conséquences, et elles sont réelles :**

1. la **taille rangée d'un pattern à 8 pistes n'est pas** `4 + 8 × 2474 = 19796` — elle dépend de
   la **queue rangée**, qui ne grandit **pas** forcément avec le nombre de pistes (elle dépend du
   **nombre d'entrées**, 80, pas du nombre de pistes) ;
2. il y a donc **deux grandeurs à revoir** : la taille du bloc rangé et **le nombre d'entrées**
   (`moveq #80`) — 80 entrées pour 6 pistes ; en faut-il plus pour 8, ou 80 est-il un maximum
   suffisant ?
3. **l'arithmétique de la disposition (§3.37) est à refaire** : l'image grandit de 60 768 dans
   mon calcul, mais ce chiffre reposait sur les 1 976 o par pattern.

#### c) Et **le contrôle C est expliqué** `[FAIT]`

Ma queue rangée synthétique plaçait les verrous « tous les 2 474 o » — alors que l'OS lit des
**entrées de 130 o** à partir de la base de la queue. Le désaccord était donc **dans mes
données**, pas dans le patch : c'est la lecture 1 du §3.41.c. Le banc doit fabriquer des entrées
au **vrai format** (130 o : pas, piste, 64 mots) — et c'est ce que cette lecture vient de rendre
possible.

#### d) L'état

`57-groove-patterns.json` reste **retiré** et le générateur **refuse d'écrire**. Mais le tableau
est plus clair qu'avant : le format rangé est **entièrement décodé** (entrée de 130 o, 80 entrées,
en-tête 112 o), et le contrôle C n'est plus un mystère.

#### e) La suite

1. **décider de la queue rangée à 8 pistes** : le nombre d'entrées (80) suffit-il, ou faut-il
   l'élargir (une borne de plus au jeu de changements) ?
2. **refaire l'arithmétique de la disposition** avec la vraie taille rangée ;
3. **donner au banc des entrées au vrai format** (130 o) et re-prouver A-D ;
4. l'aller-retour (déplier → replier = la sauvegarde), le convertisseur v6 → v7 (banque F), la page.

### 3.43 La queue rangée à huit pistes : **le compte d'entrées ne change pas** — et la taille rangée non plus `[FAIT]`/`[HYP]` (14/10)

`build/re8/probe_entries.py` (balayage capstone — **désynchronisé** dans cette zone : il ne trouve
même pas le `moveq #80` de `0x4005b80a` que je connais ; un balayage **par octets** sera nécessaire
pour confirmer le chemin d'écriture).

#### a) Le raisonnement, qui décide la question `[FAIT]`

Le gestionnaire de queue lit **au plus 80 entrées** (`moveq #80,%d3`) depuis la **base de la
queue**, et remplit tout le reste de la queue déployée avec `0xFFFF` (« pas de verrou »). Les
entrées sont une **liste plate**, chacune portant **son** numéro de piste : le compte de 80 est donc
un **budget de capacité par pattern**, **pas** une borne de piste.

**Conséquence** : pour huit pistes, **le budget de 80 entrées tient tel quel** — il est simplement
partagé entre huit pistes au lieu de six. C'est un comportement **d'origine**, inchangé par le mod.
**Aucune modification du compte d'entrées n'est nécessaire.**

Donc la **queue rangée reste 10 512 o**, et :

| | 6 pistes | 8 pistes |
|---|---|---|
| en-tête | 4 | 4 |
| pas (par piste) | 6 × 722 = 4 332 | **8 × 722 = 5 776** |
| queue rangée (plate) | **10 512** | **10 512** *(inchangée)* |
| **bloc rangé** | 14 848 | **16 292** |

#### b) **La correction du §3.35.d** `[FAIT]`

Le §3.35.d donnait un bloc rangé de `4 + 8 × 2474 = 19 796` — **faux**, parce qu'il reposait sur
la coïncidence « 1 752 o par piste » du §3.35.b. Le bon chiffre est **16 292**.

Ce que ça change :

| | §3.37 (faux) | **corrigé** |
|---|---|---|
| bloc rangé | 19 796 | **16 292** |
| image projet | 2 224 484 (+60 768) | **1 944 164** (−219 552 : elle **rétrécit**) |
| en-tête | `0x40708d84` | à recalculer (**il descend**) |
| table des patterns | `0x40708da0` | à recalculer |
| kits | déménagement | **à revoir** (l'aire totale ne grandit que de **8 704 o**) |

Le total (image + en-tête + patterns + kits) passe de 5 792 928 à **5 801 632**, soit **+8 704
octets** seulement — les 80 patterns compensant presque tout. **L'arithmétique de la disposition est
donc à refaire** (§3.37 est périmé), et le déménagement des kits est à réévaluer : il est peut-être
**petit**, voire inutile.

#### c) Ce qui reste **à vérifier** `[HYP]`

1. le **chemin d'écriture** (la sauvegarde) utilise-t-il le **même** compte (80) et le **même** pas
   (130 o) ? Un balayage **par octets** le dira (capstone se désynchronise ici) ;
2. la borne `#5 → #7` du §3.41 : elle est dans le **lecteur** ; y a-t-il l'équivalent dans
   l'**écrivain** ?

#### d) L'état

`57-groove-patterns.json` reste **retiré** ; le générateur **refuse d'écrire**. Les familles du jeu
de changements sont bonnes, **sauf** `14848 → 19796` qui doit devenir `14848 → 16292`, et toute la
disposition qui doit être recalculée.

#### e) La suite

1. balayage **par octets** du chemin d'écriture (compte 80, pas 130, borne de piste) ;
2. corriger le générateur (`14848 → 16292`) et **recalculer la disposition** ;
3. donner au banc des **entrées au vrai format** (130 o) et re-prouver A-D ;
4. l'aller-retour (déplier → replier), le convertisseur v6 → v7 (banque F), la page.

### 3.44 Le format rangé est **entièrement décodé**, la disposition **recalculée** — et le contrôle C à **4 octets** `[FAIT]`/`[HYP]` (14/10)

`build/re8/probe_bytes.py`, `diag_diff.py`, `probe_bisect.py`, `probe_bisect2.py`, `diag_t5.py`.

#### a) L'écrivain utilise **le même** compte et **le même** pas `[FAIT]`

Balayage **par octets** (capstone se désynchronise dans cette zone) :

```
4005b98a  cmpil #10400,%d0        ; 80 x 130 : l'aire des entrees (inchangee)
4005bafe  moveq #80,%d6           ; le chemin d'ecriture : 80 entrees
4005bb00  lea   %a1@(130),%a1     ; pas de 130 o
4005cdbc  moveq #80,%d0 / lea %a2@(130),%a2   ; le chemin de conversion aussi
```

Lecteur et écrivain partagent **80 entrées de 130 o** ✓ — donc **aucune borne à ajouter** de ce
côté : la queue rangée reste **10 512 o**, et le bloc rangé à 8 pistes est **16 292 o**.

#### b) La disposition, **recalculée** `[FAIT]`

| | valeur |
|---|---|
| bloc rangé | **16 292** (4 + 8×722 + 10 512) |
| image projet | **1 944 164** (elle **rétrécit** de 219 552) |
| en-tête | **`0x406c4684`** |
| table des patterns | **`0x406c46a0`** |
| kits | **`0x43dd0000`** (offset 57 719 164 relatif à l'en-tête) |

Les kits ne tiennent plus juste après les patterns (ils dépasseraient l'ancienne aire de ~10 Ko,
dans une zone citée par 2208 littéraux) → ils vont dans la **plage libre** de 720 896 o à
`0x43dd0000` (aucun littéral jusqu'à `0x43e80000`, §3.37.a). Le jeu de changements passe à
**192 écritures** (dont `14848 → 16292` et `14736 → 16180`).

#### c) Le banc : A, B, D **passent**, C est à **4 octets** `[HYP]`

Le banc a été corrigé sur trois points, tous **de son côté** (le patch n'y était pour rien) :

1. le **pas rangé** : les pas sont **contigus** (722 o par piste à partir de +4), pas espacés de
   2 474 (§3.35.b était faux) ;
2. l'**offset de la queue déployée** : `n × 722` — **4 332** à 6 pistes, **5 776** à 8 (le bloc
   déployé n'a pas d'en-tête ; c'est ce que fait l'appelant : `addil #4332,%d2`) ;
3. **chaque image reçoit un enregistrement rangé à SON format** (6 pistes pour le stock, 8 pour
   Groove) : sinon le stock lisait sa queue **au milieu des pas de la piste 6**, ce qui faussait C.

Résultat :

| contrôle | état |
|---|---|
| A. image, constantes, non-recouvrement | **ok** |
| B. le dépliage couvre **huit** pistes (queue de la piste 7 remplie) | **ok** |
| C. pas 0-5 identiques, queues 0-4 identiques | **ok** |
| **C. queue de la piste 5** | **4 octets différents** (+3 005..+3 008) |
| D. aucune zone de verrous après la piste 5 (stock) | **ok** |

Les 4 octets : le stock a `0xFFFF` (« pas de verrou »), Groove a `0x00` — Groove écrit donc
**un verrou de plus** dans la queue de sa **dernière** piste. La bissection (retirer une écriture
à la fois) localise la cause dans **les deux écritures qui déplacent la queue** (`0x4005b926` et
`0x4005b92c`) — c'est-à-dire dans **le changement de format lui-même**.

**Deux lectures, et je ne tranche pas :**
1. **comportement correct** : à 8 pistes, le gestionnaire parcourt **8** queues au lieu de 6 et
   écrit légitimement un verrou de plus dans la dernière — les 4 octets seraient alors la
   *conséquence attendue* du format, pas un défaut ;
2. **défaut** : une borne manque encore quelque part (par exemple un compteur de verrous lié au
   nombre de pistes).

**Ce qui rend la question tranchable** : il faut une queue rangée **réelle** (pas mes zéros) —
c'est-à-dire un pattern **authentique**, qu'on obtiendra en appelant le **chemin d'écriture** de
l'OS (`0x4005b642`, 4 arguments) plutôt qu'en fabriquant des octets.

#### d) L'état, sans embellissement

**Le jalon 2 n'est pas clos.** Ce qui est acquis : le format rangé **entièrement décodé** (entrée
de 130 o, 80 entrées, en-tête 112 o, pas contigus), la **disposition recalculée**, **192 écritures
vérifiées** octet à octet, et **A, B, D verts** avec C à **4 octets** sur 40 924. Le JSON reste
**retiré** et le générateur **refuse d'écrire**.

**Ce qui reste, en une ligne** : donner au banc une queue rangée **réelle** (ou un pattern
authentique), trancher les 4 octets, puis publier le hash du jalon 2 et passer à l'aller-retour
complet (déplier → **replier** = la sauvegarde), au convertisseur v6 → v7 et à la page de pistes.

### 3.45 Le chemin d'écriture décodé — et le contrôle E qui **innocente le patch** `[FAIT]`/`[HYP]` (14/10)

#### a) Le chemin de sauvegarde `[FAIT]`

`0x4005ba0a(packed, deployed, drapeau)` : il copie la queue de l'enregistrement (64 o, `a3@(30642)`
→ `a2@(14736)` — **les deux constantes sont déjà dans le jeu de changements** ✓), puis appelle
`0x4005b642` **par piste** (722 o de pas) avec **cinq** arguments
`(rangé, déployé, drapeau, -1, -1)`, et finit par la queue (`a3@(4332)` / `a2@(4336)`).

#### b) Le contrôle **E** : écrire puis relire, **par le code de l'OS** `[FAIT]`

Le banc ne fabrique plus la queue rangée : il fait **écrire** l'OS (`0x4005ba0a`), puis **relire**
(`0x4005b894`), et compare. **Aucune connaissance synthétique du format n'entre dans ce contrôle.**

Résultat :

```
stock  (6 pistes) : pas FAIL, queues FAIL
grove  (8 pistes) : pas FAIL, queues FAIL
```

**Et c'est le point capital** : E échoue **aussi sur le stock** — l'OS **non modifié**. Le patch ne
peut donc **pas** être la cause de cet échec : ce sont **les entrées du banc** qui ne sont pas
fidèles. Autrement dit, **l'aller-retour écrire→relire de l'OS n'est pas une identité octet à octet**
sur l'enregistrement déployé — certains champs sont **dérivés ou ignorés** par le format.

#### c) Ce que cela change pour le contrôle C `[HYP]`

Si le format ne préserve pas tous les octets, alors comparer les **octets déployés** stock contre
Groove est **trop strict** : les **4 octets** du §3.44 (queue de la piste 5, `+3005..+3008`) peuvent
être exactement un de ces champs dérivés — et non un défaut du patch. **La question reste ouverte**,
mais elle n'est plus « le patch est-il faux ? » : elle est « **quels octets le format préserve-t-il ?** »

#### d) Ce qui est **solidement** établi `[FAIT]`

| | |
|---|---|
| la géométrie | record déployé **40 924** (4 + 8×722 + 8×4385 + 64), rangé **16 292** (4 + 8×722 + 10 512) |
| le dépliage | couvre **8 pistes** (queue de la piste 7 remplie) — contrôle **B vert** |
| les constantes | toutes vérifiées octet à octet (**192 écritures**) |
| les pistes 0-5 | **pas identiques** au stock, **queues 0-4 identiques** |
| le stock | ne contient aucune zone de verrous après sa piste 5 — contrôle **D vert** |

#### e) L'obstacle, nommé

**Les entrées du banc sont synthétiques**, et chaque correction en a révélé une autre (pas contigus,
offset de queue, enregistrement par format, champs non préservés). La sortie de ce cercle n'est pas
un correctif de plus : c'est un **pattern authentique** — obtenu

- soit **depuis la machine** (Maxime enregistre un projet, on en extrait un pattern) ;
- soit depuis le **contenu d'usine** de l'OS, s'il est accessible.

Tant qu'on ne l'a pas, le banc ne peut pas distinguer « le patch est faux » de « l'entrée est
fausse » — et **le contrôle E vient de montrer que c'est la seconde branche qui est en jeu**.

#### f) L'état

**Le jalon 2 n'est pas clos** ; le JSON reste **retiré** et le générateur **refuse d'écrire**.
Mais le bilan est plus clair qu'il n'y paraît : le **format** est entièrement décodé, la
**disposition** recalculée, **192 écritures** vérifiées, la **géométrie prouvée** (B, D), et
l'échec restant est **attribué au banc**, pas au patch.

**La suite, en une ligne** : un **pattern authentique** comme entrée du banc, puis trancher C,
publier le hash du jalon 2, et enchaîner l'aller-retour, le convertisseur v6 → v7 et la page.

### 3.46 Le banc ne peut pas **fabriquer** un pattern valide — c'est la limite, et elle est nommée `[FAIT]`/`[HYP]` (14/10)

#### a) L'idempotence échoue **sur le stock aussi** `[FAIT]`

Contrôle **E**, version « identité du format rangé » : partir de zéros, faire **relire** l'OS
(`0x4005b894`) puis **écrire** (`0x4005ba0a`), deux fois, et comparer.

```
stock  (6 pistes) : range stable FAIL, deploye stable FAIL, 161 octet(s) non nuls
grove  (8 pistes) : range stable FAIL, deploye stable FAIL, 161 octet(s) non nuls
```

**Les deux images échouent identiquement**, avec le **même** nombre d'octets non nuls (161) : le
patch n'y est pour rien, c'est **l'entrée** qui est en cause — un enregistrement rangé **tout à
zéro n'est pas un pattern valide**, et le chemin d'écriture **abandonne** (il n'écrit que
l'en-tête).

#### b) La limite, et pourquoi elle est **structurelle** `[FAIT]`

Le banc a besoin d'un pattern **valide** (une machine, des pas, un genre) pour que le code de l'OS
le traite. Or **le construire à la main est exactement ce qui échoue depuis le §3.39** : chaque
entrée synthétique a révélé une hypothèse fausse de plus (pas contigus, offset de queue,
enregistrement par format, champs non préservés, et maintenant validité). **Ce n'est pas un
correctif de plus qu'il faut : c'est une entrée vraie.**

**Ce qui est prouvé reste prouvé** (et c'est l'essentiel) :

| | |
|---|---|
| le **format** | entièrement décodé (entrée de 130 o, 80 entrées, en-tête 112 o, pas contigus) |
| la **disposition** | recalculée (image 1 944 164, en-tête `0x406c4684`, patterns `0x406c46a0`, kits `0x43dd0000`) |
| les **192 écritures** | vérifiées octet à octet contre l'image d'origine |
| la **géométrie** | record déployé 40 924, rangé 16 292 — et le dépliage **couvre 8 pistes** (contrôle B) |
| le **stock** | ne contient aucune zone de verrous après sa piste 5 (contrôle D) |
| les **pistes 0-5** | pas **identiques**, queues 0-4 **identiques** |

#### c) Ce qu'il faut pour finir — une demande précise

Un **pattern authentique**, c'est-à-dire **un projet sorti de la machine** :

- **Elektron Transfer** sait **dumper un projet** : Maxime enregistre un projet sur son
  Model:Cycles, le transfère, et le fichier obtenu (dans `firmware/`, **jamais versionné**)
  fournit l'entrée vraie du banc ;
- à défaut, le **contenu d'usine** de l'OS, s'il est accessible.

Avec cette entrée, le banc peut **trancher** : les 4 octets du §3.44 et l'aller-retour. **Sans
elle, il ne peut pas distinguer « le patch est faux » de « l'entrée est fausse » — et les deux
contrôles E viennent de montrer que c'est la seconde branche.**

#### d) L'état final de ce cycle

**Le jalon 2 n'est pas clos**, et il ne peut pas l'être avec des entrées fabriquées. Le JSON reste
**retiré**, le générateur **refuse d'écrire**, et **rien d'incomplet n'est versionné**. Le travail
laisse une base nette : format décodé, disposition recalculée, écritures vérifiées, géométrie
prouvée — et **une demande précise** pour la suite.

### 3.47 Le projet `.mcprj` de Kevin : **confirmation du sceau v6**, mais pas l'entrée du banc `[FAIT]`/`[HYP]` (14/10)

`build/re8/probe_mcprj*.py`, `probe_payload.py`, `probe_payload2.py`. Donnée utilisateur : une
copie du payload est dans `firmware/` (**ignoré par git**, vérifié : `.gitignore:2:firmware/`).

#### a) Ce qu'est un `.mcprj` `[FAIT]`

C'est une **archive ZIP** (`PK\x03\x04`) de deux entrées :

```
manifest.json   143 o  {"FormatVersion":"1.0","ProductType":["47"],
                        "Payload":"New","FileType":"Project","FirmwareVersion":"1.13"}
New           14054 o  la charge utile
```

`ProductType 47` = Model:Cycles, `FirmwareVersion 1.13` ✓.

#### b) **Le sceau de version 6, dans de la vraie donnée** `[FAIT]`

La charge utile commence par un en-tête puis, en **`0x24`** :

```
be ef ba ce 00 00 00 06 4e 65 77 ...      <- sceau, VERSION 6, "New"
```

**C'est la confirmation indépendante du §3.29** : le sceau `0xBEEFBACE` suivi du **champ de
version**, ici **6** — la version courante — dans un projet réellement produit par la machine
(OS 1.13). On trouve **8 sceaux** (`0x24`, `0x23e8`, `0x295c`, `0x2c17`, `0x2d80`, `0x2ed9`,
`0x31f9`, `0x349e`) et **6 sceaux de clôture** `0xBACEF00C` : la charge utile contient
**plusieurs enregistrements estampillés**.

#### c) Mais **ce n'est pas** l'image du projet `[FAIT]`

| | |
|---|---|
| `00 00 00 04` (le genre attendu par le dépliage de pattern) | **aucun site** |
| pas des remplissages `0xFF` | **irrégulier** (165, 95, 58, 112, 143, 69, …) |
| taille | 14 054 o (l'image projet en fait 2 163 716) |

C'est donc un **flux de transfert à longueur variable** — le format **d'Elektron Transfer**, pas
l'image brute ni un pattern rangé. Passé au dépliage de l'OS (`0x4005b894`), à six offsets
différents, il ne produit **rien** (le contrôle de genre échoue partout).

**Conséquence** : l'entrée authentique existe, mais **dans un format non décodé** — le décoder est
un **nouveau chantier de RE** (le chemin d'import, `/projects/`, `#CONTENT_UPLOAD`).

#### d) Ce qui débloquerait vraiment le banc `[HYP]`

Deux voies, par ordre de coût :

1. **`#MMCDUMP`** : l'automate d'interface de l'OS sait **dumper le +Drive** (§3.33.c). Maxime peut
   le lancer par MIDI : on obtiendrait **l'image projet brute** (2,16 Mo, celle que la chaîne de
   version traite) — l'entrée exacte du banc ;
2. **faire initialiser un projet par l'OS lui-même** : l'image contient
   `Project::initializeNewProject` (RTTI, §3.30.c). La faire tourner donnerait un pattern
   **canonique**, donc une entrée valide **sans aucun fichier** — c'est une étape de RE, mais
   bornée.

**La voie 2 est la plus propre** : elle ne dépend d'aucune donnée extérieure et donne exactement ce
qui manque au §3.46 (un pattern **valide** pour que l'aller-retour ait un sens).

#### e) L'état

Le jalon 2 reste **non clos**, le JSON **retiré**, le générateur **refuse d'écrire**, rien
d'incomplet n'est versionné. **Acquis en plus** : le sceau de version **6** confirmé **dans de la
vraie donnée utilisateur**, et le `.mcprj` compris (archive ZIP + manifeste + flux de transfert).

### 3.48 **Le jalon 2 est clos** : il manquait **trois sites** `[FAIT]` (14/10)

Le banc a fait exactement ce qu'un banc doit faire : **il a trouvé ce que la lecture statique avait
manqué**. Les contrôles **A, B, C, D, E** passent tous, et le jalon 2 est **prouvé en émulation**.

#### a) Ce qui manquait — trois déplacements de 16 bits

Le jeu de changements du §3.36 avait trié les **immédiats** de 4332 et les **7 `pea`** de 4336 —
mais il avait manqué **trois sites en mode déplacement** :

| Site | Instruction | Avant → après |
|---|---|---|
| **`0x4005ba70`** | `pea %a3@(4332)` — **le chemin de SAUVEGARDE** | 4332 → **5776** |
| **`0x4000c62e`** | `lea %a2@(4332),%a2` | 4332 → **5776** |
| **`0x4005b94a`** | `movel %sp@(44),%a2@(30706)` — **le champ de fin d'enregistrement** | 30706 → **40920** |

Le troisième est le plus parlant : le triage du §3.36 comptait **4** sites pour 30706, et il y en a
**5** — le cinquième est l'**écriture** faite par le dépliage lui-même. Sans lui, Groove écrivait ce
champ **dans la queue de la piste 5** au lieu de la fin de l'enregistrement.

#### b) Comment ils ont été trouvés — par **l'aller-retour**, pas par la lecture

C'est le contrôle **E** (« identité du format rangé ») qui les a désignés :

- avant correction, le format rangé de Groove **n'était pas idempotent** (9 039 octets non nuls
  contre 175 pour le stock) → il lisait/écrivait la queue rangée **au mauvais offset** ;
- après les trois correctifs : **les deux images sont stables**, avec **175 octets non nuls
  chacune** — le même volume, donc le même comportement ;
- et la comparaison des **formes canoniques** (après un cycle) montre les **pistes 0-5 identiques**
  entre le stock et Groove, **pas et queues**.

#### c) Le banc, état final

```
A. image, constantes, non-recouvrement ............ ok
B. le depliage couvre huit pistes ................. ok
C. pistes 0-5 identiques (pas ET queues) .......... ok
D. aucune zone de verrous apres la piste 5 ........ ok
E. aller-retour : format range stable (2 images) .. ok
   formes canoniques 0-5 .......................... ok
TOUT OK
```

#### d) Publication

- `tools/gen_groove_pattern.py` → `57-groove-patterns.json`, **196 écritures** (contre 192 avant les
  trois correctifs) ;
- les deux tweaks ensemble : 179 + 196 = **375 écritures**, **intersection 0**, 1 348 octets modifiés ;
- **MAIN OS (jalons 1+2)** : `ac9c4e33fdbe39e31831f4af6601ab0cc318ce5e5185e7945431dacfaa642af7` ;
- publié dans `BUILD.md`.

#### e) Ce qui reste pour que Groove soit **jouable**

1. le **convertisseur v6 → v7** et le sort de la **banque F** (§3.29.f, §3.27) — sans lui, un projet
   d'origine serait mal lu : **c'est le prochain verrou** ;
2. la **page de pistes** (`[TRACK]`+`[PAGE]`, §3.32) et les 21 bornes d'interface (§3.31, §3.34) ;
3. la mesure CPU sur la machine (les lignes relogées en DDR).

**Rien n'est « testé sur la machine »** : c'est à Maxime de le faire, et le mod reste
`experimental` jusqu'à son retour.

### 3.49 Jalon 3 : le convertisseur **v6 → v7** — la conception, arrêtée `[FAIT]`/`[HYP]` (15/10)

Le jalon 2 est clos (§3.48) mais Groove **n'est pas utilisable** : sans ce convertisseur, un projet
d'origine (version 6) serait **mal lu** par un OS qui attend la version 7 — c'est le verrou qui
protège les données de l'utilisateur. La **page de pistes** (§3.32) vient après.

#### a) La chaîne existante, et le point d'insertion `[FAIT]`

`0x4005d9f6` contient **six blocs de 198 octets** (0xC6), un par version 0..5. Le dernier (v5) :

```
4005ddde  movel #2163716,%sp@-      ; alloue le tampon de la version SUIVANTE
4005dde4  jsr %fp@                  ; l'allocateur
4005ddee  pea #0x10                 ; alloue l'objet de 16 o
4005ddf4  jsr %fp@
4005de02  movel #1074852332,%a0@    ; le descripteur de CLASSE (0x4010f1ec)
4005de08  movel %a4,%a0@(12)        ; le tampon
4005de1c  jsr %pc@(0x4005c526)      ; LE CONVERTISSEUR de la version
4005de52  movel #2163716,%sp@-      ; puis memcpy(a2, resultat, taille)
4005de5c  jsr 0x4008f1f0
4005de6a  moveb #1,%a3@             ; drapeau « converti »
4005de6e  movel %d2,%sp@- / jsr %a5@ ; libere
4005de74  movel %a2@(4),%d0         ; <<< LE CONTROLE DE FIN DE CHAINE
4005de78  moveal #0xBEEFBACE,%a0
4005de7e  cmpal %a2@,%a0            ; sceau
4005de82  movel #2163712,%d1        ; offset du sceau de CLOTURE
4005de8e  cmpal %a2@(0,%d1:l),%a0
4005de94  moveq #6,%d1              ; <<< LA VERSION COURANTE
4005de96  cmpl %d0,%d1
4005de98  seq %d0
```

**Le point d'insertion est donc `0x4005de74`** : les ~42 octets du contrôle de fin (`0x4005de74` →
`0x4005de9e`) deviennent un **`jsr`** vers le nouveau code, qui fait **l'étape v7** puis **le
contrôle de fin** (`== 7`, sceau de clôture à `1944160`) et renvoie le résultat.

#### b) Ce que le convertisseur v6 → v7 doit faire `[FAIT]`

| | v6 (source) | v7 (destination) |
|---|---|---|
| image | 2 163 716 | **1 944 164** |
| patterns | 96 × 14 848 | **80 × 16 292** |
| kits | 96 × 7 094 | **80 × 7 294** |
| sceau de clôture | `+2163712` | **`+1944160`** |

Le **repacking d'un pattern** : `[4][6×722 = 4 332][10 512]` → `[4][8×722 = 5 776][10 512]`, c'est-à-dire
**copier 4, copier 4 332, mettre à zéro 1 444 (les pas des pistes 6-7), copier 10 512** — la queue
rangée (une liste plate de 80 entrées de 130 o, §3.42) est **copiée telle quelle** : ses entrées
portent leur numéro de piste (0..5), donc elles restent valides, et les pistes 6-7 n'ont aucun
verrou. Les **kits** : copier 7 094, mettre à zéro 200.

**La banque F est perdue** : le convertisseur ne garde que les **80 premiers** patterns (décision de
Kevin, §3.27). C'est le seul point de perte de données du mod, et il sera **documenté** — le
convertisseur ne peut pas avertir l'utilisateur.

#### c) La forme du code à écrire `[FAIT]`

L'élément existant ne peut pas être réutilisé tel quel : la boucle des convertisseurs avance la
**source et la destination du même pas** (14 848), alors qu'ici les pas **diffèrent** (14 848 → 16 292).
Le nouveau code est donc :

1. `memcpy(dst+8, src+8, 16)` (l'en-tête du record) et la copie de champ `a3@(24) = a2@(24)` ;
2. **une boucle de 80 patterns** : source `src + 512 + p×14848`, destination `dst + 512 + p×16292`,
   appelant un **convertisseur d'élément** qui repacke un pattern (4 + 4 332 + 1 444 zéros + 10 512) ;
3. **une boucle de 80 kits** : `7094` copiés + `200` mis à zéro, aux nouveaux offsets ;
4. `memcpy(a2, resultat, 1944164)`, le drapeau, la libération ;
5. le **contrôle de fin** : sceau, sceau de clôture à `+1944160`, version `== 7`.

Soit **~400 à 600 octets** d'assembleur ColdFire, en deux fonctions.

#### d) Où loger ce code `[HYP]`

`tools/sprites.py` recense **neuf masques de sprite libérables** (376 à 1 024 o, `0x4015c044`,
`0x4016cae8`, `0x4018a788`, `0x40189930`, `0x4018a220`, `0x40183118`, `0x40185018`, `0x40185968`,
`0x40185c58`) : les mods du dépôt les réutilisent en **redirigeant leur constructeur**. **Groove
n'utilise aucun de ces mods**, donc les masques sont libres — au prix de la même redirection (sinon
le sprite de l'OS est corrompu). L'autre voie est un **cave** du code sans aucune référence ; à
trancher en écrivant le générateur.

#### e) Les étapes du jalon 3

1. **3a** — le convertisseur d'élément (le repack d'un pattern) et sa preuve isolée ;
2. **3b** — le code de chaîne (les deux boucles, le memcpy, le contrôle de fin) et la redirection
   en `0x4005de74` ;
3. **3c** — le générateur (`tools/gen_groove_convert.py` → `58-groove-convert.json`) : les octets,
   la taille de l'image v7, l'offset du sceau de clôture, la version de fin `7`, et le logement ;
4. **3d** — la **preuve en émulation** : une image v6 réelle (le `.mcprj` de Kevin en donne un
   exemple, §3.47) convertie en v7, puis **relue** — les pistes 0-5 et les kits doivent revenir
   identiques, et les pistes 6-7 vides.

**Puis** la page de pistes (§3.32) et les 21 bornes d'interface (§3.31, §3.34) : là seulement
Groove sera **jouable**, et c'est à ce moment qu'une PR aura un sens.

### 3.50 Jalon 3, étape **3a** : le convertisseur d'élément — écrit et **prouvé** `[FAIT]` (15/10)

`tools/machines/groove/convert_v7.S`, `tools/re/test_groove_convert.py`.

#### a) Le code `[FAIT]`

`groove_elem(dst, src)` — le repack d'**un** pattern rangé, **58 octets** de ColdFire :

```
206f 0004   moveal %sp@(4),%a0      ; dst
226f 0008   moveal %sp@(8),%a1      ; src
2019 20c0   movel %a1@+,%d0 / movel %d0,%a0@+     ; [0,4)
223c 0000 043b   movel #1083,%d1                  ; 4 332 o = les 6 pistes
223c 0000 0169   movel #361,%d1                   ; 1 444 o = ZERO (pistes 6-7)
223c 0000 0a44   movel #2628,%d1                  ; 10 512 o = la queue, telle quelle
7001 4e75   moveq #1,%d0 / rts
```

Les trois longueurs et les trois offsets sont divisibles par 4, et les adresses alignées : tout se
copie en **mots longs**. L'outil est le **m68k-linux-gnu-gcc de WSL** (`-mcpu=54418`), comme le
font les mods du dépôt ; le banc essaie le compilateur **natif** d'abord, puis WSL.

#### b) Les trois contrôles `[FAIT]`

| | |
|---|---|
| **A** | le code s'assemble (58 o) et **tient dans la cave** `0x40147f22` (182 o, remplie de `0xFF` dans l'image d'origine) |
| **B** | le repack produit par le **code** est **identique octet à octet** à la **référence Python** (16 292 o comparés) |
| **C** | **à travers l'OS** : le pattern v6 déplié par le **stock** et le pattern v7 produit par le convertisseur puis déplié par **Groove** donnent les **mêmes pistes 0-5** — pas **et** queues — et **aucun verrou sur les pistes 6-7** |

**Le jalon 2 est donc vu à travers le convertisseur** : la conversion ne perd rien des pistes 0-5
et n'invente rien sur les pistes 6-7.

#### c) Trois pièges rencontrés, notés pour la suite `[FAIT]`

1. **Un script shell écrit par Python sous Windows sort en CRLF**, et `bash` l'exécute en
   *échouant silencieusement* (la dernière commande du tuyau réussit) : `write_text(..., newline='\n')`
   est obligatoire. C'est ce qui a produit « 0 octets assemblés » ;
2. **le remplissage de la queue couvre 66 octets par pas, pas 68** (§3.44) : le **34e mot** d'un pas
   n'est jamais rempli — un contrôle qui exige `0xFFFF` partout sur une queue trouve donc 64 mots
   par piste qui ne le sont pas, **sans qu'aucun verrou n'existe**. Le contrôle utile porte sur les
   **33 mots remplis** ;
3. **la queue rangée synthétique doit être valide** (une entrée = 1 o de pas, 1 o de piste,
   64 mots) : des octets quelconques font écrire des verrous sur n'importe quelle piste. C'est le
   piège du §3.46, rencontré **une troisième fois** — la queue est donc mise à **zéro** dans le
   banc.

#### d) La suite du jalon 3

**3b** — le code de chaîne : les deux boucles, le `memcpy` final, le contrôle de fin (`== 7`), et la
**redirection en `0x4005de74`**. **3c** le générateur (`58-groove-convert.json`). **3d** la preuve
sur une **image entière** : une image v6 convertie en v7 puis **relue**. Ensuite la page de pistes.

### 3.51 Jalon 3 : le **conteneur** de l'image — le jalon 2 est **incomplet**, et le chiffre publié est faux `[FAIT]` (15/10)

`build/re8/dis_v5conv.py`, `dis_unpack.py`, `dis_kitelem.py`, `dis_save.py`, `dis_7094.py`.

En écrivant 3b il a fallu **relire le conteneur** plutôt que de reprendre les chiffres du §3.43.b —
et le §3.43.b **se trompait**. Voici ce que le code dit, et il le dit trois fois.

#### a) Le blob de la chaîne, mesuré `[FAIT]`

Le convertisseur **v5 → v6** (`0x4005c526`) est le modèle exact de ce que 3b doit faire. Il traite
`a2` = le blob source et `a3` = le blob destination :

```
4005c588  addil #512,%d4               ; patterns a +512
4005c5bc  cmpil #1425408,%d2           ; borne : 96 x 14848
4005c5c4  moveal #1425920,%fp          ; kits a +1425920
4005c5f6  cmpil #737280,%d2            ; borne : 96 x 7680   <<< 7 680, pas 7 094
4005c5fe  pea 0x200 ... +2163200       ; copie 512 octets de queue
4005c61c  movel %a2@,%a3@              ; le sceau
4005c626  movel %a2@,%a3@(0,%d0:l)     ; sceau de CLOTURE a +2163712
4005c62a  moveq #6,%d0 / movel %d0,%a3@(4)   ; version
```

Donc le blob de la chaîne (v6) : **`[512][96 × 14 848][96 × 7 680][512][4]` = 2 163 716** ✓.

**Le pas rangé d'un kit est 7 680, pas 7 094.** Le dérouleur le redit, et la sauvegarde aussi :

| site | ce qu'il avance |
|---|---|
| dérouleur `0x4005d358` | `addil #7680,%d7` (rangé) **et** `addil #7094,%d5` (déployé) |
| sauvegarde `0x4008db0a` | `addil #7680,%d7` |
| sauvegarde `0x4008d92e` | l'image allouée : 2 163 716 = 512 + 1425408 + 737280 + 516 ✓ |

**7 680 = le creneau rangé** (dans le fichier et dans l'image), **7 094 = l'enregistrement déployé**
(la table SDRAM). Les deux sont avancés **au même endroit** par le dérouleur, à des pas différents :
c'est la preuve.

#### b) Le kit, dans les deux sens `[FAIT]`

L'élément de kit du dérouleur (`0x4005b2ae`, rangé → déployé) donne les deux dispositions d'un coup
(`a2` = rangé, `a3` = déployé) :

| | rangé | déployé |
|---|---|---|
| en-tête | +4 (16 o), +14 (12 o) | +0 (16 o), +10 (12 o) |
| **par piste** | +32, **6 × 100 o** → 632 | +28, **6 × 100 o** → 628 |
| champ f | +632 | +628 |
| champ g | +708 (6 656 o) | +694 (6 400 o) |
| total | 7 364 (creneau 7 680) | **7 094** ✓ |

Le déployé est le rangé **décalé de 4** ✓. Et pour huit pistes, l'aire par piste passe à **800** :
**tout ce qui la suit se décale de +200** — rangé f/g : 632 → **832**, 708 → **908** ; déployé :
628 → **828**, 694 → **894**. D'où le kit déployé = 894 + 6 400 = **7 294** ✓ — **le chiffre du
générateur est donc juste**, et il ne l'est que si le décalage est réel : c'est une confirmation.

Le kit **rangé** à huit pistes = 908 + 6 656 = **7 564 ≤ 7 680** ✓ : **le creneau rangé ne change
pas.** (Il a été dimensionné avec cette marge.)

#### c) Ce qui est faux, et ce qui manque `[FAIT]`

| | publié (§3.43.b, §3.44.b, générateur) | **correct** |
|---|---|---|
| taille du blob | 2 163 716 → **1 944 164** | → **1 918 788** |
| sceau de clôture | `+1 944 160` | **`+1 918 784`** |
| base des kits, fichier | 1 425 920 (non touchée) | **1 303 872** |
| base des kits, image | 1 426 192 (non touchée) | **1 304 144** |
| compte des patterns, sauvegarde | `moveq #96` (non touché) | **80** |
| décalages internes du kit | non touchés | **+200** (628/694/632/708) |

Le 1 944 164 publié vient de `80 × 16 292 + 80 × 7 294 + 57 284` : il met la taille **déployée** du
kit (7 294) là où va le **creneau rangé** (7 680), et traite les 57 284 comme une constante. Le
calcul juste est une **différence** : 2 163 716 − **122 048** (patterns : 96 × 14 848 → 80 × 16 292)
− **122 880** (kits : 96 × 7 680 → 80 × 7 680) = **1 918 788** ✓. Vérification croisée : l'image
`[784][80 × 16 292][80 × 7 680][244]` donne le **même** total ✓ (784 + 244 = 1 028 = 512 + 516).

#### d) Et le firmware de jalon 2 **déborde son tampon** `[FAIT]`

Le littéral d'allocation a été abaissé à 1 944 164, mais :

- la **sauvegarde** empile 96 patterns et 96 kits depuis 1 426 192 / 1 425 920 → elle écrit jusqu'à
  **2 163 472**, soit **219 308 octets après la fin** du tampon ;
- le **dérouleur** lit 80 kits au pas 7 680 depuis 1 425 920 → jusqu'à **2 040 320**, soit
  **121 532 octets après la fin**.

Les bancs du jalon 2 sont **au niveau des éléments** (déplier/replier un pattern) : ils ne peuvent
pas voir un débordement du **conteneur**. C'est le genre de défaut que la discipline « prouver en
émulation » doit attraper au niveau de l'image entière — c'est-à-dire exactement **3d**.

**Conséquence** : le jalon 3 ne peut pas se contenter d'écrire le convertisseur. Il doit d'abord
**rendre le conteneur cohérent** (les six lignes du tableau c), ce qui est une **correction du
jalon 2** (générateur + JSON + hash publié + note), puis écrire le convertisseur contre ce
conteneur-là. Tant que ce n'est pas fait, un convertisseur juste produirait un blob que l'OS
lirait **hors de son tampon**.

### 3.52 Jalon 3, partie 1 : le conteneur corrigé — et la **chaîne de versions mise de côté** `[FAIT]` (15/10)

`tools/gen_groove_pattern.py` réécrit, `build/re8/sweep_container.py`, `sweep_unknown.py`.

#### a) La cause réelle : deux choses confondues `[FAIT]`

Le balayage de toutes les constantes de disposition (immediats 32 bits **et** déplacements 16 bits)
montre que le jalon 2 a réécrit **~100 sites uniformément** — alors que **~60 d'entre eux
appartiennent à la chaîne des convertisseurs de version** (les six `v0…v5 → v6`, leurs éléments, et
les six blocs de `0x4005d9f6`). Or **leur sortie est un bloc v6** : ils doivent garder la géométrie
d'origine. Deux choses différentes étaient traitées comme une seule :

| | décrit | géométrie |
|---|---|---|
| sauvegarde, chargements, création, matérialisation, marcheurs, dérouleur/emballeur | **le bloc courant** | **v7** |
| les six convertisseurs, leurs éléments, les six blocs | **un bloc v6** (leur sortie) | **origine — à ne pas toucher** |

C'est ce qui rendait le conteneur incohérent : le bloc courant gardait les bases v6
(1 425 920 / 1 426 192 jamais touchées) pendant que les convertisseurs recevaient la géométrie v7.
Et cela avait une conséquence de sûreté : **la chaîne débordait son propre tampon** (le convertisseur
v5 → v6 copiait 96 patterns au pas v7 dans un tampon rabaissé à 1 944 164, jusqu'à 2 302 340).

#### b) Le générateur sait maintenant le prouver `[FAIT]`

`LEGACY` liste les plages de la chaîne, et le générateur **vérifie** que le jeu de changements ne
les touche pas : il applique ses écritures et compare ces plages au stock. Résultat :

```
controle : les 5 plages de la chaine de versions sont identiques au stock
total : 167 ecriture(s)
```

Les compteurs tombent **exactement** sur le triage : taille du bloc 14 sites (dont **6** dans la
chaîne), sceau de clôture 4 (dont **5**), base des kits 9 (dont **12**), fin des blocs rangés 2
(dont **6**), créneau rangé 12 (dont **7**), et les déplacements 5 / 4 / 3 / 6 / 31. La somme
retrouve les compteurs revus du §3.37.

**Une île courante dans la zone des convertisseurs** : `0x4005cd9e..0x4005cdde` est un aide du bloc
**courant** — le marcheur de la queue rangée, qui lit le pas d'une entrée à `+4336` (→ `+5780`).
C'est le contrôle du découpage qui l'a révélé : il a nommé `0x4005cdb2`, le site même que le §3.48
avait prouvé nécessaire par l'aller-retour. La plage est donc coupée en deux.

#### c) Le dernier point ouvert : les deux champs de kit `[HYP]`

L'aire par piste du kit passe de 600 à 800 octets, donc **les deux champs qui la suivent décalent de
+200** : `628 → 828` et `694 → 894` (déployés), `632 → 832` et `708 → 908` (rangés). C'est ce qui
rend le kit déployé égal à `894 + 6 400 = 7 294` — le chiffre du jalon 2, qui n'est juste **que** si
ce décalage est réel.

**Mais ces quatre valeurs ne peuvent pas être trouvées par valeur** : le balayage en rend **35, 5,
47 et 19** sites, dont l'immense majorité sont des coïncidences (`632` et `708` sont des
déplacements banals). Les sites **certains** sont les quatre de l'élément de déroulement
(`0x4005b2ae`) et les deux de l'élément v5 → v6 (`0x4005be32`, dans `LEGACY`). Les autres — **les
lecteurs des champs f et g de l'enregistrement déployé** — doivent être identifiés **par fonction**,
un par un. C'est le dernier point ouvert du jalon 2.

**En attendant, le générateur REFUSE d'écrire** (`KIT_FIELDS_PENDING`) : passer 600 à 800 sans ce
décalage ferait écrire les pistes 7-8 **par-dessus** f et g. Aucun firmware incomplet ne doit
pouvoir être construit — c'est la règle du §3.36, appliquée au cas présent.

#### d) La leçon de méthode `[FAIT]`

Pour ces quatre valeurs, **le balayage par valeur ne suffit pas** : il faut **lister les fonctions
courantes** (une liste blanche) plutôt que d'exclure la chaîne (une liste noire). C'est la forme à
donner au générateur quand f et g seront cartographiés.

### 3.53 Les deux champs de kit **cartographiés** — et la leçon confirmée `[FAIT]`/`[HYP]` (15/10)

`build/re8/map_kitfields.py`, `map_kitfields2.py`.

#### a) Ce que sont `f` et `g` `[FAIT]`

Les deux sous-convertisseurs que l'élément de déroulement appelle (`0x4005b266` pour `f`,
`0x4005b178` pour `g`) disent tout :

| | taille | structure |
|---|---|---|
| **`f`** | **66 o** | piloté par une **table** (`0x4010ee04` → `0x4010ee38`) : des mots écrits à des offsets choisis, puis 8 octets remis à zéro à `a2@(68)` |
| **`g`** | **6 400 o** | **64 morceaux de 100 o** (`cmpil #6400`, pas de 100) — **par PAS**, pas par piste |

**Aucun des deux ne dépend du nombre de pistes.** L'aire par piste (100 o × 6 → 8) grandit, donc
`f` et `g` **décalent de +200** — mais leur **contenu** est inchangé.

#### b) Les sous-convertisseurs n'ont pas besoin d'être touchés `[FAIT]`

`g` travaille sur `a4 = a2@(4)` et `f` écrit à `a2@(68)` : leurs décalages internes sont
**relatifs au morceau**, donc ils suivent le pointeur. **Seul celui qui calcule les offsets
absolus** (628/694/632/708) doit bouger.

#### c) Où sont les offsets absolus `[FAIT]`/`[HYP]`

Le balayage par valeur en rend 36, 6, 54 et 27 — mais regroupés par région, la vérité apparaît :

| | sites réels | où |
|---|---|---|
| **694** (base de `g`) | **4** | les 2 de l'élément de déroulement, `0x40009ac0`, `0x400613f4` |
| **628** (base de `f`) | **~10** | l'élément de déroulement, `0x40009ab4`, `0x40009b76`, `0x4000a562`, `0x400332ec`, `0x400613ea` |
| **632 / 708** (rangés) | **8** | l'emballeur (`0x4005d13c`, `0x4005d15e`), l'élément de déroulement, `0x4005bdda` |

Le reste est **coïncidence** : `cmp.w $2b6.w,d0` dans de la donnée, `andi.l #$2b602c0`,
`pea 0x274` (une **adresse**, pas un décalage), et des `clrl` en série sur un tampon quelconque
(`0x400333dc` efface 620, 624, 628, 632, 636). **Le moteur audio proprement dit est net** : les
huit fonctions qui indexent les kits par 7 094 n'ont **aucun** offset absolu de `f` ou `g` dans
±512 octets — donc il lit la fiche par **pointeur**, comme le fait le format d'origine.

#### d) Deux choses restent `[HYP]`

1. **un troisième élément v5 → v6** en `0x4005bdda` utilise `632` et n'est **pas** dans les plages
   `LEGACY` (qui commence à `0x4005be32`) → la plage doit être élargie ;
2. il faut trancher **un par un** les ~10 sites de `628` hors codec : certains manipulent la
   **fiche de kit**, d'autres un **tampon de pattern** (`clrl` en série). C'est le prix de la
   leçon : **pour ces quatre valeurs, le balayage par valeur ne suffit pas.**

### 3.54 Le kit : **vérifié**, pas **prouvé** — et l'obstacle est nommé `[FAIT]` (15/10)

`tools/re/test_groove_kit.py`, `build/re8/trace_kit.py`, `probe_empty_kit.py`.

#### a) Ce qu'on a essayé `[FAIT]`

Le banc des patterns prouve un pattern en émulation : il **déplie**, **emballe**, **déplie** et
compare. Le kit devait avoir le même banc. Il ne peut pas, et voici ce qui l'a montré, dans
l'ordre.

**1. Les deux éléments avaient été appelés à l'envers.** Leurs prologues le disent :

| | prologue | sens |
|---|---|---|
| `0x4005d080` | `memcpy(a2, a3@(4), 16)` — la **source** porte l'en-tête de 4 o | **dépliage** : `(déployé, rangé)` |
| `0x4005b2ae` | `memcpy(a2@(4), a3, 16)` — la **destination** porte l'en-tête | **emballage** : `(rangé, déployé, contexte)` |

Appelé à l'envers, on écrit dans le tampon qu'on relit ensuite : le banc comparait des **zéros**
et « passait ». **C'est le contrôle négatif qui l'a démasqué** — en remettant les 21 décalages à
leur ancienne place, le banc ne voyait rien. Un banc qui ne peut pas échouer ne prouve rien.

**2. Un morceau de 100 octets n'est pas de la donnée, c'est un ENREGISTREMENT IMBRIQUÉ.** Le
convertisseur appelé par les deux éléments (`0x4005afa0`) écrit **son propre sceau** et **sa
propre version 2**, puis lit un **type de machine en `+88`** et indexe une table de descripteurs
(`0x4010ee4c`) avec. Une trace des 64 dernières instructions situe la faute exactement là :

```
4005afbc  moveq #2,%d0
4005afbe  movel #0xBEEFBACE,%a2@     ; le sceau du morceau
4005afc4  movel %d0,%a2@(4)          ; sa version
4005b02e  movel %a3@(88),%d0         ; le TYPE, lu dans le morceau
4005b032  lea %a1@(3,%d0:l:4),%a1    ; indexe la table avec
4005b038  moveb %a1@,%a2@(94)        ; <<< la faute
```

Un kit **ne peut donc pas être fabriqué** : c'est le §3.46, un cran plus bas — *le banc ne peut
pas inventer les données de l'OS*. Pour les patterns, la sortie était d'appeler le **chemin
d'écriture de l'OS** (`0x4005ba0a`), qui sait en fabriquer un vrai.

**3. Le code du kit est ORIENTÉ OBJET.** `0x40009a1e`, le codec du kit, travaille sur un objet,
lit son **descripteur de classe** et appelle des **méthodes virtuelles** :

```
40009a2a  moveal %sp@(40),%a2        ; a2 = un OBJET
40009a40  moveal %a2@,%a0            ; sa classe
40009a46  moveal %a0@(48),%a0        ; une METHODE VIRTUELLE
40009a4a  jsr %a0@
```

Piloter cela dans une émulation nue ne demande pas un banc : cela demande de **reconstruire une
tranche de l'OS** (les objets, leurs classes, les enregistrements imbriqués).

#### b) Pourquoi le pattern, lui, marche `[FAIT]`

Le chemin des patterns (`0x4005b894`, `0x4005ba0a`) est de la **donnée plate** : pas d'objet,
pas de méthode virtuelle, pas d'enregistrement imbriqué. C'est toute la différence, et c'est
pourquoi le contrôle E du banc des patterns est un vrai aller-retour.

#### c) L'état, sans embellissement `[FAIT]`

| | |
|---|---|
| le format de pattern | **prouvé en émulation** — banc A–E vert sur le jeu de changements réel |
| le découpage du conteneur | **prouvé** — le générateur vérifie la chaîne de versions octet à octet |
| les 21 sites du kit | **vérifiés** octet par octet dans l'image construite |
| le **comportement** du kit | **NON PROUVÉ** |

`tools/re/test_groove_kit.py` **sort toujours 1** : il vérifie les quatre constantes, puis
**constate** l'obstacle et le nomme. Il ne doit jamais passer tant que le kit n'est pas prouvé
autrement — un « non prouvé » ne doit pas ressembler à un succès.

**Conséquence de la règle du projet** (« prouver en émulation d'abord ; du code non prouvé ne va
pas dans le flasher ») : le kit est acceptable en **ligne de commande**, il n'est **pas** candidat
au flasher, et il n'est **pas** `tested` — tant que Maxime ne l'a pas entendu sur la machine.

#### d) Les trois voies qui restent `[HYP]`

1. **Le chemin de l'image entière** (le « 3d » prévu) : construire une vraie image de projet et
   laisser le **chemin de chargement de l'OS** la lire — il faut alors la couche fichier ;
2. **la machine** : c'est de toute façon la bonne question à lui poser — *les pistes 7 et 8
   sonnent-elles juste, un kit se sauvegarde-t-il et se recharge-t-il ?* ;
3. **un audit statique**, qui est ce qu'on a : les 21 sites, chacun avec sa raison, et la
   vérification octet par octet.

**À demander à Maxime sur la machine** : un kit modifié sur les pistes 7-8 puis rechargé ; un kit
sauvegardé puis rouvert ; une piste 8 qui joue ; et un projet d'origine, pour confirmer qu'il est
**refusé proprement** et que rien n'est effacé.

### 3.55 Jalon 3, la **sélection de piste** : les bornes d'interface `[FAIT]`/`[HYP]` (15/10)

`build/re8/ui_bounds.py`, `ui_bounds.txt`.

#### a) Le constat qui a tout débloqué `[FAIT]`

Les bornes d'interface recensées au §3.31.c et au §3.34.a n'avaient **jamais été changées**. Vérifié
borne par borne contre le jeu de changements : le menu de sélection de piste, la boucle des pads, le
tableau des pads, la carte des LEDs — **aucune** n'y était, et la zone `0x4002xxxx` ne portait que
**6** écritures, toutes des pas de tables du **moteur**. C'est pour cela que les pistes 7-8 n'étaient
pas atteignables : **rien n'avait dit au panneau qu'il y en a huit.**

#### b) Le tri : PISTE, PAD ou MACHINE `[FAIT]`

Les trois valent 5 ou 6, donc la valeur ne dit rien. Le discriminant est **ce qui suit** :

| | ce qui suit | verdict |
|---|---|---|
| une **piste** | un enregistrement de pattern, ou la chaîne « Track %d » | à élargir |
| un **pad** | le tableau des pads (`0x404a8ba0`) — six, **c'est le matériel** | **laisser** |
| une **machine** | un **× 28** (taille du descripteur, §3.29.d) | **laisser** (corruption silencieuse) |

Le piège connu du §3.34.b (`0x4001b696`, × 28) est bien une **machine** : il reste.

#### c) Les neuf bornes élargies `[FAIT]`

Le **chemin de sélection** : le menu de pistes (`0x40023d98`, une entrée par piste), la liste
« Track %d » (`0x40028ee2`), les **bornages d'indice** (`0x40023ca2` **et** `0x40023ca8` — les deux
`moveq`, la garde et la valeur par défaut ; idem `0x4002b9b4` et `0x4002b9bc`), la garde d'indice
`0x40024960`, et les **gardes des actions de piste** (`0x4002399a`, `0x40023efa` — les appelants
construisent « Copy/Paste/Clear TRK %d Sound », §3.31.c). Chacune est vérifiée : l'octet de gauche
doit être un `moveq` (0x70..0x77) et celui de droite la valeur attendue — le même contrôle que pour
la garde du nombre de patterns.

**Laissées, avec leur raison** : les boucles qui parcourent les **6 pads** (`0x4001cfb6`,
`0x4001d5d2`, `0x4001d74e`, `0x40020a42` — la page 2 de Kevin ne rebranche que **deux** de ces six
pads), et les bornes de **machine** (`0x4001b696`).

#### d) Ce qui reste `[HYP]`

1. **La page 2 elle-même** (la conception de Kevin, §3.32) : pads T1-T2 → pistes 7-8, LEDs 1-2
   allumées. Le chemin **pad → piste** passe par **deux sauts virtuels** : la vue des pads → un
   sous-objet en `vue+64` (accesseur `0x400764e0`, un thunk qui ajoute 64 et saute en `0x400e8646`)
   → une méthode en `+32` de sa classe. Le descripteur de classe est en `0x401001d8` (`%a0@(128)`
   y lit bien `0x400764e0`), mais **rien ne le cite** : il est construit à l'exécution, donc la
   prochaine étape est le **constructeur**, pas une recherche de littéral.
2. **Six boucles dont le rôle n'est pas tranché** (`0x400231c2`, `0x4002fa10`, `0x4002fade`,
   `0x4001b086`, `0x4001b092`, `0x40022ec2`) : élargies trop vite, elles pourraient écrire dans un
   tableau de six. À classer avant d'y toucher.

**Ce qui est acquis** : les pistes 7-8 sont **sélectionnables** (le menu en propose huit, les
bornages et les gardes suivent) — donc **testables sur la machine**. L'affichage de page, lui, reste
à faire.

### 3.56 Le plantage du 16/10 : quatre valeurs **dérivées** oubliées — et le contrôle qui rend l'oubli impossible `[FAIT]` (16/10)

`tools/gen_groove_pattern.py` (`GEOMETRY`), `tweaks/model-cycles_OS1.13/57-groove-patterns.json`.

#### a) L'écran, décodé `[FAIT]`

`M:C OS R0038 EXCEPTION V03-M3-P00300000`. Les deux chaînes sont dans l'OS :

```
4012bc8c  "M:C OS%.12s R%.04s "
4012bca0  "EXCEPTION V%02x-M%x-P%08x"
```

Le gestionnaire est `0x40078ce2` ; il est appelé par le répartiteur `0x40001976`, qui lui passe
**la trame d'exception du CPU** (`moveal 0x4049fd64,%a0` … `movel 0x4049fd68,%sp@-` … `jsr %a0@`).
Il lit **V** dans le mot format/vecteur de la trame, **M** dans `SR` (`mvzb %a2@(2)`), **P** dans
`+4` (le PC), puis **finit par `rte`** : l'instruction fautive se ré-exécute, faut à nouveau, et
l'écran reste — c'est le « brick ». Seule la **section 3** était touchée : le retour par le
STARTUP MENU est toujours possible.

`V03` = vecteur 3 = **address error** (le même champ que le `VEC:xx` de l'Octatrack) ; et
**`P00300000` n'est pas dans l'OS** (qui vit à `0x40000400`+) : le CPU avait déjà perdu ses
pointeurs. Corruption mémoire, donc — pas un refus propre.

#### b) La cause : l'**enregistrement stocké** n'a pas suivi le bloc `[FAIT]`

Le jalon 2 change le **bloc** (2 163 716 → 1 918 788), donc l'en-tête descend à `0x406be364`. Mais
le projet n'est pas qu'un bloc : sur le +Drive (et en MRAM) il est **stocké** dans un
**enregistrement = enveloppe de 272 o + image**, et le bloc finit par une **queue de 512 o** qui se
termine sur le sceau de clôture. Ces valeurs sont **dérivées** — et le triage ne les avait pas :

| valeur d'origine | ce que c'est | sites | devrait être |
|---|---|---|---|
| **2 163 988** | l'enregistrement (272 + image) | 3 | 1 919 060 |
| **2 163 200** | la queue de 512 o, relative à l'image | 4 | 1 918 272 |
| **2 163 472** | la même, relative à l'enregistrement | 1 | 1 918 544 |
| **3 629 212** | total des deux tables déployées + en-tête | 4 | 3 857 468 |

`0x400431a8` est le chemin de l'enregistrement : `movel #2163988,%d0` puis
`movel #2163988,%sp@- / pea 0x404e9b10` — **l'adresse fixe de l'enregistrement**. Et la queue se
pose par `moveal #2163200,%a0 / addal %a2,%a0` (`0x4000eefc`, `0x400118b4`, `0x4005d248`,
`0x4005d45e`), `addal #2163472,%a0` (`0x4008dac4`).

**2 163 988 − 1 919 060 = 244 928** : exactement le rétrécissement. Ces offsets tombent donc
**dans l'en-tête de projet (`0x406be364`) et les 244 928 premiers octets de la table des patterns
déployés (`0x406be380`)** — les tables que le moteur et l'interface lisent. Un index de machine lu
dans des données devenues quelconques → un descripteur de classe faux → un pointeur de méthode faux
→ `jsr` dans le vide → *address error* → l'écran → `rte` → l'écran. **Et cela arrive au
démarrage** : le projet actif passe par là (« UPGRADING ACTIVE PROJECT… », `0x4012dd21`), ce qui
explique la machine morte au premier allumage plutôt qu'un défaut d'usage.

#### c) Pourquoi aucun contrôle ne l'avait vu `[FAIT]`

- le balayage du générateur est mené **valeur par valeur**, sur une liste écrite à la main : ces
  quatre-là sont des **sommes** (image + 272, sceau − 512, patterns + kits) et n'y figuraient pas ;
- le contrôle du §3.52 ne vérifie que la **chaîne de versions** (`LEGACY`) : il ne dit rien des
  autres valeurs ;
- les bancs du jalon 2 sont au niveau des **éléments** (déplier/emballer un pattern) : ils ne
  descendent pas au niveau de l'enregistrement (§3.46) — et l'émulateur ne fabrique pas un projet.

#### d) Le correctif, et le contrôle qui rend l'oubli impossible `[FAIT]`

1. les quatre valeurs entrent dans `IMMEDIATES` → **230 écritures** (12 sites de plus) ;
2. **`GEOMETRY`** est le contrôle **inverse** : il reprend **toute** la géométrie d'origine et exige
   qu'aucun de ses immédiats ne survive dans l'image patchée hors de la chaîne de versions
   (`find_imm_sites`/`find_disp_sites`, `LEGACY` et `EXCLUDE` exceptés). C'est la chasse qui a
   trouvé le défaut, transformée en garde.
3. **Le contrôle a été vu échouer** : les quatre entrées retirées, il nomme les 12 sites ; remises,
   il passe (`aucune des 23 valeurs de la géométrie d'origine ne survit hors de la chaîne`).
   Un contrôle qui ne peut pas échouer ne prouve rien (§3.54).

Image : **1 424 octets** changés sur 1 744 192, MAIN OS
`4a300c7eaee832014539d27916635cce6fab47b09cc732888056fb3e6b14a54d`, `.syx` 894 624 o.
Vérifié en plus, sur l'image construite : le jalon 1 (56) ne laisse survivre **aucune** de ses 42
adresses relogées (une seule coïncidence, dans une donnée graphique en `0x4018fa32`).

#### e) Ce qui reste `[HYP]`

- Le chemin de l'**enregistrement** (lire puis réécrire un vrai projet stocké) n'est **pas** rejoué
  en émulation : c'est le §3.46 — le banc ne peut pas fabriquer un projet. Le contrôle statique,
  lui, est exact, et il nomme les sites.
- **À demander à la machine** : démarrage normal (l'écran d'exception ne doit plus revenir) ;
  chargement du projet courant (il doit être **refusé proprement** — version 6 contre 7) ; une
  sauvegarde puis une réouverture ; puis les pistes 7-8 (une note sur chacune, muettes sans trig).

### 3.57 Les listes à la main : **deux sites de version** et **douze comptes** oubliés — et un contrôle **vide** `[FAIT]` (16/10)

`tools/gen_groove_pattern.py` (`PATTERN_COUNTS`, `SEAL_EXCUSES`, `COUNT_EXCUSES`, `versions_near`).

Après le §3.56, la question n'était plus « ce défaut » mais « **combien d'autres** ». Le mod
repose sur des listes **écrites à la main** ; la seule façon de répondre est de rendre chacune
**inversable** : reprendre la valeur d'origine, exiger qu'elle ait disparu. Trois contrôles,
chacun **vu échouer** avant de passer.

#### a) La **version** : deux sites sur cinq `[FAIT]`

Le sceau `0xBEEFBACE` et le sceau de clôture `0xBACEF00C` marquent le bloc projet : **tout** site
qui les écrit ou les compare fixe aussi la version. Le triage n'en listait que **trois**. La
revue des **36** sites de sceau en a trouvé deux de plus, restés en 6 :

| site | ce qu'il fait | conséquence |
|---|---|---|
| `0x4005d3c4` | **écrit** un bloc (sceau, sceau de clôture au nouvel offset, version) | le bloc écrit est **v6** |
| `0x4005d43a` | **valideur du déploiement** : `moveq #6 ; cmpl %a3@(4)` | la chaîne acceptait le bloc **v7**, puis le déploiement le **refusait** — l'OS ne pouvait pas matérialiser son propre projet |

Les exceptions (justifiées, `SEAL_EXCUSES`) sont les sceaux d'**autres** enregistrements : les
morceaux de 100 o des kits et des machines, qui portent leur propre version 2 (§3.54).

#### b) Les **comptes** : douze sites oubliés `[FAIT]`

`moveq #96` apparaît **124** fois dans l'image, `moveq #95` **421** fois. Le triage n'en changeait
que trois (plus la garde). La revue a retenu les sites dont le **voisinage immédiat** utilise une
constante du pattern ou du kit — c'est ce qui distingue un compte de patterns d'un autre 96 (le
banc de sons : 96 enregistrements de 732 o à +5 192 ; les 96 **projets** du +Drive ; les 96
**sons** indexant des descripteurs de 28 o) — et en a trouvé **douze** :

- trois **boucles sur les créneaux de kit** (`0x4000ef26`, `0x4005d556`, `0x400617fa`) : pas rangé
  7 680 ou déployé 7 094, comptées **96 au lieu de 80** — la boucle lisait **122 880 octets
  au-delà du bloc**, c'est-à-dire dans l'en-tête et la table des patterns déployés : **la classe
  du plantage** ;
- quatre **bornes d'indice de pattern rangé** (pas 14 848, base 512) et cinq **clamps d'indice de
  kit** (accès `-7680 × i`) : `95` au lieu de `79`.

#### c) Le contrôle qui ne pouvait pas échouer `[FAIT]`

Le premier contrôle de version **désassemblait** sa fenêtre avec capstone. Il **passait** — et
pour une mauvaise raison : capstone rend une **liste vide** sur certaines plages (données,
instructions EMAC), donc la fenêtre était vide, donc rien n'était vu. C'est le **test de
défaillance** qui l'a montré : correctifs retirés, le contrôle restait muet. Il balaie maintenant
les **octets** (`0x70..0x77` puis l'immediat), comme celui des comptes, qui, lui, avait échoué
correctement du premier coup.

**Leçon de méthode** : un contrôle « inversé » ne vaut que s'il a été **vu refuser**. Les trois
contrôles du générateur sont désormais : `GEOMETRY` (23 valeurs de géométrie), les 36 sites de
sceau (version 7), les comptes proches de la géométrie (96 → 80, 95 → 79) — chacun avec ses
justifications nommées, et chacun vérifié en le désactivant.

#### d) Une **erreur du §3.56**, corrigée `[FAIT]`

Le §3.56 avait écrit la « fin des kits déployés » comme la **somme des deux tables + 28**
(3 857 468). C'est faux : c'est un **décalage**, `kit_offset + kit_size`. En v6 les deux
**coïncidaient** (2 948 188 + 681 024 = 3 629 212 = « tables + 28 »), et c'est cette coïncidence
qui a fait écrire la mauvaise formule. La bonne valeur est **58 328 060** (elle atteint
`0x43e5e760`, la fin des kits, qui ont déménagé). Avec l'ancienne, la queue était copiée 570 Ko
plus loin, dans les données de l'OS.

#### e) L'état `[FAIT]`/`[HYP]`

**244 écritures**, **1 452 octets** changés sur 1 744 192, MAIN OS
`66930c1052c5641ba992f48ca1fa6445f3a8d9a2ef645d7490c2efb8abcbb9c9`, `.syx` 894 624 o.
Bancs verts : `test_groove_pattern` (format, aller-retour), `test_groove` (moteur),
`groove_page_check.js` (la page construit la même image, 1 452 octets), `webbuild_check`.

`[HYP]` Ce qui reste **non prouvé**, et c'est la même limite qu'au §3.54 : le chemin de
l'enregistrement (lire puis réécrire un vrai projet stocké), le code du kit, et les neuf bornes
d'interface — l'émulateur ne les atteint pas. Les contrôles statiques, eux, sont exacts et
nomment leurs sites.

### 3.58 Jalon 3, étape **3b** : le convertisseur **v6 → v7** — écrit et **prouvé** `[FAIT]` (16/10)

`tools/machines/groove/convert_chain.S` (288 octets), `tools/re/test_groove_chain.py`.

#### a) Le contrat de registres, **lu** dans la chaîne `[FAIT]`

Le §3.49 disait « le point d'insertion est `0x4005de74` » sans dire dans quel état on y arrive. Le
prologue de la chaîne (`0x4005d9f6`) et le bloc v5 (`0x4005dd90`) le disent :

| registre | ce qu'il porte |
|---|---|
| `a2` | **le bloc** (l'image projet), 2 163 716 octets |
| `a3` | le drapeau « converti » (peut être nul) |
| `a4` | le contexte de la chaîne |
| `fp` (`A6`) | **l'allocateur** `0x400802e0` |
| `a5` | **le libérateur** `0x400cf044` |

et le résultat est un **octet** : le chemin de chargement fait `moveb %d0,%d7` (`0x4008d982`). Le
bloc v5 fait exactement : allouer, convertir, `memcpy(bloc, résultat, taille)`, libérer, drapeau.

#### b) Le code `[FAIT]`

Deux fonctions, **288 octets** (le §3.49 en annonçait 400 à 600) :

1. `groove_v7(dst, src)` — la **transformée pure**, sans OS : les 512 premiers octets et la
   version (6 → 7) ; 80 patterns par l'**élément** du §3.50 ; la source saute la banque F
   (16 × 14 848) ; 80 kits (7 094 copiés, 200 à zéro, puis **586** sautés côté source et **386**
   côté destination — les deux creneaux font 7 680, mais les enregistrements 7 094 et 7 294) ;
   la source saute les 16 kits non gardés (122 880) ; la queue de 512 o et le sceau de clôture
   `0xBACEF00C` à `+1 918 784`.
2. `groove_chain()` — la **colle** appelée par la redirection : elle ne touche **ni d5, ni d6, ni
   d7** (le chargement lit `%d6` *après* la chaîne, `0x4008d9c8`), refait le contrôle de fin en v7
   et rend l'octet attendu.

#### c) Le banc, et les **quatre** fautes qu'il a attrapées `[FAIT]`

| | |
|---|---|
| **A** | le code s'assemble et se **lie** (288 o) |
| **B** | la transformée rend **exactement** la référence Python, octet pour octet |
| **C** | les 80 patterns sont, un par un, la sortie du **convertisseur d'élément déjà prouvé** ; kits, queue, sceau |
| **D** | la **colle s'exécute** (allocateur et libérateur remplacés par des stubs) : le bloc de l'image **devient un bloc v7 valide**, le drapeau est posé, elle rend 1 |

Quatre fautes réelles, toutes trouvées par le banc et pas par relecture : le saut de creneau de
kit confondu entre source (**586**) et destination (**386**) ; un `jsr <étiquette>` que GNU as
sort en **absolu sans lien** (la cible valait 0) ; les arguments de `groove_v7` **inversés** (en
m68k le premier argument est le **dernier** empilé) ; et le résultat lu comme un **entier** alors
que le chemin de chargement ne lit que l'**octet bas**.

#### d) Ce qui reste `[HYP]`

- le **logement** (288 octets : la cave du convertisseur d'élément en fait 182 — il faut une
  cave plus grande, ou un masque de sprite libéré et sa redirection de constructeur, §3.49.d) ;
- la **redirection** en `0x4005de74` (`jsr` + `nop`, 42 octets) et le **générateur** ;
- et le seul contrôle que le banc ne peut pas faire : la **chaîne entière dans l'OS**, parce que
  l'émulateur ne fait pas le démarrage (les constructeurs, les sémaphores, l'allocateur) — c'est
  la limite du §3.46, toujours la même.

## 4. Le chemin menant au premier firmware Groove

1. **Liste d'édition des mini-zones** `[FAIT]` (§3.8) : les trois constructions de la zone
   événements, les quatre du cluster BSS, la décision **option B** pour le groupe déroulé (A ne
   tient pas : aucune marge après `0x40058e06`), le tri complet des **16 bornes candidates**
   (10 comptes de pistes, 6 valeurs étrangères), et la **fermeture du trou du census** : la zone
   événements compte **six** tableaux par piste, dont deux invisibles aux littéraux (§3.8.e), et les
   **bornes des lignes simples** (§3.8.f : boucle maîtresse `7006`→`7008`, params
   `0x18c`→`0x210` ×2, tampons de travail `0x120`→`0x180`), avec les décoys de la boucle des voix
   (tables de 6 **machines**, pas 6 pistes).
2. **Bancs de contrôle** `[FAIT — jalon 1]` (§3.6, §3.11) : `tools/re/test_groove.py` — pistes 0-5
   octet pour octet identiques au stock, pistes 6-7 jouent et sont muettes sans trig, isolement des
   pistes neuves, banc `0xFF` **accueil par accueil**, appels de machine par piste. Les hooks de
   lecture ne sont plus nécessaires (le banc `0xFF` couvre les accueils que la boucle touche) ; le
   stub de démarrage est retiré (§3.10).
3. **Générateur** `[FAIT — jalon 1]` : `tools/gen_groove_8.py` écrit
   `tweaks/model-cycles_OS1.13/56-groove-8tracks.json` (179 écritures) : les bornes, les 154 littéraux
   relogés (lignes + deux mini-zones, sites vérifiés par désassemblage), les constructions des
   mini-zones, et une **assertion de non-recouvrement** des accueils. **Tout en DDR** (§3.10).
   Restent, jalon 2 : le **mixeur est déjà à 8** par le relogement du cluster (§3.13) — il reste
   **deux bornes à trier** (`0x400564cc`, `0x4005617c`, §3.13), les 10 entrées de descripteurs, le pas
   du pattern et la conversion des projets, l'interface (non décodée). La mesure mémoire est faite
   (§3.11.H).
4. Prouver en émulation avec `tools/re/test_load8.py` (pistes 0-5 octet-identiques stock ; 7-8 jouent
   avec machine TONE ; pile impeccable) — plus le banc `0xFF` ; la vérification MIDI/note par piste
   relève de la machine (l'ISR complet ne s'émule pas).
   **Fait (§3.16/§3.17)** : la famille `0x422ff1xx` et la famille `0x40a788xx` sont relogées, leurs
   bornes portées à 8 et leurs gardes à 7. **Seul point laissé ouvert** : `0x400564cc` (deux lectures
   incompatibles ; décision assumée de ne rien toucher — §3.17.b).
5. Chaque jalon publie son SHA-256 du MAIN OS (notes/55 §2bis) ; essai machine par Maxime avec la
   liste du §3.6.

**Jalon 1 publié** (13/10) : `56-groove-8tracks.json`, 179 écritures, 712 octets modifiés, MAIN OS
`d7ea09e22f8ede8e54ce5b5c37fd69fdcf282ccaf2c97cae0052265409986171` (OS d'origine
`cc99d4f0175d34d1e91d046e6ec85a5e8ab58ab9edbb3c24406acd48cb99ee98`). Le générateur passe `--check`.

**Jalon 1 + 2 corrigés** (16/10, §3.56 et §3.57) : `56-groove-8tracks` + `57-groove-patterns`
(244 écritures, 1 452 octets), MAIN OS
`66930c1052c5641ba992f48ca1fa6445f3a8d9a2ef645d7490c2efb8abcbb9c9`, `.syx` 894 624 o. C'est le
candidat **après** le plantage : les deux générateurs passent `--check`, et les trois contrôles du
second (géométrie, version, comptes) nomment leurs sites quand on les désactive.

## 5. Ce qui compte pour la suite

- **Dix lignes** (§3.4) : huit se relogent par réécriture de littéraux (5 + 2 + 9 + 1 + 4 + 4 + 4 +
  2 neufs), deux sont des **mini-zones entrelacées** qui demandent en plus des retouches de code
  (§3.5) : bornes à porter à 8, un groupe déroulé de six instructions à allonger, deux décalages
  figés et une comparaison de fin absolue.
- **Accueils** : **tout en DDR** — la fenêtre `0x4230dc10..0x4232d1a8` (≈128 Ko, aucun littéral, dans
  le BSS remis à zéro au démarrage), corrigé au §3.10 : le SRAM n'a pas la place (plus grand trou
  962 o, tampons de sortie 1024) et la couture SRAM n'a que ~550 o libres. Aucun stub de nettoyage
  n'est donc nécessaire ; à mesurer : le coût des lignes chaudes passées en DDR.
- **La zone du panneau n'est plus touchée** (§3.1) : entrées, maintien et anti-rebond restent
  intacts ; c'est la plus grosse réduction de risque de la séance.
- **Les contrôles** (§3.6) : census durci, hooks de lecture, banc `0xFF`, stub de démarrage si
  besoin, liste machine — la seule conséquence qu'aucun contrôle en atelier ne couvre est une ligne
  touchée par l'UI/le panneau/l'USB/le MIDI ; c'est l'objet de la liste machine.
