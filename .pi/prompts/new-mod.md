---
description: Start a new Model:Cycles mod end to end (plan, reverse, build, prove, flasher, docs, draft PR)
argument-hint: "<what the musician wants>"
---
Load the `modded-cycles-workflow` skill and run it for this request: $@

Orchestrate with the project agents in `.pi/agents/`, one step at a time, and keep the workflow checklist as your
todo list:
1. `mc-scout`: map what already exists for the request (notes, related mods, free space, open branches).
2. `mc-planner` (interactive, Maxime in his pane): agree on behaviour and limits, write the plan. Wait for it.
3. Create the branch `claude/<id>` from an up-to-date `main`.
4. `mc-reverser`: locate the OS code, write the note's OS and design sections, list the hooks.
5. `mc-firmware-dev`: generator, sources, tweak JSON, proof alone and combined, registers, BUILD.md, commit.
6. `mc-web-dev`: the feature in os.json, flasher texts, guide, release entry, stamp, FEATURES.md, README, commit.
7. `mc-reviewer`, then fix its P0/P1 findings (back to steps 5 or 6), then `mc-validator`.
8. Push and open a **draft** PR (skill `hardware-test-handoff`), and give Maxime the test plan in French.

Pass every agent the plan path, the note path and the branch. Never run two editing agents at the same time.
Talk to Maxime in French.
