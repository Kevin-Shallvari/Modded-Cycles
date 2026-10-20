---
description: Answer a feasibility question about the Model:Cycles OS without writing a mod
argument-hint: "<question, e.g. can the arpeggiator follow the swing?>"
---
Question from Maxime: $@

Load `mainos-reverse-engineering` and answer from evidence: first what the notes already decoded, then the OS
code (with `scripts/mainos.py` and, if the answer depends on behaviour, a short Unicorn probe in `build/`).
Answer in French: **Réponse courte** (possible or not, the limit, why), then the evidence with addresses and
certainty tags, the free space and the CPU cost it would need, and the conflicts with existing mods. Offer to
write it up as a new note; do not create files unless he agrees.
