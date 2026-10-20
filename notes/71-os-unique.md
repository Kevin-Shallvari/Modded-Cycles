# 71 — Un seul OS : le Modded Cycles OS 2.0

Décision de Maxime (annonce Discord du 17/10/2026, demande du 18/10/2026) : le projet n'est plus un flasher où l'on
coche des mods, c'est **un seul firmware**, le *Modded Cycles OS*, que tout le monde flashe tel quel. Cette note
consigne la décision, la composition de la 2.0, ce qui en sort et pourquoi, la mécanique dans le dépôt, et ce qu'il
reste à tester. Fichiers : `os.json`, `tools/gen_flasher_tweaks.py`, `tools/ref_mainos.py`, `tools/build.py --os`,
`docs/flasher/` (`app.js`, `index.html`, `tweaks.js`), `tools/webflash_smoke.js`. Aucun octet de tweak ne change :
la 2.0 est une combinaison que le flasher savait déjà construire.

> **Mise à jour du 19/10/2026 ([72](72-reglages-des-mods.md)).** La bascule stéréo / 6 canaux existe : la page
> *Mod Settings* (SETTINGS › Mods), réglage **USB Audio** 2CH / 6CH, tweak `mod-settings`, entre dans l'OS avant la
> fusion de la 2.0 (demande de Maxime). L'audio 6 canaux n'est donc plus « hors de l'OS » : en 6CH, les modifications
> de `6ch-usbup` sont faites en mémoire ; en 2CH, le pilote USB reste celui d'origine. L'OS a 13 tweaks et 18
> fonctions ; MAIN OS SHA-256 `1ee74aa2fa982e2b9a63d0ea032a2b8a0a54127ff87bd7e06d120f075f9c76fa` (avec
> `Syntakt_OS1.41.syx`). Le reste de cette note décrit la 2.0 telle que décidée le 18/10/2026.
>
> **Mise à jour du 20/10/2026 ([73](73-step-record.md)).** Le step record (`step-rec`, REC deux fois à l'arrêt) entre
> aussi dans l'OS : 14 tweaks, 19 fonctions ; MAIN OS SHA-256 `82a79f453151cbaceffdd047a646c96721f3ae3849a28f7821928bfbd4a1cca9`.

## En bref

- **Une seule combinaison** de tweaks, `os.json` : `model-tg-st`, `sample-preview-st`, `trig-hold`, `arp`,
  `tempo-max`, `boot-anim`, `multiline-browser`, `level-pan-values`, `trigless-dim`, `midi-live-both`, `lfo-plus`,
  `syntakt-tg-sd-cp-toy-bits-swarm-macro-acid`. MAIN OS SHA-256 `a87e70d05d213b4301a68e13ae729a62f7c898a481faaa9d9613ac518fe60ff9`
  (construit avec `Syntakt_OS1.41.syx` ; 1.42 donne le même, même section 7, notes/16).
- **Machines ajoutées, numéros fixes** : 07 Sampler, 08 SDVtg, 09 CPVtg, 10 SYToy, 11 SYBit, 12 SYSwm, 13 MACRO,
  14 ACID. Fini « le numéro dépend de ce que vous cochez ».
- **Deux fichiers officiels** demandés à tout le monde : `model-cycles_OS1.13.syx` et `Syntakt_OS1.42.syx` (ou 1.41).
- **Hors de l'OS** : audio USB 6 canaux, filtre par piste, OS optimisé, `midi-both` ; **Chord Keys retiré du
  projet**. Raisons au §2.
- **Statut** : `experimental` pour l'OS entier tant que ce firmware précis n'a pas tourné sur la machine ; chaque
  fonction garde son propre statut (`os.json`).
- `tweaks/` reste la **bibliothèque** : tous les tweaks construits et prouvés, y compris hors OS ; `build.py -t`
  les combine encore pour le développement. Les 262 combinaisons de moteurs du Syntakt restent générées (étape
  suivante possible : n'en garder que celles qui servent).

## 1. Pourquoi un seul OS

Extrait de l'annonce (en anglais sur le Discord) : « my goal is to offer a unified flasher, with a single OS version
put forward […] it helps convey that Modded Cycles is more of a coherent, global project rather than a collection of
individual tweaks ». Ce que ça change pour le projet :

- tout le monde a le même firmware : un projet, une astuce, un rapport de bug veulent dire la même chose pour tous ;
- plus de table de compatibilité à maintenir dans la page (`excludes`, `includes`, `requires`, `with`, `joins` de
  l'ancien `FEATURES`) ni d'échantillon de combinaisons à hacher (notes/49 : 464 combinaisons dans `REF_MAINOS`) ;
  une seule empreinte de MAIN OS, et chaque tweak toujours vérifié mod par mod (`REF_MODS`) ;
- une fonction qui ne tient pas avec le reste n'entre pas, au lieu de « décocher l'autre ».

## 2. Composition de la 2.0, et ce qui en sort

Le flasher 1.55 proposait 22 cartes. Quatre conflits durs empêchaient de tout mettre dans un firmware :

| Conflit | Détail | Décision |
|---|---|---|
| `chord-keys` ↔ `model-tg` | mêmes masques de sprites que l'écoute des samples, incompatible Model-TG (notes/42) | **Chord Keys retiré du projet** (demande de Maxime, 18/10/2026 : « trop en conflit »). Fichiers supprimés (tweak 45, `tools/gen_chord_keys.py`, `tools/machines/chord_keys/`, preuves et sondes) ; la note 42 reste en archive ; le travail de Nico Heuser reste dans l'historique git. |
| `track-filter` ↔ `lfo-plus`, `track-filter` ↔ `model-tg` | mêmes emplacements du son (notes/47, 56 §3.6) ; pas encore adapté à Model-TG | LFO 2, 3, 4 dans l'OS ; **filtre par piste dehors**, à reprendre quand le Sampler sera réécrit (la PR #83 l'adapte à Model-TG ; à rejuger alors). |
| `os-optimise` ↔ `model-tg`, `macro`, `acid`, `syntakt` | les raccourcis de la boucle des voix ne connaissent pas les machines ajoutées (notes/70) | **Dehors** ; premier chantier du gel : porter l'OS optimisé sur l'OS unique. |
| `midi-both` ↔ `midi-live-both` | deux réglages du même octet (notes/53) | `midi-live-both` dans l'OS : il fait aussi ce que fait `midi-both` (FUNC + appui sur LEVEL/DATA). |

Et une décision sans conflit d'octets : **l'audio USB 6 canaux reste dehors** (choix de Maxime, 18/10/2026). Il
remplace le mix stéréo USB par six pistes mono (notes/01, 13) : imposé à tous, il casserait l'usage le plus courant
(enregistrer le mix). Il revient quand une bascule stéréo / 6 canaux existera dans le menu de la machine
(issue #82).

Les 17 fonctions de l'OS, leurs touches et leurs limites sont dans `FEATURES.md` (anglais) ; la carte des
raccourcis en tête de ce fichier sert à repérer les collisions.

## 3. Mécanique dans le dépôt

### 3.1 `os.json`

```jsonc
{
  "name": "Modded Cycles OS", "version": "2.0", "status": "experimental",
  "needs": ["cycles", "syntakt"],
  "tweaks": ["model-tg-st", "sample-preview-st", "…"],          // la clé de REF_MAINOS, jointe par « + »
  "machines": [{ "code": "sampler", "name": "Sampler", "label": "Model-TG sampler" }, "…"],
  "features": [{ "id": "arp", "cat": "seq", "tweaks": ["arp"], "status": "tested", "credit": null, "guide": "arp" }, "…"]
}
```

- `tweaks` : l'OS. `build.py` les applique dans l'ordre de leur champ `order` (l'un peut se poser sur l'autre,
  notes/31) ; l'ordre de la liste ne sert qu'à la clé.
- `features` : ce que la page affiche, par rubrique (`sound`, `seq`, `live`, `screen`, `io`). Un tweak de l'OS doit
  appartenir à une fonction ; une fonction peut n'avoir aucun tweak à elle (le mute verrouillé vit dans Model-TG).
  `credit` et `license` donnent la ligne d'auteur et le fichier de licence servi ; `guide` l'ancre du guide.
- `machines` : les machines ajoutées, dans l'ordre du menu MACHINES, pour le message de fin de flash et l'en-tête.

### 3.2 Outils

| Outil | Avant | Maintenant |
|---|---|---|
| `tools/gen_flasher_tweaks.py` | la liste `FEATURES` (cartes, variantes, moteurs, règles) → `tweaks.js` avec 274 tweaks (1,1 Mo) | lit `os.json`, vérifie que l'OS se construit (conflits, `requires`, propriétaires), écrit `tweaks.js` avec les 12 tweaks de l'OS (528 Ko), `os` et `features` |
| `tools/ref_mainos.py` | rejouait les règles des cartes (`Cards`) et hachait 464 combinaisons | hache l'OS (une clé) et chaque tweak embarqué ; `app.js` passe de 3 832 à 1 843 lignes |
| `tools/build.py` | `-t ids` ou `--all` | `--os` construit `os.json` ; `-t` reste pour le développement |
| `docs/flasher/app.js` | sélecteur (cases, moteurs, exclusions, « défaire », recherche, barre de sélection) | en-tête de l'OS (nom, version, statut, machines, fichiers) + lignes en lecture seule par rubrique, Détails ; `chosenTweaks()` renvoie l'OS |
| `tools/webflash_smoke.js` | cochait chaque carte seule et par paires, 464 combinaisons sur le vrai OS | vérifie la liste, l'en-tête, les crédits, le flux complet sur une image synthétique (OS de développement à trois tweaks), puis l'OS réel contre `REF_MAINOS` et `REF_MODS` |
| `tools/check_overlaps.py`, `tools/registry.py` | inchangés : ils lisent `tweaks/` (la bibliothèque) | idem ; `check_overlaps` garantit toujours que deux tweaks constructibles ensemble n'écrivent pas les mêmes octets |

`tools/mods_for_samples.py` et `MCBuilder.modsForSamples` ne changent pas : la page emballe le même OS pour un
Model:Samples (notes/57).

### 3.3 Ce qui a été retiré du dépôt

- Chord Keys : `tweaks/model-cycles_OS1.13/45-chord-keys.json`, `tools/gen_chord_keys.py`, `tools/test_chord_keys.py`,
  `tools/machines/chord_keys/`, `tools/emu/test_chord_keys*.py`, `chord_*_checks.py`, `probe_chord_*.py`.
  `gen_sample_preview.py` ne déclare plus `conflicts: ["chord-keys"]` (`33-sample-preview*.json` régénérés, mêmes
  écritures). `REGISTRY.md` : 127 masques libres au lieu de 117.
- `docs/flasher/LICENSE-ms-multi-output.txt` : plus servi (le 6 canaux n'est plus dans la page) ; la licence reste
  dans `tweaks/` et `THIRD-PARTY-NOTICES.md`.
- `FLASH.md` → `RECOVERY.md` (anglais, récupération par le menu de démarrage) ; `dossier-technique.md` →
  `notes/00-dossier-technique.md` ; `BUILD.md` réécrit en anglais autour de `--os`.

## 4. Preuve `[FAIT en émulation]` et vérifications

- `tools/build.py --os` et la page construisent le même MAIN OS (`webflash_smoke.sh` avec les fichiers réels :
  `a87e70d0…`), chaque tweak vérifié contre `REF_MODS`, un tweak altéré refusé.
- `tools/webbuild_check.sh`, `tools/webflash_check.sh`, `check_overlaps.py`, `registry.py --check`,
  `gen_flasher_tweaks.py --check`, `ref_mainos.py --check` : OK.
- Les preuves Unicorn de chaque tweak ne changent pas (aucun octet de tweak ne change) ; la combinaison elle-même
  était dans l'échantillon `REF_MAINOS` du flasher 1.55 (groupe « largest »), construite et vérifiée mod par mod.

## 5. À essayer sur la machine `[À FAIRE]`

Flasher la 2.0 depuis la page (deux fichiers), puis :

1. MACHINES sur une piste : 07 Sampler … 14 ACID, dans cet ordre.
2. Un sample sur une piste Sampler ; FUNC + MACHINES et l'écoute du sample sous le curseur.
3. Les cinq moteurs, MACRO (FUNC + PITCH pour le lo-fi) et ACID (slide par LEN) sur six pistes : charge et coupures.
4. [LFO] répété (2, 3, 4) ; RETRIG tenu avec plusieurs notes ; FUNC + RETRIG ; TEMPO au-delà de 300.
5. Appui bref sur un pas plein ; TRK + FUNC (mute verrouillé) ; FUNC + appui sur LEVEL/DATA avec THR.
6. Animation de démarrage ; navigateur à trois lignes ; LEVEL/DATA en chiffres ; trigless atténué.
7. Retour au firmware officiel depuis la page (pistes remises sur une machine d'origine avant).

Le statut de l'OS passe à `tested` dans `os.json` après ce rapport (commit à part).
