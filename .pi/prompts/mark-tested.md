---
description: Record Maxime's hardware test result for a mod and flip it to tested
argument-hint: "<mod id> <DD/MM/YYYY> <what Maxime reported>"
---
Maxime reports a hardware test of mod `$1` on $2: ${@:3}

Load the `hardware-test-handoff` skill ("After his report"). If the report says it works, make one commit
"<Mod> tested on the Model:Cycles" with every item of that checklist (os.json feature status, tweaks.js, guide line, FEATURES.md,
release entry and stamp, README, note section "Testé sur la machine ($2)" and index row), then validate and push.
If the report describes a problem, do not flip anything: record it in the note and start `/fix-mod` instead.
Quote Maxime's words in the note; never add results he did not give.
