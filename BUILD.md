# Building the OS from the command line

The web flasher is a port of the Python toolchain in `tools/`. Everything below runs with Python 3 and its standard
library; no compiler is needed to **build** the OS. Compiling or assembling the code of a tweak (the generators) and
running the emulation proofs need more: see [`DEVELOPMENT.md`](DEVELOPMENT.md).

> No Elektron firmware is included in this repository. You bring **your own** official files from elektron.se:
> `model-cycles_OS1.13.syx` (SHA-256 `44fe586269631a0ca7da25a3383fc6733c314809505fc3cc52f1e0ed9800640c`) and
> `Syntakt_OS1.42.syx` or `Syntakt_OS1.41.syx` (same audio program). Put them in `firmware/`, which is git-ignored.
> Flashing a modified OS is at your own risk; keep a MIDI interface for the way back ([`RECOVERY.md`](RECOVERY.md)).

## The Modded Cycles OS

`os.json` at the root of the repository is the recipe: the ordered list of tweak ids the OS is made of. Build it:

```sh
python3 tools/build.py -i firmware/model-cycles_OS1.13.syx --syntakt firmware/Syntakt_OS1.42.syx --os \
  -o build/modded-cycles-os_2.0.syx
```

The build applies each tweak's writes to section 3 (the MAIN OS) of your file, checking every `old` byte, appends the
payloads (Model-TG's code, the Syntakt engines extracted from your Syntakt file, MACRO and ACID), repacks the section
(aPLib) and re-signs the container (HMAC). It prints the SHA-256 of the patched MAIN OS. For version 2.0 it must be:

```
82a79f453151cbaceffdd047a646c96721f3ae3849a28f7821928bfbd4a1cca9
```

The same value is the `REF_MAINOS` entry of `docs/flasher/app.js`: the web flasher refuses a build whose MAIN OS
differs. `--expect-mainos <sha>` makes `build.py` refuse it too. The SHA-256 of the whole `.syx` depends on the
packer and is not a reference.

Flash the result with the web flasher ("Download the .syx" is the same file), with Elektron Transfer, or, if the
machine no longer starts, through the startup menu ([`RECOVERY.md`](RECOVERY.md)).

## Development builds

`tweaks/model-cycles_OS1.13/` is the library of every tweak the project has built and proven, including those that
are not in the current OS (6-channel USB audio for good, `6ch-usbup`, the per-track filter, the Optimised OS, the Syntakt engine
combinations, Model-TG on its own, diagnostics). `build.py -t` builds any compatible set of them:

```sh
python3 tools/build.py --list                                     # every tweak of the library
python3 tools/build.py -i firmware/model-cycles_OS1.13.syx -t 6ch-usbup,arp,tempo-max -o build/dev.syx
python3 tools/build.py -i firmware/model-cycles_OS1.13.syx --syntakt firmware/Syntakt_OS1.42.syx \
  -t model-tg-st,syntakt-tg-sd-cp -o build/dev.syx                # Model-TG with two Syntakt engines
```

`build.py` refuses two tweaks that declare a conflict, a tweak whose `requires` is missing, and a write into a `0xFF`
zone the original image points into (unless a chosen tweak redirects that pointer). These builds have no reference
hash in the flasher and are for developers: never distribute them.

## Regenerating what is generated

A tweak JSON is never edited by hand: its generator writes it from the sources in `tools/machines/<mod>/` and checks
the stock bytes in your official file. After changing a generator or its sources:

```sh
python3 tools/gen_<mod>.py --cycles firmware/model-cycles_OS1.13.syx          # rewrites tweaks/.../NN-<id>.json
python3 tools/gen_<mod>.py --cycles firmware/model-cycles_OS1.13.syx --check  # validation: up to date?
python3 tools/registry.py                                                     # REGISTRY.md (free space, hooks)
python3 tools/check_overlaps.py                                               # no shared bytes between buildable tweaks
```

After changing `os.json` or a tweak of the OS:

```sh
python3 tools/gen_flasher_tweaks.py                                           # docs/flasher/tweaks.js + served licenses
python3 tools/ref_mainos.py --cycles firmware/model-cycles_OS1.13.syx --syntakt firmware/Syntakt_OS1.42.syx
                                                                              # REF_MAINOS / REF_MODS in app.js
tools/webflash_smoke.sh firmware/model-cycles_OS1.13.syx firmware/Syntakt_OS1.42.syx   # the page builds the same OS
```

Some generators compile C with the m68k toolchain and their committed output depends on the compiler version
(`DEVELOPMENT.md`); `--check` tells you when your toolchain does not reproduce the committed bytes.

## Proving a tweak

Every tweak has a proof in `tools/emu/` that runs the OS's own code in the Unicorn emulator, stock against patched,
alone and with the rest of the OS:

```sh
python3 tools/emu/test_arp.py --cycles firmware/model-cycles_OS1.13.syx
python3 tools/emu/test_arp.py --cycles firmware/model-cycles_OS1.13.syx --syntakt firmware/Syntakt_OS1.42.syx \
  --with model-tg-st,sample-preview-st,trig-hold,tempo-max,boot-anim,multiline-browser,level-pan-values,trigless-dim,midi-live-both,mod-settings,lfo-plus,syntakt-tg-sd-cp-toy-bits-swarm-macro-acid
python3 tools/emu/test_mod_settings.py --cycles firmware/model-cycles_OS1.13.syx \
  --syntakt firmware/Syntakt_OS1.42.syx              # proofs that build the whole OS from os.json themselves
python3 tools/emu/test_step_rec.py --cycles firmware/model-cycles_OS1.13.syx --syntakt firmware/Syntakt_OS1.42.syx
```

The exact runs each proof supports are in its docstring (`python3 tools/emu/test_<mod>.py --help`). The notes in
`notes/` explain what each proof checks and why.

## Other machines

- **The OS on a Model:Samples** (notes/57): `tools/mods_for_samples.py` puts a built OS into the official
  Model:Samples container, signed with the Samples key, in the packing of the OS the machine runs. The web flasher
  does the same when you choose a Model:Samples in the first tab.
- **Samples OS on a Model:Cycles, Cycles OS on a Model:Samples** (notes/41): `tools/crossflash.py`.

Both need the official `model-samples_OS1.13.syx` as well.
