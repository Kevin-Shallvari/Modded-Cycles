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
  5. **la géographie de stockage ne bouge pas** (§3.60) : l'en-tête de projet (`0x406fa024`), la
     base de la table des patterns (`0x406fa040`) et l'enregistrement stocké (2 163 988) restent
     d'origine, parce que la chaîne des convertisseurs écrit 2 163 716 octets dans l'image
     À CHAQUE DÉMARRAGE, avant tout contrôle : la région image → en-tête doit tenir ce bloc.
     Rapprocher l'en-tête (le jalon 2 original) laissait la chaîne écraser l'en-tête et le
     début de la table déployée — le plantage du 16/10. Le contrôle de la REGION l'exige.

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
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "emu"))

import build                       # noqa: E402
import test_sdvintage as T         # noqa: E402
import capstone                    # noqa: E402
import sprites                     # noqa: E402

OUT = HERE.parent / "tweaks" / "model-cycles_OS1.13" / "57-groove-patterns.json"
BASE = build.BASE

# --- le bloc courant (ce que Groove ecrit et lit) ----------------------------------------
#   bloc = [512][80 x 16292][80 x 7680][512][4] = 1 918 788
#   patterns 0x406c8ce0.., kits 0x43dd0000 (l'aire totale RETRECIT de 16672, §3.51)
IMAGE_OLD = 2163716
IMAGE_NEW = 1918788                 # 512 + 80x16292 + 80x7680 + 512 + 4
GROWTH = IMAGE_NEW - IMAGE_OLD      # -244928
# §3.60 : l'en-tete et la table des patterns RESTENT a leurs adresses d'origine. La chaine
# des convertisseurs ecrit son bloc v6 (2 163 716, une constante de SON code, dans LEGACY)
# dans l'image A CHAQUE DEMARRAGE, avant tout controle ; si l'en-tete descend, elle l'ecrase
# — c'est le plantage du 16/10. Seul le BLOC raccourcit ; la GEOGRAPHIE DE STOCKAGE reste.
HEADER_OLD = 0x406FA024
PATTERNS_OLD = 0x406FA040
PATTERN_SIZE = 40924                # deploye : 4 + 8 x 722 + 8 x 4385 + 64
PATTERN_COUNT = 80
KITS_OLD_OFFSET = 2948188           # offset des kits, relatif a l'en-tete
KITS_NEW = 0x43DD0000               # les kits ne tiennent plus apres les patterns : plage libre
KITS_NEW_OFFSET = KITS_NEW - HEADER_OLD

# --- LES VALEURS DERIVEES : L'ENREGISTREMENT STOCKE (§3.56, §3.60) ------------------------
# Le projet n'est pas seulement « un bloc » : sur le +Drive (et en MRAM) il est STOCKE dans un
# ENREGISTREMENT = une enveloppe de 272 o suivie de l'image, et le bloc se termine par une
# « queue » de 512 o qui finit sur le sceau de cloture. Les valeurs du COTE BLOC (la queue,
# relative a l'image et a l'enregistrement) sont DERIVEES (image - 512) : le balayage par
# valeur ne les voit que si on les lui donne, et le jalon 2 les avait oubliees (plantage du
# 16/10, notes/56 §3.56).
# La TAILLE DE L'ENREGISTREMENT, elle, garde sa valeur d'ORIGINE (§3.60) : c'est de la
# GEOGRAPHIE DE STOCKAGE, comme l'en-tete et la base de la table. Le stock depose 2 163 716 o
# d'image dans un enregistrement de 2 163 988 ; le bloc v7 (1 918 788) y tient avec de la
# marge — et la chaine garde la place d'ecrire son bloc v6 ENTIER dans l'image.
ENVELOPE = 272                      # l'enveloppe de l'enregistrement stocke (0x404e9b10)
RECORD_OLD = IMAGE_OLD + ENVELOPE   # 2 163 988 — et il RESTE 2 163 988 (§3.60 : pas de patch)
CLOSING_OLD = IMAGE_OLD - 4         # 2 163 712 : le sceau de cloture est les 4 derniers octets
CLOSING_NEW = IMAGE_NEW - 4         # 1 918 784
TAIL_OLD = CLOSING_OLD - 512        # 2 163 200 : la queue de 512 o, relative a l'image
TAIL_NEW = CLOSING_NEW - 512        # 1 918 272
TAIL_REC_OLD = TAIL_OLD + ENVELOPE  # 2 163 472 : la meme, relative a l'enregistrement
TAIL_REC_NEW = TAIL_NEW + ENVELOPE  # 1 918 544
# La FIN DES KITS deployes, relative a l'en-tete. Ce n'est PAS une somme des deux tailles :
# c'est un DECALAGE, et il suit les kits quand ils demenagent. En v6 les deux coincidaient
# (2 948 188 + 681 024 = 3 629 212 = « total des tables + 28 ») — c'est cette coincidence qui
# a fait ecrire la mauvaise formule au §3.56, et le pointeur de la queue tombait alors dans les
# donnees de l'OS. Voir notes/56 §3.57.
DEPLOYED_TAIL_OLD = KITS_OLD_OFFSET + 96 * 7094                 # 3 629 212
DEPLOYED_TAIL_NEW = KITS_NEW_OFFSET + PATTERN_COUNT * 7294      # 58 083 132

