# tools/re — rétro-ingénierie du MAIN OS 1.13

Outils de RE (disassemblage, mesures de charge) du projet Modded-Cycles. Le savoir-faire
décodé vit dans les notes (`notes/`), ces scripts le **produisent** : ils re-décodent
l'image officielle à la demande, octet par octet.

À la racine du dépôt, avec Python 3 (`pip install unicorn capstone`) et le `.syx`
officiel dans `firmware/` (**jamais versionné** — téléchargé depuis elektron.se) :
`model-cycles_OS1.13.syx`, SHA-256 `44fe5862…9800640c`. Le code et les adresses sont des
adresses virtuelles 1.13 (VA) : VA = offset dans la section 3 + `0x40000400`.

## mcfw.py — disassembreur du MAIN OS

```python
import mcfw
mcfw.load_mainos('firmware/model-cycles_OS1.13.syx')      # dépaquette la section 3 (MTLib)
mcfw.show(mcfw.disasm(0x400a7d4a, 0x400a7e6a))              # listing de la boucle des voix
mcfw.xrefs(0x42308828)                                      # xrefs littérales d'une constante
mcfw.emac_disasm(0x40056660, 0x40056e90)                    # les EMAC (mac.l…) que capstone ignore
```

- `disasm()` n'utilise que capstone : il bute sur les instructions EMAC et les marque
  `dc.w … <<<` — ce sont des trous, pas du code.
- `m68k-linux-gnu-objdump` est requis pour `emac_disasm` ; natif (`binutils-m68k-linux-gnu`)
  ou via **WSL Ubuntu** (`sudo apt install binutils-m68k-linux-gnu`), les chemins Windows
  sont traduits en `/mnt/<drive>/` automatiquement.

Origin du découpage à la main : les listings de travail du session 11/10/2026 sont restés
dans `build/re8/` (non-versionné, regénérables par scripts analogues). Détails dans les notes
53/54 [54-huit-pistes-audio.md](../../notes/54-huit-pistes-audio.md) et la cartographie du code
dans `notes/`.

## test_load8.py — charge CPU : 6 pistes → 8 pistes

Banc de mesure du §6 de la note 54 (« huit pistes audio »). Deux images dérivées du `.syx`
officiel : le stock, et le même avec la borne de piste `moveq #6→#8` (`0x400a7e40`, en
mémoire d'émulation seulement — **pas un tweak, jamais écrit**). Les pistes 7/8 exécutent des
machines TONE (l'index machine vient du paramètre par piste), ainsi le coût marginal d'une voix
sur une nouvelle piste se mesure immédiatement :

```sh
python3 tools/re/test_load8.py --cycles firmware/model-cycles_OS1.13.syx
```

Protocole des notes 43/51 §8 : note TONE soutenue (trig au bloc 1 puis rien), médiane des blocs
4 à 23. Résultats du 11/10/2026 (le banc vérifie lui-même `TONE == 5291` instr/bloc, le chiffre
de référence du dépôt) : boucle à vide 1 610 (stock) → 2 140 (borne 8, +265 par case vide) ;
6 → 8 TONE = 33 356 → 44 468 instr/bloc = **1,33 × la boucle**, +10,3 points de bloc.
