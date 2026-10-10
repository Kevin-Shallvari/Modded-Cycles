#!/usr/bin/env python3
"""Preuve d'étude (notes/52 §3ter) : deux retouches de Model-TG pour qu'une 7e machine (index 7) choisisse,
garde et protège une table comme le Sampler. Model-TG construit avec et sans (WT_PATCHES), son vrai code exécuté.

    M68K_CROSS=m68k-elf- .venv/bin/python build/wt-proof/test_wt_select.py --cycles firmware/model-cycles_OS1.13.syx
"""
import argparse
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "emu"))

from unicorn import UcError, UC_HOOK_CODE           # noqa: E402
from unicorn import m68k_const as mk                # noqa: E402

import build                                        # noqa: E402
import gen_model_tg as G                            # noqa: E402
import test_model_tg as TM                          # noqa: E402

WT = 7                                              # notre machine, après le Sampler (6)
WT_PATCHES = (
    ("src/model_tg.s",
     "    jsr     any_sampler\n    tstl    %d0\n    beqw    pf_need\n",
     "    jsr     wt_or_any             | Modded-Cycles: our machine's track loads too\n"
     "    tstl    %d0\n    beqw    pf_need\n",
     "navigateur : la piste cible de notre machine charge, Sampler ou non"),
    ("src/model_tg.s",
     "| ---- d0 = track index  ->  d0 = runtime sound object, or 0 --------------\n",
     "| Modded-Cycles: d2 = target track. 1 if it is our machine, else any_sampler.\n"
     "wt_or_any:\n"
     "    movel   %d2,%d0\n    jsr     sound_obj\n    tstl    %d0\n    beqs    woa_any\n"
     "    movea.l %d0,%a0\n    moveq   #0,%d0\n    moveb   %a0@(38),%d0\n"
     f"    cmpil   #{WT},%d0\n    bnes    woa_any\n    moveq   #1,%d0\n    rts\n"
     "woa_any:\n    jmp     any_sampler\n"
     "np_wt:      .long 0               | Modded-Cycles: name_probe, our machine\n\n"
     "| ---- d0 = track index  ->  d0 = runtime sound object, or 0 --------------\n",
     "wt_or_any, np_wt"),
    ("src/model_tg.s",
     "    cmpil   #6,%d0\n    bnew    np_nosmp              | only the Sampler carries a token\n"
     "    bsr     st_apply_c            | the packed state, when the sound has one\n"
     "    lea.l   st_ok,%a0\n    movel   %d0,%a0@\n    lea.l   %a2@(4),%a3\n",
     "    clrl    np_wt\n    cmpil   #6,%d0\n    beqs    np_smp\n"
     f"    cmpil   #{WT},%d0               | Modded-Cycles: our machine's token too\n"
     "    bnew    np_nosmp\n    movel   %d0,np_wt\n    bras    np_tok\n"
     "np_smp:\n"
     "    bsr     st_apply_c            | the packed state, when the sound has one\n"
     "    lea.l   st_ok,%a0\n    movel   %d0,%a0@\n"
     "np_tok:\n    lea.l   %a2@(4),%a3\n",
     "name_probe : notre machine, empreinte seule"),
    ("src/model_tg.s",
     "    tstl    %d3\n    beqw    np_notok\n    | byte 11 is the playback mode",
     "    tstl    %d3\n    beqw    np_notok\n"
     "    tstl    np_wt                 | Modded-Cycles: no Sampler state for ours\n"
     "    bnew    np_nopt\n    | byte 11 is the playback mode",
     "name_probe : sauter l'état du Sampler"),
)
VARS = ("track_hash", "track_slot", "track_pend", "track_tried", "loop_mode", "os_opt", "sl_cfg", "gr_shape",
        "gr_dir", "gr_frz", "pl_dirty", "tok_seen")