# --- L'INIT DES KITS ET DES PATTERNS : DES VALEURS DERIVEES MANQUEES (§3.61) --------
# La fonction 0x40061738 (appelee au chargement/materiel avec l'en-tete) initialise les
# kits 1..95 depuis le kit 0, puis les 80 patterns depuis le pattern 0. Le triage ne
# listait que les valeurs DE BASE (offset des kits, fin des kits, 7 094, 30 710) : trois
# valeurs DERIVEES et deux deplacements 16 bits manquaient, et le demarrage se figeait
# (digiemu : 99,4 % des 315 501 memcpy du demarrage reviennent a la boucle, sans aucune
# violation memoire).
#
#   borne 673930 = 96 x 7094 - 7094 (tous les creneaux sauf le modele). Le pas est passe
#       a 7 294 mais la borne est restee : d3 ne l'atteint plus jamais -> BOUCLE INFINIE.
#       Nouveau : 80 creneaux - 1, au pas 7 294 : 79 x 7294 = 576 226 ;
#   base source 2955282 = 2948188 + 7094 (offset des kits + un creneau : le modele est
#       le creneau 0). Nouveau : 57499612 + 7294 = 57 506 906 ;
#   n et pas 30710 (pea/lea 16 bits : invisibles au balayage 32 bits) -> 40 924 ;
#   champ d'index 30734 = 30710 + 24 (la fin de l'enregistrement, moins 4 : le contenu
#       commence a +28) -> 40 924 + 24 = 40 948.
KIT_INIT_BOUND_OLD = 95 * 7094             # 673 930
KIT_INIT_BOUND_NEW = (PATTERN_COUNT - 1) * 7294    # 79 x 7294 = 576 226 (80 creneaux)
KIT_INIT_SRC_OLD = KITS_OLD_OFFSET + 7094         # 2 955 282
KIT_INIT_SRC_NEW = KITS_NEW_OFFSET + 7294         # 57 506 906

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

# --- LA GEOMETRIE D'ORIGINE, VERIFIEE EN ENTIER (§3.56) ----------------------------------
# Le balayage ci-dessus est mene VALEUR PAR VALEUR, sur des listes ecrites a la main. Une
# valeur DERIVEE — l'enregistrement stocke (image + enveloppe), la queue de 512 o qui finit sur
# le sceau de cloture, le total des deux tables deployees — n'y est que si on l'y a mise ; et
# c'est exactement ce qui a manque au jalon 2 (plantage du 16/10).
#
# GEOMETRY est le controle INVERSE : on reprend toute la geometrie d'origine et on exige
# qu'aucun de ses immediats ne survive dans l'image patchee, hors de la chaine de versions
# (dont la sortie est un bloc v6, et qui doit donc garder ses valeurs). Ajouter une valeur ici
# quand la geometrie change : c'est ce qui empeche l'oubli de recommencer.
#
# Les trois valeurs de STOCKAGE — l'en-tete (0x406fa024), la base de la table des patterns
# (0x406fa040) et l'enregistrement stocke (2 163 988) — sont volontairement ABSENTES (§3.60) :
# elles ne doivent pas changer, et c'est le controle de la REGION qui exige qu'elles
# SURVIVENT. Les mettre ici serait l'echec permanent du controle.
GEOMETRY = [
    (IMAGE_OLD, "imm", "taille du bloc projet"),
    (CLOSING_OLD, "imm", "sceau de cloture du bloc"),
    # L'INIT DES KITS (§3.61) : la borne (95 x 7094) et la base source (offset + 7094) sont
    # des valeurs DERIVEES que le triage ne listait pas — la borne oubliee figeait le
    # demarrage. Le controle les exige disparues, comme le reste de la geometrie de bloc.
    (KIT_INIT_BOUND_OLD, "imm", "borne de la boucle d'init des kits (95x7094)"),
    (KIT_INIT_SRC_OLD, "imm", "base source de l'init des kits (offset+7094)"),
    (TAIL_OLD, "imm", "queue de 512 o, relative a l'image"),
    (TAIL_REC_OLD, "imm", "queue de 512 o, relative a l'enregistrement"),
    (DEPLOYED_TAIL_OLD, "imm", "fin des kits deployes (relative a l'en-tete)"),
    (1425408, "imm", "fin des blocs ranges du bloc courant"),
    (1425920, "imm", "base des kits dans le fichier"),
    (1426192, "imm", "base des kits dans l'image"),
    (2948160, "imm", "fin de la table des patterns deployes"),
    (2948188, "imm", "offset des kits (relatif a l'en-tete)"),
    (681024, "imm", "fin de la table des kits deployes"),
    (26310, "imm", "borne de la queue deployee"),
    (30710, "imm", "enregistrement deploye"),
    (14848, "imm", "creneau range"),
    (7094, "imm", "kit deploye"),
    # les memes pas, vus en deplacement de 16 bits (l'autre moitie du balayage)
    (14848, "tout", "creneau range (deplacement)"),
    (7094, "tout", "kit deploye (deplacement)"),
    (600, "absolu", "aire par kit par piste"),
    (4332, "registre", "taille des pas"),
    (4336, "registre", "offset de la queue"),
]

