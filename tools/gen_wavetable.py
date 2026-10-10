#!/usr/bin/env python3
"""Génère tweaks/model-cycles_OS1.13/36-wavetable-tg.json : la machine Wave, qui joue une table d'ondes de
l'utilisateur, avec Model-TG (après model-tg-st), en 8e machine (notes/52).

  - moteur : tools/machines/wavetable/wt.c (oscillateur sur les copies par demi-octave, passe-bas d'Acid, chaîne
    d'ampli d'origine), ses tables écrites ici dans wt_tables.h ;
  - mécanique des machines ajoutées : celle d'Acid avec Model-TG (gen_acid.py, notes/51 §6) ;
  - navigateur bloqué dans /Wavetables sur la piste de la machine (5 accroches dans l'OS, notes/52 §3quater) ;
  - Model-TG retouché au démarrage, en mémoire (son tweak ne change pas) : le navigateur charge un fichier sur notre
    piste, name_probe protège sa table (notes/52 §3ter), et sa tâche des LED prépare les copies (wt_tick). Les
    adresses sont cherchées dans son bloc par motifs, chacun unique.

    python3 tools/gen_wavetable.py --cycles model-cycles_OS1.13.syx [--check]
"""
import argparse
import json
import math
import pathlib
import re
import struct
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "emu"))

import gen_acid as ga              # noqa: E402
import gen_macro as gm             # noqa: E402
import gen_sdvintage_exact as gx   # noqa: E402
import gen_sdvintage_7th as g7     # noqa: E402
import gen_syntakt_machines as g8  # noqa: E402
import gen_syntakt_engines as gs   # noqa: E402
import sprites                     # noqa: E402

DEV = HERE.parent / "tweaks" / "model-cycles_OS1.13"
OUT = DEV / "36-wavetable-tg.json"
SRC = HERE / "machines" / "wavetable"
BASE = gx.BASE

MACHINE = dict(name="Wave", image=4, decay=60,
               knobs=(("Position", "POS", 0), ("Flt Env", "FENV", 64), ("Cutoff", "CUT", 127), ("Reso", "RES", 0)))
EPOS_ID, EPOS_K = 0x0a, 27        # MACHINE tenue + COLOR : enveloppe -> position (place libre ; mot sauvé par Model-TG)
EPOS_NAMES = ("Env Pos", "EPOS")
WT_MACH = 7                       # après les 6 d'origine et le Sampler
NCOPY = 21                        # copies par demi-octave : 1024 / 2^(c/2) harmoniques
FOLD_OK = 28000.0                 # repli au-dessus de 20 kHz : inaudible
COPIES_AT = 0x46800000            # SDRAM libre au-dessus de Model-TG (notes/52 §4)
POOL_BYTES = 0x1680000            # réserve des copies, partagée entre les pistes (22,5 Mo)
SCRATCH_AT = COPIES_AT + POOL_BYTES  # 64 Ko de calcul, jusqu'à 0x47E90000
ART_OFF = 0x8000                  # images, après le code

# --- l'OS (navigateur, notes/52 §3quater) ---
FOLDER = 0x40148cb0
ACTIVE = 0x40a700c4
BROWSER = ((0x400a6c20, "4fefffe048d70c0c", "wt_open"), (0x400a40e2, "42a74eb940081bd6", "wt_close"),
           (0x4003fa52, "2f2802804eb94007cf72", "wt_yes_up"), (0x400a6f9c, "2f2a02804eb94007cf72", "wt_key_up"),
           (0x400a70b0, "4eb94007d2f0", "wt_home"), (0x400a640a, "4eb94007e548", "wt_cursor"))


def tables_h():
    n0 = 69 + 12 * math.log2(FOLD_OK / 1024 / math.sqrt(2) / 440)
    hmax = [max(1, int(1024 * 2 ** (-c / 2))) for c in range(NCOPY)]
    cos = [min(32767, round(32768 * math.cos(2 * math.pi * k / 2048))) for k in range(1024)]
    sin = [min(32767, round(32768 * math.sin(2 * math.pi * k / 2048))) for k in range(1024)]
    return ga.tables_h().replace("tools/gen_acid.py", "tools/gen_wavetable.py") + "\n".join([
        f"#define NCOPY {NCOPY}",
        f"#define COPY_N0 {round(n0 * 65536)}",
        f"#define POOL_BYTES {POOL_BYTES:#x}",
        "static const s16 HMAX[NCOPY] = {" + ", ".join(map(str, hmax)) + "};",
        "static const s16 COS_TAB[1024] = {" + ", ".join(map(str, cos)) + "};",
        "static const s16 SIN_TAB[1024] = {" + ", ".join(map(str, sin)) + "};",
    ]) + "\n"


