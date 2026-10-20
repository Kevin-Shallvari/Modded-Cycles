---
name: bilingual-user-docs
description: Writes the user-facing, side-by-side English and French texts of Modded Cycles - user guide sections (docs/guide/index.html), release notes (docs/assets/release.js, posted to Discord), flasher card texts, README mod table rows, and the MC_BUILD / ?v= cache stamp. Covers the voice for musicians, button names, limits, and French conventions. Use when documenting a new mod or fix for users, writing a release entry, or reviewing site text.
---

# User docs, English and French side by side

Everything users see exists in both languages, written together: never add one without the other. Audience:
musicians with a Model:Cycles. Say what changes on the machine, which buttons to press, what the screen shows,
and the limits. No addresses, offsets, file names or jargon: those belong in the notes.

## Voice

- Short sentences, present tense, buttons in bold as printed on the machine: **FUNC**, **TRK**, **LEVEL/DATA**,
  **TEMPO**, **PITCH**, **TRIG 1–16**, **[LFO]**. Screen text as shown (`OFF`, `46K`, `12B`).
- Name the limits plainly (what does not work, what it does not go with, what happens on the original OS).
- French: « vous » on the site; French typography (`546,0 BPM`, `65 535`, space before `: ; ! ?`, « guillemets »);
  the same facts as the English, not a looser paraphrase.
- Credit outside authors by name in the guide and release ("Based on a mod by …").
- *Experimental* until Maxime tested it on his machine; then *Tested on a Model:Cycles*. Never claim a hardware
  result he did not report.

## Guide section (`docs/guide/index.html`)

Next number, before *Samples OS*; renumber the sections after it. Copy the `#tempo` or `#trig-hold` section:

```html
<section id="<anchor>">
  <h2><span class="n">NN</span><span data-l="en">Title</span><span data-l="fr">Titre</span></h2>
  <p class="lede"><span data-l="en">What it gives you, in one or two sentences.</span><span data-l="fr">…</span></p>
  <ol>
    <li><span data-l="en">Hold <b>FUNC</b> and press <b>TRIG 5</b>: …</span><span data-l="fr">Maintenez <b>FUNC</b> et appuyez sur <b>TRIG 5</b> : …</span></li>
  </ol>
  <dl class="facts">
    <div><dt><span data-l="en">Limits</span><span data-l="fr">Limites</span></dt><dd>…</dd></div>
    <div><dt><span data-l="en">Experimental</span><span data-l="fr">Expérimental</span></dt><dd><span data-l="en">checked in the emulator on the OS's own code: …; not yet tested on a Model:Cycles.</span><span data-l="fr">…</span></dd></div>
  </dl>
</section>
```

The anchor is the feature's `guide` in `os.json`.

## Release entry (`docs/assets/release.js`)

New object at the top of `window.MC_RELEASES`: next version after the top one (`2.0` → `2.1`), today's date
(`YYYY-MM-DD`), 2 to 4 `{ en, fr }` changes: what the user gets and how to use it, the limits, how it was
checked (emulator / tested on a Model:Cycles), which mods it goes with, thanks to whoever asked or reported.
After merge, the English is posted as-is to Discord #announcements (`.github/workflows/discord.yml`).

## Stamp

Same `YYYY-MM-DD-NN` string everywhere: `window.MC_BUILD` in `docs/flasher/index.html` and every `?v=` in
`docs/index.html`, `docs/flasher/index.html`, `docs/guide/index.html`. Find them with
`rg -n 'MC_BUILD|\?v=2' docs/`. Increment `NN` for a second change the same day.

## README

One row in the table of `README.md` (English only, the repo overview): feature, what it does, origin, status; and a
section in `FEATURES.md` (what it does, how to use it with the keys, limits, origin, status) plus its key combinations
in the shortcut map at the top of that file.

## Checklist

- [ ] Every new visible string has `en` and `fr`, same facts
- [ ] Buttons, screen text and limits checked against the note and the proof (not invented)
- [ ] Status wording matches `os.json` (`experimental` / `tested`)
- [ ] The `guide` anchor of `os.json` exists; the smoke test's French-row check passes
- [ ] Stamp bumped on all three pages
