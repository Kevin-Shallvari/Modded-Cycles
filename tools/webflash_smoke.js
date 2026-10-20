/* Browser smoke test (jsdom) of the web flasher: loads the real page and its scripts,
 * fakes Web MIDI, and walks through the 4 steps (the OS, OS files, connect over USB, flash).
 * The fake Model:Cycles answers the Elektron Transfer protocol (fast method) with its own
 * decoder and zlib's CRC, and keeps every byte it is sent, to compare with the firmware.
 * Run through tools/webflash_smoke.sh (installs jsdom in a temp folder).
 *   node tools/webflash_smoke.js <synth_dir> [model-cycles_OS1.13.syx] [model-samples_OS1.13.syx] [Syntakt_OS1.42.syx or 1.41]
 * The optional official files are told apart by their names. With the Model:Cycles and Syntakt OS
 * files, the Modded Cycles OS (os.json) is built and checked against REF_MAINOS, and each tweak
 * against REF_MODS (app.js, notes/49); with the Model:Samples OS too, the "Samples OS" tab and
 * the OS on a Model:Samples are checked end to end (REF_SAMPLES_ON_CYCLES, tools/mods_for_samples.py). */
const fs = require("fs");
const path = require("path");
const zlib = require("zlib");
const { pathToFileURL } = require("url");
const { JSDOM, VirtualConsole } = require("jsdom");

const FLASH = path.join(__dirname, "..", "docs", "flasher");
const TWEAKS_DIR = path.join(__dirname, "..", "tweaks", "model-cycles_OS1.13");
const SYNTH = process.argv[2];
const REAL = process.argv.slice(3);
const REAL_ST = REAL.find((f) => /syntakt/i.test(path.basename(f)));
const ST_NAME = REAL_ST ? path.basename(REAL_ST) : "Syntakt_OS1.42.syx";
const ST_VERSION = (/OS(\d+\.\d+)/.exec(ST_NAME) || [])[1];   // "1.42" or "1.41": both official, same engines
const REAL_SMP = REAL.find((f) => /samples/i.test(path.basename(f)));
const REAL_OS = REAL.find((f) => f !== REAL_ST && f !== REAL_SMP);
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
// SMOKE_SHARD=k/n (tools/webflash_smoke.sh with SMOKE_JOBS=n): kept for the script's sharding; the OS is one firmware,
// so part 0 does everything and the other parts only report what they built (nothing) to SMOKE_SEEN
const [SHARD_K, SHARD_N] = (process.env.SMOKE_SHARD || "0/1").split("/").map(Number);
const MAIN = SHARD_K === 0;

// Elektron Transfer protocol, written apart from flasher.js (Elektroid's packing: a byte with the
// high bits of the next 7, first one in bit 6).
const XHEAD = [0xf0, 0x00, 0x20, 0x3c, 0x10, 0x00];
function unpack(src) {
  const out = [];
  for (let i = 0; i < src.length; i += 8)
    for (let k = 1; k < 8 && i + k < src.length; k++) out.push(src[i + k] | ((src[i] << k) & 0x80));
  return Uint8Array.from(out);
}
function pack(src) {
  const out = [];
  for (let j = 0; j < src.length; j += 7) {
    const grp = Array.from(src.slice(j, j + 7));
    out.push(grp.reduce((hi, b, k) => hi | ((b >> 7) << (6 - k)), 0), ...grp.map((b) => b & 0x7f));
  }
  return Uint8Array.from([...XHEAD, ...out, 0xf7]);
}
const be = (m, o) => ((m[o] << 24) | (m[o + 1] << 16) | (m[o + 2] << 8) | m[o + 3]) >>> 0;
const cstr = (str) => [...Buffer.from(str, "latin1"), 0];

// A Model:Cycles on USB: answers ping, version, OS upgrade start and blocks like the real one
// (src/connectors/elektron.c), and records what it receives.
function fakeDevice(opts, reply) {
  const dev = Object.assign({ id: 27, name: "Model Cycles", version: "1.13", startStatus: 0, writeError: -1, silent: false,
    pings: 0, starts: 0, blocks: 0, received: null, size: 0, next: 0, bad: [] }, opts);
  dev.handle = (d) => {
    if (d.length < 8 || XHEAD.some((b, k) => d[k] !== b)) return;           // not for the Transfer protocol
    const m = unpack(d.subarray(6, d.length - 1));
    const head = [0, 0, m[0], m[1], m[4] | 0x80];
    let r = null;
    if (m[4] === 0x01) { dev.pings++; r = [...head, dev.id, 1, 0, ...cstr(dev.name)]; }
    else if (m[4] === 0x02) r = [...head, 0, 0, 0, 0, 0, ...cstr(dev.version)];
    else if (m[4] === 0x50) {
      dev.starts++;
      dev.size = m[5] | (m[6] << 8) | (m[7] << 16) | (m[8] << 24);      // little-endian, as Elektroid's memcpy
      if (Buffer.from(m.subarray(9, 16)).toString("latin1") !== "sysex\0\x01") dev.bad.push("start tail");
      dev.received = new Uint8Array(dev.size); dev.next = 0; dev.blocks = 0;
      r = [...head, dev.startStatus, ...(dev.startStatus ? cstr("No space") : [0])];
    } else if (m[4] === 0x51) {
      const crc = be(m, 5), len = be(m, 9), off = be(m, 13), data = m.subarray(17);
      if (data.length !== len || off !== dev.next || len > 0x800 || crc !== zlib.crc32(data, 0xffffffff) >>> 0)
        dev.bad.push(`block ${dev.blocks}: len ${len}/${data.length}, offset ${off}/${dev.next}`);
      dev.received.set(data, off);
      dev.next = off + len;
      const op = dev.blocks === dev.writeError ? 2 : dev.next >= dev.size ? 1 : 0;
      dev.blocks++;
      r = [...head, 0, 0, 0, 0, op];
    }
    if (r && !dev.silent) setTimeout(() => reply(pack(r)), 1);
  };
  return dev;
}

async function load({ midi = true, ports = true, inputs = true, busy = false, secure = true, lang = "en", devName = "Elektron Model:Cycles", device = {} } = {}) {
  const errors = [];
  const vc = new VirtualConsole();
  vc.on("jsdomError", (e) => errors.push("jsdomError: " + ((e.detail && e.detail.message) || e.message || e)));
  const sent = [];
  const listeners = new Set();
  const dev = fakeDevice(device, (data) => listeners.forEach((f) => f({ data })));
  let access = null, devOut = null, devIn = null;
  const html = fs.readFileSync(path.join(FLASH, "index.html"), "utf8");
  const dom = new JSDOM(html, {
    url: pathToFileURL(path.join(FLASH, "index.html")).href,
    runScripts: "dangerously", resources: "usable", virtualConsole: vc,
    beforeParse(window) {
      Object.defineProperty(window, "isSecureContext", { value: secure, configurable: true });
      Object.defineProperty(window.navigator, "language", { value: lang, configurable: true });
      window.addEventListener("error", (e) => errors.push("window.onerror: " + ((e.error && e.error.message) || e.message)));
      window.addEventListener("unhandledrejection", (e) => errors.push("unhandled: " + ((e.reason && e.reason.message) || e.reason)));
      if (midi) {
        const outputs = new Map(), ins = new Map();
        if (ports) {
          devOut = { id: "dev", name: devName, manufacturer: "Elektron", state: "connected",
            send: (d) => { sent.push(d.length); dev.handle(d); }, open: () => Promise.resolve(), close: () => Promise.resolve() };
          outputs.set("dev", devOut);
          outputs.set("iface", { id: "iface", name: "USB MIDI Interface", manufacturer: "Acme", send: (d) => sent.push(d.length) });
          devIn = { id: "dev-in", name: devName, manufacturer: "Elektron", state: "connected",
            open: () => (busy ? Promise.reject(new Error("InvalidAccessError: port in use")) : Promise.resolve()),
            close: () => Promise.resolve(), addEventListener: (t, f) => listeners.add(f), removeEventListener: (t, f) => listeners.delete(f) };
          if (inputs) ins.set("dev-in", devIn);
        }
        access = { outputs, inputs: ins, onstatechange: null };
        window.navigator.requestMIDIAccess = () => Promise.resolve(access);
      }
      window.URL.createObjectURL = () => "blob:x";
      window.URL.revokeObjectURL = () => {};
    },
  });
  await wait(300);
  // tweaks.js is half a megabyte: on a busy machine the scripts can take more than 300 ms to load
  for (let i = 0; i < 200 && !(dom.window.MCFlasherApp && dom.window.MC_TWEAKS && dom.window.MCBuilder); i++) await wait(50);
  return { dom, w: dom.window, doc: dom.window.document, errors, sent, dev, listeners,
    access: () => access, devOut: () => devOut, devIn: () => devIn };
}

