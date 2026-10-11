#!/usr/bin/env python3
"""Charge CPU de la boucle des voix de l'OS 1.13, 6 pistes → 8 pistes (notes/54 §6, notes/55).

Émulation (Unicorn) du vrai code de l'OS sur deux images de recherche, dérivées du
`.syx` officiel UNIQUEMENT :
- « stock »    : l'OS tel quel (baseline) ;
- « borne 8 »  : le même, avec un seul octet changé en mémoire d'émulation —
                 `moveq #6,d0` → `moveq #8,d0` à la borne de piste `0x400a7e40`
                 (70 06 → 70 08). Recherche seule : rien n'est écrit sur le disque.

Protocole des notes 43/51 §8 : note TONE soutenue (trig au bloc 1 puis rien),
médiane des blocs 4 à 23 ; les pistes non actives portent un index de machine hors
limites écrit dans leur état de voix (comme `mcengine.solo`) et la boucle ne les
calcule pas du tout. Le compteur d'instructions par bloc de 32 trames est le proxy
de charge du dépôt (notes 23/27/28/31/51 ; bloc audio de 0,67 ms).

Sortie : tableau instructions/bloc, ratios TONE, part de bloc (conversion note 31).

    python3 tools/re/test_load8.py --cycles model-cycles_OS1.13.syx
"""
import argparse
import struct
import sys
from pathlib import Path

import numpy as np
from unicorn import UC_HOOK_CODE
from unicorn import m68k_const as mk

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))            # mcfw
sys.path.insert(0, str(HERE.parent / 'emu'))   # mcengine (le dépôt)

import mcengine as E                     # noqa: E402
import mcfw                              # noqa: E402

mcfw.bridge_emac()                       # emac.disasm via m68k-objdump (natif ou WSL)

BOUND = 0x400a7e40                       # la borne de piste, notes/54 §1
REF_TONE = 5291                          # une voix d'origine, notes/43 §8 et notes/51 §8
CYCLES = 166667                          # bloc de 0,67 ms après notes/31 (1,54 cycle/instr)
OFF = 9                                  # index hors limites : la voix n'est pas calculée


def bound8(img):
    off = BOUND - mcfw.BASE
    chunk = bytes(img[off:off + 2])
    assert chunk == b'\x70\x06', 'borne inattendue à %#x : %s' % (BOUND, chunk.hex())
    return img[:off] + b'\x70\x08' + img[off + 2:]


class Engine8(E.Engine):
    """Le moteur du dépôt, avec 2 pistes de plus (image de recherche, émulation)."""

    def __init__(self, main_os):
        super().__init__(main_os)
        for t in (6, 7):
            v = E.VOICE0 + t * E.VSTRIDE
            self.uc.mem_write(v + 0x318, struct.pack('>I', 0x8000bd98 + t * 0x30))
            self.call(E.VOICE_RESET, v)   # remise à zéro d'une voix, comme 0..5 au boot
            self.trk.append(dict(color=40, shape=38, sweep=52, contour=42, decay=42,
                                 pitch=64, note=60, machine=4, punch=0, gate=0, finetune=64))
            self.uc.mem_write(E.VOICE0 + t * E.VSTRIDE, struct.pack('>I', OFF))

    def _write_params(self):
        for t in range(len(self.trk)):
            self.uc.mem_write(E.PMOD + 4 * t, struct.pack('>i', int(round(self.trk[t]['note'] * 65536))))
            p = E.PARAMS + 0xe + t * 0x42
            for k, slot in E.SLOT.items():
                self.uc.mem_write(p + slot * 2, struct.pack('>h', int(round(self.trk[t][k] * 256))))

    def block(self, trig_mask=0, release_mask=0):
        n = len(self.trk)
        self._write_params()
        sp = E.STACK - 0x100
        self.uc.mem_write(sp, struct.pack('>IIIII', E.STOP, E.TRACK_BASE, E.PARAMS, trig_mask, release_mask))
        self.uc.reg_write(mk.UC_M68K_REG_A7, sp)
        self.uc.emu_start(E.VOICE_LOOP, E.STOP, count=50_000_000)
        raw = self.uc.mem_read(E.TRACK_BASE, n * 0x80)
        return np.frombuffer(bytes(raw), dtype='>i4').reshape(n, 32).astype(np.int64)


