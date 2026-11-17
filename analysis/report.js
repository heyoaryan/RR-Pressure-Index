const fs=require('fs');
const {Document,Packer,Paragraph,TextRun,Table,TableRow,TableCell,ImageRun,HeadingLevel,AlignmentType,WidthType,BorderStyle,ShadingType,LevelFormat,Footer,PageNumber}=require('docx');
const R=JSON.parse(fs.readFileSync('rows.json'));
const PINK='C2185B', NAVY='13264D', GREY='F3F4F8';
const W=9906;
const P=(t,o={})=>new Paragraph({spacing:{after:110,line:276},...o.p,children:(Array.isArray(t)?t:[t]).map(x=>typeof x==='string'?new TextRun({text:x,font:'Arial',size:o.size||20,bold:o.bold,italics:o.it,color:o.color}):x)});
const B=(t)=>new TextRun({text:t,font:'Arial',size:20,bold:true});
const T_=(t)=>new TextRun({text:t,font:'Arial',size:20});
const H1=t=>new Paragraph({heading:HeadingLevel.HEADING_1,children:[new TextRun({text:t,font:'Arial'})]});
const H2=t=>new Paragraph({heading:HeadingLevel.HEADING_2,children:[new TextRun({text:t,font:'Arial'})]});
const bullet=(t)=>new Paragraph({numbering:{reference:'b',level:0},spacing:{after:70,line:270},children:(Array.isArray(t)?t:[t]).map(x=>typeof x==='string'?T_(x):x)});
const bd={style:BorderStyle.SINGLE,size:4,color:'C8CBD6'};
const borders={top:bd,bottom:bd,left:bd,right:bd};
function table(head,rows,widths,fs=16,boldFirstCols=[1]){
  const mk=(txt,w,isH,ci,ri)=>new TableCell({width:{size:w,type:WidthType.DXA},borders,margins:{top:50,bottom:50,left:70,right:70},
    shading:isH?{fill:NAVY,type:ShadingType.CLEAR,color:'auto'}:(ri%2?{fill:GREY,type:ShadingType.CLEAR,color:'auto'}:undefined),
    children:[new Paragraph({alignment:ci===1&&!isH?AlignmentType.LEFT:(isH&&ci===1?AlignmentType.LEFT:AlignmentType.CENTER),children:[new TextRun({text:String(txt),font:'Arial',size:fs,bold:isH||boldFirstCols.includes(ci),color:isH?'FFFFFF':undefined})]})]});
  return new Table({width:{size:widths.reduce((a,b)=>a+b,0),type:WidthType.DXA},columnWidths:widths,rows:[
    new TableRow({tableHeader:true,children:head.map((h,i)=>mk(h,widths[i],true,i,0))}),
    ...rows.map((r,ri)=>new TableRow({cantSplit:true,children:r.map((c,i)=>mk(c,widths[i],false,i,ri))}))]});
}
const img=(f,w,h)=>new Paragraph({alignment:AlignmentType.CENTER,spacing:{before:80,after:80},children:[new ImageRun({type:'png',data:fs.readFileSync(f),transformation:{width:w,height:h},altText:{title:f,description:f,name:f}})]});
const cap=t=>P(t,{size:16,it:true,color:'555555',p:{alignment:AlignmentType.CENTER}});
const kids=[];
const add=(...x)=>x.forEach(e=>kids.push(e));
add(new Paragraph({spacing:{after:60},children:[new TextRun({text:'SupeRR Selector Season 2 · Round 1',font:'Arial',size:20,bold:true,color:PINK})]}),
 new Paragraph({heading:HeadingLevel.TITLE,children:[new TextRun({text:'Who Delivers When It Matters? A Leverage-Based Pressure Rating for T20 Batters and Bowlers',font:'Arial'})]}),
 P('Methodology report · IPL and T20I ball-by-ball data, 2022 onwards',{color:'555555'}));

