# 53 — Envoyer les tables d'ondes à la machine depuis l'outil web

Demande de Kevin (11/10/2026), après la bascule de [52 §13](52-etude-tables-d-ondes.md) : l'outil web convertit la
table en un WAV 48 kHz, mais l'utilisateur doit encore la déposer sur la machine avec Elektron Transfer (ou
`elektroid-cli`). Une rubrique du site pourrait l'envoyer elle-même, comme Transfer. Cette note est l'étude de
faisabilité et de conception ; elle s'appuie sur la source d'Elektroid (`src/connectors/elektron.c`, `elektron.h`,
`res/elektron/devices.json`, commit `7806ecaf`), la même que [37](37-flash-rapide-usb.md).

Ce n'est **pas un tweak** : rien dans le firmware, rien dans `tweaks/`, aucun générateur, aucune preuve dans
`tools/emu/`. C'est une fonction de la page (`docs/flasher/flasher.js`, rubrique `docs/convert/`), comme le protocole
de flash de [37](37-flash-rapide-usb.md). Adresses : VA de l'OS 1.13.

## Réponse courte

- **C'est faisable**, sans blocage. L'envoi d'un fichier à la mémoire de la machine (« +Drive ») passe par **le même
  protocole USB MIDI SysEx** que le flash de firmware de [37](37-flash-rapide-usb.md) ; il ne reste qu'à ajouter ses
  commandes à la page.
- **Elektron Transfer fait exactement la même chose** : le Model:Cycles n'a **pas** de canal USB fournisseur (pas
  d'Overbridge comme les grandes boîtes), seulement **USB MIDI + audio** ([04](04-usb-audio.md)). Il n'y a donc pas de
  voie plus rapide à choisir : Transfer, Elektroid et notre page roulent sur la même route. La vitesse vient de
  l'**acquittement par bloc**, pas d'un autre protocole.
- **Le système de fichiers** dépend de l'identité de la machine : le Cycles (id 27) a un système **`raw`** ; le
  Model:Samples (id 25) un système **`sample`**. En mode SMP de Model-TG, le Cycles répond 25 : c'est le système
  `sample` qu'on utilise, et c'est celui dont l'en-tête correspond aux contrôles de `ensure_loaded` de Model-TG.
- **Ce que ça change** : plus besoin de fermer la page pour ouvrir Transfer (Web MIDI tient le port), et la table part
  dans le bon dossier sans manipulation.
- **À confirmer** : la taille exacte de l'en-tête (64 o ici, ~80 o mesurés en [52 §10](52-etude-tables-d-ondes.md)) et
  la vitesse réelle d'un envoi de ~2 Mo.

## 1. Comment Transfer s'y prend (et pourquoi il n'y a pas plus rapide) `[FAIT]`

- Le Cycles parle à l'ordinateur en **USB MIDI**, avec le protocole SysEx d'Elektron : trame `F0 00 20 3C 10 00`,
  charge utile empaquetée sur 7 bits, `F7`, un numéro de séquence par requête, réponse à `commande | 0x80`
  ([37 §2](37-flash-rapide-usb.md)).
- Ses descripteurs USB ([04 §3](04-usb-audio.md)) ne proposent que des configurations **« USB-MIDI seule »** (une
  sortie `bulk` de 512 o, High Speed) et **audio + MIDI HS**. **Aucun canal fournisseur** : les grandes boîtes
  (Digitakt, Digitone, Syntakt, Analog…) ont un canal Overbridge dédié, pas les Models.
- Transfer ne peut donc pas être plus rapide qu'Elektroid ici, et notre page non plus. Ce qui rend la méthode
  « rapide » rapide, par rapport à `CONFIG › UPGRADE`, est l'**accusé de réception par bloc** : on ne cadençait plus
  comme un fil MIDI DIN à 31 250 bauds ([37 §1](37-flash-rapide-usb.md)).
- Ordres de grandeur : le flash de firmware envoie des blocs de **2 Ko** (`OS_TRANSF_BLOCK_BYTES` `0x800`) et a pris
  **33 s** pour 1,2 Mo ([37 §5](37-flash-rapide-usb.md)) ; l'envoi de fichiers utilise des blocs de **8 Ko**
  (`DATA_TRANSF_BLOCK_BYTES` `0x2000`), soit quatre fois plus par message. Une table de ~2 Mo fait donc ~250 messages
  (~15 à 20 s `[HYP]`), à mesurer.

## 2. Quel système de fichiers `[FAIT : Elektroid]`

