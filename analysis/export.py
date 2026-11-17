"""Builds ../dashboard_data.json (website + PDF read from this one file) and the report charts.
Needs: balls_v2.pkl (final2), final_tables.pkl (bag), sens.pkl (stab), rel.pkl (rel)."""
import pandas as pd, numpy as np, pickle, json, warnings
warnings.filterwarnings('ignore')
from sklearn.metrics import log_loss, roc_auc_score, brier_score_loss
import final2 as F
b=F.b; T=pickle.load(open('final_tables.pkl','rb')); S=pickle.load(open('sens.pkl','rb')); REL=pickle.load(open('rel.pkl','rb'))
r2=lambda x,d=2: None if pd.isna(x) else round(float(x),d)

# ---------- overview + WP model accuracy (out-of-fold)
ov=dict(n_match=int(b.match_id.nunique()),n_ball=int(len(b)),n_ipl=int(b[b.is_ipl].match_id.nunique()),
        n_t20i=int(b[~b.is_ipl].match_id.nunique()),n_pressure=int(b.P.sum()),share=float(b.P.mean()))
cal={}
for inn in (1,2):
    m=b.innings==inn; y,p=b.bat_win[m],b.wp[m]
    ov[f'll{inn}']=log_loss(y,p); ov[f'auc{inn}']=roc_auc_score(y,p); ov[f'br{inn}']=brier_score_loss(y,p)
    base=y.mean(); ov[f'br{inn}_naive']=brier_score_loss(y,np.full(len(y),base))
    c=pd.DataFrame({'p':p,'y':y}); c['bin']=pd.cut(c.p,np.linspace(0,1,11))
    g=c.groupby('bin',observed=True).agg(p=('p','mean'),y=('y','mean'),n=('y','size'))
    cal[inn]=[[r2(a,3),r2(bb,3),int(n)] for a,bb,n in g.values]
ov['calib']=cal

# ---------- pressure vs other balls
L=b[b.legal]
def tabrow(d): return dict(balls=int(len(d)),rr=r2(d.team_runs.mean()*6,3),wk=r2(d.wk.mean()*100,3),dot=r2((d.runs==0).mean()*100,3),
                           wp=r2(d.wp.mean(),3),LI=r2(d.LI.mean(),3))
tab=[tabrow(L[~L.P]),tabrow(L[L.P])]
ph=[['Powerplay (1–6)',b[b.ph==0].P.mean()],['Middle (7–15)',b[b.ph==1].P.mean()],['Death (16–20)',b[b.ph==2].P.mean()],
    ['1st innings',b[b.innings==1].P.mean()],['2nd innings (chase)',b[b.innings==2].P.mean()]]
phase=[[k,r2(v*100,1)] for k,v in ph]
by_over={inn:[r2(v*100,1) for v in b[b.innings==inn].groupby('overid').P.mean().values] for inn in (1,2)}

# ---------- player rows: pressure vs normal (raw, legal balls; context-expected in same situations)
def bat_split(pid):
    d=b[(b.striker_id==pid)&b.bat_ok&b.legal]; o={}
    for tag,x in (('p',d[d.P]),('n',d[~d.P])):
        o[f'sr_{tag}']=x.runs.mean()*100; o[f'out_{tag}']=x.wk.mean()*100; o[f'exp_sr_{tag}']=x.er.mean()*100; o[f'exp_out_{tag}']=x.ew.mean()*100
        o[f'bnd_{tag}']=(x.is_four|x.is_six).mean()*100; o[f'dots_{tag}']=(x.runs==0).mean()*100
    o['ipl']=int(d[d.P].is_ipl.sum()); o['t20i']=int((~d[d.P].is_ipl).sum()); return o
def bowl_split(pid):
    d=b[(b.bowler_id==pid)&b.bowl_ok]; o={}
    for tag,x in (('p',d[d.P]),('n',d[~d.P])):
        l=x[x.legal]; o[f'econ_{tag}']=x.team_runs.sum()/len(l)*6; o[f'wk_{tag}']=l.bowler_wk.mean()*100
        o[f'exp_econ_{tag}']=x.etr.sum()/len(l)*6; o[f'exp_wk_{tag}']=l.ebw.mean()*100; o[f'dots_{tag}']=(l.runs==0).mean()*100
    o['ipl']=int(d[d.P&d.legal].is_ipl.sum()); o['t20i']=int((~d[d.P&d.legal].is_ipl).sum()); return o
KEEP=['name','point_score','bag_score','final_score','top10_freq','mean_rank','median_rank','p10_rank','p90_rank','pb','stints',
      'pvraw100','pv100','usual100','lift100','cons_eb','cons_raw']
out={'overview':ov,'tab':tab,'phase':phase,'by_over':by_over}
for role,fn in (('bat',bat_split),('bowl',bowl_split)):
    t=T[role]; rows=[]
    for i,(pid,r) in enumerate(t.head(10).iterrows(),1):
        d={k:(r[k] if k=='name' else r2(r[k],3)) for k in KEEP}; d.update({k:(v if isinstance(v,int) else r2(v,2)) for k,v in fn(pid).items()})
        d['rank']=i; d['pid']=int(pid); rows.append(d)
    out[role]=rows
    out['next_'+role]=[[i+11,r['name'],r2(r.final_score),r2(r.top10_freq)] for i,(p,r) in enumerate(t.iloc[10:16].iterrows())]
    # scatter: every eligible player, normal (non-pressure, shrunk) vs pressure (shrunk) value per 100 balls
    out['scatter_'+role]=[[r['name'],r2(r.usual100,1),r2(r.pv100,1),int(i<10)] for i,(p,r) in enumerate(t.iterrows())]
    # sensitivity vs the FINAL top-10
    fin=set(t.head(10).index)
    out['sens_'+role]={k:[len(fin&set(v)),len(fin&set(el)),len(el)] for k,(v,el) in S[role].items()}
    out['rel_'+role]=REL[role]
# shrinkage constants
for role in ('bat','bowl'):
    o=F.ratings(b,role); out['k_'+role]=[r2(o.k_run.dropna().iloc[0],0),r2(o.k_wk.dropna().iloc[0],0)]
json.dump(out,open('../dashboard_data.json','w'),indent=1,ensure_ascii=False)
print('bat :',[r['name'] for r in out['bat']]); print('bowl:',[r['name'] for r in out['bowl']])
print({k:round(v,3) for k,v in ov.items() if k!='calib'}); print('k',out['k_bat'],out['k_bowl']); print(phase)
