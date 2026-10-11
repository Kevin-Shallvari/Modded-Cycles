/* Convertit une table avec docs/convert/convert.js et ecrit le PCM int16 (compare a la reference Python).
 *   node tools/webwt_check.js table.wav out.raw
 */
const fs = require("fs");
const path = require("path");
const WC = require(path.join(__dirname, "..", "docs", "convert", "convert.js"));

const buf = fs.readFileSync(process.argv[2]);
const x = WC.fromWav(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
const data = WC.bake(x);
fs.writeFileSync(process.argv[3], Buffer.from(data.buffer, data.byteOffset, data.byteLength));
console.log("  js :", data.length, "points,", data.length / WC.S_TOTAL, "frames");
