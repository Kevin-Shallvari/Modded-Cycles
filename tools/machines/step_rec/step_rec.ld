/* Step record (notes/73), in freed sprite masks (notes/14 §5, tools/sprites.py), free on every branch on 20/10/2026:
 *   - five 47x47 masks (376 bytes each, freed by chord-keys' removal) and four 48x22 masks (192 bytes each): the code
 *     and sr_active, written as zero in the image (the only variable that must be 0 at start-up);
 *   - the other variables in the free hole above the OS's BSS (0x423380b0..0x4233efff, notes/56 §3.5.2), at
 *     0x4233e800: not cleared at start-up, all set when step record starts. */
SECTIONS
{
  .cave_a 0x40182b38 : {
    *(.text.hooks) *(.text.sr_note_off) *(.text.data_of) *(.rodata*) *(.bss.sr_active) *(.data.sr_active)
    . = ALIGN(2); SHORT(0)
  }
  .cave_b 0x40182e28 : { *(.text.sr_note_on) *(.text.leave) }
  .cave_c 0x4018cd48 : { *(.text.sr_lights) *(.text.notify) }
  .cave_d 0x4018d1b8 : { *(.text.enter) *(.text.restore) }
  .cave_e 0x4018d4a8 : { *(.text.sr_transport) *(.text.write_locks) }
  .cave_f 0x4018a608 : { *(.text.sr_touch) }
  .cave_g 0x4018d798 : { *(.text.sr_tick_c) }
  .cave_h 0x4018f80c : { *(.text.popup) }
  .cave_i 0x40190184 : { *(.text.move) *(.text*) }
  .ram 0x4233e800 (NOLOAD) : { *(.bss*) *(COMMON) *(.data*) }
  /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
