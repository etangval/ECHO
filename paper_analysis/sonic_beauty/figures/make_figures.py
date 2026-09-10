"""Figures and aggregate-only listening analyses for the current manuscript.

No participant-level records or seven-category ratings are reconstructed.
"""
from pathlib import Path
import json, math, re, io, os, tempfile
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from scipy.stats import binomtest, binom, beta

def holm_adjust(values):
    p=np.asarray(values,dtype=float);order=np.argsort(p,kind='stable');m=len(p)
    ordered=np.minimum(1.,np.maximum.accumulate((m-np.arange(m))*p[order]))
    result=np.empty(m);result[order]=ordered
    return result

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent/'keyboard'
TEAL='#176B87'; ORANGE='#C56B3F'; GRAY='#D5DBDF'; DARK='#1C2933'; MUTED='#566573'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10.5,'axes.labelsize':11,
 'axes.titlesize':12,'axes.titleweight':'bold','text.color':DARK,'axes.labelcolor':DARK,
 'xtick.color':DARK,'ytick.color':DARK,'axes.spines.top':False,'axes.spines.right':False,
 'axes.edgecolor':'#AAB4BB','grid.color':'#E4E8EB','pdf.fonttype':42,'ps.fonttype':42,
 'svg.fonttype':'none','savefig.facecolor':'white'})

# Exact aggregate counts read from the current Google document, Section 3.3.
# Each triple is optimized / equal / random. One source pair per completed response.
counts={
 'Sonic beauty':{'Neural spikes':(111,18,24),'Earthquakes':(103,24,26),'X-ray detections':(74,35,38)},
 'Pleasantness':{'Neural spikes':(125,4,24),'Earthquakes':(108,22,23),'X-ray detections':(85,23,39)},
 'Personal preference':{'Neural spikes':(106,15,32),'Earthquakes':(91,39,23),'X-ray detections':(67,34,46)}}
rows=[]
for outcome,domains in counts.items():
    for domain,(o,t,r) in domains.items():rows.append(dict(outcome=outcome,source=domain,optimized=o,equal=t,random=r))
    a=np.array(list(domains.values())).sum(axis=0)
    rows.append(dict(outcome=outcome,source='Pooled',optimized=int(a[0]),equal=int(a[1]),random=int(a[2])))
stats=pd.DataFrame(rows)
stats['total']=stats[['optimized','equal','random']].sum(axis=1)
stats['nonneutral']=stats.optimized+stats.random
stats['optimized_share_all']=stats.optimized/stats.total
stats['optimized_share_nonneutral']=stats.optimized/stats.nonneutral
for idx,row in stats.iterrows():
    k=int(row.optimized);n=int(row.nonneutral)
    stats.loc[idx,'p_exact_two_sided']=binomtest(k,n,p=.5,alternative='two-sided').pvalue
    lo,hi=binomtest(k,n).proportion_ci(confidence_level=.95,method='exact')
    stats.loc[idx,'exact_lower']=lo;stats.loc[idx,'exact_upper']=hi
    # Independent formula checks for the displayed statistics.
    p2=min(1.,2*binom.cdf(min(k,n-k),n,.5))
    assert np.isclose(p2,stats.loc[idx,'p_exact_two_sided'],rtol=1e-12,atol=0)
    assert np.allclose([lo,hi],[beta.ppf(.025,k,n-k+1),beta.ppf(.975,k+1,n-k)],rtol=0,atol=1e-11)
for pooled in [True,False]:
    m=(stats.source=='Pooled')==pooled
    stats.loc[m,'p_holm']=holm_adjust(stats.loc[m,'p_exact_two_sided'])
    stats.loc[m,'holm_family']='3 pooled outcomes' if pooled else '9 source-specific outcomes'
