import sys, json, struct, numpy as np
sys.path[:0]=['tools','tools/emu','build/wt-proto']
import test_wavetable as W, build, gen_wavetable as GW, mcengine as E, test_model_tg as TM, test_sdvintage as T, wt_chain as P
stock=T.main_os_from_syx('firmware/model-cycles_OS1.13.syx')
tg_tw=json.load(open(W.DEV/'30-model-tg-st.json')); wt=json.load(open(W.DEV/'36-wavetable-tg.json'))
tws=[tg_tw,wt]; p,_=build.apply_writes(stock,tws); pl,_=build.build_payload(tws,stock,None); img=bytes(p)+pl
pay=int(wt['append']['dest'],16); rt=build.payload_runtime(wt,stock,None)
sym={k:int(v,16) for k,v in wt['symbols'].items()}; tg={k:int(v,16) for k,v in tg_tw['symbols'].items()}
table=W.read_wav("/home/kevin/Downloads/Echo Sound Works - 48k (not resampled)/ESW - Pulsar.wav")
e=TM.engine(img,end=W.BASE+len(stock)+tg_tw['append']['size'],payload=(pay,rt)); e.uc.mem_map(GW.COPIES_AT,0x01800000)
for t in range(1,6): e.uc.mem_write(E.VOICE0+t*E.VSTRIDE,struct.pack('>II',9,9))
pcm=np.clip(np.round(table*32767),-32768,32767).astype('>i2').tobytes(); e.uc.mem_write(W.PCM,bytes(64)+pcm)
w32=lambda a,v:e.uc.mem_write(a,struct.pack('>I',v&0xffffffff))
for k,v in ((0,W.H),(256,W.PCM),(512,len(table))): w32(tg['slot_hash']+k+4*W.SLOT,v)
for t in range(6): w32(sym['tg_track_slot']+4*t,W.SLOT if t==0 else -1); w32(sym['tg_track_pend']+4*t,-1)
e.set(0,machine=7,note=48,pitch=64,color=40,shape=64,sweep=127,contour=0,punch=0,gate=0,finetune=64,decay=127)
x=np.concatenate([e.block(1 if b==0 else 0)[0] for b in range(6000)]).astype(float)
P.write_wav("build/wt-proto/fw/hold_shape64.wav",x)
seg=4800; cents=[]
for i in range(0,len(x)-seg,seg):
    S=np.abs(np.fft.rfft(x[i:i+seg]*np.hanning(seg))); f=np.fft.rfftfreq(seg,1/48000); cents.append((S*f).sum()/S.sum())
print("centroïde (Hz) toutes les 100 ms :",[int(c) for c in cents])
print("niveau (rms) :",[int(np.sqrt((x[i:i+seg]**2).mean())/1e5) for i in range(0,len(x)-seg,seg*4)])
