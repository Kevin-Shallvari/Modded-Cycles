# AGENTS.md — Modded Cycles

Guidance for coding agents and contributors working on this repository. This file holds what is always true; the
procedures live in **skills** (`.agents/skills/`, loaded on demand) and the roles in **pi agents** (`.pi/agents/`).
Read the skill that matches your task before you start: pi lists them automatically; other harnesses (Claude Code,
Codex) should open the `SKILL.md` named in the table below. Each folder you touch has its own short `AGENTS.md`
(`tools/`, `tweaks/`, `docs/`, `notes/`). The developer setup is in [`DEVELOPMENT.md`](DEVELOPMENT.md).

## What this project is

A community firmware for the **Elektron Model:Cycles, OS 1.13** (ColdFire MCF54415, big-endian m68k). Since
version 2.0 it is **one OS**, the *Modded Cycles OS*: the web flasher (`docs/flasher/`, GitHub Pages at
<https://18nelli18.github.io/Modded-Cycles/>) builds one firmware in the browser from the user's **own** official
files and sends it over USB. There is nothing to tick: everyone runs the same OS.

- **`os.json`** at the root is the recipe: the ordered list of *tweaks* the OS is made of, the features shown on the
  page, the added machines, the files it needs. `tools/gen_flasher_tweaks.py` turns it into `docs/flasher/tweaks.js`,
  `tools/ref_mainos.py` writes its reference hashes into `docs/flasher/app.js`, `tools/build.py --os` builds it on
  the command line.
- A **tweak** is a table of byte writes (`old` → `new`) applied to section 3 (the MAIN OS) of the official `.syx`,
  plus, for most, code compiled or assembled into free space. `tweaks/model-cycles_OS1.13/` is the **library** of
  tweaks: every tweak that was ever built and proven, including those outside the current OS. `build.py -t` can
  build any compatible subset for development; users never see that choice.
- A **feature** is what the user sees: one row of the flasher page, one guide section, one row of `FEATURES.md`.
  A feature maps to one or more tweaks of the OS (or none: it rides inside another tweak, like drumkilla's tweaks
  inside Model-TG).
- **Always the Model:Cycles OS, whatever the machine** (notes/57). The flasher installs the same OS on a
  Model:Samples; the machine choice only changes the packing (`tools/mods_for_samples.py`).

Project owner: Maxime (GitHub `18nelli18`). He tests every firmware change on his own Model:Cycles and merges.

## Hard rules

1. **Never commit an Elektron firmware image**, original or modified, or anything extracted from one (no `.syx`,
   `.zip`, extracted sections, dumps, copied routines). `.gitignore` covers `firmware/`, `*.syx`, `*.zip`, `build/`,
   `vendor/`, `*.wav`. A tweak carries only its own writes and the short `old` bytes that check the user's file; code
   taken from the Syntakt OS is extracted **at build time** from the user's file (recipes and relocation tables only,
   notes/17). Never write that a file holds "no Elektron bytes" when it carries `old` bytes.
2. **Build from the official image only**, never on top of a previous build. Every write carries its `old` bytes and
   the build refuses a mismatch. Stock hashes are in `tweaks/model-cycles_OS1.13/device.json`.
3. **Hardware testing is Maxime's.** A new feature enters the OS with `"status": "experimental"` (in `os.json`), and
   the OS as a whole goes back to `experimental` whenever its composition changes. Only after he reports that it
   works on his Model:Cycles does a status become `tested`, in a separate commit ("… tested on the Model:Cycles").
   Never mark anything tested yourself, never claim a hardware result you did not get from him.
4. **One user-visible change, one PR**, with its note, docs, guide, release entry and `FEATURES.md` row in the same
   PR. Open it as a draft; Maxime merges after testing on the hardware.
5. **Prove it in emulation first.** Every tweak has a generator with `--check` and a proof under `tools/emu/` that
   runs the OS's own code (Unicorn), stock vs patched, alone and **with the whole OS** (`--with` the tweaks of
   `os.json`). Unproven code does not enter the OS.
6. **The OS must stay buildable as one firmware.** A new tweak may not write the same bytes as a tweak of the OS
   (`tools/check_overlaps.py`), may not declare `conflicts` with one, and must chain its payload after the others.
   A feature that cannot live with the rest stays out of `os.json` until the conflict is solved: there is no
   "untick the other one" any more.
7. **Recovery must stay possible.** Only section 3 is touched; the bootloader and updater stay identical, so the
   STARTUP MENU (MIDI IN) can always bring back the official OS. The OS keeps `CONFIG › UPGRADE` over USB working.
8. **Respect the licenses and credit authors.** The project is MIT (`LICENSE`); the scope and every third-party
   license are in `THIRD-PARTY-NOTICES.md`. Record the origin and license of every tweak in
   `tweaks/model-cycles_OS1.13/PROVENANCE.md`, set `credit` and `license` on its feature in `os.json`, and serve its
   license text with the page. Never transcribe or closely paraphrase code whose license does not allow it (GPL code
   into MIT files, code with no license). Outside contributions are merged only under `CONTRIBUTING.md`.

## Languages

