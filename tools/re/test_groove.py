#!/usr/bin/env python3
"""Banc du jalon 1 de Model:Groove (notes/56 §3.6) : le moteur 8 pistes relogé en DDR.

Émulation (Unicorn) du **vrai code de l'OS**, sur deux images :
  - « stock »  : l'OS 1.13 officiel seul ;
  - « groove » : l'OS officiel + `56-groove-8tracks.json` (jalon 1 : bornes, relogement des
                 lignes par piste dans la fenêtre DDR, reconstruction des deux mini-zones).

Contrôles (chacun affiche ok / FAIL ; sortie non nulle dès qu'un échoue) :

  A. l'image groove se construit et les littéraux relogés sont bien ceux du tweak ;
  B. pistes 0-5 **octet pour octet identiques** au stock (1 note trk 0 ; 6 notes) ;
  C. les pistes **6 et 7 jouent** (une note TONE soutenue sur chacune) ;
  D. les pistes 6-7 sont **muettes** sans trig ;
  E. **isolement** : la piste 6 seule et la piste 7 seule rendent le **même** signal que
     lorsqu'elles jouent ensemble — détecte tout recouvrement entre les deux pistes neuves
     (le contrôle que le banc 0xFF ne peut pas faire : §3.6 point 7, §3.9.2) ;
  F. **banc 0xFF vs 0x00** : les accueils remplis de `0xFF` puis de `0` donnent le même signal —
     rien n'est lu avant d'être écrit dans ce que la boucle des voix touche (§3.6 point 3) ;
  G. **appels de machine par piste** : chacune des huit pistes reçoit son appel, et l'index
     comparé aux tables de six est bien l'index de **machine** (§3.8.f).

Limite assumée : l'ISR complet (mixeur, événements, MIDI, UI) ne s'émule pas (notes/27 §3.4).
Les lignes que la boucle des voix ne touche pas — params, retrig, zone « événements », cluster —
ne sont donc **pas** couvertes par F : elles restent sous la liste machine de Maxime (§3.6 point 5).

    python3 tools/re/test_groove.py --cycles model-cycles_OS1.13.syx
"""
import argparse
import json
import struct
import sys
from pathlib import Path

import numpy as np
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import m68k_const as mk

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))                       # mcfw
sys.path.insert(0, str(HERE.parent / 'emu'))        # mcengine
sys.path.insert(0, str(HERE.parent))                # build, gen_groove_8

import build                                        # noqa: E402
import gen_groove_8 as G                            # noqa: E402
import mcengine as E                                # noqa: E402
import mcfw                                         # noqa: E402

mcfw.bridge_emac()

TWEAK = HERE.parent.parent / 'tweaks' / 'model-cycles_OS1.13' / '56-groove-8tracks.json'
CALLS = (0x400A7E0E, 0x400A7E1E)      # les deux `jsr (a1)` de la boucle (appel machine)
OFF = 9                               # index de machine hors limites : la voix n'est pas calculée
NTRACKS = 8
BLOCKS = 24
TONE = 4                              # index de la machine TONE


class GrooveEngine(E.Engine):
    """Le moteur du dépôt, avec les adresses du jalon 1 (lignes relogées en DDR)."""

    def __init__(self, main_os, lay, fill=None, only=None, ntracks=NTRACKS):
        super().__init__(main_os)
        self.lay, self.n = lay, ntracks
        self.VOICE0 = lay['homes']['etats des voix']
        self.PMOD = lay['homes']['pmod']
        self.OUT = lay['homes']['tampons sortie']
        self.WORK = lay['homes']['tampons travail']
        if fill is not None:                       # banc 0xFF : remplir les accueils AVANT l'init
            for k, (lo, hi, _) in enumerate(lay['spans']):
                if only is None or k == only:
                    self.uc.mem_write(lo, bytes([fill]) * (hi - lo))
        self.trk = [dict(machine=0, pitch=64, note=60, color=0, shape=0, sweep=0, contour=0,
                         punch=0, gate=0, finetune=64, decay=40) for _ in range(ntracks)]
        for t in range(ntracks):
            v = self.VOICE0 + t * E.VSTRIDE
            self.uc.mem_write(v + 0x318, struct.pack('>I', self.WORK + t * 0x30))
            self.call(E.VOICE_RESET, v)

    def _write_params(self):
        for t in range(self.n):
            self.uc.mem_write(self.PMOD + 4 * t, struct.pack('>i', int(round(self.trk[t]['note'] * 65536))))
            p = E.PARAMS + 0xe + t * 0x42
            for k, slot in E.SLOT.items():
                self.uc.mem_write(p + slot * 2, struct.pack('>h', int(round(self.trk[t][k] * 256))))

    def block(self, trig=0, rel=0):
        self._write_params()
        sp = E.STACK - 0x100
        self.uc.mem_write(sp, struct.pack('>IIIII', E.STOP, self.OUT, E.PARAMS, trig, rel))
        self.uc.reg_write(mk.UC_M68K_REG_A7, sp)
        self.uc.emu_start(E.VOICE_LOOP, E.STOP, count=50_000_000)
        raw = self.uc.mem_read(self.OUT, self.n * 0x80)
        return np.frombuffer(bytes(raw), dtype='>i4').reshape(self.n, 32).astype(np.int64)


