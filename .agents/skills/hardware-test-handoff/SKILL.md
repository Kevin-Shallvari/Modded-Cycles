---
name: hardware-test-handoff
description: Prepares commits, the draft pull request and the hardware test plan for Maxime (who alone tests on his Model:Cycles), then records his result - commit message style, PR body (before/after, proof, checks not run, what to test with which mods and buttons), recovery reminder, and the follow-up commit flipping a mod from experimental to tested across os.json, tweaks.js, guide, release notes, README and note. Use when committing, opening or updating a PR, asking Maxime to test, or when he reports a hardware result.
---

# Commits, draft PR, hardware handoff

Only Maxime tests on hardware. A mod ships `experimental`; it becomes `tested` only after he reports that it
works on his Model:Cycles, in a separate commit. Never claim a hardware result you did not get from him.

## Commits

- English subject saying what the user gets: `Tempo up to 546 BPM (tempo-max tweak, notes/38)`.
- Body: why, bullets of what changed, how it was proven (proof name, number of checks, combinations).
- Stage explicit paths (`git add tools/gen_x.py tweaks/... docs/...`), never `git add -A`: the working tree may
  hold Maxime's untracked work (for example `Docs Optimisations/`) and firmware files must never be committed.
  Before every commit: `git status --short` and `git diff --cached --stat`; refuse any `.syx`, `.zip`, `.bin`
  or extracted dump.
- Merge `main` into a feature branch (no rebase of shared branches); after a merge, regenerate `tweaks.js`,
  `REF_MAINOS`/`REF_MODS`, `REGISTRY.md` instead of hand-resolving their conflicts.

## Draft PR

One user-visible change per PR, opened as **draft** (`gh pr create --draft`); ask before merging, Maxime merges
after his test. Body (English):

```markdown
## What changes for the user
Before: … After: … (buttons, screen, limits)

## How it was proven
- tools/emu/test_<mod>.py: N checks, stock vs patched; combined with <mods>
- validate.sh summary: <PASS lines>
- Checks not run: <SKIP lines and why>

## What to test on the machine
1. Flash from the web flasher with: <mods ticked> (and a second run with <bigger combination>)
2. <Steps with buttons> — expect <what to hear/see>
3. Regression: <what must still behave as before>
Recovery: STARTUP MENU over MIDI IN brings back the official OS.

Note: notes/NN · Tweak: OO-<id> · Release 1.xx
```

Tell Maxime in French, in the chat, the same test plan in short: which mods to tick, which buttons, what to listen
or look for, what to report (screen exception code `VEC/SR/ADDR` if it crashes).

## After his report

Works → one commit "<Mod> tested on the Model:Cycles":
- [ ] `"status": "tested"` on the feature in `os.json` (and on the OS itself only when Maxime tested this exact
      firmware), regenerate `docs/flasher/tweaks.js`
- [ ] guide: *Experimental* → *Tested* line (en + fr)
- [ ] release entry (new version, "Tested on a Model:Cycles") and the stamp
- [ ] `README.md` row status, `FEATURES.md` status line
- [ ] note: `## N. Testé sur la machine (JJ/MM/AAAA)` + index row in `notes/README.md`
- [ ] `ref_mainos.py --check` still passes (a status change does not change the firmware), validation, push

Problem → record it in the note (his words, the screen code, the combination), reproduce it as a failing check in
the proof, fix, bump the release, and send a new test plan.
