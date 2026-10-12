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

## Status (2026-10-12): M2 done and tried on the machine; Wave fixed and extended

- **SMP switch** (notes/55 §8): verified on Kevin's Model:Cycles with `amidi` probes (ping 27 → `0F 01` → 25 with the
  35-command list, readdir/mkdir/open/write/close, `0F 00` → 27), then the Convert page in a driven Chromium.
- **Convert page** (notes/53 §12): it picked Linux's "Midi Through" port (fixed: the machine's port by name, never
  "Through"); 8 KB SysEx blocks get lost from Chrome on Linux (2 KB there via `sampleBlock()`, 8 KB elsewhere; Kevin
  sent 3 MB files with 8 KB blocks on Windows). Each write carries its byte offset (`opts.blockBytes`).
- **Wave on hardware** (notes/54, dated sections): the machine byte was read at +0x38 instead of +38 (decimal, as
  Model-TG) — the track was never recognised; the file length assumed a 16-byte trailer the +Drive doesn't have. Both
  fixed; locked browser confirmed on the machine.
- **YES loads the table** (Model-TG's `preset_fail_hook` method: `0x400a6732` → `wt_yes`, `pea` at `0x400a6752` →
  `wt_msg`, `0x400a6602` → `wt_parse`); popup "Table loaded / to track N" or the reason. Kevin: "perfect".
- **Table memory**: token `W` + key (8 hex) + hash (6 hex) in the sound name (`wt_stamp`, `wt_snd` = Model-TG's
  `sound_obj`); `wt_tick` in the 5 empty LedHandler slots reloads via `0x4007de78(key, &entry)` at IPL 0, once per
  audio block. Proven in emulation, and **works on Kevin's machine** (YES, power cycle, project reload; 2026-10-12).
- Toolchain on Linux: the `mc-m68k-elf:16.2` podman image (`handoff/toolchain/Containerfile`, `handoff` branch); the
  emu tests run on the host `.venv` (unicorn, numpy). `test_wavetable.py` TOUT OK.

Next: M3 (merged generator: Syntakt engines + Acid + Wave, flasher
card back, release notes).

## Known loose ends

- The stray debug line seen with the old Windows harness does not appear when importing `test_wavetable` on Linux:
  it came from that harness, not from `tools/`.
- Release notes: not written for Wave on this branch (Wave is not in the flasher; release 1.35 still describes the old
  Wave + Model-TG card). Do them with M3.
- `vendor/Model-TG` is a git-ignored clone (gitignored via `vendor/`); needed to read the SMP reference.
- Do NOT commit the `build/` toolchain helpers or any `.syx`.
