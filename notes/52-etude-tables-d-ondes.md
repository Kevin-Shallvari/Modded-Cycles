# 52 — Étude : une machine qui joue les tables d'ondes de l'utilisateur

Demande de Kevin (09/10/2026) : une machine à tables d'ondes ; d'abord chercher ce qui pourrait l'empêcher. Puis
précision : les tables sont **celles de l'utilisateur**, rangées sur la mémoire de 1 Go et chargées par le système
d'échantillons de Model-TG ([31](31-model-tg.md)), pas des tables que nous fabriquons. §1 à §8 : l'étude (09/10/2026,
avant le code). §9 à §12 : la machine construite (`36-wavetable-tg.json`, « Wave »), ses essais sur la machine et sa
charge ; là où l'étude et la réalisation diffèrent, la réalisation fait foi.

## Réponse courte

- **Rien de bloquant** côté calcul : le Cycles fait déjà des tables d'ondes en logiciel (CHORD, §2 ; MACRO,
  [43](43-machine-macro.md)). Sur les Waldorf / PPG, le processeur tenait l'interface et des puces dédiées les
  oscillateurs `[HYP : documentation publique]` ; ici tout se fait sur le ColdFire.
- Model-TG a déjà un mode « Wave » dans son Sampler (§3). La machine doit apporter ce qu'il n'a pas : surtout un son
  sans repliement quand on joue haut (§4).
- Décidé par Kevin : **16 bits propres**, pas de réduction de bits (§5) ; **copies adoucies par octave, préparées au
  chargement de la table** (§4).
- **Construite** (§9) : 8e machine avec Model-TG, essayée sur la machine le 09/10/2026 (§10). Le son « glitché » venait
  d'Elektron Transfer, qui rééchantillonne les fichiers 44,1 kHz en 48 kHz (§10) ; pas du moteur. Expérimentale, pas
  encore dans le flasher.

## 1. Points ouverts

1. ~~Smooth~~ : forme du fondu entre deux trames (plus franc au milieu), pas un filtre (`wave_fill`) `[FAIT]`.
2. Lire un échantillon chargé par Model-TG : non protégé tel quel (§3bis) ; deux retouches, prouvées (§3ter).
3. Où ranger les copies : `0x46800000..0x47F00000`, 23 Mo libres (§4) `[FAIT]`.
4. Choix du sample : imiter le Sampler de Model-TG (Kevin). Son chemin `[FAIT, source]` : un fichier ouvert dans le
   navigateur de presets (FUNC + MACHINES) échoue comme preset ; `preset_fail_hook` vérifie qu'une piste est un
   Sampler (`any_sampler`, machine 6, sinon « Select sample machine first! »), charge le fichier (`refresh_tracks`),
   range son empreinte dans le nom du son (`name_store`) ; au rechargement du projet, `name_probe` (machine 6 aussi)
   la remet dans `track_hash`, ce qui protège la case (§3bis). Imiter = accepter aussi notre machine à ces contrôles
   (`any_sampler` et `name_probe`, §3ter) ; la protection suit alors d'office.

## 2. Les tables de CHORD `[FAIT]`

- Pointeurs : 32 mots à `0x40118590` ; le 1er vise une table en SDRAM (`0x40118648`), les autres la SRAM interne
  (`0x80001c5c..0x800074b4`, `0x8000cac0..0x8000eae0`), remplie au démarrage (`CY_SRAM_INIT`,
  `gen_syntakt_engines.py`).
- **257 mots de 32 bits** par table : un cycle de 256 échantillons et une garde (`t[256] = t[0]`).
- 30 formes douces (2 à 16 harmoniques au-dessus de 1 %) : presque sans repliement jusqu'à ~1 kHz. CHORD évite le
  problème en n'ayant que des formes pauvres ; ce n'est pas le cas des tables de l'utilisateur.

## 3. Le mode « Wave » de Model-TG `[FAIT : code de Model-TG]`

- Trames de 32 à 4 096 échantillons (2 048 pour Serum / Vital) ; potards Wave Pos, Smooth, Detune.
- Pas de Lo-fi dans ce mode (effets réservés à One shot / Loop / Slice ; Filter et Res pris par Smooth et Detune).
- Lecture directe de la trame : une table riche jouée haut se replie (§4).

## 3bis. Durée de vie d'un échantillon `[FAIT : source de Model-TG v1.1.0]`

- `ensure_loaded` range chaque fichier dans une case (`slot_hash`, `slot_base`) ; s'il manque de place, `evict_one`
  vide la case de plus bas niveau (`slot_level`).
- Niveau 3, jamais chassé : la case lue ou attendue par une piste (`track_slot`, `track_pend`, `track_hash`).
- `track_hash` n'est posé que pour une piste **Sampler** (machine 6, `name_probe`) ; toute autre machine vaut 0 :
  son échantillon devient chassable.
