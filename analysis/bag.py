import pandas as pd, numpy as np, pickle, warnings
warnings.filterwarnings('ignore')
import final2 as F
b=F.b; W=(.8,0,.2)
mids=b.match_id.unique(); idx={m:np.where(b.match_id.values==m)[0] for m in mids}
rng=np.random.default_rng(7); NB=200
S={'bat':{},'bowl':{}}; T={'bat':{},'bowl':{}}; RK={'bat':{},'bowl':{}}
for i in range(NB):
    pick=rng.choice(mids,len(mids),replace=True)
    ii=np.concatenate([idx[m] for m in pick]); bs=b.iloc[ii].copy()
    bs['match_id']=np.repeat(np.arange(len(pick)),[len(idx[m]) for m in pick])
    for role in S:
        o=F.ratings(bs,role,weights=W,elig=(75,15,100)); e=o[o.elig].sort_values('score',ascending=False)
        for r_,(p,sc) in enumerate(e.score.items(),1):
            S[role].setdefault(p,[]).append(sc); RK[role].setdefault(p,[]).append(r_)
            if r_<=10: T[role][p]=T[role].get(p,0)+1
out={}
for role in S:
    base=F.ratings(b,role,weights=W); e=base[base.elig]
    d=pd.DataFrame({'name':e.name,'point_score':e.score,'bag_score':[np.mean(S[role].get(p,[np.nan])) if len(S[role].get(p,[]))>=0.25*NB else np.nan for p in e.index],
        'top10_freq':[T[role].get(p,0)/NB for p in e.index],'mean_rank':[np.mean(RK[role].get(p,[99])) for p in e.index]},index=e.index)
    d['final_score']=0.5*d.point_score+0.5*d.bag_score
    d=d.join(e[['pb','stints','pvraw100','pv100','usual100','lift100','cons_eb','cons_raw']]).sort_values('final_score',ascending=False)
    out[role]=d; print(role); print(d.head(15).round(2))
pickle.dump(out,open('final_tables.pkl','wb'))
