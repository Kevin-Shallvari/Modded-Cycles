---
name: french-lab-notes
description: Writes and updates the numbered French technical notes of Modded Cycles (notes/NN-<slug>.md, index in notes/README.md) - structure, certainty tags [FAIT]/[HYP]/[À FAIRE]/[FAIT en émulation], address tables, emulation result tables, dated hardware-test sections, French style. Use when investigating a request, documenting a mod or fix, recording Maxime's hardware results, or correcting a wrong statement in a note.
---

# Lab notes (French)

`notes/` is the project's lab notebook, written in **French**. Every mod and fix has a note; tweak descriptions,
code comments, `BUILD.md` and the guide point to it. Index, conventions and key figures: `notes/README.md`.

## New note

- File `notes/NN-<slug>.md`: next free number (`ls notes | grep -E '^[0-9]+' | sort -n | tail -1`, and check open
  branches), French slug (`38-tempo-546-bpm.md`).
- Skeleton:

```markdown
# NN — <ce que l'utilisateur obtient, ou le problème>

<Demande et source (Reddit, Elektronauts, Discord, Maxime ; lien et date). Tweak `tweaks/…/OO-<id>.json`,
générateur `tools/gen_<mod>.py`, preuve `tools/emu/test_<mod>.py`.> Adresses : VA de l'OS 1.13.

## En bref
<Ce qui est possible, la limite, pourquoi ; ce qu'il faut tester sur la machine.>

## 1. Ce que fait l'OS
| Adresse | Rôle |
|---|---|
| `0x40022382` | `PatternGridView::consumeKeyEvent` … `[FAIT]` |

## 2. Conception
## 3. Place libre et conflits
## 4. Le tweak
## 5. Preuve en émulation
| Cas | OS d'origine | Modifié |
|---|---|---|
## 6. Reste à vérifier
```

- Row in the `notes/README.md` table: link, **bold summary**, key facts, test status.

## Certainty tags

`[FAIT]` read in the code or decoded byte for byte · `[HYP]` hypothesis · `[À FAIRE]` to do ·
`[FAIT en émulation]` proven in the emulator, not yet on the machine. Never upgrade a tag without the evidence.

## Hardware results (only from Maxime)

New section `## N. Testé sur la machine (JJ/MM/AAAA)`: what he flashed (mods, method), what he reported (quote
him), what was fixed after. Update the index row ("**testé sur la machine le JJ/MM/AAAA**"). A problem he reports
gets its own section with the diagnosis and the fix, in the same note.

## Style

Plain, precise French; French number formatting (65 535 ; 546,0 BPM); addresses as `0x40058bb4`; code in fenced
blocks. Fix a statement that turned out wrong, but record later findings, results and fixes in a new dated
section saying what changed, so the note keeps the story of the mod. Long dumps of OS bytes or disassembly do not
belong in notes (rule 1): quote the few instructions that matter.
