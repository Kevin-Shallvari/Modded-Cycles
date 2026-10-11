#!/usr/bin/env python3
"""Convertit une table d'ondes utilisateur en table « pré-travaillée » pour la machine Wave (notes/52).

Entrée : un WAV mono (une suite de trames de 2048 points). Sortie : un WAV 48 kHz mono 16 bits dont le
PCM contient, dans un ordre fixe, la table (copies pleines) puis les copies adoucies par octave plus
courtes. La machine lit ce fichier sans rien calculer : elle déduit la longueur de chaque copie d'une règle
fixe (voir la disposition ci-dessous). Plus de calcul de copies sur la machine.

Disposition (compacte, en points, dans l'ordre du fichier) :
    [ table : F trames de 2048 ]  puis  [ copies c ou lg[c] < 11, dans l'ordre de c : F trames de 2^lg[c] ]
La machine trouve F par  F = total_points / S,  S = 2048 + somme des 2^lg[c] < 2048.

    python3 tools/wt_convert.py --in table.wav --out table_wt.wav
"""
import argparse
import math
import pathlib
import struct

import numpy as np

N = 2048                      # points par trame (lgn = 11)
LGN = 11
NCOPY = 11                    # copies, une par octave
FOLD_OK = 28000.0             # repli toléré au-dessus de 20 kHz
OVER = 4                      # points par harmonique visés pour une copie


def hmax(c):
    return max(1, int(1024 * 2 ** (-c)))


def lg_of(c):
    lg = 6
    while lg < LGN and (1 << lg) < OVER * hmax(c):
        lg += 1
    return lg


def layout():
    """(S, [(c, lg, offset_in_copies)]) : S = total points par trame ; copies de lg < LGN et leur offset."""
    s = N
    out = []
    for c in range(NCOPY):
        lg = lg_of(c)
        if lg < LGN:
            out.append((c, lg, s))
            s += 1 << lg
    return s, out


S_TOTAL, SHORT_COPIES = layout()


def read_wav(path):
    """Mono : premiere piste ; accepte 16/24/32 bits entiers et float32."""
    d = pathlib.Path(path).read_bytes()
    j, i = d.find(b"fmt "), d.find(b"data")
    if j < 0 or i < 0:
        raise SystemExit("!! pas un WAV")
    fmt, ch, rate, _, _, bits = struct.unpack("<HHIIHH", d[j + 8:j + 24])
    n = struct.unpack("<I", d[i + 4:i + 8])[0]
    raw = d[i + 8:i + 8 + n]
    if fmt == 3:
        x = np.frombuffer(raw, "<f4").astype(np.float64)
    elif bits == 16:
        x = np.frombuffer(raw, "<i2") / 32768.0
    elif bits == 24:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
        x = ((b[:, 0] | b[:, 1] << 8 | b[:, 2] << 16) << 8 >> 8) / 8388608.0
    elif bits == 32:
        x = np.frombuffer(raw, "<i4") / 2147483648.0
    else:
        raise SystemExit(f"!! profondeur {bits} bits non geree")
    return x[::ch], rate, ch


def write_wav48(path, x):
    """WAV 48 kHz mono 16 bits, x en [-1, 1]."""
    b = np.clip(np.round(x * 32767), -32768, 32767).astype("<i2").tobytes()
    hdr = (b"RIFF" + struct.pack("<I", 36 + len(b)) + b"WAVEfmt "
           + struct.pack("<IHHIIHH", 16, 1, 1, 48000, 48000 * 2, 2, 16)
           + b"data" + struct.pack("<I", len(b)))
    pathlib.Path(path).write_bytes(hdr + b)


def bake(x):
    """Rend le tableau int16 de la table pre-travailee (meme disposition que le fichier)."""
    if len(x) < N:
        raise SystemExit(f"!! table trop courte : {len(x)} points (< {N})")
    frames = len(x) // N
    x = x[:frames * N].reshape(frames, N)
    # 16 bits propres, continu retire par trame, crete normalisee
    x = np.round(x * 32767) / 32767
    x = x - x.mean(axis=1, keepdims=True)
    peak = np.abs(x).max()
    if peak > 0:
        x = x / peak * 0.95
    spec = np.fft.rfft(x, axis=1)                      # harmoniques 0..1024
    raw = np.round(x * 32767).astype("<i2")
    parts = [raw.reshape(-1)]
    for c, lg, _off in SHORT_COPIES:
        s = spec.copy()
        s[:, hmax(c) + 1:] = 0
        y = np.fft.irfft(s, 1 << lg, axis=1) * ((1 << lg) / N)   # meme amplitude qu'a 2048 points
        parts.append(np.clip(np.round(y * 32767), -32768, 32767).astype("<i2").reshape(-1))
    return np.concatenate(parts)


def convert(x, out_path):
    """x : echantillons mono. Ecrit la table pre-travailee (48 kHz) et rend (trames, points)."""
    out = bake(x)
    write_wav48(out_path, out / 32767.0)
    return len(out) // S_TOTAL, len(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="src", required=True, help="WAV source (table d'ondes)")
    ap.add_argument("--out", dest="dst", required=True, help="WAV pre-travaillé (48 kHz)")
    a = ap.parse_args()
    x, rate, ch = read_wav(a.src)
    if ch != 1:
        print(f"  note : {ch} pistes, seule la premiere est gardee")
    if rate != 48000:
        print(f"  note : source {rate} Hz ; le fichier est etiquete 48 kHz (meme echantillons, comme le remede du 09/10)")
    if len(x) % N:
        print(f"  note : {len(x)} points, tronques a {len(x) // N * N} (multiple de {N})")
    frames, total = convert(x, a.dst)
    print(f"  {frames} trames ; {len(SHORT_COPIES)} copies courtes ; {total} points ; "
          f"x{total / (frames * N):.2f} la table ; ecrit {a.dst}")


if __name__ == "__main__":
    main()