# --- LE CONTROLE DE LA VERSION (§3.57) ---------------------------------------------------
# Le sceau 0xBEEFBACE et le sceau de cloture 0xBACEF00C marquent le BLOC PROJET : tout site qui
# les ecrit ou les compare fixe aussi la VERSION du bloc, qui vaut 7 depuis ce mod. Le triage
# du jalon 2 n'en listait que trois — deux ecritures et la fin de chaine — et deux autres sont
# restes en 6, dont le VALIDEUR DU DEPLOIEMENT : la chaine acceptait le bloc v7 et le
# deploiement le refusait ensuite (notes/56 §3.57).
#
# Ce controle reprend donc TOUS les sites de sceau et exige 7. Les seules exceptions sont les
# sceaux d'AUTRES enregistrements — les morceaux de 100 o des kits et des machines, qui portent
# leur propre version 2 (notes/56 §3.54) — et la chaine de versions, dont la sortie est un bloc
# v6 (LEGACY, deja exclue).
SEAL_EXCUSES = {
    0x4005AFC0: "sceau d'un enregistrement de 100 o (machine) : sa version est 2",
    0x4005B01A: "sceau de cloture du meme enregistrement de 100 o",
    0x4005B074: "sceau d'un enregistrement de 100 o (machine)",
    0x4005B0CE: "sceau de cloture du meme enregistrement de 100 o",
}

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
    628: (828, [0x40009AB2, 0x40009AC4, 0x40009B76, 0x4000A564, 0x4005B31E, 0x400613EA,
                 0x40009C4A, 0x40009F8A, 0x4000A0D6, 0x4005D140]),
    694: (894, [0x40009AC0, 0x4005B32C, 0x4005D160, 0x400613F4]),
    632: (832, [0x40009B6A, 0x4005B322, 0x4005D13A]),
    708: (908, [0x40009B64, 0x4000A552, 0x4005B330, 0x4005D15C]),
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
    # L'EN-TETE DE PROJET (0x406fa024) ET LA BASE DE LA TABLE DES PATTERNS (0x406fa040) NE
    # SONT PLUS PATCHES (§3.60) : la chaine des convertisseurs ecrit 2 163 716 o dans l'image
    # a chaque demarrage, AVANT tout controle, et la region image -> en-tete doit tenir ce
    # bloc. Le controle de la REGION (plus bas) exige que leurs sites SURVIVENT — c'est lui
    # qui a ete vu echouer sur l'ancien triage (7 et 6 sites, le plantage du 16/10).
    (KITS_OLD_OFFSET, KITS_NEW_OFFSET, 6, "offset des kits (relatif a l'en-tete)"),
    # LES VALEURS DERIVEES DU BLOC (§3.56) : la queue de 512 o se termine sur le sceau de
    # cloture, et la fin des kits deployes est un DECALAGE qui suit les kits. Le triage du
    # jalon 2 ne les avait pas : le chemin sauvegarde/chargement ecrivait donc 244 928 o
    # au-dela de l'enregistrement — dans l'en-tete de projet et la table des patterns
    # deployes. Plantage du 16/10 sur la machine. GEOMETRY (plus bas) est le controle qui
    # rend cet oubli impossible a refaire.
    # L'ENREGISTREMENT STOCKE, lui, n'est PAS patche (§3.60) : sa taille (2 163 988) est de
    # la geographie de stockage, comme l'en-tete et la base de la table. Le bloc v7
    # (1 918 788 o) y tient avec de la marge. Ses trois sites (0x400431c4, 0x400431d0,
    # 0x4008da5e — l'enveloppe 0x404e9b10) sont couverts par le controle de la REGION,
    # qui exige qu'ils SURVIVENT.
    (TAIL_OLD, TAIL_NEW, 4, "queue de 512 o, relative a l'image"),
    (TAIL_REC_OLD, TAIL_REC_NEW, 1, "queue de 512 o, relative a l'enregistrement"),
    (DEPLOYED_TAIL_OLD, DEPLOYED_TAIL_NEW, 4, "fin des kits deployes (relative a l'en-tete)"),
    # L'INIT DES KITS (§3.61) : la borne et la base source sont des valeurs DERIVEES
    # (total moins un creneau, offset plus un creneau) que le triage ne listait pas. La
    # borne restee en 95 x 7094 avec un pas de 7 294 figeait le demarrage (boucle infinie
    # sans aucune violation : 99,4 % des memcpy du demarrage). Sites uniques, vus a
    # l'audit (0x400617be, 0x400617a4).
    (KIT_INIT_BOUND_OLD, KIT_INIT_BOUND_NEW, 1,
     "borne de la boucle d'init des kits : 95x7094 -> 79x7294 (§3.61)"),
    (KIT_INIT_SRC_OLD, KIT_INIT_SRC_NEW, 1,
     "base source de l'init des kits : kits_off+7094 (§3.61)"),
]

# --- tailles et decalages en deplacement 16 bits -------------------------

# --- tailles et decalages en deplacement 16 bits -------------------------
# ATTENTION : le tri par « usage absolu » ne suffit pas — il depend de la VALEUR.
#   - `pea.l $3a00.w`     (absolu)  = une TAILLE a changer ;
#   - `pea.l $10f0(a3)`   (registre) = un DECALAGE dans l'enregistrement, a changer aussi ;
#   - `clr.l $258(a2)`    (registre) = une COINCIDENCE, a LAISSER.
DISPLACEMENTS = [
    # decalages dans l'enregistrement : usage par registre, a changer
    (4336, 5780, "registre", 5, "offset de la queue dans le pattern range"),
    # 30706 -> 40920 et 30642 -> 40856 : RETIRES (§3.62). Les nouvelles valeurs
    # depassent 0x7FFF et l'adressage 16 bits ETEND LE SIGNE (le piege a signe) : sept
    # sites ecrivant/lisant a -24xxx au lieu de +40xxx, sans aucune violation. Le lot
    # d'execution reverra chaque site avec une forme 32 bits (cave ou audible).
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
    # (0x4005b946). RETIRE (§3.62) : 40920 ne tient pas en deplacement 16 bits (signe).
    # Le lot d'execution reverra ce site avec une forme 32 bits (cave).
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
    # DEUX SITES OUBLIES PAR LE TRIAGE (§3.57) : un troisieme ECRIVAIN de bloc et le VALIDEUR
    # DU DEPLOIEMENT. Le second est le plus grave : la chaine acceptait le bloc v7 (controle de
    # fin de chaine, ci-dessus) et le deploiement le refusait ensuite, en exigeant 6 — l'OS ne
    # pouvait donc pas materialiser son propre projet.
    (0x4005D3C4, "7006", "7007", "ecriture d'un bloc : version 6 -> 7 (sceau et sceau de cloture)"),
    (0x4005D43A, "7006", "7007", "valideur du deploiement : version 6 -> 7"),
    # L'INIT DES PATTERNS (§3.61) : trois deplacements 16 bits que les balayages par valeur
    # ne voyaient pas (ni IMMEDIATES 32 bits, ni ligne DISPLACEMENTS pour 30 710).
    # RETIRES (§3.62) : 40924/40948 ne tiennent pas en 16 bits signes (le piege a signe :
    # `pea $9fdc` pousse -24612). La boucle entiere part en cave (FILL, plus bas).
]

# La garde du nombre de patterns : `moveq #95` -> `moveq #79` (l'index maximal).

# La garde du nombre de patterns : `moveq #95` -> `moveq #79` (l'index maximal).
GUARD_VA = 0x400083BA

