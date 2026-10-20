# 62 — Wave avec les moteurs du Syntakt, MACRO et ACID ; l'enveloppe de coupure sous FUNC + SWEEP

Demande de Kevin (12/10/2026, jalon 3 de `handoff-wave-standalone.md`) : jouer Wave ([60](60-wave-autonome.md)) dans le
même firmware que les vrais moteurs du Syntakt ([20](20-moteurs-syntakt-a-cocher.md)), MACRO ([43](43-machine-macro.md))
et ACID ([54](54-machine-acid.md)), toutes les combinaisons, Wave toujours la dernière machine (choix de Kevin).
Tweaks `24-syntakt-<moteurs>[-macro][-acid]-wave.json`, `25-macro-wave.json`, `26-acid-wave.json`,
`25-macro-acid-wave.json` (127 fichiers), générateur `tools/gen_wave_combos.py`, preuve
`tools/emu/test_wave_combos.py`. Dans le même travail, les potards de Wave changent (§4). Adresses : VA de l'OS 1.13.

## Réponse courte

- **Mécanique** : celle d'ACID avec les moteurs (`gen_acid_combos.py`, [54 §11](54-machine-acid.md)), étendue d'une
  machine. `gen_macro_syntakt.build_tweak` prend `wave=` après `acid=` ; sans moteurs, `gen_macro.added_machine` avec
  MACRO et/ou ACID puis Wave. Wave est liée à **`+0x79000`** de la charge utile (variables à `+0x7b000`), la même
  place dans toutes les combinaisons, au-dessus des variables d'ACID ; notre code (la glue de `gen_wavetable.py`) suit
  le moteur et compare le son de la piste au numéro de Wave, qui change d'une combinaison à l'autre.
- **8 machines ajoutées** (5 moteurs, MACRO, ACID, Wave : 14 machines) : 116 descripteurs ne tiennent plus devant les
  rangées de `ROWS7`. `gs.ROWS8` (sans Model-TG seulement) : rangées à `+0x35960`, rangées CC à `+0x35b20`,
  enregistrements à `+0x35ce0` jusqu'à `+0x35fe0`, à la place de `REC_ATK` (Model-TG seulement). `MAX_EXTRA` passe à 8.
  Les repères de l'écran MACHINES tiennent (2 lignes de 7). Jusqu'à 7 machines, rien ne bouge : les fichiers de `main`
  gardent leurs octets (vérifié, §5).
- **Potards de Wave** (§4) : SHAPE = Env Pos (enveloppe → position), **FUNC + SWEEP = enveloppe → coupure**, rangée
  dans FINE comme le lo-fi de MACRO ([55 §8](55-macro-allegee-et-lofi.md)). Le paramètre caché d'Env Pos (`k` = 27) n'existe
  plus : plus de problème d'enregistrement ni de p-lock (issue #1 du fork de Kevin).

## 1. La place de Wave

