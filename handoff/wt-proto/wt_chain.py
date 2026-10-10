#!/usr/bin/env python3
"""Prototype en flottant de la machine à tables d'ondes (notes/52) : copies par demi-octave, oscillateur, passe-bas
d'Acid (échelle ZDF 4 pôles, coude à 3 segments), amplitude simple. Écrit des WAV dans build/wt-proto/.

    .venv/bin/python build/wt-proto/wt_chain.py [table.wav]
"""
import pathlib
import struct
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
FS = 48000
N = 2048                      # points par trame
FOLD_OK = 28000.0             # repli au-dessus de 20 kHz : inaudible


def read_wav(path):
    d = pathlib.Path(path).read_bytes()
    j, i = d.find(b"fmt "), d.find(b"data")
    fmt, ch, _, _, _, bits = struct.unpack("<HHIIHH", d[j + 8:j + 24])
    n = struct.unpack("<I", d[i + 4:i + 8])[0]
    raw = d[i + 8:i + 8 + n]
    if fmt == 3:
        x = np.frombuffer(raw, "<f4").astype(np.float64)
    elif bits == 16:
        x = np.frombuffer(raw, "<i2") / 32768.0
    elif bits == 24:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
        x = ((b[:, 0] | b[:, 1] << 8 | b[:, 2] << 16) << 8 >> 8) / 8388608.0
    else:
        x = np.frombuffer(raw, "<i4") / 2147483648.0
    return x[::ch]


def write_wav(path, x):
    x = np.clip(x / max(1e-9, np.abs(x).max()) * 0.89, -1, 1)
    b = (x * 32767).astype("<i2").tobytes()
    hdr = b"RIFF" + struct.pack("<I", 36 + len(b)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, FS, FS * 2, 2, 16)
    pathlib.Path(path).write_bytes(hdr + b"data" + struct.pack("<I", len(b)) + b)