STOP = 0x40780000
CALL_SP = 0x9000e000
KIT = 0x4f000000
FIX = 0x93000000
PROJ, TRKVT = FIX + 0x10000, FIX + 0x4000
PROJ_PTR = 0x40fe4228
CUR_KIT = 0x40a78888
H_OWN, H_NEW, H_OLD = 0x0000AAAB, 0x6809683D, 0x0BADF00D
FAIL = []


def check(ok, msg):
    print(("  ok    " if ok else "  ECHEC ") + msg, flush=True)
    if not ok:
        FAIL.append(msg)


def sound(machine, name):
    s = bytearray(100)
    s[4:20] = name.ljust(16, b"\0")[:16]
    s[38] = machine
    return bytes(s)


def smp(h):
    return b"SMP%08X" % h


class Rig:
    """Model-TG seul : sons des pistes (vrai sound_obj), chargeur simulé (ensure_loaded), le reste réel."""

    def __init__(self, img, end, syms, machines, names):
        self.s = syms
        e = self.e = TM.engine(img, end=end)
        uc = self.uc = e.uc
        uc.mem_map(FIX, 0x02000000)
        self.loads, self.next_slot = [], 10
        for addr, fn in {syms["ensure_loaded"]: self._load, 0x400a51fa: lambda: 1}.items():
            self.stub(addr, fn)
        w = self.w32
        w(PROJ_PTR, PROJ)
        w(CUR_KIT, KIT)
        for t in range(6):
            uc.mem_write(KIT + 28 + 100 * t, sound(machines[t], names[t]))
            vt = TRKVT + 0x40 * t
            w(PROJ + 212 + 68 * t, vt)
            w(vt + 40, vt + 0x30)
            uc.mem_write(vt + 0x30, b"\x20\x3c" + struct.pack(">I", KIT + 28 + 100 * t) + b"\x4e\x75")
        w(syms["kit_ok"], 0)                      # kit_check sauté ; proj_has rend 0
        for k in ("slot_hash", "slot_base", "slot_count", "slot_size"):
            uc.mem_write(syms[k], bytes(4 * 64))
        for t in range(6):
            w(syms["track_hash"] + 4 * t, 0)
            w(syms["track_slot"] + 4 * t, 0xffffffff)
            w(syms["track_pend"] + 4 * t, 0xffffffff)

    def w32(self, a, v):
        self.uc.mem_write(a, struct.pack(">I", v & 0xffffffff))

    def r32(self, a):
        return struct.unpack(">I", self.uc.mem_read(a, 4))[0]

    def stub(self, addr, fn):
        def hook(uc, a, size, ud):
            r = fn()
            sp = uc.reg_read(mk.UC_M68K_REG_A7)
            uc.reg_write(mk.UC_M68K_REG_D0, r & 0xffffffff)
            uc.reg_write(mk.UC_M68K_REG_PC, struct.unpack(">I", uc.mem_read(sp, 4))[0])
            uc.reg_write(mk.UC_M68K_REG_A7, sp + 4)
        self.uc.hook_add(UC_HOOK_CODE, hook, begin=addr, end=addr)

    def _load(self):
        h = self.uc.reg_read(mk.UC_M68K_REG_D0)
        self.loads.append(h)
        for s in range(64):
            if self.r32(self.s["slot_hash"] + 4 * s) == h:
                return s
        s, self.next_slot = self.next_slot, self.next_slot + 1
        self.resident(s, h)
        return s

    def resident(self, s, h):
        for k, v in zip(("slot_hash", "slot_base", "slot_count", "slot_size"),
                        (h, 0x4c000000 + 0x100000 * s, 1024, 0x1000)):
            self.w32(self.s[k] + 4 * s, v)

    def call(self, fn, *args):
        uc = self.uc
        uc.reg_write(mk.UC_M68K_REG_SR, 0x2000)
        frame = struct.pack(">I", STOP) + b"".join(struct.pack(">I", a) for a in args)
        uc.mem_write(CALL_SP - len(frame), frame)
        uc.reg_write(mk.UC_M68K_REG_A7, CALL_SP - len(frame))
        try:
            uc.emu_start(fn, STOP, count=2_000_000)
        except UcError as ex:
            return f"erreur {ex} en {uc.reg_read(mk.UC_M68K_REG_PC):#x}"
        pc = uc.reg_read(mk.UC_M68K_REG_PC)
        return None if pc == STOP and not self.e.unmapped else f"arrêt en {pc:#x}, {self.e.unmapped[:3]}"

    def state(self):
        st = {k: [self.r32(self.s[k] + 4 * t) for t in range(6)] for k in VARS if k not in ("pl_dirty", "tok_seen")}
        st["pl_dirty"], st["tok_seen"] = self.r32(self.s["pl_dirty"]), self.r32(self.s["tok_seen"])
        st["names"] = [bytes(self.uc.mem_read(KIT + 28 + 100 * t + 4, 16)) for t in range(6)]
        st["msg"] = bytes(self.uc.mem_read(self.s["msg_buf"], 32)).split(b"\0")[0]
        return st


