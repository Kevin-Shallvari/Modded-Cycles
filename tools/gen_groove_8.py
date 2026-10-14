#!/usr/bin/env python3
"""Génère tweaks/model-cycles_OS1.13/56-groove-8tracks.json : huit pistes audio (notes/54, 55, 56).

Projet dérivé **Model:Groove** (notes/55) : l'OS 1.13 d'origine, sans aucun mod du dépôt, dont le seul
but est de passer de six à huit pistes audio. Construit en ligne de commande seulement (jamais dans le
flasher), jalon par jalon, chacun publiant le SHA-256 du MAIN OS.

Ce que fait ce jalon (le « squelette » : le compte et la mémoire, sans code neuf) :

  1. les **bornes** : boucle maîtresse des voix (`0x400a7e40`), parcours params ×2, parcours tampons
     de travail, les 4 bornes du quick-mute ;
  2. la **zone « événements »** (six tableaux par piste) : reconstruite à 8 logements, avec ses trois
     constructions (borne, décalages figés, fin absolue), ses cinq immediats de décalage (`0x77…0x93`,
     dont deux tableaux invisibles aux littéraux, notes/56 §3.8.e) et le groupe déroulé remplacé par
     une boucle (l'option A ne tient pas, notes/56 §3.8.a) ;
  3. le **cluster BSS** (tableaux longs *et* mots, deux tampons recopiés) : bornes et taille de copie ;
  4. le **relogement** de toutes les lignes par piste : les littéraux de base de chaque ligne sont
     réécrits vers leur nouvel accueil, et le générateur **vérifie qu'aucun accueil ne se recouvre**
     (notes/56 §3.6 point 6). Un site n'est accepté que s'il est **l'opérande d'une instruction**
     (désassemblé) : les coïncidences d'octets des tables de données sont rejetées.

Où : **tout dans la fenêtre DDR** `0x4230dc10..0x4232d1a8` (128 Ko, aucun littéral, dans le BSS remis
à zéro au démarrage). Le SRAM est trop dense : le plus grand trou libre fait 962 o et la seule ligne
des tampons de sortie en demande 1024 ; la couture SRAM n'a que ~550 o libres (à partir de
`0x800076da` le stock y pointe déjà). Conséquence à mesurer : les lignes chaudes (params, tampons de
sortie, tampons de travail) quittent le SRAM rapide pour la DDR.

Ce que ce jalon ne fait **pas** encore (jalons suivants) :
  - les **deux appels du mixeur** de plus et les deux tableaux de gains (sans eux, les pistes 7-8 ne
    sont pas mélangées) ;
  - les **10 entrées de descripteurs** de plus (`0x4010dce0`, 560 o) et leurs bornes ;
  - le **format de pattern** (722 o/piste) et la conversion des projets existants ;
  - l'**interface** (sélection de piste, grilles, écrans) : non décodée (notes/54 §2.6) ;
  - la mesure CPU des lignes déplacées en DDR.

Le résultat n'est donc pas jouable depuis le panneau : c'est un jalon de moteur, à prouver en
émulation (`tools/re/test_load8.py`) avant tout essai machine.

    python3 tools/gen_groove_8.py --cycles model-cycles_OS1.13.syx [--check]
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

OUT = HERE.parent / "tweaks" / "model-cycles_OS1.13" / "56-groove-8tracks.json"
BASE = build.BASE

DDR_LO, DDR_HI = 0x4230DC10, 0x4232D1A8
DDR_BASE = 0x4230E000
SLOTS = 8

# lignes par piste : nom -> (base actuelle, pas, décalages des littéraux connus du census)
ROWS = {
    "etats des voix": (0x42308828, 0x31C, [0x000, 0x004, 0x034, 0x038, 0x318]),
    "params":         (0x8000100C, 0x42,  [0x000, 0x016]),
    "tampons sortie": (0x80001858, 0x80,  [0x000]),
    "tampons travail": (0x8000BD98, 0x30, [0x000]),
    "pmod":           (0x80001830, 0x04,  [0x000]),
    "retrig":         (0x40A78D58, 0x1C,  [0x000, 0x004, 0x010, 0x014]),
}

# Zone « événements » : disposition ordonnée (ancien décalage, taille, par piste ?, pas)
ZONE_OLD = 0x800015A0
ZONE_LAYOUT = [
    (0x000, 0x1DC, False, 4, "bloc opaque (tables/fields)"),
    (0x1DC, 0x18, True, 4, "tableau 1"),
    (0x1F4, 0x18, True, 4, "tableau 2"),
    (0x20C, 0x04, False, 4, "champ"),
    (0x210, 0x04, False, 4, "champ"),
    (0x214, 0x18, True, 4, "T1"),
    (0x22C, 0x18, True, 4, "T2"),
    (0x244, 0x04, False, 4, "champ"),
    (0x248, 0x04, False, 4, "champ"),
    (0x24C, 0x18, True, 4, "A"),
    (0x264, 0x18, True, 4, "B"),
    (0x27C, 0x04, False, 4, "masque 32 bits"),
    (0x280, 0x04, False, 4, "champ"),
    (0x284, 0x0C, False, 4, "queue"),
]
ZONE_LITERALS = [
    (0x000, "base (13 sites)"), (0x00E, "champ"), (0x061, "champ"), (0x19A, "copie 0x42 o"),
    (0x20C, "champ"), (0x210, "champ"), (0x214, "T1"), (0x22C, "T2"), (0x244, "champ"),
    (0x248, "champ"), (0x24C, "A"), (0x264, "B"), (0x27C, "masque"), (0x280, "champ"),
]
# immediats « piste + K » : décalage -> rôle (K = décalage / pas)
ZONE_IMMEDIATES = {0x1DC: "tableau 1", 0x1F4: "tableau 2", 0x214: "T1", 0x22C: "T2", 0x24C: "A"}

# Cluster BSS (tableaux longs pas 4, tableaux mots pas 2, deux tampons recopiés)
CLUSTER_OLD = 0x40FE4C90
CLUSTER_LAYOUT = [
    (0x00, 0x0C, True, 2, "tampon source de copie"),
    (0x0C, 0x18, True, 4, "tableau long"),
    (0x24, 0x18, True, 4, "note courante"),
    (0x3C, 0x04, False, 4, "champ"),
    (0x40, 0x0C, True, 2, "tableau mot"),
    (0x4C, 0x0C, True, 2, "tableau mot"),
    (0x58, 0x08, False, 4, "champ"),
    (0x60, 0x04, False, 4, "champ"),
    (0x64, 0x04, False, 4, "champ"),
]
CLUSTER_LITERALS = [
    (0x00, "tampon source"), (0x0C, "tableau long"), (0x24, "note courante"),
    (0x40, "tableau mot"), (0x4C, "tableau mot"), (0x60, "champ"), (0x64, "champ"),
]

# Famille 0x422ff1xx (révélée par la garde `0x4005617c`, notes/56 §3.14–§3.15) : trois tableaux
# d'octets par piste **packés**, une table de pointeurs et un tableau de longs — tous par piste.
# Le bloc va de 0x422ff168 à 0x422ff1ac (le champ simple suivant, qui ne bouge pas).
FAMILY_OLD = 0x422FF168
# (ancien décalage, nouveau décalage, taille pour 6 logements, par piste ?, rôle)
FAMILY_LAYOUT = [
    (0x00, 0x00, 0x06, True, "octets A"),
    (0x06, 0x08, 0x06, True, "octets B"),
    (0x0C, 0x10, 0x06, True, "octets C"),
    (0x14, 0x1C, 0x18, True, "pointeurs"),
    (0x2C, 0x3C, 0x18, True, "longs"),
]
FAMILY_SIZE = 0x5C

_MD = None


def md():
    global _MD
    if _MD is None:
        import capstone
        _MD = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_M68K_040)
        _MD.big_endian = True
    return _MD


def u32(b, va):
    i = va - BASE
    return int.from_bytes(b[i:i + 4], "big")


def widen(layout, slots):
    """Nouvelle disposition : {ancien décalage: nouveau} + taille totale."""
    shift, mapping = 0, {}
    for off, size, per_track, unit, *_ in layout:
        mapping[off] = off + shift
        if per_track:
            shift += unit * slots - size
    return mapping, mapping[layout[-1][0]] + layout[-1][1]


def new_off(mapping, layout, off):
    """Décalage d'un octet quelconque : élément conteneur + déplacement interne."""
    for eoff, size, *_ in layout:
        if eoff <= off < eoff + size:
            return mapping[eoff] + (off - eoff)
    raise KeyError(off)


