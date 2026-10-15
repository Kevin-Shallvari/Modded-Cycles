#!/usr/bin/env python3
"""syx2wav.py — un `.syx` Elektron -> un WAV dont la FORME D'ONDE **est** le signal MIDI.

Pourquoi cet outil existe
-------------------------
Le MIDI IN du Model:Cycles accepte le **type A et le type B** (son entrée est
bidirectionnelle, deux optocoupleurs H11L1 derrière le jack — notes/12 §1). Il n'a donc pas
besoin d'une interface MIDI : une **sortie casque** peut porter le signal, à condition de le
**synthétiser**. Un `.syx` n'est pas de l'audio, et un lecteur audio ne sait pas le « jouer » :
ce script fabrique un WAV qui **est** le signal électrique MIDI — 31 250 bauds, trames 8N1,
fronts à bande limitée, canaux gauche et droit en opposition de phase.

**Piste EXPÉRIMENTALE, jamais testée sur matériel** (notes/12 §3, option B). La partie signal
est validée par simulation ; l'inconnue est **électrique** : le niveau de la sortie casque face
au seuil de l'optocoupleur. Seul un essai tranche.

Ce que le script garantit
-------------------------
Il **se vérifie lui-même** : il décode le WAV qu'il vient d'écrire (seuil + UART, exactement
comme la simulation de la note) et le compare **octet par octet** au `.syx`. S'il ne se décode
pas, il ne l'écrit pas.

Ce qu'il faut faire ensuite
---------------------------
  * **96 kHz** (ou 48, ou 192 — voir `--rate`) ;
  * **aucune** amélioration audio, égaliseur, normalisation ni son système ;
  * volume **fixe** pendant tout l'envoi, et **Ne pas déranger** pendant ~7 minutes ;
  * le volume se règle avec le rapport donné à la fin : viser environ **2 fois** le seuil de la
    machine (notes/12 §3.8).

    python3 tools/syx2wav.py model-cycles_OS1.13.syx --out recovery.wav --rate 96000
    python3 tools/syx2wav.py mon.syx --out mon.wav --pace 1.4 --level -1
"""
import argparse
import pathlib
import sys
import wave

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

BAUD = 31250.0
BIT = 1.0 / BAUD                 # 32 µs
FINE = 3.072e6                   # la grille fine : 32 x 96 kHz
RATIOS = {192000: 16, 96000: 32, 48000: 64}
TAIL = 4 * BIT                   # queue après le dernier bit, pour le filtre
D_CHARGE = 16                    # bascule de polarité au-delà de cette charge cumulée (bits)


# --- le fichier -------------------------------------------------------------------------

def split_sysex(raw):
    """Découpe un .syx en messages F0..F7 (même découpage que tools/flash.py)."""
    out, i = [], 0
    while True:
        a = raw.find(b"\xf0", i)
        if a < 0:
            return out
        b = raw.find(b"\xf7", a)
        if b < 0:
            return out
        out.append(raw[a:b + 1])
        i = b + 1


def check_syx(raw, path):
    """Vérifie le conteneur avec mtlib, comme flash.py — mais sans mido."""
    sys.path.insert(0, str(HERE / "mtlib"))
    from mtlib import syx
    try:
        stream, info = syx.unwrap(raw)
    except Exception as e:
        raise SystemExit("!! %s ne se vérifie pas : %s" % (path, e))
    return info


# --- la trame MIDI ----------------------------------------------------------------------

def timeline(msg, pace, state):
    """Les instants et les niveaux des bits d'un message, sur la grille fine.

    État (polarité, charge) reporté d'un message à l'autre : la parade du §3.5 alterne la
    polarité des zéros pour ne pas charger les condensateurs de liaison de la sortie casque.
    """
    ts, lv = [], []
    t = 0.0
    pol, disp = state
    for byte in msg:
        frame = [0] + [(byte >> k) & 1 for k in range(8)] + [1]      # départ, 8 bits, stop
        want = -1 if disp > 0 else 1
        if want != pol and abs(disp) > D_CHARGE:
            pol, t = want, t + BIT                                   # bascule + 1 bit de repos
        for bit in frame:
            ts.append(t)
            lv.append(0.0 if bit else float(pol))
            t += BIT
        disp += pol * frame.count(0)
    # la cadence : au moins `pace` fois la durée théorique du message
    total = max(t, pace * len(msg) * 10 * BIT)
    return np.array(ts), np.array(lv), total, (pol, disp)


# --- le rendu ---------------------------------------------------------------------------

def lowpass(fc, rate, zc=12):
    half = int(np.ceil(zc * rate / (2 * fc)))
    k = np.arange(-half, half + 1) / rate
    h = np.sinc(2 * fc * k) * np.blackman(len(k))
    return h / h.sum()


