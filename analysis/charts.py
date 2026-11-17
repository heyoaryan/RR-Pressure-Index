"""Report charts (PNG) from ../dashboard_data.json → analysis/fig_*.png"""
import json, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
D=json.load(open('../dashboard_data.json'))
PINK,NAVY,GREY='#c2185b','#1d2c5e','#9a9a96'
plt.rcParams.update({'font.family':'Arial','font.size':9,'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#888','axes.titlesize':10,'axes.titleweight':'bold'})

# 1. where pressure balls happen
fig,ax=plt.subplots(1,2,figsize=(8.2,2.9),gridspec_kw={'width_ratios':[1.6,1]})
for inn,c,l in ((1,PINK,'1st innings'),(2,NAVY,'2nd innings (chase)')):
    v=D['by_over'][str(inn)]; ax[0].plot(range(1,len(v)+1),v,'o-',ms=3.5,lw=1.6,color=c,label=l)
ax[0].set_xlabel('Over'); ax[0].set_ylabel('% of deliveries flagged'); ax[0].set_title('Share of balls that are pressure balls, by over'); ax[0].legend(frameon=False); ax[0].set_xticks(range(1,21,2))
lab=[p[0] for p in D['phase']][::-1]; val=[p[1] for p in D['phase']][::-1]
ax[1].barh(lab,val,color=[NAVY,PINK,GREY,GREY,GREY],height=.6)
for i,v in enumerate(val): ax[1].text(v+.4,i,f'{v:.1f}%',va='center',fontsize=8)
ax[1].set_title('By phase / innings'); ax[1].set_xlim(0,max(val)*1.25); ax[1].tick_params(axis='y',length=0)
plt.tight_layout(); plt.savefig('fig_where.png',dpi=200); plt.close()

# 2. WP calibration
fig,ax=plt.subplots(figsize=(3.6,3.2))
for inn,c,l in (('1',PINK,'1st innings'),('2',NAVY,'2nd innings')):
    pts=D['overview']['calib'][inn]; ax.plot([p[0] for p in pts],[p[1] for p in pts],'o-',ms=4,color=c,label=l)
ax.plot([0,1],[0,1],'--',color=GREY,lw=1); ax.set_xlabel('Predicted win probability (out-of-fold)'); ax.set_ylabel('Actual win rate')
ax.set_title('Win-probability calibration'); ax.legend(frameon=False,loc='upper left'); ax.set_aspect('equal')
plt.tight_layout(); plt.savefig('fig_calib.png',dpi=200); plt.close()

# 3. pressure vs normal scatter
fig,axs=plt.subplots(1,2,figsize=(8.2,3.9))
for ax,role,t in zip(axs,('bat','bowl'),('Batters','Bowlers')):
    P=D['scatter_'+role]; o=[p for p in P if not p[3]]; h=[p for p in P if p[3]]
    ax.scatter([p[1] for p in o],[p[2] for p in o],s=12,color=GREY,alpha=.55,lw=0,label='Other eligible')
    ax.scatter([p[1] for p in h],[p[2] for p in h],s=28,color=PINK,edgecolor='white',lw=.8,label='Our top 10',zorder=3)
    lo=min(min(p[1] for p in P),min(p[2] for p in P))-3; hi=max(max(p[1] for p in P),max(p[2] for p in P))+3
    ax.plot([lo,hi],[lo,hi],'--',color='#555',lw=1); ax.set_xlim(lo,hi); ax.set_ylim(lo,hi)
    placed=[]
    for p in sorted(h,key=lambda p:-p[2]):
        y=p[2]
        while any(abs(y-q[1])<2.2*(hi-lo)/60 and abs(p[1]-q[0])<(hi-lo)/5 for q in placed): y-=(hi-lo)/60
        placed.append((p[1],y)); moved=abs(y-p[2])>1e-9
        ax.annotate(p[0].split()[-1],(p[1],p[2]),xytext=(p[1]+(hi-lo)/(25 if moved else 80),y),fontsize=6.8,va='center',
                    arrowprops=dict(arrowstyle='-',color='#999',lw=.5,shrinkA=0,shrinkB=3) if moved else None)
    ax.set_title(t); ax.set_xlabel('Normal rating (runs per 100 balls vs average)'); ax.set_ylabel('Pressure rating (per 100 balls)')
    ax.text(lo+(hi-lo)*.03,hi-(hi-lo)*.06,'above line = better under pressure',fontsize=7,color='#555')
axs[0].legend(frameon=False,loc='lower right',fontsize=7)
plt.tight_layout(); plt.savefig('fig_scatter.png',dpi=200); plt.close()
print('charts written')
