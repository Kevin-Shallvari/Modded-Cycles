# Handoff — Wave standalone + the "added machines" combination

Working handoff (English, like `handoff-c-library.md`) for the next session. Read the repo's
[`AGENTS.md`](AGENTS.md) and [`notes/52`](notes/52-etude-tables-d-ondes.md) first.

## Goal
A **Model-TG-free** Model:Cycles firmware containing a **Syntakt engine (or a few) + Acid + Wave**:
Wave picks its wavetable in the **stock OS browser**, **reads it itself** from `/Wavetables` into its own
SDRAM buffer, and plays it. Dropping Model-TG frees ~88 KB and makes the combination fit.

## Branch / state
- Work on **`wavetable-machine`** (Wave lives there: `36-wavetable-tg.json`, `tools/gen_wavetable.py`,
  `tools/machines/wavetable/wt.c`, `notes/52`, `notes/53`). Never `model-groove` (that line has the *old* Wave).
- **Repo is green right now.** An engine decoupling was started then reverted to keep it green — see "First step".

## Decisions locked (with the user)
1. **Standalone** (no Model-TG).
2. **File format (a)**: the converter emits the **sample container** (64-byte header + big-endian PCM + 16-byte
   trailer), so **Wave's engine is unchanged**; only the loader differs.
3. **The SMP glue is borrowed** (see §"Key finding") so the transfer stays the familiar **SMP route**
   (Elektron Transfer / the Convert page upload a WAV → the stock sample FS stores the container).
4. **Upload trigger**: the Convert page **auto-flips** CYC→SMP before sending, plus a **manual reset button**.
5. **Opcode table: hand-written** (35 bytes) — option (b) (read it from the user's Samples OS) is out: not every
   user has a Model:Samples.
6. **Phasing**: Milestone 1 (Wave standalone) + Milestone 2 (SMP glue) first, then Milestone 3 (the merge).

## Key findings (verified against the images — do not re-derive)
- **The sample filesystem is STOCK Elektron code, already in the Cycles OS 1.13.** Model-TG carries none of it
  (its 88 KB blob has zero `MidiRpcFs` code). The Cycles FS handler at `0x40084ade` copies a **raw opcode table**
  `0x40112d40` (`0x14/0x15/0x16/…/0x43/0x44/0x45`); the **sample table** (`0x10/0x11/0x12/…/0x40/0x41/0x42`,
  35 bytes, at `0x4010da48` in the Samples OS) is the only thing missing.
- **Model-TG's SMP = 3 patches**: `0x40084b8e` → its hook (chooses table + id + name from a flag), `0x40084be3`
  (name pointer), `0x40084c14` (id 27/25). Its identity flag is `0x401b78fc` (0=CYC, 1=SMP), volatile, read on
  every ping → a **soft switch, no USB re-enumeration**.
- **35-byte sample opcode table** (hand-write this): `01 02 03 05 04 50 52 51 10 13 11 12 20 21 22 23 30 31 32
  36 40 41 42 46 53 54 55 56 57 58 59 5a 5b 5c 5d`.
- **Stock file-read API** (task context only): open `0x4007e4f4(&handle16,&stream)` → size `0x4007eb16(&stream)`
  → read `0x4007baaa(buf,len,&stream)` → close `0x4007bc1c(&stream)`. Or by path: `0x4007bc5e`/`0x4007baaa`/`0x4007bc1c`.
  The 16-byte browser handle (`getEntry` `0x4007cdd4`): `+0` inode, `+4` hash, `+8` size, `+12` 4th word.
- **Preset-load hook site**: `0x400a6426` (inside `0x400a63ac`) = `jsr 0x400a3052` (6 B) — the stock preset read
  (which enforces 48..160 bytes). The **pad-note hook** is `0x4008171e` (stock `link.w %fp,#-104 ; moveq #127,%d0`).
- **Track accessor** (stock kit): `kit=*(u32*)0x40a78888; sound=kit+28+100*t; machine=*(u8*)(sound+0x38)`.
- **Free buffer**: `0x46800000..0x47F00000` (~23 MB), cached view, 16-byte aligned, pointers below `0x48000000`.
  A converted table is ~8.5 KB (one cycle) to ~2.3 MB (256 frames); 6 tracks × 2.3 MB ≈ 14 MB fits.
- **Space**: without Model-TG the append anchor is `0x401aa140` → ~352 KB free (vs ~263 KB after Model-TG).
- **+Drive format**: after an SMP upload the file on the +Drive is the **container** (64+BE16+16), not a RIFF WAV.

## The plan

### Milestone 1 — Wave standalone (the crux)
1. **The loader** (new asm in `glue_asm`, `tools/gen_wavetable.py`): `wt_parse` at `0x400a6426` records the
   selected file's 16-byte handle per track; `wt_note` at `0x4008171e` reads it on the pad press via the stock
   API into `0x46800000 + t*0x300000`, sets our `wt_base[t] = buf+64` and `wt_count[t] = (size-80)/2`, then
   replays `link.w %fp,#-104 ; moveq #127,%d0 ; jmp 0x40081724`. Our own `wt_ours` (stock kit layout above).
   Keep the 5 browser hooks (`wt_open`/`wt_close`/`wt_yes_up`/`wt_key_up`/`wt_home`, OS addresses).
2. **Engine (`wt.c`)**: read `WT_BASE[t]`/`WT_COUNT[t]` (per-track globals filled by the loader) instead of
   Model-TG's `track_slot`/`slot_base`/`slot_count`. (A first cut compiled at 5 294 o — redo it, then land the
   loader in the same change so it stays functional.) Update `tools/emu/wt_host.c` to `host_wt_base`/`host_wt_count`.
