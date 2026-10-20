# AGENTS.md — notes/

The project's lab notebook, in **French**. Read the root [`AGENTS.md`](../AGENTS.md) first, then
[`README.md`](README.md) (index, conventions, key figures) before starting anything: most OS functions you will
need are already decoded in an earlier note. How to write a note: skill
[`french-lab-notes`](../.agents/skills/french-lab-notes/SKILL.md); how to search the OS:
[`mainos-reverse-engineering`](../.agents/skills/mainos-reverse-engineering/SKILL.md).

## Local invariants

- Search before investigating: `rg -n 0x4005 notes/`, `rg -n -i retrig notes/`. Starting points: 03 (platform),
  05 (patch method), 09 (OS 1.13), 14 §1–5 (machines, voice loop, sprite masks), 23/25/36 (audio load, governor),
  32–34 (keys, events, sequencer, UI), 35 (USB audio), 38 (tempo, musical clock).
- `NN-<slug>.md`, next free number from `ls`; a row in `README.md` for every note.
- Certainty tags: `[FAIT]`, `[HYP]`, `[À FAIRE]`, `[FAIT en émulation]`.
- Hardware results come only from Maxime, in a dated section `## N. Testé sur la machine (JJ/MM/AAAA)`.
- Keep the story: fix wrong statements, but record later findings in new dated sections. No firmware dumps.