`res/elektron/devices.json` décrit, par machine, les systèmes de fichiers et le stockage :

| Machine | id | Systèmes | Stockage |
|---|---|---|---|
| Model:Cycles | 27 | `raw`, `preset-raw`, `data`, `project` | `+Drive` |
| Model:Samples | 25 | `sample`, `data`, `project`, `sound` | `+Drive`, `RAM` |

- Le Cycles **n'a pas** de système `sample` d'origine : ses fichiers sur le +Drive passent par `raw`, sans en-tête
  d'échantillon (voir §4). C'est ce que dit le commentaire d'Elektroid : « no effect for the raw filesystem (M:C) ».
- **En mode SMP** (Model-TG, *Device Config › Transfer › SMP*), le Cycles s'annonce **Model:Samples** (id 25) : c'est
  le système **`sample`** qui est employé, avec l'en-tête de 64 o. C'est ce qu'utilise `elektron:sample:ul`, et ce que
  Kevin a fait en [52 §10](52-etude-tables-d-ondes.md).
- Cela colle aux contrôles de `ensure_loaded` de Model-TG ([46 §4](46-ecoute-des-samples.md)) : il lit l'en-tête et
  exige `+8 == 48 000` et `+4 ≠ 0`, c'est-à-dire le **taux** et la **taille** de l'en-tête `sample` (§4). La table doit
  donc être déposée **en mode SMP**, avec l'en-tête `sample`.

## 3. Les commandes `[FAIT : Elektroid]`

Même trame que [37](37-flash-rapide-usb.md) : la charge utile décodée commence par `[0..1]` = numéro de séquence
(big-endian), `[2..3]` = 0 dans une requête, `[4]` = commande, puis le corps. La réponse porte `commande | 0x80` et
l'état en `[5]`.

| Rôle | Système `sample` | Système `raw` | Corps de la requête |
|---|---|---|---|
| Lire un dossier | `0x10` | `0x14` | chemin |
| Créer un dossier | `0x11` | `0x15` | chemin |
| Effacer un dossier | `0x12` | `0x16` | chemin |
| Effacer un fichier | `0x20` | `0x24` | chemin |
| Renommer un fichier | `0x21` | `0x25` | chemin source + chemin cible |
| Info d'un fichier (par chemin) | `0x22` | `0x26` | chemin |
| Ouvrir en lecture | `0x30` | `0x33` | chemin |
| Fermer la lecture | `0x31` | `0x34` | id `[5..8]` |
| Lire un bloc | `0x32` | `0x35` | id `[5..8]`, taille `[9..12]`, position `[13..16]` |
| Ouvrir en écriture | `0x40` | `0x43` | chemin + taille totale `[5..8]` |
| Fermer l'écriture | `0x41` | `0x44` | id `[5..8]`, total `[9..12]` |
| Écrire un bloc | `0x42` | `0x45` | id `[5..8]`, octets du bloc `[9..12]`, position `[13..16]` + données |

Toutes les valeurs numériques du corps sont **big-endian**. Réponses : `0x40 → 0xC0`, `0x42 → 0xC2`, `0x41 → 0xC1`,
`0x10 → 0x90`, `0x11 → 0x91`, etc. ; `[5]` = 1 (succès) ou 0 (échec) ; `0xC0` porte en plus l'**id** du fichier
`[6..9]` et le nombre de **trames** `[10..13]`. Les chemins sont en **CP1252**, terminés par un octet nul.

## 4. L'envoi d'une table (système `sample`) `[FAIT : Elektroid]`

1. **Ouvrir en écriture** (`0x40`) : corps = chemin + taille totale (`longueur PCM + 64`, big-endian en `[5..8]`).
   Réponse `0xC0` : `[5]` = 1, `[6..9]` = id, `[10..13]` = trames.
2. **Écrire** (`0x42`), par blocs de `DATA_TRANSF_BLOCK_BYTES` = **8 192 o** : corps = id `[5..8]`, octets de ce bloc
   `[9..12]`, position `[13..16]` = `8 192 × n° de bloc`, puis les données. Réponse `0xC2`.
   - **Le premier bloc** (`n° 0`) commence par l'**en-tête de 64 o**, puis les échantillons : il porte donc
     64 o + 8 128 o de PCM.
   - Les échantillons sont des **int16 big-endian** (les octets du WAV, échangés deux à deux).
