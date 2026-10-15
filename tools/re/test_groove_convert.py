#!/usr/bin/env python3
"""Banc du jalon 3, étape 3a : le **convertisseur d'élément** (repack d'un pattern v6 -> v7).

`tools/machines/groove/convert_v7.S` est assemblé (m68k, via WSL si besoin), chargé dans une cave
de l'image, et appelé **dans l'émulateur**. Trois contrôles :

  A. le code s'assemble et **tient dans la cave** ;
  B. le repack produit par le CODE est **identique** à la référence Python (transformée d'octets
     pure : aucune hypothèse de validité) ;
  C. **le contrôle fort** : le pattern v6, déplié par l'OS **stock**, et le pattern v7, déplié par
     l'OS **Groove**, donnent les **mêmes pistes 0-5** (pas et queues) — et les pistes 6-7 vides
     côté Groove. C'est la propriété du jalon 2 (§3.48) vue **à travers le convertisseur**.

    python3 tools/re/test_groove_convert.py --cycles model-cycles_OS1.13.syx
"""
import argparse
import json
import pathlib
import struct
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))                       # mcfw
sys.path.insert(0, str(HERE.parent / 'emu'))        # mcengine
sys.path.insert(0, str(HERE.parent))                # build, gen_groove_*

import build                                        # noqa: E402
import mcengine as E                                # noqa: E402
import mcfw                                         # noqa: E402
import test_groove_pattern as P                     # noqa: E402

mcfw.bridge_emac()

SRC = HERE.parent / 'machines' / 'groove' / 'convert_v7.S'
CAVE = 0x40147F22            # plage de 0xFF de 182 octets (build/re8/probe_caves.py)
CAVE_SIZE = 182

STEP = 722
V6_SIZE = 4 + 6 * STEP + 10512      # 14848
V7_SIZE = 4 + 8 * STEP + 10512      # 16292
ZERO = 2 * STEP                     # 1444 : les pas des pistes 6-7


def assemble():
    """Assemble le .S et renvoie ses octets (WSL si le compilateur n'est pas natif)."""
    def native():
        with tempfile.TemporaryDirectory() as d:
            o, b = pathlib.Path(d) / 'c.o', pathlib.Path(d) / 'c.bin'
            subprocess.run(['m68k-linux-gnu-gcc', '-mcpu=54418', '-c', str(SRC), '-o', str(o)],
                           check=True, capture_output=True)
            subprocess.run(['m68k-linux-gnu-objcopy', '-O', 'binary', '-j', '.text', str(o), str(b)],
                           check=True, capture_output=True)
            return b.read_bytes()

    try:
        return native()
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    # Pas de compilateur natif : on passe par WSL, avec un script temporaire (le passage
    # d'un script en ligne de commande depuis Python ne survit pas au bash de Windows).
    with tempfile.TemporaryDirectory() as d:
        sh = pathlib.Path(d) / 'asm.sh'
        unix = str(SRC).replace('\\', '/').replace('C:', '/mnt/c', 1)
        sh.write_text(
            'set -e\n'
            'T=$(mktemp -d)\n'
            'm68k-linux-gnu-gcc -mcpu=54418 -c "%s" -o $T/c.o\n'
            'm68k-linux-gnu-objcopy -O binary -j .text $T/c.o $T/c.bin\n'
            'od -An -tx1 -v $T/c.bin | tr -d " \\n"\n' % unix, encoding='utf-8', newline='\n')
        unix_sh = str(sh).replace('\\', '/').replace('C:', '/mnt/c', 1)
        out = subprocess.run(['bash', unix_sh], capture_output=True, text=True, check=True).stdout
    return bytes.fromhex(out.strip())


def reference(src):
    """La référence : la transformée d'octets, en Python."""
    dst = bytearray(V7_SIZE)
    dst[0:4] = src[0:4]
    dst[4:4 + 6 * STEP] = src[4:4 + 6 * STEP]
    dst[4 + 6 * STEP:4 + 8 * STEP] = b'\x00' * ZERO
    dst[4 + 8 * STEP:V7_SIZE] = src[4 + 6 * STEP:V6_SIZE]
    return bytes(dst)


