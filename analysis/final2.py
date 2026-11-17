import pandas as pd, numpy as np, scipy.sparse as sp, pickle
from sklearn.linear_model import Ridge
from scipy.stats import spearmanr
pd.set_option('display.width',250); pd.set_option('display.max_columns',40); pd.set_option('display.max_rows',100)
b=pd.read_pickle('balls_v.pkl')
b['ebw_']=b.ebw
names=pd.concat([b[['striker_id','striker_name']].set_axis(['id','name'],axis=1),b[['bowler_id','bowler_name']].set_axis(['id','name'],axis=1)]).drop_duplicates('id').set_index('id').name
bats=sorted(b.striker_id.unique()); bowls=sorted(b.bowler_id.unique())
def design(df):
    bi=pd.Categorical(df.striker_id,categories=bats); bo=pd.Categorical(df.bowler_id,categories=bowls); r=np.arange(len(df))
    Xb=sp.csr_matrix((np.ones(len(df)),(r,bi.codes)),shape=(len(df),len(bats))); Xo=sp.csr_matrix((np.ones(len(df)),(r,bo.codes)),shape=(len(df),len(bowls)))
    return sp.hstack([Xb,Xo,sp.csr_matrix(df.is_ipl.values.astype(float)[:,None])]).tocsr()
# component values
b['rb_run']=b.runs-b.er                    # batter runs over exp
b['rb_wk']=-(b.wk.astype(float)-b.ew)       # batter: not getting out is good (+)
b['rw_run']=-(b.team_runs-b.etr)            # bowler runs saved
b['rw_wk']=b.bowler_wk.astype(float)-b.ebw  # bowler wickets over exp
fit=b[(~b.P)&b.bat_ok&b.bowl_ok&b.legal]; X=design(fit); nb_,no_=len(bats),len(bowls)
eff={}
for comp,alpha in (('rb_run',40),('rb_wk',40),('rw_run',40),('rw_wk',40)):
    # batter comps: bowler effect = coefficient on bowler dummies of batter-perspective; bowler comps: batter effect
    y=fit[comp].values if comp.startswith('rb') else fit[comp].values
    rd=Ridge(alpha=alpha*(1 if 'run' in comp else 3)).fit(X,y); eff[comp]=(pd.Series(rd.coef_[:nb_],index=bats),pd.Series(rd.coef_[nb_:nb_+no_],index=bowls))
# batter comp adj: subtract bowler effect on batter-perspective model; bowler comp: model fitted on bowler-perspective y, subtract batter effect
b['a_rb_run']=b.rb_run-b.bowler_id.map(eff['rb_run'][1]).fillna(0)
b['a_rb_wk']=b.rb_wk-b.bowler_id.map(eff['rb_wk'][1]).fillna(0)
b['a_rw_run']=b.rw_run-b.striker_id.map(eff['rw_run'][0]).fillna(0)
b['a_rw_wk']=b.rw_wk-b.striker_id.map(eff['rw_wk'][0]).fillna(0)
b['VB']=b.a_rb_run+b.lam*b.a_rb_wk
b['VW']=b.a_rw_run+b.lam*b.a_rw_wk
b.to_pickle('balls_v2.pkl')
CFG={'bat':dict(ok='bat_ok',pid='striker_id',runc='a_rb_run',wkc='a_rb_wk',tot='VB'),'bowl':dict(ok='bowl_ok',pid='bowler_id',runc='a_rw_run',wkc='a_rw_wk',tot='VW')}
def mom(x,n):
    m=x.mean(); s2=x.var()  # ball-level var using pooled
    return s2
def eb_shrink(df,col,pidc,mask,minn=30):
    x=df[mask]; g=x.groupby(pidc)[col]; mean=g.mean(); n=g.size(); s2=x[col].var()
    el=n>=minn; tau2=max(mean[el].var()-(s2/n[el]).mean(),1e-9)
    k=s2/tau2; mu=x[col].mean(); return mean, n, mu+(mean-mu)*n/(n+k), k, tau2
def ratings(d,role,thr=1.5,elig=(75,15,100),opp=True,weights=(0.7,0.15,0.15),verbose=False,ret_k=False):
    c=CFG[role]; pid=c['pid']; d=d[d[c['ok']]]
    pm=d.P if thr==1.5 else ((d.LI>=thr)&d.wp.between(.15,.85)&((d.legal_before>=36)|(d.w_before>=3)|(d.innings==2)))
    out=pd.DataFrame(index=sorted(d[pid].unique()))
    res={}
    for comp in ('runc','wkc'):
        col=c[comp]; m,n,eb,k,t2=eb_shrink(d,col,pid,pm); out['m_'+comp]=m; out['eb_'+comp]=eb; out['k_'+comp]=k
    out['pb']=d[pm].groupby(pid).size()
    out['pv_raw']=(out.m_runc+d.groupby(pid).lam.mean()*out.m_wkc)
    lam=d[pm].groupby(pid).lam.mean()
    out['pv_eb']=(out.eb_runc+lam*out.eb_wkc)
    # usual (non-pressure) level
    nonp=d[~pm]; out['nb']=nonp.groupby(pid).size(); out['usual_raw']=nonp.groupby(pid)[c['tot']].mean()
    # lift: shrunk pressure minus shrunk usual
    mu,nu,ebu,ku,_=eb_shrink(d,c['tot'],pid,~pm)
    out['usual_eb']=ebu
    out['lift_eb']=out.pv_eb-out.usual_eb
    # consistency
    st=d[pm].groupby([pid,'match_id'])[c['tot']].sum().reset_index(); st['pos']=st[c['tot']]>0
    out['stints']=st.groupby(pid).size(); ps=st.groupby(pid).pos.mean(); p0=st.pos.mean(); out['cons_raw']=ps
    out['cons_eb']=(ps*out.stints+p0*12)/(out.stints+12)
    out['name']=names.reindex(out.index)
    out['elig']=(out.pb>=elig[0])&(out.stints>=elig[1])&(out.nb>=elig[2])
    e=out[out.elig]; z=lambda s:(s-s.mean())/s.std()
    out.loc[e.index,'score']=weights[0]*z(e.pv_eb)+weights[1]*z(e.lift_eb)+weights[2]*z(e.cons_eb)
    out['pv100']=out.pv_eb*100; out['pvraw100']=out.pv_raw*100; out['usual100']=out.usual_eb*100; out['lift100']=out.lift_eb*100
    out['k_run']=out.k_runc; out['k_wk']=out.k_wkc
    return out
if __name__=='__main__':
    R={}
    for role in ('bat','bowl'):
        o=ratings(b,role); R[role]=o
        e=o[o.elig].sort_values('score',ascending=False)
        print(role,'eligible',len(e),'k_run',e.k_run.iloc[0].round(0),'k_wk',e.k_wk.iloc[0].round(0))
        print(e[['name','pb','stints','pvraw100','pv100','usual100','lift100','cons_eb','score']].head(20).round(2))
    pickle.dump(R,open('R.pkl','wb'))
