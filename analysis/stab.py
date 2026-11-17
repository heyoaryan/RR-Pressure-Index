"""Sensitivity: how many of the base top-10 survive when one assumption changes.
Writes sens.pkl = {role: {config_label: (top10_ids, n_eligible)}}"""
import pandas as pd, numpy as np, pickle, warnings
warnings.filterwarnings('ignore')
import final2 as F
from prep import U
b=F.b
# full ICC members; a T20I involving any associate side is dropped in the "full members" row
FULL={'India','Australia','England','New Zealand','South Africa','Pakistan','Sri Lanka','West Indies',
      'Bangladesh','Afghanistan','Zimbabwe','Ireland'}
m=pd.read_csv(U+'matches.csv')
assoc=set(m[~(m.home_team.isin(FULL)&m.away_team.isin(FULL))].match_id)
CFG={
 'Base (70/15/15)':(b,{}),
 'Old weights 80/0/20 (no lift)':(b,dict(weights=(.8,0,.2))),
 'Pressure value only':(b,dict(weights=(1,0,0))),
 'Threshold LI ≥ 1.0':(b,dict(thr=1.0)),
 'Threshold LI ≥ 2.0':(b,dict(thr=2.0)),
 'Stricter: 120 balls, 25 matches':(b,dict(elig=(120,25,150))),
 'Bowling k = 350 (vs ≈783)':(b,dict(kfix=350)),
 'IPL balls only':(b[b.is_ipl],{}),
 'T20I balls only':(b[~b.is_ipl],{}),
 'Drop T20Is with associates':(b[b.is_ipl|~b.match_id.isin(assoc)],{}),
}
if __name__=='__main__':
    sens={}
    for role in ('bat','bowl'):
        sens[role]={}
        for k,(d,kw) in CFG.items():
            if 'kfix' in kw and role=='bat': continue      # k test is about the bowling shrinkage
            o=F.ratings(d,role,**kw); e=o[o.elig].sort_values('score',ascending=False)
            sens[role][k]=(list(e.head(10).index),list(e.index))
        base=set(sens[role]['Base (70/15/15)'][0])
        print(role); [print(f'  {k:34s} {len(base&set(v)):2d}/10  base-top10 still eligible {len(base&set(el))}/10  pool {len(el)}') for k,(v,el) in sens[role].items()]
    print('associate T20I matches dropped:',len(assoc&set(b[~b.is_ipl].match_id)))
    pickle.dump(sens,open('sens.pkl','wb'))
