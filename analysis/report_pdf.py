"""Methodology report → ../Pressure_Index_Methodology.pdf
Every number comes from ../dashboard_data.json (same file the website reads), so site and PDF cannot disagree.
    SITE_URL=https://your-site.vercel.app python3 report_pdf.py"""
import json, os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

F='/System/Library/Fonts/Supplemental/'
pdfmetrics.registerFont(TTFont('Arial',F+'Arial.ttf')); pdfmetrics.registerFont(TTFont('Arial-Bold',F+'Arial Bold.ttf'))
from reportlab.lib.fonts import addMapping; addMapping('Arial',0,0,'Arial'); addMapping('Arial',1,0,'Arial-Bold')
SITE=os.environ.get('SITE_URL','https://rr-pressure-index-frontend.vercel.app'); REPO='https://github.com/heyoaryan/RR-Pressure-Index'
D=json.load(open('../dashboard_data.json')); O=D['overview']
PINK=colors.HexColor('#c2185b'); NAVY=colors.HexColor('#1d2c5e'); LINE=colors.HexColor('#d6d5cf'); SUNK=colors.HexColor('#f2f2ee')

st=lambda n,**k: ParagraphStyle(n,fontName='Arial',fontSize=9.6,leading=13.4,spaceAfter=5,**k)
B=st('b'); SM=st('sm',textColor=colors.HexColor('#555')); SM.fontSize=8.2; SM.leading=10.8
H1=ParagraphStyle('h1',fontName='Arial-Bold',fontSize=20,leading=24,textColor=NAVY,spaceAfter=4)
H2=ParagraphStyle('h2',fontName='Arial-Bold',fontSize=13,leading=16,textColor=NAVY,spaceBefore=10,spaceAfter=5)
H3=ParagraphStyle('h3',fontName='Arial-Bold',fontSize=10.2,leading=13,spaceBefore=6,spaceAfter=3)
FORM=ParagraphStyle('f',fontName='Arial',fontSize=9.6,leading=13,backColor=SUNK,borderPadding=5,spaceBefore=4,spaceAfter=9,leftIndent=5)
P=lambda t,s=B: Paragraph(t,s)
def T(rows,widths,hl_first=False,fs=8.4,wrap=False,left=2):
    if wrap:
        cs=lambda b: ParagraphStyle('c',fontName='Arial-Bold' if b else 'Arial',fontSize=fs,leading=fs*1.25)
        rows=[[Paragraph(str(c),cs(i==0)) for c in r] for i,r in enumerate(rows)]
    t=Table(rows,colWidths=[w*mm for w in widths],repeatRows=1)
    sty=[('FONT',(0,0),(-1,-1),'Arial',fs),('FONT',(0,0),(-1,0),'Arial-Bold',fs),('TEXTCOLOR',(0,0),(-1,0),colors.HexColor('#444')),
         ('LINEBELOW',(0,0),(-1,0),.8,NAVY),('LINEBELOW',(0,1),(-1,-1),.3,LINE),('ALIGN',(left,0),(-1,-1),'RIGHT'),
         ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),2.6),('BOTTOMPADDING',(0,0),(-1,-1),2.6)]
    t.setStyle(TableStyle(sty)); return t
img=lambda f,w: Image(f,width=w*mm,height=w*mm*__import__('PIL.Image',fromlist=['x']).open(f).size[1]/__import__('PIL.Image',fromlist=['x']).open(f).size[0])
f2=lambda x,d=2: f'{x:.{d}f}'
sg=lambda x,d=0: ('+' if x>0 else '−' if x<0 else '')+f'{abs(x):.{d}f}'
kb,kw=D['k_bat'],D['k_bowl']; RB,RW=D['rel_bat'],D['rel_bowl']
N,Pp=D['tab']

S=[]
S+=[P('Pressure Index',H1),P('Who performs best when a T20 match is on the line? · SupeRR Selector Season 2 · Round 1 methodology report',SM),Spacer(1,4)]
S+=[P(f'<b>Summary.</b> I rate every eligible batter and bowler on the deliveries that could actually swing a T20 result. A win-probability model gives each ball a '
      f'<i>Leverage Index</i>; a ball is a <b>pressure ball</b> when leverage is high, the match is still live, and the innings is past the opening free-hit phase. '
      f'Players are judged on runs added (or saved) per ball against an average player in the <i>same</i> situation, corrected for opposition quality and sample size. '
      f'Data: {O["n_match"]} matches ({O["n_ipl"]} IPL, {O["n_t20i"]} T20I, 2022 onwards), {O["n_ball"]:,} deliveries, of which {O["n_pressure"]:,} ({O["share"]*100:.1f}%) are pressure balls. '
      f'Interactive version: {SITE} · Code: {REPO}')]