- **English** is the language of the repository: code, comments and docstrings of new or rewritten files, commit
  messages, pull requests, issues, `README.md`, `FEATURES.md`, `BUILD.md`, `RECOVERY.md`, `DEVELOPMENT.md`,
  `CONTRIBUTING.md`, skills and agents. Older `tools/` files still have French comments; keep a file consistent when
  you edit it, do not translate for its own sake.
- **French** for the technical notes (`notes/`, the lab notebook) and `PROVENANCE.md`, which are written for the
  French-speaking core of the project; and for talking to Maxime when he writes French.
- **Both, side by side**: everything users see on the site (flasher texts, guide, release notes, home page), as
  `en`/`fr` pairs or `data-l="en"`/`data-l="fr"` spans. Never add one language without the other. User-facing text
  speaks to musicians: what it does on the machine, which buttons to press, its limits. No addresses or jargon there.

## Skills (`.agents/skills/<name>/SKILL.md`)

| Task | Skill |
|---|---|
| Shipping a feature or a fix end to end (checklist, files, order) | `modded-cycles-workflow` |
| OS addresses, disassembly, callers, strings, the decoded-subsystem map | `mainos-reverse-engineering` |
| ColdFire code in `tools/machines/`, hooks, free space, toolchain, safety | `coldfire-patching` |
| A generator and its tweak JSON, numbering, `--check`, PROVENANCE | `tweak-generators` |
| A Unicorn proof in `tools/emu/`, rigs, combined runs, cost | `emulation-proofs` |
| Putting a feature in the OS: `os.json`, `tweaks.js`, `REF_MAINOS`/`REF_MODS`, FEAT en/fr, smoke test | `flasher-integration` |
| Guide section, release entry, `FEATURES.md` row, stamp, README | `bilingual-user-docs` |
| A French note in `notes/`, certainty tags, hardware results | `french-lab-notes` |
| Running the whole validation suite, reading its result | `repo-validation` |
| Commits, draft PR, hardware test plan, flipping to tested | `hardware-test-handoff` |
| Licenses, provenance, firmware bytes, contributions | `licensing-provenance` |

## Pi agents (`.pi/agents/`, pi-interactive-subagents) and prompts (`.pi/prompts/`)

| Agent | Model (claude-bridge) | Role |
|---|---|---|
| `mc-planner` | `claude-opus-5-5`, high | interactive design with Maxime (French), writes `.pi/plans/<date>-<slug>/plan.md` |
| `mc-scout` | `claude-sonnet-5-5`, minimal | read-only map of notes, mods, free space, open branches for a request |
| `mc-reverser` | `claude-fable-5-1`, high | reverse-engineers the OS, writes the note's OS and design sections |
| `mc-firmware-dev` | `claude-fable-5-1`, high | ColdFire code, generator, tweak JSON, proof, registers |
| `mc-web-dev` | `claude-sonnet-5-5`, medium | `os.json` feature, flasher texts, guide, release notes, stamp, README, FEATURES.md |
| `mc-reviewer` | `claude-opus-5-5`, high | rules and firmware-safety review, no edits |
| `mc-validator` | `claude-haiku-4-5`, minimal | runs the validation suite, reports |
| `mc-worker` | `claude-opus-5-5`, medium | any delegated task no role covers, touching only the files the task names |

Prompts: `/new-mod <request>`, `/fix-mod <id> <report>`, `/investigate <question>`, `/validate [opts]`,
`/review-branch [branch]`, `/mark-tested <id> <date> <report>`. Plans and reviews go in `.pi/plans/` (git-ignored).
Only one agent edits the tree at a time; read-only agents may run in parallel. Setup: `DEVELOPMENT.md`.

**Every spawn names an agent** (`agent: mc-…`; `mc-worker` when no role fits) or passes an explicit
`model: claude-bridge/…`. A bare spawn starts on pi's automatic model, which on a machine holding an Anthropic
API key is `anthropic/claude-opus-4-8`, billed outside the Claude plan. The generic agents bundled with the
subagents extension (`worker`, `scout`, `planner`, `reviewer`) point at `anthropic/…` too: do not use them here.

## Repository map

