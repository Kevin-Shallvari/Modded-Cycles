"""Le firmware lit-il les copies ? Lectures pendant le rendu, avant / après les copies (Unicorn)."""
import sys, json, struct, numpy as np
sys.path[:0]=['tools','tools/emu']
import test_wavetable as W, build, gen_wavetable as GW, mcengine as E, test_model_tg as TM, test_sdvintage as T
from unicorn import UC_HOOK_MEM_READ
stock=T.main_os_from_syx('firmware/model-cycles_OS1.13.syx')
tg_tw=json.load(open(W.DEV/'30-model-tg-st.json')); wt=json.load(open(W.DEV/'36-wavetable-tg.json'))
tws=[tg_tw,wt]; p,_=build.apply_writes(stock,tws); pl,_=build.build_payload(tws,stock,None); img=bytes(p)+pl
pay=int(wt['append']['dest'],16); rt=build.payload_runtime(wt,stock,None)
sym={k:int(v,16) for k,v in wt['symbols'].items()}; tg={k:int(v,16) for k,v in tg_tw['symbols'].items()}
table=W.test_table(frames=8)
e=TM.engine(img,end=W.BASE+len(stock)+tg_tw['append']['size'],payload=(pay,rt)); e.uc.mem_map(GW.COPIES_AT,0x01800000)
for t in range(1,6): e.uc.mem_write(E.VOICE0+t*E.VSTRIDE,struct.pack('>II',9,9))
pcm=np.clip(np.round(table*32767),-32768,32767).astype('>i2').tobytes(); e.uc.mem_write(W.PCM,bytes(64)+pcm)
w32=lambda a,v:e.uc.mem_write(a,struct.pack('>I',v&0xffffffff))
for k,v in ((0,W.H),(256,W.PCM),(512,len(table))): w32(tg['slot_hash']+k+4*W.SLOT,v)
for t in range(6): w32(sym['tg_track_slot']+4*t,W.SLOT if t==0 else -1); w32(sym['tg_track_pend']+4*t,-1)
reads={'pool':0,'raw':0}
def rd(uc,acc,addr,size,val,ud):
    if GW.COPIES_AT<=addr<GW.SCRATCH_AT: reads['pool']+=1
    elif W.PCM<=addr<W.PCM+64+len(pcm): reads['raw']+=1
e.uc.hook_add(UC_HOOK_MEM_READ,rd)
def note(n,blocks=200):
    e.set(0,machine=7,note=n,pitch=64,color=64,shape=64,sweep=127,contour=0,punch=0,gate=0,finetune=64,decay=127)
    for k in reads: reads[k]=0
    x=np.concatenate([e.block(1 if b==0 else 0)[0] for b in range(blocks)]).astype(float)
    return x,dict(reads)
x0,r0=note(96); print("avant  : lectures", r0, "repli %.0f dB"%W.grit(x0[1280:],440*2**(27/12)))
clock=1000
for i in range(800):
    clock+=1; w32(W.CLOCK,clock); e.call(sym['wt_tick'])
    if i%64==0: e.block(0)
bss=bytes(e.uc.mem_read(pay+0x36000,1500))
print("empreinte dans l'état des pistes :", [hex(pay+0x36000+i) for i in range(0,1500,4) if bss[i:i+4]==struct.pack('>I',W.H)])
x1,r1=note(96); print("après  : lectures", r1, "repli %.0f dB"%W.grit(x1[1280:],440*2**(27/12)))
# même rendu sans le volume : spectre brut de la sortie
L=len(x1)-1280; S=np.abs(np.fft.rfft(x1[1280:]*np.blackman(L)))**2; fr=np.fft.rfftfreq(L,1/48000)
f0=440*2**(27/12); top=np.argsort(S)[-10:][::-1]; print("raies les plus fortes (Hz, dB, harmonique?) :",
  [(int(fr[i]),round(10*np.log10(S[i]/S.max())),round(fr[i]/f0,2)) for i in top])
print("enveloppe (rms par 20 blocs):",[int(np.sqrt((x1[i:i+640]**2).mean())/1e5) for i in range(0,len(x1),640*10)])
def grit2(x):
    L=len(x); S=np.abs(np.fft.rfft(x*np.blackman(L)))**2; fr=np.fft.rfftfreq(L,1/48000)
    f0=fr[np.argmax(S*(fr<3000))]; h=fr/f0; near=np.abs(h-np.round(h))*f0<max(25,f0*0.012); aud=fr<20000
    return f0, 10*np.log10(S[aud&~near].sum()/S[aud].sum())
print("avant  : f0 %.0f Hz, repli %.0f dB"%grit2(x0[1280:])); print("après  : f0 %.0f Hz, repli %.0f dB"%grit2(x1[1280:]))
from unicorn import UC_HOOK_CODE
from unicorn import m68k_const as mk
cap=[]
def vca(uc,a,s,u):
    sp=uc.reg_read(mk.UC_M68K_REG_A7); out=struct.unpack('>I',uc.mem_read(sp+4,4))[0]; v=struct.unpack('>I',uc.mem_read(sp+8,4))[0]
    if v==E.VOICE0: cap.append(np.frombuffer(bytes(uc.mem_read(out,128)),'>i4').astype(float))
e.uc.hook_add(UC_HOOK_CODE,vca,begin=0x400a9430,end=0x400a9430)
note(96); pre=np.concatenate(cap)
print("sortie de Wave avant le volume : f0 %.0f Hz, repli %.0f dB"%grit2(pre[1280:]))