add(H1('1. Summary'));
add(P([T_('We define pressure through '),B('leverage'),T_(': how much a single delivery can move the match, measured with a win-probability model trained on the supplied ball-by-ball data. A delivery is "high-pressure" when its leverage is at least 1.5× the average delivery, the contest is still alive (win probability between 15% and 85%), and the innings is past the opening six overs, three or more wickets down, or a chase. This flags 27,184 of 188,151 deliveries (14.5%) in 788 matches (357 IPL, 431 T20I).')]));
add(P([T_('Each player is then scored on the high-pressure deliveries only, as '),B('runs above what an average player produces in the same match context'),T_(' (innings, over, wickets lost and required-rate band), with wickets converted into runs using the win-probability model, adjusted for the quality of the opposition, and shrunk towards the league average in proportion to sample size. The final rating is 80% pressure output and 20% consistency, and is averaged over 200 bootstrap resamples of matches to stabilise it.')]));
add(P([B('Honest headline: '),T_('pressure performance is only moderately repeatable (split-half rank correlation of roughly 0.2). A player\'s own "usual" level predicts his pressure output about as well as past pressure output does, and the pressure-minus-usual "clutch" gap does not predict anything (it is slightly negative). We therefore rank on shrunk absolute pressure output and report the gap only as a diagnostic. Positions 1 to 10 are best read as a strong shortlist with a probable order, not as exact ranks, and the report quantifies that uncertainty.')]));
add(H2('Final rankings'));
const nm=(a)=>a.map(r=>[r[0],r[1]]);
add(table(['Rank','Top-10 batters under pressure','Rank','Top-10 bowlers under pressure'],R.bat.map((r,i)=>[r[0],r[1],R.bowl[i][0],R.bowl[i][1]]),[700,4253,700,4253],20,[1,3]));
add(P(''));
add(P('Next in line (not selected): batters '+R.next_bat.map(r=>`${r[1]} (${r[2]})`).join(', ')+'; bowlers '+R.next_bowl.map(r=>`${r[1]} (${r[2]})`).join(', ')+'. Final rating scores in brackets, for comparison with the table in section 6.',{size:18,color:'444444'}));

add(H1('2. Data and preparation'));
add(bullet('Source files: ball_by_ball, matches, competitions, teams, playing_eleven and competition_team_player_mapping. Scope is IPL 2022 to 2026 and men\'s T20Is. Two other competitions in the files (emerging/rising-stars tournaments) were excluded because they are neither IPL nor T20I (6,985 deliveries).'));
add(bullet('Super-over innings, 34 matches with a revised (DLS) target or reduced overs, and 2 matches without a decisive result were excluded, because the required rate is not comparable or the label is undefined. 788 matches and 188,151 deliveries remain.'));
add(bullet('Extras coding. In this file "runs" is runs off the bat only, and extras1_runs is a category code rather than a run count. Wides and no-balls (coded "Overstep") are charged 1 run plus extras_2_runs. Bye and leg-bye deliveries carry no run values at all. We checked totals against the stated winning margins in 306 run-margin matches: with no correction the margin matched exactly in 13% of matches (mean error 3.4 runs); imputing 1 run per bye or leg-bye raised this to 27% (mean error 2.3 runs), so we impute 1 run. The residual noise affects only the score used for chase targets, not player attribution.'));
add(bullet('Wickets: retired-out is not a wicket. Run-outs are not credited to bowlers. A run-out of the non-striker is not charged to the striker. Wides are not balls faced by the batter.'));
add(bullet('For each delivery we rebuild the pre-ball state: runs, wickets lost, legal balls bowled, target (first-innings total + 1), runs needed, balls left, required and current run rate.'));

