# 21 · Architecture matérielle du Model:Cycles (photos du PCB)

Analyse du 30/09/2026, d'après **11 photos du PCB** prises par l'utilisateur sur son propre Model:Cycles ouvert (dessus et dessous de la carte).
Les conventions `[FAIT]` / `[HYP]` / `[À FAIRE]` sont celles de l'[index](README.md).

> **Méthode et limites**
> - **`[FAIT]`** ici = marquage **lu sur une photo**, ou donnée d'une fiche technique, ou comptage fait par un outil du dépôt.
> - **`[HYP]`** = ce que j'en déduis. **Aucune piste n'a été suivie au multimètre** : tout ce qui dit « telle puce est reliée à telle broche » est une hypothèse, sauf quand la nature des puces l'impose (une DDR2 ne peut aller que sur le contrôleur DDR).
> - Les photos font 1506 × 2000 px : les petits boîtiers (SOT-23, QFN, WLCSP) sont **illisibles**. Ils sont listés comme tels au [§12](#12-inconnues-et-photos-utiles).
> - Chaque information a sa source juste en dessous : la photo, la fiche technique, ou l'outil.

## Photos

| n° | Fichier | Ce qu'on y voit |
|---|---|---|
| 1 | [01-dessus-vue-ensemble.jpg][P1] | Dessus de la carte entière |
| 2 | [02-u25-flash-spi.jpg][P2] | U25 (flash SPI) |
| 3 | [03-u3-ddr2.jpg][P3] | U3 (DDR2) |
| 4 | [04-u14-phy-usb-quartz.jpg][P4] | U14 (PHY USB), quartz Y1 et Y3 |
| 5 | [05-u20-alimentation.jpg][P5] | U20 (convertisseur), U13 |
| 6 | [06-verrous-hc373-encodeurs.jpg][P6] | Verrous U5, U7, U9, U28, encodeurs |
| 7 | [07-touches-hc238-sortie-audio.jpg][P7] | Touches, U12 et U16 (décodeurs), U18 (sortie audio), marquages du circuit imprimé |
| 8 | [08-coeur-numerique.jpg][P8] | U1 (CPU), U26 (eMMC), U3, U25, USB |
| 9 | [09-coeur-numerique-bis.jpg][P9] | Même zone, autre éclairage |
| 10 | [10-touches-verrous.jpg][P10] | Touches S5 à S14, verrous U4, U15, U8, U23 |
| 11 | [11-dessous-points-de-test.jpg][P11] | Dessous de la carte, encore vissée dans la coque |

Orientation de la photo 1 : **l'arrière de la machine est à droite**, son côté gauche est en haut.

---

## 0. En bref

| Fonction | Repère | Composant | Certitude |
|---|---|---|---|
| Processeur | U1 | NXP **MCF54415CMJ250** (ColdFire V4, 250 MHz, 256 billes) | `[FAIT]` |
| RAM | U3 | Nanya **NT5TU128M8HE-AC**, DDR2 1 Gbit = **128 Mo**, bus 8 bits | `[FAIT]` (2ᵉ ligne du marquage lue en partie) |
| Flash de démarrage | U25 | cFeon (Eon) **EN25QH16B-104HIP**, flash SPI 16 Mbit = **2 Mo** | `[FAIT]` (lecture probable du « 16 ») |
| Stockage de masse | U26 | Samsung **KLM4G1FETE-B041**, eMMC 5.1 de **4 Go** | `[FAIT]` |
| PHY USB | U14 | SMSC (Microchip) **USB3300-EZK**, High Speed, interface ULPI | `[FAIT]` |
| Quartz | Y1 / Y3 | **24,000 MHz** (USB) / **24,576 MHz** (= 512 × 48 kHz) | `[FAIT]` |
| Sortie ligne | U18 | TI **DRV632**, driver de ligne stéréo 2 Vrms | `[FAIT]` |
| Convertisseur N/A | U17 ou U21 | non identifié | `[À FAIRE]` |
| Entrée MIDI | U22, U2 | 2 × optocoupleur **H11L1** | `[FAIT]` |
| Touches, LED | U4 à U11, U15, U23, U28 / U12, U16 | 11 × **74HC373** (verrous 8 bits) / 2 × **74HC238** (décodeurs 3 vers 8) | `[FAIT]` |
| Alimentation | U20 | convertisseur à découpage TI, marquage « QUJ », non identifié | `[À FAIRE]` |
| Carte | | **PCBA4201D**, © 2018 Elektron : conçue avant le Model:Cycles | `[FAIT]` |

Ce que ça change pour le projet : voir le [§11](#11-ce-que-ça-change-pour-le-projet).

## 1. Synoptique

```text
                       +--------------------+
U3  DDR2 128 Mo =======|                    |==== ULPI ==== U14 USB3300 ==== J5 micro-USB
    bus DDR2 8 bits    |                    |               (Y1 24,000 MHz)
U25 flash SPI 2 Mo ====|                    |.... SSI ..... CNA (U17 ou U21 ?) ... U18 DRV632 ... MAIN OUT
    SPI (DSPI0)        |  U1                |                                  ... ampli ? ... HEADPHONES
U26 eMMC 4 Go =========|  MCF54415CMJ250    |.... UART9 ... U22 + U2 (H11L1) ... MIDI IN
    eSDHC              |  ColdFire V4       |           ... MIDI OUT/THRU
Y3  24,576 MHz ........|  250 MHz           |.... bus 8 bits ... 11 x 74HC373, 2 x 74HC238
                       |                    |                ... LED, touches, encodeurs
                       |                    |.... ADC ? ... 6 pads
                       |                    |.... SPI ? ... écran LCD
                       +--------------------+

====  liaison imposée par la nature des puces          ....  hypothèse
```

## 2. La carte

- **`[FAIT]`** Référence **`PCBA4201D`**, imprimée en haut à gauche et le long du bord gauche. Mention « ©2018 Elektron Music Machines MAV AB ».
  - Source : [photo 1][P1].
- **`[HYP]`** La carte date de **2018**, avant la sortie du Model:Cycles : elle a été dessinée pour le Model:Samples, et le Model:Cycles la reprend.
  - Cela expliquerait que l'OS de l'un démarre sur l'autre ([15 §3](15-demandes-reddit.md)), et que les deux OS aient le même bootstrap et la même initialisation de la RAM.
  - Source : date du copyright sur la [photo 1][P1] ; je n'ai pas de photo d'un Model:Samples pour comparer la référence de sa carte.
- **`[FAIT]`** Marquages de fabrication : symbole « sans plomb », « 3620 1 », « 94V-0 », « BM1 », « E213371 ».
  - **`[HYP]`** « 3620 » est un code date (semaine 36 de 2020), « 94V-0 » et « E213371 » sont la classe de tenue au feu et le numéro de dossier UL du fabricant du circuit.
  - Source : [photo 7][P7], [photo 1][P1].
- **`[FAIT]`** Marquages de lot des puces : flash SPI « 2102 », DDR2 « 2102 », eMMC « SEC 104 », CPU « CTDK2129G ».
  - **`[HYP]`** Ce sont des codes date (année, semaine) : cette machine aurait été assemblée après la mi-2021 (semaine 29 de 2021 pour le CPU).
  - Source : [photo 2][P2], [photo 3][P3], [photo 8][P8].
- **`[FAIT]`** Il y a **deux circuits** : la carte principale, et une **carte connecteurs** le long de l'arrière (jacks audio, jacks MIDI, prise batterie).
  - La carte connecteurs porte les mêmes marquages « 3620 1 », « 94V-0 », « BM1 ». Des restes d'attaches sécables se voient sur les bords des deux cartes.
  - Les deux sont reliées par une **nappe souple soudée** d'une vingtaine de conducteurs, avec une ferrite ou une résistance par ligne (L10 à L13, L19, L21, L22, R94, R97, R102, R105…).
  - **`[HYP]`** Les deux cartes sortent du même panneau et sont séparées au montage.
  - Source : [photo 1][P1] (nappe dorée au-dessus des jacks MIDI), [photo 4][P4] et [photo 8][P8] (attaches sur le bord droit), [photo 11][P11] (les deux circuits vus de dessous).
- **`[FAIT]`** Les composants sont **tous sur le dessus**. Le dessous ne porte que des points de test.
  - Source : [photo 11][P11].

### Connecteurs

Ordre officiel à l'arrière : DC IN, USB, MIDI OUT/THRU, MIDI IN, MAIN OUT R/L, HEADPHONES. Sur le côté : BATTERY DC In.
- Source : manuel du Model:Cycles, « Rear connectors » et « Side connector » ([page 12 sur ManualsLib][MANUEL]).

| Connecteur | Où, sur la [photo 1][P1] | Carte |
|---|---|---|
| DC IN | en bas à droite, à côté du gros condensateur 220 µF | principale |
| USB (J5, micro-B) | juste au-dessus | principale |
| MIDI OUT/THRU, MIDI IN (jacks 3,5 mm) | à droite des deux optocoupleurs blancs | connecteurs |
| MAIN OUT R/L, HEADPHONES (3 jacks 6,35 mm) | à droite de l'écran | connecteurs |
| BATTERY DC In | tout en haut à droite, avec le fusible F1 | connecteurs |

- **`[HYP]`** L'attribution de chaque prise suit l'ordre du manuel ; je ne l'ai pas vérifiée sur la coque.
- **`[FAIT]`** La machine s'allume en maintenant MAIN VOLUME.
  - **`[HYP]`** Il n'y a donc pas d'interrupteur mécanique (je n'en vois pas sur la carte) : l'appui de cet encodeur commande un circuit de maintien de l'alimentation, et c'est le logiciel qui coupe. Cela colle avec « l'état n'est sauvegardé qu'à l'extinction par le bouton » ([dossier §7](00-dossier-technique.md#7-firmware-stockage-et-mises-à-jour)).
  - Source : manuel, page 12 : « Press and hold MAIN VOLUME for a second to switch on the Model:Cycles » ([ManualsLib][MANUEL]).

## 3. Cœur numérique

### 3.1 Processeur : U1

- **`[FAIT]`** Marquage : logo Freescale, « COLDFIRE », « **MCF54415CMJ250** », « 0N51E », « CTDK2129G ».
  - Source : [photo 8][P8], [photo 9][P9].
- **`[FAIT]`** C'est le MCF54415 en boîtier 256 MAPBGA, 250 MHz, −40 à +85 °C. Cela répond au `[À FAIRE]` de [03 §1](03-plateforme-coldfire.md#1-processeur) et au 1ᵉʳ point du [dossier §11](00-dossier-technique.md#11-points-à-vérifier-hors-du-fil).
  - Source : *MCF5441x ColdFire Microprocessor Data Sheet*, table 2 « Orderable part numbers » ([NXP][DS-MCF]).
- **`[FAIT]`** Ce que contient cette puce, et qui sert ici :

| Bloc | Rôle probable dans le Model:Cycles |
|---|---|
| Cœur ColdFire V4 avec EMAC et MMU, 385 MIPS à 250 MHz | tout le DSP ([03 §1](03-plateforme-coldfire.md#1-processeur)) |
| 64 Ko de SRAM interne | la « RAM rapide » en `0x80000000` ([03 §2](03-plateforme-coldfire.md#2-carte-mémoire-connue-os-113-cycles)) |
| Contrôleur SDRAM pour **un seul boîtier DDR2 en 8 bits** | U3 |
| Démarrage depuis une flash SPI (*serial boot*) | U25 |
| eSDHC (SD, MMC) | U26 |
| USB host/device/OTG avec port **ULPI** pour PHY High Speed externe | U14 |
| 2 × SSI (liaison audio série) | convertisseur N/A |
| 10 UART, 4 DSPI, 6 I2C | MIDI, flash SPI, écran |
| 2 × ADC 12 bits | pads sensibles à la vélocité ? |
| BDM et JTAG | port de debug ([§9](#9-test-et-debug)) |

  - Source : fiche technique, liste de la page 1 et table 1 « MCF5441x family configurations » ([NXP][DS-MCF]) ; fiche produit ([NXP][FS-MCF]).
- **`[FAIT]`** Le MCF54415 n'a **ni accélérateur cryptographique (CAU) ni commutateur Ethernet** : seuls des modèles au-dessus (MCF54416 à MCF54418) en ont.
  - Le HMAC-SHA256 de l'image ([09 §2](09-analyse-firmware-1.13.md#2-structure-du-conteneur-ele3-vérifié)) est donc calculé en logiciel.
  - Source : fiche technique, table 1 ([NXP][DS-MCF]).
- **`[FAIT]`** Tensions demandées par la puce : cœur 1,2 V (IVDD), entrées-sorties 3,3 V (EVDD), bus mémoire 1,8 V en DDR2 (SDVDD).
  - Source : fiche technique, §2.2 et table des caractéristiques ([NXP][DS-MCF]).

### 3.2 RAM : U3

- **`[FAIT]`** Marquage : logo NANYA, « 2102 », puis une ligne que je lis « NT5TU128M8HE-AC », puis « …M0EL 3 TW ».
  - La 2ᵉ ligne est peu contrastée. « TU128M8HE-AC » se lit sur la photo 5, le début « NT5 » sur la photo 3.
  - Source : [photo 3][P3], [photo 5][P5] (en haut à gauche, tournée).
- **`[FAIT]`** NT5TU128M8HE-AC = DDR2 de 1 Gbit, organisée en 128 M × 8 bits, 1,8 V, boîtier BGA 60 billes. Soit **128 Mo**.
  - Source : fiche Nanya « 1Gb DDR2 SDRAM NT5TU128M8HE / NT5TU64M16HG » ([alldatasheet][DS-NANYA]).
- **`[FAIT]`** La forme concorde : le MCF5441x ne sait piloter qu'**un boîtier DDR2 en 8 bits**, et c'est ce qui est monté.
  - Source : fiche technique du CPU, page 1 : « SDRAM controller supporting full-speed operation from a single x8 DDR2 component » ([NXP][DS-MCF]).
- **`[HYP]`** La RAM irait donc de `0x40000000` à `0x47FFFFFF`. Le MAIN OS est chargé en `0x40000400`, et nos moteurs du Syntakt en `0x43000000` ([17](17-portage-exact-syntakt.md)) : les deux sont dedans.
  - **`[À FAIRE]`** Lire dans le bootstrap la taille déclarée au contrôleur DDR, pour confirmer que les 128 Mo sont bien tous utilisés.
  - Source : plage SDRAM `0x4000_0000`–`0x7FFF_FFFF` dans le *MCF5441x Reference Manual*, §1.8 ([NXP][RM-MCF]).

### 3.3 Flash de démarrage : U25

- **`[FAIT]`** Marquage : « cFeon », « QH16B-104HIP », « X015E11 », « 2102HLA ». Boîtier SOIC 8 broches.
  - Le « 16 » est une lecture probable, pas certaine.
  - Source : [photo 2][P2], [photo 9][P9].
- **`[FAIT]`** EN25QH16 = flash série (SPI) de 16 Mbit, soit **2 Mo**, secteurs de 4 Ko, 2,7 à 3,6 V.
  - Source : fiche Eon « EN25QH16, 16 Megabit Serial Flash Memory with 4Kbyte Uniform Sector » ([alldatasheet][DS-EON]). Je n'ai pas ouvert la fiche de la variante « B ».
- **`[FAIT]`** U25 est collée au CPU, reliée par deux réseaux de résistances RN14 et RN15 marqués « 220 » (22 Ω).
  - Source : [photo 2][P2].
- **`[HYP]`, forte** C'est elle qui contient le **bootstrap et l'OS** (pas l'eMMC). Voir le recoupement avec le firmware au [§10](#10-recoupement-avec-le-firmware).

### 3.4 Stockage de masse : U26

- **`[FAIT]`** Marquage : « SEC 104 », « B041 », « KLM4G1FETE », puis une ligne de lot. Boîtier BGA, avec un code Data Matrix.
  - Source : [photo 8][P8], [photo 9][P9].
- **`[FAIT]`** KLM4G1FETE-B041 = eMMC 5.1 de **4 Go**, boîtier FBGA 153 billes.
  - Source : fiche produit ([Samsung][DS-SAMSUNG]).
- **`[HYP]`** C'est le « +Drive » : projets, presets, réglages. Seul le MAIN OS y accède ([§10](#10-recoupement-avec-le-firmware)).

### 3.5 Horloges : Y1 et Y3

- **`[FAIT]`** Y3 : « FOX 24.576 », tout près du CPU. Y1 : « FOX 24.000 », à côté de U14.
  - Source : [photo 4][P4].
- **`[FAIT]`** 24,576 MHz = 512 × 48 000 Hz : c'est une fréquence d'horloge audio. Elle entre dans la plage acceptée par l'oscillateur du CPU (14 à 50 MHz).
  - Source : calcul ; fiche technique du CPU, caractéristiques de l'oscillateur ([NXP][DS-MCF]).
- **`[HYP]`** Y3 est le quartz du CPU. Tout le système, audio compris, dérive alors d'une horloge multiple de 48 kHz, et le cœur tourne à un multiple simple de 24,576 MHz (245,76 MHz pour ×10), un peu sous les 250 MHz annoncés.
  - **`[À FAIRE]`** Le multiplicateur de la PLL n'est pas écrit par le bootstrap. Il vient du mot de configuration lu dans la flash au démarrage série : il faudrait une copie de U25 pour le connaître.
  - Source : dans le bootstrap, les seules adresses de la PLL sont `PLL_DR` (il n'y change que le champ `OUTDIV3`, le diviseur de l'horloge eSDHC) et `PLL_SR` ; *Reference Manual*, §8.2.1, note de `PLL_CR` : « If serial boot, REFDIV = {0,SBF_RCON[23:22]} and FBKDIV = SBF_RCON[21:16] » ([NXP][RM-MCF]).
- **`[FAIT]`** 24 MHz est la fréquence que demande le PHY USB3300.
  - Source : fiche USB3300, « Integrated 24MHz Crystal Oscillator » ([Microchip][DS-USB3300]).
- **`[HYP]`** L'horloge audio (Y3) et l'horloge USB (Y1) sont donc deux quartz indépendants.

## 4. USB

- **`[FAIT]`** U14 : boîtier QFN 32 broches, marquage « SMSC », « 3300-EZK ».
  - Source : [photo 4][P4].
- **`[FAIT]`** USB3300 = PHY USB **High Speed**, interface ULPI vers le contrôleur, QFN 32, −40 à +85 °C.
  - Source : fiche USB3300 ([Microchip][DS-USB3300]).
- **`[FAIT]`** Cela répond au 2ᵉ point du [dossier §11](00-dossier-technique.md#11-points-à-vérifier-hors-du-fil) : le port USB est matériellement **High Speed** (480 Mbit/s). C'est ce qu'exploite le mod 6 canaux ([04](04-usb-audio.md)).
- **`[FAIT]`** Entre U14 et le CPU : réseaux de résistances RN2, RN3, RN20 marqués « 220 » (22 Ω en série sur les lignes ULPI).
  - Source : [photo 4][P4].
- **`[FAIT]`** Côté prise J5 : L2 (boîtier à 4 plots, probablement une self de mode commun), U19 (petit boîtier 6 broches), L1, L3.
  - **`[HYP]`** U19 est une protection contre les décharges électrostatiques.
  - Source : [photo 8][P8], [photo 9][P9].

## 5. Audio

- **`[FAIT]`** U18 : « DRV632 », logo TI, TSSOP 14 broches. À côté, quatre condensateurs chimiques 10 µF / 16 V (C17, C20, C24, C27).
  - Source : [photo 7][P7] (en haut à droite), [photo 1][P1].
- **`[FAIT]`** DRV632 = driver de ligne stéréo, **2 Vrms** avec une alimentation 3,3 V, entrées différentielles, sortie centrée sur la masse grâce à une pompe de charge interne (pas de condensateur de liaison en sortie), prévu pour des charges de 600 Ω et plus.
  - Source : fiche DRV632 ([TI][DS-DRV632]).
- **`[HYP]`** U18 attaque les sorties MAIN OUT. Ce n'est pas un ampli casque (un casque fait bien moins de 600 Ω) : la sortie casque a son propre étage.
- **`[FAIT]`** U17 : très petit boîtier à billes, sans marquage lisible, entouré de condensateurs (C31 à C45) et de trois selfs ou ferrites (L5, L6, L7). U21 : boîtier TSSOP à côté des optocoupleurs, marquage illisible.
  - **`[HYP]`** L'un des deux est le convertisseur numérique-analogique, l'autre peut être l'ampli casque.
  - Source : [photo 7][P7], [photo 1][P1].
- **`[FAIT]`** Il n'y a qu'**une chaîne de sortie analogique stéréo** sur la carte (un seul driver de ligne, trois jacks).
  - Conséquence : des sorties séparées par piste ne peuvent passer **que par l'USB**, jamais par les jacks. C'est la voie du projet.
  - Source : [photo 1][P1].

## 6. MIDI

- **`[FAIT]`** U22 et U2 : deux optocoupleurs en boîtier blanc 6 broches, marqués « H11L1 » avec le logo ON Semiconductor, juste derrière les deux jacks MIDI.
  - Source : [photo 1][P1].
- **`[FAIT]`** H11L1 = optocoupleur à sortie logique (trigger de Schmitt, collecteur ouvert), 1 MHz. LED d'entrée : 1,2 V typique, 1,5 V maxi à 10 mA. Courant de déclenchement : **1,6 mA maxi**.
  - Source : fiche H11L1M, H11L2M, H11L3M ([onsemi][DS-H11L1]).
- **`[HYP]`** Il y a **deux** optocoupleurs pour **une** entrée MIDI : leurs LED sont montées tête-bêche, une pour chaque sens du courant. C'est ce qui permet au MIDI IN d'accepter les brochages TRS de type A et de type B.
  - Cela confirme l'hypothèse « deux LED tête-bêche » de [12 §1](12-flash-par-jack-trs.md#1-ce-que-le-bootloader-écoute-vraiment), et écarte le pont de diodes.
  - Conséquence pour la piste « sortie casque » ([12 §3.3](12-flash-par-jack-trs.md#33-contrainte-n-1--le-niveau-de-sortie-linconnue-principale)) : sans pont, le seuil est plus bas que le haut de la fourchette estimée. LED 1,2 à 1,5 V, plus la résistance série × 1,6 mA. La résistance série n'est pas lue.
- **`[HYP]`** L'UART du MIDI est l'**UART9** du CPU : c'est le seul des dix UART que le bootstrap utilise, et le bootstrap n'écoute que le MIDI IN.
  - Source : [§10](#10-recoupement-avec-le-firmware) ; manuel §13.4 ([09 §3](09-analyse-firmware-1.13.md#3-le-menu-de-démarrage-et-lupgrade-manuel-confirme-06)).

## 7. Interface utilisateur

### 7.1 Touches, pads, encodeurs

- **`[FAIT]`** **31 touches**, repérées S1 à S31 : des plages de contact en peigne, à nu sur le circuit, avec une LED au centre. Les 16 touches du séquenceur sont S15 à S30 (colonne de gauche sur la photo 1).
  - **`[HYP]`** Le contact se fait par une pastille conductrice sous le clavier en silicone.
  - Source : [photo 1][P1], [photo 7][P7], [photo 10][P10].
- **`[FAIT]`** **6 pads**, repérés S32 à S37 : plus grands, à quatre quadrants de peignes fins, LED au centre.
  - **`[HYP]`** La vélocité se mesure par la résistance du contact (plus on appuie, plus la surface en contact est grande), lue par l'ADC 12 bits du CPU. Il n'y a pas d'autre convertisseur analogique-numérique visible.
  - Source : [photo 1][P1], [photo 6][P6].
- **`[FAIT]`** **16 encodeurs** à boîtier métallique, repérés EN (EN1 à EN15 lus). Chacun a deux petits boîtiers 3 broches repérés D à côté de ses trois broches (repères entre D86 et D131).
  - **`[HYP]`** Ce sont des doubles diodes : isolation dans une matrice, ou protection contre les décharges. Non tranché.
  - Source : [photo 1][P1], [photo 6][P6], [photo 8][P8].

### 7.2 LED, verrous et décodeurs

- **`[FAIT]`** **11 boîtiers marqués « HC373 »** (TSSOP 20 broches) : U4, U5, U6, U7, U8, U9, U10, U11, U15, U23, U28.
  - 74HC373 = 8 bascules de type verrou, sorties 3 états.
  - Source : [photo 6][P6], [photo 7][P7], [photo 10][P10] ; fiche du 74HC373 ([Nexperia][DS-HC373]).
- **`[FAIT]`** **2 boîtiers marqués « HC238 »** (TSSOP 16 broches) : U12 et U16, côte à côte.
  - 74HC238 = décodeur 3 vers 8, sorties actives à l'état haut.
  - Source : [photo 7][P7] ; fiche du 74HC238 ([Nexperia][DS-HC238]).
- **`[FAIT]`** Sept verrous ont **8 résistances discrètes** autour d'eux (U4 : R22 à R29, U6 : R30 à R37, U8 : R38 à R45, U10 : R46 à R53, U5 : R54 à R61, U7 : R62 à R69, U9 : R70 et suivantes).
  - Quatre autres ont à la place **deux réseaux de résistances et un transistor** marqué « 1BW » (lecture probable) : U11 (RN21, RN22, Q12), U15 (RN4, RN16, Q13), U23 (RN17, RN18, Q15), U28 (RN23, RN24, Q16).
  - Source : [photo 6][P6], [photo 7][P7], [photo 10][P10].
- **`[FAIT]`** Les LED portent les repères D33 à D85 environ, soit 53 : une par touche (31), une par pad (6), le reste en témoins (près des encodeurs, et une colonne de quatre en bas à gauche).
  - Source : [photo 1][P1], [photo 6][P6] (repères relevés par sondage, pas un par un).
- **`[HYP]`** Lecture d'ensemble, à vérifier :
  - le CPU présente un octet sur un **bus de 8 bits** commun à tous les verrous ;
  - les deux 74HC238 (2 × 8 = 16 sorties) choisissent le verrou qui le mémorise ;
  - les sept verrous « à résistances » allument les LED en direct : 7 × 8 = 56 sorties pour environ 53 LED ;
  - les quatre verrous « à réseaux » servent au balayage de la matrice des touches et des encodeurs.
- **`[FAIT]`** Deux autres boîtiers logiques n'ont pas pu être lus : U27 (TSSOP 20) et U34 (TSSOP 14).
  - **`[HYP]`** Ce sont les tampons de lecture de la matrice.
  - Source : [photo 1][P1] (entre les pads et la 1ʳᵉ colonne d'encodeurs).

### 7.3 Écran

- **`[FAIT]`** Module LCD monochrome dans un cadre blanc (rétroéclairage), relié à la carte par une petite nappe souple. Une rangée de huit petits composants passifs est posée juste à côté.
  - Source : [photo 1][P1].
- **`[HYP]`** Le contrôleur est sur le verre, piloté en SPI. La rangée de passifs serait celle des condensateurs de sa pompe de charge. Cela répondrait à la question restée sans réponse sur le forum ([dossier §2.5](00-dossier-technique.md#25-écran--question-restée-sans-réponse)) : SPI, pas I2C.
  - Indice : le bootstrap, qui affiche le menu de démarrage, utilise deux ports SPI (DSPI0 et DSPI1) et aucun des six ports I2C ([§10](#10-recoupement-avec-le-firmware)).

## 8. Alimentation

- **`[FAIT]`** Entrée DC IN sur la carte principale, avec un condensateur chimique 220 µF / 50 V, trois gros condensateurs céramique (C116, C119, C120) et une self L17. L'emplacement **D114 n'est pas monté**.
  - Source : [photo 1][P1], [photo 5][P5], [photo 8][P8].
- **`[FAIT]`** Entrée BATTERY DC In sur la carte connecteurs, avec **F1**, un composant vert marqué « 110 ».
  - **`[HYP]`** F1 est un fusible réarmable.
  - Source : [photo 1][P1] (coin en haut à droite).
- **`[FAIT]`** U20 : boîtier QFN 16 broches de 3 × 3 mm, marquage « QUJ », « TI 04K », « C24S », avec une self L9 et de gros condensateurs (C68, C70 à C74). Emplacements C69, C75 et R129 non montés.
  - **`[HYP]`** C'est le convertisseur à découpage principal (entrée → 3,3 V).
  - **`[À FAIRE]`** L'identifier. Le marquage « QUJ » n'est dans aucune des fiches TI que j'ai parcourues (TPS6213x, TPS6214x, TPS6215x, TPS6216x, TPS6217x, TPS6208x, TPS6209x, TLV62130, TLV62150).
  - Source : [photo 5][P5] ; tables « Part marking » des fiches TI, par exemple [TPS6213x][DS-TPS6213X].
- **`[FAIT]`** Autres régulateurs probables, tous illisibles : U36 (petit module gris entre C168 et C169), U24 et U32 (SOT-23 à 5 broches), U29 et U30 (près de l'audio), U31 (boîtier à languette, en bas).
  - **`[HYP]`** Ils fournissent le 1,2 V du cœur, le 1,8 V de la DDR2 et les tensions de l'audio.
  - Source : [photo 8][P8], [photo 9][P9], [photo 7][P7], [photo 1][P1].

## 9. Test et debug

- **`[FAIT]`** Le dessous de la carte est couvert de **points de test numérotés** (TP1 à TP39x).
  - **`[HYP]`** Ils servent au test en production, sur un lit de pointes.
  - Source : [photo 11][P11].
- **`[FAIT]`** Toujours dessous, près du bord arrière et du CPU : une **grille de 20 pastilles dorées** (4 colonnes de 5, en quinconce), avec des trous de centrage.
  - **`[HYP]`** C'est le connecteur de programmation et de debug d'usine, à pointes à ressort. Le CPU a un port BDM et un port JTAG ; l'un des deux y arrive très probablement.
  - Cette grille est **accessible en retirant seulement le fond** de la machine : sur la photo, la carte est encore vissée dans la coque.
  - Source : [photo 11][P11] (à droite, à mi-hauteur) ; fiche technique du CPU, table 1 ([NXP][DS-MCF]).
- **`[FAIT]`** Sur le dessus, un groupe de six emplacements de résistances sérigraphié « **BOM** », en deux colonnes « 0 » et « 1 » et trois rangées.
  - Montées : R4 et R5 (colonne 0), R3 (colonne 1). Vides : R6, R1, R2. Soit le code **0, 0, 1** de haut en bas.
  - **`[HYP]`** C'est un code de variante à 3 bits, lu par le logiciel sur des broches GPIO. Il peut distinguer un Model:Cycles d'un Model:Samples, ou une révision de nomenclature.
  - **`[À FAIRE]`** Comparer avec la photo d'un Model:Samples, et chercher la lecture de ces trois broches dans le bootstrap et le MAIN OS.
  - Source : [photo 8][P8], [photo 9][P9] (en haut à droite).

## 10. Recoupement avec le firmware

Le nouvel outil `tools/hw_periph_refs.py` compte, dans chaque section de l'OS officiel 1.13, les constantes 32 bits qui tombent dans le bloc de registres d'un périphérique du CPU.

| Périphérique (adresse de base) | bootstrap (26 602 o) | MAIN OS (1 744 192 o) | updater (31 752 o) |
|---|---|---|---|
| Contrôleur DDR (`0xFC0B_8000`) | **45** | 0 | 0 |
| DSPI0, broches du démarrage série (`0xFC05_C000`) | **103** | **299** | **299** |
| DSPI1 (`0xFC03_C000`) | **10** | 11 | 0 |
| UART9 (`0xEC07_4000`) | **20** | 21 | 0 |
| GPIO (`0xEC09_4000`) | **75** | **91** | **29** |
| DAC0 / DAC1 (`0xFC09_8000` / `0xFC09_C000`) | **3** / **3** | 1 / 4 | 0 / 0 |
| USB On-the-Go (`0xFC0B_0000`) | 0 | **128** | **91** |
| eSDHC (`0xFC0C_C000`) | 0 | **72** | 0 |
| eDMA (`0xFC04_4000`) | 0 | **151** | 1 |
| SSI0 (`0xFC0B_C000`) | 0 | 20 | 0 |
| I2C0 (`0xFC05_8000`) | 0 | 48 | 0 |
| ADC (`0xFC09_4000`) | 1 | 8 | 0 |
| I2C1 à I2C5, DSPI2, DSPI3, SSI1, USB hôte | 0 | 0 | 0 |
| *Bruit : 99ᵉ centile / maximum* | *1 / 2* | *7 / 48* | *1 / 2* |

- Source : `python3 tools/hw_periph_refs.py -i model-cycles_OS1.13.syx` ; adresses de base dans le *Reference Manual*, tables 1-3 et 1-4 ([NXP][RM-MCF]).
- **Lecture du tableau.** Le « bruit » est le compte obtenu sur des adresses où aucun registre n'existe. En gras : ce qui dépasse le maximum du bruit, donc sûr. Le reste n'est qu'un indice (le MAIN OS contient beaucoup de tables).
- Le tableau ne garde que les lignes utiles ici ; l'outil affiche tous les blocs (timers, contrôleurs d'interruption, etc.). Les autres UART ne dépassent jamais le bruit.

Ce qu'on en tire :

- **`[FAIT]`** Le **bootstrap initialise la DDR2** et lui seul. Déjà noté en [15 §3](15-demandes-reddit.md) ; ici on voit le matériel correspondant (U3).
- **`[HYP]`, forte** Le **bootstrap et l'OS sont dans la flash SPI U25**, pas dans l'eMMC :
  - le bootstrap, qui charge et décompresse le MAIN OS, utilise DSPI0 et jamais l'eSDHC ;
  - l'updater, qui écrit la nouvelle image, utilise DSPI0 et l'USB, jamais l'eSDHC ;
  - DSPI0 partage ses broches avec le démarrage série du CPU.
  - Source : tableau ci-dessus ; *Reference Manual*, table des signaux « DSPI0/SBF » ([NXP][RM-MCF]).
- **`[FAIT]`** L'**eMMC n'est adressée que par le MAIN OS**. Une eMMC vide ou abîmée n'empêche donc pas le menu de démarrage de fonctionner.
- **`[FAIT]`** Le **bootstrap n'adresse pas l'USB**. C'est la raison matérielle de la règle du manuel : le menu de démarrage ne reçoit que par le MIDI IN ([09 §3](09-analyse-firmware-1.13.md#3-le-menu-de-démarrage-et-lupgrade-manuel-confirme-06)).
- **`[FAIT]`** L'OS Model:Samples 1.13 donne le **même tableau** (mêmes périphériques, comptes à une unité près).
  - Source : `python3 tools/hw_periph_refs.py -i model-samples_OS1.13.syx`.
- **`[HYP]`** Indices plus faibles, dans le MAIN OS seulement : SSI0 pour l'audio, I2C0 pour un composant non identifié (le convertisseur audio ou U13), l'ADC pour les pads.
- **`[HYP]`** Le bootstrap touche aux deux **DAC 12 bits internes** du CPU, juste au-dessus du bruit. Ils ne servent pas à l'audio (12 bits) : peut-être le contraste de l'écran ou une tension de référence.
- Le bloc FlexBus n'est pas dans le tableau : son compte dans le MAIN OS (155) n'est pas fiable, car les valeurs `0xFC00xxxx` y sont très fréquentes comme simples données. Le bootstrap, lui, ne l'adresse jamais, alors qu'il lit des touches et pilote l'écran.
  - **`[HYP]`** Les verrous 74HC373 sont donc pilotés par des broches GPIO plutôt que par le bus externe FlexBus.

## 11. Ce que ça change pour le projet

1. **La référence du CPU est connue** : le *Reference Manual* MCF54418RM s'applique tel quel (carte des registres, contrôleur USB, SSI, ADC).
2. **Mémoire vive : 128 Mo.** Les moteurs du Syntakt chargés en `0x43000000` ([17](17-portage-exact-syntakt.md) à [19](19-cp-vintage-8e-machine.md)) ont de la marge. À confirmer par la taille déclarée dans le bootstrap ([§3.2](#32-ram--u3)).
3. **Le matériel du Model:Samples est là** : 128 Mo de RAM et 4 Go d'eMMC sur un Model:Cycles.
   - [10 §4](10-faisabilite-fonctionnalites.md) disait qu'un moteur Sample demanderait « de la RAM et du flash non prévus pour ça ». Côté matériel, ils sont prévus. Le chantier reste logiciel.
4. **Plafond de taille de l'OS : 2 Mo**, si l'image est bien dans U25.
   - L'image officielle occupe 702 160 octets une fois compressée (conteneur ELE3). Chaque moteur ajouté la fait grossir.
   - Source : longueur déclarée du conteneur de `model-cycles_OS1.13.syx`, lue avec `tools/mtlib` (`container.parse`) ; capacité de U25 au [§3.3](#33-flash-de-démarrage--u25).
   - **`[À FAIRE]`** Trouver dans l'updater la taille maximale acceptée et le plan de la flash, avant d'empiler d'autres moteurs.
5. **Une voie de secours matérielle existe peut-être** `[HYP]`, utile tant qu'il n'y a pas d'interface MIDI :
   - U25 est un boîtier SOIC 8 broches classique : son contenu peut en principe être lu et réécrit avec un programmateur SPI ;
   - la grille de 20 pastilles donne probablement accès au port de debug du CPU.
   - **Rien de tout cela n'est testé.** Lire une flash en place, carte alimentée par le programmateur, peut échouer ou abîmer quelque chose. À ne tenter qu'en dernier recours, et après avoir identifié les pastilles.
6. **MIDI IN** : deux optocoupleurs tête-bêche, seuil de 1,6 mA. C'est favorable à la piste « sortie casque » de la [note 12](12-flash-par-jack-trs.md), qui reste non testée.
7. **Sorties séparées : USB uniquement.** Une seule chaîne analogique stéréo sur la carte ([§5](#5-audio)).
8. **USB High Speed confirmé par le matériel** (PHY USB3300).

## 12. Inconnues et photos utiles

| Repère | Ce qu'on voit | Ce qu'il faudrait |
|---|---|---|
| U13 | SOIC 8 broches près du CPU, deux résistances R209 et R210 à côté | photo macro du marquage (mémoire I2C ? 2ᵉ flash ?) |
| U17, U21 | boîtier à billes nu / TSSOP | marquages, pour trouver le convertisseur N/A et l'ampli casque |
| U20 | TI « QUJ » | référence exacte ; tension sur L9 |
| U24, U29, U30, U31, U32, U36 | petits régulateurs | marquages ; tensions de sortie au multimètre |
| U27, U34 | logique TSSOP | marquages |
| Q4 à Q10, Q17, Q19… | groupe de transistors SOT-23 en bas de la carte | fonction inconnue |
| Grille de 20 pastilles | dessous | photo nette, puis continuité vers les billes BDM et JTAG du CPU |
| « BOM » R1 à R6 | code 0, 0, 1 | la même zone sur un Model:Samples |
| Carte connecteurs | dessus seulement | photo du dessous ; résistances d'entrée MIDI |

Pour relire un marquage : lumière rasante, photo prise bien à la verticale, une puce par image.

## 13. Repères relevés

| Repère | Composant | Source |
|---|---|---|
| U1 | MCF54415CMJ250 | [photo 8][P8] |
| U2, U22 | H11L1 | [photo 1][P1] |
| U3 | Nanya NT5TU128M8HE-AC | [photo 3][P3] |
| U4 à U11, U15, U23, U28 | 74HC373 | [photo 6][P6], [photo 7][P7], [photo 10][P10] |
| U12, U16 | 74HC238 | [photo 7][P7] |
| U13 | SOIC 8, non lu | [photo 5][P5] |
| U14 | USB3300-EZK | [photo 4][P4] |
| U17 | boîtier à billes, non lu | [photo 7][P7] |
| U18 | DRV632 | [photo 7][P7] |
| U19 | 6 broches près de l'USB, non lu | [photo 9][P9] |
| U20 | TI « QUJ » | [photo 5][P5] |
| U21, U27, U34 | TSSOP, non lus | [photo 1][P1] |
| U24, U32 | SOT-23 à 5 broches, non lus | [photo 9][P9] |
| U25 | cFeon QH16B-104HIP | [photo 2][P2] |
| U26 | Samsung KLM4G1FETE-B041 | [photo 8][P8] |
| U29, U30, U31, U36 | régulateurs probables, non lus | [photo 7][P7], [photo 1][P1], [photo 9][P9] |
| Y1 / Y3 | FOX 24.000 / FOX 24.576 | [photo 4][P4] |
| J5 | micro-USB | [photo 8][P8] |
| F1 | fusible de l'entrée batterie | [photo 1][P1] |
| S1 à S31 / S32 à S37 | touches / pads | [photo 1][P1] |
| EN1 à EN16 | encodeurs | [photo 1][P1] |
| Q12, Q13, Q15, Q16 | transistors « 1BW » | [photo 6][P6], [photo 7][P7], [photo 10][P10] |

## Sources

Consultées le 30/09/2026.

- Photos : dossier [`img/pcb/`](img/pcb/), prises par l'utilisateur sur son Model:Cycles.
- NXP, [*MCF5441x ColdFire Microprocessor Data Sheet*][DS-MCF] (rév. 8), [*MCF5441x Reference Manual*][RM-MCF] (rév. 5), [fiche produit MCF5441x][FS-MCF].
- Microchip (SMSC), [fiche USB3300][DS-USB3300].
- Texas Instruments, [fiche DRV632][DS-DRV632], [fiche TPS6213x][DS-TPS6213X] (tables des marquages).
- onsemi, [fiche H11L1M, H11L2M, H11L3M][DS-H11L1].
- Samsung, [KLM4G1FETE-B041][DS-SAMSUNG].
- Nanya, [NT5TU128M8HE-AC][DS-NANYA] ; Eon, [EN25QH16][DS-EON] (sites de fiches techniques ; pages vues dans les résultats de recherche).
- Nexperia, [74HC373][DS-HC373], [74HC238][DS-HC238].
- Elektron, manuel du Model:Cycles, [page 12 sur ManualsLib][MANUEL].
- Firmware : `tools/hw_periph_refs.py` sur les fichiers officiels `model-cycles_OS1.13.syx` et `model-samples_OS1.13.syx` (non versionnés).

[P1]: img/pcb/01-dessus-vue-ensemble.jpg
[P2]: img/pcb/02-u25-flash-spi.jpg
[P3]: img/pcb/03-u3-ddr2.jpg
[P4]: img/pcb/04-u14-phy-usb-quartz.jpg
[P5]: img/pcb/05-u20-alimentation.jpg
[P6]: img/pcb/06-verrous-hc373-encodeurs.jpg
[P7]: img/pcb/07-touches-hc238-sortie-audio.jpg
[P8]: img/pcb/08-coeur-numerique.jpg
[P9]: img/pcb/09-coeur-numerique-bis.jpg
[P10]: img/pcb/10-touches-verrous.jpg
[P11]: img/pcb/11-dessous-points-de-test.jpg
[DS-MCF]: https://www.nxp.com/docs/en/data-sheet/MCF54418.pdf
[RM-MCF]: https://www.nxp.com/docs/en/reference-manual/MCF54418RM.pdf
[FS-MCF]: https://www.nxp.com/docs/en/fact-sheet/MCF5441XFS.pdf
[DS-USB3300]: https://ww1.microchip.com/downloads/en/DeviceDoc/00001783C.pdf
[DS-DRV632]: https://www.ti.com/lit/ds/symlink/drv632.pdf
[DS-TPS6213X]: https://www.ti.com/lit/ds/symlink/tps62130.pdf
[DS-H11L1]: https://www.onsemi.com/download/data-sheet/pdf/h11l3m-d.pdf
[DS-SAMSUNG]: https://semiconductor.samsung.com/estorage/emmc/emmc-5-1/klm4g1fete-b041/
[DS-NANYA]: https://www.alldatasheet.com/datasheet-pdf/pdf/1145662/NANYA/NT5TU128M8HE-AC.html
[DS-EON]: https://www.alldatasheet.com/datasheet-pdf/pdf/458190/EON/EN25QH16-104HIP.html
[DS-HC373]: https://assets.nexperia.com/documents/data-sheet/74HC_HCT373.pdf
[DS-HC238]: https://assets.nexperia.com/documents/data-sheet/74HC_HCT238.pdf
[MANUEL]: https://www.manualslib.com/manual/1790470/Elektron-Cycles.html?page=12