# --- Model-TG : adresses cherchées dans son bloc -------------------------------------------------------------
def find_tg(tg):
    """Sites et variables de Model-TG que nous retouchons ou lisons (motifs uniques dans son bloc)."""
    blob, at = tg["blob"], tg["blob_at"]
    h = blob.hex()

    def one(pat, what):
        ms = [m for m in re.finditer(pat, h) if m.start() % 2 == 0]
        if len(ms) != 1:
            raise SystemExit(f"!! Model-TG : {what} trouvé {len(ms)} fois")
        return ms[0]
    va = lambda m, g=0: at + m.start(g) // 2
    word = lambda m, g: int(m.group(g), 16)

    def rel(m, g):                              # lea d16(pc) : cible = adresse du mot d'extension + d16
        d = int(m.group(g), 16)
        return va(m, g) + (d - 0x10000 if d & 0x8000 else d)
    # preset_fail_hook : lea sel_track ; move.l d2,(a0) ; jsr any_sampler ; tst.l d0 ; beq.w pf_need ;
    # lea sel_hash ; move.l (a0),d3 ; beq.w ; lea track_hash ; ... lea track_slot ; ... lea track_pend
    m = one(r"41fa[0-9a-f]{4}2082(4eb9([0-9a-f]{8}))4a806700[0-9a-f]{4}41fa[0-9a-f]{4}26106700[0-9a-f]{4}"
            r"41fa([0-9a-f]{4})21832c0041fa([0-9a-f]{4})70ff21802c0041fa([0-9a-f]{4})21802c00", "navigateur")
    r = dict(pf_site=va(m, 1), any_sampler=word(m, 2), track_hash=rel(m, 3), track_slot=rel(m, 4),
             track_pend=rel(m, 5))
    if r["track_slot"] != r["track_hash"] + 24 or r["track_pend"] != r["track_slot"] + 24:
        raise SystemExit("!! Model-TG : track_hash / track_slot / track_pend")
    # name_probe : cmpi.l #6,d0 ; bne.w np_nosmp ; bsr st_apply_c ; lea st_ok ; move.l d0,(a0) ; lea 4(a2),a3
    m = one(r"(0c8000000006)6600([0-9a-f]{4})(61[0-9a-f]{2}(?:[0-9a-f]{4})?)41f[9a]([0-9a-f]{4}(?:[0-9a-f]{4})?)"
            r"2080(47ea0004)", "name_probe")
    disp = int(m.group(2), 16)
    disp -= 0x10000 if disp & 0x8000 else 0
    st_ok = rel(m, 4) if len(m.group(4)) == 4 else word(m, 4)
    r.update(np_site=va(m, 1), np_nosmp=va(m, 1) + 8 + disp, np_cont=va(m, 3), st_ok=st_ok, np_tok=va(m, 5))
    if r["np_cont"] != r["np_site"] + 10:
        raise SystemExit("!! Model-TG : name_probe")
    # led_hook : jsr sld_tick ; lea ld_busy,a0 ; clr.l (a0)
    m = one(r"(4eb9([0-9a-f]{8}))41fa([0-9a-f]{4})4290", "led_hook")
    if rel(m, 3) != tg["ld_busy"]:
        raise SystemExit("!! Model-TG : led_hook")
    r.update(lh_site=va(m, 1), sld_tick=word(m, 2))
    for k in ("pf_site", "np_site", "lh_site"):
        if not at <= r[k] < at + len(blob):
            raise SystemExit(f"!! Model-TG : {k}")
    r["old"] = {k: blob[r[k] - at:r[k] - at + n].hex() for k, n in (("pf_site", 6), ("np_site", 10), ("lh_site", 6))}
    return r


