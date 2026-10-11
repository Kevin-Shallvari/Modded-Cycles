# 54 — Huit pistes audio : étude de faisabilité

Travail du 11/10. Demande de Kevin (branche `8-audio-tracks`, devenue le projet dérivé
[55-model-groove](55-model-groove.md), branche `model-groove`) : « 8 pistes audio, ce mod ajoutera
2 pistes audio aux 6 d'origine. Je veux étudier uniquement la faisabilité technique. »

**Cette note ne produit aucun tweak** : ni générateur, ni carte dans le flasher, rien d'utilisateur-visible. C'est le
premier balayage des endroits où l'OS 1.13 compte ses **6 pistes audio**, sur l'image officielle (SHA-256 de la
section 3 vérifié : `cc99d4f0…ee98`). C'est la méthode de la note [18](18-septieme-machine.md) (« tout ce qui
dépend du nombre de machines »), appliquée aux **pistes**.

Adresses : VA de l'OS 1.13. Listings de travail (capstone, les EMAC restent en `dc.w`) : produits
par `tools/re/mcfw.py` (versionné, [tools/re/README.md](../tools/re/README.md)) ; les listings bruts
de la séance restent dans `build/re8/` (non versionné, regénérables).

## 0. En bref

| Composant | Ce que le code fait (`[FAIT]` sauf mention) | Pour 2 pistes de plus |
|---|---|---|
| Boucle des voix `0x400a7d4a` | borne `moveq #6,d0` en `0x400a7e40` ; état par voix à `0x42308828 + k·0x31c` (k = 0…5) | lever la borne ; mais la RAM des états est pleine à ras (§2.1) |
| Tampons audio des pistes | 6 tampons de 0x80 o à `0x80001858`, la plage s'arrête exactement à `0x80001b58`, utilisée ensuite (§2.2) | reloger 2 tampons et mettre à jour les littéraux |
| Le mixeur (`0x400567a4…`) | 6 appels notés à la main (pas une boucle comptée), 6 tableaux de gains par piste `0x40a78b80…8c08` (§2.4) | écrire les 2 appels de plus, à la main comme les 6 |
| Table des descripteurs `0x4010dce0` | 76 entrées de 0x38 o ; 30 concernent les encoders par piste, avec l'index 0…5 écrit dans un champ (§2.5) | + 10 entrées (560 o) en cave et les bornes d'accès |
| Format du pattern | 722 o par piste (mémoire et fichier), copie champ à champ codée à la main (`0x4005b4ec`/`0x4005b642`) (§2.3) | code + compatibilité des projets existants |
| Masque de mute de l'interface | mot 32 bits, un bit par piste (`lsl.l d2,d1` à `0x4001386c/0x40013880`) | bits 6 et 7 libres, rien à faire |
| Mutes de l'interface | 3 bornes `moveq #5` dans la chaîne du quick-mute `0x40013846`, `0x40013928`, `0x40013a90` | 3 sites à retoucher |
| Sélection des pistes (touche TRK, grilles, écrans) | **pas décodée** | `[À FAIRE]`, sphère entière |
| La piste MIDI (7ᵉ objet du M:C) | pas décodée | `[À FAIRE]` |

**Verdict : faisable en théorie, chantier le plus lourd jamais tenté sur le M:C.** L'équivalent des notes 18/19
pour les machines, en plus gros : les états de voix et les tampons audio n'ont **pas** de place libre en ligne
(2 relogements de RAM/SDRAM), le format de projet est à ouvrir, et le décodage de l'interface (sélection des
pistes) est encore vierge. À titre de comparaison, le portage des moteurs du Syntakt (notes 16–24) ne touchait pas
au format de projet.

---

## 1. La boucle des voix

(`tools/re/mcfw.py`, listing de `0x400a7d4a` à `0x400a7e6a`.)

- Prologue et tables connus (note 14 §2.3) : `0x400a7d4a`, tables `update`/`render` à `0x40118628`/`0x40118610`.
- **La borne du compteur de pistes est `moveq #6,d0` en `0x400a7e40`**, comparée à `d2`
  (`cmp.l d2,d0` en `0x400a7e56`), boucle en arrière à `0x400a7d96`. C'est *la* seule borne de piste du cœur du
  moteur.
