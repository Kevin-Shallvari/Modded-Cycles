"""Tables Echo Sound Works sur le moteur HOST : temps de préparation (étapes), place, rendus à écouter."""
import sys, pathlib, tempfile, numpy as np
sys.path[:0]=['tools','tools/emu','build/wt-proto']
import test_wavetable as W, gen_wavetable as GW, wt_chain as P
root=pathlib.Path('/home/kevin/Downloads/Echo+Sound+Works+-+Modular/Echo Sound Works - Modular')
out=pathlib.Path('build/wt-proto/esw'); out.mkdir(exist_ok=True)
for name in ("ESW - Pulsar.wav","ESW - Chimes.wav","ESW - 90's Super Saw.wav"):
    x=W.read_wav(root/name); fr=len(x)//2048; x=x[:fr*2048]
    with tempfile.TemporaryDirectory() as d:
        h=W.Host(pathlib.Path(d)); h.load(3,0xE5E5,x); h.tslot[0]=3
        h.knobs(note=48); h.block(trig=True)
        last=None; t=0
        pool=np.frombuffer(h.copies, dtype='<i2')
        for t in range(1,20000):
            h.tick()
            if t%64==0: h.block()
            if t%50==0:
                used=np.count_nonzero(pool[:])
                if used==last: break
                last=used
        print(f"{name}: {fr} trames, ~{t} étapes ({t*0.67/1000:.1f} s à un bloc par étape), {np.flatnonzero(pool).max()*2/1e6:.1f} Mo")
        # écoute : basse, SHAPE haut puis bas ; enveloppe de volume simple
        seq=[36,36,48,36,39,36,43,46]*2
        for shape in (120,20):
            y=[]
            for n in seq:
                h.knobs(note=n,color=64,shape=shape,decay=60)
                blk=[h.block(trig=(b==0)) for b in range(375)]
                z=np.concatenate(blk).astype(float); y.append(z*np.exp(-np.arange(len(z))/48000/0.15))
            P.write_wav(out/f"{name[6:-4].replace(' ','_')}_shape{shape}.wav", np.concatenate(y))
print(sorted(p.name for p in out.iterdir()))
