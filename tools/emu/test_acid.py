#!/usr/bin/env python3
"""Preuve de la machine Acid (notes/44) : une basse façon 303 en machine ajoutée, seule (26-acid.json, 7e machine)
et avec Model-TG (33-acid-tg.json par-dessus 30-model-tg-st.json, 8e machine, mêmes vérifications).
Le vrai code de l'OS, émulé (Unicorn), avec la charge utile telle que le crochet de démarrage la reconstitue.

  1. Démarrage : le décompresseur du bootstrap relit l'OS agrandi ; le crochet (stub.S, PACK) remet à zéro la zone
     de la charge utile, y recopie ses morceaux, ne touche pas à la SRAM, puis reprend la remise à zéro du BSS de
     l'OS.
  2. Interface : les vérifications de test_syntakt_machines.py, appliquées à Acid : rangées, recherches,
     descripteurs, écran MACHINES, molette, enregistrements, changement de machine réel, potards, icône.
  3. Son :
     - avant la chaîne d'ampli, la sortie d'Acid est EXACTEMENT celle du même moteur compilé pour l'ordinateur
       (tools/emu/acid_ref.c, HOST), rejoué avec ce que le moteur reçoit dans l'OS à chaque bloc : réglages par
       défaut, filtre passe-bas et passe-haut, ouvert (64), balayé (COLOR en 8.8, à chaque bloc), résonance au
       maximum (auto-oscillation), enveloppe dans les deux sens, accent, GATE, notes extrêmes, voix qui se tait puis
       repart ;
     - une voix est calculée exactement quand l'OS l'impose (trig, ou enveloppe d'ampli au-dessus de 2^14) ;
       muette : sortie nulle ;
     - la chaîne d'ampli (DECAY, GATE, PUNCH) lit dans la voix Acid exactement ce qu'elle lit pour TONE ;
     - les machines d'origine ne changent pas et aucune instruction d'Acid ne tourne sans piste Acid ;
     - machine locks ; 6 pistes Acid ensemble ; Acid mêlée aux machines d'origine ;
     - la résonance au maximum reste bornée (le coude), et la coupure suit COLOR (fréquence mesurée).
  4. Coût : instructions par bloc d'une voix Acid (passe-bas, passe-haut, ouvert, au-delà du coude), d'une voix
     muette, et de TONE ; pile.
  5. Avec les autres mods (--with) : démarrage, machines d'origine identiques aux mêmes mods sans Acid, et Acid
     identique à Acid seule.

    python3 tools/emu/test_acid.py --cycles model-cycles_OS1.13.syx [--with 6ch-usbup,model-tg-st,trig-hold,arp,tempo-max,boot-anim]
"""
import argparse
import json
import pathlib
import struct
import subprocess
import sys
import tempfile

import numpy as np
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_UNMAPPED
from unicorn import m68k_const as mk

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import build                        # noqa: E402
import gen_acid as ga               # noqa: E402
import gen_syntakt_engines as gs    # noqa: E402
import mcengine as E                # noqa: E402
import test_sdvintage as T          # noqa: E402
import test_model_tg as TM          # noqa: E402
import test_model_tg_syntakt as tms  # noqa: E402
import test_sdvintage_7th as t7     # noqa: E402
import test_syntakt_machines as tsm  # noqa: E402

DEV = HERE.parent.parent / "tweaks" / "model-cycles_OS1.13"
BASE = E.BASE
check = t7.check                    # échecs : t7.FAIL

IDLE_LEVEL = 1 << 14
MARK = 0x41434431                   # 'ACD1'
AMP = ((0x400a9252, 0x400a9302), (0x400a9430, 0x400a9498), (0x400a967a, 0x400a9756))   # chaîne d'ampli de l'OS
TONE = 4
OFF = 9                             # machine hors limites : la voix n'est pas calculée
BASE_KW = dict(note=36, pitch=64, color=30, shape=0, sweep=90, contour=100, punch=0, gate=0, finetune=64, decay=50)
VOFF = (0x2c, 0x34, 0x38, 0x230, 0x234)


def load(name):
    return json.loads((DEV / name).read_text(encoding="utf-8"))


class Fw:
    """Un firmware : MAIN OS (avec ce qui est ajouté après), et la charge utile d'Acid telle qu'en mémoire."""

    def __init__(self, stock, tweaks):
        p, _ = build.apply_writes(stock, tweaks)
        pl, _ = build.build_payload(tweaks, stock, None)
        self.img, self.tweaks = bytes(p) + pl, tweaks
        tg = [t for t in tweaks if t["id"].startswith("model-tg")]
        self.blob_end = BASE + len(stock) + tg[0]["append"]["size"] if tg else None
        ours = [t for t in tweaks if t["id"].startswith("acid")]
        self.payload = None
        if not ours:
            return
        ap_ = ours[0]["append"]
        self.pay = int(ap_["dest"], 16)
        self.runtime = build.payload_runtime(ours[0], stock, None)
        self.payload = (self.pay, self.runtime)
        self.code_end = self.pay + len(ap_["parts"][0]["hex"]) // 2          # code et tables d'Acid
        self.nm = gs.TG_FIRST + 1 if tg else 7
        self.index = self.nm - 1
        self.upd = int(ours[0]["symbols"]["acid_update"], 16)
        self.rnd = int(ours[0]["symbols"]["acid_render"], 16)
        data = self.pay + gs.LAYOUT["DATA"]
        u32 = lambda va: struct.unpack_from(">I", self.runtime, va - self.pay)[0]
        if (u32(data + 4 * self.nm + 4 * self.index), u32(data + 8 * self.nm + 4 * self.index)) != (self.upd, self.rnd):
            raise SystemExit("!! tables update/render de la charge utile")

    def engine(self, solo=None):
        if self.blob_end:
            e = TM.engine(self.img, end=self.blob_end, payload=self.payload)
        else:
            e = E.Engine(self.img, payload=self.payload)
        if solo is not None:             # les autres pistes : machine hors limites, rien n'est calculé
            for t in range(6):
                if t != solo:
                    e.uc.mem_write(E.VOICE0 + t * E.VSTRIDE, struct.pack(">II", OFF, OFF))
        return e