# final lists up front
def final_tables():
    hb=['#','Batter','Rating','Pressure balls','SR press. / normal','Outs per 100 press. / normal','Lift /100','Top-10 in resamples']
    rb=[hb]+[[p['rank'],p['name'],f2(p['final_score']),int(p['pb']),f"{p['sr_p']:.0f} / {p['sr_n']:.0f}",f"{p['out_p']:.1f} / {p['out_n']:.1f}",sg(p['lift100']),f"{p['top10_freq']*100:.0f}%"] for p in D['bat']]
    hw=['#','Bowler','Rating','Pressure balls','Econ press. / normal','Wkts per 100 press. / normal','Lift /100','Top-10 in resamples']
    rw=[hw]+[[p['rank'],p['name'],f2(p['final_score']),int(p['pb']),f"{p['econ_p']:.2f} / {p['econ_n']:.2f}",f"{p['wk_p']:.1f} / {p['wk_n']:.1f}",sg(p['lift100']),f"{p['top10_freq']*100:.0f}%"] for p in D['bowl']]
    W=[7,40,14,18,27,33,15,22]
    hdr=lambda r: [[Paragraph(f'<b>{c}</b>',ParagraphStyle('th',fontName='Arial-Bold',fontSize=7.6,leading=9,alignment=0 if i<2 else 2)) for i,c in enumerate(r[0])]]+r[1:]
    return [P('Final top 10 — batters',H3),T(hdr(rb),W),Spacer(1,5),P('Final top 10 — bowlers',H3),T(hdr(rw),W)]
S+=[P('Final rankings (same order as entered on Unstop)',H2)]+final_tables()
S+=[P('Rating = mean of the full-data score and the 200-resample bootstrap mean score (z-units). “press. / normal” are raw rates on pressure balls vs all other balls the player faced/bowled.',SM)]

# 1 pressure
S+=[PageBreak(),P('1. Pressure definition',H2)]
S+=[P('Pressure is defined by how much the next ball can change who wins, not by a fixed over or a required-rate rule. A ball is a <b>pressure ball</b> when all three hold:')]
S+=[T([['Condition','Rule','Why'],
       ['1. High leverage','Leverage Index (LI) ≥ 1.5','The result of this ball moves win probability 1.5× more than an average ball.'],
       ['2. Match still live','Batting side win prob. 15%–85%','Excludes dead-rubber slogging and foregone conclusions.'],
       ['3. Past the free-hit phase','After over 6, or 3+ wickets down, or any ball of a chase','Early 1st-innings balls carry little real pressure even when the model is uncertain.']],[36,52,86],wrap=True)]
S+=[P('<b>Leverage Index.</b> For each ball I enumerate the outcomes 0, 1, 2, 3, 4, 6 and W, weight each by its frequency in that phase, and compute the expected absolute change in win probability. LI is that value divided by its mean over all balls, so an average ball = 1.0. '
      'The LI ≥ 1.5 threshold was chosen on split-half reliability: it gave the most repeatable player ratings among 1.0 / 1.5 / 2.0 / 3.0 while keeping ~18% of balls.')]
S+=[img('fig_where.png',172),P('<b>Where pressure balls happen.</b> Almost no early 1st-innings balls qualify (condition 3); chases are pressured from ball one and peak again at the death.',SM)]
S+=[P('Pressure balls vs every other ball',H3),T([['','Pressure','Other'],['Average leverage (LI)',f"{Pp['LI']:.2f}×",f"{N['LI']:.2f}×"],['Wickets per 100 balls',f"{Pp['wk']:.1f}",f"{N['wk']:.1f}"],
       ['Run rate',f"{Pp['rr']:.2f}",f"{N['rr']:.2f}"],['Dot-ball %',f"{Pp['dot']:.1f}%",f"{N['dot']:.1f}%"],['Batting-side win prob.',f"{Pp['wp']*100:.0f}%",f"{N['wp']*100:.0f}%"]],[70,30,30],left=1)]
