---
name: modded-cycles-workflow
description: End-to-end checklist for shipping a Model:Cycles firmware mod, or a fix to one, in the Modded Cycles repo - French note, generator, tweak JSON, Unicorn proof, overlap and registry checks, web flasher card, bilingual guide and release notes, draft PR, hardware-test handoff to Maxime. Use when starting a new mod, fixing or extending an existing mod, planning which files a change must touch, or orchestrating subagents on this repo.
---

# Modded Cycles: shipping a mod

A feature = a tweak JSON (byte writes `old` → `new` on section 3 of the user's own OS 1.13) + optional ColdFire code,
produced by a generator, proven in emulation, put into the one OS of `os.json`, documented in two languages. The hard
rules in the root `AGENTS.md` apply to every step. Copy this checklist into your todo list and tick it as you go.

```
New mod: <id>  (note NN, tweak order OO)
- [ ] 0. Request understood; nothing in notes/ already answers it; branch claude/<id> from main
- [ ] 1. notes/NN-<slug>.md (French) + row in notes/README.md            -> skill french-lab-notes
- [ ] 2. OS code located, addresses [FAIT]                               -> skill mainos-reverse-engineering
- [ ] 3. Design: hook points, free space, settings storage, conflicts    -> skill coldfire-patching
- [ ] 4. tools/gen_<mod>.py (+ tools/machines/<mod>/) -> tweaks/.../OO-<id>.json, --check passes
                                                                          -> skill tweak-generators
- [ ] 5. tools/emu/test_<mod>.py: stock vs patched, alone and --with the other tweaks of os.json
                                                                          -> skill emulation-proofs
- [ ] 6. check_overlaps.py, registry.py (+ commit REGISTRY.md), PROVENANCE.md row, BUILD.md section
- [ ] 7. Into the OS: os.json (feature, experimental; OS status back to experimental), tweaks.js,
          REF_MAINOS/REF_MODS, FEAT en+fr, smoke lists
                                                                          -> skill flasher-integration
- [ ] 8. Guide section, release entry, MC_BUILD/?v= stamp, FEATURES.md and README rows -> skill bilingual-user-docs
- [ ] 9. Full validation, summary table kept for the PR                  -> skill repo-validation
- [ ] 10. Commits, push, draft PR with the hardware test plan           -> skill hardware-test-handoff
```

## Step 0: before any code

- `rg -n -i '<keywords>|<addresses>' notes/` and read `notes/README.md` (index + key figures). Most subsystems
  are already decoded; an earlier note often answers the question or shows the trap.
- Find the next free numbers by listing, never by memory:
  `ls notes | grep -E '^[0-9]+' | sort -n | tail -3` and `ls tweaks/model-cycles_OS1.13 | sort | cut -c1-3 | uniq`.
  Order ranges are in the `tweak-generators` skill.
- Check open branches for collisions (same note number, same order, same freed mask):
  `git fetch && git branch -r` then `python3 tools/registry.py --git origin/<branch>`.
- If the request is ambiguous (which button, what the screen shows, which limit is acceptable), ask Maxime in
  French before designing. He decides user-facing behaviour.

## A fix to an existing mod

Same path minus new files: a new dated section in the mod's note (what was wrong, why, the fix), the generator,
the proof (add a check that fails on the old version), regenerated JSON / `tweaks.js` / `REF_MAINOS` / `REF_MODS`
/ `REGISTRY.md`, a new release entry, the stamp. A fix to a `tested` mod goes back to `experimental` only if
Maxime says so; say in the PR what must be re-tested.

## After Maxime's hardware test

He reports; you never infer it. Follow the `hardware-test-handoff` skill: a separate small commit
"<Mod> tested on the Model:Cycles" flipping `status` to `tested` everywhere it appears.

## Files a new mod touches (review list)

| Area | Files |
|---|---|
| Research | `notes/NN-*.md`, `notes/README.md` |
| Build | `tools/gen_<mod>.py`, `tools/machines/<mod>/*`, `tweaks/model-cycles_OS1.13/OO-<id>.json` |
| Proof | `tools/emu/test_<mod>.py` |
| Registers | `tweaks/model-cycles_OS1.13/REGISTRY.md` (generated), `PROVENANCE.md`, `BUILD.md`, `THIRD-PARTY-NOTICES.md` if outside code |
| The OS | `os.json`, `docs/flasher/tweaks.js` (generated), `docs/flasher/app.js` (FEAT texts, generated REF blocks), `tools/webflash_smoke.js` |
| Users | `docs/guide/index.html`, `docs/assets/release.js`, stamp in 3 pages, `FEATURES.md`, `README.md` |

## Working with subagents (pi)

Project agents live in `.pi/agents/`. Typical split, one agent per step, each told the note path and the branch:
`mc-scout` (map notes and code for the request) → `mc-reverser` (locate OS code, draft the note's OS sections)
→ `mc-firmware-dev` (generator, code, proof) → `mc-web-dev` (flasher + guide + release) → `mc-reviewer`
(rules, overlaps, ISA pitfalls) → `mc-validator` (full suite). Run steps that edit the same files sequentially;
only read-only agents may run in parallel. Prompt templates: `/new-mod`, `/fix-mod`, `/investigate`, `/validate`, `/review-branch`, `/mark-tested`.