- Compactage (`rebuild_slots`) : toutes les pistes à −1, puis les échantillons sont rechargés ailleurs et les pistes
  repointées (`refresh_tracks`). Une adresse gardée d'un bloc à l'autre peut donc viser autre chose.

Conséquences pour la machine : relire `track_slot` puis `slot_base` à chaque bloc (−1 : silence) ; refaire les copies
quand le couple (empreinte, adresse) change ; et soit faire compter sa piste comme Sampler dans `name_probe`, soit
partir du mode Wave de Model-TG lui-même.

## 3ter. Les contrôles « est-ce un Sampler ? » de Model-TG `[FAIT : source v1.1.0, lecture]`

Machine 6 testée en 15 endroits (octet `+38` du son, ou `trk_mach`). Notre machine (index 7 avec Model-TG) :

| Où | Rôle | Pour notre machine |
|---|---|---|
| `any_sampler` (`preset_fail_hook`) | le navigateur charge un fichier s'il y a un Sampler sur **une** piste, pas forcément la cible | **accepter 7**, et tester la **piste cible** (Kevin : la table se charge qu'il y ait un Sampler ou non) |
| `name_probe` | remet l'empreinte du nom dans `track_hash` (protection, §3bis) ; lit aussi l'état du Sampler (`st_apply_c`, menus) | **accepter 7**, en sautant l'état du Sampler |
| `tok_of` | lit l'empreinte « SMP… » du nom (verrous de sample par pas, `sp_lock`) | à accepter si l'on veut une table par pas (option) |
| `pool_store_hook` | sample rangé dans le Sound Pool pour un verrou | idem (option) |
| `wp_id` | dessin de la forme du sample à l'écran | option (afficher la table) |
| `gran_menu_open`, `mm_open` | menus du Sampler (modes, réglages) | laisser : pas pour nous |
| `fh_ours` | filtre du Sampler | laisser |
| `rp_arm` | rééchantillonnage vers une piste Sampler | laisser |
| `mc_commit_hook`, `restore_hook` | valeurs par défaut du Sampler au changement de machine | laisser |
| `trk_mach` (silence d'une prise, gain d'une prise, mutes) | lecture des prises du Sampler | laisser |

Deux retouches de la source (comme `ST_PATCHES` de `gen_model_tg.py`), +64 o :

- `preset_fail_hook` appelle `wt_or_any` : 1 si la piste cible est notre machine, sinon `any_sampler` d'origine ;
- `name_probe` accepte aussi la machine 7 : empreinte lue, état du Sampler (`st_apply_c`, modes, options) sauté.

**Prouvé en émulation** (09/10/2026, `build/wt-proof/test_wt_select.py`, hors dépôt) `[FAIT]` : Model-TG construit avec
et sans (binutils 2.46, qui redonne `30-model-tg*.json`), son vrai code exécuté, 22 vérifications :