assert stats.query('source == "Pooled"')[['optimized','equal','random']].values.tolist()==[[288,77,88],[318,49,86],[264,88,101]]
assert stats.query('source == "Pooled"').total.tolist()==[453,453,453]
assert all(stats.query('source != "Pooled"').groupby('source').total.nunique()==1)
stats.to_csv(ROOT/'listening_aggregate_statistics.csv',index=False)
pd.DataFrame(rows).to_csv(ROOT/'listening_aggregate_counts.csv',index=False)
q=stats.query('source == "Pooled"')
(ROOT/'statistics_summary.json').write_text(json.dumps({
 'source':'Current manuscript Section 3.3; aggregate counts only',
 'observations':'453 completed responses; independent persons are not verified across devices',
 'null':'P(optimized | non-neutral response) = 0.5',
 'test':'Exact two-sided conditional sign test (binomial with p=0.5)',
 'multiplicity':'Holm separately across 3 pooled outcomes and 9 source-specific outcomes',
 'interval':'95% Clopper–Pearson exact binomial interval for optimized share among non-neutral responses; not simultaneous',
 'not_recomputed':['ordinal-score bootstrap','covariate adjustments','attention and placement sensitivity'],
 'checks':'Domain sums, totals, exact-binomial symmetry, independent beta-quantile interval formula passed',
 'pooled':q.to_dict(orient='records')},indent=2))

registry=[]
def save(fig,number,name,caption):
    stem=f'Figure_{number}_{name}'
    for extension in ('png','pdf','svg'):
        buffer=io.BytesIO()
        fig.savefig(buffer,format=extension,dpi=300)
        data=buffer.getvalue()
        if extension=='pdf' and not data.rstrip().endswith(b'%%EOF'):
            raise ValueError('Incomplete PDF export')
        target=ROOT/(stem+'.'+extension)
        with tempfile.NamedTemporaryFile(dir=ROOT,prefix='.figure_',delete=False) as temporary:
            temporary.write(data);temporary.flush();os.fsync(temporary.fileno())
            temporary_name=temporary.name
        os.replace(temporary_name,target)
        if target.read_bytes()!=data: raise IOError('Figure export differs from rendered bytes')
    registry.append(dict(number=str(number),name=name,stem=stem,caption=caption,width_inches=float(fig.get_figwidth()),height_inches=float(fig.get_figheight()),png=stem+'.png'))
    plt.close(fig)
def label(ax,letter,title):
    ax.text(0,1.065,letter,transform=ax.transAxes,weight='bold',fontsize=14,va='bottom')
    ax.text(.045,1.07,title,transform=ax.transAxes,weight='bold',fontsize=11.5,va='bottom')
def sci(v):
    if v>=.001:return f'{v:.4f}' if v<.1 else f'{v:.3f}'
    power=int(math.floor(math.log10(v)));base=v/(10**power)
    return rf'${base:.2f}\times10^{{{power}}}$'

# Figure 1: explicitly synthetic construction, not a production result.
fig=plt.figure(figsize=(7.2,6.4))
top=fig.add_axes([.075,.80,.88,.15]);top.axis('off')
cards=[('Event record','Times, identities and multiplicity'),('Pitch assignment','One stable, distinct pitch per identity'),('Sound rendering','Shared clock; expressive attributes')]
for i,(title,sub) in enumerate(cards):
    x=i*.35
    top.add_patch(FancyBboxPatch((x,.20),.29,.65,boxstyle='round,pad=0.012,rounding_size=0.03',fc='#EDF4F7',ec='#B6CCD6'))
    top.text(x+.145,.62,title,ha='center',weight='bold',fontsize=10)
    top.text(x+.145,.42,sub.replace('; ',';\n').replace('Times, identities and multiplicity','Times, identities\nand multiplicity').replace('One stable, distinct pitch per identity','One stable, distinct pitch\nper identity'),ha='center',va='center',fontsize=9)
    if i<2:top.annotate('',xy=(x+.335,.52),xytext=(x+.297,.52),arrowprops={'arrowstyle':'->','color':MUTED,'lw':1.4})
top.text(0,1.04,'A  Where creative intervention enters',weight='bold',fontsize=12)
times=np.array([.4,1.1,1.1,2.,2.7,3.8,4.2,4.2,5.3,6.1,7.2,8.0,9.1,9.8])
cats=np.array([0,1,3,2,0,3,1,2,0,2,3,1,0,2]);pitch=np.array([60,67,64,73]);colors=['#176B87','#A55A2A','#65803D','#855C9B']
a=fig.add_axes([.10,.46,.35,.20]);b=fig.add_axes([.60,.46,.35,.20])
for c in range(4):
    t=times[cats==c];a.scatter(t,np.full(len(t),c),marker='|',s=160,linewidths=2.2,color=colors[c]);b.scatter(.5+t/2,np.full(len(t),pitch[c]),marker='|',s=160,linewidths=2.2,color=colors[c])
