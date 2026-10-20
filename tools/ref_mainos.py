#!/usr/bin/env python3
"""Reference hashes of the web flasher, written into docs/flasher/app.js (notes/49).

Two generated blocks:
  REF_MAINOS  the SHA-256 of the MAIN OS (section 3, patched, with the payloads appended) of the Modded Cycles OS,
              built with tools/build.py from the official files: one key, the tweak ids of os.json joined by "+".
              The page refuses a build whose MAIN OS differs.
  REF_MODS    for each tweak embedded in tweaks.js: the hash of its writes (w) and, when it appends a payload, of the
              payload image (p). The page checks every tweak against it on every build.

    python3 tools/ref_mainos.py --cycles firmware/model-cycles_OS1.13.syx --syntakt firmware/Syntakt_OS1.42.syx
    python3 tools/ref_mainos.py --cycles ... --syntakt ... --check      # validation: app.js up to date?

Rerun after any change to os.json or to a tweak of the OS (then commit app.js). Never edit the blocks by hand, and
after a merge regenerate them instead of resolving their conflicts.
"""
import argparse
import contextlib
import functools
import hashlib
import io
import json
import pathlib
import re
import struct
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "emu"))

import build                       # noqa: E402
import gen_flasher_tweaks          # noqa: E402

ROOT = HERE.parent
TWEAKS_JS = ROOT / "docs" / "flasher" / "tweaks.js"
APP_JS = ROOT / "docs" / "flasher" / "app.js"
# a block: "const NAME = {", its lines (each preceded by a newline; none if empty), "\n};"
BLOCKS = {name: re.compile(r"(const " + name + r" = \{)((?:\n  .*)*)(\n\};\n)") for name in ("REF_MAINOS", "REF_MODS")}


def mc_tweaks():
    return gen_flasher_tweaks.read_js(TWEAKS_JS.read_text(encoding="utf-8"))


def main_os(cycles):
    """Decompressed MAIN OS of the official .syx, as tools/build.py reads it."""
    c = build.container.parse(build.unwrap(pathlib.Path(cycles).read_bytes())[0])
    s3 = next(s for s in c["sections"] if s["id"] == 3)
    return build.aplib.depack(c["blob"][s3["off"]:s3["off"] + s3["size"]])[0]


def writes_bytes(t):
    """A tweak's writes, one after the other: off (4 bytes), len(old) (4), old, len(new) (4), new; the same bytes
    docs/flasher/builder.js hashes (writesBytes)."""
    out = bytearray()
    for w in t["writes"]:
        old, new = bytes.fromhex(w["old"]), bytes.fromhex(w["new"])
        out += struct.pack(">II", w["off"], len(old)) + old + struct.pack(">I", len(new)) + new
    return bytes(out)


def blocks(cycles, syntakt):
    """(REF_MAINOS text, REF_MODS text, the OS key)."""
    tw = mc_tweaks()
    by_id = {t["id"]: t for t in tw["tweaks"]}
    stock = main_os(cycles)
    if build.sha(stock) != tw["device"]["section_sha256"]:      # never from an already modified build (rule 2)
        raise SystemExit("!! --cycles: not the official MAIN OS 1.13: model-cycles_OS1.13.syx from elektron.se is needed")
    st_img = None
    if any("syntakt" in (t.get("append") or {}) for t in tw["tweaks"]):
        if not syntakt:
            raise SystemExit("!! the OS reads the Syntakt engines: --syntakt Syntakt_OS1.42.syx (or 1.41) is needed")
        import syntakt as st                                # tools/emu/syntakt.py: checks the .syx and its section 7
        st.dsp_image = functools.lru_cache(maxsize=None)(st.dsp_image)   # read once (build_payload reads it again)
        st_img = st.dsp_image(syntakt)
    known = tw["device"].get("cave_refs_ok")

    mods = []
    for t in tw["tweaks"]:
        ref = {"w": hashlib.sha256(writes_bytes(t)).hexdigest()}
        if t.get("append"):
            ref["p"] = hashlib.sha256(build.payload_image(t, build.payload_runtime(t, stock, st_img))).hexdigest()
        mods.append(f'  "{t["id"]}": {json.dumps(ref, separators=(", ", ": "))},')

    ids = tw["os"]["tweaks"]
    key = "+".join(ids)
    if key != tw["os"]["key"]:
        raise SystemExit("!! tweaks.js: os.key differs from os.tweaks: rerun tools/gen_flasher_tweaks.py")
    chosen = sorted((by_id[i] for i in ids), key=lambda t: t["order"])
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            build.check_conflicts(chosen)
            patched, dirty = build.apply_writes(stock, chosen)
            build.check_caves(stock, chosen, False, dirty, patched, known)
            apps = [t for t in chosen if t.get("append")]
            payload = build.build_payload(apps, stock, syntakt)[0] if apps else b""
    except SystemExit as e:
        raise SystemExit(f"!! the OS ({key}) is refused by tools/build.py: {e}")
    lines = [f"  // {tw['os']['name']} {tw['os']['version']}: the tweaks of os.json, built by tools/build.py --os",
             f'  "{key}": "{build.sha(bytes(patched) + payload)}",']
    return "\n".join(lines), "\n".join(mods), key


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycles", required=True, help="official model-cycles_OS1.13.syx")
    ap.add_argument("--syntakt", help="official Syntakt_OS1.42.syx (or 1.41)")
    ap.add_argument("--check", action="store_true", help="check that app.js is up to date")
    args = ap.parse_args()
    ref, mods, key = blocks(args.cycles, args.syntakt)
    app = APP_JS.read_text(encoding="utf-8")
    want = {"REF_MAINOS": "\n" + ref, "REF_MODS": "\n" + mods}
    found = {k: BLOCKS[k].search(app) for k in want}
    for k, m in found.items():
        if not m:
            raise SystemExit(f"!! block {k} not found in app.js")
    nm = mods.count("\n") + 1
    if args.check:
        stale = [k for k in want if found[k].group(2) != want[k]]
        if stale:
            raise SystemExit(f"!! {', '.join(stale)} of app.js out of date ({nm} mods): rerun tools/ref_mainos.py")
        print(f"REF_MAINOS and REF_MODS are up to date ({nm} mods, OS key {key[:40]}…)")
        return
    for k in sorted(want, key=lambda k: -found[k].start()):   # from the end: positions stay valid
        m = found[k]
        app = app[:m.start(2)] + want[k] + app[m.end(2):]
    APP_JS.write_text(app, encoding="utf-8")
    print(f"written: REF_MAINOS (1 firmware) and REF_MODS ({nm} mods) in {APP_JS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