// No pause between blocks (50 ms on the real machine): a 2.5 MB file goes through in a few seconds.
function noRest(w) {
  const orig = w.MCFlasher.upgradeFast;
  w.MCFlasher.upgradeFast = (session, raw, opts) => orig(session, raw, Object.assign({}, opts, { restMs: 0 }));
}
const same = (a, b) => !!a && !!b && a.length === b.length && Buffer.compare(Buffer.from(a), Buffer.from(b)) === 0;
async function untilSent(w, ms = 60000) {
  for (let i = 0; i < ms / 50 && w.MCFlasherApp.state.sending; i++) await wait(50);
}

const text = (doc, id) => doc.getElementById(id).textContent;
// text of the elements a selector picks (the Details drawers are always in the page: scope what a check reads)
const textOf = (doc, sel) => [...doc.querySelectorAll(sel)].map((e) => e.textContent).join(" ");
async function settle(w) {
  for (let i = 0; i < 200 && w.MCFlasherApp.state.building; i++) await wait(50);
  await wait(60);
}
const OS_FILE = "modded-cycles-os_2.0.syx";

async function main() {
  let fail = 0;
  const check = (cond, msg) => { console.log((cond ? "  ok  " : "  FAIL ") + msg); if (!cond) fail++; };
  const seenKeys = [];

  // 1. Page loads cleanly, everything is wired; step 1 is the OS, read-only
  if (MAIN) {
    const { w, doc, errors } = await load();
    check(errors.length === 0, "loads without JS error " + (errors.length ? JSON.stringify(errors) : ""));
    check(typeof w.MCBuilder === "object" && typeof w.MCFlasher === "object", "MCBuilder + MCFlasher present");
    const os = w.MC_TWEAKS.os;
    const ids = w.MC_TWEAKS.tweaks.map((x) => x.id);
    check(ids.join() === os.tweaks.join() && os.key === ids.join("+") && ids.length === 14
      && ids.includes("model-tg-st") && ids.includes("sample-preview-st") && ids.includes("lfo-plus") && ids.includes("mod-settings") && ids.includes("step-rec")
      && ids.includes("syntakt-tg-sd-cp-toy-bits-swarm-macro-acid")
      && !ids.some((x) => /chord|6ch|track-filter|os-optimise|exact|snare|multiout/.test(x)) && !ids.includes("midi-both"),
      `tweaks.js carries exactly the ${ids.length} tweaks of ${os.name} ${os.version} (no picker, nothing else): ${ids.join()}`);
    check(w.MC_TWEAKS.features.length === 19 && os.machines.length === 8 && os.machines[0].name === "Sampler" && os.machines[7].name === "ACID",
      "19 features, 8 added machines from the Sampler to ACID");
    check(/build \d{4}-/.test(text(doc, "build-stamp")), "version stamp shown");
    const srcs = [...doc.querySelectorAll("script[src]")].map((x) => x.getAttribute("src"));
    check(["builder.js", "tweaks.js", "flasher.js", "app.js"].every((f) => srcs.some((x) => x.startsWith(f + "?")))
      && srcs.every((x) => x.endsWith("?v=" + w.MC_BUILD)), "scripts loaded with ?v=<build> (no stale cache): " + srcs.join());
    check(doc.getElementById("compat").hidden, "no compatibility banner in a good browser");
    check(text(doc, "tab-mods") === "Modded Cycles OS", "first tab is the OS: " + text(doc, "tab-mods"));
    // the OS header
    const head = text(doc, "os-head");
    check(/Modded Cycles OS 2\.0/.test(head) && doc.querySelector("#os-head .tag")
      && doc.querySelector("#os-head .tag").textContent === (os.status === "tested" ? "Tested" : "Experimental")
      && /Nothing to pick/.test(head) && /after Chord/.test(head) && /Sampler/.test(head) && /SDVtg/.test(head) && /ACID/.test(head)
      && /Syntakt_OS1\.42\.syx/.test(head) && /No Syntakt needed/.test(head),
      "OS header: name, version, status tag, nothing to pick, the 8 added machines, the two files it needs");
    // the features, by section, no checkbox, no selection bar, no search
    const feats = [...doc.querySelectorAll("#features .mod")].map((d) => d.id.slice(4));
    check(feats.join() === "model-tg,syntakt,macro,acid,lfo-plus,trig-preview,trig-hold,arp,step-rec,tempo-max,latching-mute,sample-preview,browser-scroll,boot-anim,multiline-browser,level-pan-values,trigless-dim,midi-live-both,mod-settings",
      "19 feature rows, by section (Sounds & machines, Sequencer, Live, Screen, USB & MIDI): " + feats.join());
    check(doc.querySelectorAll("#features input").length === 0 && !doc.getElementById("mod-sel") && !doc.getElementById("mod-find")
      && !doc.getElementById("mod-q"), "nothing to tick: no checkbox, no selection bar, no search field");
    check(w.MC_TWEAKS.features.every((f) => doc.querySelector(`#cat-${f.cat} #mod-${f.id} #feat-${f.id}`)), "every feature has a row in its section (cat)");
    const sections = [...doc.querySelectorAll("#features section.grp")].map((g) => g.id.slice(4));
    check(sections.join() === "sound,seq,live,screen,io" && !doc.getElementById("cat-other") && !doc.getElementById("cat-pack"),
      "sections in CATS order, no Packs, no « Other mods »: " + sections.join());
    check([...doc.querySelectorAll("#cats a[data-cat]")].map((a) => a.dataset.cat).join() === sections.join()
      && doc.querySelector('#cats a[data-cat="seq"]').getAttribute("href") === "#cat-seq" && !doc.querySelector("#cats .led"),
      "one chip per section, linking to it, no LED");
    const tagOfFeat = (f) => (f.status === "tested" ? "Tested" : "Experimental");
    const tags = w.MC_TWEAKS.features.map((f) => f.id + ":" + doc.querySelector(`#mod-${f.id} .tag`).textContent);
    check(tags.join() === w.MC_TWEAKS.features.map((f) => f.id + ":" + tagOfFeat(f)).join()
      && /Experimental/.test(tags.find((x) => x.startsWith("model-tg:"))) && /Tested/.test(tags.find((x) => x.startsWith("syntakt:"))),
      "rows tagged as tested or not (Model-TG experimental until its 1.1.0 build is tested here): " + tags.join());
    const credits = [...doc.querySelectorAll("#features .credit a")].map((a) => a.href);
    const creditOf = (id) => [...doc.querySelectorAll(`#mod-${id} .credit a`)].map((a) => a.href);
    check(credits.length === 17
      && creditOf("model-tg")[0] === "https://github.com/TinyGregAudio/Model-TG" && /\/LICENSE-Model-TG\.txt$/.test(creditOf("model-tg")[1])
      && creditOf("sample-preview")[0] === "https://github.com/TinyGregAudio/Model-TG" && /\/LICENSE-Model-TG\.txt$/.test(creditOf("sample-preview")[1])
      && ["latching-mute", "trig-preview", "browser-scroll"].every((id) => creditOf(id)[0] === "https://github.com/drumkilla/elektron-model-tweaks"
        && /\/LICENSE-elektron-model-tweaks\.txt$/.test(creditOf(id)[1]))
      && creditOf("macro")[0] === "https://github.com/pichenettes/eurorack" && /\/LICENSE-Braids\.txt$/.test(creditOf("macro")[1])
      && creditOf("acid")[0] === "https://github.com/RobinSchmidt/Open303" && /\/LICENSE-Open303\.txt$/.test(creditOf("acid")[1])
      && creditOf("midi-live-both").join() === "https://github.com/AveyCole/Modded-Cycles"
      && creditOf("mod-settings")[0] === "https://github.com/scottmetoyer/ms-multi-output" && /\/LICENSE-ms-multi-output\.txt$/.test(creditOf("mod-settings")[1])
      && creditOf("lfo-plus").length === 0 && /based on a mod by DavidCaruso/.test(textOf(doc, "#mod-lfo-plus .credit"))
      && creditOf("syntakt").length === 0 && !doc.querySelector("#mod-syntakt .credit"),
      "each row credits its author, with a link to the MIT license of the code it carries; the Syntakt engines credit nobody (your own Syntakt file): " + JSON.stringify(credits));
    const djd = ["level-pan-values", "trigless-dim"].map((id) => doc.querySelector(`#mod-${id} .credit`));
    check(djd.every((c) => c && c.textContent === "based on a mod by djd_oz" && !c.querySelector("a")),
      "djd_oz's two mods: “based on a mod by djd_oz”, no link (no public repository)");
    // the OS reads the Syntakt engines: the Syntakt drop zone is shown at once, step 2 asks for two files
    check(!doc.getElementById("drop3-wrap").hidden && /Drop Syntakt_OS1.42.syx/.test(text(doc, "drop3"))
      && /elektron\.se\/support-downloads\/syntakt/.test(doc.getElementById("step-file").innerHTML)
      && /Syntakt OS in step 2/.test(textOf(doc, "#mod-syntakt .need")) && text(doc, "h2s") === "Load your official OS files",
      "the OS needs the Syntakt file: its drop zone and download link are shown at once, the engines row says so, step 2 says files");
    check(w.MCFlasherApp.chosenTweaks().map((x) => x.id).join("+") === os.key && w.MCFlasherApp.chosenLabels().join() === "Modded Cycles OS 2.0",
      "the page builds the OS and nothing else");
    // Details: opens and closes, holds the status and the guide link; the engines row lists the five engines
    const click = async (el) => { el.click(); await wait(5); };
    await click(doc.getElementById("more-arp"));
    const opened = !doc.getElementById("det-arp").hidden && doc.getElementById("more-arp").getAttribute("aria-expanded") === "true"
      && !!doc.querySelector('#det-arp a[href$="#arp"]') && /Status/.test(text(doc, "det-arp")) && /Tested on a real Model:Cycles/.test(text(doc, "det-arp"));
    await click(doc.getElementById("more-arp"));
    check(opened && doc.getElementById("det-arp").hidden && doc.getElementById("more-arp").getAttribute("aria-expanded") === "false",
      "Details opens the drawer (description, status, guide link) and closes it");
    check(/SDVtg/.test(textOf(doc, "#det-syntakt")) && /SYSwm/.test(textOf(doc, "#det-syntakt")) && /vintage snare/.test(textOf(doc, "#det-syntakt"))
      && /your Syntakt OS file/.test(textOf(doc, "#det-syntakt")) && !!doc.querySelector('#det-syntakt a[href$="#syntakt"]'),
      "the Syntakt engines row details the five engines and the extra file");
    check(/Sampler machine \(7th\)/.test(textOf(doc, "#mod-model-tg .parts")) && /slide trigs/.test(textOf(doc, "#mod-model-tg .parts"))
      && /Device Config › Transfer/.test(textOf(doc, "#det-model-tg")) && !!doc.querySelector('#det-model-tg a[href$="#model-tg"]'),
      "the Sampler row lists what Model-TG brings, its note and its guide link");
    check(w.MC_TWEAKS.features.every((f) => doc.querySelector(`#det-${f.id} a.feat-guide`)), "every feature links to its guide section");
    // folding a section; a folded section still names its features; its chip unfolds it
    await click(doc.getElementById("grp-h-seq"));
    const folded = doc.getElementById("grp-seq").hidden && doc.getElementById("grp-h-seq").getAttribute("aria-expanded") === "false"
      && /Arpeggiator/.test(textOf(doc, "#cat-seq .grp-sel"));
    await click(doc.querySelector('#cats a[data-cat="seq"]'));
    check(folded && !doc.getElementById("grp-seq").hidden, "a folded section names its features, its chip unfolds it");
    const list = [...doc.querySelectorAll("#credits-list a")].map((a) => a.textContent);
    check(list.join() === "scottmetoyer/ms-multi-output,drumkilla/elektron-model-tweaks,pichenettes/eurorack,RobinSchmidt/Open303,TinyGregAudio/Model-TG,mischa85/elektron-firmware-tool,dagargo/elektroid,mxldyn/octamax",
      "credits section lists the 8 upstream repositories");
    const lic = [...doc.querySelectorAll("#credits a")].map((a) => a.href).filter((h) => /LICENSE|NOTICES/.test(h));
    check(lic.join() === "https://github.com/18nelli18/Modded-Cycles/blob/main/LICENSE,https://github.com/18nelli18/Modded-Cycles/blob/main/THIRD-PARTY-NOTICES.md",
      "credits section links the project's MIT license and the third-party notices: " + JSON.stringify(lic));
    check(!!doc.getElementById("tab-samples") && doc.getElementById("panel-samples").hidden && doc.getElementById("drop2-wrap").hidden,
      "Samples OS tab present, its panel and second drop zone hidden in the OS tab");
    check(/Load your official OS file/.test(text(doc, "missing")), "flash button says what is missing: " + text(doc, "missing"));
    check(doc.getElementById("flash").disabled, "flash button disabled without a file");

    // language switch
    doc.querySelector('.lang button[data-lang="fr"]').click();
    await wait(20);
    check(/Que voulez-vous installer/.test(text(doc, "h1s")) && doc.documentElement.lang === "fr", "FR switch translates the page");
    check(/Modded Cycles OS 2\.0/.test(text(doc, "os-head")) && /Machines ajoutées/.test(text(doc, "os-head")) && /Rien à choisir/.test(text(doc, "os-head"))
      && text(doc, "tab-mods") === "Modded Cycles OS" && text(doc, "h2s") === "Déposez vos fichiers d'OS officiels",
      "FR: OS header, tab and step 2 title translated");
    check(/Machine Sampler \(Model-TG\)/.test(text(doc, "features")) && /Moteurs du Syntakt/.test(text(doc, "features"))
      && /par drumkilla/.test(text(doc, "features")) && /Testé/.test(text(doc, "features")) && /Expérimental/.test(text(doc, "features")),
      "FR switch translates the feature rows and credits");
    check(/Crédits/.test(text(doc, "credits")) && /boîte à outils/.test(text(doc, "credits")) && /publié sous licence MIT/.test(text(doc, "credits")),
      "FR switch translates the credits section");
    check(/Tempo jusqu'à 546 BPM/.test(text(doc, "features")) && doc.querySelector('#det-tempo-max a[href$="#tempo"]')
      && /Animation de démarrage/.test(text(doc, "features")) && doc.querySelector('#det-boot-anim a[href$="#boot-anim"]')
      && /Volume et pan en chiffres/.test(text(doc, "features")) && /Trigless trigs atténués/.test(text(doc, "features"))
      && /d'après un mod de djd_oz/.test(text(doc, "features")) && /Navigateur sur plusieurs lignes/.test(text(doc, "features"))
      && /Basculer MIDI OUT \+ THRU en direct/.test(text(doc, "features")) && /par AveyCole/.test(textOf(doc, "#mod-midi-live-both"))
      && /Écoute des samples/.test(text(doc, "features")) && /Machine MACRO/.test(text(doc, "features")) && /d'après eurorack d'Émilie Gillet/.test(text(doc, "features"))
      && /Machine ACID/.test(text(doc, "features")) && /d'après Open303 de Robin Schmidt/.test(text(doc, "features"))
      && /LFO 2, 3, 4/.test(text(doc, "features")) && /d'après un mod de DavidCaruso/.test(text(doc, "features"))
      && /Audio USB : stéréo ou 6 pistes/.test(text(doc, "features")) && doc.querySelector('#det-mod-settings a[href$="#mod-settings"]')
      && /entrez les notes du pattern pas à pas/.test(text(doc, "features")) && doc.querySelector('#det-step-rec a[href$="#step-rec"]'),
      "FR: every row translated, with its credit and guide link");
    check(/\+ OS Syntakt à l'étape 2/.test(textOf(doc, "#mod-syntakt .need")) && /Déposez Syntakt_OS1.42.syx/.test(text(doc, "drop3")),
      "FR: the Syntakt file is asked for in French");
    doc.querySelector('.lang button[data-lang="en"]').click();
    await wait(20);

    // Connection: USB only, fast method by default, classic as the fallback
    check(doc.querySelectorAll('input[name="method"]').length === 0 && !doc.getElementById("howto-midi")
      && !/MIDI IN|READY TO RECEIVE|TRIG 4/.test(text(doc, "step-connect")), "no MIDI IN route in step 3");
    check(doc.getElementById("m-fast").getAttribute("aria-checked") === "true" && !doc.getElementById("howto-fast").hidden
      && doc.getElementById("howto-usb").hidden && /Close Elektron Transfer/.test(text(doc, "howto-fast"))
      && !/CONFIG › UPGRADE/.test(text(doc, "howto-fast")) && /about 30 seconds/.test(text(doc, "method-note")),
      "fast method by default: its steps (close Transfer, no menu to open)");
    doc.getElementById("allow").click();
    await wait(150);
    const sel = doc.getElementById("port");
    check(!sel.hidden && sel.value === "dev", "Allow MIDI -> Model:Cycles port preselected (" + sel.value + ")");
    check(/Model:Cycles found: OS 1\.13/.test(text(doc, "midi-status")) && doc.getElementById("step-connect").classList.contains("done"),
      "fast: the machine is asked who it is: " + text(doc, "midi-status").slice(0, 50));
    doc.getElementById("m-slow").click();
    await wait(20);
    check(/CONFIG › UPGRADE/.test(text(doc, "howto-usb")) && !doc.getElementById("howto-usb").hidden && doc.getElementById("howto-fast").hidden
      && /USB port is selected/.test(text(doc, "midi-status")) && /5 to 10 minutes/.test(text(doc, "method-note")),
      "classic method: CONFIG › UPGRADE steps, status: " + text(doc, "midi-status").slice(0, 50));
    sel.value = "iface";
    sel.dispatchEvent(new w.Event("change"));
    await wait(20);
    check(/pick the port named/i.test(text(doc, "midi-status")), "another port -> warning");
    doc.getElementById("m-fast").click();
    await wait(20);
    check(/pick the port named/i.test(text(doc, "midi-status")) && w.MCFlasherApp.state.dev.state === "noinput", "fast, another port (output only) -> warning");
    doc.querySelector('.lang button[data-lang="fr"]').click();
    await wait(20);
    check(/Rapide \(USB\)/.test(text(doc, "m-fast")) && /Fermez Elektron Transfer/.test(text(doc, "howto-fast")), "FR: method and steps translated");
    doc.querySelector('.lang button[data-lang="en"]').click();
    await wait(20);
    check(errors.length === 0, "no JS error in step 1 " + (errors.length ? JSON.stringify(errors) : ""));
  }

  // 1c. Fast method: a machine that doesn't answer (CONFIG > UPGRADE open, Transfer running), no MIDI input
  if (MAIN) {
    const { doc, dev } = await load({ device: { silent: true } });
    doc.getElementById("allow").click();
    await wait(1300);
    check(/doesn't answer/.test(text(doc, "midi-status")) && dev.pings === 1, "silent machine -> 'doesn't answer' after the 1 s handshake");
    dev.silent = false;
    doc.getElementById("refresh").click();
    await wait(150);
    check(/Model:Cycles found/.test(text(doc, "midi-status")) && dev.pings === 2, "Refresh asks again -> found");
  }
  if (MAIN) {
    const { doc } = await load({ busy: true });
    doc.getElementById("allow").click();
    await wait(100);
    check(/in use by another program: close Elektron Transfer/.test(text(doc, "midi-status")), "port held by another program -> says so");
  }
  if (MAIN) {
    const { doc } = await load({ inputs: false });
    doc.getElementById("allow").click();
    await wait(100);
    check(/no MIDI input from the Model:Cycles/.test(text(doc, "midi-status")), "no MIDI input -> says the fast method needs both directions");
  }

  // 1b. A Model:Cycles running the Samples OS shows up as "Model:Samples": it refuses a Model:Cycles firmware
  if (MAIN) {
    const { doc } = await load({ devName: "Elektron Model:Samples", device: { id: 25, name: "Model Samples" } });
    doc.getElementById("allow").click();
    await wait(150);
    check(doc.getElementById("port").value === "dev" && /Model:Samples found/.test(text(doc, "midi-status")),
      "fast: Model:Samples port -> identified: " + text(doc, "midi-status").slice(0, 60));
    doc.getElementById("m-slow").click();
    await wait(20);
    check(/refuses a Model:Cycles firmware/.test(text(doc, "midi-status")), "classic: Model:Samples port -> warning about the way back");
  }

  // 2. No Web MIDI (Firefox / Safari) -> clear banner
  if (MAIN) {
    const { doc } = await load({ midi: false });
    check(!doc.getElementById("compat").hidden && /Chrome, Edge or Opera/.test(text(doc, "compat")), "no Web MIDI -> banner");
    check(doc.getElementById("allow").disabled, "no Web MIDI -> Allow button disabled");
  }

  // 3. Insecure context (file://) -> clear banner
  if (MAIN) {
    const { doc } = await load({ secure: false });
    check(/secure page/i.test(text(doc, "compat")), "file:// -> banner: " + text(doc, "compat").slice(0, 40));
  }

  // 4. French browser -> French page
  if (MAIN) {
    const { doc } = await load({ lang: "fr-FR" });
    check(doc.documentElement.lang === "fr" && /Flasher Model:Cycles/.test(text(doc, "step-flash") + doc.title), "fr-FR browser -> French page");
  }

  // 5. Build from a synthetic OS, then flash, then stop. The real OS needs the Syntakt file and the official
  // image; here, after checking that the page asks for the Syntakt file, the OS is swapped for a development
  // one made of the three drumkilla tweaks (the synthetic image carries their old bytes), so the whole build and
  // flash flow runs without any Elektron file.
  if (SYNTH && MAIN) {
    const env5 = await load();
    const { w, doc, errors, sent } = env5;
    const raw = new Uint8Array(fs.readFileSync(path.join(SYNTH, "synth.syx")));
    const meta = JSON.parse(fs.readFileSync(path.join(SYNTH, "meta.json")));
    const app = w.MCFlasherApp;
    // the synthetic OS stands in for the official one
    w.MC_TWEAKS.device.section_sha256 = meta.section_sha256;
    w.MC_TWEAKS.device.stock_syx_sha256 = w.MCBuilder.hex(w.MCBuilder.sha256(raw));
    for (const k of Object.keys(app.REF_MAINOS)) delete app.REF_MAINOS[k];
    app.loadOs(raw, "synth.syx");
    await settle(w);
    check(/Official Model:Cycles OS 1.13 recognised/.test(text(doc, "file-status")), "OS file recognised as official");
    check(!app.state.fw && app.state.fwError === "needs_syntakt" && /read from the official Syntakt OS/.test(text(doc, "file-status"))
      && /Load the official Syntakt OS file/.test(text(doc, "missing")) && !doc.getElementById("drop3-wrap").hidden,
      "the OS reads the Syntakt engines: without the Syntakt file, nothing is built and the page asks for it");
    app.loadSyntakt(raw, "Syntakt_OS1.42.syx");
    await settle(w);
    check(!app.state.syntakt && /not the official Syntakt OS 1.42/.test(text(doc, "file3-status")), "a wrong file in the Syntakt zone is refused");
    // the development OS
    const dev5 = ["01-latching-mute", "02-trig-preview", "03-browser-scroll"].map((f) => JSON.parse(fs.readFileSync(path.join(TWEAKS_DIR, f + ".json"), "utf8")));
    w.MC_TWEAKS.tweaks.push(...dev5);
    w.MC_TWEAKS.os.tweaks = dev5.map((x) => x.id);
    w.MC_TWEAKS.os.key = w.MC_TWEAKS.os.tweaks.join("+");
    app.loadOs(raw, "synth.syx");                                  // a new file: the build cache starts afresh
    await settle(w);
    check(app.state.fw && app.state.fw.kind === "built" && /Firmware ready: Modded Cycles OS 2\.0\./.test(text(doc, "file-status"))
      && app.state.fw.name === OS_FILE && doc.getElementById("drop3-wrap").hidden && !app.state.fw.ref && !app.state.fw.modsRef,
      "firmware built automatically (development OS on the synthetic image): " + text(doc, "file-status").slice(0, 60));
    app.setMode("restore");
    await settle(w);
    check(app.state.fw && app.state.fw.kind === "stock", "Official firmware tab -> sends the OS unchanged");
    app.setMode("mods");
    await settle(w);
    check(app.state.fw && app.state.fw.kind === "built", "back to the OS tab -> built firmware again (cache)");

    doc.getElementById("allow").click();
    await wait(150);
    check(/Tick the box/.test(text(doc, "missing")), "asks for the confirmation box");
    doc.getElementById("ack").click();
    await wait(20);
    check(!doc.getElementById("flash").disabled, "flash button enabled when everything is ready");
    const fastMin = Math.max(1, Math.round(w.MCFlasher.fastSeconds(app.state.fw.raw) / 60));   // 2.5 MB synthetic file: 2 min
    check(text(doc, "summary").endsWith(`via Elektron Model:Cycles · about ${fastMin} min`) && fastMin <= 2 && /confirm on its screen/.test(text(doc, "missing"))
      && /Modded Cycles OS 2\.0/.test(text(doc, "summary")), "fast summary: " + text(doc, "summary"));
    const dl = doc.getElementById("download");
    check(!doc.getElementById("alt").hidden && dl.getAttribute("download") === OS_FILE && /Elektron Transfer/.test(text(doc, "alt")),
      "step 4 offers the .syx for Elektron Transfer: " + dl.getAttribute("download"));

    // fast: stop during the transfer (real 50 ms pause between blocks)
    const { dev } = env5;
    doc.getElementById("flash").click();
    await wait(400);
    check(!doc.getElementById("stop").hidden && /Flashing/.test(text(doc, "flash")) && dev.starts === 1 && dev.blocks > 1
      && doc.getElementById("m-slow").disabled, `fast transfer running: ${dev.blocks} blocks acknowledged, method locked`);
    doc.getElementById("stop").click();
    await untilSent(w);
    check(app.state.finished === "stopped" && /Stopped before the end/.test(text(doc, "result")) && dev.next < dev.size,
      "fast: Stop -> clear message, the machine didn't get the whole file");

    // fast: full transfer, byte for byte, then the machine restarts
    noRest(w);
    const fw5 = app.state.fw.raw;
    doc.getElementById("flash").click();
    await untilSent(w);
    check(app.state.finished === "ok" && same(dev.received, fw5) && dev.bad.length === 0 && dev.starts === 2
      && dev.blocks === Math.ceil(fw5.length / 0x800),
      `fast: the machine received the whole .syx, byte for byte, CRC checked (${dev.blocks} blocks) ` + dev.bad.slice(0, 2).join("; "));
    check(/Firmware sent/.test(text(doc, "result")) && /confirm the update on the Model:Cycles screen/.test(text(doc, "after"))
      && /after Chord come/.test(text(doc, "result")) && /Sampler/.test(text(doc, "result")) && /ACID/.test(text(doc, "result")),
      "fast: success -> confirm on the machine, the added machines named");
    const out5 = env5.devOut(), in5 = env5.devIn();
    out5.state = in5.state = "disconnected";
    env5.access().onstatechange({ port: out5 });
    await wait(20);
    check(/writing the firmware and restarting/.test(text(doc, "after")), "machine gone -> 'writing and restarting'");
    out5.state = in5.state = "connected";
    dev.version = "1.13B";
    env5.access().onstatechange({ port: out5 });
    await wait(2800);
    check(/is back: Model:Cycles OS 1\.13B/.test(text(doc, "after")), "machine back -> asked again: " + text(doc, "after"));

    // fast: refusals
    dev.startStatus = 1;
    doc.getElementById("flash").click();
    await untilSent(w);
    check(app.state.finished === "error" && /refused the update \(“No space”\)/.test(text(doc, "result")), "start refused -> " + text(doc, "result").slice(0, 60));
    dev.startStatus = 0; dev.writeError = 3;
    doc.getElementById("flash").click();
    await untilSent(w);
    check(app.state.finished === "error" && /error while receiving/.test(text(doc, "result")) && dev.blocks === 4, "block refused -> stops there");
    dev.writeError = -1; dev.id = 25;
    doc.getElementById("refresh").click();
    await wait(150);
    check(doc.getElementById("flash").disabled && /can't take this firmware/.test(text(doc, "missing"))
      && /answers as a Model:Samples/.test(text(doc, "midi-status")), "machine answering as a Model:Samples (Transfer set to SMP) -> nothing sent");
    dev.id = 27;
    doc.getElementById("refresh").click();
    await wait(150);
    check(!doc.getElementById("flash").disabled, "back to a Model:Cycles -> ready");

    // classic method
    doc.getElementById("m-slow").click();
    await wait(20);
    check(/via Elektron Model:Cycles · about \d+ min/.test(text(doc, "summary")) && /Open CONFIG › UPGRADE/.test(text(doc, "missing")),
      "classic summary: " + text(doc, "summary"));

    // stop during a paced transfer
    doc.getElementById("flash").click();
    await wait(400);
    check(!doc.getElementById("stop").hidden && /Flashing/.test(text(doc, "flash")), "during transfer: Stop visible, button busy");
    doc.getElementById("stop").click();
    for (let i = 0; i < 40 && app.state.sending; i++) await wait(50);
    check(app.state.finished === "stopped" && /Stopped/.test(text(doc, "result")), "Stop -> clear 'stopped' message");

    // full transfer at pace 0
    const n0 = sent.length;
    doc.getElementById("pace").value = "0";
    doc.getElementById("pace").dispatchEvent(new w.Event("input"));
    doc.getElementById("flash").click();
    for (let i = 0; i < 200 && app.state.sending; i++) await wait(50);
    const total = w.MCFlasher.splitMessages(app.state.fw.raw).length;
    check(sent.length - n0 === total, `every packet sent (${sent.length - n0}/${total})`);
    check(app.state.finished === "ok" && /Transfer complete/.test(text(doc, "result")) && /UPDATING FLASH/.test(text(doc, "result")),
      "success message shown");
    check(errors.length === 0, "no JS error during the flow " + (errors.length ? JSON.stringify(errors) : ""));
  }

  // 6. Real official files (notes/49): the Modded Cycles OS is built from the official Model:Cycles and Syntakt
  // files and must match its reference hash; each tweak is checked against REF_MODS; a tweak that is not the
  // Python one is refused.
  if (REAL_OS) {
    const { w, doc, errors, dev } = await load();
    const app = w.MCFlasherApp;
    const key = w.MC_TWEAKS.os.key;
    noRest(w);
    app.loadOs(new Uint8Array(fs.readFileSync(REAL_OS)), "model-cycles_OS1.13.syx");
    await settle(w);
    check(/Official Model:Cycles OS 1.13 recognised/.test(text(doc, "file-status")) && !app.state.fw && app.state.fwError === "needs_syntakt",
      "real OS recognised; without the Syntakt file the page asks for it");
    check(Object.keys(app.REF_MAINOS).length === 1 && /^[0-9a-f]{64}$/.test(app.REF_MAINOS[key] || ""),
      "REF_MAINOS holds exactly one firmware, the OS: " + key.slice(0, 40) + "…");
    check(Object.keys(app.REF_MODS).length === w.MC_TWEAKS.tweaks.length
      && w.MC_TWEAKS.tweaks.every((x) => app.REF_MODS[x.id] && /^[0-9a-f]{64}$/.test(app.REF_MODS[x.id].w)
        && !!x.append === /^[0-9a-f]{64}$/.test(app.REF_MODS[x.id].p || "")),
      `REF_MODS: the writes of each of the ${w.MC_TWEAKS.tweaks.length} tweaks, and the payload of those that append one`);
    if (!REAL_ST) console.log("  skip: no Syntakt OS given, the OS can't be built (pass Syntakt_OS1.42.syx or 1.41 too)");
    else if (MAIN) {
      app.loadSyntakt(new Uint8Array(fs.readFileSync(REAL_OS)), "model-cycles_OS1.13.syx");   // wrong file in the Syntakt zone
      await settle(w);
      check(!app.state.syntakt && /not the official Syntakt/.test(text(doc, "file3-status")) && !app.state.fw, "a Cycles file in the Syntakt zone is refused");
      app.loadSyntakt(new Uint8Array(fs.readFileSync(REAL_ST)), ST_NAME);
      await settle(w);
      const f = app.state.fw;
      seenKeys.push(app.state.buildKey);
      check(app.state.buildKey === key && f && f.kind === "built" && f.ref && f.modsRef && f.sha === app.REF_MAINOS[key] && f.name === OS_FILE
        && /Checked against the reference build/.test(text(doc, "file-status")) && new RegExp("MAIN OS " + app.REF_MAINOS[key].slice(0, 8)).test(text(doc, "file-status"))
        && text(doc, "file3-status").includes(`Official Syntakt OS ${ST_VERSION} recognised`),
        `real files: the OS matches its reference hash, each mod checked (MAIN OS ${(f ? f.sha : "").slice(0, 12)}…)`);
      doc.getElementById("allow").click();
      await wait(150);
      doc.getElementById("ack").click();
      await wait(20);
      check(!doc.getElementById("flash").disabled && /Modded Cycles OS 2\.0 via Elektron Model:Cycles/.test(text(doc, "summary")), "ready: " + text(doc, "summary"));
      doc.getElementById("flash").click();
      await untilSent(w);
      check(app.state.finished === "ok" && same(dev.received, f.raw) && dev.bad.length === 0
        && /after Chord come/.test(text(doc, "result")) && /SDVtg/.test(text(doc, "result")) && /MACRO/.test(text(doc, "result")) && /ACID/.test(text(doc, "result")),
        "fast: the OS reaches the machine byte for byte, then the added machines are named: " + text(doc, "result").slice(0, 120));
      doc.querySelector('.lang button[data-lang="fr"]').click();
      await wait(20);
      check(doc.getElementById("drop3-title").textContent === ST_NAME && text(doc, "file3-status").includes(`OS officiel Syntakt ${ST_VERSION} reconnu`)
        && /Firmware prêt : Modded Cycles OS 2\.0/.test(text(doc, "file-status")), "FR: loaded Syntakt file name kept, statuses translated");
      doc.querySelector('.lang button[data-lang="en"]').click();
      await wait(20);
      // a tweak whose writes or payload differ from the Python ones is refused (a new load: builds are cached per key)
      const tm = app.REF_MODS["tempo-max"].w, tg = app.REF_MODS["model-tg-st"].p;
      app.REF_MODS["tempo-max"].w = "0".repeat(64);
      app.loadOs(new Uint8Array(fs.readFileSync(REAL_OS)), "model-cycles_OS1.13.syx");
      await settle(w);
      check(!app.state.fw && /tempo-max : ecritures differentes de la reference/.test(app.state.fwError || ""),
        "a tweak whose writes differ from REF_MODS is refused: " + app.state.fwError);
      app.REF_MODS["tempo-max"].w = tm;
      app.REF_MODS["model-tg-st"].p = "0".repeat(64);
      app.loadOs(new Uint8Array(fs.readFileSync(REAL_OS)), "model-cycles_OS1.13.syx");
      await settle(w);
      check(!app.state.fw && /model-tg-st : charge utile differente de la reference/.test(app.state.fwError || ""),
        "a tweak whose payload differs from REF_MODS is refused: " + app.state.fwError);
      app.REF_MODS["model-tg-st"].p = tg;
      app.loadOs(new Uint8Array(fs.readFileSync(REAL_OS)), "model-cycles_OS1.13.syx");
      await settle(w);
      check(app.state.fw && app.state.fw.ref, "references restored: the OS builds again");
    }
    check(errors.length === 0, "no JS error with the real files " + (errors.length ? JSON.stringify(errors) : ""));
  }

  // 7. "Samples OS" tab with both official files
  if (REAL_OS && REAL_SMP && MAIN) {
    const env7 = await load();
    const { w, doc, errors, sent } = env7;
    const app = w.MCFlasherApp;
    const cyc = new Uint8Array(fs.readFileSync(REAL_OS)), smp = new Uint8Array(fs.readFileSync(REAL_SMP));
    doc.getElementById("tab-samples").click();
    await wait(20);
    check(!doc.getElementById("panel-samples").hidden && !doc.getElementById("drop2-wrap").hidden
      && /Load both official OS files/.test(text(doc, "h2s")), "Samples OS tab: panel, second drop zone, step 2 title");
    app.loadSamples(cyc, "model-cycles_OS1.13.syx");               // wrong file in the second zone
    await wait(20);
    check(/not the official Model:Samples OS/.test(text(doc, "file2-status")), "a Cycles file in the Samples zone is refused");
    app.loadOs(smp, "model-samples_OS1.13.syx");                   // wrong file in the first zone
    await settle(w);
    check(/first file must be the official/.test(text(doc, "file-status")) && /first file must be/.test(text(doc, "missing")),
      "a Samples file in the Cycles zone is refused for this tab");
    app.loadOs(cyc, "model-cycles_OS1.13.syx");
    app.loadSamples(smp, "model-samples_OS1.13.syx");
    await settle(w);
    const f = app.state.fw;
    const sha = f && w.MCBuilder.hex(w.MCBuilder.sha256(f.raw));
    check(f && f.kind === "samples" && sha === app.REF_SAMPLES_ON_CYCLES, "both files -> reference build (" + (sha || "").slice(0, 16) + ")");
    check(/Model:Samples OS for your Model:Cycles/.test(text(doc, "file-status")) && /recognised/.test(text(doc, "file2-status")),
      "status lines for both files");
    doc.getElementById("m-slow").click();
    doc.getElementById("allow").click();
    await wait(80);
    doc.getElementById("ack").click();
    await wait(20);
    check(/MIDI interface for the way back/.test(text(doc, "missing")) && doc.getElementById("flash").disabled,
      "flash blocked until the MIDI-interface box is ticked");
    doc.getElementById("samples-ack").click();
    await wait(20);
    check(!doc.getElementById("flash").disabled && /Model:Samples OS \(for Model:Cycles\)/.test(text(doc, "summary")), "then ready: " + text(doc, "summary"));
    doc.getElementById("tab-mods").click();
    await settle(w);
    check(app.state.fw === null && /Load the official Syntakt OS file/.test(text(doc, "missing")), "back to the OS tab: the Samples build is not sent, the OS asks for its Syntakt file");
    doc.getElementById("tab-samples").click();
    await settle(w);
    doc.getElementById("pace").value = "0";
    doc.getElementById("pace").dispatchEvent(new w.Event("input"));
    const n0 = sent.length;
    doc.getElementById("flash").click();
    for (let i = 0; i < 200 && app.state.sending; i++) await wait(50);
    check(sent.length - n0 === w.MCFlasher.splitMessages(app.state.fw.raw).length && /restarts as a Model:Samples/.test(text(doc, "result")),
      "full transfer + Samples message");
    noRest(w);
    doc.getElementById("m-fast").click();
    await wait(150);
    doc.getElementById("flash").click();
    await untilSent(w);
    check(app.state.finished === "ok" && same(env7.dev.received, app.state.fw.raw) && env7.dev.bad.length === 0
      && /restarts as a Model:Samples/.test(text(doc, "result")), "fast: the Samples OS build reaches the Model:Cycles byte for byte");
    doc.querySelector('.lang button[data-lang="fr"]').click();
    await wait(20);
    check(/OS Samples/.test(text(doc, "tab-samples")) && doc.getElementById("drop2-title").textContent === "model-samples_OS1.13.syx",
      "FR: tab translated, loaded file name kept");
    check(errors.length === 0, "no JS error in the Samples OS flow " + (errors.length ? JSON.stringify(errors) : ""));
  }

  // 7b. "Samples OS" tab, for a Model:Samples: the Cycles OS (notes/41), then its way back, over USB
  if (REAL_OS && REAL_SMP && MAIN) {
    const env = await load({ devName: "Elektron Model:Samples", device: { id: 25, name: "Model Samples" } });
    const { w, doc, errors } = env;
    const app = w.MCFlasherApp;
    const cyc = new Uint8Array(fs.readFileSync(REAL_OS)), smp = new Uint8Array(fs.readFileSync(REAL_SMP));
    doc.getElementById("tab-samples").click();
    doc.getElementById("smp-dir-smp").click();
    await wait(20);
    check(!doc.getElementById("smp-pane-smp").hidden && doc.getElementById("smp-pane-cyc").hidden
      && /Experimental/.test(text(doc, "smp-pane-smp")), "Model:Samples → Cycles OS: its own pane, tagged experimental");
    app.loadOs(cyc, "model-cycles_OS1.13.syx");
    app.loadSamples(smp, "model-samples_OS1.13.syx");
    await settle(w);
    let f = app.state.fw, sha = f && w.MCBuilder.hex(w.MCBuilder.sha256(f.raw));
    check(f && f.kind === "cos" && f.raw[4] === 0x0f && sha === app.REF_CYCLES_ON_SAMPLES,
      "both files -> Cycles OS for Model:Samples, reference build (" + (sha || "").slice(0, 16) + ")");
    doc.getElementById("allow").click();
    await wait(150);
    doc.getElementById("ack").click();
    await wait(20);
    check(/backup/.test(text(doc, "missing")) && doc.getElementById("flash").disabled, "flash blocked until the backup box is ticked");
    doc.getElementById("cos-ack").click();
    await wait(20);
    check(!doc.getElementById("flash").disabled && /Model:Cycles OS \(for Model:Samples\)/.test(text(doc, "summary")),
      "then ready: " + text(doc, "summary"));
    doc.getElementById("flash").click();
    await untilSent(w);
    check(app.state.finished === "ok" && same(env.dev.received, f.raw) && /restarts as a <b>Model:Cycles<\/b>|restarts as a Model:Cycles/.test(text(doc, "result")),
      "fast: the Cycles OS reaches the Model:Samples byte for byte");
    check(/Model:Samples screen/.test(text(doc, "result")), "after sending: confirm on the Model:Samples screen");

    // the machine now answers as a Model:Cycles: the way-there file is refused, the way back is accepted
    env.dev.id = 27;
    doc.getElementById("refresh").click();
    await wait(150);
    check(/nothing to install/.test(text(doc, "midi-status")) && doc.getElementById("flash").disabled,
      "way-there file vs a machine answering Model:Cycles: nothing sent");
    doc.getElementById("smp-dir-back").click();
    await settle(w);
    f = app.state.fw; sha = f && w.MCBuilder.hex(w.MCBuilder.sha256(f.raw));
    check(f && f.kind === "sback" && f.raw[4] === 0x11 && sha === app.REF_SAMPLES_BACK,
      "way back: official Samples OS in the Cycles packing, reference build (" + (sha || "").slice(0, 16) + ")");
    check(same(w.MCBuilder.unwrap(f.raw).stream, w.MCBuilder.unwrap(smp).stream), "way back: same content as the official Samples OS");
    await wait(150);
    check(!doc.getElementById("flash").disabled && /Model:Samples asks/.test(text(doc, "missing")),
      "way back: ready without an extra box: " + text(doc, "missing"));
    doc.getElementById("flash").click();
    await untilSent(w);
    check(app.state.finished === "ok" && same(env.dev.received, f.raw) && /own OS/.test(text(doc, "result")),
      "fast: the way back reaches the machine byte for byte");
    env.dev.id = 25;
    doc.getElementById("refresh").click();
    await wait(150);
    check(/nothing to bring back/.test(text(doc, "midi-status")), "way back vs a machine already on the Samples OS: nothing sent");
    check(errors.length === 0, "no JS error in the Model:Samples flow " + (errors.length ? JSON.stringify(errors) : ""));
  }

  // 7b-bis. Step 3 names the machine being flashed (the tab and machine chosen), and the port after the OS it runs
  {
    const { w, doc, errors } = await load({ devName: "Acme Synth" });
    const app = w.MCFlasherApp;
    noRest(w);
    doc.getElementById("allow").click();
    await wait(150);
    const seen = () => [text(doc, "flash"), text(doc, "midi-status"), doc.querySelector('[data-i18n-html="hf1"]').textContent,
      doc.querySelector('[data-i18n-html="hu3"]').textContent].join(" | ");
    check(/Flash the Model:Cycles/.test(seen()) && /Connect the Model:Cycles/.test(seen()) && /port named “Model:Cycles”/.test(seen())
      && !/Model:Samples/.test(seen()), "OS tab, Model:Cycles: step 3 names the Model:Cycles: " + text(doc, "midi-status"));
    for (const [m, port] of [["smp", "Model:Samples"], ["cos", "Model:Cycles"]]) {
      doc.getElementById("mach-" + m).click();
      await wait(20);
      check(/Flash the Model:Samples/.test(seen()) && /Connect the Model:Samples/.test(seen()) && /the Model:Samples/i.test(text(doc, "midi-status"))
        && !/the Model:Cycles/i.test(text(doc, "midi-status")) && new RegExp("port named “" + port + "”").test(seen()),
        `OS tab, ${m}: step 3 names the Model:Samples, port “${port}”: ` + seen());
    }
    app.setMode("samples");
    for (const [d, dev, port] of [["cyc", "Model:Cycles", "Model:Cycles"], ["smp", "Model:Samples", "Model:Samples"], ["back", "Model:Samples", "Model:Cycles"]]) {
      doc.getElementById("smp-dir-" + d).click();
      await wait(20);
      check(new RegExp("Flash the " + dev).test(seen()) && new RegExp("the " + dev, "i").test(text(doc, "midi-status"))
        && new RegExp("port named “" + port + "”").test(seen()), `Samples OS tab, ${d}: names the ${dev}, port “${port}”`);
    }
    app.applyLang("fr");
    await wait(20);
    check(/Flasher le Model:Samples/.test(text(doc, "flash")) && /le Model:Samples/i.test(text(doc, "midi-status")), "in French too: " + text(doc, "midi-status"));
    app.applyLang("en");
    app.setMode("mods");
    doc.getElementById("mach-cyc").click();
    await wait(20);
    check(/Flash the Model:Cycles/.test(seen()) && !errors.length, "back to the Model:Cycles, no JS error " + errors.join(" "));
  }

  // 7c. The OS on a Model:Samples (notes/57): always the Model:Cycles OS, packed for the machine. The MAIN OS is the
  // one of the Model:Cycles build (REF_MAINOS); the whole-file equality with tools/mods_for_samples.py is checked by
  // tools/emu/test_mods_for_samples.py.
  if (REAL_OS && REAL_SMP && REAL_ST && MAIN) {
    const env = await load({ devName: "Elektron Model:Samples", device: { id: 25, name: "Model Samples" } });
    const { w, doc, errors } = env;
    const app = w.MCFlasherApp;
    const key = w.MC_TWEAKS.os.key;
    noRest(w);
    const cyc = new Uint8Array(fs.readFileSync(REAL_OS)), smp = new Uint8Array(fs.readFileSync(REAL_SMP)), syn = new Uint8Array(fs.readFileSync(REAL_ST));
    check(app.state.machine === "cyc" && doc.getElementById("mach-pane").hidden && doc.getElementById("drop2-wrap").hidden
      && doc.getElementById("mach-cyc").getAttribute("aria-checked") === "true", "OS tab: Model:Cycles by default, no Samples pane");
    doc.getElementById("mach-smp").click();
    await wait(20);
    check(!doc.getElementById("mach-pane").hidden && /Tested/.test(text(doc, "mach-pane")) && !doc.getElementById("drop2-wrap").hidden
      && /Load both official OS files/.test(text(doc, "h2s")) && !doc.getElementById("mach-w-smp").hidden
      && doc.getElementById("mach-w-cos").hidden, "Model:Samples on its OS: pane tagged tested, second drop zone");
    app.loadOs(cyc, "model-cycles_OS1.13.syx");
    app.loadSyntakt(syn, ST_NAME);
    await settle(w);
    check(!app.state.fw && /official Model:Samples OS below/.test(text(doc, "file-status")), "no Samples file yet: asked for it");
    app.loadSamples(smp, "model-samples_OS1.13.syx");
    await settle(w);
    let f = app.state.fw;
    check(f && f.kind === "built" && f.machine === "smp" && f.raw[4] === 0x0f && f.ref && f.sha === app.REF_MAINOS[key]
      && f.name === "modded-cycles-os_2.0_for-samples_smp-os.syx",
      "the OS for a Model:Samples on its OS: same MAIN OS as the Model:Cycles build, Samples packing (" + (f ? f.name : "") + ")");
    check(/Packed for your Model:Samples \(on its own OS\)/.test(text(doc, "file-status")), "status line: " + text(doc, "file-status").slice(-60));
    doc.getElementById("allow").click();
    await wait(150);
    doc.getElementById("ack").click();
    await wait(20);
    check(/backup/.test(text(doc, "missing")) && doc.getElementById("flash").disabled, "flash blocked until the backup box is ticked");
    doc.getElementById("mach-ack").click();
    await wait(20);
    check(!doc.getElementById("flash").disabled && /\(for Model:Samples\)/.test(text(doc, "summary")) && /Model:Samples asks/.test(text(doc, "missing")),
      "then ready: " + text(doc, "summary"));
    doc.getElementById("flash").click();
    await untilSent(w);
    check(app.state.finished === "ok" && same(env.dev.received, f.raw) && /with your mods/.test(text(doc, "result")),
      "fast: the OS reaches the Model:Samples byte for byte");

    // now it answers as a Model:Cycles: the Samples-OS packing is refused, the Cycles-OS packing (a new version later) is sent
    env.dev.id = 27;
    doc.getElementById("refresh").click();
    await wait(150);
    check(/already on the Cycles OS/.test(text(doc, "midi-status")) && doc.getElementById("flash").disabled,
      "Samples-OS packing vs a machine answering Model:Cycles: nothing sent");
    doc.getElementById("mach-cos").click();
    await settle(w);
    f = app.state.fw;
    check(f && f.machine === "cos" && f.raw[4] === 0x11 && f.raw[8] === 0x0c && f.sha === app.REF_MAINOS[key] && !doc.getElementById("mach-w-cos").hidden
      && f.name === "modded-cycles-os_2.0_for-samples_cyc-os.syx",
      "Model:Samples already on the Cycles OS: Cycles packing with the Samples key (" + (f ? f.name : "") + ")");
    await wait(150);
    check(!doc.getElementById("flash").disabled, "ready for a machine answering Model:Cycles: " + text(doc, "missing"));
    doc.getElementById("flash").click();
    await untilSent(w);
    check(app.state.finished === "ok" && same(env.dev.received, f.raw), "fast: the new version reaches the machine byte for byte");
    env.dev.id = 25;
    doc.getElementById("refresh").click();
    await wait(150);
    check(/on its own OS/.test(text(doc, "midi-status")) && doc.getElementById("flash").disabled,
      "Cycles-OS packing vs a machine answering Model:Samples: nothing sent");

    // back to Model:Cycles: the usual build, and a machine answering Model:Samples is pointed to step 1
    doc.getElementById("mach-cyc").click();
    await settle(w);
    f = app.state.fw;
    check(f && !f.machine && f.raw[4] === 0x11 && f.sha === app.REF_MAINOS[key] && doc.getElementById("mach-pane").hidden
      && doc.getElementById("drop2-wrap").hidden && /choose it in step 1/.test(text(doc, "midi-status")),
      "Model:Cycles again: plain build; a Model:Samples answering is told to pick it in step 1");
    doc.querySelector('.lang button[data-lang="fr"]').click();
    doc.getElementById("mach-smp").click();
    await settle(w);
    check(/sous son OS/.test(text(doc, "mach-smp")) && /Des mods sur un Model:Samples/.test(text(doc, "mach-pane"))
      && /Emballé pour votre Model:Samples/.test(text(doc, "file-status")), "FR: machine picker and status translated");
    app.setMachine("cyc");                                         // remembered by the page: leave the default for the next sections
    check(errors.length === 0, "no JS error in the OS-on-Model:Samples flow " + (errors.length ? JSON.stringify(errors) : ""));
  }

  if (process.env.SMOKE_SEEN) {
    // tools/webflash_smoke.sh with SMOKE_JOBS: the coverage check over the parts (the OS is one firmware, built in part 0)
    const offered = REAL_OS && REAL_ST ? [JSON.parse(fs.readFileSync(path.join(__dirname, "..", "os.json"), "utf8")).tweaks.join("+")] : [];
    fs.writeFileSync(process.env.SMOKE_SEEN, JSON.stringify({ seen: seenKeys, offered }));
    console.log(`  (part ${SHARD_K + 1}/${SHARD_N}: ${seenKeys.length} firmware built)`);
  }
  console.log(fail ? `\nFAILED (${fail})` : "\nALL OK");
  process.exit(fail ? 1 : 0);
}
main();
