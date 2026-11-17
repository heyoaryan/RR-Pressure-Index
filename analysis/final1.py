import pandas as pd, numpy as np, scipy.sparse as sp
from sklearn.linear_model import Ridge, LinearRegression
from scipy.stats import spearmanr
pd.set_option('display.width',250); pd.set_option('display.max_columns',40); pd.set_option('display.max_rows',100)
b=pd.read_pickle('balls_final.pkl')
b['bl']=120-b.legal_before; b['need']=b.target-b.runs_before; b['rrr']=(b.need/b.bl.clip(lower=1)*6)
b['rb']=np.where(b.innings==2,pd.cut(b.rrr.fillna(0),[-1e9,6,8,10,12,15,1e9],labels=False),-1)
b['ob']=((b.overid-1)//2).clip(0,9); b['wb']=b.w_before.clip(0,7)
key=['innings','ob','wb','rb']
# expected bat-runs and wicket per delivery in context (all balls faced, incl. no-balls)
bb=b[b.bat_ok]
b['er']=b.groupby(key).runs.transform(lambda s:s.mean()); b['ew']=b.groupby(key).wk.transform(lambda s:s.astype(float).mean())
# wicket run-value lambda from WP model on pressure balls: wpa ~ a*team_runs - c*wk
P=b[b.P&b.bat_ok&b.legal]
lr=LinearRegression().fit(np.c_[P.runs,P.wk.astype(float)],P.wpa); a_,c_=lr.coef_
LAM=-c_/a_; print('WP per run',a_,'WP per wicket',c_,'lambda (runs per wicket)',LAM)
# also by phase
for ph,g in P.groupby('ph'):
    l=LinearRegression().fit(np.c_[g.runs,g.wk.astype(float)],g.wpa); print('phase',ph,'lambda',-l.coef_[1]/l.coef_[0])
LAMP={}
for ph,g in P.groupby('ph'):
    l=LinearRegression().fit(np.c_[g.runs,g.wk.astype(float)],g.wpa); LAMP[ph]=-l.coef_[1]/l.coef_[0]
print(LAMP)
b['lam']=b.ph.map(LAMP)
b['v_bat']=(b.runs-b.er)-b.lam*(b.wk.astype(float)-b.ew)       # runs-equivalent over expectation, batter
# bowler: runs conceded incl extras (team_runs) vs expected team runs per delivery; wicket only if bowler wicket
b['etr']=b.groupby(key).team_runs.transform('mean'); b['ebw']=b.groupby(key).bowler_wk.transform(lambda s:s.astype(float).mean())
b['v_bowl']=-(b.team_runs-b.etr)+b.lam*(b.bowler_wk.astype(float)-b.ebw)
# ridge opponent adj on non-pressure balls
bats=sorted(b.striker_id.unique()); bowls=sorted(b.bowler_id.unique())
def design(df):
    bi=pd.Categorical(df.striker_id,categories=bats); bo=pd.Categorical(df.bowler_id,categories=bowls); r=np.arange(len(df))
    Xb=sp.csr_matrix((np.ones(len(df)),(r,bi.codes)),shape=(len(df),len(bats))); Xo=sp.csr_matrix((np.ones(len(df)),(r,bo.codes)),shape=(len(df),len(bowls)))
    ctx=sp.csr_matrix(np.c_[df.is_ipl.astype(float)].astype(float)); return sp.hstack([Xb,Xo,ctx]).tocsr()
fit=b[(~b.P)&b.bat_ok&b.bowl_ok&b.legal]
rd=Ridge(alpha=40).fit(design(fit),fit.v_bat.values)
beff=pd.Series(rd.coef_[:len(bats)],index=bats); oeff=pd.Series(rd.coef_[len(bats):len(bats)+len(bowls)],index=bowls)
print('ridge sd bat',beff.std(),'bowl',oeff.std())
b['opp_bat']=b.bowler_id.map(oeff).fillna(0); b['opp_bowl']=b.striker_id.map(beff).fillna(0)
# batter value adj: remove bowler effect; bowler value: v_bowl = -(batter-side) => subtract (-beff)
b['vb']=b.v_bat-b.opp_bat
b['vw']=b.v_bowl+b.opp_bowl
b.to_pickle('balls_v.pkl')
# reliability check for thresholds
mids=np.sort(b.match_id.unique())
def half(s): return set(np.random.default_rng(s).permutation(mids)[:len(mids)//2])
for role,col,okc,pc in (('bat','vb','bat_ok','striker_id'),('bowl','vw','bowl_ok','bowler_id')):
    d=b[b[okc]&b.legal|(b[okc]&(role=='bowl'))].copy() if False else b[b[okc]].copy()
    for th in (1.0,1.5,2.0,3.0):
        rs=[]
        for s in range(25):
            h=half(s); o=[]
            for sub in (d[d.match_id.isin(h)],d[~d.match_id.isin(h)]):
                x=sub[(sub.LI>=th)&(sub.wp.between(.15,.85))]; o.append(pd.DataFrame({'v':x.groupby(pc)[col].mean(),'n':x.groupby(pc).size()}))
            j=o[0].join(o[1],lsuffix='a',rsuffix='b',how='inner'); j=j[(j.na>=30)&(j.nb>=30)]
            rs.append(spearmanr(j.va,j.vb)[0])
        print(role,'LI>=',th,'rho',round(np.mean(rs),3),'players~',len(j),'share balls',round(((d.LI>=th)&d.wp.between(.15,.85)).mean(),3))