3. **Fermer** (`0x41`) : corps = id `[5..8]`, total (`longueur PCM + 64`) `[9..12]`. Réponse `0xC1`.
4. **Pause** de `BE_REST_TIME_US` = **50 ms** après chaque message, comme le flash ([37 §2](37-flash-rapide-usb.md)).

En-tête d'échantillon (`struct elektron_sample_header`, **64 o**), big-endian :

| Décalage | Champ | Valeur pour une table |
|---|---|---|
| +0 | type | 0 |
| +1 | stéréo | 0 (mono) |
| +2 | réservé (2 o) | 0 |
| +4 | taille (4 o) | octets de PCM |
| +8 | taux (4 o) | 48 000 |
| +12 | début de boucle (4 o) | 0 |
| +16 | fin de boucle (4 o) | 0 |
| +20 | type de boucle | `0x7F` (pas de boucle) |
| +21 | réservé (3 o) | 0 |
| +24 | remplissage (10 × 4 o) | 0 |

Le WAV produit par `docs/convert/` (48 kHz, mono, 16 bits) est donc envoyé **sans son en-tête RIFF** : seuls les
échantillons comptent, précédés de ces 64 o. Le dossier visé est **`/Wavetables/`** ([52](52-etude-tables-d-ondes.md)).

## 5. Lire et créer un dossier `[FAIT : Elektroid]`

- **Créer** (`0x11`) : corps = chemin ; réponse `0x91`, `[5]` = 1 si créé. Comme `mkdir -p` : créer `/Wavetables` avant
  le premier envoi est sans danger (déjà là → échec bénin, à ignorer).
- **Lire** (`0x10`) : corps = chemin ; réponse `0x90`. Les entrées commencent à l'octet 5 (`FS_SMPLRW_START_POS`) :
  empreinte (4 o), taille (4 o), protégé en écriture (1 o), type (1 o, dossier/fichier), nom (CP1252, nul-terminé).
  Utile pour savoir si la table est déjà là et pour l'afficher.

## 6. Ce que ferait la page (conception) `[À FAIRE]`

- **`docs/flasher/flasher.js`** : à côté de `upgradeFast`, trois fonctions bâties sur le même `xferOpen` / `xferFrame`
  déjà en place — `listDir` (`0x10`), `makeDir` (`0x11`), `uploadSample` (`0x40` → `0x42` × N → `0x41`). Rien de
  nouveau côté transport : empaquetage 7 bits, CRC, séquence et attente de réponse existent déjà.
- **Détection du mode SMP** : la page demande déjà qui répond (`xferIdentify`) et connaît l'id 25 (Model:Samples) ; en
  mode SMP elle l'accepte pour un envoi de fichier (alors qu'elle refuse d'y flasher un OS, [37 §3](37-flash-rapide-usb.md)).
  Si la machine répond 27 (Cycles), afficher « passez *Device Config › Transfer › SMP* ».
- **`docs/convert/`** : un bouton **« Envoyer à la machine »** après la conversion, qui envoie le WAV affiché (mode
  SMP requis), avec la progression (bloc par bloc) et la vitesse mesurée.
- **Enchaînement** : flasher Wave + Model-TG → passer en SMP → convertir → envoyer. Le firmware de [52](52-etude-tables-d-ondes.md)
  reste nécessaire (la machine ne lit la table que par le moteur Wave et le chargeur de Model-TG).
- **PR séparée** : l'implémentation et sa preuve (§8) forment un changement visible distinct du reste.

## 7. Points ouverts `[À FAIRE]`

1. **Taille de l'en-tête** : Elektroid envoie **64 o** (§4) ; [52 §10](52-etude-tables-d-ondes.md) a mesuré **~80 o**
   sur la machine. À trancher avant d'écrire le code (relire la taille annoncée à l'ouverture, ou mesurer sur la
   machine).
2. **Vitesse** : mesurer l'envoi d'une table de ~2 Mo en mode SMP (blocs de 8 Ko, pause de 50 ms).
3. **Création du dossier** : confirmer que `/Wavetables` peut être créé par le système `sample` (ou qu'il existe déjà,
   [52 §3quater](52-etude-tables-d-ondes.md)) et que l'effacement est bien refusé ([52 §10](52-etude-tables-d-ondes.md)).
4. **Port occupé** : la page doit tenir le port Web MIDI pendant tout l'envoi ; Transfer/Overbridge doivent être
   fermés (comme pour le flash, [37 §3](37-flash-rapide-usb.md)).

## 8. Preuves à faire `[À FAIRE]`

