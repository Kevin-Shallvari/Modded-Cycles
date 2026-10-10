import sys, pathlib, tempfile, numpy as np
sys.path[:0]=['tools','tools/emu','build/wt-proof']
import test_wavetable as W
def grit2(x):
    L=len(x); S=np.abs(np.fft.rfft(x*np.blackman(L)))**2; fr=np.fft.rfftfreq(L,1/48000)
    f0=fr[np.argmax(S*(fr<3000))]; h=fr/f0; near=np.abs(h-np.round(h))*f0<max(25,f0*0.012); aud=fr<20000
    return f0, 10*np.log10(S[aud&~near].sum()/S[aud].sum())
for frames in (8,64):
    with tempfile.TemporaryDirectory() as d:
        h=W.Host(pathlib.Path(d)); h.load(3,0x55,W.test_table(frames=frames)); h.tslot[0]=3
        def note(n):
            h.knobs(note=n,color=64); return np.concatenate([h.block(trig=True)]+[h.block() for b in range(199)]).astype(float)
        a=note(96)
        for t in range(1,4000):
            h.tick()
            if t%64==0: h.block()
        b=note(96)
        print(frames,"trames HOST : avant %.0f Hz %.0f dB ; après %.0f Hz %.0f dB"%(grit2(a[1280:])+grit2(b[1280:])))