def glue_asm(tg, f, syms):
    """Notre code en assembleur : retouches de Model-TG au démarrage, navigateur bloqué, tick des copies."""
    old = f["old"]
    words = lambda hx: ", ".join(f"0x{hx[i:i + 4]}" for i in range(0, len(hx), 4))
    return f"""
	.text
| ---- démarrage : retouche Model-TG en mémoire si ses octets sont ceux attendus, puis son boot_extra_hook
	.globl	wt_boot
wt_boot:
	lea	pf_old, %a0
	lea	{f['pf_site']:#x}, %a1
	moveq	#2, %d0
	bsr.s	same
	bne.s	9f
	lea	np_old, %a0
	lea	{f['np_site']:#x}, %a1
	moveq	#4, %d0
	bsr.s	same
	bne.s	9f
	lea	lh_old, %a0
	lea	{f['lh_site']:#x}, %a1
	moveq	#2, %d0
	bsr.s	same
	bne.s	9f
	lea	{f['pf_site']:#x}, %a1		/* jsr wt_or_any */
	move.w	#0x4eb9, (%a1)+
	move.l	#wt_or_any, (%a1)
	lea	{f['np_site']:#x}, %a1		/* jmp wt_np ; nop ; nop */
	move.w	#0x4ef9, (%a1)+
	move.l	#wt_np, (%a1)+
	move.l	#0x4e714e71, (%a1)
	lea	{f['lh_site']:#x}, %a1		/* jsr wt_led */
	move.w	#0x4eb9, (%a1)+
	move.l	#wt_led, (%a1)
	moveq	#1, %d0
	move.l	%d0, wt_patched
9:	jmp	{tg['boot_extra_hook']:#x}
| d0 mots de (a0) et (a1) égaux : Z
same:
1:	move.w	(%a0)+, %d1
	cmp.w	(%a1)+, %d1
	bne.s	2f
	subq.l	#1, %d0
	bne.s	1b
2:	rts
	.align	2
pf_old:	.word	{words(old['pf_site'])}
np_old:	.word	{words(old['np_site'])}
lh_old:	.word	{words(old['lh_site'])}
	.globl	wt_patched
wt_patched:	.long	0

| ---- d0 = 1 si la piste d0 joue notre machine (sound_obj de Model-TG). Garde d2-d7/a2-a6.
wt_is_ours:
	move.l	%d2, -(%sp)
	jsr	{tg['sound_obj']:#x}
	move.l	(%sp)+, %d2
	tst.l	%d0
	beq.s	1f
	movea.l	%d0, %a0
	moveq	#0, %d0
	move.b	38(%a0), %d0
	cmpi.l	#{WT_MACH}, %d0
	seq	%d0
	extb.l	%d0
	neg.l	%d0
1:	rts

| ---- preset_fail_hook : la piste cible (d2) de notre machine charge, Sampler ou non
	.globl	wt_or_any
wt_or_any:
	move.l	%d2, %d0
	bsr.s	wt_is_ours
	tst.l	%d0
	bne.s	1f
	jmp	{f['any_sampler']:#x}
1:	rts

| ---- name_probe (d0 = machine) : notre machine reprend l'empreinte du nom, sans l'état du Sampler (st_ok = 1)
	.globl	wt_np
wt_np:
	cmpi.l	#6, %d0
	bne.s	1f
	jmp	{f['np_cont']:#x}
1:	cmpi.l	#{WT_MACH}, %d0
	beq.s	2f
	jmp	{f['np_nosmp']:#x}
2:	moveq	#1, %d0
	move.l	%d0, {f['st_ok']:#x}
	jmp	{f['np_tok']:#x}

| ---- led_hook : son sld_tick, puis une étape des copies (C)
	.globl	wt_led
wt_led:
	jsr	{f['sld_tick']:#x}
	jmp	{syms['wt_tick']:#x}

| ---- navigateur : sur notre piste, /Wavetables (créé s'il manque), sans remonter au-dessus
wt_ours:
	move.l	{ACTIVE:#x}, %d0
	bra.s	wt_is_ours

	.globl	wt_open
wt_open:
	bsr.s	wt_ours
	tst.l	%d0
	beq.w	5f
	tst.l	wt_lock
	bne.s	1f
	move.l	{FOLDER:#x}, %d0
	move.l	%d0, wt_saved
1:	pea	wt_h
	pea	wt_path
	jsr	0x4007aa78
	addq.l	#8, %sp
	tst.l	%d0
	beq.s	2f
	pea	wt_path			/* absent : créé */
	jsr	0x4007ac46
	pea	wt_h
	pea	wt_path
	jsr	0x4007aa78
	lea	12(%sp), %sp
	tst.l	%d0
	bne.s	6f
2:	move.l	wt_h, %d0
	move.l	%d0, wt_root
	move.l	%d0, {FOLDER:#x}
	moveq	#1, %d0
	move.l	%d0, wt_lock
	movea.l	4(%sp), %a0		/* curseur en haut */
	movea.l	(%a0), %a0
	movea.l	(%a0), %a0
	moveq	#-1, %d0
	move.l	%d0, 16(%a0)
	bra.s	6f
5:	bsr.s	wt_unlock		/* une fermeture manquée */
6:	lea	-32(%sp), %sp
	movem.l	%d2-%d3/%a2-%a3, (%sp)
	jmp	0x400a6c28

wt_unlock:
	tst.l	wt_lock
	beq.s	1f
	move.l	wt_saved, %d0
	move.l	%d0, {FOLDER:#x}
	clr.l	wt_lock
1:	rts

	.globl	wt_close
wt_close:
	bsr.s	wt_unlock
	clr.l	-(%sp)
	jsr	0x40081bd6
	jmp	0x400a40ea

	.globl	wt_yes_up
wt_yes_up:
	move.l	640(%a0), -(%sp)
	jsr	0x4007cf72
	tst.l	wt_lock
	beq.s	1f
	cmp.l	wt_root, %d0
	bne.s	1f
	addq.l	#4, %sp
	jmp	0x4003faf0
1:	jmp	0x4003fa5c

	.globl	wt_key_up
wt_key_up:
	move.l	640(%a2), -(%sp)
	jsr	0x4007cf72
	tst.l	wt_lock
	beq.s	1f
	cmp.l	wt_root, %d0
	bne.s	1f
	addq.l	#4, %sp
	moveq	#1, %d2
	jmp	0x400a7002
1:	jmp	0x400a6fa6

| ---- curseur du navigateur (0x400a640a, à la place de jsr 0x4007e548 : le fichier sous le curseur est-il
| valide ?) : sur notre piste, son empreinte, sa taille et l'heure, pour la préparation d'avance (wt_tick)
	.globl	wt_cursor
wt_cursor:
	move.l	4(%sp), -(%sp)
	jsr	0x4007e548
	addq.l	#4, %sp
	tst.l	wt_lock
	beq.s	1f
	tst.l	%d0
	beq.s	1f
	movea.l	4(%sp), %a0
	move.l	8(%a0), %d1
	move.l	%d1, {syms['wt_pf_size']:#x}
	move.l	0x8000184c, %d1
	move.l	%d1, {syms['wt_pf_clock']:#x}
	move.l	4(%a0), %d1
	move.l	%d1, {syms['wt_pf_hash']:#x}
1:	rts

	.globl	wt_home
wt_home:
	tst.l	wt_lock
	beq.s	1f
	move.l	wt_root, %d0
	move.l	%d0, 8(%sp)
	jmp	0x4007d1ca
1:	jmp	0x4007d2f0

	.align	2
wt_lock:	.long	0
wt_saved:	.long	0
wt_root:	.long	0
wt_h:	.long	0, 0, 0, 0
wt_path:	.asciz	"/Wavetables"
	.align	2
"""