| Cas | Origine | Retouché |
|---|---|---|
| Fichier ouvert sur notre machine, aucun Sampler | « Select sample machine first! » | chargé, empreinte dans le nom |
| Notre machine avec un Sampler ailleurs ; piste Sampler ; Kick avec ou sans Sampler ; notre machine sur une autre piste que la cible | — | identique |
| Projet rechargé (`name_probe`, `load_pending`) | notre piste sans table | table reprise et mise en attente ; pistes Sampler, modes et options identiques ; Kick nommé « SMP… » et notre piste sans jeton ignorés |
| Place cherchée (`evict_one` jusqu'au refus) | notre table chassée | gardée ; le fichier inutile part |
| Compactage (`rebuild_slots`, `refresh_tracks`) | plus de table | notre piste vise toujours sa table |

Limites : chargeur (`ensure_loaded`) simulé, navigateur avant `preset_fail_hook` non émulé, notre machine n'existe
pas encore (octet `+38` = 7 posé à la main).

## 3quater. Navigateur dédié (idée de Kevin, à étudier)

Un navigateur pour notre machine, limité à un dossier fixe (`/Wavetables/`). Le flashage n'écrit pas sur la mémoire :
le dossier est créé par notre code au premier usage, comme Model-TG crée `/Slices/` et `/Resampled/` (`0x4007c262`,
« créé s'il n'existe pas », `mk_write`) `[FAIT]`. Elektron Transfer y dépose les tables comme ailleurs (Kevin) `[HYP :
à voir une fois sur la machine]`. Deux voies : le navigateur de l'OS ouvert dans ce dossier et bloqué dedans, ou un
petit écran à nous.

**Lister un dossier depuis notre code** `[FAIT : lecture du code ; non émulé]` (modèle : la commande « ReadDir » du
MIDI, `0x40088b7c`) :

- `0x4007aa78(chemin, h[4])` ouvre un dossier (0 / −1 : système non monté, chemin > 255 o, pas un dossier) ;
  `0x4007ab26(h, d)` lit l'entrée suivante (`dirent2_t`, 276 o : +0 inode, +4 type, 1 = dossier, +20 nom) ; >0 entrée,
  0 fin ; `0x4007aa66(h)` revient au début ;
- `0x4007de78(inode, out[4])` : {inode, empreinte, taille, +16}, ce que donne `getEntry` ; −1 pour un dossier ;
- `0x4007ac46(chemin)` crée **un** dossier (0 créé, −1 déjà là ou parent absent) ; l'OS crée ainsi `/inbox`
  (`0x4008334a`). Chemin sans « / » final `[HYP]` ;
- tous prennent le verrou du système de fichiers (`0x40fe6df0`, peut attendre la mémoire) : **tâche de l'interface
  seulement**, jamais l'interruption audio. Aucune allocation. ~200–300 o de code.

**Bloquer le navigateur de l'OS dans le dossier** `[FAIT : lecture du code ; HYP : accroches]` :

- le dossier retenu est l'identifiant global `0x40148cb0` ; `changeDir` `0x4007d1ca` refuse un identifiant invalide ;
- accroches proposées : ouverture `0x400a6c20` (8 o : si la piste active est notre machine, garder le dossier, aller
  dans `/Wavetables`, curseur à 0), fermeture `0x400a40e2` (8 o : rendre le dossier d'avant), entrée dans un dossier
  `0x4003fa1e` (6 o : refuse `..` et les sous-dossiers), touches (`0x40118468`, `0x401184b4`, 4 o chacune : touche 12
  ferme au lieu de remonter, appui long et touche 5 avalés) ; option : dossier effacé pendant l'ouverture
  (`0x4003edde`) ;
- aucun recouvrement avec les tweaks versionnés ni le navigateur multiligne (#52) ; le Sound Pool n'est atteint
  qu'à la racine ;
- risques : dossier retenu laissé à `/Wavetables` pour les autres pistes si la fermeture est manquée (rendu aussi à
  l'ouverture suivante) ; menus FUNC (créer, renommer, effacer un dossier) encore actifs sauf à les avaler ;
- le choix d'un fichier passe par `preset_fail_hook` : `wt_or_any` (§3ter) le charge déjà pour notre machine.

**Décidé (Kevin, 09/10/2026) : le navigateur de l'OS, bloqué dans le dossier.** Sous-dossiers navigables : seul le passage
au-dessus de `/Wavetables` est refusé (`..` et touche 12 comparent le dossier courant à celui de `/Wavetables` ; à ce
niveau, la touche 12 ferme). Menus FUNC laissés tels quels. Dossier absent : créé, ouvert vide. **Prouvé en émulation** (09/10/2026, `build/wt-proof/wt_browser.S` et `test_wt_browser.py`, hors dépôt) `[FAIT]` :
350 o de code + 40 o de données, 5 accroches : ouverture `0x400a6c20` (8 o), fermeture `0x400a40e2` (8 o), YES sur
`..` `0x4003fa52` (10 o), touche 12 `0x400a6f9c` (10 o), touche 12 tenue `0x400a70b0` (6 o, `/Wavetables` au lieu de
`/`). Vrai code de l'OS (ouverture, fermeture, YES, touches, `changeDir`, relecture du dossier) avec et sans ; seuls
remplacés : les primitives du système de fichiers (un petit arbre), l'allocateur, l'affichage. 21 vérifications :

| Cas | Origine | Retouché |
|---|---|---|
| Ouverture sur une autre piste | dossier retenu | identique |
| Ouverture sur notre piste | dossier retenu | `/Wavetables`, curseur en haut |
| Entrer dans un sous-dossier, en ressortir par `..` ou la touche 12 | — | permis |
| `..` dans `/Wavetables` | remonte à `/` | rien |
| Touche 12 dans `/Wavetables` | remonte à `/` | ferme le navigateur |
| Touche 12 tenue | `/` | `/Wavetables` |
| Fermeture, puis autre piste | — | dossier d'avant rendu |
| Fermeture manquée | — | rendu à l'ouverture suivante sur une autre piste |
| `/Wavetables` absent | — | créé une fois, ouvert vide |

Aucun recouvrement avec les 85 tweaks versionnés. Limites : système de fichiers simulé (la vraie création du dossier
sur la mémoire est à voir sur la machine) ; `..` reste affiché en tête de `/Wavetables` (sans effet) ; dossier effacé
pendant l'ouverture (`0x4003edde`, vers `/`) non traité ; machine lue dans le kit (`*0x40a78888 + 28 + 100 t`, octet
`+38`).

Comparaison : le navigateur de l'OS donne défilement, noms longs, multiligne et écoute sans rien dessiner (4–5
accroches) ; un écran à nous demande dessin, encodeur et touches, en plus de la lecture du dossier.

## 4. Repliement

**Le problème.** Une forme riche (Serum, Vital) a des harmoniques jusqu'à la 1 024ᵉ. Jouée haut, celles au-delà de
24 kHz se replient en sons parasites, non harmoniques. Mesuré sur une table KRC : audible dès ~Do 2–Do 3.

**Remèdes comparés** (prototype, `build/wt-proto/`, hors dépôt) :

| Remède | Résultat |
|---|---|
| Filtre passe-bas après l'oscillateur | inutile : le repli est déjà dans la bande audible |
| Saturation, filtre IIR après l'oscillateur | idem |
| Suréchantillonnage ×2 | −7 à −13 dB seulement, encore audible dès ~Do 3 |
| **Copies adoucies par octave** (moins d'harmoniques plus on monte) | supprime le repli |

**Décidé.** Table 16 bits → copies adoucies par octave → oscillateur (choix ou fondu de la copie selon la note).
C'est le remède des tables de Serum / Vital `[HYP]`.

**Quand les préparer.** Au chargement de la table, en tâche de fond, libérées au déchargement ; pas au démarrage :

| | Estimation `[HYP : à mesurer sur la machine]` |
|---|---|
| Une trame de 2 048 | ~1 ms |
| Table de 256 trames | ~0,3 s |
| Tout le dossier KRC au démarrage | 2–3 s |
| 100 grandes tables au démarrage | 25–30 s |
| Mémoire | ~2× la table |

Mesures de la machine construite (copies par demi-octave, 8 points par harmonique) : §12.

**Copies : choix** (Kevin, 09/10/2026, sans écoute) : **une copie par demi-octave**. Proposé avec : fondu entre les
deux copies voisines selon la note (pas de saut de brillance), coupure franche, et chaque copie garde les harmoniques
dont le repli tombe au-dessus de 20 kHz (inaudible). Perte de brillance au pire ~17–20 kHz.

| Table | Taille (16 bits) | Avec copies (~3×) |
|---|---|---|
| Plus grande du dossier KRC (64 trames de 2 048) | 256 Ko | ~0,75 Mo |
| Serum / Vital maximale (256 trames de 2 048) | 1 Mo | ~3 Mo |
| 6 pistes, 6 grandes tables KRC / 6 tables maximales | — | ~4,5 Mo / ~18 Mo |

Dossier KRC mesuré (2 234 fichiers) : tables Serum de 4 à 64 trames de 2 048 ; WaveEdit 64 × 256 ; le reste en un
cycle. Les dossiers « Single-cycle » donnent chaque forme en 8 tailles (16 à 2 048 points) `[HYP : déjà limitées en
bande]`.

**Où ranger les copies** `[FAIT : lecture du code]` : **`0x46800000..0x47F00000` (23 Mo)**, vue avec cache.
- La pile en `0x48000000` (`0x400004f2`) ne sert qu'au démarrage : `main` (`0x400cefa0`) passe à la première tâche par
  `trap #0` (`0x400cf040`) et ne revient jamais à ce contexte (`0x422fee74`, cité une seule fois).
- Chaque tâche a sa pile dans le BSS (12 appels de `0x400019ec`, piles de 2 à 160 Ko) ; l'interruption audio
  (`0x40058c5e`) tourne sur la pile de la tâche en cours. Aucune pile d'interruption à part.
- Aucun code de l'OS, de Model-TG (tout est calculé sous `REGION_END`), ni de nos tweaks n'y écrit ; seuls des
  flottants et le `move.l d0,0x48000000` qui redémarre la machine (juste au-dessus) apparaissent.
- Conditions : remplir soi-même (rien n'est remis à zéro) ; vue avec cache seulement (la vue `0x4e8…` est sous l'ACR1
  de Model-TG, en écriture immédiate) ; pointeurs sous `0x48000000` (`sp_lock` traite ceux du dessus à part).

## 4bis. Filtres (décidé, 09/10/2026)

Comme Acid avec Model-TG ([51 §6](51-machine-acid.md)) : **deux filtres**, pour plus de sculpture du son (Kevin).
- Dans la machine : le passe-bas d'Acid (échelle 4 pôles, coude dans la boucle), avant l'étage d'amplitude ; SWEEP =
  coupure, CONTOUR = résonance.
- Après l'étage d'amplitude : celui de Model-TG, comme toute machine (`amp_hook` : Attack, `gflt_run`,
  rééchantillonnage) ; MACHINE tenue + SWEEP / CONTOUR ; ouvert sans résonance, il n'est pas calculé.

Chaîne : table → copies → oscillateur (COLOR + SHAPE × enveloppe) → passe-bas d'Acid → amplitude d'origine (DECAY,
GATE, PUNCH) → Model-TG (Attack, filtre, rééchantillonnage) → mixeur.

## 4ter. Potards (Kevin, 09/10/2026 ; état final)

Premier choix : SHAPE = enveloppe → position. Remplacé le soir même (Kevin) : l'enveloppe de position passe sur
MACHINE tenue + COLOR, un paramètre ajouté, et SHAPE devient une enveloppe de coupure.

| Potard | Rôle | MACHINE tenue + |
|---|---|---|
| COLOR | position dans la table (« Position ») | **Env Pos** : 0 = rien ; plus haut, chaque note part plus loin dans la table et revient vers COLOR |
| SHAPE | enveloppe → coupure, bipolaire, ±6 octaves (« Flt Env », 64 : rien) | — |
| SWEEP | coupure du passe-bas d'Acid, 20 Hz → 20 kHz (« Cutoff », défaut 127) | filtre de Model-TG |
| CONTOUR | résonance (« Reso », défaut 0) | résonance de Model-TG |
| DECAY | chaîne d'ampli d'origine et durée des deux enveloppes (défaut 60) | Attack de Model-TG |
| GATE, PUNCH | chaîne d'ampli d'origine ; PUNCH = accent | — |

Env Pos : paramètre commun (groupe 7) à la place libre `0x0a`, `k` = 27, comme Attack / Filtre / Résonance de
Model-TG ; sa valeur vit dans un mot que Model-TG sauve déjà `[FAIT : lecture du code]`. Unipolaire : COLOR tenu n'a
pas de valeur par défaut au milieu.


## 4quater. Prototype (09/10/2026)

`build/wt-proto/wt_chain.py` (hors dépôt), en flottant : copies par demi-octave (22 pour 2 048 points), oscillateur
(interpolation linéaire, fondu entre trames et entre copies), passe-bas d'Acid, amplitude simple. Table KRC « Random
Explore 64 6 », trame 32, notes tenues : sans copies, le repli vaut −3 dB du son audible au Do 7 ; avec, −55 dB (le
plancher de l'interpolation). Rendus écoutés par Kevin : **jugé suffisant pour un premier jet**.

## 5. Réduction de bits (rejetée)

Essai d'écoute (09/10/2026, table KRC « Random Explore 64 6 ») : 16 / 12 / 8 bits, lissage nul / léger / fort.
Kevin n'entend presque aucune différence : **pas de réduction de bits**, ni potard. Les potards sont réservés à de
meilleures fonctions.

## 6. Mémoire cache `[HYP]`

Lecture int16 de deux trames (fondu de position) : ~6 lignes de 16 o par bloc à 65 Hz, ~46 à 1 kHz, contre 94 à 214
pour une voix du Syntakt ([23 §3](23-optimisation-charge.md)). Coût réel à mesurer sur la machine
([23 §5](23-optimisation-charge.md)). Le moteur construit lit **quatre** trames (deux copies × deux trames, §9) :
estimation à doubler, toujours pas mesurée.

## 7. Cohabitation

Machine ajoutée liée à Model-TG : version combinée `…-tg`, comme `35-acid-tg` ([51](51-machine-acid.md)), avec le
coût en taille du flasher que cela entraîne.

## 8. Prochaines étapes (mises à jour le 10/10/2026)

Les étapes de l'étude (points ouverts §1, prototype, potards) sont faites. Restent :

1. **Charge** : optimiser le rendu (§12), mesurer d'abord, à la manière de [51 §8](51-machine-acid.md), puis sur la
   machine avec le firmware de profilage de Model-TG ([31 §7](31-model-tg.md)).
2. **Correctif A** (§10) : reconnaître une table rééchantillonnée par Transfer (longueur multiple de ~2 229,1 points)
   et ramener chaque trame à 2 048 points en préparant les copies, pour que les fichiers Serum / Vital marchent tels
   quels.
3. Points non vérifiés (§10) : le chemin du potard MACHINE tenue + COLOR sur la machine ; Env Pos après sauvegarde et
   rechargement du projet ; un LFO vers Env Pos après rechargement (Model-TG ne sauve les destinations de LFO que pour
   ses trois paramètres : probablement perdu).
4. Flasher et documentation (AGENTS.md) : `FEATURES` en `experimental`, `tweaks.js`, `REF_MAINOS`, textes en + fr,
   guide (prévenir de la conversion de Transfer tant que le correctif A manque), notes de version, README,
   PROVENANCE ; puis PR en brouillon (dépend d'`acid-tg`, #66).

## 9. Réalisation `[FAIT]`

Branche `wavetable-machine` (sur `acid-tg`). `tools/gen_wavetable.py` écrit `36-wavetable-tg.json` (127 écritures,
exige `model-tg-st`) ; moteur `tools/machines/wavetable/wt.c` ; preuve `tools/emu/test_wavetable.py` (+ `wt_host.c`,
le même moteur compilé pour l'ordinateur). Compilateur : `m68k-elf-gcc` 16.2 avec les binutils 2.38 d'Ubuntu 22.04
([BUILD.md](../BUILD.md)) ; le GCC 13.3 d'Ubuntu 24.04 donne un code plus long de 0x160 o, donc d'autres octets.

**Mécanique** : celle d'Acid avec Model-TG ([51 §6](51-machine-acid.md)) ; Wave est la machine 7 (8e, après le
Sampler). Le tweak de Model-TG ne change pas : son bloc est retouché **en mémoire au démarrage**, aux sites trouvés
par motifs uniques (`gen_wavetable.py`, `find_tg`) :
- `preset_fail_hook` → `wt_or_any` et `name_probe` accepte la machine 7 (§3ter) ;
- `led_hook` (tâche des LED, une fois par bloc audio, côté interface) appelle `wt_tick`, qui prépare les copies.

**Navigateur** : les 5 accroches de §3quater, plus une sixième, `wt_cursor` (`0x400a640a`), qui note le fichier sous le
curseur pour le chargement d'avance.

**Rendu** (`wt_update` puis `wt_render`, une fois par bloc de 32 trames) :
- `wt_update` : potards, prise du sample en attente de Model-TG (`track_pend`, à la note ou voix muette), hauteur
  (`PITCH_TAB`), indice de copie (2 par octave au-dessus de `COPY_N0`), position visée (COLOR + Env Pos ×
  enveloppe), coefficients du passe-bas d'Acid (G, G², G³, G⁴, deux divisions `recip_q28`), enveloppe.
- `wt_render`, par échantillon : position glissée échantillon par échantillon (`ps += dp`, correctif des marches
  audibles à fort Env Pos) ; pour les **deux copies** voisines (fondu `cw`) × les **deux trames** voisines (fondu `pw`),
  `at()` = 2 lectures int16 + interpolation linéaire, soit **jusqu'à 8 lectures par échantillon** dans 4 trames ;
  coupe-continu (~10 Hz, `DC_R`) ; échelle 4 pôles d'Acid avec son coude ; puis chaîne d'ampli d'origine (`AMP_ENV`,
  `VCA`, `PUNCH`) et étage de Model-TG. Voix muette : bloc mis à zéro, sortie immédiate. Multiplications par l'EMAC.
- Copie pas prête : la table brute à sa place.

**Copies** (`wt_tick` → `step`, hors de l'audio) :
- 21 copies par demi-octave (`NCOPY`, 1 024 / 2^(c/2) harmoniques), le repli au-dessus de 20 kHz toléré
  (`FOLD_OK` 28 kHz) ; copies rangées à mi-niveau.
- Réserve **partagée** de 22,5 Mo à `0x46800000` (`POOL_BYTES`), plus 64 Ko de calcul jusqu'à `0x47E90000` ; une
  allocation par table, partagée par les pistes sur la même table (`al[]`, compteur) ; `plan()` essaie 8, puis 4, puis
  2 points par harmonique jusqu'à trouver la place ; sinon la table brute.
- FFT entière, sans EMAC (`m15`), deux trames par FFT (l'une réelle, l'autre imaginaire), étapes de ~`BUDGET` = 3 072
  papillons ; deux passes : d'abord les copies de 512 points au plus (`CHEAP_LG` 9, les aigus, où le repli s'entend),
  puis les grandes ; chaque passe sert dès le bloc suivant (`publish`).
- Copies rendues quand la piste n'est plus Wave depuis ~5 s.
- **Chargement d'avance** : curseur immobile 300 ms (`DEBOUNCE` 450 blocs) sur un fichier de moins de 4 Mo (`PF_MAX`)
  → chargement poli par Model-TG (`pd_mode` 1 : ne chasse que l'inutile) et copies sur une pseudo-piste (`PF` = 6) ;
  le curseur bouge : arrêt ; YES : la piste reprend le travail (`adopt`). Bogue corrigé : revenir sur le fichier en
  moins de 300 ms ne relançait rien.

**Preuves** (09/10/2026) :
- ordinateur : copies à −78 dB de la référence exacte ; repli −53 à −56 dB du Do 4 au Do 7 ; chargement d'avance
  (attente, abandon, retour, reprise sur YES) ;
- émulation, vrai firmware : démarrage (Model-TG retouché en 3 endroits exactement), lecture, copies **identiques à
  l'octet** à celles de l'ordinateur ; le firmware lit la table brute avant les copies, puis seulement les copies
  (`build/wt-proof/dbg_fw.py`) ; COLOR, Env Pos et l'enveloppe de coupure mesurés sur la table Pulsar (§10).
- Firmware essayé par Kevin : `model-tg-st,wavetable-tg`, MAIN OS `152847e6…` (BUILD.md), le même que le JSON versionné.

## 10. Essais sur la machine (Kevin, 09/10/2026)

- `/Wavetables` créé sur la mémoire par notre code `[FAIT, machine]`.
- **Son « glitché », dégradé par cycles, plus vite quand Env Pos monte** : cause trouvée. **Elektron Transfer
  rééchantillonne en 48 kHz les WAV à 44,1 kHz** : une table de 256 trames fait 1,088 Mio sur la mémoire au lieu de
  1,0 Mio (48 000 / 44 100 = 1,088, plus un en-tête de 80 o) ; chaque trame de 2 048 points en fait ~2 229 ; Wave
  découpe tous les 2 048 points, donc deux « trames » voisines sont décalées et s'annulent en partie au milieu du
  fondu. Copies des fichiers étiquetées 48 kHz, mêmes échantillons : envoyées sans conversion (1 Mio tout rond) ;
  **plus de défaut** sur la machine `[FAIT, machine]`. Le mode Wave de Model-TG à 2 048 aurait le même défaut.
  Remède prévu : correctif A (§8) ; en attendant, réétiqueter les fichiers avant l'envoi.
- « La table bouge pendant la note » : un LFO vers Env Pos, pas un défaut.
- Charge : aucun craquement ni dépassement signalé.
- Mesuré en émulation (table Pulsar), pas encore confirmé à l'oreille : COLOR 10 / 110 → brillance 261 / 481 Hz ;
  Env Pos 100 contre 0, écart de spectre 6,7 à 10 ms, 3,8 à 400 ms, 0,3 à 900 ms (retour à COLOR, DECAY 60) ;
  SHAPE 64 : brillance plate (380 → 383 Hz), SHAPE 120 : 4 234 → 879 Hz. Valeur d'Env Pos posée en mémoire : le
  potard lui-même n'est vérifié qu'à la lecture du code.
- Accès à la mémoire depuis l'ordinateur : mode Transfer de Model-TG (**Device Config › Transfer › SMP**), le Cycles
  se présente en Model:Samples ; `elektroid-cli` liste, crée un dossier et envoie (`elektron:sample:ls`, `mkdir`, `ul`) ;
  l'effacement est refusé par la machine. Fermer le flasher avant (Web MIDI tient le port).

## 11. Tables Echo Sound Works (Kevin, 09/10/2026)

Différences avec les tables KRC, utiles pour juger le son :
- beaucoup sont des **suites de formes très différentes** (« Arp Pattern », « Thick Jumps », « Chimes ») : un balayage
  rapide change de timbre par à-coups, par construction ;
- certaines formes sont très décentrées (jusqu'à 65 % de la pleine échelle) : d'où le coupe-continu (§9) ;
- fichiers à 44,1 kHz, flottants 32 bits : voir §10.

## 12. Charge et temps de préparation

Modèle du dépôt ([31 §7](31-model-tg.md)) : 1,54 cycle par instruction, 166 667 cycles par bloc à 250 MHz ; mixage
et effets ≈ 30 % du bloc ([23](23-optimisation-charge.md)) ; six pistes peuvent être Wave.

| Mesure | Valeur | Comment |
|---|---|---|
| Boucle des voix, une piste Wave | **9 799 instructions par bloc** `[FAIT, émulation]` | `build/wt-proof/cost_fw.py` : vrai firmware, Model-TG + Wave, table de test de 64 trames, note 48, SHAPE 120, SWEEP 80, CONTOUR 60, DECAY 60, moyenne de 10 blocs après 6 ; sans copies (`wt_tick` non lancé), les 4 lectures sur la table brute |
| Même banc, TONE | 7 183 `[FAIT, émulation]` | idem |
| Une voix Wave seule | ≈ 8 300, **≈ 1,46 TONE** `[HYP : calcul]` | boucle sans voix ≈ 7 183 − 5 669 (TONE avec Model-TG, [51 §8](51-machine-acid.md)) |
| En % d'un bloc | ≈ 7,6 % par voix ; six voix ≈ 45 % `[HYP : calcul]` | × 1,54 / 166 667 |
| Acid, pour comparer | 0,43 à 0,91 TONE avec Model-TG ; filtre ouvert 0,45 TONE seul | [51 §8](51-machine-acid.md) |
| Étape de préparation (côté interface) | 3,2 ms au premier jet ; maintenant **271 148 instructions au pire, ~1,1 ms** `[FAIT, émulation]` | `test_wavetable.py` (10/10/2026 : TOUT OK) |
| Copies prêtes, table de 256 trames | toutes ~2,9 s ; **aigus propres après ~0,66 s** (64 trames : ~0,17 s) `[FAIT, ordinateur]` | `build/wt-proof/esw_host.py`, `timing_host.py` |
| Place des copies, 256 trames | ~7,4 Mo à pleine qualité : ~3 tables de ce genre à la fois dans la réserve `[FAIT, ordinateur]` | `esw_host.py` |

Ce sont des instructions, pas des cycles : défauts de cache (4 trames lues par échantillon, §6) et attentes de
l'EMAC non comptés. Aucun profil sur la machine encore. Le « 46 % » donné le 09/10 correspond sans doute à ce calcul
pour six voix : une estimation, pas une mesure de la machine.

**Déjà fait** : préparation par paires de trames, étapes courtes, aigus d'abord, réserve partagée, copies partagées
entre pistes, chargement d'avance, voix muette à zéro, coefficients par bloc.

**Pistes non essayées, non mesurées** : sauter la 2e copie quand `cw` = 0 ou que les deux pointent la même table ;
sauter le fondu de trames quand `pw` = 0 ou que la position ne bouge pas ; contourner l'échelle filtre grand ouvert
sans résonance ni enveloppe (comme Model-TG) ; garder les deux divisions de `wt_update` quand coupure et résonance
n'ont pas changé ; copies plus légères pour les grandes tables (4 points par harmonique : ~2,1 s au lieu de ~2,9 s
`[HYP]`) ; copies préparées sur l'ordinateur avant Transfer (plus d'attente, fichiers ~15× plus gros, un outil web
de plus).

## 13. Table pré-travaillée par l'outil web (10/10/2026)

Décision de Kevin : sortir la préparation des copies de la machine. Un **outil web** (nouvelle rubrique du site,
`docs/convert/`, référence `tools/wt_convert.py`) convertit la table de l'utilisateur en un WAV 48 kHz que Wave lit
directement ; la machine ne calcule plus rien. Le système de copies embarqué (FFT entière, réserve de 22,5 Mo,
préparation d'avance, `wt_tick`) est **retiré**.

**Disposition du fichier** (règle fixe, partagée par l'outil et le moteur) : trames de 2048 points ; la table entière
d'abord, puis les copies **une par octave** et **plus courtes que la table** (`NCOPY` 11, 4 points par harmonique),
dans l'ordre des copies. `LGC[c]` = lg2 de la longueur de la copie c, `OFF[c]` = son décalage en points par trame (0
pour les copies pleines : elles sont la table), `S_TOTAL` = 2048 + somme des copies courtes (= 4288). Le moteur trouve
`F = slot_count / S_TOTAL` ; un fichier non converti (longueur non multiple) **ne joue rien** (plus de repli sur la
table brute).

**Ce que ça change** : `wt.c` lit `base + OFF[c] * F` et `LGC[c]`, sans `wt_tick`, sans réserve, sans repli ;
`gen_wavetable.py` n'embarque plus de FFT (ni `HMAX`/`COS_TAB`/`SIN_TAB`), ni le crochet de la tâche des LED, ni le
curseur d'avance. Le tweak passe de 127 à 126 écritures, le code de ~14 288 à 5 418 o, le BSS de 1 912 à 648 o,
l'ajout à l'image de 21 128 à 12 792 o.

**Preuves** (10/10/2026) : `tools/emu/test_wavetable.py` (TOUT OK : convertisseur bien formé et borné en bande,
démarrage, grave et aigu jouent sans lecture hors mémoire, fichier non converti muet) ; `tools/webwt_check.sh`
(`docs/convert/convert.js` == référence Python à 1 LSB près) ; `gen_wavetable --check`, `gen_flasher_tweaks --check`,
`ref_mainos --check`, `webbuild_check.sh` et `webflash_smoke.sh` verts.

**À faire** : le guide (rubrique de la machine Wave et étape de conversion) et le flasher, quand Wave y entrera ;
les §4–§12 décrivent la préparation embarquée, désormais remplacée par cette section.

## 14. Dans le flasher (11/10/2026)

Wave entre dans le flasher comme les autres machines ajoutées : une carte **Machine Wave** (rubrique *Sons et
machines*, **expérimentale**) qui **demande Model-TG** — cocher Wave coche Model-TG, et Model-TG prend alors
`30-model-tg-st` (Wave s'ajoute après son Sampler, 8e machine). La carte est incompatible avec MACRO, Acid et les
moteurs du Syntakt (même place en mémoire) ; l'écoute des samples prend `33-sample-preview-st` avec elle, comme avec
MACRO et Acid.

- `tools/gen_flasher_tweaks.py` : la carte `wave` (`requires` model-tg, `variants` `36-wavetable-tg`), la clé `with`
  de model-tg et de sample-preview ; `check_requires` accepte désormais les versions « with » de la carte demandée
  (`model-tg-st`) — un ajout qui ne va qu'avec une combinaison de Model-TG peut ainsi la demander.
- `docs/flasher/tweaks.js` et `REF_MAINOS` (10 943 combinaisons), `docs/flasher/app.js` (textes en/fr, ancre de
  guide), `docs/guide/index.html` (rubrique 15), `docs/assets/release.js` (1.35), `README.md`, `BUILD.md`,
  `PROVENANCE.md`, `tools/webflash_smoke.js` (la carte, ses combinaisons, la ligne FR).
- Tampon `2026-10-11-01` (les trois pages + `MC_BUILD`).

**Preuves** : `gen_flasher_tweaks --check`, `ref_mainos --check`, `webbuild_check.sh`, `webflash_check.sh` et
`webflash_smoke.sh` verts (Wave : avec Model-TG `model-tg-st,wavetable-tg`, avec l'écoute
`model-tg-st,sample-preview-st,wavetable-tg`, jamais avec MACRO, Acid ni les moteurs).

**À faire** : essayer sur la machine (Kevin) — flasher `model-tg-st,wavetable-tg`, convertir une table, l'envoyer
(rubrique Convert, mode SMP), la jouer.
