#!/usr/bin/env python3
"""GÃ©nÃ¨re tweaks/model-cycles_OS1.13/58-groove-convert.json : le convertisseur de projet
**v6 -> v7** de la ligne dÃ©rivÃ©e **Model:Groove** (notes/56 Â§3.49, Â§3.58, Â§3.59).

Le problÃ¨me qu'il rÃ©sout. Le projet d'usine est un bloc **v5** Ã©crit dans l'image ; le chemin de
chargement le passe dans la chaÃ®ne des convertisseurs de version, qui en fait un bloc **v6**. Mais
depuis que le mod Groove exige la version **7** (`57-groove-patterns.json`), le contrÃ´le de fin de
chaÃ®ne **refuse** ce bloc â€” **Ã  chaque dÃ©marrage**, que l'utilisateur ait son propre projet ou non.
Refuser n'est pas anodin : c'est ce qui laisse la machine sur l'Ã©cran d'exception (notes/56 Â§3.56,
Â§3.57). Ce tweak **convertit** au lieu de refuser.

Ce qu'il Ã©crit :

  1. `tools/machines/groove/convert_chain.S` (288 octets, prouvÃ© par
     `tools/re/test_groove_chain.py`) est posÃ© dans un **masque de sprite libÃ©rÃ©** â€”
     `0x4016cae8`, 1024 o, tout `0xFF` (`tools/sprites.py`) ;
  2. le masque est rÃ©ellement libÃ©rÃ© par la redirection du constructeur de son sprite vers le
     masque partagÃ©, qui est identique octet pour octet : le rendu ne change pas ;
  3. le **contrÃ´le de fin de chaÃ®ne** en `0x4005de74` devient un **appel** Ã  la colle (6 o) suivi
     d'un **branchement** vers l'Ã©pilogue de la chaÃ®ne (4 o).

Pourquoi seulement 10 octets sur les 42 du contrÃ´le. Le branchement saute par-dessus la fin du
contrÃ´le : ces octets ne sont **jamais exÃ©cutÃ©s**. Les Ã©crire obligerait Ã  toucher `0x4005de94`,
que `57-groove-patterns.json` patche aussi (version 6 -> 7), et deux tweaks ne doivent pas Ã©crire
au mÃªme endroit â€” c'est ce que le contrÃ´le de recouvrement ci-dessous vÃ©rifie, en comparant nos
Ã©critures Ã  celles de 56 et de 57.

Le **contrat de registres** de la colle (a2 = le bloc, a3 = le drapeau, fp/A6 = l'allocateur
`0x400802e0`, a5 = le libÃ©rateur `0x400cf044`, rÃ©sultat dans l'**octet bas** de d0) est lu dans le
prologue de la chaÃ®ne elle-mÃªme et dans son bloc v5, pas supposÃ© : notes/56 Â§3.58.

    python3 tools/gen_groove_convert.py --cycles model-cycles_OS1.13.syx [--check]
"""
import argparse
import json
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "emu"))

import build                       # noqa: E402
import sprites                     # noqa: E402
import test_sdvintage as T         # noqa: E402

OUT = HERE.parent / "tweaks" / "model-cycles_OS1.13" / "58-groove-convert.json"
SRC = HERE / "machines" / "groove" / "convert_chain.S"
BASE = build.BASE

# --- le logement : un masque de sprite libÃ©rÃ© (tools/sprites.py, notes/14 Â§5) -------------
MASK = 0x4016CAE8                    # sprite 64x128 Â« damier de test Â», 1024 o, tout 0xFF
MASK_SIZE = sprites.MASKS[MASK][0]

