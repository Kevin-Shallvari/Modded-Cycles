#!/usr/bin/env python3
"""Generate docs/flasher/tweaks.js, the data the web flasher embeds, from os.json and tweaks/model-cycles_OS1.13/.

The flasher installs ONE firmware, the Modded Cycles OS: the tweaks listed in os.json ("tweaks"), applied to the
user's official OS 1.13 in the browser. tweaks.js carries only those tweaks (their writes, payload recipes and
metadata), the OS description (name, version, status, added machines) and the list of features shown on the page
(id, section, status, credit, license, guide anchor). The page's texts for each feature live in docs/flasher/app.js
(FEAT, en/fr). The other JSON files in tweaks/ are the library of building blocks tools/build.py -t can still build
for development; they are not sent to users.

    python3 tools/gen_flasher_tweaks.py            # writes docs/flasher/tweaks.js and the license files it serves
    python3 tools/gen_flasher_tweaks.py --check    # validation: is it up to date?

Checks done here: every tweak of the OS exists, the set is buildable (no declared conflict, every "requires"
satisfied inside the set, like tools/build.py), every feature points at tweaks of the OS, every tweak of the OS is
owned by a feature, categories are known, license files exist.
"""
import argparse
import collections
import copy
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
DEV_DIR = ROOT / "tweaks" / "model-cycles_OS1.13"
OS_JSON = ROOT / "os.json"
OUT = ROOT / "docs" / "flasher" / "tweaks.js"

# Sections of the feature list on the page (docs/flasher/app.js CATS has the same list, plus "other").
CATS = ("sound", "seq", "live", "screen", "io")

# Licenses of third-party code the page embeds outside the features: builder.js is a port of mtlib (drumkilla),
# itself based on elektron-firmware-tool (Marcel Bierling). See THIRD-PARTY-NOTICES.md.
PAGE_LICENSES = {
    "LICENSE-elektron-model-tweaks": DEV_DIR / "LICENSE-elektron-model-tweaks",
    "LICENSE-elektron-firmware-tool": ROOT / "tools" / "mtlib" / "LICENSE-elektron-firmware-tool",
}

SHARED_MIN = 2048      # shared values: strings or lists of at least 2 KB in compact JSON


def load_os():
    return json.loads(OS_JSON.read_text(encoding="utf-8"))


def load_tweaks():
    """{id: tweak} for every tweak JSON of the device folder."""
    by_id = {}
    for p in sorted(DEV_DIR.glob("*.json")):
        if p.name == "device.json":
            continue
        t = json.loads(p.read_text(encoding="utf-8"))
        if t["id"] in by_id:
            sys.exit(f"!! tweaks/: two files carry the id {t['id']!r}")
        by_id[t["id"]] = t
    return by_id


def check_os(os_def, by_id):
    """The OS is buildable: every tweak exists, no declared conflict, every requires satisfied (tools/build.py rules);
    the features cover exactly the tweaks of the OS; categories, statuses and licenses are valid."""
    ids = os_def["tweaks"]
    if len(set(ids)) != len(ids):
        sys.exit("!! os.json: a tweak is listed twice")
    for tid in ids:
        if tid not in by_id:
            sys.exit(f"!! os.json: unknown tweak {tid!r} (no tweaks/model-cycles_OS1.13/*.json with this id)")
    chosen = {tid: by_id[tid] for tid in ids}
    for t in chosen.values():
        for c in t.get("conflicts") or []:
            if c in chosen:
                sys.exit(f"!! os.json: {t['id']} conflicts with {c}: they cannot be in the same firmware")
        for r in t.get("requires") or []:
            if r not in chosen:
                sys.exit(f"!! os.json: {t['id']} requires {r}, which is not in the OS")
    owned = collections.Counter()
    for f in os_def["features"]:
        if f.get("cat") not in CATS:
            sys.exit(f"!! os.json: feature {f['id']} has cat {f.get('cat')!r}, expected one of {', '.join(CATS)}")
        if f.get("status") not in ("tested", "experimental"):
            sys.exit(f"!! os.json: feature {f['id']} has status {f.get('status')!r}")
        for tid in f.get("tweaks") or []:
            if tid not in chosen:
                sys.exit(f"!! os.json: feature {f['id']} names {tid}, which is not a tweak of the OS")
            owned[tid] += 1
        if f.get("license") and not (DEV_DIR / f["license"]).exists():
            sys.exit(f"!! os.json: feature {f['id']}: license file {f['license']} missing in tweaks/model-cycles_OS1.13/")
    if os_def.get("status") not in ("tested", "experimental"):
        sys.exit(f"!! os.json: status {os_def.get('status')!r}")
    unowned = [tid for tid in ids if not owned[tid]]
    if unowned:
        sys.exit(f"!! os.json: no feature names the tweak(s) {', '.join(unowned)}")
    return [chosen[tid] for tid in ids]


def share(tweaks):
    """Values repeated from one tweak to another are stored once in "shared" and replaced by {"$shared": k}.
    tweaks.js puts them back at load time (HYDRATE), read_js() does the same in Python."""
    def key(v):
        return json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    count = collections.Counter()

    def walk(v):
        if isinstance(v, (str, list)) and len(k := key(v)) >= SHARED_MIN:
            count[k] += 1
        for x in v if isinstance(v, list) else v.values() if isinstance(v, dict) else ():
            walk(x)
    for t in tweaks:
        walk(t)
    shared, index = [], {}

    def sub(v):
        if isinstance(v, (str, list)) and count[k := key(v)] > 1:
            if k not in index:
                index[k] = len(shared)
                shared.append(v)
            return {"$shared": index[k]}
        if isinstance(v, list):
            return [sub(x) for x in v]
        if isinstance(v, dict):
            return {a: sub(x) for a, x in v.items()}
        return v
    return [sub(t) for t in tweaks], shared


