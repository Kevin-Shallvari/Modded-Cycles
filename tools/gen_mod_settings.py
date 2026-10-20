#!/usr/bin/env python3
"""Writes tweaks/model-cycles_OS1.13/12-mod-settings.json: a Mod Settings page in SETTINGS › CONFIG, and its first
setting, the USB audio output in stereo (2CH, as stock) or six tracks (6CH, the 6ch-usbup mod), notes/72.

tools/machines/mod_settings/: mods.c (settings, USB switch, menus) and mods_hooks.S (hooks and glue), linked by mods.ld
into freed sprite masks (tools/sprites.py). Generated with them (mods_gen.h, not committed):
  - the 6CH changes, read from tweaks/model-cycles_OS1.13/11-6ch-usbup.json: the RUNTIME writes are made in memory by
    the mod, only in 6CH; every other write of 6ch-usbup (the stubs they jump to, and the stereo USB fix it shares with
    Model-TG, notes/35) is written as is, the same whole write as 6ch-usbup and model-tg-st;
  - the icon of the Mods line (ICON below).
The hooks on the OS are HOOKS below; every write carries its stock bytes, checked on the official MAIN OS.

    python3 tools/gen_mod_settings.py --cycles model-cycles_OS1.13.syx [--check]
"""
import argparse
import json
import pathlib
import struct
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "emu"))

import build                       # noqa: E402
import gen_sdvintage_exact as gx   # noqa: E402
import sprites                     # noqa: E402
import test_sdvintage as T         # noqa: E402

SRC = HERE / "machines" / "mod_settings"
DEV = HERE.parent / "tweaks" / "model-cycles_OS1.13"
OUT = DEV / "12-mod-settings.json"
SIX = DEV / "11-6ch-usbup.json"
BASE = gx.BASE
# sections of mods.ld: freed mask -> size (47x47 for code, 48x22 for data; free on every branch on 19/10/2026)
CAVES = {
    ".cave_a": (0x4016b6f8, 376),
    ".cave_b": (0x4016b9e8, 376),
    ".cave_c": (0x40171f30, 376),
    ".cave_d": (0x40172608, 376),
    ".cave_e": (0x40187528, 192),
    ".cave_f": (0x401876a8, 192),
    ".cave_g": (0x40188f98, 192),
    ".cave_h": (0x40179730, 376),
}
# (address, stock bytes, symbol, opcode, role)
HOOKS = (
    (0x4003c99a, "4cee3cfcff98", "cfg_tail", 0x4ef9,
     "end of the Config Menu's constructor (0x4003c134): movem.l -104(fp),d2-d7/a2-a5 -> jmp cfg_tail"),
    (0x4000576c, "45f940004e40", "usb_boot", 0x45f9,
     "start-up (0x400057c6 calls (a2) with the USB mode): lea 0x40004e40,a2 -> lea usb_boot,a2"),
)
# 6ch-usbup writes made at run time, in 6CH only (notes/04, notes/13, notes/35)
RUNTIME = {
    0x4000253b: "USB input ring: 5 slots instead of 16",
    0x40002564: "USB input ring: after the output ring",
    0x400027b3: "start of the output stream: 9 slots instead of 16",
    0x400027d3: "start of the output stream: slots of 168 bytes, 144 sent",
    0x400027e8: "start of the output stream: jmp to the 6-track priming stub",
    0x4000281f: "start of the output stream: 8 slots primed instead of 11",
    0x400029b9: "feed: 9 slots",
    0x400029d2: "feed: slots of 168 bytes",
    0x400029e4: "feed: jmp to the stub of the slot position",
    0x40002a06: "feed: jmp to the 6-track copy",
    0x40002a42: "feed: jmp to the stub that queues 24-byte frames",
    0x40002ceb: "endpoint: MaxPacketLength 168 instead of 56",
    0x4019b2fa: "descriptor: 6 channels",
    0x4019b387: "descriptor: 6 channels",
    0x4019b397: "descriptor: wMaxPacketSize 168",
}
CONFLICTS = ["6ch-multiout", "6ch-usbup"]            # they write the RUNTIME bytes for good
SYMBOLS = ("cfg_tail", "usb_boot", "mods_get", "usb_press", "mods_open", "cache_push", "cache_sync", "saved", "usb6_on",
           "page_h",
           "icon_bm", "ICON_MODS")                                  # for tools/emu/test_mod_settings.py
