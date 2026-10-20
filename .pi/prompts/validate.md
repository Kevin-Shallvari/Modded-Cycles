---
description: Run the whole validation suite on the current branch and summarise it
argument-hint: "[validate.sh options, e.g. --quick or --gen gen_x.py --proof test_x.py]"
---
Load the `repo-validation` skill and run:

```sh
.agents/skills/repo-validation/scripts/validate.sh $@
```

Report the summary table, explain each FAIL from its log in `build/validate/`, and list the SKIP lines formatted
for a PR body ("Checks not run"). Do not modify files unless I ask.
