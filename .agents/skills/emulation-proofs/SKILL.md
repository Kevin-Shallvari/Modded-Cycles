---
name: emulation-proofs
description: Writes and runs Unicorn emulation proofs (tools/emu/test_<mod>.py) that execute the Model:Cycles OS 1.13's own ColdFire code, stock versus patched, alone and combined with other mods - choosing the right rig (voice loop mcengine, sequencer seqrig, key chain, screen, UI views, USB, governor, Syntakt stengine), intercepting OS services, exact EMAC, ok/ECHEC reporting. Use when proving a new mod or a fix, reproducing a hardware bug report, measuring CPU cost, or when a proof fails.
---

# Emulation proofs

Rule 5 of `AGENTS.md`: unproven code does not go in the flasher. A proof runs the **OS's own code** (not a model
of it) on the stock MAIN OS and on the patched one, shows the difference the mod makes, and that nothing else
changes. Needs `pip install unicorn numpy` and the official files in `firmware/`.

Which rig for which subsystem, and the proof to copy: [references/rigs.md](references/rigs.md).

## Shape of `tools/emu/test_<mod>.py`

Copy `test_trig_hold.py` (event chain, interceptions) or `test_tempo_max.py` (several OS routines, EMAC).

```python
"""Preuve de … (notes/NN, tweaks/model-cycles_OS1.13/OO-<id>.json).   # French docstring: what runs, numbered checks
    python3 tools/emu/test_<mod>.py --cycles model-cycles_OS1.13.syx [--with <the other tweaks of os.json> --syntakt Syntakt_OS1.42.syx]
"""
FAIL = []
def check(ok, msg):                    # one printed line per check: "ok" / "ECHEC" (as the existing proofs)
    print(("  ok    " if ok else "  ECHEC ") + msg, flush=True)
    if not ok: FAIL.append(msg)

def main():
    stock = T.main_os_from_syx(args.cycles)
    tweaks = [by_id[i] for i in args.others.split(",") if i]          # --with
    pl, _ = build.build_payload(tweaks, stock, args.syntakt)           # payloads appended after the image
    base = build.apply_writes(stock, tweaks)[0] + pl                   # "stock" = the other mods only
    img = build.apply_writes(stock, tweaks + [tweak])[0] + pl          # patched
    ...                                                                # same scenario on base and img
    print("\nTOUT OK" if not FAIL else f"\n{len(FAIL)} ÉCHEC(S)")
    return 1 if FAIL else 0
```

## Checklist for a proof

- [ ] Writes: stock bytes match, hooks land where the generator says, no overlap with the `--with` mods
- [ ] The behaviour the user asked for, on the patched image, through the real OS entry point
- [ ] The same scenario on the stock image behaves as before (and as the note describes the original bug, if any:
      keep that check, it documents why the patch exists — tempo-max's LFO above 351.6 BPM)
- [ ] Edge cases: limits, wrap-around of counters, re-entrancy, empty/zero inputs, every track/voice
- [ ] Combined run: `--with model-tg-st,sample-preview-st,trig-hold,arp,tempo-max,boot-anim,multiline-browser,level-pan-values,trigless-dim,midi-live-both,lfo-plus,syntakt-tg-sd-cp-toy-bits-swarm-macro-acid (minus the tweak under test)
      --syntakt firmware/Syntakt_OS1.42.syx` plus every mod hooking near yours (`REGISTRY.md` §4)
- [ ] Audio-path cost measured if the code runs per block (`Engine.count_instructions`)
- [ ] Exit code non-zero on any failed check; run time stated in the docstring if long
- [ ] The note gets a stock vs modified table of what the proof showed (`[FAIT en émulation]`)

## Techniques

- Map only what is needed; hook `UC_HOOK_MEM_UNMAPPED` to print the PC and address instead of crashing blind.
- Intercept OS services you do not want to run (mailboxes, flash, screen refresh, RTOS calls) with a
  `UC_HOOK_CODE` at their entry that sets `d0` and returns (`pc = pop()`); log the calls to assert on them.
- Build OS objects with the OS's own constructors (`KeyEvent` ctor `0x4007238c`, `UIStates` methods) rather than
  hand-filled structs.
- EMAC: always route through `emac.py` when the code runs with `MACSR = 0xa0` (Unicorn's fractional MAC is wrong).
- Screen: render the 1 024-byte buffer to ASCII/PNG and compare with expected pixels (`test_boot_anim.py`,
  `test_level_pan.py`); remember y = 0 is the bottom row.
- Audio: compare sample by sample (`np.array_equal`) when the result must be exact; otherwise state the metric
  (f0, RMS, spectrum per third-octave) and its tolerance in the note.
- A hardware bug report becomes a failing check first, then the fix makes it pass.