# --- 1. démarrage ----------------------------------------------------------------------------------------------
def boot(fw, tg=None):
    """Le crochet de démarrage, exécuté pour de vrai : au début de la remise à zéro du BSS (0x400004b2, jusqu'à son
    retour) ; avec Model-TG, par le jsr de 0x40000530, jusqu'à son boot_extra_hook."""
    uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
    uc.ctl_set_cpu_model(mk.UC_CPU_M68K_ANY)
    uc.mem_map(0x40000000, 0x02400000)
    uc.mem_write(BASE, fw.img)
    dst, rt = fw.payload
    uc.mem_map(dst, 0x00100000)
    uc.mem_write(dst, b"\xa5" * 0x00100000)              # ce que la SDRAM contient avant : n'importe quoi
    uc.mem_map(0x80000000, 0x00010000)
    sram = bytearray(0x10000)                             # SRAM après son initialisation par l'OS (0x4000045c)
    for lo, hi, d in gs.CY_SRAM_INIT:
        sram[d - 0x80000000:d - 0x80000000 + hi - lo] = fw.img[lo - BASE:hi - BASE]
    uc.mem_write(0x80000000, bytes(sram))
    uc.mem_map(0x90000000, 0x00020000)
    uc.mem_write(E.STOP, b"\x4e\x71\x4e\x71")
    bad = []
    uc.hook_add(UC_HOOK_MEM_UNMAPPED, lambda u, a, addr, s, v, d: bad.append(addr) or False)
    keep = {r: 0x11110000 + i for i, r in enumerate((mk.UC_M68K_REG_D2, mk.UC_M68K_REG_D3, mk.UC_M68K_REG_D4,
                                                     mk.UC_M68K_REG_D5, mk.UC_M68K_REG_D6, mk.UC_M68K_REG_D7,
                                                     mk.UC_M68K_REG_A2, mk.UC_M68K_REG_A3, mk.UC_M68K_REG_A4,
                                                     mk.UC_M68K_REG_A5, mk.UC_M68K_REG_A6))}
    for r, v in keep.items():
        uc.reg_write(r, v)
    sp0 = 0x90010000
    if tg:
        uc.reg_write(mk.UC_M68K_REG_A7, sp0)
        uc.emu_start(gs.BOOT_CALL, tg["boot_extra_hook"], count=5_000_000)
        pc, sp = uc.reg_read(mk.UC_M68K_REG_PC), uc.reg_read(mk.UC_M68K_REG_A7)
        ret = struct.unpack(">I", uc.mem_read(sp, 4))[0]
        regs = all(uc.reg_read(r) == v for r, v in keep.items())
        check(pc == tg["boot_extra_hook"] and sp == sp0 - 4 and ret == gs.BOOT_CALL + 6 and regs and not bad,
              f"jsr 0x40000530 -> notre crochet -> boot_extra_hook {tg['boot_extra_hook']:#x}, pile et d2..d7/a2..a6 "
              "intactes")
        check(bytes(uc.mem_read(BASE, len(fw.img))) == fw.img, "image (OS, Model-TG, nos morceaux) inchangée")
    else:
        uc.mem_write(sp0, struct.pack(">I", E.STOP))
        uc.reg_write(mk.UC_M68K_REG_A7, sp0)
        uc.emu_start(0x400004b2, E.STOP, count=100_000_000)
        regs = all(uc.reg_read(r) == v for r, v in keep.items())
        tail = BASE + E.IMAGE_LEN
        cleared = not any(uc.mem_read(tail, len(fw.img) - E.IMAGE_LEN)) and not any(uc.mem_read(0x42338000, 0xb0))
        check(uc.reg_read(mk.UC_M68K_REG_PC) == E.STOP and uc.reg_read(mk.UC_M68K_REG_A7) == sp0 + 4 and regs
              and cleared and not bad,
              "0x400004b2 -> notre crochet -> remise à zéro du BSS de l'OS (nos morceaux rangés compris), retour "
              "normal, d2..d7/a2..a6 intacts")
    got = bytes(uc.mem_read(dst, len(rt)))
    packed = sum(n for _, n in next(t for t in fw.tweaks if t["id"].startswith("acid"))["append"]["pack"])
    check(got == rt, f"charge utile reconstituée à {dst:#x} : {len(rt)} o (code et tables d'Acid, détours, données, "
                     f"puis ses états à zéro), rangée en {packed} o dans l'image")
    check(bytes(uc.mem_read(0x80000000, 0x10000)) == bytes(sram), "SRAM intacte")
    end = BASE + len(fw.img)
    check(end <= gs.END_LIMIT, f"image décompressée jusqu'à {end:#x} (limite {gs.END_LIMIT:#x})")


