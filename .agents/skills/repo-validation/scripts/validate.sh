#!/usr/bin/env bash
# Run the Modded Cycles validation suite (root AGENTS.md, "Validation before pushing") and print one summary table.
#
#   validate.sh                                   # every check that needs no firmware
#   validate.sh --quick                           # same, without the jsdom smoke test (no network needed)
#   validate.sh --cycles firmware/model-cycles_OS1.13.syx --syntakt firmware/Syntakt_OS1.42.syx \
#               --gen gen_tempo_max.py --proof test_tempo_max.py [--with 6ch-usbup,arp,...]
#   validate.sh --git origin/claude/some-open-pr  # also check overlaps/registry against open branches (repeatable)
#
# Firmware defaults: firmware/model-cycles_OS1.13.syx and firmware/Syntakt_OS1.42.syx when they exist.
# Logs go to build/validate/ (git-ignored). Exit status: 1 if any check FAILED; SKIPs are listed with their reason
# so they can be reported in the PR instead of being skipped silently.
set -uo pipefail
ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
cd "$ROOT"
LOG="build/validate"; mkdir -p "$LOG"

CYCLES=""; SYNTAKT=""; QUICK=0; GENS=(); PROOFS=(); WITH=""; GITS=()
[ -f firmware/model-cycles_OS1.13.syx ] && CYCLES=firmware/model-cycles_OS1.13.syx
[ -f firmware/Syntakt_OS1.42.syx ] && SYNTAKT=firmware/Syntakt_OS1.42.syx
while [ $# -gt 0 ]; do
  case "$1" in
    --cycles) CYCLES="$2"; shift 2 ;;
    --syntakt) SYNTAKT="$2"; shift 2 ;;
    --quick) QUICK=1; shift ;;
    --gen) GENS+=("$2"); shift 2 ;;
    --proof) PROOFS+=("$2"); shift 2 ;;
    --with) WITH="$2"; shift 2 ;;
    --git) GITS+=("$2"); shift 2 ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

ROWS=(); FAILED=0
row() { ROWS+=("$(printf '%-5s %-44s %s' "$1" "$2" "$3")"); }
run() {  # run <name> <command...>
  local name="$1"; shift
  local log="$LOG/$(echo "$name" | tr ' /' '__').log"
  if "$@" >"$log" 2>&1; then row PASS "$name" ""; else
    row FAIL "$name" "log: $log"; FAILED=1
    echo "---- FAIL: $name ($*)"; tail -n 15 "$log"; fi
}
skip() { row SKIP "$1" "$2"; }

have() { command -v "$1" >/dev/null 2>&1; }
M68K=""; for p in m68k-linux-gnu- m68k-elf-; do have "${p}as" && { M68K="$p"; break; }; done
UNICORN=0; python3 -c "import unicorn, numpy" 2>/dev/null && UNICORN=1

# 1. No firmware needed
run "py_compile tools/ tools/emu/" python3 -m py_compile tools/*.py tools/emu/*.py
run "gen_flasher_tweaks --check" python3 tools/gen_flasher_tweaks.py --check
GITARGS=(); for g in ${GITS[@]+"${GITS[@]}"}; do GITARGS+=(--git "$g"); done
run "check_overlaps" python3 tools/check_overlaps.py ${GITARGS[@]+"${GITARGS[@]}"}
run "registry --check" python3 tools/registry.py --check
[ ${#GITS[@]} -gt 0 ] && run "registry --git (open branches)" python3 tools/registry.py ${GITARGS[@]+"${GITARGS[@]}"} --out "$LOG/registry-git.md"
if [ "$M68K" = "m68k-linux-gnu-" ]; then run "relocate_6ch --check" python3 tools/relocate_6ch.py --check
elif [ -n "$M68K" ]; then skip "relocate_6ch --check" "needs m68k-linux-gnu binutils (m68k-elf as relaxes lea abs.l)"
else skip "relocate_6ch --check" "no m68k binutils"; fi
if have node; then
  run "webbuild_check.sh" tools/webbuild_check.sh
  run "webflash_check.sh" tools/webflash_check.sh
  if [ "$QUICK" = 1 ]; then skip "webflash_smoke.sh (synthetic)" "--quick"
  elif have npm; then run "webflash_smoke.sh (synthetic)" tools/webflash_smoke.sh
  else skip "webflash_smoke.sh (synthetic)" "no npm"; fi
else
  skip "webbuild/webflash checks" "no node"
fi

# 2. With the official files
if [ -z "$CYCLES" ]; then
  skip "firmware checks" "no model-cycles_OS1.13.syx (put it in firmware/)"
else
  if [ -n "$SYNTAKT" ]; then
    run "ref_mainos --check" python3 tools/ref_mainos.py --cycles "$CYCLES" --syntakt "$SYNTAKT" --check
    if [ "$QUICK" = 0 ] && have npm; then
      run "webflash_smoke.sh (real files)" tools/webflash_smoke.sh "$CYCLES" "$SYNTAKT"
    else skip "webflash_smoke.sh (real files)" "--quick or no npm"; fi
  else
    skip "ref_mainos --check, smoke (real files)" "no Syntakt_OS1.42.syx"
  fi
  for g in ${GENS[@]+"${GENS[@]}"}; do
    g="$(basename "$g")"; args=(--cycles "$CYCLES")
    grep -q '"--syntakt"' "tools/$g" && [ -n "$SYNTAKT" ] && args+=(--syntakt "$SYNTAKT")
    if [ -z "$M68K" ] && grep -q 'CROSS\|objcopy\|m68k' "tools/$g"; then skip "$g --check" "no m68k toolchain"
    else run "$g --check" python3 "tools/$g" "${args[@]}" --check; fi
  done
  for t in ${PROOFS[@]+"${PROOFS[@]}"}; do
    t="$(basename "$t")"
    if [ "$UNICORN" = 0 ]; then skip "$t" "pip install unicorn numpy"; continue; fi
    args=(--cycles "$CYCLES"); [ -n "$SYNTAKT" ] && grep -q '"--syntakt"' "tools/emu/$t" && args+=(--syntakt "$SYNTAKT")
    run "$t" python3 "tools/emu/$t" "${args[@]}"
    if [ -n "$WITH" ] && grep -q '"--with"' "tools/emu/$t"; then
      run "$t --with $WITH" python3 "tools/emu/$t" "${args[@]}" --with "$WITH"
    fi
  done
fi

echo
echo "==== validation summary ($(git rev-parse --abbrev-ref HEAD) @ $(git rev-parse --short HEAD))"
printf '%s\n' "${ROWS[@]}"
exit $FAILED
