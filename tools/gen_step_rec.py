#!/usr/bin/env python3
"""Writes tweaks/model-cycles_OS1.13/45-step-rec.json: step record, notes entered one step at a time with the
sequencer stopped (notes/73).

tools/machines/step_rec/: step_rec.c (step record) and step_rec_hooks.S (the hooks), linked by step_rec.ld into freed
sprite masks (tools/sprites.py); its variables, apart from sr_active, live in the free hole above the OS's BSS
(notes/56 §3.5.2). The hooks on the OS are HOOKS below; every write carries its stock bytes, checked on the official
MAIN OS.

    python3 tools/gen_step_rec.py --cycles model-cycles_OS1.13.syx [--check]
"""
import argparse
import json
import pathlib
import struct
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "emu"))

import build                       # noqa: E402
import gen_sdvintage_exact as gx   # noqa: E402
import sprites                     # noqa: E402
import test_sdvintage as T         # noqa: E402

SRC = HERE / "machines" / "step_rec"
DEV = HERE.parent / "tweaks" / "model-cycles_OS1.13"
OUT = DEV / "45-step-rec.json"
BASE = gx.BASE
# sections of step_rec.ld: freed mask -> size (47x47 freed by chord-keys' removal; 48x22 free on every branch)
CAVES = {
    ".cave_a": (0x40182b38, 376),
    ".cave_b": (0x40182e28, 376),
    ".cave_c": (0x4018cd48, 376),
    ".cave_d": (0x4018d1b8, 376),
    ".cave_e": (0x4018d4a8, 376),
    ".cave_f": (0x4018a608, 192),
    ".cave_g": (0x4018d798, 192),
    ".cave_h": (0x4018f80c, 192),
    ".cave_i": (0x40190184, 192),
}
RAM = (0x4233e800, 0x4233e900)                  # variables (.ram of step_rec.ld), in 0x423380b0..0x4233efff
# (address, stock bytes, symbol, opcode, role)
HOOKS = (
    (0x400243d6, "700ab084673e", "sr_key", 0x4ef9,
     "transport keys (0x4002439a): moveq #10,d0 ; cmp.l d4,d0 ; beq.s -> jmp sr_key (REC, PLAY, STOP)"),
    (0x4000721c, "4eb94006ba76", "sr_on", 0x4eb9,
     "note played, message to the interface (0x40007000): jsr 0x4006ba76 (live record?) -> jsr sr_on"),
    (0x40007120, "4eb94006ba76", "sr_off", 0x4eb9,
     "note released, message to the interface (0x40007000): jsr 0x4006ba76 (live record?) -> jsr sr_off"),
    (0x4000bae0, "204031842a14", "sr_set", 0x4eb9,
     "setter of a sound word (0x4000ba7a): movea.l d0,a0 ; move.w d4,20(a0,d2.l*2) -> jsr sr_set"),
    (0x40006a76, "4eb940076ca2", "sr_leds", 0x4eb9,
     "frame of the lights (0x40006a4a): jsr 0x40076ca2 (the views' lights) -> jsr sr_leds"),
    (0x400081e4, "4eb940082464", "sr_tick", 0x4eb9,
     "interface tick, 30 Hz (message 5): jsr 0x40082464 (rts) -> jsr sr_tick"),
)
SYMBOLS = ("sr_active", "cur", "len", "nheld", "ntouch", "touched", "sound", "vc", "sr_key", "sr_on", "sr_off",
           "sr_set", "sr_leds", "sr_tick", "sr_transport", "sr_tick_c")   # for tools/emu/test_step_rec.py


