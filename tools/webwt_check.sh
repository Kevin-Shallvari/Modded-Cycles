#!/usr/bin/env bash
# Verifie que docs/convert/convert.js (le convertisseur du site) fait la meme table pre-travailee que la reference
# Python tools/wt_convert.py : meme disposition (longueur = trames x S_TOTAL) et memes echantillons a quelques LSB
# pres (deux FFT flottantes differentes). N'a besoin d'aucun fichier firmware.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v node >/dev/null || { echo "node est requis"; exit 1; }
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

python3 - "$tmp/table.wav" <<'PY'
import sys
import numpy as np
sys.path.insert(0, "tools")
import wt_convert as C
n = np.arange(C.N)
x = []
for f in range(64):
    a = f / 63
    y = (1 - a) * np.sin(2 * np.pi * n / C.N) + a * (np.sin(2 * np.pi * 40 * n / C.N) + 0.5 * np.sin(2 * np.pi * 300 * n / C.N))
    x.append(y / np.abs(y).max() * 0.9)
C.write_wav48(sys.argv[1], np.concatenate(x))
PY

python3 - "$tmp/table.wav" "$tmp/py.raw" <<'PY'
import sys
import numpy as np
sys.path.insert(0, "tools")
import wt_convert as C
x, _, _ = C.read_wav(sys.argv[1])
d = C.bake(x)
d.astype("<i2").tofile(sys.argv[2])
print("  py :", len(d), "points,", len(d) // C.S_TOTAL, "frames")
PY

node tools/webwt_check.js "$tmp/table.wav" "$tmp/js.raw"

python3 - "$tmp/py.raw" "$tmp/js.raw" <<'PY'
import sys
import numpy as np
a = np.fromfile(sys.argv[1], "<i2").astype(int)
b = np.fromfile(sys.argv[2], "<i2").astype(int)
same = len(a) == len(b)
d = int(np.abs(a - b).max()) if same else -1
ok = same and d <= 8
print(("  ok  " if ok else "  FAIL") + f" JS == Python (len {len(a)}=={len(b)}, ecart max {d} LSB)")
sys.exit(0 if ok else 1)
PY