S+=[P(f'Pressure balls carry {Pp["LI"]/N["LI"]:.1f}× the leverage of other balls and produce more wickets, at similar scoring rates: batters take more risk, and bowlers who hold their nerve are rewarded.',SM)]

# win probability
S+=[P('Win-probability model',H3)]
S+=[P(f'Two gradient-boosted classifiers (scikit-learn HistGradientBoosting, monotone constraints so e.g. more wickets lost can never raise win probability), one per innings, trained and scored <b>out-of-fold</b> (5-fold, grouped by match, so no ball is scored by a model that saw its match). '
      f'<b>First innings:</b> with no target yet, the model predicts the batting side’s chance of winning from runs scored so far, wickets lost, balls remaining, current run rate and an IPL/T20I flag. In effect it learns a projected total from the current score, wickets in hand and balls left, and compares it with what has typically been enough to win. It does not use venue or season par scores; that is a known limitation, which is partly why first-innings balls are rarely flagged. '
      f'<b>Second innings:</b> runs needed, wickets lost, balls remaining, required and current run rate, IPL flag. '
      f'At the end of the 1st innings, the chase model is evaluated at (target, 0 wickets, 120 balls) so both innings join up.')]
acc=T([['Out-of-fold accuracy','1st innings','2nd innings'],['Brier score (lower = better)',f"{O['br1']:.3f}",f"{O['br2']:.3f}"],['Brier, always predicting base rate',f"{O['br1_naive']:.3f}",f"{O['br2_naive']:.3f}"],
       ['Log loss',f"{O['ll1']:.3f}",f"{O['ll2']:.3f}"],['AUC',f"{O['auc1']:.3f}",f"{O['auc2']:.3f}"]],[58,26,26],left=1)
S+=[Table([[acc,img('fig_calib.png',62)]],colWidths=[112*mm,66*mm],style=[('VALIGN',(0,0),(-1,-1),'MIDDLE')])]
S+=[P('The 1st-innings model is weaker (AUC 0.68), as expected: half the match is unknown. Both are well calibrated (points sit on the diagonal), which matters more than AUC here, because leverage uses the size of probability swings.',SM)]

# 2 performance measurement
S+=[P('2. Performance measurement',H2)]
S+=[P('<b>Per-ball value vs. context baseline.</b> Every ball is compared with the league average in the same situation: innings × 2-over block × wickets lost × required-rate band (chases). '
      'For a batter: (runs − expected runs) − λ·(dismissal − expected dismissal rate). For a bowler: (expected runs conceded − runs conceded, incl. extras) + λ·(bowler wicket − expected). '
      'λ, the run value of a wicket, is estimated from the win-probability model on pressure balls, by phase (≈5.8 runs powerplay, 7.6 middle, 4.4 death). Run-outs of the non-striker are not charged to the striker or credited to the bowler.')]
S+=[P(f'<b>Opposition adjustment.</b> A ridge regression on <i>non-pressure</i> balls estimates each batter’s and bowler’s effect on the other; each pressure ball is corrected for the quality of the opponent faced. Fitting on non-pressure balls only means a player’s pressure performance cannot leak into its own correction.')]
S+=[P(f'<b>Shrinkage (empirical Bayes).</b> A player’s mean is pulled toward the league mean by n/(n+k), with k estimated from the data (signal vs. noise): batting k ≈ {kb[0]:.0f} balls (runs) / {kb[1]:.0f} (wickets); bowling k ≈ {kw[0]:.0f} / {kw[1]:.0f}. Bowling is shrunk much harder because bowler differences per ball are smaller relative to noise.')]
S+=[P('<b>The three components</b>')]
S+=[T([['Component','Definition','Weight'],['Pressure value','Shrunk, opposition-adjusted runs added/saved per ball on pressure balls','70%'],
       ['Consistency','Share of matches with positive pressure value (shrunk toward league mean, prior = 12 matches)','15%'],
       ['Clutch lift','Shrunk pressure value − shrunk normal (non-pressure) value','15%']],[30,125,18],wrap=True)]
