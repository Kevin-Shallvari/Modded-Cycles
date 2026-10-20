#!/usr/bin/env python3
"""Proof of step record (notes/73, tweaks/model-cycles_OS1.13/45-step-rec.json).

The OS's own code runs in Unicorn on the MAIN OS of the OS (os.json, plus step-rec if it is not in it yet), payloads
at their run addresses, on a real project: the project's data block is set (0x4000ea3a, as at start-up), filled with
a new project (0x40061738: kits and 96 patterns at their defaults), then the project, interface state and lights
objects are built by their own constructors (0x400cf866, 0x400cf9a8, 0x400cfaf4). Intercepted only: operator
new/delete (a heap), the view controller (popups are logged), the views' own dispatch of messages (0x4007769e) and of
keys (0x40075f3c, the transport view's fallback), the views' lights (0x40076ca2), the post of a message to the
interface (0x40080bf6, captured and handed to the real handler 0x40007000), and the sequencer's start, stop and pause.

  1. Writes: stock bytes, hooks to their symbols; nothing else of the OS (image, payload code, relocations) points
     into the RAM window of the variables.
  2. Keys, through the real transport handler (0x4002439a): REC pressed once, PLAY, STOP as stock (grid record on,
     sequencer started, stopped); a double press on REC with the sequencer stopped starts step record: grid record
     off, popup "Step-rec:\\nON", step 1, the active track's length. Not with FUNC, nor while the sequencer plays.
  3. Notes, played by the real 0x4008171e / 0x4008145e (pads, TRIG keys and MIDI end there), their messages handed
     to the real 0x40007000: each note written on the current step of its track. The project's data afterwards =
     the one the OS's live record writer (0x40012158) makes for the same notes on the same steps. Notes held together
     on the same step, which moves on at the last release; PLAY skips, STOP goes back (not before step 1), PLAY with
     a note held does nothing.
  4. Knobs, through the real clamped setter 0x4000b274 -> 0x4000ba7a: a change made by the user becomes a p-lock
     on the next notes of its track, written as live record writes a knob's lock (0x4001646a), read back where the
     OS's writer puts it (0x4000dece); a change without the
     "record" flag does not. Leaving restores the words of the sounds and tells the sound (notification of k).
  5. End: after the last step, step record stops by itself; REC stops it; the sequencer starting, grid record or a
     pattern change stop it (the last without restoring the sound of another pattern).
  6. Lights, through the real frame 0x40006a4a: the active track's trigs on the current page, the current step and
     its page blinking at 3.75 Hz (the 30 Hz tick), REC lit, before the views.
  7. Outside step record: the note handler, the setter, the frame of the lights and the transport keys do exactly
     what they do without the mod (same data, same lights, same calls).

    python3 tools/emu/test_step_rec.py --cycles model-cycles_OS1.13.syx --syntakt Syntakt_OS1.42.syx
"""
import argparse
import contextlib
import io
import json
import pathlib
import struct
import sys

from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE, UC_HOOK_MEM_UNMAPPED
from unicorn import m68k_const as mk

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import build                          # noqa: E402
import test_sdvintage as T            # noqa: E402

ROOT = HERE.parent.parent
DEV = ROOT / "tweaks" / "model-cycles_OS1.13"
BASE = build.BASE
STOP, STACK, HEAP = 0x90000100, 0x90040000, 0x94000000
FAKE = 0x98000000                     # fake objects: app, view, VC, events, messages
APP, VIEW, EVT, MSG = FAKE, FAKE + 0x1000, FAKE + 0x2000, FAKE + 0x3000
VC = APP + 64
DATA, DATA_END = 0x406fa024, 0x40a70000      # the project's data block (0x40006cae)
TRANSPORT, NOTE_MSG, NOTE_ON, NOTE_OFF = 0x4002439a, 0x40007000, 0x4008171e, 0x4008145e
SETTER, ACCESSOR, ID2K, GET = 0x4000b274, 0x400097f0, 0x4005a4e8, 0x4000ae20
LIVE_WRITE, LOCK_WRITE = 0x40012158, 0x4001646a
FRAME, LEDS_OF = 0x40006a4a, 0x400cfaf4
SEQ_RUN = 0x40a78874
REC, PLAY, STOPK = 9, 10, 11
PRESS, FUNC, DOUBLE = 1, 2, 4
FAIL = []


