#!/usr/bin/env python3
"""wav_pad.py — ajoute du SILENCE devant et derrière un WAV de récupération.

Pourquoi
--------
Le WAV produit par `syx2wav.py` commence **à l'échantillon 0** : le premier octet de l'image
part tout de suite. Or un lecteur audio met un temps variable à démarrer sa sortie (ouverture du
flux, amorçage du DAC), et la machine peut n'être en mode réception qu'une seconde ou deux après
qu'on a appuyé sur lecture. Tout ce qui est « mangé » au début est mangé dans **l'image
elle-même** : à ~1 750 octets/s, dix secondes perdues, c'est ~17 Ko de firmware manquants —
dont le préambule — et la somme de contenu échoue à la fin (« upgrade not successful »).

Avec un silence de tête, ces secondes perdues ne coûtent rien : elles tombent dans le vide, et
l'image commence quand tout le monde est prêt.

    python3 tools/wav_pad.py entree.wav --out sortie.wav --lead 30 --tail 5

Le signal n'est pas retouché : seuls des zéros sont ajoutés, avant et après. Le fichier reste
exactement le même signal, décalé.
"""
import argparse
import pathlib
import wave

import numpy as np


def read_wav(path):
    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2:
            raise SystemExit("!! attendu 16 bits, trouvé %d" % (w.getsampwidth() * 8))
        n, fs = w.getnchannels(), w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
        return data.reshape(-1, n), fs


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help="le WAV à encadrer")
    ap.add_argument("--out", required=True, help="le WAV à écrire")
    ap.add_argument("--lead", type=float, default=30.0, help="silence de tête, en secondes")
    ap.add_argument("--tail", type=float, default=5.0, help="silence de queue, en secondes")
    args = ap.parse_args()

    data, fs = read_wav(args.src)
    ch = data.shape[1]
    lead = int(round(args.lead * fs))
    tail = int(round(args.tail * fs))
    out = np.zeros((lead + len(data) + tail, ch), dtype="<i2")
    out[lead:lead + len(data)] = data

    with wave.open(args.out, "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(fs)
        w.writeframes(out.tobytes())

    # où commence et finit le signal, pour vérifier que le silence est bien là
    a = np.abs(out[:, 0].astype(np.float32))
    thr = 0.05 * (a.max() or 1.0)
    nz = np.nonzero(a > thr)[0]
    first, last = (nz[0] / fs, nz[-1] / fs) if len(nz) else (0.0, 0.0)

    print("   %s" % args.src)
    print("   -> %s" % args.out)
    print("   %d Hz, 16 bits, %d canal(aux)" % (fs, ch))
    print("   signal de %.2f s à %.2f s  (silence de tete %.1f s, de queue %.1f s)"
          % (first, last, args.lead, args.tail))
    print("   duree totale %.1f min (%.1f Mo)" % (len(out) / fs / 60, out.nbytes / 1e6))
    print("   crete %.1f dBFS" % (20 * np.log10(max(a.max() / 32767.0, 1e-9))))


if __name__ == "__main__":
    main()