def layout():
    """Dispositions et accueils (calcul pur, sans image) — partagé avec les bancs.

    Retourne homes (nom -> adresse), zone_map/clus_map (ancien décalage -> nouveau),
    les tailles reconstruites et la liste des plages occupées (pour l'assertion de
    non-recouvrement et pour le banc 0xFF).
    """
    zone_map, zone_size = widen(ZONE_LAYOUT, SLOTS)
    clus_map, clus_size = widen(CLUSTER_LAYOUT, SLOTS)
    homes, cursor = {}, DDR_BASE
    for name, (base, stride, _) in ROWS.items():
        homes[name] = cursor
        cursor += stride * SLOTS
    homes["zone evenements"] = cursor
    cursor += zone_size
    homes["cluster"] = cursor
    cursor += clus_size
    homes["famille 0x422ff1xx"] = cursor
    cursor += FAMILY_SIZE
    spans = sorted([(homes[n], homes[n] + ROWS[n][1] * SLOTS, n) for n in ROWS]
                   + [(homes["zone evenements"], homes["zone evenements"] + zone_size, "zone evenements"),
                      (homes["cluster"], homes["cluster"] + clus_size, "cluster"),
                      (homes["famille 0x422ff1xx"], homes["famille 0x422ff1xx"] + FAMILY_SIZE,
                       "famille 0x422ff1xx")])
    return dict(homes=homes, zone_map=zone_map, zone_size=zone_size, clus_map=clus_map,
                clus_size=clus_size, spans=spans)


