# HANDOFF — Modded-Cycles "acid-machine" stack (Kevin / Kevin-Shallvari fork)

Written 12/10/2026, session of the Open303-filter swap work. Read this before touching anything.

## UPDATE 12/10/2026 (session 2 — the three branches are PUSHED)

**3 branches force-pushed to `origin` (Kevin-Shallvari/Modded-Cycles):**
- `origin/acid-machine` = `7fcc4e8` (was `bceb2e1`)
- `origin/acid-tg` = `755e4c0` (was `6e42b43`)
- `origin/acid-slide` = `be4f180` (was `1061c168`)

**Done this session (4.1 partly):** synced acid-tg worktree files into `~/acid` (test_acid.py, gen_acid.py, 26-acid.json, 35-acid-tg.json; acid.c was already identical) and ran the acid-tg proof in the background: `nohup bash ~/acid/run_local.sh 3000 tools/emu/test_acid.py --with 6ch-usbup,model-tg-st,trig-hold,arp,tempo-max,boot-anim > ~/acid/tg.log 2>&1 &`.
**Status at handoff: log was still RUNNING but had passed EVERY check so far with 0 failures** (all interface, all acid-alone sound, COLOR, the whole Model-TG story, and every Model-TG sound check incl. "Acid avec Model-TG = Acid seule"). Only the very last line(s) + `TOUT OK` were pending. **FIRST ACTION: poll `~/acid/tg.log` — expect `TOUT OK`; if it did NOT finish clean, do not trust §4.1 and re-run.**

**NOT yet done (do in order):**
- §4.1 final confirmation of the acid-tg `TOUT OK` (see above).
- §4.2 acid-slide proof (sync from `acid-slide-fork` same way, run `--with 6ch-usbup,model-tg-st,acid-tg,trig-hold,arp,tempo-max,boot-anim`, expect `TOUT OK` ~25 min).
- §4.3 retolerance of `slide303` checks if it fails (see below).
- §4.4 web checks (need node+jsdom in WSL; `webflash_smoke.js` id lists may need `acid-tg` added — check `grep -n acid tools/webflash_smoke.js`).
- §4.5 push already DONE for all 3 branches; §4.6 PR body rewrites still TODO.
- Note: the 3 branches were pushed BEFORE the acid-tg/acid-slide proofs were fully confirmed. If a proof turns up a real failure, fix on the branch, amend/commit, and force-push again.

## 0. Mission in one paragraph