a.set(xlim=(0,10.3),ylim=(-.6,3.6),yticks=range(4),yticklabels=['A','B','C','D'],xlabel='Source time (s)',ylabel='Category')
b.set(xlim=(.5,5.65),ylim=(57,76),yticks=[60,64,67,73],xlabel='Playback time (s)',ylabel='MIDI pitch')
a.set_title('Prepared events',loc='left',pad=10);b.set_title('Same 14 occurrences',loc='left',pad=10)
fig.text(.075,.735,'B  Event preservation',weight='bold',fontsize=12)


fig.text(.53,.355,r'Illustrative example: $u=0.5+t/2$; 14 occurrences preserved.',ha='center',fontsize=9,color=MUTED)
c=fig.add_axes([.10,.105,.35,.20]);d=fig.add_axes([.55,.10,.40,.22]);d.axis('off')
c.bar(range(4),[.15,.15,.15,0],color=[GRAY,GRAY,GRAY,TEAL],width=.65)
c.text(3,.008,'0',ha='center',color=TEAL,fontsize=10)
c.set(xticks=range(4),xticklabels=['C–E','C–G','E–G','C–E–G'],ylabel='Chord-set cost H',ylim=(0,.20),yticks=[0,.15])
c.tick_params(axis='x',labelsize=9)
d.text(0,.83,'A chord is evaluated as a set.',fontsize=11,weight='bold')
d.text(0,.60,r'$\widehat H(\{C,E,G\})=0-3(0.15)=-0.45$',fontsize=11)
d.text(0,.30,'Nonzero third-order interaction\non the original pitch-class indicators.',fontsize=10)
d.text(0,.04,'Not a perceptual effect size.',fontsize=9,color=MUTED)
fig.text(.075,.318,'C  A higher-order harmonic commitment',weight='bold',fontsize=12)
save(fig,1,'framework','Figure 1. Event-preserving sonification as constrained composition. (A) Pitch relationships and expression are designed while prepared event occurrences remain fixed. (B) A synthetic four-category example illustrates the injective pitch map and common affine clock; colours track category identity. It is a schematic, not an optimised production or participant stimulus. (C) The implemented set energy assigns cost 0.15 to each two-note subset of a C-major triad and zero to the complete triad and singletons. Its third-order Möbius coefficient is −0.45, proving a property of the objective, not a perceptual benefit of that component.')

# Figure 2: all responses and conditional effects, with distinct denominators.
fig=plt.figure(figsize=(7.2,6.5))
a=fig.add_axes([.075,.77,.88,.16]);a.axis('off')
a.text(0,1.08,'A  Blinded paired comparison',fontsize=12,weight='bold')
for x,title,sub in [(0,'453 responses','One 120-s pair per response'),(.35,'Matched conditions','Pitch allocation changed'),(.70,'Three judgements','Beauty · pleasantness · preference')]:
    a.add_patch(FancyBboxPatch((x,.16),.29,.72,boxstyle='round,pad=.01',facecolor='#F1F5F7',edgecolor='#CFD9DF'))
    a.text(x+.145,.63,title,ha='center',weight='bold',fontsize=9.5)
    a.text(x+.145,.38,sub.replace('Beauty · pleasantness · preference','Beauty · pleasantness\n· preference').replace('One 120-s pair per response','One 120-s pair\nper response').replace('Pitch allocation changed','Pitch allocation\nchanged'),ha='center',va='center',fontsize=9)
a.text(0,-.05,'3 source excerpts × 3 random variants × 2 A/B placements',fontsize=9.5,color=MUTED)
ax=fig.add_axes([.25,.435,.70,.235]);out=list(counts);ys=np.arange(3)[::-1]
pooled=stats.query('source == "Pooled"').set_index('outcome').loc[out]
left=np.zeros(3)
for col,color,title in [('optimized',TEAL,'Optimized'),('equal',GRAY,'Equal'),('random',ORANGE,'Random')]:
    vals=pooled[col].values;percent=100*vals/453
    ax.barh(ys,percent,left=left,height=.59,color=color,label=title)
    for y,l,w,n in zip(ys,left,percent,vals):ax.text(l+w/2,y,f'{n}\n({w:.1f}%)',ha='center',va='center',color='white' if col!='equal' else DARK,fontsize=9.5)
    left+=percent
