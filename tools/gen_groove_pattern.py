#!/usr/bin/env python3
"""Génère tweaks/model-cycles_OS1.13/57-groove-patterns.json : le format de pattern à 8 pistes.

Projet dérivé **Model:Groove** (notes/55). **Jalon 2** (notes/56 §3.27 à §3.36), à appliquer
**après** `56-groove-8tracks.json` (jalon 1, le moteur audio). Construit en ligne de commande
seulement, jamais dans le flasher.

Ce que fait ce jalon — le format, la mémoire, et rien d'autre :

  1. **le format de pattern** : l'enregistrement déployé passe de 30 710 à **40 924** octets
     (`4 + 8×722 + 8×4385 + 64`) et le bloc rangé de 14 848 à **19 796** (`4 + 8×2474`). Les
     **pas par piste ne changent pas** (722, 4385, 1752 — §3.35) : seuls les compteurs bougent ;
  2. **les kits** : 7 094 → **7 294** octets (100 o par piste) et la borne 600 → **800** ;
  3. **le nombre de patterns** : 96 → **80**. La banque F est échangée contre les pistes 7-8
     (§3.27 : c'est le seul point de perte de données du mod, à traiter par la conversion) ;
  4. **la disposition** : l'image projet grandit de **60 768** octets (80 patterns à 8 pistes
     coûtent moins que 96 à 6), donc l'en-tête et la table des patterns se décalent d'autant, et
     **les kits déménagent** vers la plage libre de `0x43dd0000` (720 896 o sans aucun littéral
     jusqu'à `0x43e80000` — les littéraux de cette plage sont tous regroupés à sa toute fin).

Ce que ce jalon ne fait **pas** : la **conversion des projets existants** (le convertisseur
v6 → v7, §3.29.f) et l'**interface** (la page de pistes, §3.32). Sans la conversion, un projet
d'origine serait mal lu : ce jalon est un jalon de format, à prouver en émulation.

    python3 tools/gen_groove_pattern.py --cycles model-cycles_OS1.13.syx [--check]
"""
import argparse
import json
import pathlib
import struct
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "emu"))

import build                       # noqa: E402
import test_sdvintage as T         # noqa: E402
import capstone                    # noqa: E402

OUT = HERE.parent / "tweaks" / "model-cycles_OS1.13" / "57-groove-patterns.json"
BASE = build.BASE

# --- la disposition (§3.35.d) ---------------------------------------------
IMAGE_OLD = 2163716                 # 96 x 14848 + 96 x 7094 + 57284
IMAGE_NEW = 2224484                 # 80 x 19796 + 80 x 7294 + 57284
GROWTH = IMAGE_NEW - IMAGE_OLD      # 60768
HEADER_OLD = 0x406FA024
PATTERNS_OLD = 0x406FA040
HEADER_NEW = HEADER_OLD + GROWTH
PATTERNS_NEW = PATTERNS_OLD + GROWTH
KITS_NEW = 0x43DD0000
KITS_OLD_OFFSET = 2948188           # offset des kits, relatif a l'en-tête
KITS_NEW_OFFSET = KITS_NEW - HEADER_NEW

# --- immediats 32 bits : (avant, apres, sites attendus, role) -------------
IMMEDIATES = [
    (4332, 5776, 21, "taille des pas : 6 -> 8 pistes"),
    (4336, 5780, 1, "offset de la queue (immediat)"),
    (14848, 19796, 19, "bloc range d'un pattern"),
    (30710, 40924, 12, "enregistrement deploye"),
    (7094, 7294, 8, "enregistrement de kit"),
    (600, 800, 7, "borne des kits (6 -> 8 pistes)"),
    (2948160, 3273920, 2, "fin de la table des patterns (96 x 30710 -> 80 x 40924)"),
    (26310, 35080, 3, "borne de la queue deployee (6 x 4385 -> 8 x 4385) — §3.39.c"),
    (681024, 583520, 1, "fin de la table des kits (96 x 7094 -> 80 x 7294)"),
    (1425408, 1583680, 8, "fin des blocs ranges (96 x 14848 -> 80 x 19796)"),
    (IMAGE_OLD, IMAGE_NEW, 20, "taille de l'image projet"),
    (PATTERNS_OLD, PATTERNS_NEW, 6, "base de la table des patterns"),
    (HEADER_OLD, HEADER_NEW, 7, "en-tete de projet"),
    (KITS_OLD_OFFSET, KITS_NEW_OFFSET, 6, "offset des kits (relatif a l'en-tete)"),
]