def make_engine(stock, lay, active, engine=None, fill=None, only=None):
    """Construit et configure un moteur (sans jouer) : une note TONE sur chaque piste active."""
    cls = engine or GrooveEngine
    if cls is E.Engine:
        e = cls(stock)
    else:
        e = cls(stock, lay, fill=fill, only=only, ntracks=NTRACKS)
    v0 = getattr(e, 'VOICE0', E.VOICE0)
    kw = dict(pitch=64, color=30, shape=0, sweep=90, contour=100, punch=0, gate=0, finetune=64, decay=50)
    for t in range(len(e.trk)):
        e.set(t, machine=OFF, **kw)
    for t in active:
        e.set(t, machine=TONE, **dict(kw, note=36))
        e.uc.mem_write(v0 + t * E.VSTRIDE, struct.pack('>I', TONE))
    for t in range(len(e.trk)):
        if t not in active:
            e.uc.mem_write(v0 + t * E.VSTRIDE, struct.pack('>I', OFF))
    return e


def prepare(stock, lay, active, ntracks=None, engine=None, blocks=BLOCKS, fill=None, only=None):
    """Une note TONE soutenue sur chaque piste active ; renvoie les blocs de sortie."""
    e = make_engine(stock, lay, active, engine=engine, fill=fill, only=only)
    trig = sum(1 << t for t in active)
    out = []
    for b in range(blocks):
        out.append(e.block(trig if b == 1 else 0, 0))
    return np.array(out)


def line_stats(stock, lay, active, engine=None, blocks=6):
    """Lignes de cache de 16 o distinctes touchées pendant des blocs (notes/23 §4, notes/27 §3).

    L'émulateur ne chronomètre pas les attentes de la SDRAM : la mesure du dépôt est le nombre de
    lignes distinctes touchées, par région (la DDR est en cache copyback, la SRAM interne non).
    """
    e = make_engine(stock, lay, active, engine=engine)
    seen = {'code': set(), 'DDR data': set(), 'SRAM': set(), 'autre': set()}

    def hk(uc, access, addr, size, value, ud):
        for a in range(addr, addr + size):
            key = ('code' if 0x40000400 <= a < 0x4019B590
                   else 'DDR data' if 0x4019B590 <= a < 0x48000000
                   else 'SRAM' if 0x80000000 <= a < 0x80020000 else 'autre')
            seen[key].add(a >> 4)

    e.uc.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, hk)
    trig = sum(1 << t for t in active)
    for b in range(blocks):
        e.block(trig if b == 1 else 0, 0)
    return {k: len(v) for k, v in seen.items()}
    trig = sum(1 << t for t in active)
    out = []
    for b in range(blocks):
        out.append(e.block(trig if b == 1 else 0, 0))
    return np.array(out)


def machine_calls(stock, lay, active):
    """Compte les appels `jsr (a1)` par piste, et l'index comparé (d4) à chaque appel."""
    e = GrooveEngine(stock, lay)
    for t in range(NTRACKS):
        e.set(t, machine=TONE, pitch=64, color=30, shape=0, sweep=90, contour=100, punch=0,
              gate=0, finetune=64, decay=50, note=36)
        e.uc.mem_write(e.VOICE0 + t * E.VSTRIDE, struct.pack('>I', TONE))
    counts, d4s = {t: 0 for t in range(NTRACKS)}, set()

    def hk(uc, addr, size, ud):
        counts[uc.reg_read(mk.UC_M68K_REG_D2)] = counts.get(uc.reg_read(mk.UC_M68K_REG_D2), 0) + 1
        d4s.add(uc.reg_read(mk.UC_M68K_REG_D4))

    for a in CALLS:
        e.uc.hook_add(UC_HOOK_CODE, hk, begin=a, end=a + 2)
    trig = sum(1 << t for t in active)
    for b in range(6):
        e.block(trig if b == 1 else 0, 0)
    return counts, d4s


