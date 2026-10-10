#!/usr/bin/env python3
"""Preuve d'étude (notes/52 §3quater) : navigateur de l'OS bloqué dans /Wavetables sur la piste de notre machine.

Vrai code de l'OS (ouverture 0x400a6c20, fermeture 0x400a40d4, YES 0x4003f91c, touches 0x400a6d5c, dossiers
0x4007d1ca/0x4007cfca...) avec et sans wt_browser.S. Remplacés : les primitives du système de fichiers (un petit
arbre en Python), l'allocateur, et les appels d'affichage.

    .venv/bin/python build/wt-proof/test_wt_browser.py --cycles firmware/model-cycles_OS1.13.syx
"""
import argparse
import pathlib
import struct
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "emu"))

from unicorn import UcError, UC_HOOK_CODE           # noqa: E402
from unicorn import m68k_const as mk                # noqa: E402

import mcengine as E                                # noqa: E402
import test_sdvintage as T                          # noqa: E402

BASE = 0x40000400
CODE, DATA = 0x401f0000, 0x401f0400
FOLDER, ACTIVE, CUR_KIT = 0x40148cb0, 0x40a700c4, 0x40a78888
OPEN, CLOSE, YES, KEYS = 0x400a6c20, 0x400a40d4, 0x4003f91c, 0x400a6d5c
STOP, CALL_SP = 0x40780000, 0x9000e000
FIX = 0x93000000
PM, PMVT, FSD, KIT, EV, CELLS, CLOSEVT, NOP = (FIX + 0x1000 * i for i in range(8))
HEAP = 0x94000000
WT = 7
FAIL = []


def check(ok, msg):
    print(("  ok    " if ok else "  ECHEC ") + msg, flush=True)
    if not ok:
        FAIL.append(msg)


def hooks():
    """Assemble wt_browser.S ; rend (code, données, écritures {adresse: octets})."""
    run = lambda *a: subprocess.run(a, cwd=HERE, check=True, capture_output=True, text=True).stdout
    run("m68k-elf-as", "-march=cfv4e", "-o", "wt.o", "wt_browser.S")
    run("m68k-elf-ld", "-Ttext=0x%x" % CODE, "-Tdata=0x%x" % DATA, "-o", "wt.elf", "wt.o")
    sym = {p[2]: int(p[0], 16) for p in (l.split() for l in run("m68k-elf-nm", "wt.elf").splitlines()) if len(p) == 3}
    run("m68k-elf-objcopy", "-O", "binary", "-j", ".text", "wt.elf", "wt.text")
    run("m68k-elf-objcopy", "-O", "binary", "-j", ".data", "wt.elf", "wt.data")
    jmp = lambda a: b"\x4e\xf9" + struct.pack(">I", a)
    jsr = lambda a: b"\x4e\xb9" + struct.pack(">I", a)
    nop = b"\x4e\x71"
    w = {0x400a6c20: jmp(sym["wt_open"]) + nop, 0x400a40e2: jmp(sym["wt_close"]) + nop,
         0x4003fa52: jmp(sym["wt_yes_up"]) + 2 * nop, 0x400a6f9c: jmp(sym["wt_key_up"]) + 2 * nop,
         0x400a70b0: jsr(sym["wt_home"])}
    return (HERE / "wt.text").read_bytes(), (HERE / "wt.data").read_bytes(), w, sym


class Fs:
    """Arbre de dossiers : inode -> (nom, parent, dossier)."""

    def __init__(self, wavetables=True):
        self.n = {1: ("", 1, True), 2: ("Presets", 1, True), 4: ("kick", 1, False), 5: ("p1", 2, False)}
        if wavetables:
            self.n.update({3: ("Wavetables", 1, True), 6: ("Sub", 3, True), 7: ("wt_a", 3, False),
                           8: ("wt_b", 3, False), 9: ("wt_c", 6, False)})
        self.mkdirs = []

    def path(self, i):
        parts = []
        while i != 1:
            parts.append(self.n[i][0])
            i = self.n[i][1]
        return "/" + "/".join(reversed(parts))

    def find(self, path):
        for i in self.n:
            if self.path(i) == path.rstrip("/") or (i == 1 and path in ("/", "")):
                return i
        return None

    def entries(self, i):
        return [(i, ".", True), (self.n[i][1], "..", True)] + [(k, v[0], v[2]) for k, v in self.n.items()
                                                                if v[1] == i and k != 1]


