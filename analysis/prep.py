import pandas as pd, numpy as np
import os
# folder with ball_by_ball.csv, matches.csv, competitions.csv, … (override with DATA_DIR=/path/to/Data\ Pack)
U=os.path.join(os.environ.get('DATA_DIR',os.path.expanduser('~/Downloads/SupeRR Selector Season 2 | Problem Statement | Data Pack/SupeRR Selector Season 2 | Data Pack')),'')
if __name__=='__main__':
    b=pd.read_csv(U+'ball_by_ball.csv'); m=pd.read_csv(U+'matches.csv'); c=pd.read_csv(U+'competitions.csv')
    pm=pd.read_csv(U+'competition_team_player_mapping.csv')
    b=b.merge(m[['match_id','comp_id','match_date','stage','win_team_id','result','revised_target','first_inn_revised_overs','second_inn_revised_overs','venue_id']],on='match_id').merge(c[['comp_id','comp_name','match_format']],on='comp_id')
    # scope: IPL + T20I only, innings 1-2, no DLS-affected, decisive results
    b['is_ipl']=b.comp_name.str.startswith('IPL')
    scope=b.is_ipl|(b.match_format=='T20I')
    print('dropped non IPL/T20I balls',(~scope).sum())
    b=b[scope]
    b=b[b.innings<=2]
    dls=b.revised_target.notna()|b.first_inn_revised_overs.notna()|b.second_inn_revised_overs.notna()
    print('DLS balls dropped',dls.sum(), b[dls].match_id.nunique())
    b=b[~dls]
    b=b.sort_values(['match_id','innings','innings_ball_num']).reset_index(drop=True)
    # run accounting
    b['wide']=(b.extras_type=='wide'); b['nb']=(b.extras_type=='Overstep')
    b['bl']=b.extras_type.isin(['byes','legbyes'])
    b['legal']=~(b.wide|b.nb)
    b['team_runs']=b.runs+b.wide.astype(int)+b.nb.astype(int)+b.extras_2_runs+b.bl.astype(int)*1  # +1 imputed for byes/legbyes
    b['wk']=b.is_wicket & ~b.dismissal_type.isin(['Retire Out'])
    b['bowler_wk']=b.wk & ~b.dismissal_type.isin(['RunOut','Obstracting the field','Obstructing the field'])
    g=b.groupby(['match_id','innings'])
    b['cum_runs_after']=g.team_runs.cumsum(); b['cum_w_after']=g.wk.cumsum(); b['cum_legal_after']=g.legal.cumsum()
    b['runs_before']=b.cum_runs_after-b.team_runs; b['w_before']=b.cum_w_after-b.wk.astype(int); b['legal_before']=b.cum_legal_after-b.legal.astype(int)
    tot=b[b.innings==1].groupby('match_id').team_runs.sum().rename('inn1_total')
    b=b.merge(tot,on='match_id',how='left')
    b['target']=np.where(b.innings==2,b.inn1_total+1,np.nan)
    # match must have both innings
    have=b.groupby('match_id').innings.nunique(); ok=have[have==2].index
    b=b[b.match_id.isin(ok)]
    # winner of batting team
    b['bat_win']=np.where(b.win_team_id==b.batting_team_id,1.0,np.where(b.win_team_id==b.bowling_team_id,0.0,np.nan))
    print('rows w/o decisive winner',b.bat_win.isna().sum(), b[b.bat_win.isna()].match_id.nunique())
    b=b[b.bat_win.notna()].reset_index(drop=True)
    # inning-length sanity
    il=b.groupby(['match_id','innings']).legal.sum().unstack()
    print((il<60).sum())
    print(b.shape, b.match_id.nunique(), b.is_ipl.groupby(b.match_id).first().value_counts())
    b.to_pickle('balls.pkl')
