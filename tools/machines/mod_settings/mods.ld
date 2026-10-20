/* Mod Settings (notes/72), in freed sprite masks (notes/14 §5, tools/sprites.py), free on every branch on 19/10/2026:
 *   - five 47x47 masks (376 bytes each, freed by chord-keys' removal): the code;
 *   - three 48x22 masks (192 bytes each): the 6CH changes, the icon and the state.
 * The state (.data, .bss) is written as zeros in the image: these areas are not cleared at start-up. */
SECTIONS
{
  .cave_a 0x4016b6f8 : {
    *(.text.hooks) *(.text.glue) *(.text.mods_boot) *(.text.usb6_wanted) *(.text.mods_get) *(.text.rec_ok)
    *(.text.rec_sum)
  }
  .cave_b 0x4016b9e8 : {
    *(.text.usb6_apply) *(.text.copy) *(.text.usb_draw) *(.rodata.usb_draw*)
  }
  .cave_c 0x40171f30 : {
    *(.text.mods_menu_add) . = ALIGN(4); *(.rodata.MODS_INV*) *(.rodata.USB_INV*) *(.rodata.mods_menu_add*)
  }
  .cave_d 0x40172608 : {
    *(.text.add_item) *(.text.mods_open) *(.rodata.*str*)
  }
  .cave_h 0x40179730 : {
    *(.text.usb_press) *(.text.usb6_set) *(.text.mods_put) *(.text.usb6_rings) *(.text*)
  }
  .cave_e 0x40187528 : {
    *(.rodata.SITES) *(.rodata.NEW6)
  }
  .cave_f 0x401876a8 : {
    *(.rodata.ICON_MODS) *(.rodata*) . = ALIGN(4); *(.data*) *(.bss.page_h) *(.bss.icon_bm) *(.bss.usb6_on)
  }
  .cave_g 0x40188f98 : {
    *(.bss*) *(COMMON) . = ALIGN(4); LONG(0)        /* LONG: written to the image, as zeros */
  }
  /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
