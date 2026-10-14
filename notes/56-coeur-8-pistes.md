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
| A. littéraux relogés (132 écritures, 536 octets) | ok |
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
   `tweaks/model-cycles_OS1.13/56-groove-8tracks.json` (132 écritures) : les bornes, les 113 littéraux
   relogés (lignes + deux mini-zones, sites vérifiés par désassemblage), les constructions des
   mini-zones, et une **assertion de non-recouvrement** des accueils. **Tout en DDR** (§3.10).
   Restent, jalon 2 : le **mixeur est déjà à 8** par le relogement du cluster (§3.13) — il reste
   **deux bornes à trier** (`0x400564cc`, `0x4005617c`, §3.13), les 10 entrées de descripteurs, le pas
   du pattern et la conversion des projets, l'interface (non décodée). La mesure mémoire est faite
   (§3.11.H).
4. Prouver en émulation avec `tools/re/test_load8.py` (pistes 0-5 octet-identiques stock ; 7-8 jouent
   avec machine TONE ; pile impeccable) — plus le banc `0xFF` ; la vérification MIDI/note par piste
   relève de la machine (l'ISR complet ne s'émule pas).
5. Chaque jalon publie son SHA-256 du MAIN OS (notes/55 §2bis) ; essai machine par Maxime avec la
   liste du §3.6.

**Jalon 1 publié** (13/10) : `56-groove-8tracks.json`, 132 écritures, 536 octets modifiés, MAIN OS
`bcdd9930a2419ad2b9c1e7c6c1e65169a0fd181b13e8153b3c30ee10538d7a28` (OS d'origine
`cc99d4f0175d34d1e91d046e6ec85a5e8ab58ab9edbb3c24406acd48cb99ee98`). Le générateur passe `--check`.

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
