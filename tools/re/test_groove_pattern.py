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
UNPACK = 0x4005B894          # depliage d'un pattern : (deploye, range, champ)
SAVE = 0x4005BA0A            # emballage d'un pattern : (range, deploye, drapeau)
TAIL = 0x4005B766            # gestionnaire de queue (appele par UNPACK)

DEPLOYED = 0x406FA040        # la table des patterns (deployee)
PACKED = 0x404E9C20          # l'image projet (les blocs ranges)
DEPLOYED_SIZE = 40924        # 4 + 8 x 722 + 8 x 4385 + 64
PACKED_SIZE = 16292          # 4 + 8 x 722 + 10512
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
    """Un bloc range synthetique, au VRAI format (§3.42) :
       [4 o d'en-tete (genre = 4)][n x 722 o de pas, CONTIGUS][la queue : 112 + 80 x 130 o].

    La queue est laissee a ZERO : le gestionnaire la lit comme des entrees de 130 o
    (1 o de pas, 1 o de piste, 64 mots), et des octets quelconques lui feraient ecrire
    n'importe ou. A zero, elle est une entree valide (pas 0, piste 0) et identique dans
    les deux images — ce qui rend les controles C et D significatifs.
    """
    buf = bytearray(PACKED_SIZE)
    struct.pack_into('>I', buf, 0, 4)                  # le genre attendu par 0x4005b8b0
    for t in range(n):
        base = 4 + t * STEP
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


def tail_off(n):
    """Offset de la queue DEPLOYEE. Le bloc deploye n'a pas d'en-tete : les pas commencent
    en +0 (722 o par piste), donc la queue suit — 4 332 a 6 pistes, 5 776 a 8. C'est ce que
    fait l'appelant de `0x4005b766` : `movel %a2,%d2 / addil #4332,%d2` (le bloc RANGE, lui,
    a un en-tete de 4 o : sa queue est en `a3@(4336)`)."""
    return n * STEP


def deployed_from_steps(n):
    """Un enregistrement DEPLOYE minimal : les pas (722 o par piste, contigus) puis une queue
    entierement a 0xFFFF (« pas de verrou ») — la representation d'un pattern sans verrou.
    C'est l'entree que le chemin d'ECRITURE de l'OS (`0x4005ba0a`) sait emballer."""
    size = 4 + n * STEP + n * LOCKS + 64
    buf = bytearray(b'\xff' * size)
    for t in range(n):
        base = t * STEP
        for k in range(STEP):
            buf[base + k] = (t * 7 + k) & 0xFF
    return bytes(buf)


def pack(engine, deployed, n):
    """Appelle l'ECRITURE de l'OS et renvoie l'enregistrement range produit."""
    size = 4 + n * STEP + 10512
    engine.uc.mem_write(PACKED, bytes(size))
    engine.uc.mem_write(DEPLOYED, deployed)
    engine.call(SAVE, PACKED, DEPLOYED, 0)
    return bytes(engine.uc.mem_read(PACKED, size))


