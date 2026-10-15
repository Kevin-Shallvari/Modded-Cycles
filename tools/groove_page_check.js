/* Vérifie le chemin critique de la page docs/groove/ SANS navigateur :
 *   builder.js + docs/groove/tweaks.js -> build -> MAIN OS attendu.
 *
 * C'est le contrôle qui compte : si la page ne construit pas exactement le firmware que la
 * ligne de commande produit, elle doit refuser d'envoyer — et ce test le prouve.
 *
 *   node tools/groove_page_check.js <chemin du model-cycles_OS1.13.syx>
 */
"use strict";
const fs = require("fs");
const path = require("path");

global.window = global;
const ROOT = path.join(__dirname, "..");
require(path.join(ROOT, "docs", "flasher", "builder.js"));
require(path.join(ROOT, "docs", "groove", "tweaks.js"));

const syx = process.argv[2];
if (!syx) { console.error("usage: node tools/groove_page_check.js <model-cycles_OS1.13.syx>"); process.exit(2); }

const raw = new Uint8Array(fs.readFileSync(syx));
const G = global.MC_GROOVE;
const B = global.MCBuilder;

let bad = 0;
function check(label, ok, detail) {
  const pad = label.length < 46 ? label + " ".repeat(46 - label.length) : label;
  console.log("   %s %s%s", pad, ok ? "ok" : "FAIL", detail ? "  " + detail : "");
  if (!ok) bad++;
}

console.log("\nA. les donnees de la page");
check("tweaks.js charge (MC_GROOVE)", !!(G && G.tweaks), G ? G.tweaks.length + " tweak(s)" : "");
check("l'empreinte attendue est presente", !!(G && /^[0-9a-f]{64}$/.test(G.mainos || "")));
check("l'ordre est moteur puis format",
      JSON.stringify(G.order) === JSON.stringify(["groove-8tracks", "groove-patterns"]),
      JSON.stringify(G.order));

console.log("\nB. la construction, par le code de la page");
const r = B.build(raw, G.device, G.tweaks, { expectMainOsSha: G.mainos });
check("build() rend un .syx", !!(r && r.raw && r.raw.length), r ? r.raw.length + " octets" : "");
check("MAIN OS = l'empreinte attendue", r.mainOsSha === G.mainos, r.mainOsSha.slice(0, 16) + "…");
check("des octets ont ete patches", r.patchedBytes > 0, r.patchedBytes + " octets");

console.log("\nC. et la page REFUSE une construction qui ne correspond pas");
let refused = false;
try {
  B.build(raw, G.device, G.tweaks, { expectMainOsSha: "0".repeat(64) });
} catch (e) {
  refused = true;
}
check("une empreinte fausse est refusee", refused);

console.log("\n%s", bad ? "ECHEC" : "TOUT OK");
process.exit(bad ? 1 : 0);