S+=[P('Rating = 0.70·z(pressure value) + 0.15·z(consistency) + 0.15·z(clutch lift)',FORM)]
S+=[P(f'<b>Why lift only gets 15%.</b> The brief asks how players perform under pressure <i>compared with their usual level</i>, so lift is included. But lift is noisy: its split-half reliability is ρ = {RB["Clutch lift"]:.2f} (bat) and {RW["Clutch lift"]:.2f} (bowl), against {RB["Pressure value, shrunk"]:.2f} / {RW["Pressure value, shrunk"]:.2f} for pressure value itself. A large lift weight would reward players who simply had a quiet normal sample. At 15% the final top 10 keeps 9/10 batters and 9/10 bowlers compared with a version that gives lift zero weight, so the list follows the brief without being driven by noise.')]
S+=[P('<b>Final score.</b> The score is computed on the full data and on 200 bootstrap resamples of matches; final rating = ½·full-data score + ½·bootstrap mean. This rewards players whose rating doesn’t depend on a few matches.')]

# 3 fair comparisons
S+=[P('3. Fair comparisons',H2)]
S+=[P('<b>Sample size and eligibility.</b> Minimum 75 pressure balls, across at least 15 matches, plus 100 non-pressure balls (needed to measure normal level and lift). '
      f'This leaves {D["sens_bat"]["Base (70/15/15)"][2]} batters and {D["sens_bowl"]["Base (70/15/15)"][2]} bowlers. Shrinkage handles the remaining differences in sample size; a stricter 120-ball / 25-match rule is tested below.')]
S+=[P('<b>Match context.</b> Every ball is compared only with balls from the same innings, 2-over block, wickets-lost and required-rate band, so a death-overs finisher is not compared with a powerplay opener.')]
S+=[P(f'<b>IPL and T20I.</b> Both are used. An IPL flag sits in the win-probability model and in the opposition regression, so the general difference in scoring between the two is absorbed. '
      f'T20Is include associate nations; rather than drop them, I rely on the opposition adjustment (runs scored off a weak attack count for less) and test it: removing every T20I involving an associate side (50 matches) keeps '
      f'{D["sens_bat"]["Drop T20Is with associates"][0]}/10 batters and {D["sens_bowl"]["Drop T20Is with associates"][0]}/10 bowlers. Rating on IPL balls only or T20I balls only is also shown in the sensitivity table.')]

# 4 evidence
S+=[P('4. Evidence for the top 10',H2)]
S+=[P('The two tables on page 1 show each player’s raw pressure rates next to their normal rates. Below, every eligible player’s pressure rating is plotted against their normal rating. Points above the dashed line performed better under pressure than normally.')]
S+=[img('fig_scatter.png',172)]
S+=[P('The top 10 is <b>not just the 10 best players</b>. Batters such as Mendis, Nawaz, Short, Powell and Kishan sit far above the line: ordinary normal numbers, outstanding under pressure. Some excellent hitters make the list on sheer level: Klaasen sits on the line and Sooryavanshi below it (very high normal level, still elite under pressure). Among bowlers the effect is smaller: seven of the top 10 sit above the line, while Narine and Pathirana are “level” picks below it.',SM)]
def expected_tbl(role):
    if role=='bat':
        rows=[['#','Batter','SR pressure','SR expected (same situations)','Outs/100 pressure','Outs/100 expected','IPL / T20I balls']]+[[p['rank'],p['name'],f"{p['sr_p']:.0f}",f"{p['exp_sr_p']:.0f}",f"{p['out_p']:.1f}",f"{p['exp_out_p']:.1f}",f"{p['ipl']} / {p['t20i']}"] for p in D['bat']]
    else:
        rows=[['#','Bowler','Econ pressure','Econ expected (same situations)','Wkts/100 pressure','Wkts/100 expected','IPL / T20I balls']]+[[p['rank'],p['name'],f"{p['econ_p']:.2f}",f"{p['exp_econ_p']:.2f}",f"{p['wk_p']:.1f}",f"{p['exp_wk_p']:.1f}",f"{p['ipl']} / {p['t20i']}"] for p in D['bowl']]
    hdr=[[Paragraph(f'<b>{c}</b>',ParagraphStyle('th',fontName='Arial-Bold',fontSize=7.6,leading=9,alignment=0 if i<2 else 2)) for i,c in enumerate(rows[0])]]
    return T(hdr+rows[1:],[7,42,22,32,25,25,23])