# --- 2. interface ----------------------------------------------------------------------------------------------
def interface_alone(stock, fw):
    """Les vérifications de test_syntakt_machines.py, pour une machine ajoutée : Acid."""
    tsm.SAFE = True
    tsm.ADDED = [dict(ga.MACHINE, code="acid", index=6, label="Acid")]
    tsm.N, tsm.NM, tsm.TOP = 1, 7, 6
    tsm.FIRST, tsm.REC = {6: 76}, {6: gs.RECS}
    tsm.ROWS, tsm.CCROWS = gs.ROWSN, gs.CCROWSN
    tsm.NAMES = ["Kick", "Snare", "Metal", "Perc", "Tone", "Chord", ga.MACHINE["name"]]
    patched, payload = fw.img, fw.runtime
    a, b = tsm.tables(stock, patched, payload)
    tsm.lookups(a, b)
    tsm.accessors(a, b, stock, patched)
    tsm.setter_and_wheel(stock, patched, payload)
    tsm.records_and_change(stock, patched, payload)
    tsm.out_of_range(stock, patched, payload)
    pictures(stock, fw)


def pictures(stock, fw, ref=None):
    """Les images d'Acid (notes/44 §3.4) : objets Bitmap tels que les construirait l'OS, pixels voulus, et les 5 sites
    qui dessinent une image de machine : nos objets pour Acid, ceux de ref (l'OS d'origine, ou Model-TG seul) pour
    les autres machines."""
    ref_img = ref.img if ref else stock
    ui = lambda f: tms.UI(f) if f.blob_end else t7.UI(f.img, f.runtime)       # avec Model-TG : sa mémoire
    sym = next(t for t in fw.tweaks if t["id"].startswith("acid"))["symbols"]
    obj = {k: int(sym[f"art_{k}"], 16) for k in ("card", "mid", "small")}
    rt = lambda a, n: fw.runtime[a - fw.pay:a - fw.pay + n]
    # 1. les objets : octet pour octet ce que fait le constructeur de l'OS (0x40070172) avec nos images et ses masques
    ok, grids = True, {}
    for name, (w, h, mask, _, _) in ga.ART.items():
        image = struct.unpack(">I", rt(obj[name] + 0x10, 4))[0]
        u = ui(fw)
        u.call(0x40070172, 0x91000000, w, h, image, mask)
        ok &= bytes(u.uc.mem_read(0x91000000, 25)) == rt(obj[name], 25) and not u.bad
        grids[name] = ga.bm_read(rt(image, 4 * w * ga.bm_words(h)), w, h)
    # 2. les pixels : la fiche = celle de TONE sauf « STYLE:ACID » et les notes ; les smileys du générateur
    w, h, _, im0, step = ga.ART["card"]
    tone = ga.bm_read(stock[im0 + ga.TONE * step - BASE:][:step], w, h)
    card = grids["card"]
    same_top = all(card[y] == tone[y] for y in range(27, 33))                  # « CLASS:SYNTH »
    labels = all(card[y][x] == tone[y][x] for y in range(0, 21) for x in range(0, 15))   # « STR: DEX: MAG: »
    ok &= same_top and labels and card == ga.card_grid(tone)
    ok &= grids["mid"] == ga.smiley(34, 34, 16.6, (5.2, 4.5, 2.2, 3.8), 9.5, 3.2)
    ok &= grids["small"] == ga.smiley(25, 22, 11.2, (3.6, 3.0, 1.5, 2.6), 6.3, 2.4)
    check(ok, f"images d'Acid : 3 objets Bitmap identiques à ceux du constructeur de l'OS (fiche 48 x 33, smileys "
              f"34 x 34 et 25 x 22, masques de l'OS) ; fiche = celle de TONE (CLASS:SYNTH, libellés) avec STYLE:ACID et "
              f"STR/DEX/MAG {ga.STARS}")
    # 3. écran MACHINES : fiche et lettre
    ok, A = True, fw.index
    for m in range(A + 1):
        if ref:                                                  # sans lire les noms (celui du Sampler est en RAM)
            is_, ip = ([a[1] for k, a in tms.machines_screen(f, m) if k == "image"] for f in (ref, fw))
            bp = []
        else:
            _, is_, _, _ = t7.drum_select(ref_img, b"", m)
            _, ip, _, bp = t7.drum_select(fw.img, fw.runtime, m)
        ok &= not bp and (ip == [obj["card"], obj["mid"]] if m == A else ip == is_)
    check(ok, f"écran MACHINES : machines 0..{A - 1} identiques {'à Model-TG seul' if ref else 'au stock'} ; Acid -> sa "
              "fiche et son smiley")
    # 4. petite lettre (0x400a4dc4) et les 3 autres sites : l'image passée à la fonction de dessin 0x40071da4
    sites = (("petite lettre", 0x400a4dc4, 0, 0x40fe37f0, "small"),       # (nom, départ, d0 = m << .., tableau, objet)
             ("lettre 0x4001b6a6", 0x4001b696, 0, 0x40fe384c, "mid"),
             ("petite lettre 0x400a40bc", 0x400a4096, 0, 0x40fe37f0, "small"),
             ("petite lettre 0x400a4fc6", 0x400a4f9e, 8, 0x40fe37f0, "small"))
    res = []
    for label, start, sh, table, name in sites:
        got = {}
        for which, mk_ui in (("ref", lambda: ui(ref) if ref else t7.UI(stock)), ("modifié", lambda: ui(fw))):
            for m in range(A + 2):
                u = mk_ui()
                u.hooks = {0x40071da4: "image"}
                # on entre au milieu d'une fonction : arrêt dès que l'image est passée au dessin
                u.uc.hook_add(UC_HOOK_CODE, lambda uc, a, s_, d: uc.emu_stop(), begin=0x40071da4, end=0x40071da4)
                u.uc.mem_write(table, struct.pack(">I", 0x92200000))
                fp = t7.STACK - 0x100
                u.uc.mem_write(fp, struct.pack(">II", 0, t7.STOP))
                u.uc.mem_write(t7.STACK - 0x800, struct.pack(">I", t7.STOP) * 64)
                u.uc.reg_write(mk.UC_M68K_REG_A6, fp)
                u.uc.reg_write(mk.UC_M68K_REG_A7, t7.STACK - 0x800)
                u.uc.reg_write(mk.UC_M68K_REG_D0, m << sh)
                u.uc.reg_write(mk.UC_M68K_REG_D2, m)
                u.uc.reg_write(mk.UC_M68K_REG_A0, 0x91000000)
                u.uc.emu_start(start, t7.STOP, count=100_000)
                calls = [args[1] for k, args in u.calls if k == "image"]
                got[which, m] = calls[:1]
        ok = all(got["ref", m] == got["modifié", m] for m in range(A))
        ok &= got["modifié", A] == [obj[name]] and got["ref", A] == [0x92200000 + 28 * 5]
        res.append((label, ok, got["modifié", A + 1]))
    check(all(ok for _, ok, _ in res),
          f"images aux 4 autres sites ({', '.join(l for l, _, _ in res)}) : machines 0..{A - 1} identiques "
          f"{'à Model-TG seul' if ref else 'au stock'}, Acid -> son smiley (sans Acid : CHORD) ; machine hors limites "
          f"{A + 1} -> {['smiley' if g == [obj['small']] or g == [obj['mid']] else g for _, _, g in res]}")