ax.set(yticks=ys,yticklabels=out,xlim=(0,100),xticks=[0,25,50,75,100],xlabel='All completed responses (%)')
ax.tick_params(axis='y',length=0,pad=8);ax.spines['left'].set_visible(False)
fig.legend(*ax.get_legend_handles_labels(),loc='center',bbox_to_anchor=(.62,.687),ncol=3,frameon=False,handlelength=1)
fig.text(.075,.73,'B  Choice distribution (n = 453 for each judgement)',fontsize=12,weight='bold')
ax=fig.add_axes([.25,.095,.48,.215]);ax.axvline(.5,color=MUTED,lw=1,ls='--',zorder=0)
for y,(_,r) in zip(ys,pooled.iterrows()):
    ax.errorbar(r.optimized_share_nonneutral,y,xerr=[[r.optimized_share_nonneutral-r.exact_lower],[r.exact_upper-r.optimized_share_nonneutral]],fmt='o',color=TEAL,ms=6,capsize=3,lw=1.6)
ax.set(yticks=ys,yticklabels=out,xlim=(.45,.92),xticks=[.5,.6,.7,.8,.9],xticklabels=['50','60','70','80','90'],xlabel='Optimized share among non-neutral responses (%)',ylim=(-.55,2.65))
ax.tick_params(axis='y',length=0,pad=8);ax.spines['left'].set_visible(False);ax.grid(axis='x',zorder=-1)
ax.text(1.10,1.05,r'$p_{\rm Holm}$',transform=ax.transAxes,ha='left',fontsize=10,weight='bold')
for y,(_,r) in zip(ys,pooled.iterrows()):
    ax.text(1.10,y,sci(r.p_holm),transform=ax.get_yaxis_transform(),va='center',fontsize=10)
fig.text(.075,.342,'C  Conditional preference (95% exact intervals)',fontsize=12,weight='bold')
save(fig,2,'pooled_listening','Figure 2. Pooled listening results. (A) Design summary; all conditions preserve the prepared onsets and shared expressive attributes, varying categorical pitch allocation. (B) Counts and percentages include all 453 completed responses for each judgement; the three outcomes come from the same respondents. (C) Optimized shares condition on non-neutral responses (n = 376, 404 and 365, respectively); bars are two-sided 95% exact binomial intervals, not multiplicity-adjusted simultaneous intervals. Dashed line: conditional probability 0.5. Exact two-sided sign tests compare the observed optimized and random counts, with Holm correction across three pooled outcomes. Inference concerns responses to the fixed excerpts, not a population of independent musical works.')

# Figure 3: all nine source-specific effects and adjusted tests.
fig=plt.figure(figsize=(7.2,6.4));ax=fig.add_axes([.265,.11,.385,.79])
ax.axvline(.5,color=MUTED,ls='--',lw=1)
positions=[];labs=[];records=[]
for group,outcome in enumerate(out):
    for j,domain in enumerate(counts[outcome]):
        y=10-group*4-j;r=stats[(stats.outcome==outcome)&(stats.source==domain)].iloc[0]
        positions.append(y);labs.append(domain);records.append((y,r))
        ax.errorbar(r.optimized_share_nonneutral,y,xerr=[[r.optimized_share_nonneutral-r.exact_lower],[r.exact_upper-r.optimized_share_nonneutral]],fmt='o',color=TEAL,ms=6,capsize=3,lw=1.6)
    ax.text(-.55,10.65-group*4,outcome,transform=ax.get_yaxis_transform(),weight='bold',fontsize=11)
ax.set(yticks=positions,yticklabels=labs,xlim=(.42,.94),ylim=(-.8,11.35),xticks=[.5,.6,.7,.8,.9],xticklabels=['50','60','70','80','90'])
ax.tick_params(axis='y',length=0,pad=10,labelsize=10);ax.grid(axis='x');ax.spines['left'].set_visible(False)
ax.set_xlabel('Optimized share among\nnon-neutral responses (%)',fontsize=10.5)
ax.text(1.11,11.3,'Opt / equal / rnd',transform=ax.get_yaxis_transform(),fontsize=8.7,ha='center',weight='bold')
ax.text(1.59,11.3,r'$p_{\rm Holm}$',transform=ax.get_yaxis_transform(),fontsize=10,ha='center',weight='bold')
for y,r in records:
    ax.text(1.11,y,f'{r.optimized} / {r.equal} / {r.random}',transform=ax.get_yaxis_transform(),ha='center',va='center',fontsize=9)
    ax.text(1.59,y,sci(r.p_holm),transform=ax.get_yaxis_transform(),ha='center',va='center',fontsize=9.5)
