import pandas as pd, numpy as np, pickle, warnings
warnings.filterwarnings('ignore')
import final2 as F
b=F.b; W=(.8,0,.2)
mids=b.match_id.unique(); grp={m:g for m,g in b.groupby('match_id')}
idx={m:np.where(b.match_id.values==m)[0] for m in mids}
R={}; 
for role in ('bat','bowl'):
    base=F.ratings(b,role,weights=W); R[role]=base
    top=base[base.elig].sort_values('score',ascending=False)
    print(role,'eligible',len(top)); print(top[['name','pb','stints','pvraw100','pv100','usual100','lift100','cons_eb','score']].head(15).round(2))
rng=np.random.default_rng(42); NB=120
cnt={r:{} for r in R}; ranks={r:{} for r in R}
for i in range(NB):
    pick=rng.choice(mids,len(mids),replace=True)
    ii=np.concatenate([idx[m] for m in pick]); bs=b.iloc[ii].copy()
    bs['match_id']=np.repeat(np.arange(len(pick)),[len(idx[m]) for m in pick])
    for role in R:
        o=F.ratings(bs,role,weights=W,elig=(75,15,100)); e=o[o.elig].sort_values('score',ascending=False)
        for r_,p in enumerate(e.index,1):
            ranks[role].setdefault(p,[]).append(r_)
            if r_<=10: cnt[role][p]=cnt[role].get(p,0)+1
stab={}
for role in R:
    base=R[role]; t=base[base.elig].sort_values('score',ascending=False).head(25)
    s=pd.DataFrame({'name':t.name,'rank':range(1,26),'top10_freq':[cnt[role].get(p,0)/NB for p in t.index],'median_rank':[np.median(ranks[role].get(p,[99])) for p in t.index],
                    'p10_rank':[np.percentile(ranks[role].get(p,[99]),10) for p in t.index],'p90_rank':[np.percentile(ranks[role].get(p,[99]),90) for p in t.index]},index=t.index)
    stab[role]=s; print(role); print(s.round(2))
# sensitivity
sens={}
for role in R:
    cfgs={'base':dict(),'LI>=1.0':dict(thr=1.0),'LI>=2.0':dict(thr=2.0),'PV only':dict(weights=(1,0,0)),'wts .7/.15/.15':dict(weights=(.7,.15,.15)),'strict elig':dict(elig=(120,25,150))}
    tops={}
    for k,c in cfgs.items():
        kw=dict(weights=W); kw.update(c); o=F.ratings(b,role,**kw); tops[k]=list(o[o.elig].sort_values('score',ascending=False).head(10).index)
    sens[role]=tops
    base10=set(tops['base']); print(role,{k:len(base10&set(v)) for k,v in tops.items()})
pickle.dump((R,stab,sens),open('stab.pkl','wb'))
