#!/usr/bin/env python3
"""Génère les tweaks de la machine Acid : une basse façon 303 (dent de scie -> carré, filtre en échelle à 4 pôles sans
retard, passe-bas ou passe-haut, résonance écrasée par un coude), en machine ajoutée du Model:Cycles (notes/51).

  - 26-acid.json : 7e machine, après les 6 d'origine ;
  - 35-acid-tg.json : avec Model-TG (après model-tg-st), 8e machine, après son Sampler.

Le moteur est notre code (tools/machines/acid/acid.c, en entiers, compilé ici) ; ses tables (coupure, enveloppe,
hauteur) sont calculées ici et écrites dans acid_tables.h au moment de la compilation. La mécanique des machines
ajoutées est celle de MACRO (gen_macro.py, notes/43), elle-même celle des moteurs du Syntakt (gen_syntakt_engines.py,
notes/20) : mêmes détours, mêmes tables déplacées, mêmes adresses dans la charge utile. Aucun octet Elektron : le
MAIN OS officiel sert à vérifier les octets d'origine, et la table des descripteurs est recopiée au build depuis TON
fichier (recette « cycles »).

    python3 tools/gen_acid.py --cycles model-cycles_OS1.13.syx [--check]

Le JSON versionné est compilé par m68k-linux-gnu-gcc 13.3 (Ubuntu 24.04, comme MACRO) : un autre GCC donne
d'autres octets, et --check le dit.
"""
import argparse
import json
import math
import pathlib
import struct
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "emu"))

import gen_macro as gm             # noqa: E402
import gen_sdvintage_exact as gx   # noqa: E402
import gen_sdvintage_7th as g7     # noqa: E402
import gen_syntakt_machines as g8  # noqa: E402
import gen_syntakt_engines as gs   # noqa: E402
import sprites                     # noqa: E402
import usb_steady                  # noqa: E402
import voice_loop                  # noqa: E402

DEV = HERE.parent / "tweaks" / "model-cycles_OS1.13"
OUT = DEV / "26-acid.json"
OUT_TG = DEV / "35-acid-tg.json"
SRC = HERE / "machines" / "acid"
BASE = gx.BASE

CFLAGS = ["-mcpu=54418", "-O2", "-U_FORTIFY_SOURCE", "-ffreestanding", "-fno-builtin",
          "-fno-tree-loop-distribute-patterns", "-nostdlib", "-fno-pic", "-fno-common", "-ffunction-sections",
          "-fdata-sections", "-fomit-frame-pointer", "-Wall", "-Wextra", "-Werror"]

# --- la machine (comme une entrée de gs.CATALOG) -----------------------------------------------------------
# knobs : COLOR, SHAPE, SWEEP, CONTOUR = (nom long en mots de 8 lettres au plus, nom court, défaut) ; decay : défaut
# de l'Amp Decay ; image : celle que montre shown() (TONE, dont Acid reprend la chaîne d'ampli), remplacée par
# les images d'Acid dans ses propres détours (ART)
MACHINE = dict(name="Acid", image=4, decay=50,
               knobs=(("Cutoff", "CUT", 30), ("Wave", "WAVE", 0), ("Reso", "RES", 90), ("Env Mod", "ENV", 100)))

# --- tables (acid_tables.h) --------------------------------------------------------------------------------
FS, BLOCK = 48000, 32
FDEC_ACCENT_MAX = 57             # accent : décroissance du filtre bornée à ~200 ms (DECAY 57)


def q31(x):
    return max(-2 ** 31, min(2 ** 31 - 1, round(x * 2 ** 31)))