REC = 0x404e9b80                                      # the settings record (mods.c)
ICON = """
...............................
..........#####................
.........#######...............
.........#######...............
.........#######...............
..........#####................
...........###.................
.....###############...........
.....###############...........
.....###############...........
.....###############...........
.....###############..###......
.....###############.#####.....
.....#####################.....
.....#####################.....
.....#####################.....
.....###############.#####.....
.....###############..###......
.....###############...........
.....###############...........
.....###############...........
...............................
"""


def bitmap(art, w=31, h=22):
    """The OS's Bitmap (0x40070172): a 32-bit word per column, the bottom row in bit 31, the top one in bit 32 - h."""
    rows = [r for r in art.strip().splitlines()]
    if len(rows) != h or any(len(r) != w for r in rows):
        raise SystemExit("!! icon: wrong size")
    return b"".join(struct.pack(">I", sum(1 << (32 - h + y) for y in range(h) if rows[y][x] == "#"))
                    for x in range(w))


def split_six(stock):
    """(runtime sites [(va, new)], static writes) from 6ch-usbup, checked on the stock MAIN OS."""
    six = json.loads(SIX.read_text(encoding="utf-8"))
    sites, static = [], []
    for w in six["writes"]:
        va, old, new = w["off"] + BASE, bytes.fromhex(w["old"]), bytes.fromhex(w["new"])
        if stock[w["off"]:w["off"] + len(old)] != old:
            raise SystemExit(f"!! 6ch-usbup: stock bytes differ at {va:#x}")
        (sites.append((va, new)) if va in RUNTIME else static.append(w))
    if {va for va, _ in sites} != set(RUNTIME):
        raise SystemExit("!! 6ch-usbup: RUNTIME sites missing from 11-6ch-usbup.json")
    return sites, static


def header(sites):
    lines = ["/* Generated by tools/gen_mod_settings.py: the 6CH changes (11-6ch-usbup.json) and the icon. */",
             "struct site { u32 addr; u8 len, at; };",
             f"#define USB6_SITES {len(sites)}",
             f"#define USB6_BYTES {sum(len(n) for _, n in sites)}",
             "static const struct site SITES[USB6_SITES] = {"]
    at = 0
    for va, new in sites:
        lines.append(f"\t{{ {va:#010x}, {len(new)}, {at} }},")
        at += len(new)
    lines.append("};")
    pool = b"".join(n for _, n in sites)
    lines.append("static const u8 NEW6[USB6_BYTES] = { " + ", ".join(f"{b:#04x}" for b in pool) + " };")
    lines.append("static const u8 ICON_MODS[124] = { " + ", ".join(f"{b:#04x}" for b in bitmap(ICON)) + " };")
    return "\n".join(lines) + "\n"


def compile_mods(sites):
    """Linked code (ELF): {section: (address, bytes)}, symbols."""
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        (d / "mods_gen.h").write_text(header(sites), encoding="utf-8")
        obj, hooks, elf = d / "mods.o", d / "hooks.o", d / "mods.elf"
        gx.run([gx.CROSS + "gcc", *gx.CFLAGS, "-I", str(d), "-c", str(SRC / "mods.c"), "-o", str(obj)])
        gx.run([gx.CROSS + "gcc", "-mcpu=54418", "-c", str(SRC / "mods_hooks.S"), "-o", str(hooks)])
        gx.run([gx.CROSS + "ld", "-T", str(SRC / "mods.ld"), "--no-warn-rwx-segments", "-o", str(elf), str(hooks),
                str(obj)])
        syms = {}
        for line in gx.run([gx.CROSS + "nm", str(elf)]).splitlines():
            p = line.split()
            if len(p) == 3:
                syms[p[2]] = int(p[0], 16)
        heads = gx.run([gx.CROSS + "objdump", "-h", str(elf)])
        secs = {}
        for name in CAVES:
            out = d / (name.strip(".") + ".bin")
            gx.run([gx.CROSS + "objcopy", "-O", "binary", "-j", name, str(elf), str(out)])
            secs[name] = (int(heads.split(name)[1].split()[2], 16), out.read_bytes())
        for line in heads.splitlines():                   # nothing left outside the caves
            p = line.split()
            if len(p) > 3 and p[1].startswith(".") and p[1] not in CAVES and int(p[2], 16):
                raise SystemExit(f"!! section {p[1]} outside the caves (mods.ld)")
    return secs, syms


