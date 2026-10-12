# Handoff — SMP glue folded into Wave (M2) + toolchain

Branch `wavetable-machine`. English, like `handoff-c-library.md` / `handoff-wave-standalone.md`.

## Where we are

- **M1 done** (Wave standalone, no Model-TG): `tools/gen_wavetable.py`, `tools/machines/wavetable/wt.c`,
  `tools/emu/test_wavetable.py`, `tweaks/model-cycles_OS1.13/36-wavetable.json` (id `wavetable`, order 36).
- **Exact toolchain recovered** and used to regenerate the JSON: `m68k-elf-gcc` **16.2.0** (Homebrew, in WSL at
  `/home/linuxbrew/.linuxbrew/bin`) + Ubuntu 22.04 `binutils-m68k-linux-gnu` **2.38** (`.deb` from
  `pool/universe/b/binutils/`, extracted to `/home/kevin/.mc/root`). Wrapper prefix `~/.mc/bin/mc-`
  (`mc-gcc = m68k-elf-gcc -B~/.mc/as/`, `as`/`ld`/`nm`/`objcopy`/`objdump` = 2.38). Run the generators with:
  `M68K_CROSS=/home/kevin/.mc/bin/mc- LD_LIBRARY_PATH=/home/kevin/.mc/root/usr/lib/x86_64-linux-gnu python3 …`
  Validated by reproducing `20-sdvintage-snare.json` and `22-sdvintage-7th.json` **byte for byte**.
- **M2 in progress**: the SMP glue is **folded into the Wave tweak** (user's choice). Generator + proof written;
  **the proof has NOT been re-run after the last fix** (see below). Page side and docs NOT done.

## M2 — what the SMP glue does (verified against Model-TG)

The Cycles OS only handles the **raw** file family; the Model:Samples advertises the **sample** family. Sites
(mirroring Model-TG, MIT, `vendor/Model-TG` @ `70b39dd`):

- `0x40084b8e` (6 B `487800222d48`) → `smp_id_hook`: identity reply list + name from `smp_mode`; re-enters `0x40084bde`.
- `0x40084c14` (6 B `721b4fef0028`) → `smp_id_hook2`: product 27/25; re-enters `0x40084c1a`.
- `0x40084be2` (4 B `401285c9`, the name `pea` immediate) → `smp_namebuf`.
- `0x4009249c` (4 B `400949d8`, **jsr target**) → `smp_rpc_type`: sample request type → raw twin.
- `0x40094c9a` (8 B `71aa00084fef0020`) → `smp_rpc_ot`: raw reply type → sample.
- `0x40148d44` (SysEx table slot `0x40148d08[15]`, was 0) → `smp_desc`: a trigger for command **0x0F**
  (`F0 00 20 3C 0F 00 <m> F7` sets `smp_mode = m`). Table indexed by `msg[4]` in the dispatch `0x400812f6`.
- `smp_map` = the **whole** family: `10→14 11→15 12→16 20→24 21→25 22→26 23→27 30→33 31→34 32→35 36→37 40→43
  41→44 42→45 46→47` + `00 00` (two zeros: `rpc_type` scans even indices, `rpc_ot` odd — both need a terminator).
  **This was the bug fixed last**: the first cut only had 3 pairs.
- 35-byte list (no `0x09`, so Transfer does not ask the stereo question → mono, legacy chunk size).

## Next move

1. **Re-run the proof**: `M68K_CROSS=… LD_LIBRARY_PATH=… python3 tools/emu/test_wavetable.py --cycles firmware/model-cycles_OS1.13.syx`.
   Fast harness (boot + SMP only, ~1 min) is at `C:\Users\Kevin\AppData\Local\Temp\opencode\smp_harness.py`
   (imports `test_wavetable`, calls `fw_tests` + `smp_tests`). Expect the `smp_map` (50 B) and the
   `rpc_type`/`rpc_ot` expectations (now 0x40→0x43, 0xC0→0xC3, 0xC7→0xC6) to pass. Then the full run (~6 min).
2. **Page side** (`docs/convert/index.html` + `docs/flasher/flasher.js`): before an upload, send the 0x0F trigger
   (SMP); add a manual "Set CYC/SMP" button. Read `notes/53` and `notes/37` for the SysEx framing.
3. **Docs/registration**: tweak `description` + module docstring (M2), `BUILD.md` hashes (the append grew to
   **12932 o**, so the three hashes there are stale), `notes/55-smp-sans-model-tg.md` (new) + `notes/README.md`,
   `PROVENANCE.md`. The flasher card stays **removed** until M3.
4. Re-run the no-firmware checks: `py_compile`, `gen_flasher_tweaks --check`, `ref_mainos --check` (the Wave JSON
   is not in the flasher, so both should stay green), `gen_wavetable --check`.

## Known loose ends

- A stray debug line appears when importing the emu modules in the harness (`id wavetable writes … pack …`,
  `symbols {…}`, then one line per write). **Not from a `print()`/`sys.stdout.write`** in `tools/` (grepped) — find
  and remove it before merging. It does **not** appear in `gen_wavetable.py`'s own output.
- `BUILD.md` Wave hashes are stale (JSON changed twice).
- `vendor/Model-TG` is a git-ignored clone (gitignored via `vendor/`); needed to read the SMP reference.
- Do NOT commit the `build/` toolchain helpers or any `.syx`.
