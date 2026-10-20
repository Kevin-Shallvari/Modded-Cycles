#!/usr/bin/env python3
"""Explore the Model:Cycles OS 1.13 MAIN OS (section 3) without leaving the repo's rules.

Reads the user's official .syx (never committed), checks it against tweaks/model-cycles_OS1.13/device.json, and caches
the decompressed section 3 under build/ (git-ignored). Standard library only, plus m68k binutils for `dis`.

    mainos.py extract firmware/model-cycles_OS1.13.syx [--with arp,trig-hold]   # -> build/mainos[...].bin
    mainos.py dis   IMAGE 0x40022382 [0x40022400 | +0x80]                        # objdump, ColdFire ISA_C + EMAC
    mainos.py xrefs IMAGE 0x40072490 [--pcrel]                                   # who calls / points to an address
    mainos.py strings IMAGE 'TEMPO|BPM' [--xrefs]                                # UI strings and who uses them
    mainos.py bytes IMAGE 0x4002249c 6                                           # raw bytes (for `old` checks)
    mainos.py va 0x2209c   |   mainos.py off 0x4002249c                          # section-3 offset <-> VA

IMAGE is a .syx (extracted on the fly) or a .bin written by `extract`. Addresses are OS 1.13 VAs.
"""
import argparse
import hashlib
import json
import pathlib
import re
import shutil
import struct
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
TOOLS = ROOT / "tools"
DEV = ROOT / "tweaks" / "model-cycles_OS1.13"
CACHE = ROOT / "build"
BASE = 0x40000400                      # VA of the first byte of section 3 (tools/build.py BASE)
sys.path.insert(0, str(TOOLS))


def num(s):
    return int(s, 0)


def stock_sha():
    return json.loads((DEV / "device.json").read_text(encoding="utf-8"))["section_sha256"]


def section3(syx):
    from mtlib import aplib, container
    from mtlib.syx import unwrap
    stream, _ = unwrap(pathlib.Path(syx).read_bytes())
    c = container.parse(stream)
    s3 = next(s for s in c["sections"] if s["id"] == 3)
    return aplib.depack(c["blob"][s3["off"]:s3["off"] + s3["size"]])[0]


def load(image):
    p = pathlib.Path(image)
    if p.suffix.lower() == ".syx":
        data = section3(p)
        if hashlib.sha256(data).hexdigest() != stock_sha():
            raise SystemExit("!! not the official Model:Cycles OS 1.13 (section 3 SHA-256 differs from device.json)")
        return data
    return p.read_bytes()


def tweaks_by_id():
    out = {}
    for f in DEV.glob("*.json"):
        if f.name != "device.json":
            t = json.loads(f.read_text(encoding="utf-8"))
            out[t["id"]] = t
    return out


def cmd_extract(a):
    data = load(a.syx)
    name = "mainos"
    if a.with_:
        import build
        by = tweaks_by_id()
        ids = [i for i in a.with_.split(",") if i]
        missing = [i for i in ids if i not in by]
        if missing:
            raise SystemExit(f"!! unknown tweak id(s): {', '.join(missing)}")
        data = build.apply_writes(data, [by[i] for i in ids])[0]
        name += "+" + "+".join(ids)
    CACHE.mkdir(exist_ok=True)
    out = pathlib.Path(a.out) if a.out else CACHE / f"{name}.bin"
    out.write_bytes(bytes(data))
    print(f"{out}  ({len(data)} bytes, VA {BASE:#x}..{BASE + len(data):#x}, sha256 {hashlib.sha256(data).hexdigest()[:16]}…)")
    print("note: payloads appended after the image (Syntakt engines, Model-TG, MACRO) are not included")


def cross():
    for p in ("m68k-linux-gnu-", "m68k-elf-"):
        if shutil.which(p + "objdump"):
            return p
    raise SystemExit("!! m68k binutils not found (m68k-linux-gnu-objdump or m68k-elf-objdump)")


def cmd_dis(a):
    data = load(a.image)
    start = num(a.start)
    stop = start + num(a.stop[1:]) if a.stop and a.stop.startswith("+") else num(a.stop) if a.stop else start + 0x60
    if not BASE <= start < stop <= BASE + len(data):
        raise SystemExit(f"!! range outside section 3 ({BASE:#x}..{BASE + len(data):#x})")
    CACHE.mkdir(exist_ok=True)
    tmp = CACHE / "_dis.bin"
    tmp.write_bytes(data)
    out = subprocess.run([cross() + "objdump", "-D", "-b", "binary", "-m", "m68k:isa-c:emac",
                          f"--adjust-vma={BASE:#x}", f"--start-address={start:#x}", f"--stop-address={stop:#x}",
                          str(tmp)], capture_output=True, text=True, check=True).stdout
    body = out.split(">:", 1)[-1] if ">:" in out else out
    print(body.strip("\n"))


ABS_KIND = {0x4eb9: "jsr", 0x4ef9: "jmp"}