class Rig:
    def __init__(self, img, fs, machines, active, hk=None):
        self.fs = fs
        e = self.e = E.Engine(img)
        uc = self.uc = e.uc
        uc.mem_map(FIX, 0x02000000)
        uc.mem_map(0x40800000, 0x01800000)          # BSS de l'OS
        if hk:
            uc.mem_write(CODE, hk[0])
            uc.mem_write(DATA, hk[1])
            for a, b in hk[2].items():
                uc.mem_write(a, b)
        self.heap, self.errors, self.closed, self.previews = HEAP, [], 0, []
        cstr = lambda a: bytes(uc.mem_read(a, 256)).split(b"\0")[0].decode()
        fsn = fs

        def dir_open(a):
            i = fsn.find(cstr(a[0]))
            if i is None or not fsn.n[i][2]:
                return 0xffffffff
            self.mem(a[1], struct.pack(">IIII", i, 0, 0, 0))
            return 0

        def mkdir(a):
            p = cstr(a[0]).rstrip("/")
            fsn.mkdirs.append(p)
            par = fsn.find(p.rsplit("/", 1)[0] or "/")
            if fsn.find(p) is not None or par is None:
                return 0xffffffff
            fsn.n[max(fsn.n) + 1] = (p.rsplit("/", 1)[1], par, True)
            return 0

        def readdir(a):
            h = a[0]
            i, pos = self.r32(h), self.r32(h + 4)
            ent = fsn.entries(i)
            if pos >= len(ent):
                return 0
            ino, name, d = ent[pos]
            rec = bytearray(276)
            struct.pack_into(">IH", rec, 0, ino, 1 if d else 2)
            struct.pack_into(">I", rec, 8, i)
            rec[20:20 + len(name)] = name.encode()
            self.mem(a[1], bytes(rec))
            self.w32(h + 4, pos + 1)
            return 1

        def path_of(a):
            self.mem(a[2], fsn.path(a[0]).encode() + b"\0")
            return a[2]

        stubs = {
            0x4007aa78: dir_open, 0x4007ac46: mkdir, 0x4007ab26: readdir,
            0x4007aa66: lambda a: self.w32(a[0] + 4, 0) or 0,
            0x4007ab10: lambda a: self.mem(a[1], struct.pack(">IIII", a[0], 0, 0, 0)) or 0,
            0x4007afd4: path_of,
            0x4007ea32: lambda a: int(a[0] in fsn.n), 0x4007ec30: lambda a: int(a[0] in fsn.n and fsn.n[a[0]][2]),
            0x400802e0: self._new, 0x400802ec: lambda a: 0, 0x40001cc4: lambda a: 0, 0x40001df6: lambda a: 0,
            # ouverture et fermeture : écran, minuterie, pas tenu
            0x4006e6e6: lambda a: 0, 0x400cf9a8: lambda a: FIX + 0x10000, 0x4006b736: lambda a: 0,
            0x4008251c: lambda a: 0, 0x400cf044: lambda a: 0, 0x40081bd6: lambda a: 0,
            0x400a63ac: lambda a: self.previews.append(a[1]) or 0,
            0x40076082: lambda a: 0, 0x4006ed84: lambda a: 0,
            # affichage de la liste (méthodes du navigateur)
            0x400727b8: lambda a: 0, 0x4003f5c6: lambda a: 0, 0x400a3f88: lambda a: 0,
            NOP: self._closed,
        }
        for addr, fn in stubs.items():
            self.stub(addr, fn)

        def top_view(uc, a_, size, ud):            # vue du dessus = ce navigateur (touche tenue, 0x400a7028)
            a0 = uc.reg_read(mk.UC_M68K_REG_A0)
            self.mem(a0, struct.pack(">II", PM + 56, FIX + 0x12000))
            self.w32(FIX + 0x12004, 1)
            sp = uc.reg_read(mk.UC_M68K_REG_A7)
            uc.reg_write(mk.UC_M68K_REG_PC, struct.unpack(">I", uc.mem_read(sp, 4))[0])
            uc.reg_write(mk.UC_M68K_REG_A7, sp + 4)
        uc.hook_add(UC_HOOK_CODE, top_view, begin=0x40076b7e, end=0x40076b7e)
        # navigateur : vtable de l'OS en RAM ; +56 : la vue que la touche 12 ferme (vt[40])
        uc.mem_write(PMVT, bytes(uc.mem_read(0x401183ec, 0x100)))
        self.w32(PM, PMVT)
        self.w32(PM + 56, CLOSEVT)
        self.w32(CLOSEVT + 40, NOP)
        # dossier : vrai constructeur, sur le dossier retenu
        self.w32(FOLDER, 2)
        self.call(0x4007d26c, FSD, 2)
        for k in (632, 640):
            self.w32(PM + k, FSD)
        self.w32(CELLS + 4, PM)                    # arg -> cellule -> navigateur
        self.w32(CELLS, CELLS + 4)
        self.w32(CUR_KIT, KIT)
        for t, m in enumerate(machines):
            self.mem(KIT + 28 + 100 * t + 38, bytes([m]))
        self.w32(ACTIVE, active)

    # -- mémoire et appels --
    def w32(self, a, v):
        self.uc.mem_write(a, struct.pack(">I", v & 0xffffffff))

    def r32(self, a):
        return struct.unpack(">I", self.uc.mem_read(a, 4))[0]

    def mem(self, a, b):
        self.uc.mem_write(a, b)

    def _new(self, a):
        p, n = self.heap, (a[0] + 15) & ~15
        self.heap += n
        self.uc.mem_write(p, bytes(n))
        return p

    def _closed(self, a):
        self.closed += 1
        return 1

    def stub(self, addr, fn):
        def hook(uc, a, size, ud):
            sp = uc.reg_read(mk.UC_M68K_REG_A7)
            r = fn(struct.unpack(">6I", uc.mem_read(sp + 4, 24)))
            uc.reg_write(mk.UC_M68K_REG_D0, (r or 0) & 0xffffffff)
            uc.reg_write(mk.UC_M68K_REG_PC, struct.unpack(">I", uc.mem_read(sp, 4))[0])
            uc.reg_write(mk.UC_M68K_REG_A7, sp + 4)
        if addr == NOP:
            self.mem(NOP, b"\x4e\x75")
        self.uc.hook_add(UC_HOOK_CODE, hook, begin=addr, end=addr)

    def call(self, fn, *args):
        uc = self.uc
        frame = struct.pack(">I", STOP) + b"".join(struct.pack(">I", a & 0xffffffff) for a in args)
        uc.reg_write(mk.UC_M68K_REG_SR, 0x2000)
        uc.mem_write(CALL_SP - len(frame), frame)
        uc.reg_write(mk.UC_M68K_REG_A7, CALL_SP - len(frame))
        try:
            uc.emu_start(fn, STOP, count=3_000_000)
        except UcError as ex:
            self.errors.append((hex(fn), hex(uc.reg_read(mk.UC_M68K_REG_PC)), str(ex)))
        if uc.reg_read(mk.UC_M68K_REG_PC) != STOP:
            self.errors.append((hex(fn), hex(uc.reg_read(mk.UC_M68K_REG_PC)), "pas revenu"))
        return uc.reg_read(mk.UC_M68K_REG_D0)

    # -- gestes --
    def open(self):
        self.call(OPEN, CELLS)

    def close(self):
        self.call(CLOSE, CELLS)

    def yes(self, name):
        i = self.names().index(name)
        self.w32(FIX + 0x11000, PM)
        self.w32(FIX + 0x11004, i)
        self.w32(FIX + 0x11010, FIX + 0x11000)
        self.call(YES, FIX + 0x11010)

    def key12(self, long=False):
        self.mem(EV, bytes(32))
        self.w32(EV + 12, 12)
        self.w32(EV + 16, 0x20 if long else 0x01)
        return self.call(KEYS, PM, EV) & 0xff

    # -- état --
    def where(self):
        return self.fs.path(self.r32(FSD + 272))

    def names(self):
        a, b = self.r32(FSD + 260), self.r32(FSD + 264)
        return [bytes(self.uc.mem_read(self.r32(p) + 20, 32)).split(b"\0")[0].decode() for p in range(a, b, 8)]

    def ok(self):
        return not self.errors and not self.e.unmapped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", required=True)
    a = ap.parse_args()
    stock = T.main_os_from_syx(a.cycles)
    hk = hooks()
    img = bytearray(stock)
    for addr, b in hk[2].items():
        img[addr - BASE:addr - BASE + len(b)] = b
    img = bytes(img)
    print(f"code {len(hk[0])} o + données {len(hk[1])} o ; accroches : "
          + ", ".join(f"{k:#x} ({len(v)} o)" for k, v in hk[2].items()))
    K = [0, WT, 0, 0, 0, 0]

    def rig(fs=None, active=1, hooked=True):
        return Rig(img if hooked else stock, fs or Fs(), K, active, hk if hooked else None)

    print("1. autre piste (Kick)")
    for hooked in (False, True):
        r = rig(active=0, hooked=hooked)
        r.open()
        check(r.ok() and r.where() == "/Presets" and r.r32(FOLDER) == 2,
              f"{'retouché' if hooked else 'origine'} : s'ouvre dans le dossier retenu ({r.where()}) {r.errors[:1]}")

    print("2. notre piste : ouverture, sous-dossier, remontées")
    r = rig()
    r.open()
    check(r.ok() and r.where() == "/Wavetables" and r.names() == ["..", "Sub", "wt_a", "wt_b"],
          f"s'ouvre dans /Wavetables {r.names()} {r.errors[:1]}")
    check(r.previews == [0], f"curseur en haut, entrée 0 écoutée ({r.previews})")
    r.yes("Sub")
    check(r.where() == "/Wavetables/Sub" and r.names() == ["..", "wt_c"], f"YES sur Sub : {r.where()} {r.names()}")
    r.yes("..")
    check(r.where() == "/Wavetables", f"YES sur .. depuis Sub : {r.where()}")
    r.yes("..")
    check(r.ok() and r.where() == "/Wavetables", f"YES sur .. depuis /Wavetables : refusé ({r.where()})")
    r.yes("Sub")
    r.key12()
    check(r.where() == "/Wavetables" and r.closed == 0, f"touche 12 depuis Sub : remonte ({r.where()})")
    res = r.key12()
    check(r.where() == "/Wavetables" and r.closed == 1, f"touche 12 dans /Wavetables : ferme ({r.where()}, {res})")
    r.yes("Sub")
    r.key12(long=True)
    check(r.where() == "/Wavetables", f"touche 12 tenue depuis Sub : retour à /Wavetables ({r.where()})")
    r.yes("Sub")
    r.close()
    check(r.ok() and r.r32(FOLDER) == 2, f"fermeture : dossier retenu rendu (/Presets) {r.errors[:1]}")
    r.w32(ACTIVE, 0)
    r.open()
    check(r.where() == "/Presets", f"puis Kick : /Presets ({r.where()})")

    print("3. fermeture manquée")
    r = rig()
    r.open()
    r.w32(ACTIVE, 0)
    r.open()
    check(r.ok() and r.where() == "/Presets", f"ouverture suivante sur Kick : /Presets ({r.where()})")

    print("4. dossier absent")
    fs = Fs(wavetables=False)
    r = rig(fs=fs)
    r.open()
    check(r.ok() and fs.mkdirs == ["/Wavetables"] and r.where() == "/Wavetables" and r.names() == [".."],
          f"créé et ouvert vide ({fs.mkdirs}, {r.where()}, {r.names()})")
    r.close()
    r.open()
    check(fs.mkdirs == ["/Wavetables"], "pas recréé à l'ouverture suivante")

    print("5. origine, pour comparer")
    r = rig(hooked=False)
    r.open()
    check(r.where() == "/Presets", f"notre piste : dossier retenu ({r.where()})")
    r.w32(FOLDER, 3)
    r.open()
    r.yes("..")
    check(r.where() == "/", f"YES sur .. depuis /Wavetables : remonte ({r.where()})")
    r.w32(FOLDER, 3)
    r.open()
    r.key12()
    check(r.where() == "/" and r.closed == 0, f"touche 12 : remonte ({r.where()})")
    r.w32(FOLDER, 6)
    r.open()
    r.key12(long=True)
    check(r.ok() and r.where() == "/", f"touche 12 tenue : racine ({r.where()}) {r.errors[:1]}")
    print("TOUT OK" if not FAIL else f"{len(FAIL)} ECHEC(S)")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
