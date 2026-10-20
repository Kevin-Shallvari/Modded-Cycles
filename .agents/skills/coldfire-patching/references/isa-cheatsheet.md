# ColdFire ISA cheatsheet (MCF54415, ISA_C + EMAC)

Encodings verified on real patch bytes (notes/03 §4). Big-endian everywhere; the USB stream wants little-endian,
hence `byterev`.

## Encodings

| Instruction | Encoding | Example |
|---|---|---|
| `jmp abs.l` / `jsr abs.l` | `4EF9 aaaaaaaa` / `4EB9 aaaaaaaa` (6 bytes) | `4ef94019b1e0` |
| `jsr (d16,pc)` / `bsr.w` / `bsr.l` | `4EBA dddd` / `6100 dddd` / `61FF dddddddd` (disp from PC+2) | |
| `nop` / `rts` / `rte` | `4E71` / `4E75` / `4E73` | |
| `moveq #n,Dx` (−128..127) | `70 | x<<1`, `nn` | `7212` = `moveq #18,d1` |
| `move.l #imm,Dn` / `movea.l #imm,An` | `203C | n<<9` / `207C | n<<9` + imm32 | `247c80001858` |
| `move.l abs.l,Dn` | `2039 | n<<9` + addr | `2239404a05e8` |
| `lea abs.l,An` / `lea (d16,pc),An` | `41F9 | n<<9` / `41FA | n<<9` | `45f9…` = `lea …,a2` |
| `lsl.l #k,Dy` / `lsr.l #k,Dy` (k = 1..8) | `E188 | (k&7)<<9 | y` / `E088 | (k&7)<<9 | y` | `e788` = `lsl.l #3,d0` |
| `lsl.l Dx,Dy` | `E1A8 | x<<9 | y` | `e3ac` = `lsl.l d1,d4` |
| `add.l Dx,Dy` / `sub.l Dx,Dy` | `D080 | y<<9 | x` / `9080 | y<<9 | x` | `d081`, `9285` |
| `byterev Dn` | `02C0 | n` | `02c2` |
| `swap Dn` / `clr.w Dn` | `4840 | n` / `4240 | n` | |
| Stub prologue / epilogue | `4fef ffd4 48d7 07ff` … `4cd7 07ff 4fef 002c` | `lea -44(sp),sp ; movem.l d0-d7/a0-a2,(sp)` |

## Traps

- Most arithmetic and logic exists only in `.l` on data registers.
- Immediate shift counts are 1..8; beyond, put the count in a register. No `rol`/`ror`. Multiply by constants with
  shifts and adds (×24 = (x<<4)+(x<<3)).
- `moveq` is −128..127; larger constants need `move.l #imm` (6 bytes) or `moveq` + shift.
- `movem` has no predecrement/postincrement: `lea -N(sp),sp ; movem.l regs,(sp)` and the reverse.
- No `dbra`: `subq.l #1,dN ; bne`.
- ColdFire-only instructions capstone cannot decode: `byterev`, `bitrev`, `ff1`, `mvs`, `mvz`, `mov3q`, `sats`,
  EMAC (`mac`, `msac`, `movclr`, `move.l ACCn`). Use m68k binutils with `-m m68k:isa-c:emac`.
- `mvs.b`/`mvz.b` sign/zero-extend into a long: a byte read with `mvs.b` is a signed value, not a boolean
  (notes/53: the OUT/THRU byte).
- Assembler relaxation: `lea sym,%aN` may become PC-relative depending on binutils; write `lea (sym).l,%aN` when
  the absolute form matters (and always when the code is copied elsewhere at boot).
- EMAC in the audio engine: `MACSR = 0xa0` (signed fractional). Save/restore ACC and MACSR if a stub uses EMAC
  outside the engine; the stock block accounting (`0x40056ea8`) accumulates without clearing first (notes/47).

## Crash codes on the screen

`EXCEPTION VEC:xx SR:xxxx ADDR:xxxxxxxx`

| Code | Usual cause |
|---|---|
| `VEC:04` | illegal instruction: jump into the middle of an instruction or into hook padding |
| `VEC:0B` | line-F / dead return address: corrupted stack or re-entrant stub with global state |
| `ADDR:0` | null pointer dereference |
| `SR:27xx` | IPL 7: crashed in the audio interrupt context |
| frozen on the logo | detour to a wrong address (typed instead of taken from `nm`), or boot hook broken |