def compile_sr():
    """Linked code (ELF): {section: (address, bytes)}, symbols, [(name, address, size)] of every allocated section."""
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        obj, hooks, elf = d / "sr.o", d / "hooks.o", d / "sr.elf"
        gx.run([gx.CROSS + "gcc", *gx.CFLAGS, "-c", str(SRC / "step_rec.c"), "-o", str(obj)])
        gx.run([gx.CROSS + "gcc", "-mcpu=54418", "-c", str(SRC / "step_rec_hooks.S"), "-o", str(hooks)])
        gx.run([gx.CROSS + "ld", "-T", str(SRC / "step_rec.ld"), "--no-warn-rwx-segments", "-o", str(elf), str(hooks),
                str(obj)])
        syms = {}
        for line in gx.run([gx.CROSS + "nm", str(elf)]).splitlines():
            p = line.split()
            if len(p) == 3:
                syms[p[2]] = int(p[0], 16)
        heads = gx.run([gx.CROSS + "objdump", "-h", str(elf)])
        allocated = []
        for line in heads.splitlines():
            p = line.split()
            if len(p) > 3 and p[1].startswith(".") and int(p[2], 16):
                allocated.append((p[1], int(p[3], 16), int(p[2], 16)))
        secs = {}
        for name in CAVES:
            out = d / (name.strip(".") + ".bin")
            gx.run([gx.CROSS + "objcopy", "-O", "binary", "-j", name, str(elf), str(out)])
            secs[name] = (int(heads.split(name)[1].split()[2], 16), out.read_bytes())
    for name, vma, size in allocated:
        if name in CAVES:
            continue
        if name != ".ram" or not (RAM[0] <= vma and vma + size <= RAM[1]):
            raise SystemExit(f"!! section {name} ({size} bytes at {vma:#x}) outside the caves and the RAM window")
    return secs, syms, allocated


def build_tweak(stock):
    secs, syms, allocated = compile_sr()
    writes, used = [], {}
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
        writes.append({"off": va - BASE, "old": old_hex, "new": struct.pack(">HI", op, syms[sym]).hex()})
    replay = {"sr_set": "204031842a14"}               # hooks that replay the instructions they replace
    for sym, ins in replay.items():
        code = next(c for n, (addr, c) in secs.items() if addr <= syms[sym] < addr + len(c))
        at = syms[sym] - next(addr for n, (addr, c) in secs.items() if addr <= syms[sym] < addr + len(c))
        if bytes.fromhex(ins[:4]) != code[at:at + 2] or bytes.fromhex(ins[4:]) not in code[at:at + 64]:
            raise SystemExit(f"!! {sym} does not replay {ins}")
    writes.sort(key=lambda w: w["off"])
    ram = next(size for name, _, size in allocated if name == ".ram")
    total = sum(used.values())
    tweak = {
        "id": "step-rec",
        "order": 45,
        "name": "Step record : les notes d'un pattern pas à pas",
        "description": [
            "Séquenceur à l'arrêt, double appui sur REC : step record (popup « Step-rec: ON »). Chaque note jouée",
            "(touches TRIG en chromatique sur la piste active, pads T1-T6 sur leur piste, clavier MIDI) est écrite sur",
            "le pas courant, comme le live rec l'écrit (trig, note, vélocité) ; les notes tenues ensemble vont sur le",
            "même pas, qui avance au relâchement de la dernière. PLAY saute un pas, STOP recule d'un pas, REC quitte ; le",
            "step record s'arrête aussi après le dernier pas de la piste. Le pas courant et sa page clignotent vite, REC",
            "est allumé. Potards tournés avant une note : p-locks sur ce trig et les suivants, le son de la piste revient",
            "à son état d'avant à la sortie.",
            f"Code dans neuf masques de sprites libérés (tools/sprites.py) : {total} o ; {ram} o de variables en",
            f"{RAM[0]:#x}, au-dessus du BSS. Généré par tools/gen_step_rec.py, notes/73.",
        ],
        "device": "Model:Cycles",
        "os": "1.13",
        "section": 3,
        "symbols": {n: f"{syms[n]:#x}" for n in SYMBOLS},
        "writes": writes,
    }
    return tweak, used, ram


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycles", required=True, help="official model-cycles_OS1.13.syx")
    ap.add_argument("--check", action="store_true", help="checks that the committed JSON is up to date")
    args = ap.parse_args()
    stock = T.main_os_from_syx(args.cycles)
    if build.sha(stock) != json.loads((DEV / "device.json").read_text(encoding="utf-8"))["section_sha256"]:
        raise SystemExit("!! not the official MAIN OS 1.13")
    tweak, used, ram = build_tweak(stock)
    build.apply_writes(stock, [tweak])                # the stock bytes match
    text = json.dumps(tweak, indent=1) + "\n"
    print("  " + ", ".join(f"{n} {used[n]}/{CAVES[n][1]}" for n in CAVES) + f" bytes; RAM {ram} bytes")
    if args.check:
        ok = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print(f"  {OUT.name} {'is up to date' if ok else 'DOES NOT MATCH (another GCC?)'}")
        raise SystemExit(0 if ok else 1)
    OUT.write_text(text, encoding="utf-8")
    print(f"  written: {OUT.relative_to(HERE.parent)} ({len(tweak['writes'])} writes)")


if __name__ == "__main__":
    main()
