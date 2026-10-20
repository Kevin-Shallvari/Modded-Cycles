#!/usr/bin/env python3
"""Proof of Mod Settings and its USB audio setting, 2CH / 6CH (notes/72, tweaks/model-cycles_OS1.13/12-mod-settings.json).

The OS's own code runs in Unicorn on the MAIN OS of the OS (os.json, plus mod-settings if it is not in it yet), with
its payloads:
  1. Writes: stock bytes, the RUNTIME sites left stock by every tweak of the OS, the other writes of 6ch-usbup made
     whole and identical. With the RUNTIME bytes of 6ch-usbup, the image is the OS with 6ch-usbup instead of
     mod-settings, apart from mod-settings' own code, masks and hooks. Start-up still calls (a2) at 0x400057c6.
  2. Start-up (usb_boot, as 0x400057c6 calls it, the USB set-up 0x40004e40 intercepted): without a record, with a
     damaged record, with 2CH or an unknown value, the set-up is called with the same mode and the image is unchanged;
     with 6CH the 15 changes are made before it, the ring indices cleared.
  3. Menus: the real Config Menu constructor and drawing (fonts, bitmaps and screen of the OS). Nine lines, the eight
     first the same as without the mod, the ninth "Mods" with its icon; the page "Mod Settings": one line "USB Audio",
     its value 2CH. Opening it pushes the page's own view and releases the copy of its shared pointer.
  4. Switch (the line's press function): saved, USB stopped (driver still stock), changes made, USB restarted;
     image = before with the 6ch-usbup bytes, ring indices cleared, interrupt level restored, CACR = the OS's value
     without DCINVA after 1024 cache pushes; value 6CH. Pressed again: back to the image before, byte for byte.
  5. Settings: the record is in the block the OS saves (0x400449b8 -> 0x4008cf3a: data, size), outside its checksum:
     the OS's settings stay valid, and an OS setting changed afterwards leaves the record as it is.
  6. USB stream (the controller model of tools/emu/test_usb_in.py): the memory after switching to 6CH and back to
     2CH streams without a missing, repeated or skipped frame; and the start of a 6CH stream with a ring index left
     from 2CH would queue a slot outside the ring, which is why the switch clears it.

    python3 tools/emu/test_mod_settings.py --cycles model-cycles_OS1.13.syx --syntakt Syntakt_OS1.42.syx \\
        [--seconds 1] [--png folder]
"""
import argparse
import contextlib
import io
import json
import pathlib
import struct
import sys

from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_UNMAPPED
from unicorn import m68k_const as mk

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import build                          # noqa: E402
import test_multiline_browser as MB   # noqa: E402  (png)
import test_sdvintage as T            # noqa: E402
import test_usb_in as U               # noqa: E402

ROOT = HERE.parent.parent
DEV = ROOT / "tweaks" / "model-cycles_OS1.13"
BASE = build.BASE
STOP, STACK = 0x90000100, 0x90010000
CANVAS, BUF, HEAP = 0x92004000, 0x92005000, 0x94000000
REC = 0x404e9b80
CFG_CTOR, CFG_SIZE = 0x4003c134, 0x298
USB_SETUP = 0x40004e40
FAIL = []


def check(ok, msg):
    print(("  ok    " if ok else "  FAIL  ") + msg, flush=True)
    if not ok:
        FAIL.append(msg)
    return ok


