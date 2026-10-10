import sys, json, struct, numpy as np
sys.path[:0]=['tools','tools/emu']
import test_wavetable as W, build, gen_wavetable as GW, mcengine as E, test_model_tg as TM, test_sdvintage as T, gen_sdvintage_7th as g7, gen_syntakt_engines as gs
stock=T.main_os_from_syx('firmware/model-cycles_OS1.13.syx')
tg_tw=json.load(open(W.DEV/'30-model-tg-st.json')); wt=json.load(open(W.DEV/'36-wavetable-tg.json'))
tws=[tg_tw,wt]; p,_=build.apply_writes(stock,tws); pl,_=build.build_payload(tws,stock,None); img=bytes(p)+pl
pay=int(wt['append']['dest'],16); rt=build.payload_runtime(wt,stock,None)
tg={k:int(v,16) for k,v in tg_tw['symbols'].items()}; sym={k:int(v,16) for k,v in wt['symbols'].items()}
gs.set_base(pay)
u=lambda b,a,base: struct.unpack_from(">I",b,a-base)[0]
e_at=gs.DESCN+GW.EPOS_ID*g7.DSTRIDE
ent=[u(rt,e_at+4*i,pay) for i in range(14)]
cs=lambda a: bytes(rt[a-pay:a-pay+16]).split(b"\0")[0]
print("param 0x0a :", ent[:11], cs(ent[11]), cs(ent[13]))
pt=g7.DESC+GW.EPOS_ID*g7.DSTRIDE+44
print("noms dans param_table :", cs(u(img,pt,E.BASE)), cs(u(img,pt+8,E.BASE)))
stubs=rt[gs.STUBS-pay:gs.DATA-pay].hex()
seq="720d2141000c"+"720c21410018"+"720b2141001c"+"720a21410010"
print("couche MACHINE tenue : Attack(DECAY) Filtre(SWEEP) Réso(CONTOUR) puis Env Pos(COLOR) :", stubs.count(seq), "fois")