# --- tailles et decalages en deplacement 16 bits -------------------------
# ATTENTION : le tri par « usage absolu » ne suffit pas — il depend de la VALEUR.
#   - `pea.l $3a00.w`     (absolu)  = une TAILLE a changer ;
#   - `pea.l $10f0(a3)`   (registre) = un DECALAGE dans l'enregistrement, a changer aussi ;
#   - `clr.l $258(a2)`    (registre) = une COINCIDENCE de 600, a LAISSER.
# Trois familles, donc, et chacune doit etre revue site par site (notes/56 §3.37) :
#   (valeur, apres, mode, sites attendus, role) avec mode = 'absolu' | 'registre' | 'tout'
DISPLACEMENTS = [
    # decalages dans l'enregistrement : usage par registre, a changer
    (4336, 5780, "registre", 7, "offset de la queue"),
    (30706, 40920, "registre", 4, "champ a la fin de l'enregistrement"),
    (30642, 40856, "registre", 3, "enregistrement - 68"),
    (14736, 19684, "registre", 8, "bloc range - 112"),
    # tailles absolues, a changer
    (7094, 7294, "tout", 8, "taille de kit (7 absolus + le pas de 0x4005d55a)"),
    (600, 800, "absolu", 6, "taille de kit (copie) — ses 13 sites a registre sont des champs"),
    (14848, 19796, "tout", 33, "bloc range (30 absolus + 4 vrais a registre)"),
]

# Sites ecartes APRES REVUE (§3.38) : la valeur apparait par coincidence dans la ZONE DE
# DONNEES de l'image (chaines, tables), jamais du code. Verifie un par un : les octets
# voisins sont des `.short` (donnee desassemblee comme du code).
EXCLUDE = {
    0x4011AB70: "7094 : donnee (move.b -$4925(a5),$1bb6(a5))",
    0x40139F70: "14848 : donnee (move.b (a5),$3a00(a0))",
    0x4013C276: "14848 : donnee (move.w d0,d5)",
    0x4019D936: "14848 : donnee (move.w d0,d5)",
    0x401A10F6: "14848 : donnee (cmpil #...,d0)",
    0x401A17DE: "14848 : donnee (move.l d7,$3a00(a7))",
    0x401A8C5E: "14848 : donnee (subl d4,fp@(14848))",
}

# --- la garde du nombre de patterns --------------------------------------
GUARD_VA = 0x400083BA               # moveq #95 -> moveq #79

# La revue des sites en mode registre a ete faite (§3.38) ; mais le BANC a trouve DEUX bornes
# oubliees (§3.39, §3.40) :
#   - 26310 = 6 x 4385 (la borne de piste du gestionnaire de queue) : AJOUTEE, le banc passe ;
#   - `moveb #5,%d5` (0x4005b820) : l'index de piste ENCODE dans les verrous ranges est valide
#     contre 5. Six sites `moveb #5,%dN` existent dans l'image, dont celui-ci ; les cinq autres
#     sont a revoir. Tant que ce n'est pas fait, l'outil REFUSE d'ecrire (sauf --draft) : aucun
#     firmware incomplet ne doit pouvoir etre construit.
REVIEW_PENDING = True
PENDING_VALUES = ["borne #5 de l'index de piste encode (6 sites moveb #5 a revoir)"]

_MD = None


def md():
    global _MD
    if _MD is None:
        _MD = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_M68K_040)
        _MD.big_endian = True
    return _MD


def ins_at(stock, va):
    """L'instruction qui couvre `va` (ou None)."""
    for back in (2, 4, 6, 8, 10):
        start = va - back
        if start < BASE:
            continue
        ins = list(md().disasm(bytes(stock[start - BASE:start - BASE + 24]), start))
        if not ins:
            continue
        i = ins[0]
        if i.address <= va < i.address + i.size:
            return i
    return None


def find_imm_sites(stock, value):
    """Sites d'un immediat 32 bits : l'operande contient la valeur."""
    pat = struct.pack(">I", value)
    needle = "%x" % value
    out, i = [], 0
    while True:
        i = stock.find(pat, i)
        if i < 0:
            break
        va = BASE + i
        if i % 2 == 0:
            ins = ins_at(stock, va)
            if ins is not None and needle in ins.op_str.lower().replace("$", "").replace(" ", ""):
                out.append(va)
        i += 1
    return out