# --- LE REMPLISSAGE EN CAVE (§3.62) -----------------------------------------------------
# La seconde boucle de 0x40061738 (80 patterns depuis le modele) demande n = pas =
# 40 924 et index 40 948 : trois 16 bits qui ETENDENT LE SIGNE. La boucle part en cave :
# le masque de sprite 0x4018a788 (damier inverse, 1024 o tout 0xFF — le registre des
# masques tools/sprites.py, meme mecanisme que 58 : son constructeur est redirige vers
# le masque partage, identique octet pour octet, donc le rendu ne change pas). Son
# masque a lui, pas celui de 58 : la combinaison 56+57 seule reste constructible
# (la colle n'y tourne que sur le chemin de refus, justement celui que 56+57 exerce).
FILL_SRC = HERE / "machines" / "groove" / "fill_patterns.S"
FILL_MASK = 0x4018A788
FILL_OFF = 0
FILL_RESERVE = 64                    # assez pour la boucle (~58 o) ; garde-fou
FILL_LOOP = 0x400617DA               # `clrl %d3` : tete de la seconde boucle
FILL_LOOP_END = 0x40061800           # l'epilogue (moveml), cible du bra
FILL_LOOP_DEAD = (0x400617E2, 0x400617FA)   # corps mort, remplace par des nop
FILL_SIBLINGS = ("56-groove-8tracks.json", "58-groove-convert.json")

# --- LES COMPTES DE PATTERNS/KITS OUBLIES (§3.57) ---------------------------------------
# Le triage du jalon 2 n'en listait que TROIS (plus la garde ci-dessus). La revue complete des
# `moveq #96/#95` — tous registres, et seulement ceux dont le voisinage IMMEDIAT utilise une
# constante du pattern ou du kit — en a trouve DOUZE de plus : des boucles sur les creneaux de
# kit (pas 7 680 et pas range 14 848), des bornes d'indice de pattern range et des clamps
# d'indice de kit. Chacun est nomme ici, et le generateur verifie l'opcode et la valeur.
#
# Ce qui a ete ECARTE, et pourquoi (c'est COUNT_EXCUSES plus bas, verifie par le controle) :
#   - le banc de SONS : 96 enregistrements de 732 o a +5 192 (`movel #732`) — 17 sites ;
#   - 96 SONS indexant des enregistrements de 28 o (le descripteur de machine, §3.29.d) ;
#   - les 96 PROJETS du +Drive (`jsr 0x4008c2c2` sur le gestionnaire de projets).
PATTERN_COUNTS = [
    (0x4000EDFE, 95, 79, "kit range : borne d'indice (acces -7680 x i, base fichier)"),
    (0x4000EE32, 95, 79, "pattern range : borne d'indice (pas 14 848, base 512)"),
    (0x4000EE5E, 95, 79, "kit range : borne d'indice (acces -7680 x i)"),
    (0x4000EE92, 95, 79, "pattern range : borne d'indice (pas 14 848, base 512)"),
    (0x4000EF26, 96, 80, "boucle de balayage des creneaux de kit ranges (pas 7 680)"),
    (0x4000F0B6, 95, 79, "kit range : borne d'indice (acces -7680 x i)"),
    (0x4000F0EE, 95, 79, "pattern range : borne d'indice (pas 14 848, base 512)"),
    (0x4000F11C, 95, 79, "kit range : borne d'indice (acces -7680 x i)"),
    (0x4000F154, 95, 79, "pattern range : borne d'indice (pas 14 848, base 512)"),
    (0x4005D556, 96, 80, "boucle des kits : deploye 7 094 et creneau range 7 680"),
    (0x400617FA, 96, 80, "boucle des kits ranges (pas 7 094)"),
    (0x4006A418, 96, 80, "bloc courant : borne d'indice de pattern"),
]

# Le controle des comptes (§3.57) : tout `moveq #96/#95` dont le voisinage (COUNT_WINDOW)
# utilise une constante du pattern ou du kit doit etre CHANGE — sauf justification ci-dessous.
COUNT_GEOM = [14848, 30710, 7094, 4332, 4336, 7680, 1425408, 1425920, 1426192,
              2948160, 2948188, 2163712, 2163716, 3629212, 26310, 681024]
COUNT_WINDOW = 80
# Le banc de SONS (96 enregistrements de 732 o a +5 192) : il n'est atteint par ce controle que
# la ou son voisinage touche AUSSI la geometrie du pattern — un seul site. Les seize autres
# sites du banc n'ont aucune constante de pattern autour d'eux : ils ne sont pas des candidats,
# et les inscrire ici serait une justification qui ne verifie rien.
COUNT_EXCUSES = {
    0x4000ECE0: "banc de sons (96 x 732 o a +5 192) ; la constante 30 710 du voisinage est "
                "celle du motif deploye, pas de ce site",
}
# et les cinq sites hors du banc de sons, chacun avec sa raison :
COUNT_EXCUSES.update({
    0x4000FE66: "96 = les 96 PROJETS du +Drive (jsr 0x4008c2c2, gestionnaire de projets)",
    0x4000FF50: "96 = les 96 PROJETS du +Drive (jsr 0x4008c2c2)",
    0x40010056: "96 = les 96 PROJETS du +Drive (jsr 0x4008c2c2)",
    0x40020380: "indice de SONS : l'accesseur 0x4000eb90 (banc de 732 o) suit",
    0x4008C430: "96 = les 96 SONS de la banque (enregistrements de 28 o, §3.29.d)",
})