def check(ok, msg):
    print(("  ok    " if ok else "  FAIL  ") + msg, flush=True)
    if not ok:
        FAIL.append(msg)
    return ok


class Rig:
    def __init__(self, img, runtimes=()):
        uc = self.uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        uc.ctl_set_cpu_model(mk.UC_CPU_M68K_ANY)
        uc.reg_write(mk.UC_M68K_REG_SR, 0x2700)
        uc.mem_map(0x40000000, 0x08000000)            # image, BSS, RAM above it, payloads (0x46700000)
        uc.mem_write(BASE, img)
        for dest, data in runtimes:
            uc.mem_write(dest, data)
        uc.mem_map(0x4a000000, 0x08000000)            # the uncached alias (Model-TG's sample memory)
        uc.mem_map(0x80000000, 0x00020000)
        uc.mem_map(0x90000000, 0x0a000000)
        uc.mem_map(0xfc000000, 0x01000000)
        uc.mem_write(STOP, b"\x4e\x71\x4e\x71")
        self.heap, self.bad, self.hooks, self.log, self.msgs, self.trail = HEAP, [], {}, [], [], []
        uc.hook_add(UC_HOOK_MEM_UNMAPPED, lambda u, a, addr, s, v, d: self.bad.append(addr) or False)
        uc.hook_add(UC_HOOK_CODE, self._hook)
        self.hooks.update({
            0x400802e0: lambda a: self.alloc(a[0]), 0x400802ec: lambda a: 0,
            0x4007700e: lambda a: self.log.append(("push", a[0], self.popup)) or 1,
            0x4007769e: lambda a: 0,                  # no view takes the message
            0x40075f3c: lambda a: self.log.append(("view", self.u32(a[1] + 12))) or 0,
            0x40076ca2: lambda a: self.log.append(("views", a[0])) or 0,
            0x40080bf6: lambda a: self.msgs.append(bytes(self.uc.mem_read(a[0], 32))) or 0,
            0x400542dc: lambda a: self.log.append(("start",)) or 0,
            0x40055f14: lambda a: self.log.append(("stop",)) or 0,
            0x40056060: lambda a: self.log.append(("pause",)) or 0,
            0x40056004: lambda a: self.log.append(("stop2",)) or 0,
        })
        self.popup = None
        self.watch = {0x400747c0: self._popup}
        self.call(0x4000045c)                          # .data -> SRAM
        self.call(0x400e7ccc)                          # fonts (popups)
        self.call(0x400d018c)                          # static set-up of the lights' tables (0x404a8bdc, ...)
        self.w32(0x40a7887c, 0x406fa040)               # the playing pattern's buffer (set by the sequencer), and
        for i in range(24):                            # and the tracks' ones (0x422ff168 + 4 x (track + 5), + 0x2c)
            self.w32(0x422ff168 + 4 * i, 0x406fa040)
        self.call(0x4000ea3a, DATA)                    # the project's data block, as at start-up
        self.call(0x40061738, DATA)                    # a new project
        self.proj = self.call(0x400cf866)
        self.ui = self.call(0x400cf9a8)
        self.leds = self.call(LEDS_OF)
        self.w32(VIEW + 44, VC)

    def _popup(self, a):
        self.popup = self.cstr(self.u32(a[1]))

    def alloc(self, n):
        a, self.heap = self.heap, self.heap + ((n + 15) & ~15)
        self.uc.mem_write(a, bytes(n))
        return a

    def u32(self, a):
        return struct.unpack(">I", self.uc.mem_read(a, 4))[0]

    def s16(self, a):
        return struct.unpack(">h", self.uc.mem_read(a, 2))[0]

    def w32(self, a, v):
        self.uc.mem_write(a, struct.pack(">I", v & 0xffffffff))

    def cstr(self, a):
        return bytes(self.uc.mem_read(a, 40)).split(b"\0")[0].decode(errors="replace")

    def _hook(self, uc, addr, size, ud):
        self.trail.append(addr)
        if len(self.trail) > 64:
            del self.trail[:32]
        if addr in self.watch:
            sp = uc.reg_read(mk.UC_M68K_REG_A7)
            self.watch[addr](struct.unpack(">6I", uc.mem_read(sp + 4, 24)))
        if addr in self.hooks:
            sp = uc.reg_read(mk.UC_M68K_REG_A7)
            ret = self.hooks[addr](struct.unpack(">8I", uc.mem_read(sp + 4, 32)))
            uc.reg_write(mk.UC_M68K_REG_D0, (ret or 0) & 0xffffffff)
            uc.reg_write(mk.UC_M68K_REG_PC, self.u32(sp))
            uc.reg_write(mk.UC_M68K_REG_A7, sp + 4)

    def call(self, fn, *args, count=100_000_000):
        sp = STACK - 0x800
        self.uc.mem_write(sp, struct.pack(">I" + "I" * len(args), STOP, *[a & 0xffffffff for a in args]))
        self.uc.reg_write(mk.UC_M68K_REG_A7, sp)
        try:
            self.uc.emu_start(fn, STOP, count=count)
        except Exception:
            print("  !! in", hex(fn), "after", [hex(a) for a in self.trail[-14:]], "bad", [hex(a) for a in self.bad[-3:]])
            raise
        if self.uc.reg_read(mk.UC_M68K_REG_A7) != sp + 4:
            FAIL.append(f"stack not balanced after {fn:#x}")
        return self.uc.reg_read(mk.UC_M68K_REG_D0)

    # --- the OS's objects ---
    def track(self, t):
        return self.call(0x4000cfcc, self.call(0x4000f208, self.proj), t)

    def acc(self, t):
        return self.call(ACCESSOR, self.proj + 116, t)

    def data(self):
        return bytes(self.uc.mem_read(DATA, DATA_END - DATA))

    def grid(self):
        return self.call(0x4006b978, self.ui) & 0xff

    def lock(self, t, step, k):
        """The p-lock of word k on a step (0xffff: none), where the OS's writer puts it (0x4000dece): the lock
        table's data + 2 x (4385 x track + 34 x step + k)."""
        trk = self.track(t)
        tbl = self.u32(trk + 44)
        base = self.call(self.u32(self.u32(tbl) + 40), tbl)
        return struct.unpack(">H", self.uc.mem_read(base + 2 * (4385 * self.u32(trk + 56) + 34 * step + k), 2))[0]

    # --- what the user does ---
    def key(self, code, flags=PRESS):
        self.uc.mem_write(EVT, bytes(32))
        self.w32(EVT + 12, code)
        self.w32(EVT + 16, flags)
        return self.call(TRANSPORT, VIEW, EVT) & 0xff

    def deliver(self):
        """The messages posted to the interface, to its real handler."""
        out = []
        for m in self.msgs:
            self.uc.mem_write(MSG, bytes(12) + m)
            out.append(self.call(NOTE_MSG, APP, MSG) & 0xff)
        self.msgs.clear()
        return out

    def note(self, t, n, vel=100):
        self.call(NOTE_ON, t, n, vel, 0x40, 0, 0xffffffff, 0xffffffff)
        return self.deliver()

    def release(self, t, n):
        self.call(NOTE_OFF, t, n, 0x40)
        return self.deliver()

    def knob(self, t, pid, value, record=1):
        return self.call(SETTER, self.acc(t), pid, value, t, record, 1)

    def frame(self):
        self.uc.mem_write(VC + 33, b"\x01")
        self.log.clear()
        self.call(FRAME, APP)
        return [self.u32(self.leds + 40 + 4 * led) for led in range(54)]