def variant(cycles, repo, patches):
    tw, stock, _, syms = G.export(cycles, repo, patches)
    tw = G.adapt(tw, stock, syms)
    pl, _ = build.build_payload([tw], stock, None)
    img = bytes(build.apply_writes(stock, [tw])[0]) + pl
    return img, G.BASE + len(stock) + tw["append"]["size"], syms


def browser(v, machines, target):
    """Fichier ouvert dans le navigateur sur la piste target (sel_hash = H_NEW) : vrai preset_fail_hook."""
    r = Rig(*v, machines, [b"Kick"] * 6)
    r.w32(v[2]["sel_hash"], H_NEW)
    err = r.call(v[2]["preset_fail_hook"], 0, 0, target)
    return err, r.state(), r.loads


def reload(v, machines, names, wt_track):
    """Projet rechargé : vrai name_probe, puis load_pending ; puis le chargeur cherche de la place (evict_one) tant
    qu'il peut, et un compactage (rebuild_slots + refresh_tracks)."""
    s = v[2]
    r = Rig(*v, machines, names)
    r.resident(3, H_OLD)                           # un fichier que rien ne demande
    errs = [r.call(s["name_probe"]), r.call(s["load_pending"])]
    after_probe = r.state()
    slot = after_probe["track_pend"][wt_track] & 0xffff
    evicted = []
    for _ in range(8):
        errs.append(r.call(s["evict_one"]))
        if not r.uc.reg_read(mk.UC_M68K_REG_D0):
            break
        evicted.append([r.r32(s["slot_hash"] + 4 * k) for k in range(64)])
    kept = [h for h in (H_OLD, H_OWN, H_NEW) if any(r.r32(s["slot_hash"] + 4 * k) == h for k in range(64))]
    errs += [r.call(s["rebuild_slots"]), r.call(s["refresh_tracks"])]
    after_compact = r.state()
    slot2 = after_compact["track_slot"][wt_track]
    h2 = r.r32(s["slot_hash"] + 4 * slot2) if slot2 < 64 else None
    return [e for e in errs if e], after_probe, slot, kept, h2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", required=True)
    ap.add_argument("--model-tg", default=str(ROOT / "vendor" / "Model-TG"))
    a = ap.parse_args()
    cycles, repo = pathlib.Path(a.cycles).resolve(), pathlib.Path(a.model_tg).resolve()
    print("build de Model-TG, d'origine (MC_PATCHES) et retouché (+ WT_PATCHES)")
    v0 = variant(cycles, repo, G.MC_PATCHES)
    v1 = variant(cycles, repo, G.MC_PATCHES + WT_PATCHES)
    print(f"  bloc de code : {v0[1] - G.BASE - 0x1aa140:+} -> retouché {v1[1] - v0[1]:+} o")

    print("1. navigateur (preset_fail_hook), fichier H_NEW ouvert sur la piste 1")
    S, K = 6, 0
    cases = [("notre machine, aucun Sampler", [K, WT, K, K, K, K], 1, True),
             ("notre machine, un Sampler piste 4", [K, WT, K, K, S, K], 1, False),
             ("piste Sampler", [K, S, K, K, K, K], 1, False),
             ("Kick, aucun Sampler", [K, K, K, K, K, K], 1, False),
             ("Kick, un Sampler piste 4", [K, K, K, K, S, K], 1, False),
             ("notre machine piste 2, cible piste 1 (Kick)", [K, K, WT, K, K, K], 1, False)]
    for label, mach, t, changes in cases:
        e0, s0, l0 = browser(v0, mach, t)
        e1, s1, l1 = browser(v1, mach, t)
        check(not e0 and not e1, f"{label} : revient proprement ({e0 or e1 or ''})")
        if changes:
            check(s0["msg"].startswith(b"Select sample") and s0["track_hash"][t] == 0 and not l0,
                  f"{label} : origine refuse ({s0['msg']!r})")
            check(s1["track_hash"][t] == H_NEW and s1["track_slot"][t] < 64 and l1 == [H_NEW]
                  and s1["names"][t][:11] == smp(H_NEW),
                  f"{label} : retouché charge, track_hash, case {s1['track_slot'][t]}, nom {s1['names'][t][:11]!r}")
        else:
            check(s0 == s1 and l0 == l1, f"{label} : identique ({s0['msg']!r}, chargements {l0})")

    print("2. projet rechargé (name_probe, load_pending), place cherchée (evict_one), compactage")
    mach = [S, WT, K, WT, K, S]
    names = [smp(H_OWN), smp(H_NEW), smp(H_OLD), b"Wavetable", b"Kick", b"SMP0000AAAB"]
    e0, p0, sl0, kept0, h0 = reload(v0, mach, names, 1)
    e1, p1, sl1, kept1, h1 = reload(v1, mach, names, 1)
    check(not e0 and not e1, f"reviennent proprement {e0 or e1 or ''}")
    check(p0["track_hash"] == [H_OWN, 0, 0, 0, 0, H_OWN], f"origine : track_hash {[hex(x) for x in p0['track_hash']]}")
    check(p1["track_hash"] == [H_OWN, H_NEW, 0, 0, 0, H_OWN],
          f"retouché : notre piste 1 reprend sa table, piste 3 sans jeton et Kick « SMP » ignorés "
          f"{[hex(x) for x in p1['track_hash']]}")
    check(sl1 < 64, f"retouché : load_pending la met en attente (case {sl1})")
    check(p1["tok_seen"] == p0["tok_seen"] + 1, f"tok_seen : un jeton de plus, le nôtre ({p0['tok_seen']} -> {p1['tok_seen']})")
    same = {k: (p0[k], p1[k]) for k in VARS if k not in ("track_hash", "track_slot", "track_pend", "track_tried",
                                                          "pl_dirty", "tok_seen") and p0[k] != p1[k]}
    check(not same, f"état du Sampler inchangé (modes, options, tok_seen) {same or ''}")
    check(p0["track_hash"][0::5] == p1["track_hash"][0::5] and p0["track_slot"][0::5] == p1["track_slot"][0::5],
          "pistes Sampler : identiques")
    check(H_NEW not in kept0, f"origine : la table de notre piste est chassée (restent {[hex(x) for x in kept0]})")
    check(H_NEW in kept1 and H_OLD not in kept1,
          f"retouché : la table reste, le fichier inutile part (restent {[hex(x) for x in kept1]})")
    check(h1 == H_NEW, f"retouché : après compactage, notre piste vise toujours sa table ({h1 and hex(h1)})")
    check(h0 != H_NEW, f"origine : après compactage, plus de table ({h0 and hex(h0)})")
    print("TOUT OK" if not FAIL else f"{len(FAIL)} ECHEC(S)")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
