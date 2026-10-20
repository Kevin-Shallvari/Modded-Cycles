/* Hooks of step record (notes/73), linked with step_rec.c into freed sprite masks (step_rec.ld). The writes on the OS
 * are in tools/gen_step_rec.py (HOOKS). */
	.globl	sr_key, sr_on, sr_off, sr_set, sr_leds, sr_tick

	.section .text.hooks, "ax"

/* 0x400243d6 (6 bytes), in the transport keys' handler 0x4002439a: jmp sr_key instead of
 * moveq #10,d0 ; cmp.l d4,d0 ; beq.s 0x4002441a. d4 = key code, d2 = the KeyEvent, a3 = the view. Taken: the handler
 * returns 1 (0x40024650, d4 = 1); otherwise the three instructions, then the handler goes on. */
sr_key:
	move.l	%d2, -(%sp)
	move.l	%a3, -(%sp)
	move.l	%d4, -(%sp)
	jsr	sr_transport
	lea	12(%sp), %sp
	tst.l	%d0
	bne.s	1f
	moveq	#10, %d0
	cmp.l	%d4, %d0
	beq.s	2f
	jmp	0x400243dc
2:	jmp	0x4002441a
1:	moveq	#1, %d4
	jmp	0x40024650

/* 0x4000721c and 0x40007120 (6 bytes each), in the interface's message handler 0x40007000: jsr sr_on / sr_off
 * instead of jsr 0x4006ba76 (is live record on?), for a note played / released; a2 = the message (+8 track, +16
 * note, +17 velocity). In step record: the note is ours, and "no" sends the handler to its end (0x40007214, the
 * message taken). Otherwise the original question. */
sr_on:
	tst.b	sr_active
	bne.s	1f
	jmp	0x4006ba76
1:	move.l	%a2, -(%sp)
	jsr	sr_note_on
	addq.l	#4, %sp
	moveq	#0, %d0
	rts

sr_off:
	tst.b	sr_active
	bne.s	1f
	jmp	0x4006ba76
1:	move.l	%a2, -(%sp)
	jsr	sr_note_off
	addq.l	#4, %sp
	moveq	#0, %d0
	rts

/* 0x4000bae0 (6 bytes), in the setter 0x4000ba7a: jsr sr_set instead of movea.l d0,a0 ; move.w d4,20(a0,d2.l*2).
 * d0 = the sound's data, d2 = k, d4 = the new value, d5 = "record" (a change made by the user), a2 = the
 * accessor, 20(fp) = the track. In step record, sr_touch sees the word before it is written; then the write. */
sr_set:
	movea.l	%d0, %a0
	tst.b	sr_active
	beq.s	1f
	tst.b	%d5
	beq.s	1f
	move.l	%a0, -(%sp)
	move.l	20(%fp), -(%sp)
	move.l	%a2, -(%sp)
	move.l	%d4, -(%sp)
	move.l	%d2, -(%sp)
	move.l	%a0, -(%sp)
	jsr	sr_touch
	lea	20(%sp), %sp
	movea.l	(%sp)+, %a0
1:	move.w	%d4, (20, %a0, %d2.l*2)		/* the replaced instruction, 3184 2a14 */
	rts

/* 0x40006a76 (6 bytes), in a frame of the lights 0x40006a4a: jsr sr_leds instead of jsr 0x40076ca2 (the views post
 * their lights; 4(sp) = the view controller). Ours first, then the views. */
sr_leds:
	tst.b	sr_active
	beq.s	1f
	move.l	4(%sp), -(%sp)
	jsr	sr_lights
	addq.l	#4, %sp
1:	jmp	0x40076ca2

/* 0x400081e4 (6 bytes), the interface's 30 Hz tick (message 5): jsr sr_tick instead of jsr 0x40082464 (rts). */
sr_tick:
	tst.b	sr_active
	beq.s	1f
	jsr	sr_tick_c
1:	rts
