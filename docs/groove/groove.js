/* Model:Groove — page « 8 track M:C ».
 *
 * Une seule chose : construire la ligne dérivée (56-groove-8tracks + 57-groove-patterns) à
 * partir du .syx OFFICIEL de l'utilisateur, vérifier le MAIN OS, et l'envoyer par USB.
 *
 * Rien n'est dupliqué : la construction vient de ../flasher/builder.js (window.MCBuilder) et
 * l'envoi de ../flasher/flasher.js (window.MCFlasher) — les mêmes que la page des mods.
 */
(function () {
  "use strict";

  var G = window.MC_GROOVE;
  var $ = function (id) { return document.getElementById(id); };
  var state = { raw: null, built: null, cancel: false, sending: false };

  function say(el, msg, cls) {
    el.textContent = msg;
    el.className = "status" + (cls ? " " + cls : "");
  }

  function hexPrefix(s, n) { return String(s || "").slice(0, n || 12); }

  /* ---- 1. le fichier officiel ------------------------------------------------ */

  function readFile(file) {
    var r = new FileReader();
    r.onload = function () {
      state.raw = new Uint8Array(r.result);
      state.built = null;
      $("send").disabled = true;
      try {
        var info = window.MCFlasher.verify(state.raw);
        say($("file-status"),
            "OK — " + info.name + " (OS " + info.version + "), " + state.raw.length + " bytes.",
            "is-ok");
        $("build").disabled = false;
      } catch (e) {
        state.raw = null;
        $("build").disabled = true;
        say($("file-status"), "This is not a valid Elektron OS file: " + (e.message || e), "is-bad");
      }
    };
    r.readAsArrayBuffer(file);
  }

  /* ---- 2. la construction, et le contrôle du MAIN OS ------------------------- */

  function build() {
    $("build").disabled = true;
    say($("build-status"), "Building…", "is-busy");
    try {
      var r = window.MCBuilder.build(state.raw, G.device, G.tweaks,
                                     { expectMainOsSha: G.mainos });
      state.built = r;
      say($("build-status"),
          "Built — MAIN OS " + hexPrefix(r.mainOsSha) + "…, " +
          r.patchedBytes + " bytes patched, " + r.raw.length + " bytes total. " +
          "It matches the expected hash, so it is the same firmware the command line produces.",
          "is-ok");
      $("send").disabled = false;
    } catch (e) {
      state.built = null;
      say($("build-status"),
          "REFUSED — " + (e.message || e) +
          ". The build did not match the expected MAIN OS, so nothing will be sent.",
          "is-bad");
      $("build").disabled = false;
    }
  }

  /* ---- 3. l'envoi ------------------------------------------------------------ */

  function isDevicePort(name) { return /model\s*[:_-]?\s*(cycles|samples)/i.test(name || ""); }

  function midiPorts() {
    return new Promise(function (res, rej) {
      if (!navigator.requestMIDIAccess) { rej(new Error("Web MIDI is not available in this browser.")); return; }
      navigator.requestMIDIAccess({ sysex: true }).then(function (access) {
        var out = null, inp = null;
        access.outputs.forEach(function (o) { if (!out && isDevicePort(o.name)) out = o; });
        if (out) access.inputs.forEach(function (i) { if (!inp && isDevicePort(i.name)) inp = i; });
        if (!out || !inp) { rej(new Error("No Model:Cycles found. Connect it by USB and power it on in the STARTUP MENU.")); return; }
        res({ out: out, inp: inp });
      }).catch(rej);
    });
  }

  function send() {
    if (!state.built) return;
    state.cancel = false;
    state.sending = true;
    $("send").disabled = true;
    $("cancel").hidden = false;
    var F = window.MCFlasher;
    say($("send-status"), "Looking for the machine…", "is-busy");

    midiPorts().then(function (p) {
      say($("send-status"), "Connected to “" + p.out.name + "”. Sending…", "is-busy");
      return F.xferOpen(p.inp, p.out).then(function (session) {
        return F.upgradeFast(session, state.built.raw, {
          onProgress: function (done, total) {
            var pct = total ? Math.round(100 * done / total) : 0;
            say($("send-status"), "Sending… " + pct + "%", "is-busy");
          },
          isCancelled: function () { return state.cancel; }
        });
      });
    }).then(function () {
      say($("send-status"),
          "Sent. The machine will reboot into Model:Groove. Remember: an original project is refused cleanly, and the STARTUP MENU restores the official OS.",
          "is-ok");
    }).catch(function (e) {
      say($("send-status"), "Failed: " + (e.message || e) + " — nothing was written.", "is-bad");
    }).then(function () {
      state.sending = false;
      $("cancel").hidden = true;
      $("send").disabled = false;
    });
  }

  /* ---- câblage --------------------------------------------------------------- */

  $("file").addEventListener("change", function (ev) {
    if (ev.target.files && ev.target.files[0]) readFile(ev.target.files[0]);
  });
  var drop = $("drop");
  drop.addEventListener("click", function () { $("file").click(); });
  drop.addEventListener("keydown", function (ev) {
    if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); $("file").click(); }
  });
  ["dragenter", "dragover"].forEach(function (t) {
    drop.addEventListener(t, function (ev) { ev.preventDefault(); drop.classList.add("over"); });
  });
  ["dragleave", "drop"].forEach(function (t) {
    drop.addEventListener(t, function (ev) { ev.preventDefault(); drop.classList.remove("over"); });
  });
  drop.addEventListener("drop", function (ev) {
    var f = ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0];
    if (f) readFile(f);
  });
  $("build").addEventListener("click", build);
  $("send").addEventListener("click", send);
  $("cancel").addEventListener("click", function () { state.cancel = true; });

  // la page doit dire si les donnees manquent (elle serait alors inutile)
  if (!G || !G.tweaks || !G.mainos) {
    say($("build-status"), "tweaks.js is missing or incomplete — regenerate it with tools/gen_groove_page.py.", "is-bad");
  }
})();