- Les pointeurs per-piste (`a5/a6/a3/a4`) avancent de `0x31c` par piste (`lea $31c(aX)` en
  `0x400a7e42/0x400a7e46/0x400a7e4a/0x400a7e52`) — le pas d'état vocal de la note 14 §2.4.
- Les `moveq #5` au cœur de la boucle (`0x400a7dba/0x400a7dc0/0x400a7df4`) bornent l'**index machine** (machines
  0…5 avec le repli 5, note 18 §5), pas l'index de piste : ils ne changent pas avec le nombre de pistes.

## 2. Où l'OS range les pistes

### 2.1 Les états des voix, en RAM, remplis à ras

- Les états sont à `0x42308828 + k·0x31c`. Les constantes de base (`0x42308828`, `0x4230882c`, `0x4230885c`,
  `0x42308860`) n'apparaissent **chacune qu'une seule fois dans tout l'OS** (scan des xrefs) : reloger le tableau
  ne toucherait que la boucle et les fonctions du même groupe (init des voix, relâchements).
- `0x42308828 + 6·0x31c = 0x42309ad0`, et `0x42309ad0` est déjà utilisé ailleurs (3 références, en
  `0x400598ea`, `0x40059be8`, `0x40059bf6`, l'état audio suivant, cf. note 19). **Conclusion `[FAIT]` : aucune
  case de 7ᵉ/8ᵉ voix n'existe sur place.** Il faut reloger le tableau.

### 2.2 Les tampons audio des pistes

- Six tampons de `0x80` o (32 trames × 4 o) à `0x80001858 + k·0x80`, plage exacte `0x80001858..0x80001b58`
  (9 références littérales à `0x80001858` dans l'OS).
- `0x80001b58` est immédiatement **utilisé ensuite** par le mixeur (4 références, §2.4) comme départ du post-mix.
  **Pas de place sur place pour une 7ᵉ/8ᵉ piste** : 2 tampons à loger ailleurs + les littéraux à reprendre.

### 2.3 Les patterns (séquenceur)

- Stride piste : **722 o** dans la forme mémoire (B : `0x406fa040 + pattern × 30 710 + piste × 722`, note 32 §4)
  et dans la forme fichier (A) ; la copie champ à champ au chargement/enregistrement (`0x4005b4ec` A→B,
  `0x4005b642` B→A) est codée à la main : aucun compteur de pistes n'y apparaît (la boucle en `d6` de
  `0x4005b6f0` parcourt autre chose, pas les pistes). Les 6 pistes passent par les accesseurs de champs
  `0x40015800..0x40017200`, indexés par piste : une piste de plus est une rangée de plus dans tous ces codes.
- La compatibilité des projets existants suppose une conversion (l'OS en fait déjà pour les versions passées :
  `0x4005c040`/`0x4005c1cc`, note 32 §4).

### 2.4 Le mixeur — six appels notés à la main

- **Correction de la note 09 §6** : le « boucle sur 8 emplacements » est en réalité un **masque de 8 bits**
  (`btst d1,d3`, boucle `d1` de 0 à 7, `0x40056a9e..0x40056ac6`) de mute/routage, **pas** une borne du compte de
  pistes et donc pas un « espace de tête ». À corriger dans une note de suivi.
- Le mélange des pistes est écrit **piste par piste** : 6 couples d'appels `pea…` → `jsr` aux fonctions
  `0x40056698`/`0x40056716`, qui multiplient le tampon mono de la piste (`0x80001858`) par un tableau de gains et
  versent dans `0x8000b990` (L, 10 xrefs) ou `0x8000b994` (R, 4 xrefs). Les six tableaux de gains par piste :
  `0x40a78b80`, `…8b9c`, `…8bb8`, `…8bd0`, `…8be8`, `…8c08` (xrefs : `b80` ×3, `b9c`, `bb8`, `bd0`, `be8` ×2
  chacun, `c08` ×3). Les voisins de ces adresses (`…8b98`, `…8bb4`, `…8c00/04/20/24/28/2c/30`) portent les envois
  delay/reverb et des gains sensibles. **Aucun tableau en réserve** : six pistes, six tableaux.

### 2.5 La table des descripteurs `0x4010dce0`

- Table de 76 entrées de 0x38 o = `0x4010dce0..0x4010ed80` (2 888 o), décodée en colonne (`descs.txt`).
- 30 entrées sont **par piste** : 4 encoders (`0x0B..0x0E`) par piste, suivis d'une entrée « toutes » ;
  **l'index de piste (0 à 5) est écrit dans le deuxième mot de chaque entrée**, et il croît mécaniquement de
  colonne en colonne tout au long de la table. Les entrées 0x11/0x12 (LFO/trig params, note 14 §2.1) et les
  machines spéciales 0xA/0xB/0x13 ne portent pas d'index de piste.
- Huit pistes ⇒ **10 entrées de plus** = 560 o de table, plus les bornes d'accès à reprendre.
- La même entité tabulaire pour les **machines** a déjà été étendue (notes 18/19/43) ; pour les **pistes**, rien
  n'a jamais été fait.

### 2.6 L'interface (mutes, sélection des pistes — pas décodée)

- Les mutes par piste tiennent dans un **mot de 32 bits** : bit i = piste i
  (`moveq #1,d1 ; lsl.l d2,d1 ; or/not.l …, $14(a0)` sous `0x400138xx`). Bits 6 et 7 libres.
- La chaîne du quick-mute compte les `moveq #5` (`0x40013846`, `0x40013928`, `0x40013a90`) : trois sites à
  retoucher pour 8, comme on l'a déjà fait pour les bornes des machines.
- La **sélection des pistes** (touche TRK, grilles de pas, TRK + pad, écrans) et la piste **MIDI** du M:C ne sont
  pas décodées : c'est le sous-chantier inconnu du mod.

## 3. Le Model:Samples 1.13 ne fournit pas de modèle « 8 pistes »

(`model-samples_OS1.13.syx`, section 3 extraite : `a351392c…1ab2`.)

- Les deux OS partagent la même écriture : le `TRACK_BASE` du M:S, **`0x80001b48`** (l'équivalent du Cycles
  `0x80001858`), vise **exactement les 9 mêmes littéraux** (6 dans le mixeur, 3 dans le chemin voix/ISR).
- Or le M:S est aussi un OS à 6 pistes audio : la comparaison octet à octet ne donne **aucun** site « piste > 6 »
  à recopier. Le mod doit être systématique sur notre OS, sans modèle.

## 4. Ce qui reste `[À FAIRE]`

1. **Décoder l'UI de piste** : sélection, grilles, écrans, accroche des 7ᵉ/8ᵉ pads côté interface.
   Sous-chantier le plus entièrement inconnu.
2. **Décoder le format projet** au complet : `0x4005c040/c1cc` et la migration des patterns/kits.
3. **Recenser la RAM/SDRAM** avec les relogements : états des voix (0x31c × 2), tampons audio (0x80 × 2),
   tables de gains, réécriture des littéraux (`0x80001858`), et croiser avec ce qui occupe déjà ces zones
   (Modded-Cycles `0x43000000` et les autres modifs RAM).
4. **Le mixeur** : 6 appels → 8, 2 tableaux de gains de plus, preuve en émulation.
5. **Conflits** : `6ch-usbup`, `arp`, `model-tg` et les moteurs du Syntakt partagent les sites de la boucle des
   voix et du mixeur (k = 0…5), le régulateur de charge (notes 25/30/36) compte les pistes.
6. **CPU** : la boucle des voix avec 2 voix TONE de plus coûterait environ **33 % de plus en instructions
   par bloc** — mesuré en émulation, §6.

## 6. Charge CPU : mesuré en émulation `[FAIT en émulation]`

Mesure du 11/10 avec `tools/re/test_load8.py --cycles` (versionné) : la vraie boucle des voix émulée (Unicorn), sur deux
**images de recherche** dérivées de l'OS officiel seul — le stock, et le même avec un seul octet changé
en mémoire d'émulation (la borne `moveq #6→#8` de `0x400a7e40` ; pas un tweak, jamais écrit). Protocole
des notes 43/51 §8 : note soutenue (trig au bloc 1 puis rien), médiane des blocs 4 à 23 ; les pistes non
actives portent un index de machine hors limites écrit dans leur état de voix (comme `mcengine.solo`) et la
boucle ne les calcule pas du tout.

| Cas (médiane en instructions/bloc de 32 trames) | stock 1.13 | borne 8 |
|---|---|---|
| aucune voix calculée (la boucle tourne à vide) | 1 610 | 2 140 |
| 1 voix TONE (trk 0) | 6 901 | 7 431 |
| 1 voix TONE sur **trk 6** | — | 7 431 |
| 1 voix TONE sur **trk 7** | — | 7 431 |
| toutes les voix TONE | **33 356 (6 voix)** | **44 468 (8 voix)** |

- La boucle à vide passe de 1 610 à 2 140 instr/bloc (**+530**) : réserver deux pistes coûte 265 instr/bloc
  par case vide — le coût de la borne seule, sans autre retouche du code.
- Une voix TONE coûte **exactement 5 291 instr/bloc sur une piste 7 ou 8 comme sur le trk 0** : même
  chiffre que notes/43 §8 et notes/51 §8 — le protocole croise les mesures des notes précédentes, et les
  pistes nouvelles se comportent comme les 6 d'origine.
- 6 TONE → 8 TONE : **+11 112 instr/bloc, 44 468 = 1,33 × la base 33 356**. En part de bloc (conversion de
  la note 31 § : 1,54 cycle par instruction, 166 667 cycles par bloc de 0,67 ms), la boucle des voix passe
  d'environ **30,8 % à 41,1 %** du bloc, **+10,3 points**.
- Rapporté à la charge audio complète — l'OS d'origine est déjà à ~77 % du bloc à l'arrêt (notes/23) — ce
  delta décrit la portion « boucle des voix » : deux voix de plus ne suffisent pas à induire des coupures
  à elles seules (le régulateur, notes 25/30/36, juge le bloc réel et ne coupe qu'au-dessus de ~93 %), mais
  **des machines lourdes (Syntakt ≈ 2 TONE par voix, notes 27/31) sur 8 pistes remettront la charge au-dessus
  du plafond** plus vite qu'aujourd'hui. C'est le vrai arbitrage du mod 8 pistes.
- Vérifications du banc (TOUT OK) : pistes 0–5 rendues **octet pour octet identiques** au stock dans les deux
  scénarios ; pistes 7/8 muettes (blocs nuls) tant qu'elles ne sont pas trigées ; une voix sur trk 6 ou trk 7
  coûte le même nombre d'instructions que sur le trk 0 ; profondeur de pile inchangée (56 à 216 o).

Le reste d'un vrai mod 8 pistes — la RAM « états de voix » relogée (§2.1) et le mixeur à 8 appels (§2.4) —
n'est pas mesuré ici : à reprendre avec les §2.1/2.4 quand le code existera.

## 5. Coût si on décide de le faire

| Travaux | Effort | Remarques |
|---|---|---|
| Boucle des voix (borne + états relevés ailleurs) | modéré | suivre les notes 18/19 : `moveq #6 → #8` et une base de piste unique |
| Mixeur (6 appels → 8, 2 tableaux de gains) | modéré | le code existe, à copier à la main deux fois |
| Tampons audio relogés (2 × 0x80) + littéraux | léger | 9 littéraux, simple |
| Table des descripteurs + 10 entrées (560 o) | léger | en cave, avec le changement des bornes |
| Format projet (722 o/piste → 8) et conversion | lourd | la seule partie qui touche les fichiers des utilisateurs |
| UI/sélection des pistes, écrans, claviers | **l'inconnu le plus gros** | décodage à faire entièrement |
| Preuve en émulation + essais sur la machine | lourd | comparable au chantier des moteurs du Syntakt |

**Prise de position** : les deux vrais verrous sont la RAM pleine sur place (§2.1/2.2) et le sélecteur de piste
jamais décodé (§2.6). La suite passe par les points 1 et 3 du §4, sur le modèle des notes 16/18, et il n'y a pas
de `$6 → $8` universel : le nombre de pistes est écrit **partout**, pas à un seul endroit. Suite donnée : la
charte du projet dérivé [55-model-groove](55-model-groove.md).

---

Fichiers de travail : `tools/re/` (versionné : `mcfw.py`, `test_load8.py`, [README](../tools/re/README.md))
; les listings bruts de la séance (`build/re8/` : `mixer.txt`, `pattern_ab.txt`, `descs.txt`, `quickmute.txt`,
`ms_voice.txt` + les `probe_*.py`) restent non versionnés, regénérables avec `tools/re/mcfw.py`.
