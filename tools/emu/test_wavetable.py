#!/usr/bin/env python3
"""Preuve de la machine Wave (notes/52 ; tweaks/model-cycles_OS1.13/36-wavetable-tg.json).

   1. Convertisseur (tools/wt_convert.py) : la table pre-travailee est bien formee (longueur = F x S_TOTAL, copies
      bornees en bande) et le moteur HOST en joue du son.
   2. Firmware (Unicorn, model-tg-st + wavetable-tg) : demarrage (retouches de Model-TG appliquees, octets d'origine
      verifies), une table convertie joue (grave et aigu) par la vraie boucle des voix, aucune lecture hors memoire ;
      un fichier non converti ne joue rien.
   3. Lecture : sur un aigu, le moteur lit une copie courte (bande limitee), pas la table.

    python3 tools/emu/test_wavetable.py --cycles model-cycles_OS1.13.syx [--table table.wav]
"""
import argparse
import ctypes
import json
import pathlib
import struct
import subprocess
import sys
import tempfile

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import build                        # noqa: E402
import gen_wavetable as GW          # noqa: E402
import mcengine as E                # noqa: E402
import test_model_tg as TM          # noqa: E402
import test_sdvintage as T          # noqa: E402
import wt_convert as WC             # noqa: E402
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_UNMAPPED, UC_HOOK_MEM_READ   # noqa: E402
from unicorn import m68k_const as mk  # noqa: E402

DEV = HERE.parent.parent / "tweaks" / "model-cycles_OS1.13"
BASE = E.BASE
CLOCK = 0x8000184c
OFF = 9                             # machine hors limites : voix non calculée
SLOT, H = 3, 0x00C0FFEE
PCM = 0x4c000000                    # le fichier, où Model-TG l'aurait chargé

FAIL = []
N = 2048


def check(ok, msg):
    print(("  ok    " if ok else "  ECHEC ") + msg, flush=True)
    if not ok:
        FAIL.append(msg)


def read_wav(path):
    d = pathlib.Path(path).read_bytes()
    j, i = d.find(b"fmt "), d.find(b"data")
    fmt, ch, _, _, _, bits = struct.unpack("<HHIIHH", d[j + 8:j + 24])
    n = struct.unpack("<I", d[i + 4:i + 8])[0]
    raw = d[i + 8:i + 8 + n]
    x = (np.frombuffer(raw, "<f4").astype(float) if fmt == 3 else
         np.frombuffer(raw, "<i2") / 32768 if bits == 16 else np.frombuffer(raw, "<i4") / 2 ** 31)
    return x[::ch]


def test_table(seed=7, frames=64):
    """Une table de test : des trames riches (dents de scie et impulsions mêlées), 16 bits."""
    rng = np.random.default_rng(seed)
    t = np.arange(N) / N
    out = []
    for f in range(frames):
        a = f / max(1, frames - 1)
        saw = 1 - 2 * t
        pulse = np.where(t < 0.1 + 0.6 * a, 1.0, -1.0)
        x = (1 - a) * saw + a * pulse + 0.05 * rng.standard_normal(N)
        out.append(x / np.abs(x).max() * 0.9)
    return np.concatenate(out)


def converter_tests(table):
    print("1. convertisseur (tools/wt_convert.py)")
    data = WC.bake(table)
    F = len(data) // WC.S_TOTAL
    check(len(data) % WC.S_TOTAL == 0 and F == len(table) // N,
          f"longueur = {F} trames x S_TOTAL ({len(data)} points)")
    ok = True
    for c, lg, off in WC.SHORT_COPIES:
        sub = data[off * F:off * F + F * (1 << lg)].reshape(F, 1 << lg).astype(float)
        sp = np.abs(np.fft.rfft(sub[0]))
        if sp[WC.hmax(c) + 1:].max() > 0.01 * max(1.0, sp.max()):
            ok = False
    check(ok, f"les {len(WC.SHORT_COPIES)} copies courtes sont bornees en bande (hmax)")
    # HOST : le moteur en joue du son
    with tempfile.TemporaryDirectory() as d:
        h = Host(pathlib.Path(d))
        h.load(SLOT, H, data)
        h.knobs(note=48)
        y = np.concatenate([h.block(trig=(b == 0)) for b in range(40)])
        check(np.abs(y).max() > 1e4, f"HOST : une note joue ({np.abs(y).max():.3g})")
    return data