# --- 3. son : la référence -------------------------------------------------------------------------------------
class Ref:
    """Le moteur compilé pour l'ordinateur (acid.c avec HOST, acid_ref.c), avec les tables de gen_acid.py."""

    def __init__(self, tmp):
        (tmp / "acid_tables.h").write_text(ga.tables_h())
        self.exe = tmp / "acid_ref"
        subprocess.run(["gcc", "-DHOST", "-O2", "-Wall", "-Wextra", "-Werror", f"-I{tmp}", str(ga.SRC / "acid.c"),
                        str(HERE / "acid_ref.c"), "-o", str(self.exe)], check=True)

    def run(self, recs):
        inp = b"".join(struct.pack("<6i9h", r["pmod"], *r["v"], *r["p"]) for r in recs)
        out = subprocess.run([str(self.exe)], input=inp, capture_output=True, check=True).stdout
        x = np.frombuffer(out, dtype="<i4").reshape(-1, 33).astype(np.int64)
        return x[:, 0], x[:, 1:]


class Probe:
    """Ce que reçoit le moteur à chaque bloc (entrée d'acid_update) et ce qu'il sort avant la chaîne d'ampli (entrée
    de AMP_ENV appelée depuis la charge utile) ; les lectures de la voix par la chaîne d'ampli."""

    def __init__(self, fw, e, track, reads=False):
        self.recs, self.block, self.reads = [], 0, [] if reads else None
        self.v = E.VOICE0 + track * E.VSTRIDE
        self.out_at = None
        uc = e.uc
        arg = lambda k: struct.unpack(">I", uc.mem_read(uc.reg_read(mk.UC_M68K_REG_A7) + 4 * k, 4))[0]

        def upd(uc_, a, s, u):
            if arg(2) != self.v:
                return
            vb = bytes(uc.mem_read(self.v, E.VSTRIDE))
            pb = bytes(uc.mem_read(arg(3), 0x26))
            self.recs.append(dict(block=self.block, pmod=struct.unpack(">i", struct.pack(">I", arg(1)))[0],
                                  v=[struct.unpack_from(">i", vb, o)[0] for o in VOFF],
                                  p=[struct.unpack_from(">h", pb, o)[0] for o in range(0x14, 0x26, 2)],
                                  render=0, out=None))

        def rnd(uc_, a, s, u):
            if arg(2) == self.v:
                self.out_at = arg(1)
                v32 = lambda o: struct.unpack(">i", uc.mem_read(self.v + o, 4))[0]
                self.recs[-1]["expected"] = int(bool(v32(0x34) or v32(0x38) or abs(v32(0x230)) >= IDLE_LEVEL
                                                     or abs(v32(0x234)) >= IDLE_LEVEL))

        def amp(uc_, a, s, u):
            if fw.pay <= arg(0) < fw.code_end and arg(1) == self.v:
                self.recs[-1]["render"] = 1
                self.recs[-1]["out"] = np.frombuffer(bytes(uc.mem_read(self.out_at, 128)), ">i4").astype(np.int64)
        uc.hook_add(UC_HOOK_CODE, upd, begin=fw.upd, end=fw.upd)
        uc.hook_add(UC_HOOK_CODE, rnd, begin=fw.rnd, end=fw.rnd)
        uc.hook_add(UC_HOOK_CODE, amp, begin=AMP[0][0], end=AMP[0][0])
        if reads:
            uc.hook_add(UC_HOOK_MEM_READ, self._read, begin=self.v, end=self.v + E.VSTRIDE - 1)

    def _read(self, uc, access, addr, size, value, ud):
        pc = uc.reg_read(mk.UC_M68K_REG_PC)
        if any(lo <= pc < hi for lo, hi in AMP):
            self.reads.append((self.block, addr - self.v, bytes(uc.mem_read(addr, size))))


def play(fw, idx, kw, blocks, trigs=(1,), changes=None, track=0, reads=False):
    """Une piste sur la machine idx, les autres éteintes. changes : {bloc : réglages} (p-locks, potards)."""
    e = fw.engine(solo=track)
    e.set(track, machine=idx, **kw)
    pr = Probe(fw, e, track, reads) if fw.payload and idx == fw.index else None
    out = []
    for b in range(blocks):
        for k, v in (changes or {}).get(b, {}).items():
            e.set(track, **{k: v})
        if pr:
            pr.block = b
        out.append(e.block(1 << track if b in trigs else 0)[track])
    return np.stack(out), pr, e.unmapped