def tables_h():
    """Les tables du moteur, en entiers : coupure (G = g/(1+g), g = tan(pi fc/fs), 1/16 d'octave au-dessus de 10 Hz,
    jusqu'à 0,45 fs), décroissance de l'enveloppe du filtre par bloc (DECAY 0..127 : 30 ms .. 2 s), incrément de phase
    de la note 0 fois 2^(i/192) (1/16 de demi-ton)."""
    ng = int(16 * math.log2(0.45 * FS / 10)) + 2
    g_tab = []
    for i in range(ng):
        g = math.tan(math.pi * min(10 * 2 ** (i / 16), 0.45 * FS) / FS)
        g_tab.append(q31(g / (1 + g)))
    fdec = [q31(math.exp(-1 / (0.03 * (2 / 0.03) ** (d / 127) * FS / BLOCK))) for d in range(128)]
    dt0 = 440 * 2 ** (-69 / 12) / FS * 2 ** 32
    pitch = [round(dt0 * 2 ** (i / 192)) for i in range(193)]
    return "\n".join([
        "/* écrit par tools/gen_acid.py : ne pas modifier */",
        "#pragma once",
        f"#define G_TAB_N {ng}",
        "static const s32 G_TAB[G_TAB_N] = {" + ", ".join(map(str, g_tab)) + "};",
        "static const s32 FDEC_TAB[128] = {" + ", ".join(map(str, fdec)) + "};",
        f"#define FDEC_ACCENT_MAX {FDEC_ACCENT_MAX}",
        "static const u32 PITCH_TAB[193] = {" + ", ".join(f"{x}u" for x in pitch) + "};",
    ]) + "\n"


# --- images (notes/51 §3.4) ----------------------------------------------------------------------------------
# Les machines ont 3 images (Bitmap, 1 bit par pixel, colonne par colonne, y = 0 en bas, notes/39 §2), construites au
# démarrage dans 3 tableaux de 6 : la fiche 48 x 33 (écran MACHINES), la lettre 34 x 34 (écran MACHINES, 0x4001b6a6) et
# la petite lettre 25 x 22 (0x400a4de6, 0x400a40bc, 0x400a4fc6). Acid a les siennes : la fiche de TONE recopiée au build
# depuis TON OS (« CLASS:SYNTH ») puis retouchée par relocalisations (« STYLE:ACID », ses notes), et un smiley dessiné
# ici. Leurs masques : ceux de l'OS (entièrement opaques).
TONE = 4
ART = dict(card=(48, 33, 0x4016ac78, 0x4016adf8, 0x180), mid=(34, 34, 0x4017c20c, 0x4017c31c, 0x110),
           small=(25, 22, 0x4017a218, 0x4017a27c, 0x64))       # (largeur, hauteur, masque, image 0, pas)
BITMAP_VT = 0x401117c8                                          # vtable posée par le constructeur 0x40070172
ART_OFF = 0x1800                                                # dans la charge utile, après le code et les tables
STARS = (4, 5, 3)                                               # STR, DEX, MAG de la fiche (choix de Kevin)
FONT = {"A": (".#.", "#.#", "###", "#.#", "#.#"), "C": (".##", "#..", "#..", "#..", ".##"),
        "I": ("###", ".#.", ".#.", ".#.", "###"), "D": ("##.", "#.#", "#.#", "#.#", "##.")}   # 3 x 5, comme l'OS
DIAMOND = ((".#.", "###", "#####", "###", ".#."), (".#.", "#.#", "#...#", "#.#", ".#."))      # plein, vide


def bm_words(h):
    return (h + 31) // 32