add(H1('3. How pressure is defined'));
add(H2('3.1 Win-probability and leverage'));
add(P('Pressure is about what is at stake, so we measure it directly. We trained gradient-boosted win-probability models (one per innings, with monotonic constraints so that more runs needed never helps the chasing side and more wickets in hand never hurts). Features are runs needed (chase) or runs scored (first innings), wickets lost, balls left, required and current run rate, and an IPL/T20I flag. All predictions are out-of-fold, using five folds grouped by match, so a match never informs its own probabilities.'));
add(P(`Validation: chase model AUC ${0.889}, log-loss 0.417, Brier 0.136; first-innings model AUC 0.679, log-loss 0.646 (the first innings is inherently less predictable). Calibration is shown in Figure 1A.`));
add(P([T_('For every delivery we then compute the '),B('Leverage Index (LI)'),T_(': the expected absolute change in win probability on the next ball, taking the model\'s win probability after each possible outcome (0, 1, 2, 3, 4, 6, wicket) weighted by how often that outcome occurs in that phase of the innings, divided by the average of the same quantity over all deliveries. LI = 1 is an average ball; LI = 3 is a ball that matters three times as much.')]));
add(H2('3.2 The pressure rule'));
add(P('A delivery is high-pressure when all of the following hold:'));
add(bullet([B('LI ≥ 1.5. '),T_('The ball moves the match at least 50% more than average. This combines required rate, wickets in hand, balls remaining and closeness in one number.')]));
add(bullet([B('Contest alive: '),T_('win probability between 15% and 85%. A dead rubber chase is not pressure.')]));
add(bullet([B('Stage filter: '),T_('legal balls bowled ≥ 36, or three or more wickets down, or second innings. This stops early first-innings noise (where the win model has little information) from being labelled pressure, while still treating an early collapse as pressure.')]));
add(P('The 1.5 threshold was chosen by a reliability trade-off: lower thresholds dilute pressure with ordinary balls, higher ones leave too few balls per player (split-half rank correlation of the batting metric: 0.27 at LI ≥ 1.0, 0.25 at 1.5, 0.17 at 2.0). We report sensitivity to this choice in section 7.'));
add(img('fig_pressure.png',620,174));
add(cap('Figure 1. (A) Calibration of the out-of-fold win-probability models. (B) Share of deliveries flagged high-pressure by over. (C) Distribution of the Leverage Index.'));
add(H2('3.3 Does the definition separate pressure from ordinary play?'));
add(table(['Measure (legal deliveries)','Ordinary','High-pressure'],[
 ['Deliveries','154,404','25,944'],['Mean Leverage Index','0.76','2.41'],['Mean win probability of batting side','0.49','0.50'],
 ['Wickets per 100 balls','5.48','6.12'],['Dot-ball %','37.1','36.4'],['Run rate (runs per over)','8.47','8.57'],['Average wickets down','2.65','2.84']],[4300,2800,2806],18,[0]));
add(P(''));
add(P('High-pressure balls carry about three times the leverage and are played with the match on a knife-edge (win probability close to 50%). Wickets fall 12% more often. Run rates are similar, which is exactly the point: pressure changes the cost of mistakes and the value of runs, not the average scoring rate, so measuring it needs a model of stakes rather than a simple run-rate filter. By phase, 25% of powerplay chase deliveries, 17% of middle-over chase deliveries and 27% of death-over chase deliveries are flagged, against 2%, 9% and 14% in the first innings (Figure 1B).'));

add(H1('4. How performance is measured'));
add(H2('4.1 Context-adjusted value per delivery'));
add(P('For every delivery we compare what happened with the league average in an identical context (innings × two-over block × wickets lost × required-rate band in chases):'));
add(bullet([B('Batters: '),T_('(runs off the bat − expected runs) and (not being dismissed − expected non-dismissal), the latter converted to runs using the run value of a wicket.')]));
add(bullet([B('Bowlers: '),T_('(expected runs − runs conceded including wides and no-balls) and (bowler wicket − expected bowler wickets) in the same way.')]));
add(P('Run value of a wicket: we regressed win-probability change on runs and wicket on high-pressure deliveries. A wicket costs the batting side the equivalent of 5.8 runs in the powerplay, 7.6 in the middle overs and 4.4 at the death (relative to a dot ball), and these phase-specific values are used. This makes wickets and runs comparable for both roles with one formula.'));
add(H2('4.2 Opposition adjustment'));
add(P('IPL attacks and T20I opponents differ greatly. On ordinary (non-pressure) deliveries only, we fitted a ridge regression of each component on batter and bowler indicators plus an IPL flag. The bowler coefficient is the average amount by which that bowler depresses or inflates batting returns; the batter coefficient does the same for bowling. These effects are subtracted from every pressure delivery. Using only non-pressure balls to estimate them avoids leaking a player\'s pressure result into his own adjustment. Players who appear in both competitions link the two scales.'));
add(H2('4.3 Player baseline ("usual" level)'));
add(P('Each player\'s usual level is his mean adjusted value on non-pressure deliveries, shrunk in the same way as below. The pressure-minus-usual difference is reported as "lift" (Table 3, section 7.1). It answers the question in the brief of how a player compares with his own normal, but see section 7 for why it is not used in the ranking.'));
add(H2('4.4 Small-sample control (empirical-Bayes shrinkage)'));
add(P('A player with 90 pressure balls can look brilliant by luck. Runs and wickets components are each shrunk toward the league pressure average by n/(n + k), where k is estimated from the data as the ratio of ball-level noise variance to between-player variance. The estimates are k ≈ 127 balls (batter runs), 174 (batter dismissals), 783 (bowler runs saved) and 627 (bowler wickets). Intuitively, bowling outcomes are noisier relative to true skill, so bowlers are shrunk harder, and a bowler\'s wicket count is treated with correspondingly more scepticism.'));
add(H2('4.5 Consistency'));
add(P('Consistency is the share of a player\'s high-pressure innings (or spells) in which his net adjusted value was positive, pulled toward the league share (0.50) with a prior weight of 12 innings, so that short samples are not rewarded.'));
add(H2('4.6 Final rating'));
add(P('Rating = 0.8 × z(shrunk pressure value) + 0.2 × z(shrunk consistency), where z is computed across eligible players. The rating is computed on the full data and on 200 bootstrap resamples of matches (new matches drawn with replacement); the reported score is the average of the full-data score and the bootstrap mean, which damps the influence of any single match or innings. The weights were chosen by out-of-sample testing (section 7), not by preference.'));