def cases():
    """(nom, réglages, trigs, changements, blocs)."""
    k = BASE_KW
    return [
        ("réglages par défaut", dict(k), (1, 120), None, 240),
        ("carré", dict(k, shape=127), (1, 120), None, 200),
        ("fondu scie/carré 64", dict(k, shape=64), (1,), None, 120),
        ("passe-bas fermé (COLOR 0)", dict(k, color=0, contour=64), (1,), None, 80),
        ("passe-bas ouvert (COLOR 63)", dict(k, color=63), (1,), None, 80),
        ("ouvert (COLOR 64)", dict(k, color=64), (1,), None, 80),
        ("passe-haut (COLOR 80)", dict(k, color=80, contour=40), (1, 60), None, 120),
        ("passe-haut (COLOR 127)", dict(k, color=127), (1,), None, 80),
        ("résonance 0", dict(k, sweep=0), (1,), None, 80),
        ("résonance 127 (auto-oscillation)", dict(k, sweep=127, contour=64), (1,), None, 200),
        ("résonance 127 + accent", dict(k, sweep=127, punch=1), (1, 100), None, 200),
        ("enveloppe vers le bas (CONTOUR 0)", dict(k, color=50, contour=0), (1,), None, 120),
        ("enveloppe au maximum (CONTOUR 127)", dict(k, color=10, contour=127), (1,), None, 120),
        ("accent", dict(k, punch=1), (1, 60, 120), None, 180),
        ("DECAY 0 et 127", dict(k, decay=0), (1,), {60: {"decay": 127}}, 160),
        ("GATE", dict(k, gate=1, decay=20), (1,), {50: {"gate": 0}}, 120),
        ("DECAY 10 : la voix se tait, puis repart", dict(k, decay=10), (1, 200), None, 260),
        ("note 0, PITCH 0 : borné en bas", dict(k, note=0, pitch=0), (1,), None, 60),
        ("note 127, PITCH 127, FINE 127 : borné en haut", dict(k, note=127, pitch=127, finetune=127), (1,), None, 60),
        ("note 96, FINE 0", dict(k, note=96, finetune=0), (1,), None, 60),
        ("COLOR balayé en 8.8 à chaque bloc (LP -> HP)", dict(k), (1,),
         {b: {"color": b * 127 / 200} for b in range(200)}, 200),
        ("tous les potards bougent à chaque bloc", dict(k), (1, 50, 100),
         {b: {"shape": (7 * b) % 128, "sweep": (5 * b) % 128, "contour": (3 * b) % 128, "color": (11 * b) % 128}
          for b in range(150)}, 150),
        ("notes qui changent (trigs)", dict(k), (1, 30, 60, 90), {30: {"note": 48}, 60: {"note": 39}, 90: {"note": 24}},
         120),
    ]


# --- 3. son : les vérifications --------------------------------------------------------------------------------
def exact(fw, ref, todo, label):
    """Avant la chaîne d'ampli : identique au moteur compilé pour l'ordinateur, et une voix muette n'est pas
    calculée."""
    bad, idle_seen, peaks, gate_bad, blocks_seen = [], 0, [], [], 0
    for name, kw, trigs, changes, blocks in todo:
        out, pr, unm = play(fw, fw.index, kw, blocks, trigs, changes)
        flags, want = ref.run(pr.recs)
        got_flags = np.array([r["render"] for r in pr.recs])
        rendered = [i for i, r in enumerate(pr.recs) if r["render"]]
        got = np.array([pr.recs[i]["out"] for i in rendered]).reshape(-1, 32)
        idle = [r["block"] for r in pr.recs if not r["render"]]
        silent = not out[idle].any() if idle else True
        idle_seen += len(idle)
        blocks_seen += len(pr.recs)
        if any(r.get("expected") != r["render"] for r in pr.recs):
            gate_bad.append(name)
        peak = int(np.abs(got).max()) if len(got) else 0
        peaks.append(peak)
        # la machine ne change qu'au bloc qui suit un trig (notes/43 §2) : Acid tourne à chaque bloc ensuite
        every = [r["block"] for r in pr.recs] == list(range(min(trigs) + 1, blocks))
        ok = (every and np.array_equal(flags, got_flags) and np.array_equal(want[rendered], got)
              and silent and not unm and peak > 1 << 20)
        if not ok:
            first = next((i for i in range(len(got)) if not np.array_equal(want[rendered][i], got[i])), None)
            bad.append(name)
            print(f"        ECART {name} : {len(got)} blocs rendus, drapeaux égaux {np.array_equal(flags, got_flags)},"
                  f" 1er bloc différent {first}, crête {peak:.3g}, muets non nuls {not silent}, hors mémoire {unm[:2]}")
    check(not bad, f"{label} : avant la chaîne d'ampli, identique échantillon par échantillon au moteur compilé pour "
                   f"l'ordinateur ({len(todo)} cas, crêtes {min(peaks):.2g} à {max(peaks):.2g} sur 2^31) {bad[:5]}")
    check(idle_seen > 0 and not gate_bad, f"{label} : voix calculée exactement quand l'OS l'impose (trig, ou enveloppe "
          f"d'ampli au-dessus de 2^14), sur {blocks_seen} blocs ; {idle_seen} blocs de voix muette, sortie nulle "
          f"{gate_bad[:5]}")