class Host:
    def __init__(self, tmp):
        (tmp / "wt_tables.h").write_text(GW.tables_h())
        so = tmp / "wt.so"
        subprocess.run(["gcc", "-O2", "-shared", "-fPIC", "-DHOST", f"-I{tmp}", "-Wall", "-Wextra", "-Werror",
                        str(GW.SRC / "wt.c"), str(HERE / "wt_host.c"), "-o", str(so)], check=True)
        self.lib = ctypes.CDLL(str(so))
        self.slot_arr = (ctypes.c_int32 * 192).in_dll(self.lib, "host_slot")
        self.tslot = (ctypes.c_int32 * 6).in_dll(self.lib, "host_track_slot")
        self.tpend = (ctypes.c_int32 * 6).in_dll(self.lib, "host_track_pend")
        self.clock = ctypes.c_uint32.in_dll(self.lib, "host_clock")
        self.mem = ctypes.create_string_buffer(8 << 20)
        ctypes.c_void_p.in_dll(self.lib, "host_mem").value = ctypes.addressof(self.mem)
        self.v = ctypes.create_string_buffer(0x31c)
        self.p = ctypes.create_string_buffer(0x40)
        self.out = (ctypes.c_int32 * 32)()
        for t in range(6):
            self.tslot[t] = -1
            self.tpend[t] = -1

    def load(self, slot, h, data):
        ctypes.memmove(ctypes.addressof(self.mem) + 64, data.tobytes(), len(data) * 2)
        self.slot_arr[slot], self.slot_arr[64 + slot], self.slot_arr[128 + slot] = h, 0, len(data)
        self.tslot[0] = slot

    def knobs(self, note=60, color=0, shape=64, sweep=127, contour=0, decay=127):
        for off, val in ((0x14, 64 << 8), (0x16, color << 8), (0x18, shape << 8), (0x1a, sweep << 8),
                         (0x1c, contour << 8), (0x1e, 0), (0x22, 0x4000), (0x24, decay << 8)):
            struct.pack_into("<h", self.p, off, val)
        self.pmod = note << 16

    def block(self, trig=False):
        struct.pack_into("<iii", self.v, 0x34, 1 if trig else 0, 1 if trig else 0, 0)
        struct.pack_into("<ii", self.v, 0x230, 1 << 20, 1 << 20)
        struct.pack_into("<i", self.v, 0x300, 0)
        self.lib.wt_update(ctypes.c_int32(self.pmod), self.v, self.p)
        self.lib.wt_render(self.out, self.v)
        return np.array(self.out[:], dtype=np.int64)


