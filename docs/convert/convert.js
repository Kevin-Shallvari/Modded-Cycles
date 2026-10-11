/*
 * Convertisseur de tables d'ondes (notes/52) : un WAV mono de l'utilisateur -> un WAV 48 kHz mono que la machine
 * Wave lit directement (la table entiere, puis les copies adoucies par octave plus courtes). Aucun calcul de
 * copies sur la machine. Meme disposition que tools/wt_convert.py (reference).
 *
 * Expose WTConvert.bake(samples) -> Int16Array (samples : Float64Array mono, longueur multiple de 2048),
 * WTConvert.toWav(int16) -> Uint8Array, WTConvert.fromWav(arrayBuffer) -> Float64Array.
 */
(function (root) {
  "use strict";
  var N = 2048, LGN = 11, NCOPY = 11, FOLD_OK = 28000, OVER = 4;

  function hmax(c) { return Math.max(1, Math.floor(1024 * Math.pow(2, -c))); }
  function lgOf(c) { var l = 6; while (l < LGN && (1 << l) < OVER * hmax(c)) l++; return l; }

  var LG = [], OFF = [], S_TOTAL = N, c;
  for (c = 0; c < NCOPY; c++) LG[c] = lgOf(c);
  for (c = 0; c < NCOPY; c++) { OFF[c] = LG[c] === LGN ? 0 : S_TOTAL; if (LG[c] < LGN) S_TOTAL += 1 << LG[c]; }
  var SHORT = [];
  for (c = 0; c < NCOPY; c++) if (LG[c] < LGN) SHORT.push(c);

  /* FFT complexe radix-2 en place (re, im) ; inverse si inv. */
  function fft(re, im, inv) {
    var n = re.length, i, j, k, len, half, a, b, tr, ti, ur, ui, ang, wr, wi;
    for (i = 1, j = 0; i < n; i++) {
      var bit = n >> 1;
      for (; j & bit; bit >>= 1) j ^= bit;
      j ^= bit;
      if (i < j) { tr = re[i]; re[i] = re[j]; re[j] = tr; ti = im[i]; im[i] = im[j]; im[j] = ti; }
    }
    for (len = 2; len <= n; len <<= 1) {
      half = len >> 1;
      for (k = 0; k < half; k++) {
        ang = (inv ? 2 : -2) * Math.PI * k / len;
        wr = Math.cos(ang); wi = Math.sin(ang);
        for (i = 0; i < n; i += len) {
          a = i + k; b = a + half;
          ur = re[b] * wr - im[b] * wi; ui = re[b] * wi + im[b] * wr;
          tr = re[a] + ur; ti = im[a] + ui;
          re[b] = re[a] - ur; im[b] = im[a] - ui;
          re[a] = tr; im[a] = ti;
        }
      }
    }
    if (inv) for (i = 0; i < n; i++) { re[i] /= n; im[i] /= n; }
  }

  function bake(samples) {
    var F = Math.floor(samples.length / N), f, k, i;
    var frames = [], peak = 0;
    for (f = 0; f < F; f++) {
      var fr = new Float64Array(N), mean = 0;
      for (k = 0; k < N; k++) { var v = Math.round(samples[f * N + k] * 32767) / 32767; fr[k] = v; mean += v; }
      mean /= N;
      for (k = 0; k < N; k++) { fr[k] -= mean; var av = fr[k] < 0 ? -fr[k] : fr[k]; if (av > peak) peak = av; }
      frames.push(fr);
    }
    if (peak > 0) for (f = 0; f < F; f++) for (k = 0; k < N; k++) frames[f][k] = frames[f][k] / peak * 0.95;
    var out = [];
    for (f = 0; f < F; f++) { var raw = new Int16Array(N); for (k = 0; k < N; k++) raw[k] = Math.round(frames[f][k] * 32767); out.push(raw); }
    var specs = [];
    for (f = 0; f < F; f++) {
      var re = Float64Array.from(frames[f]), im = new Float64Array(N);
      fft(re, im, false);
      specs.push([re, im]);
    }
    for (i = 0; i < SHORT.length; i++) {
      var cc = SHORT[i], lg = LG[cc], m = 1 << lg, hm = hmax(cc);
      for (f = 0; f < F; f++) {
        var sre = new Float64Array(m), sim = new Float64Array(m), sp = specs[f];
        for (k = 0; k <= m / 2; k++) { sre[k] = k <= hm ? sp[0][k] : 0; sim[k] = k <= hm ? sp[1][k] : 0; }
        for (k = m / 2 + 1; k < m; k++) { sre[k] = sre[m - k]; sim[k] = -sim[m - k]; }
        fft(sre, sim, true);
        var cp = new Int16Array(m), sc = m / N * 32767;
        for (k = 0; k < m; k++) { var y = Math.round(sre[k] * sc); cp[k] = y > 32767 ? 32767 : y < -32768 ? -32768 : y; }
        out.push(cp);
      }
    }
    var total = 0;
    for (i = 0; i < out.length; i++) total += out[i].length;
    var flat = new Int16Array(total), at = 0;
    for (i = 0; i < out.length; i++) { flat.set(out[i], at); at += out[i].length; }
    return flat;
  }

  function fromWav(buf) {
    var d = new DataView(buf), u8 = new Uint8Array(buf), j = -1, i = -1, k;
    for (k = 0; k + 4 <= u8.length; k++) { if (d.getUint32(k, false) === 0x666d7420) j = k; if (d.getUint32(k, false) === 0x64617461) i = k; }
    if (j < 0 || i < 0) throw new Error("not a WAV");
    var fmt = d.getUint16(j + 8, true), ch = d.getUint16(j + 10, true), bits = d.getUint16(j + 22, true);
    var n = d.getUint32(i + 4, true), off = i + 8, x = new Float64Array(n / (bits / 8) / ch), m = 0;
    for (k = 0; k + ch * (bits / 8) <= n; k += ch * (bits / 8)) {
      var v;
      if (fmt === 3) v = d.getFloat32(off + k, true);
      else if (bits === 16) v = d.getInt16(off + k, true) / 32768;
      else if (bits === 24) { var b0 = u8[off + k], b1 = u8[off + k + 1], b2 = u8[off + k + 2]; v = ((b0 | b1 << 8 | b2 << 16) << 8 >> 8) / 8388608; }
      else v = d.getInt32(off + k, true) / 2147483648;
      x[m++] = v;
    }
    return x.subarray(0, m);
  }

  function toWav(int16) {
    var n = int16.length * 2, buf = new ArrayBuffer(44 + n), d = new DataView(buf), u8 = new Uint8Array(buf);
    function str(s, o) { for (var k = 0; k < s.length; k++) u8[o + k] = s.charCodeAt(k); }
    str("RIFF", 0); d.setUint32(4, 36 + n, true); str("WAVE", 8); str("fmt ", 12);
    d.setUint32(16, 16, true); d.setUint16(20, 1, true); d.setUint16(22, 1, true); d.setUint32(24, 48000, true);
    d.setUint32(28, 96000, true); d.setUint16(32, 2, true); d.setUint16(34, 16, true); str("data", 36);
    d.setUint32(40, n, true);
    for (var k = 0; k < int16.length; k++) d.setInt16(44 + 2 * k, int16[k], true);
    return u8;
  }

  /* ZIP sans compression (methode « store »), pour telecharger plusieurs tables d'un coup. */
  function crc32(buf) {
    var c, crc = 0xffffffff;
    for (var i = 0; i < buf.length; i++) {
      c = (crc ^ buf[i]) & 0xff;
      for (var k = 0; k < 8; k++) c = c & 1 ? (c >>> 1) ^ 0xEDB88320 : c >>> 1;
      crc = (crc >>> 8) ^ c;
    }
    return (crc ^ 0xffffffff) >>> 0;
  }
  function le(v, n) { var a = new Uint8Array(n); for (var i = 0; i < n; i++) a[i] = (v >>> (8 * i)) & 255; return a; }
  function cat(arrs) { var n = 0, i; for (i = 0; i < arrs.length; i++) n += arrs[i].length; var o = new Uint8Array(n), at = 0; for (i = 0; i < arrs.length; i++) { o.set(arrs[i], at); at += arrs[i].length; } return o; }
  function zipStore(files) {
    var enc = new TextEncoder(), parts = [], central = [], offset = 0;
    files.forEach(function (f) {
      var name = enc.encode(f.name), crc = crc32(f.data), sz = f.data.length;
      var head = [le(0x04034b50, 4), le(20, 2), le(0, 2), le(0, 2), le(0, 2), le(0, 2), le(crc, 4), le(sz, 4), le(sz, 4), le(name.length, 2), le(0, 2)];
      var local = cat(head.concat([name, f.data]));
      parts.push(local);
      var cd = [le(0x02014b50, 4), le(20, 2), le(20, 2), le(0, 2), le(0, 2), le(0, 2), le(0, 2), le(crc, 4), le(sz, 4), le(sz, 4), le(name.length, 2), le(0, 2), le(0, 2), le(0, 2), le(0, 2), le(0, 4), le(offset, 4)];
      central.push(cat(cd.concat([name])));
      offset += local.length;
    });
    var cdBytes = cat(central);
    var end = [le(0x06054b50, 4), le(0, 2), le(0, 2), le(files.length, 2), le(files.length, 2), le(cdBytes.length, 4), le(offset, 4), le(0, 2)];
    return cat(parts.concat([cdBytes, cat(end)]));
  }

  var api = { bake: bake, fromWav: fromWav, toWav: toWav, zipStore: zipStore, S_TOTAL: S_TOTAL, N: N, hmax: hmax, LG: LG, OFF: OFF, SHORT: SHORT };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.WTConvert = api;
})(typeof self !== "undefined" ? self : this);
