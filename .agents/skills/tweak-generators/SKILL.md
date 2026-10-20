---
name: tweak-generators
description: Writes and maintains tools/gen_<mod>.py generators and the tweak JSON files they produce in tweaks/model-cycles_OS1.13/ (writes with old/new bytes, order ranges, conflicts/requires, append payloads, symbols, --check), plus PROVENANCE.md, REGISTRY.md and BUILD.md updates. Use when creating or changing a tweak, regenerating JSON after a source change, picking a tweak number, or when a --check fails.
---

# Tweak generators and tweak JSON

Never edit a tweak JSON by hand: change the generator or its sources, rerun, commit both. Exceptions:
drumkilla's `01`–`03` (copied, hashes in `PROVENANCE.md`; `02` carries our 3-byte fix) and `10-6ch-multiout`.
Field reference and order ranges: [references/tweak-format.md](references/tweak-format.md).

## Anatomy of `tools/gen_<mod>.py`

Copy `tools/gen_tempo_max.py` (data only) or `tools/gen_trig_hold.py` (assembled code in a freed mask). Keep the
folder's conventions: Python 3, **French** docstring and comments, standard library except for code mods.

1. Module docstring (French): what the mod does on the machine, where its code lives, the note, the command line.
2. Constants: `OUT = …/NN-<id>.json`, the hook table `(va, stock bytes hex, symbol, role)`, the free space taken.
3. `main()`: `--cycles` (and `--syntakt` if it extracts Syntakt code at build time), `--check`.
   - Load section 3 (`test_sdvintage.main_os_from_syx`) and refuse a file whose SHA-256 differs from
     `device.json["section_sha256"]`.
   - Build each write from the stock image: `old` is always read from the official bytes, never typed; check the
     expected stock bytes of each hook before writing (`raise SystemExit("!! …")`).
   - `build.apply_writes(stock, [tweak])` before writing, so a bad `old` fails here, not in the build.
   - Output exactly `json.dumps(tweak, indent=1) + "\n"` (match the existing generator you copied; some use
     `ensure_ascii=False`). `--check` compares with the committed file and exits 1 on difference.
4. The last line of `description` names the free space used, the generator and the note.

## Loop

```sh
python3 tools/gen_<mod>.py --cycles firmware/model-cycles_OS1.13.syx          # write
python3 tools/gen_<mod>.py --cycles firmware/model-cycles_OS1.13.syx --check  # must print up to date
python3 tools/check_overlaps.py                                               # no shared bytes with installable mods
python3 tools/registry.py && git diff --stat tweaks/model-cycles_OS1.13/REGISTRY.md
python3 tools/build.py -i firmware/model-cycles_OS1.13.syx -t <id> -o build/<id>.syx   # full build + checks
```

If `--check` differs only after a toolchain change, say so (which `as`/`gcc` produced the committed file) rather
than regenerating silently: committed bytes are what Maxime tested.

## Registers to update in the same PR

- `tweaks/model-cycles_OS1.13/PROVENANCE.md`: one row (author, origin repo + commit for outside work, license,
  what we changed, generator, note).
- `REGISTRY.md`: regenerate and commit. Bytes of saved structures go in `DECLARED` of `tools/registry.py`.
- `BUILD.md` (French): a section with the generator, proof and build commands, and the MAIN OS SHA-256 of the
  main combinations (`tools/build.py` prints "MAIN OS patche SHA-256"; `--expect-mainos` re-checks it).
- `device.json` only for a justified `cave_refs_ok` entry (with `why` and a note).

## Families with their own generator

- Syntakt engines (`24-syntakt-*`, `31-syntakt-tg-*`, `90`–`92`): `CATALOG` in `gen_syntakt_engines.py`, then
  `--all` and `--all --tg`; never hand-pick files.
- Added machines (MACRO `25`, ACID `26`, with Model-TG `32`/`35`, combos): `gen_macro.added_machine`,
  `gen_acid_combos.py`, `gen_macro_syntakt.py`; read notes/43, 50, 54 §11.
- Model-TG (`30`): `gen_model_tg.py --model-tg <clone>`; add-ons that need it (`33` sample-preview) `requires` it.
- `11-6ch-usbup`: `tools/relocate_6ch.py`.
