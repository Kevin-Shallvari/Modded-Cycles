| Browser locked to /Wavetables on our machine's track (notes/52 §3quater).
    FOLDER  = 0x40148cb0    | remembered folder id
    ACTIVE  = 0x40a700c4    | active track
    CUR_KIT = 0x40a78888
    WT_MACH = 7
    DIR_OPEN  = 0x4007aa78  | (path, h[4]) -> 0 / -1
    MKDIR     = 0x4007ac46  | (path) -> 0 / -1
    CUR_ID    = 0x4007cf72  | (folder) -> id
    CHANGEDIR = 0x4007d1ca  | (folder, id)
    FSD_OPEN  = 0x4007d2f0  | (folder, String*, create)

    .text
    .globl wt_open, wt_close, wt_yes_up, wt_key_up, wt_home
| d0 = 1 if the active track plays our machine. Keeps d2-d7/a1-a7.
wt_ours:
    movel   ACTIVE,%d0
    moveq   #100,%d1
    mulsl   %d1,%d0
    addl    CUR_KIT,%d0
    movea.l %d0,%a0
    moveq   #0,%d0
    moveb   %a0@(28+38),%d0
    cmpil   #WT_MACH,%d0
    seq     %d0
    extbl   %d0
    negl    %d0
    rts

| at 0x400a6c20 (open): on our track, remember the folder and go to ours.
wt_open:
    bsr     wt_ours
    tstl    %d0
    beqw    wo_other
    tstl    wt_lock
    bnes    wo_kept
    movel   FOLDER,%d0
    movel   %d0,wt_saved
wo_kept:
    pea     wt_h
    pea     wt_path
    jsr     DIR_OPEN
    addql   #8,%sp
    tstl    %d0
    beqs    wo_ok
    pea     wt_path               | missing: make it
    jsr     MKDIR
    pea     wt_h
    pea     wt_path
    jsr     DIR_OPEN
    lea     %sp@(12),%sp
    tstl    %d0
    bnes    wo_stock              | cannot: the normal browser
wo_ok:
    movel   wt_h,%d0
    movel   %d0,wt_root
    movel   %d0,FOLDER
    moveq   #1,%d0
    movel   %d0,wt_lock
    movea.l %sp@(4),%a0           | cursor back to the top
    movea.l %a0@,%a0
    movea.l %a0@,%a0
    moveq   #-1,%d0
    movel   %d0,%a0@(16)
    bras    wo_stock
wo_other:
    bsr     wt_unlock             | a close we missed
wo_stock:
    lea     %sp@(-32),%sp         | replaced
    moveml  %d2-%d3/%a2-%a3,%sp@
    jmp     0x400a6c28

| folder back as before. Keeps d1-d7/a0-a7.
wt_unlock:
    tstl    wt_lock
    beqs    wu_out
    movel   wt_saved,%d0
    movel   %d0,FOLDER
    clrl    wt_lock
wu_out:
    rts

| at 0x400a40e2 (close)
wt_close:
    bsr     wt_unlock
    clrl    %sp@-                 | replaced
    jsr     0x40081bd6
    jmp     0x400a40ea

| at 0x4003fa52 (YES on ".."): none above our folder.
wt_yes_up:
    movel   %a0@(640),%sp@-       | replaced
    jsr     CUR_ID
    tstl    wt_lock
    beqs    wy_go
    cmpl    wt_root,%d0
    bnes    wy_go
    addql   #4,%sp
    jmp     0x4003faf0            | nothing
wy_go:
    jmp     0x4003fa5c

| at 0x400a6f9c (back key): in our folder, close instead of going up.
wt_key_up:
    movel   %a2@(640),%sp@-       | replaced
    jsr     CUR_ID
    tstl    wt_lock
    beqs    wk_go
    cmpl    wt_root,%d0
    bnes    wk_go
    addql   #4,%sp
    moveq   #1,%d2
    jmp     0x400a7002            | close
wk_go:
    jmp     0x400a6fa6

| at 0x400a70b0 (back key held, jsr): home is our folder, not "/".
wt_home:
    tstl    wt_lock
    beqs    wh_go
    movel   wt_root,%d0
    movel   %d0,%sp@(8)
    jmp     CHANGEDIR
wh_go:
    jmp     FSD_OPEN

    .data
    .balign 4
wt_lock:    .long 0
wt_saved:   .long 0
wt_root:    .long 0
wt_h:       .long 0,0,0,0
wt_path:    .asciz "/Wavetables"
