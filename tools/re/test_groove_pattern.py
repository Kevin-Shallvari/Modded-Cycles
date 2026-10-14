#!/usr/bin/env python3
"""Banc du jalon 2 de Model:Groove (notes/56 §3.35 à §3.38) : le format de pattern à 8 pistes.

Émulation (Unicorn) du **vrai code de l'OS**, sur trois images :
  - « stock »  : l'OS 1.13 officiel seul ;
  - « g1 »     : l'OS officiel + `56-groove-8tracks.json` (moteur audio, jalon 1) ;
  - « groove » : l'OS officiel + **les deux** (jalon 2 : le format de pattern).

Ce que ce banc appelle : `0x4005b894(a2 = enregistrement déployé, a3 = enregistrement rangé)` —
la boucle de dépliage du chargement d'un pattern, dont le générateur change le **pas** (722,
inchangé) et la **borne** (4332 → 5776), ainsi que le gestionnaire de queue (`0x4005b766`).

Contrôles (ok / FAIL ; sortie non nulle dès qu'un échoue) :

  A. l'image se construit (les deux tweaks, **sans recouvrement**) et les constantes du
     format sont bien celles du tweak ;
  B. le dépliage couvre **huit** pistes : après l'appel, la queue déployée de la **piste 7**
     est remplie (le gestionnaire de queue écrit `0xFFFF`, « pas de verrou ») — et sur le
     stock elle ne l'est pas (la piste 7 n'existe pas) ;
  C. les pistes **0-5 sont dépliées à l'identique** du stock : le changement n'ajoute que 6-7 ;
  D. le stock n'écrit **rien** au-delà de 6 pistes (la géométrie d'origine est bien 6).

Limite assumée : l'aller-retour complet (déplier puis replier, la sauvegarde) demande les
quatre arguments de `0x4005b642` et l'encodage des verrous ; c'est le contrôle suivant.

    python3 tools/re/test_groove_pattern.py --cycles model-cycles_OS1.13.syx
"""
import argparse
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))                       # mcfw
sys.path.insert(0, str(HERE.parent / 'emu'))        # mcengine
sys.path.insert(0, str(HERE.parent))                # build, gen_groove_8, gen_groove_pattern

import build                                        # noqa: E402
import gen_groove_8 as G1                           # noqa: E402
import gen_groove_pattern as G2                     # noqa: E402
import mcengine as E                                # noqa: E402
import mcfw                                         # noqa: E402

mcfw.bridge_emac()

TW = HERE.parent.parent / 'tweaks' / 'model-cycles_OS1.13'
UNPACK = 0x4005B894          # depliage d'un pattern : (deploye, range)
TAIL = 0x4005B766            # gestionnaire de queue (appele par UNPACK)

DEPLOYED = 0x406FA040        # la table des patterns (deployee)
PACKED = 0x404E9C20          # l'image projet (les blocs ranges)
DEPLOYED_SIZE = 40924        # 4 + 8 x 722 + 8 x 4385 + 64
PACKED_SIZE = 19796          # 4 + 8 x 2474
STEP = 722
LOCKS = 4385
TAIL_OFF = 4332
NO_LOCK = 0xFFFF


def build_images(stock):
    t1 = json.loads((TW / '56-groove-8tracks.json').read_text(encoding='utf-8'))
    t2 = json.loads((TW / '57-groove-patterns.json').read_text(encoding='utf-8'))
    off1 = {w['off'] for w in t1['writes']}
    off2 = {w['off'] for w in t2['writes']}
    g1, d1 = build.apply_writes(stock, [t1])
    both, d2 = build.apply_writes(stock, [t1, t2])
    return t1, t2, g1, both, off1 & off2, sum(d1), sum(d2)


def make_packed(n):
    """Un bloc range synthetique : en-tete 4 o (genre = 4) puis n x 2474 o.

    La QUEUE rangee est laissee a ZERO : le gestionnaire la lit comme des entrees de
    verrou, et des octets quelconques lui feraient ecrire n'importe ou (§3.40.c). A zero,
    elle signifie « pas de verrou » — ce qui rend les controles C et D significatifs.
    """
    buf = bytearray(PACKED_SIZE)
    struct.pack_into('>I', buf, 0, 4)                  # le genre attendu par 0x4005b8b0
    for t in range(n):
        base = 4 + t * (STEP + 1752)
        for k in range(STEP):
            buf[base + k] = (t * 7 + k) & 0xFF         # les pas, reconnaissables par piste
    return bytes(buf)


