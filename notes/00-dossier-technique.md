# Dossier technique : Model:Cycles, mod USB multipiste

> **Objectif du projet** : faire sortir en USB les 6 pistes du Model:Cycles, au lieu du seul mix stéréo (2 canaux).
> **Source analysée** : fil [« Model:Cycles Q & A with Ess »](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712) sur Elektronauts (topic 122712).
> **Périmètre** : les 248 messages visibles du fil ont été lus (n° #1 à #268, du 28/02/2020 au 30/07/2026).
> **Date de l'analyse** : 24/09/2026.

---

## 0. Méthode et conventions

### Comment lire ce dossier

Chaque information est rédigée en français. Juste en dessous figure un **extrait verbatim** du message d'origine (en anglais), avec l'auteur, la date et un lien direct vers le post. Les extraits sont volontairement courts : ils contiennent la phrase technique utile. Le lien permet de relire la réponse complète dans son contexte.

### Niveau de fiabilité

| Étiquette | Signification |
|---|---|
| **`OFFICIEL`** | Affirmé par un membre d'Elektron (Ess ou eangman) |
| **`UTILISATEUR`** | Observation ou affirmation d'un utilisateur, non confirmée par Elektron |
| **`HYPOTHÈSE`** | Spéculation d'un utilisateur |
| **`ANALYSE`** | Déduction de ma part, **non présente telle quelle dans le fil** (sans citation) |

### Qui est qui dans le fil

| Pseudo | Rôle (d'après le fil) | Posts |
|---|---|---|
| **Ess** | Employé Elektron à l'époque, concepteur des machines sonores du M:C (prototypes Max/Max4Live). A quitté Elektron en octobre 2020. | #1, #45, #47, #75, #122, #143, #158, #160, #168, #173, #238 |
| **eangman** | Staff Elektron, rédacteur du manuel | #82 |
| **Oscar A.** | Ingénieur DSP Elektron, a porté les machines sur le hardware (cité par Ess, n'intervient pas) | n/a |
| **Jon** | Créateur du concept Model:series (cité par Ess) | n/a |
| **AdamJay, avantronica** | Modérateurs du forum | divers |

### Messages manquants

Les numéros suivants n'apparaissent plus dans le fil (supprimés, ou déplacés par les modérateurs vers d'autres sujets) : #28, 32, 50, 64, 84, 85, 97, 117, 132, 133, 167, 186, 187, 192, 198, 221, 230, 235, 244, 259. La liste des fils de destination se trouve en [section 10](#10-fils-connexes-à-explorer).

---

## 1. Synthèse express pour le projet

1. **Aujourd'hui**, le M:C est une interface audio USB *class compliant*, en **stéréo uniquement** ([§3](#3-usb-audio-et-connectique)).
2. **Elektron juge le multicanal class compliant « délicat et gourmand en CPU »** et ne sait pas s'il est faisable. C'est **le risque n°1 du projet** ([§3.3](#33-multicanal-en-class-compliant--lavis-officiel)).
3. **Le CPU** est un ColdFire MCF5441(x) à 250 MHz, le même que sur Digitakt, Digitone, Analog Rytm et Analog Four. **Tout le DSP est écrit en assembleur** ([§2](#2-plateforme-matérielle-cpu)).
4. **Il n'y a pas d'Overbridge** sur la gamme Model. En revanche, des Elektron qui partagent la même famille de CPU le supportent ([§3.5](#35-overbridge)).
5. **La chaîne de signal par piste** est : machine → Volume/Dist (numérique) → Pan (sans fuite) → envois Delay/Reverb (effets partagés). Le tout arrive sur **un bus de mix qui sature**, et cette saturation fait interagir les pistes entre elles ([§5](#5-chaîne-de-signal-et-mixage-cœur-du-sujet)).
6. **Un contournement existe déjà pour 2 pistes** : panoramique à fond à gauche / à droite, effets coupés ([§5.6](#56-contournement-existant--2-pistes-isolées-par-panoramique)).
7. **L'état n'est sauvegardé qu'à l'extinction** par le bouton power. C'est une limite matérielle à garder en tête pendant les tests ([§7](#7-firmware-stockage-et-mises-à-jour)).

---

## 2. Plateforme matérielle (CPU)

### 2.1 Processeur principal
**`OFFICIEL`** Le CPU est un **Freescale/NXP ColdFire MCF5441** (sic). Il développe jusqu'à 385 MIPS Dhrystone 2.1 à **250 MHz**.

> "Coldfire MCF5441 with up to 385 dhrystone 2.1 MIPS @ 250 MHz"
> — **Ess**, 05/03/2020, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122)

*Question d'origine* :
> "What is the core cpu on the Model:Series, at what clock speed?"
> — delta-c, 02/03/2020, [#80](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/80)

`ANALYSE` : « MCF5441 » ne désigne pas une référence complète. Il s'agit très probablement de la famille **MCF5441x** (MCF54410 à MCF54418). La référence exacte devra être relevée sur la puce ([§11](#11-points-à-vérifier-hors-du-fil)).

### 2.2 Même CPU que le reste de la gamme Elektron (sauf Octatrack)
**`OFFICIEL`** C'est le même processeur que sur les autres produits Elektron de l'époque, **sauf l'Octatrack**.

> "Same one as in our other current lineup of products sans the Octatrack."
> — **Ess**, 05/03/2020, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122)

**`OFFICIEL`** Attention toutefois : un même CPU ne veut pas dire un même logiciel. Ce processeur généraliste fait des choses très différentes selon la machine.

> "it's a general purpose CPU and it does very different things across all machines."
> — **Ess**, 05/03/2020, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122)

### 2.3 Pas de puce DSP ni de FPGA dédiés (déduit)
**`OFFICIEL`** + **`ANALYSE`** On a demandé à Ess si la FM tournait en assembleur sur le CPU ou si une puce FPGA ou FM dédiée l'assistait. Il a répondu que **tout le DSP est fait en assembleur**. Il ne mentionne aucun coprocesseur, ce qui suggère que tout tourne sur le ColdFire.

> "purely in assembler on the CPU or is there an FPGA /dedicated FM hardware"
> — delta-c (question), 02/03/2020, [#80](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/80)

> "All DSP is done in assembler."
> — **Ess**, 05/03/2020, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122)

### 2.4 Budget CPU serré
**`OFFICIEL`** Le Rytm pourrait en théorie faire tourner les machines du M:C. En pratique, il est déjà trop occupé par ses autres tâches. Cela montre que **la marge CPU de ces plateformes est faible**, ce qui compte pour un mod qui ajouterait de la charge (flux USB supplémentaires).

> "the Rytm does a lot of other stuff so it won't have enough power"
> — **Ess**, 05/03/2020, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122)

### 2.5 Écran : question restée sans réponse
**`UTILISATEUR`** Un utilisateur a demandé la référence de l'écran et s'il utilise le bus I2C. Il envisageait de le remplacer par un OLED. **Personne ne lui a répondu.**

> "does it (the screen) speak I2C?"
> — sigint, 12/03/2020, [#189](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/189)

---

## 3. USB, audio et connectique

### 3.1 Interface audio USB class compliant
**`UTILISATEUR`** (renvoie aux specs officielles) L'interface audio USB du M:C est *class compliant*, sans pilote. L'information figure sur la fiche produit Elektron.

> "Is the audio interface class compliant?"
> — ManMadeDisaster (question), 02/03/2020, [#98](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/98)

> "yes - it's shown on the product specs !!"
> — avantronica (modérateur), 02/03/2020, [#100](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/100)

### 3.2 Sortie USB en stéréo uniquement
**`UTILISATEUR`** Le M:S et le M:C ne sortent qu'**en stéréo** : c'est précisément la limite que le projet vise à lever.

> "I was told that M:S & M:C is stereo out only."
> — Synj00, 29/02/2020, [#61](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/61)

### 3.3 Multicanal en class compliant : l'avis officiel
**`OFFICIEL`** ⚠️ **C'est l'information la plus importante du fil pour ce projet.** Ess a répondu à la question de l'enregistrement multicanal : en class compliant, c'est **délicat et gourmand en CPU**, et il **n'est pas sûr que ce soit possible**.

> "any chance of multi channel record in the future via the recorder app?"
> — mleaf (question), 29/02/2020, [#10](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/10)

> "Multi-channel via class compliant audio is a bit tricky and CPU heavy"
> — **Ess**, 29/02/2020, [#45](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/45) *(la phrase se termine par « not sure if possible »)*

### 3.4 Sorties séparées en class compliant, sans Overbridge
**`HYPOTHÈSE`** Un utilisateur défend l'idée que des sorties séparées pourraient passer par l'audio USB class compliant, **sans avoir besoin d'Overbridge**. C'est exactement l'approche de ce projet.

> "Separate outs could be done via the Class Compliant USB audio"
> — phutyle, 29/02/2020, [#43](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/43) *(la suite : « no need for Overbridge support »)*

### 3.5 Overbridge
**`UTILISATEUR`** Le Model:Samples n'est pas pris en charge par Overbridge, et un utilisateur en déduit qu'il en ira de même pour le Model:Cycles. Overbridge ne fonctionne que sur les machines haut de gamme et sur Digitakt/Digitone.

> "So far only their high end devices and the Digitakt/Digitone are supported by Overbridge."
> — Jeronan, 29/02/2020, [#39](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/39)

`ANALYSE` : selon Ess ([§2.2](#22-même-cpu-que-le-reste-de-la-gamme-elektron-sauf-octatrack)), Digitakt et Digitone ont le même CPU que le M:C. Or ils sortent leurs pistes séparément en USB via Overbridge. **Le CPU est donc capable de faire du multicanal USB.** Deux réserves : Overbridge est un protocole propriétaire (pas class compliant), et l'électronique USB du M:C (port, PHY, vitesse) peut différer de celle de ces machines.

### 3.6 Port micro-USB, pas d'alimentation par l'USB
**`OFFICIEL`** Pourquoi un port micro-USB, et pourquoi ne peut-on pas alimenter la machine par ce port ? Ess l'explique par la **complexité** que cela aurait ajoutée au projet, jugée hors périmètre.

> "how much complexity that would have added to the project"
> — **Ess**, 29/02/2020, [#45](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/45)

### 3.7 Alimentation 5 V par le port latéral
**`UTILISATEUR`** La machine peut être alimentée en **5 V USB par le port latéral** (celui de la poignée batterie). On compte ainsi trois ports distincts : alimentation principale, alimentation latérale et USB données.

> "Considering that via the side port you can power the M:C with 5v USB"
> — Drumunkey, 24/03/2020, [#212](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/212)

### 3.8 Isolation USB / alimentation : risque de boucle de masse
**`HYPOTHÈSE`** Séparer l'alimentation du port USB de données évite probablement les **boucles de masse** et les sifflements, un problème connu sur OP-1/OP-Z. Un autre utilisateur confirme ce type de bruit sur un autre appareil. **À prendre en compte si le mod touche au câblage USB.**

> "Keeping them isolated from each other means no background whine when plugged in."
> — pselodux, 24/03/2020, [#213](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/213)

> "I returned the Uno because of the horrible usb buzz/hum."
> — Drumunkey, 24/03/2020, [#215](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/215)

### 3.9 Pas d'entrée audio
**`OFFICIEL`** Il n'y a pas d'entrée audio. Ess pense que c'est un choix lié au **format** (manque de place physique) et au **coût**.

> "a decision based on the form factor (lack of physical space) and cost."
> — **Ess**, 29/02/2020, [#45](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/45)

---

## 4. Architecture DSP et moteur sonore

### 4.1 DSP écrit à la main en assembleur par un ingénieur dédié
**`OFFICIEL`** Chaque machine est implémentée **en assembleur** par Oscar, l'ingénieur DSP. Créer une nouvelle machine représente donc beaucoup de travail.

> "our DSP engineer Oscar who implements it on hardware (in assembler!)"
> — **Ess**, 29/02/2020, [#45](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/45)

### 4.2 Processus : prototype Max, puis traduction pour le hardware
**`OFFICIEL`** Les machines ont d'abord été prototypées dans Max, puis diffusées en interne sous forme de devices Max4Live. Une fois le son validé, les patchs ont été **traduits pour tourner sur le hardware**, ce qui a pris plusieurs mois.

> "first I made prototypes in Max which I made Max4live Devices out of"
> — **Ess**, 05/03/2020, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122)

> "we started translating the patches to run on hardware"
> — **Ess**, 05/03/2020, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122)

**`OFFICIEL`** Les patchs Max ne seront pas partagés.

> "No, I can't share the patches"
> — **Ess**, 05/03/2020, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122)

**`UTILISATEUR`** Le firmware n'exécute donc pas le patch Max d'origine.

> "it's not actually using the original Max patch."
> — pselodux, 27/03/2020, [#218](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/218)

### 4.3 Moteur à structure dynamique (changement de machine par pas)
**`OFFICIEL`** Le moteur audio repose sur une **grande structure reconfigurable dynamiquement**. C'est elle qui permet de **changer de machine à chaque pas** du séquenceur.

> "a huge structure that can dynamically change […] allows us to swap machine per step"
> — **Ess**, 05/03/2020, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122)

`ANALYSE` : le graphe de traitement d'une piste n'est pas figé. Un tap (point de prélèvement) par piste devra donc se placer **en aval de la machine**, à un endroit stable quelle que soit la machine chargée.

### 4.4 Pas de vol de voix : une voix par piste
**`OFFICIEL`** Le M:C n'a pas de *note stealing*.

> "the Cycles doesn't have any note stealing"
> — **Ess**, 01/03/2020, [#75](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/75)

`ANALYSE` : chaque piste a sa propre voix, donc **6 signaux distincts existent en interne avant le mixage**. Isoler ces signaux est la condition de base du projet.

### 4.5 Synthèse : modulation de phase, 4 opérateurs
**`OFFICIEL`** La « FM » est en réalité de la **modulation de phase** (PM), comme chez Yamaha. Son principal avantage est d'autoriser le feedback sans désaccorder le son.

> "The FM is not FM at all; it's phase modulation"
> — **Ess**, 05/03/2020, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122)

> "the possibility of doing feedback without detuning the sound."
> — **Ess**, 05/03/2020, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122)

**`OFFICIEL`** Ess considère que 4 opérateurs représentent un bon compromis.

> "4 Operators are a very good amount I think"
> — **Ess**, 05/03/2020, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122)

### 4.6 Machine CHORD
**`OFFICIEL`** La voix CHORD se compose de **4 oscillateurs qui jouent tous la même wavetable**.

> "it's just four oscillators that each play the same wavetable."
> — **Ess**, 05/03/2020, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122)

**`OFFICIEL`** Toutes les wavetables ont été générées **par synthèse additive**.

> "All of the tables in the Cycles are made strictly with additive synthesis."
> — **Ess**, 05/03/2020, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122)

**`OFFICIEL`** Le paramètre COLOR mélange successivement le 1er renversement, puis le 2e renversement de l'accord. Ses derniers crans transposent le même accord à l'octave.

> "it mixes in the first inversion then the second inversion of the chord"
> — **Ess**, 29/02/2020, [#45](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/45)

### 4.7 Machine KICK
**`OFFICIEL`** Le KICK s'inspire des boîtes à rythmes classiques, avec une touche de FM. Sa particularité : un **façonnage d'onde triangulaire réinjecté dans le feedback**.

> "The Kick drum is inspired by classic drum machines but with some FM sprinkles."
> — **Ess**, 05/03/2020, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122)

> "having the triangular waveform shaping that goes to feedback is kind of unique"
> — **Ess**, 05/03/2020, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122)

### 4.8 Pas d'EQ, filtres propres à certaines machines, octave par défaut
**`OFFICIEL`** Il n'y a pas d'EQ, mais certaines machines intègrent un filtre : le hihat, par exemple, est filtré en passe-haut. Chaque machine a aussi une « octave par défaut ».

> "some of them have a filter. The hihat for example is high-passed."
> — **Ess**, 07/03/2020, [#158](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/158)

> "each machine has a certain 'default octave' as well."
> — **Ess**, 07/03/2020, [#158](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/158)

### 4.9 Paramètres d'une machine et macros (capture du prototype M4L)
**`OFFICIEL`** Ess a partagé une capture du device Max4Live du kick (« model_kick_v2_1_smoothed_exp_shpe2 »), en précisant que **tous les prototypes avaient cette apparence**. On y voit 6 paramètres : **Pitch, Decay, Sweep, Contour, Color, Shape**. Ce sont les mêmes que sur la façade.

> "Sure! This is how all of them looked:"
> — **Ess**, 07/03/2020, [#160](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/160)

**`OFFICIEL`** Le patch Max4Live est le même que celui qui a servi à concevoir les contrôles.

> "The Max4Live patch is really the same patch."
> — **Ess**, 07/03/2020, [#158](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/158)

**`OFFICIEL`** Le mapping et la mise à l'échelle des macros relèvent du **secret de fabrication**. Ess envisage seulement d'expliquer les algorithmes.

> "No, the mapping and scaling is our secret sauce. The algorithms, maybe."
> — **Ess**, 05/03/2020, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122)

**`OFFICIEL`** La stat « MAG » (magie) des fiches de machines indique grossièrement la **quantité de macro-mapping** de chaque machine. Ces stats n'ont aucun effet fonctionnel.

> "Magic that's loosely referring to how much macro mapping is in each machine."
> — **Ess**, 05/03/2020, [#143](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/143)

### 4.10 Ajouter des machines : possible, mais coûteux
**`OFFICIEL`** Ajouter des machines est techniquement possible, mais demande beaucoup de travail. Un 7e patch a d'ailleurs été abandonné, par manque de temps et parce que sa structure différait trop des autres.

> "It is technically possible, but making a machine takes a lot of work"
> — **Ess**, 29/02/2020, [#45](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/45)

> "There were one patch that didn't make the cut"
> — **Ess**, 05/03/2020, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122)

### 4.11 Résolution interne des paramètres (au-delà de 7 bits)
**`OFFICIEL`** La profondeur du LFO est un paramètre **haute résolution** : elle va de -64.0 à 63.0 par pas de 0.1. La résolution interne dépasse donc les 0-127 du MIDI.

> "MIDI implementation would indicate that it uses a finer resolution than 0-127."
> — stutech (question), 29/02/2020, [#53](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/53)

> "from -64.0 to 63.0 so it has a a resolution of 0.1 steps."
> — **eangman**, 02/03/2020, [#82](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/82)

### 4.12 Emplacement des LFO : question sans réponse
**`UTILISATEUR`** Les LFO appartiennent-ils aux machines ou aux pistes et au séquenceur ? **Personne n'a répondu.**

> "are they part of the machines or part of the track/sequencer?"
> — Seta, 24/03/2020, [#214](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/214)

---

## 5. Chaîne de signal et mixage (cœur du sujet)

`ANALYSE` : d'après les éléments ci-dessous, le chemin d'une piste se reconstitue ainsi :

```
[Machine (PM, 1 voix)] → [Volume + Dist numérique] → [Pan] ─┬─→ bus de MIX (sature) → sortie stéréo / USB stéréo
                                                            ├─→ envoi DELAY  (HP/LP fixe) ──┐
                                                            └─→ envoi REVERB (Tone)  ───────┴─→ retour au MIX
```

*(L'ordre exact entre Volume/Dist et Pan n'est pas confirmé dans le fil.)*

### 5.1 Étage Volume + Distorsion par piste
**`OFFICIEL`** Monter le Volume d'une piste jusqu'à la saturation fait entrer en jeu une **distorsion numérique**, qui n'est modélisée sur aucun matériel existant. C'est donc un **étage de gain/saturation propre à chaque piste**.

> "when you increase Volume to the point of distortion (post 70)"
> — **Ess**, 29/02/2020, [#45](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/45)

> "a digital model not based on any specific hardware"
> — **Ess**, 29/02/2020, [#45](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/45)

`ANALYSE` : « post 70 » veut très probablement dire « au-delà de 70 » (coquille pour *past 70*) : la distorsion interviendrait au-dessus de la valeur 70. Il est moins probable que ce soit un renvoi à un message n°70. À vérifier sur la machine.

### 5.2 Panoramique sans fuite
**`OFFICIEL`** Une piste panoramiquée à fond ne déborde **pas** sur le canal opposé.

> "If you pan all the way, does the sound bleed into the opposite channel?"
> — blinkingboxes (question), 28/02/2020, [#5](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/5)

> "No."
> — **Ess**, 29/02/2020, [#45](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/45)

### 5.3 Le bus de mix sature, et les pistes interagissent
**`OFFICIEL`** Quand le mix sature en interne, la saturation fait interagir les pistes : l'énergie fréquentielle de chacune modifie l'écrêtage du mix. Ess parle de **modulation croisée « naturelle »**. Il ne s'agit pas d'une modulation programmée volontairement.

> "when one track starts clipping all the other tracks interact with the distortion"
> — MichaalHell (observation), 28/02/2020, [#9](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/9)

> "No, when the mix is clipping internally it just sounds like that."
> — **Ess**, 29/02/2020, [#45](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/45)

> "I guess you could call it 'natural' cross modulation"
> — **Ess**, 29/02/2020, [#45](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/45)

`ANALYSE` : **point de conception majeur.** Les pistes prélevées avant le bus de mix n'auront pas cette saturation commune. Leur somme dans un DAW ne sonnera donc pas exactement comme la sortie stéréo d'origine. Il faudra choisir le point de prélèvement en connaissance de cause ([§9](#9-implications-pour-le-projet-analyse)).

### 5.4 Effets Delay et Reverb : des effets partagés en envoi
**`OFFICIEL`** La reverb a un paramètre **Tone** (FUNC maintenu + potentiomètre Reverb Size). Le delay a un **filtrage HP/LP fixe**.

> "The Reverb does have a Tone parameter (Hold FUNC and turn Reverb Size)"
> — **Ess**, 05/03/2020, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122)

> "the Delay has a fixed HP/LP setting that rolls of nicely."
> — **Ess**, 05/03/2020, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122)

**`OFFICIEL`** L'algorithme de reverb est le même que sur le Model:Samples.

> "Yes, it's the same."
> — **Ess**, 05/03/2020, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122) *(en réponse à « Does the M:C have the same reverb algorithm as the M:S? »)*

**`UTILISATEUR`** Le delay est-il lui aussi identique à celui du M:S ? **La question est restée sans réponse.**

> "I'm wondering if the delay effect is exactly the same as in the model:samples."
> — Dr.K, 12/05/2020, [#229](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/229)

### 5.5 VDEP : la vélocité agit sur le volume de la piste
**`OFFICIEL`** VDEP (menu PADS) règle l'influence de la vélocité sur le **volume de la piste**. Il n'agit pas sur la réponse des pads.

> "VDEP controls how much the velocity will control the track volume."
> — **Ess**, 01/03/2020, [#75](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/75)

### 5.6 Contournement existant : 2 pistes isolées par panoramique
**`UTILISATEUR`** En studio, un utilisateur exploite le M:C comme **synthé bi-timbral** : chaque piste est envoyée sur son propre côté de la sortie, sans reverb ni delay. C'est la seule façon d'obtenir 2 pistes séparées sans modification, et cela confirme le besoin du projet.

> "a two part monophonic synth with individual outputs (dry, no reverb or delay)"
> — Seta, 24/03/2020, [#214](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/214)

**`UTILISATEUR`** Dès le début du fil, un utilisateur exprimait le besoin de séparer batterie et parties mélodiques à l'enregistrement.

> "It would be really useful to separate drums from tones when recording."
> — blinkingboxes, 28/02/2020, [#5](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/5)

---

## 6. MIDI (utile si le mod touche aussi à l'USB-MIDI)

### 6.1 MIDI Thru logiciel
**`OFFICIEL`** Le MIDI Thru est un **soft thru**, c'est-à-dire reconstruit par logiciel, « mais bien fait ».

> "Yes, it's a soft Thru, but it's done right so..."
> — **Ess**, 05/03/2020, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122)

### 6.2 Données MIDI émises par le séquenceur
**`UTILISATEUR`** D'après le manuel (cité de mémoire par un utilisateur), le séquenceur n'émet que des **notes MIDI**.

> "only MIDI note data will be transmitted by the sequencer."
> — stutech, 11/03/2020, [#182](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/182)

**`UTILISATEUR`** Les modulations des LFO internes ne sortent pas en MIDI. Seuls les mouvements **manuels** des potentiomètres sont émis, à condition que M Out soit activé sur la piste.

> "if M Out is enabled per track you can sweep the encoder manually"
> — avantronica (modérateur), 11/03/2020, [#183](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/183)

**`UTILISATEUR`** Contrairement aux grosses machines Elektron, on ne peut pas filtrer les CC envoyés par les potentiomètres.

> "you can't filter notes from encoders though as the bigger boxes do"
> — avantronica (modérateur), 11/03/2020, [#185](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/185)

### 6.3 Synchronisation des changements de pattern
**`UTILISATEUR`** Avec un Octatrack en maître, le changement de pattern arrivait avec une mesure de retard. Il a fallu passer le *scale setup* de « track » à « pattern » pour qu'il se fasse en rythme.

> "switch from track to pattern in scale setup"
> — mas_akala, 29/02/2020, [#34](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/34)

---

## 7. Firmware, stockage et mises à jour

### 7.1 Sauvegarde de l'état uniquement à l'extinction propre
**`OFFICIEL`** L'état courant n'est sauvegardé que si l'on éteint la machine **avec le bouton power**. Une coupure d'alimentation perd toutes les modifications faites depuis l'allumage. Ess précise que c'est une **limite du matériel**.

> "You need to power the unit down by pressing the power off button"
> — **Ess**, 29/02/2020, [#45](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/45)

> "It's a limitation of the hardware."
> — **Ess**, 29/02/2020, [#45](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/45)

**`UTILISATEUR`** D'autres utilisateurs l'ont confirmé plus tard (#253, #254, #266).

> "hold the power button until it shuts down, then disconnect the mains."
> — Adam9, 25/06/2021, [#253](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/253)

`ANALYSE` : la mémoire de travail est vraisemblablement recopiée en mémoire non volatile uniquement à l'extinction. **Pendant les tests du mod, toujours éteindre avec le bouton power**, sous peine de perdre des réglages ou de laisser un état incohérent.

### 7.2 Base de code commune avec le Model:Samples (indice)
**`UTILISATEUR`** Le même bug (le mode MUTE qui reste verrouillé après FUNC + une touche ouvrant une boîte de dialogue) a été corrigé dans l'OS 1.02 du M:S. Il était encore présent sur le M:C.

> "it looks like this BUG is presently in the M:C."
> — Tchu, 02/03/2020, [#81](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/81)

**`OFFICIEL`** Officiellement, le mode MUTE n'est pas verrouillable : il faut maintenir FUNC.

> "There is no way to latch the mute mode"
> — **Ess**, 01/03/2020, [#75](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/75)

`ANALYSE` : un bug identique sur les deux machines laisse penser que le M:S et le M:C partagent une **grande partie de leur firmware** (interface, séquenceur). Retenir ce point pour l'étude du firmware.

### 7.3 Versions d'OS mentionnées
**`UTILISATEUR`** Le fil renvoie vers un sujet « **Model:Cycles OS 1.11 & 1.12: bug reports** » (post déplacé par un modérateur, #211). Pour le Model:Samples, il cite le changelog de l'OS 1.01 à 1.02 (#81).

### 7.4 Perspectives de mises à jour officielles
**`UTILISATEUR`** Ess a quitté Elektron en octobre 2020. **Aucune sortie multipiste officielle n'a été annoncée** dans le fil.

> "Ess left Elektron last month."
> — craig, 13/11/2020, [#243](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/243)

### 7.5 Philosophie d'interface Model:series (utile pour intégrer une option)
**`OFFICIEL`** Jon, qui a conçu le concept Model:series, veut **le moins de fonctions secondaires possible** afin de préserver le principe « un bouton = une fonction ».

> "wants to keep as few secondary functions as possible"
> — **Ess**, 29/02/2020, [#45](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/45)

`ANALYSE` : un réglage « mode USB multipiste » irait donc logiquement dans le menu SETTINGS, plutôt que sur une combinaison de touches.

---

## 8. Hardware : démontage et modifications physiques

### 8.1 Retrait des boutons
**`OFFICIEL`** Ess a retiré les boutons de sa machine en faisant levier avec une cuillère.

> "I removed the knobs (using a spoon as leverage)"
> — **Ess**, 29/02/2020, [#45](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/45)

### 8.2 Mod de sensibilité des pads
**`UTILISATEUR`** Un utilisateur a rendu les pads plus sensibles en collant du **ruban adhésif sous la membrane caoutchouc**. Un autre confirme que ça marche.

> "I put duct tape under the track pads rubber, to make them more sensitive."
> — DaveWaves, 11/03/2021, [#248](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/248)

**`OFFICIEL`** Ess reconnaît qu'il faudrait proposer plusieurs **profils de réponse des pads**, un réglage qui relèverait du firmware.

> "I agree that we should look into different pad profiles"
> — **Ess**, 01/03/2020, [#75](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/75)

---

## 9. Implications pour le projet (analyse)

> ⚠️ Cette section est **mon analyse** à partir des éléments ci-dessus. Elle n'est pas sourcée dans le fil.

**Faisabilité**
- Le CPU de la plateforme sait faire du multicanal USB : c'est le même que Digitakt et Digitone, qui le font via Overbridge (§2.2, §3.5).
- Chaque piste a sa propre voix (§4.4), donc les 6 signaux existent en interne avant le mixage.
- Ess dit clairement que le **multicanal class compliant est lourd pour le CPU** (§3.3), sur une plateforme déjà peu dotée en marge (§2.4).

**Décisions de conception à prendre**
1. **Nombre de canaux** : 6 mono (une piste = un canal) ou 12 (6 paires stéréo post-pan) ? Faut-il ajouter le mix stéréo d'origine (8 ou 14 canaux) ?
2. **Point de prélèvement** de chaque piste :
   - avant ou après **Volume/Dist** (§5.1) ;
   - avant ou après **Pan** (§5.2) ;
   - dans tous les cas **avant la saturation du bus de mix** (§5.3), ce qui change le rendu par rapport à la sortie stéréo.
3. **Effets partagés** (§5.4) : pistes sèches plus une paire stéréo « retours FX » ? Ou pistes post-envoi ?
4. **Stabilité du tap** malgré le moteur dynamique qui change de machine par pas (§4.3).
5. **Emplacement du réglage** : un menu plutôt qu'un raccourci, par cohérence avec la philosophie Model (§7.5).

**Plan de repli**
- Le hard-pan donne déjà 2 pistes isolées (§5.6).

---

## 10. Fils connexes à explorer

Des posts de ce fil ont été déplacés vers les sujets suivants, qui peuvent contenir d'autres informations techniques :

- [Model:Cycles Feature Requests Thread](https://www.elektronauts.com/t/model-cycles-feature-requests-thread/122523) (nombreuses demandes, dont sans doute les sorties séparées)
- [Model:Cycles OS 1.11 & 1.12: bug reports](https://www.elektronauts.com/t/model-cycles-os-1-11-1-12-bug-reports/122530)
- [Model:Cycles Tips & Tricks Thread](https://www.elektronauts.com/t/model-cycles-tips-tricks-thread/122798)
- [Model:Cycles (fil principal)](https://www.elektronauts.com/t/model-cycles/122478)
- [Clicks](https://www.elektronauts.com/t/clicks/123020)
- [LFO types, how to hold](https://www.elektronauts.com/t/lfo-types-how-to-hold/123116)
- [FM workshop livestream](https://www.elektronauts.com/t/fm-workshop-livestream-live-dj-sets/125242)

---

## 11. Points à vérifier (hors du fil)

Ces informations sont **absentes du fil** mais nécessaires au projet :

- [x] **Référence exacte du CPU** (marquage de la puce, famille MCF5441x) et fiche technique NXP (contrôleur USB, interfaces audio). → **MCF54415CMJ250**, lu sur la puce le 30/09/2026 ([notes/21 §3.1](notes/21-architecture-materielle.md#31-processeur--u1)).
- [x] **Vitesse du port USB** (Full-Speed ou High-Speed) : elle conditionne directement le nombre de canaux transportables. → **High Speed** : PHY USB3300 sur la carte ([notes/21 §4](notes/21-architecture-materielle.md#4-usb)), et mod 6 canaux validé en High Speed.
- [ ] **Format audio USB actuel** : fréquence d'échantillonnage et résolution.
- [ ] **Format, mode de mise à jour et éventuelle protection du firmware.**
- [ ] **Architecture interne mono ou stéréo** de chaque machine, avant le Pan.
- [ ] **Ordre exact** des étages Volume/Dist, Pan et envois FX.
- [ ] **Schémas-blocs des machines** : Ess avait accepté d'en partager (« Sure, why not. I'll try and find the time. », [#45](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/45)), mais ils ne sont jamais apparus dans le fil.

---

## Annexe : informations secondaires (faible pertinence directe)

| Info | Fiabilité | Extrait | Source |
|---|---|---|---|
| Pas de solo, uniquement des mutes | `OFFICIEL` | "No, you can only mute tracks." | Ess, [#45](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/45) |
| Nombre de retrigs réglable par piste, tempo par pattern | `UTILISATEUR` | "Retrig count is per track" / "Tempo is per pattern" | MichaalHell, [#31](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/31) |
| Paramètres de la page LFO principale verrouillables par pas (p-lock), pas ceux de la page SETUP | `UTILISATEUR` | "You can p-lock the main LFO page parameters." | AdamJay, [#66](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/66) |
| Vélocité réglable pour chaque trig (V100 par défaut) | `UTILISATEUR` | "You can edit velocity per trig, standard beeing V100." | Seta, [#120](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/120) |
| Décalage d'une piste entière : TRACK + encodeur principal | `UTILISATEUR` | "holding TRACK and turning the main encoder" | stutech, [#115](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/115) |
| Un nudge de ±23 ne déplace pas le trig jusqu'au pas suivant | `UTILISATEUR` | "Nope" | avantronica, [#200](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/200) |
| Un LFO aléatoire en mode reset donne une nouvelle valeur à chaque frappe | `OFFICIEL` | "Apparently yes, I had no idea." | Ess, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122) |
| « Pattern save » = point de sauvegarde, rechargeable | `OFFICIEL` | "a save point you can go back to" | Ess, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122) |
| Pas de Direct Jump prévu pour les patterns | `OFFICIEL` | "we have no plans to add Direct Jump." | Ess, [#75](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/75) |
| Pour être joué par le séquenceur, un preset doit être chargé sur la piste | `OFFICIEL` | "you have to load the preset to the track" | Ess, [#75](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/75) |
| Le mute par pattern est jugé nécessaire (souhait, pas un engagement) | `OFFICIEL` | "I think it's very necessary for live performance." | Ess, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122) |
| Portamento : aucune promesse | `OFFICIEL` | "Can't make any promises though!" | Ess, [#75](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/75) |
| Le « Control All » ne reste pas verrouillé | `UTILISATEUR` | "No" | AdamJay, [#119](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/119) |
| Poignée batterie choisie pour garder un boîtier fin | `OFFICIEL` | "to keep the form factor slimmer" | Ess, [#122](https://www.elektronauts.com/t/model-cycles-q-a-with-ess/122712/122) |
