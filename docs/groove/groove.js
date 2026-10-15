/* Model:Groove — page « 8 track M:C ».
 *
 * Une seule chose : construire la ligne dérivée (56-groove-8tracks + 57-groove-patterns) à
 * partir du .syx OFFICIEL de l'utilisateur, vérifier le MAIN OS, et l'envoyer par USB.
 *
 * Rien n'est dupliqué : la construction vient de ../flasher/builder.js (window.MCBuilder) et
 * l'envoi de ../flasher/flasher.js (window.MCFlasher) — les mêmes que la page des mods.
 *
 * Sur les ports MIDI : on LISTE ce que le navigateur voit et on laisse CHOISIR, comme la page
 * des mods. Filtrer par nom en aveugle cache le diagnostic : si rien n'est trouvé, on ne sait
 * pas si c'est le port, le câble, le pilote ou le nom.
 */
(function () {
  "use strict";

  var G = window.MC_GROOVE;
  var $ = function (id) { return document.getElementById(id); };
  var state = { raw: null, built: null, midi: null, cancel: false, sending: false };

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
      $("download").disabled = true;
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
      $("download").disabled = false;
    } catch (e) {
      state.built = null;
      say($("build-status"),
          "REFUSED — " + (e.message || e) +
          ". The build did not match the expected MAIN OS, so nothing will be sent.",
          "is-bad");
      $("build").disabled = false;
    }
  }

  /* ---- 3a. les ports MIDI, listés -------------------------------------------- */

  function isDevicePort(name) { return /model\s*[:_-]?\s*(cycles|samples)/i.test(name || ""); }

  function portList(access) {
    var outs = [], ins = [];
    access.outputs.forEach(function (p) { outs.push(p); });
    access.inputs.forEach(function (p) { ins.push(p); });
    return { outs: outs, ins: ins };
  }

  function refreshPorts() {
    if (!navigator.requestMIDIAccess) {
      say($("port-status"), "This browser has no Web MIDI. Use Chrome or Edge.", "is-bad");
      return;
    }
    say($("port-status"), "Asking the browser for MIDI…", "is-busy");
    navigator.requestMIDIAccess({ sysex: true }).then(function (access) {
      state.midi = access;
      var l = portList(access);
      var sel = $("port");
      sel.innerHTML = "";
      var ph = document.createElement("option");
      ph.value = "";
      ph.textContent = l.outs.length ? "— choose a port —" : "— no MIDI output found —";
      sel.appendChild(ph);

      var auto = null, deviceCount = 0;
      l.outs.forEach(function (p) {
        var o = document.createElement("option");
        o.value = p.id;
        o.textContent = (p.name || "?") + (p.manufacturer ? "  [" + p.manufacturer + "]" : "");
        if (isDevicePort(p.name)) { deviceCount++; auto = p.id; o.textContent += "   ← Model:Cycles"; }
        sel.appendChild(o);
      });
      if (deviceCount === 1) sel.value = auto;
      $("refresh").hidden = false;

      var msg = l.outs.length + " output port(s), " + l.ins.length + " input(s) seen by the browser.";
      if (!l.outs.length) {
        msg += " Nothing at all: check the USB cable, the driver, and that the machine is on.";
      } else if (!deviceCount) {
        msg += " None of them is named like a Model:Cycles — pick the one your machine is on and try; " +
               "the name is shown so you can tell.";
      }
      say($("port-status"), msg, l.outs.length ? "is-ok" : "is-bad");
    }).catch(function (e) {
      say($("port-status"),
          "MIDI access was refused or failed: " + (e.message || e) +
          ". Chrome asks for permission on the first click — allow it, then press Refresh.", "is-bad");
    });
  }

  function inputFor(out, ins) {
    var name = (out.name || "").trim();
    var dev = ins.filter(function (i) { return isDevicePort(i.name); });
    return ins.find(function (i) { return (i.name || "").trim() === name; })
        || ins.find(function (i) { return i.name && name && (i.name.indexOf(name) >= 0 || name.indexOf(i.name) >= 0); })
        || (isDevicePort(name) && dev.length === 1 ? dev[0] : null);
  }

  /* ---- 3b. l'envoi ------------------------------------------------------------ */

  function send() {
    if (!state.built) return;
    if (!state.midi) { say($("send-status"), "Press Refresh ports first.", "is-bad"); return; }
    var id = $("port").value;
    if (!id) { say($("send-status"), "Choose a port first — the list is above.", "is-bad"); return; }

    var out = null;
    state.midi.outputs.forEach(function (p) { if (p.id === id) out = p; });
    if (!out) { say($("send-status"), "That port has disappeared. Press Refresh ports.", "is-bad"); return; }

    var l = portList(state.midi);
    var inp = inputFor(out, l.ins);
    if (!inp) {
      say($("send-status"),
          "Found the output “" + (out.name || "?") + "” but no matching MIDI input to listen to. " +
          "The fast method needs both. Check the cable and press Refresh ports.",
          "is-bad");
      return;
    }

    state.cancel = false;
    state.sending = true;
    $("send").disabled = true;
    $("cancel").hidden = false;
    var F = window.MCFlasher;
    say($("send-status"), "Connected to “" + (out.name || "?") + "”. Sending…", "is-busy");

    F.xferOpen(inp, out).then(function (session) {
      return F.upgradeFast(session, state.built.raw, {
        onProgress: function (done, total) {
          var pct = total ? Math.round(100 * done / total) : 0;
          say($("send-status"), "Sending… " + pct + "%", "is-busy");
        },
        isCancelled: function () { return state.cancel; }
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

  /* ---- 3c. le téléchargement, pour un outil SysEx ---------------------------- */

  function download() {
    if (!state.built) return;
    var blob = new Blob([state.built.raw], { type: "application/octet-stream" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "model-cycles_OS1.13_groove.syx";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
    say($("send-status"),
        "Downloaded model-cycles_OS1.13_groove.syx. On the machine press SETTINGS, open " +
        "CONFIG > UPGRADE, confirm YES, then send the file with any SysEx tool.", "is-ok");
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
  $("refresh").addEventListener("click", refreshPorts);
  $("send").addEventListener("click", send);
  $("download").addEventListener("click", download);
  $("cancel").addEventListener("click", function () { state.cancel = true; });

  if (!G || !G.tweaks || !G.mainos) {
    say($("build-status"), "tweaks.js is missing or incomplete — regenerate it with tools/gen_groove_page.py.", "is-bad");
  }
})();
