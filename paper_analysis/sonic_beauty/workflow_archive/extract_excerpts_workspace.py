"""Audited-boundary reanalysis; no OMR values enter publication tables.

Run with the repository workspace as cwd. Uses the previously exported
LilyPond note listeners and core_metrics.py, whose license is preserved.
"""
from pathlib import Path
from fractions import Fraction
import csv, re, json, sys, hashlib, shutil
from collections import defaultdict
import numpy as np
import pandas as pd

ROOT=Path('/workspace/scratch/0c9800343be2')
OUT=ROOT/'output/digital_creativity_rewrite'
OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'output/piano_18'))
from analyze import evaluate

def val(s):
    return float(Fraction(re.match(r'[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?:/\d+)?',str(s)).group()))

def chunks(name):
    text=(ROOT/f'analysis/new25build/{name}/events.log').read_text()
    out=[]
    for block in text.split('Preprocessing graphical objects...'):
        rows=[]
        for line in re.findall(r'^EVT\|([^\n]+)',block,re.M):
            t,g,d,p,staff,voice,bar,pos=line.split('|')
            if val(g)!=0:continue
            rows.append(dict(onset=val(t),duration=val(d),pitch=int(p),staff=staff,voice=voice,bar=int(bar),measure_position=val(pos)))
        if rows:out.append(rows)
    return out

def opening(rows):
    # Exact start of full bar 9, rather than its first sounding note.
    starts=[r['onset']-r['measure_position'] for r in rows if r['bar']==9]
    if not starts:raise ValueError('Bar 9 boundary is unavailable')
    if max(starts)-min(starts)>1e-6:raise ValueError('Inconsistent bar boundary')
    end=float(np.mean(starts))
    return [dict(r,duration=min(r['duration'],end-r['onset'])) for r in rows if r['onset']<end-1e-8],end

def aggregate(parts,sensitivity=True):
    z=[evaluate(rows,end,sensitivity=sensitivity) for rows,end in parts]
    keys=z[0]
    # All intended movements and all four scales must be defined.
    if any(not np.isfinite(v[k]) for v in z for k in keys):
        raise ValueError('Undefined score; no silent nan-averaging allowed')
    return {k:float(np.mean([v[k] for v in z])) for k in keys}

def main():
    meta=json.loads((ROOT/'output/piano_18/metadata.json').read_text())
    rows=list(csv.DictReader((ROOT/'output/piano_18/notes.csv').open()))
    for r in rows:
        for k in ['onset','duration','measure_position']:r[k]=float(r[k])
        for k in ['pitch','bar']:r[k]=int(r[k])
    selections=[]
    def add(id,composer,title,parts,source):
        selections.append(dict(id=id,composer=composer,title=title,parts=parts,source=source))
    for m in meta:
        if m['id']=='satie_gnos':continue
        rr=[r for r in rows if r['piece']==m['id']]
        add(m['id'],m['composer'],m['short'],[opening(rr)],m['source_url'])
    br=list(csv.DictReader((ROOT/'output/piano_18/opening_notes.csv').open()))
    br=[r for r in br if r['piece']=='bartok']
    for r in br:
        for k in ['onset','duration','measure_position']:r[k]=float(r[k])
        for k in ['pitch','bar']:r[k]=int(r[k])
    old=pd.read_csv(ROOT/'output/piano_18/opening_results.csv')
    bend=float(old.loc[old.id=='bartok','duration_quarters'].iloc[0])
    add('bartok','Bartók','Romanian Folk Dances No.6',[(br,bend)],'User-supplied PDF; opening manually transcribed in prior analysis')
    df=pd.read_csv(ROOT/'analysis/new_modern/ravel/Ravel_-_Jeux_dEau.notes.tsv',sep='\t')
    rv=[]
    for r in df.itertuples():
        if pd.notna(r.gracenote):continue
        rv.append(dict(onset=val(r.quarterbeats),duration=val(r.duration_qb),pitch=int(r.midi),staff=str(r.staff),voice=str(r.voice),bar=int(r.mn),measure_position=4*val(r.mn_onset)))
    add('ravel_jeux','Ravel','Jeux d’eau',[opening(rv)],'https://github.com/DCMLab/ravel_piano')
    add('schoenberg_19_6','Schoenberg','Op.19 No.6',[opening(chunks('schoenberg')[5])],'Open Scores LilyPond; project attribution in source manifest')
    add('scriabin_59_2','Scriabin','Prelude Op.59 No.2',[opening(chunks('scriabin')[0])],'Mutopia LilyPond; project attribution in source manifest')
    add('casella_31','Casella','Deux Contrastes Op.31',[opening(r) for r in chunks('casella')],'Open Scores LilyPond; both pieces equally weighted')
    add('szymanowski_1','Szymanowski','Nine Preludes Op.1',[opening(r) for r in chunks('szymanowski')],'Open Scores LilyPond; all nine equally weighted')
    results=[];rawnotes=[];nulls=[];manifest=[]
    for i,s in enumerate(selections,1):
        ps=s['parts'];z=aggregate(ps)
        result=dict(number=i,**{k:v for k,v in s.items() if k!='parts'},units=len(ps),notes=sum(len(x[0]) for x in ps),quarters=sum(x[1] for x in ps),**z)
        rng=np.random.default_rng(20260910+i)
        for rep in range(99):
            parts=[]
            for rr,end in ps:
                pitches=rng.permutation([r['pitch'] for r in rr])
                parts.append(([dict(r,pitch=int(p)) for r,p in zip(rr,pitches)],end))
            zz=aggregate(parts,False)
            nulls.append(dict(id=s['id'],replicate=rep,X=zz['X'],Y=zz['Y']))
        ns=[n for n in nulls if n['id']==s['id']]
        for axis in ['X','Y']:
            vals=np.array([n[axis] for n in ns]);result[f'null_{axis}_mean']=float(vals.mean())
            result[f'null_{axis}_sd']=float(vals.std(ddof=1))
            result[f'null_{axis}_tail_fraction']=(1+int((vals>=z[axis]).sum()))/100
        results.append(result)
        for j,(rr,end) in enumerate(ps,1):
            manifest.append(dict(id=s['id'],unit=j,end_quarters=end,notes=len(rr),scope='pickup, if any, plus full bars 1–8',source=s['source']))
            rawnotes.extend(dict(selection=s['id'],unit=j,**{k:r[k] for k in ['onset','duration','pitch','staff','voice','bar','measure_position']}) for r in rr)
        print(i,s['composer'],round(z['X'],2),round(z['Y'],2),flush=True)
    assert len(results)==23
    for name,data in [('comparison_23',results),('analysis_notes',rawnotes),('permutation_controls',nulls),('excerpt_manifest',manifest)]:
        pd.DataFrame(data).to_csv(OUT/(name+'.csv'),index=False)
    (OUT/'analysis_parameters.json').write_text(json.dumps(dict(release_tail=.5,release_sensitivity=[0,.25,.5,1],transport_spans=[.5,1,2,4],phases=[0,.5],controls=99,seed_base=20260910,unit='quarter note',coverage_policy='at least two distinct absolute pitches',aggregation='equal arithmetic mean of individual-unit X and Y',excluded=['Berg Op.1: unverified full OMR','Webern Op.27: unverified full OMR; prior movement assignment invalid']),indent=2))
    print(pd.DataFrame(results)[['composer','title','X','Y','null_X_mean','null_Y_mean']].round(2).to_string(index=False))

if __name__=='__main__':main()