# --- la redirection : le contrÃ´le de fin de chaÃ®ne ----------------------------------------
CHAIN = 0x4005DE74                   # `movel %a2@(4),%d0` : la version du bloc
EPILOGUE = 0x4005DEA0                # `moveml %sp@,%d2-%d4/%a2-%fp` : l'Ã©pilogue de la chaÃ®ne
# Les 42 octets du contrÃ´le de fin de chaÃ®ne, tels quels dans l'OS d'origine. La version y est
# encore 6 (`7206`) : 57 la passe Ã  7, mais tout ce contrÃ´le devient du code MORT (le
# branchement ci-dessous le saute), donc les deux tweaks ne se gÃªnent pas.
END_CHECK = ("202a0004207cbeefbaceb1d2661c223c00210400207cbacef00c"
             "b1f21800660a7206b28057c044806002")
JSR_OLD = END_CHECK[0:12]            # `movel %a2@(4),%d0` + les 2 premiers octets du `moveal`
BRA_OLD = END_CHECK[12:20]           # la fin du `moveal #-1091585330,%a0`

GLUE_SIG = "4feffff048d700e0"        # `lea -16(%sp),%sp` + `movem.l %d5-%d7,(%sp)`
V7_SIG = "206f0004"                  # `movel %sp@(4),%a0` : la premiÃ¨re fonction du fichier

# --- les tweaks dont celui-ci dÃ©pend, et avec lesquels il ne doit pas se recouvrir ---------
REQUIRES = ["groove-patterns"]
SIBLINGS = ("56-groove-8tracks.json", "57-groove-patterns.json")