def build_tweak(stock):
    sites, static = split_six(stock)
    secs, syms = compile_mods(sites)
    writes, used = [dict(w) for w in static], {}
    for name, (mask, room) in CAVES.items():
        addr, code = secs[name]
        if addr != mask or len(code) > room:
            raise SystemExit(f"!! {name}: {len(code)} bytes at {addr:#x}, room {room} at {mask:#x}")
        kept = sprites.kept_of(mask)
        if stock[mask - BASE:mask - BASE + room] != stock[kept - BASE:kept - BASE + room]:
            raise SystemExit(f"!! {name}: mask {mask:#x} differs from the kept mask {kept:#x}")
        writes.append({"off": addr - BASE, "old": stock[addr - BASE:addr - BASE + len(code)].hex(), "new": code.hex()})
        writes.append(sprites.redirect_write(mask))
        used[name] = len(code)
    for va, old_hex, sym, op, _ in HOOKS:
        old = bytes.fromhex(old_hex)
        if stock[va - BASE:va - BASE + len(old)] != old:
            raise SystemExit(f"!! unexpected stock bytes at {va:#x}")
        new = struct.pack(">HI", op, syms[sym])
        writes.append({"off": va - BASE, "old": old_hex, "new": new.hex()})
    writes.sort(key=lambda w: w["off"])
    total = sum(used.values())
    tweak = {
        "id": "mod-settings",
        "order": 12,
        "name": "Mod Settings : sortie audio USB 2CH ou 6CH",
        "description": [
            "SETTINGS › CONFIG : une ligne Mods de plus (après Device), qui ouvre la page Mod Settings des réglages des",
            "mods. Premier réglage, USB Audio : 2CH (le mix stéréo, comme d'origine) ou 6CH (les six pistes, comme",
            "6ch-usbup). LEVEL/DATA pressé change le réglage : il est enregistré avec ceux de l'OS (enregistrement de 16 o",
            f"en {REC:#x}, hors de la somme de contrôle de l'OS), puis l'USB est coupé et rebranché, comme pour un",
            "changement de USB mode : l'ordinateur relit les descripteurs.",
            "En 6CH, les 15 modifications de 6ch-usbup au pilote USB et aux descripteurs sont faites en mémoire (au",
            "démarrage, ou au changement de réglage, USB arrêté) ; les octets remplacés sont gardés et remis en 2CH. En 2CH",
            "le pilote est celui de l'OS, octet pour octet. Les stubs de 6ch-usbup et sa correction du flux USB stéréo",
            "(partagée avec Model-TG, notes/35) sont écrits tels quels.",
            f"Code dans huit masques de sprites libérés (tools/sprites.py) : {total} o. Généré par tools/gen_mod_settings.py,",
            "notes/72.",
        ],
        "device": "Model:Cycles",
        "os": "1.13",
        "section": 3,
        "conflicts": CONFLICTS,
        "runtime": [{"off": va - BASE, "len": len(new), "why": RUNTIME[va]} for va, new in sites],
        "symbols": {n: f"{syms[n]:#x}" for n in SYMBOLS},
        "writes": writes,
    }
    return tweak, used


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycles", required=True, help="official model-cycles_OS1.13.syx")
    ap.add_argument("--check", action="store_true", help="checks that the committed JSON is up to date")
    args = ap.parse_args()
    stock = T.main_os_from_syx(args.cycles)
    if build.sha(stock) != json.loads((DEV / "device.json").read_text(encoding="utf-8"))["section_sha256"]:
        raise SystemExit("!! not the official MAIN OS 1.13")
    tweak, used = build_tweak(stock)
    build.apply_writes(stock, [tweak])                # the stock bytes match
    text = json.dumps(tweak, indent=1) + "\n"
    print("  " + ", ".join(f"{n} {used[n]}/{CAVES[n][1]} bytes" for n in CAVES))
    if args.check:
        ok = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print(f"  {OUT.name} {'is up to date' if ok else 'DOES NOT MATCH (another GCC?)'}")
        raise SystemExit(0 if ok else 1)
    OUT.write_text(text, encoding="utf-8")
    print(f"  written: {OUT.relative_to(HERE.parent)} ({len(tweak['writes'])} writes)")


if __name__ == "__main__":
    main()