def amp_like_tone(fw):
    """La chaîne d'ampli (enveloppe, VCA, PUNCH) lit dans la voix Acid exactement ce qu'elle lit dans une voix TONE,
    bloc par bloc, tant que la voix Acid est calculée."""
    res = []
    for kw in (dict(decay=30), dict(decay=90, punch=1), dict(decay=60, gate=1), dict(decay=127, punch=1, gate=1)):
        k = dict(BASE_KW, **kw)
        changes = {60: {"gate": 0}} if kw.get("gate") else None
        _, pm, unm = play(fw, fw.index, k, 120, (1, 40), changes, reads=True)
        stop = next((r["block"] for r in pm.recs if not r["render"]), 120)
        tone_reads = []
        e = fw.engine(solo=0)                   # TONE : lectures de la chaîne d'ampli, sans le moteur d'Acid
        e.set(0, machine=TONE, **k)
        v = E.VOICE0
        blk = {"b": 0}

        def rd(uc, access, addr, size, value, ud):
            pc = uc.reg_read(mk.UC_M68K_REG_PC)
            if any(lo <= pc < hi for lo, hi in AMP):
                tone_reads.append((blk["b"], addr - v, bytes(uc.mem_read(addr, size))))
        e.uc.hook_add(UC_HOOK_MEM_READ, rd, begin=v, end=v + E.VSTRIDE - 1)
        for b in range(120):
            for k2, v2 in (changes or {}).get(b, {}).items():
                e.set(0, **{k2: v2})
            blk["b"] = b
            e.block(1 if b in (1, 40) else 0)
        rt = [x for x in tone_reads if x[0] < stop]
        rm = [x for x in pm.reads if x[0] < stop]
        res.append((rt == rm and len(rm) > 0 and not unm, stop, len({o for _, o, _ in rm})))
    check(all(ok for ok, _, _ in res),
          f"chaîne d'ampli : mêmes lectures de la voix que TONE (DECAY, PUNCH, GATE ; {res[0][2]} champs), bloc par "
          f"bloc jusqu'au silence (blocs {[s for _, s, _ in res]})")


def stock_unchanged(ref_fw, fw, label):
    """6 pistes sur les machines d'origine (2 trigs) : identiques, et rien du code d'Acid ne tourne."""
    def run(f, hook):
        e = f.engine()
        for t in range(6):
            e.set(t, **dict(BASE_KW, machine=t, note=60, color=64, shape=64, contour=64, decay=60))
        ran = []
        if hook:
            e.uc.hook_add(UC_HOOK_CODE, lambda uc, a, s, u: ran.append(a), begin=f.pay, end=f.code_end - 1)
        x = np.stack([e.block(0x3f if b in (1, 150) else 0) for b in range(300)])
        return x, ran, e.unmapped
    r, _, _ = run(ref_fw, False)
    x, ran, unm = run(fw, True)
    check(np.array_equal(r, x) and np.abs(x).max() > 1e7 and not ran and not unm,
          f"6 machines d'origine : identiques à {label}, échantillon par échantillon, sans une instruction d'Acid")


def like(alone, fw, label):
    """Sortie finale de la piste Acid identique dans deux firmwares."""
    bad = []
    for kw in (dict(), dict(color=90), dict(sweep=127, punch=1), dict(shape=127, color=64)):
        k = dict(BASE_KW, decay=40, **kw)
        a, _, _ = play(alone, alone.index, k, 200, (1, 120))
        b, _, unm = play(fw, fw.index, k, 200, (1, 120))
        if not np.array_equal(a, b) or unm or not a.any():
            bad.append(str(kw))
    check(not bad, f"{label}, sortie finale de la piste (4 réglages) {bad}")


