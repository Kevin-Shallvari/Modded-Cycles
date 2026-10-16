#!/usr/bin/env python3
"""Emballe le MAIN OS de **Model:Groove** dans le conteneur du Model:Samples (notes/55, notes/56).

La ligne Groove se construit à partir du `.syx` officiel du **Model:Cycles** : produit `0x11`,
signature avec la **clé Cycles**. Sur une machine dont le **bootstrap est celui du Samples**, le
STARTUP MENU n'accepte qu'un conteneur **`0x0F`** signé avec la **clé Samples** — et c'est la
seule voie quand la machine est bloquée, puisque le STARTUP MENU écoute sur le **MIDI IN**, pas
sur l'USB.

Le script prend le `.syx` Groove **déjà construit**, en extrait la section 3 (son flux aPLib est
repris **tel quel**, rien n'est recompressé) et la remet dans le conteneur du Samples officiel :

- amorçage, updater et méta restent ceux du Samples ;
- la clé de signature est celle du Samples ;
- le fichier produit est **relu entièrement** : checksums de chaque paquet, sections 2/4/5
  identiques à celles du Samples, section 3 décompressée identique, HMAC avec la clé Samples.

    python3 tools/groove_pack.py --built model-cycles_OS1.13_groove.syx \\
        --samples model-samples_OS1.13.syx --expect-mainos 1e15286a... \\
        -o model-groove_OS1.13_for-model-samples.syx

Le `.syx` d'entrée est celui de `tools/build.py --tweaks groove-8tracks,groove-patterns,groove-convert` ;
`--expect-mainos` vérifie qu'on n'emballe pas autre chose que le build attendu.
"""
import argparse
import hashlib
import hmac
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import crossflash as X                                    # noqa: E402
from mtlib import aplib, container                        # noqa: E402
from mtlib.syx import unwrap, wrap, BYTES_PER_MSG         # noqa: E402


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--built", required=True, help="le .syx Groove construit (produit 0x11)")
    ap.add_argument("--samples", required=True, help="model-samples_OS1.13.syx officiel (hôte)")
    ap.add_argument("--expect-mainos", help="SHA-256 attendu du MAIN OS du .syx d'entrée")
    ap.add_argument("-o", "--output", help="fichier de sortie")
    args = ap.parse_args()

    smp = X.load(args.samples, "samples")                 # vérifie hôte + MAIN OS officiels
    s_info, s_c, s_stored, s_plain = smp
    s_key = X.host_key(smp)

    raw = pathlib.Path(args.built).read_bytes()
    stream, info = unwrap(raw)                            # vérifie chaque checksum de paquet
    if info["product"] != 0x11:
        raise SystemExit("!! %s : produit 0x%02x, attendu 0x11 (le conteneur Cycles)"
                         % (args.built, info["product"]))
    c = container.parse(stream)
    s3 = next((s for s in c["sections"] if s["id"] == 3), None)
    if s3 is None:
        raise SystemExit("!! %s : pas de section 3" % args.built)
    my_stored = c["blob"][s3["off"]:s3["off"] + s3["size"]]
    my_plain = aplib.depack(my_stored)[0]
    if args.expect_mainos and sha(my_plain) != args.expect_mainos.lower():
        raise SystemExit("!! MAIN OS %s, attendu %s" % (sha(my_plain), args.expect_mainos))
    print("Groove : MAIN OS %s... (%d octets stockes)" % (sha(my_plain)[:16], len(my_stored)))

    blob = container.rebuild(s_c, {3: my_stored}, s_key)
    out = wrap(container.build_stream(blob, BYTES_PER_MSG), s_info["product"], s_info["start_seq"])

    # --- relecture complète du résultat, comme crossflash.cross -------------------------
    stream, info = unwrap(out)
    if info["product"] != s_info["product"]:
        raise SystemExit("!! relecture : produit 0x%02x" % info["product"])
    c2 = container.parse(stream)
    got = {s["id"]: c2["blob"][s["off"]:s["off"] + s["size"]] for s in c2["sections"]}
    for sid in s_stored:
        want = my_stored if sid == 3 else s_stored[sid]
        if got.get(sid) != want:
            raise SystemExit("!! relecture : section %s differente de l'attendu" % sid)
    if aplib.depack(got[3])[0] != my_plain:
        raise SystemExit("!! relecture : le MAIN OS decompresse differe")
    body, dig = c2["blob"][:-container.DIGEST_LEN], c2["blob"][-container.DIGEST_LEN:]
    if hmac.new(s_key, body, hashlib.sha256).digest() != dig:
        raise SystemExit("!! relecture : HMAC invalide avec la cle Samples")

    name = args.output or pathlib.Path(args.built).with_name(
        "model-groove_OS1.13_for-model-samples.syx")
    pathlib.Path(name).write_bytes(out)
    print("écrit : %s (%d o, SHA-256 %s...)" % (name, len(out), sha(out)[:16]))
    print("  produit 0x%02x, amorcage/updater/meta du Samples, section 3 = celle de %s"
          % (info["product"], pathlib.Path(args.built).name))
    print("  relu et vérifié : paquets, sections 2/4/5, section 3 décompressée, HMAC Samples")


if __name__ == "__main__":
    main()
