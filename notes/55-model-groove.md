# 55 — Model:Groove : la charte du projet dérivé (8 pistes audio)

Travail du 11/10. Demande de Kevin : ouvrir un projet dérivé **Model:Groove** dont l'objectif n°1
est d'obtenir **8 pistes audio au lieu des 6** (notes/54), en retirant « tout ce qui n'est pas
mission critique » de l'OS, et en **préservant le savoir-faire accumulé** jusqu'ici.

Réponse à ses questions du 11/10 enregistrées ici : projet **dans ce dépôt** (branche
`model-groove`, depuis `8-audio-tracks`) ; **FX delay/reverb gardés** (pas de strip pour le
moment, §3) ; **Model-TG et tous les mods du dépôt retirés** de la ligne Groove ; savoir-faire
RE préservé **au minimum utile** (le banc de mesure versionné, §6).

## 0. En bref

| **Mission critique** (on ne les touche pas) | **Retiré de la ligne Groove** |
|---|---|
| la boucle des voix et son compteur de pistes (notes/54 §1) | Model-TG et sample-preview (82 Ko de flash en place, la zone d'échantillons de 64 Mo, les crochets mixeur/voix) |
| le mixeur (6 appels notés à la main → 8 un jour) | les moteurs du Syntakt, MACRO, Acid, arp, trig-hold, tempo-max, boot-anim, drumkilla QoL, browser-scroll |
| la table des descripteurs (76 entrées, notes/54 §2.5) | les réglages « creature comfort » du dépôt (toutes les cartes du flasher, sauf `usb6` si le jour vient) |
| le format des patterns (722 o/piste, notes/54 §2.3) | |
| les mutes et le quick-mute (masque 32 bits, 3 bornes) | |
| le régulateur de charge (la seule protection de surcharge, notes 25/30/36) | |
| le navigateur d'échantillons stock, la piste MIDI, l'UI de piste | |
| le conteneur ELE3, le bootloader, l'upgrade USB (règle 6 du dépôt) | |

Le firmware de référence de Groove est **l'OS officiel 1.13 nu, sans aucun tweak** : zéro
écriture. Tout le travail à venir s'empile sur cette base — et jamais sur un build qui
contiendrait un mod du dépôt principal.

## 1. La branche et son identité de build

- Branche `model-groove` née de `8-audio-tracks` (l'investigation des notes/54).
- Constructions Groove : ligne de commande (`tools/build.py`), **pas dans le flasher web** — le
  flasher garantit `CONFIG › UPGRADE` fonctionnel et des combinaisons testées ; il garde cela.
  Précédent : `6ch-multiout` et `sdvintage-snare`, en ligne de commande seulement
  (docs/AGENTS.md). La récupération reste garantie : section 3 seule, bootloader intact.
- Chaque jalon Groove publie le SHA-256 du MAIN OS construit dans le PR, comme les autres mods.

## 2. Le modèle de charge, une fois les FX gardés (le choix de Kevin)

- Les 2 voix de plus coûtent **+11 112 instr/bloc** sur la boucle des voix quand elles sont TONE
  (44 468 = 1,33 × 33 356, notes/54 §6), soit **+10,3 points** d'un bloc de 166 667 cycles. Voir
  le §2bis pour la marge réelle (l'audio complet n'est pas émulable, mais les mesures existent).
- Arithmétique honnête : l'OS d'origine est à ~77 % du bloc à l'arrêt (notes/23). 8 pistes de
  **machines légères/passées TONE** suivent le régulateur sans toucher le plafond (~93 %) ;
  **8 pistes Syntakt (≈ 2 TONE/voix) ou Wave (≈ 1,46 TONE)** amènent la charge au-dessus du
  plafond et déclenchent des coupures. Arbitrage de conception de Groove : peser machine par
  machine ; si les coupures arrivent, la première économie candidate est le « skip des voix
  muettes » de notes/23 (−40 % à −77 % d'instructions quand les voix se taisent), pas le
  retrait des FX.
- Les FX restent (choix du 11/10). Le strip FX (retiré à ~12 % du bloc, notes/31 §7 : délais +
  reverb calculés en permanence) est rangé comme **plan B** si les coupures deviennent le blocage.

## 2bis. Phase 1 `[FAIT]` — la marge réelle, sans banc « ISR complet »

- **Le banc de la fonction audio complète n'est pas émulable** (déjà constaté, notes/27 §3.4) :
  `0x4005979e` tourne sans fin en émulation, faute de l'état de l'OS (l'entrée `0x40091ab2`, puis
  la fonction de sortie et effets `0x400567ba` ne reviennent pas). La marge ne sortira donc pas
  d'un banc d'émulation, mais du croisement des mesures machine + la boucle des voix :
  - **OS d'origine, à l'arrêt : ~77 % du bloc** (notes/23, machine) ;
  - **mixage + effets : ~30 % du bloc, à chaque bloc, même à l'arrêt** (notes/27 §3.4, machine ;
    seule la fonction mixage `0x40056f58` est émulable : 6 000 instr/bloc) ;
  - **une voix TONE soutenue : 5 291 instr/bloc = 4,9 % du bloc** (notes/43/51 §8 ; banc en
    émulation, notes 54 §6) ;
  - **6 → 8 voix TONE soutenues : +11 112 instr = +10,3 points** (notes/54 §6, banc en émulation).
- **Lecture** : passer de 6 à 8 voix TONE pleines soutenues ajoute ~10 points à une charge qui,
  pour l'audio complet avec machines d'origine, vit déjà sous le plafond du régulateur
  (86 % de moyenne soutenue, 93 % en pic — notes/30/36). En 8 TONE soutenues, la marge devient
  **mince [HYP — à confirmer machine avec le compteur du diagnostic]** ; en 8 machines plus
  lourdes (Syntakt ≈ 2 TONE/voix), les coupures arrivent. C'est gelé dans les critères de la
  phase 2 : chaque banc de celle-ci rejouera la mesure avec la boucle des voix relogée, et le
  compteur de diagnostic (firmware de diagnostic, notes 27 §4) reste la voie machine.
- **Identité de build de la base Groove** : le `.syx` officiel lui-même (SHA-256
  `44fe5862…9800640c`, MAIN OS `cc99d4f0…ee98`), pas une reconstruction — la repack avec zéro
  écriture ne dépaquette pas strictement à l'octet comme le packeur d'Elektron (654 701 o
  contre 654 704), mais renvoie **le même MAIN OS** (vérifié, `tools/mtlib/aplib.py`). À partir
  de la phase 2, `tools/build.py -t <id>` publiera le SHA du MAIN OS construit, comme les autres
  mods.

## 3. Les phases (chaque jalon : preuve en émulation d'abord, essai matériel de Maxime ensuite,
    PR draft un changement visible)

| Phase | Contenu | Critères d'acceptation |
|---|---|---|
| 0 (ce PR) | charte ; banc de mesure préservé | la réexécution du banc reproduit note 54 (TONE 5 291, 1,33 ×) |
| 1 | base Groove = OS stock nu ; identité de build ; marge réelle | identité publiée (§2bis) ; la marge appuyée sur les mesures machine + boucle émulée |
| 2 | le cœur 8 pistes : RAM relogée (états de voix hors `0x42309ad0`, 2 tampons hors `0x80001b58`, 2 tableaux de gains), borne `6→8`, mixeur 6→8 appels, +10 entrées de descripteurs (560 o), 3 bornes du quick-mute, stride du pattern + conversions | pistes 7/8 jouent ; pistes 0-5 octet pour octet d'origine ; projets existants lisibles |
| 3 | l'UI de sélection des pistes (le « plus gros inconnu », notes/54 §2.6) : touche TRK, pads, grilles, écrans | sélection/jouer la 7ᵉ et la 8ᵉ à la main, en émulation d'abord |
| 4 | USB 8 canaux (sortir les 8 pistes), doc utilisateur (guide, version) | la machine produit 8 pistes audibles ; les mutes y répondent |

## 4. Ce qui change ici pour le dépôt

- `notes/README.md` indexe cette charte ; `notes/54` est la base technique (aucun des deux ne se
  répète).
- Les tweaks du dépôt principal **ne sont pas modifiés** : Groove est une ligne séparée. Les
  éventuels partages de code (ex. relocations RAM) passeront d'abord par le dépôt d'outils
  (ex. `voice_loop.py`, `gov_asm.py` — à réutiliser, pas à copier).
- `tools/re/` (§6) est la seule addition du dépôt en code.

## 5. Les risques connus (tous repris des notes)

1. L'UI de sélection des pistes est **entièrement inconnue** (notes/54 §2.6) : le risque n°1,
   on décode en phase 3, mais on construit le cœur sans attendre.
2. Le format projet : ajouter des pistes de 722 o → conversion des projets existants — faire
   attention à ce que Maxime ne perde pas son projet courant. Protocole de sauvegarde avant
   chaque essai matériel.
3. La charge : §2. 8 pistes Syntakt/Wave seront coupées par le régulateur ; les machines
   légères passent.
4. La RAM : états de voix et tampons audio à reloger — les inconnues de §2.1/2.2 des notes/54 ;
   la sortie SDRAM est libre (23 Mo vérifiés à `0x46800000`, notes/52 §3), le soin reste la
   cohérence de tous les littéraux.
5. L'upgrade USB doit rester possible (règle 6) : chaque firmware Groove le rejoue en émulation
   comme le font les autres mods.

## 6. Préservation du savoir-faire

Demandé explicitement par Kevin (« mission critical »). Ce qui est versionné dès ce PR :

- **`tools/re/README.md`** — comment tourner le banc et l'outil de RE, avec les résultats de
  référence (TONE 5 291 ; 6→8 TONE = 1,33 × la boucle) pour détecter une dérive de protocole.
- **`tools/re/mcfw.py`** — le chargeur/désassembleur du MAIN OS (capstone + bridges
  `m68k-objdump`, choisir natif ou WSL Ubuntu) : `load_mainos`, `disasm`, `xrefs`, `u8/u16/u32`,
  `emac_disasm`, `bridge_emac`.
- **`tools/re/test_load8.py`** — le banc de charge 6→8 pistes (`--cycles`), avec vérifications
  intégrées (pistes 0-5 octet-identiques, blocs nuls pour pistes non trigées, TONE de
  référence), exit non nul en cas d'échec.

Le reste de la séance du 11/10 (les listings `mixer.txt`, `pattern_ab.txt`, `descs.txt`,
`quickmute.txt`… et les scripts de probe) reste dans `build/re8/`, **non versionné par choix** :
les chiffres utiles sont dans les notes 53/54, et `tools/re/mcfw.py` régénère tout en quelques
lignes. Les scripts de mesure s'appuient sur `tools/emu/` (partagé avec les preuves des mods).

Adresses : VA de l'OS 1.13. Rédigée avec les mêmes conventions que les notes :
[FAIT] vérifié sur l'image, [HYP] hypothèse, [À FAIRE] à mener.
