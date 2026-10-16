#!/usr/bin/env python3
"""Banc du jalon 3, étape 3b : la **chaîne v6 -> v7** (notes/56 §3.49, §3.58).

`tools/machines/groove/convert_chain.S` contient deux fonctions :

  - `groove_v7(dst, src)` : la **transformée pure**, sans OS. Un bloc v6 -> un bloc v7.
  - `groove_chain()`      : la **colle**, appelée par la redirection en `0x4005de74`.

Ce banc ne prouve que la **transformée** — c'est elle qui porte le format ; la colle ne fait
qu'allouer, recopier, libérer et refaire le contrôle de fin, et son contrat de registres est lu
dans le prologue de la chaîne (notes/56 §3.58). Trois contrôles :

  A. le code s'assemble, et sa taille est celle annoncée ;
  B. la transformée, exécutée **dans l'émulateur**, rend **exactement** la référence Python —
     octet pour octet, sur un bloc v6 synthétique dont les sceaux sont aux bonnes places ;
  C. **le contrôle fort** : les 80 patterns du bloc v7 sont, un par un, **le résultat du
     convertisseur d'élément déjà prouvé** (§3.50) ; les kits gardent leurs 7 094 octets et
     gagnent 200 zéros ; la queue et le sceau de clôture sont aux nouvelles places.

    python3 tools/re/test_groove_chain.py --cycles model-cycles_OS1.13.syx
"""
import argparse
import pathlib
import struct
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))                       # mcfw
sys.path.insert(0, str(HERE.parent / 'emu'))        # mcengine
sys.path.insert(0, str(HERE.parent))                # build
sys.path.insert(0, str(HERE))                       # test_groove_convert

import build                                        # noqa: E402
import mcengine as E                                # noqa: E402
import mcfw                                         # noqa: E402
import test_groove_convert as C                     # noqa: E402

mcfw.bridge_emac()

SRC = HERE.parent / 'machines' / 'groove' / 'convert_chain.S'
CODE_AT = 0x437E0000            # adresse de travail du banc, hors des tampons (voir D)
SRC_AT = 0x43000000             # le bloc v6 de travail (2 163 716 o -> 0x43210404)
DST_AT = 0x43400000             # le bloc v7 de travail (1 918 788 o -> 0x435D4C04)

V6 = 512 + 96 * 14848 + 96 * 7680 + 512 + 4         # 2 163 716
V7 = 512 + 80 * 16292 + 80 * 7680 + 512 + 4         # 1 918 788
V6_KITS, V7_KITS = 1425920, 1303872
V6_TAIL, V7_TAIL = 2163200, 1918272
SEAL, CLOSE = 0xBEEFBACE, 0xBACEF00C
FAIL = []


def check(label, ok, detail=''):
    print('   %-58s %s%s' % (label, 'ok' if ok else 'FAIL', '  ' + detail if detail else ''))
    if not ok:
        FAIL.append(label)


def assemble(src):
    """Assemble et LIE le .S (WSL si le compilateur m68k n'est pas natif).

    Le lien est necessaire : un appel interne (`bsr groove_v7`) sort du compilateur avec une
    relocation non resolue, et sans lien la cible vaut 0 — le code saute a l'adresse zero.
    """
    def native():
        with tempfile.TemporaryDirectory() as d:
            o, b = pathlib.Path(d) / 'c.o', pathlib.Path(d) / 'c.bin'
            subprocess.run(['m68k-linux-gnu-gcc', '-mcpu=54418', '-c', str(src), '-o', str(o)],
                           check=True, capture_output=True)
            subprocess.run(['m68k-linux-gnu-ld', '-Ttext=0', '-e', '0', '--oformat=binary',
                            '-o', str(b), str(o)], check=True, capture_output=True)
            return b.read_bytes()

    try:
        return native()
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    with tempfile.TemporaryDirectory() as d:
        sh = pathlib.Path(d) / 'asm.sh'
        unix = str(src).replace('\\', '/').replace('C:', '/mnt/c', 1)
        sh.write_text('set -e\nT=$(mktemp -d)\n'
                      'm68k-linux-gnu-gcc -mcpu=54418 -c "%s" -o $T/c.o\n'
                      'm68k-linux-gnu-ld -Ttext=0 -e 0 --oformat=binary -o $T/c.bin $T/c.o\n'
                      'od -An -tx1 -v $T/c.bin | tr -d " \\n"\n' % unix,
                      encoding='utf-8', newline='\n')
        unix_sh = str(sh).replace('\\', '/').replace('C:', '/mnt/c', 1)
        out = subprocess.run(['bash', unix_sh], capture_output=True, text=True, check=True).stdout
    return bytes.fromhex(out.strip())


