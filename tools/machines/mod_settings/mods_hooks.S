/* Hooks and helpers of Mod Settings (notes/72), linked with mods.c into freed sprite masks (mods.ld). The writes
 * on the OS are in tools/gen_mod_settings.py (HOOKS). */
	.globl	cfg_tail, usb_boot, item_label, item_icon, make_handle, irq_off, irq_restore, cache_push, cache_sync

	.section .text.hooks, "ax"

/* 0x4003c99a (6 bytes): jmp cfg_tail instead of movem.l -104(fp),d2-d7/a2-a5, at the end of the Config Menu's
 * constructor (ModelSettingsMenu, 0x4003c134); a2 = the menu. Our line, then the original epilogue. */
cfg_tail:
	move.l	%a2, -(%sp)
	jsr	mods_menu_add
	addq.l	#4, %sp
	movem.l	-104(%fp), %d2-%d7/%a2-%a5
	unlk	%fp
	rts

/* 0x4000576c (6 bytes): lea usb_boot,a2 instead of lea 0x40004e40,a2. Start-up calls (a2) once, at 0x400057c6,
 * with the USB mode in 4(sp): the 6CH changes if they are set, then the original set-up of the USB mode. */
usb_boot:
	jsr	mods_boot
	jmp	0x40004e40

	.section .text.glue, "ax"

/* Label of a line, as 0x4002cc44: the std::string returned is built at a0 from the text kept in the closure of the
 * std::function (4(sp): its storage). Same as tools/machines/arp/arp_hooks.S. */
item_label:
	movea.l	4(%sp), %a1
	movea.l	(%a1), %a1
	link.w	%fp, #-4
	move.l	%d2, -(%sp)
	pea	-1(%fp)
	move.l	(%a1), -(%sp)
	move.l	%a0, %d2
	move.l	%a0, -(%sp)
	jsr	0x400f980c
	lea	12(%sp), %sp
	move.l	%d2, %d0
	move.l	-8(%fp), %d2
	unlk	%fp
	rts

/* Display of a Config Menu line, as 0x4003b19e: its icon (the Bitmap kept in the closure), drawn by 0x40071da4
 * (canvas, bitmap, x, y, 1). Arguments: storage, line, canvas, x, y. */
item_icon:
	movea.l	4(%sp), %a0
	movea.l	(%a0), %a0
	move.l	(%a0), %d0
	move.l	12(%sp), 4(%sp)
	move.l	%d0, 8(%sp)
	move.l	16(%sp), 12(%sp)
	move.l	20(%sp), 16(%sp)
	moveq	#1, %d0
	move.l	%d0, 20(%sp)
	jmp	0x40071da4

/* make_handle(handle, parent, view + 56): the shared pointer of a child view, as the Config Menu builds its own
 * (0x4007536a returns it at a0). */
make_handle:
	movea.l	4(%sp), %a0
	move.l	12(%sp), -(%sp)
	move.l	12(%sp), -(%sp)
	jsr	0x4007536a
	addq.l	#8, %sp
	rts

irq_off:
	moveq	#0, %d0
	move.w	%sr, %d0
	move.w	#0x2700, %sr
	rts

irq_restore:
	move.l	4(%sp), %d0
	move.w	%d0, %sr
	rts

/* After code and descriptors changed in memory. The data cache is in copyback mode over the SDRAM (ACR0
 * 0x4007e020): the changed lines must reach memory, so that the instruction cache and the USB controller read the
 * new bytes. On the V4 core CPUSHL selects a set and a way (address bits 11..4, bits 1..0), as Linux uses it on this
 * family; the OS uses it with the address of the bytes it changed (descriptors, 0x400049dc). Both are done:
 * cache_push(p) with the address of each changed line's first and last byte, then cache_sync() over every set and
 * way (256 sets x 4 ways cover 16 KB, the data cache is 8 KB). Pushing a line is harmless in either reading. Then the
 * instruction and branch caches are invalidated by the OS's own CACR (0xa50ce100, written once at 0x40000548)
 * without DCINVA, which would drop the data cache's dirty lines. */
cache_push:
	movea.l	4(%sp), %a0
	nop
	cpushl	%bc, (%a0)
	rts

cache_sync:
	nop
	suba.l	%a0, %a0
1:	cpushl	%bc, (%a0)
	addq.l	#1, %a0
	cpushl	%bc, (%a0)
	addq.l	#1, %a0
	cpushl	%bc, (%a0)
	addq.l	#1, %a0
	cpushl	%bc, (%a0)
	lea	13(%a0), %a0
	cmpa.l	#0x1000, %a0
	bcs.s	1b
	move.l	#0xa40ce100, %d0
	movec	%d0, %cacr
	nop
	rts