Kevin ported his Acid machine (PRs #65/#66/#67 on 18nelli18/Modded-Cycles) onto latest upstream `main`
and replaced its knee-feedback ladder with the TB-303 4-pole ladder of Open303 (Robin Schmidt, MIT,
`rosic_Open303.cpp`/`rosic_TeeBeeFilter.h`, commit `313bf0d9`). Kevin decided: credit **Open303 only**
(no 18nelli18 credit), borrow the **whole filter algorithm** (ladder + 150 Hz feedback HPF + b0/k/RES
tables + gain law) but keep our oscillator (polyBLEP), DJ-style COLOR, bipolar envelope, accent,
our 10 Hz-law for HP mixing, and our output gain stage; Open303's own normalized output knee is
replaced by a saturating shift (EMAC-clamped, ×256). Level law is accepted as Open303's: the
COLOR-boundary test was retolerated (63/63.99 within 2 dB, LP closed ≤ 9 dB resonance rows, HP side
≤ 4 dB) — the old ±2 dB-on-everything expectation is gone.

## 1. Repos, worktrees, branches

| Path | What |
|---|---|
| `C:\Users\Kevin\Desktop\repos\Modded-Cycles` | Kevin's main local clone of his fork (dirty WIP, DO NOT TOUCH) |
| `C:\Users\Kevin\Desktop\repos\acid-machine-fork` | git worktree, branch `acid-machine-fetch` (local, push target = `origin/acid-machine`) |
| `C:\Users\Kevin\Desktop\repos\acid-tg-fork` | git worktree, branch `acid-tg` (rebased, result `755e4c0`) |
| `C:\Users\Kevin\Desktop\repos\acid-slide-fork` | git worktree, branch `acid-slide` (rebased, result `be4f180`) |
| WSL `~/acid` (Ubuntu, `/home/kevin/acid`) | fast proof tree (native ext4, NOT /mnt/c - that is 5-10× slower). Carries `firmware/model-cycles_OS1.13.syx` (official, sha256 `44fe5862…9800640c` verified) + `firmware/Syntakt_OS1.42.syx` + `run_local.sh` wrapper |
| `C:\Users\Kevin\Desktop\repos\acid-wsl-tmp` | slow /mnt/c copy, mostly obsolete, keep only as reference |

Remotes (all worktrees share them): `origin` = Kevin's fork (Kevin-Shallvari/Modded-Cycles),
`upstream` = 18nelli18/Modded-Cycles. Do NOT push to upstream, only `origin`.

## 2. Branch state (exact commits)

`acid-machine-fetch` (⇒ push as `acid-machine`, force):
- `5afac21` #65 (acid, our engine) cherry-picked onto upstream `main` `7c39fb8` (track-filter 1.45), all conflicts resolved by regenerating, `tweaks.js`/`REF_*` regenerated
- `8554e0b` gen_acid conflicts fix: 62 `-macro` ids + the plain list (check_overlaps + registry green)
- `cf4ae17` **the filter swap** (WIP label in body but complete): Open303 ladder in `tools/machines/acid/acid.c`, tables `tools/gen_acid.py::tables_303()` → `tools/machines/acid/acid303_tables.h` (generated at compile time by gen_acid's compile_machine; NOT committed — produced), NCUT=175 from 10 Hz (Open303 floor is 200 Hz; we extend down), our polyBLEP osc..., output `qmul(og, shl_sat(qmul(g,y4), 8))`
- `1ef9cdc` final constants (shl 8) + `test_acid.py` boundary check retolerated + `26-acid.json` regenerated (gcc 15.2) — **TOUT OK** alone
- `7fcc4e8` credits: `tweaks/model-cycles_OS1.13/LICENSE-Open303` (from upstream `License.txt`, served by gen_flasher_tweaks as `docs/flasher/LICENSE-Open303.txt`), FEATURES acid card `"license": "LICENSE-Open303"` + desc texts en/fr, PROVENANCE.md acid row, notes/51 §9bis + row in notes/README.md, BUILD.md hashes (`acid` `32a42726…`, `6ch-usbup,acid` `e2df6c99…`, `6ch-usbup,acid,trig-hold,arp,tempo-max,boot-anim` `c99a0928…`), guide §21, README row, release 1.46 texts, stamps `2026-10-11-03` on the 3 pages
- `TOUT OK` including `--with 6ch-usbup,trig-hold,arp,tempo-max,boot-anim` (in WSL log history, verify with rerun)

`acid-tg` (⇒ push, force), 1 commit on top of `1ef9cdc`:
- `755e4c0` #66 rebased (`5b424bb` + amend `755e4c0`): `35-acid-tg.json` regenerated with gcc 15.2, gen_acid.py keeps tg-vs-alone conflicts (`ids -= model-tg-st/model-tg` when tg), card `with model-tg: 35-acid-tg`, excludes updated to `[syntakt, macro]` (model-tg allowed now), license key added, BUILD.md rows updated (`model-tg-st,acid-tg` `d3982495…`, `6ch-usbup,model-tg-st,acid-tg,trig-hold,arp,tempo-max,boot-anim` `0cf29bec…`), check_overlaps/registry/py_compile green. **Not yet test-run** (test_acid covers the tg build; the alone-run passed on the same engine — still run it once, see §4).

`acid-slide` (⇒ push, force), 1 commit on top of `755e4c0`:
- `be4f180` #67 rebased (`d21badb` + amend `be4f180`): SLD hooks survived in `acid.c` (struct + `SLD_BASE` fields `ncur, was, in, glide`, `pw[]` override, trig-hiding in render before AMP chain, glide ramp `SLide`), `26/35` JSONs regenerated (grows engine to 5784 o variables 624 o), `check_overlaps`/`registry`/`ref_mainos` (838 combos, 147 mods) green, py_compile green. **The full `test_acid.py` (which contains the `slide303` check + `--with model-tg-st,acid-tg,…`) was NOT completed** — last attempt died on a missing `m68k-elf-objdump` in the middle of gen-time compile (that is gen_acid.py failing because PATH lacked the objdump symlink, see §3.2), before the actual tests.

## 3. Environment recipes (learned the hard way)

3.1 **WSL Ubuntu** carries `m68k-linux-gnu-gcc` 15.2 + `m68k-linux-gnu-objdump`. The proofs need
`m68k-elf-objdump`: symlink `ln -sf /usr/bin/m68k-linux-gnu-objdump ~/.local/bin/m68k-elf-objdump`
(kevin's PATH includes `~/.local/bin`; `run_local.sh` exports it). WSL **crashes** (`E_UNEXPECTED`)
under long heavy loads — work in `~/acid` (native fs), run proofs with `nohup bash ~/acid/run_local.sh <timeout> [args...] > log 2>&1 &` from a `wsl -d Ubuntu -- bash -c '...'` one-shot and poll the log; a killed shell does NOT kill the job.
3.2 **pgrep self-match**: `pgrep -f test_acid.py` inside `bash -c 'pgrep -f test_acid.py'` matches itself. Use `pgrep -fa "python3 tool"` and filter.
3.3 Never edit generated JSONs/tweaks.js by hand.
3.4 Line endings: the worktrees are checked out with CRLF on Windows; our regenerators write LF. DO NOT "fix" a file wholesale (a python read-as-cp1252 write-as-utf8 mangled `notes/README.md` once — reverted). For notes/README.md-style surgical row edits read/write BYTES.
3.5 The payload (`26/35-acid.json`) embeds `acid303_tables.h`+engine compiled by gcc — regenerate with `python3 tools/gen_acid.py --cycles firmware/model-cycles_OS1.13.syx` (add `--syntakt` not needed), then regenerate `docs/flasher/tweaks.js` via `python3 tools/gen_flasher_tweaks.py` and `python3 tools/registry.py`. gen_flasher_tweaks rewrites `docs/flasher/LICENSE-*.txt` - after regen do `git checkout -- docs/flasher/LICENSE-Braids.txt docs/flasher/LICENSE-Model-TG.txt` (they churn CRLF).
3.6 Conflict-dump helper scripts already written (windows/py): `keep_head.py`/`keep_head2/3/4` in `C:\Users\Kevin\AppData\Local\Temp\opencode\` strip `<<<<<<<` keeping HEAD side (ours) — reuse carefully, then hand-check `tools/gen_acid.py`, `tools/emu/test_acid.py`, `tools/webflash_smoke.js`, `FEATURES` in `tools/gen_flasher_tweaks.py` (they contain BOTH sides after a rebase).
3.7 For `ref_mainos.py` the syntakt file must be a plain path: copy `Syntakt_OS1.42.syx` to `firmware/` root (the space inside `Syntakt OS 1.42/...` path breaks argv).
3.8 `git commit --amend` was used in both amended worktrees; `GIT_EDITOR=true` env for noninteractive (use `$env:GIT_EDITOR="true"` in pwsh).

## 4. Remaining work (in order)

4.1 **acid-tg branch**: rerun proof on `~/acid` (copy the worktree's acid.c/test/gen there — they are NOT synced to ~/acid yet: only `acid-machine` files are):
```bash
cp /mnt/c/Users/Kevin/Desktop/repos/acid-tg-fork/tools/machines/acid/acid.c ~/acid/tools/machines/acid/
cp /mnt/c/Users/Kevin/Desktop/repos/acid-tg-fork/tools/emu/test_acid.py ~/acid/tools/emu/
cp /mnt/c/Users/Kevin/Desktop/repos/acid-tg-fork/tweaks/model-cycles_OS1.13/{26-acid,35-acid-tg}.json ~/acid/tweaks/model-cycles_OS1.13/
cd ~/acid && nohup bash run_local.sh 3000 tools/emu/test_acid.py --with 6ch-usbup,model-tg-st,trig-hold,arp,tempo-max,boot-anim > /home/kevin/acid/tg.log 2>&1 &
```
Expect `TOUT OK` (~15-20 min). If ANY set of voice-level differences appears in the tg part only, debug with the `run_local.sh`-driven `tools/emu/test_acid.py` output; the amp-stage of Model-TG is the only new signal path (the engine outputs Q31 before the Model-TG Attack/filter stage - unchanged by this PR).
4.2 **acid-slide branch**: same sync from `acid-slide-fork`, run
`--with 6ch-usbup,model-tg-st,acid-tg,trig-hold,arp,tempo-max,boot-anim` (slide checks live inside test_acid.py's Model-TG story and are gated on SLD_BASE - the test builds the tg tweak with `-DSLD_BASE`). Expect `TOUT OK` (~25 min). Watch for: (a) the `slide303` graded checks were written against the OLD engine's transient-continue semantics — because the borrowed ladder settles slower (resonance builds over ~1 s at 110 Hz), level/timing tolerances there may need the same treatment as the boundary check did (retolerance with a documented reason, values from Open303's law);
(b) gen-time compile failures with `-DSLD_BASE` = SLD_INIT/SLD_BASE missing — the gen sets them; only the WSL-path compile attempts in lettuce mode show this (never set them by hand outside gen).
4.3 If 4.2's slide303 failure appears and you need to retolerance: edit `tools/emu/test_acid.py` sections under `deg=` for the slide checks and rewrite the check message to say what the Open303 law does (be explicit: resonator settling, not the previous knee-clamped feedback that settled instantly).
4.4 **Web checks**: `tools/webbuild_check.sh`, `tools/webflash_check.sh`, `tools/webflash_smoke.sh [cycles.syx syntakt.syx]` need **node + jsdom in WSL** — not yet run. Install (`npm i -g` not needed, they use local `node_modules` if present) or document "skipped, no node" in the PR. Watch the smoke-test's tweak id order lists - they hard-code the counts (23 ids / 20 feats / "Acid" positions) - the acid-tg branch added a `35-acid-tg` tweak (the ids list in webflash_smoke.js must now include acid-tg in the list positions - inspect carefully with `grep -n acid tools/webflash_smoke.js` and adjust).
4.5 Final **push** (force):
```bash
# in each worktree, after its log is confirmed green:
git push origin HEAD:acid-machine   # force with --force-with-lease (remote branches hold old commits)
git push --force-with-lease origin acid-tg acid-slide   # from any single worktree actually
```
Targets: `Kevin-Shallvari/Modded-Cycles` branches `acid-machine` (was old #65), `acid-tg` (#66), `acid-slide` (#67). Then update the 3 PRs' bodies (drafts; Maxime tests on hardware; status stays "experimental"; hardware test items listed in notes/51 §9 and PR bodies - reuse the notes §9 numbered list).
4.6 **PR body rewrites** for all three (they still describe the knees and the old numbers): before/after sentences for users, what to test on the machine (rotate COLOR across low notes/boundary/resonance, watch the level law, accent with high resonance saturates a little), the level law note, the Open303 MIT licence note, cost 0.45..0.79 TONE, "rebases onto main 1.45", the retolerance decision, plus git hashes.

## 5. Known warts (do not re-litigate)

- The level check's ±9 dB LP row is a DESIGN DECISION (Kevin's (b)); do not flip it back to ±2.
- The ±2 dB boundary check rows were measured as `[-0.4,-0.4,-1.1,-1.2]`, `[-8.0,-8.0,-1.1,-1.2]`, `[-7.5,...]`, `[-0.1...]`, `[-1.5...]`, `[-0.2,-0.2,-3.8,-3.8]` at boost shl 8.
- `26-acid.json` / `35-acid-tg.json` were built with gcc **15.2**, not the repo's usual 13.3 — BUILD.md and notes say 15.2 explicitly. If Maxime's CI regen differs, diff and update the text, do not try to install 13.3.
- `docs/flasher/tweaks.js` regen rewrites the whole file (275k lines churn) — normal, the generator output must be checked with `gen_flasher_tweaks.py --check`, not reviewed by hand.
- The two Open303 hook classes: our gen only borrows the FILTER; Open303's env (MEG), accent integrator (`rc2`), its `acid_out` knee are NOT ported — our og (0.35/0.525 PUNCH accent) and saturating shl(8) replace them. `LICENSE-Open303` covers the borrowed algorithm.
- The engine's `struct acid` gained SLD fields; the bare acid branches compile them out via `#ifdef SLD_BASE`.
- The local branch name is `acid-machine-fetch` (created by a worktree clash); push it AS `acid-machine` (`git push origin HEAD:acid-machine` from that worktree).

## 6. If something refuses

- gen_acid fails with "l'image dépasserait": END_LIMIT from gen_macro/gs; the payloads chain `0x43000000`/`0x46700000` and need END_LIMIT headroom; check what's on that tip. If a regenerates changes the END_LIMIT math, re-check `check_overlaps`.
- registry complains about a mask: run `python3 tools/registry.py` (no `--check`) and commit the diff; the SLD branch's added writes came from `35-acid-tg.json` (its writes were regenerated at rebase).
- ref_mainos errors on defaults: copy the syntakt OS to `firmware/` root first (§3.7).
- If WSL dies again: `wsl --shutdown` then re-run; long proofs must go through `nohup ... &` and polling.
- The test file's `sys.path` pulls `tools/` — always run proofs from the repo root, not from `tools/`.