def bm_read(data, w, h):
    """g[y][x] d'une image au format Bitmap (0x400701b8 : bit 31 - (y & 31) du mot x * mots + y / 32)."""
    n = bm_words(h)
    return [[(struct.unpack_from(">I", data, 4 * (x * n + y // 32))[0] >> (31 - (y & 31))) & 1 for x in range(w)]
            for y in range(h)]


def bm_bytes(g, w, h):
    n, out = bm_words(h), bytearray(4 * w * bm_words(h))
    for x in range(w):
        for y in range(h):
            if g[y][x]:
                k = x * n + y // 32
                struct.pack_into(">I", out, 4 * k, struct.unpack_from(">I", out, 4 * k)[0] | (1 << (31 - (y & 31))))
    return bytes(out)


def card_grid(tone):
    """La fiche d'Acid : celle de TONE (« CLASS:SYNTH », « STYLE:RAW », STR/DEX/MAG), « STYLE:ACID » et ses notes."""
    g = [row[:] for row in tone]
    top = 32 - 7                                                # 2e ligne (y du haut des lettres)
    for y in range(top - 4, top + 1):
        for x in range(24, 48):
            g[y][x] = 0
    for k, ch in enumerate("ACID"):
        for r, line in enumerate(FONT[ch]):
            for c, b in enumerate(line):
                g[top - r][24 + 4 * k + c] = int(b == "#")
    for row, n in enumerate(STARS):
        ytop = 32 - 14 - 7 * row
        for i in range(5):
            for r, line in enumerate(DIAMOND[0 if i < n else 1]):
                for c, b in enumerate(line):
                    g[ytop - r][18 + 6 * i - len(line) // 2 + c] = int(b == "#")
    return g


def smiley(w, h, face, eye, smile_r, smile_w):
    """Disque plein, yeux et sourire évidés (y monte : les yeux au-dessus du centre)."""
    cx, cy = (w - 1) / 2, (h - 1) / 2
    ex, ey, ew, eh = eye
    g = [[0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            dx, dy = x - cx, y - cy
            if dx * dx + dy * dy > face * face:
                continue
            g[y][x] = 1
            if any(((dx - s * ex) / ew) ** 2 + ((dy - ey) / eh) ** 2 <= 1 for s in (-1, 1)):
                g[y][x] = 0
            d, ang = math.hypot(dx, dy + 0.15 * smile_r), math.degrees(math.atan2(dy + 0.15 * smile_r, dx))
            if abs(d - smile_r) <= smile_w / 2 and -160 <= ang <= -20:
                g[y][x] = 0
    return g


def art(img, pay):
    """Les 3 images et leurs objets Bitmap : (parts, reloc, adresses des objets)."""
    u32 = lambda va: struct.unpack_from(">I", img, va - BASE)[0]
    if u32(0x400b13b6 + 2) != ART["card"][2]:
        raise SystemExit("!! masque de la fiche")
    w, h, mask, im0, step = ART["card"]
    tone_at = im0 + TONE * step
    tone_bytes = img[tone_at - BASE:tone_at - BASE + step]
    card = bm_bytes(card_grid(bm_read(tone_bytes, w, h)), w, h)
    grids = dict(mid=smiley(34, 34, 16.6, (5.2, 4.5, 2.2, 3.8), 9.5, 3.2),
                 small=smiley(25, 22, 11.2, (3.6, 3.0, 1.5, 2.6), 6.3, 2.4))
    objs_at = pay + ART_OFF
    at = objs_at + 0x60
    where, parts, reloc, objs = {}, [], [], bytearray()
    where["card"] = at
    parts.append({"dest": f"{at:#x}", "cycles": [f"{tone_at:#x}", f"{tone_at + step:#x}"]})
    reloc = [[f"{at + k:#x}", tone_bytes[k:k + 4].hex(), card[k:k + 4].hex()]
             for k in range(0, step, 4) if card[k:k + 4] != tone_bytes[k:k + 4]]
    at += step
    for name in ("mid", "small"):
        w_, h_ = ART[name][:2]
        data = bm_bytes(grids[name], w_, h_)
        where[name] = at
        parts.append({"dest": f"{at:#x}", "hex": data.hex()})
        at += len(data)
    for name in ("card", "mid", "small"):                       # comme le constructeur 0x40070172
        w_, h_, mask_ = ART[name][:3]
        objs += struct.pack(">IIIIIIB3x", BITMAP_VT, w_, h_, bm_words(h_), where[name], mask_, 0)
    parts.insert(0, {"dest": f"{objs_at:#x}", "hex": bytes(objs).hex()})
    addr = {name: objs_at + 28 * i for i, name in enumerate(("card", "mid", "small"))}
    return parts, reloc, addr, at


def art_asm(addr, first, tg, others=False):
    """Détours des images d'Acid (machine first), à la suite de gs.detours_asm : drum_icons et small_icon avec nos
    objets ; aux 3 autres sites, jsr à la place de « add.l tableau, %d0 » (d0 = 28 x machine). Avec Model-TG, son
    Sampler (6) garde l'image de CHORD."""
    sampler = "\tcmpi.l\t#168, %d0\n\tbne.s\t1f\n\tmove.l\t#140, %d0\n" if tg else ""          # Sampler -> CHORD
    if others:                                                  # avec les moteurs du Syntakt : toute machine > 5
        sampler = "\tcmpi.l\t#168, %d0\n\tbcs.s\t1f\n\tmove.l\t#140, %d0\n"
    return f"""
	.globl	acid_drum_icons
acid_drum_icons:
	move.l	%d3, %d0
	bsr.w	shown
	move.l	%d0, %d4
	lsl.l	#2, %d0
	lsl.l	#5, %d4
	sub.l	%d0, %d4
	pea	0x1
	pea	0x17
	pea	0x20
	lea	0x40071da4, %a2
	movea.l	0x40fe32cc, %a1
	adda.l	%d4, %a1
	add.l	0x40fe384c, %d4
	moveq	#{first}, %d0
	cmp.l	%d0, %d3
	bne.s	1f
	lea	{addr['card']:#x}, %a1
	move.l	#{addr['mid']:#x}, %d4
1:	move.l	%a1, -(%sp)
	move.l	%d2, -(%sp)
	jsr	(%a2)
	lea	48(%sp), %sp
	pea	0x1
	pea	0x22
	pea	0x60
	move.l	%d4, -(%sp)
	move.l	%d2, -(%sp)
	jsr	(%a2)
	lea	20(%sp), %sp
	jmp	0x400a2680
	.globl	acid_small_icon
acid_small_icon:
	lea	10(%a0), %a0
	move.l	%a0, -(%sp)
	move.l	16(%fp), -(%sp)
	moveq	#{first}, %d0
	cmp.l	%d0, %d2
	bne.s	1f
	move.l	#{addr['small']:#x}, %d0
	jmp	0x400a4dec
1:	move.l	%d2, %d0
	bpl.s	2f
	moveq	#0, %d0
2:	moveq	#5, %d1
	cmp.l	%d0, %d1
	bge.s	3f
	bsr.w	shown
	moveq	#5, %d1
	cmp.l	%d0, %d1
	bge.s	3f
	moveq	#5, %d0
3:	jmp	0x400a4dde
	.globl	acid_mid_at
acid_mid_at:
	cmpi.l	#{28 * first}, %d0
	bne.s	2f
	move.l	#{addr['mid']:#x}, %d0
	rts
2:
{sampler}1:	add.l	0x40fe384c, %d0
	rts
	.globl	acid_small_at
acid_small_at:
	cmpi.l	#{28 * first}, %d0
	bne.s	2f
	move.l	#{addr['small']:#x}, %d0
	rts
2:
{sampler}1:	add.l	0x40fe37f0, %d0
	rts
"""


ART_SITES = ((0x4001b6a6, "d0b940fe384c", "acid_mid_at"), (0x400a40bc, "d0b940fe37f0", "acid_small_at"),
             (0x400a4fc6, "d0b940fe37f0", "acid_small_at"))
ART_JUMPS = {"drum_icons": "acid_drum_icons", "small_icon": "acid_small_icon"}


LINK = """SECTIONS
{{
  .text {code:#x} : {{ *(.text.acid_update) *(.text.acid_render) *(.text*) }}
  .rodata : {{ *(.rodata*) }}
  .data : {{ *(.data*) }}
  .bss {bss:#x} (NOLOAD) : {{ *(.bss*) *(COMMON) }}
  /DISCARD/ : {{ *(.comment) *(.note*) *(.eh_frame*) }}
}}
"""
BSS_OFF = gm.BSS_OFF


def compile_machine(tmp, pay, defs=(), bss_off=BSS_OFF):
    """Le moteur, lié à pay (code, tables) et pay + BSS_OFF (états des 6 pistes). Renvoie (octets, symboles, fin du
    BSS)."""
    (tmp / "acid_tables.h").write_text(tables_h())
    o, ld, elf, out = tmp / "acid.o", tmp / "link.ld", tmp / "acid.elf", tmp / "acid.bin"
    gx.run([gx.CROSS + "gcc", *CFLAGS, *defs, f"-I{tmp}", "-c", str(SRC / "acid.c"), "-o", str(o)])
    ld.write_text(LINK.format(code=pay, bss=pay + bss_off))
    rwx = ["--no-warn-rwx-segments"] if "no-warn-rwx" in gx.run([gx.CROSS + "ld", "--help"]) else []   # binutils >= 2.39
    gx.run([gx.CROSS + "ld", "-T", str(ld), "--gc-sections", *rwx, "-e", "acid_update",
            "-u", "acid_render", "-o", str(elf), str(o)])
    secs = {}
    for line in gx.run([gx.CROSS + "objdump", "-h", str(elf)]).splitlines():
        f = line.split()
        if len(f) > 4 and f[0].isdigit():
            secs[f[1]] = (int(f[3], 16), int(f[2], 16))      # adresse, taille
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
    if len(blob) > ART_OFF:
        raise SystemExit(f"!! code et tables trop grands : {len(blob)} o (les images commencent à +{ART_OFF:#x})")
    bss = secs.get(".bss", (pay + bss_off, 0))
    if bss[0] != pay + bss_off:
        raise SystemExit("!! BSS")
    return blob, syms, (bss[0] + bss[1] + 3) & ~3


def build_tweak(img, tg=None):
    """Tweak de la machine Acid (comme gm.build_tweak). tg : Model-TG (gs.tg_context) pour la version combinée."""
    pay = gs.PAY_TG if tg else gs.PAY_ALONE
    gs.set_base(pay)
    first = gm.TG_FIRST if tg else 6             # 6 machines d'origine, le Sampler avec Model-TG, puis Acid
    nm, n = first + 1, 1
    top = nm - 1
    cur = tg["img"] if tg else img
    u32 = lambda va: struct.unpack_from(">I", cur, va - BASE)[0]
    m = MACHINE
    with tempfile.TemporaryDirectory() as d:
        tmp = pathlib.Path(d)
        blob, syms, bss_end = compile_machine(tmp, pay, [f"-DSLD_BASE={tg['SLD_BASE']:#x}",   # slide 303 (§10.5)
                                                         f"-DSLD_INIT={tg['sld_init']:#x}"] if tg else [])
        art_parts, art_reloc, art_addr, art_end = art(img, pay)
        if art_end > pay + BSS_OFF:
            raise SystemExit("!! images")
        names_at, upd_at, rnd_at, map_at = gs.DATA, gs.DATA + 4 * nm, gs.DATA + 8 * nm, gs.DATA + 16 * nm
        stubs, ssyms = gm.assemble(tmp, "det", gs.detours_asm(n, [m["image"]], [76], tg) + art_asm(art_addr, first, tg)
                                   + (gm.dispatch_tg_asm(syms, rnd_at, tg) if tg else ""), gs.STUBS)
        if gs.STUBS + len(stubs) > gs.DATA:
            raise SystemExit("!! détours trop grands")

        # --- données : noms, tables update/render, machine -> enregistrement, chaînes
        strings = [m["name"]] + [k[i] for k in m["knobs"] for i in (0, 1)]
        at, addr = map_at + ((nm + 3) & ~3), {}
        for s_ in strings:
            if s_ not in addr:
                addr[s_] = at
                at += len(s_) + 1
        if tg:                                  # noms : ceux de Model-TG
            blob_u32 = lambda va: struct.unpack_from(">I", tg["blob"], va - tg["blob_at"])[0]
            names = [blob_u32(tg["sampler_name_table"] + 4 * i) for i in range(7)] + [addr[m["name"]]]
        else:
            names = [u32(g7.NAMES + 4 * i) for i in range(6)] + [addr[m["name"]]]
        pad = [u32(g7.UPDATE_TAB)] * (first - 6), [u32(g7.RENDER_TAB)] * (first - 6)   # entrée du Sampler : jamais lue
        upd = [u32(g7.UPDATE_TAB + 4 * i) for i in range(6)] + pad[0] + [syms["acid_update"]]
        rnd = [u32(g7.RENDER_TAB + 4 * i) for i in range(6)] + pad[1] + [syms["acid_render"]]
        data = bytearray()
        for t in (names, upd, rnd, range(1, nm + 1)):
            data += b"".join(g7.be32(x) for x in t)
        data += cur[gs.MAP - BASE:gs.MAP - BASE + 6] + bytes(range(6, nm)) + bytes(((nm + 3) & ~3) - nm)
        for s_ in addr:
            data += s_.encode("ascii") + b"\0"
        if gs.DATA + len(data) > gs.DESCN:
            raise SystemExit("!! données")

        # --- 5 descripteurs, sur le modèle de ceux de SNARE
        new = bytearray()
        for k, (long_, short, default, *rng) in enumerate(m["knobs"]):
            if any(len(w_) > 8 for w_ in long_.split()):
                raise SystemExit(f"!! {long_} : la fenêtre des potards n'affiche que des mots de 8 lettres (notes/18 §10)")
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

        # --- écritures (comme gm.build_tweak sans Model-TG)
        writes = []

        def w(va, old, new_):
            if cur[va - BASE:va - BASE + len(old)] != old:
                raise SystemExit(f"!! {va:#x} : {old.hex()} attendu, {cur[va - BASE:va - BASE + len(old)].hex()} trouvé")
            writes.append({"off": va - BASE, "old": old.hex(), "new": new_.hex()})

        def moveq(va, old, new_, reg_byte):
            w(va, bytes([reg_byte, old]), bytes([reg_byte, new_]))

        def jmp(va):
            return bytes.fromhex("4ef9") + g7.be32(va)

        writes.append(None)                     # crochet de démarrage : écrit plus bas (il porte la liste des morceaux)
        red = sprites.redirect_write(gx.CAVE)
        w(BASE + red["off"], bytes.fromhex(red["old"]), bytes.fromhex(red["new"]))
        if tg:                                  # notre crochet, puis le sien
            w(gs.BOOT_CALL + 2, g7.be32(tg["boot_extra_hook"]), g7.be32(gx.CAVE))
        else:
            w(gx.HOOK, bytes.fromhex(gx.HOOK_OLD), jmp(gx.CAVE) + bytes.fromhex("4e71"))
        moved = {g7.DESC: gs.DESCN, g7.DESC + 8: gs.DESCN + 8, g7.DESC + 0x20: gs.DESCN + 0x20, g7.ROWS: gs.ROWSN,
                 g7.CCROWS: gs.CCROWSN, tg["sampler_name_table"] if tg else g7.NAMES: names_at,
                 g7.UPDATE_TAB: upd_at, g7.RENDER_TAB: rnd_at, gs.MAP: map_at}
        want = {g7.DESC: 34, g7.DESC + 8: 1, g7.DESC + 0x20: 2, g7.ROWS: 4 if tg else 5, g7.CCROWS: 2, gs.MAP: 1,
                g7.RENDER_TAB: 0 if tg else 1}
        for old, new_ in moved.items():
            rs = g7.refs32(cur, old)
            if len(rs) != want.get(old, 1):
                raise SystemExit(f"!! références à {old:#x} : {len(rs)}")
            for va in rs:
                w(va, g7.be32(old), g7.be32(new_))
        if tg:
            w(gs.DISPATCH[0], cur[gs.DISPATCH[0] - BASE:gs.DISPATCH[0] - BASE + 6], jmp(ssyms["dispatch"]))
        jumps = g7.JUMPS + g8.JUMPS8
        for va in g7.BOUNDS:
            if va in {j[0] for j in jumps}:
                continue
            b0, b1 = cur[va - BASE], cur[va - BASE + 1]
            if b0 & 0xf1 != 0x70 or b1 not in (75, 76):
                raise SystemExit(f"!! {va:#x}")
            moveq(va, b1, b1 + 5 * n, b0)
        for va, reg in ((0x400a7dba, 0x72), (0x400a7df4, 0x70), (0x4005a6a6, 0x72), (0x400147a4, 0x70),
                        (0x400148aa, 0x72), (0x400148b2, 0x70), (0x400a25e0, 0x70)):
            if tg and va == 0x4005a6a6:
                continue                        # détour sampler_lfo_gate de Model-TG : chaîné plus bas
            if cur[va - BASE] != reg or cur[va - BASE + 1] not in (5, 6):
                raise SystemExit(f"!! borne {va:#x}")
            moveq(va, cur[va - BASE + 1], top, reg)
        moveq(0x4005a572, 5, 6, 0x72)
        w(0x4005a2b8, bytes.fromhex("487800c0"), bytes.fromhex("4878") + (32 * nm).to_bytes(2, "big"))
        if nm > gs.MARKS_ROW:
            w(0x400a26a2, bytes.fromhex("7850428545f9"), jmp(ssyms["marks"]))
        else:
            moveq(0x400a26e8, cur[0x400a26e8 - BASE + 1], nm, 0x70)
        if tg:                                  # borne 5 -> 7 : le Sampler et Acid passent, le reste replié sur 5
            for va in (0x4001b696, 0x400a4096, 0x400a4f9e):
                moveq(va, 5, 7, 0x72)
        else:                                   # repli des machines > 5 : 6
            for va in (0x4001b69c, 0x400a40a6, 0x400a4fb0):
                moveq(va, 5, 6, 0x70)
        for va, old, sym in ART_SITES:
            w(va, bytes.fromhex(old), bytes.fromhex("4eb9") + g7.be32(ssyms[sym]))
        chained = {0x4004df5c: "descr_hook", 0x4004df76: "descr_b_hook"}
        for va, old, sym in jumps:
            old = jmp(tg[chained[va]]) if tg and va in chained else bytes.fromhex(old)
            w(va, old, jmp(ssyms[ART_JUMPS.get(sym, sym)]))
        if tg:
            w(gs.AMP_ROW, bytes.fromhex("20065286eb88"), jmp(ssyms["amp_row"]))
            w(0x4005a6a6, jmp(tg["sampler_lfo_gate"]), jmp(ssyms["lfo_gate"]))
            w(0x4005a6b6, jmp(tg["sampler_amp_gate"]), jmp(ssyms["amp_gate"]))
        for va, old, sym in g7.CALLS:
            w(va, bytes.fromhex(old), bytes.fromhex("4eb9") + g7.be32(ssyms[sym]) + bytes.fromhex("4e71"))

        # --- charge utile
        parts = [
            {"dest": f"{pay:#x}", "hex": blob.hex()},
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
        reloc = [[f"{gs.DESCN + k:#x}", orig[k:k + 4].hex(), final[k:k + 4].hex()]
                 for k in range(0, len(final), 4) if final[k:k + 4] != orig[k:k + 4]] + art_reloc
        size = bss_end - pay
        segs = gs.segments(parts, size)
        at = tg["at"] if tg else BASE + gx.IMAGE_LEN
        if at + sum(n_ for _, n_ in segs) > gs.END_LIMIT:
            raise SystemExit(f"!! ajout de {sum(n_ for _, n_ in segs)} o : l'image dépasserait {gs.END_LIMIT:#x}")
        (tmp / "segs.inc").write_text("".join(f"\t.long\t{a:#x}, {n_ // 4}\n" for a, n_ in segs))
        stub, _ = gm.assemble(tmp, "stub", gx.SRC / "stub.S", gx.CAVE, [
            f"-DPAYLOAD_SRC={at:#x}", f"-DPAYLOAD_DST={pay:#x}", f"-DPAYLOAD_LONGS={size // 4}", "-DPACK", f"-I{tmp}",
            *([f"-DCHAIN_TO={tg['boot_extra_hook']:#x}"] if tg else [])])
    if len(stub) > sprites.zone(gx.CAVE)[1]:
        raise SystemExit("!! crochet de démarrage trop grand pour sa place")
    writes[0] = {"off": gx.CAVE - BASE, "old": "ff" * len(stub), "new": stub.hex()}
    if cur[gx.CAVE - BASE:gx.CAVE - BASE + len(stub)] != b"\xff" * len(stub):
        raise SystemExit("!! place du crochet de démarrage déjà prise")
    writes.sort(key=lambda x: x["off"])
    for a_, b_ in zip(writes, writes[1:]):
        if a_["off"] + len(a_["new"]) // 2 > b_["off"]:
            raise SystemExit(f"!! écritures qui se chevauchent en {BASE + b_['off']:#x}")

    tid = "acid-tg" if tg else "acid"
    ids = gm.other_ids() | {"macro", "macro-tg", "model-tg"} | ({"acid"} if tg else {"model-tg-st"})
    out = {
        "id": tid,
        "order": 35 if tg else 26,
        "name": ("Model-TG + " if tg else "")
        + "Machine Acid : une basse façon 303 (scie -> carré, filtre en échelle passe-bas / passe-haut)",
        "description": ([
            "Version combinée avec Model-TG (notes/31, notes/51) : s'ajoute après model-tg-st, Acid est la 8e machine,",
            "après le Sampler ; sa sortie passe par l'étage d'amplitude de Model-TG (Attack, filtre).",
        ] if tg else [
            "Machine Acid en 7e machine, après les 6 d'origine (notes/51).",
        ]) + [
            "COLOR = filtre façon DJ (passe-bas 20 Hz -> 20 kHz, ouvert à 64, passe-haut 10 Hz -> 20 kHz), SHAPE = scie",
            "-> carré, SWEEP = résonance (auto-oscillation en haut), CONTOUR = enveloppe du filtre (bipolaire, 64 : rien),",
            "DECAY = durée de l'enveloppe du filtre et chaîne d'ampli d'origine réglée comme TONE, PUNCH = accent.",
            "Filtre en échelle à 4 pôles sans retard, résonance écrasée par un coude résolu exactement. Une voix muette",
            "n'est pas calculée. Code : tools/machines/acid/acid.c. Généré par tools/gen_acid.py. Aucun octet Elektron.",
        ],
        "device": "Model:Cycles",
        "os": "1.13",
        "section": 3,
    }
    if tg:
        out["requires"] = [tg["id"]]
    out.update({
        "conflicts": sorted(ids),
        "writes": writes,
        "append": {"at": f"{at:#x}", "dest": f"{pay:#x}", "size": size, "parts": parts, "reloc": reloc,
                   "pack": [[f"{a_:#x}", n_] for a_, n_ in segs]},
        # pour la preuve (tools/emu/test_acid.py) : les entrées du moteur
        "symbols": dict({k: f"{syms[k]:#x}" for k in ("acid_update", "acid_render")},
                        **{f"art_{k}": f"{v:#x}" for k, v in art_addr.items()}),
    })
    if tg:                                # pour la preuve du slide : les états des pistes
        out["symbols"]["acid_tracks"] = f"{syms['tracks']:#x}"
    if not tg:                            # comme MACRO seule : envoi à l'USB à heure fixe (notes/35), boucle des voix
        out = usb_steady.add_to(out)      # (notes/36) ; la version combinée les a par model-tg-st
        out = voice_loop.add_to(out)
    return out, dict(code=len(blob), bss=bss_end - pay - BSS_OFF, image=sum(n_ for _, n_ in segs), syms=syms)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycles", required=True, help="model-cycles_OS1.13.syx officiel")
    ap.add_argument("--check", action="store_true", help="vérifie que le JSON versionné correspond")
    args = ap.parse_args()
    img = g7.cycles_main(args.cycles)
    if len(img) != gx.IMAGE_LEN:
        raise SystemExit("!! ce n'est pas le MAIN OS 1.13 officiel")
    bad = 0
    for path, tg in ((OUT, None), (OUT_TG, gs.tg_context(img))):
        tweak, info = build_tweak(img, tg)
        text = json.dumps(tweak, indent=1) + "\n"
        print(f"  {tweak['id']} : {len(tweak['writes'])} écritures, code et tables {info['code']} o, variables "
              f"{info['bss']} o, ajout à l'image {info['image']} o")
        bad += gm.emit(path, text, args.check)
    if bad:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
