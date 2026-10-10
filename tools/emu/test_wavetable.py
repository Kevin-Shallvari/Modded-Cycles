#!/usr/bin/env python3
"""Preuve de la machine Wave (notes/52 ; tweaks/model-cycles_OS1.13/36-wavetable-tg.json).

  1. Moteur sur l'ordinateur (wt.c compilé avec HOST, mêmes entiers) : copies par demi-octave comparées à la
     référence exacte (FFT en flottant), repli d'une note tenue avant et après les copies, rien hors de la zone.
  2. Firmware (Unicorn, model-tg-st + wavetable-tg) : démarrage (retouches de Model-TG appliquées, octets d'origine
     vérifiés), une note de notre machine rendue par la vraie boucle des voix sur une table chargée.

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
import gen_syntakt_engines as gs    # noqa: E402
import gen_wavetable as GW          # noqa: E402
import mcengine as E                # noqa: E402
import test_model_tg as TM          # noqa: E402
import test_sdvintage as T          # noqa: E402
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_UNMAPPED   # noqa: E402
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


class Host:
    def __init__(self, tmp):
        (tmp / "wt_tables.h").write_text(GW.tables_h())
        so = tmp / "wt.so"
        subprocess.run(["gcc", "-O2", "-shared", "-fPIC", "-DHOST", f"-I{tmp}", "-Wall", "-Wextra", "-Werror",
                        str(GW.SRC / "wt.c"), str(HERE / "wt_host.c"), "-o", str(so)], check=True)
        self.lib = ctypes.CDLL(str(so))
        g = lambda n, t: t.in_dll(self.lib, n)
        self.slot_arr = (ctypes.c_int32 * 192).in_dll(self.lib, "host_slot")
        self.tslot = (ctypes.c_int32 * 6).in_dll(self.lib, "host_track_slot")
        self.tpend = (ctypes.c_int32 * 6).in_dll(self.lib, "host_track_pend")
        self.clock = g("host_clock", ctypes.c_uint32)
        self.mem = ctypes.create_string_buffer(8 << 20)
        self.copies = ctypes.create_string_buffer(GW.POOL_BYTES)
        self.scratch = ctypes.create_string_buffer(64 << 10)
        for name, buf in (("host_mem", self.mem), ("host_copies", self.copies), ("host_scratch", self.scratch)):
            ctypes.c_void_p.in_dll(self.lib, name).value = ctypes.addressof(buf)
        self.v = ctypes.create_string_buffer(0x31c)
        self.p = ctypes.create_string_buffer(0x40)
        self.out = (ctypes.c_int32 * 32)()
        for t in range(6):
            self.tslot[t] = -1
            self.tpend[t] = -1

    def load(self, slot, h, samples):
        pcm = (np.clip(np.round(samples * 32767), -32768, 32767)).astype("<i2").tobytes()
        ctypes.memmove(ctypes.addressof(self.mem) + 64, pcm, len(pcm))
        self.slot_arr[slot], self.slot_arr[64 + slot], self.slot_arr[128 + slot] = h, 0, len(samples)

    def knobs(self, note=60, color=0, shape=64, sweep=127, contour=0, decay=127):
        struct.pack_into(">hhhhhhhhhh", self.p, 0x14, 64 << 8, color << 8, shape << 8, sweep << 8, contour << 8, 0,
                         0, 0x4000, decay << 8, 0)
        # le moteur lit les mots en ordre natif sur l'ordinateur
        for off, val in ((0x14, 64 << 8), (0x16, color << 8), (0x18, shape << 8), (0x1a, sweep << 8),
                         (0x1c, contour << 8), (0x1e, 0), (0x22, 0x4000), (0x24, decay << 8)):
            struct.pack_into("<h", self.p, off, val)
        self.pmod = (note - 64 + 64) << 16

    def block(self, trig=False):
        struct.pack_into("<iii", self.v, 0x34, 1 if trig else 0, 1 if trig else 0, 0)
        struct.pack_into("<ii", self.v, 0x230, 1 << 20, 1 << 20)
        struct.pack_into("<i", self.v, 0x300, 0)
        self.lib.wt_update(ctypes.c_int32(self.pmod), self.v, self.p)
        self.lib.wt_render(self.out, self.v)
        return np.array(self.out[:], dtype=np.int64)

    def tick(self):
        self.clock.value += 1
        self.lib.wt_tick()


def grit(x, f0):
    L = len(x)
    S = np.abs(np.fft.rfft(x * np.blackman(L))) ** 2
    fr = np.fft.rfftfreq(L, 1 / 48000)
    h = fr / f0
    near = np.abs(h - np.round(h)) * f0 < 8
    aud = fr < 20000
    return 10 * np.log10(S[aud & ~near].sum() / S[aud].sum() + 1e-30)


def host_tests(table):
    print("1. moteur sur l'ordinateur (HOST)")
    with tempfile.TemporaryDirectory() as d:
        h = Host(pathlib.Path(d))
        h.load(3, 0x1234, table)
        h.tslot[0] = 3
        frames = len(table) // N

        def note(n, blocks=600):
            h.knobs(note=n, color=64)
            out = [h.block(trig=True)] + [h.block() for _ in range(blocks - 1)]
            return np.concatenate(out)[32 * 40:].astype(float)
        raw = {n: grit(note(n), 440 * 2 ** ((n - 69) / 12)) for n in (60, 84, 96)}
        ticks = 0
        h.knobs(note=60)
        h.block(trig=True)
        while ticks < 200000:
            h.tick()
            ticks += 1
            if ticks % 64 == 0:
                h.block()                       # notre machine reste « vue »
        # copies contre la référence exacte
        ref_spec = np.fft.rfft(np.round(table * 32767).reshape(frames, N), axis=1)
        worst, c_lo = -999.0, None
        cp = np.frombuffer(h.copies.raw[:GW.POOL_BYTES], dtype="<i2")
        off = 0
        hmax = [max(1, int(1024 * 2 ** (-c / 2))) for c in range(GW.NCOPY)]
        for c in range(GW.NCOPY):
            if hmax[c] >= N // 2:
                continue
            c_lo = c if c_lo is None else c_lo
            lg = 6
            while lg < 11 and (1 << lg) < 8 * hmax[c]:
                lg += 1
            m = 1 << lg
            k = min(hmax[c], m // 2 - 1)
            for fr_ in (0, frames // 2, frames - 1):
                s = np.zeros(m // 2 + 1, complex)
                s[:k + 1] = ref_spec[fr_, :k + 1] * m / N
                s[0] = 0                                    # sans le continu
                ref = np.fft.irfft(s, m)
                got = 2 * cp[off + fr_ * m: off + (fr_ + 1) * m].astype(float)     # rangées à mi-niveau
                err = 20 * np.log10(np.sqrt(((got - ref) ** 2).mean()) / (np.sqrt((ref ** 2).mean()) + 1e-9) + 1e-12)
                worst = max(worst, err)
            off += frames * m
        check(worst < -60, f"copies = référence exacte à {worst:.0f} dB près (pire copie / trame)")
        check(bytes(h.copies.raw[off * 2:GW.POOL_BYTES]) == bytes(GW.POOL_BYTES - off * 2),
              f"rien au-delà des copies ({off * 2} o sur {GW.POOL_BYTES})")
        got = {n: grit(note(n), 440 * 2 ** ((n - 69) / 12)) for n in (60, 84, 96)}
        for n in (60, 84, 96):
            print(f"        note {n} : repli {raw[n]:.0f} dB brut -> {got[n]:.0f} dB avec les copies")
        check(got[96] < -50 and got[96] < raw[96] - 20, "Do 7 : repli inaudible avec les copies")
        check(got[60] < -50, "Do 4 : propre")


def prefetch_tests(table):
    """Navigateur : le fichier sous le curseur, préparé d'avance (debounce), puis pris par la piste au YES."""
    print("1b. préparation d'avance (curseur du navigateur), HOST")
    with tempfile.TemporaryDirectory() as d:
        h = Host(pathlib.Path(d))
        lib = h.lib
        hv = lambda n: ctypes.c_uint32.in_dll(lib, n)
        loads = []
        h.load(SLOT, H, table)
        ctypes.c_int32.in_dll(lib, "host_load_slot").value = SLOT
        h.knobs(note=72)
        h.block(trig=True)                      # piste 0 : notre machine, sans table encore

        def cursor(hash_):
            hv("wt_pf_size").value = len(table) * 2
            hv("wt_pf_clock").value = h.clock.value
            hv("wt_pf_hash").value = hash_

        def run(n):
            for i in range(n):
                h.tick()
                if i % 64 == 0:
                    h.block()
        cursor(H)
        run(400)
        check(lib.wt_ready(6) == 0 and not bytes(h.copies.raw[:4096]).strip(b"\0"),
              "curseur posé 270 ms : rien de préparé (debounce)")
        run(100)
        check(lib.wt_hash(6) == H, "après 300 ms : préparation commencée")
        cursor(H + 1)                           # le curseur part : abandon
        run(5)
        check(lib.wt_hash(6) == 0, "curseur déplacé pendant la préparation : abandonnée")
        cursor(H)
        run(12000)
        full = lib.wt_ready(6)
        check(full != 0, f"revenu et resté : copies prêtes ({full:#x})")
        h.tslot[0] = SLOT                       # YES : Model-TG pointe la piste sur le fichier
        run(2)
        check(lib.wt_ready(0) == full and lib.wt_ready(6) == 0, "YES : la piste prend les copies d'avance, sans refaire")