- **`tools/webxfer_check.py`** : transcription Python ligne à ligne du C d'Elektroid ([37 §4](37-flash-rapide-usb.md)) ;
  y ajouter l'en-tête de 64 o, l'empaquetage des blocs de 8 Ko et les messages d'ouverture/écriture/fermeture, et
  comparer **chaque octet** à ceux de la page.
- **`tools/webflash_smoke.js`** : le faux Model:Cycles sait déjà répondre au ping, à la version et au flash ; lui
  apprendre `0x40` / `0x42` / `0x41` (et `0x10` / `0x11`), vérifier que le fichier arrive **octet pour octet** et que
  la page refuse une machine hors mode SMP.
- **Sur la machine (Maxime)** : mode SMP, envoi d'une table convertie, puis la charger dans Wave et vérifier qu'elle
  sonne ; noter la vitesse et la taille de l'en-tête réelle.

## 9. En résumé

| Question | Réponse |
|---|---|
| Faisable depuis la page ? | Oui, même protocole que le flash USB ([37](37-flash-rapide-usb.md)) `[FAIT]` |
| Autre protocole plus rapide ? | Non : le Model:Cycles n'a que USB MIDI + audio ([04](04-usb-audio.md)) `[FAIT]` |
| Quel système, quel en-tête ? | Mode SMP → `sample`, en-tête 64 o `[FAIT]` ; ~80 o mesuré, à trancher `[À FAIRE]` |
| Vitesse d'une table ~2 Mo ? | ~15 à 20 s `[HYP]`, à mesurer |
| Place libre / tweak ? | Aucun : c'est la page, pas le firmware |

## 10. Réalisation (11/10/2026)

La page sait envoyer : le bouton **« Envoyer à la machine »** apparaît après la conversion
(`docs/convert/index.html`).

- **`docs/flasher/flasher.js`** : `sampleReadDir` (`0x10`), `sampleMakeDir` (`0x11`) et `uploadSample`
  (`0x40` → `0x42` × N → `0x41`), bâties sur le `xferOpen` / `xferFrame` de [37](37-flash-rapide-usb.md) ; en-tête de
  64 o, blocs de `0x2000`, échantillons 16 bits big-endian, pause de 50 ms (`REST_MS`).
- **`docs/convert/index.html`** : charge `../flasher/flasher.js` ; le bouton ouvre le port Web MIDI, demande qui
  répond (`xferIdentify`), **exige l'id 25** (mode SMP de Model-TG) sinon affiche la marche à suivre, crée
  `/Wavetables` et les sous-dossiers du ZIP, puis envoie chaque table ; progression fichier par fichier.

**Preuves** (11/10/2026) :

- `tools/webxfer_check.py` : `uploadSample` envoie **les octets exacts d'Elektroid** (ouverture + 5 blocs de `0x2000`
  + fermeture), et la taille annoncée vaut PCM + 64.
- `tools/webflash_smoke.js` : le faux Model:Cycles apprend `0x10` / `0x11` / `0x40` / `0x42` / `0x41` ;
  `uploadSample` reçoit l'en-tête de 64 o et le PCM 16 bits big-endian **octet pour octet**, un seul bloc pour une
  petite table, aucun message malformé.
- `webflash_check.sh`, `webbuild_check.sh`, `gen_flasher_tweaks --check` verts.

**Débit (11/10/2026)** : `uploadSample` chronomètre chaque bloc et démarre **sans pause** ; sur un bloc refusé ou un
délai dépassé, il **recule** (10 ms, jusqu'à 200 ms) et **renvoie le bloc** — l'accusé de réception suffit à régler le
débit, la pause n'est qu'une marge. La page Convert a un **sélecteur de cadence** (0 / 10 / 25 / 50 ms, retenu dans le
navigateur), un affichage **MB/s · ms/bloc**, le temps du **ping**, une **barre de progression** sur l'ensemble de
l'envoi, et un bouton **Arrêter** qui termine la table en cours puis s'arrête. Le statut dit chaque étape (autorisation
MIDI, machine trouvée, fichier i/n, bloc lent avec recul) — `uploadSample` appelle `onRetry` à chaque recul. La
cadence du **flash de firmware n'est pas touchée** (un OS abîmé ne se récupère pas par USB).

**À faire** : essayer sur la machine (Kevin) à 0 / 10 / 25 / 50 ms — noter MB/s et ms/bloc face au ping, vérifier
qu'une table et un dossier (sous-dossiers compris) jouent — puis fixer la cadence par défaut ; trancher la taille de
l'en-tête (64 contre ~80 mesurés, §7).