fig.text(.075,.96,'Source-specific listening results',fontsize=14,weight='bold')

save(fig,3,'source_specific_listening','Figure 3. Source-specific listening results. Each source has one fixed excerpt: 153 neural, 153 earthquake and 147 X-ray responses. Points show optimized shares among non-neutral responses; horizontal bars are 95% exact binomial intervals. The right columns retain optimized/equal/random counts and exact two-sided sign-test p values, Holm-corrected jointly across all nine source–outcome comparisons. Intervals are pointwise and have not been adjusted for multiplicity. X-ray personal preference remains inconclusive at the conventional 0.05 threshold (adjusted p = 0.0594), although its beauty and pleasantness contrasts favour optimization. Between-source or between-outcome differences are not themselves tested by comparing separate p values.')

keyboard_source=ROOT/'keyboard_figure_data.csv'
if not keyboard_source.exists():
    keyboard_source=BASE/'comparison_25.csv'
df=pd.read_csv(keyboard_source)
short=['Bach · Prelude','Rameau · Tambourin','Scarlatti · K.455','Mozart · Turkish March','Mozart · K.545 / I','Beethoven · Moonlight / I','Beethoven · Für Elise','Schubert · Op.90/3','Mendelssohn · Op.30/6','Schumann · Träumerei','Chopin · Op.9/2','Liszt · Consolation 3','Brahms · Op.118/2','Grieg · Wedding Day','Debussy · Clair de lune','Debussy · Arabesque 1','Satie · Gymnopédie 1','Bartók · Folk Dance 6','Ravel · Jeux d’eau','Schoenberg · Op.19/6','Scriabin · Op.59/2','Casella · Op.31 (2)','Szymanowski · Op.1 (9)','Berg · Sonata Op.1','Webern · Op.27 (3)']
df['short_label']=short
fig,ax=plt.subplots(figsize=(11,7.2));fig.subplots_adjust(left=.09,right=.61,bottom=.16,top=.88)
ax.scatter(df.X,df.Y,s=53,facecolors='white',edgecolors=TEAL,lw=1.8,zorder=3)
offsets={1:(8,5),2:(-17,5),3:(9,1),4:(8,6),5:(-17,-1),6:(-25,-23),7:(-14,-17),8:(-25,10),9:(8,6),10:(-20,8),11:(-20,7),12:(9,6),13:(-17,-19),14:(9,-3),15:(8,8),16:(9,-3),17:(-18,-14),18:(-11,-18),19:(-20,-17),20:(8,8),21:(8,6),22:(-22,-8),23:(8,8),24:(8,6),25:(8,6)}
for _,r in df.iterrows():ax.annotate(str(int(r.number)),(r.X,r.Y),xytext=offsets[int(r.number)],textcoords='offset points',fontsize=10.5,color=TEAL)
ax.set(xlim=(min(39,df.X.min()-5),95),ylim=(min(44,df.Y.min()-5),97),xticks=range(30,100,10),yticks=range(40,100,10),xlabel='X: chord-template affinity with roughness penalty',ylabel='Y: pitch-distribution continuity')
ax.grid(True,zorder=0);ax.set_axisbelow(True)
fig.text(.075,.95,'ECHO: 25 keyboard selections',fontsize=16,weight='bold')
for i,label in enumerate(short):fig.text(.65,.88-i*.0285,f'{i+1:02d}  {label}',fontsize=9.5,va='center',color=DARK)
fig.text(.075,.045,'Opening excerpts. Cycles are equal-piece means. Higher coordinates indicate greater model affinity or continuity.',fontsize=9,color=MUTED)
save(fig,4,'keyboard_coordinates','Figure 4. Two-dimensional description of 25 keyboard selections. Points use the same descriptor definitions. Excerpts include pickups, where present, and at least eight complete bars. Webern movement I extends to bar 14 (10.5 quarter notes), the shortest complete-bar extension supporting all four temporal scales at both phases; movements II and III use eight bars. Casella, Szymanowski and Webern are equal-piece means of two, nine and three constituents. X combines duration-weighted chord-template affinity with a roughness penalty; Y describes multiscale continuity of aggregate pitch distributions. These are model descriptors, not calibrated listener ratings. Parameter sensitivity is shown in Figure S1.')

