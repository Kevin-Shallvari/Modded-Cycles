# OS 1.13 map: decoded subsystems

Starting points only. Every address below is `[FAIT]` in the cited note, which holds the contract (registers,
arguments, what else calls it). Re-read the note before hooking anything, and check `REGISTRY.md` §4–5: a mod may
already detour it.

## Contents
- Memory and image
- Audio engine and voices
- Sequencer, events, tempo
- Keys, encoders, UI views
- Screen
- USB, MIDI, settings, update
- Free space and payloads

## Memory and image

| What | Address | Note |
|---|---|---|
| Section 3 base (`VA = off + BASE`) | `0x40000400` | 02, 09 |
| SRAM (internal, fast); 6 track render blocks, 32 × 32-bit, stride `0x80` | `0x80000000`; `0x80001858` | 03 §2, 26 |
| Smoothed parameter words (33 words k 0..32 × 6 tracks) | `0x8000100c` | 47 |
| DDR BSS/heap (zero in the image) | `0x404…`, `0x40a…`, `0x40f…` | 03 |
| End limit for the decompressed image + payloads | `0x40200000` (`build.END_LIMIT`) | 17, 50 |
| SDRAM payload (Syntakt engines, MACRO); Model-TG payload | `0x43000000`; `0x46700000` | 17, 31 |
| DMA timer 0 counter (135.168 MHz), event timestamps | `0xfc07000c` | 23, 33 |

## Audio engine and voices

