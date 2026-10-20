# Developer Setup — Modded Cycles

This document describes the complete, reproducible setup for working on the Modded Cycles firmware-mod project, including the pi coding agent layer.

## What You Need

### Python 3 and virtual environment

Create a `.venv` and install the emulation dependencies:

```sh
python3 -m venv .venv
source .venv/bin/activate   # or .venv/Scripts/activate on Windows
pip install unicorn numpy
```

`unicorn` and `numpy` are required only for the Unicorn emulation proofs (`tools/emu/`); the build and the generators run with the standard library alone.

### m68k cross toolchain

The ColdFire MCF54415 is a big-endian m68k. The project needs binutils and, for some code mods, GCC.

| Platform | Package(s) | Provides |
|---|---|---|
| macOS (Homebrew) | `m68k-elf-binutils`, `m68k-elf-gcc` | `m68k-elf-as`, `m68k-elf-ld`, `m68k-elf-objdump`, `m68k-elf-nm`, `m68k-elf-gcc` |
| Debian / Ubuntu | `binutils-m68k-linux-gnu`, `gcc-m68k-linux-gnu` | `m68k-linux-gnu-as`, etc. |

**Which committed outputs depend on which toolchain:**

- **`m68k-elf-gcc 16.2.0 / binutils 2.47`** (Homebrew): SD VINTAGE v2 (notes/16 §6) and the C mods (Syntakt bridge, MACRO, ACID, arpeggiator, sample preview…). The compiled bytes are committed; another compiler version can produce different bytes, which `--check` reports. Build recipe of that toolchain from source: notes/42 §16.
- **`m68k-linux-gnu-` binutils only**: `relocate_6ch.py --check` produces its committed JSON only with `m68k-linux-gnu-as`. The `m68k-elf-as` relaxes `lea abs.l` to PC-relative, so the bytes differ. Never regenerate `11-6ch-usbup.json` with `m68k-elf-` binutils.
- **Assembly-only mods** (e.g. `boot_anim.S`): `--check` depends only on binutils, not on the compiler.

The generators detect the available prefix: `m68k-elf-` (Homebrew) or `m68k-linux-gnu-` (Debian). C code that calls the OS must be built with `m68k-elf-gcc` (m68k-elf ABI), never `m68k-linux-gnu-gcc` (SVR4 ABI), because the OS returns pointers in `d0`.

### Node.js and npm

Required for the web checks (`webbuild_check.sh`, `webflash_check.sh`, `webflash_smoke.sh`). Install Node.js ≥18 and npm. `tools/webflash_smoke.sh` installs jsdom in a temporary folder (network needed); nothing is added to the repository.

### Other tools

- **gh** (GitHub CLI): for opening PRs, listing branches.
- **ripgrep** (`rg`): the notes and skills use `rg` for fast searches.

### Official firmware files

