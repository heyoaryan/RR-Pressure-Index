import pandas as pd, numpy as np, pickle, warnings
warnings.filterwarnings('ignore')
from sklearn.metrics import log_loss, roc_auc_score, brier_score_loss
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
b=pd.read_pickle('balls_v2.pkl'); T=pickle.load(open('final_tables.pkl','rb'))
pd.set_option('display.width',250); pd.set_option('display.max_columns',40)
E={}
E['n_match']=b.match_id.nunique(); E['n_ball']=len(b); E['n_ipl']=b[b.is_ipl].match_id.nunique(); E['n_t20i']=b[~b.is_ipl].match_id.nunique()
E['n_pressure']=int(b.P.sum()); E['share']=b.P.mean()
for inn in (1,2):
    m=b.innings==inn; E[f'll{inn}']=log_loss(b.bat_win[m],b.wp[m]); E[f'auc{inn}']=roc_auc_score(b.bat_win[m],b.wp[m]); E[f'br{inn}']=brier_score_loss(b.bat_win[m],b.wp[m])
print({k:(round(v,4) if isinstance(v,float) else v) for k,v in E.items()})
b['ph']=b.ph.map({0:'Powerplay',1:'Middle',2:'Death'}); b['bl']=120-b.legal_before
L=b[b.legal]
tab=L.groupby('P').agg(balls=('runs','size'),rr=('team_runs',lambda s:s.mean()*6),wk=('wk',lambda s:s.mean()*100),dot=('runs',lambda s:(s==0).mean()*100),
   wp=('wp','mean'),LI=('LI','mean'),bl=('bl','mean'),wl=('w_before','mean'))
print(tab.round(2))
c=b[(b.innings==2)]; c['rrr']=(c.target-c.runs_before)/c.bl.clip(lower=1)*6
print(c.groupby('P').agg(rrr_med=('rrr','median'),need_med=('need','median') if 'need' in c else ('rrr','size'),bl=('bl','median'),wl=('w_before','mean')).round(2))
print(b.groupby(['innings','ph']).P.mean().unstack().round(3))
print(b.groupby('is_ipl').P.mean().round(3), b.groupby('is_ipl').P.sum())
# top-10 details
fb=T['bat'].head(10); fw=T['bowl'].head(10)
def split(pid,role,idc):
    d=b[b.P&(b[idc]==pid)]; return pd.Series({'ipl_balls':int(d.is_ipl.sum()),'t20i_balls':int((~d.is_ipl).sum()),'matches':d.match_id.nunique()})
rows=[]
for pid in fb.index:
    d=b[b.P&(b.striker_id==pid)&b.bat_ok]; l=d[d.legal]
    rows.append(dict(pid=pid,ipl=int(d.is_ipl.sum()),t20i=int((~d.is_ipl).sum()),sr=l.runs.sum()/len(l)*100,out_pct=l.wk.mean()*100,bnd=(l.is_four.sum()+l.is_six.sum())/len(l)*100,exp_sr=l.er.mean()*100,exp_out=l.ew.mean()*100,dots=(l.runs==0).mean()*100))
bt=pd.DataFrame(rows).set_index('pid'); print(bt.round(1))
rows=[]
for pid in fw.index:
    d=b[b.P&(b.bowler_id==pid)&b.bowl_ok]; l=d[d.legal]
    rows.append(dict(pid=pid,ipl=int(d.is_ipl.sum()),t20i=int((~d.is_ipl).sum()),econ=d.team_runs.sum()/len(l)*6,wk_pct=l.bowler_wk.mean()*100,exp_econ=d.etr.mean()*6,exp_wk=l.ebw.mean()*100,dots=(l.runs==0).mean()*100))
bw=pd.DataFrame(rows).set_index('pid'); print(bw.round(1))
pickle.dump((E,tab,bt,bw),open('evid.pkl','wb'))
# charts
cal=pd.DataFrame({'p':b.wp,'y':b.bat_win,'inn':b.innings}); cal['bin']=pd.cut(cal.p,np.linspace(0,1,11))
fig,ax=plt.subplots(1,3,figsize=(15,4.2))
for inn,col in ((1,'#c0392b'),(2,'#1f4e79')):
    g=cal[cal.inn==inn].groupby('bin',observed=True).agg(p=('p','mean'),y=('y','mean')); ax[0].plot(g.p,g.y,'o-',color=col,label=f'Innings {inn}')
ax[0].plot([0,1],[0,1],'k--',lw=1); ax[0].set_xlabel('Predicted win prob (out-of-fold)'); ax[0].set_ylabel('Actual win rate'); ax[0].set_title('A. Win-probability model calibration'); ax[0].legend()
b['ovr']=b.overid
g=b.groupby(['innings','ovr']).P.mean().unstack(0)
ax[1].plot(g.index,g[1]*100,'o-',color='#c0392b',label='Innings 1'); ax[1].plot(g.index,g[2]*100,'o-',color='#1f4e79',label='Innings 2 (chase)')
ax[1].set_xlabel('Over'); ax[1].set_ylabel('% of deliveries flagged high-pressure'); ax[1].set_title('B. When pressure occurs'); ax[1].legend()
lv=b.LI.clip(upper=6); ax[2].hist(lv,bins=60,color='#7f8c8d'); ax[2].axvline(1.5,color='#e91e8c',lw=2); ax[2].set_xlabel('Leverage Index (clipped at 6)'); ax[2].set_title('C. Leverage distribution; pink = 1.5 cut-off'); ax[2].set_ylabel('Deliveries')
plt.tight_layout(); plt.savefig('fig_pressure.png',dpi=150); plt.close()
# top10 bars
fig,ax=plt.subplots(1,2,figsize=(14,5))
for a,(role,t,col) in zip(ax,(('Batters',T['bat'].head(10),'#e91e8c'),('Bowlers',T['bowl'].head(10),'#1f4e79'))):
    t=t.iloc[::-1]; a.barh(t.name,t.final_score,color=col); 
    for i,(s,f) in enumerate(zip(t.final_score,t.top10_freq)): a.text(s+.03,i,f'top-10 in {f*100:.0f}% of resamples',va='center',fontsize=8)
    a.set_title(f'Top-10 {role}: final rating (z-units)'); a.set_xlim(0,t.final_score.max()*1.6)
plt.tight_layout(); plt.savefig('fig_top10.png',dpi=150); plt.close()
