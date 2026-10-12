#!/usr/bin/env python3
"""Preuve de la machine Wave seule (notes/52, notes/54 ; tweaks/model-cycles_OS1.13/36-wavetable.json).

   1. Convertisseur (tools/wt_convert.py) : la table pre-travailee est bien formee (longueur = F x S_TOTAL, copies
      bornees en bande) et le moteur HOST en joue du son.
   2. Firmware (Unicorn) : demarrage (le crochet seul range la charge utile, la remise a zero du BSS de l'OS suit),
      puis le chargeur, sur le vrai code de l'OS : le navigateur note l'entree du fichier (wt_parse), un appui sur le
      pad lit le fichier (wt_note) par l'API de fichiers de l'OS (simulee : un arbre en memoire) dans le tampon de la
      piste, et pose WT_BASE / WT_COUNT ; un fichier non converti ne joue rien.
   3. Lecture : 6 pistes Wave (6 tables) jouent chacune comme jouee seule, mêlées aux machines d'origine qui ne
      changent pas.
   4. Identite Transfer CYC/SMP (notes/55) sur le vrai code de l'OS : smp_mode = 0 redonne exactement le stock
      (produit 27, « Model Cycles », types inchanges) ; smp_mode = 1 donne le Model:Samples (produit 25, « Model
      Samples », liste sample, requetes sample -> raw, reponses raw -> sample) ; la commande SysEx 0x0F pose le
      drapeau ; la place SysEx 0x0F de l'OS pointe sur notre descripteur.

    python3 tools/emu/test_wavetable.py --cycles model-cycles_OS1.13.syx [--table table.wav]

Environ 6 minutes (le convertisseur et plusieurs firmwares complets en Unicorn).
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
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_UNMAPPED
from unicorn import m68k_const as mk

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import build                        # noqa: E402
import gen_wavetable as GW          # noqa: E402
import mcengine as E                # noqa: E402
import test_sdvintage as T          # noqa: E402
import wt_convert as WC             # noqa: E402

DEV = HERE.parent.parent / "tweaks" / "model-cycles_OS1.13"
BASE = E.BASE
KIT, ACTIVE = GW.KIT, GW.ACTIVE
BUF, BUF_STRIDE = GW.BUF, GW.BUF_STRIDE
OPEN, READ, CLOSE, PARSE_CALL = GW.OPEN, GW.READ, GW.CLOSE, GW.PARSE_CALL
OFF = 9                             # machine hors limites : la voix n'est pas calculee
BWRITE, BREAD = 0x90004000, 0x90005000      # zone d'essai (kit simule, entree de navigateur)
KITPTR = 0x90006000

FAIL = []
N = 2048
D0 = mk.UC_M68K_REG_D0
A7 = mk.UC_M68K_REG_A7
PC = mk.UC_M68K_REG_PC
A0 = mk.UC_M68K_REG_A0


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


def test_table(seed=7, frames=64, n=N):
    """Une table de test : des trames riches (dents de scie et impulsions mêlées), 16 bits."""
    rng = np.random.default_rng(seed)
    t = np.arange(n) / n
    out = []
    for f in range(frames):
        a = f / max(1, frames - 1)
        saw = 1 - 2 * t
        pulse = np.where(t < 0.1 + 0.6 * a, 1.0, -1.0)
        x = (1 - a) * saw + a * pulse + 0.05 * rng.standard_normal(n)
        out.append(x / np.abs(x).max() * 0.9)
    return np.concatenate(out)


def container(data, inode):
    """Le fichier tel que sur le +Drive : en-tete de 64 o (taille a +8), PCM 16 bits gros-boutiens, fin de 16 o."""
    pcm = np.asarray(data, dtype="<i2").astype(">i2").tobytes()
    hdr = bytearray(64)
    struct.pack_into(">I", hdr, 8, 64 + len(pcm) + 16)
    return struct.pack(">IIII", inode, 0, 64 + len(pcm) + 16, 0), bytes(hdr) + pcm + bytes(16)


def converter_tests(table):
    print("1. convertisseur (tools/wt_convert.py)")
    data = WC.bake(table)
    F = len(data) // WC.S_TOTAL
    check(len(data) % WC.S_TOTAL == 0 and F == len(table) // N,
          f"longueur = {F} trames x S_TOTAL ({len(data)} points)")
    ok = True
    for c, lg, off in WC.SHORT_COPIES:
        sub = np.asarray(data[off * F:off * F + F * (1 << lg)]).reshape(F, 1 << lg).astype(float)
        sp = np.abs(np.fft.rfft(sub[0]))
        if sp[WC.hmax(c) + 1:].max() > 0.01 * max(1.0, sp.max()):
            ok = False
    check(ok, f"les {len(WC.SHORT_COPIES)} copies courtes sont bornees en bande (hmax)")
    with tempfile.TemporaryDirectory() as d:
        h = Host(pathlib.Path(d))
        h.load(data)
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
        self.base = (ctypes.c_int32 * 6).in_dll(self.lib, "host_wt_base")
        self.count = (ctypes.c_int32 * 6).in_dll(self.lib, "host_wt_count")
        self.clock = ctypes.c_uint32.in_dll(self.lib, "host_clock")
        self.mem = ctypes.create_string_buffer(4 << 20)
        ctypes.c_void_p.in_dll(self.lib, "host_mem").value = ctypes.addressof(self.mem)
        self.v = ctypes.create_string_buffer(0x31c)
        self.p = ctypes.create_string_buffer(0x40)
        self.out = (ctypes.c_int32 * 32)()
        for t in range(6):
            self.base[t] = 0
            self.count[t] = 0

    def load(self, data):
        ctypes.memmove(ctypes.addressof(self.mem) + 64, np.asarray(data, dtype="<i2").tobytes(), len(data) * 2)
        self.base[0] = 64
        self.count[0] = len(data)

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


class Fw:
    def __init__(self, stock, tweaks):
        p, _ = build.apply_writes(stock, tweaks)
        pl, _ = build.build_payload(tweaks, stock, None)
        self.stock = stock
        self.img = bytes(p) + pl
        self.wt = next(t for t in tweaks if t["id"] == "wavetable")
        self.pay = int(self.wt["append"]["dest"], 16)
        self.runtime = build.payload_runtime(self.wt, stock, None)
        self.sym = {k: int(v, 16) for k, v in self.wt["symbols"].items()}
        self.pack = sum(n for _, n in self.wt["append"]["pack"])

    def boot(self):
        """Le crochet de demarrage, execute pour de vrai : au debut de la remise a zero du BSS (0x400004b2), jusqu'a
        son retour. Renvoie le Uc (charge utile reconstituee, tampons mappes) pour l'essai du chargeur."""
        uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        uc.ctl_set_cpu_model(mk.UC_CPU_M68K_ANY)
        uc.mem_map(0x40000000, 0x02400000)
        uc.mem_write(BASE, self.img)
        uc.mem_map(self.pay, 0x00100000)
        uc.mem_write(self.pay, b"\xa5" * 0x00100000)
        uc.mem_map(BUF, 0x02000000)
        uc.mem_write(BUF, b"\xa5" * 0x02000000)
        uc.mem_map(0x80000000, 0x00010000)
        sram = bytearray(0x10000)
        for lo, hi, d in GW.gs.CY_SRAM_INIT:
            sram[d - 0x80000000:d - 0x80000000 + hi - lo] = self.img[lo - BASE:hi - BASE]
        uc.mem_write(0x80000000, bytes(sram))
        uc.mem_map(0x90000000, 0x00020000)
        uc.mem_write(E.STOP, b"\x4e\x71\x4e\x71")
        bad = []
        uc.hook_add(UC_HOOK_MEM_UNMAPPED, lambda u, a, addr, s_, v, d: bad.append(addr) or False)
        keep = {r: 0x11110000 + i for i, r in enumerate((mk.UC_M68K_REG_D2, mk.UC_M68K_REG_D3, mk.UC_M68K_REG_D4,
                                                         mk.UC_M68K_REG_D5, mk.UC_M68K_REG_D6, mk.UC_M68K_REG_D7,
                                                         mk.UC_M68K_REG_A2, mk.UC_M68K_REG_A3, mk.UC_M68K_REG_A4,
                                                         mk.UC_M68K_REG_A5, mk.UC_M68K_REG_A6))}
        for r, v in keep.items():
            uc.reg_write(r, v)
        sp0 = 0x90010000
        uc.mem_write(sp0, struct.pack(">I", E.STOP))
        uc.reg_write(A7, sp0)
        uc.emu_start(0x400004b2, E.STOP, count=100_000_000)
        regs = all(uc.reg_read(r) == v for r, v in keep.items())
        cleared = not any(uc.mem_read(BASE + E.IMAGE_LEN, len(self.img) - E.IMAGE_LEN))
        check(uc.reg_read(PC) == E.STOP and uc.reg_read(A7) == sp0 + 4 and regs and cleared and not bad,
              "0x400004b2 -> notre crochet -> remise a zero du BSS de l'OS (charge utile rangee), retour normal, "
              "d2..d7/a2..a6 intacts")
        got = bytes(uc.mem_read(self.pay, len(self.runtime)))
        check(got == self.runtime,
              f"charge utile reconstituee a {self.pay:#x} : {len(self.runtime)} o, rangee en {self.pack} o dans l'image")
        return uc