Download these from [elektron.se](https://www.elektron.se/support/) into `firmware/` (git-ignored). **Never commit them.**

| File | SHA-256 |
|---|---|
| `model-cycles_OS1.13.syx` | `44fe586269631a0ca7da25a3383fc6733c314809505fc3cc52f1e0ed9800640c` |
| `Syntakt_OS1.42.syx` (or 1.41, same audio program) | checked by `tools/emu/syntakt.py` (section 7 hash); whole-file hashes in `tools/crossflash.py` `OFFICIAL` |
| `model-samples_OS1.13.syx` (optional) | for crossflash tests only |

The section-3 (MAIN OS) hash is in `tweaks/model-cycles_OS1.13/device.json`.

---

## The OS recipe: `os.json`

The web flasher and `tools/build.py --os` build ONE firmware, described by `os.json` at the repository root: the ordered
list of tweak ids, the features shown on the page (section, status, credit, license, guide anchor), the added machines
and the official files it needs. `tweaks/model-cycles_OS1.13/` is the library of every tweak ever built and proven;
`build.py -t` can still combine them for development.

After editing `os.json` or a tweak of the OS:

```sh
python3 tools/gen_flasher_tweaks.py            # docs/flasher/tweaks.js + served licenses (refuses an unbuildable OS)
python3 tools/ref_mainos.py --cycles firmware/model-cycles_OS1.13.syx --syntakt firmware/Syntakt_OS1.42.syx
                                               # REF_MAINOS (the OS) and REF_MODS (each tweak) in docs/flasher/app.js
python3 tools/build.py -i firmware/model-cycles_OS1.13.syx --syntakt firmware/Syntakt_OS1.42.syx --os -o build/os.syx
tools/webflash_smoke.sh firmware/model-cycles_OS1.13.syx firmware/Syntakt_OS1.42.syx   # the page builds the same OS
```

Details and the step list for a new feature: `AGENTS.md`, skills `modded-cycles-workflow` and `flasher-integration`.

---

## Validation Commands

The validation script lives at `.agents/skills/repo-validation/scripts/validate.sh`. It reports PASS/FAIL/SKIP per check.

```sh
V=.agents/skills/repo-validation/scripts/validate.sh

# Quick (no firmware, no network): compile, tweaks.js, overlaps, registry, relocate_6ch, builder parity
$V --quick

# Full (adds jsdom smoke test, needs npm and network)
$V

# With a specific mod's generator and proof (needs firmware/, unicorn)
$V --gen gen_trig_hold.py --proof test_trig_hold.py \
   --with 6ch-usbup,model-tg-st,syntakt-tg-sd-cp-toy-bits-swarm,arp,tempo-max

# Against an open branch (overlap and registry, repeatable)
$V --git origin/claude/open-pr
```

### What each check verifies

| Check | Requires | What it does |
|---|---|---|
| `gen_flasher_tweaks.py --check` | — | `tweaks.js` and the served license files match `os.json` + `tweaks/` |
| `check_overlaps.py` | — | Mods that can be combined never write the same bytes |
| `registry.py --check` | — | `REGISTRY.md` is up to date |
| `relocate_6ch.py --check` | `m68k-linux-gnu-` binutils | `11-6ch-usbup.json` matches (skips with `m68k-elf-`) |
| `webbuild_check.sh`, `webflash_check.sh` | node, npm | `builder.js` produces the same bytes as `build.py` |
| `webflash_smoke.sh` | node, npm, network | jsdom smoke test of the flasher page |
| `py_compile` | — | Python syntax |
| `ref_mainos.py --check` | firmware files | `REF_MAINOS`/`REF_MODS` hashes match |
| `gen_<mod>.py --check` | firmware, toolchain | Tweak JSON is up to date |
| `test_<mod>.py` | firmware, unicorn, numpy | Emulation proof passes |

Logs go to `build/validate/*.log`. Exit 1 if anything failed.

---

## Pi Setup

[Pi](https://pi.dev) is the coding agent used on this project, installed via npm:

```sh
npm install -g @earendil-works/pi-coding-agent
```

### Required packages

Install these pi packages (reasons below):

```sh
pi install pi-claude-bridge          # route to Claude Max via Claude Code
pi install context-mode              # efficient handling of large outputs
pi install git:github.com/HazAT/pi-interactive-subagents  # spawn the .pi/agents/* subagents
pi install @juicesharp/rpiv-ask-user-question  # ask the user questions
pi install pi-web-access             # fetch web pages (REA docs, etc.)
```

Other packages Maxime uses (optional): `@router-for-me/pi-cliproxyapi-provider`, `@deevus/pi-wayfinder`, `pi-atelier`, `pi-lmstudio`, `@villoh/pi-tools`.

### Claude bridge configuration

To use your Claude Max subscription through Claude Code, create `~/.pi/agent/claude-bridge.json`:

```json
{
  "provider": {
    "plan": "max"
  }
}
```

The subagents in `.pi/agents/` reference models like `claude-bridge/claude-opus-5-5`, which route through this bridge.

### Minimal `~/.pi/agent/settings.json`

```json
{
  "packages": [
    "pi-claude-bridge",
    "context-mode",
    "git:github.com/HazAT/pi-interactive-subagents",
    "@juicesharp/rpiv-ask-user-question",
    "pi-web-access"
  ],
  "defaultProvider": "claude-bridge",
  "defaultModel": "claude-opus-5-5"
}
```

### Why `defaultProvider` and `defaultModel` matter

When pi starts without a model (a new `pi` session, or a subagent spawned without an `agent:` definition or an
explicit `model:`), it picks one in this order: `defaultProvider` + `defaultModel` from settings if that provider
has credentials; otherwise its built-in provider list, where `anthropic` comes first with `claude-opus-4-8`. On a
machine that also holds an Anthropic API key in `auth.json`, a bare start therefore goes to the Anthropic API
directly, outside the Claude plan, and fails with
`Third-party apps now draw from your extra usage, not your plan limits` once that usage is exhausted.

The two settings above pin every bare start to the bridge. A default that is not available on a machine is
ignored (pi falls back to its automatic choice), so the setting is harmless for contributors without the bridge.
`/model` then `select as default` writes the same two keys. Pi reads them again only at startup: switch the
running session with `/model` if needed.

Two more guards live in the repository: every spawn names an agent (`agent: mc-…`, `mc-worker` for a task no
role covers), so the extension passes `--model` explicitly; and the generic agents bundled with
`pi-interactive-subagents` (`worker`, `scout`, `planner`, `reviewer`, `visual-tester`) are never used here, as
they point at `anthropic/…` models.

### Project trust

Pi loads the project layer (`.pi/agents/`, `.pi/prompts/`) only after you grant project trust. On first run in the repo, pi prompts you. After trust is granted, run `/reload` if you change those files.

---

## Project Agent Layer

### Subagents (`.pi/agents/*.md`)

| Agent | Model | Role | When spawned |
|---|---|---|---|
| `mc-planner` | `claude-opus-5-5`, high | Interactive design with Maxime (French), writes the plan | `/new-mod`, planning phase |
| `mc-scout` | `claude-sonnet-5-5`, minimal | Read-only map of notes, mods, free space, branches | `/new-mod` step 1, `/investigate` |
| `mc-reverser` | `claude-fable-5-1`, high | Reverse-engineers the OS, writes note's OS and design sections | After plan approval |
| `mc-firmware-dev` | `claude-fable-5-1`, high | ColdFire code, generator, tweak JSON, proof, PROVENANCE, BUILD.md | After design is done |
| `mc-web-dev` | `claude-sonnet-5-5`, medium | Flasher card, guide, release notes, stamp, README | After tweak is proven |
| `mc-reviewer` | `claude-opus-5-5`, high | Rules and firmware-safety review, no edits | Before push, on demand |
| `mc-validator` | `claude-haiku-4-5`, minimal | Runs `validate.sh`, reports summary | `/validate`, before push |
| `mc-worker` | `claude-opus-5-5`, medium | Any delegated task no role covers (inventory, bulk rewrite, research with files), only the files the task names | Ad-hoc, by the orchestrator |

All models are `claude-bridge/…`. Only one editing agent runs at a time; read-only agents may run in parallel.
Never spawn a subagent without `agent:` (or an explicit `model: claude-bridge/…`): see the settings section above.

### Prompts (`.pi/prompts/*.md`)

| Command | Arguments | What it does |
|---|---|---|
| `/new-mod` | `<what the musician wants>` | Full workflow: scout → planner → branch → reverser → firmware-dev → web-dev → reviewer → validator → draft PR |
| `/fix-mod` | `<mod id> <what goes wrong>` | Reproduce in emulation, fix, re-prove, release entry, draft PR |
| `/investigate` | `<question>` | Answer a feasibility question from evidence without writing a mod |
| `/validate` | `[options]` | Run `validate.sh`, report PASS/FAIL/SKIP with log excerpts |
| `/review-branch` | `[branch]` | Spawn `mc-reviewer`, summarise verdict and P0/P1 findings |
| `/mark-tested` | `<mod id> <date> <report>` | Record Maxime's hardware result, flip mod to tested if it works |

### Skills (`.agents/skills/*/SKILL.md`)

| Skill | What it covers | When loaded |
|---|---|---|
| `modded-cycles-workflow` | End-to-end checklist for shipping a mod or fix | Starting or planning any mod |
| `mainos-reverse-engineering` | OS addresses, disassembly, `scripts/mainos.py`, OS map | Needing an address or hook point |
| `coldfire-patching` | ColdFire code, hook styles, free space, toolchain, safety | Writing code into the firmware |
| `tweak-generators` | `tools/gen_*.py`, tweak JSON, `--check`, PROVENANCE | Creating or changing a tweak |
| `emulation-proofs` | Unicorn proofs, rigs, EMAC, bug reproduction | Proving a mod, reproducing a bug |
| `flasher-integration` | os.json, tweaks.js, REF_MAINOS/REF_MODS, FEAT texts, smoke tests | Putting a tweak into the OS, changing a feature's texts or status |
| `bilingual-user-docs` | Guide, release notes, card texts, README row, stamp | Documenting for users |
| `french-lab-notes` | `notes/NN-*.md`, certainty tags, hardware results | Writing or updating notes |
| `repo-validation` | `validate.sh`, checks list, reading results | Before commit/push |
| `hardware-test-handoff` | Commit, PR body, test plan, flipping to tested | Opening a PR, recording test |
| `licensing-provenance` | Third-party code, PROVENANCE.md, THIRD-PARTY-NOTICES | Using outside code |

---

## REA (Reverse Engineer Anything)

[REA](https://github.com/morluto/rea) is an MCP server for reverse engineering. It can disassemble native binaries via Ghidra, Hopper, IDA, objdump, or Rizin.

### What REA brings to this project

The MAIN OS is a raw big-endian ColdFire (m68k) binary extracted from section 3 of the `.syx`, loaded at virtual address `0x40000400`. Currently, we use:

- **m68k binutils** (`m68k-elf-objdump`) for disassembly via `scripts/mainos.py`
- **Unicorn** for emulation proofs (with `tools/emu/emac.py` for correct EMAC)

REA could provide an interactive decompiler session if configured with a suitable provider.

### Provider choice on macOS

| Provider | Suitability |
|---|---|
| **objdump** | Works with our existing m68k binutils. REA's `inspect_with_objdump` can call it, but you must configure `REA_OBJDUMP_COMMAND=m68k-elf-objdump`. Limited to disassembly (no pseudocode). |
| **Rizin** | Supports m68k via `rz-asm -a m68k`. Can disassemble raw binaries with base address (`-B 0x40000400`). No decompiler. |
| **Ghidra** | Supports ColdFire (`68000:BE:32:Coldfire` language). Provides pseudocode. Requires importing raw binary at base `0x40000400`. Ghidra headless can be automated. |
| **Hopper** | macOS-native, but m68k support is limited (68000, not ColdFire-specific). |

**Recommended**: Ghidra for pseudocode, or objdump for quick disassembly (already installed).

### Limitations

- REA does not automatically handle raw binary imports with a custom load address. You must configure Ghidra/Rizin manually to import `build/mainos.bin` at base `0x40000400`.
- Capstone (used by some tools) does not decode ColdFire-only instructions (`byterev`, `mvs`, `mvz`, `mov3q`, EMAC). The m68k binutils and Ghidra do.
- Provider environment variables (`REA_OBJDUMP_COMMAND`, `GHIDRA_INSTALL_DIR`) must be set if not using defaults.

### MCP registration for pi

Register REA in `.pi/mcp.json` (project-level, loaded after trust). The entry is **disabled by default** so pi does not start REA unless explicitly enabled.

To enable: edit `.pi/mcp.json` and set `"enabled": true`, then run `/reload` in pi.

Environment variables for providers (set in your shell or `.zshrc`, not in the JSON):

```sh
export REA_OBJDUMP_COMMAND=m68k-elf-objdump
export GHIDRA_INSTALL_DIR=/path/to/ghidra_11.x
```

---

## Conventions Recap

- **[AGENTS.md](AGENTS.md)**: Hard rules, languages, skills table, repository map, PR workflow.
- **[CONTRIBUTING.md](CONTRIBUTING.md)**: License terms for contributions.
- **[notes/README.md](notes/README.md)**: Index of technical notes (French).
