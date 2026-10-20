---
name: mainos-reverse-engineering
description: Locates and decodes code and data in the Model:Cycles OS 1.13 MAIN OS (ColdFire MCF54415, big-endian) - extracting section 3 from the official .syx, disassembling with m68k binutils, finding callers and pointers (xrefs), UI strings, C++ vtables, and the already-decoded subsystem map from notes/. Use when a mod needs an OS address, a hook point, a data structure or the behaviour of an OS routine, or when checking an [HYP] claim.
---

# Reverse-engineering the MAIN OS

Section 3 of the official `.syx` is the MAIN OS, loaded at `VA = offset + 0x40000400`. All addresses in this repo
are OS 1.13 VAs. The official files live in `firmware/` (git-ignored, downloaded by Maxime from elektron.se);
never commit them or anything extracted from them, and never paste long dumps into notes or code.

## 1. Search what is already known (always first)

```sh
rg -n '0x4002238' notes/ tools/          # an address (drop the last digit to catch neighbours)
rg -n -i 'consumeKeyEvent|retrig' notes/ # a class, method or subsystem
```

[references/os-map.md](references/os-map.md) lists the decoded subsystems with their key addresses and the
note that proves each one. Read that note's section before reusing an address: it holds the calling contract.

## 2. Explore the image

`scripts/mainos.py` (standard library + m68k binutils) caches section 3 in `build/` and checks its SHA-256
against `tweaks/model-cycles_OS1.13/device.json`:

```sh
S=.agents/skills/mainos-reverse-engineering/scripts/mainos.py
python3 $S extract firmware/model-cycles_OS1.13.syx                 # build/mainos.bin
python3 $S extract firmware/model-cycles_OS1.13.syx --with arp      # same with tweaks applied (no payloads)
python3 $S dis build/mainos.bin 0x40022382 +0x100                    # ISA_C + EMAC mnemonics
python3 $S xrefs build/mainos.bin 0x40072490 --pcrel                 # jsr/jmp/lea/pointers + bsr/bra/(pc)
python3 $S strings build/mainos.bin 'TEMPO|BPM' --xrefs              # UI text -> code that draws it
python3 $S bytes build/mainos.bin 0x4002249c 6                       # stock bytes for an `old` check
python3 $S off 0x4002249c                                            # VA -> section-3 offset (tweak "off")
```

For decompilation, Ghidra with language `68000:BE:32:Coldfire`, raw import of the extracted `.bin` at base
`0x40000400`. Capstone does not decode ColdFire-only instructions (`byterev`, `mvs`, `mvz`, `mov3q`, EMAC).

## 3. Method

1. Start from something observable: a UI string, a known constant (tempo 300 BPM = 36000 in 1/120 BPM), a
   hardware register (`0xFCxxxxxx`, `tools/hw_periph_refs.py`), or a neighbour already in os-map.md.
2. Walk callers with `xrefs`, callees by reading `jsr` targets. C++ objects: the first long of an object is its
   vtable; a method called as `movea.l (a0),a1 ; movea.l N(a1),a1 ; jsr (a1)` is slot `N/4`. Tables of 32-bit
   pointers into code are vtables or dispatch tables.
3. Confirm by running the OS's own code in Unicorn (skill `emulation-proofs`) rather than by reading alone:
   the OS follows the m68k-elf C ABI (args on the stack from `4(sp)`, every result in `d0`, **pointers too**,
   `d2-d7/a2-a6` callee-saved; notes/42 §6), but hand-written DSP code ignores it.
4. Record everything in the note with certainty tags: `[FAIT]` read in code or decoded byte for byte, `[HYP]`
   hypothesis, `[FAIT en émulation]` run in the emulator. A table per routine: address, role, inputs, outputs.

## 4. Traps

- The screen counts y from the **bottom** (notes/39 §2): the first boot animation shipped upside down.
- Big `0xFF` blocks are sprite masks, not free caves (`tools/sprites.py`); `registry.py` lists what is free.
- A mod already in `tweaks/` may have moved the code you are reading: check `REGISTRY.md` §4 (hooks) and §5
  (rewritten pointers) for your address, and disassemble with `--with <ids>` of the mods it can be built with.
- The OS keeps working state in SRAM at `0x80000000` (fast RAM) and the 6 render blocks at `0x80001858`; DDR
  addresses `0x404…`/`0x40a…`/`0x40f…` are BSS/heap and are zero in the image.
- Unicorn's EMAC is wrong in signed fractional mode (`MACSR = 0xa0`, the audio engine's): use `tools/emu/emac.py`.
- The Model:Samples OS differs; never take an address from it (decision of notes/57).
