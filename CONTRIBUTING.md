# Contributing to Modded Cycles

Thanks for wanting to help. Bug reports, test reports, ideas and code are all welcome: open an
[issue](https://github.com/18nelli18/Modded-Cycles/issues) or a pull request, or come and talk on the
[Discord](https://discord.gg/hWegtJZcmm), which is where the project is run day to day.

## What the project is, and is not

Modded Cycles is a community, open-source, free OS for the Model:Cycles. Its goal is to push the machine as far as
it goes **without changing Elektron's workflow**: new machines, new modulation, better everyday gestures, all
integrated the way an Elektron feature would be. It is **one OS** that everyone runs, not a catalogue of mods to
pick from, and it is not a mod store: a mod that works well and is stable is not automatically integrated.

A feature joins the OS when:

- the community wants it (the Discord is where that shows), and it has real value for the way people play;
- it fits the workflow: Elektron-like shortcuts and screens, no surprises on the original machines;
- it is **compatible with everything already in the OS**: no shared bytes, no shared storage, no conflict
  declared, payloads chained; a feature that needs another one to be unticked does not exist any more;
- it is proven in emulation on the OS's own code, alone and with the whole OS;
- it has been tested on a real Model:Cycles (by Maxime, who merges) before it is marked *Tested*;
- its processor cost is known and acceptable: the average musician should not have to think about load.

Engines are the exception to "one of each": several kicks or several synth engines are fine as long as each one is
distinct enough to earn its place.

The maintainer (Maxime) decides. When a freeze is on (as announced on the Discord), fixes and integration work are
merged, new features wait.

## The shape of a contribution

The tools, the checks and the agent setup are described in [`DEVELOPMENT.md`](DEVELOPMENT.md); the step list a
feature goes through is in [`AGENTS.md`](AGENTS.md) and the `modded-cycles-workflow` skill. In short:

1. **Talk first.** Open an issue or a Discord thread describing what the musician gets. Reserve the free space you
   intend to use (`tweaks/model-cycles_OS1.13/REGISTRY.md`) so two contributors do not take the same bytes.
2. **One feature, one branch, one pull request**, opened as a draft, with: a French technical note in `notes/`, the
   generator and sources, the tweak JSON it writes, the Unicorn proof (alone and `--with` the tweaks of `os.json`),
   the feature in `os.json` with `"status": "experimental"`, the regenerated files, the guide section and release
   entry in English and French, the `FEATURES.md` and README rows.
3. **Say what you could not check.** The PR body lists the checks that did not run on your machine (no toolchain,
   no official files, no network) instead of skipping them silently, and what Maxime should test on the hardware.
4. **Numbers come last.** Note numbers, tweak numbers, versions and stamps collide when several PRs are open: say
   which ones you took, and expect the maintainer to renumber at merge time.
5. **Hardware results are reported, never assumed.** A feature becomes *Tested* in a separate commit after Maxime
   has run it on his Model:Cycles. Your own tests are welcome in the PR; they do not flip the status.

Small, focused pull requests are merged quickly. A fork's whole `main` branch cannot be reviewed: split it.

## License of your contribution

- By opening a pull request, you agree that your contribution is licensed under the [MIT License](LICENSE), like the
  rest of the project.
- A mod folder may carry its own permissive license instead (MIT, BSD, ISC or 0BSD) in a `LICENSE` file next to its
  sources: say so in the pull request. Copyleft code (GPL and the like) cannot go into the web flasher's bundle.
- If your work builds on someone else's code, say where it comes from and under which license, so it can be credited in
  [`tweaks/model-cycles_OS1.13/PROVENANCE.md`](tweaks/model-cycles_OS1.13/PROVENANCE.md) and
  [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md). Do not transcribe or closely paraphrase code whose license
  does not allow it (GPL code into MIT files, code with no license at all).
- Work sent privately (on Discord, as `.syx` files or scripts) is published only after its author has said yes in
  writing, with the credit they want.

## Elektron firmware

Never commit or attach an Elektron firmware image, original or modified, nor anything extracted from one (sections,
dumps, copied routines). The build reads the user's own official file; a tweak carries only its writes and the short
`old` bytes that check that file. Firmware files you build for testing stay on your computer.

## Reporting a bug

Say which version of the OS you flashed (the number shown in the flasher), which machine (Model:Cycles or
Model:Samples), what you did (buttons, in order), what you expected and what happened. If the machine showed an
exception screen, copy its `VEC`, `SR` and `ADDR` values. A short project or pattern that reproduces the problem is
the most useful thing you can send.
