# Recovery: bringing back the official OS through the startup menu

The web flasher is the normal way to install the Modded Cycles OS and to go back to the official firmware (its
**Official firmware** tab). This page is for the day the machine does not start any more, or refuses updates over
USB: the Model:Cycles keeps a **startup menu** in a part of the flash that OS updates never write, and that menu
can always reinstall an OS. It only listens to the **MIDI IN** port, never to USB.

## What you need

- **A MIDI interface** whose output is connected to the Model:Cycles **MIDI IN**: a TRS output and a stereo
  mini-jack cable (3 contacts, TRS, not a mono TS cable), or a DIN output and the adapter that came with the
  machine. The Model:Cycles MIDI IN is a 3.5 mm jack; both TRS types A and B are accepted (notes/12).
- **The official OS file** `model-cycles_OS1.13.syx`, unzipped from elektron.se. It is your rescue image: keep it
  at hand before any flash.
- **Python 3** and this repository. The scripts install `python-rtmidi` in a local virtual environment the first time
  (on macOS the compiler may be asked for once with `xcode-select --install`; on Linux the ALSA headers, for example
  `sudo apt install libasound2-dev build-essential`).

## The sequence, screen by screen

1. Turn the Model:Cycles off. Connect the MIDI interface output to its MIDI IN.
2. Hold **FUNC** and turn the machine on: the **STARTUP MENU** appears.
3. Press **TRIG 4** (OS UPGRADE). The screen shows **READY TO RECEIVE**.
4. On the computer, send the file to the port of the **MIDI interface** (not a USB port of the Model:Cycles, which
   the startup menu ignores):

   ```sh
   ./flash.sh firmware/model-cycles_OS1.13.syx          # macOS / Linux (flash.bat on Windows)
   ./flash.sh --verify firmware/model-cycles_OS1.13.syx # only checks the file, sends nothing
   ```

   The script checks the file (packet checksums, device id), lists the MIDI output ports, asks which one to use,
   and sends the file at MIDI speed. The screen shows **RECEIVING…** then **UPDATING FLASH**. Five to ten minutes.
5. The machine restarts by itself on the OS it received. Do not turn it off before.

Without the scripts, any SysEx tool works (SysEx Librarian on macOS, Elektron's C6): put the machine in OS UPGRADE
and send the `.syx` to the interface connected to the MIDI IN. The scripts add the checks and a sending pace the
machine keeps up with.

## Pace

If packets get lost (the screen stays on RECEIVING…), turn the machine off and on, enter OS UPGRADE again and send
more slowly:

```sh
python3 tools/flash.py firmware/model-cycles_OS1.13.syx --port "NAME OF YOUR INTERFACE" --send --pace 2.0
```

The default pace is 1.4.

## If it does not work

| Symptom | Likely cause | What to do |
|---|---|---|
| The screen stays on `READY TO RECEIVE` while the progress bar moves | wrong port, cable the wrong way round (OUT → IN), mono (TS) jack instead of stereo (TRS), or a USB port of the machine chosen | pick the port of the **MIDI interface**; check the cable (3-contact stereo jack); USB never works in the startup menu |
| Stuck on `RECEIVING…` | a packet was lost | harmless: power cycle, enter OS UPGRADE again, send with `--pace 2.0` |
| "no MIDI output port found" | interface not connected or not recognised | connect it before running the script; check it appears in the system |
| `python-rtmidi` does not install | missing compiler or headers | follow the script's message (Xcode on macOS, ALSA on Linux, C++ Build Tools on Windows) |
| "the file does not verify" | corrupt `.syx` or wrong version | download the official file again |

## Before going back to the official OS

Set every track that uses an added machine (7 to 14: Sampler, the Syntakt engines, MACRO, ACID) back to one of the
six original machines (Kick to Chord), and set **Device Config › Transfer** to CYC. The official OS has no machine
beyond Chord: a project left on machine 9 would open on a machine the official OS does not have.

## A Model:Samples

A Model:Samples running the Modded Cycles OS goes back to its own OS from the flasher's **Samples OS** tab
("Model:Samples: back to its OS"), over USB. If that ever failed, its startup menu accepts the official
`model-samples_OS1.13.syx` through its MIDI IN the same way, with the Model:Samples device id (the scripts detect it
from the file).

The transport and recovery details are in [`notes/06-flash-et-recuperation.md`](notes/06-flash-et-recuperation.md)
and [`notes/12-flash-par-jack-trs.md`](notes/12-flash-par-jack-trs.md) (French).
