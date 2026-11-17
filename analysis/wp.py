import pandas as pd, numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier as HGB
from sklearn.model_selection import GroupKFold
from sklearn.metrics import log_loss, roc_auc_score, brier_score_loss
b=pd.read_pickle('balls.pkl')
F1=['runs','wl','bl','crr','ipl']; F2=['need','wl','bl','rrr','crr','ipl']
MONO1=[1,-1,1,0,0]; MONO2=[-1,-1,1,1,0,0]
def feats(inn,runs,wl,legal,target,ipl):
    bl=120-legal
    if inn==1:
        crr=np.where(legal>0,runs/np.maximum(legal,1)*6,0)
        return np.c_[runs,wl,bl,crr,ipl]
    need=target-runs
    rrr=np.where(bl>0,need/np.maximum(bl,1)*6,99)
    crr=np.where(legal>0,runs/np.maximum(legal,1)*6,0)
    return np.c_[need,wl,bl,np.clip(rrr,0,60),crr,ipl]
def mk(inn): return HGB(max_iter=250,learning_rate=0.05,max_leaf_nodes=15,min_samples_leaf=200,l2_regularization=1.0,monotonic_cst=(MONO1 if inn==1 else MONO2),random_state=0)
b['ipl']=b.is_ipl.astype(int)
X1=feats(1,b.runs_before,b.w_before,b.legal_before,b.target,b.ipl)  # arrays for all, interpret per inn later
mask1=(b.innings==1).values; mask2=~mask1
X1=feats(1,b.runs_before.values,b.w_before.values,b.legal_before.values,None,b.ipl.values)
X2=feats(2,b.runs_before.values,b.w_before.values,b.legal_before.values,b.target.fillna(0).values,b.ipl.values)
y=b.bat_win.values; grp=b.match_id.values
# outcome distribution by phase for legal balls
lb=b[b.legal].copy()
lb['phase']=pd.cut(lb.overid,[0,6,15,20],labels=[0,1,2]).astype(int)
lb['o']=np.where(lb.wk,'W',lb.runs.astype(str))
OUT=['0','1','2','3','4','6','W']
dist=lb[lb.o.isin(OUT)].groupby('phase').o.value_counts(normalize=True).unstack()[OUT].fillna(0)
dist=dist.div(dist.sum(1),axis=0); print(dist.round(3))
dist.to_pickle('outdist.pkl')
def terminal_or_pred(inn,runs,wl,legal,m1,m2,ipl,inn1_target_needed=None):
    # WP for batting team given state AFTER a hypothetical ball. arrays.
    runs=np.asarray(runs,float);wl=np.asarray(wl);legal=np.asarray(legal);ipl=np.asarray(ipl)
    out=np.zeros(len(runs))
    if inn==2:
        tgt=inn1_target_needed
        need=tgt-runs
        won=need<=0; ended=(wl>=10)|(legal>=120)
        tie=ended&(need==1)
        live=~won&~ended
        out[won]=1.0; out[tie]=0.5
        if live.any(): out[live]=m2.predict_proba(feats(2,runs[live],wl[live],legal[live],tgt[live],ipl[live]))[:,1]
    else:
        ended=(wl>=10)|(legal>=120)
        live=~ended
        if live.any(): out[live]=m1.predict_proba(feats(1,runs[live],wl[live],legal[live],None,ipl[live]))[:,1]
        if ended.any():
            tg=runs[ended]+1
            out[ended]=1-m2.predict_proba(feats(2,np.zeros(ended.sum()),np.zeros(ended.sum()),np.zeros(ended.sum()),tg,ipl[ended]))[:,1]
    return out
n=len(b); wp=np.zeros(n); LI=np.zeros(n); EXP_ABS=np.zeros(n)
phase=pd.cut(b.overid,[0,6,15,20],labels=[0,1,2]).astype(int).values
gkf=GroupKFold(5)
for k,(tr,te) in enumerate(gkf.split(b,y,grp)):
    t1=tr[mask1[tr]]; t2=tr[mask2[tr]]
    m1=mk(1).fit(X1[t1],y[t1]); m2=mk(2).fit(X2[t2],y[t2])
    te1=te[mask1[te]]; te2=te[mask2[te]]
    wp[te1]=m1.predict_proba(X1[te1])[:,1]; wp[te2]=m2.predict_proba(X2[te2])[:,1]
    # leverage
    for inn,idx in ((1,te1),(2,te2)):
        d=b.iloc[idx]
        acc=np.zeros(len(idx))
        for oi,o in enumerate(OUT):
            r=0 if o=='W' else int(o)
            wl2=d.w_before.values+(1 if o=='W' else 0)
            w_after=terminal_or_pred(inn,d.runs_before.values+r,wl2,d.legal_before.values+1,m1,m2,d.ipl.values,d.target.values if inn==2 else None)
            p=dist.loc[phase[idx],o].values
            acc+=p*np.abs(w_after-wp[idx])
        EXP_ABS[idx]=acc
    print('fold',k,'done')
b['wp']=wp; b['exp_abs']=EXP_ABS
# calibration/validation
for inn in (1,2):
    mm=b.innings==inn
    print(inn,'logloss',log_loss(y[mm],wp[mm]),'brier',brier_score_loss(y[mm],wp[mm]),'auc',roc_auc_score(y[mm],wp[mm]))
cal=pd.DataFrame({'p':wp,'y':y,'inn':b.innings}); cal['bin']=pd.cut(cal.p,np.linspace(0,1,11))
print(cal.groupby(['inn','bin'],observed=True).agg(p=('p','mean'),y=('y','mean'),n=('y','size')).round(3))
# WP after: next ball's pre-state wp in same innings; terminal -> actual / chase start
b['wp_next']=b.groupby(['match_id','innings']).wp.shift(-1)
last=b.wp_next.isna()
# last ball of innings 1: 1 - wp of first ball of innings 2 ; last ball of inn 2: actual result
first2=b[(b.innings==2)].groupby('match_id').wp.first()
b.loc[last&(b.innings==1),'wp_next']=1-b.loc[last&(b.innings==1),'match_id'].map(first2).values
b.loc[last&(b.innings==2),'wp_next']=b.loc[last&(b.innings==2),'bat_win']
b['wpa']=b.wp_next-b.wp
print(b.wpa.describe()); print('mean wpa by innings',b.groupby('innings').wpa.mean())
mean_abs=b.exp_abs.mean(); b['LI']=b.exp_abs/mean_abs
print(b.LI.describe(percentiles=[.5,.75,.8,.9,.95]))
b.to_pickle('balls_wp.pkl')