def loader(uc, fw, track, handle, cont, inode):
    """Simule le parcours navigateur -> chargeur sur le vrai code de l'OS : l'API de fichiers de l'OS est remplacee
    par un arbre en memoire d'un seul fichier. Renvoie le journal des appels."""
    log = []
    fs = {inode: cont}

    def op_ret(uc_, d0):
        sp = uc_.reg_read(A7)
        ra = struct.unpack(">I", uc_.mem_read(sp, 4))[0]
        uc_.reg_write(A7, sp + 4)
        uc_.reg_write(PC, ra)
        uc_.reg_write(D0, d0 & 0xffffffff)

    def op_open(uc_, a, s, u):
        sp = uc_.reg_read(A7)
        h = struct.unpack(">I", uc_.mem_read(sp + 4, 4))[0]
        st = struct.unpack(">I", uc_.mem_read(sp + 8, 4))[0]
        ino = struct.unpack(">I", uc_.mem_read(h, 4))[0]
        log.append(("open", ino))
        if ino not in fs:
            op_ret(uc_, -1)
            return
        uc_.mem_write(st, struct.pack(">IIII", ino, 0, 0, 1))
        op_ret(uc_, 1)

    def op_read(uc_, a, s, u):
        sp = uc_.reg_read(A7)
        buf = struct.unpack(">I", uc_.mem_read(sp + 4, 4))[0]
        ln = struct.unpack(">I", uc_.mem_read(sp + 8, 4))[0]
        st = struct.unpack(">I", uc_.mem_read(sp + 12, 4))[0]
        d = fs[struct.unpack(">I", uc_.mem_read(st, 4))[0]]
        o = struct.unpack(">I", uc_.mem_read(st + 4, 4))[0]
        n = min(ln, len(d) - o)
        uc_.mem_write(buf, d[o:o + n])
        uc_.mem_write(st + 4, struct.pack(">I", o + n))
        log.append(("read", n))
        op_ret(uc_, n)

    def op_close(uc_, a, s, u):
        log.append(("close",))
        op_ret(uc_, 0)

    uc.hook_add(UC_HOOK_CODE, op_open, begin=OPEN, end=OPEN)
    uc.hook_add(UC_HOOK_CODE, op_read, begin=READ, end=READ)
    uc.hook_add(UC_HOOK_CODE, op_close, begin=CLOSE, end=CLOSE)
    uc.hook_add(UC_HOOK_CODE, lambda u, a, s, d: op_ret(u, 0), begin=PARSE_CALL, end=PARSE_CALL)

    # kit simule : la borne haute de wt_is_ours, machine = Wave pour toutes les pistes
    uc.mem_write(KIT, struct.pack(">I", KITPTR))
    uc.mem_write(KITPTR, b"\0" * 0x400)
    for t in range(6):
        uc.mem_write(KITPTR + 28 + 100 * t + 0x38, bytes([GW.WT_MACH]))
    uc.mem_write(ACTIVE, struct.pack(">I", track))
    uc.mem_write(BWRITE, handle)

    def call(pc, args, until):
        sp = E.STACK - 0x800
        uc.mem_write(sp, struct.pack(">%dI" % (len(args) + 1), until, *args))
        uc.reg_write(A7, sp)
        uc.reg_write(A0, BREAD)
        uc.emu_start(pc, until, count=20_000_000)

    call(fw.sym["wt_parse"], [BWRITE], E.STOP)
    call(fw.sym["wt_note"], [track], GW.NOTE_CONT)
    return log


