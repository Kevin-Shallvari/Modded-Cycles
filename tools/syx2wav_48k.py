#!/usr/bin/env python3
"""syx2wav_48k.py — dérive un WAV 48 kHz à partir du WAV 96 kHz **déjà vérifié**.

Pourquoi ainsi plutôt qu'un nouveau rendu : le signal 96 kHz a passé l'auto-contrôle octet par
octet, donc il est bon. Le descendre à 48 kHz est une décimation : un filtre anti-repliement
puis un échantillon sur deux. C'est *le même* signal que celui qu'un rendu direct à 48 kHz
produirait (mêmes fronts, placés au sous-échantillon près) — mais ça prend des secondes au lieu
de vingt minutes.

Ce que ça coûte : la bande au-dessus de ~21 kHz. C'est là que vivent les fronts raides du MIDI,
donc la marge se resserre — c'est le compromis du 48 kHz, et il est inévitable.

    python3 tools/syx2wav_48k.py entree_96k.wav --out sortie_48k.wav
"""
import argparse
import pathlib
import sys
import wave

import numpy as np


def read_wav(path):
    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2:
            raise SystemExit("!! attendu 16 bits, trouvé %d" % (w.getsampwidth() * 8))
        n, fs = w.getnchannels(), w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64)
        data = data.reshape(-1, n)
        return data, fs


def lowpass(fc, fs, zc=16):
    half = int(np.ceil(zc * fs / (2 * fc)))
    k = np.arange(-half, half + 1) / fs
    h = np.sinc(2 * fc * k) * np.blackman(len(k))
    return h / h.sum()


def convolve(x, h):
    n = len(x) + len(h) - 1
    N = 1 << (n - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(h, N), N)
    o = (len(h) - 1) // 2
    return y[o:o + len(x)]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help="le WAV 96 kHz vérifié")
    ap.add_argument("--out", required=True, help="le WAV 48 kHz à écrire")
    ap.add_argument("--rate", type=int, default=48000)
    args = ap.parse_args()

    data, fs = read_wav(args.src)
    if fs % args.rate:
        raise SystemExit("!! %d Hz n'est pas un multiple de %d Hz" % (fs, args.rate))
    ratio = fs // args.rate

    # filtre anti-repliement à 0,45 de la fréquence d'arrivée, appliqué AVANT de sous-échantillonner
    h = lowpass(0.45 * args.rate, fs)
    half = (len(h) - 1) // 2
    out = np.empty((len(data) // ratio, data.shape[1]), dtype=np.int16)
    for ch in range(data.shape[1]):
        x = np.concatenate([np.zeros(half), data[:, ch], np.zeros(half)])
        y = convolve(x, h)[half:half + len(data)]
        y = y[:len(out) * ratio][::ratio]
        out[:, ch] = np.clip(np.round(y), -32768, 32767).astype(np.int16)

    with wave.open(args.out, "wb") as w:
        w.setnchannels(out.shape[1])
        w.setsampwidth(2)
        w.setframerate(args.rate)
        w.writeframes(out.tobytes())

    print("   %s" % args.src)
    print("   -> %s" % args.out)
    print("   %d Hz, 16 bits, %d canal(aux), %.1f min (%.1f Mo)"
          % (args.rate, out.shape[1], len(out) / args.rate / 60, out.nbytes / 1e6))
    print("   crête %.1f dBFS" % (20 * np.log10(max(np.max(np.abs(out)) / 32767.0, 1e-9))))


if __name__ == "__main__":
    main()
