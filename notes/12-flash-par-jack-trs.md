# 12 · Flasher avec un simple câble jack stéréo (entrée MIDI TRS)

Question du 25/09/2026 : **peut-on flasher le Model:Cycles avec un simple câble jack stéréo, sans passer par l'adaptateur DIN ?**
Réponse établie par recherche documentaire et simulation numérique, **sans matériel**. Les conventions `[FAIT]` / `[HYP]` / `[À FAIRE]` sont celles de l'[index](README.md).

---

## En bref

| Branchement | Verdict | Remarques |
|---|---|---|
| Interface USB-MIDI à **sortie MIDI en jack TRS 3,5 mm** → câble jack stéréo → MIDI IN du M:C | ✅ **Oui**, rien à modifier | Le MIDI IN du M:C accepte le type A **et** le type B : un câble jack stéréo 3,5 mm mâle-mâle quelconque convient. `flash.py` inchangé. |
| Interface MIDI DIN actuelle → un câble **DIN mâle → jack TRS mâle** | ✅ Oui | Un seul câble au lieu de câble DIN + adaptateur CA-3. |
| **Sortie casque** de l'ordinateur → câble jack stéréo → MIDI IN | 🟠 **Plausible, non testé** | Pas avec le `.syx` tel quel : il faut **synthétiser le signal MIDI dans un fichier audio**. La simulation valide la partie signal ; reste une inconnue électrique (niveau de sortie face au seuil de l'optocoupleur). Aucun précédent documenté trouvé. |
| Port USB du M:C, **menu de démarrage** | 🔴 Non | Exclu par le manuel (§13.4). |
| Port USB du M:C, **OS en marche** (`CONFIG → UPGRADE`, Transfer) | 🟡 1ᵉʳ flash seulement | Voie officielle, **jamais essayée avec le mod** ; ensuite le mod casse l'upgrade USB, donc le retour arrière repasse par le MIDI IN (§4). |

## 1. Ce que le bootloader écoute vraiment