def locks(fw, label):
    """Machine locks sur une piste : SNARE, Acid, TONE, Acid (passe-haut), KICK : tout joue."""
    seq = [dict(machine=1), dict(machine=fw.index, color=30), dict(machine=TONE), dict(machine=fw.index, color=90),
           dict(machine=0)]
    e = fw.engine(solo=0)
    e.set(0, **dict(BASE_KW, machine=1, decay=40))
    out = []
    for b in range(60 * len(seq)):
        if b % 60 == 0:
            e.set(0, **seq[b // 60])
        out.append(e.block(1 if b % 60 == 1 else 0)[0])
    x = np.stack(out)
    parts = [int(np.abs(x[60 * k + 2:60 * k + 60]).max()) for k in range(len(seq))]
    marks = struct.unpack(">I", e.uc.mem_read(E.VOICE0 + 0x2c, 4))[0]
    check(all(p > 1e6 for p in parts) and not e.unmapped and marks != MARK,
          f"{label} : machine locks SNARE -> Acid (passe-bas) -> TONE -> Acid (passe-haut) -> KICK sur une piste : tout "
          f"joue (crêtes {[f'{p:.2g}' for p in parts]})")


def six_tracks(fw, label):
    """6 pistes Acid, 6 réglages : chacune identique à la même piste jouée seule (un état par piste)."""
    sets = [dict(color=10), dict(color=40, shape=127), dict(color=64), dict(color=90), dict(sweep=127),
            dict(punch=1, contour=20)]
    e = fw.engine()
    for t, kw in enumerate(sets):
        e.set(t, **dict(BASE_KW, machine=fw.index, note=36 + 5 * t, **kw))
    x = np.stack([e.block(0x3f if b in (1, 100) else 0) for b in range(160)])
    ok = not e.unmapped
    for t, kw in enumerate(sets):
        y, _, unm = play(fw, fw.index, dict(BASE_KW, note=36 + 5 * t, **kw), 160, (1, 100), track=t)
        ok &= np.array_equal(x[:, t], y) and not unm and y.any()
    check(ok, f"{label} : 6 pistes Acid ensemble (6 réglages), chacune identique à la même piste jouée seule")


def mixed(fw, ref_fw, label, sampler=False):
    """Acid mêlée aux autres machines (et au Sampler de Model-TG, muet sans échantillon) : les autres pistes identiques
    au même firmware sans Acid, chaque piste Acid identique à la même piste jouée seule."""
    trigs = {1: 0x3f, 150: 0x3f}
    mach = [0, fw.index, 6 if sampler else 2, 5, fw.index, TONE]
    ours = {1: dict(color=20), 4: dict(color=100)}
    setup = {t: dict(BASE_KW, machine=m, note=48, decay=40, **ours.get(t, {})) for t, m in enumerate(mach)}

    def multi(f, s):
        e = f.engine()
        for t, kw in s.items():
            e.set(t, **kw)
        return np.stack([e.block(trigs.get(b, 0)) for b in range(300)]), e.unmapped
    x, unm = multi(fw, setup)
    r, unm_r = multi(ref_fw, {t: dict(kw, machine=0 if t in ours else kw["machine"]) for t, kw in setup.items()})
    ok = not unm and not unm_r
    for t in range(6):
        if t in ours:
            y, _, unm_s = play(fw, fw.index, dict(BASE_KW, note=48, decay=40, **ours[t]), 300, (1, 150), track=t)
            ok &= np.array_equal(x[:, t], y) and y.any() and not unm_s
        else:
            ok &= np.array_equal(x[:, t], r[:, t])
    if sampler:
        ok &= not x[:, 2].any()
    check(ok, f"{label} : pistes {[m + 1 for m in mach]} ensemble ; autres machines identiques sans Acid, chaque "
              "piste Acid identique à la même piste jouée seule")


def behaviour(fw):
    """Le son se comporte comme prévu : la coupure suit COLOR, la résonance au maximum reste bornée."""
    def tone_of(kw, blocks=120):
        x, _, _ = play(fw, fw.index, dict(BASE_KW, **kw), blocks, (1,))
        return x[20:].reshape(-1).astype(float)

    def centroid(x):
        X = np.abs(np.fft.rfft(x * np.hanning(len(x))))
        f = np.fft.rfftfreq(len(x), 1 / 48000)
        return float((f * X).sum() / X.sum())
    lp = [centroid(tone_of(dict(color=c, contour=64, sweep=0, decay=127))) for c in (10, 30, 50)]
    hp = [centroid(tone_of(dict(color=c, contour=64, sweep=0, decay=127))) for c in (70, 95, 120)]
    check(lp[0] < lp[1] < lp[2] and hp[0] < hp[1] < hp[2],
          f"COLOR : le centre du spectre monte avec la coupure, passe-bas {[round(c) for c in lp]} Hz, passe-haut "
          f"{[round(c) for c in hp]} Hz")
    # pas de marche à COLOR 64 (notes/44 §3.2)
    def level(kw):
        x = tone_of(dict(kw, contour=64, decay=127), 160)
        X = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
        return 10 * np.log10(X[np.fft.rfftfreq(len(x), 1 / 48000) < 16000].sum())
    steps = []
    for kw in (dict(shape=0, punch=0), dict(shape=127, punch=1)):
        for sweep in (0, 90, 127):
            k = dict(kw, sweep=sweep)
            mid = level(dict(k, color=64))
            steps.append([round(float(level(dict(k, color=c)) - mid), 1) for c in (63, 64 - 1 / 256, 64 + 1 / 256, 65)])
    check(all(abs(s) <= 2 for st in steps for s in st),
          f"COLOR 63 / 63,99 / 64,01 / 65 : niveau à 2 dB près du filtre ouvert (64) (note 36 ; scie, puis carré + "
          f"accent ; résonance 0, 90, 127 : {steps} dB)")
    x = tone_of(dict(sweep=127, punch=1, contour=64, color=40, decay=127), 400)
    first, last = np.abs(x[:4800]).max(), np.abs(x[-4800:]).max()
    check(last < 2 ** 31 - 1 and last <= 1.5 * first,
          f"résonance 127 + accent : auto-oscillation bornée par le coude (crête {first / 2 ** 31:.2f} au début, "
          f"{last / 2 ** 31:.2f} à la fin, sur 2^31), sans saturation")


# --- 4. coût ---------------------------------------------------------------------------------------------------
def cost(fw, label):
    """Instructions par bloc d'une voix (boucle des voix entière, moins la même boucle sans voix), pile."""
    def run(idx, kw, blocks, trigs=(1,)):
        e = fw.engine(solo=0)
        e.set(0, machine=idx, **kw)
        if idx == OFF:
            e.uc.mem_write(E.VOICE0, struct.pack(">II", OFF, OFF))
        n = {"i": 0, "sp": 1 << 32}

        def hk(uc, a, s, u):
            n["i"] += 1
            if fw.pay <= a < fw.code_end:
                n["sp"] = min(n["sp"], uc.reg_read(mk.UC_M68K_REG_A7))
        e.uc.hook_add(UC_HOOK_CODE, hk)
        per = []
        for b in range(blocks):
            i0 = n["i"]
            e.block(1 if b in trigs else 0)
            per.append(n["i"] - i0)
        return np.array(per), n["sp"]
    base, _ = run(OFF, BASE_KW, 4, trigs=())
    zero = int(np.median(base))
    tone, _ = run(TONE, dict(BASE_KW, color=40, shape=38, sweep=52, contour=42, decay=42), 24)
    tone = int(np.median(tone[4:])) - zero
    rows, deep = [], 0
    for name, kw in (("passe-bas", dict()), ("passe-haut", dict(color=90)), ("ouvert (64)", dict(color=64)),
                     ("carré", dict(shape=127)), ("résonance 127 + accent (coude)", dict(sweep=127, punch=1)),
                     ("note 96", dict(note=96))):
        per, sp = run(fw.index, dict(BASE_KW, decay=100, **kw), 24)
        per = per - zero
        rows.append((name, int(per[2]), int(round(per[4:].mean())), int(per[4:].max())))
        deep = max(deep, E.STACK - 0x100 - sp)
    idle, _ = run(fw.index, dict(BASE_KW, decay=0), 200, trigs=(1,))
    idle = int(np.median(idle[150:])) - zero
    print(f"        boucle des voix sans voix : {zero} instructions par bloc ; TONE : {tone}")
    for n_, f, t, x in rows:
        print(f"        {n_:<32} 1er bloc {f:6}  moyenne {t:6}  maximum {x:6}  ({t / tone:.2f} TONE)")
    typ = [r[2] for r in rows]
    check(True, f"{label} : coût moyen d'une voix Acid {min(typ)} à {max(typ)} instructions par bloc ({min(typ) / tone:.2f} "
                f"à {max(typ) / tone:.2f} TONE ; TONE {tone}) ; voix muette {idle} ; pile {deep} o sous la boucle des voix")
    return rows


def with_others(stock, cycles, ids, alone, tg_fw, tg):
    """Acid avec d'autres mods (--with) : Acid seule, ou sa version combinée si model-tg-st est dans la liste."""
    by_id = {t["id"]: t for t in (load(f.name) for f in sorted(DEV.glob("[0-9]*.json")))}
    unknown = [i for i in ids if i not in by_id]
    if unknown:
        raise SystemExit(f"!! tweaks inconnus : {unknown}")
    others = [by_id[i] for i in ids]
    with_tg = any(t["id"].startswith("model-tg") for t in others)
    mine = by_id["acid-tg" if with_tg else "acid"]
    clash = [t["id"] for t in others if mine["id"] in t.get("conflicts", []) or t["id"] in mine["conflicts"]]
    if clash:
        raise SystemExit(f"!! incompatibles avec acid : {clash}")
    fw = Fw(stock, sorted(others + [mine], key=lambda t: t["order"]))
    ref_fw = Fw(stock, sorted(others, key=lambda t: t["order"]))
    label = ", ".join(ids)
    print(f"\n== acid avec {label}")
    print("démarrage")
    t7.X.bootstrap_depack_ok(cycles, fw.tweaks, None) or t7.FAIL.append("bootstrap avec " + label)
    boot(fw, tg if with_tg else None)
    print("son")
    stock_unchanged(ref_fw, fw, "ces mods sans Acid")
    like(tg_fw if with_tg else alone, fw, f"Acid avec {label} = Acid {'avec Model-TG seul' if with_tg else 'seule'}")
    locks(fw, f"Acid avec {label}")
    mixed(fw, ref_fw, f"Acid avec {label}", sampler=with_tg)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycles", required=True, help="model-cycles_OS1.13.syx officiel")
    ap.add_argument("--with", dest="others", default="", help="ids d'autres tweaks : Acid avec eux (section 5)")
    args = ap.parse_args()
    stock = T.main_os_from_syx(args.cycles)
    acid = load("26-acid.json")
    off = Fw(stock, [])
    alone = Fw(stock, [acid])
    with tempfile.TemporaryDirectory() as d:
        ref = Ref(pathlib.Path(d))
        print(f"== {acid['id']} : Acid en machine {alone.index + 1}")
        print("démarrage")
        t7.X.bootstrap_depack_ok(args.cycles, acid, None) or t7.FAIL.append("bootstrap")
        boot(alone)
        print("interface")
        interface_alone(stock, alone)
        print("son")
        exact(alone, ref, cases(), "Acid seule")
        amp_like_tone(alone)
        stock_unchanged(off, alone, "l'OS d'origine")
        locks(alone, "Acid seule")
        six_tracks(alone, "Acid seule")
        mixed(alone, off, "Acid seule")
        behaviour(alone)
        print("coût")
        cost(alone, "Acid seule")

        gs.set_base(gs.PAY_TG)
        gs.CATALOG["acid"] = ga.MACHINE
        tg_tw, acid_tg = load("30-model-tg-st.json"), load("33-acid-tg.json")
        fw, ref_tg = Fw(stock, [tg_tw, acid_tg]), Fw(stock, [tg_tw])
        tg = {k: int(v, 16) for k, v in tg_tw["symbols"].items()}
        tg["knob_vec"] = tms.knob_vec_at(acid_tg)
        print(f"\n== {acid_tg['id']} : avec Model-TG, Acid en machine {fw.index + 1}")
        print("démarrage")
        t7.X.bootstrap_depack_ok(args.cycles, [tg_tw, acid_tg], None) or t7.FAIL.append("bootstrap avec Model-TG")
        boot(fw, tg)
        print("interface")
        tms.interface(ref_tg, fw, ["acid"], tg)
        pictures(stock, fw, ref_tg)
        print("son")
        exact(fw, ref, [c for c in cases() if c[0].startswith(("réglages", "passe-haut (COLOR 80", "accent", "DECAY 10"))],
              "Acid avec Model-TG")
        stock_unchanged(ref_tg, fw, "Model-TG seul")
        like(alone, fw, "Acid avec Model-TG = Acid seule")
        locks(fw, "Acid avec Model-TG")
        six_tracks(fw, "Acid avec Model-TG")
        mixed(fw, ref_tg, "Acid avec Model-TG", sampler=True)
        print("coût")
        cost(fw, "Acid avec Model-TG")
        if args.others:
            with_others(stock, args.cycles, args.others.split(","), alone, fw, tg)
    fail = t7.FAIL + tms.FAIL + getattr(tsm, "FAIL", [])
    print("\nTOUT OK" if not fail else f"\n{len(fail)} ÉCHEC(S)")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