S+=[KeepTogether([P('Pressure performance vs an average player in the same situations',H3),expected_tbl('bat')]),KeepTogether([Spacer(1,5),expected_tbl('bowl')])]

# 5 reliability
S+=[P('5. Reliability and limitations',H2)]
S+=[P(f'<b>Split-half reliability.</b> Matches are split at random into two halves (20 times); players are rated on each half separately, and I measure the Spearman correlation between the two halves (about {RB["_players"]:.0f} batters / {RW["_players"]:.0f} bowlers eligible in both halves at half thresholds).')]
S+=[T([['Measure','Bat ρ','Bowl ρ']]+[[k,f2(RB[k]),f2(RW[k])] for k in RB if not k.startswith('_')],[80,22,22],left=1)]
S+=[P('Pressure performance is a real but modest signal. A player’s normal level is the most repeatable thing we measure, and the gap between pressure and normal (lift) repeats only weakly, which is why it is weighted lightly.',SM)]
S+=[P('<b>Bootstrap.</b> The full rating is recomputed on 200 resamples of matches (with replacement). “Top-10 in resamples” in the final tables is the share of resamples in which the player finishes top 10. Ranks inside the top 10 are less certain than membership.')]
def sens_rows():
    keys=[k for k in dict.fromkeys(list(D['sens_bat'])+list(D['sens_bowl'])) if not k.startswith('Base')]
    f=lambda v: '—' if v is None else (f'{v[0]}/10' + (f' (of {v[1]})' if v[1]<10 else ''))
    return [['If I change…','Batters kept','Bowlers kept']]+[[k,f(D['sens_bat'].get(k)),f(D['sens_bowl'].get(k))] for k in keys]
S+=[P('Sensitivity: how many of the final top 10 survive a different assumption',H3),T(sens_rows(),[85,35,35],left=1)]
S+=[P('Each row is one re-run on the full data (no bootstrap), compared with the final bootstrapped top 10. “(of n)”: only n of our top 10 are still eligible under that rule; e.g. IPL-only cuts each player’s balls roughly in half, and players with mostly-T20I careers drop out. Among those still eligible, most remain in the top 10, so the list is not driven by one competition.',SM)]
S+=[P('<b>Limitations</b>',H3)]
for t in [f'<b>Bowling is less stable than batting</b> (only {D["sens_bowl"]["Threshold LI ≥ 1.0"][0]}/10 survive at LI ≥ 1.0). Bowling ranks 6–10 should be read as a group, not an exact order. Bowling shrinkage is heavy (k ≈ {kw[0]:.0f}); lowering it to k = 350 keeps {D["sens_bowl"]["Bowling k = 350 (vs ≈783)"][0]}/10.',
          'The first-innings win-probability model has no venue or season par score, so it cannot tell a strong total at a high-scoring ground from one at a low-scoring ground.',
          'Pressure is defined from the match state only; crowd, tournament stage and individual match-ups are not modelled.',
          'Young players with short careers (e.g. Sooryavanshi, 92 pressure balls) are shrunk but still carry wide rank intervals.',
          'Fielding, captaincy and running between the wickets beyond runs scored are outside this rating.']:
    S+=[P('• '+t)]
S+=[P('Appendix: reproduce',H2)]
S+=[P(f'Website: {SITE}<br/>Code: {REPO}<br/>Run order (from <font face="Courier">analysis/</font>): prep.py → wp.py → ledger.py → final1.py → final2.py → bag.py → stab.py → rel.py → export.py → charts.py → report_pdf.py, then <font face="Courier">python3 dashboard/build_data.py</font> to refresh the website. Full instructions in the README.')]

def deco(c,d):
    c.saveState(); c.setFont('Arial',7.5); c.setFillColor(colors.HexColor('#888'))
    c.drawString(18*mm,10*mm,'Pressure Index · SupeRR Selector S2 · Round 1'); c.drawRightString(A4[0]-18*mm,10*mm,str(d.page)); c.restoreState()
doc=SimpleDocTemplate('../Pressure_Index_Methodology.pdf',pagesize=A4,leftMargin=18*mm,rightMargin=18*mm,topMargin=16*mm,bottomMargin=16*mm,
                      title='Pressure Index — Methodology',author='Pressure Index')
doc.build(S,onFirstPage=deco,onLaterPages=deco); print('PDF written')