LINK = """SECTIONS
{{
  .text {code:#x} : {{ *(.text.wt_update) *(.text.wt_render) *(.text*) }}
  .rodata : {{ *(.rodata*) }}
  .data : {{ *(.data*) }}
  .bss {bss:#x} (NOLOAD) : {{ *(.bss*) *(COMMON) }}
  /DISCARD/ : {{ *(.comment) *(.note*) *(.eh_frame*) }}
}}
"""


def compile_machine(tmp, pay, f):
    """Le moteur, lié à pay (code, tables) et pay + gm.BSS_OFF (états). Renvoie (octets, symboles, fin du BSS)."""
    (tmp / "wt_tables.h").write_text(tables_h())
    o, ld, elf, out = tmp / "wt.o", tmp / "link.ld", tmp / "wt.elf", tmp / "wt.bin"
    defs = [f"-DTG_TRACK_SLOT={f['track_slot']:#x}", f"-DTG_TRACK_PEND={f['track_pend']:#x}",
            f"-DTG_SLOT_HASH={f['slot_hash']:#x}",
            f"-DTG_PD_MODE={f['pd_mode']:#x}", f"-DTG_ENSURE_LOADED_S=\"{f['ensure_loaded']:#x}\"", f"-DCOPIES_AT={COPIES_AT:#x}", f"-DSCRATCH_AT={SCRATCH_AT:#x}"]
    gx.run([gx.CROSS + "gcc", *ga.CFLAGS, *defs, f"-I{tmp}", "-c", str(SRC / "wt.c"), "-o", str(o)])
    ld.write_text(LINK.format(code=pay, bss=pay + gm.BSS_OFF))
    warn = ["--no-warn-rwx-segments"] if "no-warn-rwx" in gx.run([gx.CROSS + "ld", "--help"]) else []
    gx.run([gx.CROSS + "ld", "-T", str(ld), "--gc-sections", *warn, "-e", "wt_update",
            "-u", "wt_render", "-u", "wt_tick", "-o", str(elf), str(o)])
    secs = {}
    for line in gx.run([gx.CROSS + "objdump", "-h", str(elf)]).splitlines():
        p_ = line.split()
        if len(p_) > 4 and p_[0].isdigit():
            secs[p_[1]] = (int(p_[3], 16), int(p_[2], 16))
    extra = set(secs) - {".text", ".rodata", ".data", ".bss"}
    if extra:
        raise SystemExit(f"!! sections inattendues : {sorted(extra)}")
    gx.run([gx.CROSS + "objcopy", "-O", "binary", "-R", ".bss", str(elf), str(out)])
    blob = out.read_bytes()
    syms = {}
    for line in gx.run([gx.CROSS + "nm", str(elf)]).splitlines():
        p_ = line.split()
        if len(p_) == 3:
            syms[p_[2]] = int(p_[0], 16)
    bss = secs.get(".bss", (pay + gm.BSS_OFF, 0))
    if bss[0] != pay + gm.BSS_OFF:
        raise SystemExit("!! BSS")
    return blob, syms, (bss[0] + bss[1] + 3) & ~3


# --- images : la fiche de TONE (« STYLE:WAVE »), une onde pour les lettres ---
FONT = dict(ga.FONT, W=("#.#", "#.#", "#.#", "###", "#.#"), V=("#.#", "#.#", "#.#", "#.#", ".#."),
            E=("###", "#..", "##.", "#..", "###"))