add(H1('5. Fair comparisons'));
add(bullet([B('Eligibility: '),T_('at least 75 high-pressure deliveries, in at least 15 different matches, and at least 100 ordinary deliveries to establish a baseline. This leaves 114 batters and 115 bowlers. A two-sided check at 120 / 25 / 150 changes the top 10 by one or two names (section 7).')]));
add(bullet([B('Different contexts: '),T_('expected values are conditioned on innings, over, wickets and required rate, so a finisher who always bats at the death is compared only with other death-overs batters in similar chases. A powerplay bowler is compared with powerplay bowlers.')]));
add(bullet([B('IPL versus T20I: '),T_('both are scored on the same scale with an IPL flag in the win model and in the opposition regression. Pressure is spread evenly (14.3% of IPL and 14.5% of T20I deliveries). Players seen mostly in one competition are connected to the rest only through a few shared opponents, so their adjustment is less certain. This matters for several selected names and is discussed in section 8.')]));
add(bullet([B('Format of results: '),T_('every table shows how many deliveries came from the IPL and from T20Is so the reader can judge for themselves.')]));

add(H1('6. Evidence for the top 10'));
add(P('Table 1. Top-10 batters. PV = pressure value, in runs per 100 deliveries above the average player in the same context (raw = unshrunk; shrunk figure is shown relative to the average eligible player). SR = strike rate; Exp. = what an average player produces in the same situations; Out% = dismissals per 100 balls faced.',{size:17,it:true}));
add(table(['#','Batter','Press. balls','Press. inns.','IPL / T20I','SR','Exp. SR','Out %','Exp. Out %','Raw PV','Shrunk PV vs avg','Pos. inns.','Top-10 freq.','Score'],R.bat,[340,1480,580,580,780,500,560,520,580,520,680,640,640,520],14));
add(P(''));
add(P('Table 2. Top-10 bowlers. Econ = runs conceded per over including extras; Exp. = average in the same situations; Wkt % = bowler-credited wickets per 100 balls.',{size:17,it:true}));
add(table(['#','Bowler','Press. balls','Press. spells','IPL / T20I','Econ','Exp. Econ','Wkt %','Exp. Wkt %','Raw PV','Shrunk PV vs avg','Pos. spells','Top-10 freq.','Score'],R.bowl,[340,1480,580,580,780,500,560,520,580,520,680,640,640,520],14));
add(P(''));
add(img('fig_top10.png',620,221));
add(cap('Figure 2. Final ratings with the share of 200 bootstrap resamples in which each player stays inside the top 10.'));
add(H2('Reading the table'));
add(bullet([B('Vaibhav Sooryavanshi '),T_('has the most extreme output (strike rate 248 against an expected 141 on pressure balls) but only 92 balls, so shrinkage cuts his score by roughly half. He still ranks first and stays in the top 10 in 65% of resamples.')]));
add(bullet([B('Klaasen, Suryakumar Yadav, Powell and Tim David '),T_('combine large samples (180 to 320 pressure balls, 41 to 64 innings) with a strong gap over expectation, making them the best-evidenced batting names.')]));
add(bullet([B('Kamindu Mendis '),T_('is dismissed on 2.0% of pressure balls versus an expected 6.1%, but 89 of his 100 balls are T20Is and he sits on the 16-innings edge of eligibility.')]));
add(bullet([B('Hazlewood '),T_('concedes 7.6 an over under pressure against an expected 9.1 and takes wickets at 1.7× the expected rate. '),B('Narine '),T_('(economy 6.0 against 8.0) and '),B('Abrar Ahmed '),T_('(5.7 against 7.8) are the run-saving leaders. '),B('Chahal '),T_('and '),B('Krunal Pandya '),T_('are well-evidenced (325 and 208 pressure balls).')]));