def abs_kind(op):
    if op in ABS_KIND:
        return ABS_KIND[op]
    if op & 0xf1ff == 0x41f9:
        return f"lea ->a{(op >> 9) & 7}"
    if op & 0xf1ff == 0x207c:
        return f"movea.l #imm ->a{(op >> 9) & 7}"
    if op & 0xf1ff == 0x203c:
        return f"move.l #imm ->d{(op >> 9) & 7}"
    if op & 0xf1ff == 0x2039:
        return f"move.l (abs) ->d{(op >> 9) & 7}"
    if op == 0x2f3c:
        return "move.l #imm,-(sp)"
    if op == 0x4879:
        return "pea"
    return "data/other"


def xrefs(data, target, pcrel):
    hits = []
    pat = struct.pack(">I", target)
    for m in re.finditer(re.escape(pat), data):
        o = m.start()
        if o & 1:
            continue
        op = struct.unpack_from(">H", data, o - 2)[0] if o >= 2 else 0
        kind = abs_kind(op)
        hits.append((BASE + o - 2 if kind != "data/other" else BASE + o, kind))
    if pcrel:
        for o in range(0, len(data) - 4, 2):
            op = struct.unpack_from(">H", data, o)[0]
            pc = BASE + o + 2
            if op == 0x61ff or op == 0x60ff:
                if o + 6 <= len(data) and pc + struct.unpack_from(">i", data, o + 2)[0] == target:
                    hits.append((BASE + o, "bsr.l" if op == 0x61ff else "bra.l"))
            elif op in (0x6100, 0x6000, 0x4eba, 0x4efa) or op & 0xf1ff == 0x41fa:
                if pc + struct.unpack_from(">h", data, o + 2)[0] == target:
                    k = {0x6100: "bsr.w", 0x6000: "bra.w", 0x4eba: "jsr (pc)", 0x4efa: "jmp (pc)"}.get(op)
                    hits.append((BASE + o, k or f"lea (pc) ->a{(op >> 9) & 7}"))
            elif op >> 8 in (0x61, 0x60) and op & 0xff not in (0, 0xff):
                if pc + struct.unpack(">b", bytes([op & 0xff]))[0] == target:
                    hits.append((BASE + o, "bsr.s" if op >> 8 == 0x61 else "bra.s"))
    return sorted(set(hits))


def cmd_xrefs(a):
    data = load(a.image)
    target = num(a.addr)
    hits = xrefs(data, target, a.pcrel)
    for va, kind in hits:
        print(f"{va:#010x}  {kind}")
    print(f"{len(hits)} reference(s) to {target:#x}" + ("" if a.pcrel else " (absolute only; add --pcrel for bsr/bra/jsr(pc)/lea(pc))"))


def cmd_strings(a):
    data = load(a.image)
    rx = re.compile(a.regex.encode())
    n = 0
    for m in re.finditer(rb"[\x20-\x7e]{%d,}" % a.min, data):
        if rx.search(m.group()):
            va = BASE + m.start()
            line = f"{va:#010x}  {m.group().decode()!r}"
            if a.xrefs:
                refs = xrefs(data, va, False)
                line += "   <- " + (", ".join(f"{v:#x} {k}" for v, k in refs[:6]) or "no absolute ref")
            print(line)
            n += 1
    print(f"{n} string(s)")


def cmd_bytes(a):
    data = load(a.image)
    va, n = num(a.addr), num(a.n)
    print(data[va - BASE:va - BASE + n].hex())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("extract")
    p.add_argument("syx")
    p.add_argument("--with", dest="with_", default="", help="tweak ids to apply first (comma-separated)")
    p.add_argument("-o", "--out")
    p.set_defaults(fn=cmd_extract)
    p = sub.add_parser("dis")
    p.add_argument("image")
    p.add_argument("start")
    p.add_argument("stop", nargs="?", help="end VA, or +length (default +0x60)")
    p.set_defaults(fn=cmd_dis)
    p = sub.add_parser("xrefs")
    p.add_argument("image")
    p.add_argument("addr")
    p.add_argument("--pcrel", action="store_true", help="also scan PC-relative branches and lea/jsr (slower)")
    p.set_defaults(fn=cmd_xrefs)
    p = sub.add_parser("strings")
    p.add_argument("image")
    p.add_argument("regex")
    p.add_argument("--min", type=int, default=3)
    p.add_argument("--xrefs", action="store_true")
    p.set_defaults(fn=cmd_strings)
    p = sub.add_parser("bytes")
    p.add_argument("image")
    p.add_argument("addr")
    p.add_argument("n")
    p.set_defaults(fn=cmd_bytes)
    p = sub.add_parser("va")
    p.add_argument("off")
    p.set_defaults(fn=lambda a: print(f"{num(a.off) + BASE:#010x}"))
    p = sub.add_parser("off")
    p.add_argument("va")
    p.set_defaults(fn=lambda a: print(f"{num(a.va) - BASE:#x} ({num(a.va) - BASE})"))
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
