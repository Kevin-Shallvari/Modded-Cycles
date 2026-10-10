# Handoff: Modded-Cycles, Kevin's work (2026-10-10)

For whichever coding agent picks this up. Everything here is plain text; nothing depends on a specific tool.

This file lives on the `handoff` branch of Kevin's fork, with `handoff/` (toolchain recipe, probe scripts). That branch
is `wavetable-machine` plus these files only: **never open a PR from `handoff`**; work and open PRs from
`wavetable-machine` (or a branch made from it).

Start by reading the repo's `AGENTS.md` (and the `AGENTS.md` of each folder you touch). It is binding: languages,
hard rules (never commit Elektron firmware or bytes from it, build only from the official image, hardware testing
is the owner's, prove every mod in emulation, one user-visible change per PR), and the PR shape.

## Who is who

- **Maxime** (GitHub `18nelli18`): repo owner. Tests every firmware change on his Model:Cycles and merges.
  AGENTS.md says "talk to Maxime in French"; that rule is about him.
- **Kevin** (GitHub `Kevin-Shallvari`): contributor, the person you are working with. Read-only access to the
  original repo, so he works from a fork.

## Working with Kevin

- **Talk to him in English.** He does not speak French. Repo files still follow AGENTS.md's languages
  (notes, `PROVENANCE.md`, tool comments/docstrings and tweak names in French; site text en+fr).
- **Keep every code comment short** (one line where possible). The "why" goes in `notes/NN`, referenced from code.
- He is a DSP/firmware novice: explain trade-offs in sound terms (what you hear, dB), not formulas.
- He decides by ear on prototypes; don't reopen choices he already made (listed below).
- He tests on his own Model:Cycles; report only results he gave you.

## Repo and remotes

```sh
git clone https://github.com/18nelli18/Modded-Cycles.git && cd Modded-Cycles
git remote add fork https://github.com/Kevin-Shallvari/Modded-Cycles.git && git fetch fork
git checkout -b wavetable-machine fork/wavetable-machine
git show fork/handoff:HANDOFF.md > /tmp/HANDOFF.md                     # this file, readable from any branch
mkdir -p build && git archive fork/handoff handoff | tar -x -C build --strip-components=1   # probes into build/ (git-ignored)
```
After that, `build/` holds `toolchain/`, `wt-proof/` and `wt-proto/` as the scripts expect.
Push to `fork`; PRs go from the fork to `18nelli18/Modded-Cycles` `main` (a fork PR can only target `main`, so
stacked PRs show their parents' commits until those merge).

## Branches (all on `fork`)

| Branch | Head | State |
|---|---|---|
| `acid-machine` | `bceb2e1` | PR #65 open: Acid, a 303-style bass as a 7th machine (notes/51) |
| `acid-tg` | `6e42b43` | PR #66 open, on #65: Acid with Model-TG (notes/51 §6) |
| `acid-slide` | `1061c16` | PR #67 open, on #66: 303 slides via Model-TG slide trigs (notes/51 §10.5) |
| `acid-syntakt` | `0661b31` | on acid-slide, **no PR yet**: Acid with the Syntakt engines under Model-TG (notes/51 §11) |
| `wavetable-machine` | `e2d06be` | **current work**, on acid-tg: Wave machine; `notes/52` §9–§12 updated 2026-10-10 with the build, hardware findings and performance figures |
| `wavetable` | `e3f0546` | older copy of the study commit on main; superseded |
| `backup/acid-*` | | pre-rebase copies (notes were numbered 44 then); backup only |

All Acid PRs await Maxime's hardware test.

## Toolchain (important)

The committed compiled outputs (Syntakt tweaks, SD VINTAGE v2, `36-wavetable-tg.json`) are reproduced only by
**`m68k-elf-gcc` 16.2 (Homebrew) with Ubuntu 22.04's m68k binutils 2.38**. With Ubuntu 24.04's
`m68k-linux-gnu-gcc` 13.3, `gen_wavetable.py --check` fails (code 0x160 bytes larger, 7 jump targets shift).

`handoff/toolchain/` (copied to `build/toolchain/` above) rebuilds that environment:
```sh
podman build -t mc-m68k-elf:16.2 -f build/toolchain/Containerfile build/toolchain   # or docker
cp build/toolchain/mc16 build/mc16 && chmod +x build/mc16
build/mc16 python3 tools/gen_wavetable.py --cycles firmware/model-cycles_OS1.13.syx --check   # → "est à jour"
```
The launcher sets `M68K_CROSS=/opt/mc/bin/mc-`, which the generators read. Emulation proofs also need
`pip install unicorn numpy` (on the host or in the image). On 2026-10-10 `test_wavetable.py` passed (TOUT OK) and `gen_wavetable.py --check` passed with that compiler. The repo's `notes/52` §9–§12 and `BUILD.md` ("Machine Wave") now carry the same facts in French, for agents that only get the repo.

Official firmware goes in `firmware/` (git-ignored), downloaded from elektron.se: `model-cycles_OS1.13.syx`
(SHA-256 starts `44fe5862`) and `Syntakt_OS1.42.syx`.

## Acid (done, in review)

Approved design, decided by ear: saw→square continuous morph on SHAPE; COLOR = DJ filter (0..63 low-pass
20 Hz→20 kHz, 64 open, 65..127 high-pass from 10 Hz); SWEEP = resonance (self-oscillates at the top); CONTOUR =
bipolar env mod; DECAY = filter env + amp length; PUNCH = accent. 4-pole ZDF ladder, no oversampling, exact
3-segment soft-knee clipper in the feedback loop; coefficients per block (low CPU is a priority). No level step at
COLOR 64. The name is "Acid" (avoid the Roland "303" trademark). Slides only through Model-TG slide trigs. Details: notes/51.

## Wave (wavetable machine): status

Committed on `wavetable-machine`: `tools/machines/wavetable/wt.c` (engine), `tools/gen_wavetable.py` (writes
`tweaks/model-cycles_OS1.13/36-wavetable-tg.json`, 127 writes, requires `model-tg-st`), `tools/emu/test_wavetable.py`
+ `tools/emu/wt_host.c` (proof), `notes/52-etude-tables-d-ondes.md` (study). Not in the flasher yet.

Design (frozen choices, don't reopen):
- Plays the **user's own tables** from `/Wavetables` on the drive, loaded through Model-TG's sample system. Wave is
  the 8th machine, after the Sampler.
- OS browser locked to `/Wavetables` on the Wave track: folder created if missing, sub-folders allowed, going
  above refused (5 hooks, notes/52 §3quater, plus a 6th, `wt_cursor`, for prefetch). Model-TG patched **in memory at boot** (its tweak is unchanged) so a
  table loads on a non-Sampler track, with or without a Sampler in the kit, and stays protected.
- **Clean 16-bit, no bit reduction** (listening test: no audible difference). No post-oscillator filtering tricks.
- Anti-aliasing: **band-limited copies per half-octave**, built when a table loads (not at power-up), blending the
  two nearest by pitch. Built in a shared ~22.5 MB pool in 0x46800000..0x47F00000 (free above Model-TG); high
  notes first; small steps (~1.1 ms) so the UI stays smooth; **prefetch** once the browser cursor rests 300 ms on a file.
- Per-sample position glide, DC blocker. Cost ≈ 1.46 TONE per voice in emulation (see the performance section; the "46%" quoted earlier is a six-voice estimate, not a measurement).
- Two filters, as on Acid-TG: Acid's low-pass inside the machine, then Model-TG's per-track filter.
- Knobs:

| | Main knob | Hold MACHINE + |
|---|---|---|
| COLOR | Position in the table | **Env Pos** (new hidden param, id 0x0a; 0 = none, up = note starts further in and glides back to COLOR) |
| SHAPE | Filter envelope (64 = none, bipolar) | — |
| SWEEP | Cutoff (Acid low-pass) | Model-TG filter cutoff |
| CONTOUR | Resonance | Model-TG resonance |
| DECAY | Volume + length of both envelopes | Attack (Model-TG) |

Results on Kevin's machine (2026-10-09):
- Our code created `/Wavetables` on the drive: works.
- The "glitchy, cyclic thinning" sound had **one confirmed cause: Elektron Transfer resamples 44.1 kHz WAVs to
  48 kHz on upload.** A 256-wave table took 1.088 MiB on the drive instead of 1.0 MiB, so each 2048-point wave
  became ~2229 points and Wave's 2048-point slicing drifted. Copies relabelled as 48 kHz (same samples, nothing
  resampled) upload unconverted, and **the glitch was gone** on the machine.
- A "table moving during the note" report came from an LFO Kevin had on Env Pos; no bug.
- Env Pos, COLOR and the filter envelope measured working in emulation (Pulsar table). The hold-MACHINE+COLOR knob
  path was only checked by reading code. Not tested: save/reload of Env Pos (stored in a word Model-TG already
  saves); an LFO on Env Pos probably won't survive a project reload.

## Wave performance: everything known (read before optimizing)

The next task is performance work on Wave. Below: the architecture, what was measured (with how), what was
already optimized, what is open. `[measured]` = numbers from a run; `[estimate]` = computed, never measured;
`[hardware]` = reported by Kevin from his machine.

### Platform and budget

- ColdFire MCF54415 (V4e), 250 MHz, 8 KB I-cache + 8 KB D-cache, EMAC (`mac.l`, accumulators). Audio interrupt
  every 32 frames at 48 kHz = 0.667 ms = **166,667 cycles per block**. The repo's model (notes/27, 28, 31 §7) is
  **1.54 cycles per instruction** plus ~15 cycles per 16-byte line read or written in SDRAM.
- Whole-machine reference (notes/31 §7, 6 tracks playing): ~45,500 instructions in the voice loop ≈ 43–45% of a
  block; mixing and send effects ≈ 30% (notes/23 §6bis); Model-TG estimates delay+reverb at ~12% even idle.
  Model-TG has a load governor (notes/36). Any per-voice saving counts ×6 (all six tracks can be Wave).
- Measurement method used everywhere in the repo: count instructions in Unicorn over the real voice loop
  (`UC_HOOK_CODE`), steady state, often "loop with the voice minus the same loop without it" (notes/43 §8, 51 §8).
  These are instructions, not cycles: cache misses and EMAC stalls aren't counted. On the machine, Model-TG's
  profiling firmware (notes/31 §7: `gen_syntakt_engines.py --tg --meter --profile`, timer `0xfc07800c`, peak/average
  on the MACHINES screen) gives real numbers; it has not been run with Wave yet.

### Engine layout (`tools/machines/wavetable/wt.c`)

The voice loop calls `wt_update(pmod, v, p)` and then `wt_render(out, v)` once per block per track (contract: notes/14).
- `wt_update` (per block): knob reads, Model-TG pending-sample handover, note → phase increment (`PITCH_TAB`),
  copy index `cpos` (2 copies per octave above `COPY_N0`), position target (COLOR + Env Pos × envelope), filter
  coefficients of Acid's ladder (G table, G², G³, G⁴, **two `recip_q28` divisions** for D1/Ds), envelope decay.
- `wt_render` (per sample, 32×): silent-voice early exit (zeros the block); position glided sample by sample
  (`ps += dp`); for **two copies** (the two half-octave copies around the note, blended by `cw`) × **two frames**
  (position blend `pw`) it calls `at()` = **2 int16 reads + linear interpolation** each, so up to **4 `at()` = 8 table
  reads per sample**, from 4 different 2^lg-point frames; then DC blocker (`DC_R`, ~10 Hz); then Acid's 4-pole ZDF
  ladder with the 3-segment knee (one `qmac4`, one `qmac2`, a branch, 4 one-pole stages with `qmul`); output
  `shl_sat`. Then the stock amp chain (`AMP_ENV`, `VCA`, `PUNCH` at OS addresses), then Model-TG's stage (Attack,
  filter skipped when open with no resonance, resampling).
- `qmul`/`qmac2`/`qmac4` use EMAC inline asm on target and int64 in the HOST build (`wt_host.c`), which gives the
  same integer results.
- If a copy isn't ready, `cb[k]` points at the raw table (`sh = 0`); copies are stored at half level (`sh = 1`).
- Copy builder, off the audio path: `wt_tick()` runs once per audio block from **Model-TG's LED task** (`led_hook`,
  UI side, level 0). `step()` does ~`BUDGET` = 3072 FFT butterflies per call (comment says "~0.6 ms"; measured
  ~1.1 ms worst case). It is integer-only, **no EMAC** (`m15` Q15 multiplies), two frames per complex FFT (one real,
  one imaginary), stages LOAD → FWD → SPLIT → BUILD → INV → STORE, in two passes: pass 0 = copies ≤ 512 points
  (`CHEAP_LG 9`, the high notes, where grit is audible), pass 1 = the big copies. `publish()` turns on a pass's
  copies at the next block. Pool allocation: `plan()` tries 8, then 4, then 2 points per harmonic until `gap()` finds
  room; tracks on the same table share one allocation (`al[]`, refcounted). Prefetch: pseudo-track `PF` = 6,
  `DEBOUNCE` 450 blocks (300 ms), `PF_MAX` 4 MB, loads via Model-TG's polite mode (`pd_mode 1`), `adopt()` hands
  the work to the track on YES.

