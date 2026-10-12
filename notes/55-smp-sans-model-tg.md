# 55 — Ranger les tables de Wave sans Model-TG : l'identité Model:Samples dans le tweak Wave

Feuille de route du 11/10/2026 (handoff `handoff-smp-glue.md`, milestone 2, demande de Kevin) : Wave est autonome
([54](54-wave-autonome.md)), mais ses tables se rangent sur le +Drive comme des fichiers `sample` de Model:Samples
([53](53-envoi-des-tables-depuis-l-outil-web.md)), ce qui demandait le mode SMP de Model-TG — incompatible avec Wave.
La glue SMP est donc **reprise dans le tweak Wave** (choix de Kevin), avec une commande SysEx pour la basculer depuis
la page de conversion. Tweak `36-wavetable.json` (générateur `tools/gen_wavetable.py`, `smp_glue_asm`), preuve
`tools/emu/test_wavetable.py` §3, page `docs/convert/` et `docs/flasher/flasher.js` (`setSmpMode`).
Adresses : VA de l'OS 1.13.

## Réponse courte

Le système de fichiers `sample` est du **code Elektron déjà dans l'OS du Cycles** : il ne gère que la famille « raw »
(types `0x14/0x15/…/0x47`), et le Model:Samples annonce la famille « sample » (`0x10/0x11/…/0x46`). Il suffit donc,
quand on le demande, de **se présenter en Model:Samples** (id 25, nom, liste de commandes) et de **renommer** les types
sample → raw à l'entrée, raw → sample à la sortie : 6 sites de l'OS, les mêmes que Model-TG, plus une place libre de la
table SysEx de l'OS pour la commande `F0 00 20 3C 0F 00 <m> F7` (m = 1 : Model:Samples, 0 : Model:Cycles). Le drapeau
n'est pas gardé : au démarrage la machine est un Model:Cycles. La page de conversion bascule la machine avant l'envoi
et la remet après. Prouvé en émulation, puis essayé sur la machine le 12/10/2026 (§8).

## 1. Ce que fait Model-TG `[FAIT : vendor/Model-TG @ 70b39dd, src/model_tg.s]`

Le mode *Device Config › Transfer › SMP* de Model-TG pose un drapeau lu à chaque ping (pas de nouvelle énumération
USB) et détourne les mêmes sites que ci-dessous. Sa table `rpc_map` (« sample-family type, raw twin ») est celle que
Wave reprend, octet pour octet. Model-TG pose son drapeau depuis son menu ; il n'utilise pas la table SysEx de l'OS.

## 2. Les sites `[FAIT]`

| Site | Octets d'origine | Rôle | Notre code |
|---|---|---|---|
| `0x40084b8e` (6 o) | `487800222d48` (`pea 0x22` …) | réponse d'identité : longueur et adresse de la liste de commandes | `smp_id_hook` : liste raw du Cycles (`0x40112d40`, 34 o) ou la nôtre (35 o), nom dans `smp_namebuf` ; reprend en `0x40084bde` |
| `0x40084be2` (4 o) | `401285c9` | immédiat du `pea` du nom « Model Cycles » | → `smp_namebuf` |
| `0x40084c14` (6 o) | `721b4fef0028` (`moveq #27,%d1` …) | numéro de produit | `smp_id_hook2` : 27 ou 25 ; reprend en `0x40084c1a` |
| `0x4009249c` (4 o) | `400949d8` | cible du `jsr` qui lit le type d'une requête (msg + 8) | `smp_rpc_type` : type sample → jumeau raw |
| `0x40094c9a` (8 o) | `71aa00084fef0020` | type de la réponse | `smp_rpc_ot` : raw \| 0x80 → sample \| 0x80 ; reprend en `0x40094ca2` |
| `0x40148d44` (4 o) | `00000000` | place 15 de la table SysEx `0x40148d08` | → `smp_desc` |

`smp_map` (32 o) : `10→14 11→15 12→16 20→24 21→25 22→26 23→27 30→33 31→34 32→35 36→37 40→43 41→44 42→45 46→47`, puis
deux zéros (`smp_rpc_type` lit les octets pairs, `smp_rpc_ot` les impairs : chacun a besoin de sa fin). Les deux
familles sont disjointes, une réponse qui n'est pas raw passe telle quelle. `smp_list` (35 o) : la liste du
Model:Samples **sans** `0x09`, pour que Transfer ne pose pas la question stéréo (mono, taille de bloc habituelle).

## 3. La commande SysEx `0x0F` `[FAIT : désassemblage de 0x400812f6]`

L'aiguillage SysEx de l'OS (`0x400812f6`, arguments : message, longueur, 0) :

1. compare les 4 premiers octets à `F0 00 20 3C` (`0x4011294a`) ;
2. prend `d = table[msg[4]]` dans `0x40148d08` (`msg[4]` ≤ 17 ; une place à 0 = ignoré) ;
3. exige `d[0] = msg[4]`, `d[1] = msg[5]`, et `d+8 ≤ msg[6] ≤ d+12` (mots longs) ;
4. saute à `(d+4)[msg[6] − d+16]` avec les arguments d'origine.