def is_operand_site(stock, va):
    """Le littéral en `va` est-il l'opérande d'une instruction (et non une coïncidence) ?"""
    v = u32(stock, va)
    txt = "%08x" % v
    for back in (2, 4, 6):
        start = va - back
        ins = list(md().disasm(bytes(stock[start - BASE:start - BASE + 16]), start))
        if not ins:
            continue
        i = ins[0]
        if i.address <= va and i.address + i.size >= va + 4:
            if txt in i.op_str.lower().replace("$", ""):
                return True
    return False


def find_sites(stock, value):
    """Tous les sites réels (opérande) d'une valeur, dans toute l'image."""
    out, coinc = [], []
    pat = struct.pack(">I", value)
    i = 0
    while True:
        i = stock.find(pat, i)
        if i < 0:
            break
        va = BASE + i
        if i % 2 == 0:
            (out if is_operand_site(stock, va) else coinc).append(va)
        i += 1
    return out, coinc


def find_addi_sites(stock, value, lo, hi):
    """Sites de `addi.l #value,Dn` dans une plage (les immediats « piste + K »)."""
    out, cur = [], lo
    needle = "#$%x," % value
    while cur < hi:
        ins = list(md().disasm(bytes(stock[cur - BASE:hi - BASE]), cur))
        if not ins:
            cur += 2
            continue
        for i in ins:
            if i.mnemonic == "addi.l" and needle in ("%s " % i.op_str).lower().replace(" ", ""):
                out.append(i.address + 2)          # le littéral est l'immediat, pas l'opcode
        cur = ins[-1].address + ins[-1].size
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycles", required=True, help="model-cycles_OS1.13.syx officiel")
    ap.add_argument("--check", action="store_true", help="vérifie que le JSON versionné correspond")
    args = ap.parse_args()
    stock = T.main_os_from_syx(args.cycles)
    dev = json.loads((OUT.parent / "device.json").read_text(encoding="utf-8"))
    if build.sha(stock) != dev["section_sha256"]:
        raise SystemExit("!! ce n'est pas le MAIN OS 1.13 officiel")

    zone_map, zone_size = widen(ZONE_LAYOUT, SLOTS)
    clus_map, clus_size = widen(CLUSTER_LAYOUT, SLOTS)
    print("zone événements : %#x -> %#x octets" % (0x290, zone_size))
    print("cluster BSS     : %#x -> %#x octets" % (0x68, clus_size))

    lay = layout()
    homes, spans = lay["homes"], lay["spans"]
    if spans[-1][1] > DDR_HI:
        raise SystemExit("!! les accueils ne tiennent pas dans la fenêtre DDR")
    for (a, b, na), (c, d, nb) in zip(spans, spans[1:]):
        if b > c:
            raise SystemExit("!! recouvrement : %s et %s" % (na, nb))
    print("accueil : %d zone(s) dans [%#x, %#x), aucune ne se recouvre" % (len(spans), spans[0][0], spans[-1][1]))

    # littéraux des lignes
    sites = []
    for name, (base, stride, offs) in ROWS.items():
        n = 0
        for off in offs:
            real, coinc = find_sites(stock, base + off)
            for va in real:
                sites.append((va, base + off, homes[name] + off, "%s +%#x" % (name, off)))
            n += len(real)
            if coinc:
                print("    (%s +%#x : %d coïncidence(s) ignorée(s))" % (name, off, len(coinc)))
        print("  %-16s %d site(s)" % (name, n))

    zn = homes["zone evenements"]
    for off, role in ZONE_LITERALS:
        real, coinc = find_sites(stock, ZONE_OLD + off)
        for va in real:
            sites.append((va, ZONE_OLD + off, zn + new_off(zone_map, ZONE_LAYOUT, off), "zone %s" % role))
        if coinc:
            print("    (zone %s : %d coïncidence(s) ignorée(s))" % (role, len(coinc)))

    for off, role in ZONE_IMMEDIATES.items():
        oldk, newk = off // 4, new_off(zone_map, ZONE_LAYOUT, off) // 4
        real = find_addi_sites(stock, oldk, 0x40058300, 0x40059A00)
        for va in real:
            sites.append((va, oldk, newk, "zone immediat %s (%#x -> %#x)" % (role, oldk, newk)))
        print("  immediat %-12s K %#x -> %#x  %d site(s)" % (role, oldk, newk, len(real)))

    cn = homes["cluster"]
    for off, role in CLUSTER_LITERALS:
        real, coinc = find_sites(stock, CLUSTER_OLD + off)
        for va in real:
            sites.append((va, CLUSTER_OLD + off, cn + new_off(clus_map, CLUSTER_LAYOUT, off), "cluster %s" % role))
        if coinc:
            print("    (cluster %s : %d coïncidence(s) ignorée(s))" % (role, len(coinc)))

    fn = homes["famille 0x422ff1xx"]
    for old_off, new_off_f, size, per_track, role in FAMILY_LAYOUT:
        real, coinc = find_sites(stock, FAMILY_OLD + old_off)
        for va in real:
            sites.append((va, FAMILY_OLD + old_off, fn + new_off_f, "famille %s" % role))
        print("  famille %-10s %d site(s)" % (role, len(real)))
        if coinc:
            print("    (famille %s : %d coïncidence(s) ignorée(s))" % (role, len(coinc)))

    print("total : %d littéraux relogés" % len(sites))

    # constructions et bornes
    T1 = new_off(zone_map, ZONE_LAYOUT, 0x214)
    T2 = new_off(zone_map, ZONE_LAYOUT, 0x22C)
    A = new_off(zone_map, ZONE_LAYOUT, 0x24C)
    B = new_off(zone_map, ZONE_LAYOUT, 0x264)
    patches = [
        (0x400A7E40, "7006", "7008", "boucle maîtresse des voix : 6 -> 8"),
        (0x40056F92, "0c810000018c", "0c8100000210", "parcours params : 8 x 0x42"),
        (0x400584EA, "0c800000018c", "0c8000000210", "parcours params (b)"),
        (0x4005978C, "0c8200000120", "0c8200000180", "parcours tampons de travail : 8 x 0x30"),
        (0x40013846, "7005", "7007", "quick-mute (1)"),
        (0x40013928, "7005", "7007", "quick-mute (2)"),
        (0x40013A90, "7205", "7207", "quick-mute (3), garde"),
        (0x40013A96, "7405", "7407", "quick-mute (3), repli"),
        (0x40059240, "7206", "7208", "boucle bitmask événements"),
        (0x4005929A, "7206", "7208", "boucle bitmask cluster"),
        (0x40056E90, "7206", "7208", "mixeur : boucle du tableau de mots (6 -> 8)"),
        (0x4005449E, "7206", "7208", "famille : boucle des trois tableaux d'octets"),
        (0x40055372, "7006", "7008", "famille : boucle au pas du pattern (722)"),
        (0x400553E2, "7c06", "7c08", "famille : boucle d'écriture par piste"),
        (0x4005617C, "7205", "7207", "famille : garde « index de piste <= 5 » -> 7"),
        (0x4005965C, "7218", "7220", "remise à zéro du cluster : 8 longs"),
        (0x400596F2, "7405", "7407", "cluster : garde dernière piste"),
        (0x40059830, "4878000c", "48780010", "cluster : copie 16 o"),
        (0x400591F8, "41f9800017cc", "41f9" + struct.pack(">I", zn + T2).hex(), "zone : base T2"),
        (0x40059218, "42a8ffe8", "42a8" + struct.pack(">h", T1 - T2).hex(), "zone : distance T2 -> T1"),
        (0x40059518, "41f9800017ec", "41f9" + struct.pack(">I", zn + A).hex(), "zone : base A"),
        (0x40059520, "42a80014", "42a8" + struct.pack(">h", B - A - 4).hex(), "zone : distance A -> B"),
        (0x40059524, "b1fc80001804", "b1fc" + struct.pack(">I", zn + B).hex(), "zone : fin absolue"),
    ]
    grp_old = bytes.fromhex("42b9800017ec42b9800017f042b9800017f442b9800017f842b9800017fc42b980001800")
    grp_new = (bytes.fromhex("41f9") + struct.pack(">I", zn + A) + bytes.fromhex("72084298538166fa")
               + b"\x4e\x71" * 11)
    patches.append((0x40058DE2, grp_old.hex(), grp_new.hex(), "zone : groupe déroulé -> boucle"))
    if len(grp_new) != len(grp_old):
        raise SystemExit("!! le remplacement du groupe déroulé ne fait pas 36 octets")

    writes = []
    for va, old, new, role in patches:
        if stock[va - BASE:va - BASE + len(old) // 2] != bytes.fromhex(old):
            raise SystemExit("!! octets d'origine inattendus en %#x (%s)" % (va, role))
        writes.append((va, old, new))
    for va, old, new, role in sites:
        ob = struct.pack(">I", old)
        if stock[va - BASE:va - BASE + 4] != ob:
            raise SystemExit("!! littéral inattendu en %#x (%s)" % (va, role))
        writes.append((va, ob.hex(), struct.pack(">I", new).hex()))

    seen, uniq = set(), []
    for va, old, new in sorted(writes):
        if va in seen or old == new:
            continue
        seen.add(va)
        uniq.append({"off": va - BASE, "old": old, "new": new})

    tweak = {
        "id": "groove-8tracks",
        "order": 56,
        "name": "Huit pistes audio (Model:Groove)",
        "description": [
            "Model:Groove, jalon 1 : le moteur audio compte huit pistes au lieu de six, et toutes les "
            "lignes par piste ont été relogées dans la fenêtre DDR remise à zéro au démarrage.",
            "Ce jalon ne touche à aucun mod du dépôt (la ligne Groove part de l'OS d'origine) et ne "
            "change ni les machines, ni les effets delay/reverb, ni l'interface.",
            "Il n'est pas encore jouable depuis le panneau : le mixeur (2 appels), les descripteurs, "
            "le format de pattern et la sélection de piste sont des jalons suivants. Construit en "
            "ligne de commande seulement, hors flasher. Généré par tools/gen_groove_8.py, notes/54-56.",
        ],
        "device": "Model:Cycles",
        "os": "1.13",
        "section": 3,
        "writes": uniq,
    }

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