class UI:
    """The OS's interface code, function by function: image, payloads, BSS, SRAM, a heap; fonts and the static
    bitmaps built by the OS's own initialisation (0x400e7ccc, 0x400ab7b8); a 128 x 64 screen (Bitmap 0x40070172)."""

    def __init__(self, img):
        uc = self.uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        uc.ctl_set_cpu_model(mk.UC_CPU_M68K_ANY)
        uc.reg_write(mk.UC_M68K_REG_SR, 0x2700)
        uc.mem_map(0x40000000, 0x02400000)
        uc.mem_write(BASE, img)
        uc.mem_map(0x80000000, 0x00020000)
        uc.mem_map(0x90000000, 0x08000000)
        uc.mem_write(STOP, b"\x4e\x71\x4e\x71")
        self.heap, self.bad, self.hooks, self.watch, self.trace, self.count = HEAP, [], {}, {}, [], 0
        uc.hook_add(UC_HOOK_MEM_UNMAPPED, lambda u, a, addr, s, v, d: self.bad.append(addr) or False)
        uc.hook_add(UC_HOOK_CODE, self._hook)
        self.hooks[0x400802e0] = lambda a: self.alloc(a[0])            # operator new
        self.hooks[0x400802ec] = lambda a: 0                           # operator delete
        self.call(0x400e7ccc)
        self.call(0x400ab7b8, 1, 0xffff)
        self.call(0x40070172, CANVAS, 128, 64, BUF, BUF + 0x800)

    def alloc(self, n):
        a, self.heap = self.heap, self.heap + ((n + 15) & ~15)
        self.uc.mem_write(a, bytes(n))
        return a

    def u32(self, a):
        return struct.unpack(">I", self.uc.mem_read(a, 4))[0]

    def w32(self, a, v):
        self.uc.mem_write(a, struct.pack(">I", v & 0xffffffff))

    def cstr(self, a):
        return bytes(self.uc.mem_read(a, 64)).split(b"\0")[0].decode(errors="replace")

    def _hook(self, uc, addr, size, ud):
        self.count += 1
        if addr in self.watch:
            sp = uc.reg_read(mk.UC_M68K_REG_A7)
            self.trace.append((self.watch[addr], struct.unpack(">8I", uc.mem_read(sp + 4, 32))))
        if addr in self.hooks:                                         # intercepted: arguments, then rts
            sp = uc.reg_read(mk.UC_M68K_REG_A7)
            ret = self.hooks[addr](struct.unpack(">8I", uc.mem_read(sp + 4, 32)))
            uc.reg_write(mk.UC_M68K_REG_D0, (ret or 0) & 0xffffffff)
            uc.reg_write(mk.UC_M68K_REG_PC, self.u32(sp))
            uc.reg_write(mk.UC_M68K_REG_A7, sp + 4)

    def call(self, fn, *args, a0=None, count=50_000_000):
        sp = STACK - 0x400
        self.uc.mem_write(sp, struct.pack(">I" + "I" * len(args), STOP, *[a & 0xffffffff for a in args]))
        self.uc.reg_write(mk.UC_M68K_REG_A7, sp)
        if a0 is not None:
            self.uc.reg_write(mk.UC_M68K_REG_A0, a0)
        self.bad.clear()
        self.uc.emu_start(fn, STOP, count=count)
        if self.uc.reg_read(mk.UC_M68K_REG_A7) != sp + 4:
            FAIL.append(f"stack not balanced after {fn:#x}")
        return self.uc.reg_read(mk.UC_M68K_REG_D0)

    def image(self, n):
        return bytes(self.uc.mem_read(BASE, n))

    # --- views ---
    def count_items(self, view):
        return self.call(self.u32(self.u32(view) + 12), view)

    def items(self, view):
        begin = self.u32(view + 4)
        return [self.u32(begin + 8 * i) for i in range(self.count_items(view))]

    def label(self, item):
        out = self.alloc(4)
        self.call(0x40073236, item, a0=out)                            # the line's name (std::string at a0)
        return self.cstr(self.u32(out))

    def draw(self, view):
        self.uc.mem_write(BUF, bytes(0x800))
        self.trace.clear()
        self.call(self.u32(self.u32(view) + 120), view, CANVAS)
        buf = bytes(self.uc.mem_read(BUF, 1024))
        return [[(struct.unpack(">I", buf[8 * x + 4 * (y // 32):8 * x + 4 * (y // 32) + 4])[0] >> (31 - y % 32)) & 1
                 for x in range(128)] for y in range(64)]                # [y][x], y from the bottom (MB.png)

    def move(self, view, n):
        self.call(0x40072524, view, n)                                # the list's own move of the selection


def os_tweaks(extra):
    by_id = {}
    for f in DEV.glob("[0-9]*.json"):
        t = json.loads(f.read_text(encoding="utf-8"))
        by_id[t["id"]] = t
    ids = json.loads((ROOT / "os.json").read_text(encoding="utf-8"))["tweaks"]
    ids = [i for i in ids if i not in extra] + list(extra)
    return by_id, sorted((by_id[i] for i in ids), key=lambda t: t["order"])


def build_img(stock, tweaks, syntakt):
    with contextlib.redirect_stdout(io.StringIO()):
        p, _ = build.apply_writes(stock, tweaks)
        pl, _ = build.build_payload(tweaks, stock, syntakt)
    return bytes(p), bytes(p) + pl


def state_ranges(t):
    """Bytes the mod writes while it runs: its state (.bss of mods.c), and the settings record."""
    s = {k: int(v, 16) for k, v in t["symbols"].items()}
    return [(s["saved"], s["saved"] + 100), (s["page_h"], s["page_h"] + 8), (s["icon_bm"], s["icon_bm"] + 28),
            (s["usb6_on"], s["usb6_on"] + 1)]


def same_outside(a, b, ranges):
    skip = set()
    for lo, hi in ranges:
        skip.update(range(lo - BASE, hi - BASE))
    return [i + BASE for i in range(min(len(a), len(b))) if a[i] != b[i] and i not in skip]


def writes_tests(stock, os_img, six_img, ms, six, sites):
    print("1. writes")
    runtime = {r["off"]: r["len"] for r in ms["runtime"]}
    check(all(os_img[o:o + n] == stock[o:o + n] for o, n in runtime.items()),
          f"the {len(runtime)} RUNTIME sites keep their stock bytes in the OS ({sum(runtime.values())} bytes)")
    six_w = {w["off"]: w for w in six["writes"]}
    shared = [w for w in ms["writes"] if w["off"] in six_w]
    check(all(six_w[w["off"]] == w for w in shared) and len(shared) + len(runtime) == len(six["writes"]),
          f"the {len(shared)} other writes of 6ch-usbup are the same whole writes")
    applied = bytearray(os_img)
    for va, new in sites:
        applied[va - BASE:va - BASE + len(new)] = new
    own = [(w["off"] + BASE, w["off"] + BASE + len(w["new"]) // 2) for w in ms["writes"] if w["off"] not in six_w]
    diff = same_outside(bytes(applied), six_img, own)
    check(not diff, "OS + mod-settings with the RUNTIME bytes of 6ch-usbup = OS + 6ch-usbup, apart from "
                    f"mod-settings' own writes ({len(own)}: code, masks, hooks)" + (f" ; differ: {diff[:6]}" if diff else ""))
    s = {k: int(v, 16) for k, v in ms["symbols"].items()}
    hook = {w["off"] + BASE: bytes.fromhex(w["new"]) for w in ms["writes"]}
    check(hook[0x4003c99a] == struct.pack(">HI", 0x4ef9, s["cfg_tail"]) and
          hook[0x4000576c] == struct.pack(">HI", 0x45f9, s["usb_boot"]) and
          stock[0x400057c6 - BASE:0x400057c8 - BASE] == b"\x4e\x92",
          "hooks: jmp cfg_tail at the end of the Config Menu, lea usb_boot,a2 at start-up, still called by "
          "jsr (a2) at 0x400057c6")


def set_record(u, value=None, damaged=False):
    if value is None:
        u.uc.mem_write(REC, bytes(16))
        return
    rec = bytearray(b"MODS" + bytes([1, value]) + bytes(10))
    rec[15] = (0x5a + sum(rec[4:15])) & 0xff
    if damaged:
        rec[15] ^= 0x10
    u.uc.mem_write(REC, bytes(rec))


def boot_tests(img, ms, sites, n):
    print("2. start-up (usb_boot, called as 0x400057c6 calls the USB set-up)")
    s = {k: int(v, 16) for k, v in ms["symbols"].items()}
    ranges = state_ranges(ms)
    for label, rec in (("no record", None), ("a damaged record", "bad"), ("2CH", 0), ("an unknown value (2)", 2),
                       ("6CH", 1)):
        u = UI(img)
        before = u.image(n)
        set_record(u, 1 if rec == "bad" else rec, damaged=rec == "bad")
        u.w32(0x8000bc94, 12)
        u.w32(0x8000bc90, 15)
        seen = []
        u.hooks[USB_SETUP] = lambda a: seen.append((a[0], all(bytes(u.uc.mem_read(va, len(nw))) == nw
                                                               for va, nw in sites), u.count))
        u.count = 0
        u.call(s["usb_boot"], 5)
        after = u.image(n)
        if rec == 1:
            expect = bytearray(before)
            for va, nw in sites:
                expect[va - BASE:va - BASE + len(nw)] = nw
            diff = same_outside(after, bytes(expect), ranges)
            check(seen and seen[0][:2] == (5, True) and not diff and u.u32(0x8000bc94) == 0 and
                  u.u32(0x8000bc90) == 0,
                  f"{label}: the 15 changes made before the USB set-up, called once with the mode (5); ring "
                  "indices cleared; nothing else changed")
        else:
            diff = same_outside(after, before, [])
            check(len(seen) == 1 and seen[0][:2] == (5, False) and not diff and u.u32(0x8000bc94) == 12,
                  f"{label}: USB set-up called once with the mode (5), image and ring indices unchanged, "
                  f"{seen[0][2] if seen else '?'} instructions before it")


def menu_tests(img, os_img_without, ms, png):
    print("3. menus (the real Config Menu constructor and drawing)")
    s = {k: int(v, 16) for k, v in ms["symbols"].items()}
    ref = UI(os_img_without)
    rcfg = ref.alloc(CFG_SIZE)
    ref.call(CFG_CTOR, rcfg)
    ref_labels = [ref.label(i) for i in ref.items(rcfg)]
    u = UI(img)
    cfg = u.alloc(CFG_SIZE)
    u.call(CFG_CTOR, cfg)
    items = u.items(cfg)
    labels = [u.label(i) for i in items]
    check(len(ref_labels) == 8 and labels[:8] == ref_labels and labels[8:] == ["Mods"],
          f"Config Menu: {', '.join(labels)} (without the mod: {len(ref_labels)} lines, the same eight)")
    u.watch = {0x40071da4: "icon", 0x40071c10: "value"}
    u.move(cfg, 8)
    shots = [u.draw(cfg)]
    icons = [a for name, a in u.trace if name == "icon"]
    check(not u.bad and any(a[1] == s["icon_bm"] and a[2] == 0x60 for a in icons) and
          u.u32(s["icon_bm"] + 0x10) == s["ICON_MODS"] and u.u32(s["icon_bm"] + 0x14) == 0x4016e980,
          "line 9: its icon drawn under the label (a Bitmap: our image, the kept copy of the 31 x 22 masks)")
    page = u.u32(s["page_h"]) - 56
    plabels = [u.label(i) for i in u.items(page)]
    shots.append(u.draw(page))
    title = u.cstr(u.u32(page + 148)), u.cstr(u.u32(page + 556))
    values = [u.cstr(a[7]) for name, a in u.trace if name == "value"]
    check(plabels == ["USB Audio"] and values == ["2CH"] and title == ("Mod", "Settings"),
          f"page {' '.join(title)}: lines {plabels}, value {values}")
    pushed = []
    u.hooks[0x40075754] = lambda a: pushed.append((a[0], u.u32(a[1]), u.u32(a[1] + 4)))
    ctrl = u.u32(s["page_h"] + 4)
    uses = u.u32(ctrl + 4)
    st, clo = u.alloc(16), u.alloc(4)
    u.w32(clo, cfg)
    u.w32(st, clo)
    u.call(s["mods_open"], st)
    check(pushed == [(cfg, page + 56, ctrl)] and u.u32(ctrl + 4) == uses,
          f"Mods pressed: the Config Menu pushes the page's view ({page + 56:#x}); the copy of the shared pointer is "
          f"released (use count {uses})")
    return u, cfg, page, shots


def switch_tests(u, page, ms, sites, n, shots):
    print("4. switch (LEVEL/DATA pressed on USB Audio)")
    s = {k: int(v, 16) for k, v in ms["symbols"].items()}
    ranges = state_ranges(ms)
    log = []
    sites_new = lambda: all(bytes(u.uc.mem_read(va, len(nw))) == nw for va, nw in sites)   # noqa: E731
    sites_any = lambda: any(bytes(u.uc.mem_read(va, len(nw))) == nw for va, nw in sites)   # noqa: E731
    u.hooks[0x400449b8] = lambda a: log.append("save")
    u.hooks[0x40004d9a] = lambda a: log.append(("stop", sites_any()))
    u.hooks[0x40004db4] = lambda a: log.append(("restart", sites_new()))
    pushes = []
    cache_loop = s["cache_sync"] + 4                                # the set and way loop
    u.uc.hook_add(UC_HOOK_CODE, lambda uc, a, sz, d: pushes.append(a), begin=cache_loop, end=cache_loop + 0x14)
    lines = []
    u.watch = {0x40071c10: "value", s["cache_push"]: "line"}
    st, clo = u.alloc(16), u.alloc(4)
    u.w32(clo, page)
    u.w32(st, clo)
    before = u.image(n)
    u.w32(0x8000bc94, 12)
    u.w32(0x8000bc90, 15)
    u.uc.reg_write(mk.UC_M68K_REG_SR, 0x2000)
    u.uc.reg_write(mk.UC_M68K_REG_CR_CACR, 0xa50ce100)
    u.call(s["usb_press"], st)
    after = u.image(n)
    expect = bytearray(before)
    for va, nw in sites:
        expect[va - BASE:va - BASE + len(nw)] = nw
    diff = same_outside(after, bytes(expect), ranges)
    rec = bytes(u.uc.mem_read(REC, 16))
    cpush = sum(1 for a in pushes if u.uc.mem_read(a, 2) == b"\xf4\xe8")
    lines = sorted({a[0] for name, a in u.trace if name == "line"})
    want = sorted({va for va, nw in sites} | {va + len(nw) - 1 for va, nw in sites})
    check(log == ["save", ("stop", False), ("restart", True)],
          "order: settings saved, USB stopped with the stock driver, changes made, USB restarted")
    check(not diff and u.u32(0x8000bc94) == 0 and u.u32(0x8000bc90) == 0,
          "6CH: the image is the one before with the 6ch-usbup bytes, nothing else; ring indices cleared" +
          (f" ; differ: {[hex(x) for x in diff[:6]]}" if diff else ""))
    check(rec[:6] == b"MODS\x01\x01" and rec[15] == (0x5a + sum(rec[4:15])) & 0xff,
          f"record: {rec.hex()} (MODS, version 1, USB 6CH, check byte)")
    check(u.uc.reg_read(mk.UC_M68K_REG_SR) & 0x0700 == 0 and lines == want and
          u.uc.reg_read(mk.UC_M68K_REG_CR_CACR) == 0xa40ce100 and cpush == 1024,
          f"interrupt level restored; cache pushed at the first and last byte of each site ({len(lines)} addresses), "
          f"then over {cpush} sets and ways (256 x 4), then CACR = 0xa40ce100 (the OS's 0xa50ce100 without DCINVA)")
    shots.append(u.draw(page))
    values = [u.cstr(a[7]) for name, a in u.trace if name == "value"]
    check(values == ["6CH"], f"value shown: {values}")
    log.clear()
    u.call(s["usb_press"], st)
    back = u.image(n)
    diff = same_outside(back, before, ranges)
    rec = bytes(u.uc.mem_read(REC, 16))
    check(log == ["save", ("stop", True), ("restart", False)] and not diff and rec[5] == 0,
          "pressed again: saved 2CH, USB stopped, the driver's bytes put back (the image before, byte for byte), "
          "USB restarted" + (f" ; differ: {[hex(x) for x in diff[:6]]}" if diff else ""))
    ok = True
    for k in range(6):
        u.call(s["usb_press"], st)
        ok &= not same_outside(u.image(n), bytes(expect) if k % 2 == 0 else before, ranges)
    check(ok, "six more presses: 6CH, 2CH, ... each time the same two images")
    return after, back


def settings_tests(img, ms):
    print("5. settings")
    s = {k: int(v, 16) for k, v in ms["symbols"].items()}
    u = UI(img)
    saved = []
    u.hooks[0x400d0a10] = lambda a: 0x91000000
    u.hooks[0x4008cf3a] = lambda a: saved.append((u.u32(a[1] + 4), u.u32(a[1] + 8)))
    u.hooks[0x40004d9a] = lambda a: 0
    u.hooks[0x40004db4] = lambda a: 0
    u.call(0x400ddef2)                                            # static set-up of the settings' storage
    u.call(0x400449ce)                                            # the OS's default settings (valid block)
    ok_before = u.call(0x40044b40) & 0xff
    st, clo = u.alloc(16), u.alloc(4)
    u.w32(clo, 0)
    u.w32(st, clo)
    u.hooks[0x40076082] = lambda a: 0
    saved.clear()
    u.call(s["usb_press"], st)
    rec = bytes(u.uc.mem_read(REC, 16))
    inside = saved and saved[-1][0] <= REC and REC + 16 <= saved[-1][0] + saved[-1][1]
    ok_after = u.call(0x40044b40) & 0xff
    check(ok_before == 1 and ok_after == 1 and inside,
          f"the record ({REC:#x}, 16 bytes) is in the block the OS saves ({saved[-1][0]:#x}, {saved[-1][1]} bytes, "
          "flash 0x78000); the OS's settings stay valid (0x40044b40)" if saved else "no save seen")
    u.call(0x40044e74, 3)                                         # an OS setting changed (copy, checksum, save)
    check(bytes(u.uc.mem_read(REC, 16)) == rec and u.call(s["mods_get"], 0) == 1,
          "an OS setting changed afterwards: the record is unchanged, still 6CH")


def stream_tests(stock, ms, after, back, seconds):
    print(f"6. USB stream after switching (controller model of test_usb_in.py, {seconds:g} s per run)")
    tw = {w["off"] + BASE: w for w in ms["writes"]}
    hooks = {"isr": int(tw[0x40058ca0]["new"][4:], 16), "end": int(tw[0x40059392]["new"][4:], 16)}
    n = len(stock)
    for label, img, ch, ring in (("6CH", after[:n], 6, 9), ("back to 2CH", back[:n], 2, 16)):
        res = U.summary(U.scenario(img, ch, seconds, hooks, starts=(20.0, 20.33), ppms=(-100, 100)))
        for name, (bad, cnt, d, lo, hi) in res.items():
            check(bad == 0 and lo >= 1, f"{label}, {name}: {cnt - bad}/{cnt} runs without a defect, queue {lo}..{hi} "
                                        f"of {ring}")
    for idx in (12, 0):
        usb = U.Usb(after[:n], 6, hooks)
        usb.w32(0x8000bc94, idx)
        usb.call(U.START, 1)
        bufs = [usb.r32(d + 8) for d in usb.queue]
        out = [b for b in bufs if not 0x80009800 <= b < 0x80009800 + 9 * 168]
        if idx:
            check(bufs and bufs[0] == 0x80009800 + idx * 168 and out,
                  f"6CH stream started with index {idx} left from 2CH: slot {bufs[0]:#x} outside the ring "
                  f"(0x80009800..{0x80009800 + 9 * 168:#x}): the switch must clear it")
        else:
            check(len(bufs) == 8 and not out, f"index cleared: the {len(bufs)} slots primed are in the ring")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycles", required=True)
    ap.add_argument("--syntakt", required=True, help="Syntakt_OS1.42.syx (or 1.41), for the OS's Syntakt engines")
    ap.add_argument("--seconds", type=float, default=1, help="length of each USB stream run")
    ap.add_argument("--png", help="folder for screen pictures")
    args = ap.parse_args()
    stock = T.main_os_from_syx(args.cycles)
    by_id, tweaks = os_tweaks(["mod-settings"])
    ms, six = by_id["mod-settings"], by_id["6ch-usbup"]
    import gen_mod_settings as G                                   # noqa: E402
    sites, _ = G.split_six(stock)
    os_sec, img = build_img(stock, tweaks, args.syntakt)
    without = [t for t in tweaks if t["id"] != "mod-settings"]
    six_sec, _ = build_img(stock, without + [six], args.syntakt)
    _, img_without = build_img(stock, without, args.syntakt)
    print(f"firmware: {', '.join(t['id'] for t in tweaks)}")
    n = len(stock)
    writes_tests(stock, os_sec, six_sec, ms, six, sites)
    boot_tests(img, ms, sites, n)
    u, cfg, page, shots = menu_tests(img, img_without, ms, args.png)
    after, back = switch_tests(u, page, ms, sites, n, shots)
    settings_tests(img, ms)
    stream_tests(stock, ms, after, back, args.seconds)
    if args.png:
        out = pathlib.Path(args.png)
        out.mkdir(parents=True, exist_ok=True)
        MB.png(out / "mod-settings.png", shots, scale=4)
        print(f"  pictures: {out / 'mod-settings.png'}")
    print("FAILED: " + "; ".join(FAIL) if FAIL else "all good")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