def convolve(x, h):
    n = len(x) + len(h) - 1
    N = 1 << (n - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(h, N), N)
    o = (len(h) - 1) // 2
    return y[o:o + len(x)]


def render(ts, lv, total, fs, cutoff=0.45):
    """Grille fine -> filtre anti-repliement -> décimation à `fs`. Renvoie la tension
    pointe-bague (opposition de phase), normalisée à 1 pour un bit à 0.

    ATTENTION : c'est la version FILTRÉE, correcte mais lente (~20 min pour l'OS officiel :
    une convolution par message). Une version par échelons précalculés a été essayée le
    15/10 ; elle échouait l'auto-contrôle (mauvais alignement de décimation, à corriger) et
    n'a donc pas été gardée. Le contrôle a bien fait son travail : rien n'a été écrit."""
    ratio = RATIOS[fs]
    tg = np.arange(int((total + TAIL) * FINE)) / FINE
    idx = np.clip(np.searchsorted(ts, tg, side="right") - 1, 0, len(ts) - 1)
    x = np.where((tg >= ts[0]) & (tg < ts[-1] + BIT), lv[idx], 0.0)
    y = convolve(x, lowpass(cutoff * fs, FINE))
    return y[::ratio]


# --- le décodeur (le contrôle) ----------------------------------------------------------

def uart_decode(space, rate, phase=0.3):
    """Décode |v| > seuil en octets, UART 16x avec vote majoritaire au centre du bit.
    Renvoie (octets, erreurs de trame). Même principe que la simulation de la note."""
    tick = 1.0 / (16 * BAUD)
    k = ((phase + np.arange(int(len(space) / (tick * rate)) - 1)) * tick * rate).astype(np.int64)
    s = space[np.minimum(k, len(space) - 1)]
    maj = np.zeros(len(s), bool)
    maj[1:-1] = (s[:-2].astype(int) + s[1:-1] + s[2:]) >= 2
    out, bad, nxt = [], 0, 0
    for i in np.flatnonzero(s[1:] & ~s[:-1]) + 1:
        if i < nxt or i >= len(s) - 180:
            continue
        b = maj[i + 8 + 16 * np.arange(10)]
        if not b[0]:
            continue                       # faux départ
        out.append(sum(1 << j for j in range(8) if not b[1 + j]))
        bad += int(b[9])
        nxt = i + 152
    return bytes(out), bad


def margin(space, rate, ref):
    """Erreur d'horloge tolérée (%), en plus et en moins. Un signal parfait donne ±4,25 %."""
    best = []
    for sign in (1, -1):
        ok = 0.0
        for e in np.arange(0, 8.01, 0.25):
            tick = 1.0 / (16 * BAUD * (1 + sign * e / 100))
            if any(uart_decode_at(space, rate, tick, ph) != (ref, 0)
                   for ph in (0.1, 0.5, 0.9)):
                break
            ok = e
        best.append(ok)
    return min(best)


def uart_decode_at(space, rate, tick, phase):
    k = ((phase + np.arange(int(len(space) / (tick * rate)) - 1)) * tick * rate).astype(np.int64)
    s = space[np.minimum(k, len(space) - 1)]
    maj = np.zeros(len(s), bool)
    maj[1:-1] = (s[:-2].astype(int) + s[1:-1] + s[2:]) >= 2
    out, bad, nxt = [], 0, 0
    for i in np.flatnonzero(s[1:] & ~s[:-1]) + 1:
        if i < nxt or i >= len(s) - 180:
            continue
        b = maj[i + 8 + 16 * np.arange(10)]
        if not b[0]:
            continue
        out.append(sum(1 << j for j in range(8) if not b[1 + j]))
        bad += int(b[9])
        nxt = i + 152
    return bytes(out), bad


