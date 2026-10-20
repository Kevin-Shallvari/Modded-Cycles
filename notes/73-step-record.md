# 73 — Step record : entrer les notes d'un pattern pas à pas

Demande de Maxime (20/10/2026) : séquenceur à l'arrêt, un mode « step record » où chaque note jouée s'écrit dans le
trig courant, avec les paramètres de la machine modifiés par l'utilisateur ; PLAY saute un pas, STOP recule, le pas
courant clignote vite en rouge, le mode se quitte une fois tous les pas parcourus. Choix faits avec lui avant le
travail : entrée par un **double appui sur REC** (un appui seul garde le grid recording d'origine) ; notes par les
**touches TRIG (piste active) et les pads T1–T6 (leur piste)** ; les notes tenues ensemble vont **sur le même pas**,
qui avance au dernier relâchement ; les potards tournés restent appliqués aux notes suivantes et **le son de la
piste revient à son état d'avant** à la sortie. Tweak `tweaks/model-cycles_OS1.13/45-step-rec.json`, générateur
`tools/gen_step_rec.py`, sources `tools/machines/step_rec/`, preuve `tools/emu/test_step_rec.py`. Adresses : VA de
l'OS 1.13.

## En bref

- Le step record ne fait **rien de neuf côté séquenceur** : il écrit chaque note comme le live rec de l'OS l'écrit
  (`0x40012158` : trig, note, vélocité, micro-décalage nul), sur **notre** pas au lieu du pas joué, et chaque potard
  comme le live rec en fait un p-lock (`0x4001646a`). La preuve compare la mémoire du projet, octet pour octet, avec
  celle que l'enregistreur du live rec de l'OS produit pour les mêmes notes et les mêmes potards.
- Six accroches dans la tâche de l'interface : touches de transport, message d'une note jouée, d'une note relâchée,
  setter des mots du son, image des LED, tick à 30 Hz. Hors step record, chacune rend la main à l'original dès son
  premier test.
- Code dans neuf masques de sprites libérés (2 362 o) ; 248 o de variables en `0x4233e800`, dans le trou libre
  au-dessus du BSS (notes/56 §3.5.2).
- `[FAIT en émulation]` (§5). **Testé sur la machine le 20/10/2026** (§7).

## 1. Ce que fait l'OS

### 1.1 Les touches de transport `[FAIT]`

| Adresse | Rôle |
|---|---|
| `0x4002439a` | `TransportView` (vtable `0x40100fec`, [2]) : codes **9 = REC, 10 = PLAY, 11 = STOP** (`0x4007240c`, que Model-TG enveloppe) ; `d2` = l'événement, `a3` = la vue, rend 1 si l'événement est pris (`0x40024650`, `d4`) |
| `0x40072454`, `0x40072490`, `0x40072480`, `0x40072460` | drapeaux de l'événement (+16) : bit 0 appui, bit 1 FUNC, **bit 2 double appui** (même touche en moins de 32 ticks, 267 ms, notes/33 §1), bit 3 répétition |
| `0x40024482` | REC appuyé : live rec coupé (`0x4006ba90(ui, 0)`), grid recording basculé (`0x4006ba20`) |
| `0x4002449c` | PLAY : départ (`0x400542dc`), pause (`0x40056060`), live rec si REC tenu (`0x4007faf4(9)`) |
| `0x400244d4` | STOP : `0x40055f14` ; double appui : `0x40056004` |
| `UIStates` (`0x400cf9a8`) | +357/+358 grid recording (`0x4006b978` ; `0x4006b9f6(ui, v)` l'écrit), +359 live rec (`0x4006ba76` = séquenceur en lecture et +359), +389 choix de pattern (`0x4006bb18`) |
| `0x4005481a` | état du séquenceur : 0 arrêt, 1 lecture, 2 pause (notes/34 §2) |
| `TransportView` +44 | son contrôleur de vues, écrit par `View::setController` (vt[20], `0x40076336`) ; les popups y sont empilés (`0x4007700e`) |

### 1.2 Les notes jouées `[FAIT]`

- Toute note jouée (touches TRIG en chromatique, pads, clavier MIDI) passe par `0x4008171e(piste, note, vélocité,
  0x40, …)` et toute fin de note par `0x4008145e(piste, note, 0x40)`. Les deux postent **toujours** un message de
  type 12 à l'interface (`0x40080bf6`) : +4 = 0 note / 1 fin, +8 piste, +16 note, +17 vélocité, +28 pas joué
  (`0x40056178`). Model-TG (Scale Lock) replie la note avant, en `0x4008173c` et `0x40081474` : le message porte la
  note repliée.
- Le gestionnaire `0x40007000(app, message)` (charge utile en message + 12) : un pas tenu en grid recording reçoit la
  note ; sinon, **seulement en live rec** (`0x4006ba76` en `0x4000721c`), `0x40012158` l'écrit. Fin de note : idem
  en `0x40007120`, `0x40011c84` donne la longueur.
- `0x40012158(projet, piste, note, vélocité, …, pas, micro, …, retrig)` : piste = `0x4000cfcc(0x4000f208(projet),
  piste)` (`pattern + 70 + 88 × piste`) ; trig posé s'il n'y en a pas (`0x40017b48(piste, pas, 1)`, drapeaux
  seulement, la longueur du pas ne change pas) ; note `0x40016642`, vélocité `0x400166c2`, micro `0x400167bc(… ,
  micro + 64)`. Chaque écriture refuse un pas au-delà de la longueur de la piste (`0x40016402`).

### 1.3 Les potards `[FAIT]`

- `0x4000b274(accesseur, id, valeur, piste, enregistrer, …)` borne la valeur, puis le setter `0x4000ba7a` (vtable
  `0x400fd134` [92]) écrit le mot k = `0x4005a4e8(id)` du son en **son + 20 + 2k** (`3184 2a14` en `0x4000bae2`),
  puis, si le drapeau « enregistrer » est mis, `0x4000f4b8` : en live rec, p-lock du pas joué par
  `0x4001646a(piste, pas, k, valeur)` (trig de lock posé s'il n'y a pas de trig). Enfin la notification « k changé »
  (`objet son vt[4](objet, {0x400fd0ac, k})`).
- Les vues de paramètres passent « enregistrer » = 1 (`0x4001de12` : 1, 1) ; LEVEL/DATA (volume, pan) passe 0
  (`0x4001ab2c`) : le live rec ne les enregistre pas, le step record non plus.
- Accesseur de la piste t : `0x400097f0(projet + 116, t)` (8 o dans le kit : vtable, objet son). Stockage d'un p-lock
  (`0x4000dece`) : données de la table + 2 × (4 385 × piste + 34 × pas + k), `0xffff` = pas de lock.
- `0x400164b0(piste, pas, k)` **efface** un p-lock (rend vrai s'il existait) : ce n'est pas une lecture.

### 1.4 Les LED `[FAIT]`

- Une image des LED (`0x40006a4a`) n'est faite que si le contrôleur de vues est marqué (+33, `0x40076c04`) :
  remise à zéro des 54 états, puis `0x40076ca2` (les vues), puis la fin d'image. **Le premier état posé gagne**
  (`0x40005f86(objet, led, état, 0x404a8cb8)` ; 1 éteinte, 2 allumée).
- LED logiques : touches de pas 1–16 (`0x4000608c(i)`), pages 32–35 (`0x400060ac(i)`), REC/PLAY/STOP 28–30,
  potards 36–47, pads 48–53 (tables bâties par l'initialisation statique `0x400d018c`).
- Tick de l'interface à 30 Hz (message 5, notes/44) : `0x400081e4` appelle `0x40082464`, un simple `rts`.

## 2. Conception

| Accroche | Remplace | Rôle |
|---|---|---|
| `0x400243d6` | `moveq #10,d0 ; cmp.l d4,d0 ; beq.s` | `sr_key` → `sr_transport(code, vue, événement)` ; pris : la vue rend 1 |
| `0x4000721c` | `jsr 0x4006ba76` | `sr_on` : en step record, la note est écrite et « pas de live rec » envoie le gestionnaire à sa fin |
| `0x40007120` | `jsr 0x4006ba76` | `sr_off` : idem pour le relâchement |
| `0x4000bae0` | `movea.l d0,a0 ; move.w d4,20(a0,d2.l*2)` | `sr_set` : en step record et avec « enregistrer », la valeur d'avant ; puis l'écriture, rejouée à l'octet près |
| `0x40006a76` | `jsr 0x40076ca2` | `sr_leds` : nos états d'abord, puis les vues |
| `0x400081e4` | `jsr 0x40082464` (`rts`) | `sr_tick` : clignotement et arrêt si besoin |

- **Entrée** : REC, appui frais avec le drapeau de double appui, sans FUNC ni TRACK, PATTERN, SETTINGS tenus (Model-TG
  en fait son modificateur), séquenceur pas en lecture, pas de choix de pattern. Le premier appui a allumé le grid
  recording (comportement d'origine) : il est éteint (`0x4006b9f6(ui, 0)`), le live rec coupé. Pas 1, longueur de
  la piste active, popup « Step-rec:\nON » (`0x400747c0`, comme « Live-rec:\nQuantized »).
- **Note** (message +8, +16, +17) : sur le pas courant de **sa** piste, comme `0x40012158` (trig s'il n'y en a pas,
  note, vélocité, micro 64), puis un p-lock pour chaque mot de cette piste changé par l'utilisateur et différent de
  sa valeur d'avant. La note entre dans la liste des notes tenues (8 au plus) ; au dernier relâchement, si quelque
  chose a été écrit, le pas avance. Après le dernier pas : fin.
- **PLAY / STOP** (sans note tenue) : pas suivant / précédent (pas avant le pas 1). **REC** : fin. Les autres
  événements de ces trois touches sont pris (pas de départ du séquenceur) ; avec un modificateur, ceux de l'OS.
- **Potards** : au premier changement d'un mot (piste, k), sa valeur d'avant est gardée (32 au plus), et à chaque
  changement la dernière valeur posée. **Fin** : chaque mot revient à sa valeur d'avant, avec la notification, sauf
  si autre chose l'a changé depuis (un preset chargé : il n'est pas écrasé).
- **LED** : touches de la page du pas courant (trigs de la piste active allumés, pas au-delà de la longueur éteints),
  le pas courant et sa page clignotent (état 2/1 alterné tous les 4 ticks, 3,75 Hz ; le tick marque le contrôleur),
  REC allumé.
- **Arrêts forcés** (tick) : séquenceur en lecture (Start MIDI), grid recording allumé : fin avec le son rétabli ;
  pattern changé : fin **sans** rétablir (les objets son sont ceux du nouveau pattern).

## 3. Place libre et conflits

- Masques libérés (`tools/sprites.py`), libres sur toutes les branches au 20/10/2026 : cinq 47×47 rendus libres par
  le retrait de Chord Keys (`0x40182b38`, `0x40182e28`, `0x4018cd48`, `0x4018d1b8`, `0x4018d4a8`) et quatre 48×22
  (`0x4018a608`, `0x4018d798`, `0x4018f80c`, `0x40190184`), chacun redirigé vers sa copie gardée. `sr_active` y est,
  à 0 dans l'image : seule variable qui doit valoir 0 au démarrage.
- Variables (248 o) en `0x4233e800..0x4233e8f7`, dans le trou `0x423380b0..0x4233efff` qu'aucun code de l'OS ni aucun
  tweak ne vise (notes/56 §3.5.2 ; `lfo-plus` est en `0x4233f000`). Non remises à zéro : toutes posées à l'entrée.
  Déclarées dans `REGISTRY.md` §6 (`tools/registry.py`, `DECLARED`).
- Aucune des six accroches n'est touchée par un autre tweak (`check_overlaps.py`) ; aucun tweak de la bibliothèque ni
  des branches ouvertes ne cite `0x4233e000..0x4233efff` (relevé du 20/10/2026 ; une ancienne version de `lfo-plus`
  sur la PR #93 visait `0x4233ed00`, hors de notre fenêtre).
- Compatible avec tout l'OS 2.0 : Model-TG (sa lecture des codes de touche, son Scale Lock), l'arpégiateur (ses
  messages ne partent qu'en live rec), trig-hold et trigless-dim (mode grille seulement), level-pan (le pan n'a pas le
  drapeau « enregistrer »), lfo-plus (son get/set enveloppe le setter : notre accroche est dans l'original).

## 4. Le tweak

24 écritures : 9 zones de code, 9 redirections de masques, 6 accroches. Hors step record, le coût est un test d'octet
par appel des six accroches.

## 5. Preuve en émulation

`tools/emu/test_step_rec.py --cycles … --syntakt …`, sur l'OS entier (`os.json`, charges utiles à leur adresse
d'exécution), sur un **vrai projet** : bloc de données posé comme au démarrage (`0x4000ea3a(0x406fa024)`), projet
neuf (`0x40061738` : kits et 96 patterns aux défauts), objets projet, état de l'interface et LED bâtis par leurs
constructeurs. Interceptés seulement : new/delete, le contrôleur de vues (popups notés), la distribution des messages
et des touches aux vues, les LED des vues, le post d'un message (capturé et rendu au vrai `0x40007000`), le départ et
l'arrêt du séquenceur.

| Cas | Résultat |
|---|---|
| REC une fois, PLAY, STOP | comme d'origine (grid recording, départ du séquenceur) |
| REC deux fois, en lecture ; avec FUNC | pas de step record |
| REC deux fois, à l'arrêt | step record, grid recording éteint, pas 1 sur 16, popup sur le contrôleur |
| Notes par `0x4008171e`/`0x4008145e`, messages au vrai `0x40007000` | une note par pas, deux notes tenues (pistes 1 et 3) sur le même pas, avance au dernier relâchement, PLAY avec une note tenue ignoré |
| PLAY, STOP | pas suivant, précédent, pas avant le pas 1 |
| Mémoire du projet | **= celle de l'enregistreur du live rec (`0x40012158`) pour les mêmes notes sur les mêmes pas** |
| Potards (`0x4000b274` → `0x4000ba7a`) | son entendu ; p-locks sur les notes suivantes de la piste, plus pour un mot remis à sa valeur, aucun pour un changement sans « enregistrer » ni sur une autre piste ; sortie : mots rétablis ; mémoire **= notes du live rec + locks de `0x4001646a` + son rétabli, octet pour octet** |
| Fin | après le pas 16 ; par REC ; séquenceur lancé, grid recording : son rétabli ; autre pattern : son laissé |
| LED (vraie image `0x40006a4a`) | hors step record : les mêmes qu'à l'origine ; pas 1, 2 allumés, 3 éteint, 4 clignotant, page 1, REC ; clignotement tous les 4 ticks |
| Hors step record | notes (arrêt, live rec), potards, image des LED : mêmes résultats et même mémoire qu'à l'origine |

En chemin, la preuve a trouvé deux erreurs, corrigées : le mot du son est en **+20** + 2k (`2a14` : déplacement
0x14), pas +14 ; et `0x400164b0` efface un lock au lieu de le lire.

Non couvert : le vrai clavier et les vrais pads (la preuve part de `0x4008171e`, où ils arrivent), le temps réel (le
double appui, la répétition des touches), l'écran (le popup est construit par le vrai code, pas affiché), la
synthèse.

## 6. Plan de test sur la machine (PR #101)

1. À l'arrêt, deux appuis rapides sur REC : *Step-rec: ON*, REC allumé, TRIG 1 clignote vite. Un appui seul : grid
   recording comme avant ; REC + PLAY : live rec comme avant.
2. Touches TRIG : notes sur la piste active, pas par pas ; relire en lecture.
3. Pads : une grosse caisse et un charleston ensemble sur un même pas ; la piste de chaque pad.
4. PLAY saute, STOP recule ; arrêt tout seul après le dernier pas ; REC arrête.
5. Tourner DECAY puis jouer deux notes : les deux ont le lock, le son de la piste revient à la fin.
6. Pattern de 32 ou 64 pas : la page suit le pas courant (voyant de page clignotant).
7. Avec Model-TG (Sampler, Scale Lock) et les moteurs du Syntakt ; avec un clavier MIDI.

## 7. Testé sur la machine (20/10/2026)

Maxime a flashé l'OS de la branche `claude/step-record` (PR #101, MAIN OS `82a79f45…cca9`) sur son Model:Cycles,
suivi le plan de test du §6, et répondu : « ça marche nickel. tu peux fusionner ». Le détail point par point n'a pas
été rapporté ; la fonction passe en `tested` (`os.json`).