- **`[FAIT]`** Menu de démarrage, OS UPGRADE : on envoie le SysEx « using the MIDI In port », et
  « USB MIDI transfer is not possible when upgrading the OS from the STARTUP menu » (manuel §13.4, cf. [09 §3](09-analyse-firmware-1.13.md#3-le-menu-de-démarrage-et-lupgrade-manuel-confirme-06)).
- **`[FAIT]`** Les Models ont des prises MIDI IN et MIDI OUT/THRU en **jack TRS 3,5 mm**. « The MIDI IN port accepts any configuration » (type A ou B) ;
  seul le MIDI OUT/THRU se règle (`CONFIG > MIDI > PORTS > OUT POL`). Le M:C est livré avec le kit **CA-3** : deux adaptateurs TRS type A → DIN 5 broches femelle (base de connaissances Elektron).
- ⇒ Le bootloader écoute **l'UART MIDI derrière le jack TRS**. Dans nos docs, « DIN » voulait dire « MIDI matériel ». Le connecteur DIN n'est qu'un intermédiaire, imposé par une interface DIN.
  **Corrigé** dans README, FLASH, BUILD, les scripts et les notes 05, 06, 08, 09, 11.
- **`[FAIT]`** (spécification MIDI) Côté électrique, le MIDI est une boucle de courant d'environ 5 mA vers la LED d'un optocoupleur, à travers ~220 Ω côté récepteur.
  Au repos (bit à 1) aucun courant ne passe ; un bit à 0 fait passer le courant.
  En TRS type A : pointe = broche 5 (retour du courant), bague = broche 4 (source), corps = broche 2 (blindage). Le type B inverse pointe et bague.
- **`[HYP]`** Pour accepter A et B, l'entrée est forcément **bidirectionnelle** (pont de diodes devant la LED, ou deux LED tête-bêche).
  Un courant dans un sens **ou** dans l'autre est lu comme un 0.
  **Mise à jour du 30/09/2026** : le PCB porte **deux optocoupleurs H11L1** derrière les jacks MIDI, ce qui va dans le sens des deux LED tête-bêche, sans pont ([21 §6](21-architecture-materielle.md#6-midi)).

## 2. Option A : sortie MIDI TRS + câble jack stéréo (recommandée)

- **Câble** : jack 3,5 mm **stéréo** (TRS, 3 contacts) mâle-mâle, câblage droit.
  - Pas de câble **mono** (TS) : sans la bague, il n'y a pas de boucle de courant.
  - Éviter les câbles **TRRS** (4 contacts, type casque-micro de téléphone).
- **Type A ou B de l'interface : indifférent** pour flasher, puisque l'entrée du M:C est bidirectionnelle. Le type ne compte que pour le MIDI OUT du M:C (réglage `OUT POL`).
- **Interfaces repérées** (liste non exhaustive, disponibilité à vérifier) :
  - **Retrokits RK-006** : interface USB class compliant, 2 entrées et 10 sorties, toutes en TRS type A. Sa fiche produit le dit : « you can replace MIDI cables with stereo mini-jack cables ».
  - **SnapBeat USB-MIDI (TRS) Interface** : petit dongle USB-C → sortie MIDI TRS 3,5 mm, reconnu sans pilote sous Windows d'après le vendeur. C'est le plus proche d'un « simple câble ». Sa tenue sur de longs SysEx n'est pas documentée.
  - **CME H12MIDI Pro** : E/S MIDI en 3,5 mm, type A ou B réglable par logiciel. Vérifier qu'il sert aussi d'interface pour ordinateur, et pas seulement d'hôte USB.
  - *CME WIDI Jack* (MIDI Bluetooth → TRS) : possible en théorie, **déconseillé** pour un transfert de 6 à 7 minutes sans contrôle de flux.
- **Logiciel : rien à changer.** Utiliser `./flash.sh` / `flash.bat`, ou `tools/flash.py --port "<ton interface>" --send`.
  La cadence `--pace 1.4` ménage les tampons des petites interfaces. Si le M:C reste figé sur `RECEIVING...`, passer à `--pace 2.0`.
- **Fiabilité SysEx** : certains câbles USB-MIDI bon marché corrompent les longs SysEx. Toujours faire d'abord une **répétition avec l'OS officiel 1.13** par le même chemin ([§3.8](#38-protocole-de-validation-proposé)) : si elle passe, le chemin est bon.
- **Si tu gardes ton interface DIN** : un câble **DIN mâle → jack TRS mâle**, de n'importe quel type, remplace à lui seul le câble DIN et l'adaptateur CA-3.

## 3. Option B : sortie casque de l'ordinateur (expérimental, non testé)

### 3.1 Pourquoi « envoyer le `.syx` » vers la sortie casque ne marche pas

La sortie casque restitue un **signal audio analogique**. Un lecteur audio ne sait pas « jouer » un `.syx`, et un logiciel MIDI ne voit pas la sortie casque comme un port MIDI.
Il faut **fabriquer un fichier audio dont la forme d'onde est le signal électrique MIDI** : 31 250 bits/s, trames 8N1, courant ou absence de courant.
Côté M:C, rien ne change : c'est le bootloader d'origine qui reçoit, et il ne voit que des octets MIDI.

### 3.2 Principe

- Canal gauche (pointe) et canal droit (bague) en **opposition de phase** : la tension pointe-bague vaut **le double** de la crête d'un canal.
- Repos (bit à 1) = 0 V. Bit à 0 = ±V, assez pour faire passer quelques mA dans la LED de l'optocoupleur.
- Le corps (masse audio) n'intervient pas : l'entrée MIDI est isolée.

### 3.3 Contrainte n° 1 : le niveau de sortie (l'inconnue principale)

| Sortie casque | Crête par canal (pleine échelle) | Tension pointe-bague (opposition de phase) |
|---|---|---|
| Dongle USB-C ou téléphone, ~0,5 à 1 Vrms | 0,7 à 1,4 V | 1,4 à 2,8 V |
| Sortie intégrée d'un PC, ~1 à 2 Vrms | 1,4 à 2,8 V | 2,8 à 5,7 V |
| Mac récent (Apple : 1,25 Vrms sous 150 Ω, 3 Vrms de 150 Ω à 1 kΩ) | 1,8 / 4,2 V | 3,5 / 8,5 V |

Les Vrms sont ceux d'un sinus pleine échelle ; un signal carré pleine échelle a la même crête.
Le Mac adapte sa tension à la charge qu'il détecte : l'entrée MIDI, ouverte vers la masse, sera sans doute vue comme une haute impédance.

- **`[HYP]` Seuil côté M:C** : LED (1,1 à 1,6 V) + pont éventuel (0 à 1,4 V) + 220 Ω × 1 à 5 mA, soit **≈ 1,3 à 4 V**. Le schéma d'entrée et l'optocoupleur du M:C ne sont pas documentés.
- ⇒ **Probable** sur un Mac récent ou une sortie de PC correcte, **incertain** sur un dongle ou un téléphone. **Seul un test tranche** ([§3.8](#38-protocole-de-validation-proposé), étape 1, sans risque).
- **Sécurité `[HYP]`** : la résistance d'entrée (~220 Ω) limite le courant. Au pire (Mac en mode 3 Vrms, volume maximal), cela donne ≈ 25 à 35 mA en crête.
  C'est au-dessus des 5 mA nominaux, mais sous les maxima usuels des LED d'optocoupleur (≈ 50 mA).
  **Ne pas monter le volume au-delà du nécessaire** : le calibrage vise environ 2 fois le seuil, soit typiquement une dizaine de mA (7 à 25 mA selon le circuit).

### 3.4 Contrainte n° 2 : la fréquence d'échantillonnage (simulée)

Un bit MIDI dure 32 µs, un échantillon à 48 kHz 20,8 µs. Caler chaque front sur l'échantillon le plus proche le décale jusqu'à ±1/3 de bit : c'est trop pour un UART.
Il faut donc **synthétiser des fronts à bande limitée**, placés au sous-échantillon près, et **de préférence sortir en 96 kHz**.

**Simulation** ([annexe](#annexe--script-de-simulation)) :
- flux au format réel d'un OS Elektron (marqueurs + 12 paquets de 128 octets, contenu aléatoire) ;
- filtre de reconstruction du DAC ;
- optocoupleur modélisé par un seuil, exprimé en fraction de l'amplitude ;
- UART 16× avec vote majoritaire au centre du bit.

La **marge** est l'erreur d'horloge tolérée avant la première erreur. Un signal numérique parfait donne ±4,25 %.
La norme MIDI admet ±1 % d'écart de débit, et l'écart réel entre deux horloges à quartz est bien plus faible : **une marge d'au moins 1 % suffit**.

| fs | Fronts | seuil 0,2 (+14 dB) | 0,35 (+9 dB) | 0,5 (+6 dB) | 0,65 (+4 dB) | 0,8 (+2 dB) |
|---|---|---|---|---|---|---|
| 44,1 kHz | bande limitée | ❌ | 2,5 % | 3,25 % | 1,0 % | ❌ |
| 44,1 kHz | arrondis à l'échantillon | ❌ | ❌ | ❌ | ❌ | ❌ |
| 48 kHz | bande limitée | ❌ | 2,75 % | 3,75 % | 2,0 % | ❌ |
| 48 kHz | arrondis à l'échantillon | ❌ | ❌ | ❌ | ❌ | ❌ |
| **96 kHz** | **bande limitée** | **2,25 %** | **3,75 %** | **4,25 %** | **3,25 %** | **1,5 %** |
| 96 kHz | arrondis à l'échantillon | ❌ | 1,75 % | 1,75 % | 1,0 % | ❌ |
| 192 kHz | bande limitée | 4,0 % | 4,25 % | 4,25 % | 4,0 % | 3,25 % |
| 192 kHz | arrondis à l'échantillon | 3,0 % | 3,5 % | 3,5 % | 3,5 % | 3,25 % |

Entre parenthèses : l'amplitude au-dessus du seuil de l'optocoupleur. ❌ = octets faux ou erreur de trame.

Robustesse, fronts à bande limitée, seuil 0,5 :

| fs | Filtre du DAC | Optocoupleur rapide | Extinction +4 µs | Extinction +8 µs |
|---|---|---|---|---|
| 48 kHz | 0,45·fs | 3,75 % | 3,25 % | 1,75 % |
| 48 kHz | 0,40·fs (filtre lent) | 3,0 % | 3,25 % | 1,75 % |
| 96 kHz | 0,45·fs | 4,25 % | 3,75 % | 2,5 % |
| 96 kHz | 0,40·fs (filtre lent) | 4,0 % | 3,75 % | 2,5 % |

Conclusions :
- **≥ 96 kHz et fronts à bande limitée** : ça marche si l'amplitude vaut de 1,25 à 5 fois le seuil. Cela laisse **une plage de volume d'environ 12 dB**, facile à viser.
- **44,1 ou 48 kHz** : seulement de 1,5 à 3 fois le seuil (**plage d'environ 5 dB**). Il faut calibrer.
- **Fronts arrondis à l'échantillon** : échec total à 44,1 et 48 kHz, fragile à 96 kHz.

### 3.5 Contrainte n° 3 : condensateurs de liaison et polarité

- Beaucoup de sorties casque passent par des condensateurs de liaison (100 à 470 µF).
  Si les bits à 0 ont toujours la même polarité, chacun charge ces condensateurs : ~1,5 mV par bit à 5 mA, pour 2 × 220 µF en série.
  Cela donne **environ 1 V de dérive sur un seul paquet de 128 octets** (~5,5 bits à 0 par octet). Le signal s'effondrerait, et le pont d'entrée finirait par conduire en sens inverse.
- **Parade** : l'entrée du M:C étant bidirectionnelle, on alterne la polarité des 0 **octet par octet**.
  - On ne bascule que si la charge cumulée dépasse ~16 bits, et on ajoute alors 1 bit de repos pour garder au moins 2 bits de repos entre deux polarités.
  - En simulation, la charge reste ≤ 25 bits (≈ 40 mV) et la marge est inchangée.
  - Les bits ajoutés sont absorbés par la cadence de 1,4.
- Une sortie sans condensateur (courant sur Mac et téléphones) pourrait s'en passer, mais ce schéma marche partout.

### 3.6 Contrainte n° 4 : la chaîne audio du système

- La lecture doit être **fidèle au bit près** :
  - aucun égaliseur, « amélioration audio », normalisation ni audio spatial ;
  - volume système fixe ;
  - **aucun son système** pendant les 7 minutes (mode Ne pas déranger).
- **macOS** : Configuration audio et MIDI → sortie intégrée à **96 000 Hz**.
- **Windows** : désactiver les améliorations, format par défaut 24 bits / 96 kHz, mode exclusif si le lecteur le permet.
- **Linux** : `aplay -D hw:X,Y`, sans PulseAudio ni PipeWire.
- Pas de Bluetooth. Un dongle USB-C → jack convient s'il accepte 96 kHz.
- Taille : ~7 minutes de flash ≈ 160 Mo en WAV 96 kHz, 16 bits, stéréo.

### 3.7 Risques pour la machine

- Un bit faux fausse la checksum du paquet : l'image est rejetée, ou le M:C reste bloqué sur `RECEIVING...` comme pour un paquet perdu.
  C'est sans danger : on éteint et on recommence ([06 §2](06-flash-et-recuperation.md#2-flasher)).
- **Mais la checksum de paquet ne fait que 7 bits** ([02 §2](02-format-os-syx.md#2-transport-sysex-moderne)) : un paquet corrompu passe dans 1 cas sur 128.
  - **`[HYP]`** L'image porte aussi une somme de contenu sur 32 bits et un HMAC-SHA256. Le bootloader les vérifie sans doute avant d'écrire, mais ce n'est **pas vérifié** dans le code du bootstrap.
  - Un MAIN OS corrompu reste récupérable par le menu de démarrage, que la mise à jour n'écrit pas.
  - Le seul scénario grave serait un octet corrompu passé inaperçu dans la section *bootstrap* de l'image, que la machine peut recopier au redémarrage ([FLASH §4](../FLASH.md#4-la-séquence-de-flash-écran-par-écran)).
    Ce risque existe aussi avec une interface MIDI, mais il croît avec le taux d'erreur du lien.
- D'où la **répétition obligatoire avec l'OS officiel** avant le mod.

### 3.8 Protocole de validation proposé

1. **Test sans risque, OS normal, hors enregistrement.**
   - Jouer un WAV de notes MIDI (sur les 16 canaux) à niveaux croissants, en trois variantes : polarité +, polarité −, bipolaire.
   - Le premier palier où le M:C joue donne le seuil, et confirme au passage que l'entrée est bidirectionnelle.
   - Pour flasher, viser environ 2 fois ce seuil (+6 dB). À 96 kHz, on tolère de +2 à +14 dB ; à 48 kHz, seulement de +4 à +9 dB.
2. **Répétition** : flasher l'**OS officiel 1.13** en WAV. Si `UPDATING FLASH` s'affiche puis que la machine redémarre, le lien est validé.
3. **Flash du mod** en WAV, avec exactement les mêmes réglages.

### 3.9 L'outil : `tools/syx2wav.py` — **écrit** `[FAIT]` (15/10)

```bash
python3 tools/syx2wav.py model-cycles_OS1.13.syx --out recovery.wav --rate 96000
```

Ce que le script fait, exactement comme spécifié ci-dessus :

- il **vérifie le `.syx`** avec `mtlib.syx.unwrap` (comme `flash.py`, mais sans `mido`) ;
- il découpe les messages F0..F7 (même découpage que `flash.py`) ;
- il produit des trames **8N1 à 31 250 bauds**, avec la même **cadence `--pace`** que `flash.py`
  (défaut 1,4 ; 2,0 si la machine se fige) ;
- les fronts sont **à bande limitée** : rendu sur une grille fine de 3,072 MHz, filtre
  anti-repliement à 0,45·fs, puis décimation (facteurs 16 / 32 / 64 pour 192 / 96 / 48 kHz) ;
- il **alterne la polarité** des zéros, octet par octet, au-delà de 16 bits de charge cumulée,
  avec un bit de repos à chaque bascule (§3.5) ;
- gauche et droite sont en **opposition de phase**, `--level` en dBFS, crête ≤ −1 dBFS par défaut ;
- il **s'auto-vérifie** : il décode le WAV qu'il vient d'écrire (seuil + UART 16×, vote
  majoritaire) et le compare **octet par octet** au `.syx`. **S'il ne se décode pas, il n'écrit
  rien.** Il affiche aussi la **plage de seuil** pour laquelle le premier message tient : c'est
  le repère de calibrage du volume (viser environ 2× le seuil, §3.8).

Taille : ~7 minutes ≈ **160 Mo** en 96 kHz, 16 bits, stéréo.

**Ce qui reste `[HYP]`** : le niveau de la sortie casque face au seuil de l'optocoupleur — c'est
l'inconnue du §3.3, et **seul un essai sur la machine tranche**. Le script garantit le *signal*,
pas l'*électricité*.

**Note pour la récupération** : ce chemin est le seul qui ne demande **aucune interface MIDI**.
Il vaut donc la peine d'être tenté quand une machine est bloquée et qu'on n'a pas d'interface —
en gardant en tête le risque du §3.7 (un octet corrompu passé inaperçu dans la section
*bootstrap*), qui croît avec le taux d'erreur du lien.

## 4. Pour mémoire : l'USB

- **Menu de démarrage** : non (manuel §13.4).
- **OS en marche, `CONFIG → UPGRADE`** (§12.6) avec Transfer : c'est la mise à jour « normale ».
  - **`[HYP]`** Une image modifiée et re-signée devrait passer comme une officielle, mais personne ne l'a documenté avec le mod.
  - Cela ne vaut que pour le **premier** flash : tant que le mod est installé, l'upgrade USB ne marche plus ([01 §3](01-ms-multi-output.md#3-principe-technique-résumé-du-readme-fait)). Le retour à l'OS officiel repasse donc par le MIDI IN.
- **Piste durable** ([08 §E](08-feuille-de-route.md#e-récupérer-lupgrade-usb-et-le-full-speed)) : loger les stubs dans les caves `0xff` ([09 §4bis](09-analyse-firmware-1.13.md#4bis-caves-de-code-libres-0xff--ressource-pour-toutes-les-extensions)).
  Le mod ne **casserait plus l'upgrade USB** : toutes les mises à jour passeraient par USB, et le MIDI IN ne servirait plus qu'en secours.
  C'est fait dans la variante `6ch-usbup`, qui reste à tester sur matériel ([13](13-6ch-upgrade-usb.md)).

## 5. Recommandation

1. **Sans l'adaptateur DIN, dès maintenant et sans risque** : une interface à **sortie MIDI TRS** et un **câble jack stéréo 3,5 mm** (option A).
   C'est exactement le « simple câble jack stéréo », et le M:C accepte les deux types de brochage.
2. **Sans aucune interface** : la sortie casque (option B) est plausible mais **expérimentale**. Il faut l'outil du §3.9.
   L'étape 1 du §3.8, sans risque, dit en une minute si la sortie casque est assez forte.
3. Dans tous les cas, faire une **répétition avec l'OS officiel** par le même chemin, avant le mod.

## Sources

Consultées le 25/09/2026. Plusieurs sites (Elektron, ManualsLib, CME, Retrokits) étaient inaccessibles depuis l'environnement de travail : leur contenu a été relevé dans les extraits du moteur de recherche.

- Elektron, base de connaissances, [Connectors and signals](https://support.elektron.se/support/solutions/articles/43000601004-connectors-and-signals) : jacks TRS, « MIDI IN port accepts any configuration », `OUT POL`, kit CA-3.
- Elektron, [page de support du Model:Cycles](https://www.elektron.se/support-downloads/modelcycles) et manuel ([pages 46-47 sur ManualsLib](https://www.manualslib.com/manual/1790470/Elektron-Cycles.html?page=47)) ; Sweetwater, [How to Update the Firmware on an Elektron Model:Cycles](https://www.sweetwater.com/sweetcare/articles/how-to-update-the-firmware-on-an-elektron-modelcycles/).
- [Elektron CA-3 MIDI Adapter, Type A](https://www.controlvoltage.net/elektron-ca-3-35-mm-to-5-pin-din-midi-adaptor-pair.html).
- Retrokits RK-006 : [test Sound On Sound](https://www.soundonsound.com/reviews/retrokits-rk-006), [Perfect Circuit](https://www.perfectcircuit.com/retrokits-rk-006.html), [retrokits.com](https://retrokits.com/rk006/).
- SnapBeat, [USB-MIDI (TRS) Interface](https://snapbeat.net/usb-midi-trs-interface/) ([Elecrow](https://www.elecrow.com/usb-midi-trs-interface.html)).
- CME, [H12MIDI Pro](https://www.cme-pro.com/h12midi-pro/).
- Apple, [Use high-impedance headphones with your Mac](https://support.apple.com/en-us/108351) : 1,25 Vrms sous 150 Ω, 3 Vrms de 150 Ω à 1 kΩ.
- MMA/AMEI, [MIDI 1.0 Electrical Specification Update (CA-033)](https://www.midi.org/wp-content/uploads/wpforo/default_attachments/1709416667-ca33-MIDI-10-Electrical-Specification-Update.pdf) ; Hackaday, [Optocouplers: Defending Your Microcontroller, MIDI…](https://hackaday.com/2018/05/09/optocouplers-defending-your-microcontroller-midi-and-a-hot-tip-for-speed/).

## Annexe : script de simulation

Reproduit les tableaux du §3.4 en ~40 s (Python 3.9+, `numpy`) :
`PYTHONPATH=tools python3 sim_audio_midi.py`, avec le script ci-dessous copié à la racine du dépôt.

```python
"""MIDI 31250 bauds synthétisé en audio -> opto (seuil) -> UART : le flux se décode-t-il ?

Signal idéal : repos = 0, bit à 0 = ±1 (polarité par octet, basculée seulement si la
charge cumulée dépasse D bits, avec 1 bit de repos en plus), filtré passe-bas
(= synthèse à bande limitée + DAC idéal), ou échantillonné tel quel (fronts arrondis)
puis filtré par le DAC. Opto passant si |v| > seuil. UART 16x, vote à 3 au centre,
bit de stop contrôlé. Marge = erreur d'horloge max tolérée (%) ; signal parfait : ±4,25 %.
"""
import numpy as np
from mtlib.syx import wrap, BYTES_PER_MSG

BAUD, FINE = 31250.0, 3.072e6
T = 1 / BAUD


def messages(n=12, seed=1):
    body = bytes(np.random.default_rng(seed).integers(0, 256, n * BYTES_PER_MSG, dtype=np.uint8))
    raw, out, i = wrap(body, 0x11), [], 0
    while (a := raw.find(0xF0, i)) >= 0:
        b = raw.find(0xF7, a)
        out.append(raw[a:b + 1])
        i = b + 1
    return out


def timeline(msgs, pace=1.4, D=16):
    """-> (instants de début de bit, niveaux idéaux, durée totale)"""
    t, disp, pol, ts, lv = 20e-3, 0, 1, [], []
    for m in msgs:
        t0 = t
        for byte in m:
            frame = [0] + [(byte >> k) & 1 for k in range(8)] + [1]
            want = -1 if disp > 0 else 1
            if want != pol and abs(disp) > D:
                pol, t = want, t + T          # bascule : 1 bit de repos en plus
            for bit in frame:
                ts.append(t)
                lv.append(0.0 if bit else float(pol))
                t += T
            disp += pol * frame.count(0)
        t = max(t, t0 + pace * len(m) * 10 * T)
    return np.array(ts), np.array(lv), t + 20e-3


def lowpass(fc, rate, zc=12):
    half = int(np.ceil(zc * rate / (2 * fc)))
    k = np.arange(-half, half + 1) / rate
    h = np.sinc(2 * fc * k) * np.blackman(len(k))
    return h / h.sum()


def convolve(x, h):
    n = len(x) + len(h) - 1
    N = 1 << (n - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(h, N), N)
    o = (len(h) - 1) // 2
    return y[o:o + len(x)]


def analog(ts, lv, total, fs, cutoff=0.45, naive=False):
    """tension pointe-bague normalisée, sur une grille fine"""
    if naive:                                  # fronts arrondis à l'échantillon
        tg = np.arange(int(total * fs)) / fs
        L = int(round(FINE / fs))
    else:                                      # synthèse à bande limitée
        tg, L = np.arange(int(total * FINE)) / FINE, 1
    idx = np.clip(np.searchsorted(ts, tg, side="right") - 1, 0, len(ts) - 1)
    x = np.where((tg >= ts[0]) & (tg < ts[-1] + T), lv[idx], 0.0)
    if naive:                                  # échantillons -> DAC (sur-échantillonnage)
        up = np.zeros(len(x) * L)
        up[::L] = x * L
        x = up
    rate = fs * L if naive else FINE
    return np.arange(len(x)) / rate, convolve(x, lowpass(cutoff * fs, rate))


def uart(tg, space, eps=0.0, phase=0.3):
    rate = 1 / (tg[1] - tg[0])
    tick = 1 / (16 * BAUD * (1 + eps))
    k = ((phase + np.arange(int(tg[-1] / tick) - 1)) * tick * rate).astype(np.int64)
    s = space[np.minimum(k, len(space) - 1)]
    maj = np.zeros(len(s), bool)
    maj[1:-1] = (s[:-2].astype(int) + s[1:-1] + s[2:]) >= 2
    out, bad, nxt = [], 0, 0
    for i in np.flatnonzero(s[1:] & ~s[:-1]) + 1:
        if i < nxt or i >= len(s) - 180:
            continue
        b = maj[i + 8 + 16 * np.arange(10)]
        if not b[0]:
            continue                           # faux départ
        out.append(sum(1 << j for j in range(8) if not b[1 + j]))
        bad += int(b[9])                       # erreur de trame
        nxt = i + 152
    return bytes(out), bad


def margin(tg, space, ref):
    best = []
    for sign in (1, -1):
        ok = 0.0
        for e in np.arange(0, 8.01, 0.25):
            if any(uart(tg, space, sign * e / 100, ph) != (ref, 0) for ph in (0.1, 0.5, 0.9)):
                break
            ok = e
        best.append(ok)
    return min(best)


def slow_off(space, us):
    """l'opto reste passant 'us' µs de plus après chaque extinction"""
    n = int(us * 1e-6 * FINE)
    if n == 0:
        return space
    return np.convolve(space.astype(np.int32), np.ones(n + 1, np.int32))[:len(space)] > 0


if __name__ == "__main__":
    msgs = messages()
    ref = b"".join(msgs)
    ts, lv, total = timeline(msgs)
    print(f"{len(ref)} octets, {total:.2f} s, charge max {np.max(np.abs(np.cumsum(lv))):.0f} bits")
    seuils = (0.2, 0.35, 0.5, 0.65, 0.8)
    print("fs      fronts           seuil: " + "  ".join(f"{s:>5}" for s in seuils))
    for fs in (44100, 48000, 96000, 192000):
        for naive in (False, True):
            tg, v = analog(ts, lv, total, fs, naive=naive)
            row = []
            for s in seuils:
                sp = np.abs(v) > s
                row.append(f"{margin(tg, sp, ref):4.2f}%" if uart(tg, sp) == (ref, 0) else " ÉCHEC")
            print(f"{fs:6d}  {'arrondis' if naive else 'bande limitée':14s}        " + "  ".join(row))
    print("robustesse (bande limitée, seuil 0,5) :")
    for fs in (48000, 96000):
        for cut in (0.45, 0.40):
            tg, v = analog(ts, lv, total, fs, cutoff=cut)
            sp = np.abs(v) > 0.5
            row = [f"{cut:.2f}·fs"]
            for us in (0, 4, 8):
                d = slow_off(sp, us)
                row.append(f"extinction +{us}µs: "
                           + (f"{margin(tg, d, ref):4.2f}%" if uart(tg, d) == (ref, 0) else "ÉCHEC"))
            print(f"  {fs:6d}  filtre " + "   ".join(row))
```
