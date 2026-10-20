# Emulation rigs and the proofs to copy

All under `tools/emu/` (French docstrings: read them, they list the OS addresses each rig runs).

## Shared rigs

| Module | Runs | Use for |
|---|---|---|
| `mcengine.py` (`Engine`) | the real voice loop `0x400a7d4a`, block by block (32 frames, 48 kHz); `render`, `solo`, `count_instructions`, payload code | machines, DSP, per-voice cost |
| `seqrig.py` | the real audio interrupt body with sequencer events (`0x400548ce`, queue `0x4009203c`, live notes `0x4005894a`), smoothing, LFO, voice loop, velocity gain, mixer | anything triggered by trigs, LEN, slides, live notes |
| `emac.py` | exact EMAC (signed fractional MACSR `0xa0`), intercepting each EMAC instruction | any audio code |
| `stengine.py` + `syntakt.py` | the Syntakt DSP program (section 7) and its 8-voice loop | Syntakt engine ports (exact sample comparison) |
| `test_sdvintage.py` (`T`) | helpers: `main_os_from_syx`, `apply`, f0/RMS/filters | imported by most proofs |

## Proofs by subsystem (copy the closest)

| Subsystem | Proof | Notes |
|---|---|---|
| Keys, holds, grid view, `UIStates` | `test_trig_hold.py` | 33 |
| Encoders, knob → descriptor, value windows | `lofi_ui.py`, `test_level_pan.py` | 55, 44 |
| Screen drawing, fonts, sprites | `test_boot_anim.py`, `test_multiline_browser.py`, `test_level_pan.py` | 39, 40, 44 |
| Front-panel LEDs interrupt | `test_trigless_dim.py` | 45 |
| Tempo, MIDI clock, LFO | `test_tempo_max.py`, `test_lfo_plus.py` | 38, 56 |
| Sequencer, retrig, arpeggiator | `test_arp.py`, `test_acid.py` (seqrig) | 32, 54 |
| Added machines | `test_macro.py`, `test_acid.py`, `test_acid_combos.py`, `test_macro_syntakt.py` | 43, 50, 54 |
| Syntakt engines | `test_syntakt_machines.py`, `test_sdvintage_exact.py`, `test_model_tg_syntakt.py` | 17–22, 31 |
| Per-track audio after Volume + Dist | `test_track_filter.py` | 47 |
| Load governor, idle voices, SRAM | `test_governor.py`, `test_idle.py`, `test_sram_code.py`, `test_sram_scratch.py`, `test_meter.py` | 23, 25–30, 36 |
| Model-TG and add-ons | `test_model_tg.py`, `test_sample_preview.py` | 31, 46 |
| USB audio stream | `test_usb_in.py` | 35 |
| MIDI routing, settings block | `test_midi_thru.py` | 53 |
| Update checks, Samples packing | `test_crossflash_samples.py`, `test_mods_for_samples.py` | 41, 57 |

