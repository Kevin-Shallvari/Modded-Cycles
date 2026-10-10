import sys, pathlib, tempfile, numpy as np
sys.path[:0]=['tools','tools/emu']
import test_wavetable as W
esw=pathlib.Path('/home/kevin/Downloads/Echo+Sound+Works+-+Modular/Echo Sound Works - Modular')
for name,f,note in (("Pulsar 256, note C2",esw/"ESW - Pulsar.wav",36),("Pulsar 256, note C5",esw/"ESW - Pulsar.wav",72),
                    ("KRC 64, note C2","build/wt-proto/table.wav",36)):
    x=W.read_wav(f); fr=min(256,len(x)//2048); x=x[:fr*2048]
    with tempfile.TemporaryDirectory() as d:
        h=W.Host(pathlib.Path(d)); h.load(3,0x77,x); h.tslot[0]=3
        h.knobs(note=note); h.block(trig=True)
        first=None
        for t in range(1,20000):
            h.tick()
            if t%64==0: h.block()
            r=h.lib.wt_ready(0)
            if r and first is None: first=t
            if r and r==h.lib.wt_ready(0) and t>first and bin(r).count('1')>=15: 
                full=t; break
        print(f"{name}: 1re passe (aigus + note jouée) après {first} étapes = {first*0.667:.0f} ms ; tout après {full*0.667/1000:.1f} s")