def unpack(engine, deployed, packed):
    """Appelle le depliage de l'OS et renvoie l'enregistrement deploye.

    `0x4005b894` prend TROIS arguments : (deploye, range, valeur rangee en +30706). Le
    troisieme n'est pas lu par le depliage ni par la queue, mais on le fournit proprement.
    """
    engine.uc.mem_write(PACKED, packed)
    engine.uc.mem_write(DEPLOYED, bytes(DEPLOYED_SIZE))
    engine.call(UNPACK, DEPLOYED, PACKED, 0)
    return bytes(engine.uc.mem_read(DEPLOYED, DEPLOYED_SIZE))


def tail_slice(dep, track):
    lo = TAIL_OFF + track * LOCKS
    return dep[lo:lo + 64 * 68]


def main():
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    ap = argparse.ArgumentParser(description='banc du jalon 2 de Model:Groove')
    ap.add_argument('--cycles', required=True, help='le .syx officiel model-cycles_OS1.13.syx')
    args = ap.parse_args()

    stock = bytes(mcfw.load_mainos(args.cycles, 'cc99d4f0'))
    t1, t2, g1, both, inter, n1, n2 = build_images(stock)
    ok = True

    print('\nA. image')
    print('   56 : %d ecritures (%d octets), 57 : %d ecritures' % (len(t1['writes']), n1, len(t2['writes'])))
    print('   recouvrement 56 / 57 : %d' % len(inter))
    print('   MAIN OS jalon 1 : %s' % build.sha(g1)[:16])
    print('   MAIN OS jalon 2 : %s' % build.sha(both)[:16])
    ok &= not inter and len(t2['writes']) > 0
    print('   recouvrement : %s' % ('ok' if not inter else 'FAIL'))

    # les constantes du format, telles que le tweak les ecrit
    print('\n   constantes du format (lu dans l\'image grove)')
    for off, old, new, label in ((0x4005B91E - build.BASE, b'\x00\x00\x10\xec', b'\x00\x00\x16\x90', 'borne des pas 4332 -> 5776'),
                                 (0x4005B926 - build.BASE, b'\x10\xf0', b'\x16\x94', 'offset de la queue 4336 -> 5780')):
        got = both[off:off + len(new)]
        good = got == new
        print('   %-42s %s' % (label, 'ok' if good else 'FAIL (%s)' % got.hex()))
        ok &= good

    print('\nB. le depliage couvre huit pistes (queue de la piste 7 remplie)')
    packed = make_packed(8)
    es = E.Engine(stock)
    eg = E.Engine(both)
    dep_s = unpack(es, DEPLOYED, packed)
    dep_g = unpack(eg, DEPLOYED, packed)
    for label, dep in (('stock', dep_s), ('grove', dep_g)):
        t7 = tail_slice(dep, 7)
        filled = sum(1 for i in range(0, len(t7), 2)
                     if struct.unpack_from('>H', t7, i)[0] == NO_LOCK)
        t6 = tail_slice(dep, 6)
        filled6 = sum(1 for i in range(0, len(t6), 2)
                      if struct.unpack_from('>H', t6, i)[0] == NO_LOCK)
        print('   %-6s : piste 6 -> %3d/%d mots 0xFFFF, piste 7 -> %3d/%d'
              % (label, filled6, 64 * 34, filled, 64 * 34))
    g7 = sum(1 for i in range(0, len(tail_slice(dep_g, 7)), 2)
             if struct.unpack_from('>H', tail_slice(dep_g, 7), i)[0] == NO_LOCK)
    s7 = sum(1 for i in range(0, len(tail_slice(dep_s, 7)), 2)
             if struct.unpack_from('>H', tail_slice(dep_s, 7), i)[0] == NO_LOCK)
    ok &= g7 > 0 and s7 == 0
    print('   piste 7 remplie en grove et pas en stock : %s' % ('ok' if (g7 > 0 and s7 == 0) else 'FAIL'))

    print('\nC. pistes 0-5 identiques au stock')
    same = dep_g[:TAIL_OFF] == dep_s[:TAIL_OFF]
    print('   bloc des pas (0..4332) : %s' % ('ok' if same else 'FAIL'))
    ok &= same
    for t in range(6):
        a, b = tail_slice(dep_g, t), tail_slice(dep_s, t)
        if a != b:
            print('   FAIL : queue de la piste %d differente' % t)
            ok = False
    print('   queues des pistes 0-5 : %s' % ('ok' if ok else 'FAIL'))

    print('\nD. le stock n\'ecrit rien au-dela de six pistes')
    beyond = dep_s[TAIL_OFF + 6 * LOCKS:]
    nz = sum(1 for b in beyond if b)
    print('   octets non nuls apres la piste 5 : %d : %s' % (nz, 'ok' if nz == 0 else 'FAIL'))
    ok &= nz == 0

    print('\n%s' % ('TOUT OK' if ok else 'ECHEC'))
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
