#!/usr/bin/env python3
"""Génère tweaks/model-cycles_OS1.13/36-wavetable.json : la machine Wave, SEULE (sans Model-TG), qui joue une table
d'ondes pré-travaillée puisée dans /Wavetables (notes/52, notes/54).

  - moteur : tools/machines/wavetable/wt.c (oscillateur sur les copies par octave gravées dans le fichier, passe-bas
    d'Acid, chaîne d'ampli d'origine), ses tables écrites ici dans wt_tables.h ;
  - chargeur : notre code (glue_asm) dans le bloc ajouté après l'image. Deux accroches dans l'OS :
      * 0x400a6426 : le choix d'un fichier dans le navigateur (bloqué dans /Wavetables) note son entrée de 16 o
        pour la piste active (stock : kit = *0x40a78888, son + 28 + 100 t, machine à +38 comme Model-TG) ;
      * 0x4008171e : l'appui sur un pad lit le fichier choisi (API de fichiers de l'OS : 0x4007e4f4 / 0x4007baaa /
        0x4007bc1c) dans 0x46800000 + 0x300000 t (wt_load), puis pose WT_BASE[t] = tampon + 64 et WT_COUNT[t] = (octets de PCM de l'en-tête, bornés au fichier)/2.
    Plus les 5 accroches du navigateur bloqué (notes/52 §3quater), le YES qui charge la table quand le preset échoue
    (0x400a6732, message en 0x400a6752 ; méthode de Model-TG) et la table retenue : jeton « W » + clé + empreinte dans
    le nom du son, rechargé par une tâche de l'interface (cases vides des LedHandler) ;
  - identité Transfer CYC/SMP (smp_glue_asm, notes/55) : la commande SysEx F0 00 20 3C 0F 00 <m> F7 fait répondre la
    machine en Model:Samples (m = 1) pour que la page de conversion range les tables, sans Model-TG ; 6 sites de l'OS ;
  - mécanique des machines ajoutées : celle d'Acid seule (gen_acid.py, 26-acid.json) : 7e machine (index 6), crochet
    de démarrage 0x400004b2, aucun détour de la boucle des voix (les tables update/render déplacées suffisent) ;
  - la table est convertie par l'outil web (docs/convert/, référence tools/wt_convert.py) : la machine ne calcule
    aucune copie, elle lit la disposition fixe (LGC, OFF, S_TOTAL) ; un fichier non converti ne joue rien.

    python3 tools/gen_wavetable.py --cycles model-cycles_OS1.13.syx [--check]

Le JSON versionné est compilé par m68k-elf-gcc 16.2 (Homebrew) avec les binutils 2.38 d'Ubuntu 22.04 (M68K_CROSS vers
un gcc qui appelle cet assembleur par -B), comme les moteurs du Syntakt et SD VINTAGE v2 : un autre GCC donne d'autres
octets, et --check le dit.
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

import gen_acid as ga              # noqa: E402
import gen_macro as gm             # noqa: E402
import gen_sdvintage_exact as gx   # noqa: E402
import gen_sdvintage_7th as g7     # noqa: E402
import gen_syntakt_machines as g8  # noqa: E402
import gen_syntakt_engines as gs   # noqa: E402
import sprites                     # noqa: E402
import usb_steady                  # noqa: E402
import voice_loop                  # noqa: E402

DEV = HERE.parent / "tweaks" / "model-cycles_OS1.13"
OUT = DEV / "36-wavetable.json"
SRC = HERE / "machines" / "wavetable"
BASE = gx.BASE

MACHINE = dict(name="Wave", image=4, decay=60,
               knobs=(("Position", "POS", 0), ("Flt Env", "FENV", 64), ("Cutoff", "CUT", 127), ("Reso", "RES", 0)))
EPOS_ID, EPOS_K = 0x0a, 27        # MACHINE tenue + COLOR : enveloppe -> position (place libre 0x0a, k = 27)
EPOS_NAMES = ("Env Pos", "EPOS")
WT_MACH = 6                       # 7e machine, apres les 6 d'origine
NCOPY = 11                        # copies, une par octave : 1024 / 2^c harmoniques
FOLD_OK = 28000.0                 # repli au-dessus de 20 kHz : inaudible
ART_OFF = 0x8000                  # images, apres le code

# --- l'OS (navigateur, notes/52 §3quater) ---
FOLDER = 0x40148cb0
ACTIVE = 0x40a700c4
BROWSER = ((0x400a6c20, "4fefffe048d70c0c", "wt_open"), (0x400a40e2, "42a74eb940081bd6", "wt_close"),
           (0x4003fa52, "2f2802804eb94007cf72", "wt_yes_up"), (0x400a6f9c, "2f2a02804eb94007cf72", "wt_key_up"),
           (0x400a70b0, "4eb94007d2f0", "wt_home"))

# --- l'OS (chargeur, notes/54) ---
KIT = 0x40a78888                  # kit d'origine : son(t) = kit + 28 + 100 t (KIT_SND, SND_SIZE de Model-TG)
MACH_OFF = 38                     # octet de machine du son (decimal, `mvzb %a0@(38)` de Model-TG)
PARSE_SITE, PARSE_OLD = 0x400a6426, "4eb9400a3052"     # jsr 0x400a3052 (lecture du preset d'origine), 6 o
PARSE_SITE2 = 0x400a6602          # meme appel dans le YES du navigateur (0x400a64fa), memes arguments
PARSE_CALL = 0x400a3052
NOTE_SITE, NOTE_OLD = 0x4008171e, "4e56ff98707f"       # link.w %fp,#-104 ; moveq #127,%d0 (appui sur un pad), 6 o
NOTE_CONT = 0x40081724
YES_SITE, YES_OLD = 0x400a6732, "4ebaeac62f03"         # jsr 0x400a51fa (preset sur YES) + move.l %d3,-(%sp), 6 o
PRESET_LOAD = 0x400a51fa          # rend 0 si le fichier est un preset ; arg 3 = piste visée
ERR_PEA = 0x400a6752              # pea « Error loading\npreset » (0x401302b2) du YES : pointé sur wt_msg
ERR_STR = 0x401302b2
LED_SLOTS = (0x400ff9b8, 0x400ffa78, 0x40103070, 0x401031b4, 0x40107e18)   # LedHandler, fonction vide (Model-TG)
LED_EMPTY = 0x400d7648            # rts
BLOCKS = 0x8000184c               # compteur de blocs audio
PROJECT = 0x400cf866              # projet courant ; piste t = projet + 212 + 68 t, son vivant = vtable[40]
ENTRY_OF = 0x4007de78             # (clé, &entrée 16 o) -> 0 : l'entrée du navigateur d'un fichier, par sa clé
OPEN, READ, CLOSE = 0x4007e4f4, 0x4007baaa, 0x4007bc1c  # API de fichiers de l'OS : ouvrir, lire, fermer
BUF = 0x46800000                  # tampons libres, vue avec cache (notes/52 §4)
BUF_STRIDE = 0x300000             # 3 Mo par piste (jusqu'a 256 trames)

# --- l'OS (identite Transfer CYC/SMP, notes/55) : l'OS ne gere que la famille « raw » du systeme de fichiers, le
# Model:Samples annonce la famille « sample ». En mode SMP on se declare Model:Samples (id 25, liste sample, nom) et on
# renomme les requetes sample -> raw et les reponses raw -> sample. Memes sites que Model-TG (dont c'est la glue SMP).
ID_HOOK_SITE, ID_HOOK_OLD = 0x40084b8e, "487800222d48"     # pea 0x22 ; movel %a0,%fp@(-96), 6 o
ID_HOOK_CONT = 0x40084bde
ID_HOOK2_SITE, ID_HOOK2_OLD = 0x40084c14, "721b4fef0028"   # moveq #27,%d1 ; lea %sp@(40),%sp, 6 o
ID_HOOK2_CONT = 0x40084c1a
ID_NAME_SITE, ID_NAME_OLD = 0x40084be2, "401285c9"         # immediat du pea du nom « Model Cycles », 4 o
RPC_TYPE_SITE, RPC_TYPE_OLD = 0x4009249c, "400949d8"       # cible du jsr 0x400949d8 (lecture du type, msg +8), 4 o
RPC_OT_SITE, RPC_OT_OLD = 0x40094c9a, "71aa00084fef0020"   # mvzb %a2@(8),%d0 ; lea %sp@(32),%sp, 8 o
RPC_OT_CONT = 0x40094ca2
SYSEX_TBL = 0x40148d08            # table des commandes SysEx de l'OS, indexee par msg[4] (<= 17), pointeurs u32
SYSEX_SLOT = 15                   # place libre 0x0F (0..3, 5..15 libres)
SYSEX_N = 18


def layout():
    """Copies gravées par l'outil web : taille log2 et position de chacune, longueur d'une trame (S_TOTAL)."""
    lg, off, s = [], [], 2048
    for c in range(NCOPY):
        l = 6
        while l < 11 and (1 << l) < 4 * max(1, int(1024 * 2 ** (-c))):
            l += 1
        lg.append(l)
    for c in range(NCOPY):
        off.append(0 if lg[c] == 11 else s)         # 0 : la copie est la table elle-meme
        if lg[c] < 11:
            s += 1 << lg[c]
    return lg, off, s


def tables_h():
    n0 = 69 + 12 * math.log2(FOLD_OK / 1024 / math.sqrt(2) / 440)
    lg, off, s = layout()
    return ga.tables_h().replace("tools/gen_acid.py", "tools/gen_wavetable.py") + "\n".join([
        f"#define NCOPY {NCOPY}",
        f"#define COPY_N0 {round(n0 * 65536)}",
        f"#define S_TOTAL {s}",
        "static const s16 LGC[NCOPY] = {" + ", ".join(map(str, lg)) + "};",
        "static const s32 OFF[NCOPY] = {" + ", ".join(map(str, off)) + "};",
    ]) + "\n"


def glue_asm(syms):
    """Notre code en assembleur : navigateur bloqué dans /Wavetables, chargeur (choix du fichier puis lecture
    à l'appui d'un pad). Registre et pile de l'OS intacts autour des deux accroches."""
    return f"""
	.text
| ---- la piste d0 joue-t-elle notre machine ? (kit d'origine : *0x40a78888 + 28 + 100 t, octet +38)
	.globl	wt_ours
wt_ours:
	move.l	{ACTIVE:#x}, %d0
	.globl	wt_is_ours
wt_is_ours:
	lea	-12(%sp), %sp
	movem.l	%d1-%d2/%a0, (%sp)
	move.l	%d0, %d1
	lsl.l	#6, %d1
	move.l	%d0, %d2
	lsl.l	#5, %d2
	add.l	%d2, %d1
	lsl.l	#2, %d0
	add.l	%d0, %d1
	add.l	#28, %d1
	move.l	{KIT:#x}, %a0
	adda.l	%d1, %a0
	moveq	#0, %d0
	move.b	{MACH_OFF}(%a0), %d2
	cmpi.l	#{WT_MACH}, %d2
	bne.s	1f
	moveq	#1, %d0
1:	movem.l	(%sp), %d1-%d2/%a0
	lea	12(%sp), %sp
	rts

| ---- curseur ou YES sur un fichier : note son entrée (16 o) pour la piste active (sans décharger la table jouée),
| puis la lecture de preset d'origine
	.globl	wt_parse
wt_parse:
	lea	-24(%sp), %sp
	movem.l	%d0-%d2/%a0-%a2, (%sp)
	move.l	{ACTIVE:#x}, %d0
	bsr.w	wt_is_ours
	tst.l	%d0
	beq.s	1f
	movea.l	28(%sp), %a1		/* entrée poussée par l'appelant */
	movea.l	{ACTIVE:#x}, %a2
	move.l	%a2, %d2
	lsl.l	#4, %d2
	lea	wt_h, %a0
	adda.l	%d2, %a0
	move.l	(%a1), %d0
	move.l	%d0, (%a0)
	move.l	4(%a1), %d0
	move.l	%d0, 4(%a0)
	move.l	8(%a1), %d0
	move.l	%d0, 8(%a0)
	move.l	12(%a1), %d0
	move.l	%d0, 12(%a0)
1:	movem.l	(%sp), %d0-%d2/%a0-%a2
	lea	24(%sp), %sp
	move.l	4(%sp), -(%sp)
	jsr	{PARSE_CALL:#x}
	addq.l	#4, %sp
	rts

| ---- lit la table notée pour la piste d0 dans son tampon ; d0 = 0, ou 1 rien de noté, 2 lecture, 3 trop grande,
| 4 non convertie (notes/54)
	.globl	wt_load
wt_load:
	lea	-44(%sp), %sp
	movem.l	%d1-%d7/%a0-%a3, (%sp)
	lea	-16(%sp), %sp		/* flux de l'API de fichiers */
	move.l	%d0, %d3
	move.l	%d3, %d2
	lsl.l	#2, %d2
	lea	{syms['wt_count']:#x}, %a1
	clr.l	(%a1,%d2.l)
	lea	{syms['wt_base']:#x}, %a1
	clr.l	(%a1,%d2.l)
	moveq	#1, %d5
	move.l	%d3, %d0
	lsl.l	#4, %d0
	lea	wt_h, %a0
	adda.l	%d0, %a0
	move.l	(%a0), %d1		/* entrée notée ? */
	cmpi.l	#-1, %d1
	beq.w	8f
	tst.l	%d1
	beq.w	8f
	moveq	#3, %d5
	move.l	8(%a0), %d6		/* taille du fichier (en-tête + PCM, parfois une fin) */
	cmpi.l	#{BUF_STRIDE:#x}, %d6
	bhi.w	8f
	moveq	#2, %d5
	move.l	%d3, %d0		/* tampon = 0x46800000 + 0x300000 t */
	move.l	%d0, %d1
	lsl.l	#1, %d0
	add.l	%d1, %d0
	lsl.l	#8, %d0
	lsl.l	#8, %d0
	lsl.l	#4, %d0
	add.l	#{BUF:#x}, %d0
	move.l	%d0, %d4
	move.l	%sp, %a1		/* open(&entrée, &flux) */
	move.l	%a1, -(%sp)
	move.l	%a0, -(%sp)
	jsr	{OPEN:#x}
	addq.l	#8, %sp
	tst.l	%d0
	blt.w	8f
	move.l	%d4, %a2		/* lecture par morceaux de 64 Ko */
	move.l	%d6, %d7
1:	tst.l	%d7
	beq.s	3f
	move.l	%d7, %d0
	cmpi.l	#0x10000, %d0
	bls.s	2f
	move.l	#0x10000, %d0
2:	move.l	%sp, %a1
	move.l	%a1, -(%sp)
	move.l	%d0, -(%sp)
	move.l	%a2, -(%sp)
	jsr	{READ:#x}
	lea	12(%sp), %sp
	tst.l	%d0
	ble.s	6f
	adda.l	%d0, %a2
	sub.l	%d0, %d7
	bra.s	1b
3:	move.l	%sp, %a1		/* ferme */
	move.l	%a1, -(%sp)
	jsr	{CLOSE:#x}
	addq.l	#4, %sp
	move.l	%d6, %d0		/* octets de PCM : ceux de l'en-tête (+4), bornés au fichier */
	sub.l	#64, %d0
	move.l	%d4, %a0
	move.l	4(%a0), %d1
	tst.l	%d1
	beq.s	4f
	cmp.l	%d0, %d1
	bhi.s	4f
	move.l	%d1, %d0
4:	lsr.l	#1, %d0
	moveq	#4, %d5			/* des trames entières de S_TOTAL, sinon non convertie */
	tst.l	%d0
	beq.s	8f
	move.l	%d0, %d1
	move.l	#{layout()[2]}, %d7
	divu.l	%d7, %d1
	mulu.l	%d7, %d1
	cmp.l	%d0, %d1
	bne.s	8f
	lea	{syms['wt_count']:#x}, %a0
	move.l	%d0, (%a0,%d2.l)
	lea	{syms['wt_base']:#x}, %a0
	move.l	%d4, %d0
	add.l	#64, %d0
	move.l	%d0, (%a0,%d2.l)
	moveq	#0, %d5
	bra.s	8f
6:	move.l	%sp, %a1		/* lecture incomplète : ferme */
	move.l	%a1, -(%sp)
	jsr	{CLOSE:#x}
	addq.l	#4, %sp
8:	move.l	%d5, %d0
	lea	16(%sp), %sp
	movem.l	(%sp), %d1-%d7/%a0-%a3
	lea	44(%sp), %sp
	rts

| ---- appui sur un pad : charge la table notée si elle ne l'est pas encore (repli de YES)
	.globl	wt_note
wt_note:
	lea	-60(%sp), %sp
	movem.l	%d0-%d7/%a0-%a6, (%sp)
	move.l	64(%sp), %d3		/* piste (1er argument de la fonction d'origine) */
	move.l	%d3, %d0
	bsr.w	wt_is_ours
	tst.l	%d0
	beq.s	9f
	move.l	%d3, %d2
	lsl.l	#2, %d2
	lea	{syms['wt_count']:#x}, %a1
	tst.l	(%a1,%d2.l)		/* déjà chargée ? */
	bne.s	9f
	move.l	%d3, %d0
	bsr.w	wt_load
	tst.l	%d0
	bne.s	9f
	move.l	%d3, %d0
	bsr.w	wt_stamp
9:	movem.l	(%sp), %d0-%d7/%a0-%a6
	lea	60(%sp), %sp
	link.w	%fp,#-104
	moveq	#127, %d0
	jmp	{NOTE_CONT:#x}

| ---- YES dans le navigateur (0x400a6732) : le preset ne se lit pas ; sur une piste Wave on charge la table et le
| message de l'OS devient le nôtre (wt_msg), comme le preset_fail_hook de Model-TG. Le chargement de preset échoue
| toujours : la piste ne reçoit jamais la table comme un preset.
	.globl	wt_yes
wt_yes:
	move.l	12(%sp), -(%sp)
	move.l	12(%sp), -(%sp)
	move.l	12(%sp), -(%sp)
	jsr	{PRESET_LOAD:#x}
	lea	12(%sp), %sp
	tst.l	%d0
	beq.w	9f			/* un vrai preset */
	lea	-44(%sp), %sp
	movem.l	%d1-%d7/%a0-%a3, (%sp)
	lea	{ERR_STR:#x}, %a2	/* ailleurs : le message d'origine */
	move.l	56(%sp), %d3		/* piste visée (3e argument) */
	andi.l	#0xff, %d3
	cmpi.l	#6, %d3
	bcc.s	5f
	move.l	%d3, %d0
	bsr.w	wt_is_ours
	tst.l	%d0
	beq.s	5f
	move.l	{ACTIVE:#x}, %d0	/* entrée notée sur la piste active -> piste visée */
	cmp.l	%d0, %d3
	beq.s	1f
	lsl.l	#4, %d0
	lea	wt_h, %a0
	adda.l	%d0, %a0
	move.l	%d3, %d1
	lsl.l	#4, %d1
	lea	wt_h, %a1
	adda.l	%d1, %a1
	move.l	(%a0)+, (%a1)+
	move.l	(%a0)+, (%a1)+
	move.l	(%a0)+, (%a1)+
	move.l	(%a0)+, (%a1)+
1:	move.l	%d3, %d0
	bsr.w	wt_load
	move.l	%d0, %d4
	bne.s	2f
	move.l	%d3, %d0		/* chargée : son nom la retient */
	bsr.w	wt_stamp
2:	move.l	%d4, %d0
	lea	wt_msgs, %a0		/* message n° d0 */
	lsl.l	#2, %d0
	movea.l	(%a0,%d0.l), %a2
	tst.l	%d0
	bne.s	5f
	lea	wt_msg, %a1		/* « Table loaded\nto track N » */
4:	move.b	(%a2)+, %d1
	beq.s	3f
	move.b	%d1, (%a1)+
	bra.s	4b
3:	move.l	%d3, %d1
	addi.l	#49, %d1
	move.b	%d1, (%a1)+
	clr.b	(%a1)
	bra.s	7f
5:	lea	wt_msg, %a1
6:	move.b	(%a2)+, %d1
	move.b	%d1, (%a1)+
	bne.s	6b
7:	movem.l	(%sp), %d1-%d7/%a0-%a3
	lea	44(%sp), %sp
	moveq	#1, %d0			/* toujours « échec » : l'OS affiche wt_msg */
9:	movea.l	(%sp)+, %a1		/* rejoue le move.l %d3,-(%sp) recouvert */
	move.l	%d3, -(%sp)
	jmp	(%a1)

| ---- son vivant de la piste d0 (objet de piste du projet, vtable[40]), ou 0 ; repris de sound_obj (Model-TG, MIT).
| Garde d2-d5/a2-a3 seulement.
	.globl	wt_snd
wt_snd:
	lea	-24(%sp), %sp
	movem.l	%d2-%d5/%a2-%a3, (%sp)
	move.l	%d0, %d3
	cmpi.l	#6, %d3
	bcc.s	8f
	jsr	{PROJECT:#x}
	tst.l	%d0
	beq.s	8f
	move.l	%d3, %d4
	moveq	#68, %d5
	muls.l	%d5, %d4
	addi.l	#212, %d0
	add.l	%d4, %d0
	movea.l	%d0, %a2
	move.l	(%a2), %d4		/* vtable */
	beq.s	8f
	movea.l	%d4, %a3
	movea.l	40(%a3), %a3
	move.l	%a3, %d4
	beq.s	8f
	move.l	%a2, -(%sp)
	jsr	(%a3)
	addq.l	#4, %sp
	bra.s	9f
8:	moveq	#0, %d0
9:	movem.l	(%sp), %d2-%d5/%a2-%a3
	lea	24(%sp), %sp
	rts

| ---- la table de la piste d0 (wt_h) est retenue : wt_tok[t] et le nom du son, « W » + clé (8 chiffres hex) +
| empreinte (6), que l'OS enregistre avec le projet (comme le jeton « SMP » de Model-TG)
	.globl	wt_stamp
wt_stamp:
	lea	-60(%sp), %sp
	movem.l	%d0-%d7/%a0-%a6, (%sp)
	move.l	%d0, %d7
	lsl.l	#4, %d0
	lea	wt_h, %a2
	adda.l	%d0, %a2
	move.l	(%a2), %d5		/* clé */
	move.l	4(%a2), %d6		/* empreinte, 24 bits */
	andi.l	#0xffffff, %d6
	move.l	%d7, %d0
	lsl.l	#3, %d0
	lea	wt_tok, %a0
	adda.l	%d0, %a0
	move.l	%d5, (%a0)
	move.l	%d6, 4(%a0)
	move.l	%d7, %d0
	bsr.w	wt_snd
	tst.l	%d0
	beq.s	9f
	movea.l	%d0, %a1
	addq.l	#4, %a1			/* le nom : 16 o */
	move.b	#87, (%a1)+		/* 'W' */
	move.l	%d5, %d1
	moveq	#8, %d2
	bsr.s	wt_hex
	move.l	%d6, %d1
	lsl.l	#8, %d1
	moveq	#6, %d2
	bsr.s	wt_hex
	clr.b	(%a1)
9:	movem.l	(%sp), %d0-%d7/%a0-%a6
	lea	60(%sp), %sp
	rts

| d1 = valeur cadrée à gauche, d2 = chiffres : écrit d2 chiffres hex en a1+ (abîme d0, d1, d2, d3)
wt_hex:
	moveq	#28, %d3
1:	move.l	%d1, %d0
	lsr.l	%d3, %d0
	addi.l	#48, %d0		/* '0' */
	cmpi.l	#57, %d0
	ble.s	2f
	addq.l	#7, %d0
2:	move.b	%d0, (%a1)+
	lsl.l	#4, %d1
	subq.l	#1, %d2
	bne.s	1b
	rts

| ---- a0 = un nom : d0 = 1 et d1 = clé, d2 = empreinte (24 bits) s'il porte notre jeton, sinon d0 = 0
	.globl	wt_tokof
wt_tokof:
	lea	-12(%sp), %sp
	movem.l	%d3-%d4/%a0, (%sp)
	moveq	#0, %d0
	move.b	(%a0)+, %d3
	cmpi.b	#87, %d3		/* 'W' */
	bne.s	8f
	tst.b	14(%a0)
	bne.s	8f
	moveq	#0, %d1
	moveq	#8, %d4
	bsr.s	3f
	bne.s	8f
	move.l	%d1, %d2
	moveq	#0, %d1
	moveq	#6, %d4
	bsr.s	3f
	bne.s	8f
	move.l	%d1, %d3
	move.l	%d2, %d1
	move.l	%d3, %d2
	moveq	#1, %d0
8:	movem.l	(%sp), %d3-%d4/%a0
	lea	12(%sp), %sp
	rts
3:	moveq	#0, %d3			/* d4 chiffres hex en a0+ -> d1 ; Z = 0 si un caractère n'en est pas un */
	move.b	(%a0)+, %d3
	subi.l	#48, %d3
	cmpi.l	#9, %d3
	bls.s	4f
	subq.l	#7, %d3
	cmpi.l	#10, %d3
	blt.s	5f
	cmpi.l	#15, %d3
	bhi.s	5f
4:	lsl.l	#4, %d1
	or.l	%d3, %d1
	subq.l	#1, %d4
	bne.s	3b
	moveq	#0, %d3			/* Z = 1 : fini */
	rts
5:	moveq	#1, %d3			/* Z = 0 : refusé */
	rts

| ---- tâche de l'interface (cases vides des LedHandler, comme Model-TG), au niveau 0 et une fois par bloc audio : la
| table que nomme le son d'une piste Wave est chargée si ce n'est pas déjà fait (projet rechargé, mise sous tension,
| autre kit). Une clé dont le fichier a disparu ou changé ne charge rien.
	.globl	wt_tick
wt_tick:
	lea	-60(%sp), %sp
	movem.l	%d0-%d7/%a0-%a6, (%sp)
	moveq	#0, %d0
	move.w	%sr, %d0
	andi.l	#0x0700, %d0
	bne.w	9f
	move.l	{BLOCKS:#x}, %d0
	cmp.l	wt_clock, %d0
	beq.w	9f
	move.l	%d0, wt_clock
	moveq	#0, %d7			/* piste */
1:	move.l	%d7, %d0
	bsr.w	wt_is_ours
	tst.l	%d0
	beq.s	5f
	move.l	%d7, %d0
	bsr.w	wt_snd
	tst.l	%d0
	beq.s	5f
	movea.l	%d0, %a0
	addq.l	#4, %a0
	bsr.w	wt_tokof
	tst.l	%d0
	beq.s	5f
	move.l	%d7, %d0
	lsl.l	#3, %d0
	lea	wt_tok, %a2
	adda.l	%d0, %a2
	cmp.l	(%a2), %d1
	bne.s	2f
	cmp.l	4(%a2), %d2
	beq.s	5f
2:	move.l	%d1, (%a2)		/* tenté une fois, même si ça échoue */
	move.l	%d2, 4(%a2)
	move.l	%d2, %d6
	pea	wt_tmp
	move.l	%d1, -(%sp)
	jsr	{ENTRY_OF:#x}
	addq.l	#8, %sp
	tst.l	%d0
	bne.s	5f
	lea	wt_tmp, %a0
	move.l	4(%a0), %d0
	andi.l	#0xffffff, %d0
	cmp.l	%d6, %d0
	bne.s	5f
	move.l	%d7, %d0
	lsl.l	#4, %d0
	lea	wt_h, %a1
	adda.l	%d0, %a1
	move.l	(%a0)+, (%a1)+
	move.l	(%a0)+, (%a1)+
	move.l	(%a0)+, (%a1)+
	move.l	(%a0)+, (%a1)+
	move.l	%d7, %d0
	bsr.w	wt_load
5:	addq.l	#1, %d7
	moveq	#6, %d0
	cmp.l	%d0, %d7
	blt.w	1b
9:	movem.l	(%sp), %d0-%d7/%a0-%a6
	lea	60(%sp), %sp
	rts

| ---- navigateur : sur notre piste, /Wavetables (créé s'il manque), sans remonter au-dessus
	.globl	wt_open
wt_open:
	bsr.w	wt_ours
	tst.l	%d0
	beq.w	5f
	tst.l	wt_lock
	bne.s	1f
	move.l	{FOLDER:#x}, %d0
	move.l	%d0, wt_saved
1:	pea	wt_h_dir
	pea	wt_path
	jsr	0x4007aa78
	addq.l	#8, %sp
	tst.l	%d0
	beq.s	2f
	pea	wt_path			/* absent : créé */
	jsr	0x4007ac46
	pea	wt_h_dir
	pea	wt_path
	jsr	0x4007aa78
	lea	12(%sp), %sp
	tst.l	%d0
	bne.s	6f
2:	move.l	wt_h_dir, %d0
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
5:	bsr.w	wt_unlock		/* une fermeture manquée */
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
	bsr.w	wt_unlock
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
wt_h:	.space	96				/* entrées de navigateur des 6 pistes */
wt_h_dir:	.long	0, 0, 0, 0
wt_path:	.asciz	"/Wavetables"
	.align	2
wt_msgs:	.long	wt_m0, wt_m1, wt_m2, wt_m3, wt_m4
wt_m0:	.asciz	"Table loaded\\nto track "
wt_m1:	.asciz	"No table\\nselected"
wt_m2:	.asciz	"Table read\\nfailed"
wt_m3:	.asciz	"Table too big\\n(256 frames max)"
wt_m4:	.asciz	"Table not\\nconverted"
	.align	2
	.globl	wt_msg
wt_msg:	.space	64
	.globl	wt_tok
wt_tok:	.space	48			/* table retenue par piste : clé, empreinte 24 bits */
wt_tmp:	.space	16
wt_clock:	.long	0
"""


