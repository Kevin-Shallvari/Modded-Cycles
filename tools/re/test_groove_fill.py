#!/usr/bin/env python3
"""Banc du remplissage en cave (notes/56 §3.62) : la seconde boucle de 0x40061738.

Le stub `groove_fill` (tools/machines/groove/fill_patterns.S, 58 o) remplit les 80
creneaux deployes (40 924 o) depuis le pattern 0 : n = pas = 40 924 en immediats
32 bits (pas de piege a signe), index en fin-4, fanion en fin-40 du contenu. On l'execute ici
avec le VRAI memcpy de l'OS (0x4008f1f0) et on compare octet pour octet a une
reference Python — comme le banc D de test_groove_chain.py pour la colle.

L'echelle digiemu (demarrage) prouve le cablage (jsr + bra) ; ce banc prouve la logique.

    python3 tools/re/test_groove_fill.py --cycles model-cycles_OS1.13.syx
"""
import argparse
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'emu'))
sys.path.insert(0, str(HERE.parent))

import build  # noqa: E402
import mcengine as E  # noqa: E402
import mcfw  # noqa: E402
from unicorn import m68k_const as mk  # noqa: E402

mcfw.bridge_emac()

SRC = HERE.parent / 'machines' / 'groove' / 'fill_patterns.S'
TW = HERE.parent.parent / 'tweaks' / 'model-cycles_OS1.13'

CODE_AT = 0x43100000
TABLE_AT = 0x43200000
TEMPLATE_AT = 0x43600000
GUARD_AT = TABLE_AT + 80 * 40924

N = 40924
COUNT = 80
MEMCPY = 0x4008F1F0


def check(label, ok, detail=''):
    print('   %-58s %s %s' % (label, 'ok' if ok else 'FAIL', detail))
    if not ok:
        check.failed = True


check.failed = False


def assemble(src):
    with tempfile.TemporaryDirectory() as d:
        o, b = Path(d) / 'c.o', Path(d) / 'c.bin'
        try:
            subprocess.run(['m68k-linux-gnu-gcc', '-mcpu=54418', '-c', str(src),
                            '-o', str(o)], check=True, capture_output=True)
            subprocess.run(['m68k-linux-gnu-ld', '-Ttext=0', '-e', 0, '--oformat=binary',
                            '-o', str(b), str(o)], check=True, capture_output=True)
            return b.read_bytes()
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass
    with tempfile.TemporaryDirectory() as d:
        sh = Path(d) / 'asm.sh'
        unix = str(src).replace('\\', '/').replace('C:', '/mnt/c', 1)
        sh.write_text('set -e\nT=$(mktemp -d)\n'
                      'm68k-linux-gnu-gcc -mcpu=54418 -c "%s" -o $T/c.o\n'
                      'm68k-linux-gnu-ld -Ttext=0 -e 0 --oformat=binary -o $T/c.bin $T/c.o\n'
                      'od -An -tx1 -v $T/c.bin | tr -d " \\n"\n' % unix,
                      encoding='utf-8', newline='\n')
        unix_sh = str(sh).replace('\\', '/').replace('C:', '/mnt/c', 1)
        out = subprocess.run(['bash', unix_sh], capture_output=True, text=True,
                             check=True).stdout
    return bytes.fromhex(out.strip())


def template(nonce):
    """Un modele reconnaissable : incremental, melange au nonce."""
    return bytes(((i * 7 + nonce) & 0xFF) for i in range(N))


def reference(tpl):
    """La table attendue : 80 copies, index en fin-4, fanion en fin-40 du contenu.

    (Le contenu commence a +28 du curseur : le fanion code en curseur+S-12 est
    bien en contenu S-40. Vérifié par trace des écritures du stub.)
    """
    out = bytearray(COUNT * N)
    for i in range(COUNT):
        base = i * N
        out[base:base + N] = tpl
        struct.pack_into('>I', out, base + N - 4, i)
        out[base + N - 40] = i & 0xFF
    return bytes(out)