```
os.json                       THE OS: ordered tweak ids, features (section, status, credit, license, guide anchor), machines
tweaks/model-cycles_OS1.13/   tweak library (generated JSON), device.json, PROVENANCE.md (French), REGISTRY.md (generated)
tools/build.py                Python build: --os (the OS) or -t ids; applies tweaks, checks caves, repacks and re-signs (mtlib)
tools/gen_*.py                one generator per tweak: writes its JSON, --check verifies it is up to date
tools/machines/<mod>/         C and assembly sources compiled into the firmware
tools/emu/                    Unicorn emulation of the OS: test_<mod>.py proofs, mcengine.py, seqrig.py, emac.py, syntakt.py
tools/gen_flasher_tweaks.py   os.json + tweaks/ -> docs/flasher/tweaks.js (generated) and the license files the page serves
tools/ref_mainos.py           REF_MAINOS (the OS) and REF_MODS (each tweak) hashes in docs/flasher/app.js
tools/check_overlaps.py       no firmware: tweaks that can be built together never write the same bytes (notes/49)
tools/registry.py             no firmware: builds REGISTRY.md, the free space and OS hooks registry (notes/52)
tools/crossflash.py, tools/mods_for_samples.py   one OS in the other machine's container (notes/41, 57)
tools/web*_check.*, webflash_smoke.*   checks of the web flasher against the Python build (node, jsdom)
docs/                         GitHub Pages site: index.html, flasher/, guide/, assets/release.js
notes/                        numbered technical notes (French), index in notes/README.md; 00 is the original dossier
.agents/skills/               agent skills (procedures, references, scripts); .pi/agents, .pi/prompts: pi roles and commands
FEATURES.md                   every feature of the OS, key combinations, limits, status; what is out and why
BUILD.md, RECOVERY.md         command-line build; recovery through the startup menu (MIDI IN)
DEVELOPMENT.md                developer setup: toolchain, emulator, pi, REA, validation
.github/                      discord.yml + scripts/discord.mjs: new versions, status changes, merged PRs -> Discord
README.md                     overview for Model:Cycles owners
LICENSE, THIRD-PARTY-NOTICES.md, CONTRIBUTING.md
```

Official files (never committed) go in `firmware/`: `model-cycles_OS1.13.syx` (SHA-256 `44fe5862…9800640c`) and
`Syntakt_OS1.42.syx` (or 1.41) for the Syntakt engines, downloaded from elektron.se.

## The usual PR, in one breath

Note (`notes/NN-*.md`) → generator + sources → tweak JSON → Unicorn proof alone and with the OS →
`check_overlaps.py`, `registry.py`, `PROVENANCE.md` → the feature in `os.json` (`experimental`), `tweaks.js`,
`REF_MAINOS`/`REF_MODS`, FEAT en+fr in `app.js`, smoke test lists → guide section, release entry, stamp,
`FEATURES.md` and README rows → validation → draft PR with a test plan for Maxime → after his report, a separate
"tested" commit. Details: skill `modded-cycles-workflow`.

A fix to an existing feature follows the same path minus the new files: a dated section in its note, the generator,
the proof, regenerated JSON / `tweaks.js` / `REF_MAINOS` / `REF_MODS` / `REGISTRY.md`, a release entry, the stamp.

Changing the composition of the OS (adding or removing a feature) is a user-visible change in itself: `os.json`,
regenerated files, guide, release entry, `FEATURES.md`, README, and the OS status back to `experimental`.

## Validation before pushing

Without firmware (always possible, run them all):

```sh
python3 tools/gen_flasher_tweaks.py --check      # tweaks.js and the served licenses match os.json + tweaks/
python3 tools/check_overlaps.py                  # tweaks that can be built together never write the same bytes (notes/49)
python3 tools/registry.py --check                # REGISTRY.md (free space and hooks, notes/52) matches tweaks/
python3 tools/relocate_6ch.py --check            # needs m68k-linux-gnu binutils (DEVELOPMENT.md)
tools/webbuild_check.sh                          # builder.js == build.py, byte for byte (node)
tools/webflash_check.sh                          # flasher.js validates .syx like mtlib (node)
tools/webflash_smoke.sh                          # the flasher page in jsdom (node, npm, network)
python3 -m py_compile tools/*.py tools/emu/*.py
```

With the official files in `firmware/`:

```sh
python3 tools/build.py -i firmware/model-cycles_OS1.13.syx --syntakt firmware/Syntakt_OS1.42.syx --os -o build/os.syx
python3 tools/ref_mainos.py --cycles firmware/model-cycles_OS1.13.syx --syntakt firmware/Syntakt_OS1.42.syx --check
python3 tools/gen_<mod>.py --cycles firmware/model-cycles_OS1.13.syx --check
python3 tools/emu/test_<mod>.py --cycles firmware/model-cycles_OS1.13.syx [--with <the other tweaks of os.json> --syntakt …]
tools/webflash_smoke.sh firmware/model-cycles_OS1.13.syx firmware/Syntakt_OS1.42.syx   # the OS built in the page, checked
```

`.agents/skills/repo-validation/scripts/validate.sh` runs all of this and prints one PASS/FAIL/SKIP table. If a check
cannot run (no network, no toolchain), say so in the PR instead of skipping it silently.

## Commits and PRs

- Commit messages in English: a short subject saying what the user gets ("Tempo up to 546 BPM (tempo-max tweak,
  notes/38)"), a body with the why, the bullets of what changed, and how it was proven. Stage explicit paths, never
  `git add -A`: the working tree may hold untracked work and firmware files.
- Merge `main` into a feature branch rather than rebasing shared branches; regenerate `tweaks.js`, `REF_MAINOS` /
  `REF_MODS` and `REGISTRY.md` after a merge instead of resolving their conflicts by hand.
- The PR body says what the user sees before and after, how it was proven, which checks could not run, and **what
  Maxime should test on the machine** (which buttons, what to listen or look for).
- Note numbers, tweak numbers, versions and stamps are assigned by the maintainer at merge time when several PRs are
  open; say in the PR which ones you took.