def fw_tests(stock, data):
    print("2. firmware (wavetable, Unicorn)")
    fw = Fw(stock, [json.loads((DEV / "36-wavetable.json").read_text(encoding="utf-8"))])
    uc = fw.boot()
    inode = 0x12345678
    handle, cont = container(data, inode)
    log = loader(uc, fw, 0, handle, cont, inode)
    base = struct.unpack(">i", uc.mem_read(fw.sym["wt_base"], 4))[0]
    count = struct.unpack(">i", uc.mem_read(fw.sym["wt_count"], 4))[0]
    got_pcm = bytes(uc.mem_read(BUF + 64, len(data) * 2))
    reads = sum(entry[1] for entry in log if entry[0] == "read")
    check(("open", inode) in log and reads == len(cont) and ("close",) in log,
          f"chargeur : ouvre l'entree, lit {reads} o en {sum(entry[0] == 'read' for entry in log)} morceaux, ferme "
          f"({len(log)} appels)")
    check(base == BUF + 64 and count == len(data) and got_pcm == np.asarray(data, dtype="<i2").astype(">i2").tobytes(),
          f"WT_BASE = {base:#x} (tampon + 64), WT_COUNT = {count} (echantillons), PCM copie a l'octet")
    return fw, uc


def smp_tests(fw, uc):
    """L'identite Transfer sur le vrai code de l'OS : nos accroches (notes/55) sont appelees comme l'OS les appelle."""
    print("3. identite Transfer CYC/SMP (Unicorn)")
    sym, D1, A2, A6 = fw.sym, mk.UC_M68K_REG_D1, mk.UC_M68K_REG_A2, mk.UC_M68K_REG_A6
    MSG, HDR, FRAME, ALLOC, OBJ, E9C = 0x90007000, 0x90007100, 0x90009000, 0x90008000, 0x9000a000, 0x400e9c0a
    uc.mem_write(ALLOC, b"\x4e\x75")
    uc.mem_write(MSG, b"\0" * 32)
    uc.mem_write(HDR, b"\0" * 32)

    def rd(va):
        return struct.unpack(">I", uc.mem_read(va, 4))[0]

    def wr(va, v):
        uc.mem_write(va, struct.pack(">I", v))

    def call(va, args, until, regs=()):
        sp = E.STACK - 0x800
        uc.mem_write(sp, struct.pack(">%dI" % (len(args) + 1), until, *args))
        uc.reg_write(A7, sp)
        for r, v in regs:
            uc.reg_write(r, v)
        uc.emu_start(va, until, count=20_000_000)

    def ret(u):
        sp = u.reg_read(A7)
        u.reg_write(PC, struct.unpack(">I", u.mem_read(sp, 4))[0])
        u.reg_write(A7, sp + 4)

    # a) numero de produit (0x40084c14) : 27 en CYC, 25 en SMP
    for mode, want in ((0, 27), (1, 25)):
        wr(sym["smp_mode"], mode)
        call(sym["smp_id_hook2"], [], 0x40084c1a, [(D1, 0)])
        check(uc.reg_read(D1) == want, f"id_hook2 : smp_mode {mode} -> produit {uc.reg_read(D1)} ({want} attendu)")

    # b) requete (0x4009249c, entre par jsr) : le type sample prend son jumeau raw
    for mode, src, want in ((0, 0x10, 0x10), (0, 0x14, 0x14), (1, 0x10, 0x14), (1, 0x11, 0x15), (1, 0x12, 0x16),
                            (1, 0x20, 0x24), (1, 0x36, 0x37), (1, 0x40, 0x43), (1, 0x14, 0x14)):
        wr(sym["smp_mode"], mode)
        uc.mem_write(MSG, b"\0" * 16)
        uc.mem_write(MSG + 8, bytes([src]))
        call(sym["smp_rpc_type"], [MSG], E.STOP)
        got = uc.mem_read(MSG + 8, 1)[0]
        check(got == want, f"rpc_type : smp_mode {mode}, type {src:#04x} -> {got:#04x} ({want:#04x} attendu)")

    # c) reponse (0x40094c9a, entre par jmp) : le type raw redevient sample (le stock l'ecrit apres, depuis d0)
    for mode, src, want in ((0, 0x94, 0x94), (1, 0x94, 0x90), (1, 0x95, 0x91), (1, 0x96, 0x92), (1, 0xc0, 0xc3),
                            (1, 0xc7, 0xc6), (0, 0x90, 0x90)):
        wr(sym["smp_mode"], mode)
        uc.mem_write(HDR, b"\0" * 16)
        uc.mem_write(HDR + 8, bytes([src]))
        call(sym["smp_rpc_ot"], [], 0x40094ca2, [(A2, HDR)])
        got = uc.reg_read(D0) & 0xff
        check(got == want, f"rpc_ot : smp_mode {mode}, type {src:#04x} -> {got:#04x} ({want:#04x} attendu)")

    # d) la commande SysEx 0x0F pose le drapeau
    for m in (1, 0, 1):
        uc.mem_write(MSG, bytes([0xf0, 0x00, 0x20, 0x3c, 0x0f, 0x00, m, 0xf7]))
        call(sym["smp_trig"], [MSG], E.STOP)
        check(rd(sym["smp_mode"]) == m, f"commande SysEx 0x0F, octet {m} -> smp_mode {rd(sym['smp_mode'])}")

    # e) reponse d'identite (0x40084b8e) : longueur de liste + nom, l'allocateur et le constructeur remplaces
    seen = []

    def alloc(u):
        seen.append(struct.unpack(">I", u.mem_read(u.reg_read(A7) + 4, 4))[0])
        u.reg_write(D0, OBJ)

    h1 = uc.hook_add(UC_HOOK_CODE, lambda u, a, s, d: alloc(u), begin=ALLOC, end=ALLOC)
    h2 = uc.hook_add(UC_HOOK_CODE, lambda u, a, s, d: ret(u), begin=E9C, end=E9C)
    for mode, want_len, want_name in ((0, 0x22, b"Model Cycles"), (1, 0x23, b"Model Samples")):
        wr(sym["smp_mode"], mode)
        seen.clear()
        uc.mem_write(FRAME - 0x200, b"\0" * 0x400)
        call(sym["smp_id_hook"], [], 0x40084bde, [(A6, FRAME), (mk.UC_M68K_REG_A0, ALLOC)])
        name = bytes(uc.mem_read(sym["smp_namebuf"], 16)).split(b"\0")[0]
        check(seen == [want_len] and name == want_name, f"id_hook : smp_mode {mode} -> liste {seen[0] if seen else '?'} "
              f"({want_len} attendu), nom « {name.decode()} » ({want_name.decode()} attendu)")
    uc.hook_del(h1)
    uc.hook_del(h2)

    # f) la place SysEx 0x0F de l'OS pointe sur notre descripteur, et il est bien forme
    desc = sym["smp_desc"]
    sub = rd(desc + 4)
    check(rd(0x40148d08 + 4 * GW.SYSEX_SLOT) == desc, f"table SysEx {GW.SYSEX_SLOT:#x} -> descripteur {desc:#x}")
    check(uc.mem_read(desc, 2) == bytes([GW.SYSEX_SLOT, 0]) and sub == desc + 24
          and rd(desc + 8) == 0 and rd(desc + 12) == 1 and rd(desc + 16) == 0
          and rd(sub) == sym["smp_trig"] and rd(sub + 4) == sym["smp_trig"],
          f"descripteur : commande {GW.SYSEX_SLOT:#x}, sous-table {sub:#x} -> smp_trig")
    check(uc.mem_read(sym["smp_list"], 35) == bytes.fromhex(
        "010203050450525110131112202122233031323640414246535455565758595a5b5c5d"),
        "liste « sample » de 35 octets (celle du Model:Samples, sans la question stereo)")
    check(uc.mem_read(sym["smp_map"], 50) == bytes.fromhex(
        "1014111512162024212522262330333134323536374043414442454647" "0000"),
        "table de renommage : toute la famille sample (0x10..0x46) vers ses jumeaux raw")


