import pandas as pd, numpy as np, scipy.sparse as sp
from sklearn.linear_model import Ridge
b=pd.read_pickle('balls_wp.pkl')
b['ph']=pd.cut(b.overid,[0,6,15,20],labels=[0,1,2]).astype(int)
# ---- pressure definition
live=(b.wp>=0.15)&(b.wp<=0.85)
late=(b.legal_before>=36)|(b.w_before>=3)|(b.innings==2)
b['P']=((b.LI>=1.5)&live&late)
print('pressure share',b.P.mean().round(3), b.groupby('innings').P.mean().round(3).to_dict(), 'balls',b.P.sum())
# validation: pressure vs ordinary
l=b[b.legal]
t=l.groupby('P').agg(n=('runs','size'),rpb=('team_runs','mean'),wk=('wk','mean'),dot=('runs',lambda s:(s==0).mean()),bnd=('is_four','mean'),six=('is_six','mean'))
t['sr']=t.rpb*100; print(t.round(4))
for inn in (1,2): 
    x=l[l.innings==inn].groupby('P').agg(sr=('runs',lambda s:s.mean()*100),wk=('wk','mean'),dot=('runs',lambda s:(s==0).mean())); print(inn,x.round(3))
print(b[b.P].groupby('ph').size()/b.groupby('ph').size())
# ---- values
b['needsbat']=~b.wide
b['is_ro']=b.dismissal_type.eq('RunOut')
b['bat_ok']=b.needsbat & ~(b.is_ro&(b.dismissed_player_id!=b.striker_id))
b['bowl_ok']=~b.is_ro
b['LIc']=b.LI.clip(lower=0.5)
b['n']=b.wpa/b.LIc
# ---- opponent adjustment via ridge on NON-pressure balls
def design(df):
    bi=pd.Categorical(df.striker_id,categories=bats); bo=pd.Categorical(df.bowler_id,categories=bowls)
    r=np.arange(len(df))
    Xb=sp.csr_matrix((np.ones(len(df)),(r,bi.codes)),shape=(len(df),len(bats)))
    Xo=sp.csr_matrix((np.ones(len(df)),(r,bo.codes)),shape=(len(df),len(bowls)))
    ctx=sp.csr_matrix(np.c_[df.is_ipl.astype(float),df.ph==0,df.ph==2,df.innings==2].astype(float))
    return sp.hstack([Xb,Xo,ctx]).tocsr()
bats=sorted(b.striker_id.unique()); bowls=sorted(b.bowler_id.unique())
fit=b[(~b.P)&b.bat_ok&b.bowl_ok&b.legal]
Xf=design(fit)
rd=Ridge(alpha=150,fit_intercept=True).fit(Xf,fit.n.values)
co=rd.coef_; beff=pd.Series(co[:len(bats)],index=bats); oeff=pd.Series(co[len(bats):len(bats)+len(bowls)],index=bowls)
print('bat eff sd',beff.std(),'bowl eff sd',oeff.std(),'intercept',rd.intercept_)
b['gam']=b.bowler_id.map(oeff).fillna(0); b['bet']=b.striker_id.map(beff).fillna(0)
b['adj_bat']=b.wpa-b.LIc*b.gam           # batter perspective, opp-adjusted WPA
b['adj_bowl']=-b.wpa+b.LIc*b.bet         # bowler perspective
b['n_bat']=b.adj_bat/b.LIc; b['n_bowl']=b.adj_bowl/b.LIc
b.to_pickle('balls_final.pkl')
pd.to_pickle((beff,oeff),'effects.pkl')