| What | Address | Note |
|---|---|---|
| Audio interrupt body (counts, events, velocity, masks) | `0x40058ca0`..`0x40059382` | 32, 35 |
| Per-block audio function (smoothing, LFO, voice loop, velocity gain) | `0x4005979e` | 47, 56 |
| Parameter smoothing | `0x40058474` (called at `0x400597a8`) | 47 |
| Voice loop of the 6 tracks `(out, params, trig_mask, release_mask)` | `0x400a7d4a` (called at `0x4005981e`) | 14 §2, 43 |
| Machine `update` / `render` tables; update/render call site | `0x40118628` / `0x40118610`; `0x400a7dfe` | 14, 43 |
| Per-track halving loop in the voice loop | `0x400a7e2a`..`0x400a7e38` | 36 (`tools/voice_loop.py`) |
| Amp envelope, VCA, PUNCH (leaf functions of TONE's render) | `0x400a9252`, `0x400a9430`, `0x400a967a` | 14, 43 |
| Velocity gain; block accounting; mixer (level, pan, sends) | `0x40056d9c`; `0x40056ea8`; `0x400567ba` | 47 |
| Hook after Volume + Dist (per-track filter) | `0x40059852` | 47 |
| Parameter descriptors, 56 bytes each (+4 = k) | `0x4010dce0` | 18, 56 |
| 6 LFOs update; LFO state `0x40fde838 + 32 × track` | `0x40091ab2` | 38, 56 |
| Sound save (format 2, 100-byte record) | `0x4005afa0` | 47, 56 |
| Audio load: stock OS ≈ 77 % of each 0.67 ms block; governor | — | 23, 25, 30, 36 |

EMAC: the audio engine runs with `MACSR = 0xa0` (signed fractional). Unicorn gets it wrong: `tools/emu/emac.py`.

## Sequencer, events, tempo

| What | Address | Note |
|---|---|---|
| Sequencer event builder (musical time, one step = 5 400 000) | `0x400548ce` | 54 (`tools/emu/seqrig.py`) |
| Event queue | `0x4009203c` | 54 |
| Live notes (pads, keyboard) to the audio interrupt | `0x4005894a` | 46, 54 |
| Tempo pending / applied (1/120 BPM) | `0x40058bb4` / `0x40058b62` | 38 |
| Tempo display (1/120 BPM → BPM.d); TEMPO wheel | `0x4009602e`; `0x4003d4b8` | 38 |
| Incoming MIDI clock tempo (24 intervals) | `0x40080618` | 38 |
| Load checks resetting 120 BPM | `0x4005aab2`, `0x4005b3e8` | 38 |
| Retrig setup / repeats; unused saved byte +512 of the pattern track | — | 32 §4 |

## Keys, encoders, UI views

| What | Address | Note |
|---|---|---|
| Key debounce interrupt (1 kHz) → press/release events | `0x40059e64` → `0x4007fbde` | 33 |
| Key clock (120 Hz, hold events) | `0x4007f914` | 33 |
| `KeyEvent` constructor | `0x4007238c` | 33 |
| `PatternGridView::consumeKeyEvent` | `0x40022382` | 33 |
| `UIStates` singleton pointer; `setHold(bool)` | `0x40fe4218`; `0x4006b740` | 33 |
| Front-panel interrupt (PIT3, 12 kHz, 7 latches 74HC373) | — | 45 |
| UI task (priority 6) and its message jump table | `0x40007d46`, `0x40008108` | 44 |
| UI timer service (message 5, 30 Hz) | `0x400081f2` → `0x40090f48` | 44 |
| `MainScreenView` vtable; encoder handler (slot 17); draw (slot 4) | `0x400ffe20`; `0x4001aa4e`; `0x4001b22a` | 44 |
| Knob → parameter descriptor lookup; `ParameterPageView` vtable slot 124 | `0x4001e814` | 47, 55 |
| Preset browser (ModelsFileManager) ctor, draw (vtable `0x401183ec` slot 120) | `0x400a68fc`, `0x400a539c` | 40, 46 |
| LFO view constructor call | `0x4001c3dc` → `0x40025798` | 56 |

## Screen

| What | Address | Note |
|---|---|---|
| ST7565 128 × 64 on DSPI1, **y = 0 at the bottom**, x = 0 left | — | 39 §2 |
| Draw buffer / shown buffer pointers (1 024 bytes each) | `0x401492f0` / `0x401492f4` | 39 |
| Send changed 8 × 8 blocks then swap | `0x4008e622` | 39 |
| `Bitmap` constructor (sprite image +0x10, mask +0x14) | `0x40070172` | 14 §5, `tools/sprites.py` |
| Fonts: big / small (names, titles) | `0x40ea14dc` / `0x40ea14cc` | 40 |
| Boot animation task body | `0x40053a6c` | 39 |

## USB, MIDI, settings, update

| What | Address | Note |
|---|---|---|
| USB device controller and audio feeder | `0x400025xx`..`0x40003fxx` | 01, 04, 35 |
| Feeder hooks prime / dstoff / copy / token | `0x400027e8`, `0x400029e4`, `0x40002a06`, `0x40002a42` | 01, 13 |
| USB send of a block (called at `0x40059392`) | `0x40002912` | 35 (`tools/usb_steady.py`) |
| USB modes table (4 × 0x28); descriptors | `0x4013e544`; `0x4019b132`..`0x4019b3fd` | 04, 09 |
| Ring slot pointer `SLOT_BASE` | `0x404a05e8` | 01 |
| Global settings block (`COKI`, checksum `0x40094e24`) | `0x404e9b10` | 53 |
| MIDI OUT/THRU byte (raw, read by `0x40044df8`) | `0x404e9b50` | 53 |
| MIDI IN byte handler, MIDI OUT send | `0x400012cc`, `0x40001232` | 53 |
| Update check → HMAC; 32-byte model key constant | `0x4005a0e4` → `0x40052750`; `0x401296b2` | 41 |

## Free space and payloads

Do not read free space from this file: `tweaks/model-cycles_OS1.13/REGISTRY.md` is generated from the tweaks and
is the truth (freed sprite masks taken/free, 0xFF caves, payload chains, hooks, rewritten pointers). Payload
layouts: notes/17 (Syntakt engines at `0x43000000`), 31 (Model-TG), 50 (MACRO + engines, aPLib-compressed).