add(H1('7. Reliability, validation and sensitivity'));
add(H2('7.1 Is pressure performance a stable trait?'));
add(P('We repeated 20 random splits of the 788 matches into halves, scored players in each half and correlated the two ranks (Spearman). For players with enough balls in both halves:'));
add(table(['Predictor measured on half A','Batters: rank-correlation with pressure value on half B','Bowlers'],[
 ['Pressure value, unshrunk','0.18','0.21'],['Pressure value, shrunk (our measure)','0.21','0.23'],['Rating used in final (80% PV + 20% consistency)','0.22','0.22'],['Consistency alone','0.17','0.18'],['Usual (non-pressure) level alone','0.22','0.24'],['Pressure minus usual ("clutch lift")','−0.11','−0.03']],[4500,3200,2206],18,[0]));
add(P(''));
add(P('Three conclusions follow. First, shrinkage helps. Second, pressure performance is only modestly repeatable, with correlations around 0.2 even with ~100 pressure balls in each half, which is the real ceiling on any ranking built from this data. Third, there is no evidence that players have a distinct "clutch" skill beyond their general ability: the difference between pressure and usual form is noise. The right way to find players "reliable under pressure" is therefore to find those who are both excellent in general and have delivered in high-leverage moments, which is what an absolute, shrunk pressure value measures. We keep the lift column for transparency but give it zero weight.'));
add(P('Table 3. Usual level, pressure level and lift for the selected players (shrunk, runs per 100 deliveries above context expectation; lift = pressure minus usual). Several selected players have a negative lift because their ordinary form is already excellent. That is not a weakness: it is the same skill showing up in both situations.',{size:17,it:true}));
add(table(['Batter','Usual','Pressure','Lift','Bowler','Usual','Pressure','Lift'],R.lift.bat.map((r,i)=>[r[0],r[1],r[2],r[3],R.lift.bowl[i][0],R.lift.bowl[i][1],R.lift.bowl[i][2],R.lift.bowl[i][3]]),[1900,640,800,640,1900,640,800,640],16,[0,4]));
add(P(''));
add(H2('7.2 Bootstrap stability'));
add(P('Across 200 match-level resamples, no player is certain to stay in the top 10. For the batters the most stable are Klaasen (62%), Sooryavanshi (65%), Mendis (54%) and Powell (52%); for the bowlers Hazlewood (67%), Abrar Ahmed (62%), Krunal Pandya (55%) and Narine (54%). The lower figures on ranks 8 to 10 (29% to 44% for batters, 16% to 40% for bowlers) mean that those positions are close calls with the next group (batters: Rinku Singh, Rashid Khan, Tilak Varma; bowlers: Mohsin Khan, Hasaranga, Santner).'));
add(H2('7.3 Sensitivity of the top 10'));
add(table(['Change to method','Batters: players retained of 10','Bowlers retained of 10'],[
 ['Pressure threshold LI ≥ 1.0','8','4'],['Pressure threshold LI ≥ 2.0','5','6'],['Pressure value only (no consistency)','9','8'],['Weights 70/15/15 incl. lift','9','9'],['Stricter eligibility (120 balls, 25 innings)','8','9']],[4500,3200,2206],18,[0]));
add(P(''));
add(P('Batting is robust to everything except a very high threshold, which leaves too few balls per player. Bowling is the weaker model: its top 10 depends on the pressure threshold (only 4 retained at LI ≥ 1.0) because bowler outcomes are noisier and wickets are only weakly repeatable (raw split-half correlation around zero for wicket counts). Hazlewood, Chahal, Narine, Krunal Pandya and Abrar Ahmed hold their positions across most variants.'));