def find_disp_sites(stock, value, mode):
    """Sites d'un deplacement 16 bits, selon le mode :
       'absolu'   -> l'operande n'a pas de registre (`$3a00.w`) : une taille ;
       'registre' -> l'operande a un registre (`$10f0(a3)`) : un decalage dans l'enregistrement ;
       'tout'     -> les deux.
    """
    pat = struct.pack(">H", value)
    out, i = [], 0
    while True:
        i = stock.find(pat, i)
        if i < 0:
            break
        va = BASE + i
        if i % 2 == 0:
            ins = ins_at(stock, va)
            if ins is not None and ("$%x" % value) in ins.op_str.lower():
                has_reg = "(" in ins.op_str
                if mode == "tout" or (mode == "absolu") == (not has_reg):
                    out.append(va)
        i += 1
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycles", required=True, help="model-cycles_OS1.13.syx officiel")
    ap.add_argument("--check", action="store_true", help="vérifie que le JSON versionné correspond")
    ap.add_argument("--draft", action="store_true",
                    help="écrit quand même le JSON, malgré la revue des sites en mode registre en attente")
    args = ap.parse_args()

    stock = T.main_os_from_syx(args.cycles)
    dev = json.loads((OUT.parent / "device.json").read_text(encoding="utf-8"))
    if build.sha(stock) != dev["section_sha256"]:
        raise SystemExit("!! ce n'est pas le MAIN OS 1.13 officiel")

    print("disposition : image %d -> %d (+%d)" % (IMAGE_OLD, IMAGE_NEW, GROWTH))
    print("              en-tete %#x -> %#x, patterns %#x -> %#x"
          % (HEADER_OLD, HEADER_NEW, PATTERNS_OLD, PATTERNS_NEW))
    print("              kits -> %#x (offset %d -> %d, relatif a l'en-tete)"
          % (KITS_NEW, KITS_OLD_OFFSET, KITS_NEW_OFFSET))

    writes, bad = [], []
    for old, new, expect, role in IMMEDIATES:
        sites = find_imm_sites(stock, old)
        if len(sites) != expect:
            bad.append("%s : %d site(s) au lieu de %d" % (role, len(sites), expect))
        for va in sites:
            writes.append((va, struct.pack(">I", old), struct.pack(">I", new), role))
        print("  immediat %-52s %2d site(s)" % (role, len(sites)))

    for old, new, mode, expect, role in DISPLACEMENTS:
        sites = [va for va in find_disp_sites(stock, old, mode) if va not in EXCLUDE]
        if len(sites) != expect:
            bad.append("%s (%s) : %d site(s) au lieu de %d" % (role, mode, len(sites), expect))
        for va in sites:
            writes.append((va, struct.pack(">H", old), struct.pack(">H", new), role))
        print("  taille   %-46s %-8s %2d site(s)" % (role, mode, len(sites)))

    # la garde du nombre de patterns : moveq #95 -> #79
    op = stock[GUARD_VA - BASE]
    if not (0x70 <= op <= 0x77) or stock[GUARD_VA - BASE + 1] != 95:
        raise SystemExit("!! la garde du nombre de patterns n'est pas en %#x" % GUARD_VA)
    writes.append((GUARD_VA, bytes([op, 95]), bytes([op, 79]),
                   "nombre de patterns : 96 -> 80"))

    if bad:
        for b in bad:
            print("  !! " + b)
        raise SystemExit("!! le nombre de sites ne correspond pas au triage (notes/56 §3.36)")

    seen, uniq = set(), []
    for va, old, new, role in sorted(writes, key=lambda w: w[0]):
        if va in seen:
            raise SystemExit("!! deux ecritures au meme endroit : %#x (%s)" % (va, role))
        seen.add(va)
        if old == new:
            continue
        if stock[va - BASE:va - BASE + len(old)] != old:
            raise SystemExit("!! octets d'origine inattendus en %#x (%s)" % (va, role))
        uniq.append({"off": va - BASE, "old": old.hex(), "new": new.hex()})

    print("total : %d ecriture(s)" % len(uniq))

    tweak = {
        "id": "groove-patterns",
        "order": 57,
        "name": "Format de pattern a huit pistes (Model:Groove)",
        "description": [
            "Model:Groove, jalon 2 : le format de pattern passe a huit pistes (enregistrement "
            "30 710 -> 40 924 octets deployes, 14 848 -> 19 796 ranges), les kits a 7 294 octets "
            "et le projet a 80 patterns au lieu de 96 (la banque F est echangee contre les pistes "
            "7-8, le seul point de perte de donnees du mod).",
            "S'applique APRES 56-groove-8tracks.json (jalon 1, le moteur audio). L'image projet "
            "grandit de 60 768 octets, donc l'en-tete et la table des patterns se decalent, et les "
            "kits demenagent vers la plage libre de 0x43dd0000.",
            "La conversion des projets existants (convertisseur v6 -> v7) et l'interface (page de "
            "pistes) sont des jalons suivants : sans la conversion, un projet d'origine serait mal "
            "lu. Construit en ligne de commande seulement, hors flasher. Genere par "
            "tools/gen_groove_pattern.py, notes/54-56.",
        ],
        "device": "Model:Cycles",
        "os": "1.13",
        "section": 3,
        "writes": uniq,
    }

    if REVIEW_PENDING and not args.draft:
        raise SystemExit(
            "!! revue en attente pour les sites en mode registre de %s (notes/56 §3.37) :\n"
            "   le tri absolu/registre est un premier filtre, pas une preuve.\n"
            "   Utiliser --draft pour ecrire malgre tout (fichier NON fiable)."
            % ", ".join(str(v) for v in PENDING_VALUES))

    build.apply_writes(stock, [tweak])
    text = json.dumps(tweak, indent=1, ensure_ascii=False) + "\n"
    if args.check:
        ok = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("  %s %s" % (OUT.name, "est à jour" if ok else "NE CORRESPOND PAS"))
        raise SystemExit(0 if ok else 1)
    OUT.write_text(text, encoding="utf-8")
    print("  écrit : %s (%d écritures)" % (OUT.relative_to(HERE.parent), len(uniq)))


if __name__ == "__main__":
    main()