def host_copies(table, ticks=4000):
    """Les copies que fait le moteur HOST pour cette table (octets de la zone de la piste 0)."""
    with tempfile.TemporaryDirectory() as d:
        h = Host(pathlib.Path(d))
        h.load(SLOT, H, table)
        h.tslot[0] = SLOT
        h.knobs()
        h.block(trig=True)
        for i in range(ticks):
            h.tick()
            if i % 64 == 0:
                h.block()
        return h.copies.raw[:GW.POOL_BYTES]


def fw_tests(stock, table):
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

    # démarrage : jsr 0x40000530 -> notre crochet -> wt_boot (retouches de Model-TG) -> boot_extra_hook
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
    uc.emu_start(gs.BOOT_CALL, tg["boot_extra_hook"], count=5_000_000)
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
             sym["tg_np_site"]: b"\x4e\xf9" + be(sym["wt_np"]) + b"\x4e\x71\x4e\x71",
             sym["tg_lh_site"]: b"\x4e\xb9" + be(sym["wt_led"])}
    now = bytes(uc.mem_read(BASE, len(img)))
    diff = [BASE + k for k in range(len(img)) if now[k] != img[k]]
    want = sorted(a + k for a, b in sites.items() for k in range(len(b)) if img[a - BASE + k] != b[k])
    check(all(now[a - BASE:a - BASE + len(b)] == b for a, b in sites.items()) and diff == want,
          f"Model-TG retouché en 3 endroits ({len(diff)} octets), rien d'autre dans l'image")

    # une note : vraie boucle des voix, la table dans la zone de Model-TG
    e = TM.engine(img, end=BASE + len(stock) + tg_tw["append"]["size"], payload=(pay, rt))
    e.uc.mem_map(GW.COPIES_AT, 0x01800000)
    for t in range(1, 6):
        e.uc.mem_write(E.VOICE0 + t * E.VSTRIDE, struct.pack(">II", OFF, OFF))
    pcm = np.clip(np.round(table * 32767), -32768, 32767).astype(">i2").tobytes()
    e.uc.mem_write(PCM, bytes(64) + pcm)
    w32 = lambda a, v: e.uc.mem_write(a, struct.pack(">I", v & 0xffffffff))
    for k, v in ((0, H), (256, PCM), (512, len(table))):
        w32(tg["slot_hash"] + k + 4 * SLOT, v)
    for t in range(6):
        w32(sym["tg_track_slot"] + 4 * t, SLOT if t == 0 else -1)
        w32(sym["tg_track_pend"] + 4 * t, -1)

    def note(n, blocks=300):
        e.set(0, machine=GW.WT_MACH, note=n, pitch=64, color=64, shape=64, sweep=127, contour=0, punch=0, gate=0,
              finetune=64, decay=127)
        return np.concatenate([e.block(1 if b == 0 else 0)[0] for b in range(blocks)])[32 * 40:].astype(float)
    x = note(96)
    raw = grit(x, 440 * 2 ** (27 / 12))
    check(not e.unmapped and np.abs(x).max() > 1e6, f"une note : du son ({np.abs(x).max():.3g}), aucune lecture hors "
                                                     "mémoire")
    clock, worst, n = 1000, 0, [0]

    def count(uc_, a, s_, u):
        n[0] += 1
    hk = e.uc.hook_add(UC_HOOK_CODE, count)
    for i in range(1500):
        clock += 1
        w32(CLOCK, clock)
        n[0] = 0
        e.call(sym["wt_tick"])
        worst = max(worst, n[0])
        if i % 64 == 0:
            e.block(0)
    e.uc.hook_del(hk)
    got = bytes(e.uc.mem_read(GW.COPIES_AT, GW.POOL_BYTES))
    ref = host_copies(table)
    nz = len(ref.rstrip(b"\0"))
    be16 = np.frombuffer(got, ">i2")
    le16 = np.frombuffer(ref, "<i2")
    check(nz > 0 and np.array_equal(be16, le16), f"copies du ColdFire = copies du moteur HOST, octet pour octet "
                                                f"({nz} o)")
    y = note(96)
    g = grit(y, 440 * 2 ** (27 / 12))
    print(f"        Do 7 : repli {raw:.0f} dB brut -> {g:.0f} dB avec les copies (non vérifié)")
    print(f"        une étape des copies : {worst} instructions au pire (~{worst / 250e3:.1f} ms à 250 MHz)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", required=True)
    ap.add_argument("--table", help="une table (.wav) à la place de la table de test")
    a = ap.parse_args()
    table = read_wav(a.table)[:64 * N] if a.table else test_table()
    host_tests(table)
    prefetch_tests(test_table(frames=256))
    fw_tests(T.main_os_from_syx(a.cycles), test_table(frames=8))
    print("TOUT OK" if not FAIL else f"{len(FAIL)} ECHEC(S)")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
