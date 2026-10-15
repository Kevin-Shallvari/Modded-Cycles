#!/usr/bin/env python3
"""Génère tweaks/model-cycles_OS1.13/57-groove-patterns.json : le format de pattern à 8 pistes
ET le conteneur de l'image projet.

Projet dérivé **Model:Groove** (notes/55). **Jalon 2** (notes/56 §3.27 à §3.36), à appliquer
**après** `56-groove-8tracks.json` (jalon 1, le moteur audio). Construit en ligne de commande
seulement, jamais dans le flasher.

Ce que fait ce jalon :

  1. **le format de pattern** : l'enregistrement déployé passe de 30 710 à **40 924** octets
     (`4 + 8×722 + 8×4385 + 64`) et le bloc rangé de 14 848 à **16 292** (`4 + 8×722 + 10 512`) ;
  2. **les kits** : l'enregistrement **déployé** passe de 7 094 à **7 294** (100 o par piste) et
     l'aire par piste de 600 à **800** — ce qui **décale de +200** les deux champs qui la suivent
     (628 → 828, 694 → 894 déployés ; 632 → 832, 708 → 908 rangés). Le **creneau rangé** d'un kit
     (7 680) **ne change pas** : il a été dimensionné avec la marge (7 564 à huit pistes) ;
  3. **le nombre de patterns** : 96 → **80** (la banque F est échangée contre les pistes 7-8) ;
  4. **le conteneur du bloc courant** (§3.51) : la taille du bloc projet passe de 2 163 716 à
     **1 918 788** et le sceau de clôture de +2 163 712 à **+1 918 784**, parce que les patterns
     rangés passent à 16 292 et le nombre à 80 :
         `[512][80 × 16 292][80 × 7 680][512][4]`
     d'où la base des kits : 1 303 872 dans le fichier (512 + 80×16 292) et 1 304 144 dans l'image.

**Le point capital de ce générateur** : la **chaîne des convertisseurs de version** (les six
`v0…v5 → v6`, leurs éléments, et les six blocs de `0x4005d9f6`) décrit **un bloc v6** — sa sortie.
Elle doit donc garder la **géométrie d'origine**, et le balayage par valeur doit l'**exclure**.
Le jalon 2 la réécrivait comme le reste : c'est ce qui rendait le conteneur incohérent, et ce qui
faisait **déborder** la chaîne (elle copiait 96 patterns au pas v7 dans un tampon rabaissé à
1 944 164 octets). Voir `LEGACY` ci-dessous.

    python3 tools/gen_groove_pattern.py --cycles model-cycles_OS1.13.syx [--check] [--audit]
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

# --- le bloc courant (ce que Groove ecrit et lit) ----------------------------------------
#   bloc = [512][80 x 16292][80 x 7680][512][4] = 1 918 788
#   patterns 0x406c8ce0.., kits 0x43dd0000 (l'aire totale RETRECIT de 16672, §3.51)
IMAGE_OLD = 2163716
IMAGE_NEW = 1918788                 # 512 + 80x16292 + 80x7680 + 512 + 4
GROWTH = IMAGE_NEW - IMAGE_OLD      # -244928
HEADER_OLD = 0x406FA024
PATTERNS_OLD = 0x406FA040
HEADER_NEW = HEADER_OLD + GROWTH
PATTERNS_NEW = PATTERNS_OLD + GROWTH
PATTERN_SIZE = 40924                # deploye : 4 + 8 x 722 + 8 x 4385 + 64
PATTERN_COUNT = 80
KITS_OLD_OFFSET = 2948188           # offset des kits, relatif a l'en-tete
KITS_NEW = 0x43DD0000               # les kits ne tiennent plus apres les patterns : plage libre
KITS_NEW_OFFSET = KITS_NEW - HEADER_NEW

# --- LES PLAGES DE LA CHAINE DE VERSIONS : geometrie d'ORIGINE, a NE PAS toucher --------
# Leur sortie est un bloc **v6**, pas un bloc v7 : elles gardent 2 163 716, 14 848, 4 336, etc.
# Elles restent dans l'image (le controle de fin de chaine les rend inoffensives : il exige la
# version 7, et elles produisent du 6), mais elles doivent rester *coherentes* — c'est ce qui
# garantit qu'elles ne debordent pas.
LEGACY = [
    (0x4005BDC0, 0x4005BEE0, "elements de kit v5 -> v6 et v4 -> v5"),
    (0x4005C15A, 0x4005C2E2, "elements de pattern v5 -> v6"),
    (0x4005C2E2, 0x4005CD9E, "les six convertisseurs de version et leurs aides"),
    # ILE COURANTE : 0x4005cd9e..0x4005cdde est un aide du bloc COURANT (le marcheur de la
    # queue rangee, qui lit le pas d'une entree a +4336 -> +5780). §3.48 l'a prouve par
    # l'aller-retour : sans ce decalage, la sauvegarde n'est plus idempotente. Il est pris
    # DANS la zone des convertisseurs, d'ou la coupure.
    (0x4005CDDE, 0x4005D000, "fin des convertisseurs de version"),
    (0x4005D9F6, 0x4005DE74, "les six blocs de la chaine de versions"),
]

# --- LES DEUX CHAMPS DE KIT : UNE LISTE BLANCHE (§3.52, §3.53) --------------------------
# L'aire par piste passe de 600 a 800 octets, donc les deux champs qui la suivent decalent de
# +200 : 628 -> 828 et 694 -> 894 (deployes), 632 -> 832 et 708 -> 908 (ranges).
#
# Ces quatre valeurs sont des decalages BANALS (36, 6, 54 et 27 sites), presque tous des
# coincidences. On ne peut donc PAS les trouver par valeur : on donne la LISTE BLANCHE des
# sites, chacun avec sa raison. Le generateur verifie que chacun est bien trouve par le
# balayage (sinon l'entree est fausse) et que les octets d'origine sont ceux attendus.
#
# Ecartes, avec leur raison :
#   - 0x400333dc, 0x4003c1fc : une SERIE de `clrl` sur 612..640, un tampon contigu, pas un
#     champ de 66 octets ;
#   - 0x4003f9ae : CHARGE un pointeur depuis 628 — la fiche de kit et l'enregistrement deploye
#     sont des donnees plates, sans pointeur ;
#   - 0x400db764, 0x400dc4c8 : constructeurs d'OBJET (un descripteur de classe est ecrit),
#     champs pointeurs ;
#   - 0x4003a400 : `pea 0x274` est une ADRESSE, pas un decalage ;
#   - la grappe 0x400a**** : le moteur ne parcourt pas les kits (aucun 7094), donc il lit par
#     pointeur — argument du pas, §3.53.
KIT_FIELDS = {
    628: (828, [0x40009AB2, 0x40009AC4, 0x40009B76, 0x4000A564, 0x4005B31E, 0x400613EA]),
    694: (894, [0x40009AC0, 0x4005B32C, 0x4005D160, 0x400613F4]),
    632: (832, [0x40009B6A, 0x4005B322, 0x4005D13A]),
    708: (908, [0x40009B64, 0x4005B330, 0x4005D15C]),
}

# Ce sont les adresses des INSTRUCTIONS. Le generateur retrouve la position de la valeur en
# cherchant ses deux octets DANS l'instruction (a +2 pour `pea.l $274(a3)`, a +4 pour un
# immediat 32 bits comme `addi.l #708,%d2`) : la liste blanche reste lisible, et la position
# est verifiee, pas supposee.
KIT_FIELD_SCAN = 8

# --- immediats 32 bits : (avant, apres, sites attendus, role) ----------------------------
IMMEDIATES = [
    # la geometrie des pas (deployee et rangee)
    (4332, 5776, 20, "taille des pas : 6 -> 8 pistes"),
    (4336, 5780, 1, "offset de la queue (immediat)"),
    # le bloc courant
    (IMAGE_OLD, IMAGE_NEW, 14, "taille du bloc courant (creation, chargements, sauvegarde)"),
    (2163712, 1918784, 4, "sceau de cloture du bloc courant"),
    (1425920, 1303872, 9, "base des kits dans le fichier (512 + 80x16292)"),
    (1426192, 1304144, 1, "base des kits dans l'image (784 + 80x16292)"),
    (1425408, 1303360, 2, "fin des blocs ranges du bloc courant"),
    (14848, 16292, 12, "creneau range d'un pattern (4 + 8x722 + 10512)"),
    # les enregistrements deployes (les tables de la memoire de travail)
    (30710, 40924, 12, "enregistrement deploye"),
    (7094, 7294, 8, "enregistrement de kit deploye"),
    (600, 800, 5, "aire par piste du kit (6 -> 8 pistes)"),
    (2948160, 3273920, 2, "fin de la table des patterns deployes"),
    (26310, 35080, 3, "borne de la queue deployee (6 x 4385 -> 8 x 4385) — §3.39.c"),
    (681024, 583520, 1, "fin de la table des kits deployes"),
    (PATTERNS_OLD, PATTERNS_NEW, 6, "base de la table des patterns"),
    (HEADER_OLD, HEADER_NEW, 7, "en-tete de projet"),
    (KITS_OLD_OFFSET, KITS_NEW_OFFSET, 6, "offset des kits (relatif a l'en-tete)"),
]

# --- tailles et decalages en deplacement 16 bits -------------------------
# ATTENTION : le tri par « usage absolu » ne suffit pas — il depend de la VALEUR.
#   - `pea.l $3a00.w`     (absolu)  = une TAILLE a changer ;
#   - `pea.l $10f0(a3)`   (registre) = un DECALAGE dans l'enregistrement, a changer aussi ;
#   - `clr.l $258(a2)`    (registre) = une COINCIDENCE, a LAISSER.
DISPLACEMENTS = [
    # decalages dans l'enregistrement : usage par registre, a changer
    (4336, 5780, "registre", 5, "offset de la queue dans le pattern range"),
    (30706, 40920, "registre", 4, "champ a la fin de l'enregistrement deploye (le 5e est PATCHES)"),
    (30642, 40856, "registre", 3, "enregistrement deploye - 68"),
    (14736, 16180, "registre", 6, "pattern range - 112 (14848 -> 16292)"),
    # tailles absolues, a changer
    (7094, 7294, "tout", 8, "taille de kit deploye"),
    (600, 800, "absolu", 6, "aire par piste du kit"),
    (14848, 16292, "tout", 31, "creneau range"),
]

# Les sites de KIT_FIELDS sont verifies a l'execution : chacun doit etre trouve par le
# balayage, et les octets d'origine doivent etre ceux de la valeur.

# --- corrections octet a octet -------------------------------------------
PATCHES = [
    (0x4005B820, "1a3c0005", "1a3c0007", "borne #5 -> #7 : index de piste encode"),
    # Deplacements 16 bits de 4332 et 4336 que les balayages par IMMEDIAT avaient manques
    # (§3.36 ne balayait 4332 qu'en immediat, et 4336 qu'en 7 sites « pea »). Le chemin de
    # SAUVEGARDE en depend : sans eux, la queue RANGEE est lue/ecrite a l'offset 6 pistes et
    # l'aller-retour n'est plus idempotent (trouve par le controle E, §3.48).
    (0x4005BA70, "10ec", "1690", "sauvegarde : queue rangee 4332 -> 5776"),
    (0x4000C62E, "10ec", "1690", "deplacement 4332 -> 5776"),
    (0x4005CDB2, "10f0", "1694", "lecture 4336 -> 5780"),
    # Le champ ecrit en fin d'enregistrement par le depliage : `movel %sp@(44),%a2@(30706)`
    # (0x4005b946). Son deplacement est le 5e site de 30706, manque par le triage du §3.36.
    (0x4005B94A, "77f2", "9fd8", "champ de fin : 30706 -> 40920"),
    # Le NOMBRE DE PATTERNS du bloc courant, en trois endroits (§3.51) : le balayage par
    # immediat ne voit pas un `moveq`. La garde de 0x400083ba (`moveq #95`) est traitee a part.
    (0x4005D502, "7060", "7050", "bloc courant : 96 -> 80 patterns (marcheur range/deploye)"),
    (0x4006A3E6, "7260", "7250", "bloc courant : 96 -> 80 patterns"),
    (0x4008DB10, "7060", "7050", "bloc courant : 96 -> 80 patterns (sauvegarde)"),
    # LA VERSION : le bloc courant est ecrit en version 7 et la chaine l'exige. Les six
    # convertisseurs, eux, estampillent leur sortie en 6 : ils ne sont PAS touches (§3.51).
    (0x4000FD7C, "7006", "7007", "creation de projet : version 6 -> 7"),
    (0x4000EF6E, "7206", "7207", "materialisation d'un bloc : version 6 -> 7"),
    (0x4005DE94, "7206", "7207", "controle de fin de chaine : version 6 -> 7"),
]

# La garde du nombre de patterns : `moveq #95` -> `moveq #79` (l'index maximal).
GUARD_VA = 0x400083BA

# Sites ecartes APRES REVUE (§3.38) : la valeur apparait par coincidence dans la ZONE DE
# DONNEES de l'image (chaines, tables), jamais du code.
EXCLUDE = {
    0x4011AB70: "7094 : donnee (move.b -$4925(a5),$1bb6(a5))",
    0x40139F70: "14848 : donnee (move.b (a5),$3a00(a0))",
    0x4013C276: "14848 : donnee (move.w d0,d5)",
    0x4019D936: "14848 : donnee (move.w d0,d5)",
    0x401A10F6: "14848 : donnee (cmpil #...,d0)",
    0x401A17DE: "14848 : donnee (move.l d7,$3a00(a7))",
    0x401A8C5E: "14848 : donnee (subl d4,fp@(14848))",
}

REVIEW_PENDING = False
PENDING_VALUES = []

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


def in_legacy(va):
    """La raison si `va` est dans la chaine de versions (geometrie d'origine), sinon None."""
    for lo, hi, why in LEGACY:
        if lo <= va < hi:
            return why
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
    ap.add_argument("--audit", action="store_true",
                    help="montre tous les sites trouvés, sans rien écrire ni échouer (mise au point)")
    args = ap.parse_args()

    stock = T.main_os_from_syx(args.cycles)
    dev = json.loads((OUT.parent / "device.json").read_text(encoding="utf-8"))
    if build.sha(stock) != dev["section_sha256"]:
        raise SystemExit("!! ce n'est pas le MAIN OS 1.13 officiel")

    print("conteneur : bloc %d -> %d (%+d)" % (IMAGE_OLD, IMAGE_NEW, GROWTH))
    print("            en-tete %#x -> %#x, patterns %#x -> %#x"
          % (HEADER_OLD, HEADER_NEW, PATTERNS_OLD, PATTERNS_NEW))
    print("            kits -> %#x (offset %d -> %d, relatif a l'en-tete)"
          % (KITS_NEW, KITS_OLD_OFFSET, KITS_NEW_OFFSET))
    print("chaine de versions (geometrie d'origine, NON touchee) :")
    for lo, hi, why in LEGACY:
        print("            %#010x..%#010x  %s" % (lo, hi, why))

    writes, bad = [], []
    for old, new, expect, role in IMMEDIATES:
        found = find_imm_sites(stock, old)
        sites = [va for va in found if va not in EXCLUDE and in_legacy(va) is None]
        skipped = len(found) - len(sites)
        if args.audit:
            print("  immediat %-52s %2d site(s) retenu(s), %d ecarte(s)"
                  % (role, len(sites), skipped))
            for va in sorted(found):
                tag = in_legacy(va) or EXCLUDE.get(va) or ''
                print("      %08x  %s%s" % (va, '' if not tag else '<<< ', tag))
        elif len(sites) != expect:
            bad.append("%s : %d site(s) au lieu de %d" % (role, len(sites), expect))
        for va in sites:
            writes.append((va, struct.pack(">I", old), struct.pack(">I", new), role))
        if not args.audit:
            print("  immediat %-52s %2d site(s) (dont %d dans la chaine, ecartes)"
                  % (role, len(sites), skipped))

    for old, new, mode, expect, role in DISPLACEMENTS:
        found = find_disp_sites(stock, old, mode)
        sites = [va for va in found if va not in EXCLUDE and in_legacy(va) is None]
        skipped = len(found) - len(sites)
        if args.audit:
            print("  taille   %-46s %-8s %2d retenu(s), %d ecarte(s)"
                  % (role, mode, len(sites), skipped))
            for va in sorted(found):
                tag = in_legacy(va) or EXCLUDE.get(va) or ''
                print("      %08x  %s%s" % (va, '' if not tag else '<<< ', tag))
        elif len(sites) != expect:
            bad.append("%s (%s) : %d site(s) au lieu de %d" % (role, mode, len(sites), expect))
        for va in sites:
            writes.append((va, struct.pack(">H", old), struct.pack(">H", new), role))
        if not args.audit:
            print("  taille   %-46s %-8s %2d site(s) (dont %d dans la chaine, ecartes)"
                  % (role, mode, len(sites), skipped))

    # la garde du nombre de patterns : moveq #95 -> moveq #79
    op = stock[GUARD_VA - BASE]
    if not (0x70 <= op <= 0x77) or stock[GUARD_VA - BASE + 1] != 95:
        raise SystemExit("!! la garde du nombre de patterns n'est pas en %#x" % GUARD_VA)
    writes.append((GUARD_VA, bytes([op, 95]), bytes([op, 79]),
                   "nombre de patterns : 96 -> 80"))

    for va, old_hex, new_hex, role in PATCHES:
        ob = bytes.fromhex(old_hex)
        if stock[va - BASE:va - BASE + len(ob)] != ob:
            bad.append("%s : octets d'origine inattendus en %#x" % (role, va))
        writes.append((va, ob, bytes.fromhex(new_hex), role))
        if not args.audit:
            print("  correctif %-48s %2d octet(s)" % (role, len(ob)))

    # les deux champs de kit : liste blanche. On NE demande PAS au balayage de les trouver :
    # il s'appuie sur capstone, qui se desynchronise par endroits (en 0x40009ac0 il lit
    # `divs.w` la ou objdump lit `pea.l $2b6(a3)`). La liste blanche donne les INSTRUCTIONS ;
    # on retrouve la position de la valeur dans leurs octets, et on la verifie.
    for old, (new, addrs) in sorted(KIT_FIELDS.items()):
        ob = struct.pack(">H", old)
        nb = struct.pack(">H", new)
        for va in addrs:
            raw = stock[va - BASE:va - BASE + KIT_FIELD_SCAN]
            pos = None
            for k in range(0, len(raw) - 1, 2):
                if raw[k:k + 2] == ob:
                    pos = va + k
                    break
            if pos is None:
                bad.append("champ de kit %d : la valeur n'est pas dans les octets de %#x (%s)"
                           % (old, va, raw.hex()))
                continue
            writes.append((pos, ob, nb, "champ de kit %d -> %d" % (old, new)))
        if not args.audit:
            print("  champ   %-46s %2d site(s), position verifiee"
                  % ("kit %d -> %d" % (old, new), len(addrs)))

    if args.audit:
        print("\n--audit : rien n'a ete ecrit.")
        return

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

    # --- LE CONTROLE DU DECOUPAGE : la chaine de versions doit rester IDENTIQUE au stock ---
    patched, _ = build.apply_writes(stock, [{
        "id": "x", "order": 1, "section": 3, "device": "Model:Cycles", "os": "1.13",
        "writes": uniq,
    }])
    drift = [(lo, hi, why) for lo, hi, why in LEGACY
             if patched[lo - BASE:hi - BASE] != stock[lo - BASE:hi - BASE]]
    if drift:
        for lo, hi, why in drift:
            print("  !! la chaine de versions a ete modifiee : %#x..%#x (%s)" % (lo, hi, why))
            for va, old, new, role in sorted(writes, key=lambda w: w[0]):
                if lo <= va < hi:
                    print("       %08x  %s -> %s   %s" % (va, old.hex(), new.hex(), role))
        raise SystemExit("!! le decoupage est faux : une plage LEGACY a change")

    print("total : %d ecriture(s)" % len(uniq))
    print("controle : les %d plages de la chaine de versions sont identiques au stock"
          % len(LEGACY))

    tweak = {
        "id": "groove-patterns",
        "order": 57,
        "name": "Format de pattern a huit pistes et conteneur (Model:Groove)",
        "description": [
            "Model:Groove, jalon 2 : le format de pattern passe a huit pistes (enregistrement "
            "30 710 -> 40 924 octets deployes, 14 848 -> 16 292 ranges), les kits a 7 294 octets "
            "deployes (aire par piste 600 -> 800, les deux champs qui suivent decalent de +200) "
            "et le projet a 80 patterns au lieu de 96 (la banque F est echangee contre les pistes "
            "7-8, le seul point de perte de donnees du mod).",
            "Le conteneur du bloc projet suit : 2 163 716 -> 1 918 788 octets, sceau de cloture "
            "+2 163 712 -> +1 918 784, base des kits 1 303 872 (fichier) et 1 304 144 (image). "
            "La chaine des convertisseurs de version (les six v0..v5 -> v6) garde la geometrie "
            "d'origine : sa sortie est un bloc v6, et c'est ce qui garantit qu'elle ne deborde "
            "pas de son tampon.",
            "S'applique APRES 56-groove-8tracks.json (jalon 1, le moteur audio). Les kits "
            "demenagent vers la plage libre de 0x43dd0000.",
            "La conversion des projets d'origine n'est PAS faite dans le firmware : la version du "
            "bloc courant passe a 7, donc un projet d'origine est refuse proprement (code "
            "d'erreur dedie). Construit en ligne de commande seulement, hors flasher. Genere par "
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