### Measurements

| What | Result | How |
|---|---|---|
| Voice loop, one Wave track (whole loop, 1 track) | **9,799 instructions/block** `[measured]` | `build/wt-proof/cost_fw.py`: real firmware in Unicorn, Model-TG + Wave, 64-frame test table, note 48, SHAPE 120 (filter env moving), SWEEP 80, CONTOUR 60, DECAY 60, avg of 10 blocks after 6. Raw table: `wt_tick` not run, so no copies; with `cw` ≠ 0 the 4 `at()` all read the raw table |
| Same harness, TONE on that track | 7,183 `[measured]` | same script |
| Net per voice (minus loop overhead) | Wave ≈ 8,300, i.e. **≈ 1.46× TONE** `[estimate]` | overhead 7,183 − 5,669 (TONE net with Model-TG, notes/51 §8) ≈ 1,514 |
| One Wave voice in % of a block | ≈ 7.6% net, ≈ 9% gross `[estimate]` | ×1.54 / 166,667 |
| Six Wave voices | ≈ 45–55% of a block for the voices alone `[estimate]` | not measured |
| "CPU at 46%" | said in chat on 2026-10-09; matches the six-voice estimate above (6 × 8,300 × 1.54 / 166,667), not a measurement | — |
| Acid for comparison | 4,471 avg (0.85 TONE), filter open 2,402, worst 5,604; with Model-TG 0.43–0.91 TONE | notes/51 §8 |
| Copy step (UI side) | 3.2 ms first build → **271,148 instructions worst case, ~1.1 ms** now `[measured, emulator]` | `test_wavetable.py` (TOUT OK on 2026-10-10) |
| Copies ready, 256-wave table | ~2.9 s all; **high notes clean after ~0.66 s** (64 waves: ~0.17 s) `[measured on HOST engine]` | `esw_host.py`, `timing_host.py` |
| Forward analysis alone | ~0.3 s for 256 waves `[estimate]` | butterfly count |
| Copies memory | 256-wave table at full quality ≈ 7.4 MB; pool ≈ 22.5 MB shared → ~3 such tables at once | `esw_host.py` |
| Copy accuracy | firmware copies byte-identical to HOST; HOST vs float reference −78 dB | `test_wavetable.py` |
| Anti-grit | prototype: fold-back −3 dB → −55 dB at C7; HOST: −53 to −56 dB C4–C7; firmware = HOST (−16 → −27 dB on a short C7 render, meter-limited) | `dbg_fw.py`, `dbg_host8.py` |
| On the machine | no crackle or overload reported; the only glitch had another cause (Transfer resampling) `[hardware]` | Kevin, 2026-10-09 |
| D-cache | ~6 lines/block at 65 Hz, ~46 at 1 kHz for two frames, vs 94–214 for a Syntakt voice `[estimate, notes/52 §6]`; the current code reads 4 frames | never measured |