def eng(fw, reference=False):
    e = E.Engine(fw.stock) if reference else E.Engine(fw.img, payload=(fw.pay, fw.runtime))
    e.uc.mem_map(BUF, 0x02000000)
    e.uc.mem_write(BUF, b"\0" * 0x02000000)
    return e


def pcm(data):
    return np.asarray(data, dtype="<i2").astype(">i2").tobytes()


def set_table(e, fw, t, data, note, color, decay=127):
    e.uc.mem_write(BUF + 64 + BUF_STRIDE * t, pcm(data))
    e.uc.mem_write(fw.sym["wt_base"] + 4 * t, struct.pack(">i", BUF + BUF_STRIDE * t + 64))
    e.uc.mem_write(fw.sym["wt_count"] + 4 * t, struct.pack(">i", len(data)))
    e.set(t, machine=GW.WT_MACH, note=note, color=color, shape=64, sweep=127, contour=0, punch=0, gate=0,
          finetune=64, decay=decay)


def solo_off(e, keep):
    for t in range(6):
        if t not in keep:
            e.set(t, machine=OFF)


def play(fw, track, data, note, color, blocks, trig_at=(0,), decay=127):
    e = eng(fw)
    set_table(e, fw, track, data, note, color, decay)
    solo_off(e, {track})
    return np.stack([e.block((1 << track) if b in trig_at else 0)[track] for b in range(blocks)]), e