# Puts the shared values back (share); a shared list is copied for each tweak, a string is not.
HYDRATE = (
    "(function (tw) {\n"
    "  const s = tw.shared || [];\n"
    "  delete tw.shared;\n"
    "  const h = (v) => Array.isArray(v) ? v.map(h) : v && typeof v === \"object\"\n"
    "    ? (\"$shared\" in v ? (Array.isArray(s[v.$shared]) ? JSON.parse(JSON.stringify(s[v.$shared])) : s[v.$shared])\n"
    "      : Object.fromEntries(Object.entries(v).map(([k, x]) => [k, h(x)]))) : v;\n"
    "  tw.tweaks = tw.tweaks.map(h);\n"
    "})(window.MC_TWEAKS);\n"
)


def read_js(text):
    """Content of tweaks.js (window.MC_TWEAKS), shared values put back as in the page."""
    start = text.index("window.MC_TWEAKS = ") + len("window.MC_TWEAKS = ")
    tw = json.JSONDecoder().raw_decode(text, start)[0]
    s = tw.pop("shared", [])

    def h(v):
        if isinstance(v, list):
            return [h(x) for x in v]
        if isinstance(v, dict):
            return copy.deepcopy(s[v["$shared"]]) if "$shared" in v else {k: h(x) for k, x in v.items()}
        return v
    tw["tweaks"] = [h(t) for t in tw["tweaks"]]
    return tw


def render():
    from crossflash import OFFICIAL            # hashes of the official OS files, single source (tools/crossflash.py)
    device = json.loads((DEV_DIR / "device.json").read_text(encoding="utf-8"))
    os_def = load_os()
    by_id = load_tweaks()
    tweaks = check_os(os_def, by_id)
    features = []
    for f in os_def["features"]:
        feat = {"id": f["id"], "cat": f["cat"], "status": f["status"], "credit": f.get("credit"),
                "tweaks": list(f.get("tweaks") or [])}
        if f.get("needs"):
            feat["needs"] = f["needs"]
        if f.get("license"):                    # license text served next to the page (licenses())
            feat["license"] = f["license"] + ".txt"
        if f.get("guide"):
            feat["guide"] = f["guide"]
        features.append(feat)
    shared_tweaks, shared = share(tweaks)
    payload = {
        "device": {k: device[k] for k in ("device", "os", "section_sha256", "stock_syx_sha256", "cave_refs_ok")
                   if k in device},
        "os": {
            "name": os_def["name"], "version": os_def["version"], "status": os_def["status"],
            "key": "+".join(os_def["tweaks"]),          # the REF_MAINOS key (docs/flasher/app.js, tools/ref_mainos.py)
            "tweaks": list(os_def["tweaks"]),
            "machines": os_def.get("machines", []),
            "needs": os_def.get("needs", ["cycles"]),
        },
        "tweaks": shared_tweaks,
        "features": features,
        # "Samples OS" tab: the official Model:Samples OS, put in the Cycles container (crossflash)
        "samples": {"syx_sha256": OFFICIAL["samples"]["syx"], "main_sha256": OFFICIAL["samples"]["main"],
                    "download": "https://www.elektron.se/support-downloads/modelsamples"},
        # the Syntakt engines are read from the user's official Syntakt_OS1.42.syx (or 1.41)
        "syntakt": {"download": "https://www.elektron.se/support-downloads/syntakt"},
        "shared": shared,
    }
    body = json.dumps(payload, ensure_ascii=False, indent=1)
    text = (
        "/* Generated by tools/gen_flasher_tweaks.py from os.json and tweaks/model-cycles_OS1.13/.\n"
        " * DO NOT edit by hand: rerun the script after changing os.json or a tweak. */\n"
        "window.MC_TWEAKS = " + body + ";\n" + HYDRATE
    )
    if read_js(text)["tweaks"] != tweaks:
        sys.exit("!! shared values: tweaks.js does not give back the tweaks of tweaks/")
    return text


def licenses():
    """License texts published with the page (third-party code embedded in tweaks.js and builder.js): {file: text}."""
    os_def = load_os()
    out = {OUT.parent / (f["license"] + ".txt"): (DEV_DIR / f["license"]).read_text(encoding="utf-8")
           for f in os_def["features"] if f.get("license")}
    out.update({OUT.parent / (name + ".txt"): src.read_text(encoding="utf-8") for name, src in PAGE_LICENSES.items()})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="check without writing")
    args = ap.parse_args()
    text = render()
    if args.check:
        stale = [p.name for p, t in licenses().items() if not p.exists() or p.read_text(encoding="utf-8") != t]
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text or stale:
            sys.exit("!! docs/flasher/tweaks.js (or a license file) is out of date: run tools/gen_flasher_tweaks.py")
        print("docs/flasher/tweaks.js is up to date")
        return
    for p, t in licenses().items():
        p.write_text(t, encoding="utf-8")
    OUT.write_text(text, encoding="utf-8")
    os_def = load_os()
    print(f"written: {OUT.relative_to(ROOT)} ({len(text)} bytes, {os_def['name']} {os_def['version']}: "
          f"{len(os_def['tweaks'])} tweaks, {len(os_def['features'])} features)")


if __name__ == "__main__":
    main()