### Already optimized (done, in the committed code)

- Copy builder: two frames per FFT, smaller steps (3.2 → ~1.1 ms per UI-side step), high-note copies first (pass 0),
  per-pass publishing, a shared pool instead of 3.75 MB per track, one set of copies per table shared across tracks,
  prefetch from the browser cursor (300 ms debounce, cancel/restart; a "return within 300 ms never restarts" bug
  was fixed).
- Silent voice: early exit that writes zeros (same idea as notes/23 for stock voices).
- Filter coefficients per block, not per sample (as Acid).
- Position glide per sample (`ps += dp`) was a **quality fix** (stepping clicks at high Env Pos) that added a
  little per-sample work.

### Not done / ideas raised but not implemented

- **Option B**: lighter copies for big tables (4 points per harmonic instead of 8): full build ~2.1 s instead of
  ~2.9 s `[estimate]`. `plan()` already falls back to 4 and 2 when the pool is full.
- **Option C**: precompute copies on the computer (web converter before Transfer): no wait at all, but files ~15×
  larger and a new web tool. Kept as a later idea.
- **Render-path ideas, not tried, never measured** (from reading the code; check each one against the
  emulation proof and by ear):
  - skip the second copy (2 of the 4 `at()`) when `cw` is 0 or both `cb` point at the same buffer (e.g. raw table);
  - skip the frame blend when the position sits on a frame (`pw` = 0) or doesn't move;
  - bypass the ladder when the filter is fully open with no resonance and no envelope, as Model-TG does (Acid with
    the filter open costs 0.45 TONE vs 0.85);
  - move the two `recip_q28` divisions out of `wt_update` when cutoff and resonance haven't changed;
  - hoist per-block constants out of `at()` (mask, shifts), EMAC for the interpolations;
  - D-cache: 4 frames read per sample at random phase; consider memory layout of copies.
