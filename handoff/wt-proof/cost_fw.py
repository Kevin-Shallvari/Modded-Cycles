import sys, json, struct, numpy as np
sys.path[:0]=['tools','tools/emu']
import test_wavetable as W, build, gen_wavetable as GW, mcengine as E, test_model_tg as TM, test_sdvintage as T
from unicorn import UC_HOOK_CODE
stock=T.main_os_from_syx('firmware/model-cycles_OS1.13.syx')
tg_tw=json.load(open(W.DEV/'30-model-tg-st.json')); wt=json.load(open(W.DEV/'36-wavetable-tg.json'))
tws=[tg_tw,wt]; p,_=build.apply_writes(stock,tws); pl,_=build.build_payload(tws,stock,None); img=bytes(p)+pl
pay=int(wt['append']['dest'],16); rt=build.payload_runtime(wt,stock,None)
sym={k:int(v,16) for k,v in wt['symbols'].items()}; tg={k:int(v,16) for k,v in tg_tw['symbols'].items()}
table=W.test_table(frames=64)
def setup(machine):
    e=TM.engine(img,end=W.BASE+len(stock)+tg_tw['append']['size'],payload=(pay,rt)); e.uc.mem_map(GW.COPIES_AT,0x01800000)
    for t in range(1,6): e.uc.mem_write(E.VOICE0+t*E.VSTRIDE,struct.pack('>II',9,9))
    pcm=np.clip(np.round(table*32767),-32768,32767).astype('>i2').tobytes(); e.uc.mem_write(W.PCM,bytes(64)+pcm)
    w32=lambda a,v:e.uc.mem_write(a,struct.pack('>I',v&0xffffffff))
    for k,v in ((0,W.H),(256,W.PCM),(512,len(table))): w32(tg['slot_hash']+k+4*W.SLOT,v)
    for t in range(6): w32(sym['tg_track_slot']+4*t,W.SLOT if t==0 else -1); w32(sym['tg_track_pend']+4*t,-1)
    e.set(0,machine=machine,note=48,pitch=64,color=64,shape=120,sweep=80,contour=60,punch=0,gate=0,finetune=64,decay=60)
    return e
for m,name in ((7,"Wave"),(4,"TONE")):
    e=setup(m); e.block(1)
    for b in range(5): e.block(0)
    n=[0]; h=e.uc.hook_add(UC_HOOK_CODE,lambda uc,a,s,u: n.__setitem__(0,n[0]+1))
    for b in range(10): e.block(0)
    e.uc.hook_del(h); print(f"{name}: {n[0]//10} instructions par bloc (boucle des voix entière, une piste)")