def make_v6_pattern():
    """Un pattern v6 synthétique, genre 4 (comme le dépliage l'exige), avec les pas
    reconnaissables par piste et la QUEUE RANGÉE À ZÉRO.

    La queue rangée est lue par le gestionnaire comme des entrées de verrou (1 o de pas, 1 o de
    piste, 64 mots) : des octets quelconques lui feraient écrire des verrous sur n'importe quelle
    piste — c'est le piège du §3.46. À zéro, elle est une entrée valide (pas 0, piste 0) et
    identique dans les deux images."""
    buf = bytearray(V6_SIZE)
    struct.pack_into('>I', buf, 0, 4)
    for k in range(6 * STEP):
        buf[4 + k] = (k * 7 + 3) & 0xFF
    return bytes(buf)


def main():
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    ap = argparse.ArgumentParser(description='banc du jalon 3 (convertisseur d\'element)')
    ap.add_argument('--cycles', required=True)
    args = ap.parse_args()

    stock = bytes(mcfw.load_mainos(args.cycles, 'cc99d4f0'))
    t1 = json.loads((P.TW / '56-groove-8tracks.json').read_text(encoding='utf-8'))
    t2 = json.loads((P.TW / '57-groove-patterns.json').read_text(encoding='utf-8'))
    groove, _ = build.apply_writes(stock, [t1, t2])
    ok = True

    print('\nA. le code')
    code = assemble()
    fits = len(code) <= CAVE_SIZE
    cave_ok = stock[CAVE - build.BASE:CAVE - build.BASE + len(code)] == b'\xff' * len(code)
    print('   %d octets assemblés, cave de %d : %s' % (len(code), CAVE_SIZE, 'ok' if fits else 'FAIL'))
    print('   la cave est bien en 0xFF dans l\'image d\'origine : %s' % ('ok' if cave_ok else 'FAIL'))
    ok &= fits and cave_ok

    print('\nB. le repack contre la référence Python')
    v6 = make_v6_pattern()
    ref = reference(v6)
    eng = E.Engine(groove)
    eng.uc.mem_write(CAVE, code)
    SRC_A, DST_A = 0x40600000, 0x40700000        # deux zones mappées libres
    eng.uc.mem_write(SRC_A, v6)
    eng.uc.mem_write(DST_A, bytes(V7_SIZE))
    eng.call(CAVE, DST_A, SRC_A)
    got = bytes(eng.uc.mem_read(DST_A, V7_SIZE))
    same = got == ref
    print('   %d octets comparés : %s' % (V7_SIZE, 'ok' if same else 'FAIL'))
    if not same:
        diff = [i for i in range(V7_SIZE) if got[i] != ref[i]]
        print('   premiers écarts : %s' % ', '.join('%#x' % d for d in diff[:8]))
    ok &= same

    print('\nC. à travers l\'OS : v6 déplié par le stock, v7 déplié par Groove')
    v7 = got
    dep_s = P.unpack(E.Engine(stock), P.DEPLOYED, v6)
    dep_g = P.unpack(E.Engine(groove), P.DEPLOYED, v7)
    steps = dep_g[:6 * STEP] == dep_s[:6 * STEP]
    print('   pas 0-5 : %s' % ('ok' if steps else 'FAIL'))
    ok &= steps
    off_s, off_g = P.tail_off(6), P.tail_off(8)
    tq = all(P.tail_slice(dep_g, off_g, t) == P.tail_slice(dep_s, off_s, t) for t in range(6))
    print('   queues 0-5 : %s' % ('ok' if tq else 'FAIL'))
    ok &= tq
    # Les pistes 6-7 du pattern converti ne doivent porter AUCUN verrou. Le depliage remplit
    # 66 octets par pas (33 mots, §3.44) et laisse le 34e ; un verrou ecrit dans le PREMIER mot
    # d'un pas. On verifie donc les 33 mots remplis : tous doivent rester 0xFFFF.
    bad = 0
    for t in (6, 7):
        sl = P.tail_slice(dep_g, off_g, t)
        for step in range(64):
            base = step * 34
            for w in range(33):
                if struct.unpack_from('>H', sl, 2 * (base + w))[0] != 0xFFFF:
                    bad += 1
    print('   verrous sur les pistes 6-7 : %d mot(s) rempli(s) non 0xFFFF : %s'
          % (bad, 'ok' if bad == 0 else 'FAIL'))
    ok &= bad == 0
    steps67 = dep_g[6 * STEP:8 * STEP]
    nz67 = sum(1 for b in steps67 if b)
    print('   pas des pistes 6-7 : %d octet(s) non nul(s) — issus de zéros, les bornes du '
          'dépliage y substituent leurs valeurs par défaut (contrôle informatif)' % nz67)

    print('\n%s' % ('TOUT OK' if ok else 'ECHEC'))
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
