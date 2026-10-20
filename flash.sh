#!/usr/bin/env bash
# flash.sh — installe les dépendances, vérifie le firmware et flashe le Model:Cycles.
# macOS et Linux. Windows : voir flash.bat.
#
# Usage :
#   ./flash.sh                      # auto-détecte le .syx, installe, vérifie, flashe
#   ./flash.sh mon.syx              # flashe ce fichier précis
#   ./flash.sh --verify mon.syx     # vérifie seulement (rien envoyé)
#
# ⚠️ Le flash se fait par l'entrée MIDI IN de l'appareil (jack TRS 3,5 mm) : interface à sortie
#    TRS + câble jack stéréo, ou interface DIN + adaptateur fourni. Jamais par l'USB.
#    Lis RECOVERY.md avant. Tu flashes à tes risques (garantie, brick possible mais récupérable par le MIDI IN).
set -euo pipefail
cd "$(dirname "$0")"

VENV=.venv
say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
err() { printf '\033[31m%s\033[0m\n' "$*" >&2; }

# ---- 1. arguments ------------------------------------------------------------
VERIFY_ONLY=0
SYX=""
for a in "$@"; do
  case "$a" in
    --verify) VERIFY_ONLY=1 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *.syx) SYX="$a" ;;
    *) err "argument inconnu : $a" ; exit 2 ;;
  esac
done

# auto-détection du .syx : priorité au *_mod.syx (firmware modifié) le plus récent
if [ -z "$SYX" ]; then
  SYX=$(ls -t ./*_mod.syx 2>/dev/null | head -1 || true)
  [ -z "$SYX" ] && SYX=$(ls -t ./model-cycles_OS*.syx 2>/dev/null | head -1 || true)
fi
if [ -z "$SYX" ] || [ ! -f "$SYX" ]; then
  err "Aucun fichier .syx trouvé."
  err "Construis d'abord un firmware modifié :"
  err "   python3 tools/build.py -i model-cycles_OS1.13.syx -t 6ch-multiout"
  err "…ou pose ton .syx ici et relance :  ./flash.sh mon.syx"
  exit 1
fi
say "Fichier ciblé : $SYX"

# ---- 2. Python 3 -------------------------------------------------------------
PY=""
for c in python3 python; do command -v "$c" >/dev/null 2>&1 && { PY=$(command -v "$c"); break; }; done
if [ -z "$PY" ]; then
  err "Python 3 est introuvable."
  if [ "$(uname)" = "Darwin" ]; then
    err "Installe-le : brew install python   (ou depuis python.org)"
  else
    err "Installe-le : sudo apt install python3 python3-venv python3-pip   (Debian/Ubuntu)"
    err "           ou sudo dnf install python3 python3-pip                (Fedora)"
  fi
  exit 1
fi
say "Python : $($PY --version 2>&1)"

# ---- 3. venv + dépendances (mido + python-rtmidi) ----------------------------
if [ ! -d "$VENV" ]; then
  say "Création de l'environnement Python (.venv)…"
  "$PY" -m venv "$VENV" || { err "Échec de la création du venv. Sous Debian/Ubuntu : sudo apt install python3-venv"; exit 1; }
fi
VPY="$VENV/bin/python"
say "Installation des dépendances (mido, python-rtmidi)…"
"$VPY" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
if ! "$VPY" -m pip install --quiet mido python-rtmidi; then
  err "Échec de l'installation de python-rtmidi."
  if [ "$(uname)" = "Linux" ]; then
    err "Il lui faut souvent les en-têtes ALSA. Installe-les puis relance :"
    err "   sudo apt install libasound2-dev libjack-dev build-essential   (Debian/Ubuntu)"
    err "   sudo dnf install alsa-lib-devel jack-audio-connection-kit-devel gcc-c++  (Fedora)"
  else
    err "Sous macOS, assure-toi d'avoir les outils Xcode : xcode-select --install"
  fi
  exit 1
fi

# ---- 4. vérification du fichier ---------------------------------------------
say "Vérification du fichier…"
"$VPY" tools/flash.py "$SYX" --verify
if [ "$VERIFY_ONLY" = 1 ]; then
  say "Vérification seule demandée. Rien n'a été envoyé."
  exit 0
fi

# ---- 5. rappel de branchement + flash ---------------------------------------
cat <<'EOF'

────────────────────────────────────────────────────────────────────────────
 AVANT DE CONTINUER
 1. Relie la sortie MIDI de ton interface au MIDI IN du Model:Cycles (jack TRS) :
    câble jack stéréo si l'interface a une sortie TRS, sinon DIN + adaptateur fourni.
 2. Sauvegarde tes projets (Elektron Transfer) — le flash peut les affecter.
 3. Passe l'appareil en mode réception :
        éteindre → maintenir [FUNC] → allumer → [TRIG 4] (OS UPGRADE)
    L'écran doit afficher « READY TO RECEIVE ».
 4. Garde ton .syx OFFICIEL sous la main : c'est ta récupération (même procédure).
────────────────────────────────────────────────────────────────────────────
EOF
say "Lancement du flasher (il te fera choisir le port et confirmer)…"
"$VPY" tools/flash.py "$SYX" --send
