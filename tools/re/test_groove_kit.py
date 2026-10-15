#!/usr/bin/env python3
"""Banc du **kit** de Model:Groove — et l'**obstacle**, nommé.

Ce banc devait prouver en émulation ce que le banc des patterns prouve pour un pattern :
déplier un kit, l'emballer, le déplier de nouveau, et retrouver la même chose. **Il ne le
peut pas**, et ce fichier existe pour que personne ne le redécouvre.

Ce qui est vérifiable, et qui l'est ici :

  A. les quatre décalages du kit dans l'image construite (628 → 828, 694 → 894,
     632 → 832, 708 → 908), octet par octet.

Ce qui ne l'est pas : le **comportement** du kit sous l'OS. Raison (§3.54) : le code du kit
est **orienté objet** — `0x40009a1e` travaille sur un objet, lit son descripteur de classe et
appelle des **méthodes virtuelles** (`%a0@(48)`, `%a0@(84)`) — et chaque morceau de 100 octets
est un **enregistrement imbriqué** (son propre sceau, sa propre version, un **type de machine**
à +88 qui indexe une table de descripteurs). Piloter cela dans une émulation nue demanderait de
reconstruire une tranche de l'OS, pas un banc.

Le chemin des patterns, lui, est de la **donnée plate** — c'est pourquoi son aller-retour
(contrôle E de `test_groove_pattern.py`) fonctionne.

    python3 tools/re/test_groove_kit.py --cycles model-cycles_OS1.13.syx

Sortie 1 (jamais 0) tant que le kit n'est pas prouvé autrement : le kit est **vérifié** site par
site, il n'est pas **prouvé**.
"""
import argparse
import json
import pathlib
import struct
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'emu'))
sys.path.insert(0, str(HERE.parent))

import build                        # noqa: E402
import mcengine as E                # noqa: E402
import mcfw                         # noqa: E402

mcfw.bridge_emac()

TW = HERE.parent.parent / 'tweaks' / 'model-cycles_OS1.13'

# Les deux elements du kit, tels que le derouleur et la sauvegarde les appellent :
#   0x4005d080(deploye, range)  — lit le range, ecrit le deploye (sa SOURCE porte l'en-tete)
#   0x4005b2ae(range, deploye, contexte) — l'inverse (sa DESTINATION porte l'en-tete)
UNPACK = 0x4005D080
PACK = 0x4005B2AE

SRC, DST = 0x40600000, 0x40700000

# Les quatre decalages, dans l'element de depliage : positions des valeurs dans l'instruction.
KIT_CONSTANTS = (
    (0x4005B320, b'\x02\x74', b'\x03\x3c', 'f deploye : 628 -> 828'),
    (0x4005B32E, b'\x02\xb6', b'\x03\x7e', 'g deploye : 694 -> 894'),
    (0x4005B324, b'\x02\x78', b'\x03\x40', 'f range : 632 -> 832'),
    (0x4005B332, b'\x02\xc4', b'\x03\x8c', 'g range : 708 -> 908'),
)


def main():
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    ap = argparse.ArgumentParser(description='banc du kit de Model:Groove')
    ap.add_argument('--cycles', required=True)
    args = ap.parse_args()

    stock = bytes(mcfw.load_mainos(args.cycles, 'cc99d4f0'))
    t1 = json.loads((TW / '56-groove-8tracks.json').read_text(encoding='utf-8'))
    t2 = json.loads((TW / '57-groove-patterns.json').read_text(encoding='utf-8'))
    g1, _ = build.apply_writes(stock, [t1])
    both, _ = build.apply_writes(stock, [t1, t2])

    ok = True
    print('\nA. les constantes du kit dans l\'image construite')
    print('   MAIN OS jalon 1   : %s' % build.sha(g1)[:16])
    print('   MAIN OS jalons 1+2 : %s' % build.sha(both)[:16])
    for va, old, new, label in KIT_CONSTANTS:
        got = both[va - build.BASE:va - build.BASE + 2]
        good = got == new
        ok &= good
        print('   %-28s %s (%s)' % (label, 'ok' if good else 'FAIL', got.hex()))

    print('\nB. le comportement du kit sous l\'OS')
    print('   on essaie de deplier un kit RANGE valide et vide (genre 4, morceaux a zero)...')
    try:
        eng = E.Engine(both)
        packed = bytearray(7680)
        struct.pack_into('>I', packed, 0, 4)          # genre 4 : le seul attendu
        eng.uc.mem_write(SRC, bytes(packed))
        eng.uc.mem_write(DST, bytes(7294))
        eng.call(UNPACK, DST, SRC)
        print('   il a repondu — l\'obstacle du §3.54 a peut-etre disparu : relire ce banc.')
        ok = False
    except Exception as e:
        print('   IMPOSSIBLE : %s' % type(e).__name__)
        print('   Le code du kit est oriente objet (methodes virtuelles) et ses morceaux de')
        print('   100 o sont des enregistrements imbriques dont le TYPE indexe une table de')
        print('   descripteurs : une emulation nue ne peut pas le piloter.')
        print('   Voir notes/56 §3.54. Le kit est VERIFIE site par site, il n\'est pas PROUVE.')

    print('\nconstantes dans l\'image : %s' % ('ok' if ok else 'FAIL'))
    print('comportement sous l\'OS   : NON PROUVE (§3.54)')
    print('\nLe kit est VERIFIE site par site ; il n\'est pas PROUVE. Sortie 1, toujours,')
    print('tant que l\'obstacle du §3.54 n\'est pas leve.')
    raise SystemExit(1)


if __name__ == '__main__':
    main()
