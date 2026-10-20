---
name: repo-validation
description: Runs the full Modded Cycles validation suite in one command and reports PASS/FAIL/SKIP per check - tweaks.js and REGISTRY.md up to date, overlap checks (also against open branches), 6ch relocation, builder.js vs build.py, flasher .syx checks, jsdom smoke test, REF_MAINOS with the official files, chosen generators --check and emulation proofs. Use before every commit or push, after a merge from main, when reviewing a branch, or when asked whether the repo is consistent.
---

# Validation

```sh
V=.agents/skills/repo-validation/scripts/validate.sh
$V --quick                                  # no firmware, no network: compile, tweaks.js, overlaps, registry,
                                            # relocate_6ch, builder.js == build.py, flasher .syx checks
$V                                          # + jsdom smoke test of the page (npm, network)
$V --gen gen_trig_hold.py --proof test_trig_hold.py \
   --with model-tg-st,sample-preview-st,trig-hold,arp,tempo-max,boot-anim,multiline-browser,level-pan-values,trigless-dim,midi-live-both,lfo-plus,syntakt-tg-sd-cp-toy-bits-swarm-macro-acid
                                            # + ref_mainos --check, smoke with the real files, generator --check,
                                            #   the proof alone and combined (needs firmware/ files, unicorn)
$V --git origin/claude/<open-pr>            # overlaps and registry against an open branch (repeatable)
```

Official files are taken from `firmware/model-cycles_OS1.13.syx` and `firmware/Syntakt_OS1.42.syx` when present
(`--cycles`, `--syntakt` to override). Logs: `build/validate/*.log`. Exit 1 if anything failed.

## Reading the result

- **FAIL**: fix before committing. The last 15 lines are printed; the full log is in `build/validate/`.
- **SKIP**: the check could not run here (no firmware, no toolchain, no unicorn, `--quick`). Copy the SKIP lines
  into the PR body under "Checks not run" — never drop them silently.
- `gen_flasher_tweaks --check` or `registry --check` failing after a tweak change: rerun the script without
  `--check` and commit the regenerated file. `REF_MAINOS`/`REF_MODS`: rerun `ref_mainos.py` (needs both files).
- `relocate_6ch --check` is skipped when only `m68k-elf-` binutils are installed: that assembler relaxes
  `lea abs.l` to PC-relative, and the committed file comes from `m68k-linux-gnu-` binutils. Never regenerate
  `11-6ch-usbup.json` with `m68k-elf-`.
- A generator `--check` differing only with another compiler: same rule (notes/16 §6, notes/42 §16).

## Setup hints

`pip install unicorn numpy`; m68k toolchain: `binutils-m68k-linux-gnu gcc-m68k-linux-gnu` (Debian/Ubuntu) or
`m68k-elf-*` (Homebrew); node + npm for the web checks. The official `.syx` files are downloaded by Maxime from
elektron.se and never committed.