# --- LES BORNES D'INTERFACE : LA SELECTION DE PISTE (§3.31.c, §3.34.a, §3.32.b) ---------
# La machine n'a que six pads, mais l'interface doit compter HUIT pistes. On elargit donc le
# chemin de SELECTION : le menu de pistes, la liste « Track %d », les bornages d'indice et les
# gardes des actions de piste (Copy/Paste/Clear TRK).
#
# Ce qui est LAISSE, et pourquoi :
#   - les boucles qui parcourent les 6 PADS (0x4001cfb6, 0x4001d5d2, 0x4001d74e, 0x40020a42) :
#     le panneau a six pads, c'est la contrainte materielle ; la page 2 de Kevin rebranche
#     seulement DEUX de ces pads sur les pistes 7-8 ;
#   - les bornes de MACHINE (0x4001b696 : l'indice est multiplie par 28, la taille du
#     descripteur, §3.29.d) : les elargir serait une corruption silencieuse ;
#   - les boucles dont le role n'est pas encore tranche (0x400231c2, 0x4002fa10, 0x4002fade,
#     0x4001b086, 0x4001b092, 0x40022ec2) : voir §3.55.
#
# Chaque site est verifie : l'octet de gauche doit etre un `moveq` (0x70..0x77) et celui de
# droite la valeur attendue. C'est le meme controle que pour la garde du nombre de patterns.
UI_TRACK_BOUNDS = [
    (0x4002399A, 5, 7, "garde d'action de piste (Copy/Paste/Clear TRK)"),
    (0x40023CA2, 5, 7, "bornage de l'indice de piste"),
    (0x40023CA8, 5, 7, "bornage de l'indice de piste (valeur par defaut)"),
    (0x40023D98, 5, 7, "menu de selection de piste : une entree par piste"),
    (0x40023EFA, 5, 7, "garde d'action de piste (Copy/Paste/Clear TRK)"),
    (0x40024960, 5, 7, "garde d'indice"),
    (0x4002B9B4, 5, 7, "bornage d'indice"),
    (0x4002B9BC, 5, 7, "bornage d'indice (valeur par defaut)"),
    (0x40028EE2, 6, 8, "la liste des pistes (« Track %d »)"),
]

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


def versions_near(stock, va, back=40, span=80):
    """Les numeros de version utilises pres d'un site de sceau, vus dans les OCTETS.

    On cherche les `moveq #N,%dX` de la fenetre — opcode 0x70..0x77 puis l'immediat. C'est
    volontairement un balayage d'OCTETS, pas un desassemblage : capstone rend une liste VIDE
    sur certaines plages (donnees, instructions EMAC), et un controle vide passe alors sans
    rien voir. C'est exactement ce qui est arrive au premier essai de ce controle (§3.57) :
    il fallait le test de defaillance pour s'en apercevoir.
    """
    out = []
    lo = max(0, va - BASE - back)
    hi = min(len(stock) - 1, va - BASE + span)
    for o in range(lo, hi):
        op = stock[o]
        if 0x70 <= op <= 0x77 and stock[o + 1] in (2, 6, 7):
            out.append((stock[o + 1], "%08x moveq #%d" % (BASE + o, stock[o + 1])))
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