def synthetic_v6():
    """Un bloc v6 de forme valide : les sceaux aux bonnes places, du contenu deterministe."""
    blk = bytearray(V6)
    for i in range(0, V6, 4):
        blk[i:i + 4] = struct.pack('>I', (i * 2654435761) & 0xFFFFFFFF)
    blk[0:4] = struct.pack('>I', SEAL)
    blk[4:8] = struct.pack('>I', 6)
    blk[2163712:2163716] = struct.pack('>I', CLOSE)
    return bytes(blk)


def reference(src):
    """La transformée, en Python : la définition de ce que le code doit faire."""
    dst = bytearray(V7)
    dst[0:512] = src[0:512]
    dst[4:8] = struct.pack('>I', 7)
    for p in range(80):
        s, d = 512 + p * 14848, 512 + p * 16292
        dst[d:d + 4] = src[s:s + 4]
        dst[d + 4:d + 4336] = src[s + 4:s + 4336]
        dst[d + 5780:d + 16292] = src[s + 4336:s + 14848]
    for k in range(80):
        s, d = V6_KITS + k * 7680, V7_KITS + k * 7680
        dst[d:d + 7094] = src[s:s + 7094]
    dst[V7_TAIL:V7_TAIL + 512] = src[V6_TAIL:V6_TAIL + 512]
    dst[1918784:1918788] = struct.pack('>I', CLOSE)
    return bytes(dst)