# Figure 5: show both axes without ranking or suppressing negative contrasts.
fig,axs=plt.subplots(1,2,figsize=(7.2,8.0),sharey=True,gridspec_kw={'wspace':.22})
fig.subplots_adjust(left=.385,right=.97,bottom=.105,top=.91)
ys=np.arange(len(df))[::-1]
for ax,coord in zip(axs,['X','Y']):
    delta=df[coord]-df['null_'+coord+'_mean']
    ax.barh(ys,delta,color=[TEAL if d>=0 else ORANGE for d in delta],height=.65)
    ax.axvline(0,color=MUTED,lw=1)
    ax.set(yticks=ys,yticklabels=[f'{i+1:02d}  {s}' for i,s in enumerate(short)],xlabel='Original − shuffle mean',ylim=(-.8,len(df)-.2))
    ax.set_title('A  '+r'$\Delta X$' if coord=='X' else 'B  '+r'$\Delta Y$',loc='left',fontsize=12)
    ax.grid(axis='x',zorder=0);ax.set_axisbelow(True);ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0,labelsize=8.8,pad=8)
    ax.tick_params(axis='x',labelsize=9)
fig.text(.075,.955,'Comparison with shuffled note pitches',fontsize=14,weight='bold')

save(fig,5,'keyboard_shuffle_controls','Figure 5. Original-minus-shuffle-mean descriptor differences for all 25 selections. Each excerpt has 99 seeded notehead-pitch permutations with onsets and durations fixed; cycle constituents are shuffled independently and averaged equally. This retains the notehead pitch histogram, not pitch-duration associations or voice identity. The original exceeds its shuffled mean in 20 of 25 selections for X and 22 for Y; negative contrasts are retained. These conditional descriptive controls do not test perceived beauty or establish a population-level ranking of musical periods. Full coordinates and conditional Monte Carlo fractions are supplied with the computational data.')

# Supplementary sensitivity figure: split horizontal and vertical ranges for clarity.
fig,axs=plt.subplots(1,2,figsize=(7.2,8.0),sharey=True,gridspec_kw={'wspace':.22})
fig.subplots_adjust(left=.385,right=.97,bottom=.105,top=.91)
for ax,coord,title in zip(axs,['X','Y'],['Release extension','Temporal scale']):
    for y,(_,r) in zip(ys,df.iterrows()):
        ax.plot([r[coord+'_min'],r[coord+'_max']],[y,y],color='#9DBCCB',lw=2)
        ax.scatter(r[coord],y,color=TEAL,s=20,zorder=2)
    ax.set(yticks=ys,yticklabels=[f'{i+1:02d}  {s}' for i,s in enumerate(short)],xlabel=coord,ylim=(-.8,len(df)-.2),xlim=(25,100),xticks=[25,50,75,100])
    ax.set_title(title,loc='left',fontsize=11);ax.grid(axis='x');ax.set_axisbelow(True);ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0,labelsize=8.8,pad=8);ax.tick_params(axis='x',labelsize=9)
fig.text(.075,.955,'Keyboard descriptor sensitivity',fontsize=14,weight='bold')

save(fig,'S1','keyboard_parameter_sensitivity','Figure S1. Parameter sensitivity. Left: X ranges over release extensions of 0, 0.25, 0.5 and 1 quarter note. Right: Y ranges over four phase-averaged temporal-scale coordinates at 0.5, 1, 2 and 4 quarter notes. Main coordinates are marked by points. Cycle endpoints are equal-piece means of constituent lower and upper endpoints, as specified in the implementation; they need not correspond to a single common parameter across pieces. These ranges are sensitivity summaries, not sampling confidence intervals or estimates of listener uncertainty.')

(ROOT/'figure_registry.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2))
(ROOT/'figure_captions.txt').write_text('\n\n'.join(r['caption'] for r in registry))
df.to_csv(ROOT/'keyboard_figure_data.csv',index=False)
print(stats[['outcome','source','optimized','equal','random','optimized_share_nonneutral','exact_lower','exact_upper','p_holm']].to_string(index=False))
print('Saved',len(registry),'figures in PNG, PDF and SVG.')
