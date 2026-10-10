import sys, json, struct, numpy as np
sys.path[:0]=['tools','tools/emu']
import test_wavetable as W, build, gen_wavetable as GW, mcengine as E, test_model_tg as TM, test_sdvintage as T
stock=T.main_os_from_syx('firmware/model-cycles_OS1.13.syx')
tg_tw=json.load(open(W.DEV/'30-model-tg-st.json')); wt=json.load(open(W.DEV/'36-wavetable-tg.json'))
tws=[tg_tw,wt]; p,_=build.apply_writes(stock,tws); pl,_=build.build_payload(tws,stock,None); img=bytes(p)+pl
pay=int(wt['append']['dest'],16); rt=build.payload_runtime(wt,stock,None)
sym={k:int(v,16) for k,v in wt['symbols'].items()}; tg={k:int(v,16) for k,v in tg_tw['symbols'].items()}
table=W.read_wav("/home/kevin/Downloads/Echo Sound Works - 48k (not resampled)/ESW - Pulsar.wav")
def engine():
    e=TM.engine(img,end=W.BASE+len(stock)+tg_tw['append']['size'],payload=(pay,rt)); e.uc.mem_map(GW.COPIES_AT,0x01800000)
    for t in range(1,6): e.uc.mem_write(E.VOICE0+t*E.VSTRIDE,struct.pack('>II',9,9))
    pcm=np.clip(np.round(table*32767),-32768,32767).astype('>i2').tobytes(); e.uc.mem_write(W.PCM,bytes(64)+pcm)
    w32=lambda a,v:e.uc.mem_write(a,struct.pack('>I',v&0xffffffff))
    for k,v in ((0,W.H),(256,W.PCM),(512,len(table))): w32(tg['slot_hash']+k+4*W.SLOT,v)
    for t in range(6): w32(sym['tg_track_slot']+4*t,W.SLOT if t==0 else -1); w32(sym['tg_track_pend']+4*t,-1)
    return e
def note(color=40, fenv=64, epos=0, blocks=400):
    e=engine()
    e.uc.mem_write(E.PARAMS+0xe+0x36, struct.pack('>h', epos<<8))      # Env Pos (MACHINE tenue + COLOR), k = 27
    e.set(0,machine=7,note=48,pitch=64,color=color,shape=fenv,sweep=70,contour=0,punch=0,gate=0,finetune=64,decay=60)
    return np.concatenate([e.block(1 if b==0 else 0)[0] for b in range(blocks)]).astype(float)
def bright(x):   # centroïde (Hz) de 50 ms
    S=np.abs(np.fft.rfft(x*np.hanning(len(x)))); f=np.fft.rfftfreq(len(x),1/48000); return (S*f).sum()/S.sum()
def shape_of(x): # forme d'onde normalisée d'un cycle (130.8 Hz) : pour comparer les positions
    seg=x[:367*6]; return seg/ (np.abs(seg).max()+1e-9)
seg=lambda x,a: x[int(a*48000):int(a*48000)+2400]
a=b=None
#-shape_of(seg(b,0.15))).mean()
#print(f"COLOR 10 vs 110 : écart de forme {d:.2f} (0 = identiques), clarté {bright(seg(a,0.15)):.0f} vs {bright(seg(b,0.15)):.0f} Hz")
for ep in ():
    x=note(epos=ep)
    d=np.abs(shape_of(seg(x,0.0))-shape_of(seg(x,0.2))).mean()
    print(f"Env Pos {ep:3d} : forme début vs fin de note, écart {d:.2f}")
for fe in ():
    x=note(fenv=fe)
    print(f"Filt Env (SHAPE) {fe:3d} : clarté début {bright(seg(x,0.0)):.0f} Hz -> fin {bright(seg(x,0.2)):.0f} Hz")
def spec(x):
    S=np.abs(np.fft.rfft(x*np.hanning(len(x))))[:400]; return S/np.linalg.norm(S)
x0=note(epos=0,blocks=1600); x1=note(epos=100,blocks=1600)
for t in (0.01,0.05,0.15,0.4,0.9):
    print(f"t = {t*1000:3.0f} ms : Env Pos 100 vs 0, écart des spectres {np.abs(spec(seg(x1,t))-spec(seg(x0,t))).sum():.2f}")