def run_fill(stock, code, tpl):
    eng = E.Engine(stock)
    for base, size in ((0x43000000, 0x00800000),):
        try:
            eng.uc.mem_map(base, size)
        except Exception:  # noqa: BLE001
            pass
    eng.uc.mem_write(CODE_AT, code)
    eng.uc.mem_write(TEMPLATE_AT, tpl)
    eng.uc.mem_write(TABLE_AT, bytes(COUNT * N))
    eng.uc.mem_write(GUARD_AT, b'\xAA' * 64)
    # a2 = l'en-tete : les creneaux commencent 28 o plus loin (comme patterns base).
    eng.uc.reg_write(mk.UC_M68K_REG_A2, TABLE_AT - 28)
    eng.uc.reg_write(mk.UC_M68K_REG_D4, TEMPLATE_AT)
    eng.uc.reg_write(mk.UC_M68K_REG_A3, MEMCPY)
    eng.call(CODE_AT)
    table = bytes(eng.uc.mem_read(TABLE_AT, COUNT * N))
    guard = bytes(eng.uc.mem_read(GUARD_AT, 64))
    model = bytes(eng.uc.mem_read(TEMPLATE_AT, N))
    return table, guard, model


def main():
    ap = argparse.ArgumentParser(description='banc du remplissage en cave')
    ap.add_argument('--cycles', required=True, help='le .syx officiel model-cycles_OS1.13.syx')
    args = ap.parse_args()

    print('\nA. le code')
    code = assemble(SRC)
    check('le remplissage s\'assemble et se lie', 0 < len(code) <= 64, '%d octets' % len(code))

    stock = bytearray(mcfw.load_mainos(args.cycles))

    print('\nB. le stub contre la reference Python (vrai memcpy de l\'OS)')
    tpl = template(13)
    table, guard, model = run_fill(stock, code, tpl)
    ref = reference(tpl)
    diff = [i for i in range(COUNT * N) if table[i] != ref[i]]
    check('la table rend exactement la reference', not diff,
          '' if not diff else '%d octet(s), le premier en %#x' % (len(diff), diff[0]))
    check('le 81e creneau est intact (garde 0xAA)', guard == b'\xAA' * 64)
    check('le modele est intact', model == tpl)

    print('\nC. modele a zero (index et fanion viennent du stub, pas du modele)')
    tpl0 = bytes(N)
    table0, guard0, _ = run_fill(stock, code, tpl0)
    ref0 = reference(tpl0)
    diff0 = [i for i in range(COUNT * N) if table0[i] != ref0[i]]
    check('zeros + index/fanion corrects', not diff0,
          '' if not diff0 else '%d octet(s), le premier en %#x' % (len(diff0), diff0[0]))
    check('garde intacte aussi a zero', guard0 == b'\xAA' * 64)

    print('\nD. le stub pose dans l\'image construite')
    t57 = __import__('json').loads((TW / '57-groove-patterns.json').read_text(encoding='utf-8'))
    both, _ = build.apply_writes(stock, [t57])
    cave = bytes(both[0x4018A788 - build.BASE:0x4018A788 - build.BASE + len(code)])
    check('les octets de la cave sont le stub assemble', cave == code)
    jsr = bytes(both[0x400617DA - build.BASE:0x400617DA - build.BASE + 6])
    check('le jsr pointe la cave',
          jsr[:2] == b'\x4e\xb9' and struct.unpack('>I', jsr[2:])[0] == 0x4018A788,
          jsr.hex())
    bra = bytes(both[0x400617E0 - build.BASE:0x400617E0 - build.BASE + 2])
    check('le bra saute a l\'epilogue (0x40061800)',
          bra == b'\x60\x1e', bra.hex())
    dead = bytes(both[0x400617E2 - build.BASE:0x400617E2 - build.BASE + 24])
    check('le corps mort est en nop', dead == b'\x4e\x71' * 12)

    print('\n%s' % ('TOUT OK' if not check.failed else 'ECHEC'))
    raise SystemExit(1 if check.failed else 0)


if __name__ == '__main__':
    main()