def assemble(src):
    """Assemble et LIE le .S (WSL si le compilateur m68k n'est pas natif).

    Le lien est nÃ©cessaire : un appel interne (`bsr groove_v7`) sort du compilateur avec une
    relocation non rÃ©solue, et sans lien la cible vaut 0 â€” le code sauterait Ã  l'adresse zÃ©ro.
    """
    def native():
        with tempfile.TemporaryDirectory() as d:
            o, b = pathlib.Path(d) / "c.o", pathlib.Path(d) / "c.bin"
            subprocess.run(["m68k-linux-gnu-gcc", "-mcpu=54418", "-c", str(src), "-o", str(o)],
                           check=True, capture_output=True)
            subprocess.run(["m68k-linux-gnu-ld", "-Ttext=0", "-e", "0", "--oformat=binary",
                            "-o", str(b), str(o)], check=True, capture_output=True)
            return b.read_bytes()

    try:
        return native()
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    with tempfile.TemporaryDirectory() as d:
        sh = pathlib.Path(d) / "asm.sh"
        unix = str(src).replace("\\", "/").replace("C:", "/mnt/c", 1)
        sh.write_text('set -e\nT=$(mktemp -d)\n'
                      'm68k-linux-gnu-gcc -mcpu=54418 -c "%s" -o $T/c.o\n'
                      'm68k-linux-gnu-ld -Ttext=0 -e 0 --oformat=binary -o $T/c.bin $T/c.o\n'
                      'od -An -tx1 -v $T/c.bin | tr -d " \\n"\n' % unix,
                      encoding="utf-8", newline="\n")
        unix_sh = str(sh).replace("\\", "/").replace("C:", "/mnt/c", 1)
        out = subprocess.run(["bash", unix_sh], capture_output=True, text=True, check=True).stdout
    return bytes.fromhex(out.strip())


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycles", required=True, help="model-cycles_OS1.13.syx officiel")
    ap.add_argument("--check", action="store_true",
                    help="vÃ©rifie que le JSON versionnÃ© correspond")
    args = ap.parse_args()

    stock = bytes(T.main_os_from_syx(args.cycles))
    dev = json.loads((OUT.parent / "device.json").read_text(encoding="utf-8"))
    if build.sha(stock) != dev["section_sha256"]:
        raise SystemExit("!! ce n'est pas le MAIN OS 1.13 officiel")

    code = assemble(SRC)
    chain_off = code.index(bytes.fromhex(GLUE_SIG)) if code.count(bytes.fromhex(GLUE_SIG)) == 1 \
        else -1
    glue = MASK + chain_off
    bra = EPILOGUE - (CHAIN + 8)                 # branchement depuis 0x4005de7a (mot d'extension)

    print("convertisseur v6 -> v7 (notes/56 Â§3.58, Â§3.59)")
    print("  code             : %d octets (assemble et lie)" % len(code))
    print("  logement         : masque de sprite %#x, %d o" % (MASK, MASK_SIZE))
    print("  colle            : offset %#x dans le code -> %#x" % (chain_off, glue))
    print("  controle de fin  : %#x -> jsr %#x + bra %#x" % (CHAIN, glue, EPILOGUE))

    # --- LES CONTROLES INVERSES : chacun doit pouvoir echouer ------------------------------
    bad = []
    if len(code) > MASK_SIZE:
        bad.append("le code (%d o) ne tient pas dans le masque %#x (%d o)"
                   % (len(code), MASK, MASK_SIZE))
    if code[:4].hex() != V7_SIG:
        bad.append("la premiere fonction du fichier n'est pas groove_v7 : %s au lieu de %s"
                   % (code[:4].hex(), V7_SIG))
    if chain_off < 0:
        bad.append("le prologue de la colle (%s) n'apparait pas exactement une fois" % GLUE_SIG)
    if stock[MASK - BASE:MASK - BASE + MASK_SIZE] != b"\xff" * MASK_SIZE:
        bad.append("le masque %#x (%d o) n'est pas entierement 0xFF dans l'image d'origine"
                   % (MASK, MASK_SIZE))
    ref_va = sprites.MASKS[MASK][1]
    if stock[ref_va - BASE:ref_va - BASE + 4] != MASK.to_bytes(4, "big"):
        bad.append("la constante du constructeur en %#x ne vaut pas %#x (mais %s)"
                   % (ref_va, MASK, stock[ref_va - BASE:ref_va - BASE + 4].hex()))
    if stock[CHAIN - BASE:CHAIN - BASE + len(END_CHECK) // 2].hex() != END_CHECK:
        bad.append("le controle de fin de chaine en %#x n'est pas celui attendu :\n     %s"
                   % (CHAIN, stock[CHAIN - BASE:CHAIN - BASE + 42].hex()))
    if not (-0x8000 <= bra <= 0x7FFF):
        bad.append("le branchement vers l'epilogue sort de portee : %d" % bra)
    if stock[EPILOGUE - BASE:EPILOGUE - BASE + 4] != bytes.fromhex("4cd77c1c"):
        bad.append("l'epilogue de la chaine en %#x n'est pas `moveml %%sp@,%%d2-%%d4/%%a2-%%fp`"
                   % EPILOGUE)

    writes = [
        {"off": MASK - BASE, "old": "ff" * len(code), "new": code.hex()},
        sprites.redirect_write(MASK),
        {"off": CHAIN - BASE, "old": JSR_OLD, "new": "4eb9%08x" % glue},
        {"off": CHAIN + 6 - BASE, "old": BRA_OLD, "new": "6000%04x" % (bra & 0xFFFF)},
    ]

    # --- LE CONTROLE DE RECOUVREMENT : deux tweaks ne doivent pas ecrire au meme endroit ----
    # C'est le piege de ce mod : le controle de fin de chaine se termine sur le 0x4005de94 que
    # 57 patche. On n'ecrit donc que le debut du controle, et on verifie ici qu'aucune ecriture
    # de 56 ni de 57 ne tombe dans les notres.
    spans = [(w["off"], w["off"] + len(bytes.fromhex(w["old"]))) for w in writes]
    for name in SIBLINGS:
        sib = json.loads((OUT.parent / name).read_text(encoding="utf-8"))
        for w in sib["writes"]:
            lo, hi = w["off"], w["off"] + len(bytes.fromhex(w["old"]))
            for a, b in spans:
                if lo < b and a < hi:
                    bad.append("%s ecrit en %#x..%#x, qui recouvre notre %#x..%#x (%s)"
                               % (name, lo + BASE, hi + BASE, a + BASE, b + BASE, w.get("role", "")))
    print("  recouvrement     : %d ecriture(s) de %s comparee(s) aux notres"
          % (sum(len(json.loads((OUT.parent / n).read_text(encoding="utf-8"))["writes"])
                 for n in SIBLINGS), " et ".join(SIBLINGS)))

    if bad:
        for b in bad:
            print("  !! " + b)
        raise SystemExit("!! un controle a echoue (notes/56 Â§3.59) : rien n'a ete ecrit.")

    tweak = {
        "id": "groove-convert",
        "order": 58,
        "name": "Conversion des projets v6 -> v7 (Model:Groove)",
        "description": [
            "Model:Groove, jalon 3 : le projet d'origine est CONVERTI au lieu d'etre refuse. Le "
            "projet d'usine est un bloc v5 ; la chaine des convertisseurs de version le passe en "
            "v6, et depuis que le mod exige la version 7 (57-groove-patterns.json) le controle de "
            "fin de chaine refusait ce bloc a CHAQUE demarrage, que l'utilisateur ait son propre "
            "projet ou non. C'est ce qui laissait la machine sur l'ecran d'exception.",
            "Un convertisseur v6 -> v7 de 288 octets d'assembleur "
            "(tools/machines/groove/convert_chain.S) prend la place du controle de fin de chaine "
            "(0x4005de74) : il alloue un tampon de 1 918 788 octets, recopie l'en-tete de 512 o, "
            "repacke les 80 patterns a huit pistes (l'element de 57), abandonne la banque F, "
            "repacke les 80 kits (7 094 octets copies, 200 a zero), recopie la queue de 512 o, "
            "ecrit le sceau de cloture et la version 7, recopie le tout dans l'image et refait le "
            "controle de fin de chaine en v7.",
            "Le code est pose dans un masque de sprite libere (0x4016cae8, 1024 o) : le "
            "constructeur du sprite est redirige vers le masque partage, qui est identique octet "
            "pour octet, donc le rendu ne change pas (tools/sprites.py, notes/14 Â§5). Le "
            "convertisseur ne touche ni d5, ni d6, ni d7 â€” le chemin de chargement lit %d6 APRES "
            "la chaine â€” et son contrat de registres (a2, a3, fp, a5, resultat dans l'octet bas "
            "de d0) est lu dans le prologue de la chaine elle-meme, pas suppose.",
            "Prouve par tools/re/test_groove_chain.py : la transformee rend exactement la "
            "reference Python octet pour octet, les 80 patterns sont un a un ceux du "
            "convertisseur d'element deja prouve (jalon 2), et la colle s'execute (allocateur et "
            "liberateur remplaces par des stubs) en laissant un bloc v7 valide dans l'image, le "
            "drapeau pose, et en rendant 1. Le banc a attrape quatre fautes reelles, dont deux "
            "qu'aucune relecture n'aurait vues.",
            "S'applique APRES 57-groove-patterns.json. La banque F (16 patterns) reste perdue : "
            "c'est la contrepartie du passage a huit pistes. Construit en ligne de commande "
            "seulement, hors flasher. Genere par tools/gen_groove_convert.py, notes/56 Â§3.58.",
        ],
        "device": "Model:Cycles",
        "os": "1.13",
        "section": 3,
        "requires": REQUIRES,
        "writes": writes,
    }

    build.apply_writes(stock, [tweak])
    print("  total            : %d ecriture(s), %d octet(s)"
          % (len(writes), sum(len(bytes.fromhex(w["new"])) for w in writes)))

    text = json.dumps(tweak, indent=1, ensure_ascii=False) + "\n"
    if args.check:
        ok = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("  %s %s" % (OUT.name, "est Ã  jour" if ok else "NE CORRESPOND PAS"))
        raise SystemExit(0 if ok else 1)
    OUT.write_text(text, encoding="utf-8")
    print("  Ã©crit : %s" % OUT.relative_to(HERE.parent))


if __name__ == "__main__":
    main()