def assemble(src):
    """Assemble et LIE fill_patterns.S (natif, sinon WSL — comme gen_groove_convert).

    Le lien est obligatoire (§7 du HANDOFF) : un appel absolu non resolu sauterait a
    l'adresse zero. Ici tout est relatif ou par registre, et le lien le prouve.
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
    print("            en-tete %#x et patterns %#x : ADRESSES D'ORIGINE (§3.60)"
          % (HEADER_OLD, PATTERNS_OLD))
    print("            enregistrement stocke %d o : TAILLE D'ORIGINE (§3.60)" % RECORD_OLD)
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

    # les douze comptes de patterns/kits retrouves par la revue (§3.57)
    for va, old, new, role in PATTERN_COUNTS:
        op = stock[va - BASE]
        val = stock[va - BASE + 1]
        if not (0x70 <= op <= 0x77):
            bad.append("%s : %#x n'est pas un moveq (opcode %02x)" % (role, va, op))
            continue
        if val != old:
            bad.append("%s : la valeur en %#x est %d, attendue %d" % (role, va, val, old))
            continue
        writes.append((va, bytes([op, old]), bytes([op, new]), "compte : " + role))
    if not args.audit:
        print("  compte  %-46s %2d site(s) de plus" % ("patterns et kits", len(PATTERN_COUNTS)))

    # les bornes d'interface du chemin de selection de piste
    for va, old, new, role in UI_TRACK_BOUNDS:
        op = stock[va - BASE]
        val = stock[va - BASE + 1]
        if not (0x70 <= op <= 0x77):
            bad.append("%s : %#x n'est pas un moveq (opcode %02x)" % (role, va, op))
            continue
        if val != old:
            bad.append("%s : la valeur en %#x est %d, attendue %d" % (role, va, val, old))
            continue
        writes.append((va, bytes([op, old]), bytes([op, new]), "piste : " + role))
    if not args.audit:
        print("  piste   %-46s %2d borne(s) d'interface" % ("selection de piste",
                                                            len(UI_TRACK_BOUNDS)))

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

    # --- LE REMPLISSAGE EN CAVE (§3.62) ------------------------------------------------
    code = assemble(FILL_SRC)
    stub_va = FILL_MASK + FILL_OFF
    mask_size = sprites.MASKS[FILL_MASK][0]
    mask_ref = sprites.MASKS[FILL_MASK][1]
    bra_disp = FILL_LOOP_END - (FILL_LOOP + 8)   # depuis 0x400617e2 : +30 -> `601e`
    nop_lo, nop_hi = FILL_LOOP_DEAD
    nop_old = stock[nop_lo - BASE:nop_hi - BASE]
    nop_new = b"\x4e\x71" * (len(nop_old) // 2)   # 24 o = DOUZE nop (2 o chacun)
    print("remplissage : %d octet(s) assembles et lies -> %#x (masque %#x, %d o)"
          % (len(code), stub_va, FILL_MASK, mask_size))
    fill_bad = []
    if len(code) > FILL_RESERVE:
        fill_bad.append("le remplissage (%d o) depasse sa reserve (%d o en %#x)"
                        % (len(code), FILL_RESERVE, stub_va))
    if stock[stub_va - BASE:stub_va - BASE + len(code)] != b"\xff" * len(code):
        fill_bad.append("la cave %#x n'est pas en 0xFF dans l'image d'origine" % stub_va)
    if stock[FILL_MASK - BASE:FILL_MASK - BASE + mask_size] != b"\xff" * mask_size:
        fill_bad.append("le masque %#x (%d o) n'est pas entierement 0xFF : pas libre"
                        % (FILL_MASK, mask_size))
    if stock[mask_ref - BASE:mask_ref - BASE + 4] != FILL_MASK.to_bytes(4, "big"):
        fill_bad.append("la constante du constructeur en %#x ne vaut pas %#x"
                        % (mask_ref, FILL_MASK))
    if not (-128 <= bra_disp <= 127):
        fill_bad.append("le bra vers %#x sort du .b : %d" % (FILL_LOOP_END, bra_disp))
    if stock[FILL_LOOP - BASE:FILL_LOOP + 6 - BASE].hex() != "4283487877f6":
        fill_bad.append("la tete de boucle en %#x n'est pas `clrl %%d3; pea $77f6`"
                        % FILL_LOOP)
    if stock[FILL_LOOP + 6 - BASE:FILL_LOOP + 8 - BASE].hex() != "2f04":
        fill_bad.append("l'octet du bra en %#x n'est pas `movel %%d4,%%sp@-`" % (FILL_LOOP + 6))
    # recouvrement : nos ecritures contre les JSON valides de 56 et 58 (comme 58).
    # Tout en offsets (w["off"] est un offset) : ne pas melanger avec des VA.
    spans = [(FILL_LOOP - BASE, FILL_LOOP - BASE + 8),
             (nop_lo - BASE, nop_hi - BASE),
             (stub_va - BASE, stub_va - BASE + len(code)),
             (mask_ref - BASE, mask_ref - BASE + 4)]
    for name in FILL_SIBLINGS:
        sib = json.loads((OUT.parent / name).read_text(encoding="utf-8"))
        for w in sib["writes"]:
            lo, hi = w["off"], w["off"] + len(bytes.fromhex(w["old"]))
            for a, b in spans:
                if lo < b and a < hi:
                    fill_bad.append("%s ecrit en %#x..%#x, qui recouvre notre %#x..%#x"
                                    % (name, lo + BASE, hi + BASE, a + BASE, b + BASE))
    if fill_bad:
        for b in fill_bad:
            print("  !! " + b)
        raise SystemExit("!! le logement du remplissage est faux (notes/56 §3.62).")
    writes.append((FILL_LOOP, bytes.fromhex("4283487877f6"),
                   bytes.fromhex("4eb9%08x" % stub_va),
                   "init des patterns : jsr vers le remplissage en cave (§3.62)"))
    writes.append((FILL_LOOP + 6, bytes.fromhex("2f04"),
                   bytes.fromhex("60%02x" % (bra_disp & 0xFF)),
                   "init des patterns : bra par-dessus la boucle morte (§3.62)"))
    writes.append((nop_lo, nop_old, nop_new,
                   "init des patterns : boucle morte neutralisee (%d nop, §3.62)"
                   % (len(nop_old) // 2)))
    writes.append((stub_va, b"\xff" * len(code), code,
                   "init des patterns : la boucle en 32 bits (%d o, §3.62)" % len(code)))
    writes.append((mask_ref, struct.pack(">I", FILL_MASK),
                   struct.pack(">I", sprites.SHARED_MASK),
                   "init des patterns : le sprite damier inverse vers le masque partage (§3.62)"))
    print("logement    : jsr %#x, bra %#x, %d nop, cave %#x (%d o) + redirection %#x"
          % (FILL_LOOP, FILL_LOOP_END, len(nop_old) // 2, stub_va, len(code), mask_ref))

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

    # --- LE CONTROLE DES VALEURS DERIVEES (§3.56) ------------------------------------------
    stale = []
    for value, mode, what in GEOMETRY:
        found = (find_imm_sites(patched, value) if mode == "imm"
                 else find_disp_sites(patched, value, mode))
        for va in found:
            if in_legacy(va) is None and va not in EXCLUDE:
                stale.append("%s : %d survit en %#x" % (what, value, va))
    if stale:
        for s in stale:
            print("  !! " + s)
        raise SystemExit(
            "!! une valeur de la geometrie d'origine survit hors de la chaine de versions :\n"
            "   le balayage par valeur est INCOMPLET (notes/56 §3.56). Ajouter la valeur\n"
            "   manquante a IMMEDIATES/DISPLACEMENTS, ou le site a EXCLUDE s'il s'agit d'une\n"
            "   coincidence de donnee.")
    print("controle : aucune des %d valeurs de la geometrie d'origine ne survit hors de la "
          "chaine" % len(GEOMETRY))

    # --- LE CONTROLE DU SIGNE (§3.62) ---------------------------------------------------
    # Les formes d'adressage 16 bits (absolu court, deplacement) ETENDENT LE SIGNE : une
    # valeur >= 0x8000 y devient negative. `pea $9fdc` pousse -24612 au lieu de 40924, et
    # `lea %a2@(0x9fdc)` recule au lieu d'avancer — copie vide et ecritures a rebours,
    # sans aucune violation (vu par piege memcpy : n = 0xFFFF9FDC, pas de -24612).
    # Sont exempts : les moveq (donnee, pas adresse — reconnus par PROVENANCE, pas par
    # octet : 0x77f2 commence aussi par 0x77 !) et les immediats 32 bits. Ce controle
    # aurait pris les 11 sites fautifs a la generation.
    moveq_offs = {GUARD_VA - BASE}
    moveq_offs.update(va - BASE for va, _, _, _ in PATTERN_COUNTS)
    moveq_offs.update(va - BASE for va, _, _, _ in UI_TRACK_BOUNDS)
    badsign = []
    for w in uniq:
        ob = bytes.fromhex(w["old"])
        nb = bytes.fromhex(w["new"])
        if len(nb) != len(ob):
            badsign.append("off %-8d  %d o -> %d o : une ecriture ne change jamais de taille"
                           % (w["off"], len(ob), len(nb)))
            continue
        if len(ob) == 2 and int(nb.hex(), 16) >= 0x8000 and w["off"] not in moveq_offs:
            badsign.append("off %-8d  %s -> %s" % (w["off"], w["old"], w["new"]))
    if badsign:
        for b in badsign:
            print("  !! " + b)
        raise SystemExit(
            "!! une ecriture 16 bits porte >= 0x8000 hors moveq : l'adressage 16 bits\n"
            "   ETEND LE SIGNE (notes/56 §3.62). Le site demande 32 bits (cave) ou une\n"
            "   valeur qui tient.")
    print("controle : aucune ecriture 16 bits d'adresse ne porte >= 0x8000")

    # --- LE CONTROLE DE LA REGION (§3.60) ---------------------------------------------------
    # La chaine des convertisseurs ecrit son bloc v6 (2 163 716 o, une constante de SON
    # code, dans LEGACY) DANS l'image, A CHAQUE DEMARRAGE, AVANT tout controle : le projet
    # d'usine est un bloc v5 qui traverse la chaine. La region image -> en-tete doit donc
    # tenir ce bloc. Le jalon 2 avait rapproche l'en-tete d'autant que le bloc avait
    # raccourci : la chaine ecrasait l'en-tete et le debut de la table deployee (plantage
    # du 16/10, notes/56 §3.60). Ce controle est l'INVERSE du precedant : la region doit
    # tenir le bloc, et la GEOGRAPHIE DE STOCKAGE — l'en-tete, la base de la table des
    # patterns et l'enregistrement stocke — doit SURVIVRE au patch, aux mains de toute la
    # ligne (56 et 58 compris).
    IMAGE_VA = 0x404E9C20            # ou l'OS depose l'image projet
    CHAIN_BLOCK = 2163716            # le plus grand bloc que la chaine ecrit (v5 -> v6)
    if HEADER_OLD - IMAGE_VA < CHAIN_BLOCK:
        raise SystemExit(
            "!! la region image -> en-tete ne tient que %d o, et la chaine en ecrit %d : "
            "notes/56 §3.60" % (HEADER_OLD - IMAGE_VA, CHAIN_BLOCK))
    line = [{"id": "x", "order": 57, "section": 3, "device": "Model:Cycles", "os": "1.13",
             "writes": uniq}]
    for name in ("56-groove-8tracks.json", "58-groove-convert.json"):
        sib = OUT.parent / name
        if sib.exists():
            line.append(json.loads(sib.read_text(encoding="utf-8")))
    patched_line, _ = build.apply_writes(stock, sorted(line, key=lambda t: t["order"]))
    moved = []
    for value, what in ((HEADER_OLD, "l'en-tete de projet"),
                        (PATTERNS_OLD, "la base de la table des patterns deployes"),
                        (RECORD_OLD, "la taille de l'enregistrement stocke")):
        before = sorted(va for va in find_imm_sites(stock, value)
                       if va not in EXCLUDE and in_legacy(va) is None)
        after = sorted(va for va in find_imm_sites(patched_line, value)
                      if va not in EXCLUDE and in_legacy(va) is None)
        if not before:
            moved.append("%s (%#x) : AUCUN site dans le stock — la constante est fausse"
                         % (what, value))
            continue
        gone = [va for va in before if va not in after]
        if gone:
            moved.append("%s (%#x) : %d site(s) reecrit(s) : %s"
                         % (what, value, len(gone), ", ".join("%08x" % va for va in gone)))
    if moved:
        for m in moved:
            print("  !! " + m)
        raise SystemExit(
            "!! la geographie de stockage a ete deplacee : l'en-tete, la table des patterns\n"
            "   et l'enregistrement stocke doivent rester a leurs adresses et tailles\n"
            "   d'ORIGINE (notes/56 §3.60) : la chaine des convertisseurs ecrit 2 163 716 o\n"
            "   dans l'image a chaque demarrage, AVANT le controle de fin de chaine.")
    span_end = PATTERNS_OLD + 96 * 30710 + 96 * 7094   # fin de l'aire deployee d'origine
    table_end = PATTERNS_OLD + PATTERN_COUNT * PATTERN_SIZE
    if table_end > span_end:
        raise SystemExit(
            "!! la table des patterns deployes finit a %#x, hors de l'aire d'origine "
            "(%#x) : notes/56 §3.60" % (table_end, span_end))
    print("controle : la region tient le bloc de la chaine (%d o) ; en-tete, table et "
          "enregistrement stocke restent d'origine, et la table deployee finit a %#x, "
          "dans l'aire d'origine (%#x)"
          % (HEADER_OLD - IMAGE_VA, table_end, span_end))

    # --- LE CONTROLE DE LA VERSION (§3.57) -------------------------------------------------
    seal_sites = []
    for pat, what in ((struct.pack(">I", 0xBEEFBACE), "sceau de bloc"),
                      (struct.pack(">I", 0xBACEF00C), "sceau de cloture")):
        i = stock.find(pat)
        while i >= 0:
            seal_sites.append((BASE + i, what))
            i = stock.find(pat, i + 1)
    wrong = []
    for va, what in sorted(seal_sites):
        if in_legacy(va) or va in SEAL_EXCUSES:
            continue
        six = [w for v, w in versions_near(patched, va) if v == 6]
        if six:
            wrong.append("%s en %#x : %s" % (what, va, ", ".join(six)))
    if wrong:
        for w in wrong:
            print("  !! " + w)
        raise SystemExit(
            "!! un site de sceau n'utilise pas la version courante (7) : le triage des\n"
            "   versions est INCOMPLET (notes/56 §3.57). Ajouter le site a PATCHES, ou\n"
            "   la justification a SEAL_EXCUSES s'il s'agit d'un autre enregistrement.")
    print("controle : les %d sites de sceau n'utilisent que la version courante (7)"
          % len(seal_sites))

    # --- LE CONTROLE DES COMPTES DE PATTERNS/KITS (§3.57) -----------------------------------
    counts, excused = [], 0
    for o in range(0, len(stock) - 1, 2):
        op = stock[o]
        if not (0x70 <= op <= 0x77) or stock[o + 1] not in (96, 95):
            continue
        va = BASE + o
        lo, hi = max(0, o - COUNT_WINDOW), o + COUNT_WINDOW
        near = [v for v in COUNT_GEOM if stock.find(struct.pack(">I", v), lo, hi) >= 0]
        if not near:
            continue                      # rien a voir avec le pattern ni avec le kit
        if patched[o + 1] in (80, 79):
            continue
        if va in COUNT_EXCUSES:
            excused += 1
            continue
        counts.append("%#x : moveq #%d reste inchange (voisines %s)" % (va, stock[o + 1], near))
    if counts:
        for c in counts:
            print("  !! " + c)
        raise SystemExit(
            "!! un compte de patterns/kit n'a pas ete change (notes/56 §3.57).\n"
            "   L'ajouter a PATTERN_COUNTS, ou a COUNT_EXCUSES avec sa raison.")
    print("controle : les comptes de patterns/kits proches de la geometrie sont tous changes "
          "(%d justifies)" % excused)

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
            "L'EN-TETE DE PROJET ET LA BASE DE LA TABLE DES PATTERNS RESTENT AUX ADRESSES "
            "D'ORIGINE (0x406fa024 et 0x406fa040), et l'enregistrement stocke garde sa taille "
            "d'origine (2 163 988) : la chaine des convertisseurs de version ecrit son bloc v6 "
            "(2 163 716 octets) dans l'image A CHAQUE DEMARRAGE, avant tout controle, et la "
            "region image -> en-tete doit tenir ce bloc (notes/56 §3.60 ; c'est le plantage "
            "des premiers candidats : l'en-tete avait descendu, la chaine l'ecrasait). La "
            "table deployee (80 x 40 924 = 3 273 920 octets) finit DANS l'aire que les kits "
            "occupaient en stock ; seuls les kits demenagent, vers la plage libre de "
            "0x43dd0000.",
            "Les valeurs DERIVEES DU BLOC suivent (notes/56 §3.56) : la queue de 512 o passe "
            "de 2 163 200 a 1 918 272 (2 163 472 -> 1 918 544, relative a l'enregistrement) et "
            "la fin des kits deployes de 3 629 212 a 58 083 132 — un DECALAGE "
            "(kit_offset + kit_size), pas la somme des deux tables, les kits ayant demenage. "
            "Le triage du jalon 2 les avait oubliees : le chemin sauvegarde/chargement ecrivait "
            "244 928 o au-dela de l'enregistrement — dans l'en-tete de projet et la table des "
            "patterns deployes (plantage du 16/10). La TAILLE de l'enregistrement stocke, elle, "
            "ne change PAS : c'est de la geographie de stockage (§3.60), et le bloc v7 "
            "(1 918 788 o) y tient avec de la marge.",
            "La revue du 16/10 (notes/56 §3.57) a trouve DEUX autres sites de version restes "
            "en 6 — une ecriture de bloc et le VALIDEUR DU DEPLOIEMENT, qui refusait donc le "
            "bloc v7 que la chaine venait d'accepter — et DOUZE comptes de patterns/kits "
            "oublies (boucles sur les creneaux de kit, bornes d'indice de pattern range, "
            "clamps d'indice de kit). Le generateur porte maintenant QUATRE controles "
            "inverses : GEOMETRY (la geometrie de bloc d'origine doit avoir change), la "
            "REGION (§3.60 : l'en-tete, la base de la table et l'enregistrement stocke "
            "doivent SURVIVRE — la chaine ecrit 2 163 716 o dans l'image a chaque demarrage), "
            "les 36 sites de sceau (la version doit etre 7) et les comptes proches de la "
            "geometrie (96 -> 80, 95 -> 79). Chacun a ete vu echouer avant de passer.",
            "L'INIT DES KITS ET DES PATTERNS (notes/56 §3.61) : la fonction 0x40061738 "
            "remplit les creneaux depuis le creneau 0 au chargement. Le triage ne listait que "
            "les valeurs de base : la borne (95 x 7 094 = 673 930, restee avec un pas passe a "
            "7 294 — boucle infinie SANS aucune violation, 99,4 % des memcpy du demarrage, le "
            "demarrage ne stabilisait jamais) devient 79 x 7 294 = 576 226, la base source "
            "(offset + 7 094 = 2 955 282) devient 57 506 906. La seconde boucle (80 patterns, "
            "n = pas = 40 924, index 40 948) ne tient pas en 16 bits signes (§3.62 : `pea "
            "$9fdc` pousse -24612) et ColdFire n'a pas de deplacement 32 bits : elle part en "
            "cave (boucle `groove_fill`, 58 o en 0x4018a788 — le masque damier inverse, "
            "libere par redirection de son constructeur comme 58, jsr + bra par-dessus, "
            "corps mort en nop). Les champs 16 bits hors boucle (fin 40 920, -68 40 856) "
            "attendent le lot d'execution. 57 = 227 ecritures, et le generateur refuse "
            "desormais toute ecriture 16 bits d'adresse >= 0x8000 (controle du signe, qui "
            "aurait pris les 11 fautes).",
            "S'applique APRES 56-groove-8tracks.json (jalon 1, le moteur audio). Les kits "
            "demenagent vers la plage libre de 0x43dd0000.",
            "Avec ce tweak seul, la version du bloc courant passe a 7 : un projet d'origine "
            "est refuse proprement (code d'erreur dedie), ni lu de travers ni efface — et "
            "revenir a l'OS officiel le rend lisible. La CONVERSION v6 -> v7 est le tweak "
            "suivant (58-groove-convert, notes/56 §3.58 et §3.59) : la chaine produit un bloc "
            "v6, et le convertisseur l'accepte en le passant en v7. Construit en ligne de "
            "commande seulement, hors flasher. Genere par tools/gen_groove_pattern.py, "
            "notes/54-56.",
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
