---
description: Review a branch or PR against the hard rules and firmware safety
argument-hint: "[branch, default: current]"
---
Spawn `mc-reviewer` on branch `${1:-HEAD}` compared with `main`. Pass it the note and plan paths if they exist
(`git diff --name-only main...${1:-HEAD} -- notes/ .pi/plans/`). When it finishes, summarise the verdict and the
P0/P1 findings for me in French, with the review file path.