Les places 0..3 et 5..15 sont libres ; Wave prend la 15. Notre descripteur : `0F 00 00 00`, sous-table, bornes 0 et 1,
décalage 0 ; la sous-table pointe deux fois sur `smp_trig`, qui recopie `msg[6]` dans `smp_mode`. Un octet hors
[0, 1] est rejeté par l'OS lui-même. La commande ne répond rien : la page relit l'identité par un ping.

## 4. La page `[FAIT]`

- `flasher.js` : `smpModeMessage(on)` et `setSmpMode(session, sortie, on)` (envoie la commande, attend 50 ms, rend
  `xferIdentify`).
- `docs/convert/` : si la machine répond 27, la page envoie `0x0F 01` et relit ; si elle reste 27, son firmware n'a
  pas Wave (message clair). Après l'envoi (fini, arrêté ou en erreur), elle renvoie `0x0F 00`. Un bouton « la remettre
  en Model:Cycles » couvre un envoi coupé (onglet fermé) ; redémarrer la machine fait de même.
- Tant que la machine répond Model:Samples, elle ne se présente plus en Model:Cycles (le flasher refuse alors d'y
  envoyer un OS, [37 §3](37-flash-rapide-usb.md)) : c'est pour cela que la page la remet aussitôt.

## 5. Place et conflits

414 o de code et de données dans le bloc ajouté de Wave (`smp_id_hook` .. fin de `smp_desc`), 7 écritures. Mêmes
sites que Model-TG : Wave est déjà incompatible avec lui ([54](54-wave-autonome.md)), rien de nouveau.

## 6. Preuve `[FAIT en émulation]`

`tools/emu/test_wavetable.py` §3, sur le firmware construit depuis le tweak seul :

| Cas | CYC (`smp_mode` 0) | SMP (`smp_mode` 1) |
|---|---|---|
| produit (`0x40084c14`) | 27 | 25 |
| requête `0x10`, `0x11`, `0x12`, `0x20`, `0x36`, `0x40` | inchangée | `0x14`, `0x15`, `0x16`, `0x24`, `0x37`, `0x43` ; `0x14` reste `0x14` |
| réponse `0x94`, `0x95`, `0x96`, `0xc3`, `0xc7` | inchangée | `0x90`, `0x91`, `0x92`, `0xc0`, `0xc6` ; `0xc0` reste `0xc0` |
| identité (`0x40084b8e`) | liste 34 o, « Model Cycles » | liste 35 o, « Model Samples » |
| `F0 00 20 3C 0F 00 m F7` par l'aiguillage de l'OS | m = 0 → 0 | m = 1 → 1 ; m = 2 ignoré |

Plus la forme du descripteur, la place 15 de la table, `smp_list` et `smp_map` octet pour octet. Côté page,
`tools/webflash_smoke.js` : une machine factice avec Wave passe en Model:Samples puis revient ; sans Wave elle reste un
Model:Cycles.

Le 12/10/2026, deux attentes de la preuve étaient fausses (pas le firmware) : la réponse `0xc0 → 0xc3` (à l'envers :
c'est `0xc3 → 0xc0`) et une `smp_map` attendue de 50 o, sans le `27` après `23`. Corrigées ; la commande passe
désormais par l'aiguillage de l'OS au lieu d'appeler `smp_trig` directement.

## 7. Reste à faire `[À FAIRE]`

- Sur la machine, depuis le navigateur de Kevin : un dossier entier, Elektron Transfer qui reconnaît le Model:Cycles
  après l'envoi, le bouton de remise après un envoi coupé (§8 pour ce qui est fait).
- Milestone 3 : fusion des générateurs (Wave + Acid + moteurs du Syntakt), retour de la carte Wave dans le flasher.

## 8. Sur la machine (12/10/2026)

Firmware Wave seule, flashé par Kevin. Sondes `amidi` (accès direct au port, depuis l'ordinateur) `[FAIT : sur la
machine]` : la machine répond 27 ; `F0 00 20 3C 0F 00 01 F7` la fait répondre **25** (« Model Samples », liste de 35
commandes, sans réponse à la commande elle-même) ; lecture de `/` et de `/Wavetables`, création de dossier,
ouverture / écriture / fermeture d'un fichier (blocs de 8 Ko comme de 2 Ko) répondent ; `0F 00` la remet en 27.
Puis la page `docs/convert/` dans un Chromium piloté sur la même machine : bascule, envoi d'une table de 64 trames
(548 944 o), retour en Model:Cycles. Deux défauts de la page, corrigés ([53 §12](53-envoi-des-tables-depuis-l-outil-web.md)) :
le port « Midi Through » choisi à la place de la machine, et les blocs de 8 Ko perdus sous Linux (2 Ko là, 8 Ko
ailleurs ; Kevin a envoyé des fichiers de 3 Mo en blocs de 8 Ko sous Windows).

Un autre programme qui parle à la machine pendant un envoi (un autre onglet du site) peut la remettre en Model:Cycles
au milieu : la page le dit dans le guide (fermer les autres onglets).

