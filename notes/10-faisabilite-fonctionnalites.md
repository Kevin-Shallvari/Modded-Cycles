# 10 · Faisabilité des fonctionnalités souhaitées

Évaluation au 25/09/2026, fondée sur l'analyse de l'image OS 1.13 ([09](09-analyse-firmware-1.13.md)), du fil forum ([dossier](00-dossier-technique.md)) et des dépôts amont.
Machine **pas encore reçue** : tout ce qui suit est du travail « sans matériel ». Chaque item dit ce qui est faisable **maintenant**, ce qui demandera **une validation matérielle**, et l'effort.

## Échelle

| Cote | Sens |
|---|---|
| ✅ | Fait, ou déjà supporté en stock |
| 🟢 | Faisable, effort faible |
| 🟡 | Faisable, effort moyen ; une inconnue à lever sur matériel |
| 🟠 | Difficile, gros effort ; faisabilité probable mais non garantie |
| 🔴 | Très difficile / probablement hors de portée comme mod propre du M:C |

## Ce qui est acquis sans matériel

- **Chaîne d'outils autonome** (Python pur, sans dépendance C, sans image firmware versionnée) : `tools/build.py` + `tools/mtlib/`. Voir [BUILD.md](../BUILD.md).
- **Caves de code** : ~6 Ko de zones `0xff` dans le MAIN OS ([09 §4bis](09-analyse-firmware-1.13.md#4bis-caves-de-code-libres-0xff--ressource-pour-toutes-les-extensions)). Les 4 plus grandes sont des masques de sprites : 2,7 Ko s'en libèrent sans effet visible ([14 §5](14-machine-sd-vintage.md#5-place-libre--les-caves-0xff-étaient-des-masques-de-sprites)), dont 1,4 Ko pris par SD VINTAGE et 154 o par `6ch-usbup`. De quoi loger des stubs, pas de gros moteurs.
- **Tweaks QoL prêts** (drumkilla, testés sur vrai matériel) : latching-mute, trig-preview, browser-scroll ([09 §4ter](09-analyse-firmware-1.13.md#4ter-tweaks-qol-prêts-à-lemploi-drumkilla-testés-sur-vrai-matériel)) — bon test de la procédure de flash à faible risque.
- **Le mixeur est localisé** : blocs mono par piste → coefficients L/R (pan) par piste → somme stéréo ; envois FX dérivés de la somme ([09 §6](09-analyse-firmware-1.13.md#6-le-mixeur--où-sont-le-volume-le-pan-et-les-envois-fx-vérifié)).

---

## Par fonctionnalité (dans ton ordre de priorité)

### 1. Sortie multipiste 6 canaux — ✅ (validée sur un vrai Model:Cycles le 29/09/2026)
- Le patch existe (ms-multi-output), porté dans notre dépôt au format tweak, et **notre build reproduit le MAIN OS connu-bon à l'octet près**.
- Reste **le seul test qui manque au monde** : le flasher sur un vrai Model:Cycles. C'est le **jalon 1**.
- Rien de plus à développer sans la machine.

### 2. Sortie multipiste 12 canaux (garder le pan par piste) — 🟡 **meilleur prochain chantier**
- Principe : au lieu de prélever les blocs mono (comme le 6 canaux), produire pour chaque piste **deux canaux L/R** en appliquant son pan.
- **Ce qu'on sait déjà** : le pan est un coefficient par piste, appliqué dans le mixeur ([09 §6](09-analyse-firmware-1.13.md#6-le-mixeur--où-sont-le-volume-le-pan-et-les-envois-fx-vérifié)). Les blocs mono par piste sont à `0x80001858`.
- **Ce qu'il faut faire** : dans le stub du feeder USB, lire le bloc mono + les deux coefficients de la piste, multiplier (EMAC/`muls.l`), écrire L puis R. Géométrie : 12 canaux × 4 o = 48 o/trame, `wMaxPacketSize` = 336, ring à agrandir. Toutes les constantes sont listées en [04 §5](04-usb-audio.md#5-recette--changer-le-nombre-de-canaux-n-liste-de-toutes-les-constantes).
- **Inconnue à lever sur matériel** : l'échelle exacte (format point-fixe) des coefficients de pan est la « secret sauce » d'Elektron. On peut écrire le patch, mais **son exactitude ne se validera qu'à l'oreille/à la mesure sur la machine**.
- **Alternative plus sûre** : le **mode 8 canaux** (6 pistes mono + le mix stéréo), qui ne touche pas au pan et dont presque toutes les constantes se modifient sans nouveau code ([08 §A](08-feuille-de-route.md#a-8-canaux--6-pistes--mix-stéréo-recommandé-comme-jalon-2)). Bon jalon intermédiaire avant le 12 canaux.
- **Ordre conseillé** : valider le 6 canaux (jalon 1) → 8 canaux → 12 canaux.

### 3. Modifier les algorithmes d'effet — 🔴 (mais réglages possibles 🟡)
- Reverb et delay sont du **DSP écrit à la main en assembleur ColdFire**. Remplacer un *algorithme* = réécrire du DSP de zéro : hors de portée réaliste sans un très gros travail.
- **Ce qui est faisable** : ajuster des **paramètres, plages ou valeurs par défaut** d'effet (méthode de `octa-bt-pt` sur l'Octatrack). Rappel : la reverb a déjà un paramètre Tone (FUNC + Reverb Size), le delay un filtre HP/LP fixe ([dossier §5.4](00-dossier-technique.md)).
- Verdict : pas de nouveaux algorithmes ; des retouches de paramètres, oui, à cadrer précisément.

### 4. Moteur Sample (charger des samples comme un Model:Samples) — 🔴
- Reviendrait à **porter tout le sous-système sample du M:S** dans le M:C : stockage des samples, zone sample du +Drive, gestion de la RAM audio, et une nouvelle « machine » dans la structure dynamique du moteur. C'est quasiment fusionner deux firmwares.
- Les 6 Ko de caves n'y suffisent pas de loin ; il faudrait de la RAM et du flash non prévus pour ça.
- **Voie pragmatique existante** : le *cross-flash* fait déjà tourner l'OS Cycles sur un Model:Samples (et inversement) — mais ça veut dire « utiliser un M:S », pas « ajouter le sample au M:C ».
- Verdict honnête : non, pas comme mod propre du M:C.
- **Mise à jour du 29/09/2026** ([15 §3](15-demandes-reddit.md)) : l'**OS Model:Samples complet tourne sur un vrai Model:Cycles** (cross-flash, `tools/crossflash.py`, onglet *Samples OS* du flasher web).
  Les deux OS 1.13 partagent bootstrap, init de la RAM et updater : le matériel est capable. Une machine « sample » dans l'OS Cycles reste un gros chantier, mais n'est plus hors de portée matérielle.
- **Mise à jour du 30/09/2026** ([21](21-architecture-materielle.md)) : vu sur le PCB du Model:Cycles, **128 Mo de DDR2 et une eMMC de 4 Go**. La RAM et le stockage nécessaires sont bien montés.

### 5. LFO améliorés (2 LFO complets, synchronisables, assignables partout, façon Syntakt) — 🟠
- Le M:C n'a **qu'un LFO par piste**. Ajouter un 2ᵉ LFO complet touche : la modulation dans le moteur, l'UI (pages LFO), le stockage des paramètres, et les p-locks. Chantier lourd.
- **Gain partiel plus accessible** 🟡 : élargir les **destinations** du LFO existant (plus de cibles), sans ajouter de 2ᵉ LFO — moins d'impact UI/stockage.
- Verdict : le « 2 LFO façon Syntakt » complet est ambitieux ; commencer par élargir les destinations du LFO actuel.

### 6. Polyrythmie (time signature par piste) — 🟡 (partiellement déjà là)
- Le séquenceur M:C a déjà **longueur par piste** et un **menu SCALE** (multiplicateur de vitesse par piste). Des longueurs différentes par piste = déjà de la polyrythmie.
- **À confirmer** (manuel §9.11 SCALE, à relire précisément) : jusqu'où va le réglage par piste. Si ton besoin dépasse ce qui existe, c'est un mod séquenceur d'effort moyen.
- Verdict : sans doute **en grande partie faisable en stock** ; l'écart éventuel est un mod raisonnable.

### 7. Contrôle MIDI par USB (clock, start/stop) — ✅ **déjà supporté en stock**
- Manuel §12.3.1 SYNC : **CLK IN** (répond à l'horloge **et au transport** MIDI externes) et **CLK OUT** (les émet). §12.3.4 PORTS : `INP FROM` / `OUT TO` réglables sur **USB** ou **M+U**.
- Donc : régler `PORTS → OUT TO = USB` (ou `M+U`) et `SYNC → CLK IN/OUT = ON`. Le « MIDI transport » couvre start/stop/continue.
- Verdict : **aucun mod nécessaire**, c'est un réglage. Gain immédiat.

### 8. Arpégiateur (mode chromatique) — 🟠
- Fonction **inexistante** sur le M:C (contrairement au Digitone/Syntakt). Génération de notes nouvelle + UI + stockage.
- Effort important ; faisable en principe mais long. À placer après les gains multipistes.

### 9. Scale / quantification de gamme (mode chromatique) — 🟡
- Contraindre les notes jouées/séquencées à une gamme : c'est un **hook de traitement de note**, plus contenu qu'un arpégiateur.
- Bon candidat une fois le multipiste validé : effort moyen, caves suffisantes.

### 10. Mode polyphonique du moteur de synthé — 🔴
- **1 voix par piste, sans vol de voix** (confirmé par Ess, [dossier §4.4](00-dossier-technique.md)). La polyphonie = plusieurs voix par piste = changement fondamental du moteur + coût CPU sur une plateforme déjà juste.
- Verdict : très difficile, à considérer en dernier.

---

## Synthèse et recommandation

| # | Fonction | Cote | Quand |
|---|---|---|---|
| 7 | MIDI USB clock/transport | ✅ stock | maintenant (réglage) |
| 1 | 6 canaux USB | ✅ code | **jalon 1** : flash + test dès réception |
| 2 | 8 puis 12 canaux USB | 🟡 | après le jalon 1 (dé-risque toute l'approche USB) |
| 6 | Polyrythmie | 🟡 (déjà en partie) | vérifier le stock, puis petit mod si besoin |
| 9 | Scale chromatique | 🟡 | après le multipiste |
| 5 | Destinations LFO élargies | 🟡 | ensuite ; 2ᵉ LFO complet = 🟠 plus tard |
| 8 | Arpégiateur | 🟠 | long terme |
| 3 | Réglages d'effet (pas les algos) | 🟡 / 🔴 | opportuniste |
| 10 | Polyphonie | 🔴 | en dernier |
| 4 | Moteur Sample | 🔴 | non (utiliser un M:S / cross-flash) |

**Le chemin critique** : d'abord **valider le 6 canaux sur ta machine** (jalon 1). Il confirme d'un coup que notre chaîne build→flash→audio fonctionne, ce qui débloque tout le reste (8/12 canaux, puis les fonctions séquenceur). Tant que ce jalon n'est pas passé, développer les autres patchs, c'est bâtir sur du non-vérifié.

**Sans matériel, d'ici ta réception**, le travail utile est : (a) préparer le patch **8 canaux** (peu de code, presque tout en constantes), (b) finir de qualifier la **source du mix** et l'**échelle des coefficients de pan** par rétro-ingénierie (pour préparer 8 et 12 canaux), (c) cadrer précisément **polyrythmie** et **scale** en relisant le manuel et le séquenceur. Voir [08-feuille-de-route.md](08-feuille-de-route.md).