- Fix A (Transfer-converted tables) adds a resampling step to the copy builder: it costs on the UI side, not in
  the audio path.
- No hardware CPU profile of Wave yet: run Model-TG's profiling firmware with 1 and 6 Wave tracks.

### Harnesses for perf work

- `tools/emu/test_wavetable.py` (committed): the full proof; must stay green after any optimization (copies
  byte-identical to HOST, startup patches, playback). ~5 min.
- `tools/emu/wt_host.c` + the HOST build of `wt.c`: same integer engine on the PC, used for timing and renders.
- `build/wt-proof/` (from `handoff/wt-proof/`, git-ignored once copied): `cost_fw.py` (instructions per block, Wave vs TONE),
  `timing_host.py` and `esw_host.py` (copy timing and pool size on real tables; they point at Kevin's
  `~/Downloads/Echo+Sound+Works...` paths), `render_fw.py` (firmware renders before/after), `ab_host.py` (raw vs
  copies A/B), `dbg_fw.py` (which memory the firmware reads), `knobs_fw.py`, `held_fw.py`, `hold_fw.py` (knob,
  Env Pos and held-layer checks), `test_wt_browser.py`, `test_wt_select.py` (browser and Model-TG patch proofs),
  `dis.sh` (disassembly; needs `mainos.bin` extracted from the official image). Run from the repo root; they import
  from `tools/` and `tools/emu/`, and some from `build/wt-proto/` (`wt_chain.py`, the float prototype). Several
  used a `.venv/bin/python` with unicorn + numpy.