def card_grid(tone):
    g = [row[:] for row in tone]
    top = 32 - 7
    for y in range(top - 4, top + 1):
        for x in range(24, 48):
            g[y][x] = 0
    for k, ch in enumerate("WAVE"):
        for r_, line in enumerate(FONT[ch]):
            for c, b in enumerate(line):
                g[top - r_][24 + 4 * k + c] = int(b == "#")
    for row, n in enumerate((3, 4, 5)):
        ytop = 32 - 14 - 7 * row
        for i in range(5):
            for r_, line in enumerate(ga.DIAMOND[0 if i < n else 1]):
                for c, b in enumerate(line):
                    g[ytop - r_][18 + 6 * i - len(line) // 2 + c] = int(b == "#")
    return g


def wave_icon(w, h, thick):
    """Deux périodes d'une onde qui passe du sinus à la dent de scie, en trait épais (y monte)."""
    g = [[0] * w for _ in range(h)]
    amp, mid = (h - 2 * thick) / 2, (h - 1) / 2
    for x in range(w):
        t = x / (w - 1)
        ph = 2 * t % 1.0
        sine, saw = math.sin(2 * math.pi * ph), 1 - 2 * ph
        y = mid + amp * ((1 - t) * sine + t * saw)
        for yy in range(h):
            if abs(yy - y) <= thick / 2:
                g[yy][x] = 1
    return g


def art(img, pay):
    u32 = lambda va: struct.unpack_from(">I", img, va - BASE)[0]
    if u32(0x400b13b6 + 2) != ga.ART["card"][2]:
        raise SystemExit("!! masque de la fiche")
    w, h, mask, im0, step = ga.ART["card"]
    tone_at = im0 + ga.TONE * step
    tone_bytes = img[tone_at - BASE:tone_at - BASE + step]
    card = ga.bm_bytes(card_grid(ga.bm_read(tone_bytes, w, h)), w, h)
    grids = dict(mid=wave_icon(34, 34, 3.2), small=wave_icon(25, 22, 2.4))
    objs_at = pay + ART_OFF
    at = objs_at + 0x60
    where, parts, objs = {}, [], bytearray()
    where["card"] = at
    parts.append({"dest": f"{at:#x}", "cycles": [f"{tone_at:#x}", f"{tone_at + step:#x}"]})
    reloc = [[f"{at + k:#x}", tone_bytes[k:k + 4].hex(), card[k:k + 4].hex()]
             for k in range(0, step, 4) if card[k:k + 4] != tone_bytes[k:k + 4]]
    at += step
    for name in ("mid", "small"):
        w_, h_ = ga.ART[name][:2]
        data = ga.bm_bytes(grids[name], w_, h_)
        where[name] = at
        parts.append({"dest": f"{at:#x}", "hex": data.hex()})
        at += len(data)
    for name in ("card", "mid", "small"):
        w_, h_, mask_ = ga.ART[name][:3]
        objs += struct.pack(">IIIIIIB3x", ga.BITMAP_VT, w_, h_, ga.bm_words(h_), where[name], mask_, 0)
    parts.insert(0, {"dest": f"{objs_at:#x}", "hex": bytes(objs).hex()})
    addr = {name: objs_at + 28 * i for i, name in enumerate(("card", "mid", "small"))}
    return parts, reloc, addr, at


def build_tweak(img, tg):
    """Le tweak (comme gen_acid.build_tweak avec Model-TG), plus le navigateur et les retouches de Model-TG."""
    pay = gs.PAY_TG
    gs.set_base(pay)
    first = gm.TG_FIRST
    if first != WT_MACH:
        raise SystemExit("!! index de la machine")
    nm, n = first + 1, 1
    top = nm - 1
    cur = tg["img"]
    u32 = lambda va: struct.unpack_from(">I", cur, va - BASE)[0]
    m = MACHINE
    f = find_tg(tg)
    f.update(slot_hash=tg["slot_hash"], pd_mode=tg["pd_mode"], ensure_loaded=tg["ensure_loaded"])
    with tempfile.TemporaryDirectory() as d:
        tmp = pathlib.Path(d)
        blob, syms, bss_end = compile_machine(tmp, pay, f)
        glue_at = pay + ((len(blob) + 15) & ~15)
        glue, gsyms = gm.assemble(tmp, "glue", glue_asm(tg, f, syms), glue_at)
        if glue_at + len(glue) > pay + ART_OFF:
            raise SystemExit(f"!! code trop grand : {glue_at + len(glue) - pay} o")
        art_parts, art_reloc, art_addr, art_end = art(img, pay)
        if art_end > pay + gm.BSS_OFF:
            raise SystemExit("!! images")
        names_at, upd_at, rnd_at, map_at = gs.DATA, gs.DATA + 4 * nm, gs.DATA + 8 * nm, gs.DATA + 16 * nm
        det = gs.detours_asm(n, [m["image"]], [76], tg)
        held = "moveq #0x0b, %d1\n\tmove.l %d1, 28(%a0)"          # MACHINE tenue : + Env Pos sur COLOR
        if det.count(held) != 1:
            raise SystemExit("!! couche MACHINE tenue")
        det = det.replace(held, held + f"\n\tmoveq #{EPOS_ID:#x}, %d1\n\tmove.l %d1, 16(%a0)")
        stubs, ssyms = gm.assemble(tmp, "det", det
                                   + ga.art_asm(art_addr, first, tg) + gm.dispatch_tg_asm(syms, rnd_at, tg), gs.STUBS)
        if gs.STUBS + len(stubs) > gs.DATA:
            raise SystemExit("!! détours trop grands")

        strings = [m["name"]] + [k[i] for k in m["knobs"] for i in (0, 1)] + list(EPOS_NAMES)
        at, addr = map_at + ((nm + 3) & ~3), {}
        for s_ in strings:
            if s_ not in addr:
                addr[s_] = at
                at += len(s_) + 1
        blob_u32 = lambda va: struct.unpack_from(">I", tg["blob"], va - tg["blob_at"])[0]
        names = [blob_u32(tg["sampler_name_table"] + 4 * i) for i in range(7)] + [addr[m["name"]]]
        pad = [u32(g7.UPDATE_TAB)] * (first - 6), [u32(g7.RENDER_TAB)] * (first - 6)
        upd = [u32(g7.UPDATE_TAB + 4 * i) for i in range(6)] + pad[0] + [syms["wt_update"]]
        rnd = [u32(g7.RENDER_TAB + 4 * i) for i in range(6)] + pad[1] + [syms["wt_render"]]
        data = bytearray()
        for t in (names, upd, rnd, range(1, nm + 1)):
            data += b"".join(g7.be32(x) for x in t)
        data += cur[gs.MAP - BASE:gs.MAP - BASE + 6] + bytes(range(6, nm)) + bytes(((nm + 3) & ~3) - nm)
        for s_ in addr:
            data += s_.encode("ascii") + b"\0"
        if gs.DATA + len(data) > gs.DESCN:
            raise SystemExit("!! données")

        new = bytearray()
        for k, (long_, short, default, *rng) in enumerate(m["knobs"]):
            if any(len(w_) > 8 for w_ in long_.split()):
                raise SystemExit(f"!! {long_} : mots de 8 lettres au plus (notes/18 §10)")
            e = bytearray(img[g7.DESC + (g7.SNARE_DESC + k) * g7.DSTRIDE - BASE:][:g7.DSTRIDE])
            e[0x00:0x04] = g7.be32(6)
            if rng:
                e[0x08:0x0c], e[0x0c:0x10] = g7.be32(rng[0] << 8), g7.be32(rng[1] << 8)
            e[0x10:0x14] = g7.be32(default << 8)
            e[0x2c:0x30] = g7.be32(addr[long_])
            e[0x34:0x38] = g7.be32(addr[short])
            new += e
        e = bytearray(img[g7.DESC + (g7.SNARE_DESC + 4) * g7.DSTRIDE - BASE:][:g7.DSTRIDE])
        e[0x10:0x14] = g7.be32(m["decay"] << 8)
        new += e

        writes = []

        def w(va, old, new_):
            if cur[va - BASE:va - BASE + len(old)] != old:
                raise SystemExit(f"!! {va:#x} : {old.hex()} attendu, {cur[va - BASE:va - BASE + len(old)].hex()} trouvé")
            writes.append({"off": va - BASE, "old": old.hex(), "new": new_.hex()})

        def moveq(va, old, new_, reg_byte):
            w(va, bytes([reg_byte, old]), bytes([reg_byte, new_]))

        def jmp(va):
            return bytes.fromhex("4ef9") + g7.be32(va)

        writes.append(None)
        red = sprites.redirect_write(gx.CAVE)
        w(BASE + red["off"], bytes.fromhex(red["old"]), bytes.fromhex(red["new"]))
        w(gs.BOOT_CALL + 2, g7.be32(tg["boot_extra_hook"]), g7.be32(gx.CAVE))
        moved = {g7.DESC: gs.DESCN, g7.DESC + 8: gs.DESCN + 8, g7.DESC + 0x20: gs.DESCN + 0x20, g7.ROWS: gs.ROWSN,
                 g7.CCROWS: gs.CCROWSN, tg["sampler_name_table"]: names_at,
                 g7.UPDATE_TAB: upd_at, g7.RENDER_TAB: rnd_at, gs.MAP: map_at}
        want = {g7.DESC: 34, g7.DESC + 8: 1, g7.DESC + 0x20: 2, g7.ROWS: 4, g7.CCROWS: 2, gs.MAP: 1,
                g7.RENDER_TAB: 0}
        for old, new_ in moved.items():
            rs = g7.refs32(cur, old)
            if len(rs) != want.get(old, 1):
                raise SystemExit(f"!! références à {old:#x} : {len(rs)}")
            for va in rs:
                w(va, g7.be32(old), g7.be32(new_))
        w(gs.DISPATCH[0], cur[gs.DISPATCH[0] - BASE:gs.DISPATCH[0] - BASE + 6], jmp(ssyms["dispatch"]))
        jumps = g7.JUMPS + g8.JUMPS8
        for va in g7.BOUNDS:
            if va in {j[0] for j in jumps}:
                continue
            b0, b1 = cur[va - BASE], cur[va - BASE + 1]
            if b0 & 0xf1 != 0x70 or b1 not in (75, 76):
                raise SystemExit(f"!! {va:#x}")
            moveq(va, b1, b1 + 5 * n, b0)
        for va, reg in ((0x400a7dba, 0x72), (0x400a7df4, 0x70), (0x400147a4, 0x70),
                        (0x400148aa, 0x72), (0x400148b2, 0x70), (0x400a25e0, 0x70)):
            if cur[va - BASE] != reg or cur[va - BASE + 1] not in (5, 6):
                raise SystemExit(f"!! borne {va:#x}")
            moveq(va, cur[va - BASE + 1], top, reg)
        moveq(0x4005a572, 5, 6, 0x72)
        w(0x4005a2b8, bytes.fromhex("487800c0"), bytes.fromhex("4878") + (32 * nm).to_bytes(2, "big"))
        if nm > gs.MARKS_ROW:
            w(0x400a26a2, bytes.fromhex("7850428545f9"), jmp(ssyms["marks"]))
        else:
            moveq(0x400a26e8, cur[0x400a26e8 - BASE + 1], nm, 0x70)
        for va in (0x4001b696, 0x400a4096, 0x400a4f9e):
            moveq(va, 5, 7, 0x72)
        for va, old, sym in ga.ART_SITES:
            w(va, bytes.fromhex(old), bytes.fromhex("4eb9") + g7.be32(ssyms[sym]))
        chained = {0x4004df5c: "descr_hook", 0x4004df76: "descr_b_hook"}
        for va, old, sym in jumps:
            old = jmp(tg[chained[va]]) if va in chained else bytes.fromhex(old)
            w(va, old, jmp(ssyms[ga.ART_JUMPS.get(sym, sym)]))
        w(gs.AMP_ROW, bytes.fromhex("20065286eb88"), jmp(ssyms["amp_row"]))
        w(0x4005a6a6, jmp(tg["sampler_lfo_gate"]), jmp(ssyms["lfo_gate"]))
        w(0x4005a6b6, jmp(tg["sampler_amp_gate"]), jmp(ssyms["amp_gate"]))
        for va, old, sym in g7.CALLS:
            w(va, bytes.fromhex(old), bytes.fromhex("4eb9") + g7.be32(ssyms[sym]) + bytes.fromhex("4e71"))
        # navigateur bloqué dans /Wavetables (notes/52 §3quater)
        for va, old, sym in BROWSER:
            old = bytes.fromhex(old)
            if sym in ("wt_home", "wt_cursor"):
                new_ = bytes.fromhex("4eb9") + g7.be32(gsyms[sym])
            else:
                new_ = jmp(gsyms[sym]) + bytes.fromhex("4e71") * ((len(old) - 6) // 2)
            w(va, old, new_)

        parts = [
            {"dest": f"{pay:#x}", "hex": blob.hex()},
            {"dest": f"{glue_at:#x}", "hex": glue.hex()},
            {"dest": f"{gs.STUBS:#x}", "hex": stubs.hex()},
            {"dest": f"{gs.DATA:#x}", "hex": bytes(data).hex()},
            {"dest": f"{gs.DESCN:#x}", "cycles": [f"{g7.DESC:#x}", f"{g7.DESC + g7.NDESC * g7.DSTRIDE:#x}"]},
            {"dest": f"{gs.DESCN + g7.NDESC * g7.DSTRIDE:#x}", "hex": bytes(new).hex()},
        ] + art_parts
        lo_, hi_ = g7.DESC - BASE, g7.DESC - BASE + g7.NDESC * g7.DSTRIDE
        final, orig = bytearray(cur[lo_:hi_]), img[lo_:hi_]
        alg = g7.ALG_DESC * g7.DSTRIDE + 0x0c
        if struct.unpack_from(">I", final, alg)[0] != (first - 1) << 8:
            raise SystemExit("!! max du paramètre Algorithm")
        struct.pack_into(">I", final, alg, top << 8)
        # Env Pos : paramètre commun (groupe 7) à la place libre 0x0a, comme Attack / Filtre / Résonance de Model-TG
        e_at = EPOS_ID * g7.DSTRIDE
        if final[e_at:e_at + 8] != b"\xff" * 8:
            raise SystemExit("!! place 0x0a déjà prise")
        struct.pack_into(">14I", final, e_at, 7, EPOS_K, 0, 32512, 0, 0, 0xffffffff, 0xffffffff, 0, 0x600, 38,
                         addr[EPOS_NAMES[0]], 0x40129882, addr[EPOS_NAMES[1]])
        pt = g7.DESC + e_at + 44                    # ses noms aussi dans la table d'origine (recopiés par tg_sync)
        w(pt, cur[pt - BASE:pt - BASE + 12], struct.pack(">III", addr[EPOS_NAMES[0]], 0x40129882, addr[EPOS_NAMES[1]]))
        reloc = [[f"{gs.DESCN + k:#x}", orig[k:k + 4].hex(), final[k:k + 4].hex()]
                 for k in range(0, len(final), 4) if final[k:k + 4] != orig[k:k + 4]] + art_reloc
        size = bss_end - pay
        segs = gs.segments(parts, size)
        at = tg["at"]
        if at + sum(n_ for _, n_ in segs) > gs.END_LIMIT:
            raise SystemExit(f"!! ajout de {sum(n_ for _, n_ in segs)} o : l'image dépasserait {gs.END_LIMIT:#x}")
        (tmp / "segs.inc").write_text("".join(f"\t.long\t{a:#x}, {n_ // 4}\n" for a, n_ in segs))
        stub, _ = gm.assemble(tmp, "stub", gx.SRC / "stub.S", gx.CAVE, [
            f"-DPAYLOAD_SRC={at:#x}", f"-DPAYLOAD_DST={pay:#x}", f"-DPAYLOAD_LONGS={size // 4}", "-DPACK", f"-I{tmp}",
            f"-DCHAIN_TO={gsyms['wt_boot']:#x}"])
    if len(stub) > sprites.zone(gx.CAVE)[1]:
        raise SystemExit("!! crochet de démarrage trop grand pour sa place")
    writes[0] = {"off": gx.CAVE - BASE, "old": "ff" * len(stub), "new": stub.hex()}
    if cur[gx.CAVE - BASE:gx.CAVE - BASE + len(stub)] != b"\xff" * len(stub):
        raise SystemExit("!! place du crochet de démarrage déjà prise")
    writes.sort(key=lambda x: x["off"])
    for a_, b_ in zip(writes, writes[1:]):
        if a_["off"] + len(a_["new"]) // 2 > b_["off"]:
            raise SystemExit(f"!! écritures qui se chevauchent en {BASE + b_['off']:#x}")

    ids = gm.other_ids() | {"macro", "macro-tg", "model-tg", "acid", "acid-tg"}
    out = {
        "id": "wavetable-tg",
        "order": 36,
        "name": "Model-TG + Machine Wave : joue tes tables d'ondes (dossier /Wavetables)",
        "description": [
            "Version avec Model-TG (notes/52) : s'ajoute après model-tg-st, Wave est la 8e machine, après le Sampler ;",
            "sa sortie passe par l'étage d'amplitude de Model-TG (Attack, filtre).",
            "La table : un fichier de /Wavetables (créé s'il manque), ouvert dans le navigateur sur la piste de Wave,",
            "chargé et protégé par Model-TG (retouché en mémoire au démarrage). Copies par demi-octave préparées au",
            "chargement, dans la SDRAM libre au-dessus de Model-TG (0x46800000..0x47F00000) : pas de repliement.",
            "COLOR = position dans la table, SHAPE = enveloppe -> position (64 : rien), SWEEP / CONTOUR = coupure et",
            "résonance du passe-bas d'Acid, DECAY = enveloppe et chaîne d'ampli d'origine, PUNCH = accent.",
            "Code : tools/machines/wavetable/wt.c. Généré par tools/gen_wavetable.py. Aucun octet Elektron.",
        ],
        "device": "Model:Cycles",
        "os": "1.13",
        "section": 3,
        "requires": [tg["id"]],
        "conflicts": sorted(ids),
        "writes": writes,
        "append": {"at": f"{at:#x}", "dest": f"{pay:#x}", "size": size, "parts": parts, "reloc": reloc,
                   "pack": [[f"{a_:#x}", n_] for a_, n_ in segs]},
        "symbols": dict({k: f"{syms[k]:#x}" for k in ("wt_update", "wt_render", "wt_tick")},
                        **{k: f"{gsyms[k]:#x}" for k in ("wt_boot", "wt_or_any", "wt_np", "wt_led", "wt_open", "wt_patched")},
                        **{f"tg_{k}": f"{v:#x}" for k, v in f.items() if k != "old"}),
    }
    return out, dict(code=len(blob), glue=len(glue), bss=bss_end - pay - gm.BSS_OFF, image=sum(n_ for _, n_ in segs))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycles", required=True, help="model-cycles_OS1.13.syx officiel")
    ap.add_argument("--check", action="store_true", help="vérifie que le JSON versionné correspond")
    args = ap.parse_args()
    img = g7.cycles_main(args.cycles)
    if len(img) != gx.IMAGE_LEN:
        raise SystemExit("!! ce n'est pas le MAIN OS 1.13 officiel")
    tweak, info = build_tweak(img, gs.tg_context(img))
    text = json.dumps(tweak, indent=1) + "\n"
    print(f"  {tweak['id']} : {len(tweak['writes'])} écritures, code {info['code']} o + {info['glue']} o, variables "
          f"{info['bss']} o, ajout à l'image {info['image']} o")
    if gm.emit(OUT, text, args.check):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
