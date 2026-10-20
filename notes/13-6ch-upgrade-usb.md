# 13 · Variante `6ch-usbup` : garder l'upgrade USB avec le mod 6 canaux

Travail du 25/09/2026, **sans matériel et sans l'image firmware**. Les domaines d'Elektron sont bloqués par le proxy de l'environnement de travail, donc aucun build complet n'a été fait ici.
Tout ce qui dépend de l'image est vérifié **par `build.py`, sur ta machine**, au moment du build.
Ce qui est fait correspond au point E de la feuille de route ([08 §E](08-feuille-de-route.md#e-récupérer-lupgrade-usb-et-le-full-speed)).

> ✅ **Validée sur un vrai Model:Cycles le 29/09/2026.** L'utilisateur a flashé `6ch-usbup` par USB (`CONFIG > UPGRADE`) depuis l'OS officiel.
> Les 6 canaux marchent. Il a ensuite reflashé par USB, **avec `6ch-usbup` installé**, une image `6ch-usbup` + SD VINTAGE, qui a pris.
> La mise à jour par USB survit donc au mod : c'est la variante qu'installe le flasher web, qui n'envoie plus qu'en USB.
> La récupération par le MIDI IN ([RECOVERY.md](../RECOVERY.md)) reste la voie de secours.

> **Mise à jour (build sur l'image réelle, [14 §5](14-machine-sd-vintage.md#5-place-libre--les-caves-0xff-étaient-des-masques-de-sprites)).**
> - La première cave, `0x40154ae4`, est en fait le **masque 0xFF d'un sprite** 32×260 : les stubs y auraient fait des trous à l'écran, et `build.py` exigeait `--force-cave`.
> - Les stubs sont maintenant dans le masque `0x4015c044` (720 o, sprite 64×90). Ce sprite est redirigé vers un masque identique : même rendu.
> - Le build passe sans `--force-cave`, et les stubs émulés à leur nouvelle adresse donnent les mêmes registres et la même mémoire.
> - Les mesures du §3 datent de l'ancienne cave. Les stubs n'ont pas changé d'un octet et restent indépendants de leur position.

> **Mise à jour ([35](35-glitches-usb-multipiste.md), 04/10/2026).** `6ch-usbup` n'a plus les mêmes octets que `6ch-multiout` pour le flux :
> - chaque bloc part vers l'ordinateur au début de l'interruption suivante, à heure fixe, au lieu de juste après son calcul ;
> - la file est alignée au démarrage du flux, le ring passe de 8 cases de 192 o à 9 cases de 168 o (même SRAM), 8 cases amorcées ;
> - la copie des 6 pistes (`tracks6`) est déroulée, mêmes octets écrits. Le tableau ci-dessous décrit la variante d'avant.

---

## En bref

| | `6ch-multiout` (ms-multi-output) | **`6ch-usbup`** (cette note) |
|---|---|---|
| Sortie 6 canaux (pilote, ring, config audio) | oui | **identique** (mêmes octets) |
| Où sont les 4 stubs | dans 4 descripteurs USB (2 CDC, 2 MIDI seule) | dans le masque de sprite libéré `0x4015c044` (720 o), **mêmes octets** |
| Descripteurs CDC et MIDI seule | écrasés par du code | **d'origine** |
| Table des modes USB (`0x4013e544`) | 4 entrées redirigées vers la config audio | **d'origine** |
| `CONFIG → UPGRADE` par USB | cassé (README de l'auteur) | **marche** (testé le 29/09/2026) |
| `USB MODE = MID` | sert quand même la config audio 6 canaux | MIDI seul, **comme en stock** |
| Testé sur matériel | oui, sur un M:S en cross-flash | **oui, sur un vrai Model:Cycles** (29/09/2026) |

Build : `python3 tools/build.py -i model-cycles_OS1.13.syx -t 6ch-usbup`. Les deux variantes sont incompatibles : `build.py` refuse de les combiner.

## 1. Pourquoi `6ch-multiout` casse l'upgrade USB

- **`[FAIT]`** Le README de l'auteur l'écrit : « this image reuses the two bootloader USB descriptors as code space, so `CONFIG → UPGRADE` over USB stops working ».
- **`[FAIT]`** La table des modes USB ([01 §4.b](01-ms-multi-output.md#4b-table-des-modes-usb-fait-valeurs-hyp-sémantique)) a 4 entrées. D'origine, elles pointent sur 2 configs MIDI seule (101 o) et 2 configs CDC-ACM (75 o).
  La config audio+MIDI HS (`0x4019b2b6`, 328 o), celle qui passe en 6 canaux, **n'est pas dans cette table** : elle est choisie par un autre chemin.
- **`[FAIT]`** Le patch d'origine écrit ses 4 stubs dans ces 4 descripteurs, 4 à 6 octets après leur début (pour éviter la fonction de « fixup », [09 §5](09-analyse-firmware-1.13.md#5--découverte-importante--les-descripteurs-sont-réécrits-à-lexécution)).
  Il redirige ensuite les 4 entrées de la table vers la config audio pour ne jamais servir ces descripteurs corrompus. La redirection ne sert qu'à ça.
- **`[HYP]`** (déjà posée en [04 §3](04-usb-audio.md#3-descripteurs)) Les configs CDC, ou les configs MIDI seule, sont celles du mode upgrade. D'où la perte de l'upgrade par USB.
- ⇒ Si les stubs vont ailleurs, on peut **tout laisser d'origine** dans les descripteurs et dans la table.
  La seule différence USB avec le stock reste la config audio passée en 6 canaux (3 octets, [01 §4.c](01-ms-multi-output.md#4c-descripteur-de-configuration-hs-audiomidi-0x4019b2b6-328-o)).

## 2. Conception

- **Les stubs ne changent pas d'un octet.**
  - Ils sont indépendants de leur position : leurs branchements internes sont relatifs, leurs sauts de retour absolus, et ils n'adressent que des registres, `TRACK_BASE` et `SLOT_BASE`.
  - On les copie avec un **décalage constant de −0x3F020**, multiple de 16. Chacun garde l'alignement modulo 16 du build testé, et les écarts entre stubs restent les mêmes.
- **Les 4 crochets du pilote** ne changent que par l'adresse de leur `jmp`.
- **La cave** `0x4015c044` (720 o) :
  - c'est le masque `0xFF` du sprite 64×90, libéré en faisant lire à ce sprite le masque identique `0x40154ae4` ([14 §5](14-machine-sd-vintage.md#5-place-libre--les-caves-0xff-étaient-des-masques-de-sprites), `tools/sprites.py`) ;
  - elle n'empiète ni sur les caves des tweaks de drumkilla (`0x40147f22`–`0x40148b86`), ni sur celles de SD VINTAGE : tout reste combinable ;
  - le bloc de stubs (292 o d'une extrémité à l'autre) est centré dans la cave.

| Stub | Avant (descripteur) | Après (cave) | Taille | Crochet | Reprise |
|---|---|---|---|---|---|
| prime6 | `0x4019b136` (CDC n°1) | `0x4015c116` | 32 o | `0x400027e8` | `0x400027fe` |
| token6 | `0x4019b182` (CDC n°2) | `0x4015c162` | 26 o | `0x40002a42` | `0x40002a4c` |
| tracks6 | `0x4019b1e0` (MIDI n°1) | `0x4015c1c0` | 74 o | `0x40002a06` | `0x40002a26` |
| dstoff6 | `0x4019b244` (MIDI n°2) | `0x4015c224` | 22 o | `0x400029e4` | `0x400029ee` |

- **Ce qui reste identique à `6ch-multiout`** :
  - les 9 écritures du pilote (ring, masques, strides, `MaxPacketLength`) ;
  - les 3 écritures de la config audio (`bNrChannels` ×2, `wMaxPacketSize`).
- **Ce qui disparaît** : les 5 écritures dans les descripteurs et les 8 écritures dans la table des modes.
- **Ce qui s'ajoute** : la redirection du sprite (4 o en `0x400b6434`). On passe de 29 à 21 écritures.
- **Outillage** :
  - `tools/relocate_6ch.py` dérive `11-6ch-usbup.json` de `10-6ch-multiout.json`, mécaniquement, sans l'image ;
    - `--check` vérifie que le fichier versionné est à jour ;
    - `--cave VA:taille` vise une autre cave si celle-ci pose problème ;
  - `tools/build.py` a deux nouveaux contrôles (§4).

## 3. Ce qui est vérifié ici (sans image ni matériel)

- **Dérivation** : chaque octet de stub couvert par une écriture de `6ch-multiout` est recoupé. Un seul ne l'est pas, `0x4019b147` : il vaut `01` dans le stub comme dans le descripteur, donc la table d'origine ne l'écrivait pas.
- **Différences entre variantes** (image synthétique portant les octets d'origine connus) : `6ch-multiout` et `6ch-usbup` ne diffèrent que dans :
  - les cibles des 4 `jmp` (12 o) ;
  - la cave (149 o) ;
  - les descripteurs (143 o) ;
  - la table des modes (15 o).
  Avec `6ch-usbup`, descripteurs et table sont **identiques à l'origine**.
- **Émulation ColdFire** (Unicorn, [annexe](#annexe--émulation-des-crochets)). Pour chacun des 4 stubs, on part du crochet du pilote et on s'arrête au point de reprise, avec les octets lus dans les deux fichiers JSON.
  - `6ch-multiout` et `6ch-usbup` donnent **les mêmes registres, la même mémoire et le même nombre d'instructions** (9, 12, 270 et 8).
  - La sémantique est celle des sources de l'auteur :
    - prime6 remplit le dTD (`0x00900080`, `0xdead0001`, 144) ;
    - token6 donne 144 et 144<<16 ;
    - dstoff6 renvoie `[SLOT_BASE]` + trames×24 ;
    - tracks6 entrelace les 6 blocs de piste, en inversant les octets et avec le repli modulo 32, et restaure tous les registres.
  - Tout le reste de la mémoire contenait une instruction illégale : aucun octet hors crochet et stub n'a été exécuté.
  - Le modèle `cfv4e` de QEMU n'implémente pas `byterev` (ISA_C). tracks6 a donc été émulé avec le modèle `any` ; le vrai MCF5441x possède cette instruction.
- **Recompression** (`aplib.repack`, sur un flux synthétique) :
  - le flux imite une zone `0xFF` de 1040 o encodée en copie chevauchante, puis une copie lointaine qui lit l'intérieur de cette zone ;
  - après écriture des 4 stubs, le flux réencodé se décompresse exactement en l'image patchée, avec une somme d'en-tête cohérente ;
  - `repack` réencode en littéraux toute opération qui écrit **ou lit** un octet modifié.
- **Désassemblage** : les branchements de tracks6 visent l'intérieur du stub déplacé (aujourd'hui `ble.w` → `0x4015c1fc`, `bne.w` → `0x4015c1e2`, `bgt.w` → `0x4015c1d6`, relu dans l'image construite), et les 4 `jmp` de retour visent les reprises d'origine.
- **Contrôles de `build.py`**, testés sur des images synthétiques :
  - les deux variantes ensemble sont refusées ;
  - un pointeur injecté dans la cave bloque le build, sauf avec `--force-cave` ;
  - un pointeur sur le 1er octet de la cave est signalé comme tel ;
  - un `lea (d16,PC)` injecté est signalé en avertissement ;
  - sur des données aléatoires : 0 référence sûre et 0 à 5 références douteuses (faux positifs) par image ;
  - le contrôle prend 0,2 s.

## 4. Ce que `build.py` vérifie sur TON image

1. **Octets « old »** (comme avant) : chaque octet de la cave doit valoir `0xFF`, sinon refus.
2. **Zone** : du début du bloc `0xFF` jusqu'à la fin des octets écrits, affichée.
   Attendu : `zone 0xFF utilisee : 0x4015c044..0x4015c239 (502 o)`.
3. **Références vers cette zone dans l'image d'origine** :
   - une constante 32 bits qui pointe dedans (pointeur, `jmp`/`jsr` absolu, adresse immédiate) **bloque le build**. La zone ne serait pas libre ; `--force-cave` passe outre après vérification à la main ;
   - sauf si ses octets sont réécrits par le tweak lui-même : c'est le cas du pointeur de masque du sprite. Il est affiché comme « neutralisé » ;
   - un adressage `(d16,PC)` ou un branchement qui vise la zone est **affiché pour vérification**, sans bloquer. Une donnée peut ressembler à une instruction.
   Attendu : `reference reecrite par un tweak (neutralisee) : 0x400b6434 -> 0x4015c044 (constante 32 bits)`, puis `references (constantes 32 bits) vers ces zones dans l'image d'origine : aucune`.
4. **Incompatibilités** : `6ch-multiout` et `6ch-usbup` ensemble sont refusés, y compris avec `--all`.

## 5. Risques restants

- **`[HYP]` La cave pourrait ne pas être libre.** Une écriture à l'exécution via un pointeur de base + décalage ne se voit pas en analyse statique.
  - Ici, c'est le masque d'un sprite statique : il n'est lu que par le dessin, et plus du tout une fois le sprite redirigé. Le risque est faible.
  - Symptômes : plantage, gel ou son corrompu, éventuellement longtemps après le démarrage.
  - Parade : le protocole du §6, et la récupération par le MIDI IN.
  - Si ça arrive : viser un autre masque libéré (`tools/sprites.py`), par exemple `python3 tools/relocate_6ch.py --cave 0x4018a788:1024` (pas combinable avec SD VINTAGE, qui l'occupe), puis refaire le build.
- **`[HYP]` L'upgrade USB pourrait dépendre d'autre chose** que les descripteurs, par exemple des constantes du pilote que le mod change aussi.
  Le README de l'auteur n'invoque que les descripteurs, mais seul le test tranchera.
- **Comportement changé par rapport à `6ch-multiout`** : `USB MODE = MID` redevient « MIDI seul », comme en stock. Avant, il servait la config 6 canaux.
- **Inchangé** :
  - hôte USB High Speed obligatoire ;
  - pas de mix stéréo en USB ;
  - la récupération par le menu de démarrage passe par le MIDI IN.

## 6. Protocole de test matériel `[À FAIRE]`

0. Récupération prête : MIDI IN (câble jack stéréo ou adaptateur DIN), OS officiel 1.13, projets sauvegardés.
1. **Build** : `python3 tools/build.py -i model-cycles_OS1.13.syx -t 6ch-usbup`. Garder la sortie : les lignes « zone 0xFF » et « références » répondent au §4.
2. **Flash** par le menu de démarrage (MIDI IN), comme d'habitude.
3. **Démarrage et interface** : la machine démarre, l'interface répond.
4. **6 canaux** : dérouler le plan de [06 §3](06-flash-et-recuperation.md#3-vérifier-premier-vrai-modelcycles) (6 canaux, carte des canaux, `analyse_dupes`).
5. **Endurance** : au moins 30 minutes en jouant et en naviguant (changement de pattern et de projet, sauvegarde, navigateur de sons), puis extinction et rallumage.
   C'est là qu'une cave mal choisie se trahirait.
6. **Modes USB** : `CONFIG → DEVICE → USB MODE = MID` doit donner un périphérique MIDI seul. Retour à `A+M` : les 6 canaux reviennent (question Q14 de la feuille de route).
7. **Le test clé** : depuis `6ch-usbup`, `CONFIG → UPGRADE` par USB avec Transfer, en envoyant l'**OS officiel 1.13**.
   - Si la machine l'installe et revient en stéréo, **l'upgrade USB est rétabli** ✅.
   - Refaire ensuite l'aller par USB (`6ch-usbup` depuis l'OS officiel) pour valider tout le cycle sans MIDI IN.
8. Consigner les résultats (dans `tests/`) et mettre à jour cette note.

## Annexe : émulation des crochets

Reproduit le §3 : Python 3.9+, `pip install unicorn` ; à lancer depuis la racine du dépôt.

```python
"""Émule chaque crochet -> stub -> reprise, octets lus dans les deux fichiers JSON :
v1 = 10-6ch-multiout (stubs dans les descripteurs USB), v2 = 11-6ch-usbup (stubs dans la cave).
Compare v1 et v2 (registres, mémoire, nombre d'instructions) et vérifie la sémantique attendue."""
import json, pathlib
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
from unicorn import m68k_const as mk

T = pathlib.Path("tweaks/model-cycles_OS1.13")
BASE, TRACK_BASE, SLOT_BASE = 0x40000400, 0x80001858, 0x404a05e8
HOOKS = {"prime6": (0x400027e8, 0x400027fe), "token6": (0x40002a42, 0x40002a4c),
         "tracks6": (0x40002a06, 0x40002a26), "dstoff6": (0x400029e4, 0x400029ee)}
D, A = mk.UC_M68K_REG_D0, mk.UC_M68K_REG_A0


def image(name, extra=()):
    mem = {}
    for w in json.loads((T / name).read_text())["writes"]:
        for i, b in enumerate(bytes.fromhex(w["new"])):
            mem[w["off"] + BASE + i] = b
    mem.update(extra)
    return mem


def sample(t, f):
    return (t << 24) | (f << 16) | 0x5A00 | (t * 32 + f)


def run(mem, name):
    hook, ret = HOOKS[name]
    uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
    uc.ctl_set_cpu_model(mk.UC_CPU_M68K_ANY)            # cfv4e de QEMU n'a pas byterev (ISA_C)
    for base, size in ((0x40000000, 0x200000), (0x404a0000, 0x10000), (0x80000000, 0x10000), (0x90000000, 0x10000)):
        uc.mem_map(base, size)
    uc.mem_write(0x40000000, b"\x4a\xfc" * 0x100000)    # hors patch : instruction illégale partout
    for a, b in mem.items():
        uc.mem_write(a, bytes([b]))
    uc.reg_write(mk.UC_M68K_REG_A7, 0x9000f000)
    for k in range(8):
        uc.reg_write(D + k, 0x11110000 + k)
    for k in range(7):
        uc.reg_write(A + k, 0x22220000 + k)
    if name == "prime6":
        uc.reg_write(A + 2, 0x80008000)                  # a2 = dTD
    elif name == "token6":
        uc.reg_write(D + 0, 0x80008100)                  # d0 = pointeur dTD
        uc.reg_write(D + 4, 6)                           # d4 = trames
    elif name == "dstoff6":
        uc.reg_write(D + 0, 3)                           # trames déjà dans la case
        uc.mem_write(SLOT_BASE, (0x80009800).to_bytes(4, "big"))
    else:
        for t in range(6):
            for f in range(32):
                uc.mem_write(TRACK_BASE + t * 0x80 + f * 4, sample(t, f).to_bytes(4, "big"))
        uc.reg_write(D + 0, 12)                          # 6 trames (mots longs)
        uc.reg_write(D + 1, 0x80009900)                  # destination
        uc.reg_write(D + 3, 30)                          # offset de trame : teste le repli mod 32
    steps = []
    uc.hook_add(UC_HOOK_CODE, lambda u, addr, size, _: steps.append(addr))
    uc.emu_start(hook, ret, count=5000)
    regs = [uc.reg_read(D + k) for k in range(8)] + [uc.reg_read(A + k) for k in range(8)]
    return uc.reg_read(mk.UC_M68K_REG_PC), regs, bytes(uc.mem_read(0x80008000, 0x2000)), len(steps)


def expected(name, regs, sram):
    rd = lambda a: int.from_bytes(sram[a - 0x80008000:a - 0x80008000 + 4], "big")
    if name == "prime6":
        return (rd(0x80008004), rd(0x80008000), rd(0x80008020)) == (0x00900080, 0xdead0001, 144)
    if name == "token6":
        return (regs[8], regs[0], regs[4]) == (0x80008100, 144, 144 << 16)
    if name == "dstoff6":
        return regs[1] == 0x80009800 + 3 * 24
    exp = b"".join(int.from_bytes(sample(t, (30 + k) & 31).to_bytes(4, "big")[::-1], "big").to_bytes(4, "big")
                   for k in range(6) for t in range(6))
    got = sram[0x1900:0x1900 + len(exp)]
    return got == exp and regs[:8] == [12, 0x80009900, 0x11110002, 30, 0x11110004, 0x11110005, 0x11110006, 0x11110007]


v1 = image("10-6ch-multiout.json", {0x4019b147: 0x01})   # octet de prime6 égal au descripteur d'origine
v2 = image("11-6ch-usbup.json")
for name in HOOKS:
    r1, r2 = run(v1, name), run(v2, name)
    print(f"{name:8s} reprise 0x{r2[0]:08x}, {r2[3]:3d} instructions, v1 == v2 : {r1 == r2}, "
          f"sémantique : {expected(name, r2[1], r2[2])}")
```

Sortie obtenue le 25/09/2026 :
```
prime6   reprise 0x400027fe,   9 instructions, v1 == v2 : True, sémantique : True
token6   reprise 0x40002a4c,  12 instructions, v1 == v2 : True, sémantique : True
tracks6  reprise 0x40002a26, 270 instructions, v1 == v2 : True, sémantique : True
dstoff6  reprise 0x400029ee,   8 instructions, v1 == v2 : True, sémantique : True
```