def playback(fw, data):
    print("4. lecture (vraie boucle des voix)")
    e = eng(fw)
    set_table(e, fw, 0, data, 48, 64)
    solo_off(e, {0})
    seen = []
    hk = e.uc.hook_add(UC_HOOK_MEM_READ, lambda u, a, addr, sz, val, d: seen.append(addr))
    y = np.concatenate([e.block(1 if b == 0 else 0)[0] for b in range(160)])
    e.uc.hook_del(hk)
    inside = [a for a in seen if BUF + 64 <= a < BUF + 64 + len(data) * 2]
    check(not e.unmapped and np.abs(y[32 * 40:]).max() > 1e6 and len(inside) > 0,
          f"la table joue par la vraie boucle des voix (crete {np.abs(y[32 * 40:]).max():.3g}), {len(inside)} "
          "lectures dans le fichier, aucune lecture hors memoire")
    yh = play(fw, 0, data, 96, 64, 160)[0].reshape(-1)
    check(np.abs(yh[32 * 40:]).max() > 1e6, f"note aigue (copie courte) joue ({np.abs(yh[32 * 40:]).max():.3g})")
    e2 = eng(fw)
    set_table(e2, fw, 0, data, 48, 64)
    e2.uc.mem_write(fw.sym["wt_count"], struct.pack(">i", len(data) - 1))
    solo_off(e2, {0})
    z = np.concatenate([e2.block(1 if b == 0 else 0)[0] for b in range(80)])
    check(np.abs(z).max() == 0 and not e2.unmapped, "fichier non converti (longueur non multiple de S_TOTAL) : rien")