def measure(engine_cls, img, ntracks, active, blocks=24):
    """Note TONE soutenue ; renvoie médiane/max des blocs 4..23, pile, et les blocs."""
    e = engine_cls(img)
    kw = dict(pitch=64, color=30, shape=0, sweep=90, contour=100, punch=0, gate=0, finetune=64, decay=50)
    for t in range(ntracks):
        e.set(t, machine=OFF, **kw)
    for t in active:
        e.set(t, machine=4, **dict(kw, note=36))               # TONE soutenue
        e.uc.mem_write(E.VOICE0 + t * E.VSTRIDE, struct.pack('>I', 4))
    for t in range(ntracks):
        if t not in active:
            # index de machine hors limites dans l'État de la voix (comme mcengine.solo) :
            # la boucle ne calcule pas la voix du tout (un OFF dans les seuls paramètres
            # laisse la boucle dérouler une CHORD muette, d'un coût trompeur).
            e.uc.mem_write(E.VOICE0 + t * E.VSTRIDE, struct.pack('>I', OFF))
    trig = sum(1 << t for t in active)
    n = {'i': 0, 'a7': 1 << 32}

    def hk(uc, addr, size, ud):
        n['i'] += 1
        a7 = uc.reg_read(mk.UC_M68K_REG_A7)
        if a7:
            n['a7'] = min(n['a7'], a7)
    e.uc.hook_add(UC_HOOK_CODE, hk)
    per, out = [], []
    for b in range(blocks):
        i0 = n['i']
        blk = e.block(trig if b == 1 else 0, 0)                # trig au bloc 1, soutenu ensuite
        out.append(blk.copy())
        per.append(n['i'] - i0)
    per = np.array(per)
    tail = per[4:]
    return dict(first=int(per[0]), med=int(np.median(tail)), max=int(tail.max()),
                stack=E.STACK - 0x100 - n['a7'], blocks=out)


def fmt_pct(i):
    return '%.1f %%' % (100.0 * i * 1.54 / CYCLES)


def main():
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')   # console Windows cp1252

    ap = argparse.ArgumentParser(description='charge CPU : boucle des voix stock vs 8 pistes')
    ap.add_argument('--cycles', required=True, help='le .syx officiel model-cycles_OS1.13.syx')
    ap.add_argument('--want-sha', default='cc99d4f0', help='préfixe du SHA-256 de la section 3')
    args = ap.parse_args()

    stock = bytes(mcfw.load_mainos(args.cycles, args.want_sha))
    b8 = bound8(stock)

    def run(stock_e, ntracks, active):
        cls = E.Engine if stock_e else Engine8
        return measure(cls, stock if stock_e else b8, ntracks, active)

    # ---- baseline : OS stock, 6 pistes --------------------------------------
    zero6 = run(True, 6, [])
    t0_6 = run(True, 6, [0])
    full6 = run(True, 6, range(6))
    # ---- image « borne 8 » ----------------------------------------------------
    zero8 = run(False, 8, [])
    t0_8 = run(False, 8, [0])
    t6_8 = run(False, 8, [6])          # la même note sur une piste nouvelle
    t7_8 = run(False, 8, [7])
    full8 = run(False, 8, range(8))

    rows = [
        ('stock : aucune voix calculée', zero6),
        ('stock : 1 voix TONE (trk 0)', t0_6),
        ('stock : 6 voix TONE (toutes)', full6),
        ('borne 8 : aucune voix calculée (7-8 muettes)', zero8),
        ('borne 8 : 1 voix TONE (trk 0)', t0_8),
        ('borne 8 : 1 voix TONE (trk 6)', t6_8),
        ('borne 8 : 1 voix TONE (trk 7)', t7_8),
        ('borne 8 : 8 voix TONE (toutes)', full8),
    ]
    print()
    print('%-40s %7s %9s %9s %8s' % ('scénario', '1er', 'médiane', 'max', 'bloc'))
    for label, r in rows:
        print('%-40s %7d %9d %9d %7s' % (label, r['first'], r['med'], r['max'], fmt_pct(r['med'])))

    base, tone = full6['med'], t0_6['med'] - zero6['med']
    print()
    print('une voix TONE : %d instr/bloc (référence notes/43/51 §8 : %d)' % (tone, REF_TONE))
    print('2 cases vides à la borne : %+d instr/bloc' % (zero8['med'] - zero6['med']))
    print('6 TONE → 8 TONE          : %+d instr/bloc (%.2f × la base)' % (full8['med'] - base, full8['med'] / base))
    print('part de bloc : boucle 6 TONE %s → 8 TONE %s (%+.1f points)'
          % (fmt_pct(base), fmt_pct(full8['med']),
             100 * (full8['med'] - base) * 1.54 / CYCLES))

    ok = True

    def same_outputs(a, b, label):
        eq = np.array_equal(np.array(a['blocks']), np.array(b['blocks'])[:, :6, :])
        print('%s : pistes 0-5 identiques stock vs borne 8 : %s' % (label, 'OK' if eq else 'DIFFERENTS'))
        return eq

    ok &= same_outputs(t0_6, t0_8, '1 note trk 0')
    ok &= same_outputs(full6, full8, '6 notes')
    bad = np.count_nonzero(np.concatenate([b[6:8].ravel() for b in t0_8['blocks']]))
    print('pistes 7/8 sans trig : blocs nuls : %s' % ('OK' if bad == 0 else 'NON : %d valeurs' % bad))
    ok &= bad == 0
    print('TONE attendu %d : %s' % (REF_TONE, 'OK' if tone == REF_TONE else 'DIFFERENT'))
    ok &= tone == REF_TONE
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
