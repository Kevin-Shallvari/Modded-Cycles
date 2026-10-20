# AGENTS.md — tools/

The Python build, one generator per mod, the ColdFire sources, and the emulation proofs. Read the root
[`AGENTS.md`](../AGENTS.md) first. Procedures live in skills:

| Task | Skill |
|---|---|
| a generator, a tweak JSON, `--check` | [`tweak-generators`](../.agents/skills/tweak-generators/SKILL.md) |
| ColdFire code in `machines/`, hooks, free space, toolchain | [`coldfire-patching`](../.agents/skills/coldfire-patching/SKILL.md) |
| a proof in `emu/` | [`emulation-proofs`](../.agents/skills/emulation-proofs/SKILL.md) |
| OS addresses, disassembly | [`mainos-reverse-engineering`](../.agents/skills/mainos-reverse-engineering/SKILL.md) |
| `os.json`, `gen_flasher_tweaks.py`, `ref_mainos.py`, `web*_check`, `webflash_smoke.js` | [`flasher-integration`](../.agents/skills/flasher-integration/SKILL.md) |

Method and safety rules in full: [`notes/05-methode-patch.md`](../notes/05-methode-patch.md); platform and ISA:
[`notes/03-plateforme-coldfire.md`](../notes/03-plateforme-coldfire.md).

## Local invariants

- Python 3, **standard library only** for everything that builds or flashes (`build.py`, `mtlib/`,
  `gen_flasher_tweaks.py`, `ref_mainos.py`, `check_overlaps.py`, `registry.py`): users run them without installing
  anything. Only code-mod generators and `emu/` may need `unicorn`, `numpy` and the m68k toolchain.
- New or rewritten files are in **English**; older files keep their French comments: keep a file consistent, do not
  translate for its own sake. A module docstring says what the mod does, where its code lives, its note, and the
  command line.
- Addresses are ColdFire VAs of OS 1.13; section 3 offset = `VA - 0x40000400` (`build.BASE`).
- Every generated file in the repo passes its generator's `--check`; `old` bytes always come from the official image.
- Reuse the shared writers (`usb_steady.py`, `voice_loop.py`, `gov_asm.py`, `sprites.py`) instead of copying bytes.
- `build.py` and `docs/flasher/builder.js` read tweaks identically; change both in the same commit.