def main():
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    ap = argparse.ArgumentParser(description='banc du jalon 1 de Model:Groove')
    ap.add_argument('--cycles', required=True, help='le .syx officiel model-cycles_OS1.13.syx')
    args = ap.parse_args()

    stock = bytes(mcfw.load_mainos(args.cycles, 'cc99d4f0'))
    lay = G.layout()
    tweak = json.loads(TWEAK.read_text(encoding='utf-8'))
    groove, dirty = build.apply_writes(stock, [tweak])
    ok = True

    print('\nA. image')
    print('   %d écritures, %d octets modifiés, MAIN OS %s' % (len(tweak['writes']), sum(dirty), build.sha(groove)[:16]))
    ok &= len(tweak['writes']) > 0 and sum(dirty) > 0
    for name, base, stride, offs in [(n, *G.ROWS[n]) for n in G.ROWS]:
        for off in offs:
            va = base + off
            if groove[va - build.BASE:va - build.BASE + 4] == struct.pack('>I', base + off):
                print('   FAIL : littéral non relogé en %#x' % va)
                ok = False
    print('   littéraux relogés : %s' % ('ok' if ok else 'FAIL'))

    print('\nB. pistes 0-5 identiques au stock')
    s1 = prepare(stock, lay, [0], engine=E.Engine)
    g1 = prepare(groove, lay, [0])
    s6 = prepare(stock, lay, list(range(6)), engine=E.Engine)
    g6 = prepare(groove, lay, list(range(6)))
    for label, s, g in (('1 note trk 0', s1, g1), ('6 notes', s6, g6)):
        eq = np.array_equal(g[:, :6, :], s)
        print('   %-14s : %s' % (label, 'ok' if eq else 'FAIL'))
        ok &= eq

    print('\nC. les pistes 6 et 7 jouent')
    g6only = prepare(groove, lay, [6])
    g7only = prepare(groove, lay, [7])
    for t, g in ((6, g6only), (7, g7only)):
        nz = np.count_nonzero(g[:, t, :])
        print('   trk %d : %d valeurs non nulles : %s' % (t, nz, 'ok' if nz else 'FAIL'))
        ok &= nz > 0

    print('\nD. pistes 6-7 muettes sans trig')
    g0 = prepare(groove, lay, [])
    bad = np.count_nonzero(g0[:, 6:8, :])
    print('   %d valeur(s) non nulle(s) : %s' % (bad, 'ok' if bad == 0 else 'FAIL'))
    ok &= bad == 0

    print('\nE. isolement des pistes neuves (6 seule vs 6+7, idem 7)')
    gboth = prepare(groove, lay, [6, 7])
    for t, alone in ((6, g6only), (7, g7only)):
        eq = np.array_equal(gboth[:, t, :], alone[:, t, :])
        print('   trk %d : %s' % (t, 'ok' if eq else 'FAIL (recouvrement)'))
        ok &= eq

    print('\nF. banc 0xFF vs 0x00, accueil par accueil (pistes actives 0 et 6)')
    active = [0, 6]
    base = prepare(groove, lay, active, fill=0x00)
    culprits = []
    for k, (lo, hi, name) in enumerate(lay['spans']):
        f = prepare(groove, lay, active, fill=0xFF, only=k)
        eq = np.array_equal(f[:, active, :], base[:, active, :])
        print('   %-16s [%#x,%#x) : %s' % (name, lo, hi, 'ok' if eq else 'FAIL'))
        if not eq:
            culprits.append(name)
    ok &= not culprits
    if culprits:
        print('   -> lu avant écrit dans : %s' % ', '.join(culprits))

    print('\nG. appels de machine par piste')
    counts, d4s = machine_calls(groove, lay, list(range(NTRACKS)))
    miss = [t for t in range(NTRACKS) if counts.get(t, 0) == 0]
    print('   appels : %s' % ', '.join('trk%d=%d' % (t, counts.get(t, 0)) for t in range(NTRACKS)))
    print('   index comparé (d4) : %s -> %s' % (sorted(d4s), 'machine (attendu)' if d4s == {TONE} else 'INATTENDU'))
    ok &= not miss and d4s == {TONE}
    if miss:
        print('   FAIL : piste(s) sans appel : %s' % miss)

    print('\nH. lignes de cache de 16 o touchées (6 blocs, 1 note par piste)')
    print('   %-28s %7s %9s %7s %6s' % ('scénario', 'code', 'DDR data', 'SRAM', 'autre'))
    ls6 = line_stats(stock, lay, list(range(6)), engine=E.Engine)
    ls8 = line_stats(groove, lay, list(range(NTRACKS)))
    for label, ls in (('stock : 6 voix', ls6), ('groove : 8 voix', ls8)):
        print('   %-28s %7d %9d %7d %6d' % (label, ls['code'], ls['DDR data'], ls['SRAM'], ls['autre']))
    print('   delta  : code %+d, DDR data %+d, SRAM %+d'
          % (ls8['code'] - ls6['code'], ls8['DDR data'] - ls6['DDR data'], ls8['SRAM'] - ls6['SRAM']))
    print('   La DDR est en cache copyback, la SRAM interne à un cycle (notes/23 §4, notes/27 §3) ;')
    print("   l'émulateur ne chronomètre pas les défauts de cache : ces lignes sont un indicateur,")
    print('   pas un temps — le temps réel se mesure sur la machine (notes/23 §4).')

    print('\n%s' % ('TOUT OK' if ok else 'ÉCHEC'))
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