def os_tweaks(extra):
    by_id = {}
    for f in DEV.glob("[0-9]*.json"):
        t = json.loads(f.read_text(encoding="utf-8"))
        by_id[t["id"]] = t
    ids = json.loads((ROOT / "os.json").read_text(encoding="utf-8"))["tweaks"]
    ids = [i for i in ids if i not in extra] + list(extra)
    return by_id, sorted((by_id[i] for i in ids), key=lambda t: t["order"])


def build_img(stock, tweaks, syntakt):
    import syntakt as S                                   # tools/emu/syntakt.py
    with contextlib.redirect_stdout(io.StringIO()):
        p, _ = build.apply_writes(stock, tweaks)
        pl, _ = build.build_payload(tweaks, stock, syntakt)
    rts, st = [], S.dsp_image(syntakt)
    for t in tweaks:
        ap = t.get("append")
        if ap and ap["dest"] != ap["at"]:
            rts.append((int(ap["dest"], 16), build.payload_runtime(t, stock, st)))
    return bytes(p), bytes(p) + pl, rts


def writes_tests(stock, img, rts, sr):
    print("1. writes")
    s = {k: int(v, 16) for k, v in sr["symbols"].items()}
    import gen_step_rec as G                              # noqa: E402
    hooks = {va: (bytes.fromhex(old), sym, op) for va, old, sym, op, _ in G.HOOKS}
    ok = all(img[va - BASE:va - BASE + 6] == struct.pack(">HI", op, s[sym]) and
             stock[va - BASE:va - BASE + 6] == old for va, (old, sym, op) in hooks.items())
    check(ok, f"{len(hooks)} hooks: stock bytes before, jmp/jsr to their symbols after "
              "(transport keys, note played, note released, setter, lights, tick)")
    lo, hi = G.RAM
    own = [(w["off"], w["off"] + len(w["new"]) // 2) for w in sr["writes"]]
    refs = []
    for name, blob, base in [("image", img, BASE)] + [(f"payload {d:#x}", r, d) for d, r in rts]:
        for i in range(0, len(blob) - 3, 2):
            v = struct.unpack_from(">I", blob, i)[0]
            if lo - 0x100 <= v < hi + 0x100 or 0x4a33e700 <= v < 0x4a33ea00:
                a = base + i
                if not (name == "image" and any(o <= a - BASE < e for o, e in own)):
                    refs.append(f"{name} {a:#x}")
    check(not refs, f"nothing but step record points into its RAM window {lo:#x}..{hi:#x} (or its uncached alias)"
                    + (f": {refs[:6]}" if refs else ""))
    check(s["sr_active"] < lo or s["sr_active"] >= hi, f"sr_active ({s['sr_active']:#x}) in the image: 0 at start-up")
    at = s["sr_set"] - BASE
    check(img[at:at + 2] == bytes.fromhex("2040") and bytes.fromhex("31842a14") in img[at:at + 64],
          "sr_set replays the two instructions it replaces (movea.l d0,a0 ; move.w d4,20(a0,d2.l*2))")


def keys_tests(img, base_img, rts, s):
    print("2. keys (the real transport handler 0x4002439a)")
    r, b = Rig(img, rts), Rig(base_img, rts)
    act = lambda: r.uc.mem_read(s["sr_active"], 1)[0]           # noqa: E731
    same = True
    for rig in (r, b):
        rig.log.clear()
        rig.got = [rig.key(REC), rig.grid(), rig.key(REC, PRESS | 0x10), rig.key(PLAY), list(rig.log)]
    same = r.got == b.got and act() == 0 and r.got[1] == 1 and ("start",) in r.got[4]
    check(same, f"stopped, REC once: grid record on, as stock; PLAY starts the sequencer, as stock ({r.got[:4]})")
    r, b = Rig(img, rts), Rig(base_img, rts)
    r.w32(SEQ_RUN, 1)
    r.key(REC)
    r.key(REC, PRESS | DOUBLE)
    check(act() == 0, "playing, REC pressed twice: no step record (stock: grid record on, then off)")
    r = Rig(img, rts)
    r.key(REC)
    r.key(REC, PRESS | DOUBLE | FUNC)
    check(act() == 0, "FUNC + REC pressed twice: no step record")
    r = Rig(img, rts)
    r.log.clear()
    first = r.key(REC)
    grid1 = r.grid()
    took = r.key(REC, PRESS | DOUBLE)
    st = (act(), r.grid(), r.uc.mem_read(s["cur"], 1)[0], r.uc.mem_read(s["len"], 1)[0], r.u32(s["vc"]))
    pushes = [x for x in r.log if x[0] == "push"]
    check(first == 1 and grid1 == 1 and took == 1 and st == (1, 0, 0, 16, VC) and
          pushes == [("push", VC, "Step-rec:\nON")] and not r.bad,
          f"stopped, REC pressed twice: step record, grid record off, step 1 of 16, popup {pushes[-1][2]!r} "
          "on the view controller")
    return r


def notes_tests(img, base_img, rts, s):
    print("3. notes (the real 0x4008171e / 0x4008145e, their messages to the real 0x40007000)")
    r, ref = Rig(img, rts), Rig(base_img, rts)
    r.key(REC)
    r.key(REC, PRESS | DOUBLE)
    cur = lambda: r.uc.mem_read(s["cur"], 1)[0]                 # noqa: E731
    held = lambda: r.uc.mem_read(s["nheld"], 1)[0]              # noqa: E731
    pr = ref.proj

    def live(t, n, v, step):                                    # the OS's live record writer, on that step
        ref.call(LIVE_WRITE, pr, t, n, v, 0, step, 0, 0xffffffff, 0xffffffff)

    log = []
    a = r.note(0, 60, 100)
    log.append((cur(), held()))
    live(0, 60, 100, 0)
    r.release(0, 60)
    log.append((cur(), held()))
    r.note(0, 64, 90)
    r.note(2, 36, 127)
    live(0, 64, 90, 1)
    live(2, 36, 127, 1)
    log.append((cur(), held()))
    r.release(0, 64)
    log.append((cur(), held()))
    r.key(PLAY)
    log.append((cur(), held()))
    r.release(2, 36)
    log.append((cur(), held()))
    check(a == [1] and log == [(0, 1), (1, 0), (1, 2), (1, 1), (1, 1), (2, 0)],
          f"a note on step 1, step 2 at its release; two notes held (tracks 1 and 3) both on step 2, PLAY with a note "
          f"held ignored, step 3 at the last release (step, notes held: {log})")
    r.key(PLAY)
    r.key(PLAY)
    after_skip = cur()
    r.key(STOPK)
    back = cur()
    r.note(5, 72, 64)
    live(5, 72, 64, back)
    r.release(5, 72)
    for _ in range(6):
        r.key(STOPK)
    at0 = cur()
    check((after_skip, back, at0) == (4, 3, 0), f"PLAY skips (step {after_skip + 1}), STOP goes back (step "
                                                 f"{back + 1}), not before step 1 ({at0 + 1})")
    check(r.data() == ref.data(), "the project's data = what the OS's live record writer (0x40012158) makes for "
                                  "the same notes on the same steps: trigs, notes, velocities, nothing else")
    t0 = r.track(0)
    check(r.call(0x40015c20, t0, 0) & 0xff and r.call(0x40015c20, t0, 1) & 0xff and
          not r.call(0x40015c20, t0, 2) & 0xff and r.call(0x40015c20, r.track(2), 1) & 0xff,
          "trigs read back by the OS (0x40015c20): track 1 steps 1 and 2, track 3 step 2; skipped step 3 empty")
    check(not r.bad, "no access outside memory")


def knob_ids(r):
    """Parameter ids whose word is in the sound (k = 0..22), as the setter accepts them."""
    out = []
    for pid in range(0, 80):
        k = r.call(ID2K, pid)
        if 0 <= k <= 22 and k not in [x[1] for x in out]:
            out.append((pid, k))
    return out


def knobs_tests(img, base_img, rts, s):
    print("4. knobs (the real clamped setter 0x4000b274 -> 0x4000ba7a)")
    r, ref = Rig(img, rts), Rig(base_img, rts)
    ids = knob_ids(r)
    (p1, k1), (p2, k2), (p3, k3) = ids[2], ids[5], ids[8]

    def get(rig, t, p):
        v = rig.call(GET, rig.acc(t), p)
        return v - 0x100000000 if v & 0x80000000 else v

    old = [get(r, 0, p) for p in (p1, p2, p3)]
    r.key(REC)
    r.key(REC, PRESS | DOUBLE)
    turns = ((p1, (old[0] + 0x1300) % 0x7f00, 1), (p2, (old[1] + 0x2100) % 0x7f00, 1),
             (p3, (old[2] + 0x0700) % 0x7f00, 0))                  # the last: a change the OS does not record
    for rig in (r, ref):
        for p, v, rec in turns:
            rig.knob(0, p, v, record=rec)
    v1, v2, v3 = (get(ref, 0, p) for p in (p1, p2, p3))            # the values the setter kept (clamped)
    heard = [get(r, 0, p) for p in (p1, p2, p3)]
    r.note(0, 60, 100)
    r.release(0, 60)
    r.note(0, 62, 100)
    r.release(0, 62)
    r.knob(0, p1, old[0])                                        # turned back to where it was: no lock any more
    r.note(0, 63, 100)
    r.release(0, 63)
    r.note(1, 48, 100)                                           # another track: none of track 1's locks
    r.release(1, 48)
    pr = ref.proj
    for step, n, locks in ((0, 60, ((k1, v1), (k2, v2))), (1, 62, ((k1, v1), (k2, v2))), (2, 63, ((k2, v2),))):
        ref.call(LIVE_WRITE, pr, 0, n, 100, 0, step, 0, 0xffffffff, 0xffffffff)
        for k, v in locks:
            ref.call(LOCK_WRITE, ref.track(0), step, k, v)
    ref.call(LIVE_WRITE, pr, 1, 48, 100, 0, 3, 0, 0xffffffff, 0xffffffff)
    for p, v in ((p1, old[0]), (p2, old[1])):                     # step record's exit: the sound as before
        ref.knob(0, p, v, record=0)
    check(heard == [v1, v2, v3] and v1 != old[0] and v2 != old[1],
          f"knobs turned: the sound changes as usual, it is heard ({', '.join(hex(x) for x in heard)})")
    want = {(0, k1): v1, (0, k2): v2, (1, k1): v1, (1, k2): v2, (2, k2): v2}
    got = {(st, k): r.lock(0, st, k) for st in range(4) for k in (k1, k2, k3)}
    other = [r.lock(1, 3, k) for k in (k1, k2, k3)]
    check(all(got[key] == want.get(key, 0xffff) for key in got) and other == [0xffff] * 3,
          f"p-locks in the OS's storage: k {k1} = {v1:#x}, k {k2} = {v2:#x} on steps 1-2, k {k2} only on step 3 "
          f"(k {k1} turned back), none for k {k3} (changed without the record flag), none on track 2")
    r.key(REC)
    restored = [get(r, 0, p) for p in (p1, p2, p3)]
    check(restored == [old[0], old[1], v3],
          f"REC: the words changed during step record back to {[hex(x) for x in old[:2]]}; the one changed without "
          "the record flag kept")
    dr, df = r.data(), ref.data()
    diff = [i for i in range(len(dr)) if dr[i] != df[i]]
    check(not diff, "the project's data = live record's notes, plus the locks as live record writes a "
                    "knob turned (0x4001646a), sounds restored: byte for byte"
                    + (f" ; differ at {[hex(DATA + i) for i in diff[:8]]} ({len(diff)} bytes): "
                       f"{[(hex(DATA + i), dr[i], df[i]) for i in diff]}" if diff else ""))
    check(not r.bad, "no access outside memory")


def end_tests(img, base_img, rts, s):
    print("5. end")
    r = Rig(img, rts)
    act = lambda: r.uc.mem_read(s["sr_active"], 1)[0]           # noqa: E731
    r.key(REC)
    r.key(REC, PRESS | DOUBLE)
    for i in range(15):
        r.key(PLAY)
    r.log.clear()
    r.note(3, 50, 80)
    on15 = (act(), r.uc.mem_read(s["cur"], 1)[0])
    r.release(3, 50)
    pushes = [x[2] for x in r.log if x[0] == "push"]
    check(on15 == (1, 15) and act() == 0 and pushes == ["Step-rec:\nOFF"] and
          r.call(0x40015c20, r.track(3), 15) & 0xff,
          "a note on step 16 of 16, then its release: step record ends by itself (popup 'Step-rec: OFF')")
    for name, setup, back in (("the sequencer starts", lambda: r.w32(SEQ_RUN, 1), True),
                              ("grid record on", lambda: r.call(0x4006b9f6, r.ui, 1), True),
                              ("another pattern", lambda: r.uc.mem_write(0x406fa040 + 30706, b"\x00\x00\x00\x05"),
                               False)):
        r = Rig(img, rts)
        acc = r.acc(4)
        pid, k = knob_ids(r)[3]
        before = r.call(GET, acc, pid)
        r.key(REC)
        r.key(REC, PRESS | DOUBLE)
        r.knob(4, pid, (before + 0x0d00) % 0x7f00)
        setup()
        r.call(s["sr_tick"])
        now = r.call(GET, r.acc(4), pid)
        check(r.uc.mem_read(s["sr_active"], 1)[0] == 0 and ((now == before) == back),
              f"{name}: step record stops at the next tick; sound {'restored' if back else 'left as it is (it is not this pattern any more)'}")
    r = Rig(img, rts)
    r.key(REC)
    r.key(REC, PRESS | DOUBLE)
    r.key(REC)
    check(r.uc.mem_read(s["sr_active"], 1)[0] == 0 and r.grid() == 0, "REC: step record stops, grid record stays off")


def lights_tests(img, base_img, rts, s):
    print("6. lights (the real frame 0x40006a4a)")
    r, b = Rig(img, rts), Rig(base_img, rts)
    ref = b.frame()
    out = r.frame()
    check(out == ref and ("views", VC) in r.log, "not in step record: the same lights as without the mod, views called")
    r.key(REC)
    r.key(REC, PRESS | DOUBLE)
    r.note(0, 60)
    r.release(0, 60)
    r.note(0, 61)
    r.release(0, 61)
    r.key(PLAY)                                                  # step 4: steps 1-2 hold trigs, 3 skipped
    steps = [r.call(0x4000608c, i) for i in range(16)]
    pages = [r.call(0x400060ac, i) for i in range(4)]
    seen = []
    for tick in range(9):
        led = r.frame()
        seen.append((tuple(led[x] for x in steps), tuple(led[x] for x in pages), led[28],
                     r.uc.mem_read(VC + 33, 1)[0]))
        for _ in range(4 if tick % 2 == 0 else 0):
            r.call(s["sr_tick"])
    on = seen[0]
    want_on = tuple([2, 2, 1, 2] + [1] * 12)
    check(on[0] == want_on and on[1] == (2, 1, 1, 1) and on[2] == 2 and ("views", VC) in r.log,
          f"step 4: steps 1, 2 lit (trigs), 3 off, 4 lit (blink on), page 1 lit, REC lit; then the views ({on[:3]})")
    blinks = [x[0][3] for x in seen[::2]]
    check(blinks == [2, 1, 2, 1, 2] and all(x[0][:3] == want_on[:3] for x in seen),
          f"every 4 ticks (30 Hz) the current step blinks (on/off {blinks}), the others stay as they are")
    check(not r.bad, "no access outside memory")


def outside_tests(img, base_img, rts, s):
    print("7. outside step record: as without the mod")
    r, b = Rig(img, rts), Rig(base_img, rts)
    for rig in (r, b):
        rig.got = []
        rig.got.append(rig.note(0, 60))
        rig.got.append(rig.release(0, 60))
        pid, k = knob_ids(rig)[4]
        rig.got.append(rig.knob(2, pid, 0x2300))
        rig.got.append(rig.call(GET, rig.acc(2), pid))
        rig.call(0x4006ba90, rig.ui, 1)                          # live record on, sequencer playing
        rig.w32(SEQ_RUN, 1)
        rig.got.append(rig.note(1, 50))
        rig.got.append(rig.release(1, 50))
        rig.got.append(rig.knob(1, pid, 0x1100))
        rig.w32(SEQ_RUN, 0)
        rig.call(0x4006ba90, rig.ui, 0)
        rig.got.append(rig.frame())
        rig.got.append(rig.data())
    check(r.got == b.got and r.u32(s["sr_active"]) >> 24 == 0,
          "notes (stopped, and in live record), knob changes, a frame of the lights: same results and same data as "
          "without the mod")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycles", required=True)
    ap.add_argument("--syntakt", required=True, help="Syntakt_OS1.42.syx (or 1.41), for the OS's Syntakt engines")
    args = ap.parse_args()
    stock = T.main_os_from_syx(args.cycles)
    by_id, tweaks = os_tweaks(["step-rec"])
    sr = by_id["step-rec"]
    without = [t for t in tweaks if t["id"] != "step-rec"]
    sec, img, rts = build_img(stock, tweaks, args.syntakt)
    _, base_img, _ = build_img(stock, without, args.syntakt)
    print(f"firmware: {', '.join(t['id'] for t in tweaks)}")
    s = {k: int(v, 16) for k, v in sr["symbols"].items()}
    writes_tests(stock, img, rts, sr)
    keys_tests(img, base_img, rts, s)
    notes_tests(img, base_img, rts, s)
    knobs_tests(img, base_img, rts, s)
    end_tests(img, base_img, rts, s)
    lights_tests(img, base_img, rts, s)
    outside_tests(img, base_img, rts, s)
    print("FAILED: " + "; ".join(FAIL) if FAIL else "all good")
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
