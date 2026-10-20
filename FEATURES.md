# Modded Cycles OS 2.0: feature inventory

This file is a complete overview of what Modded Cycles adds to or changes in the Elektron Model:Cycles OS 1.13. For
each feature it covers the keys that reach it, what the screen shows, its limits, where it comes from and whether it
has been tested on a Model:Cycles. It is written for someone who knows the Model:Cycles and wants the full picture
before reworking things. It has no addresses or offsets; those are in the French notes (`notes/`). Written on
2026-10-18, from the committed guide, README, flasher texts, release notes and notes, plus Model-TG's own
documentation at its tag `v1.1.0`.

**OS 2.0 composition:** Model-TG v1.1.0 (Sampler machine and everything it brings, including drumkilla's latching
mute, trig preview and scrolling names), sample preview, the five Syntakt engines (SD VINTAGE, CP VINTAGE, SY TOY,
SY BITS, SY SWARM), MACRO, ACID, arpeggiator, easier trig removal, tempo up to 546 BPM, startup animation, multi-line
browser, volume/pan as numbers, dimmed trigless trigs, live MIDI OUT + THRU toggle, LFO 2/3/4, Mod Settings
(USB audio in stereo or six tracks, added on 19/10/2026) and step record (added on 20/10/2026).

How to read the status lines:

- **Tested on a Model:Cycles on DD/MM/YYYY**: the date comes from the note or the commit that recorded Maxime's report
  (or the contributor's report, where stated). "With …" lists the other mods that were on the machine.
- **Experimental**: the feature is marked experimental in `os.json`, or no hardware test is recorded.
- The sources record no hardware test of **the exact OS 2.0 bundle**. The largest combinations tested are listed per
  feature. `os.json` marks the OS itself `"status": "experimental"` until that test.

Key names are printed **in bold**, as they appear on the panel: **FUNC**, **TRK** (the guide also writes TRACK),
**LEVEL/DATA**, **TEMPO**, **PITCH**, **DECAY**, **COLOR**, **SHAPE**, **SWEEP**, **CONTOUR**, **PUNCH**, **TRIG 1–16**
(the step keys), **T1–T6** (the track pads), **RETRIG**, **MACHINES**, **[LFO]**, **PAGE**, **SETTINGS**, **REC**,
**PLAY**, **PATTERN**. Model-TG's own documentation calls **MACHINES** "PRESET" and the back key "return"; this
project's guide calls the back key **BACK**. This file uses **MACHINES** and **BACK**.

---

## Contents

1. [Shortcut map](#1-shortcut-map)
2. [Machines and sound](#2-machines-and-sound)
   - [2.1 Sampler (Model-TG), overview](#21-sampler-model-tg-overview)
   - [2.2 Syntakt engines](#22-syntakt-engines)
   - [2.3 MACRO machine](#23-macro-machine)
   - [2.4 ACID machine](#24-acid-machine)
   - [2.5 LFO 2, 3, 4](#25-lfo-2-3-4)
   - [2.6 Order of the machines in OS 2.0](#26-order-of-the-machines-in-os-20)
   - [2.7 Load governor](#27-load-governor)
3. [Sequencer](#3-sequencer)
   - [3.1 Arpeggiator](#31-arpeggiator)
   - [3.2 Easier trig removal](#32-easier-trig-removal-trig-hold)
   - [3.3 Trig preview](#33-trig-preview)
   - [3.4 Tempo up to 546 BPM](#34-tempo-up-to-546-bpm)
   - [3.5 Step record](#35-step-record)
4. [Live](#4-live)
   - [4.1 Latching mute](#41-latching-mute)
   - [4.2 Live MIDI OUT + THRU toggle](#42-live-midi-out--thru-toggle)
   - [4.3 Mod Settings: USB audio, stereo or 6 tracks](#43-mod-settings-usb-audio-stereo-or-6-tracks)
5. [Screen and browsing](#5-screen-and-browsing)
   - [5.1 Startup animation](#51-startup-animation)
   - [5.2 Multi-line browser](#52-multi-line-browser)
   - [5.3 Scrolling names](#53-scrolling-names)
   - [5.4 Volume and pan as numbers](#54-volume-and-pan-as-numbers)
   - [5.5 Dimmed trigless trigs](#55-dimmed-trigless-trigs)
   - [5.6 Sample preview](#56-sample-preview)
6. [Model-TG in depth](#6-model-tg-in-depth)
7. [Outside the single OS, and why](#7-outside-the-single-os-and-why)
8. [Open questions](#8-open-questions)

---

## 1. Shortcut map

Every key combination OS 2.0 adds or changes, sorted by the first key. "Stock, changed" means the gesture exists on
the original OS and the mod changes what it does. Combinations that only exist inside a Model-TG page (slice editor,
retrig page, menus) are listed with that page as context.

| Keys | What it does | Feature | Context / when it applies |
|---|---|---|---|
| **[LFO]** pressed again while the LFO page is open | Steps through LFO 1 → 2 → 3 → 4 (a big 2, 3 or 4 in the left box); the fifth press closes the page | LFO 2, 3, 4 | Stock, changed: the LFO page now has four layers. It always reopens on LFO 1 |
| **BACK** | Resets the master effects and a latched repeat (does not close the page) | Model-TG retrig page | Only on the retrig page |
| **BACK** | Closes the page | Model-TG mode menu, mode options, slice editor, System page | Inside those pages |
| **FUNC** tapped alone | Leaves latched mute mode | Latching mute | Only while mute mode is latched |
| **FUNC** + **LEVEL/DATA** (turn) | Shows the pan as a number (-64 to 63) in place of the "R" at the right of the pan bar; steps of 1 instead of 2 | Volume and pan as numbers | Stock gesture (pan), changed display and step size; main screen only |
| **FUNC** + **LEVEL/DATA** (press) | Toggles "THR forwards only" and "THR forwards and also sends the Cycles' own MIDI"; the screen shows THR either way | Live MIDI OUT + THRU toggle | SETTINGS › CONFIG › MIDI › PORTS, cursor on OUT/THRU, set to THR |
| **FUNC** + **LEVEL/DATA** (press) | Removes the selected slice's marker (it joins the one before) | Model-TG slice editor | Slice editor only |
| **FUNC** + **MACHINES** | Preset menu, as stock; on a Sampler track it also lists sample files; picking one loads it (*Sample loaded to Sampler*) | Model-TG Sampler | Stock gesture, extended. On a non-Sampler track Model-TG says *Select sample machine first!* |
| **FUNC** + **MACHINES** with a step held, then pick a sample | Sample lock on that step | Model-TG Sampler | Sampler track |
| **FUNC** + **MACHINES**, cursor on a sample file, then press the track's pad (or its trig keys in keyboard mode) | Plays the highlighted sample with the track's settings | Sample preview | Sampler tracks only. Nothing plays while scrolling |
| **FUNC** + **PAGE** | Scale menu, as stock, with two added items **Scl** and **Key** (Scale Lock) | Model-TG Scale Lock | Stock menu, extended |
| **FUNC** + **PITCH** (turn) | Lo-fi: OFF in the middle, sample rate on the left (46K down to 4K), bit depth on the right (12B down to 2B) | MACRO | **MACRO tracks only.** Stock, changed: on every other machine FUNC + PITCH still moves the note by semitones |
| **FUNC** + **RETRIG** | Retrig Setup menu, now with two more rows under Rte, Len, A.On: **Arp** (direction) and **Oct** (octaves) | Arpeggiator | Stock menu, extended |
| **FUNC** + trig key on an empty step | Places a trigless trig (stock); the key now lights dimmed | Dimmed trigless trigs | Grid mode |
| **FUNC** + trig key (on a step with a trig) | Stock change applied on release; now decided within 0.5 s instead of 0.2 s | Easier trig removal | Grid mode |
| **FUNC** + **TRIG 1–16** | Plays and selects slices 17–32 | Model-TG slice editor | Slice editor only |
| **FUNC** + knob 1 or 2 | Moves the slice start, then snaps it to the next zero crossing | Model-TG slice editor | Slice editor only |
| **FUNC** + **T1–T6** (mute) | On a Sampler track, the mute fades it out and ends its note. With Model-TG mutes take effect at once (this project's change) | Model-TG, latching mute | Mute mode, held or latched |
| **FUNC** held at power-on | Startup menu (recovery), **unchanged** | (stock) | Listed here because every mod is designed to keep it working |
| knob 1 / knob 2 / knob 3 | Move the selected slice start coarse / fine; zoom | Model-TG slice editor | Slice editor only |
| knobs 1–12 (PITCH … CHANCE) | The 12 master effects (Drive, Crush, Rate, Pump, Filter, Resonance, Ring mod, Noise riser, Gate, Tape stop, Vinyl, Flanger) | Model-TG retrig page | Retrig page only |
| any knob | Chooses the playback mode | Model-TG mode menu | Mode menu only |
| **LEVEL/DATA** (turn) | Shows the volume as a number (0 to 127) in place of the loudspeaker; steps of 1 instead of 2 | Volume and pan as numbers | Stock gesture, changed display and step size; main screen only |
| **LEVEL/DATA** (turn / press) | Moves between rows / edits a row | Model-TG mode options, retrig page rows (RETRIG, FX RETURNS) | Inside those pages |
| **LEVEL/DATA** (turn / press) | Selects a slice / splits the selected slice in two | Model-TG slice editor | Slice editor only |
| **LEVEL/DATA** (turn right) | Shows each track's share of the processor | Model-TG System page | Device Config › System |
| **LEVEL/DATA** (press, without FUNC) | Switches OUT/THRU to OUT, as stock; back on THR, forwarding only | Live MIDI OUT + THRU toggle | OUT/THRU row |
| **LEVEL/DATA** (press) on **Mods** | Opens Mod Settings, the page of the mods' own settings | Mod Settings | SETTINGS menu, last line (after Device) |
| **LEVEL/DATA** (press) on **USB Audio** | Switches between 2CH (the stereo mix, as stock) and 6CH (each track on its own channel); the Model:Cycles leaves the computer and comes back about a second later | Mod Settings: USB audio | SETTINGS › Mods |
| **MACHINES** held + **DECAY** | Attack (instant to about 2 s) | Model-TG | Every machine, including the Syntakt engines |
| **MACHINES** held + **SWEEP** | Filter (Model-TG's ladder low-pass) | Model-TG | Every machine. Same gesture as the per-track filter, which is why that mod is outside OS 2.0 |
| **MACHINES** held + **CONTOUR** | Resonance | Model-TG | Same note as above |
| **MACHINES**, then pick ACID / MACRO / Sampler / an engine | The added machines, after Chord | Machines | MACHINES menu, see [2.6](#26-order-of-the-machines-in-os-20) |
| **PAGE** with a trig key held | Plays that step (note, length, p-locks, sound lock) instead of turning the page | Trig preview | Sequencer stopped or paused. Stock, changed |
| **PATTERN** | Closes the retrig page so you can choose a pattern | Model-TG retrig page | Retrig page only |
| **PLAY** | Skips the current step (it stays as it was) | Step record | In step record, no note held |
| **PITCH** (turn) on a MACRO track | Note, as stock; the fine-tune parameter moved under FUNC + PITCH | MACRO | MACRO tracks |
| **PUNCH** | Arms tap slicing (*ARMED*), or stops it | Model-TG slice editor | Slice editor only |
| **REC** pressed twice quickly | Starts step record (*Step-rec: ON*): the notes played go one by one on the blinking step | Step record | Sequencer stopped (or paused). Stock, changed: the second press used to turn grid recording back off |
| **REC** | Stops step record (*Step-rec: OFF*) | Step record | In step record |
| **REC** + **PLAY** with the arpeggiator playing | Records each arpeggiated note on the step where it plays, with its length | Arpeggiator | Live recording |
| **RETRIG** held (or A.On on) + several notes held | Arpeggio at the Rte rate. With one note: the stock retrig | Arpeggiator | Stock, changed |
| **STOP** | Goes back one step | Step record | In step record, no note held; not before step 1 |
| **SETTINGS** tapped | Opens its usual menu, with one more line at the end: **Mods** (a puzzle piece) | Mod Settings | Stock menu, extended |
| **SETTINGS** held | No longer brings up the pattern save prompt; it is Model-TG's modifier key | Model-TG | Stock, changed (Model-TG's guide and this project's guide) |
| **SETTINGS** + **BACK** | Turns the master effects off from anywhere (*Master FX off*) | Model-TG | Anywhere |
| **SETTINGS** + **MACHINES** | Playback mode menu (One shot, Loop, Slice, Granular, Stretch, Pluck, Wave) | Model-TG Sampler | Sampler track |
| **SETTINGS** + **PUNCH** | Options of the current playback mode | Model-TG Sampler | Sampler track |
| **SETTINGS** + **REC** | Resample menu | Model-TG | Anywhere; the take goes onto the track you opened it on |
| **SETTINGS** + **RETRIG** | Retrig page: repeats on the trig keys, 12 master effects on the knobs, sidechain | Model-TG | Anywhere |
| **SETTINGS** or **RETRIG** | Closes the retrig page (effects stay on) | Model-TG | Retrig page |
| **SETTINGS** + trig key | Slide trig on / off (*Slide on* / *Slide off*); on an empty step, places a slide trig | Model-TG slide trigs | Grid mode |
| **T1–T6** | Mute / unmute, one finger | Latching mute | Latched mute mode |
| **T1–T6** (pads) | Choose which tracks the retrig page and its effects act on; an unlit pad drives the Pump | Model-TG retrig page | Retrig page only |
| **TRIG 1–16** held | Repeats the output, from 1/64 (key 1) to one bar (key 16), straight and triplet values in between | Model-TG retrig page | Retrig page only (Momentary or Latch) |
| **TRIG 1–16** | Play and select slices 1–16 | Model-TG slice editor | Slice editor only |
| **TRIG 1–16** after arming tap slicing | First press plays the sample from the start and clears the markers; each next press drops a marker | Model-TG slice editor | Slice editor, armed |
| trig key on a step that has a trig, released within 0.5 s | Removes the trig (stock: within 0.2 s) | Easier trig removal | Grid mode. Held longer: the trig stays and its settings show |
| **TRK** held + **FUNC** tapped | Latches mute mode; FUNC stays lit | Latching mute | Anywhere mute mode is reachable |
| **TRK** held + **T1–T6** | Selects a track, as stock | (stock) | Model-TG chose SETTINGS as its modifier so that TRK chords keep working |

Known collisions and raw spots, collected from the sources:

- **MACHINES held + SWEEP / CONTOUR** is Model-TG's filter and was also the per-track filter's gesture. That is the
  reason the per-track filter is outside OS 2.0 (flasher clash text: "both use MACHINES + SWEEP / CONTOUR for a track
  filter").
- **SETTINGS held** lost the stock pattern save prompt (Model-TG guide; this project's guide repeats it).
- **FUNC + PAGE** (Scale menu) carries Model-TG's Scale Lock. Chord Keys also changed the notes of the trig keys; the
  flasher listed that as their clash ("both change the notes of the TRIG keys").
- **FUNC + PITCH** means two different things depending on the machine (lo-fi on MACRO, semitones elsewhere).
- **FUNC + LEVEL/DATA**: turned on the main screen it is the pan (with a number); pressed on the OUT/THRU row it is
  the MIDI toggle. Different gestures and screens, so no clash, but the same pair of keys.
- **BACK on the retrig page** resets instead of closing, unlike everywhere else.
- **Model-TG's documentation uses key names not printed on the panel** ("PRESET" for MACHINES, "return" for BACK).
- **Model-TG queued mutes** until you left mute mode. This project changed it so mutes act at once (see
  [4.1](#41-latching-mute)).
- **Model-TG's Attack, Filter and Resonance p-locks** came back on other parameters after reloading a pattern; LFO
  2, 3, 4 fixes it (see [2.5](#25-lfo-2-3-4)).

---

## 2. Machines and sound

### 2.1 Sampler (Model-TG), overview

**What it does.** Adds a seventh machine, **Sampler**, that plays your own WAV files (48 kHz, mono or stereo) from the
Model:Cycles' storage, in seven playback modes, with slicing, resampling, a retrig page with 12 master effects, slide
trigs, Scale Lock, and Attack, Filter and Resonance on every machine. Every part is described in
[section 6](#6-model-tg-in-depth). This section only sums up how to start.

**How to use it** (guide, "Loading a sample"):

1. On the Model:Cycles, set **Device Config › Transfer** from **CYC** to **SMP**: Elektron Transfer now sees a
   Model:Samples. Send your WAV files (48 kHz, mono or stereo).
2. Set a track to the Sampler machine, the 7th, right after Chord.
3. Press **FUNC + MACHINES** (preset menu) and pick a file: the screen shows *Sample loaded to Sampler*.
4. "To give one step its own sample, hold the step, press **FUNC + MACHINES** and pick a file."

**Limits and interactions.**

- Up to 64 samples in memory, shared by every track and pattern that uses them. With the Syntakt engines (always the
  case in OS 2.0) the sample memory is **63 MB instead of 64**: the last MB runs the engines.
- "In SMP, use Transfer for samples only and never accept an OS update from it. Install an OS only while Transfer is
  on CYC; every power-on starts on CYC." The fast USB flasher also needs CYC.
- Tracks set to the Sampler don't play on another firmware.
- The load governor never turns the Sampler off, nor the track Model-TG is recording from or whose slices it is
  editing (notes/31 §4.5).

**Origin and license.** Model-TG by TinyGregAudio, MIT (`tweaks/model-cycles_OS1.13/LICENSE-Model-TG`), built by its
author's own build from tag `v1.1.0` (commit `70b39dd`). This project's changes: mutes at once in mute mode, the trig
preview pause fix in its copy, 1 MB less sample memory so the Syntakt engines fit (notes/31 §4.1, §10; notes/34).

**Status.** The flasher card and README say **Experimental**. The guide says: "Tested — Model-TG 1.1 with the 5
engines and 6-channel audio, on a Model:Cycles. Other choices are still marked experimental." The notes record:

- 01/10/2026: Sampler loads and plays, diagnostic firmware with the engines (v1.0.0, notes/31 §6).
- 02/10/2026: Model-TG 1.0 + the 5 engines + 6-channel audio, built by the flasher, "tout marche" (notes/31 §6).
- 03/10/2026: Model-TG v1.1.0 + the 5 engines + 6-channel audio, including a slide trig on an engine track, "c bon ça
  marche" (notes/31 §9); then with the immediate mutes and the arpeggiator, "ça fonctionne nickel" (notes/31 §10).
  On that date the Model-TG + 5 engines combination was marked tested again.

OS 2.0 contains that tested combination. The two sources disagree on the label: the Model-TG card says experimental,
the combination with the engines is marked tested.

### 2.2 Syntakt engines

**What it does.** Five of the Syntakt's digital machines become extra machines on the Model:Cycles. Their code is
copied from your own `Syntakt_OS1.42.syx` (1.41 works too) at build time, in the browser. In the emulator they produce
the same samples as the Syntakt.

| Machine on screen | Syntakt engine | Sound |
|---|---|---|
| SDVtg | SD VINTAGE | vintage snare |
| CPVtg | CP VINTAGE | vintage clap |
| SYToy | SY TOY | tuned toy-like percussion |
| SYBit | SY BITS | two digital oscillators, rate and bit reduction |
| SYSwm | SY SWARM | a swarm of detuned saws (supersaw) |

**How to use it.**

1. Press **MACHINES** and pick one of them. In OS 2.0 they are machines 08 to 12 (after Chord and the Sampler, see
   [2.6](#26-order-of-the-machines-in-os-20)).
2. The four machine knobs and **PUNCH** take the Syntakt's parameters. The screen shows their Syntakt names, and
   changing machine applies the Syntakt's defaults:

| | COLOR | SHAPE | SWEEP | CONTOUR | PUNCH |
|---|---|---|---|---|---|
| SDVtg | Inharm | Freq Complex | Pitch Sweep | Mod Envelope | Punch |
| CPVtg | Body Char | Balance | Spacing Crunch | Body Envelope | Punch |
| SYToy | Form | Impact | Bright | Partial Decay | Punch |
| SYBit | Detune (40–88) | Balance | Rate Redux | Waveform | Bit Redux |
| SYSwm | Noise Mod | Detune Anim | Detune | Osc Mix | Sub-octave |

3. With Model-TG they also get **MACHINES + DECAY / SWEEP / CONTOUR** (Attack, Filter, Resonance), slide trigs, and
   their processor time shows on Model-TG's System page.

**Limits and interactions.**

- A Syntakt voice costs a little more than an original voice (measured share of one audio block: original voice
  ≈ 6 %, Syntakt voice ≈ 7 %, mix and effects ≈ 40 %). The load governor (see [2.7](#27-load-governor)) fades out the
  least audible voice when the load stays too high.
- Needs the Syntakt OS file to build. No Syntakt is needed.
- "Before flashing another choice or the official firmware, set the tracks that use an added machine back to an
  original one (Kick to Chord)": otherwise **MACHINES** can freeze on those tracks.
- The engines' machine numbers change depending on whether Model-TG is in: projects made on one layout play another
  machine on the other.
- Not tried: resampling a track that plays a Syntakt engine (notes/31 §8).
- SP TWINSHOT is impossible (its samples are not in the OS file); the other Syntakt machines are analogue, so the
  port is complete (notes/24).

**Origin and license.** This project (bridge, relocation, governor). The engine code and tables are Elektron's: they
are not in the repository; a recipe copies them from the user's Syntakt file at build time (notes/17, `PROVENANCE.md`).

**Status.** Tested on a Model:Cycles. SD VINTAGE, CP VINTAGE, SY TOY, SY BITS and SY SWARM each on 30/09/2026
(notes/17–22); with Model-TG v1.1.0 and 6-channel audio on 03/10/2026 (notes/31 §9); with MACRO and Model-TG on
10/10/2026; with MACRO, ACID and Model-TG on 12/10/2026 (notes/54 §11.7).

### 2.3 MACRO machine

**What it does.** One extra machine, **MACRO**, holds the 47 synthesis models of Braids, Émilie Gillet's open-source
macro-oscillator. It is her own code, compiled for the Model:Cycles. In the emulator it gives exactly the samples of
that code on a computer.

**How to use it** (guide):

1. Press **MACHINES** and pick **MACRO** (machine 13 in OS 2.0, after the engines; its icon is Tone's).
2. Turn **SHAPE** (Model) to choose one of the 47 models, 0 to 46. "Lock it on a step to change model from one step to
   the next."
3. Shape the sound with **COLOR** (Timbre) and **SWEEP** (Color); what they do depends on the model.
4. **CONTOUR** (Env Timbre) lets the amp envelope open the timbre: "at 0, nothing; turned up, each note starts brighter
   and closes as it fades."
5. **PITCH** and the keys set the note as on the original machines. **DECAY**, **GATE** and **PUNCH** work as on Tone.
6. Lo-fi: hold **FUNC** and turn **PITCH**. Middle (default) = unchanged, screen shows **OFF**. Left = **RATE**, the
   sample rate drops step by step from 48 kHz to about 4 kHz (screen **46K** down to **4K**). Right = **BITS**, from
   12 bits down to 2 (screen **12B** down to **2B**). Shown in the large value window, one step per knob click.
   Can be p-locked.

| Model | Family | Models, in order |
|---|---|---|
| 0–8 | Analog-style waves | CSAW, MORPH, SAW/SQUARE, SINE/TRIANGLE, BUZZ, SQUARE SUB, SAW SUB, SQUARE SYNC, SAW SYNC |
| 9–13 | Three oscillators | TRIPLE SAW, TRIPLE SQUARE, TRIPLE TRIANGLE, TRIPLE SINE, TRIPLE RING MOD |
| 14–16 | Swarm, comb, toy | SAW SWARM, SAW COMB, TOY |
| 17–20 | Filtered waves | DIGITAL FILTER LP, PK, BP, HP |
| 21–24 | Formants and harmonics | VOSIM, VOWEL, VOWEL FOF, HARMONICS |
| 25–27 | FM | FM, FEEDBACK FM, CHAOTIC FEEDBACK FM |
| 28–33 | Physical models | PLUCKED, BOWED, BLOWN, FLUTED, STRUCK BELL, STRUCK DRUM |
| 34–36 | Drums | KICK, CYMBAL, SNARE |
| 37–40 | Wavetables | WAVETABLES, WAVE MAP, WAVE LINE, WAVE PARAPHONIC (chords) |
| 41–46 | Noises and particles | FILTERED NOISE, TWIN PEAKS NOISE, CLOCKED NOISE, GRANULAR CLOUD, PARTICLE NOISE, DIGITAL MODULATION |

**Limits and interactions.**

- Computed at 96 kHz as on the module, then filtered down to 48 kHz (flat to 19 kHz). Thirteen models whose sound only
  follows the note (CSAW, SAW/SQUARE, SQUARE SUB, SAW SUB, TRIPLE SAW, SQUARE, TRIANGLE and SINE, the four wavetable
  models, DIGITAL MODULATION) are computed at 48 kHz one octave up, for half the computing, and go back to 96 kHz on
  the highest notes.
- A MACRO voice costs about twice an original voice: under one for CLOCKED NOISE, about three times for HARMONICS
  (emulator figures; "memory access can make it heavier on the machine"). On its own MACRO has no governor; in OS 2.0
  the engines' governor looks after MACRO tracks too.
- The lo-fi replaces the fine tune on MACRO tracks only.
- With Model-TG, MACRO gets Model-TG's Attack, Filter and Resonance, and its time shows on the System page
  (notes/43).
- Set MACRO tracks back to an original machine before flashing anything else.

**Origin and license.** Braids from `pichenettes/eurorack` by Émilie Gillet, MIT (`LICENSE-Braids`), compiled
unchanged. Request from the Discord ("Mutable Instruments engines").

**Status.** Tested on a Model:Cycles on 07/10/2026; with the 5 engines and Model-TG on 10/10/2026; the 48 kHz
models on 11/10/2026; the lo-fi on **FUNC + PITCH** with its value on screen on 12/10/2026 (version 1.54; the first
lo-fi did not reach the fine tune on the machine, notes/55 §8).

### 2.4 ACID machine

**What it does.** One extra machine, **ACID**, an acid bass in the style of the TB-303: a saw or square wave through a
resonant filter with its own envelope and slide, plus a drive. The model follows Robin Schmidt's Open303, rewritten
in fixed point. Slides come from trig lengths.

**How to use it** (guide):

1. Press **MACHINES** and pick **ACID**, the last machine (14 in OS 2.0). Its icon is Tone's.
2. Shape it with the knobs. The defaults already give the squelch.

| Knob | Name on screen | What it does |
|---|---|---|
| COLOR | Cutoff (CUT) | the filter's cutoff: low is dark, high is open |
| SHAPE | Reso (RES) | the resonance, up to the squelch of the high settings |
| SWEEP | Env Mod (ENV) | how far the filter envelope opens the cutoff on each note |
| CONTOUR | Drive (DRV) | 0 is clean, warmth in the first quarter, a growl around the middle, fuzz at the top; level stays about the same |
| DECAY | — | the filter envelope's decay (0.2 to 2 s) and the amp's |
| PUNCH | — | off: saw wave; on: square wave |

3. Slide: "give a trig a length (LEN) that runs past the next trig, for example 1.06 or INF on neighbouring steps.
   The next note then glides from this one." With the default 1/16 on neighbouring steps, every note plays again.
   Played live, a note played while the previous one is still held slides too.
4. **PITCH**, the keys and **FINE** set the note. **GATE** on: notes hold their whole length, as on a 303. Velocity
   sets the volume.

**Limits and interactions.**

- One voice per track; the filter keeps running from note to note. A silent ACID track is not computed. Loud peaks
  are rounded off even at drive 0.
- About the cost of a Tone voice.
- "A trig that changes the machine (a MACHINE lock) always plays again." "A trigless trig with a NOTE lock glides to
  its note."
- Under a very heavy load the engines' governor can fade an ACID note out; that track's next trig then plays afresh
  instead of sliding.
- ACID's slide (pitch, by trig length) is separate from Model-TG's slide trigs (parameters, by SETTINGS + trig key).
  notes/54 §2: Model-TG's slide trigs "glide the parameters, not the note".
- Set ACID tracks back to an original machine before flashing anything else.

**Origin and license.** Model from Open303 by Robin Schmidt, MIT (`LICENSE-Open303`), rewritten for the ColdFire
(the model, not the code). The first version had an accent on CONTOUR; Maxime didn't find it useful, so it became
the drive (notes/54).

**Status.** Tested on a Model:Cycles on 11/10/2026 (first version, then the drive version); with all five engines and
MACRO, with and without Model-TG, on 12/10/2026; the anti-click fade-in on 18/10/2026 with the 5 engines and MACRO
(release 1.55).

### 2.5 LFO 2, 3, 4

**What it does.** Each track gets three more LFOs next to the original one: up to four LFOs on a track at once. Works
with or without Model-TG.

**How to use it** (guide):

1. Press **[LFO]** to open the LFO page as usual: this is LFO 1.
2. Press **[LFO]** again: a big **2** in the left box means you are now setting LFO 2. Again for 3, again for 4. "The
   fifth press closes the page. Next time the page opens on LFO 1."
3. On pages 2, 3 and 4, the knobs **SPD**, **MULT**, **WAVE**, **DEST** and **DEP** belong to that LFO. Pick a
   destination with DEST and raise DEP to hear it.

**Limits and interactions.**

- **FADE**, **SPH** and **MODE** are shared by the four LFOs: on pages 2 to 4 they change LFO 1's settings too. Trig
  retrig is shared as well.
- **LFO 2 is saved** with the sound (kit, sound pool) and can be p-locked (hold a trig and turn a knob on page 2);
  its SPD and DEP are stored a little less finely than LFO 1's (whole values shown come back exactly).
- **LFO 3 and 4 are for live play**: one setting per track whatever the pattern, kit or sound; not saved, back to
  defaults at power-on; cannot be p-locked ("turning a knob with a trig held changes the setting itself").
- An extra LFO aimed at LFO 1's destination does nothing. DEST skips destinations another LFO of the track already
  uses (NONE is always available). Two extra LFOs loaded onto the same destination add up.
- Old sounds load with LFO 2 at no destination. Sounds saved with DavidCaruso's firmware keep their LFO 2. The
  official OS loads sounds saved with this mod and ignores LFO 2.
- **Fixes a Model-TG bug**: p-locks on Attack, Filter and Resonance used to come back after reloading a pattern as
  locks on other parameters (NONE, LFO speed, multiplier). Patterns saved before keep the wrong locks.
- Cost: about 1.3 % of the audio time for LFO 2 on all six tracks, about 3.5 % with 2, 3 and 4 everywhere (emulator).
- Not with the per-track filter: both keep their settings in the same place of the sound.

**Origin and license.** Idea and first version by DavidCaruso (his firmware `Model-TG-VA-DR-v1`, shared on Discord
without source or license), rewritten by this project from the behaviour of his binary: none of his bytes are used.
DavidCaruso agreed to the MIT license on 11/10/2026 (notes/56 §1.3). His trig generator and VA machines were also
rewritten, then removed at Maxime's request on 11/10/2026.

**Status.** Tested on a Model:Cycles on 11/10/2026 (alone, with Model-TG, and with the full set), "ça marche nickel".

### 2.6 Order of the machines in OS 2.0

The guide's rule: the added machines come after Chord; the Sampler is the 7th, the engines follow in the order SD,
CP, TOY, BITS, SWARM, then MACRO, then ACID last. With everything in OS 2.0 (also the list in the draft `os.json`):

| # | Machine | # | Machine |
|---|---|---|---|
| 01–06 | Kick, Snare, Metal, Perc, Tone, Chord (stock) | 11 | SYBit |
| 07 | Sampler (Model-TG) | 12 | SYSwm |
| 08 | SDVtg | 13 | MACRO |
| 09 | CPVtg | 14 | ACID |
| 10 | SYToy | | |

A project that uses machine 08 or higher only plays the same machine on a firmware with the same layout. The single OS
fixes this layout for everyone, which removes the "the number depends on what you ticked" problem described all over
the guide.

### 2.7 Load governor

Not a feature you play, but it shapes every heavy machine above (guide, "Processor load"; notes/25, 30, 36):

- It measures every audio block. Under a sustained high load, voices that are dying out are stopped earlier (below
  −66 dB). If the load stays too high, it fades out the voice heard least in the mix (a muted track first, then the
  quietest), one at a time. A single heavy block does not trigger it.
- It covers the original machines, the Syntakt engines, MACRO and ACID. It never turns off the Sampler or the track
  Model-TG is recording or slice-editing.
- Advice from the guide when notes get cut: lower the volume of the track you can spare most, mute what you don't
  hear, shorten long decays, or use the delay and reverb less (about 12 % of the processor).

---

## 3. Sequencer

### 3.1 Arpeggiator

**What it does.** "The retrig becomes an arpeggiator: hold several notes on a track and they play one after another,
at the retrig rate. With a single note, it is the retrig you know."

**How to use it** (guide):

1. Press **FUNC + RETRIG**: below **Rte**, **Len** and **A.On** come two new lines, **Arp** (direction) and **Oct**
   (octaves). They are saved with the pattern, for each track.
2. Hold **RETRIG** (or turn **A.On** on) and hold several notes on the track: they play one after another at the Rte
   rate.
3. Add or release notes while it plays: the rhythm goes on and a new note takes its place. It stops when you release
   the last note.

| Arp | Order of the notes |
|---|---|
| UP | lowest to highest, then again (default) |
| DOWN | highest to lowest |
| UPDN | up then down, without repeating the notes at the ends |
| RAND | a held note at random, never the same twice in a row |
| PLAY | in the order you pressed them |
| OFF | the original retrig: the last note pressed is repeated |

**Oct** 2 to 4 adds the same notes one, two or three octaves higher, after the first octave.

4. Live recording (**REC + PLAY**): "the notes the arpeggiator plays are recorded one by one, each on the step where
   it plays, with its length."

**Limits and interactions.**

- Live recording keeps one note per step: above 1/16 on a track at 1×, only the last note of each step is kept. A
  single held note on 1 octave is recorded as before, as one trig with retrig.
- Default UP, 1 octave: existing projects behave as the stock retrig while one note is held.
- Settings use a pattern byte the original OS ignores: projects open everywhere.
- All machines, including the engines, MACRO, ACID and the Sampler.
- Model-TG's retrig page (**SETTINGS + RETRIG**) is a different thing: it repeats the output, not a note.
- Not confirmed on the machine: that Arp and Oct survive a save and a restart (notes/32 §10, "la tenue des réglages
  après redémarrage n'est pas confirmée explicitement").

**Origin and license.** This project, on Maxime's request (03/10/2026), MIT.

**Status.** Tested on a Model:Cycles on 03/10/2026 (with Model-TG, the 5 engines and 6-channel audio); live recording
on 04/10/2026 (version 1.14).

### 3.2 Easier trig removal (trig-hold)

**What it does.** On the stock OS, a press on a trig that lasts more than 0.2 s counts as a hold and the trig stays.
The soft keys often go past that. With this mod, you have half a second.

**How to use it** (guide):

1. "Press a trig key whose step already has a trig and let go within half a second: the trig is removed."
2. "Hold it longer: the trig stays and its settings show on the screen, as when you hold a trig on the stock OS."
3. "Turn a knob while you hold: the trig stays and gets the parameter lock, however short the press."

**Limits and interactions.**

- 0.5 s only on steps that already have a trig. On an empty step, the trig is placed at once, as before.
- "The other changes the OS makes when you let go (FUNC + trig key, lock trigs) follow the same half second."
- Goes with every other mod, Model-TG included. Interaction with Model-TG's **SETTINGS + trig key** (slide trig) is
  not described in the sources (see [Open questions](#8-open-questions)).

**Origin and license.** This project, from a Reddit report (notes/33), MIT.

**Status.** Tested on a Model:Cycles on 03/10/2026, with 6-channel audio, Model-TG, the 5 engines and the
arpeggiator.

### 3.3 Trig preview

**What it does.** Hear one step without starting the sequencer.

**How to use it** (guide):

1. With the sequencer stopped or paused, hold a trig key.
2. Press **PAGE**: the step plays with its note, length, p-locks and sound lock.

**Limits and interactions.**

- "The page doesn't turn and the trig isn't erased. It sounds whatever its condition or probability, even on a muted
  track."
- Fix by this project (04/10/2026): a MIDI Stop (for example from a DAW over USB) pauses the sequencer even when it is
  stopped, and PAGE then turned the page instead of playing the step. Now it also works paused. The same fix is
  applied to Model-TG's copy (notes/34).
- In OS 2.0 it comes inside Model-TG.

**Origin and license.** drumkilla, `elektron-model-tweaks`, MIT. Model-TG includes it.

**Status.** Tested by its author on his hardware (notes/15). The pause fix was tested on a Model:Cycles on 04/10/2026,
with 6-channel audio, Model-TG, the 5 engines, trig removal and the arpeggiator (notes/34).

### 3.4 Tempo up to 546 BPM

**What it does.** The tempo goes up to 546.0 BPM instead of 300.0.

**How to use it.** Press **TEMPO** and turn the knob as usual: above 300.0 it carries on, up to 546.0. Tap tempo and
an incoming MIDI clock follow too. The project saves it.

**Limits and interactions.**

- Why 546: the project stores the tempo in 1/120 of a BPM on 16 bits (65,535 / 120 = 546.1). Going higher would
  change the project format.
- Tempo-synced LFOs stay right. The original OS made an LFO at its highest speed and multiplier leave its cycle from
  351.6 BPM; the mod fixes that.
- A project saved above 300 BPM reopens at 120 BPM on the original OS.
- More notes per second means more load; the governor may fade a voice out with heavy machines.

**Origin and license.** This project (notes/38), MIT.

**Status.** Tested on a Model:Cycles on 04/10/2026.

### 3.5 Step record

**What it does.** With the sequencer stopped, the notes of a pattern are entered one step at a time: each note played
lands on the current step, which then moves on.

**How to use it** (guide):

1. Sequencer stopped, press **REC** twice quickly. The screen shows *Step-rec: ON*, **REC** stays lit and **TRIG 1**
   blinks fast (3.75 times a second): it is the current step.
2. Play a note: a **TRIG** key plays the active track chromatically (as when stopped), a pad **T1–T6** its own track,
   a MIDI keyboard the track it plays. The note and its velocity are written on the blinking step; the step moves on
   at the release.
3. Notes held together (two pads, for example) all go on the same step, which moves on at the last release.
4. **PLAY** skips a step, **STOP** goes back one (not before step 1). **REC** stops; step record also stops after the
   last step of the active track.
5. Knobs turned before a note: the sound changes as usual (it is heard); the note gets the new values as p-locks, and
   so do the next notes of that track, until the knobs are turned again (a value turned back to where it was is not
   locked any more). When step record ends, the sounds come back exactly as they were.

**Limits and interactions.**

- A step that already holds a trig: its note and velocity are replaced and its nudge cleared, as live recording does;
  its other settings and p-locks stay. PLAY leaves it as it is.
- How long a note is held is not recorded: a trig keeps the length its step already has.
- The cursor covers the steps of the active track when step record starts; a pad on a track with another length
  writes on the same step number.
- The lights: the active track's trigs on the page of the current step, the current step and its page light blinking,
  REC lit.
- A single **REC** press still toggles grid recording, and **REC + PLAY** still starts live recording. The first of
  the two presses turns grid recording on for an instant. FUNC, TRACK, PATTERN or SETTINGS held: the keys do what
  they always do.
- It stops when the sequencer starts (a MIDI Start), grid recording is turned on, or the pattern changes. In the last
  case the sound of the pattern you left keeps the knob changes (it is no longer the pattern on screen).
- Changes that the OS does not record in live recording are not locked either (volume and pan from the main screen,
  for instance).

**Origin and license.** This project (notes/73), MIT. A request from Maxime (20/10/2026).

**Status.** Tested on a Model:Cycles on 20/10/2026: Maxime reported "ça marche nickel" (it works perfectly) after the
test plan of PR #101 (notes/73 §7). Also checked in the emulator on the OS's own code, with everything else in OS 2.0
(what it writes is byte for byte what the OS's live recording writes for the same notes and knob turns).

---

## 4. Live

### 4.1 Latching mute

**What it does.** Mute mode stays on: you mute tracks with one finger, without holding FUNC.

**How to use it** (guide):

1. Hold **TRK** and tap **FUNC**: the mode locks and FUNC stays lit.
2. Tap **T1–T6** to mute or unmute the tracks.
3. A short tap on **FUNC** alone leaves the mode.

**Limits and interactions.**

- **TRK**, **RETRIG** and the pattern bank keys keep working meanwhile. FUNC combinations (menus, fast encoders) don't
  leave the mode (notes/15).
- The stock gesture (holding FUNC) is unchanged.
- **With Model-TG**: Model-TG's own version queued the presses and applied them when you left the mode ("Pad presses
  are queued and all take effect when you leave mute mode", Model-TG guide). This project changed Model-TG so each
  track key mutes at once, as with drumkilla's tweak alone (notes/31 §10). The same applies to held mute mode.
- On a Sampler track, a mute fades the Sampler out and ends its note (Model-TG guide).

**Origin and license.** drumkilla, `elektron-model-tweaks`, MIT; included in Model-TG, with this project's change to
Model-TG's mute queue.

**Status.** Tested by its author on his hardware (notes/15). The immediate mutes with Model-TG were tested on a
Model:Cycles on 03/10/2026 (T1–T6 in latched mode, with 6-channel audio, the 5 engines and the arpeggiator).

### 4.2 Live MIDI OUT + THRU toggle

**What it does.** With THR selected, a shortcut decides whether the Cycles' own MIDI goes out too, on top of the
forwarded MIDI. The original OUT/THR menu doesn't change. With the toggle on, it does what "MIDI OUT while in THRU"
(`midi-both`) did, so that mod is not in OS 2.0.

**How to use it** (guide):

1. Press **SETTINGS**, open **CONFIG › MIDI › PORTS** and set **OUT/THRU** to **THR**, as usual.
2. With the cursor on OUT/THRU, hold **FUNC** and press the **LEVEL/DATA** knob: the Cycles now also sends its own
   clock, notes and parameter changes, while incoming MIDI keeps passing through.
3. Hold **FUNC** and press **LEVEL/DATA** again to go back to forwarding only.

**Limits and interactions.**

- The screen shows **THR** either way. "To know which one is on, watch whether the next device gets the Cycles' clock
  or notes."
- Without FUNC, a press on LEVEL/DATA switches to OUT, as before. Back on THR, the Cycles forwards only, until the
  next FUNC + press.
- Clock twice: if the Cycles follows the clock on its MIDI IN and sends its own, the next device can get the clock
  twice. Turn off clock send in the Cycles' MIDI sync settings.
- Two senders: the Cycles relays bytes as they arrive, not whole messages like a merger box. If both sides send notes
  or knob moves at once, the next device can get a wrong or stuck note. Clock and start/stop are not affected. Best
  when only one side plays notes.
- Whether the choice survives power-off: "as far as the code shows" yes; not checked on the machine (notes/53 §8,
  `[HYP]`). With the official OS or `midi-both`, the saved value simply reads as THR.
- FUNC + turning the knob on that row has not been studied (notes/53 §8).

**Origin and license.** AveyCole (fork `AveyCole/Modded-Cycles`). Same code, linked at another place. The fork has no
license file; `PROVENANCE.md` and notes/53 §10 say the license is still to be confirmed with AveyCole.

**Status.** Tested by AveyCole on his Model:Cycles on 10/10/2026 ("tested and working!!!"). Maxime judged that
enough and did not test it himself (notes/53 §9). Marked tested on 11/10/2026.

### 4.3 Mod Settings: USB audio, stereo or 6 tracks

**What it does.** The SETTINGS menu (the Config Menu) gets a ninth line, **Mods**, after Device. It opens **Mod
Settings**, a page meant for the mods' own settings. Its first and only setting so far, **USB Audio**, chooses what
goes to the computer over USB:

- **2CH**, the default: the stereo mix, exactly as the stock OS sends it (the 6-channel code is not even in place).
- **6CH**: each track on its own USB channel (48 kHz, 32-bit, 6 inputs): six mono stems, taken before the pan, without
  delay and reverb. The stereo mix is not sent over USB.

**How to use it** (guide):

1. Press **SETTINGS**. Turn **LEVEL/DATA** to the last line, **Mods**, and press **LEVEL/DATA**.
2. The page shows **USB Audio** and its value. Press **LEVEL/DATA** to switch between 2CH and 6CH.
3. The Model:Cycles leaves the computer and comes back about a second later with 2 or 6 inputs, as when you change
   **Device › USB mode**. Stop recording in the DAW before switching.

**Limits and interactions.**

- The choice is saved at once with the Model:Cycles' settings and comes back at power-on. It is kept in a free corner
  of the settings that the official OS ignores: with the official OS the audio is stereo, back on this OS the choice
  returns.
- USB Audio only matters with **Device › USB mode** on A+M. On MID there is no USB audio; the setting waits.
- In 6CH, playing the computer's audio through the Model:Cycles is not reliable: use another output, or 2CH.
- macOS sees 6 inputs; on Windows use FlexASIO (channels = 6, 48 kHz); Linux not tested.
- Mutes: in 6CH a muted track plays no new trigs; on its stem the note it was playing rings out (notes/35).

**Origin and license.** The 6-channel audio is `scottmetoyer/ms-multi-output` (MIT), as rebuilt by this project in
`6ch-usbup` (USB updates kept, steady stream). The page, the setting and the switch are this project's (notes/72):
the 6-channel changes to the USB driver are made in memory only in 6CH, and undone for 2CH.

**Status.** Tested on a Model:Cycles on 19/10/2026: Maxime reported "ça marche nickel" (it works perfectly) after
the test plan of PR #100 (notes/72 §7). 6-channel audio itself was tested on 29/09/2026, the steady stream on
04/10/2026, with Model-TG and the engines on 02/10 and 03/10/2026. Also checked in the emulator on the OS's own code
(Config Menu, drawing, both switches, saved settings, the USB stream after switching).

---

## 5. Screen and browsing

### 5.1 Startup animation

**What it does.** At power-on, the screen shows the modded-cycles logo instead of the original tile animation.

**How to use it.** Hold **MAIN VOLUME** to switch on, as usual. "The four rounded squares of the logo pop in one by
one, the top right one hollows out, then 'modded-cycles' types itself underneath."

**Limits and interactions.** Same duration as the original (about 1.8 s); startup is not slower. The startup menu is
unchanged: **FUNC** held at power-on still opens it.

**Origin and license.** This project, on Maxime's request (notes/39), MIT.

**Status.** Tested on a Model:Cycles on 05/10/2026 (the first try was upside down and was fixed before that).

### 5.2 Multi-line browser

**What it does.** The preset browser shows three names at once in a small font, instead of one in big letters.

**How to use it** (guide):

1. Open the preset menu as usual: **FUNC + MACHINES**.
2. Move through the list as before: the **>** follows the cursor, and the list scrolls past the first or last line.
   The arrows on the right show whether you can still go up or down.

What the screen shows: **>** marks the name under the cursor; the highlighted (inverted) name is the sound loaded on
the track; **■** marks a folder.

**Limits and interactions.**

- Works for sounds, folders and the Model-TG Sampler's samples. The title, position and *Fn=Menu* don't change.
- Long names are cut at the edge of the screen. With scrolling names (in Model-TG), only the name under the cursor
  scrolls.
- In a sub-folder of +Drive, the list keeps its window instead of sending the cursor back to the top (notes/40).

**Origin and license.** From an idea and a Python script by a community member (sent to Maxime on 05/10/2026). This
project rewrote it; none of the script's code is used. The member's name is "to confirm" in `PROVENANCE.md`.

**Status.** Tested on a Model:Cycles on 10/10/2026 (notes/40 §6).

### 5.3 Scrolling names

**What it does.** In the sound browser, a selected name too long for the screen scrolls to the left.

**How to use it.** Nothing to press: move the cursor onto a long name.

**Limits and interactions.** One character every 0.17 s, a 0.5 s pause at the ends; short names stay put. With the
multi-line browser, only the line under the cursor scrolls. Model-TG uses the same scroll for the sample name on the
Sampler's machine page.

**Origin and license.** drumkilla, `elektron-model-tweaks`, MIT; included in Model-TG.

**Status.** Tested by its author on his hardware (notes/15). The flasher marks it tested. No dated test by Maxime
of this tweak on its own is recorded in the notes I read; it ships inside Model-TG, whose combinations were tested.

### 5.4 Volume and pan as numbers

**What it does.** On the main screen, the selected track's volume and pan show as numbers while you turn
**LEVEL/DATA**.

**How to use it** (guide):

1. On the main screen, turn **LEVEL/DATA**: the track's volume (0 to 127) shows in small digits in place of the
   loudspeaker, left of the volume bar.
2. Hold **FUNC** and turn **LEVEL/DATA**: its pan (-64 to 63) shows in place of the "R" at the right end of the pan
   bar.
3. Stop turning: the number goes away 3 to 4 seconds later and the icon comes back.

**Limits and interactions.**

- On the main screen, LEVEL/DATA now moves in steps of 1 instead of 2: turn twice as far for the same change. Its fast
  mode doesn't change. (djd_oz's choice.)
- Only when you turn the knob, for the selected track. A change by MIDI or by loading a project shows nothing.
  Menus, the file browser and value windows don't change.

**Origin and license.** A mod by djd_oz (sent as a firmware file on 06/10/2026), rewritten by this project. License
"to confirm with him" (`PROVENANCE.md`).

**Status.** Tested on a Model:Cycles on 06/10/2026 and 07/10/2026, with Model-TG, the 5 engines, 6-channel audio and
the other mods.

### 5.5 Dimmed trigless trigs

**What it does.** A trig key that holds a trigless trig lights dimmed, so you can tell it from a note trig.

**How to use it.** Place a trigless trig as usual: hold **FUNC** and press a trig key on an empty step. The key lights
dimmed; note trigs stay at full brightness. As on the stock OS, the trigless trig goes dark briefly every 2 seconds.

**Limits and interactions.**

- Unchanged: note trigs, trigs with parameter locks, the playing light, the pads and the other lights.
- The key is lit one millisecond out of every three (333 times a second): it looks steady at about a third of its
  brightness, however many trigless trigs the page holds. A first version flickered unevenly on the machine.
- Model-TG's slide trigs double-blink on the trig keys. How a slide trig that is also trigless looks is not described
  (see [Open questions](#8-open-questions)).

**Origin and license.** A mod by djd_oz (sent as a firmware file on 06/10/2026), rewritten by this project; the
light timing is this project's. License "to confirm with him" (`PROVENANCE.md`).

**Status.** Tested on a Model:Cycles on 07/10/2026 (version 2), with all 16 trig keys holding trigless trigs, Model-TG,
the 5 engines, 6-channel audio and the other mods.

### 5.6 Sample preview

**What it does.** In the preset menu of a Sampler track, the track's pad plays the sample under the cursor, the way
the original OS lets you hear a preset before you pick it.

**How to use it** (guide):

1. On a Sampler track, press **FUNC + MACHINES** (preset menu) and move the cursor onto a sample file. Nothing plays
   while you scroll, as with presets.
2. Press the track's pad (or its trig keys in keyboard mode): you hear the highlighted sample, with the track's
   settings (playback mode, Start, End, filter…).
3. The first press on a sample that isn't in memory yet loads it: a short wait, then it plays. The next presses
   usually play at once.
4. Pick the file as usual to load it onto the track (*Sample loaded to Sampler*), or just leave the menu.

**Limits and interactions.**

- Sampler tracks only. On other machines, presets preview as before and sample files are not previewed.
- The track keeps its own sample, name included; its trigs still play it.
- Silence: if there isn't enough free memory (a preview keeps room for recording and never removes a sample the
  project uses), while Model-TG is resampling, or for an unreadable file. To retry, move the cursor away and back; if
  Model-TG was busy loading, press again.
- Bonus: Sampler presets that remember their sample should also play that sample instead of the track's.

**Origin and license.** This project, from a Discord request (6 votes); reuses a short piece of Model-TG's code
(MIT, credited to TinyGregAudio). Without it, Model-TG is unchanged.

**Status.** Tested on a Model:Cycles on 07/10/2026, with Model-TG alone and with the 5 engines, 6-channel audio, trig
removal and the arpeggiator. With MACRO: in the emulator only (guide).

---

## 6. Model-TG in depth

Model-TG v1.1.0 by TinyGregAudio, MIT. Sources for this section: its `README.md`, `docs/USER_GUIDE.md` and
`docs/INTERNALS.md` at tag `v1.1.0` (identical to `main` on 18/10/2026), this project's guide and notes/31.
Unless said otherwise, the features in this section have **no dated test by Maxime in the notes**. Model-TG's author
tests his own build on his hardware (notes/31 §2). Maxime's recorded tests are listed in [2.1](#21-sampler-model-tg-overview).

How Model-TG's keys work (its guide and `INTERNALS.md`): its pages open with **SETTINGS** held, "so the stock TRACK
combinations keep working". "Tapping SETTINGS on its own still opens the Config Menu. Holding it no longer brings up
the *Save pattern* prompt." The twelve parameter knobs are numbered 1 to 12 (1 = PITCH … 12 = CHANCE).

### 6.1 The Sampler machine

- The seventh machine, next to Kick, Snare, Metal, Perc, Tone and Chord. Choose it like any machine.
- Samples are 48 kHz. Up to 64 in memory at once, shared between tracks and patterns that use the same file.
- **Preloading**: every sample the project uses loads in the background, so pattern changes don't wait. If memory
  runs short, samples the current pattern doesn't need are dropped first and reload when needed.
- **Sample locks**: hold a step, press **FUNC + MACHINES** and open a sample file; that step plays that sample. "A
  lock keeps the Start, End and Filter it was locked with."
- The sample's name shows on the machine page in place of "Sample", scrolling when long.

### 6.2 The Sampler's parameters

- **Start** and **End** set the part that plays. "Set Start above End to play it reversed." Both can be p-locked,
  so reverse works per trig.
- **Fine Start/End**: a slow turn moves an eighth of a step; faster turns move in whole steps.
- **Waveform view**: turning Start or End shows the sample full screen with Start and End as lines. With a step held,
  it shows the sample that step plays (including a sample lock).
- **Filter** and **Resonance**: a 4-pole ladder low-pass.
- "All six parameters are LFO destinations" (Model-TG guide; the six are not listed by name).

### 6.3 Playback modes

**How to use it.** Hold **SETTINGS** and press **MACHINES**, turn any knob to choose, then press **SETTINGS**,
**MACHINES** or **BACK** to close. The mode is saved per track.

| Mode | What it does | The four page knobs |
|---|---|---|
| One shot | plays Start → End once (default) | Start, End, Filter, Res |
| Loop | loops Start → End | Start, End, Filter, Res |
| Slice | cuts the sample into slices; the note picks one | Start, End (inside the slice), Filter, Res |
| Granular | up to 6 grains at the note's pitch | Position, Grain Size (10 ms–1 s), Density, Spray |
| Stretch | granular with a moving playhead: time and pitch independent | Speed (0 frozen, 96 original, 127 ≈ 3.8×), Grain Size, Density, Spray |
| Pluck | a plucked string (Karplus-Strong) struck by a burst of the sample | Strike Pos, Strike Len (1 ms–1 s), Tone, Feedback |
| Wave | the sample as a wavetable of single-cycle frames | Wave Pos, Frame Size (32–4096; 2048 for Serum/Vital tables), Smooth, Detune |

### 6.4 Mode options

**How to use it.** Hold **SETTINGS** and press **PUNCH**. Turn **LEVEL/DATA** to move between rows, press it to edit
a row, turn to change it; **SETTINGS** or **BACK** closes. Saved with the project. **EFX**, **CHN** and **STU** belong
to the track, so they carry over when you change mode.

| Mode | Options |
|---|---|
| One shot | **EFX** Filter / Lo-fi / Tape / Vinyl / None · **CHN** Mono / Stereo · **STU** stutter off, 1/4, 1/8, 1/16, 1/32, 8T, 16T |
| Loop | **TYP** Forward / Reverse / Ping-pong · **XFD** crossfade off, 10, 25, 50, 100, 250 ms · **SYN** off, 1, 2 or 4 bars · **EFX** · **CHN** |
| Slice | **MOD** EQL / TRN / MAN · **SLC** 8, 16, 32 · **EFX** · **CHN** · **EDT** · **SEQ** |
| Granular | **SHP** Hann / Triangle / Perc / Square · **DIR** Forward / Reverse / Random · **FRZ** freeze Position at the note's start · **CHN** |
| Stretch | **MOD** Forward, Reverse, once Forward/Reverse, Sync 1/2/4 bars (at Speed 96 the sample lasts exactly that) · **CHN** |
| Pluck | **MOD** Synth / Drum · **EXC** exciter Sample / Noise / Click · **CHN** |
| Wave | **CHN** |

With **EFX** on Lo-fi, Tape or Vinyl, the Filter and Res knobs become that effect's two controls: Lo-fi = Rate (48 kHz
to about 1 kHz) and Crush (16 bits to 1); Tape = wow/flutter and saturation; Vinyl = crackle, hiss and wow.

### 6.5 Slice mode and the slice editor

- In Slice mode the note chooses the slice. In keyboard mode the trig keys play consecutive slices (first key =
  slice 1); each sequencer trig plays the slice its note picks. Slices play at original speed; Start and End trim
  inside the slice; Start above End reverses it.
- **MOD**: **EQL** equal slices (SLC 8, 16, 32); **TRN** at transients, each moved back to its attack; **MAN** your own
  markers, up to 32 (SLC shows how many). Switching to MAN keeps the current slices.

**Slice editor (EDT).** Press **EDT** in the Slice options. The track switches to MAN and a full-screen editor opens:
the sample, every marker as a dotted line, the selected slice's start as a solid line with a bar, and *SLICE n/total*
with its start time.

| Control | What it does |
|---|---|
| **TRIG 1–16** | play and select slices 1–16 (hold **FUNC** for 17–32) |
| **LEVEL/DATA** turn | select a slice |
| knob 1 | move the selected slice's start (coarse; faster turns go further) |
| knob 2 | move it fine |
| **FUNC** + knob 1 or 2 | move, then snap to the next zero crossing |
| knob 3 | zoom in and out around the selected start |
| **LEVEL/DATA** press | split the selected slice in two |
| **FUNC** + **LEVEL/DATA** press | remove the selected slice's marker (it joins the one before) |
| **BACK**, **SETTINGS** or **MACHINES** | close |

Slice 1 always starts at the sample's start; slices are at least 64 samples long.

**Tap slicing.** In the editor, press **PUNCH** to arm (top right shows *ARMED*). Nothing plays until you press a trig
key: the first press plays the whole sample from the start, at full level whatever the Amp Decay, and clears the old
markers. Each press after that drops a marker where the sample is playing. Tapping stops at the end of the sample or
when you press **PUNCH** again.

**Sequencing the slices (SEQ).** Put trigs on the track, then press **SEQ** in the Slice options. Each trig's note is
set so the pattern walks through the sample (slice 1, 2, …, starting again after the last). Works in all three MOD
settings.

**Where markers are kept.** Markers belong to the sample, not the project: every track and pattern using that sample
gets the same slices. Saved as `/Slices/<the sample's id>` when you close the editor.

### 6.6 Resampling

**How to use it.** Hold **SETTINGS** and press **REC**. The take becomes the sample of the track you opened the menu
on.

| Row | Settings |
|---|---|
| **SRC** | a track (dry: after its envelope and filter, before its level, pan and sends), **MST** the whole output, or **USB** the computer's audio |
| **CHN** | **STE** stereo, **MON** mono |
| **LEN** | 1, 2, 4, 8 or 16 bars, **PTN** the pattern's length, or **MAN** until you stop |
| **STA** | **PAT** at step 1 of the pattern, **NOW**, or **SND** at the source's first sound |
| **MUT** | **ON** mutes the other tracks as the take lands |
| **TRM** | level trim, −6 to +6 dB |
| **CLR** | empty this track in this pattern |
| **REC** | arm, and stop or cancel |
| **SAV** | name the take and save it as `/Resampled/<name>` |

**Limits.** A bar-length take goes onto the track as the bar ends. Takes play back at the level they were heard. An
unsaved take lives in memory only and belongs to the pattern it was recorded in. Saving runs while the music plays.
Not tried by this project: resampling a Syntakt engine track, and USB resampling together with 6-channel audio
(notes/31 §2, §8).

### 6.7 Stereo

Stereo takes and stereo WAVs are kept as stereo. With **CHN** Stereo, every mode plays them in stereo, effects
included; with Mono (default) they play mono. A stereo file whose channels are the same is kept as mono. "Stereo
play is very CPU intensive": about twice the processor.

### 6.8 Retrig page and master effects

**How to use it.** Hold **SETTINGS** and press **RETRIG**.

1. **Repeats**: hold a trig key to repeat the output, locked to the tempo: key 1 every 1/64, key 16 every bar,
   straight and triplet values in between.
2. **Pads** choose which tracks the page acts on: all lit at first; a press turns a track off or back on.
3. Turn **LEVEL/DATA** to move between the rows **RETRIG** (Momentary while you hold, the newest held key wins; or
   Latch, a press starts or switches, the same key again stops) and **FX RETURNS** (whether delay and reverb repeat
   too). Press it to change one.
4. The 12 knobs are effects on the lit tracks, before the delay and reverb. Each is off at 0; the bottom line shows
   the effect and its value.

| Knob | Effect |
|---|---|
| 1 · PITCH | Drive: soft clipping up to 8×, level-compensated |
| 2 · DECAY | Crush: 16 bits down to 1 |
| 3 · COLOR | Rate: 48 kHz down to 1 kHz |
| 4 · SHAPE | Pump: sidechain ducking |
| 5 · SWEEP | Filter: low-pass left of centre, high-pass right |
| 6 · CONTOUR | Resonance of the filter |
| 7 · DELAY | Ring mod: 30 Hz to 4 kHz |
| 8 · REVERB | Noise riser: white noise rising, on the whole output |
| 9 · LFO SPEED | Gate: off, 1/4, 1/8, 1/8T, 1/16, 1/16T, 1/32, on the tempo |
| 10 · VOLUME | Tape stop |
| 11 · SWING | Vinyl: hiss and crackle, on the whole output |
| 12 · CHANCE | Flanger: one sweep per bar |

5. Close with **SETTINGS** or **RETRIG** (or **PATTERN**, to choose a pattern): the effects stay on, through pattern
   changes. **BACK** on the page resets the effects and a latched repeat. **SETTINGS + BACK** turns the effects off
   from anywhere (*Master FX off*).

**Sidechain (Pump).** "The Pump knob ducks the lit tracks each time the tracks you turned off play":

1. On the retrig page, press the kick track's pad to turn it off. It now plays as it is, without the page's effects,
   and drives the pump.
2. Turn **SHAPE** (knob 4) to set the depth, 0 to 127.
3. Close with **SETTINGS**: the pump keeps going.

With no pad off, it pumps on every quarter note. Several tracks off all drive it. Attack instant, release fixed (about
170 ms); only the depth is set. The leading track has to be heard: muted or at volume 0, it no longer drives the
pump. The delay and reverb receive the ducked tracks, but their own returns aren't ducked.

### 6.9 Attack, Filter and Resonance on every machine

- **Attack**: hold **MACHINES** and turn **DECAY**, from instant up to about 2 s.
- **Filter** and **Resonance**: hold **MACHINES** and turn **SWEEP** (Filter) or **CONTOUR** (Resonance). It is the
  Sampler's ladder filter; wide open it is bypassed.
- On every machine: the stock ones, the Syntakt engines (notes/31 §4.4) and MACRO (notes/43). ACID is not mentioned
  in the sources.
- Real parameters: p-locks, LFO destinations, saved with the project. The p-lock reload bug is fixed by LFO 2, 3, 4
  ([2.5](#25-lfo-2-3-4)).

### 6.10 Slide trigs

**How to use it.** Hold **SETTINGS** and press a trig key: that step becomes a slide trig (*Slide on*) or an ordinary
trig again (*Slide off*). On an empty step it places a trig that is already a slide trig. Slide trigs double-blink on
the trig keys.

**What it does.** Every parameter that differs between the trig before and the slide trig glides from one value to
the other over the whole gap, and arrives as the slide trig plays. A value is the step's p-lock, or the sound's own.

- Glides: the machine's parameters, fine tune, Amp Decay, volume, pan, delay and reverb sends, the LFO's speed, fade,
  phase and depth, and Attack, Filter and Resonance.
- Jumps as usual: the machine, Gate, and the LFO's multiplier, destination, waveform and trig mode.
- Works on every machine, the Syntakt engines included (proven in the emulator and tested on 03/10/2026 on an engine
  track). The trig before can be trigless.
- The glide follows the tempo and the track's speed. Across swung steps it can arrive a little early or late, then
  holds until the slide trig plays.
- The mark is saved with the pattern and copied with its step; removing the trig removes it.
- It glides parameters, not the note (notes/54). ACID's pitch slide is separate (trig length).
- Cost (emulator): about +0.16 % of a block at rest during playback, about +1.8 % with six tracks all gliding 19
  parameters (notes/31 §9).

### 6.11 Scale Lock

Two items in the Scale menu (**FUNC + PAGE**): **Scl** (the scale) and **Key**. Notes you play are moved onto the
scale. Slice tracks are left alone, so consecutive keys stay consecutive slices. The sources do not list the
available scales.

### 6.12 Uploading samples with Elektron Transfer

In **Device Config › Transfer**, switch the identity from **CYC** to **SMP**, with no need to reconnect Transfer: the
Cycles answers as a Model:Samples, and you can upload samples, stereo WAVs included. Every power-on starts at CYC.
"In SMP, use Transfer for samples only, and never accept an OS update from it." The web flasher's fast method needs
CYC (guide, Troubleshooting).

### 6.13 The System page

**Device Config › System** shows the audio processor load (now and at its worst) and sample memory used and free.
Turn **LEVEL/DATA** right for each track's share of the processor. **BACK**, **MACHINES** or **SETTINGS** closes it.
The Syntakt engines and MACRO show their time there too. Silent tracks cost almost nothing. Note: the System page
counts from the start of the audio interrupt and reads about 11 points more than this project's own load counter
(notes/31 §6).

### 6.14 Lower processor load and a stock fix

- Silent tracks cost almost nothing, Kick and Chord are cheaper (same sound), delay and reverb switch off while
  nothing is sounding (Model-TG guide and `INTERNALS.md`).
- Model-TG also fixes "a long-standing stock bug: a random exception while browsing, caused by the filesystem block
  cache" (`INTERNALS.md`).

### 6.15 The three drumkilla tweaks inside Model-TG

Latching mute, trig preview and scrolling names come with Model-TG ([4.1](#41-latching-mute), [3.3](#33-trig-preview),
[5.3](#53-scrolling-names)). Two of them were changed by this project inside Model-TG: immediate mutes (03/10/2026)
and trig preview while paused (04/10/2026).

### 6.16 Files Model-TG writes

| Where | What |
|---|---|
| `/Resampled/<name>` | takes saved with **SAV** |
| `/Slices/<id>` | slice markers, one small file per sample |

### 6.17 Model-TG's own button reference, translated to the panel

| Where | Model-TG's wording | On the panel | Does |
|---|---|---|---|
| anywhere | SETTINGS + PRESET | **SETTINGS + MACHINES** | playback mode menu (Sampler track) |
| anywhere | SETTINGS + PUNCH | **SETTINGS + PUNCH** | the mode's options |
| anywhere | SETTINGS + RECORD | **SETTINGS + REC** | Resample menu |
| anywhere | SETTINGS + RETRIG | **SETTINGS + RETRIG** | retrig page and master FX |
| anywhere | SETTINGS + return | **SETTINGS + BACK** | master FX off |
| anywhere | PRESET + Decay / Sweep / Contour | **MACHINES + DECAY / SWEEP / CONTOUR** | Attack / Filter / Resonance |
| grid | SETTINGS + trig key | **SETTINGS + trig key** | slide trig on / off |
| browser | pick a sample file | **FUNC + MACHINES**, pick a file | load it onto the Sampler track |
| step held | PRESET, pick a sample | step held, **FUNC + MACHINES**, pick a file | sample lock |
| slice editor | PUNCH | **PUNCH** | arm or stop tap slicing |
| Scale menu | FUNC + PAGE | **FUNC + PAGE** | Scl and Key |

Note the browser row: Model-TG's guide says "open the preset browser (PRESET)", while this project's guide says
**FUNC + MACHINES**, and notes/31 §6 says Maxime's test loaded a sample "par le navigateur de presets (FUNC +
MACHINE)". Model-TG's "PRESET" key is **MACHINES** (key code 5 in its `INTERNALS.md`).

### 6.18 What this project changed or added around Model-TG

| Change | Why | Source |
|---|---|---|
| Mutes act at once in mute mode | Maxime's choice after a user report | notes/31 §10 |
| Trig preview works while paused (in its copy) | MIDI Stop paused the sequencer and broke PAGE | notes/34 |
| Sample memory 63 MB instead of 64 | the last MB runs the Syntakt engines | notes/31 §4 |
| Engines, MACRO and ACID after the Sampler; engines get Attack/Filter/Resonance, slides and System page time | the combined build | notes/31 §4, notes/43, notes/54 |
| Governor never turns off the Sampler or the track being recorded or slice-edited | keep timing-critical tracks | notes/31 §4.5 |
| Attack/Filter/Resonance p-locks reload correctly | fixed by LFO 2, 3, 4 | notes/56 |
| Sample preview in the preset menu | Discord request | notes/46 |
| USB tracks cut at mute with Model-TG; USB send at a fixed time | 6-channel glitches (the send at a fixed time helps 2CH too; see 4.3) | notes/35 |

---

## 7. Outside the single OS, and why

### 7.1 6-channel USB audio

In the OS since 19/10/2026, behind the **USB Audio** setting of Mod Settings: see
[4.3](#43-mod-settings-usb-audio-stereo-or-6-tracks). It stayed out of the first OS 2.0 draft because it replaced the
stereo USB mix; the setting (issue #82) lets each user choose. The `6ch-usbup` tweak that installs it for good is
still in the library, for developers.

### 7.2 Per-track filter

**What it does.** A DJ-style filter on every track: hold **MACHINES** and turn **SWEEP** (L64 … OFF … H63), with
**CONTOUR** for resonance, **COLOR** for envelope amount and **SHAPE** for envelope decay. Real parameters (p-locks,
LFO, velocity, CC 74/71).

**Why it's out.** Same gesture as Model-TG's filter (**MACHINES + SWEEP / CONTOUR**), and it keeps its settings in the
same place of the sound as LFO 2, 3, 4. It comes back after Model-TG is replaced. Its fix of the stock OS's saving of
p-locks on added parameters goes with it.

**Origin.** This project, from a Discord request (notes/47). **Status:** tested on a Model:Cycles on 11/10/2026.

### 7.3 Optimised OS

**What it does.** Skips work that can't change the sound (silent voices, idle delay and reverb, Dist at 0, zero
sends, PUNCH off) and fixes two freezes of Elektron's OS. Measured on the machine: average load 72 → 20 % stopped,
77 → 65 % playing, same sound.

**Why it's out.** Not compatible with Model-TG, MACRO, ACID or the Syntakt engines. Porting it to the single OS is the
first job of the feature freeze.

**Origin.** This project, notes/70, on branch `claude/os-optimise` (not in this branch). **Status:** two test files
flashed by Maxime on 18/10/2026, "same sound" (notes/70); its flasher status is not in this branch.

### 7.4 MIDI OUT while in THRU (`midi-both`)

**What it does.** THR always forwards incoming MIDI **and** sends the Cycles' own. **Why it's out:** superseded by the
live toggle ([4.2](#42-live-midi-out--thru-toggle)), which does the same when switched on and can be switched off.
The two could never be installed together. **Origin:** AveyCole (license to confirm). **Status:** tested by AveyCole
on 10/10/2026.

### 7.5 Chord Keys

**What it does.** Played the selected CHORD track from **TRIG 1–16** (I–VII, the same an octave higher, then I–II),
with Keys/Root/Scale and per-degree extensions in **FUNC + RETRIG**, and SHAPE as Chord Voicing.

**Why it's out.** Removed from the project on 18/10/2026 because of conflicts. The conflict recorded in the flasher is
with Model-TG: "both change the notes of the TRIG keys (Model-TG has its own Scale Lock)". It also added rows to the
FUNC + RETRIG menu, next to the arpeggiator's. notes/42 is kept as an archive; the tweak, generator, sources and proofs
were deleted from the repository on 18/10/2026 (notes/71) and stay in the git history before that date.

**Origin.** Nico Heuser (PR #46). **Status:** tested by Nico on 06/10/2026 and by Maxime on 10/10/2026.

### 7.6 Samples OS, and the Cycles OS on a Model:Samples

Separate flashing paths, not mods of the Cycles OS:

- **Samples OS**: the official Model:Samples OS inside a Model:Cycles firmware file. Coming back needs a MIDI
  interface (startup menu). Tested on a Model:Cycles on 29/09/2026.
- **Cycles OS on a Model:Samples** (Samples OS tab): turns a Model:Samples into a Model:Cycles, and back, over USB.
  Experimental.
- **Mods on a Model:Samples** (Mods tab, machine picker): whatever the machine, the flasher installs the Model:Cycles OS
  with the mods (decision of 10/10/2026, notes/57). Tested on a Model:Samples on 11/10/2026. Original flasher by RDS
  (AIM), integrated by DaftMaple.

---

## 8. Open questions

1. **Model-TG's status label.** The flasher card and README say experimental; the guide and notes/31 §10 say Model-TG
   + the 5 engines was tested on 03/10/2026 (on a `build.py` firmware with the same MAIN OS as the flasher). Which label
   should OS 2.0 inherit? (Checked: `tools/gen_flasher_tweaks.py`, README, guide, notes/31.)
2. **No hardware test of the full OS 2.0 bundle** is recorded: the closest are Model-TG + 5 engines + MACRO + ACID
   (12/10 and 18/10/2026) and LFO 2, 3, 4 "with the full set" (11/10/2026). The bundle also adds midi-live-both and
   adds the Mod Settings page (6CH switched in memory) compared with the tested sets. (Checked: notes/31, 54, 56; draft `os.json`.)
3. **Model-TG features never tested by Maxime**: the notes record no test of the playback modes beyond One shot,
   mode options, slice editor and tap slicing, SEQ, resampling, stereo, the retrig page and master effects, Pump,
   Scale Lock, or the System page. Only loading and playing a sample, the Attack key, a slide trig and mutes are
   recorded. (Checked: notes/31 §6, §9, §10.)
4. **Scrolling names**: no dated test by Maxime of this tweak alone in the notes; it is marked tested and ships in
   Model-TG. (Checked: notes/15, release.js, git log.)
5. **ACID with Model-TG's Attack, Filter, Resonance and slide trigs**: the sources say "every machine" for the engines
   and MACRO, but say nothing about ACID tracks. (Checked: guide, notes/43, notes/54.)
6. **Trig removal (0.5 s) vs Model-TG's SETTINGS + trig key**: does a slow SETTINGS + trig press on a step with a trig
   behave as expected? Not described. (Checked: guide, notes/33.)
7. **Dimmed trigless + slide trig double-blink**: how a trigless trig marked as a slide looks on the keys is not
   described. (Checked: guide, notes/45, Model-TG guide.)
8. **Live MIDI toggle persistence**: whether "THR + send" survives power-off is `[HYP]`, not checked on a machine; FUNC +
   turning the knob on that row was not studied. (Checked: notes/53 §8.)
9. **Licenses to confirm**: AveyCole (no license in the fork; "à confirmer avant la fusion"), djd_oz (volume/pan
   numbers, dimmed trigless trigs), and the name of the community member behind the multi-line browser. (Checked:
   `PROVENANCE.md`, `THIRD-PARTY-NOTICES.md`, notes/53 §10.)
10. **Arpeggiator settings after a restart**: Maxime's test did not explicitly confirm that Arp and Oct survive a save
    and a power cycle. (Checked: notes/32 §10.)
11. **Back key name**: this project's guide says **BACK**, Model-TG's docs say "return" (key code 12). Which name is
    printed on the panel should be checked so the OS 2.0 docs use one word. (Checked: guide, Model-TG
    `USER_GUIDE.md`, `INTERNALS.md`.)
12. **"All six parameters are LFO destinations"** on the Sampler: Model-TG's guide doesn't name the six (Start, End,
    Filter, Resonance are four). (Checked: Model-TG `USER_GUIDE.md`.)
13. **Scale Lock scales**: the list of scales behind **Scl** is not documented in the sources. (Checked: Model-TG
    `USER_GUIDE.md`, `INTERNALS.md`, guide.)
14. **Untested combinations around resampling**: a Syntakt engine track as SRC, and USB resampling together with
    6CH. (Checked: notes/31 §2, §8.)
15. **Chord Keys**: removed from the guide, README, flasher and tools on 18/10/2026 (notes/71); the old release notes
    still mention it as history, on purpose.
16. **Optimised OS status**: notes/70 lives on `claude/os-optimise`; its flasher status and the exact list of what it
    conflicts with in Model-TG were not checked in this branch.
