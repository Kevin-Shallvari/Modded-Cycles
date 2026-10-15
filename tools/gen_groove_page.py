#!/usr/bin/env python3
"""Génère docs/groove/tweaks.js : les deux tweaks de Model:Groove, pour la page « 8 track M:C ».

Source unique : les JSON canoniques de tweaks/model-cycles_OS1.13/. Ce script recopie, il ne
décide rien — comme tools/gen_flasher_tweaks.py pour la page des mods.

La page `docs/groove/` est **séparée** de la page des mods : elle ne propose qu'une chose, la
ligne dérivée Model:Groove, avec ses avertissements. Elle réutilise `docs/flasher/builder.js`
(la construction) et `docs/flasher/flasher.js` (l'envoi USB) : rien n'est dupliqué.

Le fichier porte aussi l'empreinte du MAIN OS attendue, pour que la page refuse d'envoyer une
construction qui ne correspond pas.

    python3 tools/gen_groove_page.py --cycles model-cycles_OS1.13.syx [--check]
"""
import argparse
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "emu"))

import build                       # noqa: E402
import test_sdvintage as T         # noqa: E402

ROOT = HERE.parent
TW = ROOT / "tweaks" / "model-cycles_OS1.13"
OUT = ROOT / "docs" / "groove" / "tweaks.js"

# L'ordre compte : 56 (le moteur) puis 57 (le format), comme dans BUILD.md.
ORDER = ["56-groove-8tracks.json", "57-groove-patterns.json"]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycles", required=True, help="model-cycles_OS1.13.syx officiel")
    ap.add_argument("--check", action="store_true",
                    help="vérifie que docs/groove/tweaks.js correspond")
    args = ap.parse_args()

    stock = bytes(T.main_os_from_syx(args.cycles))
    dev = json.loads((TW / "device.json").read_text(encoding="utf-8"))
    if build.sha(stock) != dev["section_sha256"]:
        raise SystemExit("!! ce n'est pas le MAIN OS 1.13 officiel")

    tweaks = []
    for name in ORDER:
        t = json.loads((TW / name).read_text(encoding="utf-8"))
        tweaks.append(t)

    patched, _ = build.apply_writes(stock, tweaks)
    mainos = hashlib.sha256(patched).hexdigest()
    n = sum(len(t["writes"]) for t in tweaks)

    lines = [
        "/* Genere par tools/gen_groove_page.py depuis tweaks/model-cycles_OS1.13/.",
        " * NE PAS editer a la main : relance le script apres avoir change un tweak.",
        " *",
        " * Model:Groove — ligne derivee, hors page des mods (docs/groove/).",
        " * MAIN OS attendu pour 56 + 57 : %s" % mainos,
        " */",
        "window.MC_GROOVE = {",
        '  "mainos": "%s",' % mainos,
        '  "device": "Model:Cycles",',
        '  "os": "1.13",',
        '  "order": [%s],' % ", ".join('"%s"' % t["id"] for t in tweaks),
        '  "tweaks": [',
    ]
    for i, t in enumerate(tweaks):
        lines.append("    {")
        for key in ("id", "order", "name", "description", "device", "os", "section"):
            lines.append("      %s: %s," % (json.dumps(key),
                                            json.dumps(t[key], ensure_ascii=False)))
        lines.append('      "writes": [')
        for w in t["writes"]:
            lines.append('        {"off": %d, "old": "%s", "new": "%s"},'
                         % (w["off"], w["old"], w["new"]))
        lines.append("      ]")
        lines.append("    }" + ("," if i + 1 < len(tweaks) else ""))
    lines.append("  ]")
    lines.append("};")

    text = "\n".join(lines) + "\n"
    print("Model:Groove : %d tweak(s), %d ecriture(s)" % (len(tweaks), n))
    print("  MAIN OS attendu : %s" % mainos)
    print("  ecrit dans      : %s" % OUT.relative_to(ROOT))

    if args.check:
        ok = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("  %s" % ("est à jour" if ok else "NE CORRESPOND PAS"))
        raise SystemExit(0 if ok else 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print("  écrit (%d octets)" % len(text))


if __name__ == "__main__":
    main()