def fw_tests(stock, data):
    print("2. firmware (model-tg-st + wavetable-tg, Unicorn)")
    tg_tw = json.loads((DEV / "30-model-tg-st.json").read_text(encoding="utf-8"))
    wt = json.loads((DEV / "36-wavetable-tg.json").read_text(encoding="utf-8"))
    tws = [tg_tw, wt]
    p, _ = build.apply_writes(stock, tws)
    pl, _ = build.build_payload(tws, stock, None)
    img = bytes(p) + pl
    pay = int(wt["append"]["dest"], 16)
    rt = build.payload_runtime(wt, stock, None)
    sym = {k: int(v, 16) for k, v in wt["symbols"].items()}
    tg = {k: int(v, 16) for k, v in tg_tw["symbols"].items()}

    # démarrage : jsr 0x40000530 -> notre crochet -> wt_boot -> boot_extra_hook
    uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
    uc.ctl_set_cpu_model(mk.UC_CPU_M68K_ANY)
    uc.mem_map(0x40000000, 0x02400000)
    uc.mem_write(BASE, img)
    uc.mem_map(pay, 0x00100000)
    uc.mem_write(pay, b"\xa5" * 0x00100000)
    uc.mem_map(0x80000000, 0x00010000)
    uc.mem_map(0x90000000, 0x00020000)
    bad = []
    uc.hook_add(UC_HOOK_MEM_UNMAPPED, lambda u, a, addr, s_, v, d: bad.append(addr) or False)
    keep = {r: 0x11110000 + i for i, r in enumerate((mk.UC_M68K_REG_D2, mk.UC_M68K_REG_D3, mk.UC_M68K_REG_D4,
                                                     mk.UC_M68K_REG_D5, mk.UC_M68K_REG_D6, mk.UC_M68K_REG_D7,
                                                     mk.UC_M68K_REG_A2, mk.UC_M68K_REG_A3, mk.UC_M68K_REG_A4,
                                                     mk.UC_M68K_REG_A5, mk.UC_M68K_REG_A6))}
    for r, v in keep.items():
        uc.reg_write(r, v)
    uc.reg_write(mk.UC_M68K_REG_A7, 0x90010000)
    uc.emu_start(0x40000530, tg["boot_extra_hook"], count=5_000_000)
    pc, sp = uc.reg_read(mk.UC_M68K_REG_PC), uc.reg_read(mk.UC_M68K_REG_A7)
    check(pc == tg["boot_extra_hook"] and sp == 0x90010000 - 4 and not bad
          and all(uc.reg_read(r) == v for r, v in keep.items()),
          "jsr 0x40000530 -> notre crochet -> wt_boot -> boot_extra_hook, pile et d2..d7/a2..a6 intactes")
    got = bytearray(uc.mem_read(pay, len(rt)))
    flag = sym["wt_patched"]
    check(got[flag - pay:flag - pay + 4] == b"\0\0\0\1", "retouches faites (drapeau de wt_boot)")
    got[flag - pay:flag - pay + 4] = rt[flag - pay:flag - pay + 4]
    check(bytes(got) == rt, f"charge utile reconstituée à {pay:#x} ({len(rt)} o)")
    be = lambda x: struct.pack(">I", x)
    sites = {sym["tg_pf_site"]: b"\x4e\xb9" + be(sym["wt_or_any"]),
             sym["tg_np_site"]: b"\x4e\xf9" + be(sym["wt_np"]) + b"\x4e\x71\x4e\x71"}
    now = bytes(uc.mem_read(BASE, len(img)))
    diff = [BASE + k for k in range(len(img)) if now[k] != img[k]]
    want = sorted(a + k for a, b in sites.items() for k in range(len(b)) if img[a - BASE + k] != b[k])
    check(all(now[a - BASE:a - BASE + len(b)] == b for a, b in sites.items()) and diff == want,
          f"Model-TG retouché en 2 endroits ({len(diff)} octets), rien d'autre dans l'image")

    # une note : vraie boucle des voix, la table convertie dans la zone de Model-TG
    e = TM.engine(img, end=BASE + len(stock) + tg_tw["append"]["size"], payload=(pay, rt))
    for t in range(1, 6):
        e.uc.mem_write(E.VOICE0 + t * E.VSTRIDE, struct.pack(">II", OFF, OFF))
    e.uc.mem_write(PCM, data.tobytes())
    w32 = lambda a, v: e.uc.mem_write(a, struct.pack(">I", v & 0xffffffff))
    for k, v in ((0, H), (256, PCM), (512, len(data))):
        w32(tg["slot_hash"] + k + 4 * SLOT, v)
    for t in range(6):
        w32(sym["tg_track_slot"] + 4 * t, SLOT if t == 0 else -1)
        w32(sym["tg_track_pend"] + 4 * t, -1)

    def note(n, blocks=120, reads=False):
        e.set(0, machine=GW.WT_MACH, note=n, pitch=64, color=64, shape=64, sweep=127, contour=0, punch=0, gate=0,
              finetune=64, decay=127)
        seen = []
        hk = None
        if reads:
            hk = e.uc.hook_add(UC_HOOK_MEM_READ, lambda u, a, addr, sz, val, d: seen.append(addr))
        y = np.concatenate([e.block(1 if b == 0 else 0)[0] for b in range(blocks)])
        if hk:
            e.uc.hook_del(hk)
        return y[32 * 40:].astype(float), seen

    yl, _ = note(48)
    yh, seen = note(96, reads=True)
    check(not e.unmapped and np.abs(yl).max() > 1e6 and np.abs(yh).max() > 1e6,
          f"grave et aigu jouent (grave {np.abs(yl).max():.3g}, aigu {np.abs(yh).max():.3g}), aucune lecture hors mémoire")

    # sur l'aigu, le moteur lit dans le fichier (les copies y sont, rien n'est calculé)
    inside = [a for a in seen if PCM + 64 <= a < PCM + 64 + len(data) * 2]
    check(len(inside) > 0, f"l'aigu lit dans le fichier ({len(inside)} lectures)")

    # fichier non converti : longueur non multiple de S_TOTAL -> rien
    w32(tg["slot_hash"] + 512 + 4 * SLOT, len(data) - 1)
    yr, _ = note(48, blocks=60)
    check(np.abs(yr).max() == 0, "fichier non converti : rien")
    w32(tg["slot_hash"] + 512 + 4 * SLOT, len(data))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycles", required=True, help="model-cycles_OS1.13.syx officiel")
    ap.add_argument("--table", help="une table (.wav) à la place de la table de test")
    a = ap.parse_args()
    stock = T.main_os_from_syx(a.cycles)
    table = read_wav(a.table) if a.table else test_table()
    data = converter_tests(table)
    fw_tests(stock, data)
    print("\n" + ("TOUT OK" if not FAIL else f"{len(FAIL)} ECHEC(S)"))
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
