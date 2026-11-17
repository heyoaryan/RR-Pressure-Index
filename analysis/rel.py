"""Split-half reliability: split matches into two random halves, rate players on each half,
Spearman rho between halves for each component. 20 splits. Writes rel.pkl"""
import pandas as pd, numpy as np, pickle, warnings
warnings.filterwarnings('ignore')
from scipy.stats import spearmanr
import final2 as F
b=F.b; mids=np.sort(b.match_id.unique())
COLS={'Pressure value, raw':'pvraw100','Pressure value, shrunk':'pv100','Final rating (70/15/15)':'score',
      'Consistency alone':'cons_eb','Usual (non-pressure) level':'usual100','Clutch lift':'lift100'}
HALF_ELIG=(35,7,50)   # roughly half the full-data thresholds
out={}
for role in ('bat','bowl'):
    rs={k:[] for k in COLS}; npl=[]
    for s in range(20):
        h=set(np.random.default_rng(s).permutation(mids)[:len(mids)//2])
        A=F.ratings(b[b.match_id.isin(h)],role,elig=HALF_ELIG); B=F.ratings(b[~b.match_id.isin(h)],role,elig=HALF_ELIG)
        j=A[A.elig].join(B[B.elig],lsuffix='_a',rsuffix='_b',how='inner'); npl.append(len(j))
        for k,c in COLS.items(): rs[k].append(spearmanr(j[c+'_a'],j[c+'_b'])[0])
    out[role]={k:float(np.mean(v)) for k,v in rs.items()}; out[role]['_players']=float(np.mean(npl))
    print(role,{k:round(v,3) for k,v in out[role].items()})
pickle.dump(out,open('rel.pkl','wb'))
