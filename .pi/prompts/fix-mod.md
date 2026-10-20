---
description: Fix an existing mod from a bug report (reproduce in emulation, fix, re-prove, release)
argument-hint: "<mod id> <what goes wrong, who reported it>"
---
Load the `modded-cycles-workflow` skill (section "A fix to an existing mod") for mod `$1`. Report: ${@:2}

1. Read the mod's note, generator, sources and proof; find the note with `rg -n '$1' notes/README.md`.
2. Reproduce the report as a failing check in its proof (`tools/emu/test_*.py`) on the current tweak, with the
   combination of mods the reporter used. If it does not reproduce, say so and ask Maxime for details (screen
   exception code, mods ticked, steps) before changing anything.
3. Delegate the fix to `mc-firmware-dev` (generator/sources, regenerated JSON, proof passing alone and combined),
   then `mc-web-dev` (tweaks.js, REF_MAINOS/REF_MODS, release entry, stamp, guide limits if they change).
4. Record in the note a new dated section: the report, the diagnosis, the fix, the proof.
5. `mc-reviewer`, `mc-validator`, then a draft PR with what Maxime must re-test. Talk to Maxime in French.