# --- principal --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("syx", help="le .syx à envoyer (l'officiel, ou un firmware construit)")
    ap.add_argument("--out", required=True, help="le WAV à écrire")
    ap.add_argument("--rate", type=int, default=96000, choices=sorted(RATIOS),
                    help="fréquence d'échantillonnage (défaut 96000 ; 96000 recommandé)")
    ap.add_argument("--pace", type=float, default=1.4,
                    help="marge de cadence, comme tools/flash.py (défaut 1.4 ; monter à 2.0 si la machine se fige)")
    ap.add_argument("--level", type=float, default=-1.0,
                    help="crête en dBFS (défaut -1 ; ne pas dépasser 0)")
    ap.add_argument("--no-check", action="store_true",
                    help="ne pas décoder le WAV pour se vérifier (déconseillé)")
    args = ap.parse_args()

    raw = pathlib.Path(args.syx).read_bytes()
    info = check_syx(raw, args.syx)
    msgs = split_sysex(raw)
    if not msgs:
        raise SystemExit("!! aucun message SysEx dans %s" % args.syx)

    fs = args.rate
    ratio = RATIOS[fs]
    peak = 10 ** (args.level / 20.0)
    state = (1, 0)
    chunks, decoded, errors, total_bits = [], [], 0, 0

    for n, m in enumerate(msgs):
        ts, lv, total, state = timeline(m, args.pace, state)
        v = render(ts, lv, total, fs)
        # mise à l'échelle : la crête demandée (float32 : ~160 Mo pour 7 minutes, pas le double)
        mx = float(np.max(np.abs(v))) or 1.0
        v = (v * (peak / mx)).astype(np.float32)
        if not args.no_check:
            for th in (0.35, 0.5, 0.65):
                got, bad = uart_decode(np.abs(v) > th * peak, fs)
                if got == bytes(m) and bad == 0:
                    break
            else:
                got, bad = uart_decode(np.abs(v) > 0.5 * peak, fs)
            decoded.append(got)
            errors += bad
        # la queue du message : le silence de la cadence
        gap = int(round((total - (ts[-1] + BIT)) * fs))
        chunks.append(v)
        if gap > 0:
            chunks.append(np.zeros(gap, dtype=v.dtype))
        total_bits += 10 * len(m)

    sig = np.concatenate(chunks)
    if not args.no_check:
        ref = b"".join(bytes(m) for m in msgs)
        got = b"".join(decoded)
        if got != ref or errors:
            bad_at = next((i for i in range(min(len(got), len(ref))) if got[i] != ref[i]),
                          min(len(got), len(ref)))
            raise SystemExit(
                "!! le WAV ne se décode pas : %d octet(s) sur %d, %d erreur(s) de trame, "
                "premier écart à %d.\n   Rien n'a été écrit — c'est le contrôle qui a parlé."
                % (len(got), len(ref), errors, bad_at))

    data = np.clip(np.stack([sig, -sig], axis=1) * 32767.0, -32768, 32767).astype("<i2")
    with wave.open(args.out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(fs)
        w.writeframes(data.tobytes())

    dur = len(sig) / fs
    print("%s : %d message(s), %d octet(s) de trame" % (pathlib.Path(args.syx).name,
                                                        len(msgs), total_bits // 10))
    print("   écrit        : %s" % args.out)
    print("   %d Hz, 16 bits, stéréo (opposition de phase), crête %.1f dBFS" % (fs, args.level))
    print("   durée        : %.1f min (%.1f Mo)" % (dur / 60, data.nbytes / 1e6))
    if not args.no_check:
        print("   auto-contrôle : le WAV se décode octet par octet (seuils 0,35 / 0,5 / 0,65)")
        # quelle plage de seuil tient ? On réutilise le premier message, déjà rendu.
        ts, lv, total, _ = timeline(msgs[0], args.pace, (1, 0))
        v1 = render(ts, lv, total, fs)
        mx1 = float(np.max(np.abs(v1))) or 1.0
        v1 = v1 * (peak / mx1)
        ref = bytes(msgs[0])
        good = []
        for th in np.arange(0.15, 0.81, 0.05):
            got, bad = uart_decode(np.abs(v1) > th * peak, fs)
            if got == ref and bad == 0:
                good.append(th)
        if good:
            print("   le premier message tient pour un seuil de %.2f à %.2f de la crête"
                  % (good[0], good[-1]))
            print("   -> règle le volume pour que le seuil de l'optocoupleur tombe dans cette")
            print("      plage : c'est le repère de calibrage (viser ~2x le seuil, notes/12 §3.8)")
    print("\nÀ FAIRE SUR LA MACHINE")
    print("   1. éteindre → maintenir [FUNC] → allumer → [TRIG 4]  (l'écran doit dire READY TO RECEIVE)")
    print("   2. câble jack stéréo 3,5 mm mâle-mâle : sortie casque → MIDI IN du Model:Cycles")
    print("      (l'entrée accepte les deux brochages : n'importe quel câble TRS convient ;")
    print("       pas un câble mono TS, pas un TRRS de téléphone)")
    print("   3. jouer ce WAV en entier, à volume FIXE, sans égaliseur ni son système")
    print("   4. l'écran doit passer à RECEIVING… puis UPDATING FLASH — ne rien couper")
    print("   Le volume se règle à l'oreille du signal : viser environ 2 fois le seuil (notes/12 §3.8).")


if __name__ == "__main__":
    main()