def tail_slice(dep, off, track):
    lo = off + track * LOCKS
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
    # Chaque image recoit un enregistrement RANGE A SON format : 6 pistes pour le stock
    # (14 848 o), 8 pistes pour Groove (16 292 o). Sinon le stock lit sa queue au milieu
    # des pas de la piste 6 — ce qui n'a aucun sens et faussait le controle C.
    packed6 = make_packed(6)
    packed8 = make_packed(8)
    es = E.Engine(stock)
    eg = E.Engine(both)
    dep_s = unpack(es, DEPLOYED, packed6)
    dep_g = unpack(eg, DEPLOYED, packed8)
    off_s, off_g = tail_off(6), tail_off(8)
    print('   offset de la queue : stock %d, grove %d' % (off_s, off_g))
    for label, dep, off in (('stock', dep_s, off_s), ('grove', dep_g, off_g)):
        line = []
        for t in (6, 7):
            sl = tail_slice(dep, off, t)
            filled = sum(1 for i in range(0, len(sl), 2)
                         if struct.unpack_from('>H', sl, i)[0] == NO_LOCK)
            line.append('piste %d -> %3d/%d' % (t, filled, 64 * 34))
        print('   %-6s : %s' % (label, ', '.join(line)))
    s7 = sum(1 for i in range(0, len(tail_slice(dep_s, off_s, 7)), 2)
             if struct.unpack_from('>H', tail_slice(dep_s, off_s, 7), i)[0] == NO_LOCK)
    g7 = sum(1 for i in range(0, len(tail_slice(dep_g, off_g, 7)), 2)
             if struct.unpack_from('>H', tail_slice(dep_g, off_g, 7), i)[0] == NO_LOCK)
    ok &= g7 > 0 and s7 == 0
    print('   piste 7 remplie en grove et pas en stock : %s' % ('ok' if (g7 > 0 and s7 == 0) else 'FAIL'))

    print('\nC. pistes 0-5 identiques au stock')
    same = dep_g[:6 * STEP] == dep_s[:6 * STEP]
    print('   bloc des pas 0-5 (0..%d) : %s' % (6 * STEP, 'ok' if same else 'FAIL'))
    ok &= same
    qok = True
    for t in range(6):
        if tail_slice(dep_g, off_g, t) != tail_slice(dep_s, off_s, t):
            print('   FAIL : queue de la piste %d differente' % t)
            qok = False
    print('   queues des pistes 0-5 : %s' % ('ok' if qok else 'FAIL'))
    ok &= qok

    print('\nD. le stock ne contient aucune zone de verrous apres sa piste 5')
    # le stock finit sa queue en 4332 + 6x4385 = 30642 ; au-dela il n'y a que la queue de
    # l'enregistrement (68 o). Aucun mot 0xFFFF ne doit y apparaitre.
    after = dep_s[off_s + 6 * LOCKS:]
    nlocks = sum(1 for i in range(0, len(after) - 1, 2)
                 if struct.unpack_from('>H', after, i)[0] == NO_LOCK)
    print('   %d mot(s) 0xFFFF sur les %d octets de fin : %s'
          % (nlocks, len(after), 'ok' if nlocks == 0 else 'FAIL'))
    ok &= nlocks == 0

    print('\nE. aller-retour par le code de l\'OS : identite du FORMAT RANGE')
    # On ne suppose RIEN sur le format : on part d'un enregistrement range vide (genre 4),
    # on fait RELIRE l'OS (0x4005b894) puis ECRIRE (0x4005ba0a), deux fois.
    #   - le FORMAT RANGE doit etre stable (c'est le format stocke) ;
    #   - l'enregistrement DEPLOYE, lui, contient des champs derives (§3.45) : il n'est pas
    #     canonique, donc on compare les formes CANONIQUES (apres un cycle) entre les images.
    eok = True
    canon = {}
    for label, img, n in (('stock', stock, 6), ('grove', both, 8)):
        eng = E.Engine(img)
        size = 4 + n * STEP + 10512
        p0 = bytearray(size)
        struct.pack_into('>I', p0, 0, 4)      # le GENRE : sans lui, le depliage abandonne
        dep1 = unpack(eng, DEPLOYED, bytes(p0))
        p1 = pack(eng, dep1, n)
        dep2 = unpack(eng, DEPLOYED, p1)
        p2 = pack(eng, dep2, n)
        stable_p = p1 == p2
        nz = sum(1 for b in p1 if b)
        canon[label] = (dep2, n)
        print('   %-6s (%d pistes) : format range stable %s, %d octet(s) non nuls'
              % (label, n, 'ok' if stable_p else 'FAIL', nz))
        eok &= stable_p
    ok &= eok

    print('\n   formes canoniques, pistes 0-5 (stock vs grove)')
    ds, ns = canon['stock']
    dg, ng = canon['grove']
    same_steps = ds[:6 * STEP] == dg[:6 * STEP]
    print('     pas 0-5 : %s' % ('ok' if same_steps else 'FAIL'))
    ok &= same_steps
    tq = True
    for t in range(6):
        if tail_slice(ds, tail_off(ns), t) != tail_slice(dg, tail_off(ng), t):
            print('     FAIL : queue canonique de la piste %d differente' % t)
            tq = False
    print('     queues 0-5 : %s' % ('ok' if tq else 'FAIL'))
    ok &= tq

    print('\n%s' % ('TOUT OK' if ok else 'ECHEC'))
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