| Décalage | Contenu |
|---|---|
| `+0x00000` .. | moteurs du Syntakt (passerelle reprise de leur tweak), ou MACRO sans moteurs |
| `+0x42000` | MACRO avec les moteurs (`gms.MACRO_AT`), variables à `+0x5b000` |
| `+0x76000` | ACID (`gac.ACID_AT`, GOV_SKIP), variables à `+0x78000` (jusqu'à `+0x782e8`) |
| `+0x79000` | **Wave** : moteur (≈ 5,5 Ko) puis notre code (≈ 2,3 Ko) |
| `+0x7b000` | variables du moteur de Wave (720 o) |

Les tampons des tables (`0x46800000` + 3 Mo × piste) ne croisent rien : sans Model-TG, la charge utile est à
`0x43000000` ; les versions Model-TG des autres machines (charge à `0x46700000`, finissant sous `0x46800000`) ne vont
jamais avec Wave. Plus grande combinaison (5 moteurs, MACRO, ACID, Wave) : 116 descripteurs, 254 126 o compressés,
image jusqu'à `0x401e81ee` (limite `0x40200000`).

## 2. Ce qui change dans les outils de `main`

- `gen_syntakt_engines.py` : `ROWS8`, `set_rows` (au-delà de 7 machines), `MAX_EXTRA` = 8, `detours_asm(…, fenv=)` et
  `fenv_asm` (§4), `fenv_index`.
- `gen_macro_syntakt.build_tweak(…, wave=)` : Wave après ACID ; `wave["post"](out)` ajoute nos écritures avant que la
  charge utile soit mesurée (taille rangée exacte).
- `gen_macro.added_machine` passe `fenv` aux détours.
- `gen_flasher_tweaks.py` : la carte Wave rejoint (`joins`) les moteurs, MACRO et ACID ; ACID et MACRO portent leurs
  versions avec Wave ; une version sans fichier Model-TG est permise (Wave n'en a pas).

## 3. Conflits

Chaque fichier Wave est incompatible avec tous les tweaks de machines ajoutées (`gen_wavetable.all_ids`), Model-TG et sa
base : un firmware n'en prend qu'un, le flasher choisit le bon selon les cartes cochées.

## 4. Les potards de Wave : Env Pos sur SHAPE, l'enveloppe de coupure sous FUNC + SWEEP

**Le défaut** `[FAIT : désassemblage et émulation]`. Env Pos était un paramètre commun (descripteur 10, mot `k` = 27,
groupe 7), à la manière d'Attack, Filtre et Résonance de Model-TG. Sans Model-TG :

- l'OS l'inscrit pour **toutes** les machines (`(k = 27, machine) → descripteur 10` pour les machines 0 à 6, et
  `0x4005a50a(10) = 7`) ;
- la sauvegarde du son (`0x4005afa0`) ne garde que 23 mots de paramètres : le mot 27 revenait à 0 au rechargement
  ([60](60-wave-autonome.md)) ;
- l'identifiant de rangée des p-locks vient de `0x4010ee4c[k]`, 23 entrées : un p-lock d'Env Pos tombait sur la rangée
  d'un autre paramètre ([56 §3.1](56-ajouts-davidcaruso.md)) ;
- surtout, **aucune couche « MACHINE tenue + potard » n'existe sans Model-TG** : c'est le code de Model-TG qui la
  faisait (`other_descr`). Dans Wave autonome, Env Pos n'était donc joignable par aucun potard.

**La correction** (choix de Kevin, 12/10/2026) :

| Potard | Avant | Après |
|---|---|---|
| COLOR | position | position |
| SHAPE | enveloppe → coupure (64 : rien) | **Env Pos** : enveloppe → position (0 : rien) |
| SWEEP | coupure | coupure |
| **FUNC + SWEEP** | — | **enveloppe → coupure**, rangée dans FINE (64 : rien, `OFF` à l'écran, `-64` .. `+63`) |
| CONTOUR | résonance | résonance |
| DECAY | durée de l'enveloppe (coupure, position, ampli) | idem |

FINE (mot 17, descripteur 43) n'est sous aucun potard dans l'OS d'origine ([55 §8.1](55-macro-allegee-et-lofi.md)) :
le reprendre ne coûte rien, et il est **enregistré, p-lockable et destination de LFO**. Wave ne l'utilise plus pour
s'accorder. Mécanique de MACRO : dans `knob_vec` (détour de `0x4001e8da`), sur la piste Wave, FUNC tenu et le potard
SWEEP (`d2` = 6), l'entrée lue devient 16, que `rec_build` met à FINE ; les fonctions de l'objet d'interface de FINE
(`0x40a71754 + 100 × 43`, +0x50 pas, +0x20 texte, +0x30 dessin) deviennent `fenv_step`, `fenv_fmt`, `fenv_draw`. Avec
MACRO dans le même firmware, ses vérifications ratées passent à celles de Wave ; MACRO garde FUNC + PITCH. Sans Wave,
les détours gardent leurs octets.

## 5. Preuves `[FAIT en émulation]`

- **`main` inchangé** : `gen_macro.py`, `gen_acid.py`, `gen_acid_combos.py` (MACRO + ACID, les 5 moteurs avec MACRO et
  ACID, avec et sans Model-TG) `--check` : à jour après tous les changements.
- **`tools/emu/test_wavetable.py`** (Wave seule) : TOUT OK, dont `fenv_ui.py` : FUNC + SWEEP → FINE sur la piste Wave,
  SWEEP seul → la coupure, les autres potards et les autres machines comme l'OS d'origine, un pas par cran (vrai
  `0x4000b7d6`), texte `-64` .. `OFF` .. `+63` (vrai sprintf), fenêtre de valeur pixel pour pixel comme l'OS dessine un
  texte, chaque caractère dans la grande police.
- **`tools/emu/test_wave_combos.py`**, TOUT OK le 12/10/2026 sur un échantillon : `acid-wave`, `macro-wave`,
  `macro-acid-wave`, `syntakt-sd-wave` et la plus grande, `syntakt-sd-cp-toy-bits-swarm-macro-acid-wave` (14 machines,
  `ROWS8`). Pour chacune : démarrage (charge utile identique à la combinaison sans Wave, hors ce qui compte les machines
  et la place de Wave ; ACID et Wave sans MACRO : comparée à `macro-acid` au-dessus d'ACID), interface
  (`test_syntakt_machines.py`), FUNC + SWEEP (et MACRO qui garde son lo-fi), notre code au numéro de Wave (chargeur,
  YES, table retenue, identité Transfer), son (pistes Wave identiques à Wave seule, les autres à la combinaison sans
  Wave, à l'arrêt d'une voix muette par le régulateur près). Les 122 autres combinaisons : générées et vérifiées par
  `check_overlaps.py`, pas jouées une à une.
- **Place des détours** : avec MACRO, ACID, Wave et 4 ou 5 moteurs, les détours dépassaient leurs 2 Ko (2 070 o) ;
  Wave reprend alors le pas et le dessin du lo-fi de MACRO (`fine_draw`, le formateur passé dans `a1`) ; sans Wave,
  les octets de MACRO ne changent pas.
- `tweaks.js` passe de 8,25 à 12,4 Mo avec les 127 fichiers.

## 6. Reste à faire `[À FAIRE]`

- Sur la machine (Kevin) : Wave seule, puis une combinaison avec les moteurs et ACID ; FUNC + SWEEP sur une piste Wave
  (texte à l'écran, effet sur la coupure), SHAPE (Env Pos) ; enregistrer, recharger.
- Les images propres à Wave (fiche, onde) : à reprendre pour toutes les machines ajoutées.

## 7. Dans l'OS 2.1 (21/10/2026)

Décision de Kevin : l'OS de sa branche de prévisualisation porte Wave à la place de Model-TG. `36-wavetable.json`
déclare `conflicts` avec `model-tg-st` (notes/61 : même glue SMP, mêmes six sites de l'OS), et les 127 combinaisons de
`gen_wave_combos.py` sont construites sans Model-TG : les deux machines ne peuvent pas tenir dans le même firmware,
alors que l'OS 2.0 de `main` est bâti autour du Sampler de Model-TG.

Ce qui change dans `os.json` (`"version": "2.1"`, statut `experimental`) :

- `"tweaks"` : plus de `model-tg-st` ni de `sample-preview-st` ; `syntakt-tg-<moteurs>-macro-acid` est remplacé par
  `syntakt-sd-cp-toy-bits-swarm-macro-acid-wave` (14 machines, numérotation de `gen_wave_combos.py` : moteurs 07 à 11,
  MACRO 12, ACID 13, Wave 14) ;
- `"machines"` : le Sampler disparaît, Wave entre en dernier ;
- `"features"` : lignes `model-tg` et `sample-preview` retirées ; ligne `wave` ajoutée (`cat` `sound`, `guide` `wave`,
  notes 58 à 62).

Vérifications `[FAIT]` :

- `tools/build.py --os` construit l'OS : MAIN OS `5af7e300…d49bf3efac`, 504 528 o de charge utile depuis le Syntakt ;
- `tools/ref_mainos.py` a réécrit `REF_MAINOS` et `REF_MODS` (12 tweaks) ;
- `tools/check_overlaps.py` et `tools/registry.py --check` passent (411 tweaks, 110 masques libres) ;
- `tools/webflash_smoke.sh` avec les deux fichiers officiels : l'OS construit dans la page donne le même MAIN OS que
  `REF_MAINOS`, chaque tweak vérifié contre `REF_MODS` ;
- `tools/emu/test_wavetable.py` : TOUT OK (chargeur, six pistes, machines mêlées).

`[À FAIRE]` : la preuve `tools/emu/test_wave_combos.py` sur l'ensemble de l'OS 2.1 (moteurs, MACRO, ACID et Wave)
n'a pas été menée à son terme ici (longue) ; l'essai sur la machine de cet OS précis reste à faire, et la fusion
Wave + Model-TG (jalon 3 de [60](60-wave-autonome.md)) reste le seul chemin pour retrouver aussi le Sampler.
