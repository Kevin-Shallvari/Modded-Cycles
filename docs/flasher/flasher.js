/* Web MIDI flasher core for the Model:Cycles / Model:Samples.
 *
 * Pure logic, no DOM: verify a .syx (same checks as tools/mtlib/syx.py, byte for
 * byte — tools/webflash_check.js compares it against the Python), then send it
 * one of two ways:
 *  - fast: the USB protocol of Elektron Transfer (OS upgrade by 2 KB blocks, each
 *    acknowledged by the machine), as worked out by Elektroid
 *    (https://github.com/dagargo/elektroid, src/connectors/elektron.c);
 *  - classic: the raw .syx to CONFIG > UPGRADE, paced like tools/flash.py.
 * The user interface lives in app.js.
 *
 * NO firmware image is included: the user drops their own .syx.
 *
 * Wrapped in an IIFE: top-level declarations of classic <script>s are global and
 * would collide with builder.js.
 */
(function () {
"use strict";

const ELEKTRON = [0x00, 0x20, 0x3c];
const MSG_LEN = 128;
const CS_OFF = 126;
// product id -> [name, device byte, mask seed V, checksum base C0]
const PRODUCTS = {
  0x11: ["Model:Cycles", 0x0c, 0x3a, 0x22],
  0x0f: ["Model:Samples", 0x0a, 0x3c, 0x1e],
};
const DIN_BYTES_PER_SEC = 31250 / 10; // 8N1 on the MIDI wire
const DEFAULT_PACE = 1.4;

/* Split a .syx into F0..F7 messages (each one includes F0 and F7). */
function splitMessages(raw) {
  const msgs = [];
  let i = 0;
  while (true) {
    const a = raw.indexOf(0xf0, i);
    if (a < 0) break;
    const b = raw.indexOf(0xf7, a);
    if (b < 0) throw new Error(`unterminated SysEx at offset ${a}`);
    msgs.push(raw.subarray(a, b + 1));
    i = b + 1;
  }
  return msgs;
}

function maskByte(V, i) {
  return (V - i) & 0x3f;
}

/* Checksum of one message (mtlib.syx.checksum): over bytes 8..125. */
function packetChecksum(msg, V, C0) {
  let acc = 0;
  for (let i = 8; i < 126; i++) acc += msg[i] ^ maskByte(V, i);
  return (C0 - acc) & 0x7f;
}

function u21(b, o) {
  return (b[o] << 14) | (b[o + 1] << 7) | b[o + 2];
}

/* Verify the file like mtlib.syx.unwrap: structure and every checksum.
 * Returns { product, name, count, bytes, messages, wireMinutes }.
 * Throws an Error with a clear message at the first problem. */
function verify(raw) {
  const msgs = splitMessages(raw);
  if (msgs.length < 3) throw new Error("not an Elektron firmware file (too few SysEx messages)");
  const head = msgs[0];
  const tail = msgs[msgs.length - 1];
  const data = msgs.slice(1, -1);

  for (let k = 0; k < 3; k++) {
    if (head[1 + k] !== ELEKTRON[k] || tail[1 + k] !== ELEKTRON[k])
      throw new Error("not an Elektron file (header is not 00 20 3C)");
  }
  const prod = head[4];
  if (!(prod in PRODUCTS)) throw new Error(`unsupported product id 0x${prod.toString(16)}`);
  const [name, , V, C0] = PRODUCTS[prod];
  if (head[6] !== 0x7f || head[7] !== 0x01 || tail[6] !== 0x7f || tail[7] !== 0x02)
    throw new Error("start/end markers missing");

  const count = u21(head, 12);
  if (count !== data.length)
    throw new Error(`the header announces ${count} packets, ${data.length} found`);

  for (let n = 0; n < data.length; n++) {
    const m = data[n];
    if (m.length !== MSG_LEN)
      throw new Error(`packet ${n}: length ${m.length} (expected ${MSG_LEN})`);
    if (m[CS_OFF] !== packetChecksum(m, V, C0))
      throw new Error(`packet ${n}: bad checksum — the file is corrupted, do not flash it`);
  }

  const bytes = raw.length;
  const wireMinutes = bytes / DIN_BYTES_PER_SEC / 60;
  return { product: prod, name, count, bytes, messages: msgs.length, wireMinutes };
}

/* Expected transfer time in seconds for a given pace. */
function transferSeconds(raw, pace) {
  return (raw.length / DIN_BYTES_PER_SEC) * (Number.isFinite(pace) ? pace : DEFAULT_PACE);
}

/* Send every message of `raw` to a Web MIDI output, paced for a 31.25 kbaud wire.
 * opts = { pace, onProgress(done, total), isCancelled() }.
 * Resolves to { sent, total, cancelled, seconds }. */
async function sendSysex(output, raw, opts = {}) {
  const pv = opts.pace;
  const pace = Number.isFinite(pv) && pv >= 0 ? pv : DEFAULT_PACE;   // explicit 0 is honoured
  const msgs = splitMessages(raw);
  const t0 = Date.now();
  let n = 0;
  for (; n < msgs.length; n++) {
    if (opts.isCancelled && opts.isCancelled()) break;
    output.send(msgs[n]); // full message, F0..F7 included
    const delayMs = (pace * msgs[n].length) / DIN_BYTES_PER_SEC * 1000;
    if (delayMs > 0) await sleep(delayMs);
    if (opts.onProgress && (n % 50 === 0 || n === msgs.length - 1)) opts.onProgress(n + 1, msgs.length);
  }
  return { sent: n, total: msgs.length, cancelled: n < msgs.length, seconds: (Date.now() - t0) / 1000 };
}

// ---------------------------------------------------------------------------
// Fast path: the Elektron Transfer protocol over USB MIDI (notes/37).
// Each message is F0 00 20 3C 10 00 <payload packed 7 bits per byte> F7. Decoded payload:
// [0..1] sequence number (big-endian, one per request), [2..3] 0 in a request, the request's
// sequence in the response, [4] command (response: command | 0x80), then the body.
// ---------------------------------------------------------------------------
const XFER_HEADER = [0xf0, 0x00, 0x20, 0x3c, 0x10, 0x00];
const XFER_IDS = { 27: "Model:Cycles", 25: "Model:Samples" };   // ping answer [5] -> device
const XFER_PRODUCT = { 27: 0x11, 25: 0x0f };                    // device -> .syx product id it takes
const OS_BLOCK = 0x800;               // OS upgrade block (Elektroid OS_TRANSF_BLOCK_BYTES)
const REST_MS = 50;                   // pause after each acknowledged block (BE_REST_TIME_US)
const PING_TIMEOUT_MS = 1000;         // ELEKTRON_HANDSHAKE_TIMEOUT_MS
const XFER_TIMEOUT_MS = 8000;         // Elektroid waits 5 s (BE_SYSEX_TIMEOUT_MS); a bit more costs nothing

/* 8 bytes on the wire for every 7: a byte with the 7 high bits (first byte's in bit 6), then the
 * 7 bytes without them (elektron_encode_payload). */
function encode7(src) {
  const out = new Uint8Array(src.length + Math.ceil(src.length / 7));
  for (let i = 0, j = 0; j < src.length; i += 8, j += 7) {
    let hi = 0;
    for (let k = 0; k < 7; k++) {
      hi <<= 1;
      if (j + k < src.length) {
        if (src[j + k] & 0x80) hi |= 1;
        out[i + k + 1] = src[j + k] & 0x7f;
      }
    }
    out[i] = hi;
  }
  return out;
}

function decode7(src) {
  const out = new Uint8Array(src.length - Math.ceil(src.length / 8));
  for (let i = 0, j = 0; i < src.length; i += 8, j += 7) {
    for (let k = 0, bit = 0x40; k < 7 && i + k + 1 < src.length; k++, bit >>= 1)
      out[j + k] = src[i + k + 1] | (src[i] & bit ? 0x80 : 0);
  }
  return out;
}

let CRC_TABLE = null;
/* zlib's crc32(crc, buf, len). The machine wants crc32(0xffffffff, block) (elektron_crc). */
function crc32(data, crc = 0) {
  if (!CRC_TABLE) {
    CRC_TABLE = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      CRC_TABLE[n] = c >>> 0;
    }
  }
  let c = ~crc >>> 0;
  for (let i = 0; i < data.length; i++) c = CRC_TABLE[(c ^ data[i]) & 0xff] ^ (c >>> 8);
  return ~c >>> 0;
}

/* Whole SysEx message for a decoded payload. */
function xferFrame(payload) {
  const enc = encode7(payload);
  const out = new Uint8Array(XFER_HEADER.length + enc.length + 1);
  out.set(XFER_HEADER, 0);
  out.set(enc, XFER_HEADER.length);
  out[out.length - 1] = 0xf7;
  return out;
}

/* Decoded payload of a received message, or null if it is not a Transfer-protocol message. */
function xferParse(raw) {
  if (!raw || raw.length < 12 || raw[raw.length - 1] !== 0xf7) return null;
  for (let k = 0; k < XFER_HEADER.length; k++) if (raw[k] !== XFER_HEADER[k]) return null;
  return decode7(raw.subarray(XFER_HEADER.length, raw.length - 1));
}

/* NUL-terminated string at offset `o` of a decoded payload. */
function xferString(msg, o) {
  let s = "";
  for (let i = o; i < msg.length && msg[i]; i++) s += String.fromCharCode(msg[i]);
  return s;
}

function be32(v) {
  return [(v >>> 24) & 0xff, (v >>> 16) & 0xff, (v >>> 8) & 0xff, v & 0xff];
}

class XferError extends Error {
  constructor(code, detail) {
    super(detail ? `${code}: ${detail}` : code);
    this.code = code;             // "busy" | "timeout" | "gone" | "refused" | "write" | "mismatch"
    this.detail = detail || "";
  }
}

/* A request/response channel on a Web MIDI input + output pair (elektron_tx_and_rx): one request
 * at a time; its response echoes its sequence number and command, other messages are skipped. */
async function xferOpen(input, output) {
  try {
    if (input.open) await input.open();
    if (output.open) await output.open();
  } catch (e) {
    throw new XferError("busy", e && e.message ? e.message : String(e));
  }
  let seq = 0;
  let waiter = null;
  // Elektroid gives up on a matching sequence of the wrong type; skipping it instead only matters
  // if another program talks to the machine at the same time (macOS shares ports): the timeout
  // still catches a machine that doesn't answer.
  const onMessage = (ev) => {
    const msg = waiter && xferParse(ev.data);
    if (!msg || msg.length < 6 || ((msg[2] << 8) | msg[3]) !== waiter.seq || msg[4] !== waiter.type) return;
    const w = waiter;
    waiter = null;
    clearTimeout(w.timer);
    w.resolve(msg);
  };
  input.addEventListener("midimessage", onMessage);
  return {
    request(body, timeoutMs = XFER_TIMEOUT_MS) {
      if (waiter) return Promise.reject(new Error("one request at a time"));
      const s = seq;
      seq = (seq + 1) & 0xffff;
      const payload = new Uint8Array(4 + body.length);
      payload[0] = s >> 8;
      payload[1] = s & 0xff;
      payload.set(body, 4);
      return new Promise((resolve, reject) => {
        waiter = { seq: s, type: body[0] | 0x80, resolve, reject,
          timer: setTimeout(() => { waiter = null; reject(new XferError("timeout")); }, timeoutMs) };
        try {
          output.send(xferFrame(payload));
        } catch (e) {
          clearTimeout(waiter.timer);
          waiter = null;
          reject(new XferError("gone", e && e.message ? e.message : String(e)));
        }
      });
    },
    close() {
      input.removeEventListener("midimessage", onMessage);
      if (waiter) { clearTimeout(waiter.timer); waiter.reject(new XferError("gone")); waiter = null; }
      try { if (input.close) input.close(); } catch (e) { /* already closed */ }
      try { if (output.close) output.close(); } catch (e) { /* already closed */ }
    },
  };
}

/* Who is on the other end (elektron_handshake): { id, device, name, version }.
 * device is "Model:Cycles", "Model:Samples" or null for another Elektron machine. */
async function xferIdentify(session) {
  const ping = await session.request([0x01], PING_TIMEOUT_MS);
  const id = ping[5];
  const name = ping.length > 7 ? xferString(ping, 7 + ping[6]) : "";
  await sleep(REST_MS);
  const ver = await session.request([0x02]);
  await sleep(REST_MS);
  return { id, device: XFER_IDS[id] || null, product: XFER_PRODUCT[id] || null, name, version: xferString(ver, 10) };
}

/* Upload a whole .syx as an OS upgrade (elektron_upgrade_os): the machine checks each block's
 * CRC, then asks on its screen to confirm the update.
 * opts = { onProgress(done, total), isCancelled(), restMs }.
 * Resolves to { sent, total, cancelled, seconds, blocks }; throws an XferError if the machine
 * refuses or stops answering. */
async function upgradeFast(session, raw, opts = {}) {
  const rest = Number.isFinite(opts.restMs) ? opts.restMs : REST_MS;
  const t0 = Date.now();
  const start = [0x50, ...be32(raw.length).reverse(), 0x73, 0x79, 0x73, 0x65, 0x78, 0x00, 0x01];  // size little-endian, "sysex\0", 1
  const r0 = await session.request(start);
  if (r0[5] !== 0) throw new XferError("refused", xferString(r0, 6));
  let offset = 0, blocks = 0;
  while (offset < raw.length) {
    if (opts.isCancelled && opts.isCancelled())
      return { sent: offset, total: raw.length, cancelled: true, seconds: (Date.now() - t0) / 1000, blocks };
    const len = Math.min(OS_BLOCK, raw.length - offset);
    const block = raw.subarray(offset, offset + len);
    const body = new Uint8Array(13 + len);
    body.set([0x51, ...be32(crc32(block, 0xffffffff)), ...be32(len), ...be32(offset)], 0);
    body.set(block, 13);
    const r = await session.request(body);
    offset += len;
    blocks++;
    if (opts.onProgress) opts.onProgress(offset, raw.length);
    const op = (r[9] << 24) >> 24;              // signed, as in Elektroid: 0 more, 1 done, > 1 error
    if (op === 1) break;
    if (op > 1) throw new XferError("write", xferString(r, 6));
    if (rest > 0) await sleep(rest);
  }
  return { sent: offset, total: raw.length, cancelled: false, seconds: (Date.now() - t0) / 1000, blocks };
}

/* Rough fast transfer time in seconds: per block, the pause plus about 15 ms for the message and
 * the machine's answer over USB (a real Model:Cycles took 33 s for a whole modded firmware, notes/37).
 * The page shows the measured pace once it runs. */
function fastSeconds(raw) {
  return Math.ceil(raw.length / OS_BLOCK) * (REST_MS + 15) / 1000;
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

// ---------------------------------------------------------------------------
// Sample / file transfer over the same Transfer protocol (notes/53). The Wave machine reads its tables from the
// +Drive, where they sit as Model:Samples "sample" files, so the machine must answer id 25 (Wave's SMP
// identity, switched by setSmpMode, notes/55). Commands, bodies and the 64-byte header come from Elektroid's
// src/connectors/elektron.c (FS_SAMPLE_*); numbers in a body are big-endian.
// ---------------------------------------------------------------------------
const DATA_BLOCK = 0x2000;             // DATA_TRANSF_BLOCK_BYTES
const ALSA_BLOCK = 0x800;              // Chrome on Linux / ChromeOS (ALSA) loses 8 KB SysEx (notes/53 §12)

/* Upload block size for this browser: 8 KB as Elektroid, 2 KB where Web MIDI goes through ALSA. */
function sampleBlock() {
  const nav = typeof navigator !== "undefined" ? navigator : null;
  const p = nav ? ((nav.userAgentData && nav.userAgentData.platform) || nav.platform || nav.userAgent || "") : "";
  return /linux|chrome ?os|cros/i.test(p) ? ALSA_BLOCK : DATA_BLOCK;
}
const SAMPLE_HEADER_LEN = 64;          // struct elektron_sample_header
const ELEKTRON_SAMPLE_RATE = 48000;

function be32(v) { return [(v >>> 24) & 0xff, (v >>> 16) & 0xff, (v >>> 8) & 0xff, v & 0xff]; }
function u32be(b, o) { return ((b[o] << 24) | (b[o + 1] << 16) | (b[o + 2] << 8) | b[o + 3]) >>> 0; }

/* cp1252 (Latin-1) path, NUL-terminated. */
function pathBytes(path) {
  const out = [];
  for (let i = 0; i < path.length; i++) out.push(path.charCodeAt(i) & 0xff);
  out.push(0);
  return out;
}

/* List a folder (0x10): [{ hash, size, writeProtected, type, name }]. type 1 = directory. */
async function sampleReadDir(session, path) {
  const msg = await session.request([0x10, ...pathBytes(path)]);
  const out = [];
  let p = 5;
  while (p + 10 <= msg.length) {
    const hash = u32be(msg, p); p += 4;
    const size = u32be(msg, p); p += 4;
    const writeProtected = msg[p]; p += 1;
    const type = msg[p]; p += 1;
    let name = "";
    while (p < msg.length && msg[p]) { name += String.fromCharCode(msg[p]); p++; }
    p += 1;
    out.push({ hash, size, writeProtected, type, name });
  }
  return out;
}

/* Create a folder (0x11). true if created, false if it already existed (harmless). */
async function sampleMakeDir(session, path) {
  const msg = await session.request([0x11, ...pathBytes(path)]);
  return msg[5] === 1;
}

/* Upload mono 16-bit samples (Int16Array) to `path` on the sample filesystem. Elektroid's
 * elektron_upload_sample: open writer, 8 KB blocks (the first carries the 64-byte header), close writer.
 * opts.blockBytes (sampleBlock() by default): each write carries its byte offset in the file.
 * Pacing: starts at opts.restMs (0 by default), then backs off (opts.stepMs, up to opts.maxRestMs) and
 * resends the block whenever one is refused or times out (opts.maxRetry) — the ack already gates the flow,
 * the pause is only a margin. opts.onSpeed(s) reports each block's round-trip. */
async function uploadSample(session, path, samples, opts = {}) {
  const pcmLen = samples.length * 2;
  const total = pcmLen + SAMPLE_HEADER_LEN;
  const t0 = Date.now();
  const maxRetry = Number.isFinite(opts.maxRetry) ? opts.maxRetry : 5;
  const step = Number.isFinite(opts.stepMs) ? opts.stepMs : 10;
  const maxRest = Number.isFinite(opts.maxRestMs) ? opts.maxRestMs : 200;
  let rest = Number.isFinite(opts.restMs) ? opts.restMs : 0;
  const blockBytes = Number.isFinite(opts.blockBytes) && opts.blockBytes > SAMPLE_HEADER_LEN ? opts.blockBytes : sampleBlock();

  const header = new Uint8Array(SAMPLE_HEADER_LEN);
  const hv = new DataView(header.buffer);
  hv.setUint8(0, 0);                            // type
  hv.setUint8(1, 0);                            // stereo: 0 = mono
  hv.setUint32(4, pcmLen, false);               // size (bytes of PCM)
  hv.setUint32(8, ELEKTRON_SAMPLE_RATE, false); // rate
  hv.setUint32(12, 0, false);                   // loop start
  hv.setUint32(16, 0, false);                   // loop end
  hv.setUint8(20, 0x7f);                        // loop type: none

  const r0 = await session.request([0x40, ...be32(total), ...pathBytes(path)]);
  if (r0[5] !== 1) throw new XferError("refused", xferString(r0, 6));
  const id = u32be(r0, 6);

  let sent = 0, seq = 0, pos = 0, blockMs = 0, retries = 0;
  for (;;) {
    const block = [];
    let consumed = 0;
    if (seq === 0) { for (let i = 0; i < SAMPLE_HEADER_LEN; i++) block.push(header[i]); consumed += SAMPLE_HEADER_LEN; }
    let n = Math.min(blockBytes - consumed, pcmLen - sent);
    n -= n & 1;                                 // whole 16-bit samples
    for (let i = 0; i < n; i += 2) {
      const v = samples[(sent + i) >> 1];       // 16-bit big-endian on the wire
      block.push((v >> 8) & 0xff, v & 0xff);
    }
    consumed += n;

    const bt = performance.now();
    let r;
    try {
      r = await session.request([0x42, ...be32(id), ...be32(consumed), ...be32(pos), ...block]);
    } catch (e) {
      if (retries++ < maxRetry) { rest = Math.min(maxRest, Math.max(rest + step, Math.round(blockMs) + step)); if (opts.onRetry) opts.onRetry({ blockMs, rest, tries: retries, reason: "timeout" }); continue; }
      throw e;
    }
    blockMs = performance.now() - bt;
    if (r[5] !== 1) {
      if (retries++ < maxRetry) { rest = Math.min(maxRest, Math.max(rest + step, Math.round(blockMs) + step)); if (opts.onRetry) opts.onRetry({ blockMs, rest, tries: retries, reason: "refused" }); continue; }
      throw new XferError("write", xferString(r, 6));
    }
    sent += n; seq++; pos += consumed;
    if (opts.onProgress) opts.onProgress(sent, pcmLen);
    if (opts.onSpeed) opts.onSpeed({ sent, total: pcmLen, blockMs, rest, blocks: seq, seconds: (Date.now() - t0) / 1000 });
    if (sent >= pcmLen) break;
    if (rest > 0) await sleep(rest);
  }

  const rc = await session.request([0x41, ...be32(id), ...be32(total)]);
  if (rc[5] !== 1) throw new XferError("close", xferString(rc, 6));
  return { bytes: total, blocks: seq, seconds: (Date.now() - t0) / 1000, rest };
}

/* Wave's identity switch (notes/55): F0 00 20 3C 0F 00 <m> F7, 1 = Model:Samples, 0 = Model:Cycles. No reply;
 * resolves to the new xferIdentify answer. Not kept across a restart (back to Model:Cycles). */
function smpModeMessage(on) {
  return new Uint8Array([0xf0, 0x00, 0x20, 0x3c, 0x0f, 0x00, on ? 1 : 0, 0xf7]);
}
async function setSmpMode(session, output, on) {
  output.send(smpModeMessage(on));
  await sleep(REST_MS);
  return xferIdentify(session);
}

const API = { splitMessages, verify, packetChecksum, transferSeconds, sendSysex,
              PRODUCTS, DEFAULT_PACE, DIN_BYTES_PER_SEC,
              encode7, decode7, crc32, xferFrame, xferParse, xferString, xferOpen, xferIdentify, upgradeFast,
              fastSeconds, XferError, XFER_IDS, XFER_PRODUCT, OS_BLOCK,
              DATA_BLOCK, ALSA_BLOCK, sampleBlock, SAMPLE_HEADER_LEN, ELEKTRON_SAMPLE_RATE, be32, pathBytes, sampleReadDir, sampleMakeDir, uploadSample,
              smpModeMessage, setSmpMode };
if (typeof module !== "undefined" && module.exports) module.exports = API;
if (typeof window !== "undefined") window.MCFlasher = API;
})();
