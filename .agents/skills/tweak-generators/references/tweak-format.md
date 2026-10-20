# Tweak JSON format (tweaks/model-cycles_OS1.13/NN-<id>.json)

## File name and order

`NN-<id>.json`; `NN` is also `order`, the application order in both builders. Find the next free number with
`ls tweaks/model-cycles_OS1.13 | cut -c1-3 | sort -u` and check open branches (`git branch -r`, `registry.py --git`).

| Range | What |
|---|---|
| `01`–`09` | small UI tweaks by drumkilla |
| `10`–`19` | USB audio (6 channels) |
| `20`–`29` | machines: SD VINTAGE, Syntakt engines (`24-syntakt-*`), MACRO `25`, ACID `26` |
| `30`–`39` | Model-TG and its combinations (`30`, `31`, `32` macro-tg, `35` acid-tg), add-ons that need it (`33` sample-preview) |
| `40`–`49` | sequencer and interface (`40` arp … `48` track-filter; `45` free since chord-keys was removed on 18/10/2026) |
| `50`–`59` | MIDI (`50` midi-both, `51` midi-live-both) |
| `60`–`69` | modulation (`60` lfo-plus) |
| `90`–`99` | diagnostics, never offered to users |

## Fields

```jsonc
{
 "id": "tempo-max",                  // kebab-case; build.py -t and the flasher use it; unique
 "order": 42,
 "name": "Tempo jusqu'à 546.0 BPM",   // French, short
 "description": ["…", "…"],          // French lines: what it does, limits, free space, "Généré par tools/gen_….py, notes/NN."
 "device": "Model:Cycles", "os": "1.13", "section": 3,
 "conflicts": ["…"],                 // ids never built together (both builders refuse)
 "requires": ["…"],                  // ids it is applied on top of (may write over their bytes)
 "writes": [{"off": 50286, "old": "223c00008ca0", "new": "223c0000fff0"}]  // section-3 offset, plain hex, same length
}
```

Optional, already used: `append` (payload copied at boot; `compress: "aplib"` + `stored`), `gov` (load governor
settings), `symbols` (state addresses for the proofs), `version`, `source`, `result_sha256`.

`runtime` (`mod-settings`, notes/72): `[{"off": …, "len": …, "why": "…"}]`, bytes of the OS the tweak's code rewrites
while the OS runs (no `old`/`new`: the builders ignore it). `check_overlaps.py` refuses any write there by a tweak
that can be installed with it, even one it requires; `registry.py` lists them in §6.

A new field must be read identically by `tools/build.py` and `docs/flasher/builder.js` in the same commit;
`tools/webbuild_check.sh` and `tools/webflash_smoke.sh` verify it.

## Rules the checks enforce

- `check_overlaps.py`: two installable-together tweaks never write the same bytes, except the same whole write
  (`off`, `old`, `new`) or through `requires`; otherwise declare `conflicts`. Nobody writes a `runtime` range.
  Hex without spaces, `old`/`new` same non-zero length, inside section 3, unique ids, `requires` targets exist,
  payload chains fit.
- `registry.py`: no write into a freed mask without its redirect; none into a kept copy.
- `build.py`: every `old` matches the stock image; writes into `0xFF` zones pointed to by the stock image are refused
  unless a chosen tweak rewrites the pointer or `device.json` `cave_refs_ok` lists it.
