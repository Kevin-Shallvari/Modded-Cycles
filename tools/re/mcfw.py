"""Aides de rétro-ingénierie pour le MAIN OS 1.13 des Elektron Model (notes/54, 55).

Charge le MAIN OS (section 3 d'un `.syx` officiel), décode avec capstone le mode
M68K_040, et garde en mémoire les listings (les instructions EMAC que capstone 5.0
ne connaît pas ressortent en `dc.w`) :

    import mcfw
    mcfw.load_mainos('firmware/model-cycles_OS1.13.syx')
    mcfw.show(mcfw.disasm(0x400a7d4a, 0x400a7e6a))
    mcfw.xrefs(0x42308828)

Voir `tools/re/README.md` pour le détail et la convention d'adresses (VA = offset + 0x40000400).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # tools/ (mtlib)

from mtlib import aplib, container, syx  # noqa: E402

BASE = 0x40000400          # VA = offset dans la section 3 + BASE

_ldr = {}                  # état : image chargée, listings, empreintes


def load_mainos(path, want_sha=None):
    """Dépaquette la section 3 du `.syx` et la garde dans le module."""
    import hashlib
    with open(path, 'rb') as f:
        raw = f.read()
    stream, info = syx.unwrap(raw)
    parsed = container.parse(stream)
    s3 = next(s for s in parsed['sections'] if s['id'] == 3)
    data, ops = aplib.depack(stream[8 + s3['off']:8 + s3['off'] + s3['size']][:s3['size']])
    _ldr['data'] = data
    _ldr['sha'] = hashlib.sha256(data).hexdigest()
    if want_sha and not _ldr['sha'].startswith(want_sha):
        raise ValueError('section 3 : sha256 %s, attendu %s' % (_ldr['sha'], want_sha))
    print('section 3 : %d octets, sha256 %s' % (len(data), _ldr['sha']))
    return data


def _rd(va, n=4):
    return _ldr['data'][va - BASE: va - BASE + n]


def be(va, n):
    return int.from_bytes(_rd(va, n), 'big')


def u8(va):
    return _ldr['data'][va - BASE]


def u16(va):
    return be(va, 2)


def u32(va):
    return be(va, 4)


def _objdump(args):
    """m68k-linux-gnu-objdump, natif s'il existe, sinon via WSL Ubuntu (chemins /mnt)."""
    import shutil
    import subprocess
    exe = 'm68k-linux-gnu-objdump'
    native = shutil.which(exe)
    if native:
        return subprocess.run([native, *args], capture_output=True, text=True,
                              check=True).stdout
    # pas de toolchain natif : la dit sous WSL (binutils-m68k-linux-gnu)
    argv, paths = [], []
    for a in args:
        p = a.replace('\\', '/')
        if len(p) > 1 and p[1] == ':':         # C:/... -> /mnt/c/...
            p = '/mnt/' + p[0].lower() + p[2:]
        paths.append(p)
    return subprocess.run(['wsl', '-d', 'Ubuntu', '--', exe, *paths],
                          capture_output=True, text=True, check=True).stdout


def disasm(va, end=None, size=256, title=None):
    """Listing d'une fonction ; capstone bute sur les EMAC, alors repart au demi-mot
    suivant (les trous marqués `dc.w` : à ne pas prendre pour du code)."""
    if end is None:
        end = va + size
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_M68K_040)
    md.big_endian = True
    lines, cur = [], va
    while cur < end:
        out = list(md.disasm(bytes(_ldr['data'][cur - BASE:end - BASE]), cur))
        if out:
            for ins in out:
                lines.append('%08x  %-3s %s   ; %s' % (ins.address, ins.mnemonic,
                                                       ins.op_str, ins.bytes.hex()))
            cur = out[-1].address + out[-1].size
            continue
        lines.append('%08x  dc.w %04x   <<<' % (cur, u16(cur)))
        cur += 2
    _ldr[title or '%08x' % va] = lines
    return lines


def _parse_objdump(out):
    """Format de résultat de emac.disasm/tools/emu : {addr: (taille, mnémo, opérandes)}."""
    import re
    res = {}
    for line in out.splitlines():
        m = re.match(r'\s*([0-9a-f]+):\t([0-9a-f ]+)\t(\S+)\s*(.*)$', line)
        if m:
            res[int(m.group(1), 16)] = (len(m.group(2).replace(' ', '')) // 2,
                                        m.group(3), m.group(4).strip())
    return res


def bridge_emac():
    """Route le `emac.disasm` de tools/emu (utilisé par mcengine) via `_objdump`,
    pour que les bancs de mesure tournent même sans toolchain natif m68k."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'emu'))
    import emac
    emac.disasm = lambda binfile, base, start, stop, arch='m68k:isa-c:emac': _parse_objdump(
        _objdump(['-D', '-b', 'binary', '-m', arch,
                  '--adjust-vma=%#x' % base, '--start-address=%#x' % start,
                  '--stop-address=%#x' % stop, binfile]))


def emac_disasm(start, stop, arch='m68k:isa-c:emac'):
    """Désassemble les instructions EMAC (mac.l/msac.l…) du MAIN OS chargé, que
    capstone ne connaît pas : même format de résultat que tools/emu/emac.disasm."""
    import tempfile
    fd, path = tempfile.mkstemp(suffix='.bin')
    try:
        os.write(fd, _ldr['data'])
        os.close(fd)
        return _parse_objdump(_objdump(['-D', '-b', 'binary', '-m', arch,
                                        '--adjust-vma=%#x' % BASE,
                                        '--start-address=%#x' % start,
                                        '--stop-address=%#x' % stop, path]))
    finally:
        os.unlink(path)


def show(lines):
    for l in lines:
        print(l)


def xrefs(value, lo=0x40000400, hi=0x401d0000, width=4):
    """Occurrences littérales de `value` (32 bits par défaut) dans le MAIN OS."""
    pat = value.to_bytes(width, 'big')
    data = _ldr['data']
    hits, i = [], data.find(pat, lo - BASE, hi - BASE)
    while i >= 0:
        hits.append(BASE + i)
        i = data.find(pat, i + 1, hi - BASE)
    return hits
