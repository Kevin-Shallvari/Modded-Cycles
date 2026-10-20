---
name: coldfire-patching
description: Designs and writes ColdFire (MCF54415, ISA_C + EMAC, big-endian) code that runs inside the Model:Cycles OS 1.13 - hook styles (call replacement, detour with padding, in-place rewrite, pointer/vtable slot), stub register contracts, choosing free space (freed sprite masks, caves, SDRAM payload), saved-settings bytes, m68k-elf toolchain and linker scripts, interrupt and audio-load safety. Use when a mod needs new code or new data in the firmware, when editing tools/machines/*, or when reviewing a hook.
---

# Patching ColdFire code into the OS

Origin of every rule: notes/05 (method, crashes it came from) and notes/03 (platform). Encodings and ISA traps:
[references/isa-cheatsheet.md](references/isa-cheatsheet.md). Free space, payloads and settings storage:
[references/free-space.md](references/free-space.md).

## 1. Choose the lightest hook (in this order)

1. **Data or immediate change, in place** (tempo-max: bounds, constants). No code, no free space.
2. **Rewrite the routine in place** when the new code fits in the old bytes (boot-anim's 690-byte task body,
   trig-preview's 3 bytes, `tools/voice_loop.py`). Same entry, same exits, same registers out.
3. **Call replacement**: an existing `jsr abs.l target` (6 bytes, `4eb9 aaaaaaaa`) becomes `jsr stub`; the stub
   does its work and returns what `target` returned (trig-hold's three hooks). No padding, nothing moved.
4. **Pointer or vtable slot**: rewrite one 32-bit pointer (a C++ vtable slot, a callback, a dispatch table) to a
   wrapper that calls the original. `REGISTRY.md` §5 lists slots other mods already rewrote.
5. **Detour**: overwrite ≥ 6 bytes with `jmp stub` + `nop` (`4e71`) padding; the stub replays the moved
   instructions exactly, adds its logic, and `jmp`s back to the next intact instruction.

For 3–5, check `REGISTRY.md` §4: if another mod hooks the same address, either write the identical bytes
(shared writers such as `tools/usb_steady.py`) or chain through its stub, or declare `conflicts`.

## 2. Contract of a stub (write it at the top of the `.S`)

- Entry state: which registers hold what, what is on the stack, whether it runs in an interrupt.
- Exit state: every register the following code reads, condition codes if a branch follows, `d0` result.
- Clobbers: save everything else with `lea -N(sp),sp ; movem.l d0-d2/a0-a1,(sp)` and the reverse
  (ColdFire `movem` has no `-(sp)`/`(sp)+` forms).
- Calls into the OS follow the m68k-elf ABI: args pushed right to left, result in `d0` (pointers too), `d0-d1/a0-a1`
  clobbered, `d2-d7/a2-a6` preserved. C code calling the OS must be built with **m68k-elf-gcc**, never
  `m68k-linux-gnu-gcc` (SVR4 ABI reads pointer results from `a0`: notes/42 §6).

## 3. Safety rules (each one came from a crash)

- Detour targets and data addresses come from `nm` of the linked ELF, never typed (R3: frozen logo).
- No branch, jump or stored pointer may land **inside** a detour's padding (R4: `EXCEPTION VEC:04`). Check with
  `mainos.py xrefs --pcrel` on every padded address.
- Code reachable from an interrupt or re-entrantly keeps no state in a single global, saves every register it
  touches, never waits or blocks (R6: `VEC:0B`). Exception only with a bounded wait, justified in the note
  (trigless-dim's 0.5 µs latch waits, notes/45).
- The audio interrupt already uses about 77 % of each 0.67 ms block (notes/23). Keep work out of the voice loop
  and the audio path; when you cannot, count instructions in emulation (`mcengine.Engine.count_instructions`)
  and check the load governor (`tools/emu/test_governor.py`, notes/25, 30, 36).
- USB audio timing belongs to `tools/usb_steady.py` (notes/35); reuse `usb_steady.py`, `voice_loop.py`,
  `gov_asm.py`, `sprites.py` writers instead of copying their bytes.
- Never touch sections other than 3; never break `CONFIG › UPGRADE` over USB (the flasher only offers mods that
  keep it).

## 4. Toolchain

- Detect the prefix like the generators: `next((c for c in ("m68k-linux-gnu-", "m68k-elf-") if shutil.which(c +
  "gcc")), "m68k-linux-gnu-")`; C mods that call the OS require `m68k-elf-`.
- Assemble/compile with `-mcpu=54418`; one linker script per mod (`tools/machines/<mod>/<mod>.ld`) placing a
  `.cave` (or named) section at the free address; `objcopy -O binary -j <section>`; `nm` for symbols. Copy
  `tools/machines/trig_hold/` (`.S` + `.ld`) and `gen_trig_hold.compile_hold()`.
- Output bytes depend on the toolchain. GCC: SD VINTAGE v2 and the C mods need m68k-elf GCC 16.2.0 / binutils
  2.47 (build recipe in notes/42 §16). binutils: m68k-elf `as` relaxes `lea abs.l` to `lea (d16,pc)`, so
  `relocate_6ch.py --check` only matches with `m68k-linux-gnu-` binutils. Pin the toolchain in the note when
  bytes depend on it; prefer explicit encodings (`lea (sym).l`) in new code so both assemblers agree.

## 5. Before handing over

- [ ] Contract comment at the top of each `.S`; every hook listed in the generator with its stock bytes and role
- [ ] Free space taken from `REGISTRY.md` "libre", `sprites.redirect_write(mask)` in the same tweak
- [ ] `mainos.py xrefs --pcrel` shows nothing landing in padded bytes
- [ ] Interrupt/re-entrancy reviewed; audio-path cost measured if touched
- [ ] Proof runs the hooked OS routine itself, stock vs patched (skill `emulation-proofs`)
