import pandas as pd, numpy as np, pickle, json, warnings
warnings.filterwarnings('ignore')
import final2 as F
T=pickle.load(open('final_tables.pkl','rb')); E,tab,bt,bw=pickle.load(open('evid.pkl','rb'))
b=F.b
# league pressure means (for relative values)
base={}
for role in ('bat','bowl'):
    o=F.ratings(b,role); e=o[o.elig]; base[role]=float(e.pv_eb.mean()*100)
print(base)
out={}
rows=[]
for i,(pid,r) in enumerate(T['bat'].head(10).iterrows(),1):
    d=bt.loc[pid]; rows.append([i,r['name'],int(r.pb),int(r.stints),f"{int(d.ipl)} / {int(d.t20i)}",f"{d.sr:.0f}",f"{d.exp_sr:.0f}",f"{d.out_pct:.1f}",f"{d.exp_out:.1f}",f"{r.pvraw100:.0f}",f"{r.pv100-base['bat']:+.0f}",f"{r.cons_raw*100:.0f}%",f"{r.top10_freq*100:.0f}%",f"{r.final_score:.2f}"])
out['bat']=rows
rows=[]
for i,(pid,r) in enumerate(T['bowl'].head(10).iterrows(),1):
    d=bw.loc[pid]; rows.append([i,r['name'],int(r.pb),int(r.stints),f"{int(d.ipl)} / {int(d.t20i)}",f"{d.econ:.1f}",f"{d.exp_econ:.1f}",f"{d.wk_pct:.1f}",f"{d.exp_wk:.1f}",f"{r.pvraw100:.0f}",f"{r.pv100-base['bowl']:+.0f}",f"{r.cons_raw*100:.0f}%",f"{r.top10_freq*100:.0f}%",f"{r.final_score:.2f}"])
out['bowl']=rows
# next 5 in each
for role in ('bat','bowl'):
    out['next_'+role]=[[i+11,r['name'],f"{r.final_score:.2f}",f"{r.top10_freq*100:.0f}%"] for i,(p,r) in enumerate(T[role].iloc[10:16].iterrows())]
# usual vs pressure scatter data for top 10 (lift)
out['lift']={role:[[r['name'],f"{r.usual100-0:.0f}",f"{r.pv100:.0f}",f"{r.lift100:+.0f}"] for p,r in T[role].head(10).iterrows()] for role in ('bat','bowl')}
json.dump(out,open('rows.json','w'),indent=1)
print(json.dumps(out['bat'][:3]))