def six_tracks(fw, data):
    print("5. 6 pistes Wave et machines mêlées")
    tables = [WC.bake(test_table(seed=10 + t, frames=8, n=512)) for t in range(6)]

    def build(silent=()):
        e = eng(fw)
        for t in range(6):
            set_table(e, fw, t, tables[t], 36 + 5 * t, 20 + 15 * t, decay=120)
        for t in silent:
            e.uc.mem_write(fw.sym["wt_count"] + 4 * t, struct.pack(">i", 0))
        return e
    e = build()
    x = np.stack([e.block(0x3f if b in (1, 80) else 0) for b in range(120)])
    ok = not e.unmapped and all(x[:, t].any() for t in range(6))
    for t in (0, 3, 5):                         # une table en moins : seule cette piste se tait
        y = build(silent={t})
        z = np.stack([y.block(0x3f if b in (1, 80) else 0) for b in range(120)])
        ok &= not y.unmapped and not z[:, t].any() and all(np.array_equal(x[:, o], z[:, o]) for o in range(6) if o != t)
    check(ok, "6 pistes Wave (6 tables, 6 reglages) : chaque piste joue seule, son etat (table, position, note, "
              "enveloppe) est independant des autres")

    # melange : piste 0 Wave, piste 2 TONE ; la piste TONE est identique a l'OS d'origine
    e = eng(fw)
    set_table(e, fw, 0, data, 48, 64)
    e.set(2, machine=4, note=60, color=64, shape=64, sweep=64, contour=64, punch=0, gate=0, finetune=64, decay=60)
    solo_off(e, {0, 2})
    ref = eng(fw, reference=True)
    ref.set(2, machine=4, note=60, color=64, shape=64, sweep=64, contour=64, punch=0, gate=0, finetune=64, decay=60)
    solo_off(ref, {2})
    a = np.stack([e.block(0x05 if b in (1, 80) else 0) for b in range(120)])
    b = np.stack([ref.block(0x04 if b in (1, 80) else 0) for b in range(120)])
    check(not e.unmapped and not ref.unmapped and np.array_equal(a[:, 2], b[:, 2]) and a[:, 2].any(),
          "piste TONE mêlée a Wave : identique a l'OS d'origine (les 6 machines d'origine ne changent pas)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycles", required=True, help="model-cycles_OS1.13.syx officiel")
    ap.add_argument("--table", help="une table (.wav) a la place de la table de test")
    a = ap.parse_args()
    stock = T.main_os_from_syx(a.cycles)
    table = read_wav(a.table) if a.table else test_table()
    data = converter_tests(table)
    fw, uc = fw_tests(stock, data)
    smp_tests(fw, uc)
    del uc
    playback(fw, data)
    six_tracks(fw, data)
    print("\n" + ("TOUT OK" if not FAIL else f"{len(FAIL)} ECHEC(S)"))
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