add(H1('8. Limitations'));
add(bullet('Sample size is the binding constraint. Even the busiest players have 300 to 430 pressure deliveries. The rankings carry real uncertainty and the bootstrap frequencies should be read alongside the ranks.'));
add(bullet('Opposition strength is estimated from the same data. T20I opponents include associate nations, and players who feature mainly in T20Is (Kamindu Mendis, Mohammad Nawaz, Abrar Ahmed, Sikandar Raza) are linked to the IPL scale only through shared opponents; their numbers could be flattered or depressed by the T20I adjustment.'));
add(bullet('The first-innings win model is weak (AUC 0.68) with no information on pitch, venue, team strength or toss, so first-innings pressure is identified less precisely than chase pressure. Venue and pre-match team strength would improve it.'));
add(bullet('Bye and leg-bye runs are missing and were imputed at 1 run each. Run-out and non-striker attribution is simplified. Ball-by-ball data does not tell us batter intent or field settings.'));
add(bullet('Batting position and role are not modelled explicitly beyond context (a finisher is compared with others in the same over and wicket state, not with other finishers). Left-right matchups and bowler type are ignored.'));
add(bullet('Leverage is partly endogenous: a batter who keeps a chase alive creates more high-pressure deliveries for himself. We kept the filter defined on the pre-ball state to reduce this, but cannot remove it.'));
add(bullet('The IPL 2026 season is included as supplied; results for players with few recent matches are less certain.'));

add(H1('9. Reproducing the analysis'));
add(P('The Python pipeline (pandas, scikit-learn, scipy) is supplied alongside this report. Order of execution and fixed parameters:'));
add(bullet('prep.py: filtering, extras accounting, pre-ball state (random seeds fixed).'));
add(bullet('wp.py: HistGradientBoosting win models (250 iterations, learning rate 0.05, 15 leaves, min 200 samples per leaf, monotone constraints), GroupKFold(5) by match, outcome distribution by phase, leverage index.'));
add(bullet('ledger.py and final1.py: pressure flag, context expectations, wicket run-values, ridge opposition adjustment (alpha 40; wicket components 120).'));
add(bullet('final2.py: component shrinkage, usual level, consistency, rating. valid.py, rel.py, rel2.py: split-half validation. bag.py and stab.py: 200 and 120 bootstrap replicates (seeds 7 and 42) and sensitivity. mkjson.py, evid.py, report.js: tables, charts, document.'));

const doc=new Document({
 styles:{default:{document:{run:{font:'Arial',size:20}}},
  paragraphStyles:[
   {id:'Title',name:'Title',basedOn:'Normal',run:{font:'Arial',size:40,bold:true,color:NAVY},paragraph:{spacing:{before:0,after:120}}},
   {id:'Heading1',name:'Heading 1',basedOn:'Normal',next:'Normal',quickFormat:true,run:{font:'Arial',size:30,bold:true,color:PINK},paragraph:{spacing:{before:300,after:120},keepNext:true,outlineLevel:0}},
   {id:'Heading2',name:'Heading 2',basedOn:'Normal',next:'Normal',quickFormat:true,run:{font:'Arial',size:23,bold:true,color:NAVY},paragraph:{spacing:{before:200,after:90},keepNext:true,outlineLevel:1}}]},
 numbering:{config:[{reference:'b',levels:[{level:0,format:LevelFormat.BULLET,text:'•',alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:560,hanging:280}}}}]}]},
 sections:[{properties:{page:{size:{width:11906,height:16838},margin:{top:1000,bottom:1000,left:1000,right:1000}}},
  footers:{default:new Footer({children:[new Paragraph({alignment:AlignmentType.CENTER,children:[new TextRun({text:'SupeRR Selector S2 · Round 1 methodology · page ',font:'Arial',size:16,color:'777777'}),new TextRun({children:[PageNumber.CURRENT],font:'Arial',size:16,color:'777777'})]})]})},
  children:kids}]});
Packer.toBuffer(doc).then(b=>{fs.writeFileSync('/Users/aryansinghthakur/Downloads/code/SupeRR_Round1_Methodology_Report.docx',b);console.log('ok')});