def smp_glue_asm():
    """Notre glue SMP (notes/55), assemblee avec le chargeur : elle rejoue les blocs d'origine en choisissant la liste,
    le nom et le numero de produit selon smp_mode, renomme les types des requetes et des reponses, et pose le drapeau
    depuis une commande SysEx. Les registres et la pile de l'OS sont rendus comme les blocs d'origine."""
    return """
| ================= Identite Transfer CYC / SMP (notes/55) =================
| --- reponse d'identite : liste + nom selon smp_mode (0x40084b8e..0x40084bdc)
	.globl	smp_id_hook
smp_id_hook:
	movea.l	%a0, %a5		/* 0x400845de, l'allocateur (lea juste avant) */
	lea	smp_n_cyc, %a4
	moveq	#0x22, %d6
	tst.l	smp_mode
	beq.s	1f
	lea	smp_n_smp, %a4
	moveq	#0x23, %d6
1:	lea	smp_namebuf, %a1
2:	move.b	%a4@+, %d7
	move.b	%d7, %a1@+
	bne.s	2b
	move.l	%d6, %sp@-		/* comme « pea 0x22 » : la longueur de la liste */
	move.l	%a5, %fp@(-96)
	clr.l	%fp@(-36)
	clr.l	%fp@(-32)
	clr.l	%fp@(-28)
	jsr	%a5@
	lea	0x400e9c0a, %a4
	move.l	%fp, %d6
	addi.l	#-44, %d6
	move.l	%fp, %d7
	addi.l	#-68, %d7
	lea	0x400f980c, %a5
	move.l	%d0, %sp@-
	movea.l	%d0, %a1
	tst.l	smp_mode
	bne.s	3f
	pea	0x40112d62		/* la liste « raw » du Cycles */
	lea	%a1@(34), %a1
	pea	0x40112d40
	bra.s	4f
3:	pea	smp_list+35
	lea	%a1@(35), %a1
	pea	smp_list
4:	move.l	%a1, %fp@(-28)
	move.l	%d0, %fp@(-36)
	jsr	%a4@
	jmp	0x40084bde

| --- numero de produit : 27 (Cycles) ou 25 (Samples) (0x40084c14)
	.globl	smp_id_hook2
smp_id_hook2:
	moveq	#27, %d1
	tst.l	smp_mode
	beq.s	1f
	moveq	#25, %d1
1:	lea	%sp@(40), %sp
	jmp	0x40084c1a

| --- requete : le type « sample » prend le type « raw » jumeau (0x4009249c)
	.globl	smp_rpc_type
smp_rpc_type:
	movea.l	%sp@(4), %a0
	moveq	#0, %d0
	move.b	%a0@(8), %d0
	tst.l	smp_mode
	beq.s	2f
	lea	smp_map, %a1
1:	moveq	#0, %d1
	move.b	%a1@, %d1
	beq.s	2f
	cmp.l	%d1, %d0
	beq.s	3f
	addq.l	#2, %a1
	bra.s	1b
3:	move.b	%a1@(1), %d0
	move.b	%d0, %a0@(8)
2:	rts

| --- reponse : le type « raw » redevient « sample » (0x40094c9a)
	.globl	smp_rpc_ot
smp_rpc_ot:
	moveq	#0, %d0
	move.b	%a2@(8), %d0
	tst.l	smp_mode
	beq.s	2f
	lea	smp_map, %a1
1:	moveq	#0, %d1
	move.b	%a1@(1), %d1
	beq.s	2f
	bset	#7, %d1
	cmp.l	%d1, %d0
	beq.s	3f
	addq.l	#2, %a1
	bra.s	1b
3:	move.b	%a1@, %d0
	bset	#7, %d0
2:	lea	%sp@(32), %sp
	jmp	0x40094ca2

| --- SysEx 0x0F : pose le drapeau (0 = CYC, 1 = SMP), sur le 3e octet apres la commande
	.globl	smp_trig
smp_trig:
	movea.l	%sp@(4), %a0
	moveq	#0, %d0
	move.b	%a0@(6), %d0
	move.l	%d0, smp_mode
	rts

	.align	2
	.globl	smp_mode
smp_mode:	.long	0
	.globl	smp_map
smp_map:	.byte	0x10, 0x14, 0x11, 0x15, 0x12, 0x16
	.byte	0x20, 0x24, 0x21, 0x25, 0x22, 0x26, 0x23, 0x27
	.byte	0x30, 0x33, 0x31, 0x34, 0x32, 0x35, 0x36, 0x37
	.byte	0x40, 0x43, 0x41, 0x44, 0x42, 0x45, 0x46, 0x47
	.byte	0, 0
	.globl	smp_list
smp_list:	.byte	0x01, 0x02, 0x03, 0x05, 0x04, 0x50, 0x52, 0x51, 0x10, 0x13, 0x11, 0x12
	.byte	0x20, 0x21, 0x22, 0x23, 0x30, 0x31, 0x32, 0x36, 0x40, 0x41, 0x42, 0x46
	.byte	0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5a, 0x5b, 0x5c, 0x5d
smp_n_cyc:	.asciz	"Model Cycles"
smp_n_smp:	.asciz	"Model Samples"
	.align	2
	.globl	smp_namebuf
smp_namebuf:	.space	16
	.globl	smp_desc
smp_desc:	.byte	0x0f, 0x00, 0x00, 0x00
	.long	smp_sub
	.long	0, 1, 0, 0
smp_sub:	.long	smp_trig, smp_trig
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


def compile_machine(tmp, pay):
    """Le moteur, lié à pay (code, tables) et pay + gm.BSS_OFF (états et wt_base/wt_count). Renvoie (octets, symboles,
    fin du BSS)."""
    (tmp / "wt_tables.h").write_text(tables_h())
    o, ld, elf, out = tmp / "wt.o", tmp / "link.ld", tmp / "wt.elf", tmp / "wt.bin"
    gx.run([gx.CROSS + "gcc", *ga.CFLAGS, f"-I{tmp}", "-c", str(SRC / "wt.c"), "-o", str(o)])
    ld.write_text(LINK.format(code=pay, bss=pay + gm.BSS_OFF))
    warn = ["--no-warn-rwx-segments"] if "no-warn-rwx" in gx.run([gx.CROSS + "ld", "--help"]) else []
    gx.run([gx.CROSS + "ld", "-T", str(ld), "--gc-sections", *warn, "-e", "wt_update",
            "-u", "wt_render", "-o", str(elf), str(o)])
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
    for need in ("wt_base", "wt_count"):
        if need not in syms:
            raise SystemExit(f"!! {need} absent du moteur")
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


def build_tweak(img):
    """Le tweak de la machine Wave seule (comme gen_acid.build_tweak sans Model-TG)."""
    pay = gs.PAY_ALONE
    gs.set_base(pay)
    first = 6
    if WT_MACH != first:
        raise SystemExit("!! index de la machine")
    nm, n = first + 1, 1
    top = nm - 1
    m = MACHINE
    with tempfile.TemporaryDirectory() as d:
        tmp = pathlib.Path(d)
        blob, syms, bss_end = compile_machine(tmp, pay)
        glue_at = pay + ((len(blob) + 15) & ~15)
        glue, gsyms = gm.assemble(tmp, "glue", glue_asm(syms) + smp_glue_asm(), glue_at)
        if glue_at + len(glue) > pay + ART_OFF:
            raise SystemExit(f"!! code trop grand : {glue_at + len(glue) - pay} o")
        art_parts, art_reloc, art_addr, art_end = art(img, pay)
        if art_end > pay + gm.BSS_OFF:
            raise SystemExit("!! images")
        names_at, upd_at, rnd_at, map_at = gs.DATA, gs.DATA + 4 * nm, gs.DATA + 8 * nm, gs.DATA + 16 * nm
        stubs, ssyms = gm.assemble(tmp, "det", gs.detours_asm(n, [m["image"]], [76], None)
                                   + ga.art_asm(art_addr, first, None), gs.STUBS)
        if gs.STUBS + len(stubs) > gs.DATA:
            raise SystemExit("!! détours trop grands")

        strings = [m["name"]] + [k[i] for k in m["knobs"] for i in (0, 1)] + list(EPOS_NAMES)
        at, addr = map_at + ((nm + 3) & ~3), {}
        for s_ in strings:
            if s_ not in addr:
                addr[s_] = at
                at += len(s_) + 1
        names = [struct.unpack_from(">I", img, g7.NAMES + 4 * i - BASE)[0] for i in range(6)] + [addr[m["name"]]]
        pad = [struct.unpack_from(">I", img, g7.UPDATE_TAB - BASE)[0]] * (first - 6), \
              [struct.unpack_from(">I", img, g7.RENDER_TAB - BASE)[0]] * (first - 6)
        upd = [struct.unpack_from(">I", img, g7.UPDATE_TAB + 4 * i - BASE)[0] for i in range(6)] + pad[0] \
            + [syms["wt_update"]]
        rnd = [struct.unpack_from(">I", img, g7.RENDER_TAB + 4 * i - BASE)[0] for i in range(6)] + pad[1] \
            + [syms["wt_render"]]
        data = bytearray()
        for t in (names, upd, rnd, range(1, nm + 1)):
            data += b"".join(g7.be32(x) for x in t)
        data += img[gs.MAP - BASE:gs.MAP - BASE + 6] + bytes(range(6, nm)) + bytes(((nm + 3) & ~3) - nm)
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
            if img[va - BASE:va - BASE + len(old)] != old:
                raise SystemExit(f"!! {va:#x} : {old.hex()} attendu, {img[va - BASE:va - BASE + len(old)].hex()} trouvé")
            writes.append({"off": va - BASE, "old": old.hex(), "new": new_.hex()})

        def moveq(va, old, new_, reg_byte):
            w(va, bytes([reg_byte, old]), bytes([reg_byte, new_]))

        def jmp(va):
            return bytes.fromhex("4ef9") + g7.be32(va)

        def call(va):
            return bytes.fromhex("4eb9") + g7.be32(va)

        writes.append(None)                     # crochet de démarrage : écrit plus bas
        red = sprites.redirect_write(gx.CAVE)
        w(BASE + red["off"], bytes.fromhex(red["old"]), bytes.fromhex(red["new"]))
        w(gx.HOOK, bytes.fromhex(gx.HOOK_OLD), jmp(gx.CAVE) + bytes.fromhex("4e71"))
        moved = {g7.DESC: gs.DESCN, g7.DESC + 8: gs.DESCN + 8, g7.DESC + 0x20: gs.DESCN + 0x20, g7.ROWS: gs.ROWSN,
                 g7.CCROWS: gs.CCROWSN, g7.NAMES: names_at, g7.UPDATE_TAB: upd_at, g7.RENDER_TAB: rnd_at,
                 gs.MAP: map_at}
        want = {g7.DESC: 34, g7.DESC + 8: 1, g7.DESC + 0x20: 2, g7.ROWS: 5, g7.CCROWS: 2, gs.MAP: 1,
                g7.RENDER_TAB: 1}
        for old, new_ in moved.items():
            rs = g7.refs32(img, old)
            if len(rs) != want.get(old, 1):
                raise SystemExit(f"!! références à {old:#x} : {len(rs)}")
            for va in rs:
                w(va, g7.be32(old), g7.be32(new_))
        jumps = g7.JUMPS + g8.JUMPS8
        for va in g7.BOUNDS:
            if va in {j[0] for j in jumps}:
                continue
            b0, b1 = img[va - BASE], img[va - BASE + 1]
            if b0 & 0xf1 != 0x70 or b1 not in (75, 76):
                raise SystemExit(f"!! {va:#x}")
            moveq(va, b1, b1 + 5 * n, b0)
        for va, reg in ((0x400a7dba, 0x72), (0x400a7df4, 0x70), (0x4005a6a6, 0x72), (0x400147a4, 0x70),
                        (0x400148aa, 0x72), (0x400148b2, 0x70), (0x400a25e0, 0x70)):
            if img[va - BASE] != reg or img[va - BASE + 1] not in (5, 6):
                raise SystemExit(f"!! borne {va:#x}")
            moveq(va, img[va - BASE + 1], top, reg)
        moveq(0x4005a572, 5, 6, 0x72)
        w(0x4005a2b8, bytes.fromhex("487800c0"), bytes.fromhex("4878") + (32 * nm).to_bytes(2, "big"))
        if nm > gs.MARKS_ROW:
            w(0x400a26a2, bytes.fromhex("7850428545f9"), jmp(ssyms["marks"]))
        else:
            moveq(0x400a26e8, img[0x400a26e8 - BASE + 1], nm, 0x70)
        for va in (0x4001b69c, 0x400a40a6, 0x400a4fb0):
            moveq(va, 5, 6, 0x70)
        for va, old, sym in jumps:
            w(va, bytes.fromhex(old), jmp(ssyms[ga.ART_JUMPS.get(sym, sym)]))
        for va, old, sym in ga.ART_SITES:
            w(va, bytes.fromhex(old), bytes.fromhex("4eb9") + g7.be32(ssyms[sym]))
        for va, old, sym in g7.CALLS:
            w(va, bytes.fromhex(old), bytes.fromhex("4eb9") + g7.be32(ssyms[sym]) + bytes.fromhex("4e71"))
        # navigateur bloqué dans /Wavetables (notes/52 §3quater)
        for va, old, sym in BROWSER:
            old = bytes.fromhex(old)
            if sym == "wt_home":
                new_ = call(gsyms[sym])
            else:
                new_ = jmp(gsyms[sym]) + bytes.fromhex("4e71") * ((len(old) - 6) // 2)
            w(va, old, new_)
        # chargeur (notes/54)
        w(PARSE_SITE, bytes.fromhex(PARSE_OLD), call(gsyms["wt_parse"]))
        w(PARSE_SITE2, bytes.fromhex(PARSE_OLD), call(gsyms["wt_parse"]))
        w(YES_SITE, bytes.fromhex(YES_OLD), call(gsyms["wt_yes"]))
        w(ERR_PEA + 2, g7.be32(ERR_STR), g7.be32(gsyms["wt_msg"]))
        for slot in LED_SLOTS:          # tâche de l'interface (notes/54)
            w(slot, g7.be32(LED_EMPTY), g7.be32(gsyms["wt_tick"]))
        w(NOTE_SITE, bytes.fromhex(NOTE_OLD), jmp(gsyms["wt_note"]))
        # identite Transfer CYC/SMP sans Model-TG (notes/55)
        w(ID_HOOK_SITE, bytes.fromhex(ID_HOOK_OLD), jmp(gsyms["smp_id_hook"]))
        w(ID_HOOK2_SITE, bytes.fromhex(ID_HOOK2_OLD), jmp(gsyms["smp_id_hook2"]))
        w(ID_NAME_SITE, bytes.fromhex(ID_NAME_OLD), g7.be32(gsyms["smp_namebuf"]))
        w(RPC_TYPE_SITE, bytes.fromhex(RPC_TYPE_OLD), g7.be32(gsyms["smp_rpc_type"]))
        w(RPC_OT_SITE, bytes.fromhex(RPC_OT_OLD), jmp(gsyms["smp_rpc_ot"]) + bytes.fromhex("4e71"))
        if not 0 <= SYSEX_SLOT < SYSEX_N:
            raise SystemExit("!! place SysEx hors table")
        slot = SYSEX_TBL + 4 * SYSEX_SLOT
        if img[slot - BASE:slot - BASE + 4] != b"\0\0\0\0":
            raise SystemExit(f"!! place SysEx {SYSEX_SLOT:#x} déjà prise")
        w(slot, b"\0\0\0\0", g7.be32(gsyms["smp_desc"]))

        parts = [
            {"dest": f"{pay:#x}", "hex": blob.hex()},
            {"dest": f"{glue_at:#x}", "hex": glue.hex()},
            {"dest": f"{gs.STUBS:#x}", "hex": stubs.hex()},
            {"dest": f"{gs.DATA:#x}", "hex": bytes(data).hex()},
            {"dest": f"{gs.DESCN:#x}", "cycles": [f"{g7.DESC:#x}", f"{g7.DESC + g7.NDESC * g7.DSTRIDE:#x}"]},
            {"dest": f"{gs.DESCN + g7.NDESC * g7.DSTRIDE:#x}", "hex": bytes(new).hex()},
        ] + art_parts
        lo_, hi_ = g7.DESC - BASE, g7.DESC - BASE + g7.NDESC * g7.DSTRIDE
        final, orig = bytearray(img[lo_:hi_]), img[lo_:hi_]
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
        reloc = [[f"{gs.DESCN + k:#x}", orig[k:k + 4].hex(), final[k:k + 4].hex()]
                 for k in range(0, len(final), 4) if final[k:k + 4] != orig[k:k + 4]] + art_reloc
        size = bss_end - pay
        segs = gs.segments(parts, size)
        at = BASE + gx.IMAGE_LEN
        if at + sum(n_ for _, n_ in segs) > gs.END_LIMIT:
            raise SystemExit(f"!! ajout de {sum(n_ for _, n_ in segs)} o : l'image dépasserait {gs.END_LIMIT:#x}")
        (tmp / "segs.inc").write_text("".join(f"\t.long\t{a_:#x}, {n_ // 4}\n" for a_, n_ in segs))
        stub, _ = gm.assemble(tmp, "stub", gx.SRC / "stub.S", gx.CAVE, [
            f"-DPAYLOAD_SRC={at:#x}", f"-DPAYLOAD_DST={pay:#x}", f"-DPAYLOAD_LONGS={size // 4}", "-DPACK", f"-I{tmp}"])
    if len(stub) > sprites.zone(gx.CAVE)[1]:
        raise SystemExit("!! crochet de démarrage trop grand pour sa place")
    writes[0] = {"off": gx.CAVE - BASE, "old": "ff" * len(stub), "new": stub.hex()}
    if img[gx.CAVE - BASE:gx.CAVE - BASE + len(stub)] != b"\xff" * len(stub):
        raise SystemExit("!! place du crochet de démarrage déjà prise")
    writes.sort(key=lambda x: x["off"])
    for a_, b_ in zip(writes, writes[1:]):
        if a_["off"] + len(a_["new"]) // 2 > b_["off"]:
            raise SystemExit(f"!! écritures qui se chevauchent en {BASE + b_['off']:#x}")

    ids = gm.other_ids() | {"macro", "macro-tg", "model-tg", "model-tg-st", "acid", "acid-tg"}
    out = {
        "id": "wavetable",
        "order": 36,
        "name": "Machine Wave : joue tes tables d'ondes (dossier /Wavetables)",
        "description": [
            "Machine Wave en 7e machine, après les 6 d'origine (notes/52, notes/54) : elle joue une de tes tables",
            "d'ondes, un fichier de /Wavetables (créé s'il manque) converti par l'outil web (table entière puis copies",
            "adoucies par octave), choisi dans le navigateur sur la piste de Wave et chargé par YES (message « Table",
            "loaded »), retenu dans le nom du son et rechargé avec le projet. Pas de repliement, rien de calculé sur la",
            "machine.",
            "Pour l'envoi, la commande SysEx 0x0F la fait répondre en Model:Samples (notes/55), sans Model-TG.",
            "COLOR = position dans la table, SHAPE = enveloppe -> position (64 : rien), MACHINE tenue + COLOR = Env Pos,",
            "SWEEP = coupure du passe-bas d'Acid (20 Hz -> 20 kHz), CONTOUR = résonance, DECAY = enveloppe et chaîne",
            "d'ampli d'origine, PUNCH = accent. Code : tools/machines/wavetable/wt.c. Généré par tools/gen_wavetable.py.",
            "Aucun octet Elektron.",
        ],
        "device": "Model:Cycles",
        "os": "1.13",
        "section": 3,
        "conflicts": sorted(ids),
        "writes": writes,
        "append": {"at": f"{at:#x}", "dest": f"{pay:#x}", "size": size, "parts": parts, "reloc": reloc,
                   "pack": [[f"{a_:#x}", n_] for a_, n_ in segs]},
        "symbols": dict({k: f"{syms[k]:#x}" for k in ("wt_update", "wt_render", "wt_base", "wt_count")},
                        **{k: f"{gsyms[k]:#x}" for k in ("wt_parse", "wt_note", "wt_load", "wt_yes", "wt_msg", "wt_snd", "wt_stamp",
                                                        "wt_tokof", "wt_tick", "wt_tok", "wt_open", "wt_close",
                                                        "smp_id_hook", "smp_id_hook2", "smp_rpc_type", "smp_rpc_ot",
                                                        "smp_trig", "smp_mode", "smp_desc", "smp_list", "smp_map",
                                                        "smp_namebuf")},
                        **{f"art_{k}": f"{v:#x}" for k, v in art_addr.items()}),
    }
    out = usb_steady.add_to(out)
    out = voice_loop.add_to(out)
    return out, dict(code=len(blob), glue=len(glue), bss=bss_end - pay - gm.BSS_OFF, image=sum(n_ for _, n_ in segs))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycles", required=True, help="model-cycles_OS1.13.syx officiel")
    ap.add_argument("--check", action="store_true", help="vérifie que le JSON versionné correspond")
    args = ap.parse_args()
    img = g7.cycles_main(args.cycles)
    if len(img) != gx.IMAGE_LEN:
        raise SystemExit("!! ce n'est pas le MAIN OS 1.13 officiel")
    tweak, info = build_tweak(img)
    text = json.dumps(tweak, indent=1) + "\n"
    print(f"  {tweak['id']} : {len(tweak['writes'])} écritures, code {info['code']} o + {info['glue']} o, variables "
          f"{info['bss']} o, ajout à l'image {info['image']} o")
    if gm.emit(OUT, text, args.check):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