- Compare cost the repo's way: TONE as the unit, with and without Model-TG, first block / average / maximum,
  on several settings (filter open/closed, Env Pos moving, copies ready vs raw, high/low notes), as in notes/51 §8.

## Next steps

0. **Performance work on Wave** (the next agent's assignment, see the section above). Measure first (the repo's
   way, plus Model-TG's profiler on the machine), change, re-measure, keep `test_wavetable.py` green, let Kevin
   judge by ear. Record figures in `notes/52` (French).

Then, in the order agreed with Kevin before the handoff:

1. **Fix A**: Wave detects Transfer-converted tables (length = a whole number of ~2229.1-point waves) and resamples
   each wave back to 2048 points when building the copies, so Serum/Vital files work straight from Transfer.
2. Write the 2026-10-09 findings into `notes/52` (in French): conversion cause, Env Pos layer, filter envelope,
   prefetch, pool.
3. Flasher and docs per AGENTS.md: `FEATURES` entry (`"status": "experimental"`), regenerate `tweaks.js` and
   `REF_MAINOS`, flasher texts en+fr, guide section en+fr (warn about the Transfer conversion until fix A ships),
   release notes, README row, PROVENANCE, BUILD.md.
4. Full validation (list in AGENTS.md), then a draft PR fork → origin; it depends on #65/#66.
5. Optionally, a PR for `acid-syntakt` (its full `test_acid --syntakt` run was skipped; notes/51 §11 says so).

## Hardware and drive access

- Local flasher: `python3 -m http.server 8000 -d docs` → <http://127.0.0.1:8000/flasher/>, "custom file" sends a
  `.syx` as-is. Close that tab (or the whole browser) before other MIDI tools: Web MIDI holds the port.
- Model-TG's Transfer mode (**Device Config › Transfer › SMP**) makes the Cycles appear as a Model:Samples.
  Then `elektroid-cli` can `elektron:sample:ls`, `mkdir` and `ul`; deletes are refused by the device (use
  Elektron Transfer). Wave can only load tables in normal mode.
- On Kevin's drive: relabelled tables in `/Wavetables/ESW 48k` and `/Wavetables/{Analog,Spectral,Digital}`; the
  old converted `Echo+Sound+Works+-+Modular` and `Make Noise 0-Coast Wavetable Pack` folders are still there.

## What is where

- `HANDOFF.md` (this file) and `handoff/` on the `handoff` branch: toolchain recipe (`toolchain/Containerfile`,
  `toolchain/mc16`), emulation probes (`wt-proof/*.py`, `wt_browser.S`, `dis.sh`) and the float prototype
  (`wt-proto/wt_chain.py`). Some probes point at Kevin's local wavetable files (`/home/kevin/Downloads/...`): change
  the path to any 2048-point-per-frame WAV table. `dis.sh` needs `mainos.bin`, extracted from the official image.
- The facts themselves are also in the repo, in French: `notes/52` §9–§12 and `BUILD.md` ("Machine Wave").
- Not on GitHub, on purpose: the session transcripts and listening renders (Kevin keeps them privately; the
  transcripts may quote firmware bytes) and every firmware image. Ask Kevin if you need a detail from a past session.