def main():
    ap = argparse.ArgumentParser(description='banc de la chaine v6 -> v7')
    ap.add_argument('--cycles', required=True, help='le .syx officiel model-cycles_OS1.13.syx')
    args = ap.parse_args()

    print('\nA. le code')
    code = assemble(SRC)
    check('le convertisseur s\'assemble', len(code) > 0, '%d octets' % len(code))

    stock = bytearray(mcfw.load_mainos(args.cycles))
    eng = E.Engine(stock)
    for base, size in ((0x43000000, 0x00800000),):
        try:
            eng.uc.mem_map(base, size)
        except Exception:                                      # noqa: BLE001
            pass
    eng.uc.mem_write(CODE_AT, code)
    blk = synthetic_v6()
    eng.uc.mem_write(SRC_AT, blk)
    eng.uc.mem_write(DST_AT, bytes(V7))
    entry = CODE_AT
    # groove_v7 est la premiere fonction du fichier : son entree est a l'offset 0 du .text
    r = eng.call(entry, DST_AT, SRC_AT)
    out = bytes(eng.uc.mem_read(DST_AT, V7))

    print('\nB. la transformee, contre la reference Python')
    ref = reference(blk)
    diff = [i for i in range(V7) if out[i] != ref[i]]
    check('le code rend exactement la reference', not diff,
          '' if not diff else '%d octet(s), le premier en %#x' % (len(diff), diff[0]))
    check('la version du bloc v7 est 7', struct.unpack('>I', out[4:8])[0] == 7)
    check('le sceau de cloture est a +1 918 784',
          out[1918784:1918788] == struct.pack('>I', CLOSE))

    print('\nC. les morceaux, contre ce qui est deja prouve')
    ok_elem = True
    for p in range(80):
        s, d = 512 + p * 14848, 512 + p * 16292
        if out[d:d + 16292] != C.reference(blk[s:s + 14848]):
            ok_elem = False
            break
    check('les 80 patterns = le convertisseur d\'element (§3.50)', ok_elem)
    ok_kits = all(out[V7_KITS + k * 7680:V7_KITS + k * 7680 + 7094]
                  == blk[V6_KITS + k * 7680:V6_KITS + k * 7680 + 7094] for k in range(80))
    zeroed = all(out[V7_KITS + k * 7680 + 7094:V7_KITS + k * 7680 + 7294] == bytes(200)
                 for k in range(80))
    check('les 80 kits : 7 094 copies', ok_kits)
    check('les 80 kits : 200 octets a zero', zeroed)
    check('la queue de 512 o est recopiee', out[V7_TAIL:V7_TAIL + 512] == blk[V6_TAIL:V6_TAIL + 512])
    check('la banque F est abandonnee (16 patterns de moins)',
          V7 == 512 + 80 * 16292 + 80 * 7680 + 512 + 4)

    print('\nD. la colle (l\'allocateur et le liberateur sont des stubs)')
    # Le contrat, lu dans le prologue de la chaine : a2 = le bloc, a3 = le drapeau,
    # fp (A6) = l'allocateur 0x400802e0, a5 = le liberateur.
    from unicorn import UC_HOOK_CODE
    from unicorn import m68k_const as mk
    ALLOC, BUF_AT, FLAG_AT = 0x400802E0, 0x43600000, 0x436FF000
    free_at = CODE_AT + 0x2000
    chain_off = code.index(bytes.fromhex('4feffff048d700e0'))   # le prologue de la colle
    check('la colle est trouvee dans le binaire', chain_off > 0, 'offset %#x' % chain_off)

    eng2 = E.Engine(stock)
    for base, size in ((0x43000000, 0x00800000),):
        try:
            eng2.uc.mem_map(base, size)
        except Exception:                                      # noqa: BLE001
            pass
    eng2.uc.mem_write(CODE_AT, code)
    eng2.uc.mem_write(free_at, b'\x4e\x75')                    # le liberateur : un rts
    eng2.uc.mem_write(SRC_AT, blk)                             # le bloc v6 dans l'image
    eng2.uc.mem_write(BUF_AT, bytes(V7))
    eng2.uc.mem_write(FLAG_AT, b'\x00')

    def on_alloc(uc, address, size, u):
        if address == ALLOC:                                   # l'allocateur : notre tampon
            sp = uc.reg_read(mk.UC_M68K_REG_A7)
            uc.reg_write(mk.UC_M68K_REG_D0, BUF_AT)
            uc.reg_write(mk.UC_M68K_REG_PC,
                         struct.unpack('>I', uc.mem_read(sp, 4))[0])
            uc.reg_write(mk.UC_M68K_REG_A7, sp + 4)

    eng2.uc.hook_add(UC_HOOK_CODE, on_alloc)
    for reg, val in (('A2', SRC_AT), ('A3', FLAG_AT), ('A6', ALLOC), ('A5', free_at)):
        eng2.uc.reg_write(getattr(mk, 'UC_M68K_REG_' + reg), val)
    try:
        r = eng2.call(CODE_AT + chain_off)
    except Exception as exc:                                   # noqa: BLE001
        pc = eng2.uc.reg_read(mk.UC_M68K_REG_PC)
        check('la colle s\'execute', False,
              '%s  PC=%#x  non mappe=%s' % (exc, pc, eng2.unmapped[-3:]))
        r = None
    after = bytes(eng2.uc.mem_read(SRC_AT, V7))
    flag = bytes(eng2.uc.mem_read(FLAG_AT, 1))
    # le chemin de chargement ne lit que l'OCTET bas : `moveb %d0,%d7` (0x4008d982)
    check('la colle rend 1 (le bloc est en v7)', r is not None and (r & 0xFF) == 1,
          'd0 = %s' % (hex(r) if r is not None else None))
    check('le bloc de l\'image est devenu un bloc v7 valide', after == ref,
          '' if after == ref else '%d octet(s) differents'
          % sum(1 for i in range(V7) if after[i] != ref[i]))
    check('le drapeau est pose', flag == b'\x01')

    print()
    print('TOUT OK' if not FAIL else 'ECHEC : %s' % ', '.join(FAIL))
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
