---
name: licensing-provenance
description: Checks licenses and records provenance when Modded Cycles uses outside work - porting or compiling third-party code (Braids, Open303, Model-TG, ms-multi-output, drumkilla, Elektroid), integrating a community mod or fork, accepting a contribution - and keeps Elektron firmware bytes out of the repo. Covers THIRD-PARTY-NOTICES.md, PROVENANCE.md, LICENSE files served with the flasher, card credit, and CONTRIBUTING terms. Use whenever code, tables or ideas come from someone else, or a file might carry firmware bytes.
---

# Licenses, provenance, firmware bytes

## Elektron bytes (rule 1)

- Never commit an Elektron image, original or modified, or anything extracted from it (`.syx`, `.zip`, sections,
  dumps, copied routines). `.gitignore` covers `firmware/`, `*.syx`, `*.zip`, `build/`, `vendor/`, `*.wav`.
- A tweak carries only its own writes plus the short `old` bytes that check the user's file. Never write that a
  file holds "no Elektron bytes" when it carries `old` bytes.
- Code taken from the Syntakt OS is extracted **at build time** from the user's file (recipes and relocation
  tables only, notes/17). Same for the parameter descriptor tables copied by MACRO/ACID.

## Before porting outside code

1. Find the license in the upstream repo at a pinned commit. MIT/BSD/Apache: OK with notice. GPL: never into
   MIT files (`tools/webxfer_check.py` is a GPL transcription kept separate, `LICENSES/GPL-3.0-or-later.txt`).
   No license (a mod sent privately, a binary): do not copy or closely paraphrase; rewrite from the behaviour, and
   get the author's written OK to use it (DavidCaruso's LFO mod, notes/56).
2. Pin the source: clone into `vendor/` (git-ignored) at a commit recorded in the generator and the note.
3. Compile unchanged when possible (Braids for MACRO); if rewritten (Open303 → ACID), say so.

## What to record (same PR)

| Where | What |
|---|---|
| `tweaks/model-cycles_OS1.13/PROVENANCE.md` | row: author, origin repo + commit, license, what we changed, generator, note |
| `THIRD-PARTY-NOTICES.md` | outside code: name, author, license, where it is used |
| `tweaks/model-cycles_OS1.13/LICENSE-<Name>` | the license text, copied next to the tweaks |
| `docs/flasher/LICENSE-<Name>.txt` | served with the page; `license` key on the feature in `os.json` |
| `os.json` feature `credit` | `{"kind": "based", "who": "<author>", "repo": "<owner/repo>"}`; without `repo`: "based on a mod by …" |
| guide + release | "Based on a mod by …" / « D'après un mod de … » |

## Contributions

Outside contributions are merged only under `CONTRIBUTING.md`; work sent privately needs its author's written OK,
recorded in the note.
