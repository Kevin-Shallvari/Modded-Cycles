"""A/B : table brute (standard) contre copies (anti-grit), même jeu, moteur HOST."""
import sys, pathlib, tempfile, numpy as np
sys.path[:0]=['tools','tools/emu','build/wt-proto']
import test_wavetable as W, wt_chain as P
esw=pathlib.Path('/home/kevin/Downloads/Echo+Sound+Works+-+Modular/Echo Sound Works - Modular')
tables={"Pulsar":esw/"ESW - Pulsar.wav","90s_Super_Saw":esw/"ESW - 90's Super Saw.wav",
        "Chimes":esw/"ESW - Chimes.wav","KRC_Random_64_6":pathlib.Path("build/wt-proto/table.wav")}
out=pathlib.Path('build/wt-proto/ab'); out.mkdir(exist_ok=True)
# basse, puis montée, puis mélodie aiguë
seq=[(n,0.25) for n in [36,36,48,36,43,46]]+[(n,0.18) for n in range(48,100,4)]+[(n,0.2) for n in [84,88,91,96,91,88,84,79,96,100,96,91]]
def play(h):
    y=[]
    for n,d in seq:
        h.knobs(note=n,color=40,shape=64,decay=127)
        z=np.concatenate([h.block(trig=(b==0)) for b in range(int(d*1500))]).astype(float)
        y.append(z*np.exp(-np.arange(len(z))/48000/0.25))
    return np.concatenate(y)
for name,f in tables.items():
    x=W.read_wav(f); fr=min(256,len(x)//2048); x=x[:fr*2048]
    with tempfile.TemporaryDirectory() as d:
        h=W.Host(pathlib.Path(d)); h.load(3,0xAB00+fr,x); h.tslot[0]=3
        std=play(h)
        for t in range(1,6000):
            h.tick()
            if t%64==0: h.block()
        ag=play(h)
    pk=max(np.abs(std).max(),np.abs(ag).max())
    P.write_wav(out/f"{name}_1_standard.wav", std/pk*np.abs(std).max())
    P.write_wav(out/f"{name}_2_anti-grit.wav", ag/pk*np.abs(ag).max())
print(sorted(p.name for p in out.iterdir()))