3. **Generator**: drop `find_tg`, the `wt_boot` patches of `preset_fail_hook`/`name_probe`, `wt_or_any`, `wt_np`,
   `wt_is_ours`-via-`sound_obj`, and `dispatch_tg_asm`. Use the **alone** boot hook (replace `gx.HOOK` `0x400004b2`)
   and the alone dispatch (Acid-alone style: no voice detour; the relocated `rnd` table routes). No `requires`.
4. **Proof**: rewrite `tools/emu/test_wavetable.py` (browser → loader → buffer → playback, 6 tracks, mixed
   machines). **Hardware test by Kevin.**
- **First step**: disassemble the stock preset-read path (`0x400a2a28`…`0x400a2ab0`) to lock the exact
  `0x4007e4f4`/`0x4007eb16`/`0x4007baaa`/`0x4007bc1c` argument conventions, then write the loader.

### Milestone 2 — the SMP glue
1. A new small generator: the 35-byte sample opcode table + a hook at `0x40084b8e` (choose sample table + id 25 +
   "Model Samples" from our flag, else the stock raw table + id 27 + "Model Cycles"; re-enter stock at `0x40084bde`).
2. Our flag (a free word) + a **MIDI trigger**: a new opcode in the SysEx dispatch (`0x400812f6` → product-`0x10`)
   that writes the flag.
3. `docs/convert/index.html`: **auto-flip** to SMP before a transfer + a **manual "Set CYC/SMP"** fallback button.
   `docs/flasher/flasher.js` already has the sample-FS transfer (notes/53) — unchanged.
4. Proof (the ping answers 25; the stock handler accepts the sample commands; a WAV upload stores the container).

### Milestone 3 — the merged generator
Generalize `tools/gen_syntakt_engines.py` to also take our engines (Acid, Wave): a **shared payload allocator**
(code + BSS + `TABLES_AT` — the bulk), one `detours_asm(n, images, firsts)` with the union of `bridge_update_*`
and `acid_update`/`wt_update`, one append/pack/stub, **keep the governor** (`tools/gov_asm.py`), reconcile the
art/icon schemes. New tweaks + a unified flasher **"added machines"** picker (Syntakt engines + Acid + Wave, no
Model-TG) + `REF_MAINOS` + proofs + docs. Without Model-TG it fits (~352 KB free; MACRO still won't).

## Key files
- `tools/gen_wavetable.py` (651 lines: `find_tg`, `glue_asm`, `compile_machine`, `build_tweak`, `tables_h`).
- `tools/machines/wavetable/wt.c` (the engine; Model-TG macros at the top, `wt_update` slot block, `wt_render` base).
- `tools/emu/wt_host.c`, `tools/emu/test_wavetable.py` (the proof).
- `tools/gen_syntakt_engines.py` (`gs.LAYOUT`/`set_base`/`detours_asm`/`LAYOUT`, `PAY_ALONE`/`PAY_TG`), `tools/gov_asm.py`.
- `docs/convert/index.html`, `docs/flasher/flasher.js` (notes/53).
- Notes: `notes/52` (Wave), `notes/53` (transfer), `notes/46` (browser/preset path), `notes/43`/`51`/`20` (added machines).

## Repo state
Clean and green: `gen_wavetable --check` passes, tree clean, on `wavetable-machine`. The earlier flasher
registration of Wave is committed (`220551c`). The engine-decoupling experiment was reverted (see "First step").