class Table:
    """Trames 16 bits et leurs copies par demi-octave (préparées au chargement)."""

    def __init__(self, x):
        x = np.round(x * 32767) / 32767                     # 16 bits propres
        self.frames = x[:len(x) // N * N].reshape(-1, N)
        self.F = len(self.frames)
        spec = np.fft.rfft(self.frames, axis=1)             # harmoniques 0..1024
        self.f0 = FOLD_OK / (N // 2) / np.sqrt(2)           # copie 0 : toutes les harmoniques
        self.copies = []
        c = 0
        while True:
            top = self.f0 * 2 ** ((c + 1) / 2)              # note la plus haute servie par cette copie
            hmax = int(FOLD_OK // top)
            s = spec.copy()
            s[:, hmax + 1:] = 0
            self.copies.append(np.fft.irfft(s, N, axis=1))
            if hmax < 1:
                break
            c += 1

    def read(self, ph, pos, f, raw=False):
        """ph : phase [0,1) ; pos : position en trames ; f : fréquence (Hz), par échantillon."""
        i = ph * N
        i0 = np.floor(i).astype(int) % N
        i1 = (i0 + 1) % N
        fr = i - np.floor(i)
        pos = np.clip(pos, 0, self.F - 1)
        p0 = np.floor(pos).astype(int)
        p1 = np.minimum(p0 + 1, self.F - 1)
        pf = pos - p0

        def look(tab):
            a = tab[p0, i0] * (1 - fr) + tab[p0, i1] * fr
            b = tab[p1, i0] * (1 - fr) + tab[p1, i1] * fr
            return a * (1 - pf) + b * pf
        if raw:
            return look(self.frames)
        cpos = np.clip(2 * np.log2(np.maximum(f, 1e-3) / self.f0), 0, len(self.copies) - 2)
        c0 = np.floor(cpos).astype(int)
        cf = cpos - c0
        out = np.zeros_like(ph)
        for c in np.unique(c0):
            m = c0 == c
            sub = lambda tab: Table.read_sub(tab, i0[m], i1[m], fr[m], p0[m], p1[m], pf[m])
            out[m] = sub(self.copies[c]) * (1 - cf[m]) + sub(self.copies[c + 1]) * cf[m]
        return out

    @staticmethod
    def read_sub(tab, i0, i1, fr, p0, p1, pf):
        a = tab[p0, i0] * (1 - fr) + tab[p0, i1] * fr
        b = tab[p1, i0] * (1 - fr) + tab[p1, i1] * fr
        return a * (1 - pf) + b * pf


def acid_lp(x, cut_knob, res_knob):
    """Passe-bas d'Acid en flottant : 4 étages TPT, contre-réaction k f(y4) sans retard, f = coude à 3 segments.
    cut_knob, res_knob : 0..127 par échantillon (coupure 20 Hz -> 20 kHz)."""
    T1, T2, S = 0.12, 0.40, 0.35
    B2, B3 = T1 - S * T1, T1 + S * (T2 - T1)
    fc = 20.0 * 2 ** (np.asarray(cut_knob, float) / 127 * 10)
    g = np.tan(np.pi * np.minimum(fc, 0.45 * FS) / FS)
    G = g / (1 + g)
    k = 4.3 * np.asarray(res_knob, float) / 127
    s = np.zeros(4)
    y_out = np.empty_like(x)
    xg = 0.5 * x
    for n in range(len(x)):
        Gn, kn = G[n], k[n]
        G2, G4 = Gn * Gn, Gn ** 4
        Sm = (Gn ** 3 * (1 - Gn) * s[0] + G2 * (1 - Gn) * s[1] + Gn * (1 - Gn) * s[2] + (1 - Gn) * s[3])
        u_in = xg[n]
        y = (G4 * u_in + Sm) / (1 + kn * G4)
        if abs(y) < T1:
            fb = y
        else:
            sg = 1.0 if y > 0 else -1.0
            y = (G4 * u_in - kn * G4 * B2 * sg + Sm) / (1 + kn * S * G4)
            fb = S * y + B2 * sg if abs(y) < T2 else B3 * sg
        u = u_in - kn * fb
        v = u
        for j in range(4):
            w = Gn * (v - s[j])
            v = w + s[j]
            s[j] = v + w
        y_out[n] = v * (1 + kn / 2)
    return y_out


def env(n_samples, decay_knob, starts):
    """Enveloppe par note : 1 au trig, décroissance exponentielle (DECAY 0..127 : ~30 ms .. ~4 s)."""
    t60 = 0.03 * (4.0 / 0.03) ** (decay_knob / 127)
    e = np.zeros(n_samples)
    for a, b in zip(starts, list(starts[1:]) + [n_samples]):
        t = np.arange(b - a) / FS
        e[a:b] = np.exp(-6.9 * t / t60)
    return e


def voice(tab, notes, color, shape, sweep, contour, decay, raw=False, filt=True):
    """notes : [(début s, durée s, note MIDI)] ; potards : constantes ou tableaux par échantillon (0..127)."""
    total = int(max(a + d for a, d, _ in notes) * FS) + FS // 2
    f = np.zeros(total)
    starts = []
    for a, d, m in notes:
        i0, i1 = int(a * FS), int((a + d) * FS)
        f[i0:] = 440 * 2 ** ((m - 69) / 12) if np.isscalar(m) else 0
        starts.append(i0)
    for a, d, m in notes:                                    # glissandos : m = (note de départ, note d'arrivée)
        if not np.isscalar(m):
            i0, i1 = int(a * FS), int((a + d) * FS)
            f[i0:i1] = 440 * 2 ** ((np.linspace(m[0], m[1], i1 - i0) - 69) / 12)
            f[i1:] = f[i1 - 1]
    knob = lambda v: np.broadcast_to(np.asarray(v, float), (total,)) if np.ndim(v) == 0 else np.asarray(v, float)
    e = env(total, decay, starts)
    pos = (knob(color) / 127 + (knob(shape) - 64) / 63 * e) * (tab.F - 1)
    ph = np.cumsum(f / FS) % 1.0
    x = tab.read(ph, pos, f, raw=raw)
    if filt:
        x = acid_lp(x, knob(sweep), knob(contour))
    amp = env(total, decay, starts) if decay < 127 else np.ones(total)
    return x * amp


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else HERE / "table.wav"
    tab = Table(read_wav(src))
    print(f"table : {tab.F} trames de {N} ; {len(tab.copies)} copies par demi-octave")
    out = HERE / "chain"
    out.mkdir(exist_ok=True)
    # 1. glissando Do1 -> Do8, position au milieu, filtre ouvert : avec et sans copies
    g = [(0.0, 10.0, (24, 108))]
    for raw in (True, False):
        y = voice(tab, g, 64, 64, 127, 0, 127, raw=raw, filt=False)
        write_wav(out / f"1_glissando_{'brut' if raw else 'copies'}.wav", y)
    # 2. balayage de la position (COLOR de 0 à 127), une note tenue
    n = int(8.5 * FS)
    write_wav(out / "2_position.wav", voice(tab, [(0, 8, 45)], np.linspace(0, 127, n), 64, 127, 0, 127, filt=False))
    # 3. SHAPE : enveloppe -> position, notes courtes
    seq = [(i * 0.25, 0.25, m) for i, m in enumerate([36, 36, 48, 36, 39, 36, 43, 46] * 2)]
    write_wav(out / "3_shape_env.wav", voice(tab, seq, 10, 120, 127, 0, 60, filt=False))
    # 4. filtre d'Acid : coupure qui monte et descend, résonance haute, même suite
    n = int(4.5 * FS)
    cut = 40 + 60 * (0.5 - 0.5 * np.cos(np.linspace(0, 2 * np.pi, n)))
    write_wav(out / "4_filtre_reso.wav", voice(tab, seq, 30, 90, cut, 100, 60))
    # 5. mélodie aiguë (copies : pas de grain)
    mel = [(i * 0.2, 0.2, m) for i, m in enumerate([84, 88, 91, 96, 91, 88, 84, 79] * 2)]
    write_wav(out / "5_aigu.wav", voice(tab, mel, 40, 70, 127, 0, 50, filt=False))
    print("écrit :", ", ".join(sorted(p.name for p in out.iterdir())))


if __name__ == "__main__":
    main()
